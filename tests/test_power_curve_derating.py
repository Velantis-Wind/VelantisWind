# -*- coding: utf-8 -*-
import math
import os
import tempfile
import unittest

from VelantisWind.ag_core.turbine import TxtSpec, _estimate_ct, _preserve_power_curve, load_curves_from_txt


class PreservePowerCurveTest(unittest.TestCase):
    def test_high_wind_derating_is_kept(self):
        # Curva con parada de corte: cae antes del cutout, como algunos OEM reales.
        values = [0.0, 500.0, 1000.0, 1000.0, 800.0, 0.0]
        self.assertEqual(_preserve_power_curve(values), values)

    def test_negative_and_non_finite_values_are_sanitized(self):
        values = [-5.0, 100.0, float("nan"), float("inf"), -float("inf"), 50.0]
        result = _preserve_power_curve(values)
        self.assertEqual(result, [0.0, 100.0, 0.0, 0.0, 0.0, 50.0])
        self.assertTrue(all(math.isfinite(v) for v in result))



class EstimatedCtTest(unittest.TestCase):
    def test_zero_power_points_have_no_thrust(self):
        ws = [2.0, 4.0, 8.0, 16.5, 20.0, 26.0]
        power = [0.0, 1.0e5, 2.0e6, 3.0e6, 0.0, 0.0]
        self.assertEqual(_estimate_ct(ws, power), [0.0, 0.8, 0.8, 0.5, 0.0, 0.0])

    def test_csv_without_ct_column(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "curve.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("ws,power_kw\n3,0\n8,2000\n26,3000\n25,0\n")
            ws, power, ct = load_curves_from_txt(path, TxtSpec(ws_col=0, power_col=1, delimiter=",", skip_header=1))
        self.assertEqual(ws, [3.0, 8.0, 25.0, 26.0])
        self.assertEqual(ct, [0.0, 0.8, 0.0, 0.2])


if __name__ == "__main__":
    unittest.main()
