# -*- coding: utf-8 -*-
"""The points of the ordinary calculation of #63 (P2): the curve per density outside its wind-speed axis, the
runner with the grid of the exception of WeightedSum, the exception in the AEP with its atomic attempt, the
protected diagnosis of each simulation, the raster at the speed asked for and the predicate of WeightedSum."""
import copy
import math
import os
import tempfile
import types
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core import aep_compute as ac
from VelantisWind.ag_core import edge_cases as ec
from VelantisWind.ag_core.results import aep_arrays
from VelantisWind.ag_core.simulation import runner, zero_node
from VelantisWind.ag_core.turbine import _pad_curve_grid, build_wt_from_curve_table
from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, POINT, simulation_wind_turbines
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.wake_setup import api
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory
from tests.test_zero_node import density_table, manual, model, write_wrg

NAN, INF = math.nan, math.inf
HOURS = 8766.0
LAYOUT = [(1100.0, 1500.0), (1500.0, 1500.0), (1900.0, 1500.0)]


def physics(engine="PropagateDownwind", deficit="BastankhahGaussianDeficit", superposition="LinearSum",
            sup_params=None, **fields):
    base = cfg.default_config(engine, deficit)
    config = cfg.WakeConfig(**{**base.__dict__, "superposition": cfg.Component(superposition, dict(sup_params or {})),
                               **fields})
    return config


def comparable(result):
    """What a result says of the calculation, without its templates: to compare two results to the bit."""
    rows = [{k: v for k, v in row.items()} for row in result["per_turbine_table"]]
    return {"rows": rows, "breakdown": result["breakdown"], "per_wd": (result["aep_per_wd_wake_MWh"],
                                                                      result["aep_per_wd_free_MWh"]),
            "aep": result["aep_wake_MWh"], "free": result["aep_free_MWh"]}


def same_bits(test, a, b):
    """Every float of two nested structures equal to the bit (+0 and −0 differ)."""
    if isinstance(a, dict):
        test.assertEqual(set(a), set(b))
        for k in a:
            same_bits(test, a[k], b[k])
    elif isinstance(a, (list, tuple)):
        test.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            same_bits(test, x, y)
    elif isinstance(a, float) or isinstance(b, float):
        test.assertEqual(np.float64(a).tobytes(), np.float64(b).tobytes(), (a, b))
    else:
        test.assertEqual(a, b)


