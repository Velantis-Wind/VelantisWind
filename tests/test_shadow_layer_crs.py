# -*- coding: utf-8 -*-
"""Shadow flicker with a turbine layer in another CRS than the project: refused before calculating, and its location
detected from the layer's own CRS."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from VelantisWind import shadow_page  # noqa: E402
from VelantisWind.shadow_core.domain import ShadowRunConfig  # noqa: E402
from VelantisWind.shadow_core.validation import validate_shadow_run_config  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def layer(name, crs, x, y):
    lyr = QgsVectorLayer(f"Point?crs={crs}", name, "memory")
    feature = QgsFeature(lyr.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
    lyr.dataProvider().addFeatures([feature])
    QgsProject.instance().addMapLayer(lyr)
    return lyr


class ShadowLayerCrsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.receivers = layer("Receivers", "EPSG:32630", 500000.0, 4400000.0)

    def errors(self, turbines):
        config = ShadowRunConfig(
            turbine_layer_id=turbines.id(), receiver_layer_id=self.receivers.id(), dem_layer_id=None, latitude=40.0,
            longitude=-3.0, year=2025, timezone_mode="offset", timezone_name="", timezone_offset=1.0, observer_height_m=2.0,
            max_shadow_distance_m=2000.0, time_step_minutes=5, min_sun_elevation_deg=3.0, max_sun_elevation_deg=90.0,
            turbine_availability=1.0, use_parallel=False, num_workers=1, create_raster=False, raster_resolution_m=50.0,
            raster_timestep_minutes=10,
        )
        return validate_shadow_run_config(config)

    def test_a_turbine_layer_in_another_crs_is_refused(self):
        self.assertEqual(self.errors(layer("Same", "EPSG:32630", 500500.0, 4400000.0)), [])
        [error] = self.errors(layer("Degrees", "EPSG:4326", -3.0, 40.0))
        self.assertIn("Degrees", error)

    def test_without_a_valid_crs_is_refused(self):
        # Two invalid CRSs compare equal: the layer is refused anyway.
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem())
        [error] = self.errors(layer("No CRS", "", 500500.0, 4400000.0))
        self.assertIn("No CRS", error)

    def detect(self, turbines_id, model_rows=()):
        page = mock.Mock(_model_rows=list(model_rows))
        page.cb_turbines.currentData.return_value = turbines_id
        with mock.patch.object(shadow_page, "detect_timezone_name", return_value=("", "", "")), \
                mock.patch.object(QtWidgets.QMessageBox, "information"), mock.patch.object(QtWidgets.QMessageBox, "warning"), \
                mock.patch.object(QtWidgets.QMessageBox, "critical") as critical:
            shadow_page.ShadowPage._auto_detect_coordinates(page)
        return page, critical

    def test_a_layer_without_a_valid_crs_detects_nothing(self):
        # Its transformation is invalid and would return the points unchanged: no location is detected from them.
        no_crs = layer("No CRS", "", -3.0, 40.0)
        for selected, rows in ((no_crs.id(), ()), ("", ({"layer_id": no_crs.id()},))):
            with self.subTest(selected=bool(selected)):
                page, critical = self.detect(selected, rows)
                page.sp_latitude.setValue.assert_not_called()
                self.assertIn("No CRS", critical.call_args.args[2])

    def test_location_is_detected_from_the_layer_crs(self):
        # A turbine at 3° W, 40° N in a layer in degrees: the detected location is that one, not the degrees read as
        # project metres.
        turbines = layer("Degrees", "EPSG:4326", -3.0, 40.0)
        page = mock.Mock(_model_rows=[])
        page.cb_turbines.currentData.return_value = turbines.id()
        with mock.patch.object(shadow_page, "detect_timezone_name", return_value=("", "", "")), \
                mock.patch.object(QtWidgets.QMessageBox, "information"), mock.patch.object(QtWidgets.QMessageBox, "warning"):
            shadow_page.ShadowPage._auto_detect_coordinates(page)
        [(lat,)] = [c.args for c in page.sp_latitude.setValue.call_args_list]
        [(lon,)] = [c.args for c in page.sp_longitude.setValue.call_args_list]
        self.assertAlmostEqual(lat, 40.0, places=6)
        self.assertAlmostEqual(lon, -3.0, places=6)


if __name__ == "__main__":
    unittest.main()
