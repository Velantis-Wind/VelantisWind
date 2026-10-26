# -*- coding: utf-8 -*-
"""
VelantisWind - Support / sponsorship dialog.

Small non-invasive dialog opened only from the Hub/About area.
It keeps sponsorship, professional support, academic collaboration and custom
workflow adaptation clearly separated from the open-source plugin functionality.
"""
from __future__ import annotations

from qgis.PyQt import QtCore, QtGui, QtWidgets

from .i18n import current_language, tr_text as _tr


# -----------------------------------------------------------------------------
# Public links. Keep them here so they are easy to update before release.
# Contact uses mailto only; donations go to the GitHub Sponsors profile of
# .github/FUNDING.yml, the support information is in SUPPORT.md and the
# supporters list in VelantisWind/SUPPORTERS.md.
# -----------------------------------------------------------------------------
GITHUB_PROJECT_URL = "https://github.com/Velantis-Wind/VelantisWind"
SPONSOR_URL = "https://github.com/sponsors/VelantisWind"
SUPPORT_DOC_URL = "https://github.com/Velantis-Wind/VelantisWind/blob/main/SUPPORT.md"
SUPPORTERS_URL = "https://github.com/Velantis-Wind/VelantisWind/blob/main/VelantisWind/SUPPORTERS.md"
CONTACT_EMAIL = "info@velantiswind.com"
CONTACT_URL = f"mailto:{CONTACT_EMAIL}?subject=VelantisWind%20support"


