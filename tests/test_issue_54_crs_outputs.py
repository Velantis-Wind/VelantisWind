# -*- coding: utf-8 -*-
"""Regression checks for #54: derived and QGIS-local CRSes across QGIS outputs."""
import tempfile
import unittest
import math
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsProject  # noqa: E402

from tests.test_energy_project_crs import DERIVED_PROJECTED  # noqa: E402
from VelantisWind.crs_utils import memory_layer_with_crs, portable_crs_definition, preferred_wkt  # noqa: E402
from VelantisWind.ag_core.qgis_io import resource_extent  # noqa: E402
from VelantisWind.noise_core.qgis_io import layers as noise_layers  # noqa: E402
from VelantisWind.noise_core.noise_compute import compute_noise  # noqa: E402
from VelantisWind.noise_core.qgis_io.apply_results import apply_noise_task_result  # noqa: E402
from VelantisWind.shadow_core.qgis_io.layers import create_results_layer_for_page  # noqa: E402
from VelantisWind.wake_core import controller as wake_controller  # noqa: E402


class CRSOutputRoundTripTest(unittest.TestCase):
    def setUp(self):
        project = QgsProject.instance()
        project.clear()
        self.addCleanup(project.clear)
        self.derived = QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED)
        self.assertTrue(self.derived.isValid())
        self.assertFalse(self.derived.authid())
        self.assertFalse(self.derived.toWkt())
        project.setCrs(self.derived)
        self.project = project

    def test_portable_crs_uses_wkt2_for_local_id(self):
        fake = mock.Mock()
        fake.isValid.return_value = True
        fake.authid.return_value = "USER:100000"
        fake.toWkt.return_value = preferred_wkt(self.derived)
        self.assertEqual(portable_crs_definition(fake), preferred_wkt(self.derived))
        self.assertEqual(portable_crs_definition(self.derived), preferred_wkt(self.derived))
        self.assertEqual(portable_crs_definition(QgsCoordinateReferenceSystem("EPSG:32630")), "EPSG:32630")

    def test_memory_layer_assigns_actual_crs_instead_of_epsg_fallback(self):
        layer = memory_layer_with_crs("Point", "custom", self.derived)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.crs(), self.derived)
        self.assertNotEqual(layer.crs().authid(), "EPSG:25830")

    def test_memory_layer_rejects_invalid_crs_explicitly(self):
        with self.assertRaises(ValueError):
            memory_layer_with_crs("Point", "invalid", QgsCoordinateReferenceSystem())
        self.assertEqual(self.project.mapLayers(), {})

    def test_wake_raster_context_does_not_persist_local_user_authid(self):
        local = mock.Mock(wraps=self.derived)
        local.authid.return_value = "USER:100000"
        project = mock.Mock()
        project.crs.return_value = local
        project.homePath.return_value = ""
        with mock.patch.object(wake_controller.QgsProject, "instance", return_value=project):
            context = wake_controller._capture_project_context()
        self.assertEqual(context[2], "")
        self.assertEqual(context[1], preferred_wkt(self.derived))

    def test_resource_extent_keeps_the_derived_project_crs(self):
        self.assertEqual(resource_extent._project_crs_authid(), preferred_wkt(self.derived))
        layer = resource_extent.add_extent_layer((500000, 501000, 4400000, 4401000), source_type="WRG")
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.crs(), self.derived)
        self.assertEqual(layer.featureCount(), 1)

    def test_resource_extent_rejects_invalid_explicit_crs_without_removing_old_layer(self):
        layer = resource_extent.add_extent_layer((0, 1, 0, 1), source_type="WRG")
        with self.assertRaises(ValueError):
            resource_extent.add_extent_layer((0, 1, 0, 1), source_type="WRG", crs_authid="not-a-crs")
        self.assertIsNotNone(self.project.mapLayer(layer.id()))

    def test_resource_extent_keeps_old_layer_when_replacement_cannot_be_created(self):
        layer = resource_extent.add_extent_layer((0, 1, 0, 1), source_type="WRG")
        layer_id = layer.id()
        with mock.patch.object(
            resource_extent,
            "memory_layer_with_crs",
            side_effect=RuntimeError("memory provider failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "memory provider failed"):
                resource_extent.add_extent_layer((2, 3, 2, 3), source_type="WRG")
        self.assertIsNotNone(self.project.mapLayer(layer_id))

    def test_noise_source_and_dominant_links_keep_project_crs(self):
        sources = noise_layers._build_source_layer(self.project, [], {}, "Noise custom sources")
        links = noise_layers._build_dominant_links_layer(self.project, [], "Noise custom links")
        self.assertEqual(sources.crs(), self.derived)
        self.assertEqual(links.crs(), self.derived)

    def test_invalid_noise_result_crs_does_not_remove_previous_outputs(self):
        previous = [memory_layer_with_crs("Point", name, self.derived)
                    for name in ("Noise · Receivers", "Noise · Sources", "Noise · Dominant links")]
        previous_ids = [layer.id() for layer in previous]
        for layer in previous:
            self.project.addMapLayer(layer)
        with self.assertRaises(ValueError):
            apply_noise_task_result({"crs_authid": "not-a-crs"}, {})
        self.assertTrue(all(self.project.mapLayer(layer_id) is not None for layer_id in previous_ids))

    def test_sync_noise_with_landuse_keeps_derived_crs_and_receiver_coordinates(self):
        sources = memory_layer_with_crs("Point", "T1", self.derived)
        sources.setCustomProperty("velantis/model_name", "T1")
        receivers = memory_layer_with_crs("Point", "receivers", self.derived)
        for layer, x in ((sources, 500000.0), (receivers, 500500.0)):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 4400000.0)))
            self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
            layer.updateExtents()
            self.project.addMapLayer(layer)
        landuse = memory_layer_with_crs("Polygon", "landuse", self.derived)
        self.project.addMapLayer(landuse)

        # Land-use polygons select this synchronous calculation route in the UI.
        # Exercise the real evaluator and output layer, not just the CRS helper.
        compute_noise(
            receivers, {"T1": {"lwa": 105.0, "hub_height": 100.0}},
            source_layer_ids=[sources.id()], ground_mode="landuse", landuse_layer=landuse,
        )

        [result] = self.project.mapLayersByName("Noise · Receivers")
        self.assertEqual(result.crs(), self.derived)
        self.assertEqual(result.featureCount(), 1)
        output = next(result.getFeatures())
        self.assertEqual(output.geometry().asPoint(), QgsPointXY(500500.0, 4400000.0))
        self.assertTrue(math.isfinite(float(output["noise_dba"])))

    def test_shadow_result_layer_keeps_receiver_crs(self):
        receiver_layer = memory_layer_with_crs("Point", "receivers", self.derived)
        before = set(self.project.mapLayers())
        page = mock.Mock()
        create_results_layer_for_page(page, [], receiver_layer, [], None)
        added = [layer for id_, layer in self.project.mapLayers().items() if id_ not in before]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].crs(), self.derived)

    def test_wake_raster_context_uses_preferred_wkt2(self):
        context = wake_controller._capture_project_context()
        self.assertEqual(context[1], preferred_wkt(self.derived))
        self.assertIn("DERIVEDPROJCRS[", context[1])


if __name__ == "__main__":
    unittest.main()
