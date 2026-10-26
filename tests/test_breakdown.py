# -*- coding: utf-8 -*-
"""The signed loss breakdown and its variants (``ag_core/results/breakdown.py``, ``variants.py``; #46 P3, closes #58)."""
import unittest
import warnings

import numpy as np

from VelantisWind.ag_core.results import breakdown as bd
from VelantisWind.ag_core.results import variants as vr
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory as fac

warnings.filterwarnings("ignore", module="py_wake")


def C(name, **params):
    return cfg.Component(name, params)


def with_(config, **changes):
    return cfg.WakeConfig(**{**config.__dict__, **changes})


# Known values, per turbine (MWh): a gain by blockage at turbine 2 and a gain by turbulence at turbine 1.
A0 = np.array([100.0, 100.0, 100.0])
AW = np.array([90.0, 80.0, 100.0])
AWT = np.array([92.0, 79.0, 100.0])
AWB = np.array([89.0, 79.5, 100.5])
AWTB = np.array([91.0, 78.0, 100.6])
FULL = {"A_0": A0, "A_W": AW, "A_WT": AWT, "A_WB": AWB, "A_WTB": AWTB}
OK_STATES = {k: bd.OK for k in bd.AEP_TERMS}


class BreakdownTest(unittest.TestCase):
    def test_the_identity_with_signed_values(self):
        states = bd.term_states(aep_states=OK_STATES, turbulence=True, blockage=True, turbulence_changes_deficit=True)
        rows = bd.per_turbine(FULL, OK_STATES, states)
        for i, r in enumerate(rows):
            self.assertAlmostEqual(r["l_wake_mwh"], A0[i] - AW[i])
            self.assertAlmostEqual(r["d_turb_mwh"], AWT[i] - AW[i])
            self.assertAlmostEqual(r["d_blk_mwh"], AWTB[i] - AWT[i])
            self.assertAlmostEqual(r["l_total_mwh"], r["l_wake_mwh"] - r["d_turb_mwh"] - r["d_blk_mwh"])
            self.assertAlmostEqual(r["l_total_mwh"], A0[i] - AWTB[i])
        # A gain stays a gain: never clipped to zero.
        self.assertAlmostEqual(rows[2]["d_blk_mwh"], 0.6)
        self.assertAlmostEqual(rows[0]["d_turb_mwh"], 2.0)
        self.assertAlmostEqual(rows[2]["l_total_mwh"], -0.6)
        farm = bd.aggregate(FULL, OK_STATES, states)[None]
        self.assertAlmostEqual(farm["L_total"]["mwh"], farm["L_W"]["mwh"] - farm["D_T"]["mwh"] - farm["D_B"]["mwh"])
        self.assertAlmostEqual(farm["I_TB"]["mwh"], float((AWTB - AWT - AWB + AW).sum()))
        self.assertAlmostEqual(farm["L_W"]["pct"], 100 * 30.0 / 300.0)
        by_model = bd.aggregate(FULL, OK_STATES, states, groups=["a", "a", "b"])
        self.assertAlmostEqual(by_model["a"]["D_B"]["mwh"], (91 - 92) + (78 - 79))
        self.assertAlmostEqual(by_model["b"]["D_B"]["mwh"], 0.6)
        self.assertAlmostEqual(sum(m["L_total"]["mwh"] for m in by_model.values()), farm["L_total"]["mwh"])

    def test_a_failed_variant_is_not_available_never_zero_nor_the_total(self):
        aep = dict(FULL, A_W=None)
        aep_states = dict(OK_STATES, A_W=bd.FAILED)
        states = bd.term_states(aep_states=aep_states, turbulence=True, blockage=True, turbulence_changes_deficit=True)
        self.assertEqual((states["L_W"], states["D_T"], states["D_B"], states["L_total"]),
                         (bd.FAILED, bd.FAILED, bd.OK, bd.OK))
        row = bd.per_turbine(aep, aep_states, states)[0]
        self.assertIsNone(row["l_wake_mwh"])
        self.assertIsNone(row["d_turb_mwh"])
        self.assertIsNone(row["l_wake_pct"])
        self.assertAlmostEqual(row["l_total_mwh"], 9.0)
        self.assertIn("A_W=failed", row["wake_states"])
        farm = bd.aggregate(aep, aep_states, states)[None]
        self.assertIsNone(farm["L_W"]["mwh"])
        self.assertEqual(farm["L_W"]["state"], bd.FAILED)

    def test_a_failed_free_stream_leaves_the_rest_and_no_percentages(self):
        aep = dict(FULL, A_0=None)
        aep_states = dict(OK_STATES, A_0=bd.FAILED)
        states = bd.term_states(aep_states=aep_states, turbulence=True, blockage=True, turbulence_changes_deficit=True)
        row = bd.per_turbine(aep, aep_states, states)[1]
        self.assertIsNone(row["aep_free_mwh"])
        self.assertIsNone(row["l_total_mwh"])
        self.assertAlmostEqual(row["d_turb_mwh"], -1.0)
        self.assertIsNone(row["d_turb_pct"])

    def test_without_turbulence_and_blockage(self):
        aep = {"A_0": A0, "A_W": AWTB, "A_WT": None, "A_WB": None, "A_WTB": AWTB}
        aep_states = dict(OK_STATES, A_WT=bd.NOT_MODELLED, A_WB=bd.NOT_MODELLED)
        states = bd.term_states(aep_states=aep_states, turbulence=False, blockage=False, turbulence_changes_deficit=False)
        self.assertEqual((states["D_T"], states["D_B"], states["I_TB"]), (bd.NOT_MODELLED,) * 3)
        row = bd.per_turbine(aep, aep_states, states)[0]
        self.assertEqual(row["l_wake_mwh"], row["l_total_mwh"])
        self.assertIsNone(row["d_turb_mwh"])
        self.assertIsNone(row["aep_wt_mwh"])
        self.assertIn("D_B=not_modelled", row["wake_states"])

    def test_blockage_without_turbulence_measures_from_the_wakes_only(self):
        aep = {"A_0": A0, "A_W": AW, "A_WT": None, "A_WB": AWTB, "A_WTB": AWTB}
        aep_states = dict(OK_STATES, A_WT=bd.NOT_MODELLED)
        states = bd.term_states(aep_states=aep_states, turbulence=False, blockage=True, turbulence_changes_deficit=False)
        row = bd.per_turbine(aep, aep_states, states)[2]
        self.assertAlmostEqual(row["d_blk_mwh"], AWTB[2] - AW[2])
        self.assertAlmostEqual(row["l_total_mwh"], row["l_wake_mwh"] - row["d_blk_mwh"])

    def test_turbulence_that_does_not_reach_the_deficit(self):
        states = bd.term_states(aep_states=OK_STATES, turbulence=True, blockage=False, turbulence_changes_deficit=False)
        self.assertEqual(states["D_T"], bd.ZERO_BY_CONSTRUCTION)

    def test_variants_not_requested(self):
        aep_states = dict(OK_STATES, A_W=bd.NOT_REQUESTED, A_WB=bd.NOT_REQUESTED)
        states = bd.term_states(aep_states=aep_states, turbulence=True, blockage=False, turbulence_changes_deficit=True)
        self.assertEqual((states["L_W"], states["D_T"], states["L_total"]), (bd.NOT_REQUESTED, bd.NOT_REQUESTED, bd.OK))


