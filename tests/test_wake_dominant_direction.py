# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

import numpy as np
import xarray as xr

from VelantisWind.wake_core.engine import _pick_resource_dominant_wd

WD = np.array([0.0, 90.0, 180.0, 270.0, 360.0])


def _site(freq, a=8.0, k=2.0, speedup=None):
    """Resource on a 2x2 grid; ``freq`` has shape (x, y, wd) without the 360° closure."""
    freq = np.asarray(freq, dtype=float)
    freq = np.concatenate([freq, freq[:, :, :1]], axis=2)
    dims = ("x", "y", "wd")
    ds = xr.Dataset(
        {
            "Sector_frequency": (dims, freq),
            "Weibull_A": (dims, np.full(freq.shape, a)),
            "Weibull_k": (dims, np.full(freq.shape, k)),
        },
        coords={"x": [0.0, 1000.0], "y": [0.0, 1000.0], "wd": WD},
    )
    if speedup is not None:
        ds["Speedup"] = ("wd", np.asarray(speedup, dtype=float))
    return SimpleNamespace(ds=ds)


class DominantDirectionTest(unittest.TestCase):
    def test_picks_the_most_frequent_sector_over_the_domain(self):
        freq = np.tile([0.1, 0.5, 0.3, 0.1], (2, 2, 1))
        wd, score = _pick_resource_dominant_wd(_site(freq))
        self.assertEqual(wd, 90.0)
        self.assertGreater(score, 0.0)

    def test_samples_the_resource_at_turbine_positions(self):
        freq = np.tile([0.1, 0.1, 0.7, 0.1], (2, 2, 1))
        freq[0, 0] = [0.1, 0.7, 0.1, 0.1]
        site = _site(freq)

        self.assertEqual(_pick_resource_dominant_wd(site)[0], 180.0)
        self.assertEqual(_pick_resource_dominant_wd(site, [10.0], [20.0])[0], 90.0)

    def test_speedup_scales_the_power_density_proxy(self):
        freq = np.full((2, 2, 4), 0.25)
        speedup = [1.0, 1.0, 1.0, 1.2, 1.0]
        self.assertEqual(_pick_resource_dominant_wd(_site(freq, speedup=speedup))[0], 270.0)

    def test_returns_none_without_weibull_climate(self):
        site = _site(np.full((2, 2, 4), 0.25))
        site.ds = site.ds.drop_vars("Weibull_k")
        self.assertIsNone(_pick_resource_dominant_wd(site))


if __name__ == "__main__":
    unittest.main()
