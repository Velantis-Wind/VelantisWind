# -*- coding: utf-8 -*-
"""The resolutions of the rules and the warnings of Q5e (#64, decisions 6.3 and 6.4).

Each resolution names only options that take its cause away without falling into another rule: applied to its case
(one where the rule is the only cause), the plugin refuses nothing with one and two turbines and in the map, and PyWake
written by hand calculates. SquaredSum is never proposed in a blockage: it stops with a speed-up (decision 8 of
#46a), and it has its persistent warning.
"""
import unittest
import warnings

import numpy as np

from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import notices
from VelantisWind.ag_core.wake_setup import validation as val
from tests.test_wake_interaction import A2A, PDW, PUD, base, blockage, refusal, pywake_stops
from tests.test_wake_setup_factory import C, with_

warnings.filterwarnings("ignore", module="py_wake")


def cases():
    """``(code, config, options)``: a case of the rule, and each option of its resolution applied to it."""
    b, a2a, pud = base(PDW), base(A2A), base(PUD)
    noj = with_(base(PDW, "NOJDeficit"), rotor=None)
    sums = [C(s) for s in ("LinearSum", "SquaredSum", "MaxSum")]
    node_rotors = [None, C("RotorCenter"), C("CGIRotorAvg", n=7), C("EqGridRotorAvg", n=4)]
    bl = with_(a2a, **blockage(A2A))
    pud_bl = with_(pud, **blockage(PUD))
    out = [
        ("R1", with_(b, **blockage(PDW)),
         [with_(b, engine=a2a.engine, **blockage(A2A)), with_(pud, **blockage(PUD)), b]),
        ("R1", with_(noj, **blockage(PDW)),  # NOJ has no use_effective_ws: PUD is not proposed (R3)
         [with_(noj, engine=a2a.engine, **blockage(A2A)), noj]),
        ("R7", with_(base(PDW, "GCLDeficit"), superposition=C("WeightedSum")),
         [with_(base(PDW, "GCLDeficit"), superposition=s) for s in sums]),
        ("R8", with_(b, rotor=C("GaussianOverlapAvgModel"), superposition=C("WeightedSum")),
         [with_(b, rotor=r, superposition=C("WeightedSum")) for r in node_rotors if r != C("RotorCenter")]),
        ("R9b", with_(noj, superposition=C("WeightedSum")), [with_(noj, superposition=s) for s in sums]),
        ("R9", with_(b, superposition=C("WeightedSum"), ground=C("Mirror")),
         [with_(b, superposition=C("WeightedSum"), ground=None)]
         + [with_(b, superposition=s, ground=C("Mirror")) for s in sums]),
        ("R9c", with_(noj, superposition=C("CumulativeWakeSum")), [with_(noj, superposition=s) for s in sums]),
        ("R10", with_(b, rotor=C("AreaOverlapAvgModel")), [with_(b, rotor=r) for r in node_rotors]),
        ("R11", with_(noj, rotor=C("GaussianOverlapAvgModel")), [with_(noj, rotor=r) for r in node_rotors]),
        ("R12", with_(b, rotor=C("CGIRotorAvg", n=7), ground=C("MultiMirror")),
         [with_(b, rotor=None, ground=C("MultiMirror")), with_(b, rotor=C("CGIRotorAvg", n=7), ground=C("Mirror"))]
         + [with_(b, rotor=C("CGIRotorAvg", n=7), ground=C("MultiMirror", superpositionModel=s)) for s in sums]),
        ("R12", with_(a2a, **blockage(A2A, rotorAvgModel=C("CGIRotorAvg", n=7), groundModel=C("MultiMirror"))),
         [with_(a2a, **blockage(A2A, groundModel=C("MultiMirror"))),
          with_(a2a, **blockage(A2A, rotorAvgModel=C("CGIRotorAvg", n=7), groundModel=C("Mirror")))]
         + [with_(a2a, **blockage(A2A, rotorAvgModel=C("CGIRotorAvg", n=7),
                                  groundModel=C("MultiMirror", superpositionModel=C(s))))
            for s in ("LinearSum", "MaxSum")]),
        ("R16", with_(a2a, **blockage(A2A, rotorAvgModel=C("AreaOverlapAvgModel"))),
         [with_(a2a, **blockage(A2A, rotorAvgModel=r)) for r in (None, C("CGIRotorAvg", n=7), C("EqGridRotorAvg", n=4))]),
        ("R17", with_(base(A2A, "NiayifarGaussianDeficit"),
                      turbulence=C("STF2017TurbulenceModel", rotorAvgModel=C("AreaOverlapAvgModel"))),
         [with_(base(A2A, "NiayifarGaussianDeficit"), turbulence=C("STF2017TurbulenceModel", rotorAvgModel=r))
          for r in (None, C("CGIRotorAvg", n=7), C("EqGridRotorAvg", n=4))]),
        ("R18", with_(a2a, ground=C("Mirror", superpositionModel=C("WeightedSum"))),
         [with_(a2a, ground=C("Mirror", superpositionModel=s)) for s in sums]),
        ("R18", with_(a2a, **blockage(A2A, groundModel=C("Mirror", superpositionModel=C("WeightedSum")))),
         [with_(a2a, **blockage(A2A, groundModel=C("Mirror", superpositionModel=C(s)))) for s in ("LinearSum", "MaxSum")]),
        ("R6", with_(bl, blockage_superposition=C("WeightedSum")),
         [with_(bl, blockage_superposition=C(s)) for s in ("LinearSum", "MaxSum")]),
        ("R6", with_(pud_bl, superposition=C("WeightedSum"), blockage_superposition=C("CumulativeWakeSum")),
         [with_(pud_bl, superposition=C("WeightedSum"), blockage_superposition=C("LinearSum"))]),
        ("R5", with_(pud_bl, blockage_superposition=C("SquaredSum")),
         [with_(pud_bl, blockage_superposition=C(s)) for s in ("LinearSum", "MaxSum")]),
        ("R9f", with_(pud_bl, superposition=C("WeightedSum"), blockage_superposition=C("MaxSum")),
         [with_(pud_bl, superposition=C("WeightedSum")), with_(bl, superposition=C("WeightedSum"),
                                                               blockage_superposition=C("MaxSum")),
          with_(pud, superposition=C("WeightedSum"))]
         + [with_(pud_bl, superposition=s, blockage_superposition=C("MaxSum")) for s in sums]),
    ]
    # R9d with All2AllIterative (the AEP) and R9e (the map) with PropagateDownwind: CumulativeWakeSum and a ground that
    # inherits it (a sum of its own would resolve the AEP of R9d and keep R9e: not proposed).
    r9d = with_(a2a, superposition=C("CumulativeWakeSum"), ground=C("Mirror"))
    out.append(("R9d", r9d, [with_(r9d, ground=None)] + [with_(r9d, superposition=s) for s in sums]))
    r9e = with_(b, superposition=C("CumulativeWakeSum"), ground=C("Mirror"))
    out.append(("R9e", r9e, [with_(r9e, ground=None)] + [with_(r9e, superposition=s) for s in sums]))
    # R8 with NOJ: another rotor would be R9b; another sum.
    out.append(("R8", with_(base(PDW, "NOJDeficit"), superposition=C("WeightedSum")),
                [with_(base(PDW, "NOJDeficit"), superposition=s) for s in sums]))
    # R8 with a ground: another rotor alone would be R9, R9d or, in the map, R9e (discrete round 1, A1); no ground and
    # another rotor, or another sum.
    rc, mirror = C("RotorCenter"), C("Mirror")
    other_rotors = [None, C("CGIRotorAvg", n=7), C("EqGridRotorAvg", n=4)]
    for case in (with_(b, rotor=rc, ground=mirror, superposition=C("WeightedSum")),
                 with_(a2a, rotor=rc, ground=mirror, superposition=C("CumulativeWakeSum")),
                 with_(b, rotor=rc, ground=mirror, superposition=C("CumulativeWakeSum"))):
        out.append(("R8", case, [with_(case, ground=None, rotor=r) for r in other_rotors]
                    + [with_(case, superposition=s) for s in sums]))
    # MultiMirror inheriting the sum under a rotor average: another sum alone would be R12; with a sum of its own too.
    mm = C("MultiMirror")
    r8 = with_(b, rotor=rc, ground=mm, superposition=C("WeightedSum"))
    out.append(("R8", r8, [with_(r8, ground=None, rotor=r) for r in other_rotors]
                + [with_(r8, superposition=s, ground=C("MultiMirror", superpositionModel=s)) for s in sums]))
    for code, case in (("R9b", with_(noj, rotor=C("CGIRotorAvg", n=7), ground=mm, superposition=C("WeightedSum"))),
                       ("R9c", with_(noj, rotor=C("CGIRotorAvg", n=7), ground=mm,
                                     superposition=C("CumulativeWakeSum"))),
                       ("R7", with_(base(PDW, "GCLDeficit"), rotor=C("CGIRotorAvg", n=7), ground=mm,
                                    superposition=C("WeightedSum")))):
        out.append((code, case, [with_(case, superposition=s, ground=C("MultiMirror", superpositionModel=s))
                                 for s in sums]))
    for code, case in (("R9", with_(b, rotor=C("CGIRotorAvg", n=7), ground=mm, superposition=C("WeightedSum"))),
                       ("R9d", with_(a2a, rotor=C("CGIRotorAvg", n=7), ground=mm,
                                     superposition=C("CumulativeWakeSum"))),
                       ("R9e", with_(b, rotor=C("CGIRotorAvg", n=7), ground=mm, superposition=C("CumulativeWakeSum")))):
        out.append((code, case, [with_(case, ground=None)] + [
            with_(case, superposition=s, ground=C("MultiMirror", superpositionModel=s)) for s in sums]))
    return out


