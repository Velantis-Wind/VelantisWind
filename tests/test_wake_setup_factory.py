# -*- coding: utf-8 -*-
"""Validation, exact construction, class check and readers of the wake configuration (``ag_core/wake_setup``, #46 P1b)."""
import inspect
import os
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, simulation_wind_turbines
from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory as fac
from VelantisWind.ag_core.wake_setup import readers as rd
from VelantisWind.ag_core.wake_setup import validation as val

warnings.filterwarnings("ignore", module="py_wake")

from py_wake.examples.data.hornsrev1 import Hornsrev1Site, V80  # noqa: E402

SITE, WT = Hornsrev1Site(), V80()
X, Y = np.array([0.0, 560.0, 1120.0, 300.0]), np.array([0.0, 0.0, 0.0, 400.0])
WD, WS = np.array([0.0, 90.0, 270.0]), np.array([6.0, 10.0, 14.0])
NEEDS_TI = ("NiayifarGaussianDeficit", "ZongGaussianDeficit", "CarbajofuertesGaussianDeficit",
            "BlondelSuperGaussianDeficit2020", "BlondelSuperGaussianDeficit2023", "NOJLocalDeficit")


def with_(config, **changes):
    return cfg.WakeConfig(**{**config.__dict__, **changes})


def C(name, **params):
    return cfg.Component(name, params)


def simulate(wfm):
    return wfm(X, Y, wd=WD, ws=WS)


def build(config):
    return fac.build_wind_farm_model(config, SITE, WT, ws_grid=WS)


def codes(config):
    return [i.code for i in val.validate(config)]


def direct(engine, deficit, **kwargs):
    """PyWake directly, by hand, with the same inputs and the plugin's bin-mean power (the oracle)."""
    return engine(SITE, simulation_wind_turbines(WT, WS, BIN_MEAN), deficit, **kwargs)


class ClassFidelityTest(unittest.TestCase):
    """Each class with its signature values in PDW gives, bit for bit, the AEP of PyWake directly."""

    def test_each_class_with_its_signature_in_propagate_downwind(self):
        from py_wake.superposition_models import LinearSum
        from py_wake.turbulence_models import STF2017TurbulenceModel
        from py_wake.wind_farm_models import PropagateDownwind
        for e in cat.entries(cat.DEFICIT):
            with self.subTest(deficit=e.name):
                config = cfg.default_config("PropagateDownwind", e.name)
                if e.name in NEEDS_TI:
                    # Rejected with PyWake's reason with the defaults (decision 16), and PyWake does reject it.
                    self.assertEqual(codes(config), ["R2"])
                    with self.assertRaises(AssertionError):
                        direct(PropagateDownwind, cat.resolve_class(e)())
                    # A turbulence chosen in the test, not a default.
                    config = with_(config, turbulence=C("STF2017TurbulenceModel"))
                    oracle = direct(PropagateDownwind, cat.resolve_class(e)(), superpositionModel=LinearSum(),
                                    turbulenceModel=STF2017TurbulenceModel())
                else:
                    oracle = direct(PropagateDownwind, cat.resolve_class(e)(), superpositionModel=LinearSum())
                self.assertEqual(codes(config), [])
                ours = simulate(build(config)).aep()
                theirs = simulate(oracle).aep()
                self.assertTrue(np.array_equal(ours.values, theirs.values))

    def test_two_constructions_share_no_object(self):
        config = with_(cfg.default_config("All2AllIterative", "NOJDeficit"), turbulence=C("CrespoHernandez"),
                       blockage=C("VortexDipole", use_effective_ws=False), blockage_superposition=C("LinearSum"))
        a, b = build(config), build(config)
        pairs = [(a.wake_deficitModel, b.wake_deficitModel), (a.superpositionModel, b.superpositionModel),
                 (a.turbulenceModel, b.turbulenceModel), (a.blockage_deficitModel, b.blockage_deficitModel),
                 (a.wake_deficitModel.rotorAvgModel, b.wake_deficitModel.rotorAvgModel),
                 (a.blockage_deficitModel.superpositionModel, b.blockage_deficitModel.superpositionModel)]
        for x, y in pairs:
            self.assertIsNot(x, y)
        # Nor with the default objects of PyWake's signatures.
        default_rotor = cat.signature_defaults(cat.entry(cat.DEFICIT, "NOJDeficit"))["rotorAvgModel"]
        self.assertIsNot(a.wake_deficitModel.rotorAvgModel, default_rotor)
        default_sup = cat.signature_defaults(cat.entry(cat.ENGINE, "All2AllIterative"))["superpositionModel"]
        self.assertIsNot(a.superpositionModel, default_sup)

    def test_no_nested_object_is_shared(self):
        # The defaults of the signatures that are not passed (the rotor average and the added-turbulence superposition
        # of the turbulence models, the weight function of the STF models, the lists of coefficients and those of the
        # engine) are copies too: walked through every attribute of the engine and its components, except the site
        # and the turbines (inputs of the engine) and the components' reference back to the engine.
        def reachable(obj, out):
            if inspect.ismethod(obj):  # the STF models keep their weight function as its bound method
                obj = obj.__self__
            if id(obj) in out or obj is SITE or isinstance(obj, type):
                return out
            if isinstance(obj, (list, tuple, dict, np.ndarray)) or type(obj).__module__.startswith("py_wake"):
                out[id(obj)] = obj
                items = (obj.values() if isinstance(obj, dict) else obj if isinstance(obj, (list, tuple)) else
                         [] if isinstance(obj, np.ndarray) else
                         [v for k, v in vars(obj).items() if k not in ("windFarmModel", "_windFarmModel")])
                for v in items:
                    reachable(v, out)
            return out

        defaults = {}
        for position in cat.POSITIONS:
            for e in cat.entries(position):
                reachable(list(cat.signature_defaults(e).values()), defaults)
        for turbulence in ("CrespoHernandez", "STF2017TurbulenceModel", "STF2005TurbulenceModel", "GCLTurbulence"):
            for deficit in ("NOJDeficit", "TurboGaussianDeficit", "NiayifarGaussianDeficit"):
                with self.subTest(turbulence=turbulence, deficit=deficit):
                    config = with_(cfg.default_config("All2AllIterative", deficit), turbulence=C(turbulence),
                                   blockage=C("SelfSimilarityDeficit2020"), blockage_superposition=C("LinearSum"))
                    found = [{}, {}]
                    for wfm, out in zip((build(config), build(config)), found):
                        reachable({k: v for k, v in vars(wfm).items() if k not in ("site", "windTurbines")}, out)
                    self.assertEqual([type(found[0][i]).__name__ for i in set(found[0]) & set(found[1])], [])
                    self.assertEqual([type(found[0][i]).__name__ for i in set(found[0]) & set(defaults)], [])


