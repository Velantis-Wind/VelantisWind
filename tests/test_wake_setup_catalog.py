# -*- coding: utf-8 -*-
"""The wake catalogue and the configuration contract (``ag_core/wake_setup``, #46 P1a)."""
import json
import unittest
from unittest.mock import patch

from VelantisWind import i18n
from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup.catalog_translations import TRANSLATIONS, register_catalog_translations

# The signatures of PyWake 2.6.18 (README of the plan, «Catálogo»; evidencias/catalogo_clases/firmas.salida.txt).
DEFICITS = {
    "BastankhahGaussianDeficit": ({"ct2a": "ct2a_madsen", "k": 0.0324555, "ceps": 0.2, "ctlim": 0.899,
                                   "use_effective_ws": False}, None, None),
    "NiayifarGaussianDeficit": ({"ct2a": "ct2a_madsen", "a": [0.38, 0.004], "ceps": 0.2, "ctlim": 0.899,
                                 "use_effective_ws": False, "use_effective_ti": True}, None, None),
    "ZongGaussianDeficit": ({"ct2a": "ct2a_madsen", "a": [0.38, 0.004], "ctlim": 0.899, "deltawD": 2 ** -0.5,
                             "eps_coeff": 8 ** -0.5, "lam": 7.5, "B": 3, "use_effective_ws": False,
                             "use_effective_ti": True}, None, None),
    "CarbajofuertesGaussianDeficit": ({"ct2a": "ct2a_madsen", "a": [0.35, 0.0], "ceps": [-1.91, 0.34],
                                       "use_effective_ws": False, "use_effective_ti": True}, None, None),
    "TurboGaussianDeficit": ({"ct2a": "ct2a_madsen", "A": 0.04, "cTI": [1.5, 0.8], "ceps": 0.25, "ctlim": 0.999,
                              "use_effective_ws": False, "use_effective_ti": False}, None, "Mirror"),
    "BlondelSuperGaussianDeficit2020": ({"a_s": 0.17, "b_s": 0.005, "c_s": 0.2, "b_f": -0.68, "c_f": 2.41,
                                         "ctlim": 0.999, "use_effective_ws": False, "use_effective_ti": True},
                                        None, None),
    "BlondelSuperGaussianDeficit2023": ({"a_s": 0.28, "b_s": 0.01, "c_s": [0.1, 0.1], "b_f": [-25.98, -1.06],
                                         "c_f": 2, "ctlim": 0.999, "use_effective_ws": False,
                                         "use_effective_ti": True}, None, None),
    "IEA37SimpleBastankhahGaussianDeficit": ({}, None, None),
    "GCLDeficit": ({"use_effective_ws": False, "use_effective_ti": False}, None, None),
    "NOJDeficit": ({"ct2a": "ct2a_madsen", "k": 0.1}, "AreaOverlapAvgModel", None),
    "NOJLocalDeficit": ({"ct2a": "ct2a_madsen", "a": [0.38, 0.004], "use_effective_ws": True,
                         "use_effective_ti": True}, "AreaOverlapAvgModel", None),
    "TurboNOJDeficit": ({"ct2a": "ct2a_madsen", "A": 0.6, "cTI": [1.5, 0.8], "use_effective_ws": False,
                         "use_effective_ti": False}, "AreaOverlapAvgModel", None),
}
BLOCKAGES = ("SelfSimilarityDeficit2020", "SelfSimilarityDeficit", "VortexCylinder", "VortexDipole", "HybridInduction",
             "RankineHalfBody", "Rathmann", "RathmannScaled")