class VariantsTest(unittest.TestCase):
    def setUp(self):
        self.full = with_(cfg.default_config("All2AllIterative", "ZongGaussianDeficit"),
                          turbulence=C("CrespoHernandez"), blockage=C("VortexDipole", use_effective_ws=False),
                          blockage_superposition=C("LinearSum"), superposition=C("SquaredSum"))

    def test_each_variant_has_exactly_its_intervention(self):
        v = vr.variant_configs(self.full)
        for name, turb, blk in (("A_W", None, None), ("A_WT", "CrespoHernandez", None), ("A_WB", None, "VortexDipole")):
            with self.subTest(variant=name):
                c = v[name]
                self.assertEqual(c.turbulence.name if c.turbulence else None, turb)
                self.assertEqual(c.blockage.name if c.blockage else None, blk)
                self.assertEqual(c.deficit.params["use_effective_ti"], turb is not None)
                # Nothing else changes: engine, superposition, rotor, ground and the other arguments.
                for field in ("engine", "superposition", "rotor", "ground"):
                    self.assertEqual(getattr(c, field), getattr(self.full, field))
                for p, value in self.full.deficit.params.items():
                    if p != "use_effective_ti":
                        self.assertEqual(c.deficit.params[p], value)

    def test_classes_without_use_effective_ti_are_not_given_it(self):
        for name in ("BastankhahGaussianDeficit", "NOJDeficit", "IEA37SimpleBastankhahGaussianDeficit"):
            with self.subTest(deficit=name):
                c = with_(cfg.default_config("All2AllIterative", name), turbulence=C("STF2017TurbulenceModel"))
                a_w = vr.variant_configs(c)["A_W"]
                self.assertNotIn("use_effective_ti", a_w.deficit.params)
                self.assertEqual(a_w.deficit, c.deficit)
                # The deficit does not read the effective TI: the breakdown says so instead of an impact.
                self.assertFalse(vr.turbulence_changes_deficit(fac.build_deficit(c)))
        self.assertTrue(vr.turbulence_changes_deficit(fac.build_deficit(self.full)))

    def test_run_breakdown_protects_each_variant(self):
        calls = []

        def run(target):
            calls.append(target)
            if target is not vr.FREE_STREAM and target.turbulence is None and target.blockage is not None:
                raise RuntimeError("variante A_WB")
            return np.ones(3) if target is vr.FREE_STREAM else np.full(3, 0.5)

        aep, states, derived, errors = vr.run_breakdown(self.full, np.full(3, 0.4), run, compute_variants=True,
                                                         turbulence_reaches_deficit=True)
        self.assertEqual(states, {"A_WTB": bd.OK, "A_0": bd.OK, "A_W": bd.OK, "A_WT": bd.OK, "A_WB": bd.FAILED})
        self.assertIn("variante A_WB", errors["A_WB"])
        self.assertEqual(derived["I_TB"], bd.FAILED)
        self.assertEqual(derived["D_B"], bd.OK)
        self.assertEqual(len(calls), 4)
        aep, states, derived, _ = vr.run_breakdown(self.full, np.full(3, 0.4), run, compute_variants=False,
                                                    turbulence_reaches_deficit=True)
        self.assertEqual((states["A_W"], derived["L_W"], derived["L_total"]), (bd.NOT_REQUESTED, bd.NOT_REQUESTED, bd.OK))

    def test_the_variants_of_a_plain_configuration(self):
        plain = cfg.default_config()
        self.assertEqual(vr.variant_configs(plain), {"A_W": None, "A_WT": None, "A_WB": None})
        aep, states, derived, _ = vr.run_breakdown(plain, np.full(2, 3.0), lambda t: np.full(2, 4.0),
                                                    compute_variants=True, turbulence_reaches_deficit=False)
        self.assertEqual(states["A_W"], bd.OK)
        self.assertIs(aep["A_W"], aep["A_WTB"])
        self.assertEqual((states["A_WT"], states["A_WB"]), (bd.NOT_MODELLED, bd.NOT_MODELLED))


