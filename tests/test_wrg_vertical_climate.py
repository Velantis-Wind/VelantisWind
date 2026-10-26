# -*- coding: utf-8 -*-
import math
import unittest
from unittest import mock

import numpy as np
import xarray as xr

from VelantisWind.ag_core.resources import turbulence_grid
from VelantisWind.ag_core.results.aep_arrays import _aggregate_to_sector_centers
from VelantisWind.ag_core.wrg_site import _prepare_vertical_climate

CLIMATE = ("Sector_frequency", "Weibull_A", "Weibull_k")


def _dataset(heights):
    shape = (3, 2, len(heights), 4)
    dims = ("x", "y", "h", "wd")
    a = 6.0 + np.arange(np.prod(shape), dtype=float).reshape(shape) / 10.0
    return xr.Dataset(
        {
            "Sector_frequency": (dims, np.full(shape, 0.25)),
            "Weibull_A": (dims, a),
            "Weibull_k": (dims, np.full(shape, 2.0)),
            "Elevation": (("x", "y"), np.zeros(shape[:2])),
        },
        coords={"x": [0.0, 50.0, 100.0], "y": [0.0, 50.0], "h": list(heights), "wd": [0.0, 90.0, 180.0, 270.0]},
    )


class PrepareVerticalClimateTest(unittest.TestCase):
    def test_single_height_climate_becomes_height_independent(self):
        ds = _dataset([131.0])
        out = _prepare_vertical_climate(ds)

        for name in CLIMATE:
            self.assertNotIn("h", out[name].dims)
        self.assertNotIn("h", out.coords)
        self.assertEqual(out.attrs["wrg_vertical_policy"], "single_height_reference")
        self.assertEqual(out.attrs["wrg_reference_height_m"], 131.0)
        self.assertEqual(out.attrs["wrg_heights_m"], [131.0])
        self.assertIn("h", ds["Weibull_A"].dims)

    def test_single_height_keeps_h_for_other_variables(self):
        ds = _dataset([131.0])
        ds["TI"] = (("x", "y", "h"), np.full((3, 2, 1), 0.1))
        out = _prepare_vertical_climate(ds)

        self.assertNotIn("h", out["Weibull_A"].dims)
        self.assertIn("h", out["TI"].dims)
        self.assertIn("h", out.coords)

    def test_multi_height_is_left_for_interpolation(self):
        ds = _dataset([100.0, 140.0])
        out = _prepare_vertical_climate(ds)

        self.assertEqual(out["Weibull_A"].dims, ds["Weibull_A"].dims)
        self.assertEqual(out.attrs["wrg_vertical_policy"], "multi_height_interpolation")
        self.assertEqual(out.attrs["wrg_heights_m"], [100.0, 140.0])

    def test_without_height_axis(self):
        out = _prepare_vertical_climate(_dataset([100.0]).isel(h=0, drop=True))
        self.assertEqual(out.attrs["wrg_vertical_policy"], "no_height_axis")


class SectorAggregationTest(unittest.TestCase):
    def test_fine_bins_are_summed_into_nearest_sector_with_wraparound(self):
        dirs = [350.0, 10.0, 80.0, 100.0, 170.0, 190.0, 260.0, 280.0]
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        out, centers = _aggregate_to_sector_centers(values, dirs, [0.0, 90.0, 180.0, 270.0])

        self.assertEqual(centers, [0.0, 90.0, 180.0, 270.0])
        self.assertEqual(out, [3.0, 7.0, 11.0, 15.0])
        self.assertTrue(math.isclose(sum(out), sum(values)))

    def test_native_directions_are_unchanged(self):
        dirs = [0.0, 90.0, 180.0, 270.0]
        out, centers = _aggregate_to_sector_centers([1.0, 2.0, 3.0, 4.0], dirs, dirs)
        self.assertEqual((out, centers), ([1.0, 2.0, 3.0, 4.0], dirs))

    def test_mismatched_lengths_are_returned_as_given(self):
        out, centers = _aggregate_to_sector_centers([1.0, 2.0], [0.0, 90.0, 180.0], [0.0, 180.0])
        self.assertEqual((out, centers), ([1.0, 2.0], [0.0, 90.0, 180.0]))


class RebuildSiteTest(unittest.TestCase):
    def test_rebuild_keeps_interpolation_shear_bounds_and_distance(self):
        class OldSite:
            interp_method = {"wd": "nearest", "x": "linear", "y": "linear", "h": "linear"}
            shear = object()
            bounds = "limit"
            distance = object()

        calls = []
        with mock.patch.object(turbulence_grid, "XRSite", lambda ds, **kw: calls.append((ds, kw)) or "site"):
            self.assertEqual(turbulence_grid._rebuild_xrsite_if_needed(OldSite(), "ds"), "site")

        self.assertEqual(calls, [("ds", {
            "interp_method": OldSite.interp_method,
            "shear": OldSite.shear,
            "bounds": "limit",
            "distance": OldSite.distance,
        })])


if __name__ == "__main__":
    unittest.main()
