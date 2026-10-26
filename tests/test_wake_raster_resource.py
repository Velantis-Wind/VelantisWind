# -*- coding: utf-8 -*-
"""The wake raster loads a WRG as the AEP does: Speedup none, the interpolation of the dialog and the same distance;
its cache tells them apart; the task keeps what it was created with."""
import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402

from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.ag_core import wrg_site  # noqa: E402
from VelantisWind.ag_core.resource_grid import WrgContractError  # noqa: E402
from VelantisWind.energy_core import dialog_state  # noqa: E402
from VelantisWind.energy_core.runner import EnergyRunner  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.wake_core import controller, raster  # noqa: E402
from tests.test_energy_turbine_layers import point_layer  # noqa: E402
from tests.test_resource_settings import LAYOUT, model, write_wrg  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class LoaderSpy:
    """The keyword arguments of every call to a ``load_wrg_site``, which still runs."""

    def __init__(self, real):
        self.real, self.calls = real, []

    def __call__(self, paths, **kwargs):
        self.calls.append(dict(kwargs))
        return self.real(paths, **kwargs)


class _Case(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.wrg = write_wrg(self.folder, 12)


class DialogToTaskTest(_Case):
    """V15: from the dialog's controls to the task and to the real loader, as the AEP would load the WRG."""

    def setUp(self):
        super().setUp()
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        patch = mock.patch.object(QtWidgets.QMessageBox, "warning")
        patch.start()
        self.addCleanup(patch.stop)
        self.dialog = AEPSetupDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.addCleanup(QgsProject.instance().layersWillBeRemoved.disconnect,
                        self.dialog._on_project_layers_will_be_removed)
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileNames", return_value=([self.wrg], "")), \
                mock.patch.object(self.dialog, "_draw_current_resource_extent"):
            self.dialog._pick_wrg()
        row = self.dialog._rows[0]
        row["wt"], row["name"], row["meta"] = model()["wt"], "T", {"hh": 90.0, "diam": 100.0}
        self.dialog._update_wind_speeds()
        self.dialog._rows[0]["layer_cb"].setLayer(point_layer("Layout", LAYOUT))

    def launch(self):
        captured = {}
        with mock.patch("VelantisWind.aep_setup_dialog.iface"), \
                mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(300, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a: (a[3][0], True)), \
                mock.patch.object(controller, "start_wake_raster_task",
                                  side_effect=lambda config, **_: captured.setdefault("config", config) and mock.Mock()):
            self.dialog._run_plot_wakes()
        return captured["config"]

    def test_the_task_and_the_loader_get_what_the_aep_would_use(self):
        d = self.dialog
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("linear"))
        config = self.launch()
        self.assertEqual(config.to_engine_kwargs()["wrg_wd_interp"], "linear")
        self.assertEqual(config.wake_config, d.wake_group.config())  # the physics of the group, as for the AEP
        # Changing the controls afterwards does not change the task.
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("nearest"))
        self.assertEqual(config.to_engine_kwargs()["wrg_wd_interp"], "linear")
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("linear"))
        # The real loaders: the raster's and the AEP's, with the same controls.
        raster_spy = LoaderSpy(wrg_site.load_wrg_site)
        kwargs = dict(config.to_engine_kwargs(), output_dir=self.folder, crs_authid="EPSG:32630", wd_target=270.0)
        with mock.patch.object(wrg_site, "load_wrg_site", raster_spy):
            raster.compute_wake_raster_config(**kwargs)
        aep_spy = LoaderSpy(wrg_site.load_wrg_site)
        state = dialog_state.build_energy_dialog_state(d, project_crs_authid="EPSG:32630", warn=False)
        aep_config = state.to_energy_config()
        aep_config.update_project_layers = False
        with mock.patch.object(wrg_site, "load_wrg_site", aep_spy):
            EnergyRunner().run(aep_config)
        [raster_call], [aep_call] = raster_spy.calls, aep_spy.calls
        self.assertEqual(raster_call, aep_call)  # every argument of the loader, as the AEP gives it
        self.assertEqual(raster_call["wd_interp"], "linear")
        self.assertIs(raster_call["terrain_following"], wrg_site.TERRAIN_FOLLOWING)
        self.assertEqual(raster_call.get("speedup_method", "none"), "none")
        self.assertEqual(aep_call["speedup_method"], "none")


class SpeedupTest(_Case):
    def test_another_speedup_is_refused(self):
        for method in ("global_weibull", "weibull", None):
            with self.subTest(method=method), self.assertRaises(WrgContractError):
                raster.compute_wake_raster_config([model()], wake_config=cfg.default_config(), wrg_paths=[self.wrg],
                                                  wrg_speedup_method=method, output_dir=self.folder,
                                                  crs_authid="EPSG:32630", fixed_ti=0.1)


class RasterResourceTest(_Case):
    """V16: Speedup none, a uniform free flow and the AEP's Site; the wakes show; the JSON does not say global_weibull."""

    def test_the_map(self):
        models = [model()]
        result = raster.compute_wake_raster_config(models, wake_config=cfg.default_config(), wrg_paths=[self.wrg],
                                                   resolution_m=250.0, wd_target=270.0, output_dir=self.folder,
                                                   crs_authid="EPSG:32630", wrg_wd_interp="linear", fixed_ti=0.1)
        stats = {r["variable"]: r for r in result["rasters"]}
        self.assertEqual(stats["WS"]["min"], stats["WS"]["max"])  # uniform free flow: no speed-up
        self.assertAlmostEqual(stats["WS"]["min"], 10.0)
        self.assertLess(stats["WS_eff"]["min"], stats["WS"]["min"] - 0.5)  # the wakes show
        with open(result["metadata_path"], encoding="utf-8") as fh:
            metadata = json.load(fh)
        self.assertNotIn("global_weibull", json.dumps(metadata))
        # The Site of the map is the AEP's: same climate, interpolation and distance.
        raster_site, _kind, _ti = raster._energy_site(
            wasp_dir="", wrg_paths=[self.wrg], models=models, wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="linear", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=0.1)
        aep_site, aep_ds, _label = wrg_site.load_wrg_site([self.wrg], wd_interp="linear")
        self.assertEqual(dict(raster_site.interp_method), dict(aep_site.interp_method))
        self.assertIs(type(raster_site.distance), type(aep_site.distance))
        self.assertNotIn("Speedup", raster_site.ds)
        for name in ("Sector_frequency", "Weibull_A", "Weibull_k"):
            np.testing.assert_array_equal(raster_site.ds[name].values, aep_ds[name].values)


if __name__ == "__main__":
    unittest.main()