class ResolutionTest(unittest.TestCase):
    def test_each_resolution_takes_its_cause_away_without_another_rule(self):
        for code, case, options in cases():
            with self.subTest(code=code, case=case.to_dict()):
                self.assertIn(code, refusal(case, 2) + refusal(case, 1, True))
            for option in options:
                for n, flow_map in ((1, False), (2, False), (1, True), (2, True)):
                    with self.subTest(code=code, option=option.to_dict(), turbines=n, map=flow_map):
                        self.assertEqual(refusal(option, n, flow_map), [])
                        self.assertFalse(pywake_stops(option, n, flow_map))

    def test_the_resolution_names_the_sum_of_multimirror_where_r12_would_follow(self):
        case = with_(base(PDW), rotor=C("CGIRotorAvg", n=7), ground=C("MultiMirror"), superposition=C("WeightedSum"))
        issue = next(i for i in val.layout_issues(case) if i.code == "R9")
        self.assertIn("y una superposición propia para MultiMirror", issue.text)
        self.assertNotIn("superposición propia", next(
            i for i in val.layout_issues(with_(case, ground=C("Mirror"))) if i.code == "R9").text)

    def test_r8_with_a_ground_names_no_ground_or_another_sum(self):
        # The options of these texts are those of the cases of R8 with a ground in ``cases``.
        for ground, rotor, text in (
                (C("Mirror"), C("RotorCenter"), "Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o EqGridRotorAvg, "
                                                "o LinearSum, SquaredSum o MaxSum."),
                (C("MultiMirror"), C("RotorCenter"), "Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o "
                 "EqGridRotorAvg, o LinearSum, SquaredSum o MaxSum y una superposición propia para MultiMirror.")):
            case = with_(base(PDW), rotor=rotor, ground=ground, superposition=C("WeightedSum"))
            with self.subTest(ground=ground.name):
                self.assertEqual(next(i for i in val.validate(case) if i.code == "R8").resolution, text)

    def test_r1_names_propagateupdowniterative_only_where_its_blockage_superposition_takes_it(self):
        # Discrete round 3, A1: with SquaredSum in a blockage with up- and downstream effects PUD is R5 (any layout),
        # and with MaxSum and an iterative sum, R9f; All2AllIterative calculates.
        both = ("Elige All2AllIterative (o PropagateUpDownIterative, con use_effective_ws en el déficit y en el bloqueo), "
                "o quita el bloqueo.")
        a2a_only = "Elige All2AllIterative, o quita el bloqueo."
        b = base(PDW)
        for bsup, sup, upstream_only, text, pud_code in (("LinearSum", "LinearSum", False, both, None),
                                                         ("SquaredSum", "LinearSum", False, a2a_only, "R5"),
                                                         ("SquaredSum", "LinearSum", True, both, None),
                                                         ("MaxSum", "WeightedSum", False, a2a_only, "R9f"),
                                                         ("MaxSum", "LinearSum", False, both, None)):
            case = with_(b, superposition=C(sup), blockage=C("SelfSimilarityDeficit2020", upstream_only=upstream_only),
                         blockage_superposition=C(bsup))
            with self.subTest(bsup=bsup, sup=sup, upstream_only=upstream_only):
                self.assertEqual(next(i for i in val.validate(case) if i.code == "R1").resolution, text)
                pud = with_(case, engine=base(PUD).engine,
                            deficit=C(b.deficit.name, **dict(b.deficit.params, use_effective_ws=True)),
                            blockage=C("SelfSimilarityDeficit2020", upstream_only=upstream_only, use_effective_ws=True))
                codes = refusal(pud, 2)
                self.assertEqual(codes, [pud_code] if pud_code else [], codes)
                self.assertEqual(refusal(with_(case, engine=base(A2A).engine), 2), [])

    def test_r9f_with_a_ground_names_only_what_takes_it_away(self):
        # Discrete round 1, A2: with a ground All2AllIterative stops from the first turbine (R9, R9d), unless it has no
        # ground; another sum with MultiMirror inheriting it under a rotor average is R12, unless MultiMirror has a sum
        # of its own. Each option named takes R9f away and adds nothing the case did not have (R9 with WeightedSum and a
        # ground; R9e in the map with CumulativeWakeSum and a ground), with one and two turbines and in the map.
        pud, a2a = with_(base(PUD), **blockage(PUD)), with_(base(A2A), **blockage(A2A))
        sums = [C(s) for s in ("LinearSum", "SquaredSum", "MaxSum")]
        cgi, mm = C("CGIRotorAvg", n=7), C("MultiMirror")
        # The texts, whole: their options are exactly those tried below.
        as_is = ("Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como "
                 "superposición de estelas, o quita el bloqueo.")
        no_ground = ("Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, "
                     "SquaredSum o MaxSum como superposición de estelas, o quita el bloqueo.")
        own_mm = ("Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, "
                  "SquaredSum o MaxSum como superposición de estelas con una superposición propia para MultiMirror, o "
                  "quita el bloqueo.")
        without = ("Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como "
                   "superposición de estelas con Suelo «Ninguno», o quita el bloqueo.")
        # (sum of the wakes, ground, rotor, the ground All2AllIterative keeps, the ground of each other sum, text)
        keep = lambda ground: (lambda s: ground)  # noqa: E731
        own = lambda s: C("MultiMirror", superpositionModel=s)  # noqa: E731
        cases = [("CumulativeWakeSum", C("Mirror"), None, None, keep(C("Mirror")), no_ground),
                 ("CumulativeWakeSum", mm, cgi, None, own, own_mm),
                 ("CumulativeWakeSum", C("Mirror", superpositionModel=C("LinearSum")), None, "keep",
                  keep(C("Mirror", superpositionModel=C("LinearSum"))), as_is),
                 ("WeightedSum", C("Mirror"), None, None, keep(C("Mirror")), no_ground),
                 ("WeightedSum", mm, cgi, None, own, own_mm)]
        # Discrete round 2, A2: a sum of its own the ground cannot call (R18), which All2AllIterative and another sum
        # make PyWake evaluate: both without the ground.
        for bad in ("SqrMaxSum", "WeightedSum", "CumulativeWakeSum"):
            for sup in ("CumulativeWakeSum", "WeightedSum"):
                for ground in ("Mirror", "MultiMirror"):
                    cases.append((sup, C(ground, superpositionModel=C(bad)), None, None, keep(None), without))
        # Discrete round 3, A2: a None CumulativeWakeSum leaves out with PUD (R19), in the ground (both changes without
        # it) or in the deficit (neither change: only the blockage).
        cases.append(("CumulativeWakeSum", C("MultiMirror", mirror_height=None, superpositionModel=C("LinearSum")), None,
                      None, keep(None), without))
        only_blockage = "Elige LinearSum para el bloqueo, o quita el bloqueo."
        cases.append(("CumulativeWakeSum", None, None, "none", None, only_blockage))
        for sup, ground, rotor, a2a_ground, plain_ground, text in cases:
            case = with_(pud, superposition=C(sup), blockage_superposition=C("MaxSum"), ground=ground, rotor=rotor)
            if ground is None:  # ct2a None in the deficit
                case = with_(case, deficit=C(case.deficit.name, **dict(case.deficit.params, ct2a=None)))
            with self.subTest(sup=sup, ground=ground and ground.name, own=ground and str(ground.params)):
                self.assertEqual(next(i for i in val.layout_issues(case, 2) if i.code == "R9f").resolution, text)
                to_a2a = with_(case, engine=a2a.engine, blockage=a2a.blockage)
                self.assertEqual(refusal(to_a2a, 1) == [], a2a_ground == "keep")
                options = [with_(case, blockage_superposition=C("LinearSum")),
                           with_(case, blockage=None, blockage_superposition=base(PUD).blockage_superposition)]
                if a2a_ground != "none":
                    options.append(to_a2a if a2a_ground == "keep" else with_(to_a2a, ground=None))
                else:  # neither All2AllIterative nor another sum: refused in the AEP
                    self.assertTrue(refusal(with_(to_a2a, ground=None), 2))
                    self.assertTrue(all(refusal(with_(case, superposition=s), 2) for s in sums))
                if plain_ground is not None:
                    options += [with_(case, superposition=s, ground=plain_ground(s)) for s in sums]
                for option in options:
                    for n, flow_map in ((1, False), (2, False), (1, True), (2, True)):
                        # Every cause of the case at every stage (R9f, a stage earlier than the map, hides R9e).
                        before = {i.code for i in val.validate(case) + val.layout_issues(case, n)
                                  + (val.map_issues(case, n) if flow_map else [])} - {"R9f"}
                        after = refusal(option, n, flow_map)
                        self.assertLessEqual(set(after), before, (option.to_dict(), n, flow_map))
                        if not after:
                            self.assertFalse(pywake_stops(option, n, flow_map), (option.to_dict(), n, flow_map))

    def test_squared_sum_in_a_blockage_has_its_warning(self):
        bl = with_(base(A2A), **blockage(A2A))
        for config, where in ((with_(bl, blockage_superposition=C("SquaredSum")), "superposición del bloqueo"),
                              (with_(base(A2A), **blockage(A2A, groundModel=C(
                                  "Mirror", superpositionModel=C("SquaredSum")))),
                               "bloqueo · groundModel · superpositionModel")):
            with self.subTest(where=where):
                texts = [str(t) for t in notices.persistent_warnings(config)]
                self.assertTrue(any(f"con SquaredSum en «{where}»" in t and "aceleración" in t for t in texts), texts)
        self.assertFalse([t for t in notices.persistent_warnings(bl) if "SquaredSum" in str(t)])

    def test_the_warning_of_weight_limit_says_what_pywake_does(self):
        # The weight is min(ratio of convection velocities, weight_limit) (superposition_models.py:148): with 0, a
        # contribution of a positive ratio is cancelled and one of a negative ratio keeps its weight
        # (evidencias/consistencia/c2_weight_limit: -1, not 0).
        from py_wake.superposition_models import WeightedSum
        ones, zeros = np.ones((2, 1)), np.zeros((2, 1))
        value = WeightedSum(max_iter=1, weight_limit=0)(
            deficit_jxxx=ones, WS_xxx=np.array([10.0]), convection_velocity_jxxx=np.array([[-1.0], [1.0]]),
            sigma_sqr_jxxx=ones, cw_jxxx=zeros, hcw_jxxx=zeros, dh_jxxx=zeros, deficit_centre_jxxx=ones)
        self.assertEqual(float(np.ravel(value)[0]), -1.0)
        config = with_(base(A2A), superposition=C("WeightedSum", weight_limit=0.0))
        texts = [str(t) for ts in notices.argument_warnings(config).values() for t in ts]
        self.assertTrue(any("con un cociente positivo pesan 0.0 (con 0 se anulan" in t
                            and "con uno menor conservan el suyo" in t and "Si no itera" in t for t in texts), texts)
        self.assertFalse(any("PyWake anula" in t for t in texts))
        # Without iterating (count < max_iter is false: max_iter ≤ 0 or NaN) WeightedSum weighs nothing.
        for max_iter in (0, float("nan")):
            config = with_(base(A2A), superposition=C("WeightedSum", weight_limit=0.0, max_iter=max_iter))
            texts = [str(t) for ts in notices.argument_warnings(config).values() for t in ts]
            with self.subTest(max_iter=max_iter):
                self.assertFalse(any("weight_limit" in t for t in texts), texts)


if __name__ == "__main__":
    unittest.main()
