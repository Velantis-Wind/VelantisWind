# -*- coding: utf-8 -*-
"""Hub heights come from the turbine itself, not from a 100 m default."""
import types
import unittest
from unittest import mock

import numpy as np
import xarray as xr

from VelantisWind.ag_core.resources.turbulence_grid import compute_ti_per_turbine
from VelantisWind.ag_core.turbine import build_wt_from_manual
from VelantisWind.ag_core.turbines import height
from VelantisWind.ag_core.turbines.factory import combine_wt, ensure_wt_entry

WS = [3.0, 8.0, 15.0, 25.0]
POWER_KW = [50.0, 1400.0, 3000.0, 3000.0]
CT = [0.8, 0.79, 0.2, 0.05]


def _turbine(name, hub_height):
    return build_wt_from_manual(name, 112.0, hub_height, WS, POWER_KW, CT)


def _site_with_heights(heights, ti_by_height=None):
    shape = (2, 2, len(heights))
    data = {"Elevation": (("x", "y"), np.zeros((2, 2)))}
    if ti_by_height is not None:
        ti = np.broadcast_to(np.asarray(ti_by_height, dtype=float), shape).copy()
        data["TI"] = (("x", "y", "h"), ti)
    ds = xr.Dataset(data, coords={"x": [0.0, 1000.0], "y": [0.0, 1000.0], "h": list(heights)})
    ds.attrs["wrg_heights_m"] = list(heights)
    return types.SimpleNamespace(ds=ds)


class HubHeightPerTurbineTest(unittest.TestCase):
    def test_single_type_returns_its_own_height(self):
        hh = height.hub_heights_per_turbine(_turbine("A", 84.0), None, 3)
        np.testing.assert_allclose(hh, [84.0, 84.0, 84.0])

    def test_mixed_park_returns_the_height_of_each_type(self):
        wt, use_types = combine_wt([
            {"name": "A", "wt": _turbine("A", 84.0), "meta": {"hh": 84.0, "diam": 112.0}},
            {"name": "B", "wt": _turbine("B", 119.0), "meta": {"hh": 119.0, "diam": 112.0}},
        ])
        self.assertTrue(use_types)
        hh = height.hub_heights_per_turbine(wt, np.array([0, 1, 1, 0]), 4)
        np.testing.assert_allclose(hh, [84.0, 119.0, 119.0, 84.0])

    def test_ambient_ti_is_sampled_at_the_real_hub_height(self):
        wt = _turbine("A", 84.0)
        site = _site_with_heights([84.0, 100.0], ti_by_height=[0.06, 0.12])
        hh = height.hub_heights_per_turbine(wt, None, 2)
        ti = compute_ti_per_turbine(site, np.array([0.0, 1000.0]), np.array([0.0, 0.0]), hh_per_turb=hh)
        np.testing.assert_allclose(ti, [0.06, 0.06], rtol=1e-6)



