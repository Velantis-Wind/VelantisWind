# -*- coding: utf-8 -*-
"""Decision 23(c): with PropagateUpDownIterative and WeightedSum or CumulativeWakeSum, PyWake 2.6.18 keeps no blockage
of its downwind pass (engineering_models.py:798-824): the simulation of the turbines leaves out the downstream blockage.

Against PyWake, with the signature values and two turbines downstream out of the wake: the plugin's PUD gives the same
as PyWake with ``upstream_only=True``, while All2AllIterative and PUD with LinearSum do count it; and the warning is
given in that combination only.
"""
import unittest

import numpy as np

from VelantisWind.ag_core.wake_setup import catalog as cat
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import notices
from VelantisWind.ag_core.wake_setup.factory import build_deficit
from tests.test_wake_setup_factory import SITE, WT, C, build, codes, with_

X, Y = np.array([0.0, 400.0, 400.0]), np.array([0.0, 300.0, -300.0])
PDW, A2A, PUD = "PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"


def config_of(engine, sup, blockage, bsup="LinearSum"):
    base = cfg.default_config(engine)
    return with_(base, deficit=C("BastankhahGaussianDeficit", **dict(base.deficit.params, use_effective_ws=True)),
                 superposition=C(sup), blockage=C(blockage, use_effective_ws=True), blockage_superposition=C(bsup))


def ws_eff(wfm):
    return wfm(X, Y, wd=[270.0], ws=[9.0]).WS_eff.values


def upstream_only(config):
    """PyWake directly, with the same pieces and the blockage with ``upstream_only=True``."""
    wfm = build(config)
    blockage = cat.resolve_class(cat.entry(cat.BLOCKAGE, config.blockage.name))(use_effective_ws=True,
                                                                                 upstream_only=True)
    return type(wfm)(SITE, wfm.windTurbines, build_deficit(config), superpositionModel=type(wfm.superpositionModel)(),
                     blockage_deficitModel=blockage)


class DownstreamBlockageTest(unittest.TestCase):
    def test_pud_leaves_out_the_downstream_blockage(self):
        for sup in ("WeightedSum", "CumulativeWakeSum"):
            for e in cat.entries(cat.BLOCKAGE):
                with self.subTest(sup=sup, blockage=e.name):
                    pud = config_of(PUD, sup, e.name)
                    self.assertEqual(codes(pud), [])
                    self.assertTrue(np.array_equal(ws_eff(build(pud)), ws_eff(upstream_only(pud))))
                    # The geometry is sensitive: All2AllIterative, and PUD with LinearSum, count it.
                    a2a = config_of(A2A, sup, e.name)
                    self.assertFalse(np.array_equal(ws_eff(build(a2a)), ws_eff(upstream_only(a2a))))
                    linear = config_of(PUD, "LinearSum", e.name)
                    self.assertFalse(np.array_equal(ws_eff(build(linear)), ws_eff(upstream_only(linear))))

    def test_the_warning_is_given_in_that_combination_only(self):
        def texts(config, **kwargs):
            return [str(w) for w in notices.persistent_warnings(config, **kwargs)]
        for sup in ("WeightedSum", "CumulativeWakeSum"):
            with self.subTest(sup=sup):
                warned = texts(config_of(PUD, sup, "SelfSimilarityDeficit2020"))
                self.assertIn(f"PyWake 2.6.18: con PropagateUpDownIterative y {sup}, la simulación de las turbinas omite "
                              "el bloqueo aguas abajo", " ".join(warned))
                self.assertNotIn(notices.PUD_DOWNSTREAM_FIELD_NOTE, warned)
                self.assertIn(notices.PUD_DOWNSTREAM_FIELD_NOTE, texts(config_of(PUD, sup, "SelfSimilarityDeficit2020"),
                                                                        flow_map=True))
        quiet = (config_of(A2A, "CumulativeWakeSum", "SelfSimilarityDeficit2020"),
                 config_of(PUD, "LinearSum", "SelfSimilarityDeficit2020"),
                 config_of(PUD, "WeightedSum", "SelfSimilarityDeficit2020", "MaxSum"),  # R9f
                 config_of(PUD, "WeightedSum", "SelfSimilarityDeficit2020", "SquaredSum"),  # R5
                 config_of(PUD, "CumulativeWakeSum", "SelfSimilarityDeficit2020", "WeightedSum"))  # R6
        for config in quiet:
            with self.subTest(config=config):
                self.assertFalse(any("omite el bloqueo aguas abajo" in t for t in texts(config)))
        # SquaredSum with PUD stays refused (R5): upstream_only is False.
        self.assertEqual(codes(config_of(PUD, "WeightedSum", "SelfSimilarityDeficit2020", "SquaredSum")), ["R5"])
        # The warning of the blockage models that compute with the free wind speed (decision 19) is kept.
        both = texts(config_of(PUD, "WeightedSum", "VortexDipole"))
        self.assertTrue(any("velocidad libre aunque" in t for t in both))
        self.assertTrue(any("omite el bloqueo aguas abajo" in t for t in both))

    def test_the_texts_are_translated(self):
        from VelantisWind.ag_core.wake_setup.messages_translations import TRANSLATIONS
        for text in (notices.PUD_DOWNSTREAM_BLOCKAGE_NOTE, notices.PUD_DOWNSTREAM_FIELD_NOTE):
            for language in ("en", "fr", "de"):
                with self.subTest(language=language):
                    self.assertTrue(TRANSLATIONS[language].get(text))


if __name__ == "__main__":
    unittest.main()
