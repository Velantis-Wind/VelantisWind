# -*- coding: utf-8 -*-
"""The wake raster of a WakeConfig: the factory of the AEP, its physical inputs and its JSON (#46 P4; #75 rows 5.1-5.9).

Rows: 5.1 and 5.2 ``SameFactoryTest``; 5.3 ``SameFactoryTest`` and ``RefusalsTest``; 5.4 ``SameFactoryTest.
test_the_json_reads_the_objects``; 5.5 ``InputsTest`` and ``GrdTest``; 5.6 ``InputsTest.test_the_shared_lock``; 5.7-5.9
``ExporterTest`` and ``WithoutFreeFlowTest``. Fidelity and partition: ``FidelityTest``.
"""
import json
import os
import sys
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

from VelantisWind.ag_core.physics.air_density import AirDensityError  # noqa: E402
from VelantisWind.ag_core.simulation.pywake_lock import PYWAKE_LOCK  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import factory as fac  # noqa: E402
from VelantisWind.ag_core.wake_setup import validation  # noqa: E402
from VelantisWind.wake_core import engine, raster  # noqa: E402
from tests.test_energy_project_crs import DERIVED_PROJECTED  # noqa: E402
from tests.test_resource_settings import model, wrg_text, write_wrg  # noqa: E402

warnings.filterwarnings("ignore", module="py_wake")
_CWD = os.getcwd()


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def C(name, **params):
    return cfg.Component(name, params)


def with_(config, **changes):
    return cfg.WakeConfig(**{**config.__dict__, **changes})


def read_tif(path):
    from osgeo import gdal
    ds = gdal.Open(path)
    return ds.GetRasterBand(1).ReadAsArray().astype(float)


class _Case(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.wrg = write_wrg(self.folder, 12)
        self.models = [model()]

    def run_raster(self, config, **kwargs):
        kwargs.setdefault("fixed_ti", 0.08)
        kwargs.setdefault("wd_target", 270.0)
        out = tempfile.mkdtemp(dir=self.folder)
        return raster.compute_wake_raster_config(self.models, wake_config=config, wrg_paths=[self.wrg],
                                                 resolution_m=250.0, output_dir=out, **kwargs)

    def json(self, result):
        with open(result["metadata_path"], encoding="utf-8") as fh:
            return json.load(fh)


FULL = with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"), turbulence=C("STF2017TurbulenceModel"),
             blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False), blockage_superposition=C("LinearSum"),
             rotor=C("CGIRotorAvg", n=7))


