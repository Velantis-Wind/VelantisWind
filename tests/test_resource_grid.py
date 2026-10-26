# -*- coding: utf-8 -*-
"""The direction policy of a WRG: options, initial choice, validation and the grid of subdivision centres."""
import unittest

import numpy as np

from VelantisWind.ag_core.resource_grid import (
    WrgContractError,
    direction_grid,
    direction_options,
    initial_direction_count,
    validate_request,
)

PATH = "/ruta/recurso.wrg"
TOL_DEG = 1e-10


def circular_distance(a, b):
    return np.abs((np.asarray(a, dtype=float) - np.asarray(b, dtype=float) + 180.0) % 360.0 - 180.0)


class OptionsTest(unittest.TestCase):
    """V01."""

    TABLE = [
        (12, list(range(12, 361, 12)), 84),
        (18, list(range(18, 361, 18)), 126),
        (24, list(range(24, 361, 24)), 168),
        (48, [48, 96, 144, 192, 240, 288, 336], 336),
        (60, [60, 120, 180, 240, 300, 360], 60),
        (180, [180, 360], 180),
        (360, [360], 360),
        (400, [400], 400),
        (7, list(range(7, 358, 7)), 49),
    ]

    def test_table(self):
        for n, options, initial in self.TABLE:
            with self.subTest(n=n):
                self.assertEqual(direction_options(n), options)
                self.assertEqual(initial_direction_count(n), initial)
                self.assertIn(initial, options)
                self.assertEqual(direction_options(n)[0], n)

    def test_n_not_dividing_360_does_not_add_360(self):
        self.assertNotIn(360, direction_options(7))
        self.assertEqual(direction_options(7)[-1], 357)
        self.assertEqual(direction_options(48)[-1], 336)


class ValidationTest(unittest.TestCase):
    """V02."""

    def assert_refused(self, n, m, method="nearest"):
        with self.assertRaises(WrgContractError) as ctx:
            validate_request(n, m, method, PATH)
        self.assertIsInstance(ctx.exception, ValueError)
        message = str(ctx.exception)
        self.assertIn(PATH, message)
        self.assertIn(repr(n), message)
        self.assertIn(repr(m), message)
        return message

    def test_valid_requests(self):
        for n, m, method in [(12, 84, "nearest"), (12, 12, "linear"), (18, 360, "nearest"), (400, 400, "linear"),
                             (np.int64(12), np.int32(36), "nearest"), (7, 357, "linear")]:
            with self.subTest(n=n, m=m, method=method):
                validate_request(n, m, method, PATH)

    def test_bad_sector_counts(self):
        for n in (0, -12, True, 12.0, float("nan"), float("inf"), "12", None):
            with self.subTest(n=n):
                self.assert_refused(n, 84)

    def test_bad_direction_counts(self):
        for m in (0, -84, True, False, 84.0, float("nan"), float("inf"), np.float64(84.0), "84", None,
                  6, 40, 90, 372, 720):
            with self.subTest(m=m):
                self.assert_refused(12, m)

    def test_messages(self):
        message = self.assert_refused(18, 40)
        self.assertEqual(
            message,
            "Número de direcciones no válido: 40. Debe ser un múltiplo entero positivo de 18, "
            "el número de sectores del WRG «/ruta/recurso.wrg», sin superar 360.",
        )
        message = self.assert_refused(400, 800)
        self.assertEqual(
            message,
            "Número de direcciones no válido: 800. El WRG «/ruta/recurso.wrg» contiene 400 sectores; al superar el "
            "límite de 360, la única opción admitida es conservar sus 400 direcciones.",
        )
        self.assert_refused(400, 360)

    def test_bad_methods(self):
        for method in ("cubic", "Nearest", "", None, 1):
            with self.subTest(method=method):
                message = self.assert_refused(12, 84, method)
                self.assertIn("84", message)
                self.assertIn("12", message)


class GridExamplesTest(unittest.TestCase):
    """V03: the centres against the examples worked by hand."""

    def assert_angles(self, actual, expected):
        actual = np.asarray(actual, dtype=float)
        self.assertEqual(actual.dtype, np.float64)
        self.assertEqual(actual.size, len(expected))
        self.assertLess(float(np.max(circular_distance(actual, np.sort(np.mod(expected, 360.0))))), TOL_DEG)

    def test_n12_m36(self):
        grid = direction_grid(12, 36)
        # Sector 30° spans [15, 45]: three parts of 10°, centres 20, 30, 40.
        inside = grid[(grid > 15.0) & (grid < 45.0)]
        self.assert_angles(inside, [20.0, 30.0, 40.0])
        self.assert_angles(grid, [c + d for c in range(0, 360, 30) for d in (-10.0, 0.0, 10.0)])

    def test_n18_m36(self):
        grid = direction_grid(18, 36)
        # Sector 20° spans [10, 30]: two parts, centres 15 and 25; no sector centre in the grid.
        self.assert_angles(grid[(grid > 10.0) & (grid < 30.0)], [15.0, 25.0])
        self.assert_angles(grid, [c + d for c in range(0, 360, 20) for d in (-5.0, 5.0)])
        self.assertGreater(float(np.min(circular_distance(grid[:, None], np.arange(0, 360, 20)[None, :]))), 4.9)

    def test_n12_m360(self):
        self.assert_angles(direction_grid(12, 360), np.arange(360) + 0.5)

    def test_n12_m84_contains_the_sector_centres(self):
        grid = direction_grid(12, 84)
        for centre in range(0, 360, 30):
            self.assertLess(float(np.min(circular_distance(grid, centre))), TOL_DEG)
        self.assert_angles(grid, [c + k * 30.0 / 7.0 for c in range(0, 360, 30) for k in range(-3, 4)])

    def test_n400_m400(self):
        self.assert_angles(direction_grid(400, 400), np.arange(400) * 0.9)

    def test_m_equal_n_is_the_sector_centres(self):
        for n in (7, 12, 16, 18, 36):
            with self.subTest(n=n):
                self.assert_angles(direction_grid(n, n), np.arange(n) * 360.0 / n)


class GridPropertiesTest(unittest.TestCase):
    """V04: against the limits of every sector, the one across 0° included."""

    def test_every_option(self):
        for n in (1, 4, 7, 11, 12, 13, 16, 18, 24, 36, 48, 60, 72, 180, 360, 400):
            for m_total in direction_options(n):
                with self.subTest(n=n, m=m_total):
                    self.check(n, m_total)

    def check(self, n, m_total):
        grid = direction_grid(n, m_total)
        self.assertEqual(grid.dtype, np.float64)
        self.assertEqual(grid.size, m_total)
        self.assertTrue(np.all(grid >= 0.0) and np.all(grid < 360.0))
        self.assertTrue(np.all(np.diff(grid) > 0.0))
        step = 360.0 / m_total
        gaps = np.diff(np.r_[grid, grid[0] + 360.0])
        self.assertLess(float(np.max(np.abs(gaps - step))), TOL_DEG)
        width = 360.0 / n
        for i in range(n):
            low = i * width - width / 2.0  # sector 0 starts below 0°
            offsets = (grid - low) % 360.0
            members = offsets[offsets < width]
            self.assertEqual(members.size, m_total // n, f"sector {i}")
            self.assertGreater(float(np.min(np.minimum(members, width - members))), step / 2.0 - TOL_DEG)


if __name__ == "__main__":
    unittest.main()
