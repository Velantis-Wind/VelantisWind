# -*- coding: utf-8 -*-
"""The arguments of the subordinate objects in the configuration, the factory and what was executed (#64, Q2).

The configuration carries them, nested where an argument is another PyWake class, completed with the signatures for
what it leaves out; version 1 of the contract (#46a) is read and completed without changing what it said. The factory
builds every nested object new, with exactly its arguments, and gives the engine its own; what was executed is read
back recursively, with the source of each argument; the report shows both forms.
"""
import json
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core.results.model_config_html import _component_text
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import factory as fac
from VelantisWind.ag_core.wake_setup import readers as rd
from VelantisWind.ag_core.wake_setup import subordinates as sub
from VelantisWind.ag_core.wake_setup import validation as val
from tests.test_wake_setup_factory import SITE, WT, WS, C, build, codes, simulate, with_

warnings.filterwarnings("ignore", module="py_wake")

from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit, NiayifarGaussianDeficit  # noqa: E402
from py_wake.superposition_models import LinearSum  # noqa: E402
from py_wake.wind_farm_models import All2AllIterative as A2A  # noqa: E402

# A configuration of #46a as its version 1 wrote it: no argument of the subordinate objects.
V1 = {"schema": "velantis.wake_config", "version": 1,
      "engine": {"class": "All2AllIterative", "params": {}},
      "deficit": {"class": "NiayifarGaussianDeficit", "params": dict(cfg.default_config(
          deficit="NiayifarGaussianDeficit").deficit.params)},
      "rotor": {"class": "CGIRotorAvg", "params": {"n": 9}}, "ground": {"class": "Mirror", "params": {}},
      "superposition": {"class": "WeightedSum", "params": {}},
      "turbulence": {"class": "CrespoHernandez", "params": {}},
      "blockage": {"class": "SelfSimilarityDeficit2020", "params": {"use_effective_ws": True}},
      "blockage_superposition": {"class": "LinearSum", "params": {}}, "adaptations": []}


def full():
    """A configuration with edited arguments at every level."""
    base = cfg.default_config("All2AllIterative", "BastankhahGaussianDeficit")
    return with_(base, engine=C("All2AllIterative", convergence_tolerance=1e-3),
                 ground=C("MultiMirror", n_reps=1, superpositionModel=C("SquaredSum")),
                 turbulence=C("STF2017TurbulenceModel", c=[1.5, 1.6], weight_function=C("IECWeight", distance_limit=20),
                              rotorAvgModel=C("EqGridRotorAvg", n=2)),
                 blockage=C("SelfSimilarityDeficit2020", use_effective_ws=False, limiter=1e-6,
                            rotorAvgModel=C("EqGridRotorAvg", n=3)),
                 blockage_superposition=C("LinearSum"))


class ContractTest(unittest.TestCase):
    def test_version_1_is_completed_without_changing_what_it_said(self):
        c = cfg.WakeConfig.from_dict(V1)
        self.assertEqual(c.rotor, C("CGIRotorAvg", n=9))
        self.assertEqual(c.ground, C("Mirror", superpositionModel=None))  # it still inherits
        self.assertEqual(c.engine.params, {"convergence_tolerance": 1e-06})
        self.assertEqual(c.superposition.params, {"delta": 0.01, "max_err": 0.001, "max_iter": 5, "weight_limit": 1e10})
        self.assertEqual(c.turbulence.params["rotorAvgModel"], C("AreaOverlapAvgModel"))
        self.assertEqual(c.turbulence.params["addedTurbulenceSuperpositionModel"], C("SqrMaxSum"))
        self.assertTrue(c.blockage.params["use_effective_ws"])
        self.assertEqual(c.blockage.params["limiter"], 1e-10)
        # The same as the configuration of #46a built in memory: the signatures complete both the same way.
        same = with_(cfg.default_config("All2AllIterative", "NiayifarGaussianDeficit"), rotor=C("CGIRotorAvg", n=9),
                     ground=C("Mirror"), superposition=C("WeightedSum"), turbulence=C("CrespoHernandez"),
                     blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True),
                     blockage_superposition=C("LinearSum"))
        self.assertEqual(c, same)
        self.assertEqual(c.to_dict()["version"], 2)

    def test_version_2_round_trip_with_nested_components(self):
        c = full()
        data = json.loads(json.dumps(c.to_dict()))
        self.assertEqual(data["ground"]["params"]["superpositionModel"], {"class": "SquaredSum", "params": {}})
        self.assertEqual(cfg.WakeConfig.from_dict(data), c)

    def test_a_dictionary_is_completed_then_exact(self):
        data = full().to_dict()
        del data["turbulence"]["params"]["weight_function"]
        self.assertEqual(cfg.WakeConfig.from_dict(data).turbulence.params["weight_function"], C("FrandsenWeight"))
        data["turbulence"]["params"]["weight_function"] = {"class": "IECWeight", "params": {"kk": 1}}
        with self.assertRaises(cfg.ConfigFormatError):
            cfg.WakeConfig.from_dict(data)
        data["turbulence"]["params"]["weight_function"] = {"class": "LinearSum", "params": {}}  # another family
        with self.assertRaises(cfg.ConfigFormatError):
            cfg.WakeConfig.from_dict(data)
        data["turbulence"]["params"]["weight_function"] = None  # kept by the reading; PyWake refuses it when building
        read = cfg.WakeConfig.from_dict(data)
        self.assertIsNone(read.turbulence.params["weight_function"])
        self.assertEqual(codes(read), ["build"])

    def test_a_configuration_in_memory_is_completed_as_a_dictionary_is(self):
        empty = with_(cfg.default_config(), deficit=C("BastankhahGaussianDeficit"),
                      blockage=C("VortexDipole"), engine=C("All2AllIterative"), blockage_superposition=C("LinearSum"))
        self.assertEqual(empty.deficit, cfg.default_config().deficit)
        self.assertEqual(empty.blockage, cfg.blockage_signature("VortexDipole"))
        self.assertEqual(cfg.WakeConfig.from_dict(empty.to_dict()), empty)

    def test_version_1_with_each_cgi_and_the_same_calculation(self):
        for n in (7, 9, 21):
            with self.subTest(n=n):
                data = json.loads(json.dumps(V1))
                data["rotor"]["params"]["n"] = n
                self.assertEqual(cfg.WakeConfig.from_dict(data).rotor, C("CGIRotorAvg", n=n))
        # The same AEP, bit for bit, as PyWake built by hand with the signature values (what #46a built).
        from py_wake.deficit_models.gaussian import NiayifarGaussianDeficit
        from py_wake.rotor_avg_models import CGIRotorAvg
        from py_wake.superposition_models import WeightedSum
        from py_wake.turbulence_models import CrespoHernandez
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import All2AllIterative
        from tests.test_wake_setup_factory import direct
        data = json.loads(json.dumps(V1))
        data["ground"] = None  # WeightedSum takes no ground (R9)
        c = cfg.WakeConfig.from_dict(data)
        self.assertEqual(codes(c), [])
        hand = direct(All2AllIterative, NiayifarGaussianDeficit(rotorAvgModel=CGIRotorAvg(9)),
                      superpositionModel=WeightedSum(), turbulenceModel=CrespoHernandez(),
                      blockage_deficitModel=SelfSimilarityDeficit2020(use_effective_ws=True,
                                                                      superpositionModel=LinearSum()))
        self.assertTrue(np.array_equal(simulate(build(c)).aep().values, simulate(hand).aep().values))

    def test_the_differences_with_the_signature_give_their_route(self):
        diffs = {(d["position"], d["param"]) for d in cfg.differences_vs_signature(full())}
        self.assertIn(("engine", "convergence_tolerance"), diffs)
        self.assertIn(("ground", "superpositionModel"), diffs)
        self.assertIn(("turbulence", "weight_function"), diffs)
        self.assertIn(("turbulence", "rotorAvgModel"), diffs)
        self.assertIn(("blockage", "rotorAvgModel"), diffs)
        edited = with_(full(), turbulence=C("STF2017TurbulenceModel", weight_function=C("IECWeight", distance_limit=20)))
        self.assertIn(("turbulence", "weight_function · distance_limit"),
                      {(d["position"], d["param"]) for d in cfg.differences_vs_signature(edited)})
        self.assertEqual(cfg.differences_vs_signature(cfg.default_config()), [])


class FactoryTest(unittest.TestCase):
    def test_every_value_reaches_its_object(self):
        wfm = build(full())
        self.assertEqual(wfm.convergence_tolerance, 1e-3)
        ground = wfm.wake_deficitModel.groundModel
        self.assertEqual((type(ground).__name__, ground.n_reps, type(ground.superpositionModel).__name__),
                         ("MultiMirror", 1, "SquaredSum"))
        turb = wfm.turbulenceModel
        self.assertEqual(turb.c, [1.5, 1.6])
        self.assertEqual((type(turb.apply_weight.__self__).__name__, turb.apply_weight.__self__.dist_limit),
                         ("IECWeight", 20))
        self.assertEqual(len(turb.rotorAvgModel.nodes_x), 4)
        self.assertEqual(wfm.blockage_deficitModel.limiter, 1e-6)

    def test_nothing_is_shared_with_the_signatures_of_pywake(self):
        from py_wake.turbulence_models.stf import STF2017TurbulenceModel
        c = with_(cfg.default_config(), turbulence=C("STF2017TurbulenceModel"))
        a, b = build(c).turbulenceModel, build(c).turbulenceModel
        default = STF2017TurbulenceModel.__init__.__defaults__
        self.assertIsNot(a.c, b.c)
        self.assertFalse(any(a.c is d or a.addedTurbulenceSuperpositionModel is d for d in default))

    def test_the_free_stream_has_the_arguments_of_the_engine(self):
        wfm = fac.build_free_stream_model(full(), SITE, WT, ws_grid=WS)
        self.assertEqual(wfm.convergence_tolerance, 1e-3)

    def test_none_is_decided_by_pywake(self):
        # Decision 6.1 of #64: weight_function = None, PyWake refuses it when building (the validation builds the
        # turbulence); distance_limit = None, it fails where the turbulence is evaluated (R19; with All2AllIterative,
        # with any layout).
        for config, expected in ((with_(full(), turbulence=C("STF2017TurbulenceModel", weight_function=None)), "build"),
                                 (with_(full(), turbulence=C("STF2017TurbulenceModel",
                                                             weight_function=C("IECWeight", distance_limit=None))),
                                  "R19")):
            with self.subTest(config=config.turbulence):
                self.assertEqual(codes(config), [expected])
        self.assertEqual(codes(with_(full(), engine=C("All2AllIterative", convergence_tolerance=None))), [])
        self.assertEqual(codes(with_(full(), ground=C("MultiMirror", superpositionModel=None))), [])


