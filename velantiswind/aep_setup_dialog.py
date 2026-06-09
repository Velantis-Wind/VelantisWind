# -*- coding: utf-8 -*-
"""
ag/aep_setup_dialog.py

Diálogo para:
- Definir modelos (turbinas) y escoger CSV de coordenadas por modelo.
- Crear capas de puntos "{Modelo} (CSV)".
- Calcular AEP y VOLCAR resultados en esas capas:
    * Botón normal  -> ag_core.aep_compute.compute_and_update
"""

from typing import List, Dict, Any, Optional, Tuple
import os, csv, importlib, sys, re, copy, traceback

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import QVariant, QUrl
from qgis.PyQt.QtGui import QIcon, QPixmap, QDesktopServices

from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsLayerTreeGroup, QgsWkbTypes, edit
)
from qgis.utils import iface

# Mapa interactivo (click para añadir/borrar turbinas)
try:
    from .mapa_interactivo import _TurbineInteractiveTool
except Exception:
    _TurbineInteractiveTool = None  # type: ignore

# Caja de herramientas (QDockWidget) para el modo Mapa Interactivo
try:
    from .mapa_interactivo_dock import InteractiveMapDock
except Exception:
    InteractiveMapDock = None  # type: ignore

from .ag_core import export_results
from .results_dialog import AEPResultsDialog, ScenarioComparisonDialog
from .i18n import apply_i18n, install_runtime_i18n_patches, tr_text as _tr
from .ui_core.responsive import fit_to_screen, configure_scroll_area

# El flujo de cálculo AEP se delega bajo demanda en energy_core.dialog_controller
# para que abrir la ventana no fuerce la lógica de ejecución ni el motor PyWake.

# Conector WRG (WAsP Resource Grid): lector de metadatos. (En este paso solo usamos meta/validación)
try:
    from .ag_core.wrg_reader import read_wrg_meta  # type: ignore
except Exception:
    read_wrg_meta = None  # type: ignore

# Perímetro visual del recurso eólico cargado (WRG o WAsP/Surfer grids).
try:
    from .ag_core.qgis_io.resource_extent import (
        clear_resource_extent_layers,
        show_wasp_resource_extent,
        show_wrg_resource_extent,
    )
except Exception:
    clear_resource_extent_layers = None  # type: ignore
    show_wasp_resource_extent = None  # type: ignore
    show_wrg_resource_extent = None  # type: ignore

_GROUP_NAME = "AEP · Coordenadas por modelo"


def _debug_print(message: str) -> None:
    """Optional console diagnostics enabled with VELANTISWIND_DEBUG=1."""
    try:
        if os.environ.get("VELANTISWIND_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(message)
    except Exception:
        pass

# ------------------- utils -------------------
def _preview_csv_header(path: str) -> List[str]:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            return [c.strip() for c in (next(r, []) or [])]
    except Exception:
        return []


def _read_xy_csv(path: str) -> List[Tuple[float, float]]:
    pts = []
    with open(path, newline="", encoding="utf-8") as f:
        sn = csv.Sniffer()
        sample = f.read(2048)
        f.seek(0)
        try:
            has_header = sn.has_header(sample)
        except Exception:
            has_header = False
        r = csv.reader(f)
        if has_header:
            header = next(r, None) or []
            norm = [str(h).strip().lower() for h in header]
            ix = norm.index("x") if "x" in norm else (norm.index("easting") if "easting" in norm else 0)
            iy = norm.index("y") if "y" in norm else (norm.index("northing") if "northing" in norm else 1)
        else:
            ix, iy = 0, 1
        for row in r:
            if len(row) < 2:
                continue
            try:
                x = float(row[ix])
                y = float(row[iy])
                pts.append((x, y))
            except Exception:
                try:
                    x = float(row[0])
                    y = float(row[1])
                    pts.append((x, y))
                except Exception:
                    continue
    return pts


def _project_crs_authid() -> str:
    try:
        return QgsProject.instance().crs().authid() or "EPSG:25830"
    except Exception:
        return "EPSG:25830"


def _ensure_group(root) -> QgsLayerTreeGroup:
    for c in root.children():
        if isinstance(c, QgsLayerTreeGroup) and c.name() == _GROUP_NAME:
            return c
    return root.addGroup(_GROUP_NAME)


def _iter_project_vector_layers() -> List[QgsVectorLayer]:
    """Devuelve capas vectoriales en orden visual del árbol de capas.

    `QgsProject.mapLayers()` también contiene capas dentro de grupos, pero no
    respeta necesariamente la selección/orden visible del panel de capas. Para
    el mapa interactivo interesa recorrer primero el árbol real y después añadir
    cualquier capa huérfana como fallback.
    """
    layers: List[QgsVectorLayer] = []
    seen = set()

    def walk(node) -> None:
        try:
            children = node.children()
        except Exception:
            children = []
        for child in children:
            lyr = None
            try:
                lyr = child.layer()
            except Exception:
                lyr = None
            if isinstance(lyr, QgsVectorLayer):
                try:
                    lid = lyr.id()
                except Exception:
                    lid = id(lyr)
                if lid not in seen:
                    seen.add(lid)
                    layers.append(lyr)
            walk(child)

    try:
        walk(QgsProject.instance().layerTreeRoot())
    except Exception:
        pass

    try:
        for lyr in QgsProject.instance().mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer):
                continue
            try:
                lid = lyr.id()
            except Exception:
                lid = id(lyr)
            if lid not in seen:
                seen.add(lid)
                layers.append(lyr)
    except Exception:
        pass

    return layers


def _is_point_vector_layer(layer) -> bool:
    try:
        return (
            isinstance(layer, QgsVectorLayer)
            and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PointGeometry
        )
    except Exception:
        return False


def _find_layer_by_name(name: str) -> Optional[QgsVectorLayer]:
    for lyr in _iter_project_vector_layers():
        try:
            if lyr.name() == name:
                return lyr
        except Exception:
            continue
    return None


def _unique_layer_name(base_name: str) -> str:
    """Devuelve un nombre libre en el proyecto sin borrar capas existentes."""
    base = str(base_name or "Capa").strip() or "Capa"
    if _find_layer_by_name(base) is None:
        return base
    n = 2
    while True:
        candidate = f"{base} #{n}"
        if _find_layer_by_name(candidate) is None:
            return candidate
        n += 1


def _create_or_refresh_point_layer(
    layer_name: str,
    points: List[Tuple[float, float]],
    model_name: str,
    hub_height: Optional[float] = None,
    diameter: Optional[float] = None,
    coords_csv: str = "",
    model_index: Optional[int] = None,
    create_new: bool = False,
    generation: Optional[int] = None,
) -> QgsVectorLayer:
    # Modo clásico: reutiliza/actualiza la capa del modelo.
    # Modo create_new: crea SIEMPRE una capa nueva con nombre único para poder
    # construir parques multi-modelo sin machacar capas anteriores.
    actual_layer_name = _unique_layer_name(layer_name) if create_new else layer_name
    lyr = None if create_new else _find_layer_by_name(layer_name)
    crs = _project_crs_authid()

    if lyr is None:
        lyr = QgsVectorLayer(f"Point?crs={crs}", actual_layer_name, "memory")
        prov = lyr.dataProvider()
        prov.addAttributes([QgsField("model", QVariant.String)])
        lyr.updateFields()
        QgsProject.instance().addMapLayer(lyr, False)
        _ensure_group(QgsProject.instance().layerTreeRoot()).addLayer(lyr)

    # (Re)cargar geometrías
    prov = lyr.dataProvider()
    with edit(lyr):
        prov.truncate()
        feats = []
        for (x, y) in points:
            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(x), float(y))))
            f["model"] = model_name
            feats.append(f)
        prov.addFeatures(feats)
    # Metadatos ligeros para otros módulos del plugin (ruido, sombras, etc.)
    try:
        lyr.setCustomProperty("velantis/layer_role", "energy_turbines")
        lyr.setCustomProperty("velantis/model_name", str(model_name or ""))
        if model_index is not None:
            lyr.setCustomProperty("velantis/model_index", int(model_index))
            lyr.setCustomProperty("velantis/row_index", int(model_index))
        if generation is not None:
            lyr.setCustomProperty("velantis/layer_generation", int(generation))
        if hub_height is not None:
            lyr.setCustomProperty("velantis/hub_height_m", float(hub_height))
        if diameter is not None:
            lyr.setCustomProperty("velantis/diameter_m", float(diameter))
        if coords_csv:
            lyr.setCustomProperty("velantis/coords_csv", str(coords_csv))
    except Exception:
        pass

    lyr.triggerRepaint()
    return lyr


