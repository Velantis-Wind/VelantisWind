# -*- coding: utf-8 -*-
"""The warnings of the arguments of WeightedSum and the reasons of the effective TI (#63, P5, decisions 8 and 9):
«no pondera» and «puede no terminar», with their precedence and without duplicating the warnings that already
exist, in the dialog and in the result; once in the log, before the first simulation; the warning of the tiles of the
raster with the predicate; and every cause of an effective TI that is not a value, with its precedence."""
import math
import os
import tempfile
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core import aep_compute as ac
from VelantisWind.ag_core import edge_cases as ec
from VelantisWind.ag_core.simulation import runner
from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import notices
from VelantisWind.wake_core import engine as wake_engine
from VelantisWind.wake_core import raster as wake_raster
from tests.test_edge_cases_calculation import LAYOUT, _AepCase, physics
from tests.test_zero_node import manual, model, write_wrg

NAN, INF = math.nan, math.inf


def ws_warnings(params):
    """The texts of the warnings of WeightedSum's arguments in the dialog (``argument_warnings``)."""
    config = physics(superposition="WeightedSum", sup_params=params)
    return [str(w) for w in notices.argument_warnings(config).get(cat.SUPERPOSITION, [])]


class ArgumentWarningsTest(unittest.TestCase):
    def test_not_weighing_in_each_case_of_the_predicate(self):
        for params, arg in (({"max_iter": 0}, "max_iter"), ({"max_iter": -INF}, "max_iter"), ({"max_iter": NAN}, "max_iter"),
                            ({"max_err": NAN}, "max_err"), ({"max_err": 1.0}, "max_err"), ({"max_err": INF}, "max_err"),
                            ({"delta": NAN}, "delta"), ({"weight_limit": NAN}, "weight_limit")):
            with self.subTest(params=params):
                texts = ws_warnings(params)
                self.assertEqual([t for t in texts if "no pondera" in t],
                                 [f"En «superposición de estelas · WeightedSum», con {arg} = {params[arg]}, WeightedSum no pondera: "
                                  "suma las estelas linealmente."])
                self.assertFalse(any("iterará hasta max_iter" in t or "no itera" in t for t in texts))

    def test_it_may_not_end(self):
        for params in ({"max_err": 1e-13}, {"max_err": 0.0}, {"max_err": -1.0}, {"max_iter": INF}):
            with self.subTest(params=params):
                texts = ws_warnings(params)
                self.assertEqual(sum("iterará hasta max_iter" in t for t in texts), 1)
                self.assertFalse(any("no pondera" in t for t in texts))
        self.assertTrue(any("su nodo no se calcula aparte" in t for t in ws_warnings({"max_iter": INF})))
        self.assertFalse(any("su nodo no se calcula aparte" in t for t in ws_warnings({"max_err": 0.0})))

    def test_the_precedence(self):
        """The weighting discarded suppresses the warnings of its iteration and of its weights; not delta's."""
        texts = ws_warnings({"max_iter": 0, "max_err": 0.0, "weight_limit": -1.0, "delta": -1.0})
        self.assertEqual(len(texts), 2)
        self.assertTrue(any("no pondera" in t for t in texts) and any("delta = -1.0" in t for t in texts))
        texts = ws_warnings({"weight_limit": -1.0})
        self.assertTrue(any("weight_limit = -1.0" in t for t in texts))
        self.assertEqual(ws_warnings({}), [])

    def test_delta_inf_still_weighs(self):
        """Its threshold is delta·WS of the speeds WeightedSum receives, which can be negative (decision 9): PyWake's
        WeightedSum with delta = +inf weighs a negative speed and adds a positive one linearly. With PUD and blockage
        the propagation receives WS minus the deficit of the blockage, negative in Astra's case (round 7): there is no
        «no pondera» for it either."""
        self.assertIsNone(ec.weighting_discarded({"delta": INF}))
        self.assertEqual(ws_warnings({"delta": INF}), [])
        from py_wake.superposition_models import WeightedSum
        ones, zeros = np.ones((2, 1)), np.zeros((2, 1))

        def summed(ws):
            with np.errstate(invalid="ignore"):
                return float(np.ravel(WeightedSum(delta=INF)(
                    deficit_jxxx=ones, WS_xxx=np.array([ws]), convection_velocity_jxxx=np.array([[2.0], [4.0]]),
                    sigma_sqr_jxxx=ones, cw_jxxx=zeros, hcw_jxxx=zeros, dh_jxxx=zeros, deficit_centre_jxxx=ones))[0])
        self.assertEqual(summed(5.0), 2.0)  # the linear sum of the two deficits
        self.assertNotEqual(summed(-5.0), 2.0)  # weighed
        config = physics(engine="PropagateUpDownIterative", superposition="WeightedSum", sup_params={"delta": INF},
                         blockage=cfg.Component("SelfSimilarityDeficit", {}),
                         blockage_superposition=cfg.Component("LinearSum", {}))
        texts = [str(w) for ws in notices.argument_warnings(config).values() for w in ws]
        self.assertFalse(any("no pondera" in t for t in texts))