class CatalogueTest(unittest.TestCase):
    def test_every_option_is_its_own_exact_pywake_class(self):
        for position in cat.POSITIONS:
            for e in cat.entries(position):
                with self.subTest(position=position, option=e.option):
                    cls = cat.resolve_class(e)
                    self.assertEqual(cls.__name__, e.name)
                    self.assertTrue(cls.__module__.startswith("py_wake."), cls.__module__)
                    self.assertTrue(e.help)
        for name in cat.CT2A_FUNCTIONS:
            self.assertEqual(cat.resolve_ct2a(name).__name__, name)
        # SelfSimilarityDeficit and SelfSimilarityDeficit2020 are two classes (#75, row 3.7).
        a, b = (cat.resolve_class(cat.entry(cat.BLOCKAGE, n)) for n in ("SelfSimilarityDeficit", "SelfSimilarityDeficit2020"))
        self.assertIsNot(a, b)

    def test_the_twelve_deficits_have_the_signatures_of_the_plan(self):
        self.assertEqual([e.name for e in cat.entries(cat.DEFICIT)], list(DEFICITS))
        for name, (params, rotor, ground) in DEFICITS.items():
            with self.subTest(deficit=name):
                d, r, g = cfg.deficit_signature(name)
                self.assertEqual(list(d.params), list(params))  # every editable argument, in signature order
                for p, v in params.items():
                    if isinstance(v, float):
                        self.assertAlmostEqual(d.params[p], v, places=15)
                    else:
                        self.assertEqual(d.params[p], v)
                self.assertEqual(r.name if r else None, rotor)
                self.assertEqual(g.name if g else None, ground)
                e = cat.entry(cat.DEFICIT, name)
                defaults = cat.signature_defaults(e)
                # Everything editable in the signature is offered, except the rotor and ground (their own selectors).
                self.assertEqual(set(e.params), set(defaults) - {"rotorAvgModel", "groundModel"})
                for p in e.params:
                    self.assertIn(cat.param_kind(defaults[p]), ("bool", "ct2a", "list", "number"))

    def test_engines_and_blockage_defaults_come_from_their_signatures(self):
        self.assertEqual([e.name for e in cat.entries(cat.ENGINE)],
                         ["PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"])
        for e in cat.entries(cat.ENGINE):
            with self.subTest(engine=e.name):
                s = cfg.engine_signature(e.name)
                self.assertEqual(s[cat.SUPERPOSITION], cfg.Component("LinearSum", {}))
                self.assertIsNone(s[cat.TURBULENCE])
                self.assertIsNone(s[cat.BLOCKAGE])
        self.assertEqual([e.name for e in cat.entries(cat.BLOCKAGE)], list(BLOCKAGES))
        for name in BLOCKAGES:
            self.assertEqual(cfg.blockage_signature(name), cfg.complete(cfg.Component(name, {"use_effective_ws": False})))

    def test_component_options(self):
        self.assertEqual([e.option for e in cat.entries(cat.ROTOR)],
                         ["RotorCenter", "CGIRotorAvg", "EqGridRotorAvg",
                          "GaussianOverlapAvgModel", "AreaOverlapAvgModel"])
        self.assertEqual([e.name for e in cat.entries(cat.GROUND)], ["Mirror", "MultiMirror"])
        self.assertEqual([e.name for e in cat.entries(cat.SUPERPOSITION)],
                         ["LinearSum", "SquaredSum", "MaxSum", "WeightedSum", "CumulativeWakeSum"])
        self.assertNotIn("AUTO", [e.name for e in cat.entries(cat.SUPERPOSITION)])
        self.assertEqual([e.name for e in cat.entries(cat.TURBULENCE)],
                         ["STF2005TurbulenceModel", "STF2017TurbulenceModel", "GCLTurbulence", "CrespoHernandez"])
        self.assertEqual([e.name for e in cat.entries(cat.BLOCKAGE_SUPERPOSITION)],
                         ["LinearSum", "MaxSum", "SquaredSum", "WeightedSum", "CumulativeWakeSum"])
        # The persistent warnings of decision 19.
        self.assertTrue(cat.entry(cat.SUPERPOSITION, "CumulativeWakeSum").warning)
        with_warning = {e.name for e in cat.entries(cat.BLOCKAGE) if e.warning}
        self.assertEqual(with_warning, {"VortexCylinder", "VortexDipole", "HybridInduction", "RankineHalfBody",
                                        "Rathmann", "RathmannScaled"})
        with self.assertRaises(KeyError):
            cat.entry(cat.ROTOR, "CGIRotorAvg", {"n": 4})
        # The options PyWake cannot calculate in the blockage superposition say why (R6).
        for name in ("WeightedSum", "CumulativeWakeSum"):
            self.assertIn("única matriz", cat.entry(cat.BLOCKAGE_SUPERPOSITION, name).help)

    def test_a_class_missing_from_pywake_is_unavailable_not_replaced(self):
        e = cat.ClassEntry(cat.DEFICIT, "NoSuchDeficit", "py_wake.deficit_models.gaussian", "x")
        with self.assertRaises(cat.ClassUnavailable):
            cat.resolve_class(e)
        e = cat.ClassEntry(cat.DEFICIT, "NoSuchDeficit", "py_wake.no_such_module", "x")
        with self.assertRaises(cat.ClassUnavailable):
            cat.resolve_class(e)


