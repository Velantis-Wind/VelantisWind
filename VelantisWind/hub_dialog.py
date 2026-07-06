# -*- coding: utf-8 -*-
"""
Hub principal del plugin Velantis Wind.

Objetivos:
- Mantener la interfaz nueva del hub: título centrado, selector de idioma, tarjetas de módulo, logo central, bloque de optimización, resumen y botón de apoyo inferior.
- Pantalla inicial estable con tres módulos: Energía, Ruido y Sombras/parpadeo.
- Conectar inmediatamente con el módulo de Energía ya existente.
- Mantener la misma estructura visual al cambiar entre ES/EN/FR/DE: solo cambia el texto, nunca se reconstruye la página.
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
from .i18n import SUPPORTED_LANGUAGES, language_label
from .support_dialog import show_support_dialog
from .ui_core.responsive import fit_to_screen, configure_scroll_area

_GROUP_NAME = "AEP · Coordenadas por modelo"
_CONTACT_EMAIL = "info@velantiswind.com"
_WHITE_PAPER_URL = "https://www.velantiswind.com/"


def _ml(es: str, en: str = None, fr: str = None, de: str = None) -> str:
    """Return a deterministic four-language hub string, including dynamic labels."""
    lang = str(current_language() or "es").lower().replace("-", "_").split("_", 1)[0]
    if lang == "en" and en is not None:
        return en
    if lang == "fr" and fr is not None:
        return fr
    if lang == "de" and de is not None:
        return de
    return _tr(es)


class _ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event):  # type: ignore[override]
        try:
            if event.button() == QtCore.Qt.LeftButton:
                self.clicked.emit()
        finally:
            super().mousePressEvent(event)


class VelantisHubDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, energy_dialog_factory: Optional[Callable[[QtWidgets.QWidget], QtWidgets.QDialog]] = None, iface=None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self.setWindowTitle(_tr("Velantis Wind · Hub principal"))
        self._fit_to_screen()
        self._energy_dialog_factory = energy_dialog_factory
        self.iface = iface
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
        self.page_noise = NoisePage(self, on_back=self._go_home)
        self.page_flicker = ShadowPage(self, on_back=self._go_home)
        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_noise)
        self.stack.addWidget(self.page_flicker)
        self.stack.setCurrentWidget(self.page_home)

    def _build_home_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("velantisNewHubHome")
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

        self.hub_title = QtWidgets.QLabel("Velantis Wind")
        self.hub_title.setObjectName("hubTitle")
        self.hub_title.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(self.hub_title)

        self.lbl_hub_subtitle = QtWidgets.QLabel(_tr(
            "Selecciona el módulo de trabajo. Los módulos están operativos: "
            "Energía (AEP y wakes), Ruido y Sombras y parpadeo."
        ))
        self.lbl_hub_subtitle.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_hub_subtitle.setWordWrap(True)
        self.lbl_hub_subtitle.setObjectName("hubSubtitle")
        v.addWidget(self.lbl_hub_subtitle)

        # Selector de idioma global del plugin
        self.lang_box = QtWidgets.QGroupBox(_tr("Idioma"), self)
        lang_lay = QtWidgets.QHBoxLayout(self.lang_box)
        lang_lay.setContentsMargins(10, 6, 10, 6)
        lang_lay.setSpacing(8)
        self.lbl_language_caption = QtWidgets.QLabel(_tr("Idioma del plugin:"), self)
        lang_lay.addWidget(self.lbl_language_caption)
        self.cb_language = QtWidgets.QComboBox(self)
        self.cb_language.setObjectName("languageSelector")
        for _code in SUPPORTED_LANGUAGES:
            self.cb_language.addItem(language_label(_code), _code)
        idx_lang = self.cb_language.findData(current_language())
        self.cb_language.setCurrentIndex(idx_lang if idx_lang >= 0 else 0)
        self.cb_language.currentIndexChanged.connect(self._on_language_changed)
        lang_lay.addWidget(self.cb_language, 0)
        self.lbl_language_note = QtWidgets.QLabel(_tr("El idioma seleccionado se aplicará al hub, módulos, avisos y resúmenes generados."))
        self.lbl_language_note.setObjectName("hubMinor")
        self.lbl_language_note.setWordWrap(True)
        lang_lay.addWidget(self.lbl_language_note, 1)
        v.addWidget(self.lang_box)

        # New hub layout: compact module cards above the central logo.
        # Keep this geometry fixed so the UI does not jump between languages.
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

        optimization_wrap = QtWidgets.QFrame(self)
        optimization_wrap.setObjectName("layoutOptimizationWrap")
        optimization_wrap.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        optimization_lay = QtWidgets.QVBoxLayout(optimization_wrap)
        optimization_lay.setContentsMargins(14, 10, 14, 10)
        optimization_lay.setSpacing(8)

        optimization_row = QtWidgets.QHBoxLayout()
        optimization_row.setContentsMargins(0, 0, 0, 0)
        optimization_row.setSpacing(8)
        self.lbl_layout_optimization_hint = QtWidgets.QLabel(_ml(
            "Optimización avanzada de layout y wake steering para capturar más energía",
            "Advanced layout and wake-steering optimization to capture more energy",
            "Optimisation avancée de l’implantation et du pilotage des sillages pour capter plus d’énergie",
            "Erweiterte Layout- und Wake-Steering-Optimierung für mehr Energieertrag",
        ), self)
        self.lbl_layout_optimization_hint.setObjectName("layoutOptimizationHint")
        self.lbl_layout_optimization_hint.setWordWrap(True)
        self.lbl_layout_optimization_hint.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        optimization_row.addWidget(self.lbl_layout_optimization_hint, 1, QtCore.Qt.AlignVCenter)

        self.btn_layout_optimization_info = QtWidgets.QPushButton(_ml(
            "⚡ Optimizar layout",
            "⚡ Optimize layout",
            "⚡ Optimiser l’implantation",
            "⚡ Layout optimieren",
        ), self)
        self.btn_layout_optimization_info.setObjectName("layoutOptimizationCtaButton")
        self.btn_layout_optimization_info.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_layout_optimization_info.setToolTip(_ml(
            "Ver propuesta comercial, contacto y white paper de optimización.",
            "View the commercial proposal, contact details and optimization white paper.",
            "Voir la proposition commerciale, le contact et le livre blanc d’optimisation.",
            "Kommerzielle Kurzinfo, Kontakt und Optimierungs-Whitepaper anzeigen.",
        ))
        self.btn_layout_optimization_info.clicked.connect(self._toggle_layout_optimization_info)
        optimization_row.addWidget(self.btn_layout_optimization_info, 0, QtCore.Qt.AlignRight)
        optimization_lay.addLayout(optimization_row)

        self.layout_optimization_panel = QtWidgets.QFrame(self)
        self.layout_optimization_panel.setObjectName("layoutOptimizationPanel")
        panel_lay = QtWidgets.QVBoxLayout(self.layout_optimization_panel)
        panel_lay.setContentsMargins(12, 10, 12, 10)
        panel_lay.setSpacing(7)

        self.lbl_layout_optimization_title = QtWidgets.QLabel(_ml(
            "Motor avanzado de layout + wake steering",
            "Advanced layout + wake steering engine",
            "Moteur avancé implantation + pilotage des sillages",
            "Erweiterter Motor für Layout + Wake Steering",
        ), self)
        self.lbl_layout_optimization_title.setObjectName("layoutOptimizationTitle")
        self.lbl_layout_optimization_title.setWordWrap(True)
        panel_lay.addWidget(self.lbl_layout_optimization_title)

        self.lbl_layout_optimization_text = QtWidgets.QLabel(
            _ml(
                "VelantisWind permite explorar layouts desde recurso, restricciones y objetivos del proyecto, y cooptimizar el wake steering junto al layout para reducir pérdidas por estela, elevar la producción neta y mejorar el retorno del activo. Pensado para comparar alternativas defendibles y acelerar decisiones de diseño.",
                "VelantisWind can explore layouts from wind resource, constraints and project targets, and co-optimize wake steering together with the layout to reduce wake losses, lift net production and improve asset returns. Built to compare defensible alternatives and speed up design decisions.",
                "VelantisWind permet d’explorer des implantations à partir de la ressource éolienne, des contraintes et des objectifs du projet, et de cooptimiser le pilotage des sillages avec l’implantation afin de réduire les pertes de sillage, augmenter la production nette et améliorer le rendement de l’actif. Conçu pour comparer des variantes défendables et accélérer les décisions de conception.",
                "VelantisWind kann Layouts aus Windressource, Einschränkungen und Projektzielen entwickeln und Wake Steering gemeinsam mit dem Layout co-optimieren, um Nachlaufverluste zu reduzieren, die Nettoproduktion zu erhöhen und die Rendite des Assets zu verbessern. Entwickelt, um belastbare Alternativen zu vergleichen und Designentscheidungen zu beschleunigen.",
            ),
            self,
        )
        self.lbl_layout_optimization_text.setObjectName("layoutOptimizationText")
        self.lbl_layout_optimization_text.setWordWrap(True)
        panel_lay.addWidget(self.lbl_layout_optimization_text)

        self.lbl_layout_optimization_contact = QtWidgets.QLabel(
            _ml(
                "Solicita una revisión del caso: info@velantiswind.com · White paper en velantiswind.com",
                "Request a case review: info@velantiswind.com · White paper at velantiswind.com",
                "Demander une revue du cas : info@velantiswind.com · Livre blanc sur velantiswind.com",
                "Fallprüfung anfragen: info@velantiswind.com · Whitepaper auf velantiswind.com",
            ),
            self,
        )
        self.lbl_layout_optimization_contact.setObjectName("layoutOptimizationContact")
        self.lbl_layout_optimization_contact.setWordWrap(True)
        panel_lay.addWidget(self.lbl_layout_optimization_contact)

        panel_buttons = QtWidgets.QHBoxLayout()
        panel_buttons.setContentsMargins(0, 0, 0, 0)
        panel_buttons.setSpacing(8)
        panel_buttons.addStretch(1)

        self.btn_copy_optimization_contact = QtWidgets.QPushButton(_tr("Copiar contacto"), self)
        self.btn_copy_optimization_contact.setObjectName("layoutOptimizationSecondaryButton")
        self.btn_copy_optimization_contact.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_copy_optimization_contact.setToolTip(_tr("Copia el email de contacto al portapapeles."))
        self.btn_copy_optimization_contact.clicked.connect(self._copy_optimization_contact)
        panel_buttons.addWidget(self.btn_copy_optimization_contact)

        self.btn_open_white_paper = QtWidgets.QPushButton(_tr("Ver white paper"), self)
        self.btn_open_white_paper.setObjectName("layoutOptimizationPrimaryButton")
        self.btn_open_white_paper.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_open_white_paper.setToolTip(_tr("Abre la web de VelantisWind, donde está disponible el white paper."))
        self.btn_open_white_paper.clicked.connect(self._open_white_paper)
        panel_buttons.addWidget(self.btn_open_white_paper)
        panel_lay.addLayout(panel_buttons)

        self.layout_optimization_panel.setVisible(False)
        optimization_lay.addWidget(self.layout_optimization_panel)


        logo_wrap = QtWidgets.QWidget(self)
        logo_lay = QtWidgets.QVBoxLayout(logo_wrap)
        logo_lay.setContentsMargins(0, 2, 0, 2)
        logo_lay.setSpacing(4)

        self.logo_label = _ClickableLabel(self)
        self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
        self.logo_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.logo_label.setToolTip(_tr("Inicio"))
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
        self.logo_label.clicked.connect(self._go_home)
        logo_lay.addWidget(self.logo_label, 0, QtCore.Qt.AlignCenter)

        self.lbl_logo_info = QtWidgets.QLabel(_tr("Pulsa el logo para volver al inicio desde los módulos preparados."))
        self.lbl_logo_info.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_logo_info.setObjectName("hubMinor")
        self.lbl_logo_info.setWordWrap(True)
        logo_lay.addWidget(self.lbl_logo_info)
        v.addWidget(logo_wrap, 0)

        # Keep the optimization entry visible but not intrusive: it sits close to
        # the project context, just before the project summary.
        v.addWidget(optimization_wrap)

        self.grp_summary = QtWidgets.QGroupBox(_tr("Resumen del proyecto"))
        form = QtWidgets.QFormLayout(self.grp_summary)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(5)
        self.lbl_project = QtWidgets.QLabel("-")
        self.lbl_crs = QtWidgets.QLabel("-")
        self.lbl_layout = QtWidgets.QLabel("-")
        self.lbl_resource = QtWidgets.QLabel("-")
        self.lbl_ti = QtWidgets.QLabel("-")
        self.lbl_status = QtWidgets.QLabel(_tr("Energía: operativa · Ruido: operativo · Sombras: operativo"))
        for w in [self.lbl_project, self.lbl_crs, self.lbl_layout, self.lbl_resource, self.lbl_ti, self.lbl_status]:
            w.setWordWrap(True)
        self.lbl_project_caption = QtWidgets.QLabel(_tr("Proyecto:"), self)
        self.lbl_crs_caption = QtWidgets.QLabel(_tr("CRS:"), self)
        self.lbl_layout_caption = QtWidgets.QLabel(_tr("Layout activo:"), self)
        self.lbl_resource_caption = QtWidgets.QLabel(_tr("Recurso:"), self)
        self.lbl_ti_caption = QtWidgets.QLabel(_tr("TI WRG:"), self)
        self.lbl_status_caption = QtWidgets.QLabel(_tr("Estado módulos:"), self)
        form.addRow(self.lbl_project_caption, self.lbl_project)
        form.addRow(self.lbl_crs_caption, self.lbl_crs)
        form.addRow(self.lbl_layout_caption, self.lbl_layout)
        form.addRow(self.lbl_resource_caption, self.lbl_resource)
        form.addRow(self.lbl_ti_caption, self.lbl_ti)
        form.addRow(self.lbl_status_caption, self.lbl_status)
        v.addWidget(self.grp_summary)


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
        # Fixed card geometry keeps the hub visually stable when users switch
        # between ES/EN/FR/DE.  Only the text changes; the layout does not jump.
        btn = QtWidgets.QPushButton(text)
        btn.setMinimumSize(126, 64)
        btn.setMaximumSize(126, 82)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setObjectName("moduleCardButton")
        return btn

    def _apply_style(self):
        self.setStyleSheet(
            """
            QDialog { background: #f3f5f7; }
            QWidget#velantisNewHubHome { background: #f3f5f7; }
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
            QFrame#layoutOptimizationWrap {
                background: #ffffff;
                border: 1.2px solid #c9ddea;
                border-radius: 12px;
            }
            QLabel#layoutOptimizationHint {
                font-size: 13px;
                font-weight: 700;
                color: #103b67;
            }
            QPushButton#layoutOptimizationCtaButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #103b67, stop:1 #18a7a0);
                border: 1.5px solid #0f5f85;
                border-radius: 12px;
                color: white;
                font-size: 13px;
                font-weight: 800;
                padding: 8px 18px;
                min-height: 34px;
                min-width: 190px;
            }
            QPushButton#layoutOptimizationCtaButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d345c, stop:1 #1bbdb5);
                border-color: #18a7a0;
                color: white;
            }
            QPushButton#layoutOptimizationCtaButton:pressed {
                background: #0d345c;
            }
            QFrame#layoutOptimizationPanel {
                background: #f8fbfd;
                border: 1px solid #d4dde5;
                border-radius: 10px;
            }
            QLabel#layoutOptimizationTitle {
                font-size: 13px;
                font-weight: 800;
                color: #103b67;
            }
            QLabel#layoutOptimizationText {
                font-size: 12px;
                color: #3f4c58;
                line-height: 150%;
            }
            QLabel#layoutOptimizationContact {
                font-size: 11px;
                font-weight: 600;
                color: #103b67;
            }
            QPushButton#layoutOptimizationPrimaryButton {
                background: #103b67;
                border: 1.5px solid #103b67;
                border-radius: 9px;
                color: white;
                font-size: 11.5px;
                font-weight: 600;
                padding: 6px 12px;
                min-height: 26px;
            }
            QPushButton#layoutOptimizationPrimaryButton:hover {
                background: #1f7dc2;
                border-color: #1f7dc2;
            }
            QPushButton#layoutOptimizationSecondaryButton {
                background: #ffffff;
                border: 1px solid #b8cad8;
                border-radius: 9px;
                color: #103b67;
                font-size: 11.5px;
                font-weight: 600;
                padding: 6px 12px;
                min-height: 26px;
            }
            QPushButton#layoutOptimizationSecondaryButton:hover {
                background: #eaf3fb;
                border-color: #1f7dc2;
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

    def _apply_home_texts(self):
        """Update hub texts in place without rebuilding the widget tree.

        Rebuilding the home page on every language change made the interface
        appear to change shape and could reset scroll/state.  This method keeps
        the exact same widgets and geometry as the selected clean hub layout.
        """
        try:
            self.setWindowTitle(_tr("Velantis Wind · Hub principal"))
            self.hub_title.setText("Velantis Wind")
            self.lbl_hub_subtitle.setText(_tr("Selecciona el módulo de trabajo. Los módulos están operativos: Energía (AEP y wakes), Ruido y Sombras y parpadeo."))
            self.lang_box.setTitle(_tr("Idioma"))
            self.lbl_language_caption.setText(_tr("Idioma del plugin:"))
            self.lbl_language_note.setText(_tr("El idioma seleccionado se aplicará al hub, módulos, avisos y resúmenes generados."))
            self.btn_energy.setText(_tr("Energía\nAEP y wakes"))
            self.btn_noise.setText(_tr("Ruido"))
            self.btn_flicker.setText(_tr("Sombras y\nparpadeo"))
            self.logo_label.setToolTip(_tr("Inicio"))
            self.lbl_logo_info.setText(_tr("Pulsa el logo para volver al inicio desde los módulos preparados."))
            self.lbl_layout_optimization_hint.setText(_ml(
                "Optimización avanzada de layout y wake steering para capturar más energía",
                "Advanced layout and wake-steering optimization to capture more energy",
                "Optimisation avancée de l’implantation et du pilotage des sillages pour capter plus d’énergie",
                "Erweiterte Layout- und Wake-Steering-Optimierung für mehr Energieertrag",
            ))
            is_open = bool(getattr(self, "layout_optimization_panel", None) and self.layout_optimization_panel.isVisible())
            self.btn_layout_optimization_info.setText(
                _ml("Ocultar información", "Hide information", "Masquer les informations", "Informationen ausblenden")
                if is_open else
                _ml("⚡ Optimizar layout", "⚡ Optimize layout", "⚡ Optimiser l’implantation", "⚡ Layout optimieren")
            )
            self.btn_layout_optimization_info.setToolTip(_ml(
            "Ver propuesta comercial, contacto y white paper de optimización.",
            "View the commercial proposal, contact details and optimization white paper.",
            "Voir la proposition commerciale, le contact et le livre blanc d’optimisation.",
            "Kommerzielle Kurzinfo, Kontakt und Optimierungs-Whitepaper anzeigen.",
        ))
            self.lbl_layout_optimization_title.setText(_ml(
                "Motor avanzado de layout + wake steering",
                "Advanced layout + wake steering engine",
                "Moteur avancé implantation + pilotage des sillages",
                "Erweiterter Motor für Layout + Wake Steering",
            ))
            self.lbl_layout_optimization_text.setText(_ml(
                "VelantisWind permite explorar layouts desde recurso, restricciones y objetivos del proyecto, y cooptimizar el wake steering junto al layout para reducir pérdidas por estela, elevar la producción neta y mejorar el retorno del activo. Pensado para comparar alternativas defendibles y acelerar decisiones de diseño.",
                "VelantisWind can explore layouts from wind resource, constraints and project targets, and co-optimize wake steering together with the layout to reduce wake losses, lift net production and improve asset returns. Built to compare defensible alternatives and speed up design decisions.",
                "VelantisWind permet d’explorer des implantations à partir de la ressource éolienne, des contraintes et des objectifs du projet, et de cooptimiser le pilotage des sillages avec l’implantation afin de réduire les pertes de sillage, augmenter la production nette et améliorer le rendement de l’actif. Conçu pour comparer des variantes défendables et accélérer les décisions de conception.",
                "VelantisWind kann Layouts aus Windressource, Einschränkungen und Projektzielen entwickeln und Wake Steering gemeinsam mit dem Layout co-optimieren, um Nachlaufverluste zu reduzieren, die Nettoproduktion zu erhöhen und die Rendite des Assets zu verbessern. Entwickelt, um belastbare Alternativen zu vergleichen und Designentscheidungen zu beschleunigen.",
            ))
            self.lbl_layout_optimization_contact.setText(_ml(
                "Solicita una revisión del caso: info@velantiswind.com · White paper en velantiswind.com",
                "Request a case review: info@velantiswind.com · White paper at velantiswind.com",
                "Demander une revue du cas : info@velantiswind.com · Livre blanc sur velantiswind.com",
                "Fallprüfung anfragen: info@velantiswind.com · Whitepaper auf velantiswind.com",
            ))
            self.btn_copy_optimization_contact.setText(_tr("Copiar contacto"))
            self.btn_copy_optimization_contact.setToolTip(_tr("Copia el email de contacto al portapapeles."))
            self.btn_open_white_paper.setText(_tr("Ver white paper"))
            self.btn_open_white_paper.setToolTip(_tr("Abre la web de VelantisWind, donde está disponible el white paper."))
            self.grp_summary.setTitle(_tr("Resumen del proyecto"))
            self.lbl_project_caption.setText(_tr("Proyecto:"))
            self.lbl_crs_caption.setText(_tr("CRS:"))
            self.lbl_layout_caption.setText(_tr("Layout activo:"))
            self.lbl_resource_caption.setText(_tr("Recurso:"))
            self.lbl_ti_caption.setText(_tr("TI WRG:"))
            self.lbl_status_caption.setText(_tr("Estado módulos:"))
            self.lbl_status.setText(_tr("Energía: operativa · Ruido: operativo · Sombras: operativo"))
            self.btn_support_velantis.setText(_tr("♡ Apoyar VelantisWind"))
            self.btn_support_velantis.setToolTip(_tr("Apoya el mantenimiento, la documentación, las pruebas y el desarrollo open source futuro."))
        except Exception:
            pass

    def _toggle_layout_optimization_info(self):
        try:
            visible = not self.layout_optimization_panel.isVisible()
            self.layout_optimization_panel.setVisible(visible)
            self.btn_layout_optimization_info.setText(
                _ml("Ocultar información", "Hide information", "Masquer les informations", "Informationen ausblenden")
                if visible else
                _ml("⚡ Optimizar layout", "⚡ Optimize layout", "⚡ Optimiser l’implantation", "⚡ Layout optimieren")
            )
        except Exception:
            pass

    def _copy_optimization_contact(self):
        try:
            cb = QtWidgets.QApplication.clipboard()
            cb.setText(_CONTACT_EMAIL)
            QtWidgets.QMessageBox.information(
                self,
                _tr("Optimización de layout"),
                _tr("Email copiado al portapapeles:") + f"\n{_CONTACT_EMAIL}",
            )
        except Exception:
            QtWidgets.QMessageBox.information(
                self,
                _tr("Optimización de layout"),
                _tr("Puedes contactar en:") + f"\n{_CONTACT_EMAIL}",
            )

    def _open_white_paper(self):
        try:
            opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl(_WHITE_PAPER_URL))
        except Exception:
            opened = False
        if not opened:
            QtWidgets.QMessageBox.information(
                self,
                _tr("Ver white paper técnico"),
                _WHITE_PAPER_URL,
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

            # Keep the same UI structure; update texts in place only.
            self._apply_home_texts()

            for page in (getattr(self, "page_noise", None), getattr(self, "page_flicker", None)):
                try:
                    apply_i18n(page)
                    if hasattr(page, "refresh_from_project"):
                        page.refresh_from_project()
                        apply_i18n(page)
                except Exception:
                    pass
            self._refresh_summary()
            self._sync_language_selector()
        except Exception:
            pass

    def _sync_language_selector(self):
        try:
            cb = getattr(self, "cb_language", None)
            if cb is None:
                return
            try:
                cb.blockSignals(True)
            except Exception:
                pass
            for i, code in enumerate(SUPPORTED_LANGUAGES):
                try:
                    cb.setItemText(i, language_label(code))
                    cb.setItemData(i, code)
                except Exception:
                    pass
            idx_lang = cb.findData(current_language())
            cb.setCurrentIndex(idx_lang if idx_lang >= 0 else 0)
        finally:
            try:
                cb.blockSignals(False)
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

    def _go_home(self):
        """Return to the hub home page."""
        self.stack.setCurrentWidget(self.page_home)

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
                _tr("Energía"),
                _tr("No se ha encontrado la factoría del módulo de energía."),
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
            QtWidgets.QMessageBox.critical(
                self,
                _tr("Energía"),
                _tr("No se pudo abrir el módulo de energía.") + f"\n\n{e}",
            )

    def _on_energy_closed(self, *_args):
        self._energy_dialog = None
        self._refresh_summary()
        self.show()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def keyPressEvent(self, event):  # type: ignore[override]
        super().keyPressEvent(event)

    def closeEvent(self, event):  # type: ignore[override]
        super().closeEvent(event)

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
                self.lbl_layout.setText(_ml(
                    f"{n_layers} capa(s) de modelo · {n_turbs} turbina(s)",
                    f"{n_layers} model layer(s) · {n_turbs} turbine(s)",
                    f"{n_layers} couche(s) de modèle · {n_turbs} éolienne(s)",
                    f"{n_layers} Modell-Layer · {n_turbs} Windturbine(n)",
                ))

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