class SameFactoryTest(_Case):
    def test_the_engine_turbulence_blockage_and_rotor_of_the_configuration(self):
        captured = {}
        real = fac.build_wind_farm_model

        def spy(config, *a, **k):
            wfm = real(config, *a, **k)
            captured["wfm"] = wfm
            return wfm
        with mock.patch.object(fac, "build_wind_farm_model", side_effect=spy):
            result = self.run_raster(FULL)
        wfm = captured["wfm"]
        self.assertEqual(type(wfm).__name__, "All2AllIterative")
        self.assertEqual(type(wfm.turbulenceModel).__name__, "STF2017TurbulenceModel")
        self.assertEqual(type(wfm.blockage_deficitModel).__name__, "SelfSimilarityDeficit2020")
        self.assertEqual(len(wfm.wake_deficitModel.rotorAvgModel.nodes_x), 7)
        self.assertEqual(type(wfm.superpositionModel).__name__, "LinearSum")
        self.assertTrue(os.path.isfile(result["path"]))

    def test_the_json_reads_the_objects(self):
        meta = self.json(self.run_raster(FULL))
        executed = meta["wake_config"]["executed"]
        self.assertEqual(executed["engine"]["class"], "All2AllIterative")
        self.assertEqual(executed["turbulence"]["class"], "STF2017TurbulenceModel")
        self.assertEqual(executed["blockage"]["class"], "SelfSimilarityDeficit2020")
        self.assertEqual(executed["deficit"]["params"]["use_effective_ti"], {"value": True, "source": "observed"})
        self.assertEqual(meta["wake_config"]["expected_classes"]["rotor"], "CGIRotorAvg")
        self.assertEqual(meta["wake_config"]["selected"], FULL.to_dict())
        self.assertEqual(meta["product"], "configuración del diálogo al crear el ráster")
        self.assertIsNone(meta["aep_comparison"])  # not compared

    def test_the_json_records_the_comparison_with_the_last_aep(self):
        comparison = {"last_aep_available": True, "same_inputs_as_last_aep": False, "changed_inputs": ["densidad del aire"]}
        self.assertEqual(self.json(self.run_raster(cfg.default_config(), aep_comparison=comparison))["aep_comparison"],
                         comparison)

    def test_the_json_keeps_nan_and_infinities_of_the_configuration(self):
        # Decision 5 of #64: through the API they reach PyWake as given; the JSON of the raster writes them (Python's
        # NaN and Infinity). ctlim of ZongGaussianDeficit is never used by PyWake and c[0] = −inf gives no added
        # turbulence: the field is finite.
        base = cfg.default_config("PropagateDownwind", "ZongGaussianDeficit")
        config = with_(base, deficit=C("ZongGaussianDeficit", **dict(base.deficit.params, ctlim=float("nan"))),
                       turbulence=C("STF2017TurbulenceModel", c=[float("-inf"), 0.8]))
        meta = self.json(self.run_raster(config))
        self.assertEqual(cfg.WakeConfig.from_dict(meta["wake_config"]["selected"]),
                         cfg.WakeConfig.from_dict(config.to_dict()))
        self.assertTrue(np.isnan(meta["wake_config"]["executed"]["deficit"]["params"]["ctlim"]["value"]))
        self.assertEqual(meta["wake_config"]["executed"]["turbulence"]["params"]["c"]["value"][0], float("-inf"))

    def test_without_blockage_is_another_product_labelled(self):
        meta = self.json(self.run_raster(FULL, without_blockage=True))
        self.assertTrue(meta["without_blockage"])
        self.assertEqual(meta["product"], raster.WITHOUT_BLOCKAGE_LABEL)
        self.assertIsNone(meta["wake_config"]["executed"]["blockage"])
        self.assertEqual(meta["wake_config"]["executed"]["engine"]["class"], "All2AllIterative")  # the same engine

    def test_without_blockage_the_layer_name_says_it(self):
        from qgis.core import QgsProject
        from VelantisWind.ag_core.qgis_io import wake_raster
        for flag in (True, False):
            layers = wake_raster.add_wake_raster_result_to_qgis(self.run_raster(FULL, without_blockage=flag))
            self.addCleanup(lambda ls=layers: [QgsProject.instance().removeMapLayer(l.id()) for l in ls])
            names = [l.name() for l in layers if l.customProperty("velantiswind/variable") != "Elevation"]
            self.assertTrue(names)
            self.assertEqual({"sin bloqueo" in n for n in names}, {flag})
        # In the language of the interface.
        from VelantisWind import i18n
        with mock.patch.object(i18n, "current_language", return_value="en"):
            layers = wake_raster.add_wake_raster_result_to_qgis(self.run_raster(FULL, without_blockage=True))
        self.addCleanup(lambda ls=layers: [QgsProject.instance().removeMapLayer(l.id()) for l in ls])
        names = [l.name() for l in layers if l.customProperty("velantiswind/variable") != "Elevation"]
        self.assertTrue(names and all("without blockage (not the field of the AEP)" in n for n in names))
        self.assertFalse(any("sin bloqueo" in n for n in names))

    def test_a_substitution_is_detected_before_simulating(self):
        from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit
        real = fac.build_wind_farm_model

        def swapped(config, *a, **k):
            wfm = real(config, *a, **k)
            wfm.__dict__["wake_deficitModel"] = BastankhahGaussianDeficit()
            return wfm
        with mock.patch.object(fac, "build_wind_farm_model", side_effect=swapped), \
                mock.patch.object(engine, "_tiled_flow_map") as flow:
            with self.assertRaises(fac.ClassMismatch):
                self.run_raster(FULL)
            flow.assert_not_called()


