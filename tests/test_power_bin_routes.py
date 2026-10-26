# -*- coding: utf-8 -*-
"""Every energy run uses the bin mean of the grid it simulates; POINT gives the base's AEP."""
import dataclasses
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from VelantisWind.ag_core import aep_compute
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory
from VelantisWind.ag_core.simulation import runner
from VelantisWind.ag_core.turbine import build_wt_from_manual
from VelantisWind.ag_core.turbines import bin_power
from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, POINT, bin_edges
from VelantisWind.energy_core.dialog_state import EnergyDialogState
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput
from VelantisWind.energy_core.runner import EnergyRunner

WS = [3.0, 6.0, 9.0, 12.0, 25.0]
POWER_KW = [0.0, 400.0, 1500.0, 3000.0, 3000.0]
CT = [0.8, 0.8, 0.7, 0.4, 0.1]
LAYOUT = [(1000.0, 1500.0), (1500.0, 1500.0)]
# POINT on this case with the default resource settings (28 directions, nearest, Speedup none, 3-25 m/s every 1,
# 8766 h), computed by the code before the resource settings (5df6417) with the same grids, in its own process on
# a git archive of it: [aep_free_mwh, aep_mwh] per turbine, and the six AEP with every variant on
# (plan_parametros_recurso_dev/evidencias/base_power_bin_routes.py). The physics that code executed, read from its
# results (#46 P5b): PropagateDownwind, BastankhahGaussianDeficit, CGIRotorAvg(7), WeightedSum and STF2017 for the
# first; All2AllIterative, CrespoHernandez, SelfSimilarityDeficit2020 and LinearSum for the variants. Asked for
# explicitly, the factory gives the same numbers; the old names of the variants are the schema-2 fields.
CGI7 = {"class": "CGIRotorAvg", "n": 7}
BASE_PHYSICS = {"version": 1, "rotor": CGI7, "superposition": "WeightedSum", "turbulence": "STF2017TurbulenceModel"}
VARIANTS_PHYSICS = {"version": 1, "engine": "All2AllIterative", "rotor": CGI7, "superposition": "LinearSum",
                    "turbulence": "CrespoHernandez", "blockage": "SelfSimilarityDeficit2020"}
SCHEMA_2 = {"aep_free_mwh": "aep_free_mwh", "aep_mwh": "aep_mwh", "aep_wake_only_mwh": "aep_w_mwh",
            "aep_wake_ti_mwh": "aep_wt_mwh", "aep_wake_blk_only_mwh": "aep_wb_mwh", "aep_wake_ti_blk_mwh": "aep_mwh"}
BASE_POINT = [[9998.484567077097, 9859.493263750366], [11001.377948138368, 10860.511056837982]]
BASE_VARIANTS = {
    "aep_free_mwh": [9998.484567077097, 11001.377948138368],
    "aep_mwh": [9858.231906823945, 10858.340821624794],
    "aep_wake_only_mwh": [9859.493263750366, 10860.511056837982],
    "aep_wake_ti_mwh": [9859.493263750366, 10860.511056837982],
    "aep_wake_blk_only_mwh": [9858.231906823945, 10858.340821624794],
    "aep_wake_ti_blk_mwh": [9858.231906823945, 10858.340821624794],
}


