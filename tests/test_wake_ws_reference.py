# -*- coding: utf-8 -*-
"""The reference of the deficit's scaling (``deficit_ws_reference``) and the predefined TurbOPark (plan of the
predefined models, M4): the contract, the construction and the reading, the fidelity with ``Nygaard_2022`` in a uniform
and in a non-uniform site, and the consumers. The parity with the first step, process by process, is a local test."""
import json
import os
import tempfile
import unittest
import warnings
from unittest import mock

import numpy as np
from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core import aep_compute as ac  # noqa: E402
from VelantisWind.ag_core.results import breakdown as bd  # noqa: E402
from VelantisWind.ag_core.results import variants as vr  # noqa: E402
from VelantisWind.ag_core.results.model_config_html import model_config_html  # noqa: E402
from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, simulation_wind_turbines  # noqa: E402
from VelantisWind.ag_core.wake_setup import api  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import factory as fac  # noqa: E402
from VelantisWind.ag_core.wake_setup import presets as ps  # noqa: E402
from VelantisWind.ag_core.wake_setup import readers as rd  # noqa: E402
from VelantisWind.ag_core.wake_setup import validation as val  # noqa: E402
from VelantisWind.wake_core import engine, raster  # noqa: E402

warnings.filterwarnings("ignore", module="py_wake")

from py_wake import HorizontalGrid  # noqa: E402
from py_wake import literature as lit  # noqa: E402
from py_wake.deficit_models.gaussian import TurboGaussianDeficit  # noqa: E402
from py_wake.deficit_models.utils import ct2a_mom1d  # noqa: E402
from py_wake.ground_models import Mirror  # noqa: E402
from py_wake.rotor_avg_models import CGIRotorAvg  # noqa: E402
from py_wake.superposition_models import SquaredSum  # noqa: E402
from py_wake.wind_farm_models import PropagateDownwind  # noqa: E402
from py_wake.examples.data.ParqueFicticio import ParqueFicticioSite  # noqa: E402

from tests.test_resource_settings import model, write_wrg  # noqa: E402
from tests.test_wake_setup_factory import SITE, WT, X, Y, WD, WS  # noqa: E402

_CWD = os.getcwd()
REF = cfg.DESTINATION_FREE_STREAM
TURBOPARK = ps.config("TurbOPark")
WITHOUT = cfg.WakeConfig(**{**TURBOPARK.__dict__, "deficit_ws_reference": None})  # the control: no adjustment
# TurbOPark adapted with «Continuar», without the libraries of GaussianOverlapAvgModel (decision 17 of the predefined
# models), and its control without the adjustment.
ADAPTED = api.gaussian_overlap_adaptation(TURBOPARK, ["h5py"])
ADAPTED_WITHOUT = cfg.WakeConfig(**{**ADAPTED.__dict__, "deficit_ws_reference": None})
PF = ParqueFicticioSite()
PX, PY = PF.initial_position.T
SITES = {  # name: (site, x, y, grid of a small map, wind direction of the map)
    "uniform": (SITE, X, Y, HorizontalGrid(x=np.linspace(-300, 1400, 4), y=np.linspace(-200, 500, 3)), 270.0),
    "non_uniform": (PF, PX, PY, HorizontalGrid(x=np.linspace(263300, 264500, 4), y=np.linspace(6504900, 6506600, 3)),
                    0.0),
}


def nygaard_cgi7(site, turbines):
    """Nygaard_2022 as PyWake 2.6.18 builds it, by hand (its signature takes no rotor), with CGIRotorAvg(7)."""
    deficit = TurboGaussianDeficit(ct2a=ct2a_mom1d, groundModel=Mirror(superpositionModel=SquaredSum()),
                                   rotorAvgModel=CGIRotorAvg(7), ctlim=0.96)
    deficit.WS_key = "WS_jlk"
    return PropagateDownwind(site, turbines, wake_deficitModel=deficit, superpositionModel=SquaredSum())


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def C(name, **params):
    return cfg.Component(name, params)


def with_(config, **changes):
    return cfg.WakeConfig(**{**config.__dict__, **changes})


def build(config, site=SITE):
    return fac.build_wind_farm_model(config, site, WT, ws_grid=WS)


def results(wfm, site_name, n):
    _site, x, y, grid, wd = SITES[site_name]
    sim = wfm(x[:n], y[:n], wd=WD, ws=WS)
    fm = sim.flow_map(grid, wd=wd, ws=10.0)
    return {"WS_eff": sim.WS_eff.values, "TI_eff": sim.TI_eff.values, "AEP": sim.aep().values,
            "map WS_eff": fm.WS_eff.values, "map TI_eff": fm.TI_eff.values}