class DensityCurveTest(unittest.TestCase):
    """Decision 1: the curve per density outside its wind-speed axis, as PyWake's 1-D curve with the same data."""

    @classmethod
    def setUpClass(cls):
        cls.wts = {first: density_table(first=first) for first in (0.0, 3.0)}

    @staticmethod
    def curve(wt):
        """The N-D curve of a turbine per density (the constructor puts it in a list by type)."""
        return wt.powerCtFunction.windTurbineFunction_lst[0]

    @staticmethod
    def one_dimensional(curve, column):
        """PyWake's 1-D tabular curve with the same data: the axis and the column of one density of the table."""
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
        n = curve.interp[0].V.shape[0]
        ws = curve.interp[0].x[0][:n]
        return PowerCtTabular(ws, curve.interp[0].V[:, column], "W", curve.interp[1].V[:, column])

    def test_as_the_one_dimensional_curve_outside_the_axis(self):
        """Outside the axis, the value of its end to the bit, and NaN with NaN; inside, the same interpolation
        (written otherwise by each class: to rounding)."""
        outside = np.array([-6016.0, -1.0, -0.1, -INF, INF, 1001.0, 1e9, NAN])
        inside = np.array([0.0, 2.5, 5.0, 17.3, 1000.0])
        for first, wt in self.wts.items():
            curve = self.curve(wt)
            densities = curve.interp[0].x[1][:curve.interp[0].V.shape[1]]
            for column, rho in enumerate(densities):
                with self.subTest(first=first, rho=rho):
                    reference = self.one_dimensional(curve, column)
                    for run_only in (0, 1):
                        got = curve._power_ct(outside, run_only, Air_density=np.full(outside.shape, rho))
                        expected = reference.np_interp(outside, run_only)
                        self.assertEqual(np.asarray(got, float).tobytes(), np.asarray(expected, float).tobytes())
                        got = curve._power_ct(inside, run_only, Air_density=np.full(inside.shape, rho))
                        np.testing.assert_allclose(got, reference.np_interp(inside, run_only), rtol=1e-12, atol=1e-9)

    def test_inside_the_axis_the_call_of_always(self):
        """The oracle is the previous expression: PyWake's N-D call after the clip of the density."""
        from py_wake.wind_turbines.power_ct_functions import PowerCtNDTabular
        speeds = np.concatenate([np.linspace(0.0, 30.0, 61), [999.9999, 1000.0], np.linspace(0.05, 26.3, 17)])
        for first, wt in self.wts.items():
            curve = self.curve(wt)
            for rho in (0.9, 1.0, 1.1, 1.225, 1.3):
                with self.subTest(first=first, rho=rho):
                    density = np.full(speeds.shape, rho)
                    clipped = np.clip(density, 1.0, 1.225)
                    for run_only in (0, 1):
                        got = curve._power_ct(speeds, run_only, Air_density=density)
                        before = PowerCtNDTabular._power_ct(curve, speeds, run_only, Air_density=clipped)
                        self.assertEqual(np.asarray(got).tobytes(), np.asarray(before).tobytes())

    def test_the_cases_that_stopped_now_calculate(self):
        from py_wake.wind_turbines.power_ct_functions import PowerCtNDTabular
        wt = self.wts[3.0]
        for speeds in (np.array([-1.0, 5.0]), np.array([INF, 5.0]), np.array([NAN, 5.0])):
            with self.subTest(speeds=speeds):
                with self.assertRaises((ValueError, IndexError)):
                    PowerCtNDTabular._power_ct(self.curve(wt), speeds, 0, Air_density=np.full(2, 1.1))
                power = wt.power(speeds, type=np.zeros(2, int), Air_density=np.full(2, 1.1))
                self.assertEqual(np.isnan(power).tolist(), np.isnan(speeds).tolist())

    def test_the_value_at_0_is_that_of_the_table(self):
        """0 with the padding of a table from the cut-in; the tabulated Ct with a table from 0 m/s."""
        for first, ct0 in ((3.0, 0.0), (0.0, 0.8)):
            ct = self.wts[first].ct(np.array([-6016.0, 0.0]), type=np.zeros(2, int), Air_density=np.full(2, 1.0))
            self.assertEqual(ct.tolist(), [ct0, ct0])

    def test_the_safe_input_of_a_nan_does_not_write_on_ws(self):
        speeds = np.array([NAN, -2.0, 5.0, INF])
        before = speeds.copy()
        self.wts[0.0].power(speeds, type=np.zeros(4, int), Air_density=np.full(4, 1.1))
        self.assertEqual(speeds.tobytes(), before.tobytes())

    def test_a_traced_speed_keeps_its_gradient(self):
        """A ws traced by autograd (PyWake's gradients) outside the axis: its end, with gradient 0 (Astra, P2 r1)."""
        from py_wake.utils.gradients import autograd
        curve = self.curve(self.wts[3.0])

        def power(ws):
            return curve._power_ct(ws, 0, Air_density=np.full(2, 1.1))
        inside = autograd(power, vector_interdependence=False)(np.array([4.0, 5.0]))
        for outside in ([-1.0, 5.0], [30.0, 5.0]):
            gradient = autograd(power, vector_interdependence=False)(np.array(outside))
            self.assertEqual((gradient[0], gradient[1]), (0.0, inside[1]))

    def test_a_speed_traced_twice(self):
        """A ws traced at the second order (nested traces): outside the axis, what PyWake's table does inside it,
        whose interpolation does not take nested traces (``gradients.modf``); the mask reads the values at any
        order, so the failure, if any, is never the clip's (Astra, P2 r2)."""
        from autograd import elementwise_grad
        curve = self.curve(self.wts[3.0])

        def power(ws):
            return curve._power_ct(ws, 0, Air_density=np.full(2, 1.1))

        def second(speeds):
            try:
                return elementwise_grad(elementwise_grad(power))(np.array(speeds)).tolist()
            except Exception as exc:
                return type(exc), str(exc)
        inside = second([4.0, 5.0])
        # PyWake's own failure (``ValueError`` of its interpolation), or, if it takes nested traces, the second
        # derivative of a curve linear by pieces (Sol, P2 r1): not any common failure.
        self.assertIn(inside if isinstance(inside, list) else inside[0], ([0.0, 0.0], ValueError))
        for outside in ([-1.0, 5.0], [30.0, 5.0]):
            self.assertEqual(second(outside), inside)

    def test_combined_turbines(self):
        models = [model(self.wts[0.0], [(0.0, 0.0)], 110.0), model(self.wts[3.0], [(500.0, 0.0)], 110.0)]
        wt, use_types = ac._combine_wt(models)
        self.assertTrue(use_types)
        # Inside the axis, each type gives the previous expression (the N-D call after the clip of the density), to
        # the bit (Astra, P2 r3).
        from py_wake.wind_turbines.power_ct_functions import PowerCtNDTabular
        inside = np.concatenate([np.linspace(0.0, 30.0, 61), [1000.0]])
        for t, first in enumerate((0.0, 3.0)):
            for rho in (0.9, 1.1, 1.3):
                density = np.full(inside.shape, rho)
                before = PowerCtNDTabular._power_ct(self.curve(self.wts[first]), inside, 0,
                                                    Air_density=np.clip(density, 1.0, 1.225))
                got = wt.power(inside, type=np.full(inside.shape, t), Air_density=density)
                self.assertEqual(np.asarray(got, float).tobytes(), np.asarray(before, float).tobytes())
        speeds = np.array([-6016.0, -1.0, 0.0, 5.0, NAN])
        for t in (0, 1):
            power = wt.power(speeds, type=np.full(5, t), Air_density=np.full(5, 1.1))
            reference = self.wts[(0.0, 3.0)[t]].power(speeds, type=np.zeros(5, int), Air_density=np.full(5, 1.1))
            self.assertEqual(np.asarray(power).tobytes(), np.asarray(reference).tobytes())


