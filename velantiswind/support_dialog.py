# -*- coding: utf-8 -*-
"""
VelantisWind - Support / sponsorship dialog.

Small non-invasive dialog opened only from the Hub/About area.
It keeps sponsorship, professional support, academic collaboration and custom
workflow adaptation clearly separated from the open-source plugin functionality.
"""
from __future__ import annotations

from qgis.PyQt import QtCore, QtGui, QtWidgets

from .i18n import current_language


# -----------------------------------------------------------------------------
# Public links. Keep them here so they are easy to update before release.
# Contact uses mailto only; donation/support information is hosted in GitHub docs.
# -----------------------------------------------------------------------------
GITHUB_PROJECT_URL = "https://github.com/Velantis-Wind/VelantisWind"
SPONSOR_URL = "https://github.com/Velantis-Wind/VelantisWind/blob/main/SUPPORT.md"
SUPPORTERS_URL = "https://github.com/Velantis-Wind/VelantisWind/blob/main/SUPPORTERS.md"
SUPPORT_DOC_URL = "https://github.com/Velantis-Wind/VelantisWind/blob/main/SUPPORT.md"
CONTACT_EMAIL = "info@velantiswind.com"
CONTACT_URL = f"mailto:{CONTACT_EMAIL}?subject=VelantisWind%20support"