class ExecutedTest(unittest.TestCase):
    def test_a_nested_rotor_of_the_blockage(self):
        ex = rd.executed_config(build(full()), full())
        rotor = ex["blockage"]["params"]["rotorAvgModel"]
        self.assertEqual(rotor["source"], rd.OBSERVED)
        self.assertEqual(rotor["value"]["class"], "EqGridRotorAvg")
        self.assertEqual(rotor["value"]["params"]["n"], {"value": 3, "source": rd.PASSED})
        self.assertEqual(rotor["value"]["nodes"], 9)
        self.assertEqual(ex["turbulence"]["params"]["weight_function"]["value"]["params"]["distance_limit"],
                         {"value": 20, "source": rd.OBSERVED})
        self.assertEqual(rd.differences_vs_selection(ex, full()), [])

    def test_a_difference_in_depth_has_its_route(self):
        c = full()
        ex = rd.executed_config(build(c), c)
        ex["ground"]["params"]["superpositionModel"]["value"]["class"] = "LinearSum"
        ex["turbulence"]["params"]["weight_function"]["value"]["params"]["distance_limit"]["value"] = 10
        diffs = {(d["position"], d["param"], d["selected"], d["executed"]) for d in rd.differences_vs_selection(ex, c)}
        self.assertEqual(diffs, {("ground", "superpositionModel", "SquaredSum", "LinearSum"),
                                 ("turbulence", "weight_function · distance_limit", 20, 10)})

    def test_a_reading_failure_in_depth_says_where(self):
        wfm = build(full())
        del wfm.turbulenceModel.apply_weight.__self__.__dict__["dist_limit"]
        with self.assertRaises(fac.ReaderError) as ctx:
            rd.executed_config(wfm, full())
        self.assertEqual(ctx.exception.position, "turbulence")
        self.assertIn("weight_function", ctx.exception.diagnosis)

    def test_what_was_executed_with_46a_is_shown_as_it_was_kept(self):
        # #46a kept a nested object by its class name: it is shown as such, never completed.
        historic = {"class": "STF2017TurbulenceModel", "params": {
            "c": {"value": [1.5, 0.8], "source": rd.OBSERVED},
            "weight_function": {"value": "FrandsenWeight", "source": rd.OBSERVED}}}
        self.assertEqual(_component_text(historic, lambda t: t), "STF2017TurbulenceModel(c=[1.5, 0.8], "
                                                                  "weight_function=FrandsenWeight)")

    def test_a_rotor_without_nodes_shows_them(self):
        # Discrete round 2, B: EqGridRotorAvg with n ≤ 0 (or False) keeps no node, and the report says so (it is 0,
        # not absent), as the log does; in the deficit and nested in the blockage.
        for n in (0, -1, False):
            c = with_(cfg.default_config("All2AllIterative"), rotor=C("EqGridRotorAvg", n=n),
                      blockage=C("SelfSimilarityDeficit2020", rotorAvgModel=C("EqGridRotorAvg", n=n)),
                      blockage_superposition=C("LinearSum"))
            ex = rd.executed_config(build(c), c)
            with self.subTest(n=n):
                self.assertTrue(_component_text(ex["rotor"], lambda t: t).endswith(", nodos=0)"))
                self.assertIn("rotorAvgModel=EqGridRotorAvg(n=", _component_text(ex["blockage"], lambda t: t))
                self.assertIn("nodos=0)", _component_text(ex["blockage"], lambda t: t))
        self.assertNotIn("nodos", _component_text(c.to_dict()["rotor"], lambda t: t))  # the selection has none

    def test_the_report_shows_both_forms(self):
        c = full()
        ex = rd.executed_config(build(c), c)
        selected = _component_text(c.to_dict()["blockage"], lambda t: t)
        executed = _component_text(ex["blockage"], lambda t: t)
        self.assertIn("rotorAvgModel=EqGridRotorAvg(n=3)", selected)
        self.assertIn("rotorAvgModel=EqGridRotorAvg(n=3 [argumento pasado], nodos=9)", executed)
        self.assertNotIn("None", selected.replace("groundModel=None", ""))


class ValidationTest(unittest.TestCase):
    def test_each_control_and_each_option(self):
        # A list shorter than what PyWake reads is not a form error: it fails where PyWake reads it (decision 6.1 of
        # #64, a failure of interaction, Q5d); a number that is not a value of CGI, PyWake refuses when building.
        self.assertEqual(codes(with_(full(), turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("CGIRotorAvg", n=5)))),
                         ["build"])
        bad = {
            "an integer": with_(full(), ground=C("MultiMirror", n_reps=1.5)),
            "an option of its family": with_(full(), turbulence=C("STF2017TurbulenceModel",
                                                                  rotorAvgModel=C("RotorCenter"))),
            "an argument it does not have": with_(full(), engine=C("All2AllIterative", max_iter=3)),
        }
        for what, config in bad.items():
            with self.subTest(what=what):
                self.assertEqual(codes(config), ["R14"])
        self.assertEqual(codes(full()), [])