class RunnerTest(unittest.TestCase):
    """Decision 4: ``operator_ws`` of the runner, only for the two grids of the exception."""

    def setUp(self):
        from py_wake.site import UniformWeibullSite
        self.site = UniformWeibullSite(p_wd=[1], a=[8], k=[2], ti=0.1)
        self.grid = np.arange(0.0, 6.0)

    def wfm(self):
        config = physics(deficit="NOJDeficit")
        return factory.build_wind_farm_model(config, self.site, manual(), ws_grid=self.grid)

    def simulate(self, **kwargs):
        return runner.simulate(self.wfm(), np.array([0.0]), np.array([0.0]), wd=np.array([270.0]), **kwargs)

    def test_without_it_the_check_of_always(self):
        self.simulate(ws=self.grid)
        with self.assertRaises(ValueError):
            self.simulate(ws=self.grid[1:])

    def test_with_it_exactly_the_two_grids(self):
        for ws in (self.grid[1:], self.grid[:2]):
            self.simulate(ws=ws, operator_ws=self.grid)
        for ws in (self.grid, self.grid[2:], self.grid[:3], self.grid[1:2], None):
            with self.subTest(ws=ws), self.assertRaises(ValueError):
                self.simulate(ws=ws, operator_ws=self.grid)

    def test_the_whole_grid_starts_at_0(self):
        with self.assertRaises(ValueError):
            self.simulate(ws=self.grid[2:], operator_ws=self.grid[1:])


class _AepCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        cls.folder = tempfile.TemporaryDirectory()
        cls.wrg = write_wrg(cls.folder.name, 90, "full.wrg", empty_sector=False)
        cls.empty_wrg = write_wrg(cls.folder.name, 90, "empty.wrg", empty_sector=True)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def compute(self, config, *, wt=None, wrg=None, **kwargs):
        models = [model(wt or manual(), LAYOUT, 90.0)]
        kwargs.setdefault("compute_variants", True)
        return ac.compute_aep_from_ui("", models, wrg_paths=[wrg or self.wrg], fixed_ti=0.1, energy_ws_step=1.0,
                                      wake_physics=api.to_wake_physics(config), **kwargs)

    def ordinary(self, config, **kwargs):
        """The same calculation without the exception: the oracle of what is kept to the bit."""
        with mock.patch.object(zero_node, "plan", return_value=zero_node.ORDINARY):
            return self.compute(config, **kwargs)


WS = physics(superposition="WeightedSum", turbulence=cfg.Component("CrespoHernandez", {}))
LINEAR = physics(turbulence=cfg.Component("CrespoHernandez", {}))