_TEXTS = {
    "es": {
        "title": "Apoyar VelantisWind",
        "hero": "Flujos de trabajo eólicos de código abierto, directamente dentro de QGIS.",
        "subtitle": (
            "VelantisWind es un plugin gratuito y de código abierto para QGIS orientado al análisis preliminar "
            "de parques eólicos, validación técnica y tareas SIG de preevaluación. Tu apoyo ayuda a convertirlo "
            "en una herramienta más robusta, documentada y validada para flujos de trabajo reales."
        ),
        "why_title": "¿Qué ayuda a financiar el apoyo?",
        "why_items": [
            "Mantenimiento del plugin, estabilidad y compatibilidad con QGIS.",
            "Documentación, tutoriales, ejemplos y traducciones.",
            "Validación con casos reales de parques eólicos.",
            "Mejoras en los módulos de AEP, estelas, ruido y sombras.",
            "Soporte para quienes prueban las versiones beta, los primeros usuarios y los socios técnicos.",
            "Nuevas funcionalidades solicitadas por usuarios, consultoras, universidades y socios.",
        ],
        "company_title": "Validación y apoyo de la comunidad",
        "company_text": (
            "El apoyo de usuarios, consultoras, universidades y probadores de versiones beta ayuda a mejorar la documentación, "
            "la estabilidad, la validación con casos reales y las funcionalidades futuras del proyecto de código abierto."
        ),
        "academic_title": "Colaboración académica e investigación",
        "academic_text": (
            "VelantisWind está abierto a universidades y grupos de investigación. TFG, TFM o trabajos aplicados pueden "
            "ayudar a validar, documentar o ampliar el plugin con nuevos módulos, siempre que estén técnicamente alineados "
            "con el proyecto de código abierto."
        ),
        "tiers_title": "Opciones de apoyo",
        "tiers": [
            ("Open Supporter", "desde 1 €", "Apoyo puntual con reconocimiento opcional."),
            ("Project Supporter", "25 €", "Nombre opcional en la lista de patrocinadores."),
            ("Professional Backer", "100 €", "Nombre y enlace opcional."),
            ("Organization Backer", "500 €", "Logo pequeño o mención de organización."),
            ("Major Backer", "2.500 €", "Reconocimiento destacado y conversación técnica opcional."),
            ("Community Sponsor", "5 €/mes", "Nombre opcional en la lista de patrocinadores."),
            ("Professional Sponsor", "25 €/mes", "Nombre y enlace opcional."),
            ("Workflow Sponsor", "100 €/mes", "Logo pequeño o mención de organización."),
            ("Validation Sponsor", "250 €/mes", "Logo y mención como patrocinador de validación."),
            ("Partner Sponsor", "500 €/mes", "Logo destacado en GitHub, documentación o sección About/Sponsors."),
        ],
        "partnerships_title": "Otras formas de colaborar",
        "partnerships": [
            "Pruebas de versiones beta y comentarios técnicos.",
            "Validación frente a proyectos reales o flujos de trabajo internos.",
            "Contribuciones técnicas, documentación o ejemplos.",
            "Casos de uso, ejemplos de validación y comentarios sobre la documentación.",
            "Colaboración académica mediante TFG/TFM, investigación aplicada o material docente.",
        ],
        "disclaimer": (
            "VelantisWind seguirá siendo gratuito y de código abierto. El apoyo es opcional y no implica propiedad, exclusividad "
            "ni control sobre la hoja de ruta. El reconocimiento público es opcional y puede omitirse si el patrocinador desea permanecer anónimo. "
            f"Contacto: {CONTACT_EMAIL}"
        ),
        "btn_sponsor": "Patrocinar / donar",
        "btn_support": CONTACT_EMAIL,
        "btn_support_doc": "Ver SUPPORT.md",
        "btn_project": "Documentación del proyecto",
        "btn_supporters": "Patrocinadores",
        "sponsor_tooltip": "Abre el perfil de VelantisWind en GitHub Sponsors. Las condiciones de pago se muestran en GitHub.",
        "tiers_show": "Ver niveles de apoyo",
        "tiers_hide": "Ocultar niveles de apoyo",
        "url_fallback": "No se ha podido abrir el enlace. Copia esta dirección:",
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
        "btn_project": "Project documentation",
        "btn_supporters": "Supporters",
        "sponsor_tooltip": "Opens the VelantisWind profile on GitHub Sponsors. Payment details are shown on GitHub.",
        "tiers_show": "Show support levels",
        "tiers_hide": "Hide support levels",
        "url_fallback": "The link could not be opened. Copy this address:",
        "btn_close": "Close",
    },
    "fr": {
        "title": "Soutenir VelantisWind",
        "hero": "Des flux de travail éoliens open source, directement dans QGIS.",
        "subtitle": (
            "VelantisWind est un plugin QGIS gratuit et open source destiné à l’analyse préliminaire "
            "des parcs éoliens, aux flux de validation et aux tâches de préévaluation géospatiale. "
            "Votre soutien aide à en faire un outil plus robuste, mieux documenté et mieux validé pour des flux de travail réels."
        ),
        "why_items": [
            "Maintenance du plugin, stabilité et compatibilité avec QGIS.",
            "Documentation, tutoriels, exemples et traductions.",
            "Validation avec des cas réels de parcs éoliens.",
            "Améliorations des modules AEP, sillages, bruit et ombres portées.",
            "Support pour les bêta-testeurs, les premiers utilisateurs et les partenaires techniques.",
            "Nouvelles fonctionnalités demandées par les utilisateurs, bureaux d’études, universités et partenaires.",
        ],
        "company_title": "Validation et soutien de la communauté",
        "company_text": (
            "Le soutien des utilisateurs, bureaux d’études, universités et bêta-testeurs aide à améliorer la documentation, "
            "la stabilité, la validation avec des cas réels et les futures fonctionnalités open source."
        ),
        "academic_title": "Collaboration académique et recherche",
        "academic_text": (
            "VelantisWind est ouvert aux universités et aux groupes de recherche. Des projets de fin d’études, mémoires "
            "ou travaux appliqués peuvent aider à valider, documenter ou étendre le plugin avec de nouveaux modules, "
            "à condition qu’ils soient techniquement alignés avec le projet open source."
        ),
        "tiers_title": "Options de soutien",
        "tiers": [
            ("Open Supporter", "à partir de 1 €", "Soutien ponctuel avec reconnaissance optionnelle."),
            ("Project Supporter", "25 €", "Nom optionnel dans la liste des supporters."),
            ("Professional Backer", "100 €", "Nom et lien optionnels."),
            ("Organization Backer", "500 €", "Petit logo ou mention de l’organisation."),
            ("Major Backer", "2 500 €", "Reconnaissance mise en avant et échange technique optionnel."),
            ("Community Sponsor", "5 €/mois", "Nom optionnel dans la liste des supporters."),
            ("Professional Sponsor", "25 €/mois", "Nom et lien optionnels."),
            ("Workflow Sponsor", "100 €/mois", "Petit logo ou mention de l’organisation."),
            ("Validation Sponsor", "250 €/mois", "Logo et mention comme sponsor de validation."),
            ("Partner Sponsor", "500 €/mois", "Logo mis en avant sur GitHub, dans la documentation ou la section About/Sponsors."),
        ],
        "partnerships_title": "Autres formes de collaboration",
        "partnerships": [
            "Bêta-test et retours techniques.",
            "Validation sur des projets réels ou des flux de travail internes.",
            "Contributions techniques, documentation ou exemples.",
            "Cas d’usage, exemples de validation et retours sur la documentation.",
            "Collaboration académique via projets de fin d’études, recherche appliquée ou matériel pédagogique.",
        ],
        "disclaimer": (
            "VelantisWind restera gratuit et open source. Le soutien est optionnel et n’implique ni propriété, ni exclusivité, "
            "ni contrôle sur la feuille de route. La reconnaissance publique est optionnelle et peut être omise si le supporter souhaite rester anonyme. "
            f"Contact : {CONTACT_EMAIL}"
        ),
        "btn_sponsor": "Sponsoriser / faire un don",
        "btn_support": CONTACT_EMAIL,
        "btn_support_doc": "Voir SUPPORT.md",
        "btn_project": "Documentation du projet",
        "btn_supporters": "Supporters",
        "sponsor_tooltip": "Ouvre le profil de VelantisWind sur GitHub Sponsors. Les modalités de paiement figurent sur GitHub.",
        "tiers_show": "Voir les niveaux de soutien",
        "tiers_hide": "Masquer les niveaux de soutien",
        "url_fallback": "Le lien n’a pas pu être ouvert. Copiez cette adresse :",
        "btn_close": "Fermer",
    },
    "de": {
        "title": "VelantisWind unterstützen",
        "hero": "Open-Source-Workflows für Windenergie, direkt in QGIS.",
        "subtitle": (
            "VelantisWind ist ein kostenloses Open-Source-QGIS-Plugin für die frühe Analyse von Windparks, "
            "Validierungsworkflows und georäumliche Vorbewertungen. Ihre Unterstützung hilft dabei, daraus "
            "ein robusteres, besser dokumentiertes und besser validiertes Werkzeug für praktische Windenergie-Workflows zu machen."
        ),
        "why_items": [
            "Wartung des Plugins, Stabilität und QGIS-Kompatibilität.",
            "Dokumentation, Tutorials, Beispiele und Übersetzungen.",
            "Validierung mit realen Windpark-Fällen.",
            "Verbesserungen an den Modulen AEP, Nachlauf, Schall und Schattenwurf.",
            "Support für Beta-Tester, frühe Anwender und technische Partner.",
            "Neue Funktionen, die von Nutzern, Beratungsunternehmen, Universitäten und Partnern angefragt werden.",
        ],
        "company_title": "Validierung und Unterstützung durch die Community",
        "company_text": (
            "Die Unterstützung von Nutzern, Beratungsunternehmen, Universitäten und Beta-Testern hilft, Dokumentation, "
            "Stabilität, Validierung mit realen Fällen und zukünftige Open-Source-Funktionen zu verbessern."
        ),
        "academic_title": "Akademische Zusammenarbeit und Forschung",
        "academic_text": (
            "VelantisWind ist offen für Universitäten und Forschungsgruppen. Bachelor- und Masterarbeiten oder angewandte "
            "Forschungsprojekte können helfen, das Plugin zu validieren, zu dokumentieren oder mit neuen Modulen zu erweitern, "
            "sofern sie technisch zum Open-Source-Projekt passen."
        ),
        "tiers_title": "Unterstützungsoptionen",
        "tiers": [
            ("Open Supporter", "ab 1 €", "Einmalige Unterstützung mit optionaler Erwähnung."),
            ("Project Supporter", "25 €", "Optionaler Name in der Supporter-Liste."),
            ("Professional Backer", "100 €", "Name und optionaler Link."),
            ("Organization Backer", "500 €", "Kleines Logo oder Erwähnung der Organisation."),
            ("Major Backer", "2.500 €", "Hervorgehobene Anerkennung und optionales technisches Gespräch."),
            ("Community Sponsor", "5 €/Monat", "Optionaler Name in der Supporter-Liste."),
            ("Professional Sponsor", "25 €/Monat", "Name und optionaler Link."),
            ("Workflow Sponsor", "100 €/Monat", "Kleines Logo oder Erwähnung der Organisation."),
            ("Validation Sponsor", "250 €/Monat", "Logo und Erwähnung als Validierungssponsor."),
            ("Partner Sponsor", "500 €/Monat", "Hervorgehobenes Logo auf GitHub, in der Dokumentation oder im About/Sponsors-Bereich."),
        ],
        "partnerships_title": "Weitere Möglichkeiten zur Zusammenarbeit",
        "partnerships": [
            "Beta-Testing und technisches Feedback.",
            "Validierung anhand realer Projekte oder interner Workflows.",
            "Technische Beiträge, Dokumentation oder Beispiele.",
            "Anwendungsfälle, Validierungsbeispiele und Feedback zur Dokumentation.",
            "Akademische Zusammenarbeit über Abschlussarbeiten, angewandte Forschung oder Lehrmaterial.",
        ],
        "disclaimer": (
            "VelantisWind bleibt kostenlos und open source. Unterstützung ist optional und bedeutet weder Eigentum, Exklusivität "
            "noch Kontrolle über die Roadmap. Öffentliche Anerkennung ist optional und kann entfallen, wenn der Supporter anonym bleiben möchte. "
            f"Kontakt: {CONTACT_EMAIL}"
        ),
        "btn_sponsor": "Sponsern / spenden",
        "btn_support": CONTACT_EMAIL,
        "btn_support_doc": "SUPPORT.md ansehen",
        "btn_project": "Projektdokumentation",
        "btn_supporters": "Unterstützer",
        "sponsor_tooltip": "Öffnet das Profil von VelantisWind auf GitHub Sponsors. Die Zahlungsdetails finden Sie auf GitHub.",
        "tiers_show": "Unterstützungsstufen anzeigen",
        "tiers_hide": "Unterstützungsstufen ausblenden",
        "url_fallback": "Der Link konnte nicht geöffnet werden. Kopieren Sie diese Adresse:",
        "btn_close": "Schließen",
    },
}