class MissingFunctionTest(unittest.TestCase):
    def test_a_ct2a_the_installation_does_not_have(self):
        # The environment, with the translatable reason of the catalogue (never a text made of it).
        from VelantisWind import i18n
        from VelantisWind.ag_core.log_text import log_text
        from VelantisWind.ag_core.wake_setup.messages_translations import register_messages_translations
        register_messages_translations()
        real = cat.resolve_ct2a

        def missing(name):
            if name == "ct2a_mom1d":
                raise cat.ClassUnavailable(log_text("La instalación de PyWake no tiene la función {cls} en {module}.",
                                                    cls=name, module=cat.CT2A_MODULE))
            return real(name)
        config = with_(cfg.default_config(), deficit=C("BastankhahGaussianDeficit", **dict(
            cfg.default_config().deficit.params, ct2a="ct2a_mom1d")))
        with mock.patch.object(cat, "resolve_ct2a", side_effect=missing):
            issues = val.validate(config)
        self.assertEqual([(i.code, i.position, i.origin) for i in issues], [("R14", cat.DEFICIT, val.ENVIRONMENT)])
        with mock.patch.object(i18n, "current_language", return_value="en"):
            text = issues[0].translated(i18n.tr_text)
        self.assertIn("The PyWake installation does not have the function ct2a_mom1d", text)
        self.assertNotIn("La instalación", text)


class VariantsFidelityTest(unittest.TestCase):
    """The terms of the loss breakdown (A_0, A_W, A_WT, A_WB and the main A_WTB), calculated as the AEP calculates
    them (``variants.run_breakdown`` with the factory), bit for bit against PyWake directly written by hand."""

    @staticmethod
    def aep(wfm):
        return simulate(wfm).aep().sum(["wd", "ws"]).values

    def breakdown(self, config):
        from VelantisWind.ag_core.results import variants as var

        def run(target):
            if target is var.FREE_STREAM:
                return self.aep(fac.build_free_stream_model(config, SITE, WT, ws_grid=WS))
            return self.aep(build(target))
        wfm = build(config)
        aep, states, _derived, errors = var.run_breakdown(
            config, self.aep(wfm), run, compute_variants=True,
            turbulence_reaches_deficit=var.turbulence_changes_deficit(wfm.wake_deficitModel))
        self.assertEqual(errors, {})
        return aep, states

    def test_the_variants_are_pywake_directly(self):
        from py_wake.deficit_models import gaussian as g
        from py_wake.deficit_models.no_wake import NoWakeDeficit
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020
        from py_wake.deficit_models.vortexdipole import VortexDipole
        from py_wake.rotor_avg_models import CGIRotorAvg
        from py_wake.superposition_models import LinearSum, MaxSum
        from py_wake.turbulence_models import CrespoHernandez, STF2005TurbulenceModel, STF2017TurbulenceModel
        from py_wake.wind_farm_models import All2AllIterative, PropagateDownwind, PropagateUpDownIterative
        cases = {
            # A2A with turbulence and blockage: the four variants; Niayifar has use_effective_ti (False without
            # turbulence).
            "a2a_niayifar_cgi7_stf2017_ss2020": (
                with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"), rotor=C("CGIRotorAvg", n=7),
                      turbulence=C("STF2017TurbulenceModel"),
                      blockage=cfg.blockage_signature("SelfSimilarityDeficit2020"),
                      blockage_superposition=C("LinearSum")),
                All2AllIterative,
                lambda ti: g.NiayifarGaussianDeficit(rotorAvgModel=CGIRotorAvg(7), use_effective_ti=ti),
                STF2017TurbulenceModel, lambda: SelfSimilarityDeficit2020(superpositionModel=LinearSum())),
            # PUD: Bastankhah has no use_effective_ti (it is not given it); the blockage with its own superposition.
            "pud_bg_ews_crespo_vortexdipole_maxsum": (
                with_(cfg.default_config("PropagateUpDownIterative", "BastankhahGaussianDeficit"),
                      deficit=C("BastankhahGaussianDeficit", **dict(
                          cfg.deficit_signature("BastankhahGaussianDeficit")[0].params, use_effective_ws=True)),
                      turbulence=C("CrespoHernandez"),
                      blockage=C("VortexDipole",
                                 **dict(cfg.blockage_signature("VortexDipole").params, use_effective_ws=True)),
                      blockage_superposition=C("MaxSum")),
                PropagateUpDownIterative, lambda ti: g.BastankhahGaussianDeficit(use_effective_ws=True),
                CrespoHernandez, lambda: VortexDipole(use_effective_ws=True, superpositionModel=MaxSum())),
            # PDW without blockage: the main one is A_WT, A_W the only variant, A_WB not modelled.
            "pdw_zong_stf2005": (
                with_(cfg.default_config("PropagateDownwind", "ZongGaussianDeficit"),
                      turbulence=C("STF2005TurbulenceModel")),
                PropagateDownwind, lambda ti: g.ZongGaussianDeficit(use_effective_ti=ti), STF2005TurbulenceModel, None),
        }
        for name, (config, engine, deficit, turbulence, blockage) in cases.items():
            with self.subTest(name):
                self.assertEqual(codes(config), [])
                aep, states = self.breakdown(config)

                def oracle(ti, with_turbulence, with_blockage):
                    kwargs = {"superpositionModel": LinearSum()}
                    if with_turbulence:
                        kwargs["turbulenceModel"] = turbulence()
                    if with_blockage:
                        kwargs["blockage_deficitModel"] = blockage()
                    return self.aep(direct(engine, deficit(ti), **kwargs))
                expected = {"A_0": self.aep(direct(engine, NoWakeDeficit(), superpositionModel=LinearSum())),
                            "A_W": oracle(False, False, False), "A_WT": oracle(True, True, False)}
                if blockage is not None:
                    expected.update(A_WB=oracle(False, False, True), A_WTB=oracle(True, True, True))
                else:
                    self.assertEqual(states["A_WB"], "not_modelled")
                    expected["A_WTB"] = expected["A_WT"]
                for term, values in expected.items():
                    self.assertTrue(np.array_equal(aep[term], values), (term, aep[term], values))