class ExceptionTest(_AepCase):
    """Decision 4: with WeightedSum and the 0 m/s node, the simulations without it and the slice of a small one."""

    def test_it_applies_and_weighs(self):
        r = self.compute(WS)
        self.assertEqual(r["executed_ws"]["zero_node_m_s"], [0.0, 1.0])
        self.assertEqual(r["executed_ws"]["bin_mean_m_s"][0], 0.0)
        self.assertEqual(r["executed_ws"]["simulations_m_s"], r["executed_ws"]["bin_mean_m_s"][1:])
        self.assertTrue(any("el nodo de 0 m/s se calcula aparte" in str(n) for n in r["simulation_notes"]))
        states = r["convergence"]["main"]["WeightedSum"]["states"]
        self.assertNotIn("tolerance_not_met", states)  # no NaN residual from the 0 m/s node
        self.assertEqual(r["convergence"]["main"]["WeightedSum"]["non_finite_residuals"], 0)
        self.assertNotIn("WeightedSum", r["convergence"]["auxiliary_zero"])
        # The whole grid, today: every call ends with a non-finite residual (it adds linearly).
        o = self.ordinary(WS)
        self.assertEqual(set(o["convergence"]["main"]["WeightedSum"]["states"]), {"tolerance_not_met"})
        self.assertGreater(o["convergence"]["main"]["WeightedSum"]["non_finite_residuals"], 0)
        self.assertNotIn("executed_ws", o)

    def test_the_aep_is_that_of_the_slice_and_the_rest(self):
        """The principal AEP is the 0 m/s slice of the small simulation and the rest, before the reductions."""
        r = self.compute(WS, compute_variants=False)
        captured = {}
        real = runner.simulate

        def spy(wfm, *args, **kwargs):
            sim = real(wfm, *args, **kwargs)
            captured.setdefault("calls", []).append((np.asarray(kwargs.get("ws")).tolist(), sim))
            return sim
        with mock.patch.object(runner, "simulate", side_effect=spy):
            again = self.compute(WS, compute_variants=False)
        (rest_ws, rest), (small_ws, small) = captured["calls"][:2]
        self.assertEqual(small_ws, [0.0, 1.0])
        # The oracle, written apart: the 0 m/s cases of the small one, then the others, and np.nansum per turbine.
        cells = np.concatenate([small.aep(hours_pr_year=HOURS).values[..., :1], rest.aep(hours_pr_year=HOURS).values],
                               axis=-1)
        expected = np.nansum(cells, axis=(1, 2)) * 1000.0
        got = np.array([row["aep_mwh"] for row in again["per_turbine_table"]])
        self.assertEqual(got.tobytes(), expected.tobytes())
        same_bits(self, comparable(r), comparable(again))

    def test_a_0_and_a_calculation_without_iterations_are_kept_to_the_bit(self):
        """A_0 (LinearSum), and the AEP when WeightedSum does not iterate (max_err above its first residual)."""
        r, o = self.compute(WS), self.ordinary(WS)
        same_bits(self, [row["aep_free_mwh"] for row in r["per_turbine_table"]],
                  [row["aep_free_mwh"] for row in o["per_turbine_table"]])
        still = physics(superposition="WeightedSum", sup_params={"max_err": 0.95})
        r, o = self.compute(still, compute_variants=False), self.ordinary(still, compute_variants=False)
        self.assertIn("executed_ws", r)
        same_bits(self, [row["aep_mwh"] for row in r["per_turbine_table"]],
                  [row["aep_mwh"] for row in o["per_turbine_table"]])

    def test_without_the_node_the_path_of_always(self):
        wt = manual(start=3.0)  # a band from the cut-in: no 0 m/s in the grid
        r = self.compute(WS, wt=wt)
        self.assertNotIn("executed_ws", r)
        self.assertFalse(any("0 m/s se calcula aparte" in str(n) for n in r["simulation_notes"]))
        self.assertNotIn("auxiliary_zero", r["convergence"])
        same_bits(self, comparable(r), comparable(self.ordinary(WS, wt=wt)))

    def test_other_superpositions_are_not_touched(self):
        for name in ("LinearSum", "SquaredSum", "MaxSum"):
            with self.subTest(name=name):
                config = physics(superposition=name)
                calls = []
                real = zero_node.plan

                def spy(*args):
                    calls.append(real(*args))
                    return calls[-1]
                with mock.patch.object(zero_node, "plan", side_effect=spy):
                    r = self.compute(config, compute_variants=False)
                self.assertIs(calls[0], zero_node.ORDINARY)
                self.assertNotIn("executed_ws", r)
                self.assertNotIn("edge_cases", r)
                # The oracle, assembled apart with the pieces of always: the site, the factory, the runner and
                # aep_per_turb, with the grids the result records.
                from VelantisWind.ag_core.wrg_site import load_wrg_site
                rs = r["resource_settings"]
                site, _ds, _label = load_wrg_site([self.wrg])
                ac._apply_fixed_ti(site, 0.1, prefer_var="TI")
                grid, wd = np.asarray(rs["ws_m_s"]), np.asarray(rs["wd_eval_deg"])
                sim = runner.simulate(factory.build_wind_farm_model(config, site, manual(), ws_grid=grid),
                                      np.array([p[0] for p in LAYOUT]), np.array([p[1] for p in LAYOUT]), wd=wd, ws=grid)
                expected = aep_arrays.aep_per_turb(sim, rs["hours_per_year"])
                got = np.array([row["aep_mwh"] for row in r["per_turbine_table"]])
                self.assertEqual(got.tobytes(), expected.tobytes())

    def test_with_max_iter_infinite_it_is_not_applied(self):
        config = physics(superposition="WeightedSum", sup_params={"max_iter": INF})
        real = runner.simulate
        grids = []

        def guarded(wfm, *args, **kwargs):
            # The exception would simulate without 0 m/s, where it may never end: here the whole grid, always. Each
            # grid is recorded (asserted after: a failure in here would be one of the attempt), and every simulation
            # runs with a finite max_iter, so no loop without end can run even if this test fails.
            grids.append((kwargs.get("operator_ws") is None, float(np.asarray(kwargs.get("ws"))[0])))
            if type(wfm.superpositionModel).__name__ == "WeightedSum":
                wfm.superpositionModel.max_iter = 5
            return real(wfm, *args, **kwargs)
        with mock.patch.object(runner, "simulate", side_effect=guarded):
            r = self.compute(config, compute_variants=False)
        self.assertTrue(grids)
        self.assertEqual(set(grids), {(True, 0.0)})
        self.assertNotIn("executed_ws", r)
        self.assertTrue(any("max_iter = +inf" in str(w) for w in r["edge_cases"]["warnings"]))

    def test_the_auxiliary_convergence_of_all2all_is_kept(self):
        config = physics(engine="All2AllIterative", superposition="WeightedSum")
        r = self.compute(config, compute_variants=False)
        auxiliary = r["convergence"]["auxiliary_zero"]
        self.assertIn("All2AllIterative", auxiliary)
        self.assertNotIn("WeightedSum", auxiliary)


