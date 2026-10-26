# -*- coding: utf-8 -*-
"""The contract of the wake physics at the API: ``wake_physics`` and the previous schema (#46 P5b; README, P5 a-f)."""
import unittest

from VelantisWind.ag_core.wake_setup import api
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import validation as val
from VelantisWind.ag_core.wake_setup.api import NOT_SET, RequestError, legacy_note, resolve_request, to_wake_physics
from VelantisWind.ag_core.wake_setup.config import Component


def C(name, **params):
    return Component(name, params)


def with_(config, **changes):
    return cfg.WakeConfig(**{**config.__dict__, **changes})


def new(**physics):
    return resolve_request(dict({"version": 1}, **physics))[0]


class NewSchemaTest(unittest.TestCase):
    def test_nothing_indicated_is_the_signature_physics(self):
        self.assertEqual(resolve_request(), (cfg.default_config(), None))
        self.assertEqual(new(), cfg.default_config())

    def test_omission_empty_none_and_absence(self):
        sig = cfg.default_config(deficit="NOJDeficit")
        # Omitted and "" take the signature's rotor (AreaOverlapAvgModel for NOJ); None and "NONE" ask for none.
        self.assertEqual(new(deficit="NOJDeficit").rotor, sig.rotor)
        self.assertEqual(new(deficit="NOJDeficit", rotor="").rotor, sig.rotor)
        self.assertIsNone(new(deficit="NOJDeficit", rotor=None).rotor)
        self.assertIsNone(new(deficit="NOJDeficit", rotor="NONE").rotor)
        with self.assertRaises(RequestError):
            new(rotor="   ")

    def test_the_explicit_arguments_reach_the_configuration(self):
        c = new(engine="All2AllIterative", deficit="NiayifarGaussianDeficit",
                deficit_params={"use_effective_ti": False, "ceps": 0.3}, rotor={"class": "CGIRotorAvg", "n": 9},
                ground="Mirror", superposition="SquaredSum", turbulence="CrespoHernandez", blockage="VortexDipole",
                blockage_params={"use_effective_ws": True}, blockage_superposition="MaxSum")
        self.assertEqual(c.deficit.params["use_effective_ti"], False)
        self.assertEqual(c.deficit.params["ceps"], 0.3)
        self.assertEqual(c.deficit.params["ct2a"], cfg.deficit_signature("NiayifarGaussianDeficit")[0].params["ct2a"])
        self.assertEqual((c.rotor, c.ground, c.superposition, c.turbulence),
                         tuple(cfg.complete(x) for x in (C("CGIRotorAvg", n=9), C("Mirror"), C("SquaredSum"),
                                                         C("CrespoHernandez"))))
        self.assertEqual(c.blockage, cfg.complete(C("VortexDipole", use_effective_ws=True)))
        self.assertEqual(c.blockage_superposition, C("MaxSum"))
        self.assertEqual(val.validate(c, check_environment=False), [])
        # An explicit None in a parameter reaches the configuration (PyWake decides).
        self.assertIsNone(new(deficit_params={"ctlim": None}).deficit.params["ctlim"])

    def test_the_blockage_superposition_by_default_and_the_round_trip(self):
        c = new(engine="All2AllIterative", blockage="SelfSimilarityDeficit2020")
        self.assertEqual(c.blockage_superposition, C("LinearSum"))
        self.assertEqual(c.blockage, cfg.blockage_signature("SelfSimilarityDeficit2020"))
        for config in (cfg.default_config(), c, with_(cfg.default_config(deficit="NOJDeficit"), rotor=None),
                       with_(cfg.default_config(), rotor=C("CGIRotorAvg", n=21),
                             adaptations=({"position": "rotor", "from": "GaussianOverlapAvgModel"},))):
            self.assertEqual(resolve_request(to_wake_physics(config))[0], config)

    def test_what_cannot_be_read_is_an_error(self):
        # Version 2 exists since the predefined models (M4, deficit_ws_reference): 3 is not one.
        for physics in ({"version": 3}, {}, {"version": 1, "motor": "PDW"}, {"version": 1, "engine": None},
                        {"version": 1, "superposition": None}, {"version": 1, "engine": "TURBOPARK"},
                        {"version": 1, "blockage_params": {"x": 1}}, {"version": 1, "deficit": "AUTO"}):
            with self.subTest(physics=physics), self.assertRaises(RequestError):
                resolve_request(physics)
        # CGIRotorAvg is one option since #64 (Q3): its name alone takes the n of its signature.
        self.assertEqual(resolve_request({"version": 1, "rotor": "CGIRotorAvg"})[0].rotor, C("CGIRotorAvg", n=7))

    def test_a_blockage_the_installation_does_not_have(self):
        from unittest import mock
        from VelantisWind.ag_core.wake_setup import catalog as cat
        real = cat.resolve_class

        def missing(e):
            if e.name == "VortexDipole":
                raise cat.ClassUnavailable("La instalación de PyWake no tiene la clase VortexDipole.")
            return real(e)
        with mock.patch.object(cat, "resolve_class", side_effect=missing), self.assertRaises(api.ConfigRejected) as ctx:
            new(engine="All2AllIterative", blockage="VortexDipole")
        self.assertEqual([(i.code, i.origin) for i in ctx.exception.issues], [("R14", "environment")])

    def test_a_rotor_the_installation_does_not_have_is_not_needed_by_another_signature(self):
        # Without GaussianOverlapAvgModel installed, NOJDeficit, whose signature brings AreaOverlapAvgModel, is resolved.
        from unittest import mock
        from VelantisWind.ag_core.wake_setup import catalog as cat
        real = cat.resolve_class

        def missing(e):
            if e.name == "GaussianOverlapAvgModel":
                raise cat.ClassUnavailable("La instalación de PyWake no tiene la clase GaussianOverlapAvgModel.")
            return real(e)
        with mock.patch.object(cat, "resolve_class", side_effect=missing):
            self.assertEqual(new(deficit="NOJDeficit").rotor, C("AreaOverlapAvgModel"))
            self.assertIsNone(new(deficit="NOJDeficit", rotor=None).rotor)

    def test_an_unknown_argument_or_option_is_refused_by_the_validation(self):
        for physics in ({"deficit_params": {"k2": 1.0}}, {"turbulence": "TurbulenceX"}):
            with self.subTest(physics=physics):
                self.assertEqual({i.code for i in val.validate(new(**physics), check_environment=False)}, {"R14"})
        self.assertEqual({i.code for i in val.validate(new(rotor={"class": "CGIRotorAvg", "n": 5}),
                                                       check_environment=False)}, {"build"})  # PyWake's KeyError


