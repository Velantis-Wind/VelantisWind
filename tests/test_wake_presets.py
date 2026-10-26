# -*- coding: utf-8 -*-
"""The predefined models of PyWake as fixed configurations of the manual mode (``ag_core/wake_setup/presets.py``)."""
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core.results import breakdown as bd
from VelantisWind.ag_core.results import variants as vr
from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, simulation_wind_turbines
from VelantisWind.ag_core.wake_setup import api
from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory as fac
from VelantisWind.ag_core.wake_setup import presets as ps
from VelantisWind.ag_core.wake_setup import subordinates as sub
from VelantisWind.ag_core.wake_setup import validation as val

warnings.filterwarnings("ignore", module="py_wake")
# The class of IEA37 warns that it is deprecated as a wind farm model (decision 7): expected here.
warnings.filterwarnings("ignore", message="The IEA37SimpleBastankhahGaussian model")

from py_wake import HorizontalGrid  # noqa: E402
from py_wake import literature as lit  # noqa: E402
from py_wake.deficit_models.gaussian import TurboGaussianDeficit  # noqa: E402
from py_wake.deficit_models.utils import ct2a_mom1d  # noqa: E402
from py_wake.ground_models import Mirror  # noqa: E402
from py_wake.rotor_avg_models import CGIRotorAvg  # noqa: E402
from py_wake.superposition_models import SquaredSum  # noqa: E402
from py_wake.deficit_models.gaussian import IEA37SimpleBastankhahGaussian  # noqa: E402
from py_wake.deficit_models.no_wake import NoWakeDeficit  # noqa: E402
from py_wake.superposition_models import LinearSum  # noqa: E402
from py_wake.turbulence_models.crespo import CrespoHernandez  # noqa: E402
from py_wake.wind_farm_models import PropagateDownwind  # noqa: E402

from tests.test_wake_setup_factory import SITE, WT, X, Y, WD, WS  # noqa: E402

TURBINES = simulation_wind_turbines(WT, WS, BIN_MEAN)  # the turbines the factory gives the engine
GRID = HorizontalGrid(x=np.linspace(-300, 1400, 4), y=np.linspace(-200, 500, 3))
TITLES = ("NOJ", "BastankhahGaussian", "IEA37SimpleBastankhahGaussian", "NiayifarGaussian", "ZongGaussian",
          "SuperGaussian", "TurbOPark")
# The PyWake class of each title, as PyWake 2.6.18 builds it, with the two exceptions of the definition (decisions 5, 6).
CLASSES = {
    "NOJ": lambda **kw: lit.Jensen_1983(SITE, TURBINES, **kw),
    "BastankhahGaussian": lambda **kw: lit.Bastankhah_PorteAgel_2014(SITE, TURBINES, k=0.0324555, **kw),
    "IEA37SimpleBastankhahGaussian": lambda **kw: IEA37SimpleBastankhahGaussian(SITE, TURBINES, **kw),
    "NiayifarGaussian": lambda **kw: lit.Niayifar_PorteAgel_2016(SITE, TURBINES, **kw),
    "ZongGaussian": lambda **kw: lit.Zong_PorteAgel_2020(SITE, TURBINES, **kw),
    "SuperGaussian": lambda **kw: lit.Blondel_Cathelain_2020(
        SITE, TURBINES, **dict({"turbulenceModel": CrespoHernandez()}, **kw)),
    "TurbOPark": lambda: lit.Nygaard_2022(SITE, TURBINES),  # its signature takes nothing else
}
WITH_TURBULENCE = ("NiayifarGaussian", "ZongGaussian", "SuperGaussian")


def results(wfm, n):
    sim = wfm(X[:n], Y[:n], wd=WD, ws=WS)
    fm = sim.flow_map(GRID, wd=270.0, ws=10.0)
    return {"WS_eff": sim.WS_eff.values, "TI_eff": sim.TI_eff.values, "AEP": sim.aep().values,
            "map WS_eff": fm.WS_eff.values, "map TI_eff": fm.TI_eff.values}


def aep_per_turbine(wfm):
    return wfm(X, Y, wd=WD, ws=WS).aep().sum(["wd", "ws"]).values


def build(target):
    if target is vr.FREE_STREAM:
        return fac.build_free_stream_model(CONFIGS[RUNNING[0]], SITE, WT, ws_grid=WS)
    return fac.build_wind_farm_model(target, SITE, WT, ws_grid=WS)


CONFIGS = {t: ps.config(t) for t in TITLES}
RUNNING = [None]


def _turbopark_cgi7():
    """Nygaard_2022 as PyWake 2.6.18 builds it, by hand (its signature takes no rotor), with CGIRotorAvg(7)."""
    deficit = TurboGaussianDeficit(ct2a=ct2a_mom1d, groundModel=Mirror(superpositionModel=SquaredSum()),
                                   rotorAvgModel=CGIRotorAvg(7), ctlim=0.96)
    deficit.WS_key = "WS_jlk"
    return PropagateDownwind(SITE, TURBINES, wake_deficitModel=deficit, superpositionModel=SquaredSum())


