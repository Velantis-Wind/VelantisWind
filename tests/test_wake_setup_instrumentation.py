# -*- coding: utf-8 -*-
"""Convergence instrumentation and effective TI of a simulation (``ag_core/wake_setup/instrumentation.py``, #46 P1c)."""
import sys
import unittest
import warnings
from unittest import mock

import numpy as np
import xarray as xr

from VelantisWind.ag_core.wake_setup import instrumentation as ins

warnings.filterwarnings("ignore", module="py_wake")

from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit, NiayifarGaussianDeficit  # noqa: E402
from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020  # noqa: E402
from py_wake.examples.data.hornsrev1 import Hornsrev1Site, V80, wt_x, wt_y  # noqa: E402
from py_wake.superposition_models import WeightedSum  # noqa: E402
from py_wake.turbulence_models import STF2017TurbulenceModel  # noqa: E402
from py_wake.wind_farm_models import All2AllIterative, PropagateDownwind, PropagateUpDownIterative  # noqa: E402

SITE, WT = Hornsrev1Site(), V80()
WD, WS = [0.0, 90.0, 270.0], [8.0, 10.0]


def aep(make, record=False):
    if not record:
        return make()(wt_x, wt_y, wd=WD, ws=WS).aep().values, None
    with ins.ConvergenceRecorder() as rec:
        values = make()(wt_x, wt_y, wd=WD, ws=WS).aep().values
    return values, rec.summary()


class WeightedSumTest(unittest.TestCase):
    def test_reached_max_iter_without_changing_the_result(self):
        make = lambda: PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(), superpositionModel=WeightedSum(max_iter=2))  # noqa: E731
        plain, _ = aep(make)
        recorded, summary = aep(make, record=True)
        self.assertTrue(np.array_equal(plain, recorded))
        s = summary["WeightedSum"]
        self.assertFalse(s["converged"])
        self.assertGreater(s["states"]["max_iter"], 0)
        self.assertGreater(s["max_error"], 1e-3)

    def test_converged_with_the_signature_values(self):
        make = lambda: PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(), superpositionModel=WeightedSum(max_iter=50))  # noqa: E731
        _, summary = aep(make, record=True)
        self.assertTrue(summary["WeightedSum"]["converged"])

    def test_stopped_without_meeting_the_tolerance_is_not_max_iter(self):
        # A non-finite convection velocity: the while condition is False with a NaN error before max_iter.
        ws = WeightedSum()
        shape = (2, 1, 1, 1)
        kwargs = dict(deficit_jxxx=np.full(shape, 1.0), WS_xxx=np.full(shape[1:], 10.0),
                      convection_velocity_jxxx=np.array([np.nan, 5.0]).reshape(shape),
                      sigma_sqr_jxxx=np.full(shape, 1.0), cw_jxxx=np.zeros(shape), hcw_jxxx=np.zeros(shape),
                      dh_jxxx=np.zeros(shape), deficit_centre_jxxx=np.full(shape, 2.0))
        plain = ws(**kwargs)
        with ins.ConvergenceRecorder() as rec:
            recorded = ws(**kwargs)
        self.assertTrue(np.array_equal(plain, recorded, equal_nan=True))
        (record,) = rec.records["WeightedSum"]
        self.assertEqual(record["state"], "tolerance_not_met")
        self.assertLess(record["iterations"], ws.max_iter)