class RefusalsTest(_Case):
    def test_what_the_aep_refuses_is_refused_with_its_reason(self):
        with self.assertRaises(raster.RasterError) as ctx:
            self.run_raster(cfg.default_config(deficit="ZongGaussianDeficit"))
        self.assertIn("TI efectiva", str(ctx.exception))

    def test_what_only_the_map_refuses_is_refused_before_calculating(self):
        # R9e: the AEP calculates it; the flow map of PyWake fails, so the raster refuses it before anything.
        config = with_(cfg.default_config(), superposition=C("CumulativeWakeSum"), ground=C("Mirror"))
        self.assertEqual(validation.validate(config), [])
        from py_wake import HorizontalGrid
        from py_wake.examples.data.hornsrev1 import Hornsrev1Site, V80
        sim = fac.build_wind_farm_model(config, Hornsrev1Site(), V80())([0.0, 500.0], [0.0, 0.0], wd=[270.0], ws=[10.0])
        with self.assertRaisesRegex(NotImplementedError, "cannot be used in combination with GroundModels"):
            sim.flow_map(HorizontalGrid(x=np.linspace(-200, 900, 4), y=np.linspace(-150, 150, 3)), wd=270.0, ws=10.0)
        with mock.patch.object(raster, "_energy_site", side_effect=AssertionError("loaded")) as loaded, \
                self.assertRaisesRegex(raster.RasterError, "mapa de flujo con CumulativeWakeSum"):
            self.run_raster(config)
        loaded.assert_not_called()
        self.assertEqual([i.code for i in validation.map_issues(with_(config, ground=C("MultiMirror")))], ["R9e"])
        self.assertEqual(validation.map_issues(with_(config, ground=None)), [])

    def test_the_simulation_stops_before_the_map(self):
        # Decision 6.1 of #64: with CumulativeWakeSum(alpha = None) and a ground, three turbines stop the simulation
        # (alpha) before the map (R9e): the reason is the earlier stage, checked with the turbines of the raster.
        config = with_(cfg.default_config(), superposition=C("CumulativeWakeSum", alpha=None),
                       ground=C("Mirror", superpositionModel=C("LinearSum")))
        self.models = [model(layout=[(1200.0, 1300.0), (1450.0, 1375.0), (1700.0, 1450.0)])]
        with mock.patch.object(fac, "build_wind_farm_model", side_effect=AssertionError("built")), \
                self.assertRaisesRegex(raster.RasterError, "se detiene desde la tercera turbina") as caught:
            self.run_raster(config)
        self.assertNotIn("CumulativeWakeSum y un modelo de suelo", str(caught.exception))

    def test_r9f_is_refused_with_the_turbines_of_the_raster(self):
        # Decision 23(b): with two turbines or more, before any simulation.
        base = cfg.default_config("PropagateUpDownIterative")
        config = with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, use_effective_ws=True)),
                       superposition=C("WeightedSum"), blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True),
                       blockage_superposition=C("MaxSum"))
        with mock.patch.object(fac, "build_wind_farm_model", side_effect=AssertionError("built")) as built, \
                self.assertRaisesRegex(raster.RasterError, "se detiene desde la segunda"):
            self.run_raster(config)
        built.assert_not_called()

    def test_a_refusal_is_shown_translated_whole(self):
        # Through the task and the text the controller shows: the message and its reasons, in the language.
        from VelantisWind import i18n
        from VelantisWind.wake_core import controller
        from VelantisWind.wake_core.task import WakeRasterTask
        config = with_(cfg.default_config(), superposition=C("CumulativeWakeSum"), ground=C("Mirror"))
        with self.assertRaises(raster.RasterError) as ctx:
            self.run_raster(config)
        task = WakeRasterTask(config=mock.Mock(to_engine_kwargs=lambda: {}))
        with mock.patch.object(raster, "compute_wake_raster_config", side_effect=ctx.exception):
            self.assertFalse(task.run())
        with mock.patch.object(i18n, "current_language", return_value="en"):
            text = controller.error_text(task.result, task.error)
        self.assertIn("PyWake does not calculate the flow map with CumulativeWakeSum and a ground model", text)
        self.assertIn("For the raster, choose Ground", text)
        self.assertNotIn("ráster", text)
        self.assertNotIn("PyWake no calcula", text)

    def test_a_warning_of_the_exporter_reaches_the_controller_as_a_template(self):
        from VelantisWind.ag_core.log_text import log_text
        real = engine._create_single_wake_raster_file
        warning = log_text("PyWake no expuso el campo WS libre ({error}): no se han escrito el viento libre ni los "
                           "déficits.", error="x")

        def with_warning(*a, **k):
            result = real(*a, **k)
            result["warnings"] = list(result.get("warnings") or []) + [warning]
            return result
        with mock.patch.object(engine, "_create_single_wake_raster_file", side_effect=with_warning):
            r = self.run_raster(cfg.default_config())
        self.assertIn(warning.template_item, r["warning_items"])

    def test_the_cell_limit_can_be_set(self):
        seen = {}
        real = engine._build_domain_anchored_grid

        def spy(*a, **k):
            seen["max_cells"] = k["max_cells"]
            return real(*a, **k)
        with mock.patch.object(engine, "_build_domain_anchored_grid", side_effect=spy):
            for value, expected in (("30000", 30_000), ("10", 25_000), ("9000000", 2_000_000)):
                with self.subTest(value=value), mock.patch.dict(os.environ, {"VELANTISWIND_WAKE_MAX_CELLS": value}):
                    self.run_raster(cfg.default_config())
                    self.assertEqual(seen["max_cells"], expected)
            with mock.patch.dict(os.environ, {"VELANTISWIND_WAKE_MAX_CELLS": "x"}):
                r = self.run_raster(cfg.default_config())
            self.assertIn("VELANTISWIND_WAKE_MAX_CELLS no es válido", " ".join(r["warnings"]))

    def test_a_density_that_cannot_be_established_stops_the_raster(self):
        with mock.patch.object(engine, "resolve_air_density", side_effect=AirDensityError("sin densidad")):
            with self.assertRaises(AirDensityError):
                self.run_raster(cfg.default_config())

    def test_the_cancellation_is_kept(self):
        calls = {"n": 0}

        def cancel():
            calls["n"] += 1
            return calls["n"] > 3
        with self.assertRaises(RuntimeError) as ctx:
            self.run_raster(cfg.default_config(), cancel_callback=cancel)
        self.assertIn("cancelada", str(ctx.exception))

    def test_cancelled_once_written_nothing_is_left(self):
        written = {}
        real = engine._create_single_wake_raster_file

        def write(*a, **k):
            written["result"] = real(*a, **k)
            written["aux"] = [os.path.isfile(e["path"] + ".aux.xml") for e in written["result"]["rasters"]]
            return written["result"]
        out = tempfile.mkdtemp(dir=self.folder)
        with mock.patch.object(engine, "_create_single_wake_raster_file", side_effect=write):
            with self.assertRaises(RuntimeError):
                # In a CRS without WKT1 each raster has its CRS in an .aux.xml (#54).
                raster.compute_wake_raster_config(self.models, wake_config=cfg.default_config(), wrg_paths=[self.wrg],
                                                  fixed_ti=0.08, wd_target=270.0, resolution_m=250.0,
                                                  output_dir=out, crs_wkt=DERIVED_PROJECTED,
                                                  cancel_callback=lambda: "result" in written)
        self.assertTrue(written["result"]["rasters"])  # it was written, then removed
        self.assertTrue(all(written["aux"]))
        self.assertEqual([f for f in os.listdir(out) if f.endswith((".tif", ".json", ".aux.xml"))], [])


