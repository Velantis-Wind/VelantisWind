# -*- coding: utf-8 -*-
"""The failures of interaction and their frontier (#64, decision 6.1, piece Q5d).

A group of configurations fails only where PyWake evaluates a model between turbines or at the points of the map:
with All2AllIterative from one turbine, with PropagateDownwind and PropagateUpDownIterative from the second, and in the
map (planes/plan_modelos_estela/evidencias/consistencia/fronteras.md). For each row of that table, with each engine
that takes it, with one, two and three turbines and in the map with one and two, the refusal of the plugin
(``validate``, and ``layout_issues`` with the turbines; ``map_issues`` for the raster) is exactly where PyWake written by
hand stops (``_stops``, without the factory of the plugin), and with the rule of the row.
"""
import sys
import unittest
import warnings
from unittest import mock

from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import validation as val
from tests.test_wake_setup_factory import C, with_
from tests.test_wake_subordinates_fidelity import _stops

warnings.filterwarnings("ignore", module="py_wake")

PDW, A2A, PUD = "PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"
RUNS = ((1, False), (2, False), (3, False), (1, True), (2, True))  # turbines (the first three in a line), map


def base(engine, deficit="BastankhahGaussianDeficit"):
    """The default configuration of ``engine`` and ``deficit``; with PUD, the effective wind speed it needs (R3)."""
    config = cfg.default_config(engine, deficit)
    if engine == PUD and "use_effective_ws" in config.deficit.params:
        config = with_(config, deficit=C(deficit, **dict(config.deficit.params, use_effective_ws=True)))
    return config


def blockage(engine, name="SelfSimilarityDeficit2020", **params):
    """A blockage of ``name`` with ``params``, with the effective wind speed PUD needs (R4), and its superposition."""
    return dict(blockage=C(name, **dict({"use_effective_ws": True} if engine == PUD else {}, **params)),
                blockage_superposition=C("LinearSum"))


def pywake_stops(config, n, flow_map=False):
    """Whether PyWake written by hand stops (building, simulating, the AEP or, with ``flow_map``, the map) with the
    first ``n`` turbines."""
    return _stops(config, n, flow_map)[0]


def refusal(config, n, flow_map=False):
    """The codes of what the plugin refuses before calculating ``config``, for the AEP or the raster, with ``n``
    turbines."""
    return [i.code for i in (val.validate(config) or val.layout_issues(config, n)
                             or (val.map_issues(config, n) if flow_map else []))]


def plugin_refuses(config, n, flow_map=False):
    return bool(refusal(config, n, flow_map))


def rows():
    """``(name, engine, config, code)`` of each row of the table of frontiers: the code of its rule (``None``: PyWake
    calculates; ``"build"``: PyWake does not build it; a pair: its rule, or R9e, which stops the map before it)."""
    out = []
    for engine in (PDW, A2A, PUD):
        b = base(engine)
        noj = with_(base(engine, "NOJLocalDeficit"), rotor=None)  # its AreaOverlap would be R8 with WeightedSum
        nia = base(engine, "NiayifarGaussianDeficit")
        zong = base(engine, "ZongGaussianDeficit")
        cws = with_(b, superposition=C("CumulativeWakeSum"))
        out += [
            ("R9b NOJ + WeightedSum", engine, with_(noj, superposition=C("WeightedSum"),
                                                    turbulence=C("STF2017TurbulenceModel")), "R9b"),
            ("R9 WeightedSum + suelo", engine, with_(b, superposition=C("WeightedSum"), ground=C("Mirror")), "R9"),
            ("R9c NOJ + CumulativeWakeSum", engine, with_(noj, superposition=C("CumulativeWakeSum"),
                                                          turbulence=C("STF2017TurbulenceModel")), "R9c"),
            ("R10 AreaOverlap + Bastankhah", engine, with_(b, rotor=C("AreaOverlapAvgModel")), "R10"),
            ("R11 GaussianOverlap + NOJ", engine, with_(noj, rotor=C("GaussianOverlapAvgModel"),
                                                        turbulence=C("STF2017TurbulenceModel")), "R11"),
            ("R12 MultiMirror sin suma + rotor", engine,
             with_(b, rotor=C("CGIRotorAvg", n=7), ground=C("MultiMirror")), "R12"),
            ("R17 GaussianOverlap en la turbulencia", engine, with_(
                nia, turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("GaussianOverlapAvgModel"))), "R17"),
            ("R17 AreaOverlap en STF2017", engine, with_(
                nia, turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("AreaOverlapAvgModel"))), "R17"),
            ("AreaOverlap en CrespoHernandez", engine, with_(
                nia, turbulence=C("CrespoHernandez", rotorAvgModel=C("AreaOverlapAvgModel"))), None),
            ("R18 suma propia WeightedSum del suelo", engine, with_(
                b, ground=C("Mirror", superpositionModel=C("WeightedSum"))), "R18"),
            ("R18 suma propia SqrMaxSum del suelo, con CumulativeWakeSum", engine, with_(
                cws, ground=C("Mirror", superpositionModel=C("SqrMaxSum"))), ("R18", "R9e")),
            ("R18 antes que el None de su suma, con CumulativeWakeSum", engine, with_(
                cws, ground=C("Mirror", superpositionModel=C("WeightedSum", delta=None))), ("R18", "R9e")),
            ("R19 WeightedSum delta = None", engine, with_(b, superposition=C("WeightedSum", delta=None)), "R19"),
            ("R19 ct2a = None con CumulativeWakeSum y suelo", engine, with_(
                cws, ground=C("Mirror", superpositionModel=C("LinearSum")),
                deficit=C(b.deficit.name, **dict(b.deficit.params, ct2a=None))), ("R19", "R9e")),
            ("R19 mirror_height = None sin repeticiones, con CumulativeWakeSum", engine, with_(
                cws, ground=C("MultiMirror", mirror_height=None, n_reps=0)), ("R19", "R9e")),
            ("R19 mirror_height = None sin repeticiones", engine, with_(
                b, ground=C("MultiMirror", mirror_height=None, n_reps=0)), "R19"),
            ("mirror_height = None con una repetición: no se construye", engine, with_(
                b, ground=C("MultiMirror", mirror_height=None, n_reps=1)), "build"),
            ("R19 k = None", engine, with_(b, deficit=C(b.deficit.name, **dict(b.deficit.params, k=None))), "R19"),
            ("R19 ct2a = None con CumulativeWakeSum", engine, with_(
                cws, deficit=C(b.deficit.name, **dict(b.deficit.params, ct2a=None))), "R19"),
            ("R19 Zong deltawD = None con CumulativeWakeSum", engine, with_(
                zong, superposition=C("CumulativeWakeSum"), turbulence=C("CrespoHernandez"),
                deficit=C("ZongGaussianDeficit", **dict(zong.deficit.params, deltawD=None))), "R19"),
            ("Zong ctlim = None", engine, with_(zong, turbulence=C("CrespoHernandez"), deficit=C(
                "ZongGaussianDeficit", **dict(zong.deficit.params, ctlim=None))), None),
            ("R19 ct2a = None en CrespoHernandez", engine, with_(
                nia, turbulence=C("CrespoHernandez", ct2a=None)), "R19"),
            ("R19 CumulativeWakeSum alpha = None", engine, with_(b, superposition=C("CumulativeWakeSum", alpha=None)),
             "R19"),
            ("R19 IECWeight distance_limit = None", engine, with_(
                nia, turbulence=C("STF2017TurbulenceModel", weight_function=C("IECWeight", distance_limit=None))),
             "R19"),
            ("R19 sin suma de la turbulencia", engine, with_(
                nia, turbulence=C("STF2017TurbulenceModel", addedTurbulenceSuperpositionModel=None)), "R19"),
            ("R20 STF2017 c = [1.5]", engine, with_(nia, turbulence=C("STF2017TurbulenceModel", c=[1.5])), "R20"),
            ("R20 Niayifar a = [0.38]", engine, with_(
                nia, turbulence=C("STF2017TurbulenceModel"),
                deficit=C("NiayifarGaussianDeficit", **dict(nia.deficit.params, a=[0.38]))), "R20"),
            ("R20 TurboGaussian cTI de tres", engine, with_(
                base(engine, "TurboGaussianDeficit"), deficit=C(
                    "TurboGaussianDeficit",
                    **dict(base(engine, "TurboGaussianDeficit").deficit.params, cTI=[1.5, 0.8, 99.0]))), "R20"),
        ]
        if engine == PUD:
            out.append(("R19 PUD convergence_tolerance = None", engine, with_(
                b, engine=C(PUD, **dict(b.engine.params, convergence_tolerance=None))), "R19"))
        if engine != PDW:  # a blockage
            out += [
                ("R6 WeightedSum como suma del bloqueo", engine, with_(
                    b, **dict(blockage(engine), blockage_superposition=C("WeightedSum"))), "R6"),
                ("R12 del bloqueo", engine, with_(b, **blockage(engine, rotorAvgModel=C("CGIRotorAvg", n=7),
                                                                groundModel=C("MultiMirror"))), "R12"),
                ("R16 AreaOverlap en el bloqueo", engine, with_(b, **blockage(
                    engine, rotorAvgModel=C("AreaOverlapAvgModel"))), "R16"),
                ("R16 GaussianOverlap en el bloqueo", engine, with_(b, **blockage(
                    engine, "VortexDipole", rotorAvgModel=C("GaussianOverlapAvgModel"))), "R16"),
                ("R18 suma propia del suelo del bloqueo, con CumulativeWakeSum", engine, with_(
                    cws, **blockage(engine, groundModel=C("MultiMirror", superpositionModel=C("WeightedSum")))),
                 "R18"),
                ("R19 ct2a = None en el bloqueo", engine, with_(b, **blockage(engine, ct2a=None)), "R19"),
                ("R20 SelfSimilarity2020 r12p corta", engine, with_(b, **blockage(engine, r12p=[-0.672])), "R20"),
                ("R20 SelfSimilarity2020 ngp corta", engine, with_(b, **blockage(engine, ngp=list(
                    cfg.blockage_signature("SelfSimilarityDeficit2020").params["ngp"])[:-1])), "R20"),
                ("R20 SelfSimilarity2020 fgp corta", engine, with_(b, **blockage(engine, fgp=list(
                    cfg.blockage_signature("SelfSimilarityDeficit2020").params["fgp"])[:-1])), "R20"),
                ("R19 Rathmann limiter = None, con exclude_wake", engine, with_(b, **blockage(
                    engine, "Rathmann", limiter=None, exclude_wake=True)), "R19"),
                ("Rathmann limiter = None, sin exclude_wake", engine, with_(b, **blockage(
                    engine, "Rathmann", limiter=None, exclude_wake=False)), None),
                ("RathmannScaled limiter = None, sin exclude_wake", engine, with_(b, **blockage(
                    engine, "RathmannScaled", limiter=None, exclude_wake=False)), None),
                ("R9f PUD + MaxSum del bloqueo (con A2A calcula)", engine, with_(
                    b, superposition=C("WeightedSum"), **dict(blockage(engine), blockage_superposition=C("MaxSum"))),
                 "R9f" if engine == PUD else None),
            ]
    return out