class RulesTest(unittest.TestCase):
    """Each rule of P0 (section 6), with PyWake failing in the same configuration (when building or calculating)."""

    CASES = {
        "R1": with_(cfg.default_config(), blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False),
                    blockage_superposition=C("LinearSum")),
        "R2": cfg.default_config(deficit="ZongGaussianDeficit"),
        "R3": cfg.default_config("PropagateUpDownIterative"),
        "R3b": cfg.default_config("PropagateUpDownIterative", "NOJDeficit"),
        "R4": with_(cfg.default_config("PropagateUpDownIterative", "NOJLocalDeficit"), turbulence=C("STF2017TurbulenceModel"),
                    blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False), blockage_superposition=C("LinearSum")),
        "R5": with_(cfg.default_config("PropagateUpDownIterative", "NOJLocalDeficit"), turbulence=C("STF2017TurbulenceModel"),
                    blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True), blockage_superposition=C("SquaredSum")),
        "R6": with_(cfg.default_config("All2AllIterative"), blockage=C("VortexDipole", use_effective_ws=False),
                    blockage_superposition=C("WeightedSum")),
        "R7": with_(cfg.default_config(deficit="GCLDeficit"), superposition=C("WeightedSum")),
        "R8": with_(cfg.default_config(), rotor=C("RotorCenter"), superposition=C("WeightedSum")),
        "R9": with_(cfg.default_config(deficit="TurboGaussianDeficit"), superposition=C("WeightedSum")),
        "R9b": with_(cfg.default_config(deficit="NOJDeficit"), rotor=None, superposition=C("WeightedSum")),
        "R9c": with_(cfg.default_config(deficit="TurboNOJDeficit"), rotor=None, superposition=C("CumulativeWakeSum")),
        "R9d": with_(cfg.default_config("All2AllIterative", "TurboGaussianDeficit"), superposition=C("CumulativeWakeSum")),
        "R10": with_(cfg.default_config(), rotor=C("AreaOverlapAvgModel")),
        "R11": with_(cfg.default_config(deficit="NOJDeficit"), rotor=C("GaussianOverlapAvgModel")),
        "R12": with_(cfg.default_config(), rotor=C("CGIRotorAvg", n=7), ground=C("MultiMirror")),
    }
    # R9f depends on the layout (validation.layout_issues): PUD, an iterative wake sum and MaxSum in the blockage.
    R9F = with_(cfg.default_config("PropagateUpDownIterative"),
                deficit=C("BastankhahGaussianDeficit", **dict(cfg.default_config().deficit.params, use_effective_ws=True)),
                superposition=C("CumulativeWakeSum"), blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True),
                blockage_superposition=C("MaxSum"))

    # What PyWake 2.6.18 raises in each case: the exception and a piece of its message (P0, section 6).
    PYWAKE = {
        "R1": (TypeError, "unexpected keyword argument 'blockage_deficitModel'"),
        "R2": (AssertionError, ""),
        "R3": (AssertionError, "requires a wake deficit model that scales with the effective wind speed"),
        "R3b": (AssertionError, "requires a wake deficit model that scales with the effective wind speed"),
        "R4": (AssertionError, "only works with blockage deficit models that scales with the effective wind speed"),
        "R5": (AssertionError, "does not work with SquaredSum when the blockage model has both up and downstream"),
        "R6": (TypeError, "WeightedSum.__call__() missing"),
        "R7": (AssertionError, ""),
        "R8": (AssertionError, "only work with NodeRotorAvgModel-based rotor average models"),
        "R9": (NotImplementedError, "cannot be used in combination with GroundModels"),
        "R9b": (NotImplementedError, "calc_deficit_convection not implemented for NOJ"),
        "R9c": (AttributeError, "'TurboNOJDeficit' object has no attribute 'a'"),
        "R9d": (TypeError, "CumulativeWakeSum.__call__() missing"),
        "R10": (AssertionError, "AreaOverlapAvgModel uses the wake_radius from the wake_deficitModel"),
        "R11": (AttributeError, "'NOJDeficit' object has no attribute '_ctlim'"),
        "R12": (AttributeError, "'function' object has no attribute '__self__'"),
    }

    def test_each_rule_is_what_pywake_rejects(self):
        # What the AEP refuses with the turbines of ``simulate`` (decision 6.1 of #64: the failures of interaction
        # with PropagateDownwind and PropagateUpDownIterative are refused with the layout, from the second turbine).
        for rule, config in self.CASES.items():
            with self.subTest(rule=rule):
                issues = val.validate(config) or val.layout_issues(config, len(X))
                self.assertEqual([i.code for i in issues], [rule.rstrip("b") if rule == "R3b" else rule])
                i = issues[0]
                self.assertTrue(i.text)
                self.assertIn(i.origin, (val.PYWAKE_BUILD, val.PYWAKE_CALC))
                exc_type, fragment = self.PYWAKE[rule]
                with self.assertRaises(exc_type) as ctx:
                    if rule == "R1":
                        # The plugin never passes it; PyWake has no such argument.
                        from py_wake.wind_farm_models import PropagateDownwind
                        PropagateDownwind(SITE, WT, fac.build_deficit(config), blockage_deficitModel=fac.build_blockage(config))
                    try:
                        simulate(build(config)).aep()
                    except fac.FactoryError as fe:
                        raise fe.cause
                self.assertIn(fragment, str(ctx.exception))
                # The origin says when PyWake rejects it: when building, or only when calculating.
                if i.origin == val.PYWAKE_CALC:
                    build(config)

    def test_r9f_with_both_iterative_sums_and_every_blockage(self):
        # PUD keeps no blockage of its downwind pass with WeightedSum or CumulativeWakeSum: from the second turbine on,
        # MaxSum fails; with one turbine it calculates. Checked with the layout, before simulating.
        for sup in ("WeightedSum", "CumulativeWakeSum"):
            for e in cat.entries(cat.BLOCKAGE):
                config = with_(self.R9F, superposition=C(sup), blockage=C(e.name, use_effective_ws=True))
                with self.subTest(sup=sup, blockage=e.name):
                    self.assertEqual(codes(config), [])
                    issues = val.layout_issues(config, len(X))
                    self.assertEqual([(i.code, i.position, i.origin) for i in issues],
                                     [("R9f", cat.BLOCKAGE_SUPERPOSITION, val.PYWAKE_CALC)])
                    self.assertIn(f"PropagateUpDownIterative, {sup} y MaxSum", issues[0].text)
                    self.assertEqual(val.layout_issues(config), issues)  # not known yet: the note of the dialog
                    with self.assertRaisesRegex(ValueError, "zero-size array to reduction operation maximum"):
                        simulate(build(config)).aep()
                    self.assertEqual(val.layout_issues(config, 1), [])
                    self.assertTrue(np.isfinite(float(build(config)(X[:1], Y[:1], wd=WD, ws=WS).aep().sum())))
                    # Its resolution makes it calculable.
                    fixed = with_(config, blockage_superposition=C("LinearSum"))
                    self.assertEqual(codes(fixed) + val.layout_issues(fixed, len(X)), [])
                    self.assertTrue(np.isfinite(float(simulate(build(fixed)).aep().sum())))

    def test_r9f_is_only_that_combination(self):
        base = self.R9F
        self.assertEqual(val.layout_issues(with_(base, engine=C("All2AllIterative")), 4), [])
        self.assertEqual(val.layout_issues(with_(base, blockage=None, blockage_superposition=None), 4), [])
        self.assertEqual(val.layout_issues(with_(base, blockage_superposition=C("LinearSum")), 4), [])
        for sup in ("LinearSum", "SquaredSum", "MaxSum"):
            with self.subTest(sup=sup):
                self.assertEqual(val.layout_issues(with_(base, superposition=C(sup)), 4), [])

    def test_r5_does_not_suggest_maxsum_with_an_iterative_sum(self):
        r5 = with_(self.R9F, blockage_superposition=C("SquaredSum"))
        self.assertEqual(codes(r5), ["R5"])
        self.assertIn("Elige LinearSum para el bloqueo.", val.validate(r5)[0].text)
        self.assertIn("Elige LinearSum o MaxSum para el bloqueo.",
                      val.validate(with_(r5, superposition=C("LinearSum")))[0].text)

    def test_r6_suggests_only_what_r5_and_r9f_leave(self):
        r6 = with_(self.R9F, blockage_superposition=C("WeightedSum"))
        cases = {("PropagateUpDownIterative", "CumulativeWakeSum"): "Elige LinearSum.",
                 ("PropagateUpDownIterative", "LinearSum"): "Elige LinearSum o MaxSum.",
                 ("All2AllIterative", "CumulativeWakeSum"): "Elige LinearSum o MaxSum."}  # never SquaredSum (6.3)
        for (engine, sup), resolution in cases.items():
            with self.subTest(engine=engine, sup=sup):
                config = with_(r6, engine=C(engine), superposition=C(sup))
                issues = val.validate(config) or val.layout_issues(config, len(X))  # with PUD, from two turbines
                self.assertEqual([i.code for i in issues], ["R6"])
                self.assertIn(resolution, issues[0].text)
                # Each option it names is calculable.
                for option in resolution[len("Elige "):-1].replace(" o ", ", ").split(", "):
                    chosen = with_(r6, engine=C(engine), superposition=C(sup), blockage_superposition=C(option))
                    self.assertEqual(codes(chosen) + [i.code for i in val.layout_issues(chosen, len(X))], [], option)

    def test_resolutions_name_the_concrete_action(self):
        r2 = val.validate(self.CASES["R2"])[0]
        self.assertIn("CrespoHernandez", r2.text)  # the turbulence of Zong_PorteAgel_2020
        self.assertIn("use_effective_ti", r2.text)
        self.assertIn("use_effective_ws", val.validate(self.CASES["R3"])[0].text)
        self.assertIn("NOJDeficit no tiene use_effective_ws", val.validate(self.CASES["R3b"])[0].text)
        self.assertEqual(val.validate(self.CASES["R4"])[0].position, cat.BLOCKAGE)

    def test_resolving_a_conflict_makes_the_configuration_calculable(self):
        fixed = {
            "R2": with_(self.CASES["R2"], turbulence=C("CrespoHernandez")),
            "R2b": with_(self.CASES["R2"], deficit=C("ZongGaussianDeficit", **dict(self.CASES["R2"].deficit.params, use_effective_ti=False))),
            "R3": with_(self.CASES["R3"], deficit=C("BastankhahGaussianDeficit", **dict(self.CASES["R3"].deficit.params, use_effective_ws=True))),
            "R4": with_(self.CASES["R4"], blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True)),
            "R9": with_(self.CASES["R9"], ground=None),
            "R12": with_(self.CASES["R12"], ground=C("Mirror")),
        }
        for name, config in fixed.items():
            with self.subTest(fix=name):
                self.assertEqual(codes(config), [])
                self.assertTrue(np.isfinite(float(simulate(build(config)).aep().sum())))

    def test_an_explicit_none_reaches_pywake(self):
        # The API contract (P5 a): PyWake receives None and decides; here it builds and fails when calculating.
        base = cfg.default_config()
        config = with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, ct2a=None)))
        self.assertEqual(codes(config), [])
        self.assertIsNone(build(config).wake_deficitModel.ct2a)
        with self.assertRaises(TypeError):
            simulate(build(config)).aep()

    def test_a_number_pywake_cannot_take_as_a_float_is_an_error_of_the_calculation(self):
        # Decision 6.2 of #64: PyWake decides; it fails when calculating, with its cause (decision 1).
        base = cfg.default_config()
        config = with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, k=10 ** 1000)))
        self.assertEqual(codes(config), [])
        with self.assertRaises(Exception):
            simulate(build(config)).aep()

    def test_the_messages_are_translated_with_their_data(self):
        # The tables the application registers when it loads its results window, nothing registered by hand.
        from VelantisWind import i18n, results_dialog  # noqa: F401
        from VelantisWind.ag_core.wake_setup.messages_translations import TRANSLATIONS
        r2 = val.validate(self.CASES["R2"])[0]
        r14 = val.validate(with_(cfg.default_config(), rotor=C("CGIRotorAvg9")))[0]
        for language in ("en", "fr", "de"):
            with self.subTest(language=language), mock.patch.object(i18n, "current_language", return_value=language):
                text = r2.translated(i18n.tr_text)
                self.assertNotIn("usa la TI efectiva", text)
                self.assertNotIn("con sus propios", text)  # the turbulence of the predefined model, translated too
                self.assertIn("ZongGaussianDeficit", text)
                self.assertIn(TRANSLATIONS[language]["promedio de rotor"], r14.translated(i18n.tr_text))
        self.assertIn("usa la TI efectiva", r2.text)

    def test_unknown_options_and_arguments(self):
        base = cfg.default_config()
        for config in (with_(base, engine=C("All2All")), with_(base, deficit=C("TurboPark")),
                       with_(base, superposition=C("AUTO")),
                       with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, kk=1))),
                       with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, ct2a="ct2a_x"))),
                       with_(base, superposition=C("LinearSum", x=1)),
                       with_(base, blockage_superposition=C("LinearSum"))):
            with self.subTest(config=config):
                self.assertEqual(codes(config)[:1], ["R14"])
        # An argument left out takes the signature (decision 2; #64, Q2): it is not an error.
        self.assertEqual(with_(base, deficit=C("BastankhahGaussianDeficit", k=0.04)).deficit.params,
                         dict(base.deficit.params, k=0.04))

    def test_a_class_missing_from_pywake_is_an_environment_error(self):
        real = cat.resolve_class

        def missing(e):
            if e.name == "ZongGaussianDeficit":
                raise cat.ClassUnavailable("La instalación de PyWake no tiene la clase ZongGaussianDeficit.")
            return real(e)
        config = with_(cfg.default_config(deficit="ZongGaussianDeficit"), turbulence=C("CrespoHernandez"))
        with mock.patch.object(cat, "resolve_class", side_effect=missing):
            issues = val.validate(config)
        self.assertEqual([(i.code, i.origin) for i in issues], [("R14", val.ENVIRONMENT)])
        self.assertIn("ZongGaussianDeficit", issues[0].text)

    def test_gaussian_overlap_without_its_libraries(self):
        # The table is read where the rotor is evaluated (decision 6.1 of #64): with All2AllIterative always; with
        # PropagateDownwind from the second turbine, and in the map.
        a2a = with_(cfg.default_config("All2AllIterative"), rotor=C("GaussianOverlapAvgModel"))
        pdw = with_(cfg.default_config(), rotor=C("GaussianOverlapAvgModel"))
        with mock.patch.object(val, "missing_gaussian_overlap_modules", return_value=["h5py"]):
            self.assertEqual([(i.code, i.origin) for i in val.validate(a2a)], [("R13", val.ENVIRONMENT)])
            self.assertIn("h5py", val.validate(a2a)[0].text)
            self.assertEqual(val.validate(a2a, check_environment=False), [])
            self.assertEqual(val.validate(pdw), [])
            self.assertEqual(val.layout_issues(pdw, 1), [])
            self.assertEqual([i.code for i in val.layout_issues(pdw, 2)], ["R13"])
            self.assertEqual([i.code for i in val.map_issues(pdw)], ["R13"])