# The two presets with GaussianOverlapAvgModel adapted with «Continuar» (decision 17 of the predefined models), and
# their PyWake classes with the same adaptation.
ADAPTED = {t: api.gaussian_overlap_adaptation(CONFIGS[t], ["h5py"]) for t in ("NiayifarGaussian", "TurbOPark")}
ADAPTED_CLASSES = {
    "NiayifarGaussian": lambda **kw: lit.Niayifar_PorteAgel_2016(SITE, TURBINES,
                                                                 **dict({"rotorAvgModel": CGIRotorAvg(7)}, **kw)),
    "TurbOPark": _turbopark_cgi7,
}


class CatalogueTest(unittest.TestCase):
    def test_the_titles_in_the_order_of_the_page(self):
        self.assertEqual(ps.ids(), TITLES)
        self.assertEqual([p.url for p in ps.PRESETS], [ps.PAGE + "#" + t.lower() for t in TITLES])

    def test_every_argument_is_in_the_definition(self):
        # Nothing comes from the signatures of the installed PyWake: without them, the same configuration.
        def no_signature(*_):
            raise AssertionError("a signature was read")
        with mock.patch.object(cat, "signature_defaults", lambda e: {}), \
                mock.patch.object(sub, "signature_default", no_signature):
            built = {t: ps.config(t) for t in TITLES}
        for t in TITLES:
            with self.subTest(preset=t):
                self.assertEqual(built[t], CONFIGS[t])
                self.assertEqual({k: v for k, v in built[t].to_dict().items()
                                  if k not in ("schema", "version", "adaptations")}, dict(ps.preset(t).definition))

    def test_two_configurations_are_independent(self):
        for t in TITLES:
            with self.subTest(preset=t):
                a, b = ps.config(t), ps.config(t)
                self.assertEqual(a, b)
                # Every list, also of a nested component, changed in a only.
                lists = [v for comp in (a.deficit, a.turbulence) if comp for v in comp.params.values()
                         if isinstance(v, list)]
                for v in lists:
                    v.append(1.0)
                self.assertEqual(a != b, bool(lists))
                self.assertEqual(b, CONFIGS[t])
                self.assertEqual(ps.config(t), CONFIGS[t])
                if a.turbulence is not None:
                    # The arguments of a component and of its nested ones, changed in a only.
                    a.turbulence.params["c"] = None
                    a.turbulence.params["rotorAvgModel"].params["x"] = 1
                    self.assertEqual(b, CONFIGS[t])
                    self.assertEqual(ps.config(t), CONFIGS[t])
                    self.assertEqual(dict(b.turbulence.params["rotorAvgModel"].params), {})

    def test_valid_and_round_trips(self):
        for t in TITLES:
            with self.subTest(preset=t):
                c = ps.config(t)
                self.assertEqual(val.validate(c), [])
                self.assertEqual(val.layout_issues(c, 4), [])
                self.assertEqual(val.map_issues(c, 4), [])
                self.assertEqual(cfg.WakeConfig.from_dict(c.to_dict()), c)
                self.assertEqual(api.resolve_request(api.to_wake_physics(c)), (c, None))

    def test_the_provenance(self):
        import py_wake
        p = ps.provenance("SuperGaussian")
        self.assertEqual(p, {"preset": "SuperGaussian", "revision": 1,
                             "reference_class": "py_wake.literature.gaussian_models.Blondel_Cathelain_2020",
                             "reference_version": "2.6.18", "executed_version": py_wake.__version__,
                             "url": ps.PAGE + "#supergaussian", "notes": [ps.SUPERGAUSSIAN_NOTE]})
        self.assertEqual(ps.provenance("BastankhahGaussian")["notes"], [ps.K_NOTE])
        self.assertEqual(ps.provenance("IEA37SimpleBastankhahGaussian")["notes"], [ps.DEPRECATED_NOTE])
        self.assertEqual(ps.provenance("NOJ")["notes"], [])
        ps.provenance("NOJ")["notes"].append("x")
        self.assertEqual(ps.preset("NOJ").notes, ())
        with self.assertRaises(KeyError):
            ps.config("Fuga")