def write_wrg(folder):
    path = os.path.join(folder, "site.wrg")
    lines = ["3 3 1000 1000 500"]
    for iy in range(3):
        for ix in range(3):
            sectors = " ".join(f"250 {85 + 5 * ix} 210" for _ in range(4))
            lines.append(f"{1000 + 500 * ix} {1000 + 500 * iy} 0 90 9.0 2.1 300 4 {sectors}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def turbine():
    return build_wt_from_manual("T", 100.0, 90.0, WS, POWER_KW, CT)


def model(wt):
    return {"name": "T", "wt": wt, "meta": {"hh": 90.0, "diam": 100.0}, "coords_csv": "", "coords_xy": list(LAYOUT),
            "source_row_index": None, "source_type_index": None}


def curves(wt):
    pcf = wt.powerCtFunction
    return pcf.windTurbineFunction_lst if hasattr(pcf, "windTurbineFunction_lst") else [pcf]


def is_adapted(wt):
    return any(isinstance(c.power_ct, bin_power._BinMeanPowerCt) for c in curves(wt))


class Recorder:
    """Records, while active, every adaptation in the factory and every simulation the runner executes."""

    def __enter__(self):
        self.adaptations, self.sims = [], []
        adapt, call = factory.simulation_wind_turbines, runner.simulate

        def recording_adapt(wt, ws_grid, mode=BIN_MEAN):
            out = adapt(wt, ws_grid, mode)
            self.adaptations.append({"wt": wt, "grid": ws_grid, "mode": mode, "out": out})
            return out

        def recording_call(wfm, *args, **kwargs):
            sim = call(wfm, *args, **kwargs)
            ws = kwargs.get("ws")
            grid = np.asarray(ws if ws is not None else wfm.site.default_ws, dtype=float)
            self.sims.append({"wfm": wfm, "ws": ws, "grid": grid, "sim": sim})
            return sim

        self._patches = [mock.patch.object(factory, "simulation_wind_turbines", recording_adapt),
                         mock.patch.object(runner, "simulate", recording_call)]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False

    def free(self):
        found = [s for s in self.sims if type(s["wfm"].wake_deficitModel).__name__ == "NoWakeDeficit"]
        assert len(found) == 1, len(found)
        return found[0]


def mean_kw(lo, hi):
    """Mean (kW) of the point curve over [lo, hi], zero outside its band (3, 25): trapezoids on 1e-5 m/s."""
    x = np.arange(0.0, 30.0 + 1e-5, 1e-5)
    p = np.where((x >= 3.0) & (x <= 25.0), turbine().power(x, type=0) / 1e3, 0.0)
    prim = np.r_[0.0, np.cumsum((p[1:] + p[:-1]) / 2.0 * np.diff(x))]
    return (np.interp(hi, x, prim) - np.interp(lo, x, prim)) / (hi - lo)


def expected_free_power_kw(record):
    """The bin mean over the translated bin of each free-stream speed, on the simulated grid (kW)."""
    sim, grid = record["sim"], record["grid"]
    shape = np.asarray(sim.Power.ilk()).shape
    v = np.broadcast_to(np.asarray(sim.WS_eff.ilk(), float), shape)
    _, e = bin_edges(grid)
    j = np.clip(np.searchsorted(e, v, side="right") - 1, 0, grid.size - 1)
    return mean_kw(e[j] + v - grid[j], e[j + 1] + v - grid[j])


class RoutesTestBase(unittest.TestCase):
    def assertFinite(self, values, msg=None):
        """A NaN or an infinity fails, even where both sides of a comparison agree."""
        self.assertTrue(np.all(np.isfinite(np.asarray(values, dtype=float))), msg)

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.wrg = write_wrg(folder.name)

    def compute(self, **kwargs):
        kwargs.setdefault("fixed_ti", 0.1)
        kwargs.setdefault("compute_variants", False)
        kwargs.setdefault("wake_physics", BASE_PHYSICS)
        return aep_compute.compute_aep_from_ui("", [model(turbine())], wrg_paths=[self.wrg], **kwargs)

    def assertEachSimulationAdaptedOnce(self, rec):
        """Each simulation got its own adaptation, of turbines not yet adapted, with the grid it simulates."""
        self.assertGreater(len(rec.sims), 0)
        self.assertEqual(len(rec.adaptations), len(rec.sims))
        for a, s in zip(rec.adaptations, rec.sims):
            self.assertEqual(a["mode"], BIN_MEAN)
            self.assertIs(s["wfm"].windTurbines, a["out"])
            self.assertFalse(is_adapted(a["wt"]))
            for c in curves(s["wfm"].windTurbines):
                np.testing.assert_array_equal(c.power_ct.grid, s["grid"])

    def assertGrossIsTheBinMean(self, rec, result, hours, atol_kw=0.03):
        """The free-stream power of each flow case and the gross AEP per turbine against the separate mean."""
        free = rec.free()
        expected = expected_free_power_kw(free)
        self.assertFinite(expected)
        self.assertFinite(free["sim"].Power.values)
        # 30 W: the oracle mesh at the steps of the band, P · 1e-5 / 2 (the plan's tolerance against the oracle).
        np.testing.assert_allclose(np.asarray(free["sim"].Power.ilk()) / 1e3, expected, rtol=0, atol=atol_kw)
        P = np.broadcast_to(np.asarray(free["sim"].P.ilk(), float), expected.shape)
        aep_mwh = np.sum(P * expected, axis=(1, 2)) * hours / 1e3
        got = [row["aep_free_mwh"] for row in result["per_turbine_table"]]
        self.assertEqual(len(got), len(LAYOUT))
        self.assertFinite(got)
        np.testing.assert_allclose(got, aep_mwh, rtol=1e-6, atol=0)


class DialogRoutesTest(RoutesTestBase):
    def test_single_case_with_its_defaults(self):
        """EnergyRunner with EnergyRunConfig's defaults: the turbine's band (3-25 m/s every 1), Speedup none, variants on
        (the default physics has none: the main simulation and the free stream)."""
        config = EnergyRunConfig(models=[TurbineModelInput(**model(turbine()))], wrg_paths=[self.wrg],
                                 update_project_layers=False)
        with Recorder() as rec:
            result = EnergyRunner().run(config)
        self.assertEachSimulationAdaptedOnce(rec)
        self.assertEqual(len(rec.sims), 2)
        for s in rec.sims:
            np.testing.assert_array_equal(s["grid"], np.arange(3.0, 26.0))
        self.assertTrue(np.all(np.asarray(rec.free()["sim"].WS_eff.ilk()) % 1 == 0))  # no speed-up: the grid itself
        self.assertGrossIsTheBinMean(rec, result, 8766.0)

    def test_nothing_on_the_dialog_path_chooses_a_mode(self):
        self.assertNotIn("power_bin_mode", {f.name for f in dataclasses.fields(EnergyRunConfig)})
        self.assertNotIn("power_bin_mode", EnergyRunConfig().to_compute_kwargs())
        self.assertNotIn("power_bin_mode", EnergyDialogState.__annotations__)
        self.assertNotIn("power_bin_mode", inspect.signature(aep_compute.compute_and_update).parameters)
        root = Path(aep_compute.__file__).resolve().parents[1]
        for path in sorted((root / "energy_core").glob("*.py")) + sorted(root.glob("*.py")):
            with self.subTest(path=path.name):
                self.assertNotIn("power_bin_mode", path.read_text(encoding="utf-8"))

    def test_every_touched_function_defaults_to_the_bin_mean(self):
        functions = (factory.build_wind_farm_model, factory.build_free_stream_model, aep_compute.compute_aep_from_ui)
        for fn in functions:
            with self.subTest(function=fn.__name__):
                self.assertEqual(inspect.signature(fn).parameters["power_bin_mode"].default, BIN_MEAN)


class ChosenStepTest(RoutesTestBase):
    def test_every_simulation_uses_the_grid_of_the_chosen_step(self):
        with Recorder() as rec:
            result = self.compute(energy_ws_step=0.5)
        grid = 3.0 + 0.5 * np.arange(45)
        self.assertEachSimulationAdaptedOnce(rec)
        for s in rec.sims:
            np.testing.assert_array_equal(s["grid"], grid)
        np.testing.assert_allclose(np.diff(bin_edges(grid)[1]), 0.5, rtol=0, atol=1e-12)
        # The oracle's error at a step of the band is spread over a bin half as wide: twice the 30 W.
        self.assertGrossIsTheBinMean(rec, result, 8766.0, atol_kw=0.06)


class PointTest(RoutesTestBase):
    def test_only_the_power_changes(self):
        sims = {}
        for mode in (BIN_MEAN, POINT):
            with Recorder() as rec:
                self.compute(power_bin_mode=mode)
            sims[mode] = rec.sims
        self.assertEqual(len(sims[BIN_MEAN]), len(sims[POINT]))
        for mean, point in zip(sims[BIN_MEAN], sims[POINT]):
            for name in ("P", "WS_eff", "CT"):
                self.assertFinite(mean["sim"][name].values, name)
                np.testing.assert_array_equal(mean["sim"][name].values, point["sim"][name].values, err_msg=name)
            self.assertFinite(mean["sim"].Power.values)
            self.assertFinite(point["sim"].Power.values)
            self.assertFalse(np.allclose(mean["sim"].Power.values, point["sim"].Power.values))

    def test_point_uses_the_original_turbines_and_gives_the_base(self):
        with Recorder() as rec:
            result = self.compute(power_bin_mode=POINT)
        self.assertEqual(len(rec.adaptations), len(rec.sims))
        for a, s in zip(rec.adaptations, rec.sims):
            self.assertEqual(a["mode"], POINT)
            self.assertIs(a["out"], a["wt"])
            self.assertIs(s["wfm"].windTurbines, a["wt"])
            self.assertFalse(is_adapted(s["wfm"].windTurbines))
        got = [[row["aep_free_mwh"], row["aep_mwh"]] for row in result["per_turbine_table"]]
        self.assertFinite(got)
        np.testing.assert_allclose(got, BASE_POINT, rtol=1e-12, atol=0)
        mean = self.compute()
        mean_got = [[row["aep_free_mwh"], row["aep_mwh"]] for row in mean["per_turbine_table"]]
        self.assertEqual(np.shape(mean_got), np.shape(BASE_POINT))
        self.assertFinite(mean_got)
        self.assertFalse(np.allclose(mean_got, BASE_POINT, rtol=1e-9, atol=0))

    def test_variants_reach_the_mode(self):
        """With every variant on (A2A, SS2020): POINT gives the base's six AEP, the bin mean changes all six."""
        results = {}
        for mode in (POINT, BIN_MEAN):
            r = self.compute(compute_variants=True, wake_physics=VARIANTS_PHYSICS, power_bin_mode=mode)
            executed = r["wake_config"]["executed"]
            self.assertEqual((executed["blockage"]["class"], executed["engine"]["class"]),
                             ("SelfSimilarityDeficit2020", "All2AllIterative"))
            results[mode] = {k: [row[SCHEMA_2[k]] for row in r["per_turbine_table"]] for k in BASE_VARIANTS}
        for key, base in BASE_VARIANTS.items():
            with self.subTest(key=key):
                for mode in (POINT, BIN_MEAN):
                    self.assertEqual(len(results[mode][key]), len(base), mode)
                    self.assertFinite(results[mode][key], mode)
                np.testing.assert_allclose(results[POINT][key], base, rtol=1e-12, atol=0)
                for got, ref in zip(results[BIN_MEAN][key], base):
                    self.assertGreater(abs(got - ref) / ref, 1e-9)


class FactoryAndRunnerTest(unittest.TestCase):
    """The public factory and the runner called directly (problems 2, 6 and 7)."""

    def setUp(self):
        from py_wake.site import UniformWeibullSite

        self.wt = build_wt_from_manual("T", 100.0, 90.0, [3, 4.5, 5, 5.5, 8, 25], [0, 0, 100, 300, 300, 300], [0.8] * 6)
        self.site = UniformWeibullSite(p_wd=[1], a=[8], k=[2], ti=0.1)

    def wfm(self, **kwargs):
        config = cfg.WakeConfig(**{**cfg.default_config(deficit="NOJDeficit").__dict__,
                                   "superposition": cfg.Component("LinearSum", {})})
        return factory.build_wind_farm_model(config, self.site, self.wt, **kwargs)

    def power_kw(self, sim, ws):
        k = list(np.asarray(sim.ws)).index(ws)
        return float(np.asarray(sim.Power.ilk())[0, 0, k]) / 1e3

    def test_factory_alone_uses_the_site_grid(self):
        """Problem 2: the issue's 125 kW at 5 m/s (bin [4.5, 5.5]), not the base's 100."""
        sim = runner.simulate(self.wfm(), np.array([0.0]), np.array([0.0]), wd=np.array([270.0]))
        self.assertAlmostEqual(self.power_kw(sim, 5.0), 125.0, delta=1e-9)

    def test_factory_with_the_simulated_grid(self):
        """Problem 7: with the grid [3, 5, 8], the bin of 5 is [4, 6.5]."""
        grid = np.array([3.0, 5.0, 8.0])
        sim = runner.simulate(self.wfm(ws_grid=grid), np.array([0.0]), np.array([0.0]),
                                                    wd=np.array([270.0]), ws=grid)
        self.assertAlmostEqual(self.power_kw(sim, 5.0), (25 + 100 + 300 * 1) / 2.5, delta=1e-9)
        self.assertAlmostEqual(self.power_kw(sim, 5.0), 170.0, delta=1e-9)

    def test_simulating_another_grid_than_the_adapted_one_stops(self):
        with self.assertRaises(ValueError):
            runner.simulate(self.wfm(), np.array([0.0]), np.array([0.0]), wd=np.array([270.0]),
                            ws=np.array([3.0, 5.0, 8.0]))

    def test_the_factory_adapts_once_with_its_grid(self):
        grid = np.array([3.0, 5.0, 8.0])
        for mode in (BIN_MEAN, POINT):
            with self.subTest(mode=mode), Recorder() as rec:
                extra = {} if mode == BIN_MEAN else {"power_bin_mode": POINT}
                sim = runner.simulate(self.wfm(ws_grid=grid, **extra), np.array([0.0]), np.array([0.0]),
                                      wd=np.array([270.0]), ws=grid)
                self.assertEqual(len(rec.adaptations), 1)
                self.assertIs(rec.adaptations[0]["grid"], grid)
                self.assertEqual(rec.adaptations[0]["mode"], mode)
                expected = 170.0 if mode == BIN_MEAN else 100.0
                self.assertAlmostEqual(self.power_kw(sim, 5.0), expected, delta=1e-9)

    def test_point_keeps_the_turbines_and_an_unknown_mode_fails(self):
        """Problem 6."""
        self.assertIs(factory.simulation_wind_turbines(self.wt, None, POINT), self.wt)
        with self.assertRaisesRegex(ValueError, "desconocido"):
            factory.simulation_wind_turbines(self.wt, np.array([3.0, 5.0]), "centre")
        with self.assertRaises(ValueError):
            factory.simulation_wind_turbines(self.wt, None, BIN_MEAN)

if __name__ == "__main__":
    unittest.main()