class ExactConstructionTest(unittest.TestCase):
    def test_every_validated_argument_reaches_the_constructor(self):
        config = with_(cfg.default_config("PropagateUpDownIterative", "ZongGaussianDeficit"), turbulence=C("GCLTurbulence"))
        params = dict(config.deficit.params, ct2a="ct2a_mom1d", a=[0.3, 0.005], ctlim=0.95, lam=6.0, B=2,
                      use_effective_ws=True, use_effective_ti=False)
        config = with_(config, deficit=C("ZongGaussianDeficit", **params), rotor=C("CGIRotorAvg", n=21))
        wfm = build(config)
        d = wfm.wake_deficitModel
        self.assertEqual((d.ct2a.__name__, d.a, d._ctlim, d.lam, d.B, d.WS_key, d.TI_key),
                         ("ct2a_mom1d", [0.3, 0.005], 0.95, 6.0, 2, "WS_eff_ilk", "TI_ilk"))
        self.assertEqual(len(d.rotorAvgModel.nodes_x), 21)
        self.assertIsNone(d.groundModel)

    def test_a_failing_constructor_leaves_its_cause_and_nothing_else(self):
        calls = []

        class Failing:
            def __init__(self, **kwargs):
                calls.append(kwargs)
                if kwargs:
                    raise ValueError("argumentos rechazados")

        real = cat.resolve_class
        config = cfg.default_config()
        with mock.patch.object(cat, "resolve_class", side_effect=lambda e: Failing if e.position == cat.DEFICIT else real(e)):
            with self.assertRaises(fac.FactoryError) as ctx:
                build(config)
        # One attempt with the requested arguments; it would work without them, but nothing else is tried.
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["k"], 0.0324555)
        self.assertEqual(ctx.exception.position, cat.DEFICIT)
        self.assertIsInstance(ctx.exception.cause, ValueError)

    def test_the_absence_is_passed_explicitly(self):
        # NOJ with «Ninguno» as rotor: PyWake receives None, not the AreaOverlapAvgModel of its signature.
        config = with_(cfg.default_config(deficit="NOJDeficit"), rotor=None)
        self.assertIsNone(build(config).wake_deficitModel.rotorAvgModel)
        self.assertEqual(type(build(cfg.default_config(deficit="NOJDeficit")).wake_deficitModel.rotorAvgModel).__name__,
                         "AreaOverlapAvgModel")


