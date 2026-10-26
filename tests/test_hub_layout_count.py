# -*- coding: utf-8 -*-
"""The hub counts Energy's turbine layers by their turbine data, whatever their name or group."""
import os
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer  # noqa: E402

from VelantisWind.hub_dialog import _GROUP_NAME, VelantisHubDialog  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def layer(name, n, geometry="Point", role=None):
    lyr = QgsVectorLayer(f"{geometry}?crs=EPSG:32630", name, "memory")
    features = []
    for i in range(n):
        feature = QgsFeature(lyr.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000.0 + 500 * i, 4400000.0)))
        features.append(feature)
    lyr.dataProvider().addFeatures(features)
    if role:
        lyr.setCustomProperty("velantis/layer_role", role)
    return lyr


class LayoutCountTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)

    def count(self):
        return VelantisHubDialog._count_layout_layers_and_turbines(None, QgsProject.instance())

    def test_a_layer_chosen_in_energy_counts_whatever_its_name(self):
        project = QgsProject.instance()
        project.addMapLayer(layer("Layout usuario", 3, role="energy_turbines"))
        self.assertEqual(self.count(), (1, 3))

    def test_layers_of_older_projects_still_count(self):
        # Without turbine data: by the old name, or by the old group, also in a subgroup.
        project = QgsProject.instance()
        project.addMapLayer(layer("T1 (CSV)", 2))
        group = project.layerTreeRoot().addGroup(_GROUP_NAME)
        grouped, nested = layer("In the old group", 4), layer("In a subgroup", 1)
        project.addMapLayers([grouped, nested], False)
        group.addLayer(grouped)
        group.addGroup("Sub").addLayer(nested)
        self.assertEqual(self.count(), (3, 7))

    def test_a_layer_matching_several_rules_counts_once(self):
        project = QgsProject.instance()
        both = layer("T1 (CSV)", 4, role="energy_turbines")
        project.addMapLayer(both, False)
        project.layerTreeRoot().addGroup(_GROUP_NAME).addLayer(both)
        self.assertEqual(self.count(), (1, 4))

    def test_other_layers_do_not_count(self):
        # Other point layers, and the noise and shadow layouts even with an old name or in the old group.
        project = QgsProject.instance()
        project.addMapLayer(layer("Receivers", 5))
        project.addMapLayer(layer("Noise (CSV)", 2, role="turbine_layout"))
        noise = layer("Noise layout", 3, role="turbine_layout")
        project.addMapLayer(noise, False)
        project.layerTreeRoot().addGroup(_GROUP_NAME).addGroup("Sub").addLayer(noise)
        self.assertEqual(self.count(), (0, 0))


if __name__ == "__main__":
    unittest.main()