class SequenceFormsTest(unittest.TestCase):
    def test_a_numpy_float_reaches_pywake_as_it_is(self):
        # numpy.float64 is a float (cf249cf passed it as such): its arithmetic is NumPy's (1e200 squared is inf, not
        # an OverflowError), so it is not converted; an array is still taken as its list.
        import numpy as np
        for config in (new(deficit="ZongGaussianDeficit", deficit_params={"B": np.float64(1e200)}),
                       resolve_request(wake_deficit_model="ZG", wake_deficit_kwargs={"B": np.float64(1e200)})[0]):
            with self.subTest(config=config.deficit.params["B"]):
                self.assertIs(type(config.deficit.params["B"]), np.float64)
                from VelantisWind.ag_core.wake_setup import factory
                self.assertIs(type(factory.build_deficit(config).B), np.float64)  # as it reaches the calculation

    def test_a_namedtuple_of_coefficients_is_taken_as_its_values(self):
        # As cf249cf took it (R14: a list or a tuple of numbers), in the two schemas: a subclass of tuple is not
        # rebuilt with its own constructor.
        from collections import namedtuple
        Coef = namedtuple("Coef", "pendiente ordenada")
        params = {"a": Coef(0.38, 0.004), "use_effective_ti": False}
        for config in (new(deficit="NiayifarGaussianDeficit", deficit_params=params),
                       resolve_request(wake_deficit_model="NIA", wake_deficit_kwargs=params)[0]):
            with self.subTest(config=config.to_dict()):
                self.assertEqual(list(config.deficit.params["a"]), [0.38, 0.004])
                self.assertEqual(val.validate(config), [])