class ClassCheckTest(unittest.TestCase):
    def setUp(self):
        self.config = with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"),
                            rotor=C("CGIRotorAvg", n=9), ground=C("Mirror"), turbulence=C("STF2017TurbulenceModel"),
                            blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False),
                            blockage_superposition=C("LinearSum"))
        self.expected = fac.expected_classes(self.config)
        self.wfm = build(self.config)

    def test_the_built_model_passes(self):
        fac.check_classes(self.expected, self.wfm)

    def test_a_substitution_in_each_position_is_detected_without_simulating(self):
        from py_wake.deficit_models.noj import NOJDeficit
        from py_wake.ground_models import MultiMirror
        from py_wake.rotor_avg_models import CGIRotorAvg, RotorCenter
        from py_wake.superposition_models import SquaredSum
        from py_wake.turbulence_models import STF2005TurbulenceModel
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit
        from py_wake.wind_farm_models import All2AllIterative, PropagateDownwind
        injections = {
            cat.ENGINE: lambda w: setattr(w, "__class__", PropagateDownwind) or w,
            cat.DEFICIT: lambda w: w.__dict__.__setitem__("wake_deficitModel", NOJDeficit()) or w,
            cat.SUPERPOSITION: lambda w: w.__dict__.__setitem__("superpositionModel", SquaredSum()) or w,
            cat.TURBULENCE: lambda w: w.__dict__.__setitem__("turbulenceModel", STF2005TurbulenceModel()) or w,
            cat.BLOCKAGE: lambda w: w.__dict__.__setitem__("blockage_deficitModel", SelfSimilarityDeficit()) or w,
            cat.ROTOR: lambda w: w.wake_deficitModel.__dict__.__setitem__("rotorAvgModel", RotorCenter()) or w,
            cat.GROUND: lambda w: w.wake_deficitModel.__dict__.__setitem__("groundModel", MultiMirror()) or w,
        }
        for position, inject in injections.items():
            with self.subTest(position=position):
                wfm = inject(build(self.config))
                with mock.patch.object(All2AllIterative, "_calc_wt_interaction") as sim:
                    with self.assertRaises(fac.ClassMismatch) as ctx:
                        fac.check_classes(self.expected, wfm)
                    sim.assert_not_called()
                self.assertEqual(ctx.exception.position, position)
                self.assertNotEqual(ctx.exception.expected, ctx.exception.observed)
        # The disappearance and the appearance of an optional component, and a subclass (NOJDeficit is a Niayifar).
        for position, value in ((cat.TURBULENCE, None), (cat.BLOCKAGE, None), (cat.ROTOR, None), (cat.GROUND, None)):
            wfm = build(self.config)
            target = wfm.wake_deficitModel if position in (cat.ROTOR, cat.GROUND) else wfm
            key = {cat.TURBULENCE: "turbulenceModel", cat.BLOCKAGE: "blockage_deficitModel", cat.ROTOR: "rotorAvgModel",
                   cat.GROUND: "groundModel"}[position]
            target.__dict__[key] = value
            with self.assertRaises(fac.ClassMismatch) as ctx:
                fac.check_classes(self.expected, wfm)
            self.assertEqual((ctx.exception.position, ctx.exception.observed), (position, None))
        plain = cfg.default_config()
        wfm = build(plain)
        wfm.__dict__["turbulenceModel"] = STF2005TurbulenceModel()
        with self.assertRaises(fac.ClassMismatch) as ctx:
            fac.check_classes(fac.expected_classes(plain), wfm)
        self.assertEqual((ctx.exception.expected, ctx.exception.observed), (None, "STF2005TurbulenceModel"))
        self.assertTrue(issubclass(NOJDeficit, cat.resolve_class(cat.entry(cat.DEFICIT, "NiayifarGaussianDeficit"))))
        self.assertEqual(CGIRotorAvg.__name__, "CGIRotorAvg")

    def test_a_reader_failure_is_its_own_error(self):
        del self.wfm.wake_deficitModel.__dict__["groundModel"]
        with self.assertRaises(fac.ReaderError) as ctx:
            fac.check_classes(self.expected, self.wfm)
        self.assertEqual(ctx.exception.position, cat.GROUND)
        self.assertNotIsInstance(ctx.exception, fac.ClassMismatch)

    def test_an_accepted_adaptation_passes(self):
        # GaussianOverlap -> CGIRotorAvg(7) accepted by the user (decision 10): the configuration carries it.
        adapted = with_(self.config, rotor=C("CGIRotorAvg", n=7),
                        adaptations=({"position": "rotor", "requested": "GaussianOverlapAvgModel", "used": "CGIRotorAvg(n=7)"},))
        fac.check_classes(fac.expected_classes(adapted), build(adapted))


