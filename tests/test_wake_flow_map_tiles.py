# -*- coding: utf-8 -*-
import unittest
from unittest import mock

import numpy as np
import xarray as xr

from VelantisWind.wake_core import engine


def _field(x, y, offset):
    X, Y = np.meshgrid(x, y)
    return xr.DataArray(X * 1000.0 + Y + offset, dims=("y", "x"), coords={"x": x, "y": y})


class FakeFlowMap:
    def __init__(self):
        self.calls = []

    def __call__(self, grid, **kwargs):
        self.calls.append((np.asarray(grid.x).copy(), np.asarray(grid.y).copy(), kwargs))
        return {"WS_eff": _field(grid.x, grid.y, 0.5), "WS": _field(grid.x, grid.y, 0.0)}


class TiledFlowMapTest(unittest.TestCase):
    grid_x = np.arange(7, dtype=float) * 20.0
    grid_y = 100.0 + np.arange(5, dtype=float) * 20.0

    def _run(self, pairs, n_turbines):
        fake = FakeFlowMap()
        with mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", pairs):
            joined = engine._tiled_flow_map(fake, self.grid_x, self.grid_y, n_turbines, wd=270.0, ws=10.0)
        return fake, joined

    def _assert_complete(self, fake, joined, max_pairs, n_turbines):
        counts = np.zeros((self.grid_y.size, self.grid_x.size), dtype=int)
        for x, y, kwargs in fake.calls:
            self.assertLessEqual(x.size * y.size * n_turbines, max_pairs)
            self.assertEqual(kwargs, {"wd": 270.0, "ws": 10.0})
            counts[np.ix_(np.searchsorted(self.grid_y, y), np.searchsorted(self.grid_x, x))] += 1
        np.testing.assert_array_equal(counts, 1)
        for name, offset in (("WS_eff", 0.5), ("WS", 0.0)):
            xr.testing.assert_equal(
                joined[name].transpose("y", "x"),
                _field(self.grid_x, self.grid_y, offset),
            )

    def test_small_grid_is_a_single_call(self):
        fake, joined = self._run(pairs=4_000, n_turbines=34)
        self.assertEqual(len(fake.calls), 1)
        self._assert_complete(fake, joined, 4_000, 34)

    def test_tiles_span_several_rows(self):
        fake, joined = self._run(pairs=30, n_turbines=2)
        self.assertEqual(len(fake.calls), 3)
        self._assert_complete(fake, joined, 30, 2)

    def test_tiles_split_rows_when_a_row_exceeds_the_budget(self):
        fake, joined = self._run(pairs=6, n_turbines=2)
        self.assertEqual(len(fake.calls), 15)
        self._assert_complete(fake, joined, 6, 2)

    def test_more_turbines_than_budget_still_computes_one_cell_per_call(self):
        fake, joined = self._run(pairs=4, n_turbines=10)
        self.assertEqual(len(fake.calls), 35)
        self._assert_complete(fake, joined, max_pairs=10, n_turbines=10)

    def test_after_tile_reports_each_tile(self):
        fake = FakeFlowMap()
        reported = []
        with mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 6):
            engine._tiled_flow_map(
                fake, self.grid_x, self.grid_y, 2, after_tile=lambda *args: reported.append(args)
            )
        self.assertEqual(reported, [(done, 15) for done in range(1, 16)])

    def test_cancel_after_a_tile_stops_the_remaining_calls(self):
        class Cancelled(RuntimeError):
            pass

        def after_tile(done, total):
            if done == 2:
                raise Cancelled()

        fake = FakeFlowMap()
        with mock.patch.object(engine, "_FLOW_MAP_TILE_PAIRS", 6):
            with self.assertRaises(Cancelled):
                engine._tiled_flow_map(fake, self.grid_x, self.grid_y, 2, after_tile=after_tile)
        self.assertEqual(len(fake.calls), 2)


if __name__ == "__main__":
    unittest.main()
