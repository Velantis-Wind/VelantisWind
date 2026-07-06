# -*- coding: utf-8 -*-
"""QGIS output layers for the shadow flicker module.

Extracted from shadow_page.py to keep the page focused on UI concerns.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from qgis.PyQt import QtCore, QtGui
from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProject, QgsVectorLayer, QgsGraduatedSymbolRenderer,
    QgsRendererRange, QgsSymbol, QgsPalLayerSettings, QgsTextFormat,
    QgsTextBufferSettings, QgsVectorLayerSimpleLabeling,
)

from ..shadow_calculator import ShadowFlickerResult
from ..i18n_local import tr4 as _ml, lang_code, yes_no, hours_per_year_unit


def _result_layer_name() -> str:
    prefix = {
        "es": "Sombras_parpadeo",
        "en": "Shadow_flicker",
        "fr": "Ombres_scintillement",
        "de": "Schattenwurf",
    }.get(lang_code(), "Sombras_parpadeo")
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _category(hours: float):
    """Return localized category, severity and 30 h/year exceedance flag."""
    if hours >= 30:
        return _ml("CRÍTICO", "CRITICAL", "CRITIQUE", "KRITISCH"), 4, True
    if hours >= 20:
        return _ml("ALTO", "HIGH", "ÉLEVÉ", "HOCH"), 3, False
    if hours >= 10:
        return _ml("MEDIO", "MEDIUM", "MOYEN", "MITTEL"), 2, False
    if hours >= 5:
        return _ml("BAJO", "LOW", "FAIBLE", "NIEDRIG"), 1, False
    return _ml("MUY BAJO", "VERY LOW", "TRÈS FAIBLE", "SEHR NIEDRIG"), 0, False


def create_results_layer_for_page(self, results: List[ShadowFlickerResult], receiver_layer: QgsVectorLayer,
                                  turbines: List[dict], calculator):
    """Create shadow flicker output layer."""
    prj = QgsProject.instance()

    fields = QgsFields()
    fields.append(QgsField("receiver", QtCore.QVariant.String))
    fields.append(QgsField("hours_year", QtCore.QVariant.Double))
    fields.append(QgsField("hours_real", QtCore.QVariant.Double))
    fields.append(QgsField("minutes", QtCore.QVariant.Int))
    fields.append(QgsField("days_affected", QtCore.QVariant.Int))
    fields.append(QgsField("max_min_day", QtCore.QVariant.Int))
    fields.append(QgsField("exceeds_30h", QtCore.QVariant.String))
    fields.append(QgsField("exceeds_30m", QtCore.QVariant.String))
    fields.append(QgsField("category", QtCore.QVariant.String))
    fields.append(QgsField("severity", QtCore.QVariant.Int))

    month_names_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for month_name in month_names_short:
        fields.append(QgsField(f"h_{month_name}", QtCore.QVariant.Double))

    result_layer = QgsVectorLayer(
        f"Point?crs={receiver_layer.crs().authid()}",
        _result_layer_name(),
        "memory",
    )
    result_layer.dataProvider().addAttributes(fields)
    result_layer.updateFields()
    result_layer.setCustomProperty("velantis/shadow_output", True)

    features = []
    for result in results:
        feat = QgsFeature(result_layer.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(result.receptor_x, result.receptor_y)))
        feat.setAttribute("receiver", result.receptor_name)
        feat.setAttribute("hours_year", result.hours_per_year_astronomical)
        feat.setAttribute("hours_real", result.hours_per_year_realistic or 0.0)
        feat.setAttribute("minutes", result.minutes_per_year)
        feat.setAttribute("days_affected", result.days_affected)
        feat.setAttribute("max_min_day", result.max_minutes_per_day)

        category, severity, exceeds_30h = _category(result.hours_per_year_astronomical)
        feat.setAttribute("exceeds_30h", yes_no(exceeds_30h))
        feat.setAttribute("exceeds_30m", yes_no(result.max_minutes_per_day > 30))
        feat.setAttribute("category", category)
        feat.setAttribute("severity", severity)

        monthly = result.monthly_breakdown()
        for month_num, month_name in enumerate(month_names_short, start=1):
            feat.setAttribute(f"h_{month_name}", monthly.get(month_num, 0.0))

        features.append(feat)

    result_layer.dataProvider().addFeatures(features)
    result_layer.updateExtents()
    prj.addMapLayer(result_layer)

    self._apply_result_symbology(result_layer)
    self._apply_labels(result_layer)
    self._show_calculation_summary(results, turbines, calculator)


def apply_result_symbology_for_page(self, layer: QgsVectorLayer):
    """Apply enhanced symbology to the output layer."""
    field_name = "hours_year"
    unit = hours_per_year_unit()
    ranges = [
        (0, 5, _ml(f"MUY BAJO (< 5 {unit})", f"VERY LOW (< 5 {unit})", f"TRÈS FAIBLE (< 5 {unit})", f"SEHR NIEDRIG (< 5 {unit})"), "#90EE90"),
        (5, 10, _ml(f"BAJO (5-10 {unit})", f"LOW (5-10 {unit})", f"FAIBLE (5-10 {unit})", f"NIEDRIG (5-10 {unit})"), "#ADFF2F"),
        (10, 20, _ml(f"MEDIO (10-20 {unit})", f"MEDIUM (10-20 {unit})", f"MOYEN (10-20 {unit})", f"MITTEL (10-20 {unit})"), "#FFFF00"),
        (20, 30, _ml(f"ALTO (20-30 {unit})", f"HIGH (20-30 {unit})", f"ÉLEVÉ (20-30 {unit})", f"HOCH (20-30 {unit})"), "#FFA500"),
        (30, 999, _ml(f"CRÍTICO (> 30 {unit})", f"CRITICAL (> 30 {unit})", f"CRITIQUE (> 30 {unit})", f"KRITISCH (> 30 {unit})"), "#FF0000"),
    ]

    range_list = []
    for min_val, max_val, label, color in ranges:
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.setColor(QtGui.QColor(color))
        symbol.setSize(6.0)
        symbol.symbolLayer(0).setStrokeColor(QtGui.QColor("#000000"))
        symbol.symbolLayer(0).setStrokeWidth(0.5)
        range_list.append(QgsRendererRange(min_val, max_val, symbol, label))

    renderer = QgsGraduatedSymbolRenderer(field_name, range_list)
    renderer.setClassAttribute(field_name)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_labels_for_page(self, layer: QgsVectorLayer):
    """Apply labels to the output layer."""
    text_format = QgsTextFormat()
    text_format.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
    text_format.setSize(9)
    text_format.setColor(QtGui.QColor("#000000"))

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1.0)
    buffer_settings.setColor(QtGui.QColor("#FFFFFF"))
    text_format.setBuffer(buffer_settings)

    label_settings = QgsPalLayerSettings()
    label_settings.setFormat(text_format)
    unit = hours_per_year_unit()
    label_settings.fieldName = f"concat(receiver, ': ', round(hours_year, 1), ' {unit}')"
    label_settings.isExpression = True
    label_settings.placement = QgsPalLayerSettings.OrderedPositionsAroundPoint
    label_settings.dist = 2.0

    labeling = QgsVectorLayerSimpleLabeling(label_settings)
    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()
