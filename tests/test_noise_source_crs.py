# -*- coding: utf-8 -*-
"""Noise refuses, before calculating, a turbine layer in another CRS than the project instead of leaving it out."""
import os
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer  # noqa: E402

from VelantisWind.noise_core.domain import NoiseRunConfig  # noqa: E402
from VelantisWind.noise_core.validation import validate_run_config  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def layer(name, crs, model_name=""):
    lyr = QgsVectorLayer(f"Point?crs={crs}", name, "memory")
    feature = QgsFeature(lyr.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000.0, 4400000.0) if crs != "EPSG:4326" else QgsPointXY(-3.0, 40.0)))
    lyr.dataProvider().addFeatures([feature])
    if model_name:
        lyr.setCustomProperty("velantis/model_name", model_name)
    QgsProject.instance().addMapLayer(lyr)
    return lyr


class SourceLayerCrsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.receivers = layer("Receivers", "EPSG:32630")

    def errors(self, source_ids):
        errors, _warnings = validate_run_config(NoiseRunConfig(receiver_layer=self.receivers, model_cfg={}, source_layer_ids=source_ids))
        return [e for e in errors if "Capa de turbinas" in e or "capa de turbinas" in e]

    def test_a_chosen_layer_in_another_crs_is_refused(self):
        same = layer("Same", "EPSG:32630", "T1")
        other = layer("Other", "EPSG:4326", "T2")
        self.assertEqual(self.errors([same.id(), other.id()]),
                         ["La capa de turbinas «Other» no está en el sistema de coordenadas del proyecto: reproyéctala."])

    def test_a_layer_in_another_crs_that_is_not_chosen_does_not_matter(self):
        same = layer("Same", "EPSG:32630", "T1")
        layer("Other", "EPSG:4326", "T2")
        self.assertEqual(self.errors([same.id()]), [])

    def test_without_a_choice_every_turbine_layer_counts(self):
        layer("Same", "EPSG:32630", "T1")
        layer("Other", "EPSG:4326", "T2")
        self.assertEqual(len(self.errors([])), 1)


if __name__ == "__main__":
    unittest.main()