class EngineTest(unittest.TestCase):
    def test_all2all_converged_not_converged_and_no_check(self):
        # A negative tolerance is never met: the loop ends after its max(I, 20) iterations with PyWake's warning.
        cases = {"converged": 1e-6, "not_converged": -1.0, "no_check": None}
        for state, tol in cases.items():
            with self.subTest(state=state):
                make = lambda: All2AllIterative(SITE, WT, BastankhahGaussianDeficit(),  # noqa: E731
                                                blockage_deficitModel=SelfSimilarityDeficit2020(), convergence_tolerance=tol)
                plain, _ = aep(make)
                recorded, summary = aep(make, record=True)
                self.assertTrue(np.array_equal(plain, recorded))
                self.assertEqual(summary["All2AllIterative"]["states"], {state: 1})
                # Only «converged» is a convergence; without a check it is not claimed.
                self.assertEqual(summary["All2AllIterative"]["converged"], state == "converged")
        self.assertEqual(aep(lambda: All2AllIterative(SITE, WT, BastankhahGaussianDeficit(), convergence_tolerance=None),
                             record=True)[1]["All2AllIterative"]["iterations"], 1)

    def test_propagate_up_down_max_iter_and_the_cases_out_of_its_mask(self):
        make = lambda: PropagateUpDownIterative(  # noqa: E731
            SITE, WT, BastankhahGaussianDeficit(use_effective_ws=True),
            blockage_deficitModel=SelfSimilarityDeficit2020(use_effective_ws=True), max_iter=2)
        plain, _ = aep(make)
        recorded, summary = aep(make, record=True)
        self.assertTrue(np.array_equal(plain, recorded))
        s = summary["PropagateUpDownIterative"]
        self.assertEqual(s["states"], {"max_iter": 1})
        self.assertGreater(s["excluded_cases"], 0)
        self.assertGreater(s["excluded_max_residual"], 0)

    def test_a_max_iter_with_decimals_is_recorded_as_given(self):
        # PyWake compares it with its counter: 2.5 makes three passes (#64 lets it be edited, never rounded).
        for make, loop in ((lambda: PropagateUpDownIterative(
                SITE, WT, BastankhahGaussianDeficit(use_effective_ws=True), convergence_tolerance=0,
                blockage_deficitModel=SelfSimilarityDeficit2020(use_effective_ws=True), max_iter=2.5),
                "PropagateUpDownIterative"),
                (lambda: PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(),
                                           superpositionModel=WeightedSum(max_iter=2.5, max_err=0)), "WeightedSum")):
            with self.subTest(loop=loop):
                with ins.ConvergenceRecorder() as rec:
                    make()(np.array([0.0, 400.0, 800.0]), np.array([0.0, 0.0, 0.0]), wd=[270.0], ws=[10.0])
                records = [r for r in rec.records[loop] if "max_iter" in r]  # those that iterated
                self.assertTrue(records)
                self.assertTrue(all(r["max_iter"] == 2.5 for r in records))
                self.assertTrue(any(r["iterations"] == 3 for r in records))

    def test_propagate_up_down_converged_only_on_its_mask(self):
        # The tolerance is met by the cases the mask keeps while an excluded one has a larger residual.
        loc = {"self": mock.Mock(convergence_tolerance=1e-6, max_iter=10), "j": 3, "max_diff": 1e-7,
               "iconverging": np.array([True, False]), "diff_ilk": np.array([1e-7, 1e-3])}
        record = ins._propagate_up_down(loc)
        self.assertEqual(record["state"], "converged_on_mask")
        self.assertEqual(record["excluded_max_residual"], 1e-3)
        rec = ins.ConvergenceRecorder()
        rec.records["PropagateUpDownIterative"].append(record)
        self.assertFalse(rec.summary()["PropagateUpDownIterative"]["converged"])
        loc["diff_ilk"] = np.array([1e-7, 1e-8])
        self.assertEqual(ins._propagate_up_down(loc)["state"], "converged")

    def test_propagate_up_down_exhausts_its_loop(self):
        # Two turbines: the loop has at most two iterations, fewer than max_iter.
        wfm = PropagateUpDownIterative(SITE, WT, BastankhahGaussianDeficit(use_effective_ws=True),
                                       blockage_deficitModel=SelfSimilarityDeficit2020(use_effective_ws=True),
                                       convergence_tolerance=1e-300, max_iter=10)
        with ins.ConvergenceRecorder() as rec:
            wfm([0, 300], [0, 0], wd=[270], ws=[10])
        self.assertEqual(rec.summary()["PropagateUpDownIterative"]["states"], {"loop_exhausted": 1})

    def test_a_reader_failure_is_unavailable_never_converged(self):
        with mock.patch.dict(ins._READERS, {"All2AllIterative": mock.Mock(side_effect=KeyError("j"))}):
            _, summary = aep(lambda: All2AllIterative(SITE, WT, BastankhahGaussianDeficit()), record=True)
        self.assertEqual(summary["All2AllIterative"]["states"], {ins.UNAVAILABLE: 1})
        self.assertFalse(summary["All2AllIterative"]["converged"])

    def test_an_unavailable_state_is_said_with_its_cause_never_as_not_converged(self):
        # Decision 6.5 of #64: in the warnings of the result and in its report.
        from VelantisWind.ag_core.results.model_config_html import model_config_html
        from VelantisWind.ag_core.wake_setup.notices import convergence_warnings
        with mock.patch.dict(ins._READERS, {"All2AllIterative": mock.Mock(side_effect=KeyError("j"))}):
            _, summary = aep(lambda: All2AllIterative(SITE, WT, BastankhahGaussianDeficit()), record=True)
        self.assertEqual(summary["All2AllIterative"]["unavailable_reasons"], ["KeyError: 'j'"])
        texts = [str(w) for w in convergence_warnings(summary)]
        self.assertEqual(texts, ["Convergencia de All2AllIterative: no disponible en 1 de 1 (KeyError: 'j')."])
        html = model_config_html({"wake_config": {"selected": {}, "executed": {}}, "convergence": {"main": summary}})
        self.assertIn("convergencia de All2AllIterative no disponible en 1 de 1 (KeyError: &#x27;j&#x27;)", html)
        self.assertNotIn("no convergió", html)

    def test_read_and_unread_calls_of_one_loop_are_said_apart(self):
        from VelantisWind.ag_core.results.model_config_html import model_config_html
        from VelantisWind.ag_core.wake_setup.notices import convergence_warnings
        entry = {"calls": 2, "converged": False, "states": {ins.UNAVAILABLE: 1, "max_iter": 1},
                 "unavailable_reasons": ["KeyError: 'j'"]}
        self.assertEqual([str(w) for w in convergence_warnings({"PropagateUpDownIterative": entry})],
                         ["Convergencia de PropagateUpDownIterative: no disponible en 1 de 2 (KeyError: 'j').",
                          "Convergencia de PropagateUpDownIterative: max_iter × 1. El resultado se conserva, pero no "
                          "es un cálculo convergido."])
        html = model_config_html({"wake_config": {"selected": {}, "executed": {}},
                                  "convergence": {"main": {"PropagateUpDownIterative": entry}}})
        self.assertIn("PropagateUpDownIterative no convergió (max_iter × 1)", html)
        # A result saved before decision 6.5 of #64 has no reasons: said as such, never «()».
        old = {k: v for k, v in entry.items() if k != "unavailable_reasons"}
        self.assertIn("no disponible en 1 de 2 (causa no registrada).",
                      str(convergence_warnings({"PropagateUpDownIterative": old})[0]))
        self.assertIn("no disponible en 1 de 2 (causa no registrada)", model_config_html(
            {"wake_config": {"selected": {}, "executed": {}}, "convergence": {"main": {"PropagateUpDownIterative": old}}}))

    def test_a_non_finite_residual_does_not_depend_on_the_order(self):
        # Python's max with [finite, NaN] depends on the order; the summary takes the largest finite residual and
        # counts the others.
        rec = ins.ConvergenceRecorder()
        for errors in ((0.5, float("nan")), (float("nan"), 0.5)):
            rec.records = {"WeightedSum": [{"state": "tolerance_not_met", "error": e} for e in errors],
                           "All2AllIterative": [], "PropagateUpDownIterative": []}
            with self.subTest(errors=errors):
                entry = rec.summary()["WeightedSum"]
                self.assertEqual((entry["max_error"], entry["non_finite_residuals"]), (0.5, 1))
                from VelantisWind.ag_core.wake_setup.notices import convergence_warnings
                self.assertIn("Convergencia de WeightedSum: 1 residuo(s) no finito(s).",
                              [str(w) for w in convergence_warnings(rec.summary())])

    def test_a_loop_this_pywake_does_not_have_is_not_required(self):
        # Without PropagateUpDownIterative installed, a calculation that does not use it is recorded as before.
        from py_wake.wind_farm_models import engineering_models as em
        delattr(em, "PropagateUpDownIterative")
        self.addCleanup(setattr, em, "PropagateUpDownIterative", PropagateUpDownIterative)
        self.assertNotIn("PropagateUpDownIterative", ins._targets().values())
        make = lambda: PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(), superpositionModel=WeightedSum())  # noqa
        values, summary = aep(make, record=True)
        np.testing.assert_array_equal(values, aep(make)[0])
        self.assertGreater(summary["WeightedSum"]["calls"], 0)  # the loops it has are still watched

    def test_a_failure_that_is_not_an_absence_is_raised(self):
        with mock.patch.object(ins.importlib, "import_module", side_effect=ImportError("broken")):
            with self.assertRaises(ImportError):
                ins._targets()
        with mock.patch.object(WeightedSum, "__call__", new=None):  # the class is there, its method is not
            with self.assertRaises(AttributeError):
                ins._targets()

    def test_the_previous_trace_function_is_restored(self):
        before = sys.gettrace()
        with ins.ConvergenceRecorder():
            self.assertIsNotNone(sys.gettrace())
        self.assertIs(sys.gettrace(), before)


