# -*- coding: utf-8 -*-
"""
Hub principal del plugin Velantis Wind.

Objetivos:
- Pantalla inicial con 3 módulos: Energía, Ruido, Sombras y parpadeo.
- Conectar inmediatamente con el módulo de Energía ya existente.
- Mostrar los tres módulos operativos: Energía, Ruido y Sombras/Parpadeo.
- Mostrar un pequeño resumen del estado del proyecto/cálculo.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes
from .noise_page import NoisePage
from .shadow_page import ShadowPage
from .i18n import apply_i18n, current_language, install_runtime_i18n_patches, set_language, tr_text as _tr
from .support_dialog import show_support_dialog
from .ui_core.responsive import fit_to_screen, configure_scroll_area

_GROUP_NAME = "AEP · Coordenadas por modelo"


class _ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event):  # type: ignore[override]
        try:
            if event.button() == QtCore.Qt.LeftButton:
                self.clicked.emit()
        finally:
            super().mousePressEvent(event)


class VelantisHubDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, energy_dialog_factory: Optional[Callable[[QtWidgets.QWidget], QtWidgets.QDialog]] = None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self.setWindowTitle(_tr("Velantis Wind · Hub principal"))
        self._fit_to_screen()
        self._energy_dialog_factory = energy_dialog_factory
        self._energy_dialog = None
        self._qsettings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self._build_ui()
        self._apply_style()
        self._refresh_summary()
        apply_i18n(self)


    def _fit_to_screen(self):
        # Keep the hub usable on laptops and split-screen QGIS sessions.
        # The home page now scrolls internally, so the dialog can safely be
        # smaller without cutting the lower VelantisWind/support button.
        fit_to_screen(self, preferred=(980, 680), minimum=(620, 420), max_ratio=(0.94, 0.92))

    # --------------------------- UI ---------------------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.stack = QtWidgets.QStackedWidget(self)
        root.addWidget(self.stack, 1)

        self.page_home = self._build_home_page()
        self.page_noise = NoisePage(self, on_back=lambda: self.stack.setCurrentWidget(self.page_home))
        self.page_flicker = ShadowPage(self, on_back=lambda: self.stack.setCurrentWidget(self.page_home))

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_noise)
        self.stack.addWidget(self.page_flicker)
        self.stack.setCurrentWidget(self.page_home)

    def _build_home_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # Main content lives in a scroll area. This avoids the previous issue
        # where the logo/summary/footer could be clipped on smaller screens.
        scroll = QtWidgets.QScrollArea(page)
        configure_scroll_area(scroll)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        content = QtWidgets.QWidget(scroll)
        v = QtWidgets.QVBoxLayout(content)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(10)

        title = QtWidgets.QLabel("Velantis Wind")
        title.setObjectName("hubTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Selecciona el módulo de trabajo. Los tres módulos están operativos: "
            "Energía (AEP y wakes), Ruido, y Sombras (shadow flicker)."
        )
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("hubSubtitle")
        v.addWidget(subtitle)

        # Selector de idioma global del plugin
        lang_box = QtWidgets.QGroupBox(_tr("Idioma"), self)
        lang_lay = QtWidgets.QHBoxLayout(lang_box)
        lang_lay.setContentsMargins(10, 6, 10, 6)
        lang_lay.setSpacing(8)
        lang_lay.addWidget(QtWidgets.QLabel(_tr("Idioma del plugin:")))
        self.cb_language = QtWidgets.QComboBox(self)
        self.cb_language.addItem("Español", "es")
        self.cb_language.addItem("English", "en")
        idx_lang = self.cb_language.findData(current_language())
        self.cb_language.setCurrentIndex(idx_lang if idx_lang >= 0 else 0)
        self.cb_language.currentIndexChanged.connect(self._on_language_changed)
        lang_lay.addWidget(self.cb_language, 0)
        lang_note = QtWidgets.QLabel(_tr("El idioma seleccionado se aplicará al hub, módulos, avisos y resúmenes generados."))
        lang_note.setObjectName("hubMinor")
        lang_note.setWordWrap(True)
        lang_lay.addWidget(lang_note, 1)
        v.addWidget(lang_box)

        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(10)
        cards.addStretch(1)

        self.btn_energy = self._make_card_button("Energía\nAEP y wakes")
        self.btn_noise = self._make_card_button("Ruido")
        self.btn_flicker = self._make_card_button("Sombras y\nparpadeo")

        self.btn_energy.clicked.connect(self._open_energy_module)
        self.btn_noise.clicked.connect(self._open_noise_module)
        self.btn_flicker.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_flicker))

        cards.addWidget(self.btn_energy)
        cards.addWidget(self.btn_noise)
        cards.addWidget(self.btn_flicker)
        cards.addStretch(1)
        v.addLayout(cards)

        logo_wrap = QtWidgets.QWidget(self)
        logo_lay = QtWidgets.QVBoxLayout(logo_wrap)
        logo_lay.setContentsMargins(0, 2, 0, 2)
        logo_lay.setSpacing(4)

        self.logo_label = _ClickableLabel(self)
        self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
        self.logo_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.logo_label.setToolTip("Inicio")
        self.logo_label.setMinimumHeight(115)
        self.logo_label.setMaximumHeight(230)
        self.logo_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "velantiswind_logo.png")
        if os.path.exists(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                try:
                    geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
                    logo_side = max(150, min(230, int(geo.height() * 0.28)))
                except Exception:
                    logo_side = 210
                self.logo_label.setPixmap(pix.scaled(logo_side, logo_side, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            self.logo_label.setText("Velantis")
        self.logo_label.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_home))
        logo_lay.addWidget(self.logo_label, 0, QtCore.Qt.AlignCenter)

        info = QtWidgets.QLabel("Pulsa el logo para volver al inicio desde los módulos preparados.")
        info.setAlignment(QtCore.Qt.AlignCenter)
        info.setObjectName("hubMinor")
        info.setWordWrap(True)
        logo_lay.addWidget(info)
        v.addWidget(logo_wrap, 0)

        grp = QtWidgets.QGroupBox("Resumen del proyecto")
        form = QtWidgets.QFormLayout(grp)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(5)
        self.lbl_project = QtWidgets.QLabel("-")
        self.lbl_crs = QtWidgets.QLabel("-")
        self.lbl_layout = QtWidgets.QLabel("-")
        self.lbl_resource = QtWidgets.QLabel("-")
        self.lbl_ti = QtWidgets.QLabel("-")
        self.lbl_status = QtWidgets.QLabel("Energía: operativa · Ruido: operativo · Sombras: operativo")
        for w in [self.lbl_project, self.lbl_crs, self.lbl_layout, self.lbl_resource, self.lbl_ti, self.lbl_status]:
            w.setWordWrap(True)
        form.addRow("Proyecto:", self.lbl_project)
        form.addRow("CRS:", self.lbl_crs)
        form.addRow("Layout activo:", self.lbl_layout)
        form.addRow("Recurso:", self.lbl_resource)
        form.addRow("TI WRG:", self.lbl_ti)
        form.addRow("Estado módulos:", self.lbl_status)
        v.addWidget(grp)
        v.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Sticky footer: keep this visible even when the main content scrolls.
        # This fixes the clipped/barely-visible VelantisWind button on short screens.
        support_footer = QtWidgets.QHBoxLayout()
        support_footer.setContentsMargins(6, 0, 6, 2)
        support_footer.addStretch(1)
        self.btn_support_velantis = QtWidgets.QPushButton(_tr("♡ Apoyar VelantisWind"), self)
        self.btn_support_velantis.setObjectName("supportVelantisButton")
        self.btn_support_velantis.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_support_velantis.setMinimumHeight(34)
        self.btn_support_velantis.setMinimumWidth(190)
        self.btn_support_velantis.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.btn_support_velantis.setToolTip(_tr("Apoya el mantenimiento, la documentación, las pruebas y el desarrollo open source futuro."))
        self.btn_support_velantis.clicked.connect(self._open_support_dialog)
        support_footer.addWidget(self.btn_support_velantis, 0, QtCore.Qt.AlignRight)
        outer.addLayout(support_footer)

        return page

    def _make_card_button(self, text: str) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(text)
        btn.setMinimumSize(120, 64)
        btn.setMaximumHeight(82)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setObjectName("moduleCardButton")
        return btn

    def _apply_style(self):
        self.setStyleSheet(
            """
            QDialog { background: #f3f5f7; }
            QLabel#hubTitle { font-size: 23px; font-weight: 700; color: #103b67; }
            QLabel#hubSubtitle { font-size: 12px; color: #4f5d6b; }
            QLabel#hubMinor { font-size: 11px; color: #6d7a86; }
            QLabel#moduleTitle { font-size: 22px; font-weight: 700; color: #103b67; }
            QPushButton#moduleCardButton {
                background: white;
                border: 2px solid #103b67;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                padding: 8px;
                color: #103b67;
                text-align: center;
            }
            QPushButton#moduleCardButton:hover {
                background: #eaf3fb;
                border-color: #1f7dc2;
            }
            QPushButton#supportVelantisButton {
                background: #ffffff;
                border: 1.5px solid #b8cad8;
                border-radius: 11px;
                color: #103b67;
                font-size: 12px;
                font-weight: 600;
                padding: 7px 16px;
                min-height: 30px;
            }
            QPushButton#supportVelantisButton:hover {
                background: #eaf3fb;
                border-color: #1f7dc2;
                color: #0d345c;
            }
            QGroupBox {
                border: 1px solid #cbd4dc;
                border-radius: 10px;
                margin-top: 8px;
                background: white;
                font-weight: 600;
                color: #103b67;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }
            """
        )

    def _open_support_dialog(self):
        try:
            show_support_dialog(self)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, _tr("Apoyar VelantisWind"), str(e))

    def _on_language_changed(self):
        try:
            lang = self.cb_language.currentData() or "es"
            set_language(str(lang))
            apply_i18n(self)
            for page in (getattr(self, "page_noise", None), getattr(self, "page_flicker", None)):
                try:
                    apply_i18n(page)
                    if hasattr(page, "refresh_from_project"):
                        page.refresh_from_project()
                        apply_i18n(page)
                except Exception:
                    pass
            self._refresh_summary()
            apply_i18n(self)
        except Exception:
            pass

    # --------------------------- acciones ---------------------------
    def _open_noise_module(self):
        try:
            if hasattr(self.page_noise, "refresh_from_project"):
                self.page_noise.refresh_from_project()
        except Exception:
            pass
        self.stack.setCurrentWidget(self.page_noise)

    def _open_energy_module(self):
        """Abre el módulo de Energía reutilizando la instancia viva si existe.

        El botón «← Inicio» del módulo de Energía vuelve al hub ocultando el
        diálogo, no destruyéndolo. Reutilizar esa misma instancia es clave para
        conservar la memoria de modelos/capas del mapa interactivo. Si aquí se
        creara una ventana nueva, las capas seguirían en QGIS pero las filas de
        modelos quedarían vacías y el selector interactivo no podría editarlas.
        """
        if self._energy_dialog_factory is None:
            QtWidgets.QMessageBox.information(
                self,
                "Energía",
                "No se ha encontrado la factoría del módulo de energía.",
            )
            return

        # 1) Si ya existe un diálogo de Energía oculto por «← Inicio»,
        # reabrirlo tal cual para no perder WT, metadatos ni referencias a capas.
        try:
            dlg = getattr(self, "_energy_dialog", None)
            if dlg is not None:
                # Tocar un atributo Qt barato detecta wrappers C++ ya destruidos.
                _ = dlg.objectName()
                try:
                    if hasattr(dlg, "_refresh_project_state"):
                        dlg._refresh_project_state()
                except Exception:
                    pass
                self.hide()
                dlg.show()
                try:
                    dlg.raise_()
                    dlg.activateWindow()
                except Exception:
                    pass
                return
        except RuntimeError:
            # La instancia Python apuntaba a un QWidget destruido: crear una nueva.
            self._energy_dialog = None
        except Exception:
            # Ante cualquier estado raro, crear una nueva sin bloquear al usuario.
            self._energy_dialog = None

        # 2) Primera apertura real: crear el diálogo.
        try:
            dlg = self._energy_dialog_factory(self)
            self._energy_dialog = dlg
            try:
                dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            except Exception:
                pass
            dlg.finished.connect(self._on_energy_closed)
            self.hide()
            dlg.show()
            try:
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Energía", f"No se pudo abrir el módulo de energía.\n\n{e}")

    def _on_energy_closed(self, *_args):
        self._energy_dialog = None
        self._refresh_summary()
        self.show()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    # --------------------------- resumen ---------------------------
    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._refresh_summary()

    def _refresh_summary(self):
        try:
            prj = QgsProject.instance()
            base_name = (prj.baseName() or _tr("Proyecto sin nombre")).strip() or _tr("Proyecto sin nombre")
            self.lbl_project.setText(base_name)
            try:
                self.lbl_crs.setText(prj.crs().authid() or _tr("CRS no disponible"))
            except Exception:
                self.lbl_crs.setText(_tr("CRS no disponible"))

            n_layers, n_turbs = self._count_layout_layers_and_turbines(prj)
            if n_layers <= 0:
                self.lbl_layout.setText(_tr("Sin capas de coordenadas generadas todavía"))
            else:
                self.lbl_layout.setText(_tr(f"{n_layers} capa(s) de modelo · {n_turbs} turbina(s)"))

            wrg = (self._qsettings.value("last_wrg_path", "", type=str) or "").strip()
            wasp = (self._qsettings.value("last_wasp_dir", "", type=str) or "").strip()
            if wrg:
                self.lbl_resource.setText(f"WRG: {os.path.basename(wrg)}")
            elif wasp:
                self.lbl_resource.setText(f"WAsP grids: {wasp}")
            else:
                self.lbl_resource.setText(_tr("Sin recurso seleccionado todavía"))

            ti = (self._qsettings.value("last_wrg_ti_path", "", type=str) or "").strip()
            if ti:
                parts = [os.path.basename(p.strip()) for p in ti.split(";") if p.strip()]
                self.lbl_ti.setText(", ".join(parts[:3]) + (" …" if len(parts) > 3 else ""))
            else:
                self.lbl_ti.setText(_tr("No seleccionado (fallback previsto a TI=10% en flujo WRG)"))
        except Exception:
            pass

    def _count_layout_layers_and_turbines(self, prj: QgsProject):
        n_layers = 0
        n_turbines = 0
        try:
            root = prj.layerTreeRoot()
            group = None
            for child in root.children():
                if getattr(child, 'name', lambda: None)() == _GROUP_NAME:
                    group = child
                    break
            if group is not None:
                for child in group.children():
                    try:
                        lyr = child.layer()
                    except Exception:
                        lyr = None
                    if isinstance(lyr, QgsVectorLayer) and QgsWkbTypes.geometryType(lyr.wkbType()) == QgsWkbTypes.PointGeometry:
                        n_layers += 1
                        try:
                            n_turbines += int(lyr.featureCount())
                        except Exception:
                            pass
                return n_layers, n_turbines
        except Exception:
            pass

        # fallback: escanear proyecto entero si el grupo no existe
        for lyr in prj.mapLayers().values():
            try:
                if isinstance(lyr, QgsVectorLayer) and QgsWkbTypes.geometryType(lyr.wkbType()) == QgsWkbTypes.PointGeometry and lyr.name().endswith("(CSV)"):
                    n_layers += 1
                    n_turbines += int(lyr.featureCount())
            except Exception:
                continue
        return n_layers, n_turbines