class ContractTest(unittest.TestCase):
    def test_without_it_everything_is_written_and_read_as_before(self):
        base = cfg.default_config("PropagateDownwind", "TurboGaussianDeficit")
        self.assertIsNone(base.deficit_ws_reference)
        d = base.to_dict()
        self.assertEqual((d["version"], "deficit_ws_reference" in d), (2, False))
        self.assertEqual(api.to_wake_physics(base)["version"], 1)
        self.assertNotIn("deficit_ws_reference", api.to_wake_physics(base))
        # The earlier versions are read as without it; an explicit None in the new ones too.
        for version in (1, 2):
            self.assertIsNone(cfg.WakeConfig.from_dict(dict(d, version=version)).deficit_ws_reference)
        for data in (dict(d, version=3), dict(d, version=3, deficit_ws_reference=None)):
            self.assertEqual(cfg.WakeConfig.from_dict(data), base)
        for physics in ({"version": 2}, {"version": 2, "deficit_ws_reference": None}):
            self.assertIsNone(api.resolve_request(physics)[0].deficit_ws_reference)

    def test_with_it_a_round_trip_by_json_and_by_the_api(self):
        d = json.loads(json.dumps(TURBOPARK.to_dict()))
        self.assertEqual((d["version"], d["deficit_ws_reference"]), (3, REF))
        self.assertEqual(cfg.WakeConfig.from_dict(d), TURBOPARK)
        physics = json.loads(json.dumps(api.to_wake_physics(TURBOPARK)))
        self.assertEqual((physics["version"], physics["deficit_ws_reference"]), (2, REF))
        self.assertEqual(api.resolve_request(physics), (TURBOPARK, None))
        self.assertNotEqual(TURBOPARK, WITHOUT)

    def test_what_is_refused(self):
        d = TURBOPARK.to_dict()
        for data in (dict(d, deficit_ws_reference="WS_jlk"), dict(d, deficit_ws_reference=1),
                     dict(d, version=2)):  # the field is not of version 2
            with self.subTest(data={k: data[k] for k in ("version", "deficit_ws_reference")}), \
                    self.assertRaises(cfg.ConfigFormatError):
                cfg.WakeConfig.from_dict(data)
        physics = api.to_wake_physics(TURBOPARK)
        for request in (dict(physics, deficit_ws_reference="otra"), dict(physics, version=1)):
            with self.subTest(request={k: request[k] for k in ("version", "deficit_ws_reference")}), \
                    self.assertRaises(api.RequestError):
                api.resolve_request(request)

    def test_only_in_the_composition_of_turbopark(self):
        self.assertEqual(val.validate(TURBOPARK), [])
        deficit = TURBOPARK.deficit
        for name, config in (
                ("All2AllIterative", with_(TURBOPARK, engine=C("All2AllIterative", convergence_tolerance=1e-6))),
                ("LinearSum", with_(TURBOPARK, superposition=C("LinearSum"))),
                ("use_effective_ws", with_(TURBOPARK, deficit=C(deficit.name, **dict(deficit.params,
                                                                                     use_effective_ws=True)))),
                ("Bastankhah", with_(cfg.default_config(), deficit_ws_reference=REF)),
                ("another value", with_(TURBOPARK, deficit_ws_reference="WS_jlk"))):
            with self.subTest(change=name):
                self.assertEqual([i.code for i in val.validate(config)], ["R21"])
        # With anything else of the manual mode around it (another ground, a turbulence), it is offered; and with
        # use_effective_ws = 0, which PyWake takes as False.
        for config in (with_(TURBOPARK, ground=None), with_(TURBOPARK, turbulence=C("STF2017TurbulenceModel")),
                       with_(TURBOPARK, deficit=C(deficit.name, **dict(deficit.params, use_effective_ws=0)))):
            self.assertEqual(val.validate(config), [])


