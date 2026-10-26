# -*- coding: utf-8 -*-
import unittest

import numpy as np

from VelantisWind.ag_core.turbines.factory import (
    _infer_source_type_index,
    canonicalize_models,
)


class CanonicalizeModelsTest(unittest.TestCase):
    def test_layers_of_one_row_become_one_physical_type(self):
        wt_a, wt_b = object(), object()
        models = [
            {"wt": wt_a, "coords_xy": [(0, 0)], "source_row_index": 0,
             "source_layer_id": "l1", "source_layer_name": "A 1"},
            {"wt": wt_b, "coords_xy": [(5, 5)], "source_row_index": 1},
            {"wt": wt_a, "coords_xy": [(1, 1)], "source_row_index": 0,
             "source_layer_id": "l2", "source_layer_name": "A 2", "coords_csv": "a.csv"},
        ]

        result = canonicalize_models(models)

        self.assertEqual([m["source_row_index"] for m in result], [0, 1])
        self.assertIs(result[0]["wt"], wt_a)
        self.assertEqual(result[0]["coords_xy"], [(0, 0), (1, 1)])
        self.assertEqual(result[0]["source_layer_ids"], ["l1", "l2"])
        self.assertEqual(result[0]["source_layer_names"], ["A 1", "A 2"])
        self.assertEqual(result[0]["coords_csv"], "a.csv")
        self.assertEqual(models[0]["coords_xy"], [(0, 0)])

    def test_without_row_index_only_a_shared_turbine_object_is_merged(self):
        shared, other = object(), object()
        models = [
            {"wt": shared, "coords_xy": [(0, 0)]},
            {"wt": other, "coords_xy": [(9, 9)]},
            {"wt": shared, "coords_xy": [(1, 1)]},
            {"wt": object(), "coords_xy": [(2, 2)], "source_row_index": -1},
        ]

        result = canonicalize_models(models)

        self.assertEqual([m["coords_xy"] for m in result], [[(0, 0), (1, 1)], [(9, 9)], [(2, 2)]])

    def test_entries_with_only_csv_coordinates_are_not_merged(self):
        cases = [
            [{"coords_csv": "a.csv"}, {"coords_csv": "b.csv"}],
            [{"coords_csv": "a.csv"}, {"coords_xy": [(1, 1)]}],
            [{"coords_xy": [(0, 0)]}, {"coords_csv": "b.csv"}],
        ]
        for entries in cases:
            models = [dict(e, wt=object(), source_row_index=0) for e in entries]
            with self.subTest(entries=entries), self.assertRaisesRegex(RuntimeError, "CSV"):
                canonicalize_models(models)

    def test_csv_entry_merges_with_an_entry_without_coordinates(self):
        for entries in ([{"coords_csv": "a.csv"}, {}], [{}, {"coords_csv": "a.csv"}]):
            models = [dict(e, wt=object(), source_row_index=0) for e in entries]
            with self.subTest(entries=entries):
                result = canonicalize_models(models)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["coords_csv"], "a.csv")


class _FakeTypeList:
    key = "type"

    def __init__(self, n):
        self.windTurbineFunction_lst = [object() for _ in range(n)]


class _FakeTurbines:
    def __init__(self, diameters, heights):
        self._d = np.asarray(diameters, dtype=float)
        self._h = np.asarray(heights, dtype=float)
        self._hub_heights = self._h

    def diameter(self, types):
        return self._d[types]

    def hub_height(self, types):
        return self._h[types]


class InferSourceTypeIndexTest(unittest.TestCase):
    def _infer(self, wt, pcf, requested, d=120.0, hh=100.0):
        return _infer_source_type_index(
            wt, pcf, diameter=d, hub_height=hh, requested_index=requested
        )

    def test_unique_geometry_match_wins_over_requested_index(self):
        wt = _FakeTurbines([120, 150, 120], [100, 110, 90])
        self.assertEqual(self._infer(wt, _FakeTypeList(3), requested=0, d=120.0, hh=90.0), 2)

    def test_ambiguous_geometry_requires_valid_requested_index(self):
        wt = _FakeTurbines([120, 120], [100, 100])
        pcf = _FakeTypeList(2)
        self.assertEqual(self._infer(wt, pcf, requested=1), 1)
        with self.assertRaisesRegex(RuntimeError, "índice de tipo válido"):
            self._infer(wt, pcf, requested=217)

    def test_unique_partial_geometry_match_selects_type(self):
        wt = _FakeTurbines([120, 150, 120], [100, 110, 90])
        self.assertEqual(self._infer(wt, _FakeTypeList(3), requested=None, d=150.0, hh=None), 1)
        self.assertEqual(self._infer(wt, _FakeTypeList(3), requested=None, d=None, hh=90.0), 2)

    def test_single_type_normalizes_ui_row_index_to_internal_zero(self):
        wt = _FakeTurbines([120], [100])
        self.assertEqual(self._infer(wt, object(), requested=7), 0)
        self.assertEqual(self._infer(wt, _FakeTypeList(1), requested=7), 0)


if __name__ == "__main__":
    unittest.main()
