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

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtGui import QIcon, QPixmap
from .i18n import apply_i18n, install_runtime_i18n_patches, translate_html, tr_text as _tr


def _is_debug_enabled() -> bool:
    return str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}


def _debug_print(message: str) -> None:
    if _is_debug_enabled():
        print(message)


def _fmt_mwh(v) -> str:
    """Formatea MWh con un decimal, usando coma como separador decimal."""
    try:
        x = float(v)
    except Exception:
        return "-"
    # 12345.6 -> "12.345,6"
    txt = f"{x:,.1f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_mw(v) -> str:
    """Formatea MW con 3 decimales. Devuelve '-' si vale 0 o no se puede convertir,
    para evitar mostrar '0,000 MW' cuando en realidad la potencia no se pudo determinar.
    """
    try:
        x = float(v)
    except Exception:
        return "-"
    if x <= 0:
        return "-"
    txt = f"{x:,.3f}"
    return txt.replace(".", ",")


def _fmt_pct(v) -> str:
    """Formatea porcentaje con un decimal."""
    try:
        x = float(v)
    except Exception:
        return "-"
    return f"{x:.1f} %"


def _fmt_signed_mwh(v) -> str:
    """MWh con signo explícito para impactos incrementales."""
    try:
        x = float(v)
    except Exception:
        return "-"
    sign = "+" if x > 0 else ""
    return sign + _fmt_mwh(x)


def _fmt_signed_pct(v) -> str:
    try:
        x = float(v)
    except Exception:
        return "-"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.1f} %"


def _fmt_len(v) -> str:
    """Formatea longitudes (D, Hub) con 1 decimal y coma."""
    try:
        x = float(v)
    except Exception:
        return "-"
    txt = f"{x:.1f}"
    return txt.replace(".", ",")


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
            except Exception:
                pass

    for k in candidates_kw:
        if k in rec and rec[k] not in (None, ""):
            try:
                return float(rec[k]) / 1000.0
            except Exception:
                pass

    return 0.0