class InputsTest(_Case):
    def test_the_ti_of_the_aep(self):
        # A TI-sensitive deficit: with the fixed TI of the AEP the map changes (row 5.5); the JSON records it.
        config = with_(cfg.default_config(deficit="NiayifarGaussianDeficit"), turbulence=C("STF2017TurbulenceModel"))
        low, high = self.run_raster(config, fixed_ti=0.06), self.run_raster(config, fixed_ti=0.14)
        self.assertNotEqual(low["mean_ws"], high["mean_ws"])
        meta = self.json(low)
        self.assertEqual(meta["ti"]["source"], "fixed")
        self.assertEqual(meta["ti"]["value"], 0.06)
        np.testing.assert_allclose(meta["ti"]["values_at_turbines"], 0.06, rtol=1e-6)

    def test_the_free_flow_of_the_two_routes(self):
        # The raster's site is the AEP's: the same free wind at the same (x, y, h, wd, ws).
        from VelantisWind.ag_core import aep_compute as ac
        site_r, _kind, _ti = raster._energy_site(
            wasp_dir="", wrg_paths=[self.wrg], models=self.models, wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="nearest", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=0.08)
        site_a, ds, _u, fixed, _d = ac._orchestration.load_energy_site(
            use_wrg=True, wasp_dir="", wrg_paths=[self.wrg], wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="nearest", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=0.08,
            log=lambda *a: None, warning_level=None, info_level=None,
            resolve_wasp_dir_for_pywake=ac._resolve_wasp_dir_for_pywake, sanitize_dir_for_pywake=ac._sanitize_dir_for_pywake,
            load_site_with_filter=ac._load_site_with_filter, ensure_wd_dim=ac._ensure_wd_dim,
            rebuild_xrsite_if_needed=ac._rebuild_xrsite_if_needed, apply_ti_raster_to_site=ac._apply_ti_raster_to_site)
        ac._apply_fixed_ti(site_a, 0.08, prefer_var="TI")
        x, y, h = np.array([1200.0, 1900.0, 2600.0]), np.array([1300.0, 2100.0, 2700.0]), np.array([90.0] * 3)
        for wd, ws in ((270.0, 8.0), (45.0, 12.0)):
            a = site_a.local_wind(x, y, h, wd=[wd], ws=[ws])
            r = site_r.local_wind(x, y, h, wd=[wd], ws=[ws])
            np.testing.assert_allclose(r.WS_ilk, a.WS_ilk, rtol=1e-10, atol=1e-8)
            np.testing.assert_allclose(r.TI_ilk, a.TI_ilk, rtol=1e-10, atol=1e-12)

    def test_the_shared_lock(self):
        # Every PyWake step holds it: the site, the wind farm model, the simulation and its map, the terrain.
        owned = {}

        def spy(target, name):
            real = getattr(target, name)

            def wrapped(*a, **k):
                owned.setdefault(name, []).append(PYWAKE_LOCK._is_owned())
                return real(*a, **k)
            return mock.patch.object(target, name, side_effect=wrapped)
        with spy(raster, "_energy_site"), spy(fac, "build_wind_farm_model"), spy(engine, "_tiled_flow_map"), \
                spy(engine, "_terrain_on_grid"), spy(engine, "_create_single_wake_raster_file"):
            self.run_raster(with_(cfg.default_config("All2AllIterative"), blockage=C("SelfSimilarityDeficit2020",
                                  use_effective_ws=False), blockage_superposition=C("LinearSum")))
        self.assertEqual(owned, {n: [True] for n in ("_energy_site", "build_wind_farm_model", "_tiled_flow_map",
                                                     "_terrain_on_grid", "_create_single_wake_raster_file")})
        self.assertFalse(PYWAKE_LOCK._is_owned())

    def test_the_map_is_traced_only_with_weighted_sum(self):
        # The trace function slows every Python call down: the map, where only WeightedSum iterates, only with it.
        from VelantisWind.ag_core.wake_setup.instrumentation import ConvergenceRecorder
        traced = []
        real = engine._tiled_flow_map

        def spy(*a, **k):
            traced.append(isinstance(getattr(sys.gettrace(), "__self__", None), ConvergenceRecorder))
            return real(*a, **k)
        with mock.patch.object(engine, "_tiled_flow_map", side_effect=spy):
            self.run_raster(cfg.default_config())
            result = self.run_raster(with_(cfg.default_config(), superposition=C("WeightedSum")))
        self.assertEqual(traced, [False, True])
        self.assertIn("WeightedSum", self.json(result)["convergence"])
        self.assertIs(raster.ConvergenceRecorder, ConvergenceRecorder)

    def test_the_hub_heights_are_checked_as_in_the_aep(self):
        from VelantisWind.ag_core import aep_compute as ac
        with mock.patch.object(ac, "_clip_hub_heights_to_site", side_effect=RuntimeError("HH fuera del WRG")), \
                mock.patch.object(engine, "_tiled_flow_map") as flow:
            with self.assertRaises(RuntimeError) as ctx:
                self.run_raster(cfg.default_config())
        self.assertIn("HH fuera del WRG", str(ctx.exception))
        flow.assert_not_called()

    def test_persistent_and_weighted_sum_warnings(self):
        pud = with_(cfg.default_config("PropagateUpDownIterative"),
                    deficit=C("BastankhahGaussianDeficit", **dict(cfg.default_config().deficit.params, use_effective_ws=True)),
                    blockage=C("VortexDipole", use_effective_ws=True), blockage_superposition=C("LinearSum"))
        self.assertTrue(any("velocidad libre aunque" in w for w in self.run_raster(pud)["warnings"]))
        ws = with_(cfg.default_config(), superposition=C("WeightedSum"))
        with mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 20):
            result = self.run_raster(ws)
        self.assertTrue(any("máximo global" in w for w in result["warnings"]))
        self.assertTrue(any("máximo global" in w for w in self.json(result)["warnings"]))
        # Without iterating it weighs nothing and the tiles do not change the map (discrete round 3, B1).
        for max_iter in (0, False):
            with mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 20):
                result = self.run_raster(with_(cfg.default_config(), superposition=C("WeightedSum", max_iter=max_iter)))
            with self.subTest(max_iter=max_iter):
                self.assertFalse([w for w in result["warnings"] if "máximo global" in w])


    def test_the_cumulative_warnings_reach_the_raster_and_its_json(self):
        # Decision 23(a): the same warning as the AEP, and what the field does with a rotor.
        from VelantisWind.ag_core.wake_setup.notices import CUMULATIVE_FIELD_NOTE
        config = with_(cfg.default_config(), superposition=C("CumulativeWakeSum"), rotor=C("CGIRotorAvg", n=7))
        result = self.run_raster(config)
        for warnings_ in (result["warnings"], self.json(result)["warnings"]):
            self.assertTrue(any("no afectan al resultado numérico por esta ruta: ct2a, use_effective_ws." in w
                                for w in warnings_), warnings_)
            self.assertIn(CUMULATIVE_FIELD_NOTE, warnings_)


    def test_the_downstream_blockage_warning_reaches_the_raster(self):
        # Decision 23(c), with what the field does calculate.
        from VelantisWind.ag_core.wake_setup.notices import PUD_DOWNSTREAM_FIELD_NOTE
        base = cfg.default_config("PropagateUpDownIterative")
        config = with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, use_effective_ws=True)),
                       superposition=C("CumulativeWakeSum"), blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True),
                       blockage_superposition=C("LinearSum"))
        result = self.run_raster(config)
        for warnings_ in (result["warnings"], self.json(result)["warnings"]):
            self.assertTrue(any("omite el bloqueo aguas abajo" in w for w in warnings_), warnings_)
            self.assertIn(PUD_DOWNSTREAM_FIELD_NOTE, warnings_)