class ReadersTest(unittest.TestCase):
    def test_what_is_executed_is_read_from_the_objects(self):
        config = with_(cfg.default_config("PropagateUpDownIterative", "NOJLocalDeficit"), rotor=C("EqGridRotorAvg"),
                       turbulence=C("STF2017TurbulenceModel"), blockage=C("VortexCylinder", use_effective_ws=True),
                       blockage_superposition=C("MaxSum"))
        ex = rd.executed_config(build(config), config)
        self.assertEqual(ex["deficit"]["params"]["use_effective_ws"], {"value": True, "source": rd.OBSERVED})
        self.assertEqual(ex["deficit"]["params"]["ct2a"], {"value": "ct2a_madsen", "source": rd.OBSERVED})
        self.assertEqual(ex["rotor"], {"class": "EqGridRotorAvg", "params": {"n": {"value": 4, "source": rd.PASSED}},
                                       "nodes": 16})
        self.assertEqual(ex["blockage"]["params"]["use_effective_ws"]["value"], True)
        self.assertEqual(ex["blockage_superposition"]["class"], "MaxSum")
        self.assertEqual(ex["engine"]["params"]["max_iter"], {"value": 10, "source": rd.OBSERVED})
        self.assertIsNone(ex["ground"])
        self.assertEqual(rd.differences_vs_selection(ex, config), [])

    def test_every_argument_of_the_signatures_is_recorded(self):
        # Each class of every position, with all the arguments of its signature (P0, section 7), not only the ones
        # of the configuration: the deficit's rotor and ground, the blockage superposition and the engine's components
        # are positions of their own; the deprecated rotor of the engines is never passed.
        own = {cat.ENGINE: {"wake_deficitModel", "superpositionModel", "blockage_deficitModel", "turbulenceModel",
                            "rotorAvgModel"}, cat.DEFICIT: {"rotorAvgModel", "groundModel"},
               cat.BLOCKAGE: {"superpositionModel"}}
        base = cfg.default_config("All2AllIterative", "BastankhahGaussianDeficit")
        configs = [with_(cfg.default_config(engine, "NOJLocalDeficit"), turbulence=C("CrespoHernandez"))
                   for engine in ("PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative")]
        for e in cat.entries(cat.DEFICIT):
            configs.append(with_(cfg.default_config("All2AllIterative", e.name), turbulence=C("CrespoHernandez")))
        for position in (cat.ROTOR, cat.GROUND, cat.SUPERPOSITION, cat.TURBULENCE, cat.BLOCKAGE):
            for e in cat.entries(position):
                extra = {"blockage_superposition": C("LinearSum")} if position == cat.BLOCKAGE else {}
                configs.append(with_(base, **{position: C(e.name, **dict(e.fixed))}, **extra))
        for config in configs:
            ex = rd.executed_config(build(config), config)
            for position, entry in ex.items():
                if entry is None:
                    continue
                with self.subTest(position=position, cls=entry["class"]):
                    cls = fac.component_class(position, config.component(position))
                    names = set(rd._signature(cls)) - own.get(position, set())
                    self.assertEqual(set(entry["params"]), names)
        stf = with_(base, turbulence=C("STF2017TurbulenceModel"), superposition=C("WeightedSum"))
        ex = rd.executed_config(build(stf), stf)
        # A nested component (#64) is read recursively: its class observed, each argument with its source.
        self.assertEqual(ex["turbulence"]["params"]["weight_function"],
                         {"value": {"class": "FrandsenWeight", "params": {}}, "source": rd.OBSERVED})
        self.assertEqual(ex["turbulence"]["params"]["c"], {"value": [1.5, 0.8], "source": rd.OBSERVED})
        self.assertEqual(ex["turbulence"]["params"]["addedTurbulenceSuperpositionModel"]["value"]["class"], "LinearSum")
        self.assertEqual({k: v["value"] for k, v in ex["superposition"]["params"].items()},
                         {"delta": 0.01, "max_err": 0.001, "max_iter": 5, "weight_limit": 10000000000})
        mirror = with_(base, ground=C("MultiMirror", mirror_height=500.0))
        ex = rd.executed_config(build(mirror), mirror)
        # Read from its upper mirror (h_mirrors[1]), observed since the adversarial round of Q2.
        self.assertEqual(ex["ground"]["params"]["mirror_height"], {"value": 500.0, "source": rd.OBSERVED})

    def test_the_log_lines_carry_every_argument(self):
        config = with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"), rotor=C("EqGridRotorAvg"),
                       ground=C("MultiMirror"), turbulence=C("STF2017TurbulenceModel"), superposition=C("WeightedSum"),
                       blockage=C("SelfSimilarityDeficit2020"), blockage_superposition=C("LinearSum"))
        ex = rd.executed_config(build(config), config)
        lines = rd.executed_lines(ex)
        self.assertEqual(len(lines), len(cat.POSITIONS))
        for (position, entry), line in zip(ex.items(), lines):
            with self.subTest(position=position):
                self.assertTrue(line.startswith(f"{cat.position_label(position)}: {entry['class']}"))
                for name, arg in entry["params"].items():
                    value = rd._executed_text(arg["value"]) if isinstance(arg["value"], dict) else arg["value"]
                    self.assertIn(f"{name}={value}" + (" [argumento pasado]" if arg["source"] == rd.PASSED
                                                       else ""), line)
        self.assertIn("promedio de rotor: EqGridRotorAvg (n=4 [argumento pasado]); nodos: 16", lines)
        self.assertIn("turbulencia añadida: STF2017TurbulenceModel (c=[1.5, 0.8], addedTurbulenceSuperpositionModel=LinearSum, "
                      "weight_function=FrandsenWeight, rotorAvgModel=None, groundModel=None)", lines)

    def test_noj_k_is_observed_through_a(self):
        config = with_(cfg.default_config(deficit="NOJDeficit"), deficit=C("NOJDeficit", ct2a="ct2a_mom1d", k=0.04),
                       rotor=C("CGIRotorAvg", n=9))
        ex = rd.executed_config(build(config), config)
        self.assertEqual(ex["deficit"]["params"]["k"], {"value": 0.04, "source": rd.OBSERVED})
        self.assertEqual(ex["rotor"]["params"]["n"], {"value": 9, "source": rd.OBSERVED})

    def test_every_class_reads_back_its_configuration(self):
        for e in cat.entries(cat.DEFICIT):
            with self.subTest(deficit=e.name):
                config = cfg.default_config("All2AllIterative", e.name)
                if e.name in NEEDS_TI:
                    config = with_(config, turbulence=C("CrespoHernandez"))
                ex = rd.executed_config(build(config), config)
                self.assertEqual(rd.differences_vs_selection(ex, config), [])
                self.assertTrue(all(p["source"] == rd.OBSERVED for p in ex["deficit"]["params"].values()))
                self.assertEqual(cfg.WakeConfig.from_dict(config.to_dict()), config)

    def test_a_difference_with_the_selection_is_listed(self):
        config = cfg.default_config()
        wfm = build(config)
        wfm.wake_deficitModel.__dict__["_k"] = 0.05
        ex = rd.executed_config(wfm, config)
        self.assertEqual(rd.differences_vs_selection(ex, config),
                         [{"position": "deficit", "param": "k", "selected": 0.0324555, "executed": 0.05}])
        adapted = with_(config, rotor=C("CGIRotorAvg", n=7))
        self.assertEqual(rd.differences_vs_selection(rd.executed_config(build(adapted), adapted), config),
                         [{"position": "rotor", "param": None, "selected": None, "executed": "CGIRotorAvg"}])

    def test_an_unreadable_argument_is_a_reader_error(self):
        config = cfg.default_config()
        wfm = build(config)
        wfm.wake_deficitModel.__dict__["WS_key"] = "WS_jlk"
        with self.assertRaises(fac.ReaderError) as ctx:
            rd.executed_config(wfm, config)
        self.assertEqual(ctx.exception.position, "deficit")
        self.assertIn("WS_jlk", ctx.exception.diagnosis)
        # A missing attribute is not replaced by the value that was asked for.
        for attr in ("WS_key", "_k", "ct2a"):
            with self.subTest(attr=attr):
                wfm = build(config)
                del wfm.wake_deficitModel.__dict__[attr]
                with self.assertRaises(fac.ReaderError) as ctx:
                    rd.executed_config(wfm, config)
                self.assertEqual(ctx.exception.position, "deficit")
        eq = with_(config, rotor=C("EqGridRotorAvg"))
        wfm = build(eq)
        del wfm.wake_deficitModel.rotorAvgModel.__dict__["nodes_x"]
        with self.assertRaises(fac.ReaderError) as ctx:
            rd.executed_config(wfm, eq)
        self.assertEqual(ctx.exception.position, "rotor")