def _lang() -> str:
    try:
        lang = str(current_language() or "es").lower().strip()
    except Exception:
        lang = "es"
    short = lang.replace("-", "_").split("_", 1)[0]
    return short if short in _TEXTS else "es"


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
        two_cols.addWidget(self._info_card(_tr(_TEXTS["es"]["why_title"]), self._bullets_html(t["why_items"])), 1)
        two_cols.addWidget(self._info_card(t["company_title"], t["company_text"]), 1)
        root.addLayout(two_cols)

        root.addWidget(self._info_card(t["academic_title"], t["academic_text"]))

        # The levels are optional reading: folded until asked for.
        self.btn_toggle_tiers = QtWidgets.QPushButton(t["tiers_show"], content)
        self.btn_toggle_tiers.setObjectName("supportTierToggle")
        self.btn_toggle_tiers.setCheckable(True)
        root.addWidget(self.btn_toggle_tiers)
        self.tiers_panel = QtWidgets.QWidget(content)
        tiers_layout = QtWidgets.QVBoxLayout(self.tiers_panel)
        tiers_layout.setContentsMargins(0, 0, 0, 0)
        tiers_layout.setSpacing(6)
        tiers_title = QtWidgets.QLabel(t["tiers_title"], self.tiers_panel)
        tiers_title.setObjectName("supportTiersTitle")
        tiers_layout.addWidget(tiers_title)
        for name, amount, description in t["tiers"]:
            tiers_layout.addWidget(self._tier_row(name, amount, description))
        self.tiers_panel.setVisible(False)
        self.btn_toggle_tiers.toggled.connect(self._toggle_tiers)
        root.addWidget(self.tiers_panel)

        root.addWidget(self._info_card(t["partnerships_title"], self._bullets_html(t["partnerships"])))

        disclaimer = QtWidgets.QLabel(t["disclaimer"], content)
        disclaimer.setObjectName("supportDisclaimer")
        disclaimer.setWordWrap(True)
        root.addWidget(disclaimer)

        # Two rows: the five buttons do not fit whole in one at the dialog's width.
        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)

        self.btn_sponsor = QtWidgets.QPushButton(t["btn_sponsor"], self)
        self.btn_sponsor.setObjectName("primarySupportButton")
        self.btn_sponsor.setToolTip(t["sponsor_tooltip"])
        self.btn_sponsor.clicked.connect(lambda: self._open_url(SPONSOR_URL))
        button_row.addWidget(self.btn_sponsor)

        self.btn_support_doc = QtWidgets.QPushButton(t["btn_support_doc"], self)
        self.btn_support_doc.clicked.connect(lambda: self._open_url(SUPPORT_DOC_URL))
        button_row.addWidget(self.btn_support_doc)

        self.btn_project = QtWidgets.QPushButton(t["btn_project"], self)
        self.btn_project.clicked.connect(lambda: self._open_url(GITHUB_PROJECT_URL))
        button_row.addWidget(self.btn_project)
        button_row.addStretch(1)

        second_row = QtWidgets.QHBoxLayout()
        second_row.setSpacing(8)
        self.btn_contact = QtWidgets.QPushButton(t["btn_support"], self)
        self.btn_contact.clicked.connect(lambda: self._open_url(CONTACT_URL))
        second_row.addWidget(self.btn_contact)
        self.btn_supporters = QtWidgets.QPushButton(t["btn_supporters"], self)
        self.btn_supporters.clicked.connect(lambda: self._open_url(SUPPORTERS_URL))
        second_row.addWidget(self.btn_supporters)

        second_row.addStretch(1)
        btn_close = QtWidgets.QPushButton(t["btn_close"], self)
        btn_close.clicked.connect(self.close)
        second_row.addWidget(btn_close)

        outer.addLayout(button_row)
        outer.addLayout(second_row)
        self._apply_style()

    def _open_url(self, url: str) -> bool:
        """Open ``url`` in the browser; if it does not open, show it so that it can be copied."""
        try:
            opened = bool(QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)))
        except Exception:
            opened = False
        if not opened:
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle(self._texts["title"])
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText(f"{self._texts['url_fallback']}\n{url}")
            msg.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |
                                        QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard)
            label = msg.findChild(QtWidgets.QLabel, "qt_msgbox_label")
            if label is not None:
                label.setFocusPolicy(QtCore.Qt.StrongFocus)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
        return opened

    def _toggle_tiers(self, expanded: bool) -> None:
        self.tiers_panel.setVisible(expanded)
        self.btn_toggle_tiers.setText(self._texts["tiers_hide" if expanded else "tiers_show"])

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
