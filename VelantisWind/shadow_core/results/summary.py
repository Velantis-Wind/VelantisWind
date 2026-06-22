# -*- coding: utf-8 -*-
"""Summary dialogs and console summaries for ombres et scintillement results."""
from __future__ import annotations

from ..debug import debug_print

from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from qgis.PyQt import QtCore, QtWidgets, QtGui

from ..timezone_utils import timezone_label

try:
    from ...i18n import apply_i18n, current_language, install_runtime_i18n_patches, tr_text as _tr
except Exception:  # pragma: no cover - direct imports / tests
    def _tr(text):
        return text
    def apply_i18n(widget):
        return None
    def install_runtime_i18n_patches():
        return None
    def current_language():
        return "es"


try:
    from ...ui_core.responsive import fit_to_screen, configure_scroll_area, configure_table
except Exception:  # pragma: no cover - defensive fallback for direct imports
    fit_to_screen = None

    def configure_scroll_area(scroll):
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def configure_table(table, stretch_columns=(), interactive=True, min_height=None):
        table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        table.setWordWrap(False)
        table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        if min_height is not None:
            table.setMinimumHeight(int(min_height))



MONTH_NAMES = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
MONTH_SHORT = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
MONTH_NAMES_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONTH_SHORT_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


class NumericTableWidgetItem(QtWidgets.QTableWidgetItem):
    """QTableWidgetItem with numeric sorting while keeping formatted text."""

    def __init__(self, value, text: Optional[str] = None):
        self._sort_value = float(value) if value is not None else -1.0e30
        super().__init__(text if text is not None else f"{self._sort_value:.2f}")

    def __lt__(self, other):  # pragma: no cover - Qt calls this from C++
        if isinstance(other, NumericTableWidgetItem):
            return self._sort_value < other._sort_value
        try:
            return self._sort_value < float(other.text())
        except Exception:
            return super().__lt__(other)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _result_matrix_minutes(result) -> np.ndarray:
    """Return a defensive 12x24 matrix in minutes for a result."""
    matrix = getattr(result, "hourly_monthly_matrix", None)
    if matrix is not None:
        try:
            arr = np.asarray(matrix, dtype=float)
            if arr.shape == (12, 24):
                return arr.copy()
        except Exception:
            pass

    # Fallback: build from calendar using the timestep stored in the result.
    arr = np.zeros((12, 24), dtype=float)
    calendar = getattr(result, "calendar", {}) or {}
    step_min = max(1, _safe_int(getattr(result, "time_step_minutes", 1), 1))
    for day, times in calendar.items():
        try:
            month_idx = int(day.month) - 1
        except Exception:
            continue
        if month_idx < 0 or month_idx > 11:
            continue
        for t in times or []:
            try:
                hour = int(t.hour)
            except Exception:
                continue
            if 0 <= hour <= 23:
                arr[month_idx, hour] += float(step_min)
    return arr


def _monthly_hours(result) -> Dict[int, float]:
    matrix = _result_matrix_minutes(result)
    return {month: float(matrix[month - 1, :].sum() / 60.0) for month in range(1, 13)}


def _worst_day(result) -> Tuple[str, int]:
    explicit_date = getattr(result, "max_shadow_date", None)
    explicit_minutes = _safe_int(getattr(result, "max_minutes_per_day", 0), 0)
    if explicit_date:
        try:
            return explicit_date.strftime("%Y-%m-%d"), explicit_minutes
        except Exception:
            return str(explicit_date), explicit_minutes

    calendar = getattr(result, "calendar", {}) or {}
    if not calendar:
        return "—", explicit_minutes
    try:
        step_min = max(1, _safe_int(getattr(result, "time_step_minutes", 1), 1))
        worst = max(calendar.keys(), key=lambda d: len(calendar[d] or []) * step_min)
        return worst.strftime("%Y-%m-%d"), len(calendar.get(worst, []) or []) * step_min
    except Exception:
        return "—", explicit_minutes


def _top_turbine(result) -> Tuple[str, float]:
    contrib = getattr(result, "turbine_contributions", {}) or {}
    if not contrib:
        return "—", 0.0
    try:
        name, hours = max(contrib.items(), key=lambda kv: _safe_float(kv[1], 0.0))
        return str(name), _safe_float(hours, 0.0)
    except Exception:
        return "—", 0.0


