# -*- coding: utf-8 -*-
"""Regression checks for issue #45: accurate turbine coordinates into PyWake."""
import ast
from pathlib import Path
import unittest

import numpy as np

from VelantisWind.ag_core.orchestration.layout_builder import build_layout_arrays


class TurbineCoordinatesPrecisionTest(unittest.TestCase):
    def test_distinct_utm_positions_survive_layout_preparation(self):
        points = [(512345.68, 4412345.30), (512345.68, 4412345.60)]
        result = build_layout_arrays(
            models=[{"name": "T1", "coords_xy": points}],
            site=object(), wasp_dir="", use_wrg=False, wrg_paths=[],
            dtype=np.float64, read_xy_csv=lambda path: ([], []),
            bbox_from_site=lambda site: (512000, 513000, 4412000, 4413000),
        )
        self.assertEqual(result["xs"].dtype, np.float64)
        self.assertEqual(result["ys"].dtype, np.float64)
        self.assertEqual(result["ys"].tolist(), [p[1] for p in points])
        self.assertNotEqual(result["ys"][0], result["ys"][1])
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(float(np.float32(points[0][1])), float(np.float32(points[1][1])))

    def test_ti_interpolation_preserves_distinct_utm_positions(self):
        from types import SimpleNamespace
        import xarray as xr
        from VelantisWind.ag_core.resources.turbulence_grid import compute_ti_per_turbine

        site = SimpleNamespace(ds=xr.Dataset(
            {"TI": (("x", "y"), [[0.10, 0.20], [0.10, 0.20]])},
            coords={"x": [512345.0, 512346.0], "y": [4412345.0, 4412346.0]},
        ))
        xs = np.array([512345.68, 512345.68], dtype=np.float64)
        ys = np.array([4412345.30, 4412345.60], dtype=np.float64)
        sampled = compute_ti_per_turbine(site, xs, ys)
        np.testing.assert_allclose(sampled, [0.13, 0.16], atol=2e-6)
        self.assertNotEqual(float(sampled[0]), float(sampled[1]))

    def test_engine_call_uses_double_precision_not_float32(self):
        source = Path(__file__).resolve().parents[1] / "VelantisWind" / "ag_core" / "aep_compute.py"
        module = ast.parse(source.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(module) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "build_layout_arrays"]
        self.assertEqual(len(calls), 1)
        options = {k.arg: k.value for k in calls[0].keywords}
        self.assertEqual(ast.unparse(options["dtype"]), "np.float64")

    def test_result_table_receives_original_utm_coordinates(self):
        from VelantisWind.ag_core.results.tables import build_per_turbine_table
        points = [(512345.68, 4412345.30), (512345.68, 4412345.60)]
        kwargs = dict(
            xs=np.asarray([p[0] for p in points], dtype=np.float64),
            ys=np.asarray([p[1] for p in points], dtype=np.float64),
            nwt=2, use_types=False, type_i=None,
            names_by_type={0: "T1"}, per_model_geom={}, per_model_p_rated_MW={},
            aep_wake_wt=[900, 901], aep_free_wt=[1000, 1001], compute_variants=False,
        )
        table = build_per_turbine_table(**kwargs)
        self.assertEqual([(row["x"], row["y"]) for row in table], points)


if __name__ == "__main__":
    unittest.main()