_TEXTS = {
    "es": {
        "title": "Apoyar VelantisWind",
        "hero": "Flujos de trabajo eólicos open source, directamente dentro de QGIS.",
        "subtitle": (
            "VelantisWind es un plugin gratuito y open source para QGIS orientado al análisis preliminar "
            "de parques eólicos, validación técnica y tareas GIS de preevaluación. Tu apoyo ayuda a convertirlo "
            "en una herramienta más robusta, documentada y validada para flujos de trabajo reales."
        ),
        "why_title": "¿Qué ayuda a financiar el apoyo?",
        "why_items": [
            "Mantenimiento del plugin, estabilidad y compatibilidad con QGIS.",
            "Documentación, tutoriales, ejemplos y traducciones.",
            "Validación con casos reales de parques eólicos.",
            "Mejoras en los módulos de AEP, estelas, ruido y sombras.",
            "Soporte para beta testers, early adopters y partners técnicos.",
            "Nuevas funcionalidades solicitadas por usuarios, consultoras, universidades y partners.",
        ],
        "company_title": "Validación y apoyo de la comunidad",
        "company_text": (
            "El apoyo de usuarios, consultoras, universidades y beta testers ayuda a mejorar la documentación, "
            "la estabilidad, la validación con casos reales y las funcionalidades futuras del proyecto open source."
        ),
        "academic_title": "Colaboración académica e investigación",
        "academic_text": (
            "VelantisWind está abierto a universidades y grupos de investigación. TFG, TFM o trabajos aplicados pueden "
            "ayudar a validar, documentar o ampliar el plugin con nuevos módulos, siempre que estén técnicamente alineados "
            "con el proyecto open source."
        ),
        "tiers_title": "Opciones de apoyo",
        "tiers": [
            ("Open Supporter", "desde 1 €", "Apoyo puntual con reconocimiento opcional."),
            ("Project Supporter", "25 €", "Nombre opcional en la lista de supporters."),
            ("Professional Backer", "100 €", "Nombre y enlace opcional."),
            ("Organization Backer", "500 €", "Logo pequeño o mención de organización."),
            ("Major Backer", "2.500 €", "Reconocimiento destacado y conversación técnica opcional."),
            ("Community Sponsor", "5 €/mes", "Nombre opcional en la lista de supporters."),
            ("Professional Sponsor", "25 €/mes", "Nombre y enlace opcional."),
            ("Workflow Sponsor", "100 €/mes", "Logo pequeño o mención de organización."),
            ("Validation Sponsor", "250 €/mes", "Logo y mención como sponsor de validación."),
            ("Partner Sponsor", "500 €/mes", "Logo destacado en GitHub, documentación o sección About/Sponsors."),
        ],
        "partnerships_title": "Otras formas de colaborar",
        "partnerships": [
            "Beta testing y feedback técnico.",
            "Validación frente a proyectos reales o workflows internos.",
            "Contribuciones técnicas, documentación o ejemplos.",
            "Casos de uso, ejemplos de validación y feedback de documentación.",
            "Colaboración académica mediante TFG/TFM, investigación aplicada o material docente.",
        ],
        "disclaimer": (
            "VelantisWind seguirá siendo gratuito y open source. El apoyo es opcional y no implica propiedad, exclusividad "
            "ni control sobre el roadmap. El reconocimiento público es opcional y puede omitirse si el supporter desea permanecer anónimo. "
            f"Contacto: {CONTACT_EMAIL}"
        ),
        "btn_sponsor": "Patrocinar / donar",
        "btn_support": CONTACT_EMAIL,
                "btn_support_doc": "Ver SUPPORT.md",
        "btn_supporters": "Supporters",
        "btn_close": "Cerrar",
    },
    "en": {
        "title": "Support VelantisWind",
        "hero": "Open-source wind energy workflows, directly inside QGIS.",
        "subtitle": (
            "VelantisWind is a free and open-source QGIS plugin for early-stage wind farm analysis, "
            "validation workflows and geospatial pre-assessment tasks. Your support helps transform it "
            "into a more robust, documented and validated tool for practical wind energy workflows."
        ),
        "why_title": "What does your support help fund?",
        "why_items": [
            "Plugin maintenance, stability and QGIS compatibility.",
            "Documentation, tutorials, examples and translations.",
            "Validation with real wind farm cases.",
            "Improvements in the AEP, wake, noise and shadow flicker modules.",
            "Support for beta testers, early adopters and technical partners.",
            "New features requested by users, consultants, universities and technical partners.",
        ],
        "company_title": "Validation and community support",
        "company_text": (
            "Support from users, consultants, universities and beta testers helps improve documentation, "
            "stability, validation with real cases and future open-source functionality."
        ),
        "academic_title": "Academic and research collaboration",
        "academic_text": (
            "VelantisWind is open to universities and research groups. Bachelor’s and Master’s thesis projects "
            "or applied research can help validate, document or extend the plugin with new modules when technically "
            "aligned with the open-source project."
        ),
        "tiers_title": "Support options",
        "tiers": [
            ("Open Supporter", "from €1", "One-time support with optional acknowledgement."),
            ("Project Supporter", "€25", "Optional name in the supporters list."),
            ("Professional Backer", "€100", "Name and optional link."),
            ("Organization Backer", "€500", "Small logo or organization mention."),
            ("Major Backer", "€2,500", "Featured recognition and optional technical discussion."),
            ("Community Sponsor", "€5/month", "Optional name in the supporters list."),
            ("Professional Sponsor", "€25/month", "Name and optional link."),
            ("Workflow Sponsor", "€100/month", "Small logo or organization mention."),
            ("Validation Sponsor", "€250/month", "Logo recognition and validation sponsor mention."),
            ("Partner Sponsor", "€500/month", "Featured logo in GitHub, documentation or About/Sponsors section."),
        ],
        "partnerships_title": "Other collaboration paths",
        "partnerships": [
            "Beta testing and technical feedback.",
            "Validation against real projects or internal workflows.",
            "Technical contributions, documentation or examples.",
            "Use cases, validation examples and documentation feedback.",
            "Academic collaboration through thesis projects, applied research or teaching material.",
        ],
        "disclaimer": (
            "VelantisWind will remain free and open source. Sponsorship is optional and does not imply ownership, exclusivity "
            "or control over the roadmap. Public recognition is optional and may be omitted if the supporter prefers to remain anonymous. "
            f"Contact: {CONTACT_EMAIL}"
        ),
        "btn_sponsor": "Sponsor / donate",
        "btn_support": CONTACT_EMAIL,
                "btn_support_doc": "View SUPPORT.md",
        "btn_supporters": "Supporters",
        "btn_close": "Close",
    },
}