class MessagesTranslationsTest(unittest.TestCase):
    """Every message the validation, the factory and the class check give is translated, with its placeholders."""

    def test_every_message_is_translated(self):
        from unittest.mock import patch
        from VelantisWind import i18n
        from VelantisWind.ag_core.log_text import shown
        from VelantisWind.ag_core.wake_setup.messages_translations import SOURCES, TRANSLATIONS, register_messages_translations
        register_messages_translations()
        templates = set()
        configs = list(RulesTest.CASES.values())
        base = cfg.default_config()
        configs += [with_(base, engine=C("All2All")), with_(base, deficit=C("BastankhahGaussianDeficit", k=0.04)),
                    with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, kk=1))),
                    with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, k=float("nan")))),
                    with_(base, superposition=C("LinearSum", x=1)), with_(base, blockage_superposition=C("LinearSum")),
                    with_(base, rotor=C("GaussianOverlapAvgModel"))]
        with mock.patch.object(val, "missing_gaussian_overlap_modules", return_value=["h5py", "h5netcdf"]):
            issues = [i for c in configs for i in val.validate(c)]
        r2 = val.validate(cfg.default_config(deficit="BlondelSuperGaussianDeficit2023"))
        issues += r2
        issues += val.map_issues(with_(base, superposition=C("CumulativeWakeSum"), ground=C("Mirror")))
        issues += val.layout_issues(RulesTest.R9F, 2)
        issues += [i for sup in ("CumulativeWakeSum", "LinearSum") for bsup in ("SquaredSum", "WeightedSum")
                   for i in val.validate(with_(RulesTest.R9F, superposition=C(sup), blockage_superposition=C(bsup)))]
        for i in issues:
            templates.update(t for t in (i.message, i.resolution) if t and t != "{error}")
        for exc in (fac.FactoryError("deficit", "X", ValueError("x")), fac.ClassMismatch("rotor", None, "RotorCenter"),
                    fac.ReaderError("ground", "x")):
            templates.add(exc.args[0].template_item[0])
        from tests.pending_translations import PENDING  # translated in the final sweep (decision 7 of #64)
        self.assertLessEqual(templates - PENDING, set(SOURCES))
        for language, mapping in TRANSLATIONS.items():
            with self.subTest(language=language), patch.object(i18n, "current_language", return_value=language):
                for source in SOURCES:
                    target = mapping[source]
                    self.assertTrue(target.strip())
                    self.assertEqual(sorted(__import__("re").findall(r"\{[^}]*\}", source)),
                                     sorted(__import__("re").findall(r"\{[^}]*\}", target)))
                    self.assertEqual(i18n.tr_text(source), target)
                message = shown(fac.ClassMismatch("rotor", None, "RotorCenter").args[0], i18n.tr_text)
                self.assertNotIn("Comprobación", message)
                self.assertIn(mapping["promedio de rotor"], message)


def extended_configs():
    """Every deficit x engine x each class of each component (one at a time), as the extended diagnostic builds them."""
    out = []
    for de in cat.entries(cat.DEFICIT):
        for ee in cat.entries(cat.ENGINE):
            base = cfg.default_config(ee.name, de.name)
            params = dict(base.deficit.params)
            if ee.name == "PropagateUpDownIterative" and "use_effective_ws" in params:
                params["use_effective_ws"] = True
            base = with_(base, deficit=C(de.name, **params),
                         turbulence=C("STF2017TurbulenceModel") if params.get("use_effective_ti") else None)
            out.append(base)
            for pos in (cat.ROTOR, cat.GROUND, cat.SUPERPOSITION, cat.TURBULENCE):
                for e in ((None,) if pos != cat.SUPERPOSITION else ()) + cat.entries(pos):
                    out.append(with_(base, **{pos: C(e.name, **dict(e.fixed)) if e else None}))
            for e in (cat.entries(cat.BLOCKAGE) if ee.name != "PropagateDownwind" else cat.entries(cat.BLOCKAGE)[:1]):
                for bs in cat.entries(cat.BLOCKAGE_SUPERPOSITION):
                    for ews in (False, True):
                        out.append(with_(base, blockage=C(e.name, use_effective_ws=ews),
                                         blockage_superposition=C(bs.name)))
    return out


