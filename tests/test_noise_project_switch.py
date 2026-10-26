# -*- coding: utf-8 -*-
"""Regression (#51 for Noise, #54): a background Noise result never enters a different QGIS project, and all its
layers keep the CRS it was calculated in."""
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402

from VelantisWind.noise_core import task_controller  # noqa: E402
from VelantisWind.noise_core.qgis_io import layers as noise_layers  # noqa: E402
from VelantisWind.noise_core.qgis_io.apply_results import apply_noise_task_result  # noqa: E402
from VelantisWind.noise_core.raster.task import NoiseGridTask  # noqa: E402
from tests.test_energy_project_crs import DERIVED_PROJECTED  # noqa: E402

_UI = ("_set_dialog_busy", "_show_task_progress_dialog", "_update_task_progress_dialog", "_close_task_progress_dialog",
       "_set_dialog_progress", "_notify_qgis", "_append_status_line", "_set_calculate_enabled",
       "_hide_dialog_progress", "_finish_dialog_progress", "_append_result_status")


class NoiseProjectSwitchTest(unittest.TestCase):
    def setUp(self):
        project = QgsProject.instance()
        project.clear()
        self.addCleanup(project.clear)
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.project = project
        for name in _UI:
            patcher = mock.patch.object(task_controller, name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_every_layer_of_a_background_result_keeps_the_crs_of_its_calculation(self):
        derived = QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED)
        snapshot = {"crs_wkt": DERIVED_PROJECTED, "receivers": [{"feature_id": 1, "x": 500.0, "y": 4000.0}]}
        payload = apply_noise_task_result(snapshot, {"evaluation": {"uncovered_ids": [1]}})  # the project: EPSG:32630
        self.assertTrue(payload)
        for name in ("Noise · Receivers", "Noise · Sources", "Noise · Dominant links", "Noise · Receivers outside radius"):
            with self.subTest(layer=name):
                layers = self.project.mapLayersByName(name)
                self.assertEqual(len(layers), 1)
                self.assertEqual(layers[0].crs(), derived)

    def launch_full(self):
        """The full calculation launched in the background; returns its on_finished and the patched application."""
        callbacks = {}

        def start(_snapshot, *, on_finished, **_kwargs):
            callbacks["finished"] = on_finished
            return mock.Mock()

        apply = mock.patch("VelantisWind.noise_core.qgis_io.apply_results.apply_noise_task_result",
                           return_value={})
        self.apply = apply.start()
        self.addCleanup(apply.stop)
        with mock.patch("VelantisWind.noise_core.snapshot.builder.build_noise_calculation_snapshot",
                        return_value={"params": {}}), \
                mock.patch("VelantisWind.noise_core.tasks.noise_task.start_noise_calculation_task", side_effect=start):
            self.assertTrue(task_controller._run_full_noise_task_from_dialog(mock.Mock(), mock.Mock(), []))
        return callbacks["finished"]

    def test_a_full_calculation_is_not_added_to_another_project(self):
        finished = self.launch_full()
        self.project.clear()  # QGIS opens or creates another project while the task runs
        with mock.patch.object(task_controller.QtWidgets.QMessageBox, "warning") as warning, \
                mock.patch.object(task_controller, "NoiseResultsDialog") as results:
            finished(True, {"grid_diag": {"grid_path": "/kept/here/grid.tif"}}, None)
        self.apply.assert_not_called()
        results.assert_not_called()
        self.assertIn("/kept/here", warning.call_args.args[2])

    def test_a_full_calculation_in_the_same_project_is_added(self):
        finished = self.launch_full()
        with mock.patch.object(task_controller.QtWidgets.QMessageBox, "warning"), \
                mock.patch.object(task_controller.QtWidgets.QMessageBox, "information"), \
                mock.patch.object(task_controller, "NoiseResultsDialog"):
            finished(True, {}, None)
        self.apply.assert_called_once()

    def test_isophones_keep_the_crs_of_their_raster(self):
        import os
        import numpy as np
        from osgeo import gdal, osr
        path = os.path.join(_SETTINGS.name, "grid.tif")
        ds = gdal.GetDriverByName("GTiff").Create(path, 20, 20, 1, gdal.GDT_Float32)
        ds.SetGeoTransform((500000.0, 10.0, 0.0, 4000200.0, 0.0, -10.0))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(25830)
        ds.SetProjection(srs.ExportToWkt())
        ds.GetRasterBand(1).WriteArray(np.add.outer(np.arange(20.0), np.arange(20.0)) + 30.0)
        ds = None
        iso = noise_layers._build_isophones_layer_from_raster(self.project, path, [40.0], "Noise · Isophones")
        self.assertIsNotNone(iso)
        self.assertEqual(iso.crs().authid(), "EPSG:25830")  # the raster's, not the project's EPSG:32630

    def watched(self):
        created = []

        class Spy(task_controller.ProjectWatch):
            def __init__(self):
                super().__init__()
                created.append(self)

        patcher = mock.patch.object(task_controller, "ProjectWatch", Spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return created

    def test_a_cancelled_or_failed_full_calculation_adds_nothing_and_stops_watching(self):
        for error in ("cancelled", "failed"):
            with self.subTest(error=error):
                created = self.watched()
                finished = self.launch_full()
                with mock.patch.object(task_controller.QtWidgets.QMessageBox, "critical"):
                    finished(False, {}, error)
                self.apply.assert_not_called()
                self.assertEqual(created[-1]._signals, [])

    def test_a_full_calculation_that_cannot_start_stops_watching(self):
        created = self.watched()
        with mock.patch("VelantisWind.noise_core.snapshot.builder.build_noise_calculation_snapshot",
                        return_value={"params": {}}), \
                mock.patch("VelantisWind.noise_core.tasks.noise_task.start_noise_calculation_task",
                           side_effect=RuntimeError("no task manager")), \
                mock.patch.object(task_controller.QtWidgets.QMessageBox, "critical"):
            self.assertFalse(task_controller._run_full_noise_task_from_dialog(mock.Mock(), mock.Mock(), []))
        self.assertEqual(created[-1]._signals, [])

    def test_a_noise_raster_is_not_added_to_another_project(self):
        received = []
        task = NoiseGridTask(params={"layer_name": "Noise · Map"},
                             on_finished=lambda ok, diag, grid, iso, error: received.append((ok, grid, error)))
        task.diag = {"grid_path": "/kept/here/grid.tif"}
        self.project.clear()
        task.finished(True)
        self.assertTrue(task.project_changed)
        ok, grid, error = received[-1]
        self.assertFalse(ok)
        self.assertIsNone(grid)
        self.assertIn("/kept/here", error)
        self.assertEqual(self.project.mapLayersByName("Noise · Map"), [])

    def test_the_project_signals_are_released_when_a_raster_finishes(self):
        task = NoiseGridTask(params={}, on_finished=None)
        task.error = "failed"
        task.finished(False)
        self.assertEqual(task._project_watch._signals, [])
        self.assertFalse(task.project_changed)


if __name__ == "__main__":
    unittest.main()
