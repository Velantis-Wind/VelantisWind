# -*- coding: utf-8 -*-
"""
results_dialog.py

Diálogo para mostrar un resumen visual de los resultados AEP,
similar a la salida de WAsP, con desglose de pérdidas y
métricas adicionales (factor de capacidad, etc. cuando sea posible).
"""

from typing import Dict, Any, List, Optional, Tuple

import html as html_mod
import os
import re

from .ag_core.results.model_config_html import (POSITIONS_V1, POSITIONS_V2, _component_text, linked,
                                                model_config_html, model_config_html_v2, format_report_note)
from .ag_core.log_text import shown
from .ag_core.wake_setup.notices import result_warnings
from .ui_core.wake_controls import CollapsibleSection
from .ag_core.results.coverage import partial_aep_warning
from .ag_core.results.coverage_translations import register_coverage_translations
from .ag_core.results.model_config_translations import register_model_config_translations
from .ag_core.wake_setup.catalog_translations import register_catalog_translations
from .ag_core.wake_setup.messages_translations import register_messages_translations
from .ag_core.results import breakdown as _bd
from .ag_core.edge_cases import non_finite_label
from .number_format import format_number, format_percent
from .ag_core.results.breakdown_translations import register_breakdown_translations
from .ag_core.results.result_v2 import result_schema

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtGui import QIcon, QPixmap
from .i18n import (apply_i18n, install_runtime_i18n_patches, mark_translated, translate_html, tr_text as _tr,
                   current_language)

register_model_config_translations()
register_coverage_translations()
register_catalog_translations()
register_messages_translations()
register_breakdown_translations()




def _cleanup_german_aep_html(text: str) -> str:
    """Last-mile cleanup for generated AEP HTML in German.

    The report is assembled from dynamic Spanish/French/English fragments and
    table headers, so the generic i18n engine can leave residual mixed phrases.
    This function only runs for the German UI and avoids touching calculations.
    """
    if not text:
        return text
    html = str(text)
    repl = [
        ("Informe técnico AEP", "Technischer AEP-Bericht"),
        ("Módulo Energía · Flujo PyWake", "Energiemodul · PyWake-Workflow"),
        ("Resumen global", "Gesamtübersicht"),
        ("Por modelo de aerogenerador", "Nach Windturbinenmodell"),
        ("Por aerogenerador", "Nach Windturbine"),
        ("Por sector de viento", "Nach Windsektor"),
        ("Esta tabla replica el resumen por turbina visible en la interfaz. Para análisis GIS/Excel, usa también el CSV por turbina que genera el flujo AEP.", "Diese Tabelle entspricht der in der Oberfläche sichtbaren Zusammenfassung je Turbine. Für GIS-/Excel-Analysen sollte zusätzlich der vom AEP-Workflow erzeugte Turbinen-CSV verwendet werden."),
        ("Resumen AEP del parque", "AEP-Zusammenfassung des Windparks"),
        ("Informe técnico generado desde el módulo Energía de Velantis Wind.", "Technischer Bericht aus dem Energiemodul von Velantis Wind."),
        ("AEP bruto (free-stream)", "Brutto-AEP (Freistrom)"),
        ("AEP neto (operativo)", "Netto-AEP (operativ)"),
        ("Pérdidas totales", "Gesamtverluste"),
        ("Desglose de pérdidas", "Verlustaufschlüsselung"),
        ("Estelas", "Nachläufe"),
        ("Impacto TI/turbulencia", "TI-/Turbulenzeinfluss"),
        ("Diagnóstico incremental: positivo = recupera AEP frente al wake-only; negativo = reduce AEP. No se debe interpretar siempre como pérdida contable.", "Inkrementelle Diagnose: positiv = AEP-Rückgewinnung gegenüber wake-only; negativ = AEP-Reduktion. Dies ist nicht immer als buchhalterischer Verlust zu interpretieren."),
        ("Bloqueo", "Blockage"),
        ("Otras pérdidas", "Sonstige Verluste"),
        ("Métricas adicionales", "Zusätzliche Kennzahlen"),
        ("Potencia instalada", "Installierte Leistung"),
        ("Factor de capacidad neto", "Netto-Kapazitätsfaktor"),
        ("Energía específica neta", "Spezifischer Nettoertrag"),
        ("MWh/MW·año", "MWh/MW·Jahr"),
        ("Métricas adicionales no disponibles: no se pudo determinar la potencia nominal de las turbinas. Vuelve a definir el modelo desde «Definir…» para que la curva de potencia se guarde con la metadata.", "Zusätzliche Kennzahlen nicht verfügbar: Die Nennleistung der Turbinen konnte nicht bestimmt werden. Definiere das Modell erneut über „Definieren…“, damit die Leistungskennlinie in den Metadaten gespeichert wird."),
        ("Selección del usuario", "Benutzerauswahl"),
        ("Configuración solicitada al solver", "An den Solver übergebene Konfiguration"),
        ("Configuración finalmente ejecutada", "Tatsächlich ausgeführte Konfiguration"),
        ("Notas físicas y de compatibilidad", "Physikalische und Kompatibilitätshinweise"),
        ("Modelo de aerogenerador", "Windturbinenmodell"),
        ("Modelos / clusters de aerogeneradores", "Windturbinenmodelle / Cluster"),
        ("aerogenerador(es)", "Windturbine(n)"),
        ("AEP neta del cluster", "Netto-AEP des Clusters"),
        ("del AEP neto del parque", "des Netto-AEP des Windparks"),
        ("Pérdida total (wake/TI/bloqueo)", "Gesamtverlust (Nachlauf/TI/Blockage)"),
        ("sobre AEP bruto del cluster", "bezogen auf das Brutto-AEP des Clusters"),
        ("Déficit de estela", "Nachlaufdefizit"),
        ("Modelo de turbulencia", "Turbulenzmodell"),
        ("Modelo de bloqueo", "Blockage-Modell"),
        ("Promedio rotor", "Rotormittelung"),
        ("Superposición", "Überlagerung"),
        ("Motor", "Rechenkern"),
        ("Aviso de TI ambiente", "Hinweis zur Umgebungs-TI"),
        ("no se ha proporcionado un raster de TI", "es wurde kein TI-Raster angegeben"),
        ("El cálculo ha usado", "Die Berechnung hat"),
        ("uniforme como fallback", "gleichmäßig als Fallback verwendet"),
        ("Este valor afecta directamente al AEP en wakes TI-driven", "Dieser Wert beeinflusst das AEP direkt bei TI-gesteuerten Nachlaufmodellen"),
        ("Para resultados representativos, carga un raster TI en la sección de recurso o revisa la sensibilidad de turbulencia.", "Für repräsentative Ergebnisse lade ein TI-Raster im Ressourcenbereich oder prüfe die Turbulenzsensitivität."),
        ("Sustitución de modelo de bloqueo", "Ersetzung des Blockage-Modells"),
        ("Aviso de compatibilidad", "Kompatibilitätshinweis"),
        ("La combinación de wake TI-driven con SelfSimilarity2020 no convergió en PyWake.", "Die Kombination aus TI-gesteuertem Nachlauf und SelfSimilarity2020 konvergierte in PyWake nicht."),
        ("Se ha mantenido el bloqueo sustituyéndolo por", "Blockage wurde beibehalten, aber ersetzt durch"),
        ("El resto de la selección se ha respetado.", "Die übrige Auswahl wurde beibehalten."),
        ("La simulación no pudo ejecutarse exactamente con la combinación pedida y PyWake requirió una degradación automática.", "Die Simulation konnte nicht exakt mit der angeforderten Kombination ausgeführt werden; PyWake erforderte eine automatische Degradierung."),
        ("Paso aplicado", "Angewendeter Schritt"),
        ("Generated by Velantis Wind · QGIS energy module · PyWake-based AEP workflow.", "Erstellt mit Velantis Wind · QGIS-Energiemodul · PyWake-basierter AEP-Workflow."),
        ("Table truncated in the HTML report: showing", "Tabelle im HTML-Bericht gekürzt: angezeigt werden"),
        ("rows. The CSV export contains the full detail.", "Zeilen. Der CSV-Export enthält alle Details."),
        ("Free AEP", "Brutto-AEP"),
        ("Net AEP", "Netto-AEP"),
        ("Wake losses", "Nachlaufverluste"),
        ("Wake lossess", "Nachlaufverluste"),
        ("Blockage losses", "Blockage-Verluste"),
        ("TI impact", "TI-Einfluss"),
        ("Net specific yield", "Spezifischer Nettoertrag"),
        ("By wind sector", "Nach Windsektor"),
    ]
    for a, b in repl:
        html = html.replace(a, b)
    html = re.sub(r"(\d+[\.,]?\d*)\s*%\s*del AEP neto del parque", r"\1 % des Netto-AEP des Windparks", html)
    html = re.sub(r"(\d+[\.,]?\d*)\s*%\s*sobre AEP bruto del cluster", r"\1 % bezogen auf das Brutto-AEP des Clusters", html)
    html = re.sub(r"\bPaso aplicado\s*:", "Angewendeter Schritt:", html)
    return html


def _localized_report_html(text: str) -> str:
    out = translate_html(text)
    try:
        if str(current_language()).lower().startswith("de"):
            out = _cleanup_german_aep_html(out)
    except Exception:  # nosec B110
        pass
    return out


# User data (model names, scenario labels, notes filled with data) must not go through the report localization:
# the HTML carries a slot tag for each text and _fill_slots puts the escaped text back afterwards. Every text in
# the HTML is escaped, so a slot tag can only come from _slot.
_SLOT = re.compile(r"<vw-slot-(\d+)>")


def _slot(texts: List[str], text: Any) -> str:
    text = str(text)
    if text not in texts:
        texts.append(text)
    return f"<vw-slot-{texts.index(text)}>"


class _Html(str):
    """HTML already translated (the configuration of a schema-2 result): put back as it is, not escaped."""


def _slot_html(texts: List[str], html: str) -> str:
    """A slot for translated HTML: the report localization would translate it a second time and spoil it."""
    texts.append(_Html(html))
    return f"<vw-slot-{len(texts) - 1}>"


def _fill_slots(texts: List[str], html: str) -> str:
    """In one pass, so a text put back is never read as another slot."""
    def back(m):
        text = texts[int(m.group(1))]
        return text if isinstance(text, _Html) else html_mod.escape(text)
    return _SLOT.sub(back, html)


def _note_html(texts: List[str], note: Any) -> str:
    """A note translated here, kept from the report localization, which only translates by fragments: a note with
    data by its template, a plain Spanish note by its entry."""
    text = format_report_note(note, _tr)
    return _slot(texts, text if getattr(note, "template_item", None) else _tr(text))


def _is_debug_enabled() -> bool:
    return str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}


def _debug_print(message: str) -> None:
    if _is_debug_enabled():
        print(message)


def _fmt_mwh(v) -> str:
    """Formatea MWh con un decimal en el idioma del plugin; un no finito, con su rótulo (#63)."""
    try:
        x = float(v)
    except Exception:
        return "-"
    if non_finite_label(x):
        return non_finite_label(x)
    return format_number(x)


def _fmt_mw(v) -> str:
    """Formatea MW con 3 decimales. Devuelve '-' si vale 0 o no se puede convertir,
    para evitar mostrar '0,000 MW' cuando en realidad la potencia no se pudo determinar.
    """
    try:
        x = float(v)
    except Exception:
        return "-"
    if non_finite_label(x):
        return non_finite_label(x)
    if x <= 0:
        return "-"
    return format_number(x, ',.3f')


def _fmt_pct(v) -> str:
    """Formatea porcentaje con un decimal; un no finito, con su rótulo (#63)."""
    try:
        x = float(v)
    except Exception:
        return "-"
    if non_finite_label(x):
        return non_finite_label(x)
    return format_percent(x)


def _fmt_signed_mwh(v) -> str:
    """MWh con signo explícito para impactos incrementales; un no finito, con su rótulo (#63)."""
    try:
        x = float(v)
    except Exception:
        return "-"
    if non_finite_label(x):
        return non_finite_label(x)
    sign = "+" if x > 0 else ""
    return sign + _fmt_mwh(x)


def _fmt_signed_pct(v) -> str:
    try:
        x = float(v)
    except Exception:
        return "-"
    if non_finite_label(x):
        return non_finite_label(x)
    sign = "+" if x > 0 else ""
    return sign + format_percent(x)


# The label of a result of the previous schema, read with its own fields (P0 of the wake-model plan, section 8).
SCHEMA_1_NOTE = ("Resultado del esquema anterior (calculado con una versión previa del complemento): sus pérdidas "
                 "siguen la definición antigua, sin signo ni estados.")

_STATE_TEXT = {
    _bd.NOT_MODELLED: "no modelado",
    _bd.NOT_REQUESTED: "no solicitado",
    _bd.FAILED: "no disponible (falló su cálculo)",
}


def _term_text(entry: Dict[str, Any], signed: bool = True) -> str:
    """A term of the schema-2 breakdown: «value MWh (pct %)», or its state; a zero by construction says why."""
    state = entry.get("state")
    if entry.get("mwh") is None:
        return _tr(_STATE_TEXT.get(state, "no disponible"))
    value = (_fmt_signed_mwh if signed else _fmt_mwh)(entry["mwh"]) + " MWh"
    if entry.get("pct") is not None:
        value += f" ({(_fmt_signed_pct if signed else _fmt_pct)(entry['pct'])})"
    if state == _bd.ZERO_BY_CONSTRUCTION:
        value += " · " + _tr("sin efecto: el déficit no usa la TI efectiva")
    return value


def _term_cell(entry: Dict[str, Any], signed: bool = True) -> str:
    """A term for a table cell: the value in MWh, or «n/d» (translated: the cells are set again after apply_i18n)."""
    if entry is None or entry.get("mwh") is None:
        return _tr("n/d")
    return (_fmt_signed_mwh if signed else _fmt_mwh)(entry["mwh"])


def _fmt_len(v) -> str:
    """Formatea longitudes (D, Hub) con un decimal en el idioma del plugin."""
    try:
        x = float(v)
    except Exception:
        return "-"
    return non_finite_label(x) or format_number(x)


def _extract_rated_mw(rec: Dict[str, Any]) -> float:
    """
    Intenta extraer la potencia nominal de una turbina en MW
    a partir de varios nombres de campo posibles.
    """
    candidates_kw = ["p_rated_kw", "rated_kw", "p_nom_kw", "p_kw"]
    candidates_mw = ["p_rated_mw", "p_rated_MW", "rated_mw", "rated_MW", "p_nom_MW", "p_nom_mw"]

    for k in candidates_mw:
        if k in rec and rec[k] not in (None, ""):
            try:
                return float(rec[k])
            except Exception:  # nosec B110
                pass

    for k in candidates_kw:
        if k in rec and rec[k] not in (None, ""):
            try:
                return float(rec[k]) / 1000.0
            except Exception:  # nosec B110
                pass

    return 0.0


def _extract_coord(rec: Dict[str, Any], keys: List[str]) -> float:
    for k in keys:
        if k in rec and rec[k] not in (None, ""):
            try:
                return float(rec[k])
            except Exception:  # nosec B112
                continue
    return float("nan")


