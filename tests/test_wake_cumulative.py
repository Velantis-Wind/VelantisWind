# -*- coding: utf-8 -*-
"""Decision 23(a): the arguments of the deficit that CumulativeWakeSum leaves without numerical effect, against PyWake.

The table of the catalogue (``CUMULATIVE_WITHOUT_EFFECT``) comes from the code of PyWake 2.6.18; these are its
regression tests. Each argument of the table gives, with CumulativeWakeSum, the same effective wind speed, Ct and
effective TI per turbine, direction and speed and the same AEP per turbine, bit for bit, while the same change does
change them with LinearSum; every other argument of the class changes the result with CumulativeWakeSum.
"""
import unittest

import numpy as np

from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import notices
from tests.test_wake_setup_factory import WD, WS, X, Y, C, build, codes, with_

PDW, A2A, PUD = "PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"


def base(engine, deficit, sup="CumulativeWakeSum"):
    """The class with its signature values, without ground, with a turbulence (so use_effective_ti can change alone) and
    the effective wind speed with PUD."""
    config = cfg.default_config(engine, deficit)
    params = dict(config.deficit.params)
    if engine == PUD:
        params["use_effective_ws"] = True
    return with_(config, deficit=C(deficit, **params), superposition=C(sup), turbulence=C("CrespoHernandez"),
                 ground=None)


def changed(config, arg):
    """``config`` with ``arg`` of the deficit changed (the ground: a Mirror)."""
    if arg == "groundModel":
        return with_(config, ground=C("Mirror"))
    params = dict(config.deficit.params)
    value = params[arg]
    if arg == "ct2a":
        value = "ct2a_mom1d" if value == "ct2a_madsen" else "ct2a_madsen"
    elif arg == "ctlim":
        value = 0.5  # 0.899 or 0.999 x 1.1 would clip no Ct
    elif isinstance(value, bool):
        value = not value
    elif isinstance(value, list):
        value = [value[0] * 1.1] + value[1:]
    else:
        value = value * 3 if arg == "deltawD" else value * 1.1
    return with_(config, deficit=C(config.deficit.name, **dict(params, **{arg: value})))


def state(config):
    """WS_eff, CT and TI_eff per turbine, direction and speed, and the AEP per turbine (finite)."""
    r = build(config)(X, Y, wd=WD, ws=WS)
    out = [r.WS_eff.values, r.CT.values, r.TI_eff.values, r.aep().sum(["wd", "ws"]).values]
    assert all(np.isfinite(a).all() for a in out)
    return out


def same(a, b):
    return all(np.array_equal(u, v) for u, v in zip(a, b))


# The classes the plugin calculates with CumulativeWakeSum, written here independently of the table (the NOJ family is
# R9c; GCL and Blondel are R7).
ACCEPTED = ("BastankhahGaussianDeficit", "NiayifarGaussianDeficit", "ZongGaussianDeficit",
            "CarbajofuertesGaussianDeficit", "TurboGaussianDeficit", "IEA37SimpleBastankhahGaussianDeficit")


def rows():
    """(engine, class, argument) of the table, as the plugin offers them (the ground with PDW and PUD)."""
    for name in ACCEPTED:
        args = cat.CUMULATIVE_WITHOUT_EFFECT[name]
        for engine in (PDW, A2A, PUD):
            if engine == PUD and name == "IEA37SimpleBastankhahGaussianDeficit":
                continue  # no use_effective_ws: refused with PUD (R3)
            for arg in args + (("groundModel",) if engine != A2A else ()):
                if not (arg == "use_effective_ws" and engine == PUD):
                    yield engine, name, arg