class BuiltVariantsTest(unittest.TestCase):
    """The variants and A_0 built with the factory of P1 carry exactly their interventions (#75, rows 4.3-4.4)."""

    def setUp(self):
        from py_wake.examples.data.hornsrev1 import Hornsrev1Site, V80
        self.site, self.wt = Hornsrev1Site(), V80()

    def test_the_built_variants(self):
        full = with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"), turbulence=C("STF2005TurbulenceModel"),
                     blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False), blockage_superposition=C("LinearSum"),
                     rotor=C("CGIRotorAvg", n=9))
        for name, c in vr.variant_configs(full).items():
            with self.subTest(variant=name):
                wfm = fac.build_wind_farm_model(c, self.site, self.wt, ws_grid=np.array([8.0, 10.0]))
                fac.check_classes(fac.expected_classes(c), wfm)
                d = wfm.wake_deficitModel
                self.assertEqual(type(wfm.turbulenceModel).__name__ if wfm.turbulenceModel else None,
                                 "STF2005TurbulenceModel" if name in ("A_WT",) else None)
                self.assertEqual(d.TI_key, "TI_eff_ilk" if name == "A_WT" else "TI_ilk")
                self.assertEqual(wfm.blockage_deficitModel is not None, name == "A_WB")
                self.assertEqual(len(d.rotorAvgModel.nodes_x), 9)
                self.assertEqual(type(wfm).__name__, "All2AllIterative")

    def test_free_stream_with_each_engine_and_superposition(self):
        from py_wake.deficit_models.no_wake import NoWakeDeficit
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import PropagateDownwind
        from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, simulation_wind_turbines
        x, y, ws = [0.0, 500.0, 1000.0], [0.0, 0.0, 0.0], np.array([8.0, 10.0])
        oracle = PropagateDownwind(self.site, simulation_wind_turbines(self.wt, ws, BIN_MEAN), NoWakeDeficit(),
                                   superpositionModel=LinearSum())(x, y, wd=[0, 270], ws=ws).aep().values
        for engine in ("PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"):
            for sup in ("LinearSum", "SquaredSum", "MaxSum", "WeightedSum", "CumulativeWakeSum"):
                with self.subTest(engine=engine, superposition=sup):
                    principal = with_(cfg.default_config(engine), superposition=C(sup))
                    wfm = fac.build_free_stream_model(principal, self.site, self.wt, ws_grid=ws)
                    fac.check_classes(fac.free_stream_expected_classes(principal), wfm)
                    self.assertEqual(type(wfm).__name__, engine)
                    aep = wfm(x, y, wd=[0, 270], ws=ws).aep().values
                    np.testing.assert_allclose(aep, oracle, rtol=1e-12, atol=0)


if __name__ == "__main__":
    unittest.main()
