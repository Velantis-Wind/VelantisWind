# -*- coding: utf-8 -*-
"""A turbine without a rated power in its metadata reports its real one, not zero."""
import unittest

from VelantisWind.ag_core.results.summary import build_model_geometry_and_power
from VelantisWind.ag_core.turbine import build_wt_from_manual


class RatedPowerWithoutMetadataTest(unittest.TestCase):
    def setUp(self):
        wt = build_wt_from_manual("A", 112.0, 84.0, [3.0, 8.0, 15.0, 25.0], [50.0, 1400.0, 3000.0, 3000.0], [0.8, 0.79, 0.2, 0.05])
        # Only geometry in the metadata: the rated power has to come from the turbine.
        self.models = [{"name": "A", "wt": wt, "meta": {"hh": 84.0, "diam": 112.0}}]

    def test_installed_power_is_the_real_one(self):
        out = build_model_geometry_and_power(models=self.models, model_counts={"A": 3})
        self.assertAlmostEqual(out["per_model_p_rated_MW"]["A"], 3.0)
        self.assertAlmostEqual(out["per_model_p_inst_MW"]["A"], 9.0)


if __name__ == "__main__":
    unittest.main()
