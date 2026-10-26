# -*- coding: utf-8 -*-
"""The exception of WeightedSum with the 0 m/s node (#63, P1): when it applies, its grids, its atomic attempt and the
0 m/s slice, which, inserted before the reductions, gives with PropagateDownwind and LinearSum the cases and sums
of the whole grid to the bit."""
import math
import os
import tempfile
import types
import unittest
import warnings

import numpy as np

from VelantisWind.ag_core import aep_compute
from VelantisWind.ag_core.results import aep_arrays
from VelantisWind.ag_core.simulation import zero_node
from VelantisWind.ag_core.turbine import build_wt_from_curve_table, build_wt_from_manual
from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, POINT, simulation_wind_turbines
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.wrg_site import load_wrg_site

HOURS = 8766.0


def sup(name, **params):
    return types.SimpleNamespace(superposition=types.SimpleNamespace(name=name, params=params))


class PlanTest(unittest.TestCase):
    GRID = np.arange(0.0, 26.0)

    def test_nothing_without_weightedsum_without_the_node_or_without_weighting(self):
        for config, grid in ((sup("LinearSum"), self.GRID), (sup("SquaredSum"), self.GRID), (sup("MaxSum"), self.GRID),
                             (sup("WeightedSum"), self.GRID[1:]), (sup("WeightedSum"), None),
                             (sup("WeightedSum", max_iter=0), self.GRID), (sup("WeightedSum", max_err=1.0), self.GRID),
                             (sup("WeightedSum", delta=math.nan), self.GRID)):
            with self.subTest(config=config, grid=None if grid is None else grid[0]):
                self.assertIs(zero_node.plan(config, grid), zero_node.ORDINARY)

    def test_the_grids(self):
        p = zero_node.plan(sup("WeightedSum"), [0.0, 0.5, 1.0, 1.5])
        self.assertTrue(p.applies)
        self.assertIsNone(p.warning)
        np.testing.assert_array_equal(p.operator_ws, [0.0, 0.5, 1.0, 1.5])
        np.testing.assert_array_equal(p.ws, [0.5, 1.0, 1.5])
        np.testing.assert_array_equal(p.small_ws, [0.0, 0.5])

    def test_not_applied_with_its_warning(self):
        for config, grid, reason in (
                (sup("WeightedSum", max_iter=math.inf), self.GRID, "max_iter = +inf"),
                (sup("WeightedSum", max_iter=math.inf, max_err=0.0), self.GRID, "max_iter = +inf"),
                (sup("WeightedSum"), [0.0, 1.0], "un solo nodo")):
            with self.subTest(reason=reason):
                p = zero_node.plan(config, grid)
                self.assertFalse(p.applies)
                self.assertIsNone(p.ws)  # the whole grid of the calculation is kept
                self.assertIn("no aplicada", p.warning)
                self.assertIn(reason, p.warning)

    def test_a_failure_preparing_it_is_the_ordinary_calculation_with_a_warning(self):
        broken = types.SimpleNamespace(superposition=types.SimpleNamespace(name="WeightedSum", params=None))
        p = zero_node.plan(broken, self.GRID)
        self.assertFalse(p.applies)
        self.assertIsNone(p.operator_ws)
        self.assertIn("no se pudo preparar", p.warning)

    def test_its_grids_are_copies(self):
        grid = self.GRID.copy()
        p = zero_node.plan(sup("WeightedSum"), grid)
        grid[1] = 7.0
        self.assertEqual(p.ws[0], 1.0)


def write_wrg(folder, height, name, empty_sector=True):
    """A 3×3 WRG with four sectors; with ``empty_sector``, the last one has frequency 0 and A = 0."""
    lines = ["3 3 1000 1000 500"]
    last = "0 0 200" if empty_sector else "250 80 200"
    for iy in range(3):
        for ix in range(3):
            sectors = " ".join(["400 90 210", "250 85 205", "350 95 215", last] if empty_sector
                               else ["300 90 210", "200 85 205", "250 95 215", last])
            lines.append(f"{1000 + 500 * ix} {1000 + 500 * iy} {20 * ix} {height} 9.0 2.1 300 4 {sectors}")
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def manual(name="Manual", hh=90.0, start=0.0):
    ws = [start, 3.0, 6.0, 9.0, 12.0, 25.0]
    return build_wt_from_manual(name, 100.0, hh, ws, [0.0, 40.0, 600.0, 1900.0, 3000.0, 3000.0],
                                [0.8, 0.8, 0.8, 0.7, 0.4, 0.1])