class FidelityTest(unittest.TestCase):
    """Each preset, built by the factory, is its PyWake class bit for bit, with 1, 2 and 4 turbines."""

    def test_each_preset_is_its_pywake_class(self):
        for t in TITLES:
            for n in (1, 2, 4):
                with self.subTest(preset=t, n=n):
                    ours = results(build(CONFIGS[t]), n)
                    theirs = results(CLASSES[t](), n)
                    for k in theirs:
                        self.assertTrue(np.array_equal(ours[k], theirs[k], equal_nan=True), k)

    def test_each_adapted_preset_is_its_pywake_class_with_the_same_adaptation(self):
        for t, config in ADAPTED.items():
            for n in (1, 2, 4):
                with self.subTest(preset=t, n=n):
                    ours = results(build(config), n)
                    theirs = results(ADAPTED_CLASSES[t](), n)
                    for k in theirs:
                        self.assertTrue(np.array_equal(ours[k], theirs[k], equal_nan=True), k)
            # Not the preset: with wakes, GaussianOverlapAvgModel and CGIRotorAvg(7) differ.
            self.assertFalse(np.array_equal(results(build(config), 4)["WS_eff"],
                                            results(build(CONFIGS[t]), 4)["WS_eff"]), t)


class VariantsTest(unittest.TestCase):
    """The terms of the breakdown of each preset, against PyWake directly with the same intervention."""

    def breakdown(self, t, compute_variants=True, run=None, config=None):
        RUNNING[0] = t
        self.addCleanup(RUNNING.__setitem__, 0, None)
        config = config or CONFIGS[t]
        return vr.run_breakdown(config, aep_per_turbine(build(config)), run or (lambda c: aep_per_turbine(
            build(c))), compute_variants=compute_variants,
            turbulence_reaches_deficit=vr.turbulence_changes_deficit(fac.build_deficit(config)))

    def test_the_terms_and_their_states(self):
        for t in TITLES:
            with self.subTest(preset=t):
                aep, states, _, errors = self.breakdown(t)
                self.assertEqual(errors, {})
                self.assertEqual(states["A_WB"], bd.NOT_MODELLED)
                # A_0: NoWakeDeficit and LinearSum, without rotor, ground nor turbulence, as PyWake directly.
                self.assertTrue(np.array_equal(aep["A_0"], aep_per_turbine(
                    PropagateDownwind(SITE, TURBINES, NoWakeDeficit(), superpositionModel=LinearSum()))))
                if t in WITH_TURBULENCE:
                    # A_WT is the main one; A_W, without turbulence and with use_effective_ti=False.
                    self.assertIs(aep["A_WT"], aep["A_WTB"])
                    self.assertTrue(np.array_equal(aep["A_W"], aep_per_turbine(
                        CLASSES[t](turbulenceModel=None, use_effective_ti=False))))
                    self.assertFalse(np.array_equal(aep["A_W"], aep["A_WTB"]))
                else:
                    self.assertIs(aep["A_W"], aep["A_WTB"])
                    self.assertEqual(states["A_WT"], bd.NOT_MODELLED)
                self.assertTrue(np.array_equal(aep["A_WTB"], aep_per_turbine(CLASSES[t]())))

    def test_the_terms_of_the_adapted_presets(self):
        # The breakdown starts from the adapted configuration: CGIRotorAvg(7) in the variants that keep the deficit,
        # never GaussianOverlapAvgModel again; A_0 without rotor, ground, turbulence nor the reference of the scaling.
        for t, config in ADAPTED.items():
            with self.subTest(preset=t):
                aep, states, _, errors = self.breakdown(t, config=config)
                self.assertEqual(errors, {})
                self.assertTrue(np.array_equal(aep["A_0"], aep_per_turbine(
                    PropagateDownwind(SITE, TURBINES, NoWakeDeficit(), superpositionModel=LinearSum()))))
                self.assertTrue(np.array_equal(aep["A_WTB"], aep_per_turbine(ADAPTED_CLASSES[t]())))
                for name, variant in vr.variant_configs(config).items():
                    if variant is not None:
                        self.assertEqual(variant.rotor, cfg.Component("CGIRotorAvg", {"n": 7}), name)
                if t in WITH_TURBULENCE:
                    self.assertIs(aep["A_WT"], aep["A_WTB"])
                    self.assertTrue(np.array_equal(aep["A_W"], aep_per_turbine(
                        ADAPTED_CLASSES[t](turbulenceModel=None, use_effective_ti=False))))
                else:
                    self.assertIs(aep["A_W"], aep["A_WTB"])
                    self.assertEqual(states["A_WT"], bd.NOT_MODELLED)

    def test_without_compute_variants(self):
        for t in WITH_TURBULENCE:
            with self.subTest(preset=t):
                _, states, _, _ = self.breakdown(t, compute_variants=False)
                self.assertEqual((states["A_W"], states["A_WT"], states["A_0"]), (bd.NOT_REQUESTED, bd.OK, bd.OK))

    def test_a_failed_variant(self):
        def run(target):
            if target is not vr.FREE_STREAM:
                raise RuntimeError("forzado")
            return aep_per_turbine(build(target))
        aep, states, _, errors = self.breakdown("NiayifarGaussian", run=run)
        self.assertEqual((states["A_W"], states["A_0"], states["A_WT"]), (bd.FAILED, bd.OK, bd.OK))
        self.assertIsNone(aep["A_W"])
        self.assertIn("forzado", errors["A_W"])


if __name__ == "__main__":
    unittest.main()