def _extract_coord(rec: Dict[str, Any], keys: List[str]) -> float:
    for k in keys:
        if k in rec and rec[k] not in (None, ""):
            try:
                return float(rec[k])
            except Exception:
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
        except Exception:
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
        return f'''
        <div style="border:1px solid #d8e2dc; border-radius:10px; padding:12px; margin-bottom:12px; background:#f8fbfa;">
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
            <tr>
              <td style="vertical-align:middle; width:70px;">{logo_html}</td>
              <td style="vertical-align:middle; text-align:left; color:#1f3d36;">
                <div style="font-size:18px; font-weight:700;">Informe técnico AEP</div>
                <div style="font-size:11px; color:#6b7d78;">Módulo Energía · Flujo PyWake · {html_mod.escape(generated)}</div>
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
            except Exception:
                pass
        # Last-mile report strings that come from runtime notes and can otherwise
        # remain half-translated in exported HTML.
        replacements = {
            "yes puede influir": "can influence",
            "active (": "active (",
            "vertical approximation": "vertical approximation",
            "se ha usado un único raster de ambient TI": "a single ambient TI raster was used",
            "si mezclas varios hub heights, esa TI se replica/interpela como vertical approximation": "if several hub heights are mixed, that TI is replicated/interpolated as a vertical approximation",
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
        """Wrap the AEP report as a standalone English HTML document."""
        doc = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Velantis Wind · AEP technical report</title>
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
<div class="vw-footer">Generated by Velantis Wind · QGIS energy module · PyWake-based AEP workflow.</div>
</body>
</html>'''
        return self._translate_html_to_en(doc)

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
        self._last_report_html = ""
        self._last_report_html_raw = ""

        self._init_ui()
        self._populate()
        apply_i18n(self)

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
        except Exception:
            pass

        # Botones abajo
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close,
            QtCore.Qt.Horizontal,
            self,
        )
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
                QtWidgets.QMessageBox.information(self, "Exportar CSV por turbina", "No hay datos por turbina para exportar.")
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Exportar CSV por turbina",
                "velantiswind_aep_per_turbine_summary.csv",
                "CSV (*.csv);;Todos los archivos (*)",
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                from .ag_core.qgis_io.export import export_per_turbine_to_csv
            except Exception:
                from .ag_core.export_results import export_per_turbine_to_csv
            export_per_turbine_to_csv(per_turb, path)
            QtWidgets.QMessageBox.information(self, "CSV exportado", f"CSV por turbina exportado correctamente:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "No se pudo exportar el CSV", f"No se pudo exportar el CSV por turbina:\n{e}")

    def _qtable_to_html(self, table: QtWidgets.QTableWidget, max_rows: Optional[int] = 500) -> str:
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
            return "<p><i>Sin datos disponibles.</i></p>"
        headers = []
        for c in range(cols):
            item = table.horizontalHeaderItem(c)
            headers.append(html_mod.escape(item.text() if item is not None else f"Col {c+1}"))
        html = ["<div class='table-wrap'><table class='data-table'><thead><tr>"]
        html.extend(f"<th>{h}</th>" for h in headers)
        html.append("</tr></thead><tbody>")
        n = rows if max_rows is None or int(max_rows) <= 0 else min(rows, int(max_rows))
        for r in range(n):
            html.append("<tr>")
            for c in range(cols):
                item = table.item(r, c)
                val = item.text() if item is not None else ""
                html.append(f"<td>{html_mod.escape(str(val))}</td>")
            html.append("</tr>")
        html.append("</tbody></table></div>")
        if max_rows is not None and int(max_rows) > 0 and rows > int(max_rows):
            html.append(f"<p><small>Table truncated in the HTML report: showing {max_rows} of {rows} rows. The CSV export contains the full detail.</small></p>")
        return "".join(html)

    def _global_kpi_html(self) -> str:
        rows = [
            ("AEP bruto (free-stream)", getattr(self, "lbl_aep_free", None)),
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
                if widget is not None and not widget.isVisible():
                    continue
            except Exception:
                pass
            try:
                value = widget.text() if widget is not None else "-"
            except Exception:
                value = "-"
            out.append(f"<tr><td><b>{html_mod.escape(label)}</b></td><td>{html_mod.escape(str(value))}</td></tr>")
        out.append("</table>")
        return "".join(out)

    def _build_full_report_html(self) -> str:
        """Informe HTML completo: resumen, pestaña por modelo, por turbina y por sector."""
        parts = []
        base_report = getattr(self, "_last_report_html_raw", "") or self._last_report_html or ""
        if base_report:
            parts.append(base_report)
        else:
            parts.append(self._report_header_html())
        parts.append("<h3>Resumen global</h3>")
        parts.append(self._global_kpi_html())
        parts.append("<h3>Por modelo de aerogenerador</h3>")
        parts.append(self._qtable_to_html(getattr(self, "table_models", None), max_rows=200))
        parts.append("<h3>Por aerogenerador</h3>")
        parts.append("<p><small>Esta tabla replica el resumen por turbina visible en la interfaz. Para análisis GIS/Excel, usa también el CSV por turbina que genera el flujo AEP.</small></p>")
        parts.append(self._qtable_to_html(getattr(self, "table_turbines", None), max_rows=500))
        sector_table = getattr(self, "table_sector", None)
        if sector_table is not None:
            parts.append("<h3>Por sector de viento</h3>")
            parts.append(self._qtable_to_html(sector_table, max_rows=None))
        joined = "\n".join(parts)
        # The exported report follows the language selected in the hub: the report
        # body is authored in Spanish, so only translate to English when needed.
        try:
            from . import i18n as _i18n
        except Exception:
            try:
                import i18n as _i18n  # type: ignore
            except Exception:
                _i18n = None  # type: ignore
        if _i18n is not None:
            try:
                if _i18n.is_spanish():
                    return joined
            except Exception:
                pass
        return self._translate_html_to_en(joined)

    def _export_report_html(self) -> None:
        """Exporta el informe AEP visual como HTML con cabecera corporativa."""
        try:
            default_name = "velantiswind_aep_technical_report.html"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Exportar informe AEP",
                default_name,
                "HTML (*.html);;Todos los archivos (*)",
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
                "Informe exportado",
                f"Informe AEP exportado correctamente:\n{path}",
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "No se pudo exportar el informe",
                f"No se pudo exportar el informe AEP:\n{e}",
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
            ("<b>AEP bruto (free-stream):</b>", self.lbl_aep_free),
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
        for title, value_widget in rows:
            title_lbl = QtWidgets.QLabel(title)
            title_lbl.setMinimumWidth(0)
            title_lbl.setWordWrap(True)
            form.addWidget(title_lbl, row, 0)
            form.addWidget(value_widget, row, 1)
            if value_widget is self.lbl_loss_other:
                self.lbl_loss_other_title = title_lbl
            row += 1

        layout.addWidget(group, 0)

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
            "Hub [m]",
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
        Requiere matplotlib (lo usa también graficar.py, así que está garantizado).
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
                # Backend Qt; el plugin ya lo fuerza en graficar.py
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:
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
        intro = QtWidgets.QLabel(
            "<b>Rosa de pérdidas por sector.</b> Distribución del AEP libre y neto por "
            "dirección del viento. La diferencia entre cada barra representa las pérdidas "
            "por estela en ese sector — útil para ver qué direcciones limitan más el "
            "rendimiento del parque."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #4f5d6b;")
        layout.addWidget(intro)

        # Figura matplotlib con dos subplots: rosa polar + barras de pérdidas
        wd_arr = np.asarray(wd, dtype=float)
        free_arr = np.asarray(free_per_wd, dtype=float)
        wake_arr = np.asarray(wake_per_wd, dtype=float)
        loss_arr = np.maximum(free_arr - wake_arr, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            loss_pct = np.where(free_arr > 0, 100.0 * loss_arr / free_arr, 0.0)

        # Totales por sector y contraste con el resumen global.
        sum_free = float(np.nansum(free_arr))
        sum_net = float(np.nansum(wake_arr))
        sum_loss = float(np.nansum(loss_arr))
        global_free = float(r.get("aep_free_MWh", 0.0) or 0.0)
        global_net = float(r.get("aep_wake_MWh", r.get("aep_op_MWh", r.get("aep_MWh", 0.0))) or 0.0)
        d_free = sum_free - global_free if global_free > 0 else 0.0
        d_net = sum_net - global_net if global_net > 0 else 0.0
        tol = max(1.0, 0.001 * max(abs(global_net), abs(sum_net), 1.0))
        ok_txt = "OK" if abs(d_net) <= tol else "revisar"
        total_lbl = QtWidgets.QLabel(
            f"<b>Total sectores:</b> AEP libre {_fmt_mwh(sum_free)} MWh · "
            f"AEP neto {_fmt_mwh(sum_net)} MWh · pérdidas {_fmt_mwh(sum_loss)} MWh. "
            f"Comparación con resumen: Δ neto = {_fmt_mwh(d_net)} MWh ({ok_txt})."
        )
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
                    label="AEP libre")
            ax1.bar(theta, wake_arr, width=width, alpha=0.85,
                    color="#103b67", edgecolor="white", linewidth=0.5,
                    label="AEP neto")
            ax1.set_title("AEP por dirección [MWh]", fontsize=11, color="#103b67")
            ax1.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=8)

            # Subplot 2: pérdidas % por sector (barras lineales)
            ax2 = fig.add_subplot(1, 2, 2)
            ax2.bar(wd_arr, loss_pct, width=max(width * 360 / (2 * np.pi) * 0.9, 1.0),
                    color="#b8860b", alpha=0.85, edgecolor="white", linewidth=0.5)
            ax2.set_xlabel("Dirección [°]", fontsize=10)
            ax2.set_ylabel("Pérdidas por estela [%]", fontsize=10)
            ax2.set_title("Pérdidas por estela por sector", fontsize=11, color="#103b67")
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
            err_lbl = QtWidgets.QLabel(f"No se pudo generar la rosa de sectores: {e}")
            err_lbl.setStyleSheet("color: #b00;")
            layout.addWidget(err_lbl)
            return

        # Tabla numérica complementaria
        tbl = QtWidgets.QTableWidget(len(wd_arr) + 1, 5, self.tab_sector)
        self.table_sector = tbl
        tbl.setHorizontalHeaderLabels([
            "Dirección [°]",
            "AEP libre [MWh]",
            "AEP neto [MWh]",
            "Pérd. estela [MWh]",
            "Pérd. estela [%]",
        ])
        tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for i in range(len(wd_arr)):
            tbl.setItem(i, 0, QtWidgets.QTableWidgetItem(f"{wd_arr[i]:.1f}"))
            tbl.setItem(i, 1, QtWidgets.QTableWidgetItem(_fmt_mwh(float(free_arr[i]))))
            tbl.setItem(i, 2, QtWidgets.QTableWidgetItem(_fmt_mwh(float(wake_arr[i]))))
            tbl.setItem(i, 3, QtWidgets.QTableWidgetItem(_fmt_mwh(float(loss_arr[i]))))
            tbl.setItem(i, 4, QtWidgets.QTableWidgetItem(_fmt_pct(float(loss_pct[i]))))
        total_row = len(wd_arr)
        total_loss_pct = (100.0 * sum_loss / sum_free) if sum_free > 0 else 0.0
        total_values = ["TOTAL", _fmt_mwh(sum_free), _fmt_mwh(sum_net), _fmt_mwh(sum_loss), _fmt_pct(total_loss_pct)]
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
                    except Exception:
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

        self.lbl_n_turb.setText(str(n_turb))
        self.lbl_p_inst_mw.setText(f"{_fmt_mw(p_inst_mw)} MW" if p_inst_mw > 0 else "-")

        if cf_net is not None:
            self.lbl_cf_net.setText(_fmt_pct(cf_net))
        else:
            self.lbl_cf_net.setText("-")

        if spec_yield is not None:
            self.lbl_spec_yield.setText(f"{_fmt_mwh(spec_yield)} MWh/MW·año")
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
        lbl = QtWidgets.QLabel(
            f"Bruto: <b>{_fmt_mwh(aep_free)} MWh</b> · Neto + pérdidas: "
            f"<b>{_fmt_mwh(balance)} MWh</b> · Δ = {_fmt_mwh(delta)} MWh "
            f"({'OK' if ok else 'revisar'})"
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #4f5d6b;")
        layout.addWidget(lbl)

        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        except Exception as e:
            err = QtWidgets.QLabel(f"No se pudo generar el gráfico total: {e}")
            err.setWordWrap(True)
            err.setStyleSheet("color: #b00;")
            layout.addWidget(err)
            return

        try:
            fig = plt.Figure(figsize=(5.0, 3.4), tight_layout=True)
            ax = fig.add_subplot(1, 1, 1)
            x = [0, 1, 2]
            labels = ["Bruto", "Neto+pérd.", "Neto"]
            ax.bar([x[0]], [aep_free], label="AEP bruto")
            ax.bar([x[1]], [aep_net], label="AEP neto")
            ax.bar([x[1]], [loss_wake], bottom=[aep_net], label="Estelas")
            ax.bar([x[1]], [loss_ti], bottom=[aep_net + loss_wake], label="TI")
            ax.bar([x[1]], [loss_blk], bottom=[aep_net + loss_wake + loss_ti], label="Bloqueo")
            # Solo apilamos "Otras" si el residuo es perceptible. Con la
            # decomposición correcta es ~0 y añadir una barra de altura 0 mete
            # ruido en la leyenda.
            _balance_base = max(abs(aep_free), abs(aep_net), 1.0)
            if loss_other > 0.5 and (loss_other / _balance_base) > 5e-4:
                ax.bar([x[1]], [loss_other], bottom=[aep_net + loss_wake + loss_ti + loss_blk], label="Otras")
            ax.bar([x[2]], [aep_net], label="AEP neto final")
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.set_ylabel("MWh/año")
            ax.set_title("Comprobación del balance total")
            ax.grid(True, axis="y", alpha=0.25, linestyle=":")
            ax.legend(fontsize=8)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(220)
            canvas.setMaximumHeight(360)
            canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            layout.addWidget(canvas, 1)
        except Exception as e:
            err = QtWidgets.QLabel(f"No se pudo renderizar el balance total: {e}")
            err.setWordWrap(True)
            err.setStyleSheet("color: #b00;")
            layout.addWidget(err)

    def _populate_models(self):
        r = self.results or {}

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
                str(n_t) if n_t > 0 else "",
                _fmt_mw(p_inst_mw) if p_inst_mw > 0 else "",
                _fmt_mwh(aep_b),
                _fmt_mwh(aep_n),
                _fmt_mwh(lw),
                _fmt_mwh(lb),
                _fmt_signed_mwh(lt_signed),
                _fmt_pct(cf_net) if cf_net is not None else "-",
                _fmt_mwh(spec_yield) if spec_yield is not None else "-",
                f"{pct(lw):.1f}" if base > 0 else "-",
            ]

            for col, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(val))
                # Columna 0 (nombre) a la izquierda, resto numéricas a la derecha
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
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
                f"{x:.2f}" if x == x else "",  # x==x comprueba no-NaN
                f"{y:.2f}" if y == y else "",
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
                self.table_turbines.setItem(row, col, item)

        self.table_turbines.resizeRowsToContents()

    def _populate_report(self):
        """Texto estilo informe, similar a WAsP, con resumen global + clusters/modelos."""
        r = self.results or {}

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
                    except Exception:
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

                clusters_html += "<h4>Modelo de aerogenerador</h4><p>"
                clusters_html += f"<b>{m}</b>: {n_t} aerogenerador(es)"
                extra = []
                if D:
                    extra.append(f"D = {_fmt_len(D)} m")
                if HH:
                    extra.append(f"Hub = {_fmt_len(HH)} m")
                if extra:
                    clusters_html += " (" + ", ".join(extra) + ")"
                clusters_html += "</p>"
            else:
                # Varios modelos -> resumen por cluster
                clusters_html += "<h4>Modelos / clusters de aerogeneradores</h4><ul>"
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
                    clusters_html += f"<b>{m}</b> – {n_t} aerogenerador(es)"
                    extras = []
                    if D:
                        extras.append(f"D = {_fmt_len(D)} m")
                    if HH:
                        extras.append(f"Hub = {_fmt_len(HH)} m")
                    if extras:
                        clusters_html += " (" + ", ".join(extras) + ")"
                    clusters_html += "<br>"
                    clusters_html += (
                        f"&nbsp;&nbsp;AEP neta del cluster: {_fmt_mwh(aep_n_m)} MWh"
                    )
                    if share > 0.0:
                        clusters_html += f" ({share:.1f} % del AEP neto del parque)"
                    if loss_tot_m > 0.0:
                        clusters_html += "<br>"
                        clusters_html += (
                            f"&nbsp;&nbsp;Pérdida total (wake/TI/bloqueo): "
                            f"{_fmt_mwh(loss_tot_m)} MWh ({loss_pct_m:.1f} % sobre AEP bruto del cluster)"
                        )
                    clusters_html += "</li>"
                clusters_html += "</ul>"

        # --- Configuración del cálculo ---
        sel_user = r.get("selection_user", {}) or {}
        sel_req = r.get("selection_requested", {}) or {}
        sel_exec = r.get("selection_executed", {}) or {}
        sim_notes = r.get("simulation_notes", []) or []
        sim_degraded = bool(r.get("simulation_degraded", False))
        sim_deg_label = r.get("simulation_degradation_label") or ""

        def cfg_block(title: str, cfg: Dict[str, Any]) -> str:
            if not cfg:
                return ""
            rows = []
            labels = {
                "engine": "Engine",
                "wake_deficit": "Wake deficit",
                "turbulence": "Modelo de turbulencia",
                "blockage": "Modelo de bloqueo",
                "rotor_avg": "Rotor-average",
                "superposition": "Superposición",
            }
            for key in ("engine", "wake_deficit", "turbulence", "blockage", "rotor_avg", "superposition"):
                if key in cfg:
                    rows.append(f"<li><b>{labels.get(key, key)}:</b> {html_mod.escape(str(cfg.get(key, '-')))}</li>")
            if not rows:
                return ""
            return f"<h4>{html_mod.escape(title)}</h4><ul>{''.join(rows)}</ul>"

        notes_html = ""
        if sim_notes:
            items = ''.join(f"<li>{html_mod.escape(str(n))}</li>" for n in sim_notes if str(n).strip())
            if items:
                notes_html = f"<h4>Notas físicas y de compatibilidad</h4><ul>{items}</ul>"

        exec_banner = ""
        if sim_degraded:
            if isinstance(sim_deg_label, str) and sim_deg_label.startswith("bloqueo alternativo:"):
                alt_name = sim_deg_label.split(":", 1)[1].strip() or "alternativo"
                msg = (
                    f"La combinación de wake TI-driven con SelfSimilarity2020 no convergió en "
                    f"PyWake. Se ha mantenido el bloqueo sustituyéndolo por {alt_name} "
                    f"(acoplamiento más estable). El resto de la selección se ha respetado."
                )
                exec_banner = f"<p style='background:#e6f4ea;border:1px solid #7fc89a;padding:8px;'><b>Sustitución de modelo de bloqueo:</b> {html_mod.escape(msg)}</p>"
            else:
                msg = "La simulación no pudo ejecutarse exactamente con la combinación pedida y PyWake requirió una degradación automática."
                if sim_deg_label:
                    msg += f" Paso aplicado: {sim_deg_label}."
                exec_banner = f"<p style='background:#fff3cd;border:1px solid #e0c36d;padding:8px;'><b>Aviso de compatibilidad:</b> {html_mod.escape(msg)}</p>"

        # Banner TI fallback: muy visible, NO enterrado en la lista de notas
        ti_banner = ""
        if r.get("ti_fallback_10pct"):
            try:
                ti_pct = float(r.get("ti_fallback_percent", r.get("ambient_ti_fallback_percent", 10.0)) or 10.0)
            except Exception:
                ti_pct = 10.0
            ti_banner = (
                "<p style='background:#fff8e6;border:1px solid #e0c36d;border-radius:6px;padding:8px;'>"
                "<b>Aviso de TI ambiente:</b> no se ha proporcionado un raster de TI. "
                f"El cálculo ha usado <b>TI = {ti_pct:.1f} %</b> uniforme como fallback. "
                "Este valor afecta directamente al AEP en wakes TI-driven (Niayifar, Zong, "
                "TurboGaussian, TurboNOJ). Para resultados representativos, carga un raster "
                "TI en la sección de recurso o revisa la sensibilidad de turbulencia.</p>"
            )

        # Bloque "Métricas adicionales" — solo se muestra si tenemos potencia instalada
        # útil; si no, todo serían placeholders y no aporta nada al informe.
        if p_inst_mw and p_inst_mw > 0:
            extras_html = f"""
        <h4>Métricas adicionales</h4>
        <ul>
          <li><b>Potencia instalada:</b> {_fmt_mw(p_inst_mw)} MW</li>
          <li><b>Factor de capacidad neto:</b> {_fmt_pct(cf_net) if cf_net is not None else "-"} </li>
          <li><b>Energía específica neta:</b> {_fmt_mwh(spec_yield) if spec_yield is not None else "-"} MWh/MW·año</li>
        </ul>
"""
        else:
            extras_html = (
                "<p style='color:#888; font-style:italic;'>"
                "<small>Métricas adicionales no disponibles: no se pudo determinar la potencia "
                "nominal de las turbinas. Vuelve a definir el modelo desde «Definir…» para que "
                "la curva de potencia se guarde con la metadata.</small></p>"
            )

        # "Otras pérdidas" en el HTML solo cuando el residuo sea numéricamente
        # relevante (>0.5 MWh y >0.05% del bruto). En el camino normal con
        # variantes la decomposición wake/TI/bloqueo cierra el balance y este
        # residuo es ~0; mostrarlo a 0,0 invita a leerlo como una partida real.
        _residual_threshold_mwh = 0.5
        _residual_threshold_pct = 0.05
        if loss_other > _residual_threshold_mwh and pct(loss_other) > _residual_threshold_pct:
            loss_other_html = (
                f"<li><b>Otras pérdidas:</b> {_fmt_mwh(loss_other)} MWh "
                f"({pct(loss_other):.1f} %)</li>"
            )
        else:
            loss_other_html = ""

        # --- HTML final ---
        report_body = f"""
        {self._report_header_html()}
        <div style="border-left:4px solid #24584d; padding-left:10px; margin-bottom:10px;">
          <h3 style="margin-bottom:4px;">Resumen AEP del parque</h3>
          <div style="color:#6b7d78; font-size:11px;">Informe técnico generado desde el módulo Energía de Velantis Wind.</div>
        </div>
        {exec_banner}
        {ti_banner}
        <table width="100%" cellspacing="0" cellpadding="6" style="border-collapse:collapse; margin:8px 0 12px 0;">
          <tr style="background:#eef5f2;">
            <td><b>AEP bruto (free-stream)</b></td>
            <td align="right">{_fmt_mwh(aep_free)} MWh</td>
          </tr>
          <tr>
            <td><b>AEP neto (operativo)</b></td>
            <td align="right">{_fmt_mwh(aep_net)} MWh</td>
          </tr>
          <tr style="background:#eef5f2;">
            <td><b>Pérdidas totales</b></td>
            <td align="right">{_fmt_mwh(loss_total)} MWh ({pct(loss_total):.1f} %)</td>
          </tr>
        </table>
        <h4>Desglose de pérdidas</h4>
        <ul>
          <li><b>Estelas:</b> {_fmt_mwh(loss_wake)} MWh ({pct(loss_wake):.1f} %)</li>
          <li><b>Impacto TI/turbulencia:</b> {(_fmt_signed_mwh(ti_impact) + " MWh (" + _fmt_signed_pct(pct(ti_impact)) + ")") if ti_impact is not None else "n/d"}<br><small>Diagnóstico incremental: positivo = recupera AEP frente al wake-only; negativo = reduce AEP. No se debe interpretar siempre como pérdida contable.</small></li>
          <li><b>Bloqueo:</b> {_fmt_mwh(loss_blk)} MWh ({pct(loss_blk):.1f} %)</li>
          {loss_other_html}
        </ul>
        {extras_html}
        {cfg_block("Selección del usuario", sel_user)}
        {cfg_block("Configuración solicitada al solver", sel_req)}
        {cfg_block("Configuración finalmente ejecutada", sel_exec)}
        {notes_html}
        {clusters_html}
        """

        self._last_report_html_raw = report_body
        self._last_report_html = translate_html(report_body)
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
        except Exception:
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
        self.setWindowTitle("Comparador de escenarios AEP")
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._fit_dialog_to_screen(980, 620)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _summary(self, r: Dict[str, Any]) -> Dict[str, float]:
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
        cf_net = 100.0 * aep_net / (p_inst * self.HOURS_YEAR) if p_inst > 0 and aep_net > 0 else 0.0
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
            f"<b>{html_mod.escape(self.label_a)}</b> frente a <b>{html_mod.escape(self.label_b)}</b>. "
            "El delta se calcula como B − A."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

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
        tbl.setHorizontalHeaderLabels(["Métrica", "A", "B", "Δ B−A", "Δ %"])
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
        tabs.addTab(tab_global_scroll, "Resumen delta")

        tab_models_scroll, tab_models = self._make_scroll_tab()
        vm = QtWidgets.QVBoxLayout(tab_models)
        vm.setContentsMargins(8, 8, 8, 8)
        vm.setSpacing(8)
        tblm = QtWidgets.QTableWidget(tab_models)
        tblm.setColumnCount(6)
        tblm.setHorizontalHeaderLabels(["Modelo", "AEP neto A [MWh]", "AEP neto B [MWh]", "Δ MWh", "Δ %", "Nº turb. A/B"])
        tblm.setMinimumWidth(0)
        tblm.setWordWrap(False)
        tblm.setTextElideMode(QtCore.Qt.ElideRight)
        tblm.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        tblm.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        tblm.horizontalHeader().setDefaultSectionSize(125)
        tblm.horizontalHeader().setMinimumSectionSize(80)
        vm.addWidget(tblm, 1)
        self._fill_models_table(tblm)
        tabs.addTab(tab_models_scroll, "Por modelo")

        tab_cfg_scroll, tab_cfg = self._make_scroll_tab()
        vc = QtWidgets.QVBoxLayout(tab_cfg)
        vc.setContentsMargins(8, 8, 8, 8)
        txt = QtWidgets.QTextBrowser(tab_cfg)
        txt.setHtml(translate_html(self._config_html()))
        vc.addWidget(txt, 1)
        tabs.addTab(tab_cfg_scroll, "Configuración")

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, QtCore.Qt.Horizontal, self)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    def _fill_global_table(self, tbl: QtWidgets.QTableWidget) -> None:
        a = self._summary(self.result_a)
        b = self._summary(self.result_b)
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
        tbl.setRowCount(len(rows))
        for i, (label, key, kind) in enumerate(rows):
            va = float(a.get(key, 0.0) or 0.0)
            vb = float(b.get(key, 0.0) or 0.0)
            d = vb - va
            dp = (100.0 * d / va) if abs(va) > 1e-12 else 0.0
            vals = [label, self._fmt_value(va, kind), self._fmt_value(vb, kind), self._fmt_value(d, "signed_mwh" if kind in ("mwh", "signed_mwh") else kind, signed=True), _fmt_signed_pct(dp)]
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
            return (_fmt_signed_mwh(v) if signed else _fmt_mw(v)) + " MW"
        if kind == "pct":
            return _fmt_signed_pct(v) if signed else _fmt_pct(v)
        if kind == "num":
            return f"{v:+.0f}" if signed else f"{v:.0f}"
        return str(v)

    def _add_global_chart(self, layout: QtWidgets.QVBoxLayout) -> None:
        try:
            import matplotlib
            try:
                if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
                    matplotlib.use("QtAgg", force=True)
            except Exception:
                pass
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        except Exception:
            return
        try:
            a = self._summary(self.result_a)
            b = self._summary(self.result_b)
            fig = plt.Figure(figsize=(7.2, 2.4), tight_layout=True)
            ax = fig.add_subplot(1, 1, 1)
            labels = ["AEP neto", "Pérd. total", "Wake"]
            ax.bar([0, 1, 2], [a["aep_net"], a["loss_total"], a["wake_loss"]], width=0.35, label="A")
            ax.bar([0.35, 1.35, 2.35], [b["aep_net"], b["loss_total"], b["wake_loss"]], width=0.35, label="B")
            ax.set_xticks([0.175, 1.175, 2.175])
            ax.set_xticklabels(labels)
            ax.set_ylabel("MWh/año")
            ax.set_title("Comparación global")
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
            vals = [m, _fmt_mwh(va), _fmt_mwh(vb), _fmt_signed_mwh(d), _fmt_signed_pct(dp), f"{int(na.get(m,0) or 0)}/{int(nb.get(m,0) or 0)}"]
            for c, val in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(str(val))
                if c > 0:
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                tbl.setItem(i, c, it)
        tbl.resizeRowsToContents()

    def _config_html(self) -> str:
        def block(title: str, r: Dict[str, Any]) -> str:
            cfg = r.get("selection_executed", {}) or r.get("selection_requested", {}) or r.get("selection_user", {}) or {}
            rows = []
            for k in ("engine", "wake_deficit", "turbulence", "blockage", "rotor_avg", "superposition"):
                if k in cfg:
                    rows.append(f"<li><b>{html_mod.escape(k)}:</b> {html_mod.escape(str(cfg.get(k)))}</li>")
            notes = r.get("simulation_notes", []) or []
            if notes:
                rows.append("<li><b>Notas:</b><ul>" + "".join(f"<li>{html_mod.escape(str(n))}</li>" for n in notes) + "</ul></li>")
            return f"<h3>{html_mod.escape(title)}</h3><ul>{''.join(rows) or '<li>Sin configuración registrada</li>'}</ul>"
        return block(self.label_a, self.result_a) + block(self.label_b, self.result_b)