class PreviousSchemaTest(unittest.TestCase):
    def test_the_same_configuration_as_the_new_request_with_a_note(self):
        legacy, record = resolve_request(wfm_engine="A2A", wake_deficit_model="NIA", superposition_model="SQR",
                                        rotor_avg_model="CGI9", include_rotor_avg=True, turbulence_model="CH",
                                        include_turbulence=True, blockage_deficit_model="VD", include_blockage=True,
                                        wake_deficit_kwargs={"ceps": 0.3, "use_effective_ws": False})
        self.assertEqual(legacy, new(engine="All2AllIterative", deficit="NiayifarGaussianDeficit",
                                     superposition="SquaredSum", rotor={"class": "CGIRotorAvg", "n": 9},
                                     turbulence="CrespoHernandez", blockage="VortexDipole",
                                     deficit_params={"ceps": 0.3, "use_effective_ws": False}))
        # What was asked for and what it became (legacy_request), and the note that says it.
        self.assertEqual(record["given"], {
            "wfm_engine": "A2A", "wake_deficit_model": "NIA", "superposition_model": "SQR", "rotor_avg_model": "CGI9",
            "turbulence_model": "CH", "blockage_deficit_model": "VD",
            "wake_deficit_kwargs": {"ceps": 0.3, "use_effective_ws": False}, "include_turbulence": True,
            "include_blockage": True, "include_rotor_avg": True})
        self.assertEqual(record["translated"], {
            "version": 1,
            "engine": "All2AllIterative", "deficit": "NiayifarGaussianDeficit", "superposition": "SquaredSum",
            "rotor": {"class": "CGIRotorAvg", "n": 9}, "turbulence": "CrespoHernandez", "blockage": "VortexDipole",
            "deficit_params": {"ceps": 0.3, "use_effective_ws": False}})
        self.assertEqual(resolve_request(record["translated"])[0], legacy)  # the request it became, as it is
        note = str(legacy_note(record))
        self.assertIn("esquema anterior", note)
        self.assertIn("wfm_engine = 'A2A'", note)
        self.assertIn("All2AllIterative", note)

    def test_the_exact_class_names_and_the_closed_table(self):
        self.assertEqual(resolve_request(wake_deficit_model="TurboGaussianDeficit")[0].deficit.name,
                         "TurboGaussianDeficit")
        self.assertEqual(resolve_request(wfm_engine="pud")[0].engine.name, "PropagateUpDownIterative")
        for field, value in (("wake_deficit_model", "TURBOPARK"), ("wake_deficit_model", "NYGAARD_2022"),
                             ("wake_deficit_model", "NONE"), ("rotor_avg_model", "CGI4"), ("superposition_model", "AUTO"),
                             ("wfm_engine", "auto"), ("turbulence_model", "AUTO")):
            with self.subTest(field=field, value=value), self.assertRaises(RequestError):
                resolve_request(**{field: value})
        self.assertEqual(resolve_request(rotor_avg_model="CGIRotorAvg", include_rotor_avg=True)[0].rotor,
                         C("CGIRotorAvg", n=7))  # one option since #64 (Q3), with the n of its signature

    def test_the_same_rotor_written_two_ways(self):
        # CGIRotorAvg (one option since #64) and CGI7 are the same rotor: not a contradiction; CGI9 is another one.
        for a, b in (("CGIRotorAvg", "CGI7"), ("CGI7", "CGIRotorAvg")):
            with self.subTest(a=a, b=b):
                self.assertEqual(resolve_request(rotor_avg_model=a, wake_deficit_kwargs={"rotorAvgModel": b})[0].rotor,
                                 C("CGIRotorAvg", n=7))
        with self.assertRaises(RequestError):
            resolve_request(rotor_avg_model="CGIRotorAvg", wake_deficit_kwargs={"rotorAvgModel": "CGI9"})

    def test_the_booleans_with_their_class(self):
        sig = cfg.default_config(deficit="NOJDeficit")
        nested = dict(wake_deficit_model="NOJ")
        self.assertEqual(resolve_request(**nested)[0].rotor, sig.rotor)  # both omitted: the signature
        self.assertEqual(resolve_request(rotor_avg_model="RC", **nested)[0].rotor, C("RotorCenter"))
        self.assertIsNone(resolve_request(include_rotor_avg=False, **nested)[0].rotor)
        self.assertIsNone(resolve_request(include_rotor_avg=False, rotor_avg_model="NONE", **nested)[0].rotor)
        self.assertEqual(resolve_request(include_rotor_avg=True, rotor_avg_model="EQ", **nested)[0].rotor,
                         cfg.complete(C("EqGridRotorAvg")))
        self.assertEqual(resolve_request(include_turbulence=True, turbulence_model="STF2017")[0].turbulence,
                         cfg.complete(C("STF2017TurbulenceModel")))
        for kwargs in ({"include_turbulence": True}, {"include_turbulence": True, "turbulence_model": "NONE"},
                       {"include_blockage": False, "blockage_deficit_model": "SS2020"},
                       {"include_rotor_avg": "yes"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RequestError):
                resolve_request(**kwargs)

    def test_a_position_given_twice(self):
        with self.assertRaises(RequestError) as ctx:
            resolve_request(rotor_avg_model="RC", wake_deficit_kwargs={"rotorAvgModel": None})
        self.assertIn("rotor_avg_model", str(ctx.exception.args[0]))
        self.assertIn("rotorAvgModel", str(ctx.exception.args[0]))
        with self.assertRaises(RequestError):
            resolve_request(include_rotor_avg=False, wake_deficit_kwargs={"rotorAvgModel": "CGI7"})
        # Only in the kwargs: kept, with the rule of its boolean.
        self.assertIsNone(resolve_request(wake_deficit_model="NOJ", wake_deficit_kwargs={"rotorAvgModel": None})[0].rotor)
        self.assertEqual(resolve_request(wake_deficit_kwargs={"rotorAvgModel": "RC"})[0].rotor, C("RotorCenter"))
        self.assertEqual(resolve_request(rotor_avg_model="RC", wake_deficit_kwargs={"rotorAvgModel": "RC"})[0].rotor,
                         C("RotorCenter"))
        # "" in the kwargs is the omission (the signature's rotor); False is not a rotor.
        self.assertEqual(resolve_request(wake_deficit_model="NOJ", wake_deficit_kwargs={"rotorAvgModel": ""})[0].rotor,
                         cfg.default_config(deficit="NOJDeficit").rotor)
        with self.assertRaises(RequestError):
            resolve_request(wake_deficit_kwargs={"rotorAvgModel": False})

    def test_the_explicit_kwargs_are_kept_and_the_omission_is_not_falsy(self):
        c, _ = resolve_request(wake_deficit_kwargs={"use_effective_ws": False, "ctlim": None})
        self.assertIs(c.deficit.params["use_effective_ws"], False)
        self.assertIsNone(c.deficit.params["ctlim"])
        with self.assertRaises(TypeError):
            bool(NOT_SET)
        self.assertEqual(resolve_request(wfm_engine="", wake_deficit_model=NOT_SET), (cfg.default_config(), None))

    def test_mixing_the_two_schemas_and_the_retired_fields(self):
        with self.assertRaises(RequestError) as ctx:
            resolve_request({"version": 1}, wfm_engine="PDW")
        self.assertIn("mezcla", str(ctx.exception.args[0]))
        with self.assertRaises(RequestError):
            resolve_request(wake_model="gauss")
        with self.assertRaises(TypeError):
            resolve_request(compute_variants=True)
        self.assertEqual(set(api.LEGACY_FIELDS) - {"wake_model"}, set(api._TABLE) | {
            "wake_deficit_kwargs", "include_turbulence", "include_blockage", "include_rotor_avg"})


if __name__ == "__main__":
    unittest.main()


class NestedRequestTest(unittest.TestCase):
    """The request with the arguments of the subordinate objects (#64, Q2, design 7)."""

    def full(self):
        from tests.test_wake_nested import full
        return full()

    def test_the_round_trip_through_json(self):
        import json
        config = self.full()
        physics = json.loads(json.dumps(to_wake_physics(config)))
        self.assertEqual(physics["engine"], {"class": "All2AllIterative", "convergence_tolerance": 1e-3})
        self.assertEqual(physics["ground"]["superpositionModel"], {"class": "SquaredSum"})
        self.assertEqual(physics["blockage_params"]["rotorAvgModel"], {"class": "EqGridRotorAvg", "n": 3})
        self.assertEqual(resolve_request(physics)[0], config)
        # The default physics, as #46a wrote it, still reads to the same configuration.
        self.assertEqual(resolve_request({"version": 1, "engine": "All2AllIterative"})[0],
                         cfg.default_config("All2AllIterative"))

    def test_a_nested_class_by_name_and_what_is_left_out(self):
        c = new(turbulence={"class": "STF2017TurbulenceModel", "weight_function": "IECWeight"},
                ground={"class": "MultiMirror", "n_reps": 2})
        self.assertEqual(c.turbulence.params["weight_function"], C("IECWeight", distance_limit=10))
        self.assertEqual(c.ground.params["mirror_height"], 1000.0)  # the signature's
        self.assertIsNone(c.ground.params["superpositionModel"])

    def test_the_engine_with_its_arguments(self):
        c = new(engine={"class": "All2AllIterative", "convergence_tolerance": None})
        self.assertIsNone(c.engine.params["convergence_tolerance"])
        self.assertEqual(val.validate(c, check_environment=False), [])

    def test_a_shorter_list_is_not_a_form_error(self):
        # PyWake keeps it and fails where it reads it: a failure of interaction (decision 6.1 of #64, Q5d).
        for turbulence in ({"class": "STF2017TurbulenceModel", "c": [1.5]},
                           {"class": "CrespoHernandez", "c": [0.73, 0.83, 0.03]}):
            with self.subTest(turbulence=turbulence):
                issues = val.validate(new(turbulence=turbulence), check_environment=False)
                self.assertNotIn("R14", [i.code for i in issues])

    def test_cgi_with_each_n_of_pywake(self):
        for n in (4, 7, 9, 21):
            with self.subTest(n=n):
                c = new(rotor={"class": "CGIRotorAvg", "n": n})
                self.assertEqual(val.validate(c, check_environment=False), [])
        self.assertEqual([i.code for i in val.validate(new(rotor={"class": "CGIRotorAvg", "n": 5}),
                                                       check_environment=False)], ["build"])  # PyWake's KeyError

    def test_cgi_n_of_another_type_and_keys_that_are_not_texts(self):
        for n, expected in ((4.0, []), (4 + 0j, ["R14"]), (True, ["build"])):  # decision 6.2 of #64
            with self.subTest(n=n):
                self.assertEqual([i.code for i in val.validate(new(rotor={"class": "CGIRotorAvg", "n": n}),
                                                               check_environment=False)], expected)
        with self.assertRaises(RequestError):
            new(turbulence={"class": "STF2017TurbulenceModel", "weight_function": {"class": "IECWeight", 1: 2}})

    def test_a_nested_value_that_is_not_a_class(self):
        with self.assertRaises(RequestError):
            new(turbulence={"class": "STF2017TurbulenceModel", "weight_function": 3})
        self.assertEqual([i.code for i in val.validate(new(turbulence={"class": "STF2017TurbulenceModel",
                                                                       "weight_function": "SquaredSum"}),
                                                       check_environment=False)], ["R14"])