class MissingGeometryRegressionTest(unittest.TestCase):
    def test_uses_actual_object_geometry_when_metadata_missing(self):
        wt = _turbine("Modelo sintético", 126.0)
        name, diameter, hh, _ = ensure_wt_entry({"name": "Modelo sintético", "wt": wt})
        self.assertEqual(diameter, 112.0)
        self.assertEqual(hh, 126.0)
        combined, _ = combine_wt([{"name": "Modelo sintético", "wt": wt}])
        self.assertAlmostEqual(float(combined.hub_height(0)), 126.0)

    def test_invalid_explicit_geometry_is_not_silently_replaced(self):
        wt = _turbine("A", 126.0)
        with self.assertRaisesRegex(ValueError, "positivo"):
            ensure_wt_entry({"name": "A", "wt": wt, "hh": -1})

    def test_missing_geometry_raises_instead_of_using_100m(self):
        class Dummy:
            powerCtFunction = lambda self, ws: ws
        with self.assertRaisesRegex(ValueError, "no se pudo determinar"):
            ensure_wt_entry({"name": "Missing", "wt": Dummy()})


    def test_explicit_geometry_takes_priority(self):
        wt = _turbine("A", 126.0)
        _, diameter, hh, _ = ensure_wt_entry({
            "name": "A", "wt": wt, "meta": {"diam": 120.0, "hh": 130.0}
        })
        self.assertEqual((diameter, hh), (120.0, 130.0))

    def test_combine_refuses_missing_geometry(self):
        class Dummy:
            powerCtFunction = lambda self, ws: ws
        with self.assertRaisesRegex(ValueError, "no se pudo determinar"):
            combine_wt([{"name": "Missing", "wt": Dummy()}])

    def test_combined_turbine_uses_selected_type_geometry(self):
        wt_a = _turbine("A", 84.0)
        power_b = [100.0, 2800.0, 3200.0, 3200.0]
        ct_b = [0.9, 0.85, 0.25, 0.04]
        wt_b = build_wt_from_manual("B", 163.0, 126.0, WS, power_b, ct_b)
        mixed, use_types = combine_wt([
            {"name": "A", "wt": wt_a},
            {"name": "B", "wt": wt_b},
        ])
        self.assertTrue(use_types)
        _, diameter, hh, _ = ensure_wt_entry({
            "name": "B", "wt": mixed, "source_type_index": 1
        })
        self.assertEqual((diameter, hh), (163.0, 126.0))

        for meta in ({"diam": 163.0}, {"hh": 126.0}):
            with self.subTest(meta=meta):
                _, diameter, hh, _ = ensure_wt_entry({
                    "name": "B", "wt": mixed, "meta": meta,
                })
                self.assertEqual((diameter, hh), (163.0, 126.0))

                rebuilt, use_types = combine_wt([
                    {"name": "B", "wt": mixed, "meta": meta},
                ])
                self.assertFalse(use_types)
                np.testing.assert_allclose(rebuilt.diameter(0), 163.0)
                np.testing.assert_allclose(rebuilt.hub_height(0), 126.0)
                np.testing.assert_allclose(
                    rebuilt.power(np.array([8.0]), type=0),
                    wt_b.power(np.array([8.0]), type=0),
                )
                np.testing.assert_allclose(
                    rebuilt.ct(np.array([8.0]), type=0),
                    wt_b.ct(np.array([8.0]), type=0),
                )

    def test_single_type_ignores_ui_row_index_for_internal_geometry(self):
        wt = _turbine("B", 126.0)
        for meta in ({}, {"hh": 126.0}):
            with self.subTest(meta=meta):
                model = {
                    "name": "B", "wt": wt, "source_type_index": 1,
                    "meta": meta,
                }
                self.assertEqual(ensure_wt_entry(model)[1:3], (112.0, 126.0))

                combined, use_types = combine_wt([model])
                self.assertFalse(use_types)
                np.testing.assert_allclose(combined.diameter(0), 112.0)
                np.testing.assert_allclose(combined.hub_height(0), 126.0)

    def test_partial_geometry_that_does_not_identify_a_unique_type_is_rejected(self):
        wt_a = _turbine("A", 84.0)
        wt_b = _turbine("B", 126.0)
        mixed, _ = combine_wt([
            {"name": "A", "wt": wt_a},
            {"name": "B", "wt": wt_b},
        ])

        with self.assertRaisesRegex(RuntimeError, "índice de tipo válido"):
            combine_wt([{"name": "Ambiguous", "wt": mixed, "meta": {"diam": 112.0}}])
        with self.assertRaisesRegex(RuntimeError, "índice de tipo válido"):
            ensure_wt_entry({"name": "Ambiguous", "wt": mixed, "meta": {"diam": 112.0}})

    def test_combined_turbine_without_type_is_rejected(self):
        wt_a = _turbine("A", 84.0)
        wt_b = _turbine("B", 126.0)
        mixed, _ = combine_wt([
            {"name": "A", "wt": wt_a},
            {"name": "B", "wt": wt_b},
        ])
        with self.assertRaisesRegex(RuntimeError, "índice de tipo válido"):
            ensure_wt_entry({"name": "Ambiguous", "wt": mixed})

    def test_nonfinite_explicit_height_is_rejected(self):
        wt = _turbine("A", 126.0)
        for value in (float("nan"), float("inf"), 0.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ensure_wt_entry({"name": "A", "wt": wt, "hh": value})

    def test_strict_height_rejects_missing_hub_height(self):
        with self.assertRaisesRegex(ValueError, "altura de buje real"):
            height.hub_heights_per_turbine(object(), None, 2, strict=True)


class WrgVerticalValidationTest(unittest.TestCase):
    def test_single_height_wrg_warns_when_the_hub_differs(self):
        messages = []
        with mock.patch.object(height, "_log", lambda msg, level=None: messages.append(str(msg))):
            height.clip_hub_heights_to_site(_turbine("A", 84.0), _site_with_heights([126.0]))
        self.assertEqual(len(messages), 1)
        self.assertIn("126.0", messages[0])
        self.assertIn("84.0", messages[0])

    def test_single_height_wrg_is_silent_at_the_same_height(self):
        messages = []
        with mock.patch.object(height, "_log", lambda msg, level=None: messages.append(str(msg))):
            height.clip_hub_heights_to_site(_turbine("A", 126.0), _site_with_heights([126.0]))
        self.assertEqual(messages, [])

    def test_hub_outside_a_multi_height_wrg_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fuera del rango vertical"):
            height.clip_hub_heights_to_site(_turbine("A", 84.0), _site_with_heights([100.0, 140.0]))

    def test_hub_inside_a_multi_height_wrg_is_accepted(self):
        height.clip_hub_heights_to_site(_turbine("A", 119.0), _site_with_heights([100.0, 140.0]))


if __name__ == "__main__":
    unittest.main()
