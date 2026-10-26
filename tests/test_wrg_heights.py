# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from VelantisWind.ag_core.wrg_site import load_wrg_site

NX, NY, NSEC = 3, 2, 4


def _write_wrg(folder: str, height: float, elevation_offset: float = 0.0) -> str:
    lines = [f"{NX} {NY} 1000.0 2000.0 50.0"]
    for iy in range(NY):
        for ix in range(NX):
            node = ix + NX * iy
            sectors = " ".join(f"250 {70 + 5 * s + node} 205" for s in range(NSEC))
            lines.append(
                f"{1000.0 + 50.0 * ix} {2000.0 + 50.0 * iy} {120.0 + 3.0 * node + elevation_offset} "
                f"{height} 7.4 2.05 350 {NSEC} {sectors}"
            )
    path = os.path.join(folder, f"h{int(height)}_{elevation_offset:g}.wrg")
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")
    return path


class MultiHeightWrgTest(unittest.TestCase):
    def test_elevation_stays_two_dimensional(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [_write_wrg(folder, 140.0), _write_wrg(folder, 100.0)]
            _, ds, _ = load_wrg_site(paths)

        self.assertEqual(ds["Elevation"].dims, ("x", "y"))
        self.assertEqual(ds["h"].values.tolist(), [100.0, 140.0])
        self.assertEqual(ds["Weibull_A"].dims, ("x", "y", "h", "wd"))

    def test_different_terrain_between_heights_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [_write_wrg(folder, 100.0), _write_wrg(folder, 140.0, elevation_offset=5.0)]
            with self.assertRaises(ValueError):
                load_wrg_site(paths)


if __name__ == "__main__":
    unittest.main()