class ConstructionTest(unittest.TestCase):
    def test_the_key_is_set_before_the_engine_is_built(self):
        wfm = build(TURBOPARK)
        self.assertEqual(wfm.wake_deficitModel.WS_key, "WS_jlk")
        self.assertIn("WS_jlk", wfm.args4all)  # the engine read it when it was built
        fac.check_classes(fac.expected_classes(TURBOPARK), wfm)
        fac.check_ws_reference(TURBOPARK, wfm)
        self.assertEqual(build(WITHOUT).wake_deficitModel.WS_key, "WS_ilk")
        # A_0 has no deficit to scale: never with it.
        free = fac.build_free_stream_model(TURBOPARK, SITE, WT, ws_grid=WS)
        self.assertNotEqual(free.wake_deficitModel.WS_key, "WS_jlk")

    def test_an_adjustment_left_out_or_wrong_is_detected_with_the_same_classes(self):
        for config, wfm in ((TURBOPARK, build(WITHOUT)), (WITHOUT, build(TURBOPARK))):
            with self.subTest(reference=config.deficit_ws_reference):
                fac.check_classes(fac.expected_classes(config), wfm)  # the classes are the same
                with self.assertRaises(fac.ClassMismatch):
                    fac.check_ws_reference(config, wfm)
        wrong = build(TURBOPARK)
        wrong.wake_deficitModel.WS_key = "WS_eff_ilk"
        with self.assertRaises(fac.ClassMismatch):
            fac.check_ws_reference(TURBOPARK, wrong)

    def test_the_reading(self):
        executed = rd.executed_config(build(TURBOPARK), TURBOPARK)
        deficit = executed[cfg.DEFICIT]
        self.assertEqual(deficit["WS_key"], "WS_jlk")
        self.assertEqual(deficit["params"]["use_effective_ws"], {"value": False, "source": rd.PASSED})
        self.assertEqual(deficit["params"]["use_effective_ti"]["source"], rd.OBSERVED)
        self.assertEqual(rd.executed_ws_reference(executed), REF)
        self.assertEqual(rd.differences_vs_selection(executed, TURBOPARK), [])
        self.assertIn("referencia del escalado: velocidad libre de la turbina de destino (WS_key = WS_jlk)",
                      " ".join(rd.executed_lines(executed)))
        # Without the field, as before: no key recorded, and a deficit with WS_jlk cannot be read.
        manual = rd.executed_config(build(WITHOUT), WITHOUT)
        self.assertNotIn("WS_key", manual[cfg.DEFICIT])
        self.assertEqual(manual[cfg.DEFICIT]["params"]["use_effective_ws"]["source"], rd.OBSERVED)
        with self.assertRaises(fac.ReaderError):
            rd.executed_config(build(TURBOPARK), WITHOUT)
        # It enters the comparison of the selection with what was executed.
        self.assertEqual(rd.differences_vs_selection(manual, TURBOPARK)[-1],
                         {"position": cfg.DEFICIT, "param": "deficit_ws_reference", "selected": REF, "executed": None})


