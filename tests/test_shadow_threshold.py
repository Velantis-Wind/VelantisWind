# -*- coding: utf-8 -*-
"""Shadow flicker: exactly 30 h/year does not exceed the limit, in the summary's classification and the results layer,
and the layer's symbology gives every value a class."""
import os
import tempfile
import unittest

import numpy

from qgis.PyQt import QtCore, QtGui, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsVectorLayer  # noqa: E402

from VelantisWind.shadow_core.qgis_io import layers  # noqa: E402
from VelantisWind.shadow_core.results import summary  # noqa: E402
from VelantisWind.shadow_core.shadow_calculator import ShadowFlickerResult  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class ThirtyHoursTest(unittest.TestCase):
    def test_exactly_thirty_hours_is_high_not_critical(self):
        _, level, _ = summary._severity(30.0, 0)
        self.assertEqual(level, 3)
        _, severity, exceeds = layers._category(30.0)
        self.assertEqual(severity, 3)
        self.assertFalse(exceeds)

    def test_above_thirty_hours_or_thirty_minutes_a_day_is_critical(self):
        self.assertEqual(summary._severity(30.01, 0)[1], 4)
        self.assertEqual(summary._severity(10.0, 31)[1], 4)
        self.assertEqual(layers._category(30.01)[1:], (4, True))

    def test_exactly_thirty_minutes_a_day_does_not_exceed_either(self):
        self.assertNotEqual(summary._severity(30.0, 30)[1], 4)
        self.assertEqual(summary._severity(30.0, 31)[1], 4)

    def test_the_symbology_puts_thirty_hours_in_high_and_gives_every_value_a_class(self):
        layer = QgsVectorLayer("Point?field=hours_year:double", "shadow", "memory")
        layers.apply_result_symbology_for_page(None, layer)
        renderer = layer.renderer()
        self.assertEqual(renderer.symbolForValue(30.0).color(), QtGui.QColor("#FFA500"))  # ALTO (20-30)
        self.assertEqual(renderer.symbolForValue(30.01).color(), QtGui.QColor("#FF0000"))  # CRÍTICO
        self.assertIsNotNone(renderer.symbolForValue(1000.0))
        self.assertIsNotNone(renderer.symbolForValue(8784.0))

    def test_the_raster_legend_has_red_only_above_thirty_hours(self):
        from osgeo import gdal
        from qgis.core import QgsRasterLayer
        from VelantisWind.shadow_core.raster import map as raster_map

        for maximum, red in ((20.0, False), (30.0, False), (1805 / 60, True), (31.0, True), (80.0, True)):
            with self.subTest(maximum=maximum):
                path = os.path.join(_SETTINGS.name, f"shadow_{maximum:.4f}.tif")
                ds = gdal.GetDriverByName("GTiff").Create(path, 2, 1, 1, gdal.GDT_Float32)
                ds.GetRasterBand(1).WriteArray(numpy.array([[0.0, maximum]], dtype="float32"))
                ds = None
                layer = QgsRasterLayer(path, "shadow", "gdal")
                raster_map.apply_raster_symbology_for_page(None, layer)
                items = layer.renderer().shader().rasterShaderFunction().colorRampItemList()
                values = [item.value for item in items]
                self.assertEqual(values, sorted(values))
                self.assertEqual(len(values), len(set(values)))
                labels = [item.label for item in items]
                self.assertEqual(len(labels), len(set(labels)), labels)
                self.assertEqual(any(item.color == QtGui.QColor(255, 0, 0) for item in items), red)
                shaded = layer.renderer().shader().shade(30.0)
                self.assertEqual((shaded[1], shaded[2], shaded[3]), (255, 165, 0))  # 30 h/year is orange

    def test_the_calculator_and_the_summary_agree_at_thirty_hours(self):
        result = ShadowFlickerResult.__new__(ShadowFlickerResult)
        result.hours_per_year_astronomical = 30.0
        result.max_minutes_per_day = 0
        self.assertFalse(result.exceeds_threshold())
        self.assertNotEqual(summary._severity(result.hours_per_year_astronomical, result.max_minutes_per_day)[1], 4)


if __name__ == "__main__":
    unittest.main()
