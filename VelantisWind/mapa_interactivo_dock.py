# -*- coding: utf-8 -*-
"""mapa_interactivo_dock.py

Caja de herramientas (QDockWidget) que se muestra anclada a la derecha de
QGIS cuando el usuario entra en el modo "Mapa interactivo" del plugin
Velantis Wind. Permite trabajar sin necesidad de reabrir el diálogo
principal:

- Cambiar los modelos de física de PyWake (estela, turbulencia, bloqueo,
  rotor-average y motor WFM).
- Configurar la TI ambiente (raster(s) y alturas override) sin reabrir
  el diálogo: es la palanca real para mover el AEP en modelos TI-driven
  como Niayifar/Zong/TurboGaussian/TurboNOJ.
- Calcular o recalcular AEP para la capa que se está editando en el
  canvas.
- Exportar el layout editado a CSV ("Guardar layout").
- Graficar estelas y guardar/comparar escenarios A/B.
- Ver el estado de la capa de turbinas activa (nombre, nº de puntos,
  flag "editada") y salir del modo.

Los combos y editores del dock son PROXIES de los widgets del diálogo
principal (``AEPSetupDialog``): cualquier cambio se reenvía al widget
real del diálogo (donde sigue viviendo TODA la lógica de bloqueos,
validación, persistencia QSettings y refresh de metadatos) y los cambios
externos en el diálogo se reflejan en el dock. Eso evita duplicar reglas
de compatibilidad y mantiene una sola fuente de verdad.

Limpieza de señales: el dock registra cada ``connect()`` que hace en
``self._connections`` y los desconecta explícitamente en ``_teardown()``
(invocado desde ``closeEvent`` y desde el diálogo antes de
``deleteLater()``). Sin esto, las señales de QGIS y del diálogo siguen
disparándose contra el wrapper Python del dock destruido y aparece el
clásico ``wrapped C/C++ object of type QLineEdit has been deleted``.
"""

import os

from qgis.PyQt import QtCore, QtWidgets
from qgis.utils import iface
from qgis.core import QgsVectorLayer