@unittest.skipUnless(os.environ.get("VELANTIS_DIAGNOSTICO") == "1", "diagnóstico extenso (VELANTIS_DIAGNOSTICO=1)")
class ExtendedRulesDiagnostic(unittest.TestCase):
    """Every deficit x engine x each class of each component (one at a time): validation <=> PyWake calculates; and
    the diagnostic matrix of the plan (decision 20). Several minutes each; outside the ordinary suite.

    The only exceptions of the first are the calculation errors of decision 8 (SquaredSum in the blockage with
    All2AllIterative when a speed-up appears).
    """

    def test_validation_matches_pywake(self):
        # Against PyWake written by hand (without the factory of the plugin), by the number of turbines (decision 6.1
        # of #64): with one and two (validate + layout_issues), and in the map with one (+ map_issues).
        from tests.test_wake_subordinates_fidelity import _stops
        mismatches = []
        for config in extended_configs():
            for n, mapped in ((1, False), (2, False), (1, True)):
                refused = bool(val.validate(config, check_environment=False) or val.layout_issues(config, n)
                               or (mapped and val.map_issues(config)))
                stops, err = _stops(config, n, mapped)
                if refused != stops:
                    decision_8 = (stops and config.blockage_superposition is not None
                                  and config.blockage_superposition.name == "SquaredSum" and "speedups" in err)
                    if not decision_8:
                        mismatches.append((config.to_dict(), n, mapped, err[:100]))
        self.assertEqual(mismatches, [])

    def test_the_diagnostic_matrix(self):
        """Each valid configuration (and each class with ct2a with the two functions), in a homogeneous case (a
        uniform site, a row with overlaps and a turbine in a free zone), a heterogeneous one (a wind rose, an
        irregular layout) and a mixed park (two turbine types): whether it converges, whether its values are finite
        and whether it depends on the order of the turbines (calculated again in the reverse order, the identifiers
        restored). The matrix is written to ``VELANTIS_DIAGNOSTICO_SALIDA`` (JSON lines) if given. It does not decide
        what is offered; what it finds is said: an order dependence must have its persistent warning (decision 19).
        """
        import json
        from py_wake.examples.data.iea37 import IEA37_WindTurbines
        from py_wake.site import UniformSite
        from py_wake.wind_turbines import WindTurbines
        from VelantisWind.ag_core.wake_setup.instrumentation import ConvergenceRecorder
        from VelantisWind.ag_core.wake_setup.notices import persistent_warnings
        wd, ws = np.arange(0.0, 360.0, 30.0), np.array([5.0, 9.0, 13.0])
        scenarios = {
            "homogeneous": (UniformSite(p_wd=[1 / 12] * 12, ti=0.08), V80(),
                            np.array([0.0, 400.0, 800.0, 1200.0, 4000.0]), np.array([0.0, 0.0, 0.0, 0.0, 3000.0]),
                            None),
            "heterogeneous": (SITE, V80(), np.array([0.0, 450.0, 1100.0, 300.0, 2600.0]),
                              np.array([0.0, 120.0, -80.0, 500.0, 1800.0]), None),
            "mixed": (SITE, WindTurbines.from_WindTurbine_lst([V80(), IEA37_WindTurbines()]),
                      np.array([0.0, 500.0, 1000.0, 300.0]), np.array([0.0, 0.0, 300.0, 700.0]),
                      np.array([0, 1, 0, 1])),
        }
        configs = [c for c in extended_configs() if not val.validate(c, check_environment=False)]
        for c in list(configs):
            if c.blockage is None and "ct2a" in c.deficit.params:  # the other function of ct2a
                other = "ct2a_mom1d" if c.deficit.params["ct2a"] == "ct2a_madsen" else "ct2a_madsen"
                configs.append(with_(c, deficit=C(c.deficit.name, **dict(c.deficit.params, ct2a=other))))
        out_path = os.environ.get("VELANTIS_DIAGNOSTICO_SALIDA")
        out = open(out_path, "w", encoding="utf-8") if out_path else None
        unwarned, unexpected, never_calculated = [], [], []
        try:
            for config in configs:
                calculated = expected_only = refused = 0
                for name, (site, wts, x, y, types) in scenarios.items():
                    if val.layout_issues(config, len(x)):
                        refused += 1  # refused from this number of turbines (decision 6.1 of #64)
                        continue
                    row = {"config": config.to_dict(), "scenario": name}
                    try:
                        wfm = fac.build_wind_farm_model(config, site, wts, ws_grid=ws)
                        kw = {} if types is None else {"type": types}
                        with ConvergenceRecorder() as rec:
                            aep = wfm(x, y, wd=wd, ws=ws, **kw).aep().sum(["wd", "ws"]).values
                        back = slice(None, None, -1)
                        kw = {} if types is None else {"type": types[back]}
                        reverse = wfm(x[back], y[back], wd=wd, ws=ws, **kw).aep().sum(["wd", "ws"]).values[back]
                        row.update(converged=all(e.get("converged") for e in rec.summary().values()),
                                   finite=bool(np.isfinite(aep).all()),
                                   order_dependent=not np.allclose(aep, reverse, rtol=1e-9, atol=0.0))
                    except Exception as exc:
                        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
                    # The only error a valid configuration may give here: decision 8 (SquaredSum in the blockage of
                    # All2AllIterative when a speed-up appears). Any other is a failure of the matrix, never a silent
                    # row.
                    if "error" in row:
                        decision_8 = (config.engine.name == "All2AllIterative" and config.blockage_superposition
                                      and config.blockage_superposition.name == "SquaredSum"
                                      and "speedups" in row["error"])
                        if decision_8:
                            expected_only += 1
                        else:
                            unexpected.append(row)
                    else:
                        calculated += 1
                    if row.get("order_dependent") and not persistent_warnings(config):
                        unwarned.append(row)
                    if out:
                        out.write(json.dumps(row) + "\n")
                # Each configuration is calculated in some case, unless all its errors are those of decision 8 or it is
                # refused with the turbines of each case.
                if not calculated and expected_only + refused < len(scenarios):
                    never_calculated.append(config.to_dict())
        finally:
            if out:
                out.close()
        self.assertEqual(unexpected, [])
        self.assertEqual(never_calculated, [])
        self.assertEqual(unwarned, [])


if __name__ == "__main__":
    unittest.main()
