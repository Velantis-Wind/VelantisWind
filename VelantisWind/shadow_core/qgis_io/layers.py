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


def create_results_layer_for_page(self, results: List[ShadowFlickerResult], receiver_layer: QgsVectorLayer, 
                          turbines: List[dict], calculator):
    """Create shadow flicker output layer."""
    prj = QgsProject.instance()

    # Create fields
    fields = QgsFields()
    fields.append(QgsField("receiver", QtCore.QVariant.String))
    fields.append(QgsField("hours_year", QtCore.QVariant.Double))
    fields.append(QgsField("hours_real", QtCore.QVariant.Double))
    fields.append(QgsField("minutes", QtCore.QVariant.Int))
    fields.append(QgsField("days_affected", QtCore.QVariant.Int))
    fields.append(QgsField("max_min_day", QtCore.QVariant.Int))
    fields.append(QgsField("exceeds_30h", QtCore.QVariant.String))
    fields.append(QgsField("exceeds_30m", QtCore.QVariant.String))
    fields.append(QgsField("category", QtCore.QVariant.String))  # Visual category
    fields.append(QgsField("severity", QtCore.QVariant.Int))  # 0-4 for sorting

    # Monthly fields (monthly fields)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, month_name in enumerate(month_names, start=1):
        fields.append(QgsField(f"h_{month_name}", QtCore.QVariant.Double))

    # Create layer
    layer_name = f"Shadow_Flicker_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result_layer = QgsVectorLayer(
        f"Point?crs={receiver_layer.crs().authid()}",
        layer_name,
        "memory"
    )
    result_layer.dataProvider().addAttributes(fields)
    result_layer.updateFields()
    result_layer.setCustomProperty("velantis/shadow_output", True)

    # Add features
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

        # Classify by severity
        h = result.hours_per_year_astronomical
        if h >= 30:
            category = "CRITICAL"
            severity = 4
            exceeds_30h = "Yes"
        elif h >= 20:
            category = "HIGH"
            severity = 3
            exceeds_30h = "No"
        elif h >= 10:
            category = "MEDIUM"
            severity = 2
            exceeds_30h = "No"
        elif h >= 5:
            category = "LOW"
            severity = 1
            exceeds_30h = "No"
        else:
            category = "VERY LOW"
            severity = 0
            exceeds_30h = "No"

        feat.setAttribute("exceeds_30h", exceeds_30h)
        feat.setAttribute("exceeds_30m", "Yes" if result.max_minutes_per_day > 30 else "No")
        feat.setAttribute("category", category)
        feat.setAttribute("severity", severity)

        # Monthly breakdown (monthly fields)
        monthly = result.monthly_breakdown()
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for month_num, month_name in enumerate(month_names, start=1):
            feat.setAttribute(f"h_{month_name}", monthly.get(month_num, 0.0))

        features.append(feat)

    result_layer.dataProvider().addFeatures(features)
    result_layer.updateExtents()

    # Add to project
    prj.addMapLayer(result_layer)

    # Apply enhanced symbology
    self._apply_result_symbology(result_layer)

    # Apply labels
    self._apply_labels(result_layer)

    # FINAL SUMMARY (summary)
    self._show_calculation_summary(results, turbines, calculator)

def apply_result_symbology_for_page(self, layer: QgsVectorLayer):
    """Apply enhanced symbology to the output layer."""
    from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsStyle

    # Graduated classification by hours_year
    field_name = "hours_year"

    # Shadow ranges with more distinctive colors
    ranges = [
        (0, 5, "VERY LOW (< 5 h/year)", "#90EE90"),      # Light green
        (5, 10, "LOW (5-10 h/year)", "#ADFF2F"),        # Lime green
        (10, 20, "MEDIUM (10-20 h/year)", "#FFFF00"),     # Yellow
        (20, 30, "HIGH (20-30 h/year)", "#FFA500"),      # Orange
        (30, 999, "CRITICAL (> 30 h/year)", "#FF0000"),   # Red
    ]

    range_list = []
    for min_val, max_val, label, color in ranges:
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.setColor(QtGui.QColor(color))
        symbol.setSize(6.0)  # Larger for better visibility

        # Add black outline for better contrast
        symbol.symbolLayer(0).setStrokeColor(QtGui.QColor("#000000"))
        symbol.symbolLayer(0).setStrokeWidth(0.5)

        range_obj = QgsRendererRange(min_val, max_val, symbol, label)
        range_list.append(range_obj)

    # Create and apply renderer
    renderer = QgsGraduatedSymbolRenderer(field_name, range_list)
    renderer.setClassAttribute(field_name)
    layer.setRenderer(renderer)
    layer.triggerRepaint()

def apply_labels_for_page(self, layer: QgsVectorLayer):
    """Apply labels to the output layer."""
    from qgis.core import QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling

    # Configure text format
    text_format = QgsTextFormat()
    text_format.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
    text_format.setSize(9)
    text_format.setColor(QtGui.QColor("#000000"))

    # Add white buffer/halo for readability
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1.0)
    buffer_settings.setColor(QtGui.QColor("#FFFFFF"))
    text_format.setBuffer(buffer_settings)

    # Configure labels
    label_settings = QgsPalLayerSettings()
    label_settings.setFormat(text_format)

    # Display: "Receiver: XX.X h/year"
    label_settings.fieldName = "concat(receiver, ': ', round(hours_year, 1), ' h/year')"
    label_settings.isExpression = True

    # Position above point - use correct enum for QGIS 3.x
    from qgis.core import QgsPalLayerSettings
    label_settings.placement = QgsPalLayerSettings.OrderedPositionsAroundPoint
    label_settings.dist = 2.0

    # Apply
    labeling = QgsVectorLayerSimpleLabeling(label_settings)
    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

