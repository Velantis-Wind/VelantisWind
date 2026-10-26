# -*- coding: utf-8 -*-
"""The interactive map only adds or deletes turbines in layers it can write, in a projected CRS in metres."""
import os
import tempfile
import types
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtCore import Qt

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402

# Without an initialised QGIS the registry only has the built-in providers; delimited text is a plugin of the install.
QgsProviderRegistry.instance(os.environ.get("QGIS_PLUGINPATH") or "/usr/lib/qgis/plugins")

from VelantisWind import i18n  # noqa: E402
from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.mapa_interactivo import _TurbineInteractiveTool  # noqa: E402

_CWD = os.getcwd()
P = [(500000.0, 4400000.0), (501000.0, 4400000.0)]


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def memory_layer(crs="EPSG:32630", points=P):
    layer = QgsVectorLayer(f"Point?crs={crs}", "Turbines", "memory")
    features = []
    for x, y in points:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    return layer


def click(x, y, button=Qt.LeftButton):
    return types.SimpleNamespace(mapPoint=lambda: QgsPointXY(x, y), button=lambda: button)


class InteractiveMapLayerTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        bar = mock.patch("VelantisWind.mapa_interactivo.iface")
        self.iface = bar.start()
        self.addCleanup(bar.stop)

    def tool(self, layer):
        self.ctl = types.SimpleNamespace(
            _get_interactive_target_layer=lambda: layer,
            _snap50=lambda v: AEPSetupDialog._snap50(None, v),
            _mark_turbines_layer_dirty=mock.Mock(),
        )
        return _TurbineInteractiveTool(self.ctl, self.canvas)

    def points(self, layer):
        return sorted((f.geometry().asPoint().x(), f.geometry().asPoint().y()) for f in layer.getFeatures())

    def warnings(self):
        return [c.args[1] for c in self.iface.messageBar().pushWarning.call_args_list]

    def assertRefused(self, layer, text, *events):
        tool = self.tool(layer)
        before = self.points(layer)
        for event in events or (click(500600.0, 4400600.0), click(*P[0], button=Qt.RightButton)):
            tool.canvasPressEvent(event)
        self.assertEqual(self.points(layer), before)
        self.ctl._mark_turbines_layer_dirty.assert_not_called()
        self.assertTrue(self.warnings())
        for warning in self.warnings():
            self.assertIn(text, warning)

    def test_memory_layer_in_metres_works_as_before(self):
        layer = memory_layer()
        tool = self.tool(layer)
        tool.canvasPressEvent(click(500612.0, 4400587.0))
        self.assertIn((500600.0, 4400600.0), self.points(layer))
        tool.canvasPressEvent(click(*P[0], button=Qt.RightButton))
        self.assertNotIn(P[0], self.points(layer))
        self.assertEqual(self.ctl._mark_turbines_layer_dirty.call_count, 2)
        self.assertEqual(self.warnings(), [])

    def test_delimited_text_layer_is_refused(self):
        if "delimitedtext" not in QgsProviderRegistry.instance().providerList():
            self.skipTest("QGIS delimited-text provider not found")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.csv")
        with open(path, "w") as fh:
            fh.write("x,y\n" + "".join(f"{x},{y}\n" for x, y in P))
        layer = QgsVectorLayer(f"file://{path}?type=csv&xField=x&yField=y&crs=EPSG:32630", "Text", "delimitedtext")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        self.assertRefused(layer, "«Text» no admite")

    def test_layer_marked_read_only_is_refused(self):
        layer = memory_layer()
        layer.setReadOnly(True)
        self.assertRefused(layer, "«Turbines» es de solo lectura.")
        self.assertEqual(sorted((f.geometry().asPoint().x(), f.geometry().asPoint().y())
                                for f in layer.dataProvider().getFeatures()), P)

    def test_layer_in_edit_mode_is_refused(self):
        # The map writes straight into the layer: with an edit session open, discarding it would not undo the change.
        layer = memory_layer()
        layer.startEditing()
        self.addCleanup(lambda: layer.rollBack() if layer.isEditable() else None)
        self.assertRefused(layer, "«Turbines» está en modo edición")
        self.assertFalse(layer.isModified())
        self.assertEqual(sorted((f.geometry().asPoint().x(), f.geometry().asPoint().y())
                                for f in layer.dataProvider().getFeatures()), P)

    def test_provider_that_declares_the_capabilities_but_does_not_save(self):
        layer = memory_layer()
        provider = mock.Mock(wraps=layer.dataProvider())
        provider.capabilities.return_value = layer.dataProvider().capabilities()
        provider.addFeatures.side_effect = lambda features: (False, features)
        provider.deleteFeatures.side_effect = lambda fids: False
        layer.dataProvider = lambda: provider
        self.assertRefused(layer, "la capa no ha guardado el cambio.")

    def test_layers_not_in_metres_are_refused(self):
        for crs in ("EPSG:4326", "EPSG:4978"):
            with self.subTest(crs=crs):
                self.iface.reset_mock()
                layer = memory_layer(crs=crs, points=[])
                self.assertRefused(layer, "proyectado y en metros", click(500600.0, 4400600.0))

    def test_click_is_transformed_to_another_crs_in_metres_and_then_snapped(self):
        # ED50 / UTM 30N is some 100 m away from WGS 84 / UTM 30N: snapping the untransformed click gives another point.
        layer = memory_layer(crs="EPSG:23030", points=[])
        clicked = QgsPointXY(500612.0, 4400587.0)
        to_layer = QgsCoordinateTransform(self.canvas.mapSettings().destinationCrs(), layer.crs(), QgsProject.instance())
        expected = to_layer.transform(clicked)
        snapped = (round(expected.x() / 50.0) * 50.0, round(expected.y() / 50.0) * 50.0)
        self.assertNotEqual(snapped, (500600.0, 4400600.0))
        self.tool(layer).canvasPressEvent(click(clicked.x(), clicked.y()))
        self.assertEqual(self.points(layer), [snapped])

    def test_map_without_a_valid_crs_writes_nothing(self):
        layer = memory_layer()
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem())
        self.assertRefused(layer, "sistema de coordenadas válido")

    def test_failed_transformation_writes_nothing(self):
        layer = memory_layer(crs="EPSG:25830")
        failing = mock.Mock()
        failing.return_value.transform.side_effect = QgsCsException("out of bounds")
        provider = mock.Mock(wraps=layer.dataProvider())
        provider.capabilities.return_value = layer.dataProvider().capabilities()
        layer.dataProvider = lambda: provider
        with mock.patch("VelantisWind.mapa_interactivo.QgsCoordinateTransform", failing):
            self.assertRefused(layer, "out of bounds")
        provider.addFeatures.assert_not_called()
        provider.deleteFeatures.assert_not_called()

    def test_messages_are_translated(self):
        texts = (
            "El mapa interactivo solo edita capas en un sistema de coordenadas proyectado y en metros.",
            "No se pudo pasar el clic al sistema de coordenadas de la capa: {error}",
            "La capa «{layer}» no admite añadir turbinas.",
            "La capa «{layer}» no admite borrar turbinas.",
            "la capa no ha guardado el cambio.",
            "el mapa o la capa no tienen un sistema de coordenadas válido",
        )
        for lang in ("en", "fr", "de"):
            table = i18n._STATE["full"][lang]
            for text in texts:
                with self.subTest(lang=lang, text=text[:30]), mock.patch.object(i18n, "current_language", return_value=lang):
                    self.assertEqual(i18n.tr_text(text), table[text])
                    self.assertNotEqual(table[text], text)


if __name__ == "__main__":
    unittest.main()