def _lang() -> str:
    try:
        lang = current_language()
    except Exception:
        lang = "es"
    return "en" if str(lang).lower().startswith("en") else "es"


def _open_url(url: str) -> None:
    try:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
    except Exception:
        pass


class SupportDialog(QtWidgets.QDialog):
    """Bilingual sponsorship/support dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texts = _TEXTS[_lang()]
        self.setWindowTitle(self._texts["title"])
        self.setModal(True)
        self.setMinimumWidth(720)
        self.resize(820, 720)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self) -> None:
        t = self._texts
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("supportScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        content = QtWidgets.QWidget(scroll)
        content.setObjectName("supportContent")
        scroll.setWidget(content)

        root = QtWidgets.QVBoxLayout(content)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(12)

        hero_box = QtWidgets.QFrame(content)
        hero_box.setObjectName("supportHeroBox")
        hero_layout = QtWidgets.QVBoxLayout(hero_box)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(8)

        title = QtWidgets.QLabel(t["title"], hero_box)
        title.setObjectName("supportTitle")
        title.setWordWrap(True)
        hero_layout.addWidget(title)

        hero = QtWidgets.QLabel(t["hero"], hero_box)
        hero.setObjectName("supportHero")
        hero.setWordWrap(True)
        hero_layout.addWidget(hero)

        subtitle = QtWidgets.QLabel(t["subtitle"], hero_box)
        subtitle.setObjectName("supportSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)

        root.addWidget(hero_box)

        two_cols = QtWidgets.QHBoxLayout()
        two_cols.setSpacing(12)
        two_cols.addWidget(self._info_card(t["why_title"], self._bullets_html(t["why_items"])), 1)
        two_cols.addWidget(self._info_card(t["company_title"], t["company_text"]), 1)
        root.addLayout(two_cols)

        root.addWidget(self._info_card(t["academic_title"], t["academic_text"]))

        tiers_title = QtWidgets.QLabel(t["tiers_title"], content)
        tiers_title.setObjectName("supportTiersTitle")
        root.addWidget(tiers_title)

        for name, amount, description in t["tiers"]:
            root.addWidget(self._tier_row(name, amount, description))

        root.addWidget(self._info_card(t["partnerships_title"], self._bullets_html(t["partnerships"])))

        disclaimer = QtWidgets.QLabel(t["disclaimer"], content)
        disclaimer.setObjectName("supportDisclaimer")
        disclaimer.setWordWrap(True)
        root.addWidget(disclaimer)

        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)

        btn_sponsor = QtWidgets.QPushButton(t["btn_sponsor"], self)
        btn_sponsor.setObjectName("primarySupportButton")
        btn_sponsor.clicked.connect(lambda: _open_url(SPONSOR_URL))
        button_row.addWidget(btn_sponsor)

        btn_support = QtWidgets.QPushButton(t["btn_support"], self)
        btn_support.clicked.connect(lambda: _open_url(CONTACT_URL))
        button_row.addWidget(btn_support)

        btn_doc = QtWidgets.QPushButton(t["btn_support_doc"], self)
        btn_doc.clicked.connect(lambda: _open_url(SUPPORT_DOC_URL))
        button_row.addWidget(btn_doc)

        btn_supporters = QtWidgets.QPushButton(t["btn_supporters"], self)
        btn_supporters.clicked.connect(lambda: _open_url(SUPPORTERS_URL))
        button_row.addWidget(btn_supporters)

        button_row.addStretch(1)

        btn_close = QtWidgets.QPushButton(t["btn_close"], self)
        btn_close.clicked.connect(self.close)
        button_row.addWidget(btn_close)

        outer.addLayout(button_row)
        self._apply_style()

    def _bullets_html(self, items: list[str]) -> str:
        lis = "".join(f"<li>{item}</li>" for item in items)
        return f"<ul>{lis}</ul>"

    def _info_card(self, title: str, html_text: str) -> QtWidgets.QFrame:
        box = QtWidgets.QFrame(self)
        box.setObjectName("supportInfoCard")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_label = QtWidgets.QLabel(title, box)
        title_label.setObjectName("supportInfoTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        body = QtWidgets.QLabel(html_text, box)
        body.setObjectName("supportInfoBody")
        body.setWordWrap(True)
        body.setTextFormat(QtCore.Qt.RichText)
        body.setOpenExternalLinks(False)
        layout.addWidget(body)
        layout.addStretch(1)
        return box

    def _tier_row(self, name: str, amount: str, description: str) -> QtWidgets.QFrame:
        box = QtWidgets.QFrame(self)
        box.setObjectName("supportTierBox")
        layout = QtWidgets.QHBoxLayout(box)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(12)

        left = QtWidgets.QLabel(f"<b>{name}</b><br><span style='color:#5f6b76'>{description}</span>", box)
        left.setWordWrap(True)
        left.setTextFormat(QtCore.Qt.RichText)
        left.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(left, 1)

        right = QtWidgets.QLabel(f"<b>{amount}</b>", box)
        right.setObjectName("supportTierAmount")
        right.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        right.setMinimumWidth(120)
        layout.addWidget(right, 0)

        return box

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #f7f9fb;
                color: #1f2d3a;
            }
            QScrollArea#supportScrollArea {
                background: #f7f9fb;
                border: none;
            }
            QWidget#supportContent {
                background: #f7f9fb;
            }
            QFrame#supportHeroBox {
                border: 1px solid #d6e3ee;
                border-radius: 14px;
                background: #ffffff;
            }
            QLabel#supportTitle {
                font-size: 22px;
                font-weight: 700;
                color: #103b67;
            }
            QLabel#supportHero {
                font-size: 14px;
                font-weight: 600;
                color: #1f7dc2;
            }
            QLabel#supportSubtitle {
                font-size: 12px;
                color: #4f5d6b;
            }
            QFrame#supportInfoCard {
                border: 1px solid #d9e0e6;
                border-radius: 11px;
                background: #ffffff;
            }
            QLabel#supportInfoTitle {
                font-size: 13px;
                font-weight: 700;
                color: #103b67;
            }
            QLabel#supportInfoBody {
                font-size: 11.5px;
                color: #4f5d6b;
            }
            QLabel#supportTiersTitle {
                font-size: 14px;
                font-weight: 700;
                color: #103b67;
                padding-top: 4px;
            }
            QLabel#supportDisclaimer {
                font-size: 10.5px;
                color: #66717c;
                padding: 4px 2px;
            }
            QFrame#supportTierBox {
                border: 1px solid #d9e0e6;
                border-radius: 9px;
                background: #ffffff;
            }
            QFrame#supportTierBox:hover {
                border-color: #1f7dc2;
                background: #f8fbfe;
            }
            QLabel#supportTierAmount {
                color: #103b67;
                font-size: 12px;
            }
            QPushButton {
                padding: 7px 11px;
                min-height: 26px;
                border: 1px solid #cbd4dc;
                border-radius: 8px;
                background: #ffffff;
                color: #103b67;
            }
            QPushButton:hover {
                background: #eaf3fb;
                border-color: #1f7dc2;
            }
            QPushButton#primarySupportButton {
                background: #103b67;
                color: #ffffff;
                border: 1px solid #103b67;
                font-weight: 600;
            }
            QPushButton#primarySupportButton:hover {
                background: #1f7dc2;
                border-color: #1f7dc2;
            }
            """
        )


def show_support_dialog(parent=None) -> None:
    dlg = SupportDialog(parent)
    dlg.exec_()