class FidelityTest(_Case):
    """The plugin's raster against PyWake directly with the same partition, in float64 (the criteria of the plan)."""

    def setUp(self):
        super().setUp()
        tiles = mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 40)  # several tiles: the partition matters
        tiles.start()
        self.addCleanup(tiles.stop)

    def plugin_map(self, config):
        seen = {"result": None}
        real = engine._tiled_flow_map

        def spy(func, grid_x, grid_y, *a, **k):
            seen["grid"] = (np.asarray(grid_x, float), np.asarray(grid_y, float))
            seen["map"] = real(func, grid_x, grid_y, *a, **k)
            return seen["map"]
        with mock.patch.object(engine, "_tiled_flow_map", side_effect=spy):
            seen["result"] = self.run_raster(config, ws_plot=10.0)
        return seen

    @staticmethod
    def full_wfm(site, wt):
        from py_wake.deficit_models.gaussian import NiayifarGaussianDeficit
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020
        from py_wake.rotor_avg_models import CGIRotorAvg
        from py_wake.superposition_models import LinearSum
        from py_wake.turbulence_models import STF2017TurbulenceModel
        from py_wake.wind_farm_models import All2AllIterative
        return All2AllIterative(site, wt, NiayifarGaussianDeficit(rotorAvgModel=CGIRotorAvg(7)),
                                superpositionModel=LinearSum(), turbulenceModel=STF2017TurbulenceModel(),
                                blockage_deficitModel=SelfSimilarityDeficit2020(superpositionModel=LinearSum()))

    def direct_sim(self, build=None):
        # The same physics written by hand with PyWake, on the site of the AEP.
        site, _k, _t = raster._energy_site(
            wasp_dir="", wrg_paths=[self.wrg], models=self.models, wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="nearest", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=0.08)
        wfm = (build or self.full_wfm)(site, self.models[0]["wt"])
        x = [p[0] for p in self.models[0]["coords_xy"]]
        y = [p[1] for p in self.models[0]["coords_xy"]]
        return wfm(x, y, wd=[270.0], ws=[10.0]), len(x)

    def test_the_same_partition_and_the_full_map(self):
        from py_wake import HorizontalGrid
        seen = self.plugin_map(FULL)
        gx, gy = seen["grid"]
        sim, n = self.direct_sim()
        direct = engine._tiled_flow_map(sim.flow_map, gx, gy, n, wd=270.0, ws=10.0)
        # The reference without PyWake's internal partition, and the most partitioned one (one point per chunk):
        # the chunks PyWake took are counted.
        from py_wake.wind_farm_models.engineering_models import EngineeringWindFarmModel as EWFM
        chunks = []
        for memory in (100.0, 1e-12):
            with mock.patch.object(EWFM, "_get_flow_l", autospec=True, side_effect=EWFM._get_flow_l) as spy:
                chunks.append((sim.flow_map(HorizontalGrid(x=gx, y=gy), wd=270.0, ws=10.0, memory_GB=memory),
                               spy.call_count))
        (full, one), (chunked, many) = chunks
        self.assertEqual(one, 1)
        self.assertEqual(many, gx.size * gy.size)

        def close(a, b):
            a, b = np.asarray(a, float).squeeze(), np.asarray(b, float).squeeze()
            self.assertEqual(a.shape, b.shape)
            self.assertTrue(np.all(np.abs(a - b) <= 1e-8 + 1e-10 * np.abs(b)), np.max(np.abs(a - b)))
        for var in ("WS_eff", "WS"):
            close(seen["map"][var].values, direct[var].values)  # the plugin and PyWake, the same partition
            close(direct[var].values, full[var].transpose(*direct[var].dims).values)  # the tiles and one call
            close(chunked[var].values, full[var].values)  # PyWake's own partition
        self.assertGreater(float(np.max(np.abs(direct["WS"].values - direct["WS_eff"].values))), 0.1)  # with wakes


    def test_weighted_sum_the_same_partition_and_its_sensitivity(self):
        from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit
        from py_wake import HorizontalGrid
        from py_wake.superposition_models import WeightedSum
        from py_wake.wind_farm_models import PropagateDownwind
        seen = self.plugin_map(with_(cfg.default_config(), superposition=C("WeightedSum")))
        gx, gy = seen["grid"]
        sim, n = self.direct_sim(lambda site, wt: PropagateDownwind(site, wt, BastankhahGaussianDeficit(),
                                                                     superpositionModel=WeightedSum()))
        direct = engine._tiled_flow_map(sim.flow_map, gx, gy, n, wd=270.0, ws=10.0, memory_GB=0.08, n_cpu=1)
        for var in ("WS_eff", "WS"):  # the fidelity: the plugin and PyWake with the same partition
            a, b = np.asarray(seen["map"][var].values, float), np.asarray(direct[var].values, float)
            self.assertTrue(np.all(np.abs(a - b) <= 1e-8 + 1e-10 * np.abs(b)), np.max(np.abs(a - b)))
        # The diagnostic (a measure, not a criterion): one call against the tiles; above the threshold, the warning.
        full = sim.flow_map(HorizontalGrid(x=gx, y=gy), wd=270.0, ws=10.0, memory_GB=100.0)
        d = np.abs(np.asarray(direct["WS_eff"].values, float).squeeze() - np.asarray(full["WS_eff"].values, float).squeeze())
        above = bool(np.any(d > 1e-3 + 1e-3 * np.abs(np.asarray(direct["WS"].values, float).squeeze())))
        warned = any("máximo global" in w for w in seen["result"]["warnings"])
        self.assertTrue(warned or not above)
        self.assertGreater(seen["result"]["flow_map_tiles"] if "flow_map_tiles" in seen["result"]
                           else self.json(seen["result"])["flow_map_tiles"], 1)

    def test_propagate_up_down_in_float64_against_pywake(self):
        # With and without blockage (PyWake 2.6.18 cannot run it inside Numpy32; the raster is always in float64).
        from py_wake.deficit_models import VortexDipole
        from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import PropagateUpDownIterative
        deficit = C("BastankhahGaussianDeficit", **dict(cfg.default_config().deficit.params, use_effective_ws=True))
        for blockage in (False, True):
            config = with_(cfg.default_config("PropagateUpDownIterative"), deficit=deficit)
            if blockage:
                config = with_(config, blockage=C("VortexDipole", use_effective_ws=True),
                               blockage_superposition=C("LinearSum"))

            def build(site, wt, blockage=blockage):
                return PropagateUpDownIterative(
                    site, wt, BastankhahGaussianDeficit(use_effective_ws=True), superpositionModel=LinearSum(),
                    blockage_deficitModel=VortexDipole(use_effective_ws=True, superpositionModel=LinearSum())
                    if blockage else None)
            with self.subTest(blockage=blockage):
                seen = self.plugin_map(config)
                meta = self.json(seen["result"])
                self.assertEqual(meta["pywake_precision"], "float64")
                gx, gy = seen["grid"]
                sim, n = self.direct_sim(build)
                direct = engine._tiled_flow_map(sim.flow_map, gx, gy, n, wd=270.0, ws=10.0)
                for var in ("WS_eff", "WS"):
                    a, b = np.asarray(seen["map"][var].values, float), np.asarray(direct[var].values, float)
                    self.assertTrue(np.all(np.abs(a - b) <= 1e-8 + 1e-10 * np.abs(b)), np.max(np.abs(a - b)))

    def test_the_free_flow_in_the_precision_of_production(self):
        # Float64, as the raster always calculates: the free wind within the float64 tolerance of the plan.
        seen = self.plugin_map(FULL)
        self.assertEqual(seen["map"]["WS"].dtype, np.float64)
        gx, gy = seen["grid"]
        sim, n = self.direct_sim()
        direct = engine._tiled_flow_map(sim.flow_map, gx, gy, n, wd=270.0, ws=10.0)
        ours, ref = np.asarray(seen["map"]["WS"].values, float), np.asarray(direct["WS"].values, float)
        self.assertTrue(np.all(np.abs(ours - ref) <= 1e-8 + 1e-10 * np.abs(ref)))