# ------------------- Diálogo principal -------------------
class AEPSetupDialog(QtWidgets.QDialog):
    """
    Devuelve:
      - modelos: [{'name': str, 'wt': object, 'meta': dict|None, 'coords_csv': str}, ...]
      - wasp_dir: str
    """

    def __init__(self, parent=None, custom_dialog_factory=None, default_wasp_dir: Optional[str] = None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self.setWindowTitle(_tr("Calcular AEP · Modelos, coordenadas y recurso eólico"))
        # Icono del diálogo (el de la esquina superior izquierda / barra de tareas)
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumWidth(880)
        self.setSizeGripEnabled(True)

        self._custom_dialog_factory = custom_dialog_factory
        self._qsettings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self._last_wasp_dir = default_wasp_dir or self._qsettings.value("last_wasp_dir", "", type=str)
        self._last_csv_dir = self._qsettings.value("last_csv_dir", "", type=str)
        self._last_wrg_path = self._qsettings.value("last_wrg_path", "", type=str)
        self._last_wrg_ti_path = self._qsettings.value("last_wrg_ti_path", "", type=str)
        self._last_wfm_engine = self._qsettings.value("last_wfm_engine", "PDW", type=str)
        self._last_wake_deficit = self._qsettings.value("last_wake_deficit", "BG", type=str)
        self._last_rotor_avg_model = self._qsettings.value("last_rotor_avg_model", "CGI7", type=str)
        self._last_superposition_model = self._qsettings.value("last_superposition_model", "AUTO", type=str)
        self._last_fixed_ti_percent = self._qsettings.value("last_fixed_ti_percent", 10.0, type=float)
        self._last_blockage_deficit = self._qsettings.value("last_blockage_deficit", "NONE", type=str)
        self._last_turbulence_model = self._qsettings.value("last_turbulence_model", "NONE", type=str)

        # estado auxiliar: restaurar bloqueo tras salir de PDW
        self._blockage_before_pdw = self._last_blockage_deficit

        self._rows: List[Dict[str, Any]] = []

        # --- estado: mapa interactivo ---
        try:
            self._canvas = iface.mapCanvas()
        except Exception:
            self._canvas = None
        self._interactive_tool = None
        self._interactive_prev_tool = None
        self._dirty_turbine_layer_ids = set()
        # Última capa de turbinas elegida/creada por fila del diálogo.
        # Es importante cuando existen varias capas del mismo modelo en el
        # proyecto: el cálculo debe usar la capa que el usuario acaba de crear
        # o activar, no la primera capa antigua que encuentre por nombre.
        self._interactive_layer_id_by_row: Dict[int, str] = {}
        # Selección one-shot de capas elegidas en el dock antes de recalcular AEP.
        self._selected_turbine_layer_ids_for_next_compute: List[str] = []
        self._energy_layer_generation = 0
        self._interactive_msg_item = None
        self._interactive_msg_widget = None
        self._interactive_dock = None
        self._hidden_for_interactive = False

        # --- estado: comparador de escenarios A/B ---
        self._last_aep_result = None
        self._last_aep_label = "Último cálculo"
        self._scenario_a = None
        self._scenario_b = None

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        self._scroll_area = QtWidgets.QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._scroll_content = QtWidgets.QWidget()
        self._scroll_area.setWidget(self._scroll_content)
        outer_layout.addWidget(self._scroll_area, 1)

        root = QtWidgets.QVBoxLayout(self._scroll_content)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --------- Barra superior: volver al hub (igual que Ruido/Sombras) ---------
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        self.btn_return_hub = QtWidgets.QPushButton("← Inicio")
        self.btn_return_hub.setObjectName("aepBackButton")
        self.btn_return_hub.setToolTip(
            "Cierra el módulo de energía y vuelve al hub principal de Velantis Wind "
            "sin borrar las capas ni los resultados cargados en el proyecto."
        )
        self.btn_refresh_project = QtWidgets.QPushButton("Actualizar")
        self.btn_refresh_project.setObjectName("aepRefreshButton")
        self.btn_refresh_project.setToolTip("Refresca el estado de capas/modelos detectados en el proyecto.")
        self.btn_pywake_docs = QtWidgets.QPushButton("Documentación PyWake")
        self.btn_pywake_docs.setToolTip("Abre la documentación oficial de PyWake, base del cálculo AEP y de estelas del módulo de Energía.")
        self.btn_pywake_docs.clicked.connect(self._open_pywake_docs)
        top.addWidget(self.btn_return_hub)
        top.addWidget(self.btn_refresh_project)
        top.addWidget(self.btn_pywake_docs)
        top.addStretch(1)
        root.addLayout(top)

        # --------- Cabecera corporativa ---------
        hero = QtWidgets.QHBoxLayout()
        hero.setSpacing(16)

        hero_text = QtWidgets.QVBoxLayout()
        hero_text.setSpacing(6)
        title = QtWidgets.QLabel("Energía · AEP del parque")
        title.setObjectName("aepTitle")
        hero_text.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Cálculo de AEP con PyWake: define los modelos de aerogenerador, "
            "selecciona el recurso eólico (WAsP/Surfer grids o WRG), elige los modelos físicos "
            "(estela, turbulencia, bloqueo, rotor-average) y lanza el cálculo. "
            "Los resultados se vuelcan automáticamente sobre las capas de coordenadas del proyecto."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("aepSubtitle")
        hero_text.addWidget(subtitle)
        hero.addLayout(hero_text, 1)
        hero.addStretch(1)

        self._brand_logo_header = QtWidgets.QLabel(self)
        self._brand_logo_header.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self._brand_logo_header.setMinimumWidth(190)
        hero.addWidget(self._brand_logo_header, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        root.addLayout(hero)

        # --------- Logo Velantis ---------
        # Nota: se renderiza en la botonera inferior (izquierda) para no consumir altura arriba.
        self._vortex_logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'velantiswind_logo.png')
        self._vortex_logo_pix = None
        if os.path.exists(self._vortex_logo_path):
            try:
                self._vortex_logo_pix = QPixmap(self._vortex_logo_path)
                if self._vortex_logo_pix is not None and not self._vortex_logo_pix.isNull():
                    self._brand_logo_header.setPixmap(
                        self._vortex_logo_pix.scaled(220, 220, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    )
                    self._brand_logo_header.setToolTip('Velantis Wind')
            except Exception:
                self._vortex_logo_pix = None

        # --------- Modelos ---------
        grp_models = QtWidgets.QGroupBox("Modelos de aerogenerador")
        v_models = QtWidgets.QVBoxLayout(grp_models)

        form_top = QtWidgets.QFormLayout()
        self.sp_n = QtWidgets.QSpinBox()
        self.sp_n.setRange(1, 10)
        self.sp_n.setValue(1)
        self.sp_n.valueChanged.connect(self._rebuild_rows)
        form_top.addRow("Número de modelos:", self.sp_n)
        v_models.addLayout(form_top)

        self.rows_box = QtWidgets.QVBoxLayout()
        v_models.addLayout(self.rows_box)
        root.addWidget(grp_models)

        # --------- Recurso eólico (WAsP / WRG) ---------
        grp_resource = QtWidgets.QGroupBox("Recurso eólico (WAsP grids / WRG)")
        v_resource = QtWidgets.QVBoxLayout(grp_resource)

        # WAsP / Surfer grids
        h_wasp = QtWidgets.QHBoxLayout()
        self.ed_dir = QtWidgets.QLineEdit(self._last_wasp_dir)
        self.btn_pick_dir = QtWidgets.QPushButton("Elegir carpeta…")
        self.btn_union_recurso = QtWidgets.QPushButton("Unir recurso")

        self.btn_pick_dir.clicked.connect(self._pick_dir)
        self.btn_union_recurso.clicked.connect(self._open_union_recurso)

        h_wasp.addWidget(QtWidgets.QLabel("Grids WAsP/Surfer:"))
        h_wasp.addWidget(self.ed_dir, 1)
        h_wasp.addWidget(self.btn_pick_dir, 0)
        h_wasp.addWidget(self.btn_union_recurso, 0)
        v_resource.addLayout(h_wasp)

        note_wasp = QtWidgets.QLabel(
            "Selecciona una carpeta con grids WAsP/Surfer compatibles con PyWake. "
            "Si el recurso ya viene preparado en formato pywake_compat, el plugin lo priorizará automáticamente."
        )
        note_wasp.setWordWrap(True)
        note_wasp.setStyleSheet("color: #666;")
        v_resource.addWidget(note_wasp)

        # WRG / ZIP resource grids
        h_wrg = QtWidgets.QHBoxLayout()
        self.ed_wrg = QtWidgets.QLineEdit(self._last_wrg_path)
        self.btn_pick_wrg = QtWidgets.QPushButton("Elegir WRG/ZIP…")
        self.btn_clear_wrg = QtWidgets.QPushButton("Limpiar")
        self.btn_pick_wrg.clicked.connect(self._pick_wrg)
        self.btn_clear_wrg.clicked.connect(self._clear_wrg)

        h_wrg.addWidget(QtWidgets.QLabel("WRG/ZIP:"))
        h_wrg.addWidget(self.ed_wrg, 1)
        h_wrg.addWidget(self.btn_pick_wrg, 0)
        h_wrg.addWidget(self.btn_clear_wrg, 0)
        v_resource.addLayout(h_wrg)

        self.lbl_wrg_meta = QtWidgets.QLabel("")
        self.lbl_wrg_meta.setWordWrap(True)
        self.lbl_wrg_meta.setStyleSheet("color: #666;")
        v_resource.addWidget(self.lbl_wrg_meta)

        # Visualización GIS del dominio espacial del recurso cargado.
        h_resource_extent = QtWidgets.QHBoxLayout()
        self.cb_show_resource_extent = QtWidgets.QCheckBox("Mostrar perímetro del recurso en el mapa")
        self.cb_show_resource_extent.setChecked(True)
        self.cb_show_resource_extent.setToolTip(
            "Dibuja una capa temporal con los límites del WRG o de los grids WAsP/Surfer. "
            "Sirve para comprobar si el layout queda dentro del dominio del recurso."
        )
        self.btn_refresh_resource_extent = QtWidgets.QPushButton("Actualizar perímetro")
        self.btn_clear_resource_extent = QtWidgets.QPushButton("Limpiar perímetro")
        self.btn_refresh_resource_extent.setToolTip("Vuelve a dibujar el perímetro del recurso eólico seleccionado.")
        self.btn_clear_resource_extent.setToolTip("Elimina del proyecto la capa temporal del perímetro del recurso.")
        self.btn_refresh_resource_extent.clicked.connect(lambda: self._draw_current_resource_extent(zoom=False, manual=True))
        self.btn_clear_resource_extent.clicked.connect(self._clear_resource_extent)
        h_resource_extent.addWidget(self.cb_show_resource_extent, 1)
        h_resource_extent.addWidget(self.btn_refresh_resource_extent, 0)
        h_resource_extent.addWidget(self.btn_clear_resource_extent, 0)
        v_resource.addLayout(h_resource_extent)

        self.lbl_resource_extent = QtWidgets.QLabel("")
        self.lbl_resource_extent.setWordWrap(True)
        self.lbl_resource_extent.setStyleSheet("color: #666;")
        v_resource.addWidget(self.lbl_resource_extent)

        h_wrg_ti = QtWidgets.QHBoxLayout()
        self.ed_wrg_ti = QtWidgets.QLineEdit(self._last_wrg_ti_path)
        self.btn_pick_wrg_ti = QtWidgets.QPushButton("Elegir raster(s) TI…")
        self.btn_clear_wrg_ti = QtWidgets.QPushButton("Limpiar")
        self.btn_wrg_ti_help = QtWidgets.QToolButton()
        try:
            self.btn_wrg_ti_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_wrg_ti_help.setText("?")
        self.btn_wrg_ti_help.setAutoRaise(True)
        self.btn_wrg_ti_help.setToolTip("Explica qué es la TI, cuándo usar raster de turbulencia y cómo afecta al AEP")
        self.btn_pick_wrg_ti.clicked.connect(self._pick_wrg_ti)
        self.btn_clear_wrg_ti.clicked.connect(self._clear_wrg_ti)
        self.btn_wrg_ti_help.clicked.connect(self._show_wrg_ti_help)

        h_wrg_ti.addWidget(QtWidgets.QLabel("Raster(s) de turbulencia TI (opcional):"))
        h_wrg_ti.addWidget(self.btn_wrg_ti_help, 0)
        h_wrg_ti.addWidget(self.ed_wrg_ti, 1)
        h_wrg_ti.addWidget(self.btn_pick_wrg_ti, 0)
        h_wrg_ti.addWidget(self.btn_clear_wrg_ti, 0)
        v_resource.addLayout(h_wrg_ti)

        h_wrg_ti_h = QtWidgets.QHBoxLayout()
        self.ed_wrg_ti_heights = QtWidgets.QLineEdit()
        self.ed_wrg_ti_heights.setPlaceholderText("Opcional: altura de cada raster TI, ej. 90;120")
        self.ed_wrg_ti_heights.setToolTip(
            "Altura manual de cada raster TI, en el mismo orden que los archivos. "
            "Útil si el nombre del archivo no indica claramente 90 m, 120 m, etc."
        )
        try:
            self.ed_wrg_ti_heights.setText(self._qsettings.value("last_wrg_ti_heights", "", type=str))
        except Exception:
            pass
        self.ed_wrg_ti_heights.textChanged.connect(self._update_wrg_ti_meta)
        h_wrg_ti_h.addWidget(QtWidgets.QLabel("Alturas de TI por archivo [m]:"))
        h_wrg_ti_h.addWidget(self.ed_wrg_ti_heights, 1)
        v_resource.addLayout(h_wrg_ti_h)

        self.lbl_wrg_ti_meta = QtWidgets.QLabel("")
        self.lbl_wrg_ti_meta.setWordWrap(True)
        self.lbl_wrg_ti_meta.setStyleSheet("color: #666;")
        v_resource.addWidget(self.lbl_wrg_ti_meta)

        h_fixed_ti = QtWidgets.QHBoxLayout()
        self.sp_fixed_ti = QtWidgets.QDoubleSpinBox()
        self.sp_fixed_ti.setRange(3.0, 30.0)
        self.sp_fixed_ti.setDecimals(1)
        self.sp_fixed_ti.setSingleStep(0.5)
        try:
            self.sp_fixed_ti.setValue(float(self._last_fixed_ti_percent))
        except Exception:
            self.sp_fixed_ti.setValue(10.0)
        self.sp_fixed_ti.setSuffix(" %")
        self.sp_fixed_ti.setToolTip(
            "Valor de turbulencia ambiente que se usa si no cargas un raster TI. "
            "Ejemplo: 10 % significa TI = 0.10 dentro del Site de PyWake."
        )
        self.sp_fixed_ti.valueChanged.connect(self._persist_fixed_ti_percent)
        self.sp_fixed_ti.valueChanged.connect(lambda *_: self._update_wrg_ti_meta())
        h_fixed_ti.addWidget(QtWidgets.QLabel("TI ambiente manual si no hay raster:"))
        h_fixed_ti.addWidget(self.sp_fixed_ti, 0)
        h_fixed_ti.addStretch(1)
        v_resource.addLayout(h_fixed_ti)

        note_wrg = QtWidgets.QLabel(
            "El recurso eólico describe el viento que llega al parque antes de aplicar estelas: "
            "frecuencia por dirección, velocidades y, según el formato, parámetros Weibull. "
            "Puedes usar WAsP/Surfer grids o WRG/ZIP. Si aportas varios WRG a distintas alturas, "
            "PyWake podrá interpolar por altura cuando sea necesario."
        )
        note_wrg.setWordWrap(True)
        note_wrg.setStyleSheet("color: #666;")
        v_resource.addWidget(note_wrg)

        note_ti = QtWidgets.QLabel(
            "La TI es la intensidad de turbulencia ambiente: una medida de lo variable o 'mezclado' que llega el viento al rotor. "
            "Si no cargas raster TI, se usa el valor manual de arriba como hipótesis uniforme. "
            "La TI no siempre cambia mucho el AEP: se nota sobre todo en modelos TI-sensitive como Niayifar, Zong, TurboGaussian o TurboNOJ. "
            f"Los raster(s) TI se reproyectarán al CRS del proyecto actual ({_project_crs_authid()}) si hace falta."
        )
        note_ti.setWordWrap(True)
        note_ti.setStyleSheet("color: #666;")
        v_resource.addWidget(note_ti)

        # Refrescar metadatos si ya había rutas persistidas
        self._update_wrg_meta()
        self._update_wrg_ti_meta()

        root.addWidget(grp_resource)


        # --------- Modelo PyWake (WFM) ---------
        grp_engine = QtWidgets.QGroupBox("Motor de cálculo PyWake")
        v_engine = QtWidgets.QVBoxLayout(grp_engine)
        lbl_engine = QtWidgets.QLabel("¿Cómo se calculan las interacciones entre turbinas?")
        self.cb_wfm_engine = QtWidgets.QComboBox()
        self.cb_wfm_engine.addItem("All2AllIterative", "A2A")
        self.cb_wfm_engine.addItem("PropagateDownwind", "PDW")
        self.cb_wfm_engine.addItem("PropagateUpDownIterative", "PUD")
        v_engine.addWidget(lbl_engine)
        v_engine.addWidget(self.cb_wfm_engine)
        # Nota: compatibilidad PyWake
        self.lbl_engine_note = QtWidgets.QLabel("")
        self.lbl_engine_note.setWordWrap(True)
        self.lbl_engine_note.setStyleSheet("color: #666;")
        v_engine.addWidget(self.lbl_engine_note)
        self._set_wfm_engine_combo(self._last_wfm_engine)
        self.cb_wfm_engine.currentIndexChanged.connect(self._persist_wfm_engine)
        self.cb_wfm_engine.currentIndexChanged.connect(self._update_blockage_lock_for_engine)
        self.cb_wfm_engine.currentIndexChanged.connect(self._update_engine_note_for_wfm)
        self.cb_wfm_engine.currentIndexChanged.connect(self._update_wake_turb_note)
        root.addWidget(grp_engine)
        self._update_engine_note_for_wfm()

        # --------- Wake deficit model (PyWake) ---------
        grp_def = QtWidgets.QGroupBox("Modelo de estela: pérdida de velocidad")
        v_def = QtWidgets.QVBoxLayout(grp_def)
        def_head = QtWidgets.QHBoxLayout()
        lbl_def = QtWidgets.QLabel("¿Cómo se calcula la pérdida de velocidad detrás de cada turbina?")
        self.btn_wake_turb_help = QtWidgets.QToolButton()
        try:
            self.btn_wake_turb_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_wake_turb_help.setText("?")
        self.btn_wake_turb_help.setAutoRaise(True)
        self.btn_wake_turb_help.setToolTip("Explica qué es una estela y qué cambia entre modelos")
        self.btn_wake_turb_help.clicked.connect(self._show_wake_turb_help)
        def_head.addWidget(lbl_def)
        def_head.addWidget(self.btn_wake_turb_help, 0)
        def_head.addStretch(1)
        self.cb_wake_deficit = QtWidgets.QComboBox()
        self.cb_wake_deficit.addItem("NOJDeficit", "NOJ")
        self.cb_wake_deficit.addItem("TurboNOJDeficit", "TNOJ")
        self.cb_wake_deficit.addItem("BastankhahGaussianDeficit", "BG")
        self.cb_wake_deficit.addItem("NiayifarGaussianDeficit", "NIA")
        self.cb_wake_deficit.addItem("TurboGaussianDeficit", "TG")
        self.cb_wake_deficit.addItem("ZongGaussianDeficit", "ZG")
        self.cb_wake_deficit.setToolTip("Modelo que estima cuánto viento pierde una turbina cuando está dentro de la estela de otra. Algunos modelos usan la turbulencia TI y otros apenas la notan.")
        v_def.addLayout(def_head)
        v_def.addWidget(self.cb_wake_deficit)
        self.lbl_wake_turb_note = QtWidgets.QLabel("")
        self.lbl_wake_turb_note.setWordWrap(True)
        self.lbl_wake_turb_note.setStyleSheet("color: #666;")
        v_def.addWidget(self.lbl_wake_turb_note)
        self._set_wake_deficit_combo(self._last_wake_deficit)
        self.cb_wake_deficit.currentIndexChanged.connect(self._persist_wake_deficit)
        self.cb_wake_deficit.currentIndexChanged.connect(self._update_rotor_avg_lock_for_wake_deficit)
        self.cb_wake_deficit.currentIndexChanged.connect(self._update_turbulence_lock_for_wake_deficit)
        self.cb_wake_deficit.currentIndexChanged.connect(self._update_wake_turb_note)
        self.cb_wake_deficit.currentIndexChanged.connect(self._update_superposition_note)
        # Compatibilidad: PUD fuerza use_effective_ws en el solver; no bloqueamos modelos aquí.
        try:
            self.cb_wfm_engine.currentIndexChanged.connect(self._update_wake_deficit_lock_for_engine)
        except Exception:
            pass
        # aplicar estado inicial según el engine actual
        self._update_wake_deficit_lock_for_engine()
        root.addWidget(grp_def)

        # --------- Parámetros avanzados del modelo de estela (opcional) ---------
        self._build_advanced_wake_params_panel(root)
        # Conectar el cambio de modelo para refrescar el panel avanzado
        try:
            self.cb_wake_deficit.currentIndexChanged.connect(self._on_wake_deficit_changed_refresh_advanced)
        except Exception:
            pass
        # Aplicar estado inicial del panel avanzado (modelo persistido)
        self._on_wake_deficit_changed_refresh_advanced()

        # --------- Rotor Average model (PyWake) ---------
        grp_rotor = QtWidgets.QGroupBox("Promedio sobre el rotor (rotor-average)")
        v_rotor = QtWidgets.QVBoxLayout(grp_rotor)
        rotor_head = QtWidgets.QHBoxLayout()
        lbl_rotor = QtWidgets.QLabel("¿Cómo debe promediarse el viento dentro del disco del rotor?")
        self.btn_rotor_avg_help = QtWidgets.QToolButton()
        try:
            self.btn_rotor_avg_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_rotor_avg_help.setText("?")
        self.btn_rotor_avg_help.setAutoRaise(True)
        self.btn_rotor_avg_help.setToolTip("Explica por qué el rotor no debe tratarse siempre como un solo punto")
        self.btn_rotor_avg_help.clicked.connect(self._show_rotor_avg_help)
        rotor_head.addWidget(lbl_rotor)
        rotor_head.addWidget(self.btn_rotor_avg_help, 0)
        rotor_head.addStretch(1)
        self.cb_rotor_avg = QtWidgets.QComboBox()
        self.cb_rotor_avg.addItem("Ninguno", "NONE")
        self.cb_rotor_avg.addItem("Rápido · RotorCenter", "RC")
        self.cb_rotor_avg.addItem("Más realista · CGIRotorAvg(7)", "CGI7")
        self.cb_rotor_avg.addItem("Más realista · CGIRotorAvg(9)", "CGI9")
        self.cb_rotor_avg.addItem("Muy realista · CGIRotorAvg(21)", "CGI21")
        self.cb_rotor_avg.addItem("Malla uniforme · EqGridRotorAvg", "EQ")
        self.cb_rotor_avg.setToolTip(
            "El rotor-average calcula el viento en varios puntos del disco del rotor, no solo en el centro. "
            "Más puntos dan más realismo cuando una estela corta parte del rotor, pero aumentan el tiempo de cálculo."
        )
        self.lbl_rotor_avg_note = QtWidgets.QLabel("")
        self.lbl_rotor_avg_note.setWordWrap(True)
        self.lbl_rotor_avg_note.setStyleSheet("color: #666;")
        v_rotor.addLayout(rotor_head)
        v_rotor.addWidget(self.cb_rotor_avg)
        v_rotor.addWidget(self.lbl_rotor_avg_note)
        self._set_rotor_avg_combo(self._last_rotor_avg_model)
        self.cb_rotor_avg.currentIndexChanged.connect(self._persist_rotor_avg_model)
        self.cb_rotor_avg.currentIndexChanged.connect(self._update_rotor_avg_note)
        root.addWidget(grp_rotor)
        # aplicar restricciones rotor-average vs modelo de estela
        self._update_rotor_avg_lock_for_wake_deficit()
        self._update_rotor_avg_note()

        # --------- Modelo de superposición (PyWake) ---------
        grp_sup = QtWidgets.QGroupBox("Combinación de varias estelas (superposición)")
        v_sup = QtWidgets.QVBoxLayout(grp_sup)
        sup_head = QtWidgets.QHBoxLayout()
        lbl_sup = QtWidgets.QLabel("Si una turbina recibe varias estelas, ¿cómo se suman sus efectos?")
        self.btn_superposition_help = QtWidgets.QToolButton()
        try:
            self.btn_superposition_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_superposition_help.setText("?")
        self.btn_superposition_help.setAutoRaise(True)
        self.btn_superposition_help.setToolTip("Explica qué pasa cuando varias estelas llegan a la misma turbina")
        self.btn_superposition_help.clicked.connect(self._show_superposition_help)
        sup_head.addWidget(lbl_sup)
        sup_head.addWidget(self.btn_superposition_help, 0)
        sup_head.addStretch(1)
        self.cb_superposition_model = QtWidgets.QComboBox()
        self.cb_superposition_model.addItem("Automático", "AUTO")
        self.cb_superposition_model.addItem("LinearSum", "LIN")
        self.cb_superposition_model.addItem("SquaredSum", "SQR")
        self.cb_superposition_model.addItem("MaxSum", "MAX")
        self.cb_superposition_model.addItem("WeightedSum (solo gaussianos)", "WGT")
        self.cb_superposition_model.setToolTip(
            "La superposición decide cómo sumar varias estelas sobre una misma turbina. "
            "SquaredSum suele ser una opción equilibrada; LinearSum acumula más pérdidas; MaxSum solo toma la estela dominante."
        )
        self.lbl_superposition_note = QtWidgets.QLabel("")
        self.lbl_superposition_note.setWordWrap(True)
        self.lbl_superposition_note.setStyleSheet("color: #666;")
        v_sup.addLayout(sup_head)
        v_sup.addWidget(self.cb_superposition_model)
        v_sup.addWidget(self.lbl_superposition_note)
        self._set_superposition_combo(self._last_superposition_model)
        self.cb_superposition_model.currentIndexChanged.connect(self._persist_superposition_model)
        self.cb_superposition_model.currentIndexChanged.connect(self._update_superposition_note)
        root.addWidget(grp_sup)
        self._update_superposition_note()

        # --------- Blockage deficit model (PyWake) ---------
        grp_blk = QtWidgets.QGroupBox("Modelo de bloqueo (PyWake)")
        v_blk = QtWidgets.QVBoxLayout(grp_blk)
        blk_head = QtWidgets.QHBoxLayout()
        lbl_blk = QtWidgets.QLabel("¿Qué modelo de bloqueo quieres usar?")
        self.btn_blockage_help = QtWidgets.QToolButton()
        try:
            self.btn_blockage_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_blockage_help.setText("?")
        self.btn_blockage_help.setAutoRaise(True)
        self.btn_blockage_help.setToolTip(
            "Ayuda sobre cuándo conviene cada modelo de bloqueo y por qué a veces se desactiva automáticamente"
        )
        self.btn_blockage_help.clicked.connect(self._show_blockage_help)
        blk_head.addWidget(lbl_blk)
        blk_head.addWidget(self.btn_blockage_help, 0)
        blk_head.addStretch(1)

        self.cb_blockage_deficit = QtWidgets.QComboBox()
        self.cb_blockage_deficit.addItem("Ninguno", "NONE")
        self.cb_blockage_deficit.addItem("SelfSimilarityDeficit2020", "SS2020")
        self.cb_blockage_deficit.addItem("SelfSimilarityDeficit", "SS")
        self.cb_blockage_deficit.addItem("VortexCylinder", "VC")
        self.cb_blockage_deficit.addItem("VortexDipole", "VD")
        self.cb_blockage_deficit.addItem("HybridInduction", "HI")
        self.cb_blockage_deficit.setToolTip(
            "El bloqueo representa la reducción de velocidad aguas arriba del rotor. Solo se aplica con motores All2AllIterative o PropagateUpDownIterative."
        )
        v_blk.addLayout(blk_head)
        v_blk.addWidget(self.cb_blockage_deficit)

        # Nota gris explicativa: estado activo + interacción con el motor
        self.lbl_blockage_note = QtWidgets.QLabel("")
        self.lbl_blockage_note.setWordWrap(True)
        self.lbl_blockage_note.setStyleSheet("color: #666;")
        self.lbl_blockage_note.setTextFormat(QtCore.Qt.RichText)
        v_blk.addWidget(self.lbl_blockage_note)

        self._set_blockage_deficit_combo(self._last_blockage_deficit)
        self.cb_blockage_deficit.currentIndexChanged.connect(self._persist_blockage_deficit)
        # Refrescar la nota cuando cambien blockage o engine
        self.cb_blockage_deficit.currentIndexChanged.connect(self._update_blockage_note)
        try:
            self.cb_wfm_engine.currentIndexChanged.connect(self._update_blockage_note)
        except Exception:
            pass
        root.addWidget(grp_blk)

        # --------- Modelo de turbulencia (PyWake) ---------
        grp_turb = QtWidgets.QGroupBox("Modelo de turbulencia (PyWake)")
        v_turb = QtWidgets.QVBoxLayout(grp_turb)
        turb_head = QtWidgets.QHBoxLayout()
        lbl_turb = QtWidgets.QLabel("¿Qué modelo de turbulencia quieres usar?")
        self.btn_turbulence_help = QtWidgets.QToolButton()
        try:
            self.btn_turbulence_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_turbulence_help.setText("?")
        self.btn_turbulence_help.setAutoRaise(True)
        self.btn_turbulence_help.setToolTip("Ayuda sobre TI ambiente, turbulencia añadida y cuándo influye realmente en el AEP")
        self.btn_turbulence_help.clicked.connect(self._show_turbulence_model_help)
        turb_head.addWidget(lbl_turb)
        turb_head.addWidget(self.btn_turbulence_help, 0)
        turb_head.addStretch(1)
        self.cb_turbulence_model = QtWidgets.QComboBox()
        self.cb_turbulence_model.addItem("Ninguno", "NONE")
        self.cb_turbulence_model.addItem("STF2005TurbulenceModel", "STF2005")
        self.cb_turbulence_model.addItem("STF2017TurbulenceModel", "STF2017")
        self.cb_turbulence_model.addItem("GCLTurbulence", "GCL")
        self.cb_turbulence_model.addItem("CrespoHernandez", "CH")
        self.cb_turbulence_model.setToolTip("Este selector calcula turbulencia añadida por estela. No sustituye a la TI ambiente del site/WRG.")
        v_turb.addLayout(turb_head)
        v_turb.addWidget(self.cb_turbulence_model)

        # Nota gris dedicada a turbulencia: muestra constantes del modelo seleccionado
        self.lbl_turbulence_note = QtWidgets.QLabel("")
        self.lbl_turbulence_note.setWordWrap(True)
        self.lbl_turbulence_note.setStyleSheet("color: #666;")
        self.lbl_turbulence_note.setTextFormat(QtCore.Qt.RichText)
        v_turb.addWidget(self.lbl_turbulence_note)

        self._set_turbulence_model_combo(self._last_turbulence_model)
        self.cb_turbulence_model.currentIndexChanged.connect(self._persist_turbulence_model)
        self.cb_turbulence_model.currentIndexChanged.connect(self._update_wake_turb_note)
        self.cb_turbulence_model.currentIndexChanged.connect(self._update_turbulence_note)
        root.addWidget(grp_turb)

        # Estado inicial: si engine=PDW, bloquear selector de bloqueo
        self._update_blockage_lock_for_engine()


        # Estado inicial: aplicar compatibilidades wake↔rotorAvg y wake↔turbulence
        self._update_rotor_avg_lock_for_wake_deficit()
        self._update_turbulence_lock_for_wake_deficit()
        self._update_wake_turb_note()
        # Estado inicial de las notas dedicadas (bloqueo + turbulencia)
        self._update_blockage_note()
        self._update_turbulence_note()
        self._update_rotor_avg_note()
        self._update_superposition_note()
        # La ingesta WRG/TI se muestra ahora dentro de la sección unificada de Recurso eólico.

        # --------- Acciones ---------
        actions_box = QtWidgets.QGroupBox("Acciones", self)
        actions_grid = QtWidgets.QGridLayout(actions_box)
        actions_grid.setContentsMargins(8, 8, 8, 8)
        actions_grid.setHorizontalSpacing(6)
        actions_grid.setVerticalSpacing(6)

        # Logo Velantis en la parte inferior izquierda
        col0 = 0
        if getattr(self, '_vortex_logo_pix', None) is not None and not self._vortex_logo_pix.isNull():
            lbl_logo = QtWidgets.QLabel(self)
            lbl_logo.setPixmap(self._vortex_logo_pix.scaledToHeight(52, QtCore.Qt.SmoothTransformation))
            lbl_logo.setToolTip('Velantis Wind')
            lbl_logo.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            actions_grid.addWidget(lbl_logo, 0, 0, 1, 1)
            col0 = 1

        self.btn_gen_layers = QtWidgets.QPushButton("Generar capas de puntos")
        self.btn_plot_wakes = QtWidgets.QPushButton("Graficar estelas")
        self.btn_plot_wakes.setToolTip("Dibuja 4 mapas de estelas (N/E/S/O) usando los modelos y el recurso seleccionado (carpeta WAsP o WRG/ZIP).")
        self.btn_calc_update = QtWidgets.QPushButton("Calcular AEP")
        self.btn_calc_update.setDefault(True)

        # Mapa interactivo (toggle)
        self.btn_map_interactive = QtWidgets.QPushButton("Mapa interactivo")
        self.btn_map_interactive.setCheckable(True)
        self.btn_map_interactive.setToolTip(
            "Activa edición en el canvas: click izq añade turbina, click der borra. "
            "Las coordenadas editadas se usan directamente en el cálculo de AEP "
            "(la capa en memoria es la fuente de verdad). El CSV original NO se modifica."
        )

        # Exportar layout editado (acción explícita; nunca sobrescribe el CSV original sin confirmar)
        self.btn_export_edited = QtWidgets.QPushButton("Exportar layout editado…")
        self.btn_export_edited.setToolTip(
            "Guardar a CSV los puntos editados en el mapa interactivo.\n"
            "Default: <original>_edited.csv (no sobrescribe el CSV original)."
        )

        self.btn_store_scn_a = QtWidgets.QPushButton("Guardar escenario A")
        self.btn_store_scn_a.setToolTip("Guarda el último cálculo AEP como escenario A para compararlo después.")
        self.btn_store_scn_b = QtWidgets.QPushButton("Guardar escenario B")
        self.btn_store_scn_b.setToolTip("Guarda el último cálculo AEP como escenario B para compararlo después.")
        self.btn_compare_scenarios = QtWidgets.QPushButton("Comparar A/B")
        self.btn_compare_scenarios.setToolTip("Compara los dos escenarios guardados y muestra delta global y por modelo.")

        for b in (
            self.btn_gen_layers, self.btn_map_interactive, self.btn_export_edited,
            self.btn_plot_wakes, self.btn_calc_update,
            self.btn_store_scn_a, self.btn_store_scn_b, self.btn_compare_scenarios,
        ):
            b.setMinimumWidth(0)
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Distribución en 3 filas para pantallas pequeñas: evita una única botonera horizontal larguísima.
        actions_grid.addWidget(self.btn_gen_layers, 0, col0 + 0)
        actions_grid.addWidget(self.btn_map_interactive, 0, col0 + 1)
        actions_grid.addWidget(self.btn_export_edited, 0, col0 + 2)
        actions_grid.addWidget(self.btn_plot_wakes, 1, col0 + 0)
        actions_grid.addWidget(self.btn_calc_update, 1, col0 + 1)
        actions_grid.addWidget(self.btn_store_scn_a, 1, col0 + 2)
        actions_grid.addWidget(self.btn_store_scn_b, 2, col0 + 0)
        actions_grid.addWidget(self.btn_compare_scenarios, 2, col0 + 1, 1, 2)
        actions_grid.setColumnStretch(col0 + 0, 1)
        actions_grid.setColumnStretch(col0 + 1, 1)
        actions_grid.setColumnStretch(col0 + 2, 1)
        root.addWidget(actions_box)

        # Botonera estándar
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Conexiones
        self.btn_gen_layers.clicked.connect(self._on_generate_layers_clicked)
        self.btn_plot_wakes.clicked.connect(self._run_plot_wakes)
        self.btn_calc_update.clicked.connect(self._run_compute_and_update)
        self.btn_map_interactive.toggled.connect(self._toggle_map_interactive)
        self.btn_export_edited.clicked.connect(self._export_edited_layouts_dialog)
        self.btn_store_scn_a.clicked.connect(lambda: self._store_current_scenario("A"))
        self.btn_store_scn_b.clicked.connect(lambda: self._store_current_scenario("B"))
        self.btn_compare_scenarios.clicked.connect(self._compare_scenarios)
        self.btn_return_hub.clicked.connect(self._return_to_hub)
        self.btn_refresh_project.clicked.connect(self._refresh_project_state)

        # Inicializar
        self._rebuild_rows()
        self._apply_style()
        apply_i18n(self)
        QtCore.QTimer.singleShot(0, self._fit_to_screen)

        # Capturar ESC global mientras estemos en modo mapa interactivo
        try:
            iface.mainWindow().installEventFilter(self)
        except Exception:
            pass

    def _apply_style(self):
        """Aplica el estilo unificado del plugin Velantis Wind (paleta del hub)."""
        self.setStyleSheet(
            self.styleSheet()
            + """
            QDialog { background: #f3f5f7; }
            QLabel#aepTitle { font-size: 22px; font-weight: 700; color: #103b67; }
            QLabel#aepSubtitle { font-size: 12px; color: #4f5d6b; }
            QLabel#aepMinor { font-size: 11px; color: #667480; }
            QGroupBox {
                border: 1px solid #cbd4dc;
                border-radius: 10px;
                margin-top: 10px;
                background: white;
                font-weight: 600;
                color: #103b67;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }
            QTextEdit { background: white; }
            QTableWidget { background: white; }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton { min-height: 28px; }
            QPushButton#aepBackButton {
                font-weight: 600;
                padding-left: 12px;
                padding-right: 12px;
                background: #ffffff;
                border: 1px solid #b7c4d0;
                border-radius: 6px;
            }
            QPushButton#aepBackButton:hover { background: #eef4f8; }
            QLineEdit { background: white; }
            """
        )

    def _fit_to_screen(self) -> None:
        """Ajusta el diálogo al área visible de la pantalla y deja scroll si no cabe."""
        fit_to_screen(self, preferred=(1120, 780), minimum=(760, 520), max_ratio=(0.94, 0.92), set_maximum=False)


    def _open_pywake_docs(self) -> None:
        """Abre la documentación oficial de PyWake desde el módulo Energía."""
        try:
            QDesktopServices.openUrl(QUrl("https://topfarm.pages.windenergy.dtu.dk/PyWake/"))
        except Exception:
            try:
                iface.messageBar().pushMessage(
                    "PyWake",
                    "No se pudo abrir el navegador. URL: https://topfarm.pages.windenergy.dtu.dk/PyWake/",
                    level=Qgis.Warning,
                    duration=8,
                )
            except Exception:
                pass

    def _persist_fixed_ti_percent(self) -> None:
        try:
            self._qsettings.setValue("last_fixed_ti_percent", float(self.sp_fixed_ti.value()))
        except Exception:
            pass

    def _get_fixed_ti_fraction(self) -> float:
        try:
            val_pct = float(self.sp_fixed_ti.value())
        except Exception:
            val_pct = 10.0
        if val_pct < 3.0 or val_pct > 30.0:
            val_pct = 10.0
        return val_pct / 100.0

    # -------------------- PyWake selectors (WFM + deficit) --------------------
    def _normalize_wfm_engine(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper()
        mapping = {
            "AUTO": "AUTO",
            "PDW": "PDW",
            "PROPAGATEDOWNWIND": "PDW",
            "A2A": "A2A",
            "ALL2ALLITERATIVE": "A2A",
            "PUD": "PUD",
            "PROPAGATEUPDOWNITERATIVE": "PUD",
            "PROPAGATEUPDOWNITEARTIVE": "PUD",  # tolera typo
        }
        return mapping.get(u, "PDW")

    def _set_wfm_engine_combo(self, value: str) -> None:
        eng = self._normalize_wfm_engine(value)
        try:
            for i in range(self.cb_wfm_engine.count()):
                if str(self.cb_wfm_engine.itemData(i)).upper() == eng:
                    self.cb_wfm_engine.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_wfm_engine(self) -> None:
        try:
            val = self.cb_wfm_engine.currentData() or "PDW"
            self._qsettings.setValue("last_wfm_engine", str(val))
        except Exception:
            pass

    def _get_selected_wfm_engine(self) -> str:
        try:
            val = self.cb_wfm_engine.currentData() or self.cb_wfm_engine.currentText()
        except Exception:
            val = "PDW"
        return self._normalize_wfm_engine(str(val))

    def _normalize_wake_deficit(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper()
        mapping = {
            # La opción "Ninguno" ya no se expone en la UI. Si llega desde
            # settings/valores antiguos, caemos al valor por defecto (BG).
            "NONE": "BG",
            "NINGUNO": "BG",
            "NOJ": "NOJ",
            "NOJDEFICIT": "NOJ",
            "NOJ DEFICIT": "NOJ",
            "TNOJ": "TNOJ",
            "TURBONOJ": "TNOJ",
            "TURBONOJDEFICIT": "TNOJ",
            "NIA": "NIA",
            "NIAYIFAR": "NIA",
            "NIAYIFARGAUSSIANDEFICIT": "NIA",
            "BG": "BG",
            "BASTANKHAHGAUSSIANDEFICIT": "BG",
            "BASTANKHAHGAUSSIAN": "BG",
            "TURBOGAUSSIANDEFICIT": "TG",
            "TG": "TG",
            "ZONGGAUSSIANDEFICIT": "ZG",
            "ZG": "ZG",
        }
        return mapping.get(u, "BG")

    def _set_wake_deficit_combo(self, value: str) -> None:
        key = self._normalize_wake_deficit(value)
        try:
            for i in range(self.cb_wake_deficit.count()):
                if str(self.cb_wake_deficit.itemData(i)).upper() == key:
                    self.cb_wake_deficit.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_wake_deficit(self) -> None:
        try:
            val = self.cb_wake_deficit.currentData() or "BG"
            self._qsettings.setValue("last_wake_deficit", str(val))
        except Exception:
            pass

    def _get_selected_wake_deficit(self) -> str:
        try:
            val = self.cb_wake_deficit.currentData() or self.cb_wake_deficit.currentText()
        except Exception:
            val = "BG"
        return self._normalize_wake_deficit(str(val))


    # -------------------- Rotor-average selector (PyWake) --------------------
    def _normalize_rotor_avg_model(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper().replace(" ", "").replace("-", "")
        mapping = {
            "NONE": "NONE",
            "NINGUNO": "NONE",
            "CGI": "CGI7",
            "CGI4": "CGI7",
            "CGI7": "CGI7",
            "CGI9": "CGI9",
            "CGI21": "CGI21",
            "CGIROTORAVG": "CGI7",
            "CGIROTORAVG(7)": "CGI7",
            "CGIROTORAVG(9)": "CGI9",
            "CGIROTORAVG(21)": "CGI21",
            "GAUSSIANOVERLAPAVGMODEL": "CGI7",
            "GO": "CGI7",
            "EQGRIDROTORAVG": "EQ",
            "EQ": "EQ",
            "ROTORCENTER": "RC",
            "RC": "RC",
            "AUTO": "CGI7",
        }
        return mapping.get(u, "CGI7")

    def _set_rotor_avg_combo(self, value: str) -> None:
        key = self._normalize_rotor_avg_model(value)
        try:
            for i in range(self.cb_rotor_avg.count()):
                if str(self.cb_rotor_avg.itemData(i)).upper() == key:
                    self.cb_rotor_avg.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_rotor_avg_model(self) -> None:
        try:
            val = self.cb_rotor_avg.currentData() or "CGI7"
            self._qsettings.setValue("last_rotor_avg_model", str(val))
        except Exception:
            pass

    def _get_selected_rotor_avg_model(self) -> str:
        try:
            val = self.cb_rotor_avg.currentData() or self.cb_rotor_avg.currentText()
        except Exception:
            val = "CGI7"
        return self._normalize_rotor_avg_model(str(val))

    # -------------------- Superposition selector (PyWake) --------------------
    def _normalize_superposition_model(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper().replace(" ", "")
        mapping = {
            "AUTO": "AUTO",
            "RECOMMENDED": "AUTO",
            "LIN": "LIN",
            "LINEAR": "LIN",
            "LINEARSUM": "LIN",
            "SQR": "SQR",
            "SQUARE": "SQR",
            "SQUAREDSUM": "SQR",
            "RSS": "SQR",
            "MAX": "MAX",
            "MAXSUM": "MAX",
            "WGT": "WGT",
            "WEIGHTED": "WGT",
            "WEIGHTEDSUM": "WGT",
        }
        return mapping.get(u, "AUTO")

    def _set_superposition_combo(self, value: str) -> None:
        key = self._normalize_superposition_model(value)
        try:
            for i in range(self.cb_superposition_model.count()):
                if str(self.cb_superposition_model.itemData(i)).upper() == key:
                    self.cb_superposition_model.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_superposition_model(self) -> None:
        try:
            val = self.cb_superposition_model.currentData() or "AUTO"
            self._qsettings.setValue("last_superposition_model", str(val))
        except Exception:
            pass

    def _get_selected_superposition_model(self) -> str:
        try:
            val = self.cb_superposition_model.currentData() or self.cb_superposition_model.currentText()
        except Exception:
            val = "AUTO"
        return self._normalize_superposition_model(str(val))

    def _update_rotor_avg_note(self) -> None:
        try:
            rotor = (self._get_selected_rotor_avg_model() or "").upper()
        except Exception:
            rotor = "CGI7"
        if rotor == "NONE":
            msg = "Sin promedio de rotor: PyWake usa el viento en el centro del rotor. Es lo más simple y rápido, pero pierde detalle si una estela afecta solo a una parte del disco."
        elif rotor == "RC":
            msg = "RotorCenter: usa un único punto en el centro del rotor. Es rápido para pruebas y mapas, pero no representa la variación de velocidad dentro del disco."
        elif rotor == "CGI7":
            msg = "CGIRotorAvg(7): calcula varios puntos dentro del rotor. Aporta más realismo cuando hay estelas parciales sin aumentar demasiado el coste."
        elif rotor == "CGI9":
            msg = "CGIRotorAvg(9): usa más puntos que CGI7. Puede aportar algo más de realismo si el tiempo de cálculo sigue siendo asumible."
        elif rotor == "CGI21":
            msg = "CGIRotorAvg(21): usa muchos puntos del rotor. Es más pesado y solo compensa si buscas una sensibilidad de mayor fidelidad."
        else:
            msg = "Rotor-average significa promediar el viento en varios puntos del rotor en vez de mirar un único punto central. Más puntos = más realismo y más coste."
        try:
            self.lbl_rotor_avg_note.setText(msg)
        except Exception:
            pass

    def _show_rotor_avg_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Ayuda · Promedio sobre el rotor",
            "<b>Qué es</b><br><br>"
            "Una turbina no ve exactamente el mismo viento en todo el rotor. La parte alta, baja, izquierda o derecha del disco puede recibir velocidades distintas, sobre todo si una estela solo atraviesa una parte del rotor.<br><br>"
            "<b>Qué hace esta opción</b><br>"
            "• <b>Sin promedio / RotorCenter</b>: usa solo el centro del rotor. Es rápido, pero más simplificado.<br>"
            "• <b>CGIRotorAvg(7)</b>: calcula varios puntos dentro del disco. Aporta más realismo con un coste moderado.<br>"
            "• <b>CGIRotorAvg(9/21)</b>: usa más puntos. Puede aportar más fidelidad, pero aumenta el tiempo de cálculo.<br><br>"
            "<b>Idea sencilla</b><br>"
            "Si una estela corta solo media turbina, mirar únicamente el centro puede ser demasiado simplificado. Promediar el rotor ayuda a representar mejor ese efecto."
        )

    def _update_superposition_note(self) -> None:
        try:
            sup = (self._get_selected_superposition_model() or "AUTO").upper()
            wake = (self._get_selected_wake_deficit() or "BG").upper()
        except Exception:
            sup, wake = "AUTO", "BG"
        gaussian = wake in ("BG", "NIA", "ZG", "TG")
        try:
            self._set_combo_item_enabled_by_data(self.cb_superposition_model, "WGT", gaussian)
            if (not gaussian) and sup == "WGT":
                self._set_superposition_combo("AUTO")
                self._persist_superposition_model()
                sup = "AUTO"
        except Exception:
            pass

        if sup == "AUTO":
            msg = "Automático: el plugin escoge una opción segura según la combinación de modelos disponible."
        elif sup == "LIN":
            msg = "LinearSum: suma directamente varias pérdidas de velocidad. Puede aumentar las pérdidas en parques densos."
        elif sup == "SQR":
            msg = "SquaredSum: combina varias estelas de forma cuadrática. Suele dar un comportamiento más equilibrado cuando varias estelas se solapan."
        elif sup == "MAX":
            msg = "MaxSum: usa solo la estela dominante. Sirve para diagnosticar, pero puede quedarse corto si varias estelas se acumulan."
        elif sup == "WGT":
            msg = "WeightedSum: opción avanzada para gaussianos compatibles. Si PyWake rechaza la combinación, el plugin volverá a una opción segura."
        else:
            msg = "La superposición dice cómo sumar varias estelas cuando una turbina está detrás de más de una turbina."
        try:
            self.lbl_superposition_note.setText(msg)
        except Exception:
            pass

    def _show_superposition_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Ayuda · Superposición de estelas",
            "<b>Qué problema resuelve</b><br><br>"
            "Una turbina puede recibir la estela de varias turbinas al mismo tiempo. La superposición decide cómo se combinan esas pérdidas de velocidad antes de calcular la potencia.<br><br>"
            "• <b>Automático</b>: el plugin escoge una opción segura según la combinación de modelos.<br>"
            "• <b>LinearSum</b>: suma directa. Puede acumular muchas pérdidas en parques densos.<br>"
            "• <b>SquaredSum</b>: suma cuadrática. Suele ser una opción equilibrada cuando varias estelas se solapan.<br>"
            "• <b>MaxSum</b>: usa solo la estela más fuerte. Útil para diagnóstico, pero puede infravalorar pérdidas acumuladas.<br>"
            "• <b>WeightedSum</b>: opción avanzada para modelos gaussianos compatibles.<br><br>"
            "<b>Idea sencilla</b><br>"
            "Si dos turbinas frenan el viento antes de llegar a una tercera, hay que decidir si esas pérdidas se suman mucho, poco o solo domina una de ellas."
        )

    # ------------------ construir filas ------------------
    def _clear_layout(self, lay: QtWidgets.QLayout):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def _normalize_blockage_deficit(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper()
        mapping = {
            "NONE": "NONE",
            "NINGUNO": "NONE",
            "SS2020": "SS2020",
            "SELFSIMILARITYDEFICIT2020": "SS2020",
            "SELF": "SS2020",
            "VD": "VD",
            "VORTEXDIPOLE": "VD",
            "HI": "HI",
            "HYBRIDINDUCTION": "HI",
            "RATH": "RATH",
            "RATHMANN": "RATH",
        }
        return mapping.get(u, mapping.get(u.replace(' ', ''), "NONE"))

    def _set_blockage_deficit_combo(self, value: str) -> None:
        key = self._normalize_blockage_deficit(value)
        try:
            for i in range(self.cb_blockage_deficit.count()):
                if str(self.cb_blockage_deficit.itemData(i)).upper() == key:
                    self.cb_blockage_deficit.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_blockage_deficit(self) -> None:
        try:
            val = self.cb_blockage_deficit.currentData() or "NONE"
            self._qsettings.setValue("last_blockage_deficit", str(val))
        except Exception:
            pass

    def _get_selected_blockage_deficit(self) -> str:
        try:
            val = self.cb_blockage_deficit.currentData() or self.cb_blockage_deficit.currentText()
        except Exception:
            val = "NONE"
        return self._normalize_blockage_deficit(str(val))

    # -------------------- Turbulence selector (PyWake) --------------------
    def _normalize_turbulence_model(self, value: str) -> str:
        v = (value or "").strip()
        u = v.upper().replace(" ", "")
        mapping = {
            "NONE": "NONE",
            "NINGUNO": "NONE",
            "AUTO": "STF2017",
            "STF2005": "STF2005",
            "STF2005TURBULENCEMODEL": "STF2005",
            "STF2017": "STF2017",
            "STF2017TURBULENCEMODEL": "STF2017",
            "GCL": "GCL",
            "GCLTURBULENCE": "GCL",
            "GCLTURBULENCEMODEL": "GCL",
            "CRESPOHERNANDEZ": "CH",
            "CH": "CH",
        }
        return mapping.get(u, mapping.get(u.replace('_',''), "NONE"))

    def _set_turbulence_model_combo(self, value: str) -> None:
        key = self._normalize_turbulence_model(value)
        try:
            for i in range(self.cb_turbulence_model.count()):
                if str(self.cb_turbulence_model.itemData(i)).upper() == key:
                    self.cb_turbulence_model.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _persist_turbulence_model(self) -> None:
        try:
            val = self.cb_turbulence_model.currentData() or "NONE"
            self._qsettings.setValue("last_turbulence_model", str(val))
        except Exception:
            pass

    def _get_selected_turbulence_model(self) -> str:
        try:
            val = self.cb_turbulence_model.currentData() or self.cb_turbulence_model.currentText()
        except Exception:
            val = "NONE"
        return self._normalize_turbulence_model(str(val))

    def _update_engine_note_for_wfm(self) -> None:
        """Muestra una nota cuando el motor requiere WS efectiva."""
        try:
            eng = (self._get_selected_wfm_engine() or "").upper()
        except Exception:
            eng = ""
        txt = ""
        if eng == "PUD":
            txt = "Nota sencilla: este motor calcula interacciones hacia abajo y hacia arriba. Para que PyWake no falle con algunas combinaciones, el plugin activa automáticamente use_effective_ws=True en estelas y bloqueo."
        try:
            self.lbl_engine_note.setText(txt)
        except Exception:
            pass

    # --------- Restricción: PDW no soporta bloqueo ---------
    def _update_blockage_lock_for_engine(self) -> None:
        """Si el motor WFM es PDW, fuerza bloqueo=NONE y deshabilita el combo.
        Al salir de PDW, restaura la última selección previa.
        """
        try:
            eng = (self._get_selected_wfm_engine() or "").upper()
        except Exception:
            eng = "PDW"

        if eng == "PDW":
            # guardar selección actual para poder restaurarla
            try:
                cur = self.cb_blockage_deficit.currentData() or "NONE"
                cur_u = str(cur).upper()
                if cur_u not in ("NONE", "NINGUNO"):
                    self._blockage_before_pdw = str(cur)
            except Exception:
                pass
            # forzar NONE y bloquear
            try:
                self._set_blockage_deficit_combo("NONE")
                self.cb_blockage_deficit.setEnabled(False)
                self._persist_blockage_deficit()
            except Exception:
                pass
        else:
            try:
                self.cb_blockage_deficit.setEnabled(True)
                restore = getattr(self, "_blockage_before_pdw", None) or self._last_blockage_deficit
                self._set_blockage_deficit_combo(restore)
                self._persist_blockage_deficit()
            except Exception:
                pass

    

    def _update_wake_deficit_lock_for_engine(self) -> None:
        """PropagateUpDownIterative (PUD) requiere modelos que escalen con WS efectiva.

        En PyWake esto se resuelve, para la mayoría de deficit models, pasando
        use_effective_ws=True al constructor. El solver ya lo fuerza cuando engine==PUD,
        así que aquí no bloqueamos modelos de estela; solo actualizamos notas/compatibilidades.
        Si una instalación concreta de PyWake no acepta una combinación, el runner robusto
        degradará automáticamente y lo reportará en el resumen.
        """
        if not hasattr(self, "cb_wake_deficit") or not hasattr(self, "cb_wfm_engine"):
            return
        try:
            for key in ("NOJ", "TNOJ", "BG", "NIA", "TG", "ZG"):
                self._set_combo_item_enabled_by_data(self.cb_wake_deficit, key, True)
        except Exception:
            pass
        try:
            self._update_rotor_avg_lock_for_wake_deficit()
            self._update_turbulence_lock_for_wake_deficit()
            self._update_wake_turb_note()
        except Exception:
            pass

    # -------------------- Compatibilidad WakeDeficit vs RotorAvg --------------------
    def _set_combo_item_enabled_by_data(self, combo: QtWidgets.QComboBox, data_key: str, enabled: bool) -> None:
        """Habilita/deshabilita un item de un QComboBox buscando por itemData()."""
        try:
            dk = str(data_key).upper()
            mdl = combo.model()
            for i in range(combo.count()):
                if str(combo.itemData(i)).upper() == dk:
                    try:
                        it = mdl.item(i)  # QStandardItemModel
                        if it is not None:
                            it.setEnabled(bool(enabled))
                    except Exception:
                        # fallback: no-op si el modelo no expone items editables
                        pass
                    return
        except Exception:
            return

    def _update_rotor_avg_lock_for_wake_deficit(self) -> None:
        """Compatibilidad wake↔rotor-average.

        La versión experimental ya no expone GaussianOverlapAvgModel, porque es una opción avanzada
        que puede depender de clases internas/compatibilidad de PyWake. Los modelos
        que quedan en la UI son opciones estándar de rotor-average y no dependen del
        wake deficit seleccionado.
        """
        try:
            self._update_rotor_avg_note()
        except Exception:
            pass

    def _update_turbulence_lock_for_wake_deficit(self) -> None:
        """Compatibilidad entre wake deficit y turbulencia añadida.

        No todos los modelos necesitan un turbulenceModel añadido. Todos reciben la
        TI ambiente del Site, pero solo algunos wake deficits la usan de forma fuerte.
        En esta versión experimental mantenemos una restricción práctica: Zong funciona mejor/espera
        turbulencia añadida, así que se fuerza STF2017 si el usuario dejó Ninguno.
        """
        try:
            wake = (self._get_selected_wake_deficit() or "").upper()
        except Exception:
            wake = "BG"

        requires_turb = wake in ("ZG", "ZONGGAUSSIANDEFICIT")

        # Deshabilitar/rehabilitar el item NONE en turbulencia
        try:
            self._set_combo_item_enabled_by_data(self.cb_turbulence_model, "NONE", not requires_turb)
        except Exception:
            pass

        if requires_turb:
            try:
                cur = self.cb_turbulence_model.currentData() or "NONE"
                if str(cur).strip().upper() in ("NONE", "NINGUNO", "NO", "OFF"):
                    # STF2017 es la opción segura por defecto
                    self._set_turbulence_model_combo("STF2017")
                    self._persist_turbulence_model()
            except Exception:
                pass


    # ============================================================
    # Panel de parámetros avanzados del modelo de estela
    # ============================================================
    # Definiciones canónicas. La clave del modelo coincide con itemData del combo.
    # Cada parámetro: (kw, etiqueta UI, default PyWake, mínimo, máximo, paso, decimales,
    #                  tooltip corto)
    _ADVANCED_PARAMS = {
        "NOJ": [
            ("k", "k (expansión de estela)", 0.04, 0.005, 0.30, 0.005, 4,
             "Pendiente de expansión del cono de estela top-hat. Subir k acelera la recuperación; bajarlo alarga la estela."),
        ],
        "BG": [
            ("k", "k (pendiente gaussiana)", 0.0324555, 0.005, 0.20, 0.001, 5,
             "Pendiente del ancho σ(x) de la estela gaussiana. Default PyWake ≈ 0.0324555."),
            ("ceps", "cεps (semilla σ₀)", 0.20, 0.05, 1.0, 0.01, 3,
             "Tamaño inicial de la estela en la base (σ₀/D). Default PyWake = 0.2."),
        ],
        "NIA": [
            ("a1", "a₁ en k = a₁·TI + a₂", 0.38, 0.0, 2.0, 0.01, 3,
             "Coeficiente que convierte la TI local/efectiva en expansión de estela."),
            ("a2", "a₂ en k = a₁·TI + a₂", 0.004, 0.0, 0.05, 0.001, 4,
             "Offset mínimo de expansión cuando la TI tiende a cero."),
            ("ceps", "cεps (semilla σ₀)", 0.20, 0.05, 1.0, 0.01, 3,
             "Tamaño inicial σ₀/D. Default PyWake = 0.2."),
        ],
        "ZG": [
            ("a1", "a₁ en k = a₁·TI + a₂", 0.38, 0.0, 2.0, 0.01, 3,
             "Coeficiente de expansión dependiente de TI en la formulación Zong."),
            ("a2", "a₂ en k = a₁·TI + a₂", 0.004, 0.0, 0.05, 0.001, 4,
             "Offset mínimo de expansión de la estela."),
            ("deltawD", "δw/D (longitud fuente near-wake)", 0.70710678, 0.1, 3.0, 0.05, 4,
             "Escala longitudinal de la fuente gaussiana en near-wake. Default 1/sqrt(2)."),
            ("eps_coeff", "ε coeff", 0.35355339, 0.05, 1.5, 0.01, 4,
             "Coeficiente de anchura inicial. Default conservador PyWake = 1/sqrt(8)."),
            ("lam", "λ tip-speed ratio", 7.5, 1.0, 15.0, 0.1, 2,
             "Parámetro λ usado en la longitud near-wake de Vermeulen."),
            ("B", "B número de palas", 3.0, 1.0, 5.0, 1.0, 0,
             "Número de palas usado en la longitud near-wake. Normalmente 3."),
        ],
        "TG": [
            ("A", "A expansión TurbOPark", 0.04, 0.005, 0.20, 0.005, 4,
             "Constante principal de expansión de TurboGaussian/TurbOPark."),
            ("cTI1", "cTI[0]", 1.5, 0.1, 5.0, 0.05, 3,
             "Primer coeficiente que multiplica la TI en la formulación TurboGaussian."),
            ("cTI2", "cTI[1]", 0.8, 0.1, 5.0, 0.05, 3,
             "Segundo coeficiente TI/CT en la formulación TurboGaussian."),
            ("ceps", "cεps (semilla σ₀)", 0.25, 0.05, 1.0, 0.01, 3,
             "Tamaño inicial de la estela. Default PyWake = 0.25."),
        ],
        "TNOJ": [
            ("A", "A expansión TurboNOJ", 0.04, 0.005, 0.20, 0.005, 4,
             "Constante principal de expansión para la familia TurboNOJ cuando la versión de PyWake la expone."),
            ("cTI1", "cTI[0]", 1.5, 0.1, 5.0, 0.05, 3,
             "Primer coeficiente de sensibilidad a TI. Solo se aplicará si la clase PyWake acepta cTI."),
            ("cTI2", "cTI[1]", 0.8, 0.1, 5.0, 0.05, 3,
             "Segundo coeficiente de sensibilidad a TI. Solo se aplicará si la clase PyWake acepta cTI."),
        ],
    }

    # Texto explicativo por modelo (mostrado en el botón ℹ️)
    _ADVANCED_HELP = {
        "NOJ": (
            "<b>NOJDeficit (Jensen)</b><br><br>"
            "Modelo top-hat clásico: la estela es un cilindro que se ensancha linealmente con "
            "una sola pendiente <b>k</b>.<br><br>"
            "<b>k</b> — Pendiente de expansión. "
            "<u>Físicamente</u> representa cuánto crece el radio de la estela por metro avanzado "
            "aguas abajo: r(x) = R + k·x. Cuanto mayor k, más rápido se recupera la estela y más "
            "pequeño el déficit lejano.<br><br>"
            "<b>Valores de referencia</b><br>"
            "• Offshore limpio: k ≈ 0.04 (default PyWake)<br>"
            "• Onshore típico: k ≈ 0.075<br>"
            "• Onshore complejo / alta TI: k ≈ 0.10<br><br>"
            "<i>Nota:</i> NOJ no usa la TI ambiente para calcular k. Si tu sitio tiene TI alta y "
            "necesitas que esto se note en el AEP, usa TurboNOJ o un modelo gaussiano TI-sensible."
        ),
        "BG": (
            "<b>BastankhahGaussianDeficit</b><br><br>"
            "Modelo gaussiano de Bastankhah & Porté-Agel (2014). El perfil radial del déficit es "
            "una campana de Gauss cuyo ancho σ(x) crece linealmente.<br><br>"
            "<b>k</b> — Pendiente del crecimiento de σ. "
            "σ(x)/D = k·(x/D) + cεps. Default PyWake = 0.0324, valor calibrado contra LES en el "
            "paper original. Subirlo = estela que se ensancha y recupera antes; bajarlo = estela "
            "más estrecha y persistente.<br><br>"
            "<b>cεps</b> — Tamaño inicial de la estela junto al rotor (σ₀/D). "
            "Default PyWake = 0.2. Casi nunca se cambia; afecta sobre todo al near-wake.<br><br>"
            "<i>Nota:</i> en BG estándar la TI ambiente NO entra en k. Es robusto para "
            "benchmarking (ej. IEA Task 37) pero poco sensible al recurso TI."
        ),
        "NIA": (
            "<b>NiayifarGaussianDeficit</b><br><br>"
            "Variante gaussiana donde la pendiente k es función explícita de la <b>TI local "
            "efectiva</b> (Niayifar &amp; Porté-Agel 2016): k ≈ a₁·TI + a₂.<br><br>"
            "<b>a₁/a₂</b> — Coeficientes de k = a₁·TI + a₂. Default PyWake = [0.38, 0.004].<br>"
            "<b>cεps</b> — Tamaño inicial σ₀/D. Default PyWake = 0.2.<br><br>"
            "Cambiar la TI ambiente del WRG o el modelo de turbulencia añadida sigue siendo la "
            "palanca principal del AEP. Los coeficientes se exponen solo como ajuste avanzado."
        ),
        "ZG": (
            "<b>ZongGaussianDeficit</b><br><br>"
            "Modelo gaussiano avanzado (Zong &amp; Porté-Agel 2020) con near-wake explícito y "
            "pendiente k dependiente de TI local.<br><br>"
            "<b>a₁/a₂</b> — Coeficientes de k = a₁·TI + a₂. Default PyWake = [0.38, 0.004].<br>"
            "<b>δw/D, ε coeff, λ y B</b> — parámetros near-wake avanzados. "
            "El plugin fuerza STF2017 si lo dejas en Ninguno."
        ),
        "TNOJ": (
            "<b>TurboNOJDeficit</b><br><br>"
            "Variante TI-sensible del Jensen: la pendiente k se calcula a partir de la "
            "<b>turbulencia efectiva</b> en cada turbina.<br><br>"
            "Para mover el AEP, ajusta la <b>TI ambiente</b> o el <b>modelo de turbulencia añadida</b>. "
            "Los coeficientes A/cTI se exponen como ajuste avanzado y solo se pasan si tu PyWake los acepta."
        ),
        "TG": (
            "<b>TurboGaussianDeficit</b><br><br>"
            "Versión TI-driven de la familia gaussiana. Tanto k como el ancho cerca del rotor "
            "se derivan de la TI efectiva.<br><br>"
            "Para mover el AEP, ajusta la <b>TI ambiente</b> o el <b>modelo de turbulencia añadida</b>. "
            "Los coeficientes A/cTI/cεps se exponen como ajuste avanzado para calibración controlada."
        ),
    }

    def _build_advanced_wake_params_panel(self, parent_layout) -> None:
        """Panel colapsable con los parámetros avanzados del wake deficit seleccionado."""
        self._adv_params_widgets = {}   # {model_key: {kw: QDoubleSpinBox}}
        self._adv_params_pages = {}     # {model_key: QWidget}

        grp = QtWidgets.QGroupBox("Parámetros avanzados del modelo (opcional · dejar por defecto salvo calibración)")
        grp.setCheckable(True)
        grp.setChecked(False)
        v = QtWidgets.QVBoxLayout(grp)

        head = QtWidgets.QHBoxLayout()
        self.lbl_adv_params_intro = QtWidgets.QLabel(
            "Estos parámetros modifican la forma de la estela. Déjalos en "
            "«Valor PyWake por defecto» salvo que estés haciendo una sensibilidad, "
            "validación contra otro software o calibración técnica."
        )
        self.lbl_adv_params_intro.setWordWrap(True)
        self.lbl_adv_params_intro.setStyleSheet("color: #666;")
        self.btn_adv_params_help = QtWidgets.QToolButton()
        try:
            self.btn_adv_params_help.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            self.btn_adv_params_help.setText("?")
        self.btn_adv_params_help.setAutoRaise(True)
        self.btn_adv_params_help.setToolTip("Explica qué cambia cada parámetro sin asumir conocimiento previo")
        self.btn_adv_params_help.clicked.connect(self._show_advanced_params_help)
        head.addWidget(self.lbl_adv_params_intro, 1)
        head.addWidget(self.btn_adv_params_help, 0)
        v.addLayout(head)

        self.stk_adv_params = QtWidgets.QStackedWidget()
        # Construir una página por modelo conocido
        for key, params in self._ADVANCED_PARAMS.items():
            page = QtWidgets.QWidget()
            grid = QtWidgets.QFormLayout(page)
            grid.setContentsMargins(0, 0, 0, 0)
            self._adv_params_widgets[key] = {}
            if not params:
                lbl = QtWidgets.QLabel(
                    "<i>Este modelo no expone parámetros físicos manualmente. "
                    "Pulsa el botón ℹ️ para ver por qué.</i>"
                )
                lbl.setWordWrap(True)
                grid.addRow(lbl)
            for (kw, label, default, vmin, vmax, step, decimals, tip) in params:
                spin = QtWidgets.QDoubleSpinBox()
                spin.setDecimals(decimals)
                spin.setSingleStep(step)
                # Truco: el valor mínimo "especial" muestra "Default PyWake"
                spin.setMinimum(0.0)  # 0.0 representa "no override"
                spin.setMaximum(vmax)
                spin.setSpecialValueText(f"Valor PyWake por defecto ({default:g})")
                spin.setToolTip(tip)
                # Restaurar valor persistido (0 = default)
                stored = self._qsettings.value(
                    f"wake_param/{key}/{kw}", 0.0, type=float
                )
                # Validar contra el rango mínimo positivo del parámetro
                if stored > 0 and stored < vmin:
                    stored = 0.0
                spin.setValue(float(stored))
                # Persistir en cada cambio
                spin.valueChanged.connect(
                    lambda val, k=key, p=kw: self._qsettings.setValue(
                        f"wake_param/{k}/{p}", float(val)
                    )
                )
                # Refrescar la nota inferior con el k activo cuando cambie
                spin.valueChanged.connect(self._update_wake_turb_note)
                self._adv_params_widgets[key][kw] = spin
                row_lbl = QtWidgets.QLabel(label)
                row_lbl.setToolTip(tip)
                grid.addRow(row_lbl, spin)

            page.setLayout(grid)
            self.stk_adv_params.addWidget(page)
            self._adv_params_pages[key] = page

        v.addWidget(self.stk_adv_params)
        parent_layout.addWidget(grp)
        self._grp_adv_params = grp

    def _on_wake_deficit_changed_refresh_advanced(self) -> None:
        """Cambia la página visible del panel avanzado según el modelo seleccionado."""
        if not hasattr(self, "stk_adv_params"):
            return
        try:
            key = (self._get_selected_wake_deficit() or "BG").upper()
        except Exception:
            key = "BG"
        page = self._adv_params_pages.get(key)
        if page is not None:
            self.stk_adv_params.setCurrentWidget(page)

    def _show_advanced_params_help(self) -> None:
        """Muestra el texto de ayuda específico del modelo seleccionado."""
        try:
            key = (self._get_selected_wake_deficit() or "BG").upper()
        except Exception:
            key = "BG"
        txt = self._ADVANCED_HELP.get(
            key,
            "<i>Sin información específica para este modelo.</i>"
        )
        QtWidgets.QMessageBox.information(
            self, f"Ayuda · Parámetros del modelo ({key})", txt
        )

    def _get_wake_deficit_kwargs(self) -> Dict[str, Any]:
        """Devuelve los overrides físicos del usuario para el modelo activo.

        Solo se incluyen kwargs con valor > 0 (0 = «Default PyWake»).
        """
        kwargs: Dict[str, Any] = {}
        if not hasattr(self, "_adv_params_widgets"):
            return kwargs
        try:
            grp = getattr(self, "_grp_adv_params", None)
            if grp is not None and not grp.isChecked():
                return kwargs
        except Exception:
            pass
        try:
            key = (self._get_selected_wake_deficit() or "BG").upper()
        except Exception:
            key = "BG"
        for kw, spin in self._adv_params_widgets.get(key, {}).items():
            try:
                v = float(spin.value())
            except Exception:
                continue
            if v > 0:  # 0 = no override
                kwargs[kw] = v

        # PyWake espera algunos parámetros como listas, mientras que la UI los
        # muestra como spinboxes separados para que el usuario entienda qué toca.
        if key in ("NIA", "ZG") and ("a1" in kwargs or "a2" in kwargs):
            a1 = float(kwargs.pop("a1", 0.38))
            a2 = float(kwargs.pop("a2", 0.004))
            kwargs["a"] = [a1, a2]
        if key in ("TG", "TNOJ") and ("cTI1" in kwargs or "cTI2" in kwargs):
            c1 = float(kwargs.pop("cTI1", 1.5))
            c2 = float(kwargs.pop("cTI2", 0.8))
            kwargs["cTI"] = [c1, c2]
        return kwargs

    def _show_wake_turb_help(self):
        txt = (
            "<b>Qué es el wake effect, en simple</b><br><br>"
            "Cuando una turbina extrae energía del viento, detrás de ella queda una zona con menos velocidad y más turbulencia. "
            "Esa zona es la <b>estela</b>. Si otra turbina cae dentro, producirá menos AEP.<br><br>"
            "El <b>wake deficit model</b> decide cuánta velocidad se pierde y cómo se recupera la estela aguas abajo.<br><br>"
            "<b>Cómo elegir sin ser experto</b><br>"
            "• <b>BastankhahGaussianDeficit</b>: opción robusta para comparar layouts y parques offshore limpios.<br>"
            "• <b>NiayifarGaussianDeficit</b>: parecido a Bastankhah, pero la turbulencia TI pesa más en la expansión de la estela.<br>"
            "• <b>ZongGaussianDeficit</b>: más avanzado; útil si quieres una representación más rica del near wake y de la recuperación por TI.<br>"
            "• <b>TurboGaussianDeficit</b>: gaussiano sensible a turbulencia efectiva; interesante cuando quieres que la TI ambiente/añadida influya en el AEP.<br>"
            "• <b>NOJDeficit</b>: muy rápido y clásico; bueno para screening masivo, pero más simplificado.<br>"
            "• <b>TurboNOJDeficit</b>: mantiene la ligereza de NOJ, pero permite que la TI influya más.<br><br>"
            "<b>Idea sencilla</b><br>"
            "Para más realismo cuando la turbulencia debe influir en la recuperación de estela, usa <b>Niayifar/Zong/TurboGaussian</b>. Para un cálculo rápido, usa <b>NOJ/TurboNOJ</b>. Para una base robusta de comparación, usa <b>Bastankhah</b>.<br><br>"
            "Importante: cargar un raster TI no garantiza por sí solo que cambie mucho el AEP. El efecto se ve de verdad si el modelo de estela elegido usa la TI de forma explícita."
        )
        QtWidgets.QMessageBox.information(self, "Ayuda · Wake effect y modelo de estela", txt)

    def _show_turbulence_model_help(self):
        txt = (
            "<b>Qué significa la turbulencia en este plugin</b><br><br>"
            "• <b>TI raster / WRG</b>: describe la <b>turbulencia ambiente</b> del site. Es un dato de entrada del recurso.<br>"
            "• <b>Modelo de turbulencia</b>: calcula la <b>turbulencia añadida por estela</b> detrás de las turbinas.<br>"
            "• <b>Modelo de estela</b>: decide si esa TI ambiente/efectiva cambia realmente el déficit y, por tanto, el AEP.<br><br>"
            "<b>Cómo leerlo físicamente</b><br>"
            "• Si solo aportas un raster TI, el plugin usa esa TI horizontal para todas las turbinas; si hay varias alturas de buje, eso es una <b>aproximación vertical</b>.<br>"
            "• Si aportas varios raster(s) TI a distintas alturas, el plugin intenta reconstruir <b>TI(x,y,h)</b> e interpolar por altura.<br>"
            "• Si no aportas raster TI en WRG, el plugin avisa y usa la <b>TI ambiente fallback definida por el usuario</b> como campo uniforme.<br><br>"
            "<b>Cuándo importa mucho en el AEP</b><br>"
            "• <b>BastankhahGaussianDeficit (BG)</b> y <b>NOJDeficit</b>: la TI no cambia mucho el déficit base del wake; el impacto sobre el AEP suele ser limitado.<br>"
            "• <b>NiayifarGaussianDeficit</b>, <b>ZongGaussianDeficit</b>, <b>TurboGaussianDeficit</b> y <b>TurboNOJDeficit</b>: la TI ambiente/efectiva sí puede influir más en la apertura y recuperación de la estela.<br><br>"
            "<b>Qué conviene según el parque</b><br>"
            "• <b>Offshore con viento relativamente homogéneo</b>: una sola capa TI puede ser suficiente si las alturas de buje son parecidas.<br>"
            "• <b>Onshore, terreno rugoso o alturas de buje distintas</b>: para más realismo, usa raster(s) TI y un wake model sensible a TI (Niayifar, Zong, TurboGaussian o TurboNOJ).<br>"
            "• <b>Varios modelos de aerogenerador</b>: si mezclas alturas de buje, una sola capa TI es una aproximación; varias alturas de TI representan mejor la variación vertical.<br><br>"
            "<b>Qué elegir en el selector de modelo de turbulencia</b><br>"
            "• <b>STF2017</b>: buena opción general y la recomendación por defecto cuando necesitas un modelo de turbulencia añadida robusto.<br>"
            "• <b>STF2005</b>: alternativa clásica y sencilla si quieres comparar con configuraciones más antiguas o más conservadoras.<br>"
            "• <b>CrespoHernandez</b> y <b>GCLTurbulence</b>: útiles para comparativas o compatibilidad con ciertos modelos/estudios, pero el impacto final depende del wake model que elijas.<br><br>"
            "<b>Regla práctica</b><br>"
            "Si tu objetivo es que la turbulencia influya físicamente en el AEP, no basta con seleccionar un modelo de turbulencia: también necesitas un <b>modelo de estela sensible a TI</b>."
        )
        QtWidgets.QMessageBox.information(self, "Ayuda · Turbulencia", txt)

    def _show_blockage_help(self):
        txt = (
            "<b>Qué es el bloqueo</b><br><br>"
            "Además de crear una estela detrás, una turbina también puede frenar ligeramente el viento antes de que el flujo llegue al rotor. Ese efecto aguas arriba se llama <b>bloqueo</b> o <i>blockage</i>.<br><br>"
            "<b>Compatibilidad</b><br>"
            "• No depende del recurso WRG/GRD: depende del motor de PyWake y del modelo de bloqueo.<br>"
            "• Con <b>PropagateDownwind</b> se desactiva, porque ese motor solo calcula efectos aguas abajo.<br>"
            "• Con <b>All2AllIterative</b> o <b>PropagateUpDownIterative</b> el plugin puede intentar incluirlo con los wake models disponibles.<br><br>"
            "<b>Parámetros</b><br>"
            "En esta versión experimental no se exponen parámetros internos de bloqueo. Son calibraciones propias del modelo de PyWake; para comparar sensibilidad, cambia de modelo en lugar de tocar constantes internas.<br><br>"
            "<b>Qué opción usar</b><br>"
            "SelfSimilarityDeficit2020 es la opción principal. VortexCylinder/VortexDipole/HybridInduction se dejan como alternativas si tu instalación de PyWake las soporta."
        )
        QtWidgets.QMessageBox.information(self, "Ayuda · Bloqueo", txt)

    def _update_blockage_note(self) -> None:
        """Nota inferior del bloque de bloqueo: estado activo + interacción con engine."""
        if not hasattr(self, 'lbl_blockage_note'):
            return
        try:
            eng = (self._get_selected_wfm_engine() or '').upper()
        except Exception:
            eng = ''
        try:
            blk = (self._get_selected_blockage_deficit() or 'NONE').upper()
        except Exception:
            blk = 'NONE'

        # Caso 1: PDW desactiva el bloqueo automáticamente. Es el caso «más confuso»
        # de la UI (combo en gris) y el que más merece explicación.
        if eng == 'PDW':
            msg = (
                "<b>Bloqueo desactivado</b> porque el motor es <b>PropagateDownwind</b> "
                "(solo propaga estelas hacia abajo, no soporta bloqueo). "
                "Si quieres incluir bloqueo, cambia el motor a <b>All2AllIterative</b> o "
                "<b>PropagateUpDownIterative</b>."
            )
            self.lbl_blockage_note.setText(msg)
            return

        # Caso 2: motor compatible pero el usuario ha elegido «Ninguno»
        if blk in ('NONE', 'NINGUNO', 'NO', 'OFF', ''):
            msg = (
                "<b>Sin bloqueo:</b> el cálculo no incluirá la reducción de velocidad upstream. "
                "En parques offshore grandes esto suele subestimar las pérdidas en ~1–3 % AEP."
            )
            self.lbl_blockage_note.setText(msg)
            return

        # Caso 3: bloqueo activo. Mostrar modelo + nota de constantes.
        descr = {
            'SS2020': "SelfSimilarityDeficit2020 — opción principal para bloqueo. No requiere parámetros de usuario en esta versión experimental.",
            'SELFSIMILARITYDEFICIT2020': "SelfSimilarityDeficit2020 — opción principal para bloqueo. No requiere parámetros de usuario en esta versión experimental.",
            'SS': "SelfSimilarityDeficit — formulación self-similarity clásica. No requiere parámetros de usuario en esta versión experimental.",
            'SELFSIMILARITYDEFICIT': "SelfSimilarityDeficit — formulación self-similarity clásica. No requiere parámetros de usuario en esta versión experimental.",
            'VC': "VortexCylinder — modelo de inducción/bloqueo basado en cilindro de vorticidad. Sin parámetros de usuario en esta versión experimental.",
            'VORTEXCYLINDER': "VortexCylinder — modelo de inducción/bloqueo basado en cilindro de vorticidad. Sin parámetros de usuario en esta versión experimental.",
            'VD': "VortexDipole — alternativa de inducción. Sin parámetros de usuario en esta versión experimental.",
            'VORTEXDIPOLE': "VortexDipole — alternativa de inducción. Sin parámetros de usuario en esta versión experimental.",
            'HI': "HybridInduction — combina aproximaciones de inducción. Sin parámetros de usuario en esta versión experimental.",
            'HYBRIDINDUCTION': "HybridInduction — combina aproximaciones de inducción. Sin parámetros de usuario en esta versión experimental.",
            'RATH': "Rathmann — modelo de compatibilidad para configuraciones antiguas. Sin parámetros de usuario en esta versión experimental.",
            'RATHMANN': "Rathmann — modelo de compatibilidad para configuraciones antiguas. Sin parámetros de usuario en esta versión experimental.",
        }.get(blk, f"{blk} — modelo no estándar; revisar disponibilidad en esta versión de PyWake.")

        msg = "<b>Modelo activo:</b> " + descr
        if eng == 'PUD':
            msg += " <i>Con PUD se fuerza use_effective_ws=True para evitar errores de PyWake.</i>"
        self.lbl_blockage_note.setText(msg)

    def _update_turbulence_note(self) -> None:
        """Nota inferior dedicada al modelo de turbulencia añadida."""
        if not hasattr(self, 'lbl_turbulence_note'):
            return
        try:
            turb = (self._get_selected_turbulence_model() or 'NONE').upper()
        except Exception:
            turb = 'NONE'

        if turb in ('NONE', 'NINGUNO', 'NO', 'OFF', ''):
            msg = (
                "<b>Sin turbulencia añadida:</b> el cálculo usa la TI ambiente del recurso "
                "(WRG/raster TI o valor manual), pero no suma la turbulencia creada por las estelas. "
                "Esto es válido para modelos poco sensibles a TI; si usas Niayifar, Zong, TurboGaussian o TurboNOJ, la turbulencia añadida puede afectar más al AEP."
            )
            self.lbl_turbulence_note.setText(msg)
            return

        descr = {
            'STF2017': "STF2017 — Frandsen 2007 / IEC 61400-1 ed.3. Coeficientes empíricos fijos del paper. <b>Recomendado por defecto</b>.",
            'STF2005': "STF2005 — Frandsen original. Coeficientes empíricos fijos. Útil para comparar con configuraciones antiguas o más conservadoras.",
            'GCL': "GCLTurbulence — derivado Frandsen, formulación clásica. Constantes fijas.",
            'CH': "CrespoHernandez — Crespo &amp; Hernández 1996, ajuste empírico clásico. Constantes fijas del paper.",
            'CRESPOHERNANDEZ': "CrespoHernandez — Crespo &amp; Hernández 1996, ajuste empírico clásico. Constantes fijas del paper.",
        }.get(turb, f"{turb} — modelo no estándar; revisar disponibilidad en esta versión de PyWake.")

        msg = (
            "<b>Modelo activo:</b> " + descr +
            "<br>La TI ambiente siempre viene del recurso/raster o del valor manual. Este selector añade turbulencia generada por estelas. "
            "Su impacto en AEP será mayor si el wake model usa TI de forma explícita, como Niayifar, Zong, TurboGaussian o TurboNOJ."
        )
        self.lbl_turbulence_note.setText(msg)

    def _update_wake_turb_note(self) -> None:
        if not hasattr(self, 'lbl_wake_turb_note'):
            return
        try:
            wake = (self._get_selected_wake_deficit() or '').upper()
        except Exception:
            wake = 'BG'
        try:
            turb = (self._get_selected_turbulence_model() or '').upper()
        except Exception:
            turb = 'NONE'
        try:
            eng = (self._get_selected_wfm_engine() or '').upper()
        except Exception:
            eng = ''

        if wake in ('BG', 'BASTANKHAHGAUSSIANDEFICIT'):
            msg = 'Bastankhah: opción robusta para comparar layouts. Usa una formulación gaussiana con parámetros fijos; la TI ambiente no cambia mucho el déficit base.'
        elif wake in ('NOJ', 'NOJDEFICIT'):
            msg = 'NOJ/Jensen: modelo clásico y muy rápido. Usa una expansión fija; la TI ambiente suele tener poco efecto directo en el déficit.'
        elif wake in ('TNOJ', 'TURBONOJ', 'TURBONOJDEFICIT'):
            msg = 'TurboNOJ: versión ligera tipo NOJ, pero con más sensibilidad a turbulencia y recuperación de estela.'
        elif wake in ('NIA', 'NIAYIFARGAUSSIANDEFICIT'):
            msg = 'Niayifar: gaussiano TI-sensitive. Recomendable si quieres que el raster TI o la TI manual influyan en la recuperación de estela.'
        elif wake in ('ZG', 'ZONGGAUSSIANDEFICIT'):
            msg = 'Zong: avanzado y sensible a TI. Útil para estudiar near wake y recuperación por turbulencia con más detalle.'
        elif wake in ('TG', 'TURBOGAUSSIANDEFICIT'):
            msg = 'TurboGaussian: gaussiano sensible a TI efectiva. Tiene sentido cuando la turbulencia ambiente y añadida deben influir en el AEP.'
        else:
            msg = 'El wake effect reduce el viento disponible detrás de cada turbina. Cada modelo aproxima esa pérdida de forma distinta.'

        if turb in ('NONE', 'NINGUNO', 'NO', 'OFF') and wake in ('NIA', 'NIAYIFARGAUSSIANDEFICIT', 'ZG', 'ZONGGAUSSIANDEFICIT', 'TG', 'TURBOGAUSSIANDEFICIT', 'TNOJ', 'TURBONOJ', 'TURBONOJDEFICIT'):
            msg += ' Aviso: el modelo es sensible a TI, pero has dejado la turbulencia añadida en Ninguno; se usará la TI ambiente, pero no se sumará TI generada por estelas.'
        if eng == 'PDW':
            msg += ' Con PropagateDownwind, el bloqueo se desactiva automáticamente.'

        try:
            param_line = self._format_active_param_line(wake)
            if param_line:
                msg += "<br><span style='color:#444;'>" + param_line + "</span>"
                self.lbl_wake_turb_note.setTextFormat(QtCore.Qt.RichText)
        except Exception:
            pass

        self.lbl_wake_turb_note.setText(msg)

    def _format_active_param_line(self, wake_key: str) -> str:
        """Construye la línea «Parámetros activos…» para la nota inferior."""
        defaults = {
            "NOJ": [("k", 0.04)],
            "BG":  [("k", 0.0324555), ("ceps", 0.20)],
            "NIA": [("a1", 0.38), ("a2", 0.004), ("ceps", 0.20)],
            "ZG":  [("a1", 0.38), ("a2", 0.004), ("deltawD", 0.70710678), ("eps_coeff", 0.35355339), ("lam", 7.5), ("B", 3.0)],
            "TG":  [("A", 0.04), ("cTI1", 1.5), ("cTI2", 0.8), ("ceps", 0.25)],
            "TNOJ": [("A", 0.04), ("cTI1", 1.5), ("cTI2", 0.8)],
        }
        key = wake_key
        norm = {
            "NOJDEFICIT": "NOJ",
            "BASTANKHAHGAUSSIANDEFICIT": "BG",
            "NIAYIFARGAUSSIANDEFICIT": "NIA",
            "ZONGGAUSSIANDEFICIT": "ZG",
            "TURBONOJDEFICIT": "TNOJ",
            "TURBOGAUSSIANDEFICIT": "TG",
        }
        key = norm.get(key, key)
        if key not in defaults:
            return ""

        # Leer valores visibles, aunque el groupbox no esté activado, para que
        # la nota distinga claramente default vs override.
        active_kw = self._get_wake_deficit_kwargs()
        raw_widgets = getattr(self, "_adv_params_widgets", {}).get(key, {})
        bits = []
        for kw, defval in defaults[key]:
            user_override = False
            shown_val = defval
            try:
                spin = raw_widgets.get(kw)
                if spin is not None and float(spin.value()) > 0 and getattr(self, "_grp_adv_params", None) is not None and self._grp_adv_params.isChecked():
                    user_override = True
                    shown_val = float(spin.value())
            except Exception:
                pass
            # Casos agrupados en PyWake: a=[a1,a2], cTI=[cTI1,cTI2]
            if kw in ("a1", "a2") and "a" in active_kw:
                idx = 0 if kw == "a1" else 1
                try:
                    shown_val = float(active_kw["a"][idx]); user_override = True
                except Exception:
                    pass
            if kw in ("cTI1", "cTI2") and "cTI" in active_kw:
                idx = 0 if kw == "cTI1" else 1
                try:
                    shown_val = float(active_kw["cTI"][idx]); user_override = True
                except Exception:
                    pass
            suffix = "<i>(valor editado por usuario)</i>" if user_override else "<i>(valor PyWake por defecto)</i>"
            bits.append(f"{kw} = {shown_val:g} {suffix}")
        return "<b>Parámetros activos:</b> " + " · ".join(bits)

    def _rebuild_rows(self):
        # Conservar el estado de filas ya definidas cuando cambia el número de
        # modelos. Antes, subir el spinbox reconstruía la UI desde cero y se
        # perdían las turbinas ya definidas. Esto es clave para el flujo del
        # botón «Generar capas de puntos»: cada click puede añadir un modelo
        # nuevo sin borrar los anteriores.
        old_rows = list(getattr(self, "_rows", []) or [])
        self._clear_layout(self.rows_box)
        self._rows.clear()
        for i in range(self.sp_n.value()):
            roww = QtWidgets.QWidget(self)
            vrow = QtWidgets.QVBoxLayout(roww)
            vrow.setContentsMargins(0, 0, 0, 0)

            # Encabezado
            top = QtWidgets.QHBoxLayout()
            name_lbl = QtWidgets.QLabel(f"Modelo {i+1}: <i>(sin definir)</i>")
            name_lbl.setMinimumWidth(180)
            name_lbl.setWordWrap(True)
            # Badge: «(editado, sin guardar)» — solo visible cuando la capa de este
            # modelo se ha modificado en el mapa interactivo y no se ha exportado.
            dirty_badge = QtWidgets.QLabel("● editado en mapa, sin guardar")
            dirty_badge.setStyleSheet("color: #b8860b; font-style: italic;")
            dirty_badge.setToolTip(
                "Has movido/añadido/borrado turbinas en el mapa interactivo.\n"
                "El cálculo de AEP usa esas coordenadas vivas (no el CSV original).\n"
                "Pulsa «Exportar layout editado…» si quieres persistirlas a CSV."
            )
            dirty_badge.setVisible(False)
            btn_define = QtWidgets.QPushButton("Definir…")
            btn_define.setToolTip("Abrir diálogo para cargar curva de potencia")
            btn_define.clicked.connect(lambda _, idx=i: self._define_model(idx))
            btn_view_curve = QtWidgets.QPushButton("Ver curva")
            btn_view_curve.setToolTip(
                "Ver la curva de potencia (y Ct si está disponible) de la turbina definida.\n"
                "Útil para detectar errores de carga (kW vs W, columnas invertidas, etc.)."
            )
            btn_view_curve.setEnabled(False)  # se habilita tras Definir
            btn_view_curve.clicked.connect(lambda _, idx=i: self._show_curve_for_model(idx))
            top.addWidget(name_lbl, 1)
            top.addWidget(dirty_badge, 0)
            top.addWidget(btn_view_curve, 0)
            top.addWidget(btn_define, 0)

            # CSV de coordenadas
            bot = QtWidgets.QHBoxLayout()
            lbl_csv = QtWidgets.QLabel("Coordenadas (CSV X,Y):")
            ed_csv = QtWidgets.QLineEdit()
            ed_csv.setPlaceholderText("Selecciona CSV con columnas X,Y para este modelo")
            btn_csv = QtWidgets.QPushButton("Coords CSV…")
            btn_csv.clicked.connect(lambda _, idx=i, le=ed_csv: self._pick_coords_csv(idx, le))

            btn_make_layer = QtWidgets.QPushButton("Cargar capa")
            btn_make_layer.setToolTip("Crear/actualizar la capa de puntos para este modelo")
            btn_make_layer.clicked.connect(lambda _, idx=i: self._generate_point_layer_one(idx, force_reload_csv=True, activate_interactive=False))

            bot.addWidget(lbl_csv)
            bot.addWidget(ed_csv, 1)
            bot.addWidget(btn_csv, 0)
            bot.addWidget(btn_make_layer, 0)

            vrow.addLayout(top)
            vrow.addLayout(bot)

            self.rows_box.addWidget(roww)
            row_state = {
                "name_lbl": name_lbl,
                "wt": None,
                "name": None,
                "meta": None,
                "coords_csv_le": ed_csv,
                "dirty_badge": dirty_badge,
                "btn_view_curve": btn_view_curve,
            }

            # Restaurar datos anteriores de esta fila, si existían. No copiamos
            # widgets viejos; solo estado de negocio y texto del CSV.
            if i < len(old_rows):
                old = old_rows[i] or {}
                row_state["wt"] = old.get("wt")
                row_state["name"] = old.get("name")
                row_state["meta"] = old.get("meta")
                try:
                    old_le = old.get("coords_csv_le")
                    if old_le is not None:
                        ed_csv.setText(old_le.text())
                except Exception:
                    pass

            self._rows.append(row_state)
            try:
                self._refresh_model_row_header(i)
            except Exception:
                pass
        apply_i18n(self)

    def _refresh_model_row_header(self, idx: int) -> None:
        """Refresca etiqueta y botón de curva de una fila de modelo."""
        try:
            r = self._rows[idx]
        except Exception:
            return
        name_lbl = r.get("name_lbl")
        btn_curve = r.get("btn_view_curve")
        name = r.get("name")
        meta = r.get("meta") if isinstance(r, dict) else None
        if not name:
            try:
                if name_lbl is not None:
                    name_lbl.setText(f"Modelo {idx+1}: <i>(sin definir)</i>")
            except Exception:
                pass
            try:
                if btn_curve is not None:
                    btn_curve.setEnabled(False)
            except Exception:
                pass
            return

        try:
            d_val = (meta or {}).get("diam") if isinstance(meta, dict) else None
            h_val = (meta or {}).get("hh") if isinstance(meta, dict) else None
            p_val = (meta or {}).get("p_rated_kw") if isinstance(meta, dict) else None
            extras = []
            if d_val:
                extras.append(f"D={float(d_val):.0f} m")
            if h_val:
                extras.append(f"Hub={float(h_val):.0f} m")
            if p_val:
                extras.append(f"P={float(p_val)/1000:.2f} MW")
            extra_txt = (" · " + ", ".join(extras)) if extras else ""
        except Exception:
            extra_txt = ""
        try:
            if name_lbl is not None:
                name_lbl.setText(f"Modelo {idx+1}: <b>{name}</b>{extra_txt}")
        except Exception:
            pass
        try:
            if btn_curve is not None:
                btn_curve.setEnabled(True)
        except Exception:
            pass

    # ------------------ helpers UI ------------------
    def _define_model(self, idx: int):
        # Usa factoría si te la pasan; si no, el diálogo del plugin
        if self._custom_dialog_factory is None:
            try:
                from .ag_core.turbine_ui import CustomTurbineDialog
                dlg = CustomTurbineDialog(self)
            except Exception:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Modelos",
                    "No se pudo abrir el diálogo de turbina:\n" + traceback.format_exc(),
                )
                return
        else:
            dlg = self._custom_dialog_factory(self)

        if dlg.exec_() != dlg.Accepted:
            return

        # Objeto WT + metadatos de diálogo
        try:
            wt = dlg.get_wind_turbine()
        except Exception:
            wt = None
        meta = getattr(dlg, "result_data", lambda: None)()

        # Nombre robusto: priorizar el metadato devuelto por la pestaña realmente creada.
        # Antes se leía primero ed_name_c; como esa pestaña siempre existe y tiene un valor
        # por defecto, los presets manuales podían quedar etiquetados como "Custom WT (CSV)".
        name = None
        if isinstance(meta, dict):
            try:
                t = str(meta.get("name") or "").strip()
                if t:
                    name = t
            except Exception:
                name = None
        if not name:
            for attr in ("le_name", "ed_name", "ed_name_m", "ed_name_c"):
                if hasattr(dlg, attr):
                    try:
                        t = getattr(dlg, attr).text().strip()
                        if t:
                            name = t
                            break
                    except Exception:
                        pass
        if not name:
            name = "Custom WT"

        # Optional publication-safe diagnostic: only prints when VELANTISWIND_DEBUG=1.
        try:
            path = meta.get("path") if isinstance(meta, dict) else None
            if path and os.path.isfile(path):
                hdr = _preview_csv_header(path)
                _debug_print(f"[Energy UI] Turbine curve CSV ({os.path.basename(path)}) header: {hdr}")
        except Exception:
            pass

        self._rows[idx]["wt"] = wt
        self._rows[idx]["name"] = name
        self._rows[idx]["meta"] = meta

        # Si ya existía una capa vacía creada desde «Generar capas de puntos»
        # con el nombre por defecto (Modelo N), conservarla y asociarla al nuevo
        # modelo en lugar de obligar al usuario a volver a crear/seleccionar layouts.
        try:
            lyr = self._find_interactive_layer_for_row(idx)
            if lyr is not None:
                target_name = f"{name} (CSV)"
                if lyr.name() != target_name:
                    # Evitar choque si ya existe una capa distinta con ese nombre.
                    other = _find_layer_by_name(target_name)
                    if other is None or other.id() == lyr.id():
                        lyr.setName(target_name)
                lyr.setCustomProperty("velantis/layer_role", "energy_turbines")
                lyr.setCustomProperty("velantis/model_name", str(name or ""))
                lyr.setCustomProperty("velantis/model_index", int(idx))
                if isinstance(meta, dict):
                    if meta.get("hh") is not None:
                        lyr.setCustomProperty("velantis/hub_height_m", float(meta.get("hh")))
                    if meta.get("diam") is not None:
                        lyr.setCustomProperty("velantis/diameter_m", float(meta.get("diam")))
        except Exception:
            pass

        # Etiqueta enriquecida: nombre + D + Hub + P_nom (si hay)
        self._refresh_model_row_header(idx)

    def _show_curve_for_model(self, idx: int) -> None:
        """Muestra un diálogo con la curva de potencia (y Ct si está) del modelo idx."""
        try:
            r = self._rows[idx]
        except Exception:
            return
        meta = r.get("meta") or {}
        ws = meta.get("ws") or []
        pw_kw = meta.get("power_kw") or []
        ct = meta.get("ct")
        if not ws or not pw_kw:
            QtWidgets.QMessageBox.information(
                self, "Curva de potencia",
                "Esta turbina no tiene la curva guardada en metadatos. "
                "Vuelve a pulsar «Definir…» para regenerarla."
            )
            return
        try:
            self._open_curve_dialog(
                title=r.get("name") or f"Modelo {idx+1}",
                ws=list(ws), pw_kw=list(pw_kw), ct=list(ct) if ct else None,
                meta=meta,
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Curva de potencia", f"No se pudo dibujar la curva:\n{e}"
            )

    def _open_curve_dialog(self, *, title: str, ws, pw_kw, ct, meta: Dict[str, Any]) -> None:
        """Pop-up modal con la curva P(ws) y Ct(ws) si está disponible."""
        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("Qt5Agg")
            except Exception:
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Curva de potencia",
                f"matplotlib no disponible en este QGIS:\n{e}"
            )
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Curva de potencia · {title}")
        dlg.setMinimumSize(640, 460)
        v = QtWidgets.QVBoxLayout(dlg)

        header = QtWidgets.QLabel()
        d_val = meta.get("diam")
        h_val = meta.get("hh")
        p_val = meta.get("p_rated_kw")
        bits = []
        if d_val:
            bits.append(f"D = {float(d_val):.1f} m")
        if h_val:
            bits.append(f"Hub = {float(h_val):.1f} m")
        if p_val:
            bits.append(f"P_nom = {float(p_val)/1000:.2f} MW")
        bits.append(f"{len(ws)} puntos")
        header.setText("  ·  ".join(bits))
        header.setStyleSheet("color: #4f5d6b;")
        v.addWidget(header)

        fig = plt.figure(figsize=(7, 4.2), dpi=100)
        canvas = FigureCanvas(fig)
        v.addWidget(canvas, 1)

        ax1 = fig.add_subplot(111)
        ax1.plot(ws, pw_kw, "-o", color="#103b67", markersize=3, linewidth=1.5, label="Potencia (kW)")
        ax1.set_xlabel("Velocidad de viento (m/s)")
        ax1.set_ylabel("Potencia (kW)", color="#103b67")
        ax1.tick_params(axis="y", labelcolor="#103b67")
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, max(float(ws[-1]), 25))

        if ct:
            ax2 = ax1.twinx()
            ax2.plot(ws, ct, "--s", color="#b8860b", markersize=3, linewidth=1.2, label="Ct")
            ax2.set_ylabel("Ct (–)", color="#b8860b")
            ax2.tick_params(axis="y", labelcolor="#b8860b")
            ax2.set_ylim(0, max(1.0, max(ct) * 1.1))

        ax1.set_title(title)
        fig.tight_layout()
        canvas.draw()

        # Botón cerrar
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        v.addWidget(btns)
        dlg.exec_()

    def _extract_height_from_filename(self, path: str) -> Optional[float]:
        name = os.path.basename(str(path or ""))
        patterns = (
            r'(?i)(?:ti(?:mean)?|turb(?:ulence)?)[^\d]{0,5}(\d+(?:[\.,]\d+)?)',
            r'(?i)(\d+(?:[\.,]\d+)?)\s*m(?:[^a-zA-Z]|$)',
            r'(?i)h(?:ub)?[_-]?(\d+(?:[\.,]\d+)?)',
        )
        for pat in patterns:
            m = re.search(pat, name)
            if m:
                try:
                    return float(m.group(1).replace(',', '.'))
                except Exception:
                    pass
        return None

    def _collect_current_hub_heights(self) -> List[float]:
        vals: List[float] = []
        for r in getattr(self, '_rows', []) or []:
            meta = r.get('meta') if isinstance(r, dict) else None
            if not isinstance(meta, dict):
                continue
            for key in ('hh', 'hub_height', 'HH'):
                if key in meta and meta.get(key) is not None:
                    try:
                        vals.append(float(meta.get(key)))
                        break
                    except Exception:
                        pass
        out: List[float] = []
        for v in vals:
            if not any(abs(v - x) < 1e-6 for x in out):
                out.append(v)
        return sorted(out)

    def _show_wrg_ti_help(self):
        txt = (
            "<b>Qué es TI</b><br><br>"
            "TI significa <b>turbulence intensity</b>. En simple: mide cuánto fluctúa el viento alrededor de su velocidad media. "
            "Más TI suele significar más mezcla del flujo y una recuperación de estela distinta.<br><br>"
            "<b>Dos turbulencias diferentes</b><br>"
            "• <b>TI ambiente</b>: viene del recurso eólico o de un raster TI. Es el viento que llega al parque antes de las turbinas.<br>"
            "• <b>TI añadida por estela</b>: la genera cada turbina detrás de sí. La calcula el modelo de turbulencia de PyWake, si lo activas.<br><br>"
            "<b>Qué hace el plugin</b><br>"
            "• Si cargas raster TI, se usa como turbulencia ambiente espacial.<br>"
            "• Si no cargas raster TI, se usa el valor manual de la interfaz como hipótesis uniforme.<br>"
            "• Si tienes varios raster a distintas alturas, puedes indicar 90;120;... para interpolar por altura de buje.<br><br>"
            "<b>Cuándo importa más</b><br>"
            "BG/NOJ son robustos pero poco sensibles a TI. Niayifar, Zong, TurboGaussian y TurboNOJ hacen que la TI afecte más a la recuperación de estela y al AEP.<br><br>"
            "<b>Idea sencilla</b><br>"
            "Si no tienes datos de turbulencia, una TI manual uniforme permite correr el cálculo. Para más realismo en onshore, terreno complejo o varias alturas de buje, usa raster TI, idealmente por altura."
        )
        QtWidgets.QMessageBox.information(self, "Ayuda · Turbulencia TI", txt)

    def _maybe_warn_about_ti_setup(self, use_wrg: bool, wrg_ti_paths: List[str], wrg_ti_heights_m: Optional[List[Optional[float]]] = None) -> None:
        if not use_wrg:
            return
        hubs = self._collect_current_hub_heights()
        if len(hubs) <= 1:
            return
        if not wrg_ti_paths:
            QtWidgets.QMessageBox.information(
                self,
                "Turbulencia TI",
                "Has definido varios hub heights pero no has seleccionado raster(s) TI. "
                f"El cálculo seguirá con TI uniforme = {self.sp_fixed_ti.value():.1f} %. Es válido para una prueba, pero no representa variación vertical de turbulencia."
            )
            return
        overrides = list(wrg_ti_heights_m or [])
        heights = [
            (overrides[i] if i < len(overrides) and overrides[i] is not None else self._extract_height_from_filename(p))
            for i, p in enumerate(wrg_ti_paths)
        ]
        valid = [h for h in heights if h is not None]
        if len(wrg_ti_paths) == 1:
            htxt = f" a {valid[0]:g} m" if valid else ""
            QtWidgets.QMessageBox.information(
                self,
                "Turbulencia WRG",
                "Has definido varios hub heights pero solo un raster TI" + htxt + ". "
                "El plugin aplicará esa TI a todas las alturas como aproximación."
            )
            return
        if len(set(round(h, 6) for h in valid)) < 2:
            QtWidgets.QMessageBox.information(
                self,
                "Turbulencia WRG",
                "Se han seleccionado varios raster(s) TI, pero no he podido identificar al menos dos alturas distintas en sus nombres. "
                "El plugin no podrá reconstruir una TI vertical fiable; revisa nombres como TImean.90.asc o TI_120m.tif."
            )

    def _pick_dir(self):
        start_dir = self.ed_dir.text().strip() or self._last_wasp_dir or os.path.expanduser("~")
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecciona carpeta con grids WAsP", start_dir)
        if d:
            self.ed_dir.setText(d)
            self._last_wasp_dir = d
            try:
                self._qsettings.setValue("last_wasp_dir", d)
            except Exception:
                pass
            self._draw_current_resource_extent(zoom=False, manual=False)

    def _pick_wrg(self):
        """Selecciona uno o varios .wrg o .zip que contenga .wrg (formato WRG estándar)."""
        start_dir = ""
        try:
            start_dir = os.path.dirname(self.ed_wrg.text().strip())
        except Exception:
            start_dir = ""
        if not start_dir:
            try:
                start_dir = self._qsettings.value("last_wrg_dir", "", type=str)
            except Exception:
                start_dir = ""
        if not start_dir:
            start_dir = os.path.expanduser("~")

        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Selecciona WRG/ZIP",
            start_dir,
            "WRG/ZIP (*.wrg *.zip);;Todos (*.*)",
        )
        if paths:
            txt = ";".join(paths)
            self.ed_wrg.setText(txt)
            # guardamos el primero para persistencia
            self._last_wrg_path = paths[0]
            try:
                self._qsettings.setValue("last_wrg_path", paths[0])
                self._qsettings.setValue("last_wrg_dir", os.path.dirname(paths[0]))
            except Exception:
                pass
            self._update_wrg_meta()
            self._draw_current_resource_extent(zoom=False, manual=False)

    def _clear_wrg(self):
        self.ed_wrg.setText("")
        self._last_wrg_path = ""
        try:
            self._qsettings.setValue("last_wrg_path", "")
        except Exception:
            pass
        self._update_wrg_meta()
        self._clear_resource_extent()

    def _pick_wrg_ti(self):
        start_dir = ""
        try:
            first = [p.strip() for p in self.ed_wrg_ti.text().strip().split(";") if p.strip()]
            start_dir = os.path.dirname(first[0]) if first else ""
        except Exception:
            start_dir = ""
        if not start_dir:
            try:
                start_dir = self._qsettings.value("last_wrg_ti_dir", "", type=str)
            except Exception:
                start_dir = ""
        if not start_dir:
            start_dir = os.path.expanduser("~")

        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Selecciona raster(s) de turbulencia (TI)",
            start_dir,
            "Rasters (*.asc *.tif *.tiff *.vrt);;Todos (*.*)",
        )
        if paths:
            txt = ";".join(paths)
            self.ed_wrg_ti.setText(txt)
            self._last_wrg_ti_path = txt
            try:
                self._qsettings.setValue("last_wrg_ti_path", txt)
                self._qsettings.setValue("last_wrg_ti_dir", os.path.dirname(paths[0]))
                if hasattr(self, "ed_wrg_ti_heights"):
                    self._qsettings.setValue("last_wrg_ti_heights", self.ed_wrg_ti_heights.text().strip())
            except Exception:
                pass
            self._update_wrg_ti_meta()

    def _clear_wrg_ti(self):
        self.ed_wrg_ti.setText("")
        self._last_wrg_ti_path = ""
        try:
            self._qsettings.setValue("last_wrg_ti_path", "")
        except Exception:
            pass
        self._update_wrg_ti_meta()

    def _parse_wrg_ti_height_overrides(self) -> List[Optional[float]]:
        """Alturas TI escritas por el usuario, una por raster y en el mismo orden.

        Separadores aceptados: punto y coma o espacios. Ejemplo: ``90;120``.
        Se permite coma decimal, aunque para separar alturas es preferible usar ``;``.
        """
        try:
            txt = self.ed_wrg_ti_heights.text().strip()
        except Exception:
            txt = ""
        if not txt:
            return []

        out: List[Optional[float]] = []
        txt_norm = txt.replace(",", ".")
        for token in re.split(r"[;\s]+", txt_norm):
            token = token.strip()
            if not token:
                continue
            try:
                out.append(float(token))
            except Exception:
                out.append(None)
        try:
            self._qsettings.setValue("last_wrg_ti_heights", txt)
        except Exception:
            pass
        return out


    def _update_wrg_ti_meta(self):
        try:
            txt = self.ed_wrg_ti.text().strip()
        except Exception:
            txt = ""

        paths = [p.strip() for p in txt.split(";") if p.strip()]
        if not paths:
            self.lbl_wrg_ti_meta.setText(f"Raster(s) TI no seleccionado(s) → fallback automático a {self.sp_fixed_ti.value():.1f}% si usas WRG.")
            return

        missing = [os.path.basename(p) for p in paths if not os.path.isfile(p)]
        if missing:
            self.lbl_wrg_ti_meta.setText("Raster(s) TI no encontrado(s): " + ", ".join(missing))
            return

        overrides = self._parse_wrg_ti_height_overrides()
        parts = []
        for i, p in enumerate(paths):
            ext = os.path.splitext(p)[1].lower()
            h = overrides[i] if i < len(overrides) and overrides[i] is not None else self._extract_height_from_filename(p)
            src = "override" if i < len(overrides) and overrides[i] is not None else "nombre"
            if h is None:
                parts.append(f"{os.path.basename(p)} ({ext or 'sin extensión'}, sin altura)")
            else:
                parts.append(f"{os.path.basename(p)} ({h:g} m, {src})")
        extra = ""
        if overrides and len(overrides) != len(paths):
            extra = f" · Aviso: {len(overrides)} altura(s) para {len(paths)} raster(s)"
        self.lbl_wrg_ti_meta.setText(
            f"Raster(s) TI: {' ; '.join(parts)} · CRS destino previsto: {_project_crs_authid()}{extra}"
        )

    def _update_wrg_meta(self):
        """Actualiza el texto de metadatos WRG."""
        try:
            path = self.ed_wrg.text().strip()
        except Exception:
            path = ""

        if not path:
            self.lbl_wrg_meta.setText("")
            return

        if read_wrg_meta is None:
            self.lbl_wrg_meta.setText("(Lector WRG no disponible en esta instalación)")
            return

        # soportar múltiples rutas separadas por ';'
        paths = [p.strip() for p in path.split(";") if p.strip()]
        try:
            metas = [read_wrg_meta(p) for p in paths]
            # asumimos malla igual; mostramos la del primero
            m0 = metas[0]
            nx = m0.get("nx"); ny = m0.get("ny"); cell = m0.get("cellsize")
            nsec = m0.get("n_sectors")
            xmin, xmax, ymin, ymax = m0.get("extent", (None, None, None, None))
            hs = []
            for m in metas:
                hlist = m.get("height_m_list")
                if isinstance(hlist, (list, tuple)) and hlist:
                    hs.extend([str(h) for h in hlist])
                else:
                    hs.append(str(m.get("height_m")))
            hs_txt = ", ".join(hs)
            self.lbl_wrg_meta.setText(
                f"Malla: {nx}×{ny} | cellsize={cell} m | h={hs_txt} m | sectores={nsec} | "
                f"extent=({xmin:.0f},{ymin:.0f})–({xmax:.0f},{ymax:.0f})"
            )
        except Exception as e:
            self.lbl_wrg_meta.setText(f"WRG inválido o no legible: {e}")

    def _clear_resource_extent(self):
        """Elimina del proyecto el perímetro temporal del recurso eólico."""
        if clear_resource_extent_layers is None:
            try:
                self.lbl_resource_extent.setText("Perímetro del recurso no disponible en esta instalación.")
            except Exception:
                pass
            return
        try:
            n = clear_resource_extent_layers()
            if hasattr(self, "lbl_resource_extent"):
                if n:
                    self.lbl_resource_extent.setText("Perímetro del recurso eliminado del mapa.")
                else:
                    self.lbl_resource_extent.setText("No había perímetro del recurso que limpiar.")
        except Exception as e:
            try:
                self.lbl_resource_extent.setText(f"No se pudo limpiar el perímetro del recurso: {e}")
            except Exception:
                pass

    def _draw_current_resource_extent(self, zoom: bool = False, manual: bool = False):
        """Dibuja el dominio espacial del recurso activo: WRG/ZIP o WAsP/Surfer grids.

        Prioriza WRG si hay WRG seleccionado, igual que el flujo de cálculo. Si no,
        intenta leer la carpeta WAsP/Surfer. El dibujo es una capa temporal de
        polígonos en el proyecto QGIS.
        """
        try:
            if hasattr(self, "cb_show_resource_extent") and not self.cb_show_resource_extent.isChecked():
                if manual and hasattr(self, "lbl_resource_extent"):
                    self.lbl_resource_extent.setText("Activa 'Mostrar perímetro del recurso en el mapa' para dibujarlo.")
                return
        except Exception:
            pass

        if show_wrg_resource_extent is None or show_wasp_resource_extent is None:
            if hasattr(self, "lbl_resource_extent"):
                self.lbl_resource_extent.setText("Perímetro del recurso no disponible en esta instalación.")
            return

        try:
            wrg_txt = self.ed_wrg.text().strip() if hasattr(self, "ed_wrg") else ""
        except Exception:
            wrg_txt = ""
        try:
            wasp_dir = self.ed_dir.text().strip() if hasattr(self, "ed_dir") else ""
        except Exception:
            wasp_dir = ""

        ok = False
        msg = ""
        try:
            if wrg_txt:
                if read_wrg_meta is None:
                    ok, msg = False, "Lector WRG no disponible; no se puede dibujar el perímetro WRG."
                else:
                    paths = [p.strip() for p in wrg_txt.split(";") if p.strip()]
                    ok, msg = show_wrg_resource_extent(paths, read_wrg_meta_func=read_wrg_meta, zoom=zoom)
            elif wasp_dir:
                ok, msg = show_wasp_resource_extent(wasp_dir, zoom=zoom)
            else:
                ok, msg = False, "Selecciona una carpeta WAsP/Surfer o un WRG/ZIP para dibujar el perímetro."
        except Exception as e:
            ok, msg = False, f"No se pudo dibujar el perímetro del recurso: {e}"

        try:
            if hasattr(self, "lbl_resource_extent"):
                self.lbl_resource_extent.setText(msg)
        except Exception:
            pass
        if manual and not ok:
            try:
                QtWidgets.QMessageBox.warning(self, "Perímetro del recurso", msg)
            except Exception:
                pass

    def _pick_coords_csv(self, idx: int, line_edit: QtWidgets.QLineEdit):
        start_dir = self._last_csv_dir or os.path.expanduser("~")
        fpath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Selecciona CSV con coordenadas X,Y del modelo",
            start_dir,
            "CSV (*.csv);;Todos (*.*)",
        )
        if fpath:
            line_edit.setText(fpath)
            self._last_csv_dir = os.path.dirname(fpath)

    def _on_generate_layers_clicked(self):
        """Botón principal: crea una capa editable o añade un modelo nuevo.

        Primer click: si ya hay un modelo definido sin capa, crea su capa.
        Siguientes clicks: si todos los modelos definidos ya tienen capa, añade
        una fila nueva, vuelve a pedir el modelo de turbina y crea una capa
        asociada a esa nueva familia de aerogeneradores.
        """
        try:
            rows = list(getattr(self, "_rows", []) or [])
            target_idx = None
            must_define = False

            # 1) Prioridad: un modelo ya definido pero que aún no tiene capa.
            # Esto cubre el flujo normal: el usuario pulsa «Definir…» y luego
            # «Generar capas de puntos» para empezar a pinchar aerogeneradores.
            for i, r in enumerate(rows):
                if r.get("wt") is None:
                    continue
                if self._find_interactive_layer_for_row(i) is None:
                    target_idx = i
                    must_define = False
                    break

            # 2) Si no queda ningún modelo definido pendiente de capa, usar la
            # primera fila sin definir que el usuario haya creado manualmente.
            if target_idx is None:
                for i, r in enumerate(rows):
                    if r.get("wt") is None:
                        target_idx = i
                        must_define = True
                        break

            old_count = len(rows)
            created_new_row = False

            # 3) Si todas las filas ya tienen turbina y capa, añadir una fila
            # nueva. Este es el comportamiento que evita clonar silenciosamente
            # la capa anterior cuando se vuelve a pulsar el botón.
            if target_idx is None:
                max_models = int(self.sp_n.maximum())
                if old_count >= max_models:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Modelos",
                        f"Ya has alcanzado el máximo de {max_models} modelos. "
                        "Aumenta el límite en el código si necesitas más familias de aerogeneradores.",
                    )
                    return
                target_idx = old_count
                must_define = True
                created_new_row = True
                # setValue dispara _rebuild_rows(), que ahora conserva el estado
                # de las filas anteriores.
                self.sp_n.setValue(old_count + 1)

            # 4) Para una fila nueva/sin definir, pedir siempre la turbina antes
            # de crear la capa.
            if must_define:
                self._define_model(target_idx)
                if self._rows[target_idx].get("wt") is None:
                    # Si el usuario canceló y la fila fue añadida automáticamente,
                    # volvemos al número anterior de modelos para no dejar basura UI.
                    if created_new_row:
                        try:
                            self.sp_n.setValue(old_count)
                        except Exception:
                            pass
                    return

            lyr = self._generate_point_layer_one(
                target_idx,
                force_reload_csv=True,
                activate_interactive=False,
                quiet=False,
                create_new_layer=True,
            )
            if lyr is not None:
                try:
                    self._activate_qgis_layer(lyr)
                except Exception:
                    pass

                # Si el modo interactivo ya estaba activo, setChecked(True) no
                # emite toggled y por tanto no se vuelve a ocultar el diálogo ni
                # se refresca el dock. Esto pasaba al crear el segundo modelo:
                # quedaba visible la interfaz principal y el dock podía seguir
                # mostrando/validando la capa anterior.
                self._enter_or_refresh_interactive_after_layer_created(lyr)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Capas", f"No se pudo generar la capa de puntos:\n{e}")


    def _enter_or_refresh_interactive_after_layer_created(self, layer: QgsVectorLayer) -> None:
        """Entra o refresca el modo interactivo tras crear una capa de puntos.

        Primer click: activa el modo como antes.
        Clicks siguientes: si el modo ya está activo, no basta con volver a
        marcar el botón; hay que activar la nueva capa, refrescar el dock y
        volver a ocultar el diálogo para que el flujo sea idéntico al primer
        click.
        """
        try:
            self._activate_qgis_layer(layer)
        except Exception:
            pass

        try:
            row_idx = self._row_index_for_layer(layer)
            if row_idx is not None:
                self._interactive_layer_id_by_row[int(row_idx)] = layer.id()
        except Exception:
            pass

        try:
            already_interactive = bool(self.btn_map_interactive.isChecked())
        except Exception:
            already_interactive = bool(getattr(self, "_interactive_tool", None) is not None)

        if not already_interactive:
            try:
                self.btn_map_interactive.setChecked(True)
            except Exception:
                pass
            return

        # Modo ya activo: mantener la herramienta, pero sincronizar la UI.
        try:
            if self._interactive_tool is None and self.btn_map_interactive.isChecked():
                self._activate_map_interactive()
        except Exception:
            pass

        try:
            if self._interactive_dock is not None:
                self._interactive_dock._refresh_layer_status()
                self._interactive_dock.raise_()
        except Exception:
            pass

        # Mismo comportamiento que el primer click: se queda visible solo el mapa
        # y el dock. No se destruye el diálogo; solo se oculta para preservar estado.
        try:
            self._hide_dialog_for_interactive_map()
        except Exception:
            pass


    # ------------------ generar capas (uno / todos) ------------------
    def _generate_point_layer_one(
        self,
        idx: int,
        force_reload_csv: bool = True,
        activate_interactive: bool = False,
        quiet: bool = False,
        create_new_layer: bool = False,
    ):
        """Crea la capa de puntos de un modelo.

        - Con CSV: carga los puntos del CSV cuando `force_reload_csv=True` o la capa no existe.
        - Sin CSV: crea una capa vacía para poder introducir el layout desde el mapa.
        - En modo cálculo (`force_reload_csv=False`) nunca pisa una capa existente, para no
          borrar puntos editados en el mapa interactivo.
        - Con `create_new_layer=True` crea siempre una capa nueva con nombre único.
          Es el flujo del botón global «Generar capas de puntos», pensado para
          parques con varios modelos de aerogenerador o varias versiones de layout.
        """
        r = self._rows[idx]

        # Si se crea una capa de forma explícita desde la UI y aún no hay
        # turbina definida, abrir primero el diálogo de modelo. En cálculos o
        # asegurados silenciosos (`quiet=True`) no se pregunta nada.
        if (not quiet) and r.get("wt") is None:
            self._define_model(idx)
            r = self._rows[idx]
            if r.get("wt") is None:
                return None

        name = r.get("name") or f"Modelo {idx+1}"
        csv_path = r.get("coords_csv_le").text().strip() if r.get("coords_csv_le") else ""
        layer_name = f"{name} (CSV)"
        existing = None
        if not create_new_layer:
            existing = self._find_interactive_layer_for_row(idx) or _find_layer_by_name(layer_name)
            # Si la capa se creó antes de definir/renombrar el modelo, venía como
            # «Modelo N (CSV)». La reutilizamos y la renombramos para no crear una
            # segunda capa ni perder los puntos ya dibujados.
            try:
                if existing is not None and existing.name() != layer_name:
                    other = _find_layer_by_name(layer_name)
                    if other is None or other.id() == existing.id():
                        existing.setName(layer_name)
                    else:
                        existing = other
            except Exception:
                pass

        meta = r.get("meta") if isinstance(r, dict) else None
        hub_h = None
        diam = None
        if isinstance(meta, dict):
            try:
                if meta.get("hh") is not None:
                    hub_h = float(meta.get("hh"))
            except Exception:
                hub_h = None
            try:
                if meta.get("diam") is not None:
                    diam = float(meta.get("diam"))
            except Exception:
                diam = None

        # No pisar capas vivas durante cálculo/asegurado.
        if existing is not None and not force_reload_csv:
            lyr = existing
        else:
            pts: List[Tuple[float, float]] = []
            if csv_path:
                if os.path.isfile(csv_path):
                    pts = _read_xy_csv(csv_path)
                elif force_reload_csv and not quiet:
                    QtWidgets.QMessageBox.warning(self, "Coordenadas", f"El archivo no existe:\n{csv_path}")
                    return None
            # Si no hay CSV, se crea capa vacía: el usuario añadirá turbinas con el mapa.
            generation = None
            if create_new_layer:
                try:
                    self._energy_layer_generation = int(getattr(self, "_energy_layer_generation", 0)) + 1
                    generation = self._energy_layer_generation
                except Exception:
                    generation = None
            lyr = _create_or_refresh_point_layer(
                layer_name,
                pts,
                model_name=name,
                hub_height=hub_h,
                diameter=diam,
                coords_csv=csv_path,
                model_index=idx,
                create_new=create_new_layer,
                generation=generation,
            )
            if csv_path and os.path.isfile(csv_path):
                # Re-cargar desde CSV = volver a estado de preload: limpiar dirty flag
                try:
                    self._dirty_turbine_layer_ids.discard(lyr.id())
                    self._refresh_dirty_indicators()
                except Exception:
                    pass

        try:
            # Mantener metadatos también cuando reutilizamos una capa existente
            # generada anteriormente por el botón «Generar capas de puntos».
            lyr.setCustomProperty("velantis/layer_role", "energy_turbines")
            lyr.setCustomProperty("velantis/model_name", str(name or ""))
            lyr.setCustomProperty("velantis/model_index", int(idx))
            lyr.setCustomProperty("velantis/row_index", int(idx))
            if create_new_layer:
                lyr.setCustomProperty("velantis/layer_generation", int(getattr(self, "_energy_layer_generation", 0)))
            if hub_h is not None:
                lyr.setCustomProperty("velantis/hub_height_m", float(hub_h))
            if diam is not None:
                lyr.setCustomProperty("velantis/diameter_m", float(diam))
            if csv_path:
                lyr.setCustomProperty("velantis/coords_csv", str(csv_path))
        except Exception:
            pass

        try:
            self._interactive_layer_id_by_row[int(idx)] = lyr.id()
        except Exception:
            pass

        try:
            self._activate_qgis_layer(lyr)
        except Exception:
            pass
        try:
            if not quiet:
                n_pts = len(self._collect_layer_points_for_row(idx) or [])
                suffix = "lista para editar en el mapa" if not csv_path else "creada/actualizada"
                iface.messageBar().pushMessage(
                    "Capas",
                    f"Capa «{lyr.name()}» {suffix} ({n_pts} puntos).",
                    level=Qgis.Info,
                    duration=5,
                )
        except Exception:
            pass

        if activate_interactive:
            try:
                self.btn_map_interactive.setChecked(True)
            except Exception:
                pass
        return lyr

    def _generate_point_layers_all(
        self,
        force_reload_csv: bool = True,
        activate_interactive: bool = False,
        create_new_layer: bool = False,
    ):
        any_done = False
        first_layer = None
        for i in range(len(self._rows)):
            try:
                lyr = self._generate_point_layer_one(
                    i,
                    force_reload_csv=force_reload_csv,
                    activate_interactive=(activate_interactive and i == 0),
                    quiet=(not force_reload_csv),
                    create_new_layer=create_new_layer,
                )
                if lyr is not None:
                    any_done = True
                    if first_layer is None:
                        first_layer = lyr
            except Exception as e:
                try:
                    iface.messageBar().pushMessage(
                        "Capas",
                        f"No se pudo crear la capa del modelo {i+1}: {e}",
                        level=Qgis.Warning,
                        duration=8,
                    )
                except Exception:
                    pass
        if any_done:
            grp = _ensure_group(QgsProject.instance().layerTreeRoot())
            grp.setExpanded(True)
            if activate_interactive and first_layer is not None:
                try:
                    self._activate_qgis_layer(first_layer)
                except Exception:
                    pass
        return first_layer

    # ------------------ cálculo + actualización ------------------
    
    def _run_plot_wakes(self):
        """Dibuja mapas de estelas (N/E/S/O) a partir de capas vivas/CSV y recurso eólico."""
        # Asegurar capas sin pisar posibles ediciones vivas del mapa.
        self._generate_point_layers_all(force_reload_csv=False, activate_interactive=False)

        # Igual que en el cálculo AEP desde mapa interactivo: preguntar qué
        # capas de aerogeneradores entran en la operación. Así las estelas se
        # dibujan para el parque completo cuando hay varios modelos/capas.
        selected_models = None
        try:
            if self._candidate_turbine_layers_for_compute():
                ok = self._ask_turbine_layers_for_compute(
                    title="Capas para graficar estelas",
                    intro=(
                        "Selecciona las capas de aerogeneradores que quieres incluir en los mapas de estelas.\n"
                        "Marca varias capas si el parque combina distintos modelos de turbina."
                    ),
                    ok_text="Graficar con capas seleccionadas",
                )
                if not ok:
                    return
                selected_models = self._consume_selected_models_from_turbine_layers()
                if not selected_models:
                    return
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Capas para estelas", f"No se pudo preparar la selección de capas:\n{e}")
            return

        # Si no hay capas seleccionables, conservamos el flujo clásico basado en
        # CSV/filas del diálogo.
        if selected_models is None:
            for idx, r in enumerate(self._rows):
                live_pts = self._collect_layer_points_for_row(idx)
                csv_path = r["coords_csv_le"].text().strip() if r.get("coords_csv_le") else ""
                if live_pts:
                    continue
                if csv_path and os.path.isfile(csv_path):
                    continue
                QtWidgets.QMessageBox.warning(
                    self, "Coordenadas",
                    f"Añade turbinas en la capa del Modelo {idx+1} o selecciona un CSV X,Y válido."
                )
                return

        # Recurso eólico: WAsP (carpeta) o WRG (archivo/zip)
        wasp_dir = self.ed_dir.text().strip()
        wrg_txt = ""
        try:
            wrg_txt = self.ed_wrg.text().strip()
        except Exception:
            wrg_txt = ""

        wrg_paths = [p.strip() for p in wrg_txt.split(";") if p.strip()]
        use_wrg = bool(wrg_paths)

        if use_wrg:
            for p in wrg_paths:
                if not os.path.isfile(p):
                    QtWidgets.QMessageBox.warning(self, "WRG", f"El archivo no existe:\n{p}")
                    return
                if not p.lower().endswith((".wrg", ".zip")):
                    QtWidgets.QMessageBox.warning(self, "WRG", f"Extensión no soportada (use .wrg o .zip):\n{p}")
                    return
            try:
                _debug_print(f"[Energy plot] Wake plot with WRG: {wrg_paths}")
            except Exception:
                pass
        else:
            if not wasp_dir or not os.path.isdir(wasp_dir):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Recurso eólico",
                    "Selecciona una carpeta WAsP válida o un WRG/ZIP antes de graficar.",
                )
                return
            try:
                _debug_print(f"[Energy plot] Wake plot with WAsP/GridSite: {wasp_dir}")
            except Exception:
                pass

        # Estructura 'models' esperada por graficar.py
        if selected_models is not None:
            models = selected_models
        else:
            models = []
            for idx, r in enumerate(self._rows):
                live_pts = self._collect_layer_points_for_row(idx)
                models.append(
                    {
                        "name": r.get("name") or "Custom WT",
                        "wt": r.get("wt"),
                        "meta": r.get("meta"),
                        "coords_csv": r.get("coords_csv_le").text().strip() if r.get("coords_csv_le") else "",
                        "coords_xy": live_pts,
                    }
                )

        # Import robusto del módulo de gráficas
        graficar_fn = None
        try:
            from .graficar import graficar as graficar_fn
        except Exception:
            try:
                plugin_dir = os.path.dirname(__file__)
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                graficar_fn = importlib.import_module("graficar").graficar
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Graficar estelas", f"No se pudo importar 'graficar.py':\n{e}")
                return

        # Preguntar resolución del grid (m)
        try:
            default_res = self._qsettings.value("last_plot_resolution_m", 300, type=int)
        except Exception:
            default_res = 300

        res_m, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Graficar estelas",
            "Resolución del grid [m] (menor = más detalle, más lento):",
            int(default_res),
            10,
            10000,
            10,
        )
        if not ok:
            return
        try:
            self._qsettings.setValue("last_plot_resolution_m", int(res_m))
        except Exception:
            pass

        try:
            graficar_fn(
                models=models,
                wasp_dir=(wrg_paths[0] if use_wrg and wrg_paths else wasp_dir),
                parent=self,
                resolution_m=float(res_m),
                wrg_paths=(wrg_paths if use_wrg else None),
                superposition_model=self._get_selected_superposition_model(),
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Graficar estelas", f"Error al generar las gráficas:\n{e}")
            return

    def _run_compute_and_update(self):
        """Lanza el cálculo AEP delegando en el controlador del módulo Energía."""
        try:
            from .energy_core.dialog_controller import run_compute_and_update_from_dialog
        except Exception:
            from energy_core.dialog_controller import run_compute_and_update_from_dialog  # type: ignore
        return run_compute_and_update_from_dialog(self)

    def _export_results(self, res: Dict[str, Any], wasp_dir: str) -> None:
        """Compatibilidad: delega la exportación AEP en el controlador."""
        try:
            from .energy_core.dialog_controller import export_results_from_dialog
        except Exception:
            from energy_core.dialog_controller import export_results_from_dialog  # type: ignore
        return export_results_from_dialog(self, res, wasp_dir)

    # ------------------ comparador de escenarios ------------------
    def _register_last_aep_result(self, res: Dict[str, Any], mode_label: str = "Cálculo AEP") -> None:
        """Guarda una copia ligera del último resultado para poder enviarlo a escenario A/B."""
        try:
            self._last_aep_result = copy.deepcopy(res or {})
        except Exception:
            self._last_aep_result = dict(res or {})
        try:
            executed = (res or {}).get("selection_executed", {}) or {}
            wake = executed.get("wake_deficit") or (res or {}).get("wake_deficit_class") or ""
            engine = executed.get("engine") or (res or {}).get("engine") or ""
            stamp = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm")
            bits = [str(mode_label or "AEP"), stamp]
            extra = " / ".join(str(x) for x in (engine, wake) if x)
            if extra:
                bits.append(extra)
            self._last_aep_label = " · ".join(bits)
        except Exception:
            self._last_aep_label = str(mode_label or "Último cálculo")

    def _store_current_scenario(self, slot: str) -> None:
        """Guarda el último cálculo como escenario A o B."""
        if not self._last_aep_result:
            QtWidgets.QMessageBox.information(
                self,
                "Comparador de escenarios",
                "Primero lanza un cálculo AEP. Después podrás guardarlo como escenario A o B."
            )
            return
        default_label = self._last_aep_label or f"Escenario {slot}"
        label, ok = QtWidgets.QInputDialog.getText(
            self,
            f"Guardar escenario {slot}",
            "Nombre del escenario:",
            QtWidgets.QLineEdit.Normal,
            default_label,
        )
        if not ok:
            return
        payload = {
            "label": (label.strip() or f"Escenario {slot}"),
            "result": copy.deepcopy(self._last_aep_result),
        }
        if str(slot).upper() == "A":
            self._scenario_a = payload
        else:
            self._scenario_b = payload
        try:
            iface.messageBar().pushMessage(
                "AEP",
                f"Escenario {str(slot).upper()} guardado: {payload['label']}",
                level=Qgis.Success,
                duration=5,
            )
        except Exception:
            pass

    def _compare_scenarios(self) -> None:
        """Abre la ventana de comparación A/B si existen ambos resultados."""
        if not self._scenario_a or not self._scenario_b:
            QtWidgets.QMessageBox.information(
                self,
                "Comparador de escenarios",
                "Guarda primero un escenario A y un escenario B.\n\n"
                "Flujo recomendado: calcula el caso base → Guardar escenario A → cambia layout/modelo/física → "
                "calcula otra vez → Guardar escenario B → Comparar A/B."
            )
            return
        try:
            dlg = ScenarioComparisonDialog(
                self,
                self._scenario_a.get("result") or {},
                self._scenario_b.get("result") or {},
                label_a=self._scenario_a.get("label") or "Escenario A",
                label_b=self._scenario_b.get("label") or "Escenario B",
            )
            dlg.exec_()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Comparador de escenarios", f"No se pudo abrir la comparación:\n{e}")

    # ------------------ mapa interactivo (editar turbinas en el canvas) ------------------
    def _snap50(self, v: float) -> float:
        """Snap simple a múltiplos de 50 m (coherente con el layout del GA)."""
        try:
            step = 50.0
            return round(float(v) / step) * step
        except Exception:
            return v

    def _activate_qgis_layer(self, layer: QgsVectorLayer) -> None:
        """Activa una capa tanto a nivel de `iface` como del panel de capas.

        En QGIS, cuando una capa está dentro de un grupo, `setActiveLayer()` puede
        dejar la capa activa para las herramientas, pero no siempre queda
        visualmente seleccionada en el layer tree. La llamada doble hace que el
        modo interactivo vea la capa y que el usuario también la vea seleccionada.
        """
        if layer is None:
            return
        try:
            iface.setActiveLayer(layer)
        except Exception:
            pass
        try:
            view = iface.layerTreeView()
            if view is not None:
                view.setCurrentLayer(layer)
        except Exception:
            pass
        # Expandir grupos padres para que la selección sea visible.
        try:
            node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
            parent = node.parent() if node is not None else None
            while parent is not None:
                try:
                    parent.setExpanded(True)
                except Exception:
                    pass
                parent = parent.parent()
        except Exception:
            pass

    def _get_interactive_target_layer(self, allow_auto_pick: bool = True) -> Optional[QgsVectorLayer]:
        """Devuelve una capa de turbinas válida para el mapa interactivo.

        Primero respeta la capa activa si ya es una capa «{Modelo} (CSV)» del
        diálogo. Si no lo es, puede auto-seleccionar una capa generada por el
        botón «Generar capas de puntos».
        """
        try:
            lyr = iface.activeLayer()
        except Exception:
            lyr = None
        if _is_point_vector_layer(lyr) and self._row_index_for_layer(lyr) is not None:
            return lyr
        if allow_auto_pick:
            return self._auto_pick_interactive_layer()
        return None

    def _layer_visible_model_name(self, layer: QgsVectorLayer) -> str:
        """Extrae el nombre de modelo que muestra una capa de turbinas.

        Soporta nombres tipo:
        - ``Vestas V80-2.0 (CSV)``
        - ``Vestas V80-2.0 (CSV) #2``
        - ``Modelo 1 (CSV)``
        """
        try:
            lname = str(layer.name() or "").strip()
        except Exception:
            lname = ""
        if not lname:
            return ""
        try:
            lname = re.sub(r"\s*#\d+\s*$", "", lname).strip()
        except Exception:
            pass
        for suffix in (" (CSV)", "(CSV)"):
            if lname.endswith(suffix):
                lname = lname[: -len(suffix)].strip()
                break
        return lname

    def _row_index_from_model_name(self, model_name: str) -> Optional[int]:
        """Busca una fila por nombre visible de modelo de forma exacta."""
        name = str(model_name or "").strip()
        if not name:
            return None
        rows = list(getattr(self, "_rows", []) or [])
        matches = []
        for i, r in enumerate(rows):
            row_name = str(r.get("name") or f"Modelo {i+1}").strip()
            if row_name and name == row_name:
                matches.append(i)
        if len(matches) == 1:
            return int(matches[0])
        return None

    def _repair_layer_model_metadata(self, layer: QgsVectorLayer, idx: int) -> None:
        """Repara metadatos de capas antiguas cuando el nombre visible indica otra fila.

        Algunas capas creadas por iteraciones anteriores podían quedarse con
        ``model_index=0`` aunque el nombre visible fuese, por ejemplo,
        ``Vestas V100-2.0 (CSV)``. Si no se corrige, cálculo/estelas tratan
        esa capa como el modelo equivocado.
        """
        try:
            if idx is None or idx < 0 or idx >= len(getattr(self, "_rows", []) or []):
                return
            r = self._rows[int(idx)]
            model_name = str(r.get("name") or f"Modelo {int(idx)+1}")
            layer.setCustomProperty("velantis/layer_role", "energy_turbines")
            layer.setCustomProperty("velantis/model_index", int(idx))
            layer.setCustomProperty("velantis/row_index", int(idx))
            layer.setCustomProperty("velantis/model_name", model_name)
            meta = r.get("meta") if isinstance(r, dict) else None
            if isinstance(meta, dict):
                if meta.get("hh") is not None:
                    layer.setCustomProperty("velantis/hub_height_m", float(meta.get("hh")))
                if meta.get("diam") is not None:
                    layer.setCustomProperty("velantis/diameter_m", float(meta.get("diam")))
        except Exception:
            pass

    def _row_index_for_layer(self, layer: QgsVectorLayer) -> Optional[int]:
        """Encuentra la fila asociada a una capa «{Modelo} (CSV)».

        Preferimos el nombre visible o el ``velantis/model_name`` cuando encaja
        de forma exacta con una fila. Esto es deliberado: si una capa antigua
        arrastra un ``model_index`` incorrecto, el usuario ve el nombre correcto
        en el panel de capas y esa debe ser la fuente de verdad. El índice
        persistido queda como fallback para capas con nombres genéricos.
        """
        if not _is_point_vector_layer(layer):
            return None

        rows = list(getattr(self, "_rows", []) or [])

        # 1) Nombre visible de capa: más fiable para reparar capas antiguas con
        # model_index equivocado.
        visible_name = self._layer_visible_model_name(layer)
        idx_by_visible = self._row_index_from_model_name(visible_name)
        if idx_by_visible is not None:
            try:
                self._repair_layer_model_metadata(layer, int(idx_by_visible))
            except Exception:
                pass
            return int(idx_by_visible)

        # 2) Metadato explícito de nombre de modelo.
        try:
            stored_name = str(layer.customProperty("velantis/model_name", "") or "").strip()
        except Exception:
            stored_name = ""
        idx_by_stored_name = self._row_index_from_model_name(stored_name)
        if idx_by_stored_name is not None:
            try:
                self._repair_layer_model_metadata(layer, int(idx_by_stored_name))
            except Exception:
                pass
            return int(idx_by_stored_name)

        # 3) Índice persistido. Lo usamos solo si no hay nombre exacto mejor.
        for key in ("velantis/model_index", "velantis/row_index"):
            try:
                raw = layer.customProperty(key, None)
            except Exception:
                raw = None
            if raw is None or raw == "":
                continue
            try:
                idx = int(raw)
            except Exception:
                continue
            if 0 <= idx < len(rows):
                return idx

        # 4) Último fallback por nombre genérico antiguo.
        if visible_name:
            for i, _r in enumerate(rows):
                if visible_name == f"Modelo {i+1}":
                    return i

        return None

    def _find_interactive_layer_for_row(self, idx: int) -> Optional[QgsVectorLayer]:
        """Busca la capa de turbinas de una fila, incluyendo capas generadas vacías.

        Si hay varias capas para el mismo modelo/fila, prioriza:
        1) la última capa que el diálogo ha creado o activado para esa fila;
        2) la capa activa si pertenece a esa fila;
        3) la capa con mayor `velantis/layer_generation`;
        4) el nombre base histórico como fallback.
        """
        try:
            r = self._rows[idx]
        except Exception:
            return None
        current_name = r.get("name") or f"Modelo {idx+1}"
        preferred_names = [f"{current_name} (CSV)"]
        default_name = f"Modelo {idx+1} (CSV)"
        if default_name not in preferred_names:
            preferred_names.append(default_name)

        layers = [lyr for lyr in _iter_project_vector_layers() if _is_point_vector_layer(lyr)]

        # 0) Capa recordada por esta sesión del diálogo.
        try:
            remembered_id = (getattr(self, "_interactive_layer_id_by_row", {}) or {}).get(int(idx))
        except Exception:
            remembered_id = None
        if remembered_id:
            for lyr in layers:
                try:
                    if lyr.id() == remembered_id and self._row_index_for_layer(lyr) == idx:
                        return lyr
                except Exception:
                    continue

        # 1) Si la capa activa pertenece a esta fila, respétala.
        try:
            active = iface.activeLayer()
        except Exception:
            active = None
        if _is_point_vector_layer(active) and self._row_index_for_layer(active) == idx:
            try:
                self._interactive_layer_id_by_row[int(idx)] = active.id()
            except Exception:
                pass
            return active

        # 2) Capas con metadatos de fila/modelo. Si hay varias, usar la más reciente.
        candidates = []
        for lyr in layers:
            try:
                if self._row_index_for_layer(lyr) != idx:
                    continue
                gen_raw = lyr.customProperty("velantis/layer_generation", -1)
                try:
                    gen = int(gen_raw)
                except Exception:
                    gen = -1
                candidates.append((gen, lyr))
            except Exception:
                continue
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            chosen = candidates[0][1]
            try:
                self._interactive_layer_id_by_row[int(idx)] = chosen.id()
            except Exception:
                pass
            return chosen

        # 3) Nombre exacto, primero nombre actual y luego nombre por defecto.
        for wanted in preferred_names:
            for lyr in layers:
                try:
                    if lyr.name() == wanted:
                        return lyr
                except Exception:
                    continue
        return None

    def _auto_pick_interactive_layer(self) -> Optional[QgsVectorLayer]:
        """Auto-selecciona la primera capa «{Modelo} (CSV)» válida del proyecto.

        Orden de preferencia: modelo 0 → resto de modelos en orden. Cuando la
        encuentra, la activa con `setActiveLayer()` y con
        `layerTreeView().setCurrentLayer()` para que funcione también si está
        dentro de grupos.
        """
        active = self._get_interactive_target_layer(allow_auto_pick=False)
        if active is not None:
            try:
                row_idx = self._row_index_for_layer(active)
                if row_idx is not None:
                    self._interactive_layer_id_by_row[int(row_idx)] = active.id()
            except Exception:
                pass
            self._activate_qgis_layer(active)
            return active

        n_rows = len(getattr(self, "_rows", []) or [])
        order = list(range(n_rows))
        if 0 in order:
            order.remove(0)
            order.insert(0, 0)

        for idx in order:
            lyr = self._find_interactive_layer_for_row(idx)
            if lyr is None:
                continue
            if self._row_index_for_layer(lyr) is None:
                continue
            try:
                self._interactive_layer_id_by_row[int(idx)] = lyr.id()
            except Exception:
                pass
            self._activate_qgis_layer(lyr)
            return lyr
        return None

    def _mark_turbines_layer_dirty(self, layer: QgsVectorLayer) -> None:
        try:
            self._dirty_turbine_layer_ids.add(layer.id())
        except Exception:
            pass
        try:
            self._refresh_dirty_indicators()
        except Exception:
            pass
        try:
            if getattr(self, "_interactive_dock", None) is not None:
                self._interactive_dock._refresh_layer_status()
        except Exception:
            pass

    def _export_layer_points_to_csv(self, layer: QgsVectorLayer, csv_path: str) -> int:
        """Vuelca puntos (x,y) a CSV. Devuelve nº de puntos exportados.

        NOTA: solo se llama desde la acción explícita «Exportar layout editado…».
        El cálculo de AEP NO usa esta función: lee los puntos directamente de la capa
        en memoria a través de `_collect_layer_points_for_row`.
        """
        n = 0
        os.makedirs(os.path.dirname(csv_path), exist_ok=True) if os.path.dirname(csv_path) else None
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["x", "y"])
            for feat in layer.getFeatures():
                try:
                    p = feat.geometry().asPoint()
                except Exception:
                    continue
                w.writerow([f"{p.x():.3f}", f"{p.y():.3f}"])
                n += 1
        return n

    def _collect_points_from_layer(self, layer: QgsVectorLayer) -> List[Tuple[float, float]]:
        """Lee los puntos vivos de una capa concreta de aerogeneradores."""
        pts: List[Tuple[float, float]] = []
        if layer is None or not isinstance(layer, QgsVectorLayer):
            return pts
        for feat in layer.getFeatures():
            try:
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue
                p = geom.asPoint()
                pts.append((float(p.x()), float(p.y())))
            except Exception:
                continue
        return pts

    def _candidate_turbine_layers_for_compute(self) -> List[Dict[str, Any]]:
        """Capas de aerogeneradores seleccionables para un cálculo interactivo.

        Se listan solo capas de puntos asociadas a una fila/modelo ya definido.
        Así el cálculo puede combinar varias familias de aerogeneradores cargadas
        en el panel de capas, sin depender únicamente de la capa activa.
        """
        rows = list(getattr(self, "_rows", []) or [])
        out: List[Dict[str, Any]] = []
        try:
            active_id = iface.activeLayer().id() if iface.activeLayer() is not None else ""
        except Exception:
            active_id = ""
        remembered = set()
        try:
            remembered = set((getattr(self, "_interactive_layer_id_by_row", {}) or {}).values())
        except Exception:
            remembered = set()

        for lyr in _iter_project_vector_layers():
            if not _is_point_vector_layer(lyr):
                continue
            idx = self._row_index_for_layer(lyr)
            if idx is None or idx < 0 or idx >= len(rows):
                continue
            r = rows[idx] or {}
            if r.get("wt") is None:
                continue
            pts = self._collect_points_from_layer(lyr)
            if not pts:
                continue
            try:
                gen_raw = lyr.customProperty("velantis/layer_generation", -1)
                gen = int(gen_raw)
            except Exception:
                gen = -1
            model_name = r.get("name") or f"Modelo {idx+1}"
            out.append({
                "layer": lyr,
                "layer_id": lyr.id(),
                "layer_name": lyr.name(),
                "row_index": int(idx),
                "model_name": model_name,
                "n_points": len(pts),
                "generation": gen,
                "active": bool(lyr.id() == active_id),
                "remembered": bool(lyr.id() in remembered),
            })

        # Orden estable: modelo/fila, generación más reciente primero dentro de cada modelo.
        out.sort(key=lambda d: (int(d.get("row_index", 0)), -int(d.get("generation", -1)), str(d.get("layer_name", ""))))
        return out

    def _candidate_turbine_layers_for_edit(self) -> List[Dict[str, Any]]:
        """Capas de aerogeneradores disponibles para edición en mapa.

        A diferencia del selector de cálculo, aquí también se listan capas
        vacías para poder elegir el modelo al que se añadirán nuevas turbinas.
        """
        rows = list(getattr(self, "_rows", []) or [])
        out: List[Dict[str, Any]] = []
        try:
            active_id = iface.activeLayer().id() if iface.activeLayer() is not None else ""
        except Exception:
            active_id = ""
        remembered = set()
        try:
            remembered = set((getattr(self, "_interactive_layer_id_by_row", {}) or {}).values())
        except Exception:
            remembered = set()

        seen = set()
        for lyr in _iter_project_vector_layers():
            if not _is_point_vector_layer(lyr):
                continue
            idx = self._row_index_for_layer(lyr)
            if idx is None or idx < 0 or idx >= len(rows):
                continue
            r = rows[int(idx)] or {}
            if r.get("wt") is None:
                continue
            try:
                lid = lyr.id()
            except Exception:
                lid = ""
            if not lid or lid in seen:
                continue
            seen.add(lid)
            try:
                gen_raw = lyr.customProperty("velantis/layer_generation", -1)
                gen = int(gen_raw)
            except Exception:
                gen = -1
            pts = self._collect_points_from_layer(lyr)
            model_name = r.get("name") or f"Modelo {int(idx)+1}"
            out.append({
                "layer": lyr,
                "layer_id": lid,
                "layer_name": lyr.name(),
                "row_index": int(idx),
                "model_name": model_name,
                "n_points": len(pts),
                "generation": gen,
                "active": bool(lid == active_id),
                "remembered": bool(lid in remembered),
            })

        # Activa primero; después por fila y generación reciente.
        out.sort(key=lambda d: (0 if d.get("active") else 1, int(d.get("row_index", 0)), -int(d.get("generation", -1)), str(d.get("layer_name", ""))))
        return out

    def _set_interactive_edit_layer(self, layer_id: str) -> bool:
        """Activa una capa concreta como destino de edición del mapa interactivo."""
        try:
            lyr = QgsProject.instance().mapLayer(str(layer_id))
        except Exception:
            lyr = None
        if not _is_point_vector_layer(lyr):
            return False
        idx = self._row_index_for_layer(lyr)
        if idx is None:
            return False
        try:
            self._interactive_layer_id_by_row[int(idx)] = lyr.id()
        except Exception:
            pass
        try:
            self._activate_qgis_layer(lyr)
        except Exception:
            pass
        try:
            if getattr(self, "_interactive_dock", None) is not None:
                self._interactive_dock._refresh_layer_status()
        except Exception:
            pass
        return True

    def _ask_turbine_layers_for_compute(
        self,
        title: str = "Capas para calcular AEP",
        intro: Optional[str] = None,
        ok_text: str = "Calcular con capas seleccionadas",
    ) -> bool:
        """Pregunta qué capas de aerogeneradores usar en la próxima operación.

        Se usa tanto para recalcular AEP como para graficar estelas desde el
        mapa interactivo. Devuelve True si el usuario aceptó una selección
        válida. La selección se consume una sola vez por
        ``_consume_selected_models_from_turbine_layers``.
        """
        candidates = self._candidate_turbine_layers_for_compute()
        if not candidates:
            QtWidgets.QMessageBox.warning(
                self,
                "Capas de aerogeneradores",
                "No hay capas de turbinas válidas con puntos para calcular.\n\n"
                "Crea una capa con «Generar capas de puntos», define su modelo de turbina "
                "y añade al menos un aerogenerador en el mapa.",
            )
            return False

        # Por defecto marcamos la capa más reciente/recordada de cada modelo.
        default_ids = set()
        by_row: Dict[int, Dict[str, Any]] = {}
        for c in candidates:
            idx = int(c.get("row_index", -1))
            prev = by_row.get(idx)
            if prev is None:
                by_row[idx] = c
                continue
            score_prev = (1 if prev.get("remembered") else 0, 1 if prev.get("active") else 0, int(prev.get("generation", -1)))
            score_cur = (1 if c.get("remembered") else 0, 1 if c.get("active") else 0, int(c.get("generation", -1)))
            if score_cur > score_prev:
                by_row[idx] = c
        for c in by_row.values():
            default_ids.add(str(c.get("layer_id")))

        try:
            dlg_parent = iface.mainWindow()
        except Exception:
            dlg_parent = self
        dlg = QtWidgets.QDialog(dlg_parent)
        dlg.setWindowTitle(str(title or "Capas de aerogeneradores"))
        dlg.setMinimumSize(560, 420)
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        if intro is None:
            intro = (
                "Selecciona las capas de aerogeneradores que quieres incluir en este cálculo.\n"
                "Puedes marcar varias capas para simular un parque con varios modelos de turbina."
            )
        lbl = QtWidgets.QLabel(str(intro))
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        lst = QtWidgets.QListWidget(dlg)
        lst.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for c in candidates:
            row_idx = int(c.get("row_index", 0))
            gen = int(c.get("generation", -1))
            gen_txt = f" · gen {gen}" if gen >= 0 else ""
            active_txt = " · activa" if c.get("active") else ""
            txt = (
                f"Modelo {row_idx+1}: {c.get('model_name')}  |  "
                f"{c.get('layer_name')}  |  {c.get('n_points')} turbinas{gen_txt}{active_txt}"
            )
            item = QtWidgets.QListWidgetItem(txt)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setData(QtCore.Qt.UserRole, str(c.get("layer_id")))
            item.setCheckState(QtCore.Qt.Checked if str(c.get("layer_id")) in default_ids else QtCore.Qt.Unchecked)
            lst.addItem(item)
        lay.addWidget(lst, 1)

        h_select = QtWidgets.QHBoxLayout()
        btn_all = QtWidgets.QPushButton("Marcar todas")
        btn_none = QtWidgets.QPushButton("Desmarcar")
        h_select.addWidget(btn_all)
        h_select.addWidget(btn_none)
        h_select.addStretch(1)
        lay.addLayout(h_select)

        def _set_all(state):
            for i in range(lst.count()):
                lst.item(i).setCheckState(state)
        btn_all.clicked.connect(lambda *_: _set_all(QtCore.Qt.Checked))
        btn_none.clicked.connect(lambda *_: _set_all(QtCore.Qt.Unchecked))

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText(str(ok_text or "Aceptar"))
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancelar")
        lay.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        while True:
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                self._selected_turbine_layer_ids_for_next_compute = []
                return False
            selected_ids = []
            for i in range(lst.count()):
                item = lst.item(i)
                if item.checkState() == QtCore.Qt.Checked:
                    selected_ids.append(str(item.data(QtCore.Qt.UserRole)))
            if selected_ids:
                self._selected_turbine_layer_ids_for_next_compute = selected_ids
                return True
            QtWidgets.QMessageBox.warning(dlg, "Capas", "Selecciona al menos una capa para calcular.")

    def _consume_selected_models_from_turbine_layers(self) -> Optional[List[Dict[str, Any]]]:
        """Convierte la selección de capas del diálogo interactivo en modelos AEP.

        La selección se consume una sola vez para que el botón normal de cálculo
        conserve el comportamiento histórico si el usuario no viene del mapa
        interactivo.
        """
        selected_ids = list(getattr(self, "_selected_turbine_layer_ids_for_next_compute", []) or [])
        self._selected_turbine_layer_ids_for_next_compute = []
        if not selected_ids:
            return None

        rows = list(getattr(self, "_rows", []) or [])
        models: List[Dict[str, Any]] = []
        selected_count_by_row: Dict[int, int] = {}
        for lid in selected_ids:
            try:
                lyr = QgsProject.instance().mapLayer(str(lid))
            except Exception:
                lyr = None
            if not _is_point_vector_layer(lyr):
                continue
            idx = self._row_index_for_layer(lyr)
            if idx is None or idx < 0 or idx >= len(rows):
                continue
            r = rows[idx] or {}
            if r.get("wt") is None:
                continue
            pts = self._collect_points_from_layer(lyr)
            if not pts:
                continue
            selected_count_by_row[int(idx)] = selected_count_by_row.get(int(idx), 0) + 1
            base_name = r.get("name") or f"Modelo {idx+1}"
            models.append({
                "name": base_name,
                "wt": r.get("wt"),
                "meta": r.get("meta"),
                "coords_csv": "",
                "coords_xy": pts,
                "source_layer_id": lyr.id(),
                "source_layer_name": lyr.name(),
                "source_row_index": int(idx),
            })

        # Si el usuario seleccionó varias capas del mismo modelo, distinguir el
        # nombre para que los resultados no aparezcan como duplicados exactos.
        if models:
            for m in models:
                idx = int(m.get("source_row_index", -1))
                if selected_count_by_row.get(idx, 0) > 1:
                    m["name"] = f"{m.get('name')} · {m.get('source_layer_name')}"
        return models or None

    def _collect_layer_points_for_row(self, idx: int) -> Optional[List[Tuple[float, float]]]:
        """Devuelve los puntos vivos de la capa «{Modelo} (CSV)» del modelo idx.

        Es la fuente de verdad para el cálculo de AEP cuando el usuario ha editado el
        layout en el mapa interactivo. Devuelve None si la capa no existe (en cuyo
        caso el core caerá al CSV en disco).
        """
        try:
            r = self._rows[idx]
        except Exception:
            return None
        lyr = self._find_interactive_layer_for_row(idx)
        if lyr is None or not isinstance(lyr, QgsVectorLayer):
            return None
        pts: List[Tuple[float, float]] = []
        for feat in lyr.getFeatures():
            try:
                p = feat.geometry().asPoint()
                pts.append((float(p.x()), float(p.y())))
            except Exception:
                continue
        return pts if pts else None

    def _layer_is_dirty_for_row(self, idx: int) -> bool:
        try:
            r = self._rows[idx]
        except Exception:
            return False
        lyr = self._find_interactive_layer_for_row(idx)
        if lyr is None:
            return False
        try:
            return lyr.id() in self._dirty_turbine_layer_ids
        except Exception:
            return False

    def _refresh_dirty_indicators(self) -> None:
        """Actualiza los badges «(editado)» en cada fila de modelo."""
        if not hasattr(self, "_rows"):
            return
        for i, r in enumerate(self._rows):
            badge = r.get("dirty_badge")
            if badge is None:
                continue
            try:
                badge.setVisible(self._layer_is_dirty_for_row(i))
            except Exception:
                pass

    def _sync_dirty_layers_to_csv(self) -> None:
        """DEPRECATED: NO sincroniza al CSV original.

        Antes esta función sobrescribía el CSV que el usuario había seleccionado
        desde disco con las coordenadas editadas en el mapa interactivo, lo que
        destruía el archivo original sin aviso. Ahora el cálculo de AEP lee las
        coordenadas vivas directamente de la capa en memoria, así que NO hace
        falta volcar nada al CSV. Si el usuario quiere persistir el layout
        editado a disco, debe usar explícitamente «Exportar layout editado…».

        Se conserva el método (vacío) por compatibilidad con llamadas existentes.
        """
        # Refrescar indicadores «(editado)» por si la capa cambió desde el último render
        try:
            self._refresh_dirty_indicators()
        except Exception:
            pass
        return

    def _export_edited_layouts_dialog(self) -> None:
        """Acción explícita: el usuario decide guardar el layout editado a CSV.

        Para cada modelo cuya capa esté marcada como editada, pregunta destino
        con default `<original>_edited.csv` y NUNCA sobrescribe el CSV original
        salvo que el usuario lo confirme manualmente seleccionando ese mismo
        archivo en el diálogo de guardado.
        """
        if not hasattr(self, "_rows"):
            return
        any_dirty = any(self._layer_is_dirty_for_row(i) for i in range(len(self._rows)))
        if not any_dirty:
            QtWidgets.QMessageBox.information(
                self, "Exportar layout editado",
                "No hay layouts editados pendientes de exportar."
            )
            return

        for i, r in enumerate(self._rows):
            if not self._layer_is_dirty_for_row(i):
                continue
            name = r.get("name") or f"Modelo {i+1}"
            lyr = self._find_interactive_layer_for_row(i)
            if lyr is None:
                continue
            orig = r.get("coords_csv_le").text().strip() if r.get("coords_csv_le") else ""
            # Default sugerido: <original>_edited.csv (NO sobrescribe el original)
            if orig:
                base, ext = os.path.splitext(orig)
                suggested = base + "_edited" + (ext or ".csv")
            else:
                suggested = os.path.join(self._last_csv_dir or os.path.expanduser("~"),
                                         f"{name}_edited.csv")
            fpath, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                f"Exportar layout editado · {name}",
                suggested,
                "CSV (*.csv);;Todos (*.*)",
            )
            if not fpath:
                continue
            # Aviso explícito si el usuario apunta al archivo original
            if orig and os.path.abspath(fpath) == os.path.abspath(orig):
                ok = QtWidgets.QMessageBox.question(
                    self, "Sobrescribir CSV original",
                    f"Vas a sobrescribir el CSV original:\n{orig}\n\n¿Continuar?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
                if ok != QtWidgets.QMessageBox.Yes:
                    continue
            try:
                n = self._export_layer_points_to_csv(lyr, fpath)
                # Quitar el flag dirty para esta capa
                try:
                    self._dirty_turbine_layer_ids.discard(lyr.id())
                except Exception:
                    pass
                iface.messageBar().pushMessage(
                    "Exportar layout editado",
                    f"«{name}» → {os.path.basename(fpath)} ({n} puntos)",
                    level=Qgis.Info, duration=5,
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Exportar layout editado",
                    f"No se pudo escribir el CSV de «{name}»:\n{e}"
                )

        self._refresh_dirty_indicators()

    def _refresh_project_state(self):
        """Refresca capas/modelos visibles en el proyecto sin cambiar el flujo actual."""
        try:
            self._refresh_dirty_indicators()
        except Exception:
            pass
        try:
            if getattr(self, "_interactive_dock", None) is not None:
                self._interactive_dock._refresh_layer_status()
        except Exception:
            pass
        try:
            iface.messageBar().pushMessage(
                "Energía",
                "Estado de capas/modelos refrescado.",
                level=Qgis.Info,
                duration=3,
            )
        except Exception:
            pass

    def _return_to_hub(self):
        """Volver al hub sin destruir el estado del módulo de Energía.

        El mapa interactivo mantiene estado en memoria: filas con objetos WT,
        metadatos y la asociación fila→capa. Si al volver al hub se hacía
        ``reject()`` con ``WA_DeleteOnClose``, QGIS conservaba las capas pero el
        diálogo se destruía; al entrar otra vez, el mapa ya no sabía qué modelo
        correspondía a cada capa. Por eso esta acción ahora solo oculta Energía
        y deja la instancia viva para que el hub la reutilice.
        """
        # Salir limpiamente del modo interactivo/dock/map tool si estaba activo.
        try:
            if getattr(self, "btn_map_interactive", None) is not None and self.btn_map_interactive.isChecked():
                self.btn_map_interactive.setChecked(False)
            elif getattr(self, "_interactive_tool", None) is not None:
                self._deactivate_map_interactive()
        except Exception:
            pass

        try:
            self._hidden_for_interactive = False
        except Exception:
            pass

        # Refrescar badges/selectores antes de esconder, por si se vuelve a abrir
        # inmediatamente desde el hub.
        try:
            self._refresh_project_state()
        except Exception:
            pass

        # Mostrar el hub padre.
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "show"):
                try:
                    if hasattr(parent, "_refresh_summary"):
                        parent._refresh_summary()
                except Exception:
                    pass
                parent.show()
                try:
                    parent.raise_(); parent.activateWindow()
                except Exception:
                    pass
        except Exception:
            pass

        # Importante: ocultar, NO reject()/close(). Así no se pierde la memoria
        # de modelos ni la asociación con capas creadas en esta sesión.
        try:
            self.hide()
        except Exception:
            pass

    def closeEvent(self, event):
        """Durante el modo interactivo, cerrar el diálogo solo lo oculta.

        Así el usuario puede volver al mapa sin perder los modelos cargados ni
        las referencias a las capas. Salir de verdad del modo interactivo se hace
        con el botón «Salir» del dock o ESC.
        """
        try:
            if getattr(self, "_interactive_tool", None) is not None or bool(self.btn_map_interactive.isChecked()):
                event.ignore()
                self._hide_dialog_for_interactive_map()
                return
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()

    def reject(self):
        """Cancelar/X mientras se edita en mapa no debe destruir el estado."""
        try:
            if getattr(self, "_interactive_tool", None) is not None or bool(self.btn_map_interactive.isChecked()):
                self._hide_dialog_for_interactive_map()
                return
        except Exception:
            pass
        try:
            super().reject()
        except Exception:
            self.hide()

    def _toggle_map_interactive(self, checked: bool):
        if checked:
            self._activate_map_interactive()
        else:
            self._deactivate_map_interactive()

    def _activate_map_interactive(self):
        if _TurbineInteractiveTool is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Mapa interactivo",
                "No se pudo cargar la herramienta de mapa interactivo (import fallido).",
            )
            try:
                self.btn_map_interactive.setChecked(False)
            except Exception:
                pass
            return

        if self._canvas is None:
            try:
                self._canvas = iface.mapCanvas()
            except Exception:
                self._canvas = None
        if self._canvas is None:
            QtWidgets.QMessageBox.warning(self, "Mapa interactivo", "No se pudo obtener el map canvas de QGIS.")
            try:
                self.btn_map_interactive.setChecked(False)
            except Exception:
                pass
            return

        # Validar/autoseleccionar capa activa. Si el usuario viene de
        # «Generar capas de puntos», puede existir una capa válida dentro de un
        # grupo aunque QGIS no la tenga marcada como activa en `iface`.
        layer = self._get_interactive_target_layer(allow_auto_pick=True)
        if layer is None:
            QtWidgets.QMessageBox.information(
                self,
                "Mapa interactivo",
                "No encuentro una capa de turbinas «{Modelo} (CSV)» para editar.\n\n"
                "Pulsa primero «Generar capas de puntos» o carga una capa del modelo en el proyecto.",
            )
            try:
                self.btn_map_interactive.setChecked(False)
            except Exception:
                pass
            return

        # Guardar el map tool previo y activar el nuestro
        try:
            self._interactive_prev_tool = self._canvas.mapTool()
        except Exception:
            self._interactive_prev_tool = None

        try:
            self._interactive_tool = _TurbineInteractiveTool(self, self._canvas, tol_m=120.0)
            self._canvas.setMapTool(self._interactive_tool)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Mapa interactivo", f"No se pudo activar el modo interactivo:\n{e}")
            try:
                self.btn_map_interactive.setChecked(False)
            except Exception:
                pass
            return

        # Capturar ESC global mientras esté activo
        try:
            iface.mainWindow().installEventFilter(self)
        except Exception:
            pass

        # Mostrar caja de herramientas (dock) con física PyWake + acciones.
        # Si por alguna razón no se pudo importar el módulo del dock,
        # caemos a la messagebar mini con Recalcular/Salir.
        if not self._show_interactive_dock():
            self._show_interactive_messagebar()

        # Ocultar diálogo para trabajar cómodo
        self._hide_dialog_for_interactive_map()

    def _deactivate_map_interactive(self):
        # Sync antes de salir, para que el botón de cálculo use coords actualizadas
        try:
            self._sync_dirty_layers_to_csv()
        except Exception:
            pass

        # Quitar widget de messagebar
        self._hide_interactive_messagebar()
        # Quitar caja de herramientas (dock) si está visible
        self._hide_interactive_dock()

        # Restaurar map tool previo
        try:
            if self._canvas is None:
                self._canvas = iface.mapCanvas()
        except Exception:
            self._canvas = None
        try:
            if self._canvas is not None and self._interactive_prev_tool is not None:
                self._canvas.setMapTool(self._interactive_prev_tool)
            else:
                # fallback: activar pan
                try:
                    iface.actionPan().trigger()
                except Exception:
                    pass
        except Exception:
            pass

        self._interactive_tool = None
        self._interactive_prev_tool = None

        # Dejar de capturar ESC global
        try:
            iface.mainWindow().removeEventFilter(self)
        except Exception:
            pass

        # Reabrir diálogo si estaba oculto
        self._show_dialog_after_interactive_map()

    def _exit_map_interactive_via_esc(self):
        """Llamado desde el map tool (o eventFilter) al pulsar ESC."""
        try:
            self.btn_map_interactive.setChecked(False)
        except Exception:
            # Si no existe el botón por alguna razón, al menos desactivamos.
            try:
                self._deactivate_map_interactive()
            except Exception:
                pass

    def eventFilter(self, obj, event):
        """Captura ESC incluso si el foco no está en el canvas."""
        try:
            if self._interactive_tool is not None and event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self._exit_map_interactive_via_esc()
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _hide_dialog_for_interactive_map(self):
        try:
            if self.isVisible():
                self._hidden_for_interactive = True
                self.hide()
        except Exception:
            pass

    def _show_dialog_after_interactive_map(self):
        try:
            if getattr(self, "_hidden_for_interactive", False):
                self._hidden_for_interactive = False
                self.show()
                try:
                    self.raise_(); self.activateWindow()
                except Exception:
                    pass
        except Exception:
            pass

    def _show_interactive_messagebar(self):
        try:
            self._hide_interactive_messagebar()
        except Exception:
            pass

        try:
            msg = iface.messageBar().createMessage(
                "Mapa interactivo",
                "Click izq: añadir turbina · Click der: borrar · ESC: salir",
            )
            btn_recalc = QtWidgets.QPushButton("Recalcular AEP")
            btn_recalc.clicked.connect(self._recalc_aep_from_interactive)
            btn_dialog = QtWidgets.QPushButton("Volver al diálogo")
            btn_dialog.clicked.connect(self._show_dialog_after_interactive_map)
            btn_exit = QtWidgets.QPushButton("Salir")
            btn_exit.clicked.connect(lambda: self.btn_map_interactive.setChecked(False))

            msg.layout().addWidget(btn_recalc)
            msg.layout().addWidget(btn_dialog)
            msg.layout().addWidget(btn_exit)
            self._interactive_msg_widget = msg
            # Nota: usamos llamada posicional para compatibilidad entre versiones.
            self._interactive_msg_item = iface.messageBar().pushWidget(msg, Qgis.Info, 0)
        except Exception:
            self._interactive_msg_widget = None
            self._interactive_msg_item = None

    def _hide_interactive_messagebar(self):
        try:
            if self._interactive_msg_item is not None:
                iface.messageBar().popWidget(self._interactive_msg_item)
        except Exception:
            # Algunas versiones esperan el widget directamente
            try:
                if self._interactive_msg_widget is not None:
                    iface.messageBar().popWidget(self._interactive_msg_widget)
            except Exception:
                pass
        self._interactive_msg_item = None
        self._interactive_msg_widget = None

    # -------------- caja de herramientas (dock) del mapa interactivo --------------
    def _cleanup_stale_interactive_docks(self) -> None:
        """Elimina docks antiguos del modo interactivo que hayan quedado vivos.

        En QGIS, al recargar el plugin o alternar rápido el modo interactivo, un
        QDockWidget puede quedar anclado aunque ``self._interactive_dock`` ya no
        apunte a él. Eso genera el efecto de dos paneles "Mapa interactivo" y,
        en pantallas pequeñas, oculta botones como "Volver al diálogo".
        """
        try:
            main = iface.mainWindow()
        except Exception:
            main = None
        if main is None:
            return
        try:
            docks = main.findChildren(QtWidgets.QDockWidget)
        except Exception:
            docks = []
        for dock in docks:
            try:
                if dock is getattr(self, "_interactive_dock", None):
                    continue
                if dock.objectName() != "VelantisWindInteractiveDock":
                    continue
                try:
                    if hasattr(dock, "_teardown"):
                        dock._teardown()
                except Exception:
                    pass
                try:
                    iface.removeDockWidget(dock)
                except Exception:
                    try:
                        main.removeDockWidget(dock)
                    except Exception:
                        pass
                try:
                    dock.setParent(None)
                except Exception:
                    pass
                try:
                    dock.deleteLater()
                except Exception:
                    pass
            except RuntimeError:
                continue
            except Exception:
                continue

    def _show_interactive_dock(self) -> bool:
        """Muestra el dock con física PyWake + acciones. Devuelve True si lo creó."""
        if InteractiveMapDock is None:
            return False
        try:
            self._cleanup_stale_interactive_docks()
            if self._interactive_dock is None:
                self._interactive_dock = InteractiveMapDock(self, parent=iface.mainWindow())
                # Si el usuario cierra el dock con la X de la cabecera, salimos
                # también del modo interactivo (consistencia con el botón Salir).
                try:
                    self._interactive_dock.closed.connect(
                        lambda: self.btn_map_interactive.setChecked(False)
                    )
                except Exception:
                    pass
                try:
                    iface.addDockWidget(QtCore.Qt.RightDockWidgetArea, self._interactive_dock)
                except Exception:
                    # Fallback: añadirlo al mainWindow directamente
                    try:
                        iface.mainWindow().addDockWidget(
                            QtCore.Qt.RightDockWidgetArea, self._interactive_dock
                        )
                    except Exception:
                        return False
            self._interactive_dock.show()
            self._interactive_dock.raise_()
            # Refresco inicial por si el usuario entró con una capa ya cargada
            try:
                self._interactive_dock._sync_from_dialog()
                self._interactive_dock._refresh_layer_status()
            except Exception:
                pass
            return True
        except Exception:
            self._interactive_dock = None
            return False

    def _hide_interactive_dock(self):
        try:
            if self._interactive_dock is not None:
                # 1) Desconectar TODAS las señales que el dock haya enganchado
                # (a iface, a self.cb_*, a self.ed_wrg_ti…). Sin esto, el
                # wrapper Python del dock sobrevive un instante después de
                # deleteLater() y los slots fallan con "QLineEdit deleted".
                try:
                    self._interactive_dock._teardown()
                except Exception:
                    pass
                try:
                    iface.removeDockWidget(self._interactive_dock)
                except Exception:
                    try:
                        iface.mainWindow().removeDockWidget(self._interactive_dock)
                    except Exception:
                        pass
                try:
                    self._interactive_dock.setParent(None)
                except Exception:
                    pass
                try:
                    self._interactive_dock.deleteLater()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._interactive_dock = None

    def _recalc_aep_from_interactive(self):
        """Recalcula AEP desde el messagebar (sin tener que abrir el diálogo)."""
        # 1) sincronizar/registrar coords actuales y preguntar qué capas entran
        # en el cálculo. Esto permite combinar varias capas/modelos de aerogenerador
        # cargados en el panel de capas, no solo la capa activa.
        try:
            self._sync_dirty_layers_to_csv()
        except Exception:
            pass
        try:
            if not self._ask_turbine_layers_for_compute():
                return
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Capas para AEP", f"No se pudo preparar la selección de capas:\n{e}")
            return

        # 2) pausar el map tool durante el cálculo
        was_interactive = self._interactive_tool is not None
        try:
            if was_interactive and self._canvas is not None:
                if self._interactive_prev_tool is not None:
                    self._canvas.setMapTool(self._interactive_prev_tool)
                else:
                    try:
                        iface.actionPan().trigger()
                    except Exception:
                        pass
        except Exception:
            pass

        # 3) ejecutar el cálculo normal
        try:
            self._run_compute_and_update()
        finally:
            # 4) restaurar el map tool interactivo si seguía activo
            try:
                if was_interactive and self._canvas is not None and self._interactive_tool is not None:
                    self._canvas.setMapTool(self._interactive_tool)
            except Exception:
                pass

    # ------------------ botones OK/Cancel ------------------
    def _accept(self):
        if any(r["wt"] is None for r in self._rows):
            QtWidgets.QMessageBox.warning(self, "Faltan modelos", "Define todos los modelos antes de continuar.")
            return
        for i, r in enumerate(self._rows, start=1):
            csv_path = r["coords_csv_le"].text().strip()
            if not csv_path or not os.path.isfile(csv_path):
                QtWidgets.QMessageBox.warning(self, "Coordenadas", f"Revisa el CSV del Modelo {i}.")
                return
        d = self.ed_dir.text().strip()
        w = ""
        try:
            w = self.ed_wrg.text().strip()
        except Exception:
            w = ""
        use_wrg = bool([p.strip() for p in w.split(";") if p.strip()])
        if not use_wrg:
            if not d or not os.path.isdir(d):
                QtWidgets.QMessageBox.warning(self, "Recurso eólico", "Selecciona una carpeta WAsP válida o un WRG/ZIP.")
                return
        self.accept()

    # ------------------ compat / util externas ------------------
    def get_models(self):
        models = []
        for r in getattr(self, "_rows", []):
            models.append(
                {
                    "name": r.get("name"),
                    "wt": r.get("wt"),
                    "meta": r.get("meta"),
                    "coords_csv": r.get("coords_csv_le").text().strip() if r.get("coords_csv_le") else "",
                }
            )
        return models

    def get_wasp_dir(self) -> str:
        try:
            return self.ed_dir.text().strip()
        except Exception:
            return ""

    def _open_union_recurso(self):
        try:
            from . import union_recurso as _ur  # dentro del paquete
        except Exception:
            import union_recurso as _ur  # fallback si se ejecuta fuera
        try:
            _ur.ejecutar_union_recurso(parent=self)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Unión Recurso",
                f"No se pudo iniciar la utilidad:\n{e}",
            )