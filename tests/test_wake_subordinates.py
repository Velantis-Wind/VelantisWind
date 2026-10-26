# -*- coding: utf-8 -*-
"""The inventory of the arguments of the subordinate objects (#64, Q1), against PyWake 2.6.18.

The table is complete (every argument of each class is offered, excluded with its reason, or already a position of the
plugin), consistent with the signatures (kinds, lengths, choices, families), and each argument offered changes the
calculation in its position in a synthetic case (the effective wind speed, the effective TI or the iterations; not
necessarily the AEP), while each exclusion «without effect» has none.
"""
import inspect
import unittest
import warnings

import numpy as np

from VelantisWind.ag_core.wake_setup import subordinates as sub

warnings.filterwarnings("ignore", module="py_wake")

from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit, NiayifarGaussianDeficit  # noqa: E402
from py_wake.deficit_models.noj import NOJDeficit  # noqa: E402
from py_wake.deficit_models.utils import ct2a_madsen, ct2a_mom1d  # noqa: E402
from py_wake.examples.data.hornsrev1 import Hornsrev1Site, V80  # noqa: E402
from py_wake.ground_models import Mirror  # noqa: E402
from py_wake.rotor_avg_models import CGIRotorAvg, RotorCenter  # noqa: E402
from py_wake.superposition_models import LinearSum, SquaredSum  # noqa: E402
from py_wake.wind_farm_models import All2AllIterative, PropagateDownwind, PropagateUpDownIterative  # noqa: E402

SITE, WT = Hornsrev1Site(), V80()
# Three turbines in a row and one to the side (the case of the inventory, evidencias/q1/comun.py).
X, Y = np.array([0.0, 400.0, 800.0, 400.0]), np.array([0.0, 0.0, 0.0, 200.0])
WD, WS = [260.0, 270.0, 280.0], [6.0, 8.0, 10.0, 12.0]
BLOCKAGES = ("SelfSimilarityDeficit", "SelfSimilarityDeficit2020", "VortexCylinder", "VortexDipole", "RankineHalfBody",
             "Rathmann", "RathmannScaled", "HybridInduction")
TURBULENCES = ("STF2017TurbulenceModel", "STF2005TurbulenceModel", "GCLTurbulence", "CrespoHernandez")
ENGINES = ("PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative")
# The classes whose arguments the inventory covers, written here independently of the table.
OWNERS = ENGINES + ("CGIRotorAvg", "EqGridRotorAvg", "GaussianOverlapAvgModel", "Mirror", "MultiMirror", "WeightedSum",
                    "CumulativeWakeSum", "IECWeight") + TURBULENCES + BLOCKAGES

# The arguments of each class that are positions of the plugin already (#46a) or the inputs of the engine.
ALREADY = {e: {"site", "windTurbines", "wake_deficitModel", "superpositionModel", "blockage_deficitModel",
               "turbulenceModel"} for e in ENGINES}
ALREADY.update({b: {"superpositionModel", "use_effective_ws"} for b in BLOCKAGES})

# A value other than the signature's for each argument offered, and the case that shows its effect.
PROBE = {
    ("All2AllIterative", "convergence_tolerance"): None,
    ("PropagateUpDownIterative", "convergence_tolerance"): 1e-1,
    ("PropagateUpDownIterative", "max_iter"): 1,
    ("CGIRotorAvg", "n"): 4, ("EqGridRotorAvg", "n"): 2,
    ("Mirror", "superpositionModel"): "SquaredSum",
    ("MultiMirror", "mirror_height"): 50.0, ("MultiMirror", "n_reps"): 4, ("MultiMirror", "superpositionModel"): "SquaredSum",
    ("WeightedSum", "delta"): 0.0, ("WeightedSum", "max_err"): 0.1, ("WeightedSum", "max_iter"): 1,
    ("WeightedSum", "weight_limit"): 1.0, ("CumulativeWakeSum", "alpha"): 1.0,
    ("STF2017TurbulenceModel", "c"): [1.5, 1.6], ("CrespoHernandez", "c"): [1.0, 0.8325, -0.0325, -0.32],
    ("CrespoHernandez", "ct2a"): ct2a_mom1d, ("IECWeight", "distance_limit"): 20,
    ("SelfSimilarityDeficit", "ss_gamma"): 1.3, ("SelfSimilarityDeficit", "ss_lambda"): 0.8,
    ("SelfSimilarityDeficit", "ss_eta"): 2.0, ("SelfSimilarityDeficit2020", "r12p"): [-0.5, 0.4897],
    ("SelfSimilarityDeficit2020", "fgp"): None,  # fgp[2] = 1.3, below
    ("SelfSimilarityDeficit2020", "ngp"): None,  # ngp × 1.1, below
    ("RankineHalfBody", "high_ct_mod"): True, ("HybridInduction", "switch_radius"): 2.0,
}
COMMON_BLOCKAGE_PROBE = {"ct2a": ct2a_mom1d, "limiter": 25.0, "exclude_wake": False, "upstream_only": True,
                         "rotorAvgModel": "CGIRotorAvg", "groundModel": "Mirror", "ss_alpha": 1.5, "ss_beta": 1.0,
                         "sct": 1.5}


def obj(name, **kwargs):
    return sub.resolve(name)(**kwargs) if name is not None else None


def component(option):
    """An object of an option of a family (``None``: PyWake's None)."""
    return None if option.name is None else sub.resolve_option(option)()


def probe_of(arg):
    key = (arg.owner, arg.name)
    if key == ("SelfSimilarityDeficit2020", "fgp"):
        v = list(np.asarray(sub.signature_default(arg), float)); v[2] = 1.3
        return v
    if key == ("SelfSimilarityDeficit2020", "ngp"):
        return list(np.asarray(sub.signature_default(arg), float) * 1.1)
    if key in PROBE:
        return PROBE[key]
    if arg.owner in BLOCKAGES and arg.name in COMMON_BLOCKAGE_PROBE:
        return COMMON_BLOCKAGE_PROBE[arg.name]
    if arg.kind == sub.COMPONENT:
        default = sub.signature_default(arg)
        names = [o.name for o in sub.options(arg)]
        current = type(default).__name__ if default is not None else None
        return next(n for n in names if n != current)
    raise KeyError(key)


def value(arg, v):
    """The PyWake value of a probe: a class name of a COMPONENT becomes an object of that option."""
    if arg.kind != sub.COMPONENT:
        return v
    return component(next(o for o in sub.options(arg) if o.name == v))


def state(wfm, x=X, y=Y):
    r = wfm(x, y, wd=WD, ws=WS)
    out = [r.WS_eff.values, r.TI_eff.values, np.asarray(getattr(wfm, "iterations", 0))]
    assert all(np.isfinite(a).all() for a in out[:2])
    return out


def same(a, b):
    return all(np.array_equal(u, v) for u, v in zip(a, b))


def case(owner, **kwargs):
    """The wind farm model where an argument of ``owner`` acts, with ``kwargs`` for the owner."""
    if owner in ENGINES:
        return sub.resolve(owner)(SITE, WT, BastankhahGaussianDeficit(use_effective_ws=True),
                                  blockage_deficitModel=obj("SelfSimilarityDeficit2020", use_effective_ws=True),
                                  **kwargs)
    if owner in ("CGIRotorAvg", "EqGridRotorAvg"):
        return PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(rotorAvgModel=obj(owner, **kwargs)))
    if owner in ("Mirror", "MultiMirror"):
        return PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(groundModel=obj(owner, **kwargs)))
    if owner in ("WeightedSum", "CumulativeWakeSum"):
        return PropagateDownwind(SITE, WT, BastankhahGaussianDeficit(), superpositionModel=obj(owner, **kwargs))
    if owner in TURBULENCES:
        # NOJ (a top-hat wake) with AreaOverlapAvgModel in the turbulence, which needs one; Niayifar otherwise.
        top_hat = type(kwargs.get("rotorAvgModel")).__name__ == "AreaOverlapAvgModel"
        deficit = NOJDeficit() if top_hat else NiayifarGaussianDeficit()
        return PropagateDownwind(SITE, WT, deficit, turbulenceModel=obj(owner, **kwargs))
    if owner == "IECWeight":
        return PropagateDownwind(SITE, WT, NiayifarGaussianDeficit(),
                                 turbulenceModel=obj("STF2017TurbulenceModel", weight_function=obj(owner, **kwargs)))
    if owner in BLOCKAGES:
        return All2AllIterative(SITE, WT, BastankhahGaussianDeficit(), blockage_deficitModel=obj(owner, **kwargs))
    raise KeyError(owner)


class TableTest(unittest.TestCase):
    def test_every_argument_is_offered_excluded_or_already_a_position(self):
        self.assertEqual({a.owner for a in sub.ARGS} | {e.owner for e in sub.EXCLUDED}, set(OWNERS))
        for owner in OWNERS:
            signature = {n for n, p in inspect.signature(sub.resolve(owner).__init__).parameters.items()
                         if n != "self" and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
            offered = {a.name for a in sub.args_of(owner)}
            excluded = {e.name for e in sub.excluded_of(owner)}
            with self.subTest(owner=owner):
                self.assertFalse(offered & excluded)
                self.assertEqual(offered | excluded | (ALREADY.get(owner, set()) & signature), signature)

    def test_each_kind_agrees_with_its_signature(self):
        for a in sub.ARGS:
            d = sub.signature_default(a)
            with self.subTest(owner=a.owner, arg=a.name):
                if a.kind == sub.BOOL:
                    self.assertIsInstance(d, bool)
                elif a.kind == sub.CT2A:
                    self.assertIs(d, ct2a_madsen)
                elif a.kind == sub.LIST:
                    self.assertEqual(len(d), a.length)
                elif a.kind == sub.CHOICE:
                    self.assertIn(d, a.choices)
                elif a.kind in (sub.NUMBER, sub.INT, sub.NUMBER_OR_NONE):
                    self.assertIsInstance(d, (int, float))
                    self.assertNotIsInstance(d, bool)
                elif a.kind == sub.COMPONENT:
                    names = [o.name for o in sub.options(a)]
                    self.assertIn(type(d).__name__ if d is not None else None, names)
                    self.assertEqual(a.none, None in names)
                self.assertTrue(a.doc or a.kind == sub.COMPONENT)

    def test_every_limit_and_warning_is_described(self):
        for a in sub.ARGS:
            with self.subTest(owner=a.owner, arg=a.name):
                self.assertTrue(not a.limit or sub.LIMITS.get(a.limit))
                self.assertTrue(not a.warning or sub.WARNINGS.get(a.warning))

    def test_the_options_are_classes_of_pywake(self):
        for family, options in sub.FAMILIES.items():
            for o in options:
                with self.subTest(family=family, option=o.name):
                    if o.name is None:
                        self.assertTrue(o.label)
                    else:
                        self.assertTrue(inspect.isclass(sub.resolve_option(o)))


class EffectTest(unittest.TestCase):
    def test_each_argument_offered_changes_the_calculation(self):
        for a in sub.ARGS:
            if (a.owner, a.name) == ("RankineHalfBody", "exclude_wake"):
                continue  # its own geometry, below
            with self.subTest(owner=a.owner, arg=a.name):
                v = probe_of(a)
                self.assertFalse(same(state(case(a.owner)), state(case(a.owner, **{a.name: value(a, v)}))), v)

    def test_rankine_exclude_wake_with_a_turbine_beside_the_half_body(self):
        # In the common case the turbines downstream are inside the half-body, where the deficit is already 0
        # (rankinehalfbody.py:70); with one beside it, exclude_wake does change it (fuentes_pywake.md, S§11).
        x, y = np.array([0.0, 400.0]), np.array([0.0, 30.0])
        self.assertFalse(same(state(case("RankineHalfBody"), x, y),
                              state(case("RankineHalfBody", exclude_wake=False), x, y)))

    def test_every_option_of_a_component_calculates_in_its_position_or_has_its_rule(self):
        # Each option offered calculates in its position with several turbines, or PyWake stops with it where it
        # evaluates it between turbines and the plugin refuses it there with its rule of interaction (decision 6.1 of
        # #64: R16 in a blockage, R17 in a turbulence, R18 in a ground; their frontiers are tested against PyWake in
        # tests.test_wake_interaction); one left out for an owner, PyWake refuses it there.
        from VelantisWind.ag_core.wake_setup import validation as val
        from tests.test_wake_subordinates_fidelity import config_and_direct
        rule = {"rotor": lambda owner: "R16" if owner in BLOCKAGES else "R17", "ground_sum": lambda owner: "R18"}
        for a in sub.ARGS:
            if a.kind != sub.COMPONENT:
                continue
            offered = sub.options(a)
            for o in sub.FAMILIES[a.family]:
                with self.subTest(owner=a.owner, arg=a.name, option=o.name):
                    if o in offered:
                        try:
                            state(case(a.owner, **{a.name: component(o)}))
                        except Exception:
                            config = config_and_direct(a, o.name)[0]
                            self.assertIn(rule[a.family](a.owner),
                                          [i.code for i in val.validate(config) + val.layout_issues(config)])
                    else:  # left out for this owner: PyWake refuses it there
                        with self.assertRaises(Exception):
                            state(case(a.owner, **{a.name: component(o)}))

    def test_each_kind_is_what_pywake_takes(self):
        # A number takes a fraction and refuses None; an integer refuses a fraction; a number or None takes None; each
        # value of a closed set calculates and another one is refused.
        for a in sub.ARGS:
            if a.kind not in (sub.NUMBER, sub.INT, sub.NUMBER_OR_NONE, sub.CHOICE):
                continue
            d = sub.signature_default(a)
            with self.subTest(owner=a.owner, arg=a.name, kind=a.kind):
                if a.kind in (sub.NUMBER, sub.NUMBER_OR_NONE):
                    state(case(a.owner, **{a.name: d + 2.5 if d >= 0 else d - 2.5}))
                if a.kind == sub.NUMBER_OR_NONE:
                    state(case(a.owner, **{a.name: None}))
                elif a.kind != sub.CHOICE:
                    with self.assertRaises(Exception):
                        state(case(a.owner, **{a.name: None}))
                if a.kind == sub.INT:
                    with self.assertRaises(Exception):
                        state(case(a.owner, **{a.name: d + 0.5}))
                if a.kind == sub.CHOICE:
                    for v in a.choices:
                        state(case(a.owner, **{a.name: v}))
                    with self.assertRaises(Exception):
                        state(case(a.owner, **{a.name: max(a.choices) + 1}))

    def test_area_overlap_in_the_turbulence_of_gcl_and_crespo(self):
        for t in ("GCLTurbulence", "CrespoHernandez"):
            with self.subTest(turbulence=t):
                wfm = PropagateDownwind(SITE, WT, NOJDeficit(), turbulenceModel=obj(t))
                self.assertEqual(type(wfm.turbulenceModel.rotorAvgModel).__name__, "AreaOverlapAvgModel")
                state(wfm)


class ExclusionTest(unittest.TestCase):
    def test_stf2005_does_not_read_c(self):
        self.assertTrue(same(state(case("STF2005TurbulenceModel")),
                             state(case("STF2005TurbulenceModel", c=[3.0, 0.8]))))

    def test_the_ground_of_a_turbulence_is_never_called(self):
        for t in TURBULENCES:
            for engine in (PropagateDownwind, All2AllIterative):
                with self.subTest(turbulence=t, engine=engine.__name__):
                    a = engine(SITE, WT, NiayifarGaussianDeficit(), turbulenceModel=obj(t))
                    b = engine(SITE, WT, NiayifarGaussianDeficit(), turbulenceModel=obj(t, groundModel=Mirror()))
                    self.assertTrue(same(state(a), state(b)))

    def test_rotor_center_is_none_in_the_new_positions(self):
        turb = (case("STF2017TurbulenceModel"), case("STF2017TurbulenceModel", rotorAvgModel=RotorCenter()))
        block = (case("VortexDipole"), case("VortexDipole", rotorAvgModel=RotorCenter()))
        self.assertTrue(same(state(turb[0]), state(turb[1])))
        self.assertTrue(same(state(block[0]), state(block[1])))

    def test_every_exclusion_has_its_reason(self):
        for e in sub.EXCLUDED:
            with self.subTest(owner=e.owner, arg=e.name):
                self.assertTrue(e.reason)
                self.assertIn(e.name, inspect.signature(sub.resolve(e.owner).__init__).parameters)


if __name__ == "__main__":
    unittest.main()