class InteractiveMapDock(QtWidgets.QDockWidget):
    """Dock con física PyWake + TI ambiente + acciones para el modo Mapa Interactivo."""

    # (atributo_en_dock, atributo_en_dialogo, etiqueta_visible)
    _MIRRORED = (
        ("cb_wfm_engine",       "cb_wfm_engine",       "Motor WFM"),
        ("cb_wake_deficit",     "cb_wake_deficit",     "Estela"),
        ("cb_rotor_avg",        "cb_rotor_avg",        "Rotor-avg"),
        ("cb_blockage_deficit", "cb_blockage_deficit", "Bloqueo"),
        ("cb_turbulence_model", "cb_turbulence_model", "Turbulencia (modelo)"),
    )

    # Señal emitida cuando el usuario cierra el dock con la X de la cabecera
    closed = QtCore.pyqtSignal()

    def __init__(self, ctl, parent=None):
        super().__init__(
            "Mapa interactivo · Velantis Wind",
            parent or iface.mainWindow(),
        )
        self.ctl = ctl  # AEPSetupDialog
        self._syncing = False             # cortacircuito bidireccional combos
        self._syncing_ti = False          # cortacircuito bidireccional TI
        self._syncing_layer_combo = False  # cortacircuito selector de capa editable
        self._connections = []            # [(senders_signal, slot), ...]
        self._torn_down = False

        self.setObjectName("VelantisWindInteractiveDock")
        self.setAllowedAreas(
            QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea
        )
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetMovable
        )
        self.setMinimumWidth(300)

        self._build_ui()
        self._wire_signals()

        # Estado inicial: copiar valores actuales del diálogo
        self._sync_from_dialog()
        self._sync_ti_from_dialog()
        self._refresh_layer_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        wrapper = QtWidgets.QWidget(self)
        outer = QtWidgets.QVBoxLayout(wrapper)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # --- Capa activa ---------------------------------------------------
        grp_layer = QtWidgets.QGroupBox("Capa de turbinas")
        v_layer = QtWidgets.QVBoxLayout(grp_layer)
        v_layer.setContentsMargins(8, 8, 8, 6)
        v_layer.setSpacing(4)

        self.cb_edit_layer = QtWidgets.QComboBox()
        self.cb_edit_layer.setToolTip(
            "Elige qué capa/modelo editas con el click izquierdo/derecho del mapa. "
            "Esto permite modificar cualquiera de las capas cargadas, no solo la última creada."
        )
        self.cb_edit_layer.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.btn_refresh_layers = QtWidgets.QPushButton("↻")
        self.btn_refresh_layers.setMaximumWidth(34)
        self.btn_refresh_layers.setToolTip("Actualizar lista de capas de turbinas editables.")
        h_edit_layer = QtWidgets.QHBoxLayout()
        h_edit_layer.setSpacing(4)
        h_edit_layer.addWidget(QtWidgets.QLabel("Editar capa:"), 0)
        h_edit_layer.addWidget(self.cb_edit_layer, 1)
        h_edit_layer.addWidget(self.btn_refresh_layers, 0)
        v_layer.addLayout(h_edit_layer)

        self.lbl_layer_status = QtWidgets.QLabel("—")
        self.lbl_layer_status.setWordWrap(True)
        self.lbl_layer_status.setTextFormat(QtCore.Qt.RichText)
        self.lbl_layer_status.setStyleSheet("color: #333;")
        v_layer.addWidget(self.lbl_layer_status)

        self.lbl_hint = QtWidgets.QLabel(
            "Click izq: añadir · Click der: borrar · ESC: salir"
        )
        self.lbl_hint.setStyleSheet("color: #777; font-style: italic;")
        v_layer.addWidget(self.lbl_hint)

        # Botón visible desde el primer momento. El dock puede quedar más alto
        # que la pantalla en algunos QGIS/Windows; por eso no dependemos solo
        # de la botonera inferior.
        h_layer_quick = QtWidgets.QHBoxLayout()
        h_layer_quick.setSpacing(4)
        self.btn_show_dialog_top = QtWidgets.QPushButton("Volver al diálogo")
        self.btn_show_dialog_top.setToolTip(
            "Vuelve al diálogo principal sin salir del modo interactivo."
        )
        h_layer_quick.addWidget(self.btn_show_dialog_top, 1)
        v_layer.addLayout(h_layer_quick)

        outer.addWidget(grp_layer)

        # --- Física PyWake -------------------------------------------------
        grp_phys = QtWidgets.QGroupBox("Física PyWake")
        form = QtWidgets.QFormLayout(grp_phys)
        form.setContentsMargins(8, 8, 8, 8)
        form.setHorizontalSpacing(6)
        form.setVerticalSpacing(6)
        form.setLabelAlignment(QtCore.Qt.AlignLeft)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        for dock_attr, dlg_attr, label in self._MIRRORED:
            dlg_cb = getattr(self.ctl, dlg_attr, None)
            if not isinstance(dlg_cb, QtWidgets.QComboBox):
                continue
            cb = QtWidgets.QComboBox()
            for i in range(dlg_cb.count()):
                cb.addItem(dlg_cb.itemText(i), dlg_cb.itemData(i))
            tip = dlg_cb.toolTip() or ""
            if tip:
                cb.setToolTip(tip)
            cb.setSizeAdjustPolicy(
                QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
            form.addRow(QtWidgets.QLabel(label + ":"), cb)
            setattr(self, dock_attr, cb)

        outer.addWidget(grp_phys)

        # --- TI ambiente (raster + alturas) -------------------------------
        # Solo se muestra si el diálogo expone los editores correspondientes;
        # si no, la sección se omite.
        if isinstance(getattr(self.ctl, "ed_wrg_ti", None), QtWidgets.QLineEdit):
            grp_ti = QtWidgets.QGroupBox("TI ambiente (raster)")
            v_ti = QtWidgets.QVBoxLayout(grp_ti)
            v_ti.setContentsMargins(8, 8, 8, 8)
            v_ti.setSpacing(4)

            self.lbl_ti_status = QtWidgets.QLabel("—")
            self.lbl_ti_status.setWordWrap(True)
            self.lbl_ti_status.setTextFormat(QtCore.Qt.RichText)
            self.lbl_ti_status.setStyleSheet("color: #333;")
            v_ti.addWidget(self.lbl_ti_status)

            h_ti_btns = QtWidgets.QHBoxLayout()
            h_ti_btns.setSpacing(4)
            self.btn_ti_pick = QtWidgets.QPushButton("Elegir raster TI…")
            self.btn_ti_pick.setToolTip(
                "Selecciona uno o varios raster(s) .asc/.tif de TI ambiente "
                "(p.ej. de Vortex). Si no hay ninguno, se usa TI=10% como fallback."
            )
            self.btn_ti_clear = QtWidgets.QPushButton("Limpiar")
            self.btn_ti_clear.setToolTip("Deja la lista de raster(s) TI vacía.")
            h_ti_btns.addWidget(self.btn_ti_pick, 1)
            h_ti_btns.addWidget(self.btn_ti_clear, 0)
            v_ti.addLayout(h_ti_btns)

            # Alturas TI override (opcional)
            if isinstance(
                getattr(self.ctl, "ed_wrg_ti_heights", None), QtWidgets.QLineEdit
            ):
                h_ti_h = QtWidgets.QHBoxLayout()
                h_ti_h.setSpacing(4)
                lbl_h = QtWidgets.QLabel("Alturas [m]:")
                self.ed_ti_heights = QtWidgets.QLineEdit()
                self.ed_ti_heights.setPlaceholderText("p.ej. 90;120 (opcional)")
                self.ed_ti_heights.setToolTip(
                    self.ctl.ed_wrg_ti_heights.toolTip() or ""
                )
                h_ti_h.addWidget(lbl_h, 0)
                h_ti_h.addWidget(self.ed_ti_heights, 1)
                v_ti.addLayout(h_ti_h)
            else:
                self.ed_ti_heights = None

            outer.addWidget(grp_ti)
        else:
            # Marcadores para que el resto del código sepa que no hay sección TI
            self.lbl_ti_status = None
            self.btn_ti_pick = None
            self.btn_ti_clear = None
            self.ed_ti_heights = None

        # --- Acciones ------------------------------------------------------
        grp_act = QtWidgets.QGroupBox("Acciones")
        v_act = QtWidgets.QVBoxLayout(grp_act)
        v_act.setContentsMargins(8, 8, 8, 8)
        v_act.setSpacing(6)

        self.btn_calc = QtWidgets.QPushButton("Calcular / Recalcular AEP")
        self.btn_calc.setDefault(True)
        self.btn_calc.setToolTip(
            "Calcula AEP con la capa de turbinas activa y los modelos seleccionados."
        )
        self.btn_calc.setStyleSheet("font-weight: bold; padding: 6px;")
        v_act.addWidget(self.btn_calc)

        self.btn_export = QtWidgets.QPushButton("Guardar layout (CSV)…")
        self.btn_export.setToolTip(
            "Exporta los puntos editados de la capa activa a CSV. "
            "No sobrescribe el CSV original sin confirmar."
        )
        v_act.addWidget(self.btn_export)

        self.btn_plot_wakes = QtWidgets.QPushButton("Graficar estelas")
        self.btn_plot_wakes.setToolTip(
            "Dibuja mapas de estelas (N/E/S/O) con los modelos seleccionados."
        )
        v_act.addWidget(self.btn_plot_wakes)

        # Escenarios A/B en una fila compacta
        h_scn = QtWidgets.QHBoxLayout()
        h_scn.setSpacing(4)
        self.btn_scn_a = QtWidgets.QPushButton("Esc. A")
        self.btn_scn_a.setToolTip("Guarda el último cálculo como escenario A.")
        self.btn_scn_b = QtWidgets.QPushButton("Esc. B")
        self.btn_scn_b.setToolTip("Guarda el último cálculo como escenario B.")
        self.btn_scn_cmp = QtWidgets.QPushButton("A/B")
        self.btn_scn_cmp.setToolTip("Comparar escenarios A vs B.")
        for b in (self.btn_scn_a, self.btn_scn_b, self.btn_scn_cmp):
            b.setMinimumWidth(0)
            b.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            h_scn.addWidget(b)
        v_act.addLayout(h_scn)

        outer.addWidget(grp_act)
        outer.addStretch(1)

        # --- Salir / abrir diálogo completo --------------------------------
        h_exit = QtWidgets.QHBoxLayout()
        h_exit.setSpacing(4)
        self.btn_show_dialog = QtWidgets.QPushButton("Volver al diálogo")
        self.btn_show_dialog.setToolTip(
            "Vuelve al diálogo principal de Velantis Wind sin perder la edición."
        )
        self.btn_exit = QtWidgets.QPushButton("Salir")
        self.btn_exit.setToolTip("Salir del modo interactivo (ESC también funciona).")
        self.btn_exit.setStyleSheet("padding: 4px 12px;")
        h_exit.addWidget(self.btn_show_dialog, 1)
        h_exit.addWidget(self.btn_exit, 1)
        outer.addLayout(h_exit)

        # Scroll para que la botonera inferior nunca quede inaccesible en
        # pantallas pequeñas o cuando el dock se estrecha por grupos de capas.
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        try:
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        except Exception:
            pass
        scroll.setWidget(wrapper)
        self.setWidget(scroll)

    # ----------------------------------------------------------- signals
    def _connect(self, signal, slot):
        """Conecta y registra la conexión para desconectarla en _teardown()."""
        try:
            signal.connect(slot)
            self._connections.append((signal, slot))
        except Exception:
            # algunas señales pueden no ser conectables en versiones antiguas
            pass

    def _wire_signals(self):
        # ----- Combos: dock -> diálogo principal
        for dock_attr, dlg_attr, _ in self._MIRRORED:
            cb = getattr(self, dock_attr, None)
            if not isinstance(cb, QtWidgets.QComboBox):
                continue
            slot = (
                lambda _ix, da=dock_attr, ld=dlg_attr:
                    self._on_dock_combo_changed(da, ld)
            )
            self._connect(cb.currentIndexChanged, slot)

        # ----- Combos: diálogo -> dock (locks, persist, etc.)
        for _dock_attr, dlg_attr, _ in self._MIRRORED:
            dlg_cb = getattr(self.ctl, dlg_attr, None)
            if isinstance(dlg_cb, QtWidgets.QComboBox):
                self._connect(dlg_cb.currentIndexChanged, self._sync_from_dialog)

        # ----- TI ambiente: diálogo -> dock (cambios externos)
        dlg_ti = getattr(self.ctl, "ed_wrg_ti", None)
        if isinstance(dlg_ti, QtWidgets.QLineEdit):
            self._connect(dlg_ti.textChanged, self._on_dlg_ti_text_changed)
        dlg_ti_h = getattr(self.ctl, "ed_wrg_ti_heights", None)
        if isinstance(dlg_ti_h, QtWidgets.QLineEdit) and self.ed_ti_heights is not None:
            self._connect(dlg_ti_h.textChanged, self._on_dlg_ti_heights_text_changed)

        # ----- TI ambiente: dock -> diálogo (alturas, edición directa)
        if self.ed_ti_heights is not None:
            self._connect(
                self.ed_ti_heights.textChanged, self._on_dock_ti_heights_changed
            )

        # ----- Botones
        self._connect(self.btn_calc.clicked, self._on_calc_clicked)
        self._connect(self.btn_export.clicked, self._on_export_clicked)
        self._connect(self.btn_plot_wakes.clicked, self._on_plot_wakes_clicked)
        self._connect(
            self.btn_scn_a.clicked,
            lambda *_a: self._call_ctl("_store_current_scenario", "A"),
        )
        self._connect(
            self.btn_scn_b.clicked,
            lambda *_a: self._call_ctl("_store_current_scenario", "B"),
        )
        self._connect(
            self.btn_scn_cmp.clicked,
            lambda *_a: self._call_ctl("_compare_scenarios"),
        )
        self._connect(self.btn_show_dialog.clicked, self._on_show_dialog)
        if hasattr(self, "btn_show_dialog_top"):
            self._connect(self.btn_show_dialog_top.clicked, self._on_show_dialog)
        self._connect(self.btn_exit.clicked, self._on_exit_clicked)
        self._connect(self.cb_edit_layer.currentIndexChanged, self._on_edit_layer_changed)
        self._connect(self.btn_refresh_layers.clicked, self._refresh_layer_status)

        if self.btn_ti_pick is not None:
            self._connect(self.btn_ti_pick.clicked, self._on_ti_pick_clicked)
        if self.btn_ti_clear is not None:
            self._connect(self.btn_ti_clear.clicked, self._on_ti_clear_clicked)

        # ----- Capa activa
        try:
            self._connect(iface.currentLayerChanged, self._refresh_layer_status)
        except Exception:
            pass

    def _teardown(self):
        """Desconecta TODAS las señales registradas. Idempotente."""
        if self._torn_down:
            return
        self._torn_down = True
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except Exception:
                pass
        self._connections.clear()

    # ------------------------------------------------- ctl access guards
    def _ctl_alive(self) -> bool:
        """¿Es seguro acceder a self.ctl y a sus widgets?"""
        if self._torn_down:
            return False
        try:
            # Acceder a un atributo barato dispara RuntimeError si el wrapper C++
            # del diálogo ha sido destruido.
            _ = self.ctl.objectName()
            return True
        except Exception:
            return False

    # ----------------------------------------------------- sync de combos
    def _on_dock_combo_changed(self, dock_attr: str, dlg_attr: str):
        """Reenvía el cambio del combo del dock al combo del diálogo."""
        if self._syncing or not self._ctl_alive():
            return
        try:
            dock_cb = getattr(self, dock_attr, None)
            dlg_cb = getattr(self.ctl, dlg_attr, None)
            if not (isinstance(dock_cb, QtWidgets.QComboBox)
                    and isinstance(dlg_cb, QtWidgets.QComboBox)):
                return
            data = dock_cb.currentData()
            if data is None:
                return
            idx = dlg_cb.findData(data)
            if idx < 0 or idx == dlg_cb.currentIndex():
                return
            # Setear el índice en el diálogo dispara todas sus cadenas de señales
            # (persistencia QSettings, locks de compatibilidad, notas, etc.).
            self._syncing = True
            try:
                dlg_cb.setCurrentIndex(idx)
            finally:
                self._syncing = False
        except RuntimeError:
            # widget del diálogo borrado: nada que hacer
            return
        # Refresco extra para reflejar locks posibles del diálogo en el dock.
        self._sync_from_dialog()

    # ---------------------------------------------------------- selector capa editable
    def _refresh_edit_layer_combo(self, active_layer=None):
        """Sincroniza el combo de capas editables con el proyecto QGIS."""
        if self._syncing_layer_combo or not self._ctl_alive():
            return
        self._syncing_layer_combo = True
        try:
            candidates = []
            fn = getattr(self.ctl, "_candidate_turbine_layers_for_edit", None)
            if callable(fn):
                candidates = fn() or []

            try:
                active_id = active_layer.id() if isinstance(active_layer, QgsVectorLayer) else ""
            except Exception:
                active_id = ""
            if not active_id:
                try:
                    lyr = self.ctl._get_interactive_target_layer(allow_auto_pick=False)
                    active_id = lyr.id() if isinstance(lyr, QgsVectorLayer) else ""
                except Exception:
                    active_id = ""

            previous_id = ""
            try:
                previous_id = str(self.cb_edit_layer.currentData(QtCore.Qt.UserRole) or "")
            except Exception:
                previous_id = ""

            self.cb_edit_layer.clear()
            if not candidates:
                self.cb_edit_layer.addItem("Sin capas editables", "")
                self.cb_edit_layer.setEnabled(False)
                return

            self.cb_edit_layer.setEnabled(True)
            current_index = 0
            for i, c in enumerate(candidates):
                lid = str(c.get("layer_id") or "")
                row_idx = int(c.get("row_index", 0))
                gen = int(c.get("generation", -1))
                gen_txt = f" · gen {gen}" if gen >= 0 else ""
                active_txt = " · activa" if c.get("active") else ""
                text = (
                    f"M{row_idx+1} · {c.get('model_name')} | "
                    f"{c.get('n_points')} turb. | {c.get('layer_name')}{gen_txt}{active_txt}"
                )
                self.cb_edit_layer.addItem(text, lid)
                if lid and lid == active_id:
                    current_index = i
                elif not active_id and lid and lid == previous_id:
                    current_index = i
            if self.cb_edit_layer.count() > 0:
                self.cb_edit_layer.setCurrentIndex(current_index)
        finally:
            self._syncing_layer_combo = False

    def _on_edit_layer_changed(self, *_args):
        """El usuario elige qué capa/modelo quiere editar con el mapa."""
        if self._syncing_layer_combo or not self._ctl_alive():
            return
        try:
            layer_id = str(self.cb_edit_layer.currentData(QtCore.Qt.UserRole) or "")
        except Exception:
            layer_id = ""
        if not layer_id:
            return
        fn = getattr(self.ctl, "_set_interactive_edit_layer", None)
        if callable(fn):
            try:
                fn(layer_id)
            except RuntimeError:
                pass
            except Exception as e:
                try:
                    QtWidgets.QMessageBox.warning(self, "Mapa interactivo", f"No se pudo activar la capa seleccionada:\n{e}")
                except Exception:
                    pass
        self._refresh_layer_status()

    def _sync_from_dialog(self, *_args):
        """Refresca los combos del dock con valor + estado enabled del diálogo."""
        if self._syncing or not self._ctl_alive():
            return
        self._syncing = True
        try:
            for dock_attr, dlg_attr, _label in self._MIRRORED:
                dock_cb = getattr(self, dock_attr, None)
                dlg_cb = getattr(self.ctl, dlg_attr, None)
                if not (isinstance(dock_cb, QtWidgets.QComboBox)
                        and isinstance(dlg_cb, QtWidgets.QComboBox)):
                    continue
                try:
                    data = dlg_cb.currentData()
                    idx = dock_cb.findData(data) if data is not None else dlg_cb.currentIndex()
                    if 0 <= idx < dock_cb.count() and idx != dock_cb.currentIndex():
                        dock_cb.setCurrentIndex(idx)
                    dock_cb.setEnabled(dlg_cb.isEnabled())
                    tip = dlg_cb.toolTip() or ""
                    if tip:
                        dock_cb.setToolTip(tip)
                except RuntimeError:
                    continue
        finally:
            self._syncing = False

    # -------------------------------------------------- sync TI ambiente
    def _sync_ti_from_dialog(self):
        """Refresca el estado visible de TI ambiente desde el diálogo."""
        if self._syncing_ti or not self._ctl_alive():
            return
        if self.lbl_ti_status is None:
            return
        self._syncing_ti = True
        try:
            ti_text = ""
            try:
                ti_text = (self.ctl.ed_wrg_ti.text() or "").strip()
            except RuntimeError:
                ti_text = ""

            if not ti_text:
                self.lbl_ti_status.setText(
                    "<i>Sin raster TI</i> · "
                    "<span style='color:#a85a00;'>fallback 10%</span>"
                )
            else:
                paths = [p.strip() for p in ti_text.split(";") if p.strip()]
                if not paths:
                    self.lbl_ti_status.setText("<i>Sin raster TI</i>")
                elif len(paths) == 1:
                    self.lbl_ti_status.setText(
                        f"<b>{os.path.basename(paths[0])}</b>"
                    )
                else:
                    extras = len(paths) - 1
                    self.lbl_ti_status.setText(
                        f"<b>{os.path.basename(paths[0])}</b> "
                        f"<span style='color:#666;'>(+{extras} más)</span>"
                    )

            # Alturas
            if self.ed_ti_heights is not None:
                try:
                    h_text = (self.ctl.ed_wrg_ti_heights.text() or "").strip()
                except RuntimeError:
                    h_text = ""
                if self.ed_ti_heights.text().strip() != h_text:
                    self.ed_ti_heights.setText(h_text)
        finally:
            self._syncing_ti = False

    def _on_dlg_ti_text_changed(self, *_args):
        self._sync_ti_from_dialog()

    def _on_dlg_ti_heights_text_changed(self, *_args):
        self._sync_ti_from_dialog()

    def _on_dock_ti_heights_changed(self, *_args):
        """Propaga alturas escritas en el dock al QLineEdit del diálogo."""
        if self._syncing_ti or not self._ctl_alive():
            return
        if self.ed_ti_heights is None:
            return
        dlg_le = getattr(self.ctl, "ed_wrg_ti_heights", None)
        if not isinstance(dlg_le, QtWidgets.QLineEdit):
            return
        self._syncing_ti = True
        try:
            new = self.ed_ti_heights.text()
            if dlg_le.text() != new:
                dlg_le.setText(new)
        except RuntimeError:
            pass
        finally:
            self._syncing_ti = False

    def _on_ti_pick_clicked(self, *_args):
        """Reusa el file dialog del diálogo principal y refresca la vista."""
        was_active, canvas, _prev = self._pause_map_tool()
        try:
            self._call_ctl("_pick_wrg_ti")
        finally:
            self._resume_map_tool(was_active, canvas)
            self._sync_ti_from_dialog()

    def _on_ti_clear_clicked(self, *_args):
        self._call_ctl("_clear_wrg_ti")
        self._sync_ti_from_dialog()

    # ------------------------------------------------------------ helpers
    def _call_ctl(self, name: str, *args, **kwargs):
        if not self._ctl_alive():
            return None
        fn = getattr(self.ctl, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except RuntimeError:
                return None
            except Exception as e:
                try:
                    QtWidgets.QMessageBox.warning(
                        self, "Velantis Wind", f"{name} falló:\n{e}"
                    )
                except Exception:
                    pass
        return None

    def _pause_map_tool(self):
        """Devuelve (was_active, canvas, prev_tool) para poder restaurar."""
        was_active = False
        canvas = None
        prev = None
        if self._ctl_alive():
            try:
                was_active = getattr(self.ctl, "_interactive_tool", None) is not None
                canvas = getattr(self.ctl, "_canvas", None)
                prev = getattr(self.ctl, "_interactive_prev_tool", None)
                if was_active and canvas is not None and prev is not None:
                    canvas.setMapTool(prev)
            except RuntimeError:
                pass
        return was_active, canvas, prev

    def _resume_map_tool(self, was_active, canvas):
        if not (was_active and self._ctl_alive()):
            return
        try:
            tool = getattr(self.ctl, "_interactive_tool", None)
            if canvas is not None and tool is not None:
                canvas.setMapTool(tool)
        except RuntimeError:
            pass

    # --------------------------------------------------------- acciones
    def _on_calc_clicked(self, *_args):
        if not self._ctl_alive():
            return
        # Reutilizar el helper original con pausar/restaurar el map tool
        fn = getattr(self.ctl, "_recalc_aep_from_interactive", None)
        if callable(fn):
            try:
                fn()
            except RuntimeError:
                pass
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Calcular AEP", str(e))
            finally:
                self._refresh_layer_status()
            return
        # Fallback manual
        was_active, canvas, _prev = self._pause_map_tool()
        try:
            self._call_ctl("_run_compute_and_update")
        finally:
            self._resume_map_tool(was_active, canvas)
            self._refresh_layer_status()

    def _on_export_clicked(self, *_args):
        was_active, canvas, _prev = self._pause_map_tool()
        try:
            self._call_ctl("_export_edited_layouts_dialog")
        finally:
            self._resume_map_tool(was_active, canvas)
            self._refresh_layer_status()

    def _on_plot_wakes_clicked(self, *_args):
        was_active, canvas, _prev = self._pause_map_tool()
        try:
            self._call_ctl("_run_plot_wakes")
        finally:
            self._resume_map_tool(was_active, canvas)

    def _on_show_dialog(self, *_args):
        """Reabre el diálogo completo SIN salir del modo interactivo."""
        if not self._ctl_alive():
            return
        try:
            self.ctl._hidden_for_interactive = False
        except RuntimeError:
            return
        except Exception:
            pass
        try:
            self.ctl.show()
            self.ctl.raise_()
            self.ctl.activateWindow()
        except Exception:
            pass

    def _on_exit_clicked(self, *_args):
        """Sale del modo interactivo (delega en el toggle del diálogo)."""
        if not self._ctl_alive():
            return
        try:
            btn = getattr(self.ctl, "btn_map_interactive", None)
            if btn is not None:
                btn.setChecked(False)  # dispara _deactivate_map_interactive
                return
        except RuntimeError:
            return
        except Exception:
            pass
        self._call_ctl("_deactivate_map_interactive")

    # ------------------------------------------------------ estado capa
    def _refresh_layer_status(self, *_args):
        if not self._ctl_alive():
            return

        layer = None
        try:
            layer = self.ctl._get_interactive_target_layer()
        except RuntimeError:
            return
        except Exception:
            layer = None

        # Puede haber una capa activa vacía (por ejemplo el segundo modelo recién
        # creado) y, a la vez, otras capas de turbinas con puntos disponibles para
        # el cálculo multi-modelo. Por eso el botón de cálculo no debe depender
        # exclusivamente de la capa activa.
        candidates = []
        try:
            fn_candidates = getattr(self.ctl, "_candidate_turbine_layers_for_compute", None)
            if callable(fn_candidates):
                candidates = fn_candidates() or []
        except RuntimeError:
            candidates = []
        except Exception:
            candidates = []
        has_compute_layers = bool(candidates)

        try:
            self._refresh_edit_layer_combo(layer if isinstance(layer, QgsVectorLayer) else None)
        except Exception:
            pass

        if not isinstance(layer, QgsVectorLayer):
            extra = ""
            if has_compute_layers:
                try:
                    n_layers = len(candidates)
                    n_turbs = sum(int(c.get("n_points", 0) or 0) for c in candidates)
                    extra = (
                        f"<br><span style='color:#0a7;'>Hay {n_layers} capa(s) "
                        f"con {n_turbs} turbina(s) disponibles para calcular.</span>"
                    )
                except Exception:
                    extra = ""
            self.lbl_layer_status.setText(
                "<span style='color:#a85a00;'><b>Sin capa activa</b></span>"
                " de turbinas «<i>Modelo (CSV)</i>».<br>"
                "Selecciónala en el panel de capas, o usa "
                "«Generar capas de puntos» en el diálogo."
                + extra
            )
            self.btn_calc.setEnabled(has_compute_layers)
            self.btn_export.setEnabled(False)
            self.btn_plot_wakes.setEnabled(has_compute_layers)
            return

        try:
            n = layer.featureCount()
        except Exception:
            n = 0
        try:
            ids = getattr(self.ctl, "_dirty_turbine_layer_ids", set()) or set()
            dirty = layer.id() in ids
        except RuntimeError:
            dirty = False
        except Exception:
            dirty = False

        edited_tag = (
            " · <span style='color:#0a7;'><b>editada</b></span>" if dirty else ""
        )
        warn = ""
        if n == 0:
            warn = (
                "<br><span style='color:#a85a00;'>Aún no hay turbinas en esta capa: "
                "haz click izq en el mapa para añadirlas.</span>"
            )
            if has_compute_layers:
                try:
                    n_layers = len(candidates)
                    n_turbs = sum(int(c.get("n_points", 0) or 0) for c in candidates)
                    warn += (
                        f"<br><span style='color:#0a7;'>Puedes calcular igualmente con "
                        f"{n_layers} capa(s) ya cargada(s), {n_turbs} turbina(s) en total.</span>"
                    )
                except Exception:
                    pass
        self.lbl_layer_status.setText(
            f"<b>{layer.name()}</b>{edited_tag}<br>"
            f"{n} turbina(s){warn}"
        )
        self.btn_calc.setEnabled((n > 0) or has_compute_layers)
        self.btn_export.setEnabled(True)
        self.btn_plot_wakes.setEnabled((n > 0) or has_compute_layers)

    # ------------------------------------------------------------ close
    def closeEvent(self, ev):
        """X de cabecera → desconectamos señales y salimos del modo interactivo."""
        # Desconectar señales ANTES de cualquier emisión externa que pudiera
        # llegar tarde y pillar el wrapper Python en estado intermedio.
        self._teardown()
        try:
            self.closed.emit()
        except Exception:
            pass
        super().closeEvent(ev)
