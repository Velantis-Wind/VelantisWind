# -*- coding: utf-8 -*-
import unittest

import numpy as np

from VelantisWind.ag_core.wrg_site import _build_ds_from_wrg_text

NX, NY, NSEC = 3, 2, 4


def _wrg_text(with_site_ids: bool) -> str:
    lines = [f"{NX} {NY} 1000.0 2000.0 50.0"]
    for iy in range(NY):
        for ix in range(NX):
            node = ix + NX * iy
            sectors = []
            for s in range(NSEC):
                sectors += [
                    f"{100 + 37 * s + 11 * node}",
                    f"{61 + 7 * s + 3 * node}",
                    f"{187 + 9 * s + node}",
                ]
            row = (
                f"{1000.0 + 50.0 * ix} {2000.0 + 50.0 * iy} {120.5 + 3.25 * node} 100.0 "
                f"7.4 2.05 350 {NSEC} " + " ".join(sectors)
            )
            lines.append(f"GridPt{node:04d} {row}" if with_site_ids else row)
    return "\n".join(lines) + "\n"


class WrgParserTest(unittest.TestCase):
    def test_bulk_parser_matches_line_parser(self):
        fast = _build_ds_from_wrg_text(_wrg_text(with_site_ids=False))
        slow = _build_ds_from_wrg_text(_wrg_text(with_site_ids=True))

        self.assertEqual(fast.attrs["parser"], "numpy_bulk")
        self.assertEqual(slow.attrs["parser"], "python_fallback")
        for name in ("x", "y", "h", "wd"):
            np.testing.assert_array_equal(fast[name].values, slow[name].values)
        for name in ("Sector_frequency", "Weibull_A", "Weibull_k", "Elevation"):
            self.assertEqual(fast[name].dims, slow[name].dims)
            self.assertEqual(fast[name].dtype, slow[name].dtype)
            np.testing.assert_allclose(fast[name].values, slow[name].values, rtol=1e-6, atol=0)

    def test_bulk_parser_scales_and_orders_nodes(self):
        ds = _build_ds_from_wrg_text(_wrg_text(with_site_ids=False))

        self.assertEqual(float(ds["h"].values[0]), 100.0)
        # WRG rows run x-fastest; node 4 is ix=1, iy=1.
        self.assertAlmostEqual(float(ds["Elevation"].values[1, 1]), 133.5, places=4)
        self.assertAlmostEqual(float(ds["Weibull_A"].values[1, 1, 0, 2]), (61 + 14 + 12) / 10.0, places=5)
        self.assertAlmostEqual(float(ds["Weibull_k"].values[1, 1, 0, 2]), (187 + 18 + 4) / 100.0, places=5)
        freq = ds["Sector_frequency"].values[1, 1, 0, :NSEC]
        self.assertAlmostEqual(float(freq.sum()), 1.0, places=6)
        # The 360° closure duplicates the first sector.
        np.testing.assert_array_equal(ds["Sector_frequency"].values[..., -1], ds["Sector_frequency"].values[..., 0])


if __name__ == "__main__":
    unittest.main()