class ConfigTest(unittest.TestCase):
    def test_the_default_physics_is_the_one_of_decision_14(self):
        d = cfg.default_config()
        self.assertEqual(d.engine.name, "PropagateDownwind")
        self.assertEqual(d.deficit, cfg.deficit_signature("BastankhahGaussianDeficit")[0])
        self.assertEqual((d.rotor, d.ground, d.turbulence, d.blockage, d.blockage_superposition),
                         (None, None, None, None, None))
        self.assertEqual(d.superposition.name, "LinearSum")
        self.assertEqual(cfg.differences_vs_signature(d), [])
        self.assertEqual(cfg.identification(d), "BastankhahGaussianDeficit · motor PropagateDownwind · superposición "
                                                 "LinearSum · turbulencia ninguna · bloqueo ninguno · valores de su firma")
        self.assertNotIn("preset", cfg.identification(d).lower())

    def test_round_trip_through_json(self):
        base = cfg.default_config("All2AllIterative", "TurboGaussianDeficit")
        c = cfg.WakeConfig(
            engine=base.engine, deficit=cfg.Component("TurboGaussianDeficit", dict(base.deficit.params, ct2a="ct2a_mom1d", ctlim=0.96)),
            rotor=cfg.Component("CGIRotorAvg", {"n": 9}), ground=base.ground, superposition=cfg.Component("SquaredSum"),
            turbulence=cfg.Component("STF2017TurbulenceModel"), blockage=cfg.Component("VortexDipole", {"use_effective_ws": True}),
            blockage_superposition=cfg.Component("MaxSum"),
            adaptations=({"position": "rotor", "requested": "GaussianOverlapAvgModel", "used": "CGIRotorAvg(n=7)"},))
        data = json.loads(json.dumps(c.to_dict()))
        self.assertEqual(data["schema"], cfg.WAKE_CONFIG_SCHEMA)
        self.assertEqual(data["version"], 2)
        self.assertEqual(cfg.WakeConfig.from_dict(data), c)

    def test_a_malformed_dictionary_is_refused(self):
        good = cfg.default_config().to_dict()
        # Version 3 exists since the predefined models (M4, deficit_ws_reference): 4 is not one.
        for change in ({"version": 4}, {"version": 0}, {"version": True}, {"version": 1.0}, {"version": "1"}, {"schema": "other"}, {"extra": 1}, {"deficit": None}, {"engine": "PDW"},
                       {"rotor": {"class": "RotorCenter", "params": [], }}, {"adaptations": "x"}):
            with self.subTest(change=change):
                with self.assertRaises(cfg.ConfigFormatError):
                    cfg.WakeConfig.from_dict(dict(good, **change))
        with self.assertRaises(cfg.ConfigFormatError):
            cfg.WakeConfig.from_dict({**good, 1: "x"})
        big = dict(good, deficit={"class": good["deficit"]["class"], "params": dict(good["deficit"]["params"], k=10 ** 400)})
        self.assertEqual(cfg.WakeConfig.from_dict(big).deficit.params["k"], 10 ** 400)  # finite: the validation decides
        missing = dict(good)
        del missing["turbulence"]
        with self.assertRaises(cfg.ConfigFormatError):
            cfg.WakeConfig.from_dict(missing)
        # A configuration is complete: what a dictionary leaves out takes the signature (#64, two phases), and an
        # argument a class does not have is refused.
        deficit = good["deficit"]
        read = cfg.WakeConfig.from_dict(dict(good, deficit={"class": deficit["class"], "params": {"k": 0.04}}))
        self.assertEqual(read.deficit.params, dict(cfg.default_config().deficit.params, k=0.04))
        with self.assertRaises(cfg.ConfigFormatError):
            cfg.WakeConfig.from_dict(dict(good, deficit={"class": deficit["class"], "params": dict(deficit["params"], kk=1)}))
        self.assertEqual(cfg.WakeConfig.from_dict(dict(good, rotor={"class": "CGIRotorAvg", "params": {}})).rotor,
                         cfg.Component("CGIRotorAvg", {"n": 7}))
        # Values that the dictionary form cannot carry: objects, and a mapping where a value goes. NaN and infinities
        # it carries: they reach PyWake as given (decision 5 of #64).
        for value in (object(), {"a": 1}):
            with self.subTest(value=value):
                with self.assertRaises(cfg.ConfigFormatError):
                    cfg.WakeConfig.from_dict(dict(good, deficit={"class": deficit["class"],
                                                                 "params": dict(deficit["params"], k=value)}))
        for value in (float("nan"), float("inf"), float("-inf"), [0.1, float("nan")]):
            with self.subTest(value=value):
                read = cfg.WakeConfig.from_dict(dict(good, deficit={"class": deficit["class"],
                                                                    "params": dict(deficit["params"], k=value)}))
                self.assertTrue(cfg.same_value(read.deficit.params["k"], value))
        with self.subTest(adaptation=object()):
            with self.assertRaises(cfg.ConfigFormatError):
                cfg.WakeConfig.from_dict(dict(good, adaptations=[{"position": "rotor", "used": object()}]))
        for value in (float("nan"), float("inf")):
            with self.subTest(adaptation=value):
                read = cfg.WakeConfig.from_dict(dict(good, adaptations=[{"position": "rotor", "used": value}]))
                self.assertTrue(cfg.same_value(read.adaptations[0]["used"], value))
                self.assertEqual(cfg.WakeConfig.from_dict(json.loads(json.dumps(read.to_dict()))), read)
        self.assertEqual(cfg.WakeConfig.from_dict(dict(good, adaptations=[{"position": "rotor", "requested": None}])).adaptations,
                         ({"position": "rotor", "requested": None},))
        # An explicit None in an argument goes through the dictionary form as it is.
        with_none = dict(good, deficit={"class": deficit["class"], "params": dict(deficit["params"], use_effective_ws=None)})
        self.assertEqual(cfg.WakeConfig.from_dict(with_none).to_dict(), with_none)
        # An unknown class is not a format error: the validation rejects it with its own reason (R14).
        self.assertEqual(cfg.WakeConfig.from_dict(dict(good, deficit={"class": "Otra", "params": {"x": 1}})).deficit.name,
                         "Otra")

    def test_differences_with_the_signatures(self):
        base = cfg.default_config("All2AllIterative", "NOJDeficit")
        self.assertEqual(base.rotor, cfg.Component("AreaOverlapAvgModel"))
        c = cfg.WakeConfig(
            engine=base.engine, deficit=cfg.Component("NOJDeficit", {"ct2a": "ct2a_madsen", "k": 0.04}), rotor=None,
            ground=None, superposition=cfg.Component("SquaredSum"), turbulence=None,
            blockage=cfg.Component("SelfSimilarityDeficit2020", {"use_effective_ws": False}),
            blockage_superposition=cfg.Component("LinearSum"))
        diffs = {(d["position"], d["param"]): (d["signature"], d["value"]) for d in cfg.differences_vs_signature(c)}
        self.assertEqual(diffs, {("deficit", "k"): (0.1, 0.04), ("rotor", None): ("AreaOverlapAvgModel", None),
                                 ("superposition", None): ("LinearSum", "SquaredSum"),
                                 ("blockage", None): (None, "SelfSimilarityDeficit2020")})
        text = cfg.identification(c)
        self.assertIn("salvo: k = 0.04", text)
        # The blockage superposition by default is an explicit LinearSum (decision 8); another one is a difference.
        c2 = cfg.WakeConfig(**{**c.__dict__, "blockage_superposition": cfg.Component("MaxSum")})
        self.assertIn(("blockage_superposition", None),
                      {(d["position"], d["param"]) for d in cfg.differences_vs_signature(c2)})

    def test_a_signature_default_outside_the_catalogue_is_an_error(self):
        from py_wake.rotor_avg_models import GQGridRotorAvg
        with self.assertRaises(TypeError):
            cfg.component_from_object(cat.ROTOR, GQGridRotorAvg())
        self.assertEqual(cfg.plain_value(cat.resolve_ct2a("ct2a_mom1d")), "ct2a_mom1d")


class TranslationsTest(unittest.TestCase):
    def setUp(self):
        register_catalog_translations()

    def test_every_catalogue_text_is_translated_in_the_three_languages(self):
        sources = set(cat.texts())
        for language, mapping in TRANSLATIONS.items():
            with self.subTest(language=language):
                self.assertEqual(set(mapping), sources)
                with patch.object(i18n, "current_language", return_value=language):
                    for source, target in mapping.items():
                        self.assertTrue(target.strip())
                        self.assertEqual(i18n.tr_text(source), target)
                        self.assertEqual(target.count("{"), source.count("{"))


if __name__ == "__main__":
    unittest.main()