class FrontierTest(unittest.TestCase):
    def test_the_plugin_refuses_exactly_where_pywake_stops_with_the_rule_of_the_row(self):
        for name, engine, config, code in rows():
            calculated = 0
            for n, flow_map in RUNS:
                with self.subTest(row=name, engine=engine, turbines=n, map=flow_map):
                    stops = pywake_stops(config, n, flow_map)
                    calculated += not stops
                    codes = refusal(config, n, flow_map)
                    self.assertEqual(bool(codes), stops)
                    if codes:
                        self.assertTrue(set(code if isinstance(code, tuple) else (code,)) & set(codes), codes)
            with self.subTest(row=name, engine=engine):  # the row reaches what it is about
                self.assertTrue(calculated if code is None else calculated < len(RUNS))

    def test_none_where_pywake_reads_it_depending_on_the_values_is_an_error_of_the_calculation(self):
        # PUD compares max_iter only when its first pass does not meet the tolerance: with a blockage and two turbines
        # it fails, without blockage (or with one turbine) it calculates. WeightedSum reads max_err, max_iter and
        # weight_limit only when a contribution passes its delta. They depend on the values: no rule, the error of the
        # calculation with its cause (decision 1 of #46a).
        b = base(PUD)
        none = with_(b, engine=C(PUD, **dict(b.engine.params, max_iter=None)))
        cases = [(none, False), (with_(none, **blockage(PUD)), True)]
        for engine in (PDW, A2A, PUD):
            for arg in ("max_err", "max_iter", "weight_limit"):
                cases += [(with_(base(engine), superposition=C("WeightedSum", **{arg: None})), True),
                          (with_(base(engine), superposition=C("WeightedSum", delta=1e6, **{arg: None})), False)]
        for config, stops in cases:
            with self.subTest(config=config.to_dict()):
                self.assertFalse(plugin_refuses(config, 2))
                self.assertEqual(pywake_stops(config, 2), stops)

    def test_gaussian_overlap_without_its_libraries_where_its_table_is_read(self):
        # R13: the table of GaussianOverlapAvgModel is read where the rotor of the deficit is evaluated
        # (gaussian_overlap_model.py:14-20, 42); without h5py, the plugin refuses it exactly there. In a blockage it
        # stops before reading it (R16, :36-38): R13 is not its reason.
        for engine in (PDW, A2A, PUD):
            config = with_(base(engine), rotor=C("GaussianOverlapAvgModel"))
            for n, flow_map in RUNS:
                with self.subTest(engine=engine, turbines=n, map=flow_map), \
                        mock.patch.dict(sys.modules, {"h5py": None, "h5netcdf": None}), \
                        mock.patch.object(val, "missing_gaussian_overlap_modules", return_value=["h5py"]):
                    self.assertEqual(plugin_refuses(config, n, flow_map), pywake_stops(config, n, flow_map))
        config = with_(base(A2A), **blockage(A2A, rotorAvgModel=C("GaussianOverlapAvgModel")))
        with mock.patch.object(val, "missing_gaussian_overlap_modules", return_value=["h5py"]):
            self.assertEqual(refusal(config, 1), ["R16"])
            # Nor where an earlier stage stops (R8: the engine is not built). At the same stage, every cause that stops
            # PyWake on its own: the deficit evaluated before the table (k = None, R19) and R18 after it
            # (evidencias/consistencia/q5d_r2_comprobaciones), each with R13.
            config = with_(base(A2A), rotor=C("GaussianOverlapAvgModel"), superposition=C("CumulativeWakeSum"))
            self.assertEqual(refusal(config, 1), ["R8"])
            go = with_(base(PDW), rotor=C("GaussianOverlapAvgModel"))
            for config, codes in (
                    (with_(go, deficit=C(go.deficit.name, **dict(go.deficit.params, k=None))), ["R13", "R19"]),
                    (with_(go, ground=C("Mirror", superpositionModel=C("WeightedSum"))), ["R13", "R18"])):
                with self.subTest(config=config.to_dict()):
                    self.assertEqual(sorted(refusal(config, 2)), codes)

    def test_a_cause_pywake_never_reaches_is_not_given(self):
        # The arguments of a sum PyWake cannot call (R18 in a ground, R6 as the blockage superposition): it stops
        # before reading them; R13 where the table is never read (R11, R16).
        b = base(A2A)
        with mock.patch.object(val, "missing_gaussian_overlap_modules", return_value=["h5py"]):
            for config, codes in (
                    (with_(b, superposition=C("CumulativeWakeSum"),
                           ground=C("Mirror", superpositionModel=C("WeightedSum", delta=None))), ["R18"]),
                    (with_(b, **dict(blockage(A2A), blockage_superposition=C("WeightedSum", delta=None))), ["R6"]),
                    (with_(b, **dict(blockage(A2A), blockage_superposition=C("CumulativeWakeSum", alpha=None))),
                     ["R6"]),
                    (with_(base(A2A, "NOJDeficit"), rotor=C("GaussianOverlapAvgModel")), ["R11"]),
                    (with_(b, **blockage(A2A, "VortexDipole", rotorAvgModel=C("GaussianOverlapAvgModel"))),
                     ["R16"])):
                with self.subTest(config=config.to_dict()):
                    self.assertEqual(refusal(config, 1), codes)
                    self.assertTrue(pywake_stops(config, 1))

    def test_the_layout_notes_with_any_layout_and_from_two_or_three_turbines(self):
        # All2AllIterative fails with one turbine: a conflict (validate); PropagateDownwind from the second: a note
        # with its scope (layout_issues without the turbines), never a barrier.
        a2a = with_(base(A2A), superposition=C("WeightedSum"), ground=C("Mirror"))
        pdw = with_(base(PDW), superposition=C("WeightedSum"), ground=C("Mirror"))
        self.assertEqual([i.code for i in val.validate(a2a)], ["R9"])
        self.assertEqual(val.validate(pdw), [])
        notes = val.layout_issues(pdw)
        self.assertEqual([i.code for i in notes], ["R9"])
        self.assertIn("Por esta causa, con PropagateDownwind, PyWake", notes[0].text)
        self.assertIn("se detiene desde la segunda turbina", notes[0].text)
        self.assertEqual(val.layout_issues(pdw, 1), [])
        self.assertIn("ni con una sola turbina", val.map_issues(pdw)[0].text)
        # CumulativeWakeSum with alpha = None: from the third turbine, and the map from the second.
        alpha = with_(base(PDW), superposition=C("CumulativeWakeSum", alpha=None))
        self.assertIn("se detiene desde la tercera", val.layout_issues(alpha)[0].text)
        self.assertEqual(val.layout_issues(alpha, 2), [])
        self.assertEqual(val.map_issues(alpha), [])
        self.assertIn("desde la segunda turbina", val.map_issues(alpha, 2)[0].text)
        # The ground of the deficit with CumulativeWakeSum: not evaluated in the AEP; in the map, with R9e, both
        # causes (each stops the map on its own: without the other, PyWake meets it).
        ground = with_(base(PDW), superposition=C("CumulativeWakeSum"),
                       ground=C("Mirror", superpositionModel=C("SqrMaxSum")))
        self.assertEqual(val.layout_issues(ground), [])
        self.assertEqual([i.code for i in val.map_issues(ground)], ["R18", "R9e"])

    def test_an_unpacked_list_of_another_length_is_not_said_to_be_kept(self):
        # cTI is unpacked (c1, c2 = self.cTI): three elements are R20 where PyWake reads it, not elements kept without
        # effect (decision 6.2 of #64).
        from VelantisWind.ag_core.log_text import shown
        from VelantisWind.ag_core.wake_setup.notices import argument_warnings
        for name in ("TurboGaussianDeficit", "TurboNOJDeficit"):
            b = base(PDW, name)
            config = with_(b, deficit=C(name, **dict(b.deficit.params, cTI=[1.5, 0.8, 99.0])))
            with self.subTest(name):
                texts = [str(shown(t, lambda x: x)) for ts in argument_warnings(config).values() for t in ts]
                self.assertFalse([t for t in texts if "cTI" in t])
                self.assertEqual([i.code for i in val.layout_issues(config)], ["R20"])

    def test_the_route_of_a_ground_in_a_blockage_is_translated(self):
        config = with_(base(A2A), **blockage(A2A, groundModel=C("Mirror", superpositionModel=C("WeightedSum"))))
        from VelantisWind import i18n, results_dialog  # noqa: F401 - the tables the application registers
        issue = next(i for i in val.validate(config) if i.code == "R18")
        with mock.patch.object(i18n, "current_language", return_value="en"):
            text = issue.translated(i18n.tr_text)
        self.assertIn("«blockage · groundModel»", text)


if __name__ == "__main__":
    unittest.main()