class FidelityTest(unittest.TestCase):
    """TurbOPark is Nygaard_2022 bit for bit, in a uniform and in a non-uniform site; without the adjustment, it is
    not where the free wind speed differs between turbines."""

    def test_with_nygaard_2022(self):
        turbines = simulation_wind_turbines(WT, WS, BIN_MEAN)
        for site_name, (site, *_rest) in SITES.items():
            for n in (1, 2, 4):
                with self.subTest(site=site_name, n=n):
                    theirs = results(lit.Nygaard_2022(site, turbines), site_name, n)
                    ours = results(build(TURBOPARK, site), site_name, n)
                    for k in theirs:
                        self.assertTrue(np.array_equal(ours[k], theirs[k]), k)
        # The control: in the non-uniform site, without the adjustment, the speeds, the AEP and the map differ.
        theirs = results(lit.Nygaard_2022(PF, turbines), "non_uniform", 4)
        control = results(build(WITHOUT, PF), "non_uniform", 4)
        for k in ("WS_eff", "AEP", "map WS_eff"):
            self.assertGreater(np.abs(control[k] - theirs[k]).max(), 1e-3, k)

    def test_adapted_with_nygaard_2022_with_the_same_adaptation(self):
        # The adaptation keeps the reference of the scaling, the ground and every argument of the deficit.
        self.assertEqual(ADAPTED.deficit_ws_reference, REF)
        self.assertEqual((ADAPTED.deficit, ADAPTED.ground, ADAPTED.superposition),
                         (TURBOPARK.deficit, TURBOPARK.ground, TURBOPARK.superposition))
        self.assertEqual(val.validate(ADAPTED), [])  # R21 admits it
        turbines = simulation_wind_turbines(WT, WS, BIN_MEAN)
        for site_name, (site, *_rest) in SITES.items():
            for n in (1, 2, 4):
                with self.subTest(site=site_name, n=n):
                    theirs = results(nygaard_cgi7(site, turbines), site_name, n)
                    ours = results(build(ADAPTED, site), site_name, n)
                    for k in theirs:
                        self.assertTrue(np.array_equal(ours[k], theirs[k]), k)
        self.assertEqual(build(ADAPTED, PF).wake_deficitModel.WS_key, "WS_jlk")
        theirs = results(nygaard_cgi7(PF, turbines), "non_uniform", 4)
        control = results(build(ADAPTED_WITHOUT, PF), "non_uniform", 4)
        for k in ("WS_eff", "AEP", "map WS_eff"):
            self.assertGreater(np.abs(control[k] - theirs[k]).max(), 1e-3, k)

    def test_the_raster_with_the_same_precision_points_and_tiles(self):
        # A resource that is not uniform through the plugin's routes: the GRD of ParqueFicticio, with its Speedup (a
        # WRG is read with Speedup «none»: the same free wind speed at every turbine, where the adjustment changes
        # nothing). Four turbines in a row, 400 m apart, with the wind from the west.
        import shutil
        from py_wake.examples.data.ParqueFicticio import ParqueFicticio_path
        folder = tempfile.mkdtemp(dir=_SETTINGS.name)
        grd = os.path.join(folder, "grd")
        shutil.copytree(ParqueFicticio_path, grd, ignore=shutil.ignore_patterns("*.pkl", "*.py", "__pycache__"))
        models = [model(layout=[(262878.0 + 100 * i, 6505714.0) for i in (4, 8, 12, 16)])]
        seen = {}
        real = engine._tiled_flow_map

        def spy(func, gx, gy, *a, **k):
            seen["grid"] = (np.asarray(gx, float), np.asarray(gy, float))
            seen["map"] = real(func, gx, gy, *a, **k)
            return seen["map"]
        maps = {}
        # Small tiles (in both routes): the map is calculated in several calls, as with a large grid.
        tiles = mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 400)
        tiles.start()
        self.addCleanup(tiles.stop)
        for name, config in (("turbopark", TURBOPARK), ("without", WITHOUT), ("adapted", ADAPTED)):
            with mock.patch.object(engine, "_tiled_flow_map", side_effect=spy):
                r = raster.compute_wake_raster_config(models, wake_config=config, wasp_dir=grd, wd_target=270.0,
                                                      resolution_m=100.0, output_dir=tempfile.mkdtemp(dir=folder))
            with open(r["metadata_path"], encoding="utf-8") as fh:
                maps[name] = (np.asarray(seen["map"]["WS_eff"].values, float), json.load(fh), seen["grid"], r["wd"])
        mine, meta, (gx, gy), wd = maps["turbopark"]
        self.assertEqual(meta["turbines_used"], 4)
        self.assertGreater(meta["flow_map_tiles"], 1)
        self.assertEqual(meta["wake_config"]["effective"]["deficit_ws_reference"], REF)
        self.assertEqual(meta["wake_config"]["executed"][cfg.DEFICIT]["WS_key"], "WS_jlk")
        self.assertNotIn("deficit_ws_reference", maps["without"][1]["wake_config"]["effective"])
        site, _k, _t = raster._energy_site(wasp_dir=grd, wrg_paths=None, models=models, wrg_speedup_method="none",
                                           wrg_direction_count=None, wrg_wd_interp="nearest", wrg_ti_paths=None,
                                           wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=None)
        x = np.array([p[0] for p in models[0]["coords_xy"]])
        y = np.array([p[1] for p in models[0]["coords_xy"]])
        f32 = meta["pywake_precision"] == "float32"
        dt = np.float32 if f32 else float
        from contextlib import nullcontext
        tol = (1e-5, 1e-6) if f32 else (1e-8, 1e-10)

        def reference(wfm):
            with (engine.Numpy32() if f32 else nullcontext()):
                sim = wfm(x.astype(dt), y.astype(dt), wd=np.array([wd], dt), ws=np.array([10.0], dt))
                return np.asarray(real(sim.flow_map, gx, gy, len(x), wd=wd, ws=10.0, memory_GB=0.08,
                                       n_cpu=1)["WS_eff"].values, float)
        theirs = reference(lit.Nygaard_2022(site, models[0]["wt"]))
        self.assertEqual(mine.shape, theirs.shape)
        self.assertTrue(np.all(np.abs(mine - theirs) <= tol[0] + tol[1] * np.abs(theirs)))
        # Adapted (CGIRotorAvg(7)): the same points and tiles, against the same adaptation by hand.
        adapted, adapted_meta, adapted_grid, _wd = maps["adapted"]
        self.assertEqual(adapted_meta["flow_map_tiles"], meta["flow_map_tiles"])
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(adapted_grid, (gx, gy))))
        self.assertEqual(adapted_meta["wake_config"]["executed"][cfg.DEFICIT]["WS_key"], "WS_jlk")
        theirs_adapted = reference(nygaard_cgi7(site, models[0]["wt"]))
        self.assertTrue(np.all(np.abs(adapted - theirs_adapted) <= tol[0] + tol[1] * np.abs(theirs_adapted)))
        self.assertGreater(np.abs(adapted - theirs).max(), 1e-6)  # not the preset
        # The control: without the adjustment, the map differs (the free wind speed differs between turbines).
        self.assertGreater(np.abs(maps["without"][0] - theirs).max(), 1e-3)


class ConsumersTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.wrg = write_wrg(folder.name, 12)

    def test_the_breakdown(self):
        run = lambda target: build(target).__call__(X, Y, wd=WD, ws=WS).aep().sum(["wd", "ws"]).values  # noqa: E731

        def free(target):
            wfm = fac.build_free_stream_model(TURBOPARK, SITE, WT, ws_grid=WS) if target is vr.FREE_STREAM else \
                build(target)
            return wfm(X, Y, wd=WD, ws=WS).aep().sum(["wd", "ws"]).values
        aep, states, _derived, errors = vr.run_breakdown(TURBOPARK, run(TURBOPARK), free, compute_variants=True,
                                                         turbulence_reaches_deficit=False)
        self.assertEqual(errors, {})
        self.assertIs(aep["A_W"], aep["A_WTB"])  # without turbulence: the main one
        self.assertEqual((states["A_WT"], states["A_WB"]), (bd.NOT_MODELLED, bd.NOT_MODELLED))
        # A variant that keeps the deficit keeps its reference.
        with_turbulence = with_(TURBOPARK, turbulence=C("STF2017TurbulenceModel"))
        a_w = vr.variant_configs(with_turbulence)["A_W"]
        self.assertEqual(a_w.deficit_ws_reference, REF)
        self.assertEqual(build(a_w).wake_deficitModel.WS_key, "WS_jlk")

    def test_the_aep_its_result_and_its_presentation(self):
        r = ac.compute_aep_from_ui("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08,
                                   wake_physics=api.to_wake_physics(TURBOPARK),
                                   wake_provenance=ps.provenance("TurbOPark"))
        wc = r["wake_config"]
        self.assertEqual(wc["effective"]["deficit_ws_reference"], REF)
        self.assertEqual(wc["executed"][cfg.DEFICIT]["WS_key"], "WS_jlk")
        self.assertEqual(wc["differences_vs_selection"], [])
        self.assertEqual(wc["provenance"]["preset"], "TurbOPark")
        self.assertEqual(r["breakdown"]["A_0"]["state"], bd.OK)
        html = model_config_html(json.loads(json.dumps(r, default=str)))
        self.assertIn("Referencia del escalado", html)
        self.assertIn("velocidad libre de la turbina de destino (WS_jlk)", html)
        # A manual result without it: no row of its own.
        manual = ac.compute_aep_from_ui("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08,
                                        wake_physics=api.to_wake_physics(WITHOUT))
        self.assertNotIn("Referencia del escalado", model_config_html(manual))
        self.assertNotIn("WS_key", manual["wake_config"]["executed"][cfg.DEFICIT])

    def test_the_dialog_remembers_it_and_replaces_its_rotor_only_with_continuar(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        for key in settings.allKeys():
            settings.remove(key)
        self.addCleanup(lambda: [settings.remove(k) for k in settings.allKeys()])
        d = AEPSetupDialog()
        self.addCleanup(d.deleteLater)
        g = d.wake_group
        g.combo_preset.setCurrentIndex(g.combo_preset.findData("TurbOPark"))
        self.assertIn("velocidad libre de la turbina de destino (WS_jlk)", g.lbl_preset_reference.text())
        d2 = AEPSetupDialog()
        self.addCleanup(d2.deleteLater)
        self.assertEqual(d2.wake_group.combo_preset.currentData(), "TurbOPark")

        def launch(choice, n):
            with mock.patch(f"{val.__name__}.missing_gaussian_overlap_modules", return_value=["h5py"]), \
                    mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda box: None), \
                    mock.patch.object(QtWidgets.QMessageBox, "clickedButton",
                                      lambda box: next(b for b in box.buttons() if b.text() == choice)), \
                    mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
                physics = d._wake_physics_for_run(n_turbines=n)
            warning.assert_not_called()
            return physics
        self.assertIsNone(launch("Cancelar", 2))
        self.assertEqual(api.resolve_request(launch("Continuar", 2))[0],  # its reference kept
                         api.gaussian_overlap_adaptation(TURBOPARK, ["h5py"], api.ACCEPTED_NOW))
        self.assertEqual(api.resolve_request(launch("Cancelar", 1))[0], TURBOPARK)  # one turbine: its own rotor
        self.assertEqual(d._wake_provenance_for_run()["preset"], "TurbOPark")

if __name__ == "__main__":
    unittest.main()