class AtomicAttemptTest(_AepCase):
    """Decision 4: if a simulation of the attempt fails (late: in a variant, in A_0 or in a small one), nothing of the
    attempt survives and the whole calculation is repeated with the whole grid, with its warning."""

    def failing(self, predicate):
        real = runner.simulate
        state = {"n": 0}

        def wrapper(wfm, *args, **kwargs):
            state["n"] += 1
            if kwargs.get("operator_ws") is not None and predicate(state["n"], wfm, kwargs):
                raise ValueError("zero-size array to reduction operation maximum which has no identity")
            return real(wfm, *args, **kwargs)
        return mock.patch.object(runner, "simulate", side_effect=wrapper)

    def check(self, r):
        o = self.ordinary(WS)
        same_bits(self, comparable(r), comparable(o))
        self.assertEqual(r["convergence"], o["convergence"])
        self.assertNotIn("executed_ws", r)
        self.assertFalse(any("0 m/s se calcula aparte" in str(n) for n in r["simulation_notes"]))
        warnings_ = [str(w) for w in r["edge_cases"]["warnings"]]
        self.assertTrue(any("con la malla sin 0 m/s PyWake da un error: ValueError: zero-size array" in w
                            for w in warnings_), warnings_)

    def test_a_late_failure_in_a_variant(self):
        free = factory.build_free_stream_model
        with self.failing(lambda n, wfm, kw: n > 4 and type(wfm.wake_deficitModel).__name__ != "NoWakeDeficit"):
            self.check(self.compute(WS))
        self.assertIs(factory.build_free_stream_model, free)

    def test_a_failure_in_a_0(self):
        with self.failing(lambda n, wfm, kw: type(wfm.wake_deficitModel).__name__ == "NoWakeDeficit"):
            self.check(self.compute(WS))

    def test_a_failure_joining_wins_over_a_failed_simulation(self):
        """Joining the slice fails in the main one and a simulation fails later (A_0): the error of the join is the
        error of the calculation, never a repetition (Astra, P2 r1)."""
        def broken(self_, rest, small):
            exc = RuntimeError("la rebanada no se junta")
            self_._on_error(exc)
            raise exc
        with mock.patch.object(zero_node.Joined, "_join", broken), \
                self.failing(lambda n, wfm, kw: type(wfm.wake_deficitModel).__name__ == "NoWakeDeficit"):
            with self.assertRaisesRegex(RuntimeError, "la rebanada no se junta"):
                self.compute(WS)

    def test_a_failure_in_a_small_simulation(self):
        with self.failing(lambda n, wfm, kw: n > 2 and np.asarray(kw["ws"]).size == 2):
            self.check(self.compute(WS))