class EffectiveTiTest(unittest.TestCase):
    def test_known_values(self):
        ti = xr.DataArray(np.array([[[0.10, 0.20], [0.30, 0.40]], [[0.05, 0.05], [0.05, 0.05]]]),
                          dims=("wt", "wd", "ws"))
        p = xr.DataArray(np.array([[0.1, 0.2], [0.3, 0.4]]), dims=("wd", "ws"))
        sim = xr.Dataset({"TI_eff": ti, "P": p})
        out = ins.effective_ti_per_turbine(sim)
        np.testing.assert_allclose(out, [(0.01 + 0.04 + 0.09 + 0.16) / 1.0, 0.05], rtol=1e-15)

    def test_read_from_the_simulation_with_the_added_turbulence(self):
        sim = PropagateDownwind(SITE, WT, NiayifarGaussianDeficit(), turbulenceModel=STF2017TurbulenceModel())(
            wt_x[:5], wt_y[:5], wd=WD, ws=WS)
        out = ins.effective_ti_per_turbine(sim)
        ti, p = sim.TI_eff.values, sim.P.values
        expected = (ti * p[None]).sum((1, 2)) / p.sum()
        np.testing.assert_allclose(out, expected, rtol=1e-14)
        self.assertTrue(np.all(out >= float(sim.TI.mean()) - 1e-12))

    def test_not_readable_is_none_never_a_default(self):
        self.assertIsNone(ins.effective_ti_per_turbine(xr.Dataset({"P": xr.DataArray([1.0], dims=("wd",))})))
        # A missing value is not skipped by the sum (that would give 0 or a partial mean).
        ti = xr.DataArray(np.array([[[np.nan, np.nan]], [[np.nan, 0.1]]]), dims=("wt", "wd", "ws"))
        p = xr.DataArray(np.array([[0.5, 0.5]]), dims=("wd", "ws"))
        out = ins.effective_ti_per_turbine(xr.Dataset({"TI_eff": ti, "P": p}))
        self.assertTrue(np.all(np.isnan(out)))
        for bad in (np.inf, -np.inf):
            ti = xr.DataArray(np.array([[[bad, 0.1]], [[0.1, 0.1]]]), dims=("wt", "wd", "ws"))
            out = ins.effective_ti_per_turbine(xr.Dataset({"TI_eff": ti, "P": p}))
            self.assertTrue(np.isnan(out[0]))
            self.assertAlmostEqual(out[1], 0.1)


if __name__ == "__main__":
    unittest.main()
