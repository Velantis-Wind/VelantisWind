# -*- coding: utf-8 -*-
"""Summary dialogs and console summaries for shadow-flicker results."""
from __future__ import annotations

from ..debug import debug_print

from typing import Dict, List, Optional, Tuple

import numpy as np
from qgis.PyQt import QtCore, QtWidgets, QtGui

from ..i18n_local import (
    tr4 as _ml,
    month_names,
    hours_per_year_unit,
    close_label,
    timezone_label_local,
)

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
    if hours >= 30.0 or max_minutes_day > 30:
        return _ml("Crítico", "Critical", "Critique", "Kritisch"), 4, QtGui.QColor(255, 170, 170)
    if hours >= 20.0:
        return _ml("Alto", "High", "Élevé", "Hoch"), 3, QtGui.QColor(255, 220, 165)
    if hours >= 10.0:
        return _ml("Medio", "Medium", "Moyen", "Mittel"), 2, QtGui.QColor(255, 245, 170)
    if hours >= 5.0:
        return _ml("Bajo", "Low", "Faible", "Niedrig"), 1, QtGui.QColor(220, 245, 190)
    return _ml("Muy bajo", "Very low", "Très faible", "Sehr niedrig"), 0, QtGui.QColor(230, 245, 230)


def _all_hours(results) -> List[float]:
    return [_safe_float(getattr(r, "hours_per_year_astronomical", 0.0), 0.0) for r in (results or [])]


def _format_turbine_geometry(turbines, key: str, unit: str = "m") -> str:
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

    unique_text = _ml("valores únicos", "unique values", "valeurs uniques", "einzigartige Werte")
    return f"{min(values):.2f}–{max(values):.2f} {unit} ({len(unique_values)} {unique_text})"


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
    scroll = QtWidgets.QScrollArea()
    configure_scroll_area(scroll)
    scroll.setWidget(content)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    return scroll


def _finalize_table(table: QtWidgets.QTableWidget, *, min_height: int = 260, stretch_columns=()):
    configure_table(table, stretch_columns=stretch_columns, min_height=min_height)
    try:
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setDefaultSectionSize(24)
    except Exception:
        pass


def _tz_label(calculator) -> str:
    return timezone_label_local(
        getattr(calculator, "timezone_mode", "fixed"),
        getattr(calculator, "timezone_name", None),
        _safe_float(getattr(calculator, "timezone_offset", 0.0)),
    )


def show_calculation_summary_for_page(self, results, turbines, calculator):
    """Print a compact final calculation summary."""
    unit = hours_per_year_unit()
    hours_list = _all_hours(results)
    debug_print("\n" + "=" * 70)
    debug_print(_ml("RESUMEN DEL CÁLCULO DE SOMBRAS Y PARPADEO", "SHADOW-FLICKER CALCULATION SUMMARY", "RÉSUMÉ DU CALCUL OMBRES ET SCINTILLEMENT", "ZUSAMMENFASSUNG DER SCHATTENWURFBERECHNUNG"))
    debug_print("=" * 70)
    debug_print(f"{_ml('Sitio', 'Site', 'Site', 'Standort')}: {calculator.latitude:.5f}°, {calculator.longitude:.5f}°")
    debug_print(f"{_ml('Año', 'Year', 'Année', 'Jahr')}: {calculator.year}")
    debug_print(f"{_ml('Zona horaria', 'Timezone', 'Fuseau horaire', 'Zeitzone')}: {_tz_label(calculator)}")
    debug_print(f"{_ml('Aerogeneradores', 'Wind turbines', 'Éoliennes', 'Windturbinen')}: {len(turbines or [])}")
    debug_print(f"{_ml('Altura de buje usada', 'Hub height used', 'Hauteur de moyeu utilisée', 'Verwendete Nabenhöhe')}: {_format_turbine_geometry(turbines, 'hub_height')}")
    debug_print(f"{_ml('Diámetro de rotor usado', 'Rotor diameter used', 'Diamètre du rotor utilisé', 'Verwendeter Rotordurchmesser')}: {_format_turbine_geometry(turbines, 'rotor_diameter')}")
    debug_print(f"{_ml('Distancia máxima de sombra', 'Maximum shadow distance', 'Distance maximale d’ombre', 'Maximale Schattenentfernung')}: {getattr(calculator, 'max_shadow_distance_m', '—')} m")
    debug_print(f"{_ml('Receptores', 'Receivers', 'Récepteurs', 'Rezeptoren')}: {len(results or [])}")
    if hours_list:
        debug_print(f"Min / Max / {_ml('Media', 'Mean', 'Moyenne', 'Mittelwert')} {unit}: {min(hours_list):.2f} / {max(hours_list):.2f} / {sum(hours_list)/len(hours_list):.2f}")
        debug_print(f"{_ml('Receptores >30', 'Receivers >30', 'Récepteurs >30', 'Rezeptoren >30')} {unit}: {sum(1 for h in hours_list if h > 30.0)}")
        debug_print(f"{_ml('Receptores >20', 'Receivers >20', 'Récepteurs >20', 'Rezeptoren >20')} {unit}: {sum(1 for h in hours_list if h > 20.0)}")
    debug_print(_ml("Cálculo terminado correctamente.", "Calculation finished successfully.", "Calcul terminé avec succès.", "Berechnung erfolgreich abgeschlossen."))
    debug_print("=" * 70 + "\n")


