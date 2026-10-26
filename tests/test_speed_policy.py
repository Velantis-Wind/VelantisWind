# -*- coding: utf-8 -*-
"""The wind-speed policy of a WRG: the grid that covers the turbines' band, the band of a curve and the step."""
import unittest

import numpy as np

from VelantisWind.ag_core.resource_grid import (
    SPEED_STEPS,
    WrgContractError,
    curve_band,
    initial_speed_step,
    speed_grid,
    validate_speed_step,
)
from VelantisWind.ag_core.turbines.bin_power import bin_edges

SOURCE = "/ruta/recurso.wrg"


class SpeedGridTest(unittest.TestCase):
    """V26: the bins of the grid cover the band, have the step's width and none lies wholly outside it."""

    CASES = [
        # (low, high, step, expected grid)
        (3.0, 24.0, 1.0, [float(v) for v in range(3, 25)]),
        (3.0, 24.0, 0.5, [3.0 + 0.5 * k for k in range(43)]),
        (3.0, 24.0, 0.25, [3.0 + 0.25 * k for k in range(85)]),
        (3.5, 24.5, 1.0, [float(v) for v in range(4, 25)]),  # the bins of 3 and 25 would only touch the band
        (2.7, 25.2, 1.0, [float(v) for v in range(3, 26)]),
        (3.0, 30.0, 1.0, [float(v) for v in range(3, 31)]),
        (3.0, 3.1, 0.25, [3.0, 3.25]),  # one bin holds the band: a second one is added
        (0.0, 25.0, 1.0, [float(v) for v in range(0, 26)]),
    ]

    def test_cases(self):
        for low, high, step, expected in self.CASES:
            with self.subTest(low=low, high=high, step=step):
                grid = speed_grid(low, high, step)
                self.assertEqual(grid.dtype, np.float64)
                self.assertEqual(grid.tolist(), expected)  # exact: no accumulated error
                self.assertGreaterEqual(grid.size, 2)  # so the log line can give the step
                _, edges = bin_edges(grid)
                self.assertLessEqual(edges[0], low)
                self.assertGreaterEqual(edges[-1], high)
                widths = np.diff(edges)
                clipped = edges[0] == 0.0 and grid[0] - step / 2 < 0.0
                np.testing.assert_allclose(widths[1:] if clipped else widths, step, rtol=0, atol=1e-12)
                outside = (edges[1:] <= low) | (edges[:-1] >= high)
                if (low, high) == (3.0, 3.1):
                    self.assertEqual(outside.tolist(), [False, True])  # only the added bin
                else:
                    self.assertFalse(outside.any())


class CurveBandTest(unittest.TestCase):
    """V27, the band."""

    def test_the_declared_band_is_used_as_it_is(self):
        ws = np.arange(0.0, 30.5, 0.5)
        self.assertEqual(curve_band(ws, np.ones_like(ws), (3.0, 24.0)), (3.0, 24.0))

    def test_rows_of_zero_power_at_the_ends_are_not_cut(self):
        ws = [0.0, 1.0, 2.0, 3.0, 10.0, 20.0, 25.0, 30.0]
        power = [0.0, 0.0, 0.0, 100.0, 2000.0, 2000.0, 0.0, 0.0]
        self.assertEqual(curve_band(ws, power, None), (0.0, 30.0))
        self.assertEqual(curve_band(ws, power, (0.0, 30.0)), (0.0, 30.0))

    def test_an_open_end_closes_at_a_node(self):
        ws = np.arange(3.0, 101.0)
        self.assertEqual(curve_band(ws, np.ones_like(ws), (3.0, None)), (3.0, 100.0))
        self.assertEqual(curve_band(ws, np.ones_like(ws), (None, 50.0)), (3.0, 50.0))

    def test_columns_of_a_density_table(self):
        ws = np.arange(3.0, 26.0)
        power = np.column_stack([np.zeros_like(ws), np.ones_like(ws)])
        self.assertEqual(curve_band(ws, power, (3.0, 25.0)), (3.0, 25.0))

    def test_no_power_at_all_is_refused(self):
        ws = np.arange(3.0, 26.0)
        with self.assertRaises(WrgContractError):
            curve_band(ws, np.zeros((ws.size, 2)), (3.0, 25.0))

    def test_invalid_bands_are_refused(self):
        ws = np.arange(3.0, 26.0)
        for band in ((10.0, 5.0), (-1.0, 25.0), (3.0, float("nan"))):
            with self.subTest(band=band), self.assertRaises(WrgContractError):
                curve_band(ws, np.ones_like(ws), band)