def _severity(hours: float, max_minutes_day: int) -> Tuple[str, int, QtGui.QColor]:
    de = str(current_language()).lower().startswith("de")
    if hours >= 30.0 or max_minutes_day > 30:
        return ("Kritisch" if de else "Critique"), 4, QtGui.QColor(255, 170, 170)
    if hours >= 20.0:
        return ("Hoch" if de else "Élevé"), 3, QtGui.QColor(255, 220, 165)
    if hours >= 10.0:
        return ("Mittel" if de else "Moyen"), 2, QtGui.QColor(255, 245, 170)
    if hours >= 5.0:
        return ("Niedrig" if de else "Faible"), 1, QtGui.QColor(220, 245, 190)
    return ("Sehr niedrig" if de else "Très faible"), 0, QtGui.QColor(230, 245, 230)


def _all_hours(results) -> List[float]:
    return [_safe_float(getattr(r, "hours_per_year_astronomical", 0.0), 0.0) for r in (results or [])]


def _format_turbine_geometry(turbines, key: str, unit: str = "m") -> str:
    """Format the turbine geometry values actually passed to the calculation.

    Shadow flicker can be sensitive to both hub height and rotor diameter.  The
    final on-screen summary should therefore report the values taken from the
    turbine dictionaries used by the engine, not only the editable UI table.
    """
    values = []
    for turbine in turbines or []:
        try:
            value = float(turbine.get(key))
        except Exception:
            continue
        if np.isfinite(value):
            values.append(value)

    if not values:
        return "—"

    unique_values = sorted({round(v, 6) for v in values})
    if len(unique_values) == 1:
        return f"{unique_values[0]:.2f} {unit}"

    return (
        f"{min(values):.2f}–{max(values):.2f} {unit} "
        f"({len(unique_values)} {"einzigartige Werte" if str(current_language()).lower().startswith("de") else "valeurs uniques"})"
    )


def _aggregate_matrix_minutes(results) -> np.ndarray:
    matrix = np.zeros((12, 24), dtype=float)
    for r in results or []:
        matrix += _result_matrix_minutes(r)
    return matrix


def _make_metric_card(title: str, value: str, subtitle: str = "", color: str = "#f4f6f8") -> QtWidgets.QFrame:
    card = QtWidgets.QFrame()
    card.setFrameShape(QtWidgets.QFrame.StyledPanel)
    card.setStyleSheet(
        f"QFrame {{ background: {color}; border: 1px solid #d0d5dd; border-radius: 8px; }}"
        "QLabel { border: none; background: transparent; }"
    )
    layout = QtWidgets.QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    label_title = QtWidgets.QLabel(title)
    label_title.setStyleSheet("font-size: 10px; color: #475467;")
    label_value = QtWidgets.QLabel(value)
    label_value.setStyleSheet("font-size: 20px; font-weight: 700; color: #101828;")
    label_sub = QtWidgets.QLabel(subtitle)
    label_sub.setWordWrap(True)
    label_sub.setStyleSheet("font-size: 10px; color: #667085;")
    layout.addWidget(label_title)
    layout.addWidget(label_value)
    if subtitle:
        layout.addWidget(label_sub)
    return card


def _set_item(table: QtWidgets.QTableWidget, row: int, col: int, item: QtWidgets.QTableWidgetItem):
    item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
    table.setItem(row, col, item)