def show_summary_dialog_for_page(self, results, turbines, calculator):
    """Show a complete, filled and sortable shadow-flicker summary dialog."""
    results = list(results or [])
    turbines = list(turbines or [])
    hours_list = _all_hours(results)
    n_receivers = len(results)
    n_turbines = len(turbines)
    unit = hours_per_year_unit()
    hub_height_summary = _format_turbine_geometry(turbines, "hub_height")
    rotor_diameter_summary = _format_turbine_geometry(turbines, "rotor_diameter")
    max_hours = max(hours_list) if hours_list else 0.0
    mean_hours = (sum(hours_list) / len(hours_list)) if hours_list else 0.0
    affected = sum(1 for h in hours_list if h > 0.0)
    exceed_30h = sum(1 for r in results if _safe_float(getattr(r, "hours_per_year_astronomical", 0.0)) > 30.0)
    exceed_30m = sum(1 for r in results if _safe_int(getattr(r, "max_minutes_per_day", 0)) > 30)
    critical = max(results, key=lambda r: _safe_float(getattr(r, "hours_per_year_astronomical", 0.0), 0.0)) if results else None

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(_ml("Sombras y parpadeo - Resumen del cálculo", "Shadow flicker - Calculation summary", "Ombres et scintillement - Résumé du calcul", "Schattenwurf - Berechnungsübersicht"))
    if fit_to_screen is not None:
        fit_to_screen(dialog, preferred=(1080, 740), minimum=(620, 420), max_ratio=(0.94, 0.88))
    else:
        dialog.resize(1080, 740)
        dialog.setMinimumSize(620, 420)

    root = QtWidgets.QVBoxLayout(dialog)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    header = QtWidgets.QLabel(f"<h2>{_ml('Resumen del cálculo de sombras y parpadeo', 'Shadow-flicker calculation summary', 'Résumé du calcul d’ombres et scintillement', 'Zusammenfassung der Schattenwurfberechnung')}</h2>")
    root.addWidget(header)

    tabs = QtWidgets.QTabWidget()
    tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    root.addWidget(tabs, 1)

    # Summary tab
    tab_summary = QtWidgets.QWidget()
    summary_layout = QtWidgets.QVBoxLayout(tab_summary)
    summary_layout.setSpacing(10)

    cards = QtWidgets.QGridLayout()
    cards.setHorizontalSpacing(8)
    cards.setVerticalSpacing(8)
    cards.addWidget(_make_metric_card(_ml("Aerogeneradores", "Wind turbines", "Éoliennes", "Windturbinen"), str(n_turbines), _ml("Capa de entrada", "Input layer", "Source d’entrée", "Eingabequelle")), 0, 0)
    cards.addWidget(_make_metric_card(_ml("Receptores evaluados", "Evaluated receivers", "Récepteurs évalués", "Bewertete Rezeptoren"), str(n_receivers), _ml(f"{affected} con >0 {unit}", f"{affected} with >0 {unit}", f"{affected} avec >0 {unit}", f"{affected} mit >0 {unit}")), 0, 1)
    cards.addWidget(_make_metric_card("Maximum", f"{max_hours:.2f} {unit}", _ml("Receptor más expuesto", "Most exposed receiver", "Récepteur le plus exposé", "am stärksten exponierter Rezeptor"), "#fff4e5" if max_hours >= 20 else "#f4f6f8"), 0, 2)
    cards.addWidget(_make_metric_card(_ml("Media", "Mean", "Moyenne", "Mittelwert"), f"{mean_hours:.2f} {unit}", _ml("Media sobre los receptores", "Mean over receivers", "Moyenne sur les récepteurs", "Mittelwert über die Rezeptoren")), 0, 3)
    cards.addWidget(_make_metric_card(_ml(f"Supera 30 {unit}", f"Exceeds 30 {unit}", f"Dépasse 30 {unit}", f"Überschreitet 30 {unit}"), str(exceed_30h), _ml("Umbral anual", "Annual threshold", "Seuil annuel", "Jahresschwelle"), "#ffe4e4" if exceed_30h else "#eef8ee"), 1, 0)
    cards.addWidget(_make_metric_card(_ml("Supera 30 min/día", "Exceeds 30 min/day", "Dépasse 30 min/jour", "Überschreitet 30 min/Tag"), str(exceed_30m), _ml("Umbral diario", "Daily threshold", "Seuil journalier", "Tagesschwelle"), "#ffe4e4" if exceed_30m else "#eef8ee"), 1, 1)
    cards.addWidget(_make_metric_card(_ml("Zona horaria", "Timezone", "Fuseau horaire", "Zeitzone"), _tz_label(calculator), str(getattr(calculator, "year", ""))), 1, 2, 1, 2)
    summary_layout.addLayout(cards)

    if critical is not None:
        worst_date, worst_min = _worst_day(critical)
        top_turbine, top_hours = _top_turbine(critical)
        crit_group = QtWidgets.QGroupBox(_ml("Receptor crítico", "Critical receiver", "Récepteur critique", "Kritischer Rezeptor"))
        crit_layout = QtWidgets.QFormLayout(crit_group)
        crit_layout.addRow(_ml("Receptor:", "Receiver:", "Récepteur :", "Rezeptor:"), QtWidgets.QLabel(str(getattr(critical, "receptor_name", "—"))))
        crit_layout.addRow(_ml("Sombra anual:", "Annual shadow flicker:", "Ombre annuelle :", "Jährlicher Schattenwurf:"), QtWidgets.QLabel(f"{_safe_float(getattr(critical, 'hours_per_year_astronomical', 0.0)):.2f} {unit}"))
        crit_layout.addRow(_ml("Días afectados:", "Affected days:", "Jours affectés :", "Betroffene Tage:"), QtWidgets.QLabel(str(_safe_int(getattr(critical, "days_affected", 0)))))
        crit_layout.addRow(_ml("Día más desfavorable:", "Worst day:", "Jour le plus défavorable :", "Ungünstigster Tag:"), QtWidgets.QLabel(f"{worst_date} · {worst_min} min"))
        crit_layout.addRow(_ml("Aerogenerador dominante:", "Dominant wind turbine:", "Éolienne dominante :", "Dominante Windturbine:"), QtWidgets.QLabel(f"{top_turbine} ({top_hours:.2f} {unit})" if top_hours > 0 else top_turbine))
        summary_layout.addWidget(crit_group)

    config_group = QtWidgets.QGroupBox(_ml("Configuración", "Configuration", "Configuration", "Konfiguration"))
    config_layout = QtWidgets.QFormLayout(config_group)
    config_layout.addRow("Latitude:", QtWidgets.QLabel(f"{calculator.latitude:.5f}°"))
    config_layout.addRow("Longitude:", QtWidgets.QLabel(f"{calculator.longitude:.5f}°"))
    config_layout.addRow(_ml("Año:", "Year:", "Année :", "Jahr:"), QtWidgets.QLabel(str(calculator.year)))
    config_layout.addRow(_ml("Altura de buje usada:", "Hub height used:", "Hauteur de moyeu utilisée :", "Verwendete Nabenhöhe:"), QtWidgets.QLabel(hub_height_summary))
    config_layout.addRow(_ml("Diámetro de rotor usado:", "Rotor diameter used:", "Diamètre du rotor utilisé :", "Verwendeter Rotordurchmesser:"), QtWidgets.QLabel(rotor_diameter_summary))
    config_layout.addRow(_ml("Paso temporal:", "Time step:", "Pas temporel :", "Zeitschritt:"), QtWidgets.QLabel(f"{getattr(calculator, 'time_step_minutes', '—')} min"))
    config_layout.addRow(_ml("Disponibilidad:", "Availability:", "Disponibilité :", "Verfügbarkeit:"), QtWidgets.QLabel(f"{_safe_float(getattr(calculator, 'turbine_availability', 1.0)):.2f}"))
    config_layout.addRow(_ml("Distancia máxima de sombra:", "Maximum shadow distance:", "Distance maximale d’ombre :", "Maximale Schattenentfernung:"), QtWidgets.QLabel(f"{getattr(calculator, 'max_shadow_distance_m', '—')} m"))
    config_layout.addRow(_ml("Límites de elevación solar:", "Solar elevation limits:", "Limites d’élévation solaire :", "Grenzen der Sonnenhöhe:"), QtWidgets.QLabel(f"{getattr(calculator, 'min_sun_elevation', '—')}° – {getattr(calculator, 'max_sun_elevation', '—')}°"))
    summary_layout.addWidget(config_group)

    monthly_group = QtWidgets.QGroupBox(_ml("Detalle mensual · media sobre los receptores", "Monthly detail · mean over receivers", "Détail mensuel · moyenne sur les récepteurs", "Monatsdetail · Mittelwert über die Rezeptoren"))
    monthly_layout = QtWidgets.QVBoxLayout(monthly_group)
    monthly_table = QtWidgets.QTableWidget(12, 3)
    monthly_table.setHorizontalHeaderLabels([_ml("Mes", "Month", "Mois", "Monat"), _ml("Media h/receptor", "Mean h/receiver", "Moyenne h/récepteur", "Mittelwert h/Rezeptor"), _ml("Total h", "Total h", "Total h", "Gesamt h")])
    monthly_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    monthly_table.setSortingEnabled(False)
    monthly_totals = {m: 0.0 for m in range(1, 13)}
    for r in results:
        for m, h in _monthly_hours(r).items():
            monthly_totals[m] += h
    full_months = month_names(False)
    for month in range(1, 13):
        total = monthly_totals[month]
        avg = total / n_receivers if n_receivers else 0.0
        _set_item(monthly_table, month - 1, 0, QtWidgets.QTableWidgetItem(full_months[month - 1]))
        avg_item = NumericTableWidgetItem(avg, f"{avg:.2f}")
        avg_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(monthly_table, month - 1, 1, avg_item)
        total_item = NumericTableWidgetItem(total, f"{total:.2f}")
        total_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        _set_item(monthly_table, month - 1, 2, total_item)
    monthly_table.resizeColumnsToContents()
    _finalize_table(monthly_table, min_height=220, stretch_columns=(0,))
    monthly_layout.addWidget(monthly_table)
    summary_layout.addWidget(monthly_group, 1)
    summary_layout.addStretch(1)
    tabs.addTab(_make_scroll_tab(tab_summary), _ml("Resumen", "Summary", "Résumé", "Übersicht"))

    # Hour × Month matrix tab
    tab_12x24 = QtWidgets.QWidget()
    tab_12x24_layout = QtWidgets.QVBoxLayout(tab_12x24)

    selector_row = QtWidgets.QHBoxLayout()
    selector_row.addWidget(QtWidgets.QLabel(f"<b>{_ml('Seleccionar receptor:', 'Select receiver:', 'Sélectionner un récepteur :', 'Rezeptor auswählen:')}</b>"))
    cb_receptor = QtWidgets.QComboBox()
    cb_receptor.addItem(_ml("— Todos los receptores (suma) —", "— All receivers (sum) —", "— Tous les récepteurs (somme) —", "— Alle Rezeptoren (Summe) —"), None)
    for i, r in enumerate(results):
        cb_receptor.addItem(f"{getattr(r, 'receptor_name', f'R{i+1}')} ({_safe_float(getattr(r, 'hours_per_year_astronomical', 0.0)):.1f} {unit})", i)
    selector_row.addWidget(cb_receptor, 1)
    lbl_total_hours = QtWidgets.QLabel(f"<b>{_ml('Total', 'Total', 'Total', 'Gesamt')}: 0.0 {unit}</b>")
    selector_row.addWidget(lbl_total_hours)
    tab_12x24_layout.addLayout(selector_row)

    info_label = QtWidgets.QLabel(_ml(
        "<i>Horas de sombra por hora del día y mes. Los valores se convierten de minutos a horas. La columna Todos suma todos los meses por cada hora.</i>",
        "<i>Shadow-flicker hours by time of day and month. Values are converted from minutes to hours. The All column sums all months for each hour.</i>",
        "<i>Heures d’ombres et de scintillement par heure de la journée et par mois. Les valeurs sont converties de minutes en heures. La colonne Tous somme tous les mois pour chaque heure.</i>",
        "<i>Schattenwurfstunden nach Tagesstunde und Monat. Die Werte werden von Minuten in Stunden umgerechnet. Die Spalte Alle summiert alle Monate je Stunde.</i>",
    ))
    info_label.setWordWrap(True)
    tab_12x24_layout.addWidget(info_label)

    table_12x24 = QtWidgets.QTableWidget(24, 13)
    table_12x24.setHorizontalHeaderLabels([_ml("Todos", "All", "Tous", "Alle")] + month_names(True))
    table_12x24.setVerticalHeaderLabels([f"{h:02d}:00" for h in range(24)])
    table_12x24.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table_12x24.setSortingEnabled(False)

    def update_12x24_table():
        idx = cb_receptor.currentData()
        matrix_minutes = _aggregate_matrix_minutes(results) if idx is None else _result_matrix_minutes(results[idx])
        matrix_hours = matrix_minutes / 60.0
        total = float(matrix_hours.sum())
        lbl_total_hours.setText(f"<b>{_ml('Total', 'Total', 'Total', 'Gesamt')}: {total:.1f} {unit}</b>")
        max_val = float(matrix_hours.max()) if matrix_hours.size and matrix_hours.max() > 0 else 1.0
        max_hour_total = max(float(matrix_hours.sum(axis=0).max()) if matrix_hours.size else 1.0, 1.0)

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
    tabs.addTab(tab_12x24, _ml("Hora × Mes", "Hour × Month", "Heure × Mois", "Stunde × Monat"))

    # By receptor tab
    tab_receptors = QtWidgets.QWidget()
    rec_layout = QtWidgets.QVBoxLayout(tab_receptors)
    info_rec = QtWidgets.QLabel(_ml(
        "<i>Valores detallados por receptor. La tabla se puede ordenar por horas, días y estado.</i>",
        "<i>Detailed values by receiver. The table can be sorted by hours, days and status.</i>",
        "<i>Valeurs détaillées pour chaque récepteur. Le tableau peut être trié par heures, jours et état.</i>",
        "<i>Detaillierte Werte für jeden Rezeptor. Die Tabelle kann nach Stunden, Tagen und Status sortiert werden.</i>",
    ))
    info_rec.setWordWrap(True)
    rec_layout.addWidget(info_rec)

    columns = [
        _ml("Receptor", "Receiver", "Récepteur", "Rezeptor"),
        unit,
        _ml("h realistas", "realistic h", "h réaliste", "realistische h"),
        _ml("Días", "Days", "Jours", "Tage"),
        _ml("Máx. min/día", "Max. min/day", "Max min/jour", "Max. min/Tag"),
        _ml("Día crítico", "Critical day", "Jour critique", "kritischer Tag"),
        _ml("Aerogeneradores afectados", "Affecting turbines", "Éoliennes affectantes", "betroffene Windturbinen"),
        _ml("Aerogenerador dominante", "Dominant turbine", "Éolienne dominante", "dominante Windturbine"),
        _ml("h dominantes", "dominant h", "h dominante", "dominante h"),
        _ml("Estado", "Status", "État", "Status"),
    ]
    table_rec = QtWidgets.QTableWidget(n_receivers, len(columns))
    table_rec.setHorizontalHeaderLabels(columns)
    table_rec.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table_rec.setAlternatingRowColors(True)
    table_rec.setSortingEnabled(False)

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

        _set_item(table_rec, row, 0, QtWidgets.QTableWidgetItem(str(getattr(r, "receptor_name", f"R{row+1}"))))
        h_item = NumericTableWidgetItem(hours, f"{hours:.2f}")
        h_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        h_item.setBackground(bg)
        _set_item(table_rec, row, 1, h_item)
        real_item = NumericTableWidgetItem(real_hours_f if real_hours_f is not None else -1, "—" if real_hours_f is None else f"{real_hours_f:.2f}")
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
    tabs.addTab(tab_receptors, _ml("Por receptor", "By receiver", "Par récepteur", "Je Rezeptor"))

    buttons = QtWidgets.QHBoxLayout()
    btn_export = QtWidgets.QPushButton(_ml("📊 Exportar CSV 12×24", "📊 Export 12×24 CSV", "📊 Exporter 12×24 CSV", "📊 12×24-CSV exportieren"))
    btn_export.setToolTip(_ml("Exportar la matriz hora × mes como CSV", "Export the hour × month matrix as CSV", "Exporter la matrice heure × mois en CSV", "Stunde-×-Monat-Matrix als CSV exportieren"))
    btn_export.setMinimumHeight(36)

    def do_export():
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            dialog,
            _ml("Exportar sombras 12×24", "Export shadow flicker 12×24", "Exporter ombres et scintillement 12×24", "Schattenwurf 12×24 exportieren"),
            f"shadow_flicker_12x24_{calculator.year}.csv",
            _ml("Archivos CSV (*.csv)", "CSV files (*.csv)", "Fichiers CSV (*.csv)", "CSV-Dateien (*.csv)"),
        )
        if not path:
            return
        try:
            from ..shadow_calculator import export_shadow_12x24_csv
            export_shadow_12x24_csv(results, path, turbines=turbines, calculator=calculator)
            QtWidgets.QMessageBox.information(dialog, _ml("Exportación correcta", "Export successful", "Export réussi", "Export erfolgreich"), _ml(f"{len(results)} receptor(es) exportado(s) a:\n{path}", f"{len(results)} receiver(s) exported to:\n{path}", f"{len(results)} récepteur(s) exporté(s) vers :\n{path}", f"{len(results)} Rezeptor(en) exportiert nach:\n{path}"))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(dialog, _ml("Error de exportación", "Export failed", "Échec de l’export", "Export fehlgeschlagen"), str(exc))

    btn_export.clicked.connect(do_export)
    buttons.addWidget(btn_export)
    buttons.addStretch()
    close_button = QtWidgets.QPushButton(close_label())
    close_button.setMinimumHeight(36)
    close_button.setMinimumWidth(110)
    close_button.setDefault(True)
    close_button.clicked.connect(dialog.accept)
    buttons.addWidget(close_button)
    root.addLayout(buttons)

    dialog.exec_()
