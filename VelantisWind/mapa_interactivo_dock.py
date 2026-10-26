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
- Calcular o recalcular el AEP con las capas elegidas en las filas del
  diálogo.
- Exportar el layout editado a CSV ("Guardar layout").
- Crear ráster de estelas y guardar/comparar escenarios A/B.
- Ver el estado de la capa de turbinas que se edita (nombre, nº de puntos,
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
from qgis.core import QgsProject, QgsVectorLayer

from .ui_core.wake_group import WakeGroupMirror

try:
    from .i18n import apply_i18n, mark_translated, tr_text
except Exception:  # pragma: no cover
    def apply_i18n(_widget):
        return None
    def mark_translated(_widget):
        return None
    def tr_text(text):
        return text
try:
    from . import interactive_i18n
    interactive_i18n.register()
except Exception:  # nosec B110
    pass

try:
    from .spacing_core import SpacingController
except Exception:
    SpacingController = None  # type: ignore


class InteractiveMapDock(QtWidgets.QDockWidget):
    """Dock con física PyWake + TI ambiente + acciones para el modo Mapa Interactivo."""

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
        # Las altas y bajas de puntos en las capas de las filas (también desde la edición de QGIS) cambian si se puede
        # calcular: refrescan el estado, una vez por ráfaga.
        self._watched_layers = {}  # id -> capa de una fila cuyas señales arrancan el refresco
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setSingleShot(True)

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
        self.cb_edit_layer.setToolTip(tr_text(
            "Elige qué capa/modelo editas con el clic izquierdo/derecho del mapa. "
            "Esto permite modificar cualquiera de las capas cargadas, no solo la última creada."
        ))
        # Sus elementos, el estado de la capa y el de la TI llevan nombres de capas y de ficheros: se ponen ya
        # traducidos y apply_i18n no los toca.
        mark_translated(self.cb_edit_layer)
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
        mark_translated(self.lbl_layer_status)
        v_layer.addWidget(self.lbl_layer_status)

        self.lbl_hint = QtWidgets.QLabel(
            "Clic izq: añadir · Clic der: borrar · ESC: salir"
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

        # The visible selectors of the dialog's group, with the same options enabled, the same help and the same
        # messages; a change here is a change of the group (#75, row 1.6).
        group = getattr(self.ctl, "wake_group", None)
        self._wake_mirror = WakeGroupMirror(group, form, tr=tr_text) if group is not None else None

        outer.addWidget(grp_phys)

        # --- TI ambiente (raster + alturas) -------------------------------
        # Solo se muestra si el diálogo expone los editores correspondientes;
        # si no, la sección se omite.
        if isinstance(getattr(self.ctl, "ed_wrg_ti", None), QtWidgets.QLineEdit):
            grp_ti = QtWidgets.QGroupBox("TI ambiente (ráster)")
            v_ti = QtWidgets.QVBoxLayout(grp_ti)
            v_ti.setContentsMargins(8, 8, 8, 8)
            v_ti.setSpacing(4)

            self.lbl_ti_status = QtWidgets.QLabel("—")
            self.lbl_ti_status.setWordWrap(True)
            self.lbl_ti_status.setTextFormat(QtCore.Qt.RichText)
            self.lbl_ti_status.setStyleSheet("color: #333;")
            mark_translated(self.lbl_ti_status)
            v_ti.addWidget(self.lbl_ti_status)

            h_ti_btns = QtWidgets.QHBoxLayout()
            h_ti_btns.setSpacing(4)
            self.btn_ti_pick = QtWidgets.QPushButton("Elegir ráster TI…")
            self.btn_ti_pick.setToolTip(
                "Selecciona uno o varios rásteres .asc/.tif de TI ambiente. Si no hay ninguno, se usa TI = 10 % como respaldo."
            )
            self.btn_ti_clear = QtWidgets.QPushButton("Limpiar")
            self.btn_ti_clear.setToolTip("Deja la lista de ráster(es) TI vacía.")
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

        # --- Envolvente de separación --------------------------------------
        # Módulo spacing_core: elipse semitransparente por turbina con
        # orientación automática (sector más energético) o definida en
        # pantalla. Se reutiliza el controller compartido del diálogo
        # principal (botón «Envolventes de separación…»); solo si no existe
        # se crea uno propio (_owns_spacing) que se destruye con el dock.
        self._spacing = None
        self._owns_spacing = False
        if SpacingController is not None:
            try:
                get = getattr(self.ctl, "_ensure_spacing_controller", None)
                if callable(get):
                    self._spacing = get()
                if self._spacing is None:
                    self._spacing = SpacingController(self.ctl, iface.mapCanvas(), parent=self)
                    self._owns_spacing = True
                outer.addWidget(self._spacing.panel)
            except Exception:
                self._spacing = None
                self._owns_spacing = False

        # --- Acciones ------------------------------------------------------
        grp_act = QtWidgets.QGroupBox("Acciones")
        v_act = QtWidgets.QVBoxLayout(grp_act)
        v_act.setContentsMargins(8, 8, 8, 8)
        v_act.setSpacing(6)

        self.btn_calc = QtWidgets.QPushButton("Calcular / Recalcular AEP")
        self.btn_calc.setDefault(True)
        self.btn_calc.setToolTip(
            "Calcula el AEP con las capas de turbinas elegidas en las filas y sus modelos."
        )
        self.btn_calc.setStyleSheet("font-weight: bold; padding: 6px;")
        v_act.addWidget(self.btn_calc)

        self.btn_export = QtWidgets.QPushButton("Guardar la disposición (CSV)…")
        self.btn_export.setToolTip(
            "Guardar a CSV los puntos editados en el mapa interactivo.\n"
            "Por defecto: <nombre de la capa>_edited.csv."
        )
        v_act.addWidget(self.btn_export)

        self.btn_plot_wakes = QtWidgets.QPushButton("Crear ráster de estelas")
        self.btn_plot_wakes.setToolTip(
            "Crea una capa ráster QGIS de velocidad efectiva con las turbinas y el recurso seleccionados."
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
        except Exception:  # nosec B110
            pass
        scroll.setWidget(wrapper)
        self.setWidget(scroll)
        apply_i18n(self)

    # ----------------------------------------------------------- signals
    def _connect(self, signal, slot):
        """Conecta y registra la conexión para desconectarla en _teardown()."""
        try:
            signal.connect(slot)
            self._connections.append((signal, slot))
        except Exception:  # nosec B110
            # algunas señales pueden no ser conectables en versiones antiguas
            pass

    def _wire_signals(self):
        # ----- Física: el espejo del grupo del diálogo (sus cambios se ven aquí)
        if getattr(self, "_wake_mirror", None) is not None:
            self._connections.append((self._wake_mirror.group.changed, self._wake_mirror.sync))

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
        self._connect(self._status_timer.timeout, self._refresh_layer_status)

        if self.btn_ti_pick is not None:
            self._connect(self.btn_ti_pick.clicked, self._on_ti_pick_clicked)
        if self.btn_ti_clear is not None:
            self._connect(self.btn_ti_clear.clicked, self._on_ti_clear_clicked)

        # ----- Capa activa
        try:
            self._connect(iface.currentLayerChanged, self._refresh_layer_status)
        except Exception:  # nosec B110
            pass

    def _teardown(self):
        """Desconecta TODAS las señales registradas. Idempotente."""
        if self._torn_down:
            return
        self._torn_down = True
        # Limpiar el módulo de envolventes de separación. Si el controller es
        # el compartido del diálogo, NO se destruye (las envolventes deben
        # seguir vivas al volver al diálogo): solo se devuelve el panel.
        try:
            if getattr(self, "_spacing", None) is not None:
                if getattr(self, "_owns_spacing", False):
                    self._spacing.teardown()
                else:
                    try:
                        self._spacing.panel.setParent(None)
                    except Exception:  # nosec B110
                        pass
                self._spacing = None
        except Exception:  # nosec B110
            pass
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except Exception:  # nosec B110
                pass
        self._connections.clear()
        self._unwatch_layers(set())

    def _unwatch_layers(self, keep_ids):
        """Deja de seguir las capas que ya no están en ninguna fila.

        Solo se desconectan las que siguen en el proyecto, que están vivas: una que ya no está puede estar destruida, y
        desconectar la señal de una capa destruida puede tumbar QGIS (pasa a través de un objeto de señal guardado);
        Qt ya cortó esa conexión al destruirla. Una capa sacada del proyecto sin destruirla seguiría arrancando
        refrescos, que no cambian nada.
        """
        for layer_id in [i for i in self._watched_layers if i not in keep_ids]:
            layer = self._watched_layers.pop(layer_id)
            if QgsProject.instance().mapLayer(layer_id) is not None:
                for signal in ("repaintRequested", "crsChanged"):
                    try:
                        getattr(layer, signal).disconnect(self._status_timer.start)
                    except Exception:  # nosec B110
                        pass

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
                    lyr = self.ctl._get_interactive_target_layer()
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
                self.cb_edit_layer.addItem(tr_text("Sin capas editables"), "")
                self.cb_edit_layer.setEnabled(False)
                return

            self.cb_edit_layer.setEnabled(True)
            current_index = 0
            for i, c in enumerate(candidates):
                lid = str(c.get("layer_id") or "")
                row_idx = int(c.get("row_index", 0))
                active_txt = f" · {tr_text('activa')}" if c.get("active") else ""
                text = (
                    f"M{row_idx+1} · {c.get('model_name')} | "
                    f"{c.get('n_points')} {tr_text('turb.')} | {c.get('layer_name')}{active_txt}"
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
                    QtWidgets.QMessageBox.warning(self, tr_text("Mapa interactivo"), f"{tr_text('No se pudo activar la capa seleccionada:')}\n{e}")
                except Exception:  # nosec B110
                    pass
        self._refresh_layer_status()

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
                    f"<i>{tr_text('Sin ráster TI')}</i> · "
                    f"<span style='color:#a85a00;'>{tr_text('respaldo TI=10%')}</span>"
                )
            else:
                paths = [p.strip() for p in ti_text.split(";") if p.strip()]
                if not paths:
                    self.lbl_ti_status.setText(f"<i>{tr_text('Sin ráster TI')}</i>")
                elif len(paths) == 1:
                    self.lbl_ti_status.setText(
                        f"<b>{os.path.basename(paths[0])}</b>"
                    )
                else:
                    extras = len(paths) - 1
                    self.lbl_ti_status.setText(
                        f"<b>{os.path.basename(paths[0])}</b> "
                        f"<span style='color:#666;'>(+{extras} {tr_text('más')})</span>"
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
                        self, "Velantis Wind", f"{name} {tr_text('falló:')}\n{e}"
                    )
                except Exception:  # nosec B110
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
                QtWidgets.QMessageBox.warning(self, tr_text("Calcular AEP"), str(e))
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
        except Exception:  # nosec B110
            pass
        try:
            # Minimized with its window controls (#87), it is still visible: bring it back, keeping it maximized if it was.
            self.ctl.setWindowState(self.ctl.windowState() & ~QtCore.Qt.WindowMinimized)
            self.ctl.show()
            self.ctl.raise_()
            self.ctl.activateWindow()
        except Exception:  # nosec B110
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
        except Exception:  # nosec B110
            pass
        self._call_ctl("_deactivate_map_interactive")

    # ------------------------------------------------------ estado capa
    def retranslate(self):
        apply_i18n(self)
        self.cb_edit_layer.setToolTip(tr_text(
            "Elige qué capa/modelo editas con el clic izquierdo/derecho del mapa. "
            "Esto permite modificar cualquiera de las capas cargadas, no solo la última creada."
        ))
        self._refresh_layer_status()
        self._sync_ti_from_dialog()
        if self._wake_mirror is not None:
            self._wake_mirror.sync()

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

        # El cálculo y el ráster usan todas las filas y paran en la primera sin capa con turbinas: los botones
        # dependen de las filas, no de la capa que se edita.
        missing = []
        try:
            n_rows = len(getattr(self.ctl, "_rows", []) or [])
        except RuntimeError:
            n_rows = 0
        row_layer_ids = set()
        for idx in range(n_rows):
            try:
                row_layer = self.ctl._find_interactive_layer_for_row(idx)
                if row_layer is not None:
                    row_layer_ids.add(row_layer.id())
                    if row_layer.id() not in self._watched_layers:
                        # repaintRequested llega con cada cambio de entidades, en edición, al guardar o al descartar,
                        # y con las escrituras del mapa interactivo; crsChanged, al corregir el sistema de la capa.
                        row_layer.repaintRequested.connect(self._status_timer.start)
                        row_layer.crsChanged.connect(self._status_timer.start)
                        self._watched_layers[row_layer.id()] = row_layer
            except Exception:  # nosec B110
                pass
            try:
                n_row = len(self.ctl._collect_layer_points_for_row(idx) or [])
            except Exception:
                # Una capa que no se puede leer no cuenta; el cálculo dirá por qué.
                n_row = 0
            if not n_row:
                missing.append(idx + 1)
        has_compute_layers = n_rows > 0 and not missing
        self._unwatch_layers(row_layer_ids)
        missing_warn = (
            "<br><span style='color:#a85a00;'>"
            + tr_text("Modelos sin capa con turbinas: {rows}.").format(rows=", ".join(str(i) for i in missing))
            + " " + tr_text("Para calcular, todas las filas deben tener una capa con turbinas.")
            + "</span>"
        ) if missing else ""

        try:
            self._refresh_edit_layer_combo(layer if isinstance(layer, QgsVectorLayer) else None)
        except Exception:  # nosec B110
            pass

        if not isinstance(layer, QgsVectorLayer):
            self.lbl_layer_status.setText(
                "<span style='color:#a85a00;'><b>" + tr_text("Ninguna fila tiene capa de turbinas.") + "</b></span><br>"
                + tr_text("Elige una capa en el selector «Capa de turbinas» de una fila, o usa «Generar capas de puntos» en el diálogo.")
                + missing_warn
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
            " · <span style='color:#0a7;'><b>" + tr_text("editada") + "</b></span>" if dirty else ""
        )
        warn = ""
        if n == 0:
            warn = (
                "<br><span style='color:#a85a00;'>" +
                tr_text("Aún no hay turbinas en esta capa: haz clic izq en el mapa para añadirlas.") +
                "</span>"
            )
        self.lbl_layer_status.setText(
            f"<b>{layer.name()}</b>{edited_tag}<br>"
            f"{n} {tr_text('turbina(s)')}{warn}{missing_warn}"
        )
        self.btn_calc.setEnabled(has_compute_layers)
        self.btn_export.setEnabled(True)
        self.btn_plot_wakes.setEnabled(has_compute_layers)

    # ------------------------------------------------------------ close
    def closeEvent(self, ev):
        """X de cabecera → desconectamos señales y salimos del modo interactivo."""
        # Desconectar señales ANTES de cualquier emisión externa que pudiera
        # llegar tarde y pillar el wrapper Python en estado intermedio.
        self._teardown()
        try:
            self.closed.emit()
        except Exception:  # nosec B110
            pass
        super().closeEvent(ev)