class PudCounterexampleTest(_AepCase):
    """Astra, round 6: PropagateUpDownIterative, WeightedSum(max_err=0.95) and SelfSimilarityDeficit. The whole grid
    calculates; without 0 m/s PyWake raises (``diff_ilk[iconverging].max()`` of an empty mask), so the calculation is
    repeated with the whole grid: the AEP of always to the bit, with its warning, in both power modes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lines = ["3 3 -500 -500 500"] + [f"{-500 + 500 * ix} {-500 + 500 * iy} 0 70 8.0 2.0 300 1 1000 80 200"
                                         for iy in range(3) for ix in range(3)]
        cls.pud_wrg = os.path.join(cls.folder.name, "pud.wrg")
        with open(cls.pud_wrg, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        base = cfg.default_config("PropagateUpDownIterative", "BastankhahGaussianDeficit")
        cls.config = cfg.WakeConfig(**{
            **base.__dict__,
            "deficit": cfg.Component("BastankhahGaussianDeficit", {**base.deficit.params, "use_effective_ws": True}),
            "superposition": cfg.Component("WeightedSum", {"max_err": 0.95}),
            "blockage": cfg.Component("SelfSimilarityDeficit", {"ss_gamma": 1000, "use_effective_ws": True,
                                                                "exclude_wake": False}),
            "blockage_superposition": cfg.Component("LinearSum", {})})

    def compute_pud(self, mode):
        from VelantisWind.ag_core.turbine import build_wt_from_manual
        wt = build_wt_from_manual("T", 80.0, 70.0, [0, 1, 4, 12, 25], [1, 50, 300, 2000, 2000], [0.8] * 5)
        return ac.compute_aep_from_ui("", [model(wt, [(0.0, -300.0), (0.0, 0.0), (0.0, 300.0)], 70.0)],
                                      wrg_paths=[self.pud_wrg], fixed_ti=0.1, energy_ws_step=1.0,
                                      wrg_direction_count=1, compute_variants=False,
                                      wake_physics=api.to_wake_physics(self.config), power_bin_mode=mode)

    def test_the_whole_grid_again(self):
        for mode, aep in ((BIN_MEAN, 8294.05867113277), (POINT, 8296.270321899652)):
            with self.subTest(mode=mode):
                r = self.compute_pud(mode)
                with mock.patch.object(zero_node, "plan", return_value=zero_node.ORDINARY):
                    o = self.compute_pud(mode)
                self.assertEqual(r["aep_wake_MWh"], aep)  # Astra's 8.29405867113277 GWh with the bin mean
                same_bits(self, comparable(r), comparable(o))
                self.assertEqual(r["convergence"], o["convergence"])
                self.assertNotIn("executed_ws", r)
                self.assertTrue(any("con la malla sin 0 m/s PyWake da un error: ValueError: zero-size array" in str(w)
                                    for w in r["edge_cases"]["warnings"]))


class DiagnosisTest(_AepCase):
    """Decisions 2 and 5: the protected diagnosis of each simulation; the new fields only in the edge cases."""

    def test_an_ordinary_result_has_no_new_field(self):
        r = self.compute(LINEAR)
        self.assertNotIn("edge_cases", r)
        self.assertNotIn("executed_ws", r)
        self.assertNotIn("auxiliary_zero", r["convergence"])

    def test_a_failed_diagnosis_changes_nothing(self):
        o = self.compute(LINEAR, wrg=self.empty_wrg)
        with mock.patch.object(ec, "simulation_diagnosis", side_effect=RuntimeError("roto")):
            r = self.compute(LINEAR, wrg=self.empty_wrg)
        same_bits(self, comparable(r), comparable(o))
        self.assertEqual(r["convergence"], o["convergence"])
        def notes(res):  # the notes of the calculation; those of the edge cases are its warnings (P3)
            edge = [str(w) for w in (res.get("edge_cases") or {}).get("warnings") or []]
            return [str(n) for n in res["simulation_notes"] if str(n) not in edge]
        self.assertEqual(notes(r), notes(o))
        self.assertTrue(all(str(w) == "Aviso no disponible: RuntimeError: roto" for w in r["edge_cases"]["warnings"]
                            if not str(w).startswith("TI efectiva")))  # the reason of the TI (P5), not a diagnosis
        self.assertEqual(r["edge_cases"]["diagnoses"], {})

    def test_a_diagnosis_that_writes_and_raises_changes_nothing(self):
        """Its inputs are read-only (a write raises), and it runs after the last reduction of each simulation: even
        one that changes the simulation before raising cannot change the result (Astra, P2 r1)."""
        o = self.compute(LINEAR, wrg=self.empty_wrg)
        attempts = []

        def writes(**kwargs):
            for key in ("directions", "sector_centers", "aep", "p"):
                try:
                    kwargs[key][...] = 123.0
                    attempts.append((key, "written"))
                except ValueError:
                    attempts.append((key, "refused"))
            raise RuntimeError("diagnóstico roto")
        real = aep_arrays.edge_case_arrays

        def spoils(sim, hours):
            arrays = real(sim, hours)
            sim["Power"].values[...] = 0.0  # a diagnosis that changes the simulation itself
            return arrays
        with mock.patch.object(ec, "simulation_diagnosis", side_effect=writes), \
                mock.patch.object(aep_arrays, "edge_case_arrays", side_effect=spoils):
            r = self.compute(LINEAR, wrg=self.empty_wrg)
        self.assertTrue(attempts)
        self.assertEqual({a for _k, a in attempts}, {"refused"})
        same_bits(self, comparable(r), comparable(o))
        self.assertTrue(all("diagnóstico roto" in str(w) for w in r["edge_cases"]["warnings"]
                            if not str(w).startswith("TI efectiva")))  # the reason of the TI (P5), not a diagnosis

    def test_a_failed_text_of_the_warnings_does_not_stop_the_calculation(self):
        from VelantisWind.ag_core.wake_setup import notices
        o = self.compute(LINEAR)
        with mock.patch.object(notices, "persistent_warnings", side_effect=RuntimeError("texto roto")):
            r = self.compute(LINEAR)
        same_bits(self, comparable(r), comparable(o))
        self.assertEqual([str(w) for w in r["edge_cases"]["warnings"]], ["Aviso no disponible: RuntimeError: texto roto"])

        def spoils(config, **_kwargs):  # a text that changes the configuration it reads, then fails (Astra, P2 r2)
            config.deficit.params["k"] = 0.2
            raise RuntimeError("texto roto")
        with mock.patch.object(notices, "persistent_warnings", side_effect=spoils):
            r = self.compute(LINEAR)
        same_bits(self, comparable(r), comparable(o))
        self.assertEqual(LINEAR.deficit.params["k"], 0.0324555)

    def test_a_failed_plan_of_the_exception_does_not_change_the_calculation(self):
        """A predicate that changes the arguments it reads, then fails: the ordinary calculation, with the arguments
        of always (Astra, P2 r2)."""
        from VelantisWind.ag_core.simulation import zero_node as zn
        from VelantisWind.ag_core.wake_setup import factory
        built = []
        real = factory.build_wind_farm_model

        def spy(target, *args, **kwargs):
            built.append(copy.deepcopy(target.superposition.params))
            return real(target, *args, **kwargs)
        with mock.patch.object(factory, "build_wind_farm_model", side_effect=spy):
            o = self.ordinary(WS)
        expected, built[:] = list(built), []

        def spoils(params):
            params["max_iter"] = 1
            raise RuntimeError("predicado roto")
        with mock.patch.object(zn, "weighting_discarded", side_effect=spoils), \
                mock.patch.object(factory, "build_wind_farm_model", side_effect=spy):
            r = self.compute(WS)
        self.assertEqual(built, expected)  # every model with the arguments of always
        same_bits(self, comparable(r), comparable(o))
        self.assertNotIn("executed_ws", r)
        self.assertTrue(any("predicado roto" in str(w) for w in r["edge_cases"]["warnings"]))

    def test_the_arrays_of_the_simulations_are_not_changed(self):
        """Reading the arrays of a simulation (``aep()`` and ``broadcast_like``, the same ``aep()`` the calculation
        calls before the next simulation) changes nothing: neither the simulation, nor the site and the turbines its
        model shares with the simulations that follow (Astra, P2 r2)."""
        import pickle
        seen = []
        real = aep_arrays.edge_case_arrays

        def shared(sim):
            sims = [sim.rest, sim.small] if isinstance(sim, zero_node.Joined) else [sim]
            return [({name: v.values.tobytes() for name, v in s.windFarmModel.site.ds.data_vars.items()},
                     pickle.dumps(s.windFarmModel.windTurbines)) for s in sims]

        def spy(sim, hours):  # inside the protection of the diagnosis: it records, the test asserts
            before = shared(sim)
            arrays = real(sim, hours)
            seen.append((sim, {k: None if v is None else v.copy() for k, v in arrays.items()}, before, shared(sim)))
            return arrays
        for config in (LINEAR, WS):
            with mock.patch.object(aep_arrays, "edge_case_arrays", side_effect=spy):
                self.compute(config, wrg=self.empty_wrg)
        self.assertTrue(any(isinstance(s, zero_node.Joined) for s, *_ in seen))
        for sim, before, shared_before, shared_after in seen:
            self.assertEqual(shared_after, shared_before)
            after = real(sim, HOURS)
            for key, values in before.items():
                if values is not None:
                    self.assertEqual(after[key].tobytes(), values.tobytes(), key)

    def test_the_diagnosis_of_the_small_simulation_reads_its_0_slice_only(self):
        """Its node of one step may have negatives that do not exist in the calculation (Astra, round 5)."""
        import xarray as xr

        class Sim:
            def __init__(self, ws, ws_eff):
                dims = ("wt", "wd", "ws")
                coords = {"wt": [0, 1], "wd": [0.0, 90.0], "ws": ws}
                shape = (2, 2, len(ws))
                self.ds = xr.Dataset({"WS_eff": (dims, np.broadcast_to(ws_eff, shape).copy()),
                                      "P": (("wd", "ws"), np.full((2, len(ws)), 0.1)),
                                      "Power": (dims, np.ones(shape))}, coords=coords)

            def aep(self, **kwargs):
                return self.ds["Power"] * self.ds["P"]

            def __getitem__(self, key):
                return self.ds[key]

            def __contains__(self, key):
                return key in self.ds

        rest = Sim([1.0, 2.0, 3.0], np.array([1.0, 2.0, 3.0]))
        small = Sim([0.0, 1.0], np.array([0.0, -2.0]))  # a negative at its node of one step
        joined = zero_node.Joined(rest, small, lambda exc: None)
        arrays = aep_arrays.edge_case_arrays(joined, HOURS)
        np.testing.assert_array_equal(arrays["ws_eff"][0, 0], [0.0, 1.0, 2.0, 3.0])
        self.assertIsNone(ec.simulation_diagnosis(**arrays))
        small.ds["WS_eff"][..., 0] = -0.5  # at 0 m/s it is said
        self.assertEqual(ec.simulation_diagnosis(**aep_arrays.edge_case_arrays(joined, HOURS))["ws_eff"]["negative"], 4)

    def test_an_empty_sector_leaves_every_total_finite(self):
        r = self.compute(LINEAR, wrg=self.empty_wrg)
        diag = r["edge_cases"]["diagnoses"]["A_WTB"]
        self.assertGreater(diag["p"]["nan"], 0)  # the non-finite P does appear (0 m/s in the empty sector)
        self.assertEqual((diag["aep"]["group2"], diag["aep"]["partial_turbines"]), (0, []))
        self.assertGreater(diag["aep"]["group1"], 0)
        for row in r["per_turbine_table"]:
            self.assertTrue(np.isfinite(row["aep_mwh"]) and np.isfinite(row["aep_free_mwh"]))
        self.assertTrue(np.isfinite(r["aep_wake_MWh"]))
        self.assertTrue(all(np.isfinite(v) for v in r["aep_per_wd_wake_MWh"]))
        self.assertEqual(set(r["edge_cases"]["diagnoses"]), {"A_WTB", "A_0", "A_W"})

    def test_a_non_finite_ws_eff_with_a_finite_aep_is_counted(self):
        """A2A with blockage and ss_gamma = −inf (Astra, round 8): WS_eff = +inf, power 0, a finite AEP."""
        config = physics(engine="All2AllIterative", blockage=cfg.Component("SelfSimilarityDeficit", {"ss_gamma": -INF}),
                         blockage_superposition=cfg.Component("LinearSum", {}))
        r = self.compute(config, compute_variants=False)
        speeds = r["edge_cases"]["diagnoses"]["A_WTB"]["ws_eff"]
        self.assertGreater(speeds["+inf"] + speeds["nan"], 0)
        self.assertTrue(np.isfinite(r["aep_wake_MWh"]))

    def test_the_warnings_of_the_arguments_are_given_once_before_simulating(self):
        config = physics(superposition="WeightedSum", sup_params={"max_iter": 0})
        events = []
        real = runner.simulate

        def spy(*args, **kwargs):
            events.append("simulate")
            return real(*args, **kwargs)
        with mock.patch.object(runner, "simulate", side_effect=spy), \
                mock.patch.object(ac, "_log", side_effect=lambda msg, *a: events.append(str(msg))):
            r = self.compute(config, compute_variants=False)
        warning = next(str(w) for w in r["persistent_warnings"] if "max_iter" in str(w))
        self.assertEqual(events.count(warning), 1)
        self.assertLess(events.index(warning), events.index("simulate"))


class RasterSpeedTest(unittest.TestCase):
    """Decision 7: the raster at the speed asked for, also under 0.1 m/s."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.wrg = write_wrg(cls.folder.name, 90, "full.wrg", empty_sector=False)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def raster(self, ws):
        from VelantisWind.wake_core import raster as wake_raster
        out = os.path.join(self.folder.name, f"ws_{ws}")
        return wake_raster.compute_wake_raster_config(
            [model(manual(), LAYOUT, 90.0)], wake_config=physics(), wrg_paths=[self.wrg], fixed_ti=0.1,
            resolution_m=250.0, ws_plot=ws, wd_target=270.0, output_dir=out, crs_authid="EPSG:32630")

    def test_the_speed_asked_for(self):
        for ws in (0.05, -1.0, 2e-9):
            with self.subTest(ws=ws):
                r = self.raster(ws)
                self.assertEqual(r["ws"], ws)
                entry = next(e for e in r["rasters"] if e["variable"] == "WS")
                self.assertAlmostEqual(entry["mean"], ws, delta=abs(ws) * 1e-6)

    def test_the_relative_deficit_is_nodata_only_where_the_free_speed_is_null(self):
        from VelantisWind.ag_core.qgis_io import wake_raster as exporter
        ws_free = np.array([[0.0, 1e-9, -1e-9, 2e-9], [-2e-9, 0.05, -1.0, 10.0]])
        flow = types.SimpleNamespace()
        captured = {}

        def extract(_flow, names, label):
            return ({"WS_eff": ws_free * 0.5, "WS": ws_free}[label], np.arange(4.0) * 100, np.arange(2.0) * 100)

        def write(path, values, *args, **kwargs):
            captured[os.path.basename(path)] = np.array(values)
            open(path, "wb").close()
            finite = values[np.isfinite(values)]
            return float(finite.min()), float(finite.max())
        with mock.patch.object(exporter, "_extract_field_2d", side_effect=extract), \
                mock.patch.object(exporter, "_write_geotiff", side_effect=write), \
                mock.patch.object(exporter, "_write_metadata_sidecar", return_value="x.json"):
            exporter.build_wake_raster_file(flow, wd=270.0, ws=1.0, output_dir=self.folder.name)
        pct = list(captured.values())[3]  # WS, WS_eff, wake_deficit, wake_deficit_pct (build_wake_raster_file)
        self.assertEqual(np.isnan(pct).tolist(), (np.abs(ws_free) <= 1e-9).tolist())


