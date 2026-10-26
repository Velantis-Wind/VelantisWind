# -*- coding: utf-8 -*-
"""Regression: a background wake raster must never enter a different QGIS project."""
import os
import gc
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402

from VelantisWind.wake_core import controller  # noqa: E402


class WakeRasterProjectSwitchTest(unittest.TestCase):
    def setUp(self):
        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.addCleanup(project.clear)

    def launch(self):
        callbacks = {}
        dialog = mock.Mock(_wake_raster_task=None)

        def start(_config, *, on_finished, on_progress, **_kwargs):
            callbacks["finished"] = on_finished
            callbacks["progress"] = on_progress
            return mock.Mock()

        with mock.patch.object(controller, "start_wake_raster_task", side_effect=start):
            task = controller.start_wake_raster_from_dialog(
                dialog, models=[], wasp_dir="", resolution_m=300.0,
                wrg_paths=[], wake_config=None, wd_target=270.0,
            )
        self.assertIsNotNone(task)
        return dialog, callbacks

    def test_the_ti_target_is_the_captured_crs_even_without_an_identifier(self):
        # #54: a CRS without an identifier reaches the TI of the raster as its WKT2, captured at launch; the worker
        # never reads the project, which may have changed by then (it fell back to the fixed TI or another CRS).
        from tests.test_energy_project_crs import CUSTOM, DERIVED_PROJECTED
        for crs in (QgsCoordinateReferenceSystem.fromProj(CUSTOM), QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED),
                    QgsCoordinateReferenceSystem("EPSG:32630")):
            with self.subTest(crs=crs.description()):
                QgsProject.instance().setCrs(crs)
                configs = []

                def start(config, **_kwargs):
                    configs.append(config)
                    return mock.Mock()

                with mock.patch.object(controller, "start_wake_raster_task", side_effect=start):
                    controller.start_wake_raster_from_dialog(
                        mock.Mock(_wake_raster_task=None), models=[], wasp_dir="", resolution_m=300.0,
                        wrg_paths=[], wake_config=None, wd_target=270.0)
                config = configs[-1]
                if crs.authid() and not crs.authid().upper().startswith("USER:"):
                    self.assertEqual(config.project_crs_authid, crs.authid())
                else:
                    self.assertTrue(config.crs_wkt)
                    self.assertEqual(config.project_crs_authid, config.crs_wkt)
                    self.assertNotIn("USER:", config.project_crs_authid)

    def test_normal_completion_adds_raster(self):
        dialog, callbacks = self.launch()
        with mock.patch.object(controller, "add_wake_raster_result_to_qgis", return_value=[]) as load, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "information") as info, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warn:
            callbacks["finished"](True, {"path": "/tmp/park-a/ws_eff.tif"}, None)
        load.assert_called_once()
        info.assert_called_once()
        warn.assert_not_called()
        self.assertTrue(dialog._wake_raster_task_finished)

    def test_project_switch_after_garbage_collection_still_blocks_the_raster(self):
        _dialog, callbacks = self.launch()
        gc.collect()
        QgsProject.instance().clear()
        with mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warn:
            callbacks["finished"](True, {"path": "/tmp/a.tif"}, None)
        load.assert_not_called()
        warn.assert_called_once()

    def test_clearing_project_disables_load_but_keeps_files(self):
        _dialog, callbacks = self.launch()
        QgsProject.instance().clear()  # QGIS creates an empty project B in the same singleton.
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        with mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warn, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "information") as info:
            callbacks["finished"](True, {"path": "/tmp/park-a/ws_eff.tif"}, None)
        load.assert_not_called()
        info.assert_not_called()
        warn.assert_called_once()
        self.assertIn("/tmp/park-a", warn.call_args.args[2])

    def test_opening_another_project_does_not_import_raster(self):
        with tempfile.TemporaryDirectory() as folder:
            project_b = os.path.join(folder, "b.qgz")
            project = QgsProject.instance()
            self.assertTrue(project.write(project_b))
            project.clear()
            project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
            _dialog, callbacks = self.launch()  # The task belongs to A.
            self.assertTrue(project.read(project_b))  # Load B without closing QGIS.
            with mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load, \
                    mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warn:
                callbacks["finished"](True, {"path": os.path.join(folder, "a.tif")}, None)
            load.assert_not_called()
            warn.assert_called_once()

    def test_failed_task_never_imports_or_claims_success(self):
        _dialog, callbacks = self.launch()
        with mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "critical") as error:
            callbacks["finished"](False, {}, "calculation failed")
        load.assert_not_called()
        error.assert_called_once()

    def test_cancelled_task_restores_dialog_without_importing_layers(self):
        dialog, callbacks = self.launch()
        with mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load, \
                mock.patch.object(controller, "_message_bar") as message, \
                mock.patch.object(controller.QtWidgets.QMessageBox, "critical") as error:
            callbacks["finished"](False, {}, "Tarea de ráster de estelas cancelada.")
        load.assert_not_called()
        error.assert_not_called()
        message.assert_called_once()
        self.assertTrue(dialog._wake_raster_task_finished)
        self.assertIsNone(dialog._wake_raster_task)

    def test_project_signal_connections_are_released_after_every_finish(self):
        project = QgsProject.instance()
        for ok, result, error in ((True, {"path": "/tmp/a.tif"}, None),
                                  (False, {}, "failed"), (False, {}, "cancelled")):
            with self.subTest(ok=ok, error=error):
                before = [project.receivers(project.cleared), project.receivers(project.readProject)]
                _dialog, callbacks = self.launch()
                self.assertEqual(
                    [project.receivers(project.cleared), project.receivers(project.readProject)],
                    [n + 1 for n in before],
                )
                with mock.patch.object(controller, "add_wake_raster_result_to_qgis", return_value=[]), \
                        mock.patch.object(controller.QtWidgets.QMessageBox, "information"), \
                        mock.patch.object(controller.QtWidgets.QMessageBox, "critical"), \
                        mock.patch.object(controller, "_message_bar"):
                    callbacks["finished"](ok, result, error)
                self.assertEqual(
                    [project.receivers(project.cleared), project.receivers(project.readProject)], before,
                )

    def test_failed_launch_releases_project_signals_and_restores_button(self):
        project = QgsProject.instance()
        before = [project.receivers(project.cleared), project.receivers(project.readProject)]
        dialog = mock.Mock(_wake_raster_task=None)
        with mock.patch.object(controller, "start_wake_raster_task", side_effect=RuntimeError("start failed")):
            with self.assertRaisesRegex(RuntimeError, "start failed"):
                controller.start_wake_raster_from_dialog(
                    dialog, models=[], wasp_dir="", resolution_m=300.0, wrg_paths=[],
                    wake_config=None, wd_target=270.0,
                )
        self.assertEqual([project.receivers(project.cleared), project.receivers(project.readProject)], before)
        self.assertTrue(dialog._wake_raster_task_finished)
        dialog.btn_plot_wakes.setEnabled.assert_called_with(True)


if __name__ == "__main__":
    unittest.main()