class ProjectedCoordinatesTest(_Case):
    """The turbines stand where they stand in the AEP: projected coordinates are not rounded (as #45 in the AEP)."""

    X0, Y0 = 500000.0, 5500000.0  # in float32, northings above 4 194 304 m go in steps of 0.5 m

    def test_the_coordinates_reach_pywake_unrounded(self):
        lines = wrg_text(12).splitlines()
        nx, ny, x, y, cell = lines[0].split()
        lines[0] = " ".join([nx, ny, f"{float(x) + self.X0:g}", f"{float(y) + self.Y0:g}", cell])
        for i in range(1, len(lines)):
            f = lines[i].split()
            f[0], f[1] = f"{float(f[0]) + self.X0:g}", f"{float(f[1]) + self.Y0:g}"
            lines[i] = " ".join(f)
        with open(self.wrg, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        layout = [(self.X0 + 1200.13, self.Y0 + 1300.13), (self.X0 + 1700.17, self.Y0 + 1449.89)]
        self.models = [model(layout=layout)]
        self.assertNotEqual(float(np.float32(layout[1][1])), layout[1][1])  # float32 would move this turbine
        from py_wake.wind_farm_models import PropagateDownwind
        seen = {}
        real = PropagateDownwind.__call__

        def call(wfm, *a, **k):
            seen.update(k)
            return real(wfm, *a, **k)
        with mock.patch.object(PropagateDownwind, "__call__", call):
            result = self.run_raster(cfg.default_config())
        self.assertEqual(seen["x"].dtype, np.float64)
        self.assertEqual(sorted(zip(seen["x"].tolist(), seen["y"].tolist())), sorted(layout))
        self.assertEqual(self.json(result)["pywake_precision"], "float64")


class WithoutFreeFlowTest(_Case):
    def test_the_whole_route_writes_the_effective_speed_alone(self):
        import xarray as xr
        real = engine._tiled_flow_map

        def without_ws(func, gx, gy, n, **k):
            return real(lambda **kw: xr.Dataset({"WS_eff": func(**kw)["WS_eff"]}), gx, gy, n, **k)
        with mock.patch.object(engine, "_tiled_flow_map", side_effect=without_ws):
            result = self.run_raster(cfg.default_config())
        self.assertEqual([e["variable"] for e in result["rasters"] if e["variable"] != "Elevation"], ["WS_eff"])
        self.assertTrue(any("no se han escrito el viento libre" in w for w in result["warnings"]))
        self.assertTrue(any("no se han escrito el viento libre" in w for w in self.json(result)["warnings"]))


class GrdTest(_Case):
    """A GRD is loaded with the AEP's loader; its TI keeps the previous raster's treatment (#49), declared."""

    def setUp(self):
        super().setUp()
        import shutil
        from py_wake.examples.data.ParqueFicticio import ParqueFicticio_path
        from py_wake.site import WaspGridSite
        self.grd = os.path.join(self.folder, "grd")
        shutil.copytree(ParqueFicticio_path, self.grd, ignore=shutil.ignore_patterns("*.pkl", "*.py", "__pycache__"))
        ds = WaspGridSite.from_wasp_grd(self.grd, speedup_using_pickle=False).ds
        self.xy = [(float(ds.x.values[i]), float(ds.y.values[j])) for i, j in ((15, 8), (10, 10))]
        self.models = [model(layout=self.xy)]

    def test_the_free_flow_of_the_aep_and_the_declared_ti(self):
        from VelantisWind.ag_core import aep_compute as ac
        site_r, kind, record = raster._energy_site(
            wasp_dir=self.grd, wrg_paths=None, models=self.models, wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="nearest", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=None)
        self.assertEqual(record["source"], "grd_ti15ms_replaced_by_0.10")
        self.assertIn("TI fija de 0,10", record["note"])  # the TI the raster uses, said in its record
        site_a, _ds, _u, _f, _d = ac._orchestration.load_energy_site(
            use_wrg=False, wasp_dir=self.grd, wrg_paths=[], wrg_speedup_method="none", wrg_direction_count=None,
            wrg_wd_interp="nearest", wrg_ti_paths=None, wrg_ti_heights_m=None, project_crs_authid=None, fixed_ti=None,
            log=lambda *a: None, warning_level=None, info_level=None,
            resolve_wasp_dir_for_pywake=ac._resolve_wasp_dir_for_pywake, sanitize_dir_for_pywake=ac._sanitize_dir_for_pywake,
            load_site_with_filter=ac._load_site_with_filter, ensure_wd_dim=ac._ensure_wd_dim,
            rebuild_xrsite_if_needed=ac._rebuild_xrsite_if_needed, apply_ti_raster_to_site=ac._apply_ti_raster_to_site)
        x, y = np.array([p[0] for p in self.xy]), np.array([p[1] for p in self.xy])
        for wd, ws in ((270.0, 8.0), (45.0, 12.0)):
            a = site_a.local_wind(x, y, np.array([90.0, 90.0]), wd=[wd], ws=[ws])
            r = site_r.local_wind(x, y, np.array([90.0, 90.0]), wd=[wd], ws=[ws])
            np.testing.assert_allclose(r.WS_ilk, a.WS_ilk, rtol=1e-10, atol=1e-8)

    def test_the_raster_of_a_grd(self):
        out = tempfile.mkdtemp(dir=self.folder)
        result = raster.compute_wake_raster_config(self.models, wake_config=cfg.default_config(), wasp_dir=self.grd,
                                                   wd_target=270.0, resolution_m=300.0, output_dir=out)
        meta = self.json(result)
        self.assertEqual(meta["ti"]["source"], "grd_ti15ms_replaced_by_0.10")
        self.assertEqual(meta["resource_kind"], "WASP")


class ExporterTest(unittest.TestCase):
    def test_without_the_free_flow_nothing_is_invented(self):
        import xarray as xr
        from VelantisWind.ag_core.qgis_io import wake_raster
        x, y = np.linspace(0, 400, 5), np.linspace(0, 300, 4)
        fm = xr.Dataset({"WS_eff": (("y", "x"), np.full((4, 5), 7.0))}, coords={"x": x, "y": y})
        out = tempfile.mkdtemp(dir=_SETTINGS.name)
        result = wake_raster.build_wake_raster_file(fm, wd=270.0, ws=10.0, output_dir=out, crs_wkt="",
                                                    metadata={"warnings": ["del motor"]})
        self.assertEqual([e["variable"] for e in result["rasters"]], ["WS_eff"])
        self.assertIsNone(result["free_flow_mean_ws"])
        self.assertEqual(result["warnings"][0], "del motor")
        self.assertIn("no se han escrito el viento libre", result["warnings"][1])
        # A template, translated when shown (with the error of PyWake as its data).
        from VelantisWind import i18n
        from VelantisWind.ag_core.log_text import shown
        with mock.patch.object(i18n, "current_language", return_value="en"):
            self.assertIn("neither the free wind nor the deficits", str(shown(result["warnings"][1], i18n.tr_text)))
        with open(result["metadata_path"], encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["warnings"], result["warnings"])

    def test_each_layer_keeps_its_variable(self):
        from qgis.core import QgsProject
        from VelantisWind.ag_core.qgis_io import wake_raster
        import xarray as xr
        x, y = np.linspace(0, 400, 5), np.linspace(0, 300, 4)
        fm = xr.Dataset({"WS_eff": (("y", "x"), np.full((4, 5), 7.0)), "WS": (("y", "x"), np.full((4, 5), 9.0))},
                        coords={"x": x, "y": y})
        out = tempfile.mkdtemp(dir=_SETTINGS.name)
        result = wake_raster.build_wake_raster_file(fm, wd=270.0, ws=10.0, output_dir=out, crs_wkt="",
                                                    metadata={"variable": "WS_eff", "units": "m/s"})
        layers = wake_raster.add_wake_raster_result_to_qgis(result)
        self.addCleanup(lambda: [QgsProject.instance().removeMapLayer(l.id()) for l in layers])
        seen = {l.customProperty("velantiswind/variable"): l.customProperty("velantiswind/unit") for l in layers}
        self.assertEqual(seen["wake_deficit_pct"], "%")
        self.assertEqual(seen["WS"], "m/s")
        self.assertIn("wake_deficit", seen)


if __name__ == "__main__":
    unittest.main()