class WeightedSumPredicateTest(unittest.TestCase):
    """Decision 9: where the predicate says the weighting is discarded, WeightedSum gives LinearSum to the bit, also
    with the speeds that are not dyadic of a site with speed-ups."""

    def test_discarded_is_linear_to_the_bit(self):
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        from py_wake.deficit_models import BastankhahGaussianDeficit
        from py_wake.examples.data.ParqueFicticio import ParqueFicticioSite
        from py_wake.examples.data.hornsrev1 import V80
        from py_wake.superposition_models import LinearSum, WeightedSum
        from py_wake.wind_farm_models import PropagateDownwind
        site = ParqueFicticioSite()
        x, y = site.initial_position[:4].T
        ws = np.arange(3.3, 13.0, 1.7)

        def run(sup):
            return PropagateDownwind(site, V80(), BastankhahGaussianDeficit(), superpositionModel=sup)(
                x, y, wd=[0.0, 90.0, 270.0], ws=ws).WS_eff.values
        linear = run(LinearSum())
        for params in ({"max_iter": 0}, {"max_iter": NAN}, {"max_err": NAN}, {"max_err": 1.0}, {"max_err": INF},
                       {"delta": NAN}, {"weight_limit": NAN}):
            with self.subTest(params=params):
                self.assertIsNotNone(ec.weighting_discarded(params))
                self.assertEqual(run(WeightedSum(**params)).tobytes(), linear.tobytes())
        self.assertIsNone(ec.weighting_discarded({}))
        self.assertNotEqual(run(WeightedSum()).tobytes(), linear.tobytes())  # it does weigh here


if __name__ == "__main__":
    unittest.main()