class NonFiniteThroughTheApiTest(unittest.TestCase):
    """Decision 5 of #64: NaN and infinities given through the API reach PyWake as given, and the plugin keeps them
    (contract, round trips, what was executed, the report and the JSON of the raster); the dialog does not read them."""

    def config(self):
        from VelantisWind.ag_core.wake_setup.api import check_calculable, resolve_request
        base = cfg.default_config(deficit="NiayifarGaussianDeficit")
        config, _ = resolve_request({"version": 1, "engine": "PropagateDownwind", "deficit": "NiayifarGaussianDeficit",
                                     "deficit_params": dict(base.deficit.params, ceps=float("nan")),
                                     "superposition": "LinearSum",
                                     "turbulence": {"class": "STF2017TurbulenceModel", "c": [float("inf"), 0.8],
                                                    "weight_function": {"class": "IECWeight",
                                                                        "distance_limit": float("-inf")}}})
        check_calculable(config)  # nothing refused
        return config

    def test_they_reach_pywake_as_given(self):
        from py_wake.deficit_models.gaussian import NiayifarGaussianDeficit
        from py_wake.turbulence_models import STF2017TurbulenceModel
        from py_wake.turbulence_models.stf import IECWeight
        from py_wake.wind_farm_models import PropagateDownwind
        from tests.test_wake_subordinates_fidelity import TURBINES, outputs, same
        config = self.config()
        params = dict(config.deficit.params)
        direct = PropagateDownwind(SITE, TURBINES, NiayifarGaussianDeficit(**{k: v for k, v in params.items()
                                                                               if k != "ct2a"}),
                                   superpositionModel=LinearSum(),
                                   turbulenceModel=STF2017TurbulenceModel(
                                       c=[float("inf"), 0.8], weight_function=IECWeight(distance_limit=float("-inf"))))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            got, expected = outputs(build(config)), outputs(direct)
        self.assertTrue(same(got[:3], expected[:3]))
        self.assertFalse(np.isfinite(expected[0]).all())  # NaN in the wind speeds: they were not left out

    def test_they_survive_every_round_trip(self):
        from VelantisWind.ag_core.wake_setup.api import resolve_request, to_wake_physics
        config = self.config()
        self.assertTrue(np.isnan(config.deficit.params["ceps"]))
        self.assertEqual(config.turbulence.params["c"][0], float("inf"))
        self.assertEqual(config.turbulence.params["weight_function"].params["distance_limit"], float("-inf"))
        self.assertEqual(resolve_request(to_wake_physics(config))[0], config)
        text = json.dumps(config.to_dict())
        self.assertIn("NaN", text)
        self.assertIn("Infinity", text)
        self.assertEqual(cfg.WakeConfig.from_dict(json.loads(text)), config)
        v1 = json.loads(json.dumps(V1))
        v1["deficit"]["params"]["ceps"] = float("nan")
        self.assertTrue(np.isnan(cfg.WakeConfig.from_dict(json.loads(json.dumps(v1))).deficit.params["ceps"]))

    def test_what_was_executed_is_the_selection_and_the_report_shows_them(self):
        config = self.config()
        executed = rd.executed_config(build(config), config)
        self.assertEqual(rd.differences_vs_selection(executed, config), [])
        self.assertIn("nan", _component_text(executed["deficit"], lambda t: t).lower())
        diffs = {(d["position"], d["param"]) for d in cfg.differences_vs_signature(config)}
        self.assertIn(("deficit", "ceps"), diffs)
        again = cfg.WakeConfig.from_dict(json.loads(json.dumps(config.to_dict())))
        self.assertEqual({(d["position"], d["param"]) for d in cfg.differences_vs_signature(again)}, diffs)

    def test_the_exports_of_the_result_write_them(self):
        # The JSON next to the CSV and the summary layer (``export.wake_record``), as the exporter writes it.
        from VelantisWind.ag_core.qgis_io.export import wake_record
        config = self.config()
        result = {"wake_config": {"selected": config.to_dict(), "effective": config.to_dict(),
                                  "executed": rd.executed_config(build(config), config)}}
        back = json.loads(json.dumps(wake_record(result), ensure_ascii=False, indent=2, default=str))
        self.assertEqual(cfg.WakeConfig.from_dict(back["wake_config"]["selected"]), config)
        self.assertTrue(np.isnan(back["wake_config"]["executed"]["deficit"]["params"]["ceps"]["value"]))

    def test_component_equality_is_still_by_class(self):
        class Other(cfg.Component):
            pass
        self.assertNotEqual(cfg.Component("LinearSum", {}), Other("LinearSum", {}))
        nested = cfg.Component("Mirror", {"superpositionModel": cfg.Component("LinearSum", {})})
        self.assertNotEqual(nested, cfg.Component("Mirror", {"superpositionModel": Other("LinearSum", {})}))
        with self.assertRaises(TypeError):  # its arguments are a mapping, as before
            hash(cfg.Component("LinearSum", {}))

    def test_nan_in_a_list_and_in_a_nested_component_is_the_same_value(self):
        a = C("STF2017TurbulenceModel", c=[float("nan"), 0.8], weight_function=C("IECWeight", distance_limit=float("nan")))
        b = json.loads(json.dumps(a.to_dict()))
        self.assertEqual(cfg.Component.from_dict(b, "t"), cfg.complete(a))
        self.assertTrue(cfg.same_value([float("nan")], [float("nan")]))
        self.assertFalse(cfg.same_value([float("nan")], [0.0]))
        self.assertFalse(cfg.same_value([1.0], (1.0,)))

    def test_the_dialog_does_not_read_them(self):
        from VelantisWind.ui_core.wake_controls import parse_number
        for text in ("nan", "inf", "-inf", "1e999"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_number(text)


class ContractFormTest(unittest.TestCase):
    """Decision 6.2 of #64: R14 checks the form of the contract; whether PyWake takes a value, PyWake decides (an error
    when building, refused before calculating; one when calculating with a value, an error of the calculation)."""

    def same_as_pywake(self, config, direct):
        from tests.test_wake_subordinates_fidelity import outputs, same
        self.assertEqual(codes(config), [])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.assertTrue(same(outputs(build(config))[:3], outputs(direct)[:3]))

    def test_the_forms_pywake_takes_are_kept_and_calculate_as_pywake(self):
        from py_wake.rotor_avg_models import CGIRotorAvg, EqGridRotorAvg
        from py_wake.turbulence_models import STF2017TurbulenceModel
        from py_wake.wind_farm_models import PropagateDownwind, PropagateUpDownIterative
        from tests.test_wake_setup_factory import direct
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        base = cfg.default_config()
        bg = dict(base.deficit.params)
        niayifar = cfg.default_config(deficit="NiayifarGaussianDeficit")
        cases = {
            "use_effective_ws = 1": (with_(base, deficit=C("BastankhahGaussianDeficit", **dict(bg, use_effective_ws=1))),
                                     direct(PropagateDownwind, BastankhahGaussianDeficit(use_effective_ws=1),
                                            superpositionModel=LinearSum())),
            "k = True": (with_(base, deficit=C("BastankhahGaussianDeficit", **dict(bg, k=True))),
                         direct(PropagateDownwind, BastankhahGaussianDeficit(k=True), superpositionModel=LinearSum())),
            "EqGridRotorAvg(True)": (with_(base, rotor=C("EqGridRotorAvg", n=True)),
                                     direct(PropagateDownwind, BastankhahGaussianDeficit(rotorAvgModel=EqGridRotorAvg(True)),
                                            superpositionModel=LinearSum())),
            "CGIRotorAvg(7.0)": (with_(base, rotor=C("CGIRotorAvg", n=7.0)),
                                 direct(PropagateDownwind, BastankhahGaussianDeficit(rotorAvgModel=CGIRotorAvg(7.0)),
                                        superpositionModel=LinearSum())),
            "c = [1.5, 0.8, 99]": (with_(niayifar, turbulence=C("STF2017TurbulenceModel", c=[1.5, 0.8, 99.0])),
                                   direct(PropagateDownwind, NiayifarGaussianDeficit(), superpositionModel=LinearSum(),
                                          turbulenceModel=STF2017TurbulenceModel(c=[1.5, 0.8, 99.0]))),
        }
        pud = cfg.default_config("PropagateUpDownIterative")
        cases["max_iter = 10**20"] = (
            with_(pud, deficit=C(pud.deficit.name, **dict(pud.deficit.params, use_effective_ws=True)),
                  engine=C("PropagateUpDownIterative", **dict(pud.engine.params, max_iter=10 ** 20))),
            direct(PropagateUpDownIterative, BastankhahGaussianDeficit(use_effective_ws=True),
                   superpositionModel=LinearSum(), max_iter=10 ** 20))
        for name, (config, oracle) in cases.items():
            with self.subTest(case=name):
                self.same_as_pywake(config, oracle)
                executed = rd.executed_config(build(config), config)
                self.assertEqual(rd.differences_vs_selection(executed, config), [])
        texts = [str(t) for t in argument_warnings(cases["c = [1.5, 0.8, 99]"][0])["turbulence"]]
        self.assertTrue(any("c tiene 3 elementos" in t and "solo lee los 2 primeros" in t for t in texts))
        executed = rd.executed_config(build(cases["c = [1.5, 0.8, 99]"][0]), cases["c = [1.5, 0.8, 99]"][0])
        self.assertEqual(executed["turbulence"]["params"]["c"]["value"], [1.5, 0.8, 99.0])  # kept, with the extra one
        config = cases["CGIRotorAvg(7.0)"][0]
        self.assertEqual(config.rotor.params["n"], 7.0)  # what was passed
        self.assertEqual(rd.executed_config(build(config), config)["rotor"]["nodes"], 7)  # what PyWake built

    def test_an_array_through_the_api_is_its_list(self):
        from VelantisWind.ag_core.wake_setup.api import resolve_request, to_wake_physics
        config, _ = resolve_request({"version": 1, "engine": "PropagateDownwind", "deficit": "NiayifarGaussianDeficit",
                                     "superposition": "LinearSum",
                                     "turbulence": {"class": "STF2017TurbulenceModel", "c": np.array([1.5, 0.8])}})
        self.assertEqual(config.turbulence.params["c"], [1.5, 0.8])
        self.assertIs(type(config.turbulence.params["c"]), list)
        self.assertEqual(resolve_request(to_wake_physics(config))[0], config)
        from py_wake.turbulence_models import STF2017TurbulenceModel
        from py_wake.wind_farm_models import PropagateDownwind
        from tests.test_wake_setup_factory import direct
        self.same_as_pywake(config, direct(PropagateDownwind, NiayifarGaussianDeficit(), superpositionModel=LinearSum(),
                                           turbulenceModel=STF2017TurbulenceModel(c=np.array([1.5, 0.8]))))

    def test_an_error_of_pywake_when_building_is_refused_at_its_position(self):
        # CGIRotorAvg(7.5): PyWake has no table for it (KeyError when building); the validation builds the deficit,
        # with its rotor, and the added turbulence, with its own, and refuses it there, with PyWake's error.
        base = cfg.default_config(deficit="NiayifarGaussianDeficit")
        for position, config in (("rotor", with_(base, rotor=C("CGIRotorAvg", n=7.5))),
                                 ("turbulence", with_(base, turbulence=C("STF2017TurbulenceModel",
                                                                         rotorAvgModel=C("CGIRotorAvg", n=7.5))))):
            with self.subTest(position=position):
                issues = val.validate(config)
                self.assertEqual([i.code for i in issues], ["build"])
                self.assertIn("7.5", issues[0].text)
        issues = val.validate(with_(base, turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("CGIRotorAvg", n=7.5))))
        self.assertEqual(issues[0].position, "turbulence")

    def test_the_warnings_never_fail_with_the_numbers_the_contract_takes(self):
        # Every number of the contract (decisions 5 and 6.2 of #64) in every numeric argument of the subordinate
        # objects: the warnings are computed, without an error of their own, with and without the turbines.
        # Only configurations: nothing is built (MultiMirror would build 10**1000 mirrors, EqGridRotorAvg its nodes).
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings, persistent_warnings
        from tests.test_wake_subordinates import BLOCKAGES, ENGINES
        a2a = cfg.default_config("All2AllIterative")
        positions = {"CGIRotorAvg": "rotor", "EqGridRotorAvg": "rotor", "Mirror": "ground", "MultiMirror": "ground",
                     "WeightedSum": "superposition", "CumulativeWakeSum": "superposition"}
        for arg in sub.ARGS:
            if arg.kind not in (sub.NUMBER, sub.NUMBER_OR_NONE, sub.INT):
                continue
            values = (10 ** 1000, -10 ** 1000, True, False) + (() if arg.kind == sub.INT else
                                                                (float("nan"), float("inf"), float("-inf")))
            for value in values:
                comp = C(arg.owner, **{arg.name: value})
                if arg.owner in ENGINES:
                    config = with_(cfg.default_config(arg.owner), engine=comp)
                elif arg.owner in BLOCKAGES:
                    config = with_(a2a, blockage=comp, blockage_superposition=C("LinearSum"))
                elif arg.owner == "IECWeight":
                    config = with_(a2a, turbulence=C("STF2017TurbulenceModel", weight_function=comp))
                else:
                    config = with_(a2a, **{positions.get(arg.owner, "turbulence"): comp})
                with self.subTest(owner=arg.owner, arg=arg.name, value=value):
                    argument_warnings(config)
                    persistent_warnings(config, hub_heights=[70.0])

    def test_a_large_integer_in_combinations_and_in_the_record_of_convergence(self):
        from VelantisWind.ag_core.wake_setup.instrumentation import _as_given
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        config = with_(cfg.default_config("All2AllIterative"), blockage=C(
            "VortexDipole", limiter=-1.0, rotorAvgModel=C("EqGridRotorAvg", n=10 ** 1000 + 1)),
            blockage_superposition=C("LinearSum"))
        argument_warnings(config)  # no error of its own
        self.assertEqual(_as_given(10 ** 1000), 10 ** 1000)  # recorded as given, compared exactly
        from VelantisWind.ag_core.wake_setup.instrumentation import ConvergenceRecorder
        config = with_(cfg.default_config(), superposition=C("WeightedSum", max_err=10 ** 1000))
        with ConvergenceRecorder() as recorder, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            simulate(build(config))
        summary = recorder.summary()["WeightedSum"]
        self.assertEqual(set(summary["states"]), {"converged"})  # read, not «unavailable»

    def test_an_integer_the_contract_cannot_write_is_refused(self):
        # Python writes an integer of up to 4300 digits as text by default: beyond that, the configuration, its JSON
        # and its report could not record it (the form of the contract, R14).
        base = cfg.default_config()
        for value, expected in ((10 ** 1000, []), (10 ** 5000, ["R14"])):
            with self.subTest(digits=len(str(value)) if value < 10 ** 4000 else "> 4300"):
                config = with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, k=value)))
                self.assertEqual(codes(config), expected)
                for issue in val.validate(config):
                    self.assertIn("bits>", issue.text)  # its message, without writing the integer
        niayifar = cfg.default_config(deficit="NiayifarGaussianDeficit")
        for name, config in (("EqGridRotorAvg.n", with_(base, rotor=C("EqGridRotorAvg", n=10 ** 5000))),
                             ("MultiMirror.n_reps", with_(base, ground=C("MultiMirror", n_reps=10 ** 5000))),
                             ("NiayifarGaussianDeficit.a", with_(niayifar, deficit=C(
                                 "NiayifarGaussianDeficit", **dict(niayifar.deficit.params, a=[0.38, 10 ** 5000])))),
                             ("a nested mapping", with_(niayifar, deficit=C(
                                 "NiayifarGaussianDeficit", **dict(niayifar.deficit.params,
                                                                   a=[{"x": 10 ** 5000}, 0.004]))))):
            with self.subTest(argument=name):
                issues = val.validate(config)
                self.assertEqual([i.code for i in issues], ["R14"])
                self.assertIn("bits>", issues[0].text)

    def test_equivalent_forms_are_warned_as_pywake_reads_them(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        mm = [str(t) for t in argument_warnings(with_(cfg.default_config(), ground=C("MultiMirror", n_reps=True)))["deficit"]]
        self.assertTrue(any("8 veces" in t for t in mm))  # True is 1: 2^(2 + 1) representations
        a2a = with_(cfg.default_config("All2AllIterative"), engine=C("All2AllIterative", convergence_tolerance=False))
        self.assertTrue(any("nunca cumple su criterio" in str(t) for t in argument_warnings(a2a)["engine"]))
        longer = [str(t) for t in argument_warnings(with_(cfg.default_config(), turbulence=C(
            "STF2017TurbulenceModel", c=[0.0, 0.0, 99.0])))["turbulence"]]
        self.assertTrue(any("c = [0, 0]" in t for t in longer) and any("solo lee los 2 primeros" in t for t in longer))
        fgp = with_(cfg.default_config("All2AllIterative"), blockage=C(
            "SelfSimilarityDeficit2020", fgp=[-0.06489, 0.4911, 1.116, 0.0, 5.0]), blockage_superposition=C("LinearSum"))
        self.assertTrue(any("fgp[3] = 0" in str(t) for t in argument_warnings(fgp)["blockage"]))

    def test_the_cost_of_multimirror_with_an_exponent_python_cannot_write(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for n in (10 ** 4300 - 2, 10 ** 4300 - 1):
            config = with_(cfg.default_config(), ground=C("MultiMirror", n_reps=n))
            texts = [str(t) for t in argument_warnings(config)["deficit"]]
            self.assertTrue(any("2^(2 + n_reps)" in t or "2^1000" in t for t in texts))

    def test_vortexdipole_without_regularisation_with_minus_infinity_and_nan(self):
        # r/R < limiter is false at the centre with −inf and NaN: r = 0 stays, NaN (q5c_adv_comprobaciones); +inf
        # regularises everything.
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for limiter, warned in ((float("-inf"), True), (float("nan"), True), (float("inf"), False)):
            config = with_(cfg.default_config("All2AllIterative"),
                           blockage=C("VortexDipole", limiter=limiter, exclude_wake=False),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(limiter=limiter):
                texts = [str(t) for t in argument_warnings(config).get("blockage", [])]
                self.assertEqual(any("no regulariza el centro" in t for t in texts), warned)
                self.assertEqual(any("el de la propia turbina" in t for t in texts), warned)

    def test_the_nodes_of_eqgrid_are_counted_without_its_grid(self):
        from py_wake.rotor_avg_models import EqGridRotorAvg
        from VelantisWind.ag_core.wake_setup.readers import _eqgrid_nodes
        for n in list(range(-2, 40)) + [97, 99, 195, 1001]:
            with self.subTest(n=n):
                self.assertEqual(_eqgrid_nodes(n), len(EqGridRotorAvg(n).nodes_x))
        config = with_(cfg.default_config(), rotor=C("EqGridRotorAvg", n=3))
        wfm = build(config)
        with mock.patch("py_wake.rotor_avg_models.EqGridRotorAvg") as built:
            self.assertEqual(rd.executed_config(wfm, config)["rotor"]["nodes"], 9)
        built.assert_not_called()

    def test_the_record_of_a_request_of_the_previous_schema_keeps_its_arrays_as_lists(self):
        from VelantisWind.ag_core.wake_setup.api import resolve_request
        _, record = resolve_request(wake_deficit_model="NIA", turbulence_model="STF2017",
                                    wake_deficit_kwargs={"a": np.array([0.38, 0.004, 99.0]), "ceps": np.float64(0.2)})
        given = record["given"]["wake_deficit_kwargs"]
        self.assertEqual(given, {"a": [0.38, 0.004, 99.0], "ceps": 0.2})
        self.assertIs(type(given["a"]), list)
        self.assertEqual(json.loads(json.dumps(record, default=str))["given"]["wake_deficit_kwargs"], given)

    def test_an_equivalent_value_of_use_effective_ti_is_not_a_difference(self):
        # PyWake picks ['TI_ilk', 'TI_eff_ilk'][use_effective_ti] (deficit_model.py:21): −2 is what was asked for,
        # and the report must not say otherwise; another key is a difference.
        base = with_(cfg.default_config("PropagateDownwind", "NiayifarGaussianDeficit"),
                     turbulence=C("STF2017TurbulenceModel"))
        for value in (False, 0, -2, True, 1, -1):
            with self.subTest(use_effective_ti=value):
                config = with_(base, deficit=C("NiayifarGaussianDeficit",
                                               **dict(base.deficit.params, use_effective_ti=value)))
                self.assertEqual(rd.differences_vs_selection(rd.executed_config(build(config), config), config), [])
        # The same with use_effective_ws, in the deficit and in the blockage (['WS_ilk', 'WS_eff_ilk'][value]).
        a2a = cfg.default_config("All2AllIterative")
        for value in (0, -2, 1, -1):
            for config in (with_(a2a, deficit=C(a2a.deficit.name, **dict(a2a.deficit.params, use_effective_ws=value))),
                           with_(a2a, blockage=C("SelfSimilarityDeficit2020", use_effective_ws=value),
                                 blockage_superposition=C("LinearSum"))):
                with self.subTest(use_effective_ws=value, blockage=config.blockage is not None):
                    self.assertEqual(rd.differences_vs_selection(rd.executed_config(build(config), config), config),
                                     [])
        asked = with_(base, deficit=C("NiayifarGaussianDeficit", **dict(base.deficit.params, use_effective_ti=-2)))
        other = with_(base, deficit=C("NiayifarGaussianDeficit", **dict(base.deficit.params, use_effective_ti=True)))
        self.assertEqual([d["param"] for d in rd.differences_vs_selection(rd.executed_config(build(other), other),
                                                                            asked)], ["use_effective_ti"])

    def test_high_ct_mod_as_pywake_reads_it(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        config = with_(cfg.default_config("All2AllIterative"), blockage=C("RankineHalfBody", high_ct_mod=1),
                       blockage_superposition=C("LinearSum"))
        self.assertEqual(codes(config), [])
        self.assertTrue(any("high_ct_mod" in str(t) for t in argument_warnings(config)["blockage"]))

    def test_an_argument_the_plugin_does_not_offer_says_so(self):
        config = with_(cfg.default_config(deficit="NiayifarGaussianDeficit"), turbulence=C("STF2005TurbulenceModel", c=[1, 2]))
        issues = val.validate(config)
        self.assertEqual([i.code for i in issues], ["R14"])
        self.assertIn("El complemento no ofrece «c» de STF2005TurbulenceModel", issues[0].text)
        self.assertIn("STF2005 usa las constantes de la norma", issues[0].text)


if __name__ == "__main__":
    unittest.main()


class RulesWithEditedValuesTest(unittest.TestCase):
    """R15 (the technical limits) and the rules of #46a re-evaluated with the edited values, against PyWake."""

    def finite(self, config):
        """The effective wind speed, the effective TI and the AEP are all finite (all of them are the result)."""
        sim = simulate(build(config))
        return all(bool(np.isfinite(a).all()) for a in (sim.WS_eff.values, sim.TI_eff.values, sim.aep().values))

    def test_the_only_technical_limit_is_what_pywake_does_not_build(self):
        # Decision 5 of #64: EqGridRotorAvg with n ≤ −3 (np.linspace with n + 2 < 0), refused before building; from −2
        # PyWake builds it.
        base = cfg.default_config("All2AllIterative")
        issues = val.validate(with_(base, rotor=C("EqGridRotorAvg", n=-3)))
        self.assertEqual([(i.code, i.data["arg"]) for i in issues], [("R15", "n")])
        with self.assertRaises(fac.FactoryError) as caught:
            build(with_(base, rotor=C("EqGridRotorAvg", n=-3)))
        self.assertIn("must be non-negative", str(caught.exception.__cause__))
        self.assertEqual(codes(with_(base, rotor=C("EqGridRotorAvg", n=-2))), [])
        # Through the API, refused before anything is built (the validation builds with one point per EqGrid).
        from py_wake.rotor_avg_models import EqGridRotorAvg
        from VelantisWind.ag_core.wake_setup.api import ConfigRejected, check_calculable, resolve_request
        built = []
        real = EqGridRotorAvg.__init__

        def spy(self, n=4):
            built.append(n)
            real(self, n=n)
        config, _ = resolve_request({"version": 1, "engine": "All2AllIterative",
                                     "rotor": {"class": "EqGridRotorAvg", "n": -3}})
        with mock.patch.object(EqGridRotorAvg, "__init__", spy), self.assertRaises(ConfigRejected) as refused:
            check_calculable(config)
        self.assertEqual([i.code for i in refused.exception.issues], ["R15"])
        self.assertNotIn(-3, built)

    def test_what_pywake_calculates_is_warned_and_is_what_pywake_gives(self):
        # Decision 5 of #64: the five refusals of Q2 with which PyWake calculates (non-finite results) are warnings;
        # the plugin gives what PyWake by hand gives, compared on the result of the simulation (WS_eff, TI_eff, NaN in
        # the same places) and not on the totals, which sum a NaN as zero until #63.
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit
        from tests.test_wake_subordinates_fidelity import TURBINES, config_and_direct, outputs, same
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings

        def arg(owner, name):
            return sub.arg_spec(owner, name)

        from VelantisWind.ag_core.wake_setup.notices import persistent_warnings

        def warned(config):
            return [str(t) for texts in argument_warnings(config).values() for t in texts]
        ss = with_(cfg.default_config("All2AllIterative"),
                   blockage=C("SelfSimilarityDeficit", ss_lambda=-0.5, exclude_wake=False),
                   blockage_superposition=C("LinearSum"))
        ss_direct = A2A(SITE, TURBINES, BastankhahGaussianDeficit(), superpositionModel=LinearSum(),
                        blockage_deficitModel=SelfSimilarityDeficit(ss_lambda=-0.5, exclude_wake=False,
                                                                    superpositionModel=LinearSum()))
        cases = {
            "EqGrid n = 0": (*config_and_direct(arg("EqGridRotorAvg", "n"), 0, "All2AllIterative"), "no tiene nodos"),
            "EqGrid n = −2": (*config_and_direct(arg("EqGridRotorAvg", "n"), -2), "no tiene nodos"),
            "STF2017 c = [0, 0]": (*config_and_direct(arg("STF2017TurbulenceModel", "c"), [0.0, 0.0], "All2AllIterative"),
                                   "c = [0, 0]"),
            "STF2017 c = [0, 0.8]": (*config_and_direct(arg("STF2017TurbulenceModel", "c"), [0.0, 0.8],
                                                        "All2AllIterative"), "c[0] = 0"),
            "fgp[3] = 0": (*config_and_direct(arg("SelfSimilarityDeficit2020", "fgp"), [-0.06489, 0.4911, 1.116, 0.0]),
                           "fgp[3] = 0"),
            "VortexDipole limiter = −1": (*config_and_direct(arg("VortexDipole", "limiter"), -1.0),
                                          "el de la propia turbina"),
            "SelfSimilarityDeficit ss_lambda < 0": (ss, ss_direct, "negativo o nulo en parte del dominio"),
        }
        for name, (config, direct, text) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(codes(config), [])
                self.assertTrue(any(text in t for t in warned(config)), warned(config))
                self.assertTrue(any(text in str(t) for t in persistent_warnings(config)))  # the result's
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    got, expected = outputs(build(config)), outputs(direct)
                self.assertTrue(same(got[:2], expected[:2]))  # the simulation, NaN in the same places
                self.assertFalse(all(np.isfinite(a).all() for a in expected[:3]), "PyWake gives finite values here")
        fine = {"EqGrid n = 1": with_(cfg.default_config(), rotor=C("EqGridRotorAvg", n=1)),
                "c = [1.5, 0]": with_(cfg.default_config(), turbulence=C("STF2017TurbulenceModel", c=[1.5, 0.0])),
                "fgp[3] ≠ 0": with_(cfg.default_config("All2AllIterative"),
                                    blockage=C("SelfSimilarityDeficit2020", fgp=[-0.06489, 0.4911, 1.116, -0.2]),
                                    blockage_superposition=C("LinearSum")),
                "ss positive": with_(cfg.default_config("All2AllIterative"),
                                     blockage=C("SelfSimilarityDeficit", ss_lambda=0.5, ss_eta=0.5),
                                     blockage_superposition=C("LinearSum"))}
        for name, config in fine.items():
            with self.subTest(case=name):
                self.assertEqual(warned(config), [])

    def test_vortexdipole_with_an_eqgrid_without_nodes_has_no_centre(self):
        # n from −2 to 0 builds a rotor without nodes: no centre node, and its warning, not an error of the warnings.
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for n in (-2, -1, 0):
            config = with_(cfg.default_config("All2AllIterative"),
                           blockage=C("VortexDipole", limiter=-1.0, rotorAvgModel=C("EqGridRotorAvg", n=n)),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(n=n):
                self.assertEqual(codes(config), [])
                texts = [str(t) for t in argument_warnings(config)["blockage"]]
                self.assertFalse(any("el de la propia turbina" in t for t in texts))
                self.assertTrue(any("no tiene nodos" in t for t in texts))

    def test_the_domain_of_selfsimilaritydeficit_also_with_a_product_rounded_to_zero(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for lam, eta, warned in ((1e-200, 1e-200, True), (-1.0, -1.0, True), (0.5, 0.5, False), (-0.5, 1.0, True)):
            config = with_(cfg.default_config("All2AllIterative"),
                           blockage=C("SelfSimilarityDeficit", ss_lambda=lam, ss_eta=eta),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(ss_lambda=lam, ss_eta=eta):
                texts = [str(t) for t in argument_warnings(config).get("blockage", [])]
                self.assertEqual(any("negativo o nulo en parte del dominio" in t for t in texts), warned)

    def test_a_limit_in_a_nested_component_gives_its_route(self):
        config = with_(cfg.default_config(deficit="NiayifarGaussianDeficit"),
                       turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("EqGridRotorAvg", n=-3)))
        issues = val.validate(config)
        self.assertEqual([(i.code, i.position, i.data["arg"]) for i in issues], [("R15", "turbulence", "rotorAvgModel · n")])
        self.assertIn("«turbulencia añadida · rotorAvgModel · n»", issues[0].text)

    def test_eqgrid_without_nodes_in_the_turbulence_is_warned_for_the_ti(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        config = with_(cfg.default_config(deficit="NiayifarGaussianDeficit"),
                       turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("EqGridRotorAvg", n=0)))
        self.assertEqual(codes(config), [])
        self.assertTrue(any("NaN en la TI efectiva" in str(t) for t in argument_warnings(config)["turbulence"]))

    def test_what_was_executed_with_eqgrid_without_nodes(self):
        # The reader checks the nodes of the n passed against those PyWake builds with it: none, from −2 to 0.
        config = with_(cfg.default_config(), rotor=C("EqGridRotorAvg", n=-2))
        executed = rd.executed_config(build(config), config)
        self.assertEqual(executed["rotor"]["nodes"], 0)
        self.assertEqual(rd.differences_vs_selection(executed, config), [])

    def test_r9d_only_when_the_ground_inherits_cumulative(self):
        base = with_(cfg.default_config("All2AllIterative"), superposition=C("CumulativeWakeSum"))
        inherits = with_(base, ground=C("Mirror"))
        own = with_(base, ground=C("Mirror", superpositionModel=C("LinearSum")))
        self.assertEqual(codes(inherits), ["R9d"])
        with self.assertRaises(TypeError):
            simulate(build(inherits)).aep()
        self.assertEqual(codes(own), [])
        self.assertTrue(np.array_equal(simulate(build(own)).aep().values,
                                       simulate(build(with_(base, ground=None))).aep().values))

    def test_r12_only_without_a_sum_of_its_own_in_the_deficit_and_in_the_blockage(self):
        base = with_(cfg.default_config(), rotor=C("CGIRotorAvg", n=7))
        r12 = with_(base, ground=C("MultiMirror"))  # PropagateDownwind: from the second turbine (decision 6.1 of #64)
        self.assertEqual(codes(r12), [])
        self.assertEqual([i.code for i in val.layout_issues(r12, 2)], ["R12"])
        own = with_(base, ground=C("MultiMirror", superpositionModel=C("LinearSum")))
        self.assertEqual(codes(own), [])
        self.assertTrue(self.finite(own))
        a2a = cfg.default_config("All2AllIterative")
        for sup in ("LinearSum", "WeightedSum"):
            with self.subTest(sup=sup):
                blocked = with_(a2a, superposition=C(sup), blockage_superposition=C("LinearSum"),
                                blockage=C("SelfSimilarityDeficit2020", rotorAvgModel=C("CGIRotorAvg", n=7),
                                           groundModel=C("MultiMirror")))
                self.assertEqual([(i.code, i.position) for i in val.validate(blocked)], [("R12", "blockage")])
                with self.assertRaisesRegex(AttributeError, "__self__"):
                    simulate(build(blocked)).aep()
                fixed = with_(blocked, blockage=C("SelfSimilarityDeficit2020", rotorAvgModel=C("CGIRotorAvg", n=7),
                                                  groundModel=C("MultiMirror", superpositionModel=C("LinearSum"))))
                self.assertEqual(codes(fixed), [])
                self.assertTrue(self.finite(fixed))


class ArgumentWarningsTest(unittest.TestCase):
    """The warnings of the edited arguments (#64, Q2, design 5): what PyWake does with a value, never a barrier."""

    def texts(self, config, **kwargs):
        from VelantisWind.ag_core.wake_setup import notices
        return {p: [str(w) for w in ws] for p, ws in notices.argument_warnings(config, **kwargs).items()}

    def test_none_for_the_signature_values(self):
        for config in (cfg.default_config(), cfg.default_config("All2AllIterative"), full()):
            with self.subTest(engine=config.engine.name):
                self.assertNotIn("engine", self.texts(config))
        self.assertEqual(self.texts(cfg.default_config("PropagateUpDownIterative")), {})

    def test_each_value_that_warns(self):
        a2a = cfg.default_config("All2AllIterative")
        pud = with_(cfg.default_config("PropagateUpDownIterative"),
                    deficit=C("BastankhahGaussianDeficit", **dict(cfg.default_config().deficit.params,
                                                                  use_effective_ws=True)))
        cases = {
            "una sola iteración": (with_(a2a, engine=C("All2AllIterative", convergence_tolerance=None)), "engine"),
            "agota sus iteraciones": (with_(a2a, engine=C("All2AllIterative", convergence_tolerance=0)), "engine"),
            "agota sus pasadas": (with_(pud, engine=C("PropagateUpDownIterative", convergence_tolerance=-1e-3)), "engine"),
            "representa cada turbina 8 veces": (with_(a2a, ground=C("MultiMirror", n_reps=1)), "deficit"),
            "repite imágenes": (with_(a2a, ground=C("MultiMirror", n_reps=2)), "deficit"),
            "1 imagen(es) a la altura de la turbina real (a menos de 1 µm): aparece 2 veces": (with_(a2a, ground=C("MultiMirror", n_reps=3)),
                                                                        "deficit"),
            "2 imagen(es) a la altura de la turbina real (a menos de 1 µm): aparece 3 veces": (with_(a2a, ground=C("MultiMirror", n_reps=4)),
                                                                        "deficit"),
            "repite imágenes de las turbinas": (with_(a2a, ground=C("MultiMirror", n_reps=4)), "deficit"),
            "no añade repeticiones": (with_(a2a, ground=C("MultiMirror", n_reps=-2)), "deficit"),
            "cae sobre la turbina real o sobre su imagen": (with_(a2a, ground=C("MultiMirror", mirror_height=0.0)),
                                                            "deficit"),
            "aparece 4 veces en la suma del suelo": (with_(a2a, ground=C("MultiMirror", mirror_height=0.0, n_reps=1)), "deficit"),
            "VortexDipole no regulariza el centro del rotor": (
                with_(a2a, blockage=C("VortexDipole", limiter=-1.0, rotorAvgModel=C("CGIRotorAvg", n=4)),
                      blockage_superposition=C("LinearSum")), "blockage"),
            "no pondera": (with_(a2a, superposition=C("WeightedSum", max_iter=0)), "superposition"),
            "a 1e-30": (with_(a2a, superposition=C("WeightedSum", delta=0.0)), "superposition"),
            "con un cociente positivo pesan -1.0": (with_(a2a, superposition=C("WeightedSum", weight_limit=-1.0)),
                                                   "superposition"),
            "negativo o nulo en parte del dominio": (with_(a2a, blockage=C("SelfSimilarityDeficit", ss_lambda=-0.5),
                                            blockage_superposition=C("LinearSum")), "blockage"),
            "high_ct_mod = True": (with_(a2a, blockage=C("RankineHalfBody", high_ct_mod=True),
                                         blockage_superposition=C("LinearSum")), "blockage"),
            "«bloqueo · groundModel», con n_reps = 3, PyWake 2.6.18 añade": (
                with_(a2a, blockage=C("VortexDipole", groundModel=C("MultiMirror", n_reps=3)),
                                           blockage_superposition=C("LinearSum")), "blockage"),
        }
        for fragment, (config, position) in cases.items():
            with self.subTest(fragment=fragment):
                self.assertTrue(any(fragment in t for t in self.texts(config).get(position, [])),
                                self.texts(config))
                self.assertEqual([i.code for i in val.validate(config) if i.code != "R14"], [])  # never a barrier

    def test_a_weighted_sum_that_is_not_the_wake_superposition_has_no_warnings(self):
        # Discrete round 1, B1: as the sum of a ground PyWake never calls it with CumulativeWakeSum and PDW (it
        # calculates) and refuses it otherwise (R18); as the blockage's it is refused (R6). Each of its three warnings,
        # given at the wake superposition, is given nowhere else.
        from tests.test_wake_interaction import pywake_stops
        pdw = cfg.default_config("PropagateDownwind")
        a2a = cfg.default_config("All2AllIterative")
        warned = {"no pondera": C("WeightedSum", max_iter=0),
                  "1e-30": C("WeightedSum", delta=0.0),
                  "weight_limit": C("WeightedSum", max_iter=5, weight_limit=0.0)}
        for fragment, ws in warned.items():
            self.assertTrue(any(fragment in t for t in self.texts(with_(a2a, superposition=ws))["superposition"]))
            unused = with_(pdw, superposition=C("CumulativeWakeSum"), ground=C("Mirror", superpositionModel=ws))
            for config, codes in ((unused, []),
                                  (with_(a2a, ground=C("Mirror", superpositionModel=ws)), ["R18"]),
                                  (with_(a2a, blockage=C("SelfSimilarityDeficit2020"), blockage_superposition=ws),
                                   ["R6"])):
                with self.subTest(fragment=fragment, config=config.to_dict()):
                    texts = [t for ts in self.texts(config).values() for t in ts]
                    self.assertFalse([t for t in texts if fragment in t], texts)
                    self.assertEqual([i.code for i in val.validate(config) + val.layout_issues(config, 2)], codes)
            self.assertFalse(pywake_stops(unused, 2))

    def test_the_mirror_against_the_hubs(self):
        config = with_(cfg.default_config(), ground=C("MultiMirror", mirror_height=50.0))
        self.assertTrue(any("se comprueba con las turbinas" in t for t in self.texts(config)["deficit"]))
        low = self.texts(config, hub_heights=[70.0, 90.0])["deficit"]
        self.assertTrue(any("(90.0 m)" in t for t in low), low)
        high = self.texts(with_(config, ground=C("MultiMirror", mirror_height=1000.0)), hub_heights=[70.0, 90.0])
        self.assertFalse(any("altura de un buje" in t for t in high.get("deficit", [])))

    def test_one_iteration_is_never_converged(self):
        from VelantisWind.ag_core.wake_setup import notices
        texts = [str(w) for w in notices.convergence_warnings(
            {"All2AllIterative": {"converged": False, "states": {"no_check": 3}}})]
        self.assertEqual(texts, ["Convergencia de All2AllIterative: una iteración; convergencia no comprobada."])

    def test_the_ground_without_effect_with_a2a_and_a_sum_of_its_own(self):
        from VelantisWind.ag_core.wake_setup import notices
        base = with_(cfg.default_config("All2AllIterative"), superposition=C("CumulativeWakeSum"))
        own = with_(base, ground=C("Mirror", superpositionModel=C("LinearSum")))
        self.assertIn("groundModel (Mirror: superpositionModel)", notices.cumulative_without_effect(own))
        multi = with_(cfg.default_config(), superposition=C("CumulativeWakeSum"), ground=C("MultiMirror", n_reps=1))
        self.assertIn("groundModel (MultiMirror: mirror_height, n_reps, superpositionModel)",
                      notices.cumulative_without_effect(multi))

    def test_every_text_is_translated(self):
        from VelantisWind.ag_core.wake_setup import notices
        from VelantisWind.ag_core.wake_setup.messages_translations import TRANSLATIONS
        for text in notices.ARGUMENT_TEXTS + ("Convergencia de {loop}: una iteración; convergencia no comprobada.",):
            for language in ("en", "fr", "de"):
                with self.subTest(text=text[:40], language=language):
                    self.assertTrue(TRANSLATIONS[language].get(text))


class MultiMirrorCopiesTest(unittest.TestCase):
    def test_the_copies_of_the_real_turbine_are_those_of_pywake(self):
        # The vertical offsets PyWake gives the images (ground_models.py:98-128): a zero is the real turbine again.
        from py_wake.ground_models import MultiMirror
        from VelantisWind.ag_core.wake_setup.notices import _real_appearances
        for n in range(0, 8):
            with self.subTest(n_reps=n):
                kwargs = {"IJLK": (1, 1, 1, 1), "h_ilk": np.array([[[70.0]]]), "dh_ijlk": np.zeros((1, 1, 1, 1))}
                dh = MultiMirror(mirror_height=300.0, n_reps=n)._update_kwargs(**kwargs)["dh_ijlk"]
                self.assertEqual(_real_appearances(n, 300.0), int(np.sum(np.isclose(dh, 0.0))))
        # With the hubs of the calculation: a hub on a mirror, a negative mirror height, several hubs (the most), and
        # a mirror at the ground (its images fall on the real turbine or on its image: 2, 4, 16…).
        for mirror, hubs, n in ((70.0, [70.0], 3), (-300.0, [70.0], 3), (300.0, [70.0, 300.0], 4), (150.0, [90.0], 6),
                                (0.0, [70.0], 0), (0.0, [70.0], 1), (0.0, [70.0], 3), (0.0, [70.0], 6)):
            with self.subTest(mirror=mirror, hubs=hubs, n_reps=n):
                expected = 0
                for h in hubs:
                    kwargs = {"IJLK": (1, 1, 1, 1), "h_ilk": np.array([[[h]]]), "dh_ijlk": np.zeros((1, 1, 1, 1))}
                    dh = MultiMirror(mirror_height=mirror, n_reps=n)._update_kwargs(**kwargs)["dh_ijlk"]
                    expected = max(expected, int(np.sum(np.isclose(dh, 0.0))))
                self.assertEqual(_real_appearances(n, mirror, hubs), expected)


class AdversarialRoundTest(unittest.TestCase):
    """What the adversarial rounds of Q2 found (revisiones/astra/q2_adv_r1_*, and two independent reviewers)."""

    def test_a_value_of_a_closed_set_at_any_depth(self):
        # Decision 6.2 of #64: a number equal to a value of the set is the one PyWake looks up (CGIRotorAvg(4.0) is
        # CGIRotorAvg(4)); what is not a number of the contract (a complex, an array inside the configuration) is
        # R14; a number PyWake has no table for (True is 1, 4.5) is its error when building, before calculating.
        for n, expected in ((4.0, []), (4 + 0j, ["R14"]), (np.array([4]), ["R14"]), (True, ["build"]), (4.5, ["build"])):
            with self.subTest(n=n):
                config = with_(cfg.default_config(), turbulence=C("STF2017TurbulenceModel",
                                                                  rotorAvgModel=C("CGIRotorAvg", n=n)))
                self.assertEqual(codes(config), expected)
        self.assertEqual(codes(with_(cfg.default_config(), turbulence=C(
            "STF2017TurbulenceModel", rotorAvgModel=C("CGIRotorAvg", n=4)))), [])

    def test_a_list_given_as_a_tuple_is_the_list_of_the_contract(self):
        config = with_(cfg.default_config(), turbulence=C("STF2017TurbulenceModel", c=(1.5, 0.8)))
        self.assertEqual(config.turbulence.params["c"], [1.5, 0.8])
        self.assertNotIn("c", [d["param"] for d in cfg.differences_vs_signature(config)])  # it is the signature's
        self.assertEqual(cfg.WakeConfig.from_dict(json.loads(json.dumps(config.to_dict()))), config)

    def test_the_warnings_of_multimirror_never_build_its_images(self):
        # 2^(2 + n_reps) images: counted, not built; the count of the cost written as a power above 2^66.
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for n in (30, 14284, 2 ** 31 - 1):
            with self.subTest(n_reps=n):
                texts = [str(t) for t in argument_warnings(with_(cfg.default_config(), ground=C(
                    "MultiMirror", n_reps=n, mirror_height=0.0)))["deficit"]]
                self.assertTrue(any(("2^%d veces" % (n + 2)) in t or ("%d veces" % 2 ** (n + 2)) in t for t in texts))
                self.assertTrue(any("a la altura de la turbina real" in t for t in texts))

    def test_the_limiter_of_vortexdipole_is_warned_where_its_own_turbine_gives_nan(self):
        # NaN where the blockage is evaluated at the centre of a rotor: with All2AllIterative and a node there (no
        # rotor average, EqGridRotorAvg with an odd n, CGIRotorAvg with 7, 9 or 21); elsewhere finite. PyWake
        # calculates in both: warned, never refused (decision 5 of #64).
        from py_wake.examples.data.hornsrev1 import V80
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        cases = []
        for engine in ("All2AllIterative", "PropagateUpDownIterative"):
            for rotor, centre in ((None, True), (C("CGIRotorAvg", n=4), False), (C("CGIRotorAvg", n=7), True),
                                  (C("EqGridRotorAvg", n=2), False), (C("EqGridRotorAvg", n=3), True)):
                cases.append((engine, rotor, engine == "All2AllIterative" and centre))
        for engine, rotor, refused in cases:
            base = cfg.default_config(engine)
            config = with_(base, deficit=C(base.deficit.name, **dict(base.deficit.params, use_effective_ws=True)),
                           blockage=C("VortexDipole", limiter=-1.0, use_effective_ws=True, rotorAvgModel=rotor),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(engine=engine, rotor=rotor and rotor.label):
                self.assertEqual(codes(config), [])
                texts = [str(t) for t in argument_warnings(config)["blockage"]]
                self.assertEqual(any("el de la propia turbina" in t for t in texts), refused)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sim = fac.build_wind_farm_model(config, SITE, V80(), ws_grid=WS)(
                        np.array([0.0, 400.0, 800.0]), np.array([0.0, 0.0, 30.0]), wd=[270.0, 0.0], ws=[10.0])
                self.assertEqual(bool(np.isfinite(sim.aep().values).all()), not refused)

    def test_the_validation_never_builds_the_nodes_of_an_edited_eqgrid(self):
        from py_wake.rotor_avg_models import EqGridRotorAvg
        built = []
        real = EqGridRotorAvg.__init__

        def spy(self, n=4):
            built.append(n)
            real(self, n=n)
        config = with_(cfg.default_config("All2AllIterative"), rotor=C("EqGridRotorAvg", n=10 ** 5),
                       blockage=C("SelfSimilarityDeficit2020", rotorAvgModel=C("EqGridRotorAvg", n=10 ** 5)),
                       blockage_superposition=C("LinearSum"))
        with mock.patch.object(EqGridRotorAvg, "__init__", spy):
            self.assertEqual(codes(config), [])
        self.assertEqual(set(built), {1})

    def test_the_height_of_the_mirror_is_read_from_the_object_and_the_nodes_of_eqgrid_checked(self):
        from py_wake.rotor_avg_models import EqGridRotorAvg
        config = with_(cfg.default_config(), ground=C("MultiMirror", mirror_height=300.0,
                                                      superpositionModel=C("LinearSum")),
                       rotor=C("EqGridRotorAvg", n=3))
        wfm = build(config)
        executed = rd.executed_config(wfm, config)
        self.assertEqual(executed["ground"]["params"]["mirror_height"], {"value": 300.0, "source": "observed"})
        wfm.wake_deficitModel.groundModel.h_mirrors[1] = 1000.0  # what a lost argument would leave
        self.assertEqual(rd.differences_vs_selection(rd.executed_config(wfm, config), config),
                         [{"position": "ground", "param": "mirror_height", "selected": 300.0, "executed": 1000.0}])
        wfm = build(config)
        wfm.wake_deficitModel.rotorAvgModel = EqGridRotorAvg(4)  # the n of the signature, not the one passed
        with self.assertRaises(fac.ReaderError):
            rd.executed_config(wfm, config)

    def test_hybridinduction_does_not_share_the_arrays_of_its_inner_models(self):
        import inspect
        from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020
        config = with_(cfg.default_config("All2AllIterative"), blockage=C("HybridInduction"),
                       blockage_superposition=C("LinearSum"))
        a, b = build(config).blockage_deficitModel.near_rotor, build(config).blockage_deficitModel.near_rotor
        signature = inspect.signature(SelfSimilarityDeficit2020.__init__).parameters
        for name in ("r12p", "ngp", "fgp"):
            with self.subTest(name=name):
                self.assertIsNot(getattr(a, name), getattr(b, name))
                self.assertIsNot(getattr(a, name), signature[name].default)

    def test_an_empty_name_of_a_nested_class_in_the_api(self):
        from VelantisWind.ag_core.wake_setup.api import RequestError, resolve_request
        with self.assertRaises(RequestError):
            resolve_request({"version": 1, "engine": "All2AllIterative", "blockage": "SelfSimilarityDeficit2020",
                             "blockage_params": {"groundModel": ""}})

    def test_the_validation_never_builds_the_mirrors_of_an_edited_multimirror(self):
        from py_wake.ground_models import MultiMirror
        built = []
        real = MultiMirror.__init__

        def spy(self, mirror_height=1000., n_reps=0, superpositionModel=None):
            built.append(n_reps)
            real(self, mirror_height, n_reps, superpositionModel)
        config = with_(cfg.default_config("All2AllIterative"), ground=C("MultiMirror", n_reps=2 ** 31 - 1),
                       blockage=C("SelfSimilarityDeficit2020", groundModel=C("MultiMirror", n_reps=2 ** 31 - 1,
                                                                            superpositionModel=C("LinearSum"))),
                       blockage_superposition=C("LinearSum"))
        with mock.patch.object(MultiMirror, "__init__", spy):
            val.validate(config)
        self.assertEqual(set(built), {1})  # one repetition at most: the first uses mirror_height (Q5d)

    def test_the_centre_node_of_eqgrid_is_the_one_of_numpy(self):
        # An odd n has its middle node at 0 except where np.linspace rounds it (97, 195): finite there.
        from py_wake.examples.data.hornsrev1 import V80
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for n, refused in ((3, True), (97, False), (99, True), (4, False)):
            base = cfg.default_config("All2AllIterative")
            config = with_(base, blockage=C("VortexDipole", limiter=-1.0, rotorAvgModel=C("EqGridRotorAvg", n=n)),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(n=n):
                self.assertEqual(codes(config), [])
                texts = [str(t) for t in argument_warnings(config)["blockage"]]
                self.assertEqual(any("el de la propia turbina" in t for t in texts), refused)
                if not refused:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        sim = fac.build_wind_farm_model(config, SITE, V80(), ws_grid=WS)(
                            np.array([0.0, 400.0]), np.array([0.0, 0.0]), wd=[270.0], ws=[10.0])
                    self.assertTrue(np.isfinite(sim.aep().values).all())

    def test_an_integer_numpy_does_not_operate_as_a_number_is_an_error_of_the_calculation(self):
        # Decision 6.2 of #64: a value with which PyWake fails when calculating is an error of the calculation with its
        # cause (decision 1 of #46a), not a refusal of the plugin.
        base = cfg.default_config("All2AllIterative")
        for value in (10 ** 20, 2 ** 63 - 1, float(10 ** 20)):
            with self.subTest(value=value):
                config = with_(base, blockage=C("SelfSimilarityDeficit", ss_lambda=value),
                               blockage_superposition=C("LinearSum"))
                self.assertEqual(codes(config), [])
        config = with_(base, blockage=C("SelfSimilarityDeficit", ss_lambda=10 ** 20), blockage_superposition=C("LinearSum"))
        with self.assertRaises(Exception), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            simulate(build(config)).aep()

    def test_the_warnings_of_a_ground_cumulativewakesum_leaves_without_effect(self):
        # With PDW and PUD and CumulativeWakeSum PyWake never calls the ground: no cost nor images claimed, the note
        # of decision 23a names it; with A2A and a sum of its own PyWake calls it (it costs) though it has no effect.
        from py_wake.ground_models import MultiMirror
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings, persistent_warnings
        for engine, ground, called in (
                ("PropagateDownwind", C("MultiMirror", n_reps=3), False),
                ("PropagateUpDownIterative", C("MultiMirror", n_reps=3), False),
                ("All2AllIterative", C("MultiMirror", n_reps=3, superpositionModel=C("LinearSum")), True)):
            base = cfg.default_config(engine)
            config = with_(base, superposition=C("CumulativeWakeSum"), ground=ground, deficit=C(
                base.deficit.name, **dict(base.deficit.params, use_effective_ws=engine == "PropagateUpDownIterative")))
            calls = []
            real = MultiMirror._update_kwargs

            def trace(self, **kwargs):
                calls.append(1)
                return real(self, **kwargs)
            with self.subTest(engine=engine):
                with mock.patch.object(MultiMirror, "_update_kwargs", trace), warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    build(config)(np.array([0.0, 560.0]), np.array([0.0, 0.0]), wd=[270.0], ws=[10.0])
                self.assertEqual(bool(calls), called)
                costs = any("representa cada turbina" in str(w) for w in argument_warnings(config).get("deficit", []))
                self.assertEqual(costs, called)
                self.assertTrue(any("groundModel (MultiMirror" in str(w) for w in persistent_warnings(config)))
        texts = [str(t) for t in argument_warnings(with_(cfg.default_config(), ground=C("MultiMirror", n_reps=3)))[
            "deficit"]]
        self.assertTrue(any("aparece 2 veces en la suma del suelo" in t for t in texts))

    def test_the_differences_of_a_class_with_its_label_and_their_routes(self):
        config = with_(cfg.default_config("All2AllIterative"), rotor=C("CGIRotorAvg", n=9),
                       blockage=C("SelfSimilarityDeficit2020", groundModel=C("MultiMirror", n_reps=3)),
                       blockage_superposition=C("LinearSum"))
        diffs = [(d["position"], d["param"]) for d in cfg.differences_vs_signature(config)]
        self.assertIn(("rotor", None), diffs)
        self.assertNotIn(("rotor", "n"), diffs)  # the label already gives it: CGIRotorAvg(n=9)
        from VelantisWind.ag_core.log_text import shown
        text = shown(cfg.identification(config), lambda t: t)
        self.assertIn("rotor = CGIRotorAvg(n=9)", text)
        self.assertIn("blockage · groundModel · n_reps = 3", text)

    def test_vortexdipole_with_limiter_0_and_exclude_wake_is_warned(self):
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        config = with_(cfg.default_config("All2AllIterative"), blockage=C("VortexDipole", limiter=0.0, exclude_wake=True),
                       blockage_superposition=C("LinearSum"))
        self.assertEqual(codes(config), [])
        self.assertTrue(any("radio de estela no es positivo" in str(w) for w in argument_warnings(config)["blockage"]))

    def test_selfsimilaritydeficit_where_its_own_turbine_gives_nan_is_warned(self):
        # With All2AllIterative, ss_alpha ≠ 0 and (exclude_wake = False or limiter < 0), a product ss_lambda·ss_eta < 0,
        # or 0 with a centre node, gives NaN at the turbine itself; elsewhere it can be finite. PyWake calculates in
        # both: the warning of the domain, never a refusal (decision 5 of #64; option C of Q2 was a refusal).
        from py_wake.examples.data.hornsrev1 import V80
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        cases = (({"ss_lambda": -0.5, "exclude_wake": False}, True), ({"ss_lambda": 0.0, "exclude_wake": False}, True),
                 ({"ss_eta": 0.0, "exclude_wake": False}, True), ({"ss_lambda": -0.5, "limiter": -1.0}, True),
                 ({"ss_lambda": 0.0, "exclude_wake": False, "rotorAvgModel": C("CGIRotorAvg", n=4)}, False),
                 ({"ss_lambda": -0.5, "exclude_wake": False, "ss_alpha": 0.0}, False), ({"ss_lambda": -0.5}, False))
        for kwargs, refused in cases:
            config = with_(cfg.default_config("All2AllIterative"), blockage=C("SelfSimilarityDeficit", **kwargs),
                           blockage_superposition=C("LinearSum"))
            with self.subTest(kwargs=kwargs):
                self.assertEqual(codes(config), [])
                self.assertTrue(any("negativo o nulo en parte del dominio" in str(w)
                                    for w in argument_warnings(config)["blockage"]))
                if refused or kwargs.get("rotorAvgModel") or "ss_alpha" in kwargs:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        sim = fac.build_wind_farm_model(config, SITE, V80(), ws_grid=WS)(
                            np.array([0.0, 400.0, 800.0]), np.array([0.0, 0.0, 0.0]), wd=[270.0], ws=[10.0])
                    self.assertEqual(bool(np.isfinite(sim.aep().values).all()), not refused)
        pud = cfg.default_config("PropagateUpDownIterative")
        config = with_(pud, deficit=C(pud.deficit.name, **dict(pud.deficit.params, use_effective_ws=True)),
                       blockage=C("SelfSimilarityDeficit", ss_lambda=-0.5, exclude_wake=False, use_effective_ws=True),
                       blockage_superposition=C("LinearSum"))
        self.assertEqual(codes(config), [])  # with PUD the turbine itself is not added: no refusal

    def test_the_parameters_of_the_catalogue_too(self):
        # A large integer is a number of the contract (decision 6.2 of #64), and a list given as a tuple is the list of
        # the contract, in a deficit as in a subordinate.
        base = cfg.default_config()
        for name in ("BastankhahGaussianDeficit", "NOJDeficit"):
            config = cfg.default_config(deficit=name)
            config = with_(config, deficit=C(name, **dict(config.deficit.params, k=10 ** 20)))
            with self.subTest(deficit=name):
                self.assertEqual(codes(config), [])
        config = with_(base, deficit=C("NiayifarGaussianDeficit", **dict(
            cfg.default_config(deficit="NiayifarGaussianDeficit").deficit.params, a=(0.38, 0.004))))
        self.assertEqual(config.deficit.params["a"], [0.38, 0.004])
        self.assertNotIn("a", [d["param"] for d in cfg.differences_vs_signature(config)])
        self.assertEqual(cfg.WakeConfig.from_dict(json.loads(json.dumps(config.to_dict()))), config)

    def test_an_image_counts_as_the_real_turbine_only_at_its_height(self):
        # An offset, as PyWake computes it, under a micrometre: the warning says where the images are, not what they
        # do (that depends on the rotor; revisiones/sol/q2f_r4-r5_salida.md); far, at any scale, another height.
        from VelantisWind.ag_core.wake_setup.notices import _real_appearances
        self.assertEqual(_real_appearances(0, 300.0, [300.0]), 2)
        self.assertEqual(_real_appearances(0, 300.0, [300.00000001]), 2)  # 2e-8 m: under the micrometre
        self.assertEqual(_real_appearances(0, 300.0, [300.000002]), 1)  # 4e-6 m: another height
        self.assertEqual(_real_appearances(0, 10.0 ** 12, [10.0 ** 12 + 100]), 1)
        self.assertEqual(_real_appearances(0, 10.0 ** 12, [10.0 ** 12]), 2)
        self.assertEqual(_real_appearances(0, 10.0 ** 16, [10.0 ** 16 + 20]), 1)  # the image 40 m below
        self.assertEqual(_real_appearances(3, 300.1, [150.05]), 2)  # exact in arithmetic, 3e-13 m away in PyWake