class CalculationTest(_AepCase):
    def test_each_case_in_the_result_and_once_in_the_log_before_simulating(self):
        """Every case of decision 9 that a calculation ends (``max_iter = +inf``, below, with the simulation
        substituted), with the real simulation (Sol, P5 r1)."""
        cases = [({"max_iter": 0}, "no pondera"), ({"max_iter": NAN}, "no pondera"), ({"max_err": NAN}, "no pondera"),
                 ({"max_err": 1.0}, "no pondera"), ({"max_err": INF}, "no pondera"), ({"delta": NAN}, "no pondera"),
                 ({"weight_limit": NAN}, "no pondera"), ({"max_err": 0.0, "max_iter": 3}, "iterará hasta max_iter"),
                 ({"max_err": 1e-13, "max_iter": 3}, "iterará hasta max_iter")]
        real = runner.simulate
        for params, piece in cases:
            with self.subTest(params=params):
                events = []

                def spy(*args, **kwargs):
                    events.append("simulate")
                    return real(*args, **kwargs)
                with mock.patch.object(runner, "simulate", side_effect=spy), \
                        mock.patch.object(ac, "_log", side_effect=lambda msg, *a: events.append(str(msg))):
                    r = self.compute(physics(superposition="WeightedSum", sup_params=params), compute_variants=False)
                texts = [str(w) for w in r["persistent_warnings"] if piece in str(w)]
                self.assertEqual(len(texts), 1)
                self.assertEqual(events.count(texts[0]), 1)
                self.assertLess(events.index(texts[0]), events.index("simulate"))

    def test_in_the_result_and_once_in_the_log_before_simulating(self):
        events = []
        real = runner.simulate

        def spy(*args, **kwargs):
            events.append("simulate")
            return real(*args, **kwargs)
        with mock.patch.object(runner, "simulate", side_effect=spy), \
                mock.patch.object(ac, "_log", side_effect=lambda msg, *a: events.append(str(msg))):
            r = self.compute(physics(superposition="WeightedSum", sup_params={"max_iter": 0}), compute_variants=False)
        texts = [str(w) for w in r["persistent_warnings"]]
        warning = next(t for t in texts if "no pondera" in t)
        self.assertEqual(events.count(warning), 1)
        self.assertLess(events.index(warning), events.index("simulate"))
        self.assertFalse(any("iterará" in t for t in texts))

    def test_pud_with_blockage_and_delta_inf_weighs(self):
        """PUD with blockage hands WeightedSum speeds below 0 (WS minus the deficit of the blockage), so delta = +inf
        does not discard its weighting: the calls that receive a negative speed weigh, and the result has no «no
        pondera» (decision 9; Astra, round 7, measured it with real data; Sol, P5 r2)."""
        from py_wake.superposition_models import WeightedSum
        from VelantisWind.ag_core.turbine import build_wt_from_manual
        from VelantisWind.ag_core.wake_setup import api
        lines = ["3 3 -500 -500 500"] + [f"{-500 + 500 * ix} {-500 + 500 * iy} 0 70 8.0 2.0 300 1 1000 80 200"
                                         for iy in range(3) for ix in range(3)]
        wrg = os.path.join(self.folder.name, "pud_delta.wrg")
        with open(wrg, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        base = cfg.default_config("PropagateUpDownIterative", "BastankhahGaussianDeficit")
        config = cfg.WakeConfig(**{
            **base.__dict__,
            "deficit": cfg.Component("BastankhahGaussianDeficit", {**base.deficit.params, "use_effective_ws": True}),
            "superposition": cfg.Component("WeightedSum", {"delta": INF, "max_iter": 20}),
            "blockage": cfg.Component("SelfSimilarityDeficit", {"ss_gamma": 100, "use_effective_ws": True,
                                                                "exclude_wake": False}),
            "blockage_superposition": cfg.Component("LinearSum", {})})
        calls = []
        real = WeightedSum.__call__

        def spy(self_, deficit_jxxx, WS_xxx, *args, **kwargs):
            out = real(self_, deficit_jxxx, WS_xxx, *args, **kwargs)
            calls.append((float(np.min(WS_xxx)), not np.array_equal(out, np.sum(deficit_jxxx, 0))))
            return out
        wt = build_wt_from_manual("T", 80.0, 70.0, [0, 1, 4, 12, 25], [1, 50, 300, 2000, 2000], [0.8] * 5)
        layout = [(x, y) for x in (-250.0, 0.0, 250.0) for y in (-300.0, 0.0, 300.0)]
        with mock.patch.object(WeightedSum, "__call__", spy), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # PyWake's inf·0 in its threshold
            r = ac.compute_aep_from_ui("", [model(wt, layout, 70.0)], wrg_paths=[wrg], fixed_ti=0.1,
                                       energy_ws_step=1.0, wrg_direction_count=12, compute_variants=False,
                                       wake_physics=api.to_wake_physics(config))
        weighed = [ws for ws, differs in calls if differs]
        self.assertTrue(weighed)
        self.assertTrue(all(ws < 0 for ws in weighed))
        self.assertFalse(any("no pondera" in str(w) for w in r["persistent_warnings"]))

    def test_max_iter_inf_is_said_before_simulating(self):
        """With the simulation substituted: no loop runs (it would iterate without end)."""
        events = []

        def stop(*_args, **_kwargs):
            events.append("simulate")
            raise RuntimeError("simulación sustituida")
        with mock.patch.object(runner, "simulate", side_effect=stop), \
                mock.patch.object(ac, "_log", side_effect=lambda msg, *a: events.append(str(msg))):
            with self.assertRaises(RuntimeError):
                self.compute(physics(superposition="WeightedSum", sup_params={"max_iter": INF}), compute_variants=False)
        ending = [e for e in events if "iterará hasta max_iter" in e]
        not_applied = [e for e in events if "no aplicada" in e and "max_iter = +inf" in e]
        self.assertEqual((len(ending), len(not_applied)), (1, 1))
        first = events.index("simulate")
        self.assertLess(events.index(ending[0]), first)
        self.assertLess(events.index(not_applied[0]), first)


class RasterTilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        cls.folder = tempfile.TemporaryDirectory()
        cls.wrg = write_wrg(cls.folder.name, 90, "full.wrg", empty_sector=False)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def raster(self, params, name):
        real = wake_engine._tiled_flow_map

        def two_tiles(*args, after_tile=None, **kwargs):  # as a map in two tiles
            out = real(*args, after_tile=after_tile, **kwargs)
            after_tile(2, 2)
            return out
        with mock.patch.object(wake_engine, "_tiled_flow_map", side_effect=two_tiles):
            return wake_raster.compute_wake_raster_config(
                [model(manual(), LAYOUT, 90.0)], wake_config=physics(superposition="WeightedSum", sup_params=params),
                wrg_paths=[self.wrg], fixed_ti=0.1, resolution_m=250.0, ws_plot=10.0, wd_target=270.0,
                output_dir=os.path.join(self.folder.name, name), crs_authid="EPSG:32630")

    def test_the_warning_of_the_tiles_uses_the_predicate(self):
        self.assertTrue(any("teselas" in w for w in self.raster({}, "weighs")["warnings"]))
        for params in ({"max_err": 1.0}, {"delta": NAN}, {"max_iter": 0}):
            with self.subTest(params=params):
                self.assertFalse(any("teselas" in w for w in self.raster(params, str(params))["warnings"]))


class TiReasonsTest(unittest.TestCase):
    """Decision 8: every cause, with its precedence; the value kept stays None."""

    def test_each_cause(self):
        ti = np.array([[0.1, 0.1], [INF, NAN], [NAN, 0.1], [0.1, 0.1], [0.1, 0.1], [0.1, 0.1]])
        p = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [NAN, 0.5], [0.0, 0.0], [1e308, 1e308]])
        values = np.array([0.1, NAN, NAN, NAN, NAN, NAN])
        self.assertEqual(ec.ti_reasons(ti, p, values, 6),
                         {2: "infinite", 3: "nan", 4: "nan_weight", 5: "zero_weight", 6: "reduction"})
        self.assertEqual(ec.ti_reasons(None, p, values, 2), {1: "unavailable", 2: "unavailable"})
        self.assertIsNone(ec.ti_reasons(ti[:1], p[:1], values[:1], 1))


class TiResultTest(_AepCase):
    def test_the_reason_is_in_the_result_and_the_value_does_not_change(self):
        """An empty sector at 0 m/s: P NaN there, and the effective TI is NaN by its weighting."""
        r = self.compute(physics(), wrg=self.empty_wrg, compute_variants=False)
        self.assertEqual(set(r["ti_effective_reasons"].values()), {"nan_weight"})
        for row in r["per_turbine_table"]:
            self.assertIsNone(row["ti_effective"])
            self.assertEqual(row["ti_effective_reason"], ec.TI_REASON_TEXTS["nan_weight"])
        warning = next(w for w in r["edge_cases"]["warnings"] if str(w).startswith("TI efectiva NaN por ponderación"))
        self.assertEqual(sum(str(w) == str(warning) for w in r["edge_cases"]["warnings"]), 1)
        self.assertIn(warning, r["simulation_notes"])  # in every output, the notes too (Sol, P5 r1)
        ordinary = self.compute(physics(), compute_variants=False)
        self.assertNotIn("ti_effective_reasons", ordinary)
        self.assertFalse(any("ti_effective_reason" in row for row in ordinary["per_turbine_table"]))


if __name__ == "__main__":
    unittest.main()