def density_table(name="Table", first=3.0):
    ws = (first, 6.0, 9.0, 12.0, 25.0)
    power = tuple(tuple(p * (0.8 + 0.2 * j) for j in range(2)) for p in (40.0, 600.0, 1900.0, 3000.0, 3000.0))
    ct = tuple(tuple(c * (1.0 - 0.4 * j) for j in range(2)) for c in (0.8, 0.8, 0.7, 0.4, 0.1))
    return build_wt_from_curve_table(TurbineCurveTable(
        name=name, diameter_m=100.0, hub_height_m=110.0, wind_speeds_ms=ws, air_densities=(1.0, 1.225), power_kw=power,
        ct=ct, default_air_density=1.225, cut_in_ms=first, cut_out_ms=25.0))


def model(wt, coords, hh):
    return {"name": wt.name(0), "wt": wt, "meta": {"hh": hh, "diam": 100.0, "p_rated_kw": 3000.0},
            "coords_xy": list(coords)}


class SliceTest(unittest.TestCase):
    """The 0 m/s slice of the small simulation, inserted before the reductions, against the whole grid."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings("ignore")
        cls.folder = tempfile.TemporaryDirectory()
        paths = [write_wrg(cls.folder.name, h, f"h{h}.wrg") for h in (80, 120)]
        cls.site, cls.ds, _ = load_wrg_site(paths)
        aep_compute._apply_fixed_ti(cls.site, 0.1, prefer_var="TI")
        cls.wd = np.asarray(cls.ds["wd"].values, dtype=float)
        cls.x, cls.y = np.array([1100.0, 1500.0, 1900.0, 1500.0]), np.array([1500.0, 1300.0, 1500.0, 1900.0])

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def pair(self, wt, grid, mode, deficit=None, **inputs):
        from py_wake.deficit_models import BastankhahGaussianDeficit
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import PropagateDownwind
        wfm = PropagateDownwind(self.site, simulation_wind_turbines(wt, grid, mode),
                                deficit or BastankhahGaussianDeficit(), superpositionModel=LinearSum())
        kwargs = dict(x=self.x, y=self.y, wd=self.wd, **inputs)
        full = wfm(ws=grid, **kwargs)
        seen = []

        def simulate(ws, operator_ws):
            seen.append((np.asarray(ws).copy(), np.asarray(operator_ws).copy()))
            return wfm(ws=ws, **kwargs)
        plan = zero_node.Plan(True, operator_ws=grid, ws=grid[1:], small_ws=grid[:2])
        attempt = zero_node.Attempt(plan)
        joined = attempt.simulate(simulate)
        self.assertEqual([s[0].tolist() for s in seen], [grid[1:].tolist(), grid[:2].tolist()])
        self.assertTrue(all(np.array_equal(s[1], grid) for s in seen))
        self.assertIsNone(attempt.error)
        return full, joined, attempt

    def assert_same(self, full, joined):
        """Equal to the bit (the bytes: +0 and −0 differ, and so does a NaN's payload)."""
        a_full, a_joined = full.aep(hours_pr_year=HOURS), joined.aep(hours_pr_year=HOURS)
        self.assertEqual(a_full.dims, a_joined.dims)
        np.testing.assert_array_equal(a_full.ws.values, a_joined.ws.values)
        self.assertEqual(a_full.values.tobytes(), a_joined.values.tobytes())
        self.assertEqual(aep_arrays.aep_per_turb(full, HOURS).tobytes(), aep_arrays.aep_per_turb(joined, HOURS).tobytes())
        by_wd = [aep_arrays.extract_directional_breakdown(s, s, sector_centers_deg=self.wd, hours_per_year=HOURS)
                 for s in (full, joined)]
        self.assertEqual([np.asarray(part, float).tobytes() for part in by_wd[0]],
                         [np.asarray(part, float).tobytes() for part in by_wd[1]])

    def test_one_curve_from_0_both_power_modes_and_two_steps(self):
        for grid in (np.arange(0.0, 26.0), np.arange(0.0, 25.5, 0.5)):
            for mode in (BIN_MEAN, POINT):
                with self.subTest(step=grid[1], mode=mode):
                    full, joined, _ = self.pair(manual(), grid, mode)
                    # The empty sector does give a non-finite P, only at 0 m/s, in the whole grid.
                    p = full["P"].transpose(..., "ws").values
                    self.assertFalse(np.isfinite(p[..., 0]).all())
                    self.assertTrue(np.isfinite(p[..., 1:]).all())
                    self.assert_same(full, joined)

    def test_types_hub_heights_and_air_density(self):
        models = [model(manual("A", 90.0), [(1100.0, 1500.0), (1500.0, 1300.0)], 90.0),
                  model(density_table("B", 3.0), [(1900.0, 1500.0)], 110.0),
                  model(density_table("C", 0.0), [(1500.0, 1900.0)], 110.0)]
        wt, use_types = aep_compute._combine_wt(models)
        self.assertTrue(use_types)
        grid = np.arange(0.0, 26.0)
        for mode in (BIN_MEAN, POINT):
            with self.subTest(mode=mode):
                full, joined, _ = self.pair(wt, grid, mode, type=np.array([0, 0, 1, 2]),
                                            Air_density=np.array([1.1, 1.2, 1.05, 1.15]))
                self.assert_same(full, joined)

    def test_a_nan_of_a_parameter_is_kept_in_the_slice(self):
        """k = NaN, admitted: WS_eff at 0 m/s is NaN, and the slice keeps it (Astra, round 4)."""
        from py_wake.deficit_models import BastankhahGaussianDeficit
        grid = np.arange(0.0, 26.0)
        full, joined, _ = self.pair(manual(), grid, BIN_MEAN, deficit=BastankhahGaussianDeficit(k=math.nan))
        small_slice = joined.small.aep(hours_pr_year=HOURS).isel(ws=0).values
        self.assertTrue(np.isnan(small_slice).any())
        np.testing.assert_array_equal(joined.aep(hours_pr_year=HOURS).isel(ws=0).values, small_slice)
        self.assert_same(full, joined)

    def test_other_fields_are_those_of_the_simulation_without_the_node(self):
        grid = np.arange(0.0, 26.0)
        full, joined, _ = self.pair(manual(), grid, BIN_MEAN)
        np.testing.assert_array_equal(joined["TI_eff"].ws.values, grid[1:])
        source = joined.diagnosis_source
        np.testing.assert_array_equal(source["WS_eff"].ws.values, grid)
        self.assertTrue(np.array_equal(source["P"].values, full["P"].values, equal_nan=True))
        self.assertTrue(np.array_equal(source["WS_eff"].values, full["WS_eff"].values, equal_nan=True))
        self.assertTrue(np.array_equal(source["Sector_frequency"].values, full["Sector_frequency"].values))
        self.assertIn("P", source)

    def test_finite_and_positive_gives_no_diagnosis_with_any_superposition(self):
        from py_wake.deficit_models import BastankhahGaussianDeficit
        from py_wake.superposition_models import LinearSum, MaxSum, SquaredSum, WeightedSum
        from py_wake.wind_farm_models import PropagateDownwind
        from VelantisWind.ag_core import edge_cases
        grid = np.arange(1.0, 26.0)
        for superposition in (LinearSum(), SquaredSum(), MaxSum(), WeightedSum()):
            with self.subTest(superposition=type(superposition).__name__):
                wfm = PropagateDownwind(self.site, simulation_wind_turbines(manual(), grid, BIN_MEAN),
                                        BastankhahGaussianDeficit(), superpositionModel=superposition)
                sim = wfm(x=self.x, y=self.y, wd=self.wd, ws=grid)
                aep = sim.aep(hours_pr_year=HOURS)
                arrays = {k: sim[v].broadcast_like(aep).transpose(*aep.dims).values
                          for k, v in (("ws_eff", "WS_eff"), ("p", "P"), ("power", "Power"))}
                self.assertIsNone(edge_cases.simulation_diagnosis(
                    aep=aep.values, frequency=sim["Sector_frequency"].broadcast_like(aep).values,
                    directions=self.wd, **arrays))

    def test_a_failure_joining_is_an_error_of_the_attempt(self):
        grid = np.arange(0.0, 26.0)
        _, joined, attempt = self.pair(manual(), grid, BIN_MEAN)
        joined.small = types.SimpleNamespace(aep=lambda **kw: (_ for _ in ()).throw(RuntimeError("roto")))
        with self.assertRaises(RuntimeError):
            joined.aep(hours_pr_year=HOURS)
        self.assertIsInstance(attempt.join_error, RuntimeError)


class AttemptTest(unittest.TestCase):
    PLAN = zero_node.Plan(True, operator_ws=np.arange(0.0, 4.0), ws=np.arange(1.0, 4.0), small_ws=np.arange(0.0, 2.0))

    def test_a_failed_simulation_is_recorded_and_raised(self):
        calls = []

        def simulate(ws, operator_ws):
            calls.append(ws[0])
            if ws[0] == 0.0:
                raise ValueError("zero-size array")
            return object()
        attempt = zero_node.Attempt(self.PLAN)
        with self.assertRaises(ValueError):
            attempt.simulate(simulate)
        self.assertIsInstance(attempt.error, ValueError)
        self.assertEqual(calls, [1.0, 0.0])
        self.assertIn("con la malla sin 0 m/s PyWake da un error: ValueError: zero-size array",
                      attempt.retry_warning())

    def test_the_auxiliary_convergence_leaves_out_weightedsum(self):
        attempt = zero_node.Attempt(self.PLAN)
        attempt.auxiliary.records["WeightedSum"].append({"state": "tolerance_not_met", "error": math.nan})
        attempt.auxiliary.records["All2AllIterative"].append({"state": "converged", "iterations": 2, "max_diff": 0.0})
        self.assertEqual(set(attempt.auxiliary_summary()), {"All2AllIterative"})

    def test_the_note(self):
        self.assertIn("0, 1 m/s", zero_node.Attempt(self.PLAN).note())


if __name__ == "__main__":
    unittest.main()