class InitialStepTest(unittest.TestCase):
    """V27, the initial step."""

    def table(self, step, low=3.0, high=24.0):
        return np.round(np.arange(low, high + step / 2, step), 10)

    def test_regular_tables(self):
        for step, expected in ((0.5, 0.5), (1.0, 1.0), (0.1, 0.25), (2.0, 1.0), (0.75, 0.5), (0.25, 0.25)):
            with self.subTest(step=step):
                self.assertEqual(initial_speed_step([(self.table(step, 3.0, 24.0), (3.0, 24.0))]), expected)

    def test_the_nodes_a_reader_adds_at_the_band_edges_do_not_count(self):
        nodes = np.concatenate([np.arange(0.0, 24.5, 0.5), [2.9999, 24.0001, 30.0]])
        self.assertEqual(initial_speed_step([(nodes, (3.0, 24.0))]), 0.5)
        inside = np.concatenate([np.arange(3.0, 24.5, 0.5), [10.0001, 17.9999]])  # tiny gaps inside the band
        self.assertEqual(initial_speed_step([(inside, (3.0, 24.0))]), 0.5)

    def test_an_irregular_table_takes_its_most_frequent_gap(self):
        nodes = np.concatenate([np.arange(3.0, 12.0, 0.5), np.arange(12.0, 25.0, 1.0)])  # 18 gaps of 0.5, 12 of 1
        self.assertEqual(initial_speed_step([(nodes, (3.0, 24.0))]), 0.5)
        nodes = np.concatenate([np.arange(3.0, 8.0, 0.5), np.arange(8.0, 24.5, 1.0)])  # 10 of 0.5, 16 of 1
        self.assertEqual(initial_speed_step([(nodes, (3.0, 24.0))]), 1.0)

    def test_a_tie_takes_the_smaller_gap_and_rounding_does_not_split_a_gap(self):
        nodes = [3.0, 3.5, 4.0, 5.0, 6.0]  # two gaps of 0.5 and two of 1
        self.assertEqual(initial_speed_step([(nodes, (3.0, 6.0))]), 0.5)
        nodes = [3.0, 3.5000000001, 4.0, 4.4999999999, 5.0, 6.0, 7.0]  # four of 0.5 (after rounding), two of 1
        self.assertEqual(initial_speed_step([(nodes, (3.0, 7.0))]), 0.5)

    def test_several_curves_take_the_finest_and_no_gap_gives_one(self):
        self.assertEqual(initial_speed_step([(self.table(1.0), (3.0, 24.0)), (self.table(0.5), (3.0, 24.0))]), 0.5)
        self.assertEqual(initial_speed_step([(None, (4.0, 25.0))]), 1.0)  # analytic curve
        self.assertEqual(initial_speed_step([([3.0], (3.0, 24.0))]), 1.0)
        self.assertEqual(initial_speed_step([]), 1.0)


class StepValidationTest(unittest.TestCase):
    """V28."""

    def test_the_options(self):
        for step in SPEED_STEPS + (1, np.float64(0.5)):
            with self.subTest(step=step):
                value = validate_speed_step(step, SOURCE)
                self.assertIsInstance(value, float)
                self.assertIn(value, SPEED_STEPS)

    def test_everything_else_is_refused_without_rounding(self):
        for step in (0.3, 2, 0, -0.5, float("nan"), float("inf"), True, np.bool_(True), "0.5", None, 0.50001):
            with self.subTest(step=step):
                with self.assertRaises(WrgContractError) as ctx:
                    validate_speed_step(step, SOURCE)
                self.assertIn(SOURCE, str(ctx.exception))
                self.assertIsInstance(ctx.exception, ValueError)


if __name__ == "__main__":
    unittest.main()