def _make_scroll_tab(content: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Wrap long tab content in a responsive scroll area."""
    scroll = QtWidgets.QScrollArea()
    configure_scroll_area(scroll)
    scroll.setWidget(content)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    return scroll


def _finalize_table(table: QtWidgets.QTableWidget, *, min_height: int = 260, stretch_columns=()):
    """Apply consistent table sizing without forcing oversized dialogs."""
    configure_table(table, stretch_columns=stretch_columns, min_height=min_height)
    try:
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setDefaultSectionSize(24)
    except Exception:
        pass


def show_calculation_summary_for_page(self, results, turbines, calculator):
    """Print a compact final calculation summary.

    The full user-facing summary is shown by show_summary_dialog_for_page().
    This function intentionally avoids a second modal message box.
    """
    hours_list = _all_hours(results)
    debug_print("\n" + "=" * 70)
    debug_print("RÉSUMÉ DU CALCUL OMBRES ET SCINTILLEMENT")
    debug_print("=" * 70)
    debug_print(f"Site :     {calculator.latitude:.5f}°, {calculator.longitude:.5f}°")
    debug_print(f"Année :    {calculator.year}")
    debug_print(f"Fuseau :   {timezone_label(calculator.timezone_mode, calculator.timezone_name, calculator.timezone_offset)}")
    debug_print(f"Éoliennes : {len(turbines or [])}")
    debug_print(f"Hauteur de moyeu utilisée : {_format_turbine_geometry(turbines, 'hub_height')}")
    debug_print(f"Diamètre du rotor utilisé : {_format_turbine_geometry(turbines, 'rotor_diameter')}")
    debug_print(f"Distance maximale d’ombre : {getattr(calculator, 'max_shadow_distance_m', '—')} m")
    debug_print(f"Récepteurs : {len(results or [])}")
    if hours_list:
        debug_print(f"Min / Max / Moyenne h/an : {min(hours_list):.2f} / {max(hours_list):.2f} / {sum(hours_list)/len(hours_list):.2f}")
        debug_print(f"Récepteurs >30 h/an : {sum(1 for h in hours_list if h > 30.0)}")
        debug_print(f"Récepteurs >20 h/an : {sum(1 for h in hours_list if h > 20.0)}")
    debug_print("Calcul terminé avec succès.")
    debug_print("=" * 70 + "\n")


def show_summary_dialog_for_page(self, results, turbines, calculator):
    """Show a complete, filled and sortable shadow-flicker summary dialog."""
    install_runtime_i18n_patches()
    de = str(current_language()).lower().startswith("de")
    results = list(results or [])
    turbines = list(turbines or [])
    hours_list = _all_hours(results)
    n_receivers = len(results)
    n_turbines = len(turbines)
    hub_height_summary = _format_turbine_geometry(turbines, "hub_height")
    rotor_diameter_summary = _format_turbine_geometry(turbines, "rotor_diameter")
    max_hours = max(hours_list) if hours_list else 0.0
    mean_hours = (sum(hours_list) / len(hours_list)) if hours_list else 0.0
    affected = sum(1 for h in hours_list if h > 0.0)
    exceed_30h = sum(1 for r in results if _safe_float(getattr(r, "hours_per_year_astronomical", 0.0)) > 30.0)
    exceed_30m = sum(1 for r in results if _safe_int(getattr(r, "max_minutes_per_day", 0)) > 30)

    # Critical receiver by annual astronomical hours.
    critical = None
    if results:
        critical = max(results, key=lambda r: _safe_float(getattr(r, "hours_per_year_astronomical", 0.0), 0.0))

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle("Schattenwurf - Berechnungsübersicht" if de else "Ombres et scintillement - Résumé du calcul")
    if fit_to_screen is not None:
        fit_to_screen(dialog, preferred=(1080, 740), minimum=(620, 420), max_ratio=(0.94, 0.88))
    else:
        dialog.resize(1080, 740)
        dialog.setMinimumSize(620, 420)

    root = QtWidgets.QVBoxLayout(dialog)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    header = QtWidgets.QLabel("<h2>Zusammenfassung der Schattenwurfberechnung</h2>" if de else "<h2>Résumé du calcul d’ombres et scintillement</h2>")
    root.addWidget(header)

    tabs = QtWidgets.QTabWidget()
    tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    root.addWidget(tabs, 1)

    # ------------------------------------------------------------------
    # Summary tab
    # ------------------------------------------------------------------
    tab_summary = QtWidgets.QWidget()
    summary_layout = QtWidgets.QVBoxLayout(tab_summary)
    summary_layout.setSpacing(10)

    cards = QtWidgets.QGridLayout()
    cards.setHorizontalSpacing(8)
    cards.setVerticalSpacing(8)
    cards.addWidget(_make_metric_card("Windturbinen" if de else "Éoliennes", str(n_turbines), "Eingabequellen" if de else "Sources d’entrée"), 0, 0)
    cards.addWidget(_make_metric_card("Bewertete Rezeptoren" if de else "Récepteurs évalués", str(n_receivers), (f"{affected} mit >0 h/Jahr" if de else f"{affected} avec >0 h/an")), 0, 1)
    cards.addWidget(_make_metric_card("Maximum", f"{max_hours:.2f} h/Jahr" if de else f"{max_hours:.2f} h/an", "am stärksten exponierter Rezeptor" if de else "Récepteur le plus exposé", "#fff4e5" if max_hours >= 20 else "#f4f6f8"), 0, 2)
    cards.addWidget(_make_metric_card("Mittelwert" if de else "Moyenne", f"{mean_hours:.2f} h/Jahr" if de else f"{mean_hours:.2f} h/an", "Mittelwert über die Rezeptoren" if de else "Moyenne sur les récepteurs"), 0, 3)
    cards.addWidget(_make_metric_card("Überschreitet 30 h/Jahr" if de else "Dépasse 30 h/an", str(exceed_30h), "Jahresschwelle" if de else "Seuil annuel", "#ffe4e4" if exceed_30h else "#eef8ee"), 1, 0)
    cards.addWidget(_make_metric_card("Überschreitet 30 min/Tag" if de else "Dépasse 30 min/jour", str(exceed_30m), "Tagesschwelle" if de else "Seuil journalier", "#ffe4e4" if exceed_30m else "#eef8ee"), 1, 1)
    cards.addWidget(_make_metric_card("Zeitzone" if de else "Fuseau horaire", timezone_label(calculator.timezone_mode, calculator.timezone_name, calculator.timezone_offset), str(getattr(calculator, "year", ""))), 1, 2, 1, 2)
    summary_layout.addLayout(cards)

    if critical is not None:
        worst_date, worst_min = _worst_day(critical)
        top_turbine, top_hours = _top_turbine(critical)
        crit_group = QtWidgets.QGroupBox("Kritischer Rezeptor" if de else "Récepteur critique")
        crit_layout = QtWidgets.QFormLayout(crit_group)
        crit_layout.addRow("Rezeptor:" if de else "Récepteur :", QtWidgets.QLabel(str(getattr(critical, "receptor_name", "—"))))
        crit_layout.addRow("Jährlicher Schattenwurf:" if de else "Ombre annuelle :", QtWidgets.QLabel((f"{_safe_float(getattr(critical, 'hours_per_year_astronomical', 0.0)):.2f} h/Jahr" if de else f"{_safe_float(getattr(critical, 'hours_per_year_astronomical', 0.0)):.2f} h/an")))
        crit_layout.addRow("Betroffene Tage:" if de else "Jours affectés :", QtWidgets.QLabel(str(_safe_int(getattr(critical, "days_affected", 0)))))
        crit_layout.addRow("Ungünstigster Tag:" if de else "Jour le plus défavorable :", QtWidgets.QLabel(f"{worst_date} · {worst_min} min"))
        crit_layout.addRow("Dominante Windturbine:" if de else "Éolienne dominante :", QtWidgets.QLabel((f"{top_turbine} ({top_hours:.2f} h/Jahr)" if de and top_hours > 0 else f"{top_turbine} ({top_hours:.2f} h/an)" if top_hours > 0 else top_turbine)))
        summary_layout.addWidget(crit_group)

    config_group = QtWidgets.QGroupBox("Konfiguration" if de else "Configuration")
    config_layout = QtWidgets.QFormLayout(config_group)
    config_layout.addRow("Latitude :", QtWidgets.QLabel(f"{calculator.latitude:.5f}°"))
    config_layout.addRow("Longitude :", QtWidgets.QLabel(f"{calculator.longitude:.5f}°"))
    config_layout.addRow("Jahr:" if de else "Année :", QtWidgets.QLabel(str(calculator.year)))
    config_layout.addRow("Verwendete Nabenhöhe:" if de else "Hauteur de moyeu utilisée :", QtWidgets.QLabel(hub_height_summary))
    config_layout.addRow("Verwendeter Rotordurchmesser:" if de else "Diamètre du rotor utilisé :", QtWidgets.QLabel(rotor_diameter_summary))
    config_layout.addRow("Zeitschritt:" if de else "Pas temporel :", QtWidgets.QLabel(f"{getattr(calculator, 'time_step_minutes', '—')} min"))
    config_layout.addRow("Verfügbarkeit:" if de else "Disponibilité :", QtWidgets.QLabel(f"{_safe_float(getattr(calculator, 'turbine_availability', 1.0)):.2f}"))
    config_layout.addRow("Maximale Schattenentfernung:" if de else "Distance maximale d’ombre :", QtWidgets.QLabel(f"{getattr(calculator, 'max_shadow_distance_m', '—')} m"))
    config_layout.addRow("Grenzen der Sonnenhöhe:" if de else "Limites d’élévation solaire :", QtWidgets.QLabel((f"{getattr(calculator, 'min_sun_elevation', '—')}° bis {getattr(calculator, 'max_sun_elevation', '—')}°" if de else f"{getattr(calculator, 'min_sun_elevation', '—')}° à {getattr(calculator, 'max_sun_elevation', '—')}°")))
    summary_layout.addWidget(config_group)

    monthly_group = QtWidgets.QGroupBox("Monatsdetail · Mittelwert über die Rezeptoren" if de else "Détail mensuel · moyenne sur les récepteurs")
    monthly_layout = QtWidgets.QVBoxLayout(monthly_group)
    monthly_table = QtWidgets.QTableWidget(12, 3)
    monthly_table.setHorizontalHeaderLabels(["Monat", "Mittelwert h/Rezeptor", "Gesamt h"] if de else ["Mois", "Moyenne h/récepteur", "Total h"])
    monthly_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    monthly_table.setSortingEnabled(False)
    monthly_totals = {m: 0.0 for m in range(1, 13)}
    for r in results:
        for m, h in _monthly_hours(r).items():
            monthly_totals[m] += h
    for month in range(1, 13):
        total = monthly_totals[month]
        avg = total / n_receivers if n_receivers else 0.0
        _set_item(monthly_table, month - 1, 0, QtWidgets.QTableWidgetItem((MONTH_NAMES_DE if de else MONTH_NAMES)[month - 1]))
        avg_item = NumericTableWidgetItem(avg, f"{avg:.2f}")
        avg_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(monthly_table, month - 1, 1, avg_item)
        total_item = NumericTableWidgetItem(total, f"{total:.2f}")
        total_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(monthly_table, month - 1, 2, total_item)
        if month in (12, 1, 2):
            color = QtGui.QColor(255, 235, 235)
        elif month in (6, 7, 8):
            color = QtGui.QColor(230, 255, 230)
        else:
            color = None
        if color:
            for col in range(3):
                monthly_table.item(month - 1, col).setBackground(color)
    monthly_table.resizeColumnsToContents()
    _finalize_table(monthly_table, min_height=220, stretch_columns=(0,))
    monthly_layout.addWidget(monthly_table)
    summary_layout.addWidget(monthly_group, 1)

    summary_layout.addStretch(1)
    tabs.addTab(_make_scroll_tab(tab_summary), "Übersicht" if de else "Résumé")

    # ------------------------------------------------------------------
    # Hour × Month matrix tab
    # ------------------------------------------------------------------
    tab_12x24 = QtWidgets.QWidget()
    tab_12x24_layout = QtWidgets.QVBoxLayout(tab_12x24)

    selector_row = QtWidgets.QHBoxLayout()
    selector_row.addWidget(QtWidgets.QLabel("<b>Rezeptor auswählen:</b>" if de else "<b>Sélectionner un récepteur :</b>"))
    cb_receptor = QtWidgets.QComboBox()
    cb_receptor.addItem("— Alle Rezeptoren (Summe) —" if de else "— Tous les récepteurs (somme) —", None)
    for i, r in enumerate(results):
        cb_receptor.addItem((f"{getattr(r, 'receptor_name', f'R{i+1}')} ({_safe_float(getattr(r, 'hours_per_year_astronomical', 0.0)):.1f} h/Jahr)" if de else f"{getattr(r, 'receptor_name', f'R{i+1}')} ({_safe_float(getattr(r, 'hours_per_year_astronomical', 0.0)):.1f} h/an)"), i)
    selector_row.addWidget(cb_receptor, 1)
    lbl_total_hours = QtWidgets.QLabel("<b>Gesamt: 0.0 h/Jahr</b>" if de else "<b>Total : 0.0 h/an</b>")
    selector_row.addWidget(lbl_total_hours)
    tab_12x24_layout.addLayout(selector_row)

    info_label = QtWidgets.QLabel(
        ("<i>Schattenwurfstunden nach Tagesstunde und Monat. Die Werte werden von Minuten in Stunden umgerechnet. "
        "Die Spalte Alle summiert alle Monate je Stunde.</i>" if de else "<i>Heures d’ombres et de scintillement par heure de la journée et par mois. Les valeurs sont converties de minutes en heures. "
        "La colonne Tous somme tous les mois pour chaque heure.</i>")
    )
    info_label.setWordWrap(True)
    tab_12x24_layout.addWidget(info_label)

    table_12x24 = QtWidgets.QTableWidget(24, 13)
    table_12x24.setHorizontalHeaderLabels((["Alle"] + MONTH_SHORT_DE) if de else (["Tous"] + MONTH_SHORT))
    table_12x24.setVerticalHeaderLabels([f"{h:02d}:00" for h in range(24)])
    table_12x24.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table_12x24.setSortingEnabled(False)

    def update_12x24_table():
        idx = cb_receptor.currentData()
        if idx is None:
            matrix_minutes = _aggregate_matrix_minutes(results)
        else:
            matrix_minutes = _result_matrix_minutes(results[idx])
        matrix_hours = matrix_minutes / 60.0
        total = float(matrix_hours.sum())
        lbl_total_hours.setText((f"<b>Gesamt: {total:.1f} h/Jahr</b>" if de else f"<b>Total : {total:.1f} h/an</b>"))
        max_val = float(matrix_hours.max()) if matrix_hours.size and matrix_hours.max() > 0 else 1.0
        max_hour_total = float(matrix_hours.sum(axis=0).max()) if matrix_hours.size else 1.0
        max_hour_total = max(max_hour_total, 1.0)

        for h in range(24):
            all_months_value = float(matrix_hours[:, h].sum())
            item_all = NumericTableWidgetItem(all_months_value, f"{all_months_value:.1f}" if all_months_value > 0 else "—")
            item_all.setTextAlignment(QtCore.Qt.AlignCenter)
            font = item_all.font(); font.setBold(True); item_all.setFont(font)
            if all_months_value > 0:
                intensity = min(1.0, all_months_value / max_hour_total)
                item_all.setBackground(QtGui.QColor(255, int(255 * (1 - intensity * 0.65)), int(255 * (1 - intensity * 0.65))))
            _set_item(table_12x24, h, 0, item_all)
            for m in range(12):
                val = float(matrix_hours[m, h])
                item = NumericTableWidgetItem(val, f"{val:.1f}" if val > 0 else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if val > 0:
                    intensity = min(1.0, val / max_val)
                    if intensity < 0.35:
                        color = QtGui.QColor(255, 248, int(230 - intensity * 90))
                    elif intensity < 0.7:
                        color = QtGui.QColor(255, int(230 - (intensity - 0.35) * 210), 120)
                    else:
                        color = QtGui.QColor(255, int(max(80, 170 - (intensity - 0.7) * 220)), 120)
                    item.setBackground(color)
                _set_item(table_12x24, h, 1 + m, item)

    cb_receptor.currentIndexChanged.connect(update_12x24_table)
    update_12x24_table()
    table_12x24.resizeColumnsToContents()
    _finalize_table(table_12x24, min_height=360)
    tab_12x24_layout.addWidget(table_12x24, 1)
    tabs.addTab(tab_12x24, "Stunde × Monat" if de else "Heure × Mois")

    # ------------------------------------------------------------------
    # By receptor tab
    # ------------------------------------------------------------------
    tab_receptors = QtWidgets.QWidget()
    rec_layout = QtWidgets.QVBoxLayout(tab_receptors)
    info_rec = QtWidgets.QLabel(
        ("<i>Detaillierte Werte für jeden Rezeptor. Die Spalten werden vor dem Aktivieren der Sortierung gefüllt, damit nach dem Sortieren keine leeren Zellen entstehen.</i>" if de else "<i>Valeurs détaillées pour chaque récepteur. Les colonnes sont remplies avant d’activer le tri afin d’éviter les cellules vides après tri.</i>")
    )
    info_rec.setWordWrap(True)
    rec_layout.addWidget(info_rec)

    columns = (
        ["Rezeptor", "h/Jahr", "realistische h/Jahr", "Tage", "Max. min/Tag", "kritischer Tag",
         "betroffene Windturbinen", "dominante Windturbine", "dominante h", "Status"]
        if de else
        ["Récepteur", "h/an", "h/an réaliste", "Jours", "Max min/jour", "Jour critique",
         "Éoliennes affectantes", "Éolienne dominante", "h dominante", "État"]
    )
    table_rec = QtWidgets.QTableWidget(n_receivers, len(columns))
    table_rec.setHorizontalHeaderLabels(columns)
    table_rec.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table_rec.setAlternatingRowColors(True)
    table_rec.setSortingEnabled(False)  # Important: enable only after population.

    for row, r in enumerate(results):
        hours = _safe_float(getattr(r, "hours_per_year_astronomical", 0.0))
        real_hours = getattr(r, "hours_per_year_realistic", None)
        real_hours_f = _safe_float(real_hours, 0.0) if real_hours is not None else None
        days = _safe_int(getattr(r, "days_affected", 0))
        max_min = _safe_int(getattr(r, "max_minutes_per_day", 0))
        worst_date, _ = _worst_day(r)
        contrib = getattr(r, "turbine_contributions", {}) or {}
        top_name, top_hours = _top_turbine(r)
        status, _, bg = _severity(hours, max_min)

        name_item = QtWidgets.QTableWidgetItem(str(getattr(r, "receptor_name", f"R{row+1}")))
        _set_item(table_rec, row, 0, name_item)

        h_item = NumericTableWidgetItem(hours, f"{hours:.2f}")
        h_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        h_item.setBackground(bg)
        _set_item(table_rec, row, 1, h_item)

        real_txt = "—" if real_hours_f is None else f"{real_hours_f:.2f}"
        real_item = NumericTableWidgetItem(real_hours_f if real_hours_f is not None else -1, real_txt)
        real_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(table_rec, row, 2, real_item)

        days_item = NumericTableWidgetItem(days, str(days))
        days_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(table_rec, row, 3, days_item)

        max_item = NumericTableWidgetItem(max_min, str(max_min))
        max_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        max_item.setBackground(bg)
        _set_item(table_rec, row, 4, max_item)

        _set_item(table_rec, row, 5, QtWidgets.QTableWidgetItem(worst_date))

        affected_turbines = sum(1 for v in contrib.values() if _safe_float(v, 0.0) > 0.0)
        aff_item = NumericTableWidgetItem(affected_turbines, str(affected_turbines))
        aff_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(table_rec, row, 6, aff_item)

        _set_item(table_rec, row, 7, QtWidgets.QTableWidgetItem(str(top_name)))

        top_item = NumericTableWidgetItem(top_hours, f"{top_hours:.2f}" if top_hours > 0 else "—")
        top_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(table_rec, row, 8, top_item)

        status_item = QtWidgets.QTableWidgetItem(status)
        status_item.setBackground(bg)
        _set_item(table_rec, row, 9, status_item)

    table_rec.resizeColumnsToContents()
    _finalize_table(table_rec, min_height=360, stretch_columns=(0, 7, 9))
    table_rec.setSortingEnabled(True)
    table_rec.sortItems(1, QtCore.Qt.DescendingOrder)
    rec_layout.addWidget(table_rec, 1)
    tabs.addTab(tab_receptors, "Je Rezeptor" if de else "Par récepteur")

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    buttons = QtWidgets.QHBoxLayout()
    btn_export = QtWidgets.QPushButton("📊 12×24-CSV exportieren" if de else "📊 Exporter 12×24 CSV")
    btn_export.setToolTip("Stunde-×-Monat-Matrix als CSV exportieren" if de else "Exporter la matrice heure × mois en CSV")
    btn_export.setMinimumHeight(36)

    def do_export():
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            dialog,
            ("Schattenwurf 12×24 exportieren" if de else "Exporter ombres et scintillement 12×24"),
            f"ombres_scintillement_12x24_{calculator.year}.csv",
            ("CSV-Dateien (*.csv)" if de else "Fichiers CSV (*.csv)"),
        )
        if not path:
            return
        try:
            from ..shadow_calculator import export_shadow_12x24_csv
            export_shadow_12x24_csv(results, path, turbines=turbines, calculator=calculator)
            QtWidgets.QMessageBox.information(dialog, "Export erfolgreich" if de else "Export réussi", (f"{len(results)} Rezeptor(en) exportiert nach:\n{path}" if de else f"{len(results)} récepteur(s) exporté(s) vers :\n{path}"))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(dialog, "Export fehlgeschlagen" if de else "Échec de l’export", str(exc))

    btn_export.clicked.connect(do_export)
    buttons.addWidget(btn_export)
    buttons.addStretch()
    close_button = QtWidgets.QPushButton("Schließen" if de else "Fermer")
    close_button.setMinimumHeight(36)
    close_button.setMinimumWidth(110)
    close_button.setDefault(True)
    close_button.clicked.connect(dialog.accept)
    buttons.addWidget(close_button)
    root.addLayout(buttons)

    if fit_to_screen is not None:
        fit_to_screen(dialog, preferred=(1080, 740), minimum=(620, 420), max_ratio=(0.94, 0.88))
    if not de:
        apply_i18n(dialog)
    dialog.exec_()