class WithoutEffectTest(unittest.TestCase):
    def test_the_table_covers_every_class_cumulative_calculates(self):
        calculable = {e.name for e in cat.entries(cat.DEFICIT) if codes(base(PDW, e.name)) == []}
        self.assertEqual(calculable, set(ACCEPTED))
        self.assertEqual(set(cat.CUMULATIVE_WITHOUT_EFFECT), set(ACCEPTED))

    def test_each_row_has_no_effect_with_cumulative_and_has_one_with_linear(self):
        for engine, name, arg in rows():
            with self.subTest(engine=engine, deficit=name, arg=arg):
                cws = base(engine, name)
                self.assertEqual(codes(changed(cws, arg)), [])
                self.assertTrue(same(state(cws), state(changed(cws, arg))))
                linear = base(engine, name, "LinearSum")
                self.assertFalse(same(state(linear), state(changed(linear, arg))))

    def test_turbo_gaussian_keeps_its_signature_ground_without_effect(self):
        # The Mirror() of its signature, with PDW and PUD (with A2A, R9d).
        for engine in (PDW, PUD):
            with self.subTest(engine=engine):
                config = with_(base(engine, "TurboGaussianDeficit"), ground=cfg.default_config(engine, "TurboGaussianDeficit").ground)
                self.assertEqual(config.ground, cfg.complete(C("Mirror")))
                self.assertTrue(same(state(config), state(with_(config, ground=None))))
                self.assertIn("groundModel (Mirror: superpositionModel)", notices.cumulative_without_effect(config))

    def test_the_other_arguments_change_the_result(self):
        # Those that enter sigma_ijlk, and the rotor; ctlim of Zong is apart (it never has an effect).
        for name in ACCEPTED:
            without = cat.CUMULATIVE_WITHOUT_EFFECT.get(name, ())
            config = base(PDW, name)
            for arg in config.deficit.params:
                if arg in without or (name, arg) == ("ZongGaussianDeficit", "ctlim"):
                    continue
                with self.subTest(deficit=name, arg=arg):
                    self.assertFalse(same(state(config), state(changed(config, arg))))
            with self.subTest(deficit=name, arg="rotorAvgModel"):
                self.assertFalse(same(state(config), state(with_(config, rotor=C("CGIRotorAvg", n=7)))))

    def test_zong_ctlim_has_no_effect_with_any_superposition(self):
        for sup in ("LinearSum", "CumulativeWakeSum"):
            with self.subTest(sup=sup):
                config = base(PDW, "ZongGaussianDeficit", sup)
                self.assertTrue(same(state(config), state(changed(config, "ctlim"))))


class NoticeTest(unittest.TestCase):
    def test_the_list_names_only_what_the_configuration_has(self):
        self.assertEqual(notices.cumulative_without_effect(base(PDW, "ZongGaussianDeficit")),
                         ["ct2a", "deltawD", "use_effective_ws"])
        self.assertEqual(notices.cumulative_without_effect(base(PUD, "ZongGaussianDeficit")), ["ct2a", "deltawD"])
        self.assertEqual(notices.cumulative_without_effect(with_(base(PDW, "BastankhahGaussianDeficit"),
                                                                 ground=C("MultiMirror"))),
                         ["ct2a", "use_effective_ws",
                          "groundModel (MultiMirror: mirror_height, n_reps, superpositionModel)"])
        self.assertEqual(notices.cumulative_without_effect(base(PDW, "IEA37SimpleBastankhahGaussianDeficit")), [])
        self.assertEqual(notices.cumulative_without_effect(base(PDW, "ZongGaussianDeficit", "LinearSum")), [])

    def test_the_warning_and_its_place(self):
        texts = [str(w) for w in notices.persistent_warnings(base(A2A, "NiayifarGaussianDeficit"))]
        self.assertEqual(len(texts), 2)
        self.assertIn("orden de las turbinas", texts[0])  # decision 19, kept
        self.assertIn("Configuración principal · PyWake 2.6.18 · All2AllIterative", texts[1])
        self.assertIn("no afectan al resultado numérico por esta ruta: ct2a, use_effective_ws.", texts[1])
        self.assertIn("sigue usando la velocidad efectiva", texts[1])
        self.assertIn("no describe las variantes del desglose", texts[1])
        # Without anything to list, only the warning of the order (and that of decision 16: this class has no
        # use_effective_ti, and base adds a turbulence).
        self.assertEqual(len(notices.persistent_warnings(base(PDW, "IEA37SimpleBastankhahGaussianDeficit"))), 2)
        self.assertEqual(notices.persistent_warnings(base(PDW, "NiayifarGaussianDeficit", "LinearSum")), [])

    def test_the_raster_adds_what_its_field_does_with_a_rotor(self):
        config = base(PDW, "BastankhahGaussianDeficit")
        self.assertEqual(notices.persistent_warnings(config, flow_map=True), notices.persistent_warnings(config))
        with_rotor = with_(config, rotor=C("CGIRotorAvg", n=7))
        field = [str(w) for w in notices.persistent_warnings(with_rotor, flow_map=True)]
        self.assertEqual(field[-1], notices.CUMULATIVE_FIELD_NOTE)
        self.assertNotIn(notices.CUMULATIVE_FIELD_NOTE, [str(w) for w in notices.persistent_warnings(with_rotor)])

    def test_the_texts_are_translated(self):
        from VelantisWind.ag_core.wake_setup.messages_translations import TRANSLATIONS
        for text in (notices.CUMULATIVE_WITHOUT_EFFECT_NOTE, notices.CUMULATIVE_FIELD_NOTE):
            for language in ("en", "fr", "de"):
                with self.subTest(language=language):
                    self.assertTrue(TRANSLATIONS[language].get(text))


if __name__ == "__main__":
    unittest.main()