class AEPResultsDialog(QtWidgets.QDialog):
    """
    Muestra un resumen visual de resultados AEP, similar a WAsP:
      - Pestaña "Resumen global"
      - Pestaña "Por modelo"
      - Pestaña "Por aerogenerador"
    El diccionario `results` se espera que venga de ag_core.aep_compute.
    """

    HOURS_YEAR = 8760.0

    def _fit_dialog_to_screen(self, default_w: int = 980, default_h: int = 600) -> None:
        """Tamaño inicial robusto para portátiles/pantallas pequeñas.

        Evita que Qt calcule una ventana demasiado grande por tablas o gráficos
        internos. El usuario puede redimensionarla y todos los contenidos críticos
        quedan dentro de áreas con scroll.
        """
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                w = max(520, min(int(default_w), int(geo.width() * 0.92)))
                h = max(360, min(int(default_h), int(geo.height() * 0.88)))
                min_w = min(520, max(420, int(geo.width() * 0.70)))
                min_h = min(360, max(320, int(geo.height() * 0.60)))
                self.resize(w, h)
                self.setMinimumSize(min_w, min_h)
                return
        except Exception:  # nosec B110
            pass
        self.resize(default_w, default_h)
        self.setMinimumSize(640, 420)

    def _make_scroll_tab(self) -> Tuple[QtWidgets.QScrollArea, QtWidgets.QWidget]:
        """Crea una pestaña con scroll real y contenido redimensionable."""
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        content = QtWidgets.QWidget(scroll)
        content.setMinimumWidth(0)
        content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        scroll.setWidget(content)
        return scroll, content

    def _logo_file_url(self) -> str:
        """URL local segura para incrustar el logo en el informe HTML/exportado."""
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'velantiswind_logo.png')
        if not os.path.exists(logo_path):
            return ""
        try:
            return QtCore.QUrl.fromLocalFile(os.path.abspath(logo_path)).toString()
        except Exception:
            return "file:///" + os.path.abspath(logo_path).replace('\\', '/')

    def _report_header_html(self) -> str:
        """Cabecera corporativa reutilizable para el informe visual y exportable."""
        logo_url = self._logo_file_url()
        logo_html = (
            f'<img src="{html_mod.escape(logo_url)}" width="42" height="42" style="width:42px; height:42px; object-fit:contain;" />'
            if logo_url else '<b>Velantis Wind</b>'
        )
        generated = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm")
        # Translated here: kept from the second translation of the report.
        title = _slot(self._user_texts, _tr("Informe técnico AEP"))
        subtitle = _slot(self._user_texts, _tr("Módulo Energía · Flujo PyWake") + " · " + generated)
        return f'''
        <div style="border:1px solid #d8e2dc; border-radius:10px; padding:12px; margin-bottom:12px; background:#f8fbfa;">
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
            <tr>
              <td style="vertical-align:middle; width:70px;">{logo_html}</td>
              <td style="vertical-align:middle; text-align:left; color:#1f3d36;">
                <div style="font-size:18px; font-weight:700;">{title}</div>
                <div style="font-size:11px; color:#6b7d78;">{subtitle}</div>
              </td>
            </tr>
          </table>
        </div>
        '''

    def _translate_html_to_en(self, text: str) -> str:
        """Translate generated report fragments to English without changing the UI language.

        The visible QGIS dialog follows the language selected in the hub. The exported
        AEP technical report is intentionally standardized in English so it can be
        shared with international reviewers/testers.
        """
        if not text:
            return text
        s = str(text)
        try:
            from . import i18n as _i18n
        except Exception:
            try:
                import i18n as _i18n  # type: ignore
            except Exception:
                _i18n = None  # type: ignore
        if _i18n is not None:
            try:
                mapping = getattr(_i18n, "_FRAGMENT_TO_EN", {})
                for src, dst in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
                    if src and src in s:
                        s = s.replace(src, dst)
            except Exception:  # nosec B110
                pass
        # Last-mile report strings that come from runtime notes and can otherwise
        # remain half-translated in exported HTML.
        replacements = {
            "yes puede influir": "can influence",
            "active (": "active (",
            "vertical approximation": "vertical approximation",
            "se ha usado un único raster de ambient TI": "a single ambient TI raster was used",
            "si mezclas varios hub heights, esa TI se replica/interpola como vertical approximation": "if several hub heights are mixed, that TI is replicated/interpolated as a vertical approximation",
            "ayes que": "so",
            "versusl": "versus",
            "Pérdidas no clasificadas": "Unclassified losses",
            "Otras pérdidas": "Other losses",
            "Wake lossess": "Wake losses",
            "Energy específica neta": "Net specific yield",
            "By sector de viento": "By wind sector",
        }
        for src, dst in replacements.items():
            s = s.replace(src, dst)
        return s

    def _wrap_report_document(self, body_html: str) -> str:
        """Wrap the AEP report as a standalone localized HTML document."""
        # Translated here: kept from the second translation of the report.
        title = _slot(self._user_texts, _tr("Velantis Wind · Informe técnico AEP"))
        footer = _slot(self._user_texts, _tr("Generado por Velantis Wind · Módulo Energía de QGIS · Flujo AEP basado en PyWake."))
        doc = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; color: #1f2933; }}
    h3 {{ color: #17443b; margin-top: 22px; border-bottom: 1px solid #d8e2dc; padding-bottom: 4px; }}
    h4 {{ color: #24584d; margin-bottom: 6px; }}
    ul {{ margin-top: 6px; }}
    small {{ color: #60736e; }}
    .table-wrap {{ overflow-x: auto; margin: 8px 0 14px 0; }}
    table.data-table, table.kpi-table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    table.data-table th {{ background: #eef5f2; color: #17443b; text-align: left; border: 1px solid #d8e2dc; padding: 5px; }}
    table.data-table td, table.kpi-table td {{ border: 1px solid #d8e2dc; padding: 5px; }}
    table.data-table tr:nth-child(even), table.kpi-table tr:nth-child(even) {{ background: #fafcfc; }}
    .vw-footer {{ margin-top: 22px; padding-top: 10px; border-top: 1px solid #d8e2dc; color: #6b7d78; font-size: 11px; }}
  </style>
</head>
<body>
{body_html}
<div class="vw-footer">{footer}</div>
</body>
</html>'''
        # Export localization runs AFTER _build_full_report_html. Inject the
        # warning only now, preserving model identities through both passes.
        return self._insert_coverage_banner(_fill_slots(self._user_texts, _localized_report_html(doc)))

    def __init__(self, parent=None, results: Dict[str, Any] = None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self.setWindowTitle(_tr("Resultados AEP – Cálculo AEP (PyWake)"))
        # Icono del diálogo (el de la esquina superior izquierda / barra de tareas)
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._fit_dialog_to_screen(980, 600)
        self.setSizeGripEnabled(True)
        self.results = results or {}
        try:
            self.HOURS_YEAR = float(self.results.get("hours_per_year", 8760.0) or 8760.0)
        except Exception:
            self.HOURS_YEAR = 8760.0
        self._last_report_html = ""
        self._last_report_html_raw = ""
        # Model names are user data: the report holds slots for them and the tables restore them after apply_i18n.
        self._user_texts: List[str] = []
        self._name_items: List[Tuple[QtWidgets.QTableWidgetItem, str]] = []

        self._init_ui()
        self._populate()
        apply_i18n(self)
        if result_schema(self.results) == 2:
            # apply_i18n translates the contents of the widgets a second time, which spoils a text already
            # translated; the contents of a schema-2 result are translated when they are set, so they are set again.
            self._name_items = []
            self._populate()
        # apply_i18n translates widget contents again, including arbitrary
        # model names already inserted into the dynamically assembled notice.
        # Restore user-supplied names after static widgets have been localized.
        self._restore_coverage_after_i18n()
        self._show_wake_configuration()  # class names and warnings are data: shown again after apply_i18n
        for item, name in self._name_items:
            item.setText(name)

    _COVERAGE_PLACEHOLDER = "VW_AEP_COVERAGE_NOTICE_0_1_17"

    def _coverage_banner_html(self) -> str:
        """Build user-data-bearing HTML only after all report translations."""
        coverage = partial_aep_warning(self.results or {}, _tr)
        if not coverage:
            return ""
        return (
            "<p style='background:#fff3d9;border:1px solid #d8a34c;padding:10px;'>"
            "<b>" + html_mod.escape(_tr("Aviso de cobertura del recurso:")) + "</b> "
            + html_mod.escape(coverage) + "</p>"
        )

    def _insert_coverage_banner(self, localized_html: str) -> str:
        """Preserve turbine model names across every HTML localization pass."""
        banner = self._coverage_banner_html()
        if not banner:
            return localized_html
        # Only fixed texts precede the placeholder: its first occurrence is the banner's, even if a model has its name.
        return localized_html.replace(self._COVERAGE_PLACEHOLDER, banner, 1)

    def _restore_coverage_after_i18n(self) -> None:
        """Undo a second translation of dynamic model names in visible widgets."""
        coverage = partial_aep_warning(self.results or {}, _tr)
        self.lbl_coverage_warning.setText(coverage)
        self.lbl_coverage_warning.setVisible(bool(coverage))
        # apply_i18n may retranslate the contents of QTextBrowser as well.
        self.txt_report.setHtml(self._last_report_html)

    # ---------------------------------------------------------
    #  UI
    # ---------------------------------------------------------
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Logo Velantis (cabecera)
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'velantiswind_logo.png')
        if os.path.exists(logo_path):
            header = QtWidgets.QWidget(self)
            h = QtWidgets.QHBoxLayout(header)
            h.setContentsMargins(0, 0, 0, 0)
            h.addStretch(1)
            lbl = QtWidgets.QLabel(header)
            pix = QPixmap(logo_path)
            if not pix.isNull():
                lbl.setPixmap(pix.scaled(36, 36, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                lbl.setToolTip('Velantis Wind')
            lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            h.addWidget(lbl, 0)
            layout.addWidget(header)

        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(self.tabs)

        # --- Pestaña 1: Resumen global
        # Contenedor con scroll para que el resumen se adapte a portátiles y
        # pantallas pequeñas sin forzar el ancho/alto mínimo de la ventana.
        self.tab_global_scroll, self.tab_global = self._make_scroll_tab()
        self.tabs.addTab(self.tab_global_scroll, "Resumen global")
        self._init_tab_global()

        # --- Pestaña 2: Por modelo
        self.tab_models = QtWidgets.QWidget(self)
        self.tabs.addTab(self.tab_models, "Por modelo")
        self._init_tab_models()

        # --- Pestaña 3: Por aerogenerador
        self.tab_turbines = QtWidgets.QWidget(self)
        self.tabs.addTab(self.tab_turbines, "Por aerogenerador")
        self._init_tab_turbines()

        # --- Pestaña 4: Por sector (rosa de pérdidas) — solo si hay datos
        try:
            self._init_tab_sector()
        except Exception:  # nosec B110
            pass

        # Botones abajo
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close,
            QtCore.Qt.Horizontal,
            self,
        )
        # A standard button follows the language of QGIS, not that of the plugin.
        btns.button(QtWidgets.QDialogButtonBox.Close).setText(_tr("Cerrar"))
        self.btn_export_report_html = QtWidgets.QPushButton("Exportar informe HTML…", self)
        self.btn_export_report_html.setToolTip("Guarda el resumen AEP con logo Velantis Wind y formato corporativo en un archivo HTML.")
        btns.addButton(self.btn_export_report_html, QtWidgets.QDialogButtonBox.ActionRole)
        self.btn_export_report_html.clicked.connect(self._export_report_html)

        self.btn_export_turbines_csv = QtWidgets.QPushButton("Exportar CSV por turbina…", self)
        self.btn_export_turbines_csv.setToolTip("Guarda una tabla limpia con una fila por aerogenerador: coordenadas, modelo, AEP neto/bruto y pérdidas principales.")
        btns.addButton(self.btn_export_turbines_csv, QtWidgets.QDialogButtonBox.ActionRole)
        self.btn_export_turbines_csv.clicked.connect(self._export_turbines_csv)

        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    def _export_turbines_csv(self) -> None:
        """Exporta el detalle por aerogenerador desde la ventana de resultados."""
        try:
            per_turb = (self.results or {}).get("per_turbine_table", []) or []
            if not per_turb:
                QtWidgets.QMessageBox.information(self, _tr("Exportar CSV por turbina"), _tr("No hay datos por turbina para exportar."))
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                _tr("Exportar CSV por turbina"),
                "velantiswind_aep_per_turbine_summary.csv",
                "CSV (*.csv);;" + _tr("Todos los archivos (*)"),
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                from .ag_core.qgis_io.export import export_per_turbine_to_csv
            except Exception:
                from .ag_core.export_results import export_per_turbine_to_csv
            export_per_turbine_to_csv(per_turb, path, self.results)
            QtWidgets.QMessageBox.information(
                self, _tr("CSV exportado"), _tr("CSV por turbina exportado correctamente:\n{path}").format(path=path)
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, _tr("No se pudo exportar el CSV"), _tr("No se pudo exportar el CSV por turbina:\n{error}").format(error=e)
            )

    def _qtable_to_html(self, table: QtWidgets.QTableWidget, max_rows: Optional[int] = 500, name_col: Optional[int] = None) -> str:
        """Convert a QTableWidget to HTML.

        ``max_rows=None`` exports every row. This is important for the wind-sector
        table, where all wind directions/sectors are part of the technical trace.
        """
        if table is None:
            return ""
        try:
            rows = table.rowCount()
            cols = table.columnCount()
        except Exception:
            return ""
        if rows <= 0 or cols <= 0:
            return "<p><i>" + _slot(self._user_texts, _tr("Sin datos disponibles.")) + "</i></p>"
        headers = []
        for c in range(cols):
            item = table.horizontalHeaderItem(c)
            # A header is already translated in the window: kept from the second translation of the report.
            headers.append(_slot(self._user_texts, item.text()) if item is not None else f"Col {c+1}")
        html = ["<div class='table-wrap'><table class='data-table'><thead><tr>"]
        html.extend(f"<th>{h}</th>" for h in headers)
        html.append("</tr></thead><tbody>")
        n = rows if max_rows is None or int(max_rows) <= 0 else min(rows, int(max_rows))
        for r in range(n):
            html.append("<tr>")
            for c in range(cols):
                item = table.item(r, c)
                val = item.text() if item is not None else ""
                html.append(f"<td>{_slot(self._user_texts, val) if c == name_col else html_mod.escape(str(val))}</td>")
            html.append("</tr>")
        html.append("</tbody></table></div>")
        if max_rows is not None and int(max_rows) > 0 and rows > int(max_rows):
            html.append("<p><small>" + _slot(self._user_texts, _tr(
                "Tabla truncada en el informe HTML: se muestran {shown} de {total} filas. La exportación CSV contiene "
                "el detalle completo.").format(shown=format_number(int(max_rows), ",d"), total=format_number(rows, ",d"))) + "</small></p>")
        return "".join(html)

    def _global_kpi_html(self) -> str:
        if result_schema(self.results or {}) == 2:
            # The rows as the summary shows them (their titles change with the schema, #75 row 4.13).
            rows = [(re.sub(r"<[^>]+>", "", t.text()).strip().rstrip(":"), w) for t, w in self._global_rows]
        else:
            rows = [
                ("AEP bruto (flujo libre)", getattr(self, "lbl_aep_free", None)),
                ("AEP neto (operativo)", getattr(self, "lbl_aep_net", None)),
                ("Pérdidas por estelas", getattr(self, "lbl_loss_wake", None)),
                ("Impacto TI/turbulencia", getattr(self, "lbl_loss_ti", None)),
                ("Pérdidas por bloqueo", getattr(self, "lbl_loss_blk", None)),
                ("Otras pérdidas", getattr(self, "lbl_loss_other", None)),
                ("Pérdidas totales", getattr(self, "lbl_loss_total", None)),
                ("Nº de aerogeneradores", getattr(self, "lbl_n_turb", None)),
                ("Potencia instalada", getattr(self, "lbl_p_inst_mw", None)),
                ("Factor de capacidad neto", getattr(self, "lbl_cf_net", None)),
                ("Energía específica neta", getattr(self, "lbl_spec_yield", None)),
            ]
        out = ["<table class='kpi-table'>"]
        for label, widget in rows:
            # Saltar filas cuyo widget se ha ocultado deliberadamente (p.ej.
            # "Otras pérdidas" cuando el residuo es despreciable).
            try:
                # A row is left out only when it was hidden on purpose, also with another tab active (#75, row 6.9):
                # isVisible() is false for every widget of a tab that is not shown.
                hidden = widget.isHidden()
                if widget is not None and hidden:
                    continue
            except Exception:  # nosec B110
                pass
            try:
                value = widget.text() if widget is not None else "-"
            except Exception:
                value = "-"
            if result_schema(self.results or {}) != 2:
                label = _tr(label)
            # Translated here or in the window: kept from the second pass.
            label, value = _slot(self._user_texts, label), _slot(self._user_texts, value)
            out.append(f"<tr><td><b>{label}</b></td><td>{value}</td></tr>")
        out.append("</table>")
        return "".join(out)

    def _build_full_report_html(self) -> str:
        """Informe HTML completo: resumen, pestaña por modelo, por turbina y por sector."""
        def t(text):
            # Translated here: kept from the second translation of the report (_localized_report_html).
            return _slot(self._user_texts, _tr(text))
        parts = []
        base_report = getattr(self, "_last_report_html_raw", "") or self._last_report_html or ""
        if base_report:
            parts.append(base_report)
        else:
            parts.append(self._report_header_html())
        parts.append(f"<h3>{t('Resumen global')}</h3>")
        parts.append(self._global_kpi_html())
        parts.append(f"<h3>{t('Por modelo de aerogenerador')}</h3>")
        parts.append(self._qtable_to_html(getattr(self, "table_models", None), max_rows=200, name_col=0))
        parts.append(f"<h3>{t('Por aerogenerador')}</h3>")
        parts.append("<p><small>" + t("Esta tabla replica el resumen por turbina visible en la interfaz. Para análisis "
                                      "GIS/Excel, usa también el CSV por turbina que genera el flujo AEP.") + "</small></p>")
        parts.append(self._qtable_to_html(getattr(self, "table_turbines", None), max_rows=500, name_col=1))
        aggregation = (self.results or {}).get("ti_aggregation") if result_schema(self.results or {}) == 2 else None
        if aggregation:
            parts.append("<p><small>" + _slot(self._user_texts, _tr(
                "TI ambiente: {ambient}. TI efectiva: {effective}.").format(
                ambient=_tr(aggregation.get("ti_ambient", "")), effective=_tr(aggregation.get("ti_effective", "")))
            ) + "</small></p>")
        sector_table = getattr(self, "table_sector", None)
        if sector_table is not None:
            parts.append(f"<h3>{t('Por sector de viento')}</h3>")
            parts.append(self._qtable_to_html(sector_table, max_rows=None))
        joined = "\n".join(parts)
        # Keep the placeholder until _wrap_report_document has finished its
        # second localization pass; otherwise user names may be translated.
        return _localized_report_html(joined)

    def _export_report_html(self) -> None:
        """Exporta el informe AEP visual como HTML con cabecera corporativa."""
        try:
            default_name = "velantiswind_aep_technical_report.html"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                _tr("Exportar informe AEP"),
                default_name,
                _tr("HTML (*.html);;Todos los archivos (*)"),
            )
            if not path:
                return
            if not path.lower().endswith((".html", ".htm")):
                path += ".html"
            body = self._build_full_report_html()
            html_doc = self._wrap_report_document(body)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_doc)
            QtWidgets.QMessageBox.information(
                self,
                _tr("Informe exportado"),
                _tr("Informe AEP exportado correctamente:\n{path}").format(path=path),
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                _tr("No se pudo exportar el informe"),
                _tr("No se pudo exportar el informe AEP:\n{error}").format(error=e),
            )

    def _init_tab_global(self):
        # Antes este resumen usaba un grid de dos columnas. En pantallas pequeñas
        # el gráfico + informe HTML forzaban un ancho mínimo excesivo. Ahora usamos
        # flujo vertical con scroll: siempre cabe y sigue siendo legible.
        layout = QtWidgets.QVBoxLayout(self.tab_global)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Grupo de resumen numérico principal
        group = QtWidgets.QGroupBox("AEP, pérdidas y capacidad global", self.tab_global)
        group.setMinimumWidth(0)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        form = QtWidgets.QGridLayout(group)
        form.setContentsMargins(10, 10, 10, 10)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(4)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)

        self.lbl_aep_free = QtWidgets.QLabel("-")
        self.lbl_aep_net = QtWidgets.QLabel("-")
        self.lbl_loss_wake = QtWidgets.QLabel("-")
        self.lbl_loss_ti = QtWidgets.QLabel("-")
        self.lbl_loss_blk = QtWidgets.QLabel("-")
        self.lbl_loss_other = QtWidgets.QLabel("-")
        self.lbl_loss_total = QtWidgets.QLabel("-")

        self.lbl_n_turb = QtWidgets.QLabel("-")
        self.lbl_p_inst_mw = QtWidgets.QLabel("-")
        self.lbl_cf_net = QtWidgets.QLabel("-")
        self.lbl_spec_yield = QtWidgets.QLabel("-")

        value_labels = [
            self.lbl_aep_free, self.lbl_aep_net, self.lbl_loss_wake, self.lbl_loss_ti,
            self.lbl_loss_blk, self.lbl_loss_other, self.lbl_loss_total, self.lbl_n_turb,
            self.lbl_p_inst_mw, self.lbl_cf_net, self.lbl_spec_yield,
        ]
        for lab in value_labels:
            lab.setMinimumWidth(0)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            lab.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        row = 0
        rows = [
            ("<b>AEP bruto (flujo libre):</b>", self.lbl_aep_free),
            ("<b>AEP neto (operativo):</b>", self.lbl_aep_net),
            ("Pérdidas por estelas:", self.lbl_loss_wake),
            ("Impacto TI/turbulencia:", self.lbl_loss_ti),
            ("Pérdidas por bloqueo:", self.lbl_loss_blk),
            ("Otras pérdidas:", self.lbl_loss_other),
            ("<b>Pérdidas totales:</b>", self.lbl_loss_total),
            ("<b>Nº de aerogeneradores:</b>", self.lbl_n_turb),
            ("<b>Potencia instalada:</b>", self.lbl_p_inst_mw),
            ("<b>Factor de capacidad (neto):</b>", self.lbl_cf_net),
            ("<b>Energía específica neta:</b>", self.lbl_spec_yield),
        ]
        # Conservamos referencia al label "Otras pérdidas:" para poder ocultar
        # la fila entera cuando el residuo sea numéricamente irrelevante (la
        # decomposición wake/TI/bloqueo ya cierra el balance).
        self.lbl_loss_other_title = None
        self._global_rows = []
        for title, value_widget in rows:
            title_lbl = QtWidgets.QLabel(title)
            title_lbl.setMinimumWidth(0)
            title_lbl.setWordWrap(True)
            form.addWidget(title_lbl, row, 0)
            form.addWidget(value_widget, row, 1)
            if value_widget is self.lbl_loss_other:
                self.lbl_loss_other_title = title_lbl
            self._global_rows.append((title_lbl, value_widget))
            row += 1

        layout.addWidget(group, 0)

        self.lbl_coverage_warning = QtWidgets.QLabel(self.tab_global)
        # Model names are user data: show the notice as text, never interpreted HTML.
        self.lbl_coverage_warning.setTextFormat(QtCore.Qt.PlainText)
        self.lbl_coverage_warning.setWordWrap(True)
        self.lbl_coverage_warning.setStyleSheet(
            "background:#fff3d9; color:#6a3900; border:1px solid #d8a34c; padding:10px;"
        )
        self.lbl_coverage_warning.setVisible(False)
        layout.insertWidget(0, self.lbl_coverage_warning)
        self.lbl_schema_note = QtWidgets.QLabel(self.tab_global)
        self.lbl_schema_note.setWordWrap(True)
        self.lbl_schema_note.setStyleSheet("background:#eef1f5; color:#33414f; border:1px solid #b9c4d0; padding:8px;")
        self.lbl_schema_note.setVisible(False)
        layout.insertWidget(1, self.lbl_schema_note)
        # Schema 2: the identification of the configuration and, before the figures, its warnings (persistent,
        # adaptations and convergence); after the figures, the executed configuration, folded.
        self.lbl_wake_id = QtWidgets.QLabel(self.tab_global)
        self.lbl_wake_id.setTextFormat(QtCore.Qt.PlainText)
        self.lbl_wake_id.setWordWrap(True)
        self.lbl_wake_id.setStyleSheet("color:#24584d; font-weight:bold; padding:4px;")
        self.lbl_wake_id.setVisible(False)
        layout.insertWidget(2, self.lbl_wake_id)
        self.lbl_wake_warnings = QtWidgets.QLabel(self.tab_global)
        self.lbl_wake_warnings.setTextFormat(QtCore.Qt.RichText)  # the link of a predefined model's note, opened
        self.lbl_wake_warnings.setOpenExternalLinks(True)
        self.lbl_wake_warnings.setWordWrap(True)
        self.lbl_wake_warnings.setStyleSheet("background:#fff3d9; color:#6a3900; border:1px solid #d8a34c; padding:8px;")
        self.lbl_wake_warnings.setVisible(False)
        layout.insertWidget(3, self.lbl_wake_warnings)
        self.sec_executed = CollapsibleSection(_tr("Configuración ejecutada"), self.tab_global)
        self.txt_executed = QtWidgets.QTextBrowser(self.sec_executed.body)
        self.txt_executed.setReadOnly(True)
        self.txt_executed.setMinimumHeight(160)
        self.sec_executed.body_layout.addWidget(self.txt_executed)
        self.sec_executed.setVisible(False)
        layout.insertWidget(layout.indexOf(group) + 1, self.sec_executed)

        # Gráfico de balance global: bruto vs neto + pérdidas. Sirve como
        # comprobación visual rápida de que el desglose cuadra con el resumen.
        self.grp_balance = QtWidgets.QGroupBox("Balance total AEP", self.tab_global)
        self.grp_balance.setMinimumWidth(0)
        self.grp_balance.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.balance_layout = QtWidgets.QVBoxLayout(self.grp_balance)
        self.balance_layout.setContentsMargins(8, 8, 8, 8)
        self.balance_layout.setSpacing(6)
        layout.addWidget(self.grp_balance, 0)

        # Texto tipo informe (HTML) al estilo WAsP
        self.txt_report = QtWidgets.QTextBrowser(self.tab_global)
        self.txt_report.setReadOnly(True)
        self.txt_report.setMinimumWidth(0)
        self.txt_report.setMinimumHeight(180)
        self.txt_report.setOpenExternalLinks(True)
        self.txt_report.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(self.txt_report, 1)

    def _init_tab_models(self):
        layout = QtWidgets.QVBoxLayout(self.tab_models)

        self.table_models = QtWidgets.QTableWidget(self.tab_models)
        # Columnas: Modelo, D, Hub, nº turbinas, Pot. inst., AEP, pérdidas, etc.
        self.table_models.setColumnCount(13)
        self.table_models.setHorizontalHeaderLabels([
            "Modelo",
            "D [m]",
            "Altura de buje [m]",
            "Nº turbinas",
            "Potencia inst. [MW]",
            "AEP bruto [MWh]",
            "AEP neto [MWh]",
            "Pérd. estelas [MWh]",
            "Pérd. bloqueo [MWh]",
            "Impacto TI [MWh]",
            "FC neto [%]",
            "AEP/MW [MWh/MW·año]",
            "Pérd. estelas [%]",
        ])
        self.table_models.setMinimumWidth(0)
        self.table_models.setWordWrap(False)
        self.table_models.setTextElideMode(QtCore.Qt.ElideRight)
        self.table_models.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.table_models.horizontalHeader().setStretchLastSection(False)
        self.table_models.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table_models.horizontalHeader().setDefaultSectionSize(105)
        self.table_models.horizontalHeader().setMinimumSectionSize(70)

        layout.addWidget(self.table_models)

    def _init_tab_turbines(self):
        layout = QtWidgets.QVBoxLayout(self.tab_turbines)

        self.table_turbines = QtWidgets.QTableWidget(self.tab_turbines)
        #  ID, modelo, X, Y, P_nom, AEP_neto, AEP_bruto, loss_wake, loss_blk, CF
        self.table_turbines.setColumnCount(10)
        self.table_turbines.setHorizontalHeaderLabels([
            "ID",
            "Modelo",
            "X",
            "Y",
            "P_nom [MW]",
            "AEP neto [MWh]",
            "AEP bruto [MWh]",
            "Pérd. estela [MWh]",
            "Pérd. bloqueo [MWh]",
            "FC neto [%]",
        ])
        self.table_turbines.setMinimumWidth(0)
        self.table_turbines.setWordWrap(False)
        self.table_turbines.setTextElideMode(QtCore.Qt.ElideRight)
        self.table_turbines.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.table_turbines.horizontalHeader().setStretchLastSection(False)
        self.table_turbines.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table_turbines.horizontalHeader().setDefaultSectionSize(105)
        self.table_turbines.horizontalHeader().setMinimumSectionSize(70)

        layout.addWidget(self.table_turbines)

    def _init_tab_sector(self):
        """Pestaña «Por sector»: rosa de pérdidas por dirección.

        Solo se construye si los datos están disponibles. Si no, no se añade tab.
        Requiere matplotlib; si no está disponible, la pestaña no se añade.
        """
        r = self.results or {}
        wd = r.get("sector_directions_deg")
        wake_per_wd = r.get("aep_per_wd_wake_MWh")
        free_per_wd = r.get("aep_per_wd_free_MWh")

        # Si no hay datos por sector, no añadir la pestaña. Evitamos `if not array`
        # porque con numpy arrays puede lanzar ValueError.
        if wd is None or wake_per_wd is None or free_per_wd is None:
            return
        if len(wd) == 0 or len(wd) != len(wake_per_wd) or len(wd) != len(free_per_wd):
            return

        try:
            import matplotlib
            try:
                # Backend Qt para incrustar la figura en el diálogo
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:  # nosec B110
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            import numpy as np
        except Exception as e:
            # Si matplotlib no está disponible, no construir tab
            _debug_print(f"[Results] No se pudo importar matplotlib para rosa de sectores: {e}")
            return

        self.tab_sector_scroll, self.tab_sector = self._make_scroll_tab()
        layout = QtWidgets.QVBoxLayout(self.tab_sector)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Cabecera explicativa breve
        intro = QtWidgets.QLabel(_tr(
            "<b>Rosa de pérdidas por sector.</b> Distribución del AEP bruto y neto por "
            "dirección del viento. La diferencia entre cada barra es la pérdida total en ese sector "
            "(estelas, turbulencia y bloqueo), con su signo: negativa si el sector gana producción."
        ) if result_schema(r) == 2 else _tr(
            "<b>Rosa de pérdidas por sector.</b> Distribución del AEP bruto y neto por "
            "dirección del viento. La diferencia entre cada barra representa las pérdidas "
            "por estela en ese sector — útil para ver qué direcciones limitan más el "
            "rendimiento del parque."
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #4f5d6b;")
        layout.addWidget(intro)

        # Figura matplotlib con dos subplots: rosa polar + barras de pérdidas
        wd_arr = np.asarray(wd, dtype=float)
        free_arr = np.asarray(free_per_wd, dtype=float)
        wake_arr = np.asarray(wake_per_wd, dtype=float)
        # Schema 2: the gross minus the net of each sector is the total loss (wakes, turbulence and blockage), with
        # its sign: a sector that gains is not clipped to zero (#75, row 4.11).
        v2 = result_schema(r) == 2
        loss_arr = (free_arr - wake_arr) if v2 else np.maximum(free_arr - wake_arr, 0.0)
        loss_name = _tr("Pérdida total") if v2 else _tr("Pérdidas por estela")
        with np.errstate(divide="ignore", invalid="ignore"):
            # Schema 2: a percentage over a gross AEP that is not positive is not available (P0, section 8), never 0.
            loss_pct = np.where(free_arr > 0, 100.0 * loss_arr / free_arr, np.nan if v2 else 0.0)

        # Totales por sector y contraste con el resumen global.
        sum_free = float(np.nansum(free_arr))
        sum_net = float(np.nansum(wake_arr))
        sum_loss = float(np.nansum(loss_arr))
        global_free = float(r.get("aep_free_MWh", 0.0) or 0.0)
        global_net = float(r.get("aep_wake_MWh", r.get("aep_op_MWh", r.get("aep_MWh", 0.0))) or 0.0)
        d_free = sum_free - global_free if global_free > 0 else 0.0
        d_net = sum_net - global_net if global_net > 0 else 0.0
        tol = max(1.0, 0.001 * max(abs(global_net), abs(sum_net), 1.0))
        ok_txt = "OK" if abs(d_net) <= tol else _tr("revisar")
        if non_finite_label(sum_net) or non_finite_label(global_net):  # #63: a NaN is never «OK»
            ok_txt = _tr("no comparable: valor no finito")
        total_lbl = QtWidgets.QLabel(_tr(
            "<b>Total sectores:</b> AEP bruto {gross} MWh · AEP neto {net} MWh · pérdidas {loss} MWh. "
            "Comparación con resumen: Δ neto = {delta} MWh ({check})."
        ).format(gross=_fmt_mwh(sum_free), net=_fmt_mwh(sum_net), loss=_fmt_mwh(sum_loss), delta=_fmt_mwh(d_net),
                 check=ok_txt))
        mark_translated(total_lbl)  # composed with data: apply_i18n would translate it a second time
        total_lbl.setWordWrap(True)
        total_lbl.setStyleSheet("color: #4f5d6b; background: #f7f9fb; border: 1px solid #d8e0e8; padding: 6px;")
        layout.addWidget(total_lbl)

        try:
            fig = plt.Figure(figsize=(10, 5), tight_layout=True)
            # Subplot 1: rosa polar (AEP free vs neto)
            ax1 = fig.add_subplot(1, 2, 1, projection="polar")
            theta = np.deg2rad(wd_arr)
            width = (2 * np.pi) / max(len(wd_arr), 1)
            ax1.set_theta_zero_location("N")
            ax1.set_theta_direction(-1)  # convención meteorológica (CW desde N)
            ax1.bar(theta, free_arr, width=width, alpha=0.45,
                    color="#1f7dc2", edgecolor="white", linewidth=0.5,
                    label=_tr("AEP bruto"))
            ax1.bar(theta, wake_arr, width=width, alpha=0.85,
                    color="#103b67", edgecolor="white", linewidth=0.5,
                    label=_tr("AEP neto"))
            ax1.set_title(_tr("AEP por dirección [MWh]"), fontsize=11, color="#103b67")
            ax1.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=8)

            # Subplot 2: pérdidas % por sector (barras lineales)
            ax2 = fig.add_subplot(1, 2, 2)
            ax2.bar(wd_arr, loss_pct, width=max(width * 360 / (2 * np.pi) * 0.9, 1.0),
                    color="#b8860b", alpha=0.85, edgecolor="white", linewidth=0.5)
            ax2.set_xlabel(_tr("Dirección [°]"), fontsize=10)
            ax2.set_ylabel(f"{loss_name} [%]", fontsize=10)
            ax2.set_title(_tr("Pérdida total por sector") if v2 else _tr("Pérdidas por estela por sector"),
                          fontsize=11, color="#103b67")
            ax2.set_xlim(0, 360)
            ax2.grid(True, alpha=0.3, linestyle=":")
            ax2.tick_params(labelsize=9)

            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(260)
            canvas.setMaximumHeight(520)
            canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            layout.addWidget(canvas, 1)
        except Exception as e:
            _debug_print(f"[Results] Error renderizando rosa de sectores: {e}")
            err_lbl = QtWidgets.QLabel(_tr("No se pudo generar la rosa de sectores: {error}").format(error=e))
            mark_translated(err_lbl)
            err_lbl.setStyleSheet("color: #b00;")
            layout.addWidget(err_lbl)
            return

        # Tabla numérica complementaria
        tbl = QtWidgets.QTableWidget(len(wd_arr) + 1, 5, self.tab_sector)
        self.table_sector = tbl
        tbl.setHorizontalHeaderLabels([
            "Dirección [°]",
            "AEP bruto [MWh]",
            "AEP neto [MWh]",
            "Pérd. total [MWh]" if v2 else "Pérd. estela [MWh]",
            "Pérd. total [%]" if v2 else "Pérd. estela [%]",
        ])
        tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for i in range(len(wd_arr)):
            tbl.setItem(i, 0, QtWidgets.QTableWidgetItem(format_number(wd_arr[i], '.1f')))
            tbl.setItem(i, 1, QtWidgets.QTableWidgetItem(_fmt_mwh(float(free_arr[i]))))
            tbl.setItem(i, 2, QtWidgets.QTableWidgetItem(_fmt_mwh(float(wake_arr[i]))))
            tbl.setItem(i, 3, QtWidgets.QTableWidgetItem((_fmt_signed_mwh if v2 else _fmt_mwh)(float(loss_arr[i]))))
            pct_text = (_tr("n/d") if v2 and not np.isfinite(loss_pct[i])
                        else (_fmt_signed_pct if v2 else _fmt_pct)(float(loss_pct[i])))
            tbl.setItem(i, 4, QtWidgets.QTableWidgetItem(pct_text))
        total_row = len(wd_arr)
        total_loss_pct = (100.0 * sum_loss / sum_free) if sum_free > 0 else (None if v2 else 0.0)
        total_values = ["TOTAL", _fmt_mwh(sum_free), _fmt_mwh(sum_net), _fmt_mwh(sum_loss),
                        _tr("n/d") if total_loss_pct is None else _fmt_pct(total_loss_pct)]
        for col, val in enumerate(total_values):
            item = QtWidgets.QTableWidgetItem(str(val))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            if col > 0:
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            tbl.setItem(total_row, col, item)
        tbl.setMinimumHeight(150)
        tbl.setMaximumHeight(260)
        tbl.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        layout.addWidget(tbl)

        self.tabs.addTab(self.tab_sector_scroll, "Por sector")

    # ---------------------------------------------------------
    #  Rellenar datos
    # ---------------------------------------------------------
    def _populate(self):
        self._populate_global()
        self._populate_models()
        self._populate_turbines()
        self._populate_report()

    def _populate_global(self):
        r = self.results or {}
        coverage = partial_aep_warning(r, _tr)
        self.lbl_coverage_warning.setText(coverage)
        self.lbl_coverage_warning.setVisible(bool(coverage))
        if result_schema(r) == 2:
            return self._populate_global_v2()
        self.lbl_schema_note.setText(_tr(SCHEMA_1_NOTE))
        self.lbl_schema_note.setVisible(True)

        # AEP global (claves de aep_compute.py)
        aep_free = float(r.get("aep_free_MWh", 0.0) or 0.0)
        aep_net = float(
            r.get("aep_wake_MWh", r.get("aep_op_MWh", r.get("aep_MWh", 0.0))) or 0.0
        )

        # Pérdidas globales. TI/turbulencia se trata como impacto firmado: puede
        # reducir AEP o aumentar la recuperación de estela según modelo/configuración.
        loss_wake = float(r.get("wake_loss_MWh", r.get("loss_wake_MWh", 0.0)) or 0.0)
        loss_ti = float(r.get("loss_ti_MWh", 0.0) or 0.0)
        loss_blk = float(r.get("loss_blk_MWh", 0.0) or 0.0)
        ti_impact = None
        if r.get("ti_impact_MWh") is not None:
            try:
                ti_impact = float(r.get("ti_impact_MWh"))
            except Exception:
                ti_impact = None
        elif loss_ti:
            ti_impact = -float(loss_ti)
        ti_loss_component = max(-ti_impact, 0.0) if ti_impact is not None else loss_ti

        if aep_free <= 0.0 and aep_net > 0.0:
            aep_free = aep_net + loss_wake + ti_loss_component + loss_blk

        loss_known = loss_wake + ti_loss_component + loss_blk
        loss_other = max(aep_free - aep_net - loss_known, 0.0)
        loss_total = aep_free - aep_net if aep_free > 0 else loss_known + loss_other

        base = aep_free if aep_free > 0 else (aep_net + loss_total if aep_net > 0 else 0.0)

        def pct(x):
            if base <= 0:
                return 0.0
            return 100.0 * x / base

        # Info per-turbina para CF y potencia instalada
        per_turb = r.get("per_turbine_table", []) or []
        n_turb = len(per_turb)
        p_inst_mw = sum(_extract_rated_mw(rec) for rec in per_turb)

        # Fallback robusto: si la suma por turbina da 0 (porque turbine_ui no guarda
        # `p_rated_*` en meta y la inferencia desde wt.power() ha fallado), reconstruir
        # la potencia instalada como sum( P_nom_modelo × n_turbinas_modelo ) usando
        # los datos por modelo que ya calcula el core.
        if p_inst_mw <= 0:
            per_model_inst = r.get("per_model_p_inst_MW") or {}
            if per_model_inst:
                try:
                    p_inst_mw = float(sum(float(v or 0.0) for v in per_model_inst.values()))
                except Exception:
                    p_inst_mw = 0.0
            # Si el core es viejo y no expone per_model_p_inst_MW, reconstruirlo aquí
            if p_inst_mw <= 0:
                per_model_rated = r.get("per_model_p_rated_MW") or {}
                if per_model_rated and per_turb:
                    try:
                        from collections import Counter
                        counts = Counter(rec.get("model") for rec in per_turb)
                        p_inst_mw = float(sum(
                            float(per_model_rated.get(m, 0.0) or 0.0) * cnt
                            for m, cnt in counts.items()
                        ))
                    except Exception:  # nosec B110
                        pass

        cf_net = None
        spec_yield = None
        if p_inst_mw > 0 and aep_net > 0:
            cf_net = 100.0 * (aep_net / (p_inst_mw * self.HOURS_YEAR))
            spec_yield = aep_net / p_inst_mw  # MWh/MW·año

        # Rellenar etiquetas
        self.lbl_aep_free.setText(f"{_fmt_mwh(aep_free)} MWh")
        self.lbl_aep_net.setText(f"{_fmt_mwh(aep_net)} MWh")

        self.lbl_loss_wake.setText(
            f"{_fmt_mwh(loss_wake)} MWh ({_fmt_pct(pct(loss_wake))})"
        )
        if ti_impact is not None:
            self.lbl_loss_ti.setText(
                f"{_fmt_signed_mwh(ti_impact)} MWh ({_fmt_signed_pct(pct(ti_impact))})"
            )
        else:
            self.lbl_loss_ti.setText("n/d")
        self.lbl_loss_blk.setText(
            f"{_fmt_mwh(loss_blk)} MWh ({_fmt_pct(pct(loss_blk))})"
        )
        # "Otras pérdidas" es un residuo (aep_free - aep_net - wake - TI - blk).
        # Con la decomposición correcta de variantes ese residuo debería ser
        # ~0; lo dejamos visible solo cuando supere un umbral mínimo (>0.5 MWh
        # y >0.05% del bruto), para no inducir a leerlo como una partida real.
        residual_threshold_mwh = 0.5
        residual_threshold_pct = 0.05
        show_other = (
            loss_other > residual_threshold_mwh
            and pct(loss_other) > residual_threshold_pct
        )
        if show_other:
            self.lbl_loss_other.setText(
                f"{_fmt_mwh(loss_other)} MWh ({_fmt_pct(pct(loss_other))})"
            )
            self.lbl_loss_other.setVisible(True)
            if getattr(self, "lbl_loss_other_title", None) is not None:
                self.lbl_loss_other_title.setVisible(True)
        else:
            self.lbl_loss_other.setVisible(False)
            if getattr(self, "lbl_loss_other_title", None) is not None:
                self.lbl_loss_other_title.setVisible(False)
        self.lbl_loss_total.setText(
            f"{_fmt_mwh(loss_total)} MWh ({_fmt_pct(pct(loss_total))})"
        )

        self.lbl_n_turb.setText(format_number(n_turb, ",d"))
        self.lbl_p_inst_mw.setText(f"{_fmt_mw(p_inst_mw)} MW" if p_inst_mw > 0 else "-")

        if cf_net is not None:
            self.lbl_cf_net.setText(_fmt_pct(cf_net))
        else:
            self.lbl_cf_net.setText("-")

        if spec_yield is not None:
            self.lbl_spec_yield.setText(f"{_fmt_mwh(spec_yield)} {_tr('MWh/MW·año')}")
        else:
            self.lbl_spec_yield.setText("-")

        self._populate_global_balance_chart(
            aep_free=aep_free,
            aep_net=aep_net,
            loss_wake=loss_wake,
            loss_ti=ti_loss_component,
            loss_blk=loss_blk,
            loss_other=loss_other,
            loss_total=loss_total,
        )

    def _populate_global_balance_chart(self, aep_free: float, aep_net: float, loss_wake: float, loss_ti: float, loss_blk: float, loss_other: float, loss_total: float) -> None:
        """Dibuja un pequeño balance visual AEP bruto = neto + pérdidas."""
        layout = getattr(self, "balance_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        balance = aep_net + loss_total
        delta = balance - aep_free if aep_free > 0 else 0.0
        tol = max(1.0, 0.001 * max(abs(aep_free), abs(balance), 1.0))
        ok = abs(delta) <= tol
        lbl = QtWidgets.QLabel(_tr(
            "Bruto: <b>{gross} MWh</b> · Neto + pérdidas: <b>{balance} MWh</b> · Δ = {delta} MWh ({check})"
        ).format(gross=_fmt_mwh(aep_free), balance=_fmt_mwh(balance), delta=_fmt_mwh(delta),
                 check="OK" if ok else _tr("revisar")))
        mark_translated(lbl)  # composed with data: apply_i18n would translate it a second time
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #4f5d6b;")
        layout.addWidget(lbl)

        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:  # nosec B110
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        except Exception as e:
            err = QtWidgets.QLabel(_tr("No se pudo generar el gráfico total: {error}").format(error=e))
            mark_translated(err)
            err.setWordWrap(True)
            err.setStyleSheet("color: #b00;")
            layout.addWidget(err)
            return

        try:
            fig = plt.Figure(figsize=(5.0, 3.4), tight_layout=True)
            ax = fig.add_subplot(1, 1, 1)
            x = [0, 1, 2]
            labels = [_tr("Bruto"), _tr("Neto+pérd."), _tr("Neto")]
            ax.bar([x[0]], [aep_free], label=_tr("AEP bruto"))
            ax.bar([x[1]], [aep_net], label=_tr("AEP neto"))
            ax.bar([x[1]], [loss_wake], bottom=[aep_net], label=_tr("Estelas"))
            ax.bar([x[1]], [loss_ti], bottom=[aep_net + loss_wake], label=_tr("TI"))
            ax.bar([x[1]], [loss_blk], bottom=[aep_net + loss_wake + loss_ti], label=_tr("Bloqueo"))
            # Solo apilamos "Otras" si el residuo es perceptible. Con la
            # decomposición correcta es ~0 y añadir una barra de altura 0 mete
            # ruido en la leyenda.
            _balance_base = max(abs(aep_free), abs(aep_net), 1.0)
            if loss_other > 0.5 and (loss_other / _balance_base) > 5e-4:
                ax.bar([x[1]], [loss_other], bottom=[aep_net + loss_wake + loss_ti + loss_blk], label=_tr("Otras"))
            ax.bar([x[2]], [aep_net], label=_tr("AEP neto final"))
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.set_ylabel(_tr("MWh/año"))
            ax.set_title(_tr("Comprobación del balance total"))
            ax.grid(True, axis="y", alpha=0.25, linestyle=":")
            ax.legend(fontsize=8)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(220)
            canvas.setMaximumHeight(360)
            canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            layout.addWidget(canvas, 1)
        except Exception as e:
            err = QtWidgets.QLabel(_tr("No se pudo renderizar el balance total: {error}").format(error=e))
            mark_translated(err)
            err.setWordWrap(True)
            err.setStyleSheet("color: #b00;")
            layout.addWidget(err)

    def _populate_models(self):
        r = self.results or {}
        if result_schema(r) == 2:
            return self._populate_models_v2()

        per_aep = r.get("per_model_aep_MWh", {}) or {}
        per_aep_free = r.get("per_model_aep_free_MWh", {}) or {}
        per_loss_wake = r.get("per_model_loss_wake_MWh", {}) or {}
        per_loss_blk = r.get("per_model_loss_blk_MWh", {}) or {}
        per_loss_ti = r.get("per_model_loss_ti_MWh", {}) or {}
        per_ti_impact = r.get("per_model_ti_impact_MWh", {}) or {}

        per_model_n = r.get("per_model_n_turbines", {}) or {}
        if not per_model_n:
            per_model_n = r.get("model_counts_inside", {}) or {}

        per_model_p_inst = r.get("per_model_p_inst_MW", {}) or {}
        per_model_geom = r.get("per_model_geom", {}) or {}

        # Modelos presentes en cualquiera de los diccionarios
        models = sorted(set(
            list(per_aep.keys())
            + list(per_aep_free.keys())
            + list(per_loss_wake.keys())
            + list(per_loss_blk.keys())
            + list(per_loss_ti.keys())
            + list(per_model_n.keys())
            + list(per_model_p_inst.keys())
            + list(per_model_geom.keys())
        ))

        if not models:
            self.table_models.setRowCount(0)
            return

        self.table_models.setRowCount(len(models))

        for row, model in enumerate(models):
            aep_n = float(per_aep.get(model, 0.0) or 0.0)
            aep_b = float(per_aep_free.get(model, 0.0) or 0.0)
            lw = float(per_loss_wake.get(model, 0.0) or 0.0)
            lb = float(per_loss_blk.get(model, 0.0) or 0.0)
            lt_loss = float(per_loss_ti.get(model, 0.0) or 0.0)
            if model in per_ti_impact and per_ti_impact.get(model) is not None:
                try:
                    lt_signed = float(per_ti_impact.get(model))
                except Exception:
                    lt_signed = -lt_loss if lt_loss else 0.0
            else:
                lt_signed = -lt_loss if lt_loss else 0.0
            lt = max(-lt_signed, 0.0)
            n_t = int(per_model_n.get(model, 0) or 0)
            p_inst_mw = float(per_model_p_inst.get(model, 0.0) or 0.0)

            # Geometría del modelo
            geom = per_model_geom.get(model, {}) or {}
            D = geom.get("D") or geom.get("diameter") or geom.get("diam")
            HH = geom.get("HH") or geom.get("hub_height") or geom.get("hh")

            base = aep_b if aep_b > 0 else (aep_n + lw + lb + lt)

            def pct(x):
                if base <= 0:
                    return 0.0
                return 100.0 * x / base

            cf_net = None
            spec_yield = None
            if p_inst_mw > 0 and aep_n > 0:
                cf_net = 100.0 * (aep_n / (p_inst_mw * self.HOURS_YEAR))
                spec_yield = aep_n / p_inst_mw

            values = [
                model,
                _fmt_len(D) if D not in (None, "") else "-",
                _fmt_len(HH) if HH not in (None, "") else "-",
                format_number(n_t, ",d") if n_t > 0 else "",
                _fmt_mw(p_inst_mw) if p_inst_mw > 0 else "",
                _fmt_mwh(aep_b),
                _fmt_mwh(aep_n),
                _fmt_mwh(lw),
                _fmt_mwh(lb),
                _fmt_signed_mwh(lt_signed),
                _fmt_pct(cf_net) if cf_net is not None else "-",
                _fmt_mwh(spec_yield) if spec_yield is not None else "-",
                format_number(pct(lw), '.1f') if base > 0 else "-",
            ]

            for col, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(val))
                # Columna 0 (nombre) a la izquierda, resto numéricas a la derecha
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                else:
                    self._name_items.append((item, str(val)))
                self.table_models.setItem(row, col, item)

        self.table_models.resizeRowsToContents()

    def _populate_turbines(self):
        """
        Rellena la tabla por aerogenerador usando las claves REALES de per_turbine_table
        definidas en aep_compute.py:
          - aep_mwh          -> AEP neto (con estelas)
          - aep_free_mwh     -> AEP bruto (free-stream)
          - loss_wake_mwh    -> pérdida de estela
          - loss_blk_mwh     -> pérdida de bloqueo (muy pequeña normalmente)
        """
        r = self.results or {}
        per_turb = r.get("per_turbine_table", []) or []

        if not per_turb:
            self.table_turbines.setRowCount(0)
            return
        if result_schema(r) == 2:
            return self._populate_turbines_v2()

        self.table_turbines.setRowCount(len(per_turb))

        for row, rec in enumerate(per_turb):
            # ID
            tid = rec.get("id", rec.get("turbine_id", row + 1))
            # Modelo
            model = (
                rec.get("model")
                or rec.get("wt_name")
                or rec.get("turbine_type")
                or ""
            )
            # Coordenadas
            x = _extract_coord(rec, ["x", "X", "easting", "Easting", "lon", "longitude"])
            y = _extract_coord(rec, ["y", "Y", "northing", "Northing", "lat", "latitude"])

            # Potencia nominal
            p_nom_mw = _extract_rated_mw(rec)

            # AEP por turbina (neto/bruto) usando tus claves
            aep_net = float(
                rec.get("aep_mwh", rec.get("aep_wake_MWh", rec.get("aep_MWh", 0.0)))
                or 0.0
            )
            aep_b = float(
                rec.get("aep_free_mwh", rec.get("aep_free_MWh", 0.0)) or 0.0
            )

            # Pérdidas estela y bloqueo por turbina (si existen)
            loss_wake = float(
                rec.get("loss_wake_mwh", rec.get("loss_wake_MWh", 0.0)) or 0.0
            )
            loss_blk = float(
                rec.get("loss_blk_mwh", rec.get("loss_blk_MWh", 0.0)) or 0.0
            )

            # Si no tenemos AEP bruto, lo reconstruimos aproximado
            if aep_b <= 0.0 and aep_net > 0.0:
                aep_b = aep_net + loss_wake + loss_blk

            # Si no tenemos pérdida de estela pero sí bruto/neto
            if loss_wake <= 0.0 and aep_b > aep_net > 0.0:
                # asumimos que la mayor parte es estela, bloqueo es muy pequeño
                loss_wake = aep_b - aep_net - loss_blk
                if loss_wake < 0:
                    loss_wake = 0.0

            # Factor de capacidad (si algún día añadimos p_nom_mw en per_turbine_table)
            cf = None
            if p_nom_mw > 0 and aep_net > 0:
                cf = 100.0 * (aep_net / (p_nom_mw * self.HOURS_YEAR))

            vals = [
                str(tid),
                str(model),
                format_number(x, ',.2f') if x == x else "",  # x==x comprueba no-NaN
                format_number(y, ',.2f') if y == y else "",
                _fmt_mw(p_nom_mw) if p_nom_mw > 0 else "",
                _fmt_mwh(aep_net),
                _fmt_mwh(aep_b),
                _fmt_mwh(loss_wake),
                _fmt_mwh(loss_blk),
                _fmt_pct(cf) if cf is not None else "-",
            ]

            for col, val in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(str(val))
                if col >= 2:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif col == 1:
                    self._name_items.append((item, str(val)))
                self.table_turbines.setItem(row, col, item)

        self.table_turbines.resizeRowsToContents()

    def _populate_report(self):
        """Texto estilo informe, similar a WAsP, con resumen global + clusters/modelos."""
        r = self.results or {}
        if result_schema(r) == 2:
            return self._populate_report_v2()

        def t(text):
            # Translated here: kept from the second translation of the report (_localized_report_html).
            return _slot(self._user_texts, _tr(text))

        # --- Global ---
        aep_free = float(r.get("aep_free_MWh", 0.0) or 0.0)
        aep_net = float(
            r.get("aep_wake_MWh", r.get("aep_op_MWh", r.get("aep_MWh", 0.0))) or 0.0
        )
        loss_wake = float(r.get("wake_loss_MWh", r.get("loss_wake_MWh", 0.0)) or 0.0)
        loss_ti = float(r.get("loss_ti_MWh", 0.0) or 0.0)
        loss_blk = float(r.get("loss_blk_MWh", 0.0) or 0.0)
        ti_impact = None
        if r.get("ti_impact_MWh") is not None:
            try:
                ti_impact = float(r.get("ti_impact_MWh"))
            except Exception:
                ti_impact = None
        elif loss_ti:
            ti_impact = -float(loss_ti)
        ti_loss_component = max(-ti_impact, 0.0) if ti_impact is not None else loss_ti

        if aep_free <= 0.0 and aep_net > 0.0:
            aep_free = aep_net + loss_wake + ti_loss_component + loss_blk

        loss_known = loss_wake + ti_loss_component + loss_blk
        loss_other = max(aep_free - aep_net - loss_known, 0.0)
        loss_total = aep_free - aep_net if aep_free > 0 else loss_known + loss_other

        base = aep_free if aep_free > 0 else (aep_net + loss_total if aep_net > 0 else 0.0)

        def pct(x):
            if base <= 0:
                return 0.0
            return 100.0 * x / base

        # CF y energía específica (pueden ser None si no hay potencia instalada)
        per_turb = r.get("per_turbine_table", []) or []
        p_inst_mw = sum(_extract_rated_mw(rec) for rec in per_turb)
        # Fallback robusto (mismo motivo que en _populate_global)
        if p_inst_mw <= 0:
            per_model_inst = r.get("per_model_p_inst_MW") or {}
            if per_model_inst:
                try:
                    p_inst_mw = float(sum(float(v or 0.0) for v in per_model_inst.values()))
                except Exception:
                    p_inst_mw = 0.0
            if p_inst_mw <= 0:
                per_model_rated = r.get("per_model_p_rated_MW") or {}
                if per_model_rated and per_turb:
                    try:
                        from collections import Counter
                        counts = Counter(rec.get("model") for rec in per_turb)
                        p_inst_mw = float(sum(
                            float(per_model_rated.get(m, 0.0) or 0.0) * cnt
                            for m, cnt in counts.items()
                        ))
                    except Exception:  # nosec B110
                        pass
        cf_net = None
        spec_yield = None
        if p_inst_mw > 0 and aep_net > 0:
            cf_net = 100.0 * (aep_net / (p_inst_mw * self.HOURS_YEAR))
            spec_yield = aep_net / p_inst_mw

        # --- Info por modelo / cluster ---
        per_aep = r.get("per_model_aep_MWh", {}) or {}
        per_aep_free = r.get("per_model_aep_free_MWh", {}) or {}
        per_loss_wake_m = r.get("per_model_loss_wake_MWh", {}) or {}
        per_loss_ti_m = r.get("per_model_loss_ti_MWh", {}) or {}
        per_ti_impact_m = r.get("per_model_ti_impact_MWh", {}) or {}
        per_loss_blk_m = r.get("per_model_loss_blk_MWh", {}) or {}

        per_model_n = r.get("per_model_n_turbines", {}) or {}
        if not per_model_n:
            per_model_n = r.get("model_counts_inside", {}) or {}

        per_model_geom = r.get("per_model_geom", {}) or {}

        model_names = sorted(set(
            list(per_aep.keys())
            + list(per_aep_free.keys())
            + list(per_model_n.keys())
        ))

        clusters_html = ""
        if model_names:
            if len(model_names) == 1:
                # Un único modelo -> texto más compacto
                m = model_names[0]
                n_t = int(per_model_n.get(m, 0) or 0)
                geom = per_model_geom.get(m, {}) or {}
                D = geom.get("D") or geom.get("diameter") or None
                HH = geom.get("HH") or geom.get("hub_height") or None

                clusters_html += f"<h4>{t('Modelo de aerogenerador')}</h4><p>"
                clusters_html += (f"<b>{_slot(self._user_texts, m)}</b>: "
                                  f"{_slot(self._user_texts, _tr('{n} aerogenerador(es)').format(n=format_number(n_t, ',d')))}")
                extra = []
                if D:
                    extra.append(f"D = {_fmt_len(D)} m")
                if HH:
                    extra.append(f"{t('Altura de buje')} = {_fmt_len(HH)} m")
                if extra:
                    clusters_html += " (" + ", ".join(extra) + ")"
                clusters_html += "</p>"
            else:
                # Varios modelos -> resumen por cluster
                clusters_html += f"<h4>{t('Modelos / clusters de aerogeneradores')}</h4><ul>"
                for m in model_names:
                    n_t = int(per_model_n.get(m, 0) or 0)
                    geom = per_model_geom.get(m, {}) or {}
                    D = geom.get("D") or geom.get("diameter") or None
                    HH = geom.get("HH") or geom.get("hub_height") or None

                    aep_b_m = float(per_aep_free.get(m, 0.0) or 0.0)
                    aep_n_m = float(per_aep.get(m, 0.0) or 0.0)
                    lw_m = float(per_loss_wake_m.get(m, 0.0) or 0.0)
                    lt_m = float(per_loss_ti_m.get(m, 0.0) or 0.0)
                    lb_m = float(per_loss_blk_m.get(m, 0.0) or 0.0)

                    base_m = aep_b_m if aep_b_m > 0 else (aep_n_m + lw_m + lt_m + lb_m)
                    loss_tot_m = max(base_m - aep_n_m, 0.0) if base_m > 0 else 0.0
                    share = 100.0 * aep_n_m / aep_net if (aep_net > 0 and aep_n_m > 0) else 0.0
                    loss_pct_m = 100.0 * loss_tot_m / base_m if base_m > 0 else 0.0

                    clusters_html += "<li>"
                    clusters_html += (f"<b>{_slot(self._user_texts, m)}</b> – "
                                      f"{_slot(self._user_texts, _tr('{n} aerogenerador(es)').format(n=format_number(n_t, ',d')))}")
                    extras = []
                    if D:
                        extras.append(f"D = {_fmt_len(D)} m")
                    if HH:
                        extras.append(f"{t('Altura de buje')} = {_fmt_len(HH)} m")
                    if extras:
                        clusters_html += " (" + ", ".join(extras) + ")"
                    clusters_html += "<br>"
                    clusters_html += "&nbsp;&nbsp;" + _slot(self._user_texts, _tr(
                        "AEP neto del cluster: {aep} MWh").format(aep=_fmt_mwh(aep_n_m)))
                    if share > 0.0:
                        clusters_html += " (" + _slot(self._user_texts, _tr(
                            "{pct} % del AEP neto del parque").format(pct=format_number(share, '.1f'))) + ")"
                    if loss_tot_m > 0.0:
                        clusters_html += "<br>"
                        clusters_html += "&nbsp;&nbsp;" + _slot(self._user_texts, _tr(
                            "Pérdida total (estelas/TI/bloqueo): {loss} MWh ({pct} % sobre AEP bruto del cluster)"
                        ).format(loss=_fmt_mwh(loss_tot_m), pct=format_number(loss_pct_m, '.1f')))
                    clusters_html += "</li>"
                clusters_html += "</ul>"

        # --- Configuración del cálculo ---
        sim_notes = r.get("simulation_notes", []) or []

        notes_html = ""
        if sim_notes:
            items = ''.join(f"<li>{_note_html(self._user_texts, n)}</li>" for n in sim_notes if str(n).strip())
            if items:
                notes_html = f"<h4>{t('Notas físicas y de compatibilidad')}</h4><ul>{items}</ul>"

        # Banner TI fallback: muy visible, NO enterrado en la lista de notas
        ti_banner = ""
        if r.get("ti_fallback_10pct"):
            try:
                ti_pct = float(r.get("ti_fallback_percent", r.get("ambient_ti_fallback_percent", 10.0)) or 10.0)
            except Exception:
                ti_pct = 10.0
            ti_banner = (
                "<p style='background:#fff8e6;border:1px solid #e0c36d;border-radius:6px;padding:8px;'>"
                f"<b>{t('Aviso de TI ambiente:')}</b> " + _slot_html(self._user_texts, _tr(
                    "no se ha proporcionado un ráster de TI. El cálculo ha usado <b>TI = {ti} %</b> uniforme como "
                    "valor de respaldo. Este valor afecta directamente al AEP con los modelos de estela que dependen "
                    "de la TI (Niayifar, Zong, TurboGaussian, TurboNOJ). Para resultados representativos, carga un "
                    "ráster de TI en la sección de recurso o revisa la sensibilidad de turbulencia."
                ).format(ti=format_number(ti_pct, '.1f'))) + "</p>"
            )

        # Bloque "Métricas adicionales" — solo se muestra si tenemos potencia instalada
        # útil; si no, todo serían placeholders y no aporta nada al informe.
        if p_inst_mw and p_inst_mw > 0:
            extras_html = f"""
        <h4>{t('Métricas adicionales')}</h4>
        <ul>
          <li><b>{t('Potencia instalada:')}</b> {_fmt_mw(p_inst_mw)} MW</li>
          <li><b>{t('Factor de capacidad neto:')}</b> {_fmt_pct(cf_net) if cf_net is not None else "-"} </li>
          <li><b>{t('Energía específica neta:')}</b> {_fmt_mwh(spec_yield) if spec_yield is not None else "-"} {t('MWh/MW·año')}</li>
        </ul>
"""
        else:
            extras_html = (
                "<p style='color:#888; font-style:italic;'>"
                "<small>" + t("Métricas adicionales no disponibles: no se pudo determinar la potencia "
                              "nominal de las turbinas. Vuelve a definir el modelo desde «Definir…» para que "
                              "la curva de potencia se guarde con la metadata.") + "</small></p>"
            )

        # "Otras pérdidas" en el HTML solo cuando el residuo sea numéricamente
        # relevante (>0.5 MWh y >0.05% del bruto). En el camino normal con
        # variantes la decomposición wake/TI/bloqueo cierra el balance y este
        # residuo es ~0; mostrarlo a 0,0 invita a leerlo como una partida real.
        _residual_threshold_mwh = 0.5
        _residual_threshold_pct = 0.05
        if loss_other > _residual_threshold_mwh and pct(loss_other) > _residual_threshold_pct:
            loss_other_html = (
                f"<li><b>{t('Otras pérdidas:')}</b> {_fmt_mwh(loss_other)} MWh "
                f"({_fmt_pct(pct(loss_other))})</li>"
            )
        else:
            loss_other_html = ""

        # Keep the user-data-bearing banner out of the translation pipeline:
        # the report is localized again for the full HTML and export. Static
        # text is translated first; the banner is only inserted afterwards.
        coverage_banner = (
            self._COVERAGE_PLACEHOLDER
            if int(r.get("skipped_outside_grid") or 0) > 0 else ""
        )

        # --- HTML final ---
        report_body = f"""
        {self._report_header_html()}
        <div style="border-left:4px solid #24584d; padding-left:10px; margin-bottom:10px;">
          <h3 style="margin-bottom:4px;">{t('Resumen AEP del parque')}</h3>
          <div style="color:#6b7d78; font-size:11px;">{t('Informe técnico generado desde el módulo Energía de Velantis Wind.')}</div>
        </div>
        {coverage_banner}
        <p style="background:#eef1f5;border:1px solid #b9c4d0;padding:6px;">{t(SCHEMA_1_NOTE)}</p>
        {_slot_html(self._user_texts, model_config_html(r, _tr))}
        {ti_banner}
        <table width="100%" cellspacing="0" cellpadding="6" style="border-collapse:collapse; margin:8px 0 12px 0;">
          <tr style="background:#eef5f2;">
            <td><b>{t('AEP bruto (flujo libre)')}</b></td>
            <td align="right">{_fmt_mwh(aep_free)} MWh</td>
          </tr>
          <tr>
            <td><b>{t('AEP neto (operativo)')}</b></td>
            <td align="right">{_fmt_mwh(aep_net)} MWh</td>
          </tr>
          <tr style="background:#eef5f2;">
            <td><b>{t('Pérdidas totales')}</b></td>
            <td align="right">{_fmt_mwh(loss_total)} MWh ({_fmt_pct(pct(loss_total))})</td>
          </tr>
        </table>
        <h4>{t('Desglose de pérdidas')}</h4>
        <ul>
          <li><b>{t('Estelas:')}</b> {_fmt_mwh(loss_wake)} MWh ({_fmt_pct(pct(loss_wake))})</li>
          <li><b>{t('Impacto TI/turbulencia:')}</b> {(_fmt_signed_mwh(ti_impact) + " MWh (" + _fmt_signed_pct(pct(ti_impact)) + ")") if ti_impact is not None else t("n/d")}<br><small>{t('Diagnóstico incremental: positivo = recupera AEP frente al caso con solo estelas; negativo = reduce AEP. No se debe interpretar siempre como pérdida contable.')}</small></li>
          <li><b>{t('Bloqueo:')}</b> {_fmt_mwh(loss_blk)} MWh ({_fmt_pct(pct(loss_blk))})</li>
          {loss_other_html}
        </ul>
        {extras_html}
        {notes_html}
        {clusters_html}
        """

        self._last_report_html_raw = report_body
        self._last_report_html = self._insert_coverage_banner(_fill_slots(self._user_texts, _localized_report_html(report_body)))
        self.txt_report.setHtml(self._last_report_html)


    # ------------------------------------------------------------------------------------------------------------
    # Schema 2 (the signed breakdown of the wake-model plan, P0 section 8; closes #58). A schema-1 result keeps the
    # methods above, with its own fields.
    # ------------------------------------------------------------------------------------------------------------
    _GLOBAL_TITLES_V2 = (
        ("lbl_aep_free", "<b>AEP bruto (A_0, sin estelas ni bloqueo):</b>"),
        ("lbl_aep_net", "<b>AEP neto (configuración calculada):</b>"),
        ("lbl_loss_wake", "Pérdida por estelas (L_W):"),
        ("lbl_loss_ti", "Impacto de la turbulencia añadida (Δ_T):"),
        ("lbl_loss_blk", "Impacto del bloqueo (Δ_B):"),
        ("lbl_loss_other", "Interacción turbulencia-bloqueo (diagnóstico, fuera del balance):"),
        ("lbl_loss_total", "<b>Pérdida total (L_total = L_W − Δ_T − Δ_B):</b>"),
    )

    def _installed_mw(self, r: Dict[str, Any]) -> float:
        per_model_inst = r.get("per_model_p_inst_MW") or {}
        try:
            return float(sum(float(v or 0.0) for v in per_model_inst.values()))
        except Exception:
            return 0.0

    def _show_wake_configuration(self) -> None:
        """The identification, the warnings and the executed configuration of a result of schema 2 (hidden else)."""
        r = self.results or {}
        wc = r.get("wake_config") if result_schema(r) == 2 else None
        warnings = [str(shown(w, _tr)) for w in result_warnings(r)] if wc else []
        self.lbl_wake_id.setText(str(shown(wc.get("identification") or "", _tr)) if wc else "")
        self.lbl_wake_id.setVisible(bool(wc))
        # Rich text: the line breaks inside a warning (a reason of a convergence warning) kept, as in plain text.
        self.lbl_wake_warnings.setText("<br>".join("⚠ " + linked(w).replace("\n", "<br>") for w in warnings))
        self.lbl_wake_warnings.setVisible(bool(warnings))
        self.txt_executed.setHtml(model_config_html_v2(r, _tr) if wc else "")
        self.sec_executed.setVisible(bool(wc))

    def _populate_global_v2(self) -> None:
        r = self.results or {}
        b = r.get("breakdown") or {}
        self._show_wake_configuration()
        for title_lbl, widget in self._global_rows:
            for attr, text in self._GLOBAL_TITLES_V2:
                if widget is getattr(self, attr, None):
                    title_lbl.setText(_tr(text))
        aep_net = float(r.get("aep_wake_MWh") or 0.0)
        self.lbl_aep_free.setText(_term_text(b["A_0"], signed=False))
        self.lbl_aep_net.setText(f"{_fmt_mwh(aep_net)} MWh")
        self.lbl_loss_wake.setText(_term_text(b["L_W"]))
        self.lbl_loss_ti.setText(_term_text(b["D_T"]))
        self.lbl_loss_blk.setText(_term_text(b["D_B"]))
        interaction = b.get("I_TB") or {}
        show_interaction = interaction.get("state") != _bd.NOT_MODELLED
        self.lbl_loss_other.setText(_term_text(interaction) if show_interaction else "")
        self.lbl_loss_other.setVisible(show_interaction)
        if self.lbl_loss_other_title is not None:
            self.lbl_loss_other_title.setVisible(show_interaction)
        self.lbl_loss_total.setText(_term_text(b["L_total"]))
        per_turb = r.get("per_turbine_table", []) or []
        self.lbl_n_turb.setText(format_number(len(per_turb), ",d"))
        p_inst_mw = self._installed_mw(r)
        self.lbl_p_inst_mw.setText(f"{_fmt_mw(p_inst_mw)} MW" if p_inst_mw > 0 else "-")
        hours = float(r.get("hours_per_year") or self.HOURS_YEAR)
        if p_inst_mw > 0:
            self.lbl_cf_net.setText(_fmt_pct(100.0 * aep_net / (p_inst_mw * hours)))
            self.lbl_spec_yield.setText(f"{_fmt_mwh(aep_net / p_inst_mw)} {_tr('MWh/MW·año')}")
        else:
            self.lbl_cf_net.setText("-")
            self.lbl_spec_yield.setText("-")
        self._populate_balance_chart_v2(b, aep_net)

    def _populate_balance_chart_v2(self, b: Dict[str, Any], aep_net: float) -> None:
        """The balance A_0 − L_W + Δ_T + Δ_B = net, as a waterfall with the sign of each term (#75, row 4.10)."""
        layout = getattr(self, "balance_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        values = {t: b[t]["mwh"] for t in ("A_0", "L_W", "D_T", "D_B")}
        if values["A_0"] is None or values["L_W"] is None:
            lbl = QtWidgets.QLabel(_tr("El balance no se puede dibujar: falta el AEP bruto o la pérdida por estelas."))
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            return
        steps = [(_tr("Estelas"), -values["L_W"])]
        if b["D_T"]["state"] != _bd.NOT_MODELLED and values["D_T"] is not None:
            steps.append((_tr("Turbulencia"), values["D_T"]))
        if b["D_B"]["state"] != _bd.NOT_MODELLED and values["D_B"] is not None:
            steps.append((_tr("Bloqueo"), values["D_B"]))
        end = values["A_0"] + sum(v for _n, v in steps)
        delta = end - aep_net
        ok = abs(delta) <= max(1e-6, 1e-9 * max(abs(aep_net), 1.0))
        missing = [n for n, t in ((_tr("turbulencia"), "D_T"), (_tr("bloqueo"), "D_B"))
                   if b[t]["state"] not in (_bd.NOT_MODELLED, _bd.OK, _bd.ZERO_BY_CONSTRUCTION)]
        text = (f"{_tr('Bruto')} {_fmt_mwh(values['A_0'])} MWh " + " ".join(
            (f"{'+' if v >= 0 else '−'} {n} {_fmt_mwh(abs(v))}" if not non_finite_label(v) else f"{n} {_fmt_mwh(v)}")
            for n, v in steps)
                + f" = {_fmt_mwh(end)} MWh · {_tr('Neto')} {_fmt_mwh(aep_net)} MWh · Δ = {_fmt_signed_mwh(delta)} MWh ")
        if non_finite_label(delta):  # #63: a balance with a value that is not finite is not checked
            text += f"({_tr('no comparable: valor no finito')})"
        else:
            text += (f"({'OK' if ok else _tr('revisar')})" if not missing
                     else f"({_tr('incompleto')}: {', '.join(missing)})")
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #4f5d6b;")
        layout.addWidget(lbl)
        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:  # nosec B110
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            fig = plt.Figure(figsize=(5.0, 3.4), tight_layout=True)
            ax = fig.add_subplot(1, 1, 1)
            labels = [_tr("Bruto")] + [n for n, _v in steps] + [_tr("Neto")]
            ax.bar([0], [values["A_0"]], color="#1f7dc2")
            level = values["A_0"]
            for i, (_n, v) in enumerate(steps, start=1):
                ax.bar([i], [abs(v)], bottom=[min(level, level + v)], color="#2e8b57" if v >= 0 else "#b8860b")
                level += v
            ax.bar([len(steps) + 1], [aep_net], color="#103b67")
            ax.set_xticks(list(range(len(labels))))
            ax.set_xticklabels(labels)
            ax.set_ylabel(_tr("MWh/año"))
            ax.set_title(_tr("Comprobación del balance total"))
            ax.grid(True, axis="y", alpha=0.25, linestyle=":")
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(220)
            canvas.setMaximumHeight(360)
            layout.addWidget(canvas, 1)
        except Exception as e:
            err = QtWidgets.QLabel(_tr("No se pudo renderizar el balance total: {error}").format(error=e))
            mark_translated(err)
            err.setWordWrap(True)
            layout.addWidget(err)

    _MODEL_HEADERS_V2 = ["Modelo", "D [m]", "Altura de buje [m]", "Nº turbinas", "Potencia inst. [MW]", "AEP bruto [MWh]",
                         "AEP neto [MWh]", "Pérd. estelas L_W [MWh]", "Impacto turb. Δ_T [MWh]",
                         "Impacto bloqueo Δ_B [MWh]", "Pérd. total [MWh]", "FC neto [%]", "AEP/MW [MWh/MW·año]",
                         "Pérd. estelas L_W [%]"]

    def _populate_models_v2(self) -> None:
        r = self.results or {}
        per_model = r.get("per_model_breakdown") or {}
        counts = r.get("per_model_n_turbines") or {}
        p_inst = r.get("per_model_p_inst_MW") or {}
        geoms = r.get("per_model_geom") or {}
        self.table_models.setColumnCount(len(self._MODEL_HEADERS_V2))
        self.table_models.setHorizontalHeaderLabels([_tr(h) for h in self._MODEL_HEADERS_V2])
        self.table_models.setRowCount(len(per_model))
        hours = float(r.get("hours_per_year") or self.HOURS_YEAR)
        for row, (model, e) in enumerate(per_model.items()):
            geom = geoms.get(model, {}) or {}
            net = e["A_WTB"]["mwh"]
            mw = float(p_inst.get(model, 0.0) or 0.0)
            values = [
                model,
                _fmt_len(geom.get("D")) if geom.get("D") not in (None, "") else "-",
                _fmt_len(geom.get("HH")) if geom.get("HH") not in (None, "") else "-",
                format_number(int(counts.get(model, 0) or 0), ",d"),
                _fmt_mw(mw) if mw > 0 else "",
                _term_cell(e["A_0"], signed=False), _term_cell(e["A_WTB"], signed=False),
                _term_cell(e["L_W"]), _term_cell(e["D_T"]), _term_cell(e["D_B"]), _term_cell(e["L_total"]),
                _fmt_pct(100.0 * net / (mw * hours)) if mw > 0 and net is not None else "-",
                _fmt_mwh(net / mw) if mw > 0 and net is not None else "-",
                _fmt_signed_pct(e["L_W"]["pct"]) if e["L_W"]["pct"] is not None else _tr("n/d"),
            ]
            for col, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(val))
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                else:
                    self._name_items.append((item, str(val)))
                self.table_models.setItem(row, col, item)
        self.table_models.resizeRowsToContents()

    _TURBINE_HEADERS_V2 = ["ID", "Modelo", "X", "Y", "P_nom [MW]", "AEP neto [MWh]", "AEP bruto [MWh]",
                           "Pérd. estelas L_W [MWh]", "Impacto turb. Δ_T [MWh]", "Impacto bloqueo Δ_B [MWh]",
                           "Pérd. total [MWh]", "TI ambiente", "TI efectiva", "FC neto [%]"]

    def _populate_turbines_v2(self) -> None:
        r = self.results or {}
        rows = r.get("per_turbine_table", []) or []
        self.table_turbines.setColumnCount(len(self._TURBINE_HEADERS_V2))
        self.table_turbines.setHorizontalHeaderLabels([_tr(h) for h in self._TURBINE_HEADERS_V2])
        # Each TI says how it is aggregated (decision 21), as this result recorded it.
        for key, header in (("ti_ambient", "TI ambiente"), ("ti_effective", "TI efectiva")):
            aggregation = (r.get("ti_aggregation") or {}).get(key)
            item = self.table_turbines.horizontalHeaderItem(self._TURBINE_HEADERS_V2.index(header))
            if item is not None and aggregation:
                item.setToolTip(_tr(aggregation))
        self.table_turbines.setRowCount(len(rows))
        hours = float(r.get("hours_per_year") or self.HOURS_YEAR)

        def cell(v, signed=True):
            return _tr("n/d") if v is None else (_fmt_signed_mwh if signed else _fmt_mwh)(v)

        for row, rec in enumerate(rows):
            p_nom = float(rec.get("p_nom_mw") or 0.0)
            net = rec.get("aep_mwh")
            vals = [
                str(rec.get("id", row + 1)), str(rec.get("model") or ""),
                format_number(float(rec['x']), ',.2f'), format_number(float(rec['y']), ',.2f'),
                _fmt_mw(p_nom) if p_nom > 0 else "",
                cell(net, signed=False), cell(rec.get("aep_free_mwh"), signed=False),
                cell(rec.get("l_wake_mwh")), cell(rec.get("d_turb_mwh")), cell(rec.get("d_blk_mwh")),
                cell(rec.get("l_total_mwh")),
                format_number(rec['ti_ambient'], '.4f') if rec.get("ti_ambient") is not None else _tr("n/d"),
                format_number(rec['ti_effective'], '.4f') if rec.get("ti_effective") is not None else _tr("n/d"),
                _fmt_pct(100.0 * net / (p_nom * hours)) if p_nom > 0 and net is not None else "-",
            ]
            for col, val in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(str(val))
                if col >= 2:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif col == 1:
                    self._name_items.append((item, str(val)))
                self.table_turbines.setItem(row, col, item)
        self.table_turbines.resizeRowsToContents()

    def _populate_report_v2(self) -> None:
        r = self.results or {}
        b = r.get("breakdown") or {}

        def t(text):
            # A text translated here, kept from the second translation of the report (_localized_report_html).
            return _slot(self._user_texts, text)
        rows = [("AEP bruto (A_0, sin estelas ni bloqueo)", b["A_0"], False),
                ("AEP neto (configuración calculada)", b["A_WTB"], False),
                ("Pérdida por estelas (L_W = A_0 − A_W)", b["L_W"], True),
                ("Impacto de la turbulencia añadida (Δ_T = A_WT − A_W)", b["D_T"], True),
                ("Impacto del bloqueo (Δ_B = A_WTB − A_WT)", b["D_B"], True),
                ("Pérdida total (L_total = A_0 − A_WTB = L_W − Δ_T − Δ_B)", b["L_total"], True)]
        table = "".join(
            f"<tr><td><b>{t(_tr(label))}</b></td><td align='right'>{t(_term_text(e, s))}</td></tr>"
            for label, e, s in rows)
        interaction = ""
        if b.get("I_TB", {}).get("state") != _bd.NOT_MODELLED:
            interaction = (f"<p><small>{t(_tr('Interacción turbulencia-bloqueo (diagnóstico, fuera del balance):'))} "
                           f"{t(_term_text(b['I_TB']))}</small></p>")
        sign_note = _tr("Con signo: una pérdida (L) positiva resta producción; un impacto (Δ) positivo la suma. "
                        "Los porcentajes son sobre el AEP bruto. Un término no disponible no se cuenta como cero.")
        # Translated already (the errors of PyWake and of the physics): kept from the second pass of the report.
        errors = "".join(_slot_html(self._user_texts,
                                    f"<li>{html_mod.escape(term)}: {html_mod.escape(str(shown(e.get('error'), _tr)))}</li>")
                         for term, e in b.items() if isinstance(e, dict) and e.get("error"))
        errors_html = f"<h4>{t(_tr('Variantes que no se pudieron calcular'))}</h4><ul>{errors}</ul>" if errors else ""
        models = ""
        per_model = r.get("per_model_breakdown") or {}
        if len(per_model) > 1:
            items = "".join(
                f"<li><b>{_slot(self._user_texts, m)}</b>: {t(_tr('AEP neto'))} {_fmt_mwh(e['A_WTB']['mwh'])} MWh · "
                f"L_W {t(_term_text(e['L_W']))} · Δ_T {t(_term_text(e['D_T']))} · "
                f"Δ_B {t(_term_text(e['D_B']))} · {t(_tr('Pérdida total'))} "
                f"{t(_term_text(e['L_total']))}</li>" for m, e in per_model.items())
            models = f"<h4>{t(_tr('Por modelo de aerogenerador'))}</h4><ul>{items}</ul>"
        notes = "".join(f"<li>{_note_html(self._user_texts, n)}</li>" for n in (r.get("simulation_notes") or []) if str(n).strip())
        notes_html = f"<h4>{t(_tr('Notas físicas y de compatibilidad'))}</h4><ul>{notes}</ul>" if notes else ""
        coverage_banner = self._COVERAGE_PLACEHOLDER if int(r.get("skipped_outside_grid") or 0) > 0 else ""
        report_body = f"""
        {self._report_header_html()}
        <div style="border-left:4px solid #24584d; padding-left:10px; margin-bottom:10px;">
          <h3 style="margin-bottom:4px;">{t(_tr('Resumen AEP del parque'))}</h3>
          <div style="color:#6b7d78; font-size:11px;">{t(_tr('Informe técnico generado desde el módulo Energía de Velantis Wind.'))}</div>
        </div>
        {coverage_banner}
        {_slot_html(self._user_texts, model_config_html(r, _tr))}
        <h4>{t(_tr('Desglose de pérdidas'))}</h4>
        <table width="100%" cellspacing="0" cellpadding="6" style="border-collapse:collapse; margin:8px 0 12px 0;">{table}</table>
        <p><small>{t(sign_note)}</small></p>
        {interaction}
        {errors_html}
        {models}
        {notes_html}
        """
        self._last_report_html_raw = report_body
        self._last_report_html = self._insert_coverage_banner(_fill_slots(self._user_texts, _localized_report_html(report_body)))
        self.txt_report.setHtml(self._last_report_html)


class ScenarioComparisonDialog(QtWidgets.QDialog):
    """Comparador simple de dos resultados AEP guardados desde AEPSetupDialog."""

    HOURS_YEAR = 8760.0

    def _fit_dialog_to_screen(self, default_w: int = 980, default_h: int = 620) -> None:
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                w = max(520, min(int(default_w), int(geo.width() * 0.92)))
                h = max(360, min(int(default_h), int(geo.height() * 0.88)))
                min_w = min(520, max(420, int(geo.width() * 0.70)))
                min_h = min(360, max(320, int(geo.height() * 0.60)))
                self.resize(w, h)
                self.setMinimumSize(min_w, min_h)
                return
        except Exception:  # nosec B110
            pass
        self.resize(default_w, default_h)
        self.setMinimumSize(640, 420)

    def _make_scroll_tab(self) -> Tuple[QtWidgets.QScrollArea, QtWidgets.QWidget]:
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        content = QtWidgets.QWidget(scroll)
        content.setMinimumWidth(0)
        content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        scroll.setWidget(content)
        return scroll, content

    def __init__(self, parent=None, result_a: Dict[str, Any] = None, result_b: Dict[str, Any] = None, label_a: str = "Escenario A", label_b: str = "Escenario B"):
        super().__init__(parent)
        self.result_a = result_a or {}
        self.result_b = result_b or {}
        self.label_a = label_a or "Escenario A"
        self.label_b = label_b or "Escenario B"
        self._user_texts: List[str] = []
        self.setWindowTitle(_tr("Comparador de escenarios AEP"))
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._fit_dialog_to_screen(980, 620)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _summary_v2(self, r: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """The compared values of a schema-2 result: a term that is not available is ``None``, never zero."""
        b = r.get("breakdown") or {}
        net = float(r.get("aep_wake_MWh") or 0.0)
        p_inst = 0.0
        try:
            p_inst = float(sum(float(v or 0.0) for v in (r.get("per_model_p_inst_MW") or {}).values()))
        except Exception:  # nosec B110
            pass
        hours = float(r.get("hours_per_year") or 8760.0)
        return {
            "aep_net": net, "aep_free": b.get("A_0", {}).get("mwh"), "loss_total": b.get("L_total", {}).get("mwh"),
            "wake_loss": b.get("L_W", {}).get("mwh"), "ti_impact": b.get("D_T", {}).get("mwh"),
            "blk_loss": b.get("D_B", {}).get("mwh"), "n_turb": float(len(r.get("per_turbine_table") or [])),
            # A net AEP of zero has a capacity factor of zero (only its relative change is not available).
            "p_inst": p_inst, "cf_net": 100.0 * net / (p_inst * hours) if p_inst > 0 and hours > 0 else None,
        }

    def _summary(self, r: Dict[str, Any]) -> Dict[str, float]:
        if result_schema(r) == 2:
            return self._summary_v2(r)
        aep_free = float(r.get("aep_free_MWh", 0.0) or 0.0)
        aep_net = float(r.get("aep_wake_MWh", r.get("aep_op_MWh", r.get("aep_MWh", 0.0))) or 0.0)
        wake_loss = float(r.get("wake_loss_MWh", r.get("loss_wake_MWh", 0.0)) or 0.0)
        blk_loss = float(r.get("loss_blk_MWh", 0.0) or 0.0)
        ti_loss = float(r.get("loss_ti_MWh", 0.0) or 0.0)
        ti_impact = None
        if r.get("ti_impact_MWh") is not None:
            try:
                ti_impact = float(r.get("ti_impact_MWh"))
            except Exception:
                ti_impact = None
        elif ti_loss:
            ti_impact = -ti_loss
        loss_total = (aep_free - aep_net) if aep_free > 0 else (wake_loss + blk_loss + max(-(ti_impact or 0.0), 0.0))
        per_turb = r.get("per_turbine_table", []) or []
        n_turb = len(per_turb)
        p_inst = 0.0
        per_model_inst = r.get("per_model_p_inst_MW") or {}
        if per_model_inst:
            try:
                p_inst = float(sum(float(v or 0.0) for v in per_model_inst.values()))
            except Exception:
                p_inst = 0.0
        if p_inst <= 0.0:
            p_inst = sum(_extract_rated_mw(rec) for rec in per_turb)
        try:
            hours_year = float(r.get("hours_per_year", 8760.0) or 8760.0)
        except Exception:
            hours_year = 8760.0
        cf_net = 100.0 * aep_net / (p_inst * hours_year) if p_inst > 0 and aep_net > 0 else 0.0
        return {
            "aep_free": aep_free,
            "aep_net": aep_net,
            "loss_total": loss_total,
            "wake_loss": wake_loss,
            "ti_impact": ti_impact if ti_impact is not None else 0.0,
            "blk_loss": blk_loss,
            "n_turb": float(n_turb),
            "p_inst": p_inst,
            "cf_net": cf_net,
        }

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            _tr("<b>{a}</b> frente a <b>{b}</b>. El delta se calcula como B − A.").format(
                a=html_mod.escape(self.label_a), b=html_mod.escape(self.label_b)
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        old = [slot for slot, r in (("A", self.result_a), ("B", self.result_b)) if result_schema(r) != 2]
        if old:
            schema_note = QtWidgets.QLabel(_tr("{slot}: {text}").format(slot=", ".join(old), text=_tr(SCHEMA_1_NOTE)), self)
            schema_note.setWordWrap(True)
            schema_note.setStyleSheet("background:#eef1f5; color:#33414f; border:1px solid #b9c4d0; padding:8px;")
            layout.addWidget(schema_note)

        # A partial scenario was calculated with fewer turbines: its deltas compare different farms.
        coverage = []
        for slot, r in (("A", self.result_a), ("B", self.result_b)):
            text = partial_aep_warning(r, _tr)
            if text:
                coverage.append(_tr("{slot}: {text}").format(slot=slot, text=text))
        self.lbl_coverage_warning = None
        if coverage:
            self.lbl_coverage_warning = QtWidgets.QLabel("\n".join(coverage), self)
            # Model names are user data: show the notice as text, never interpreted HTML.
            self.lbl_coverage_warning.setTextFormat(QtCore.Qt.PlainText)
            self.lbl_coverage_warning.setWordWrap(True)
            self.lbl_coverage_warning.setStyleSheet(
                "background:#fff3d9; color:#6a3900; border:1px solid #d8a34c; padding:10px;"
            )
            layout.addWidget(self.lbl_coverage_warning)

        tabs = QtWidgets.QTabWidget(self)
        tabs.setMinimumWidth(0)
        tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(tabs, 1)

        tab_global_scroll, tab_global = self._make_scroll_tab()
        vg = QtWidgets.QVBoxLayout(tab_global)
        vg.setContentsMargins(8, 8, 8, 8)
        vg.setSpacing(8)
        tbl = QtWidgets.QTableWidget(tab_global)
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels([_tr("Métrica"), "A", "B", "Δ B−A", "Δ %"])
        tbl.setMinimumWidth(0)
        tbl.setWordWrap(False)
        tbl.setTextElideMode(QtCore.Qt.ElideRight)
        tbl.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        tbl.horizontalHeader().setDefaultSectionSize(120)
        tbl.horizontalHeader().setMinimumSectionSize(80)
        vg.addWidget(tbl, 1)
        self._fill_global_table(tbl)
        self._add_global_chart(vg)
        tabs.addTab(tab_global_scroll, _tr("Resumen delta"))

        tab_models_scroll, tab_models = self._make_scroll_tab()
        vm = QtWidgets.QVBoxLayout(tab_models)
        vm.setContentsMargins(8, 8, 8, 8)
        vm.setSpacing(8)
        tblm = QtWidgets.QTableWidget(tab_models)
        tblm.setColumnCount(6)
        tblm.setHorizontalHeaderLabels(
            [_tr("Modelo"), _tr("AEP neto A [MWh]"), _tr("AEP neto B [MWh]"), "Δ MWh", "Δ %", _tr("Nº turb. A/B")]
        )
        tblm.setMinimumWidth(0)
        tblm.setWordWrap(False)
        tblm.setTextElideMode(QtCore.Qt.ElideRight)
        tblm.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        tblm.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        tblm.horizontalHeader().setDefaultSectionSize(125)
        tblm.horizontalHeader().setMinimumSectionSize(80)
        vm.addWidget(tblm, 1)
        self._fill_models_table(tblm)
        tabs.addTab(tab_models_scroll, _tr("Por modelo"))

        tab_cfg_scroll, tab_cfg = self._make_scroll_tab()
        vc = QtWidgets.QVBoxLayout(tab_cfg)
        vc.setContentsMargins(8, 8, 8, 8)
        txt = QtWidgets.QTextBrowser(tab_cfg)
        txt.setOpenExternalLinks(True)
        txt.setHtml(_fill_slots(self._user_texts, translate_html(self._config_html())))
        vc.addWidget(txt, 1)
        tabs.addTab(tab_cfg_scroll, _tr("Configuración"))

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, QtCore.Qt.Horizontal, self)
        # A standard button follows the language of QGIS, not that of the plugin.
        btns.button(QtWidgets.QDialogButtonBox.Close).setText(_tr("Cerrar"))
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    def _fill_global_table(self, tbl: QtWidgets.QTableWidget) -> None:
        a = self._summary(self.result_a)
        b = self._summary(self.result_b)
        schemas = {result_schema(self.result_a), result_schema(self.result_b)}
        if 2 in schemas:
            rows = [
                ("AEP neto", "aep_net", "mwh"),
                ("AEP bruto", "aep_free", "mwh"),
                ("Pérdida total", "loss_total", "signed_mwh"),
                ("Pérdida por estelas (L_W)", "wake_loss", "signed_mwh"),
                ("Impacto de la turbulencia añadida (Δ_T)", "ti_impact", "signed_mwh"),
                ("Impacto del bloqueo (Δ_B)", "blk_loss", "signed_mwh"),
                ("Nº aerogeneradores", "n_turb", "num"),
                ("Potencia instalada", "p_inst", "mw"),
                ("Factor de capacidad neto", "cf_net", "pct"),
            ]
        else:
            rows = [
                ("AEP neto", "aep_net", "mwh"),
                ("AEP bruto", "aep_free", "mwh"),
                ("Pérdidas totales", "loss_total", "mwh"),
                ("Pérdidas por estela", "wake_loss", "mwh"),
                ("Impacto TI/turbulencia", "ti_impact", "signed_mwh"),
                ("Pérdidas por bloqueo", "blk_loss", "mwh"),
                ("Nº aerogeneradores", "n_turb", "num"),
                ("Potencia instalada", "p_inst", "mw"),
                ("Factor de capacidad neto", "cf_net", "pct"),
            ]
        # Two schemas define the loss terms differently: only what means the same is compared.
        comparable = {"aep_net", "aep_free", "n_turb", "p_inst", "cf_net"}
        tbl.setRowCount(len(rows))
        for i, (label, key, kind) in enumerate(rows):
            raw_a, raw_b = a.get(key), b.get(key)
            if len(schemas) > 1 and key not in comparable:
                raw_a = raw_b = None
            if 2 in schemas and (raw_a is None or raw_b is None):
                # Not available is not zero: no delta and no -100 % (#75, row 4.13).
                missing = _tr("n/d")
                vals = [_tr(label), self._fmt_value(raw_a, kind) if raw_a is not None else missing,
                        self._fmt_value(raw_b, kind) if raw_b is not None else missing, missing, missing]
                for c, val in enumerate(vals):
                    it = QtWidgets.QTableWidgetItem(str(val))
                    if c > 0:
                        it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    tbl.setItem(i, c, it)
                continue
            va = float(raw_a or 0.0)
            vb = float(raw_b or 0.0)
            d = vb - va
            dp = (100.0 * d / va) if abs(va) > 1e-12 else 0.0
            if non_finite_label(va) or non_finite_label(vb):  # #63: never «0.0 %» with a value that is not finite
                dp = float("nan")
            pct_text = _fmt_signed_pct(dp) if (abs(va) > 1e-12 or 2 not in schemas or non_finite_label(dp)) else _tr("n/d")
            vals = [_tr(label), self._fmt_value(va, kind), self._fmt_value(vb, kind), self._fmt_value(d, "signed_mwh" if kind in ("mwh", "signed_mwh") else kind, signed=True), pct_text]
            for c, val in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(str(val))
                if c > 0:
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                tbl.setItem(i, c, it)
        tbl.resizeRowsToContents()

    def _fmt_value(self, v: float, kind: str, signed: bool = False) -> str:
        if kind == "mwh":
            return (_fmt_signed_mwh(v) if signed else _fmt_mwh(v)) + " MWh"
        if kind == "signed_mwh":
            return _fmt_signed_mwh(v) + " MWh"
        if kind == "mw":
            if signed:
                return (non_finite_label(v) or (("+" if v > 0 else "") + format_number(v, ",.3f"))) + " MW"
            return _fmt_mw(v) + " MW"
        if kind == "pct":
            return _fmt_signed_pct(v) if signed else _fmt_pct(v)
        if kind == "num":
            return format_number(v, "+,.0f" if signed else ",.0f")
        return str(v)

    def _add_global_chart(self, layout: QtWidgets.QVBoxLayout) -> None:
        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:  # nosec B110
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        except Exception:
            return
        try:
            a = self._summary(self.result_a)
            b = self._summary(self.result_b)
            # Only the metrics both scenarios have, with the same meaning: a missing one is not drawn as zero.
            same = result_schema(self.result_a) == result_schema(self.result_b)
            metrics = [(k, n) for k, n in (("aep_net", _tr("AEP neto")), ("loss_total", _tr("Pérd. total")),
                                           ("wake_loss", _tr("Pérdida por estelas")))
                       if a.get(k) is not None and b.get(k) is not None and (same or k == "aep_net")]
            fig = plt.Figure(figsize=(7.2, 2.4), tight_layout=True)
            ax = fig.add_subplot(1, 1, 1)
            xs = list(range(len(metrics)))
            ax.bar(xs, [a[k] for k, _n in metrics], width=0.35, label="A")
            ax.bar([x + 0.35 for x in xs], [b[k] for k, _n in metrics], width=0.35, label="B")
            ax.set_xticks([x + 0.175 for x in xs])
            ax.set_xticklabels([n for _k, n in metrics])
            ax.set_ylabel(_tr("MWh/año"))
            ax.set_title(_tr("Comparación global"))
            ax.grid(True, axis="y", alpha=0.25, linestyle=":")
            ax.legend(fontsize=8)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(200)
            canvas.setMaximumHeight(320)
            canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            layout.addWidget(canvas, 0)
        except Exception:
            return

    def _fill_models_table(self, tbl: QtWidgets.QTableWidget) -> None:
        pa = self.result_a.get("per_model_aep_MWh", {}) or {}
        pb = self.result_b.get("per_model_aep_MWh", {}) or {}
        na = self.result_a.get("per_model_n_turbines", self.result_a.get("model_counts_inside", {})) or {}
        nb = self.result_b.get("per_model_n_turbines", self.result_b.get("model_counts_inside", {})) or {}
        models = sorted(set(pa.keys()) | set(pb.keys()) | set(na.keys()) | set(nb.keys()))
        tbl.setRowCount(len(models))
        for i, m in enumerate(models):
            va = float(pa.get(m, 0.0) or 0.0)
            vb = float(pb.get(m, 0.0) or 0.0)
            d = vb - va
            dp = (100.0 * d / va) if abs(va) > 1e-12 else 0.0
            if non_finite_label(va) or non_finite_label(vb):  # #63: never «0.0 %» with a value that is not finite
                dp = float("nan")
            vals = [m, _fmt_mwh(va), _fmt_mwh(vb), _fmt_signed_mwh(d), _fmt_signed_pct(dp), f"{format_number(int(na.get(m,0) or 0), ',d')}/{format_number(int(nb.get(m,0) or 0), ',d')}"]
            for c, val in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(str(val))
                if c > 0:
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                tbl.setItem(i, c, it)
        tbl.resizeRowsToContents()

    def _config_html(self) -> str:
        colon = " :" if str(current_language()).lower().startswith("fr") else ":"

        def block(title: str, r: Dict[str, Any]) -> str:
            rows = []
            if r.get("wake_config"):
                # Schema 2: what was executed at the eight positions, the ground included (#75, row 6.5), with its
                # arguments and nodes (row 6.6); where it is not the user's selection, both; and its warnings.
                wc = r["wake_config"]
                selected, executed = wc.get("selected") or {}, wc.get("executed") or {}
                differing = {d.get("position") for d in wc.get("differences_vs_selection") or []}
                if wc.get("provenance"):  # a predefined model: its name first
                    rows.append("<li>" + html_mod.escape(str(shown(wc.get("identification") or "", _tr))) + "</li>")
                for position, label in POSITIONS_V2:
                    text = _component_text(executed.get(position), _tr)
                    if position in differing:
                        text = f"{_component_text(selected.get(position), _tr)} → {text} ⚠"
                    rows.append(f"<li><b>{html_mod.escape(_tr(label))}{colon}</b> {html_mod.escape(text)}</li>")
                if differing:
                    rows.append("<li>" + html_mod.escape(_tr("⚠: lo ejecutado difiere de la selección del usuario.")) + "</li>")
                for warning in result_warnings(r):
                    rows.append("<li>⚠ " + linked(shown(warning, _tr)) + "</li>")
                # Translated already: kept from the second translation of the comparator's HTML.
                rows = [_slot_html(self._user_texts, "".join(rows))]
            cfg = r.get("selection_executed", {}) or r.get("selection_requested", {}) or r.get("selection_user", {}) or {}
            # Schema 1: each position by its label, as the report names it.
            selection = "".join(f"<li><b>{html_mod.escape(_tr(label))}{colon}</b> {html_mod.escape(str(cfg.get(k)))}</li>"
                                for k, label in POSITIONS_V1 if k in cfg)
            if selection:
                rows.append(_slot_html(self._user_texts, selection))
            notes = r.get("simulation_notes", []) or []
            if notes:
                rows.append(f"<li><b>{_slot(self._user_texts, _tr('Notas:'))}</b><ul>"
                            + "".join(f"<li>{_note_html(self._user_texts, n)}</li>" for n in notes) + "</ul></li>")
            empty = f"<li>{_slot(self._user_texts, _tr('Sin configuración registrada'))}</li>"
            return f"<h3>{_slot(self._user_texts, title)}</h3><ul>{''.join(rows) or empty}</ul>"
        return block(self.label_a, self.result_a) + block(self.label_b, self.result_b)

