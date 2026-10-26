# -*- coding: utf-8 -*-
"""The 1-D builder hands PyWake the curve as supplied: shape kept, band enforced, no density rescale."""
import math
import os
import tempfile
import unittest

import numpy as np

from VelantisWind.ag_core.turbine import TxtSpec, build_wt_from_manual, load_curves_from_txt

# Rated power with a real high-wind reduction, listed only over its operating band.
WS = [3.0, 10.0, 20.0, 24.0]
POWER_KW = [78.0, 4500.0, 4500.0, 2447.0]
CT = [0.89, 0.77, 0.06, 0.02]


def _build(ws=WS, power_kw=POWER_KW, ct=CT):
    return build_wt_from_manual("Synthetic WT", 100.0, 100.0, list(ws), list(power_kw), None if ct is None else list(ct))


def _power_kw(wt, ws, **kwargs):
    return np.asarray(wt.power(np.atleast_1d(np.asarray(ws, dtype=float)), type=0, **kwargs), dtype=float) / 1000.0


def _ct(wt, ws, **kwargs):
    return np.asarray(wt.ct(np.atleast_1d(np.asarray(ws, dtype=float)), type=0, **kwargs), dtype=float)


def _write_csv(folder, rows, header="ws,power_kw,ct"):
    path = os.path.join(folder, "curve.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\n".join(",".join(str(v) for v in row) for row in rows) + "\n")
    return path


class HighWindReductionTest(unittest.TestCase):
    def test_manual_list_keeps_the_reduction(self):
        wt = _build()
        np.testing.assert_allclose(_power_kw(wt, [20.0, 22.0, 24.0]), [4500.0, 3473.5, 2447.0])

    def test_csv_keeps_the_reduction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_csv(folder, zip(WS, POWER_KW, CT))
            ws, power_w, ct = load_curves_from_txt(path, TxtSpec(ws_col=0, power_col=1, delimiter=",", skip_header=1, ct_col=2))
        wt = build_wt_from_manual("Synthetic WT", 100.0, 100.0, ws, [p / 1000.0 for p in power_w], ct)
        np.testing.assert_allclose(_power_kw(wt, [20.0, 22.0, 24.0]), [4500.0, 3473.5, 2447.0])


class OperatingBandTest(unittest.TestCase):
    def test_zero_outside_the_tabulated_band_with_a_step(self):
        wt = _build()
        ws = [0.0, 2.0, 3.0 - 1e-6, 3.0, 24.0, 24.0 + 1e-6, 25.0, 70.0]
        np.testing.assert_allclose(_power_kw(wt, ws), [0.0, 0.0, 0.0, 78.0, 2447.0, 0.0, 0.0, 0.0])
        np.testing.assert_allclose(_ct(wt, ws), [0.0, 0.0, 0.0, 0.89, 0.02, 0.0, 0.0, 0.0])

    def test_interior_of_the_band_is_unchanged(self):
        wt = _build()
        ws = np.arange(3.0, 24.0001, 0.25)
        np.testing.assert_allclose(_power_kw(wt, ws), np.interp(ws, WS, POWER_KW))
        np.testing.assert_allclose(_ct(wt, ws), np.interp(ws, WS, CT))

    def test_curve_with_explicit_end_zeros_is_unchanged(self):
        ws = [2.5] + WS + [24.001]
        power = [0.0] + POWER_KW + [0.0]
        ct = [0.0] + CT + [0.0]
        wt = _build(ws, power, ct)
        grid = np.arange(0.0, 40.0001, 0.1)
        np.testing.assert_allclose(_power_kw(wt, grid), np.interp(grid, ws, power))
        np.testing.assert_allclose(_ct(wt, grid), np.interp(grid, ws, ct))

    def test_table_reaching_100_ms_is_not_cut_inside(self):
        # PyWake places its own idle node at 100 m/s when a cut-out is given, so
        # none is given then: the table is kept and its last value repeats above.
        for last in (100.0, 120.0):
            with self.subTest(last=last):
                ws = [3.0, 10.0, 90.0, 99.0, last]
                power = [78.0, 4500.0, 4500.0, 4000.0, 3000.0]
                ct = [0.89, 0.77, 0.06, 0.05, 0.04]
                wt = _build(ws, power, ct)
                grid = [2.0, 95.0, 99.5, 100.0, last, last + 10.0]
                np.testing.assert_allclose(_power_kw(wt, grid), [0.0] + list(np.interp(grid[1:], ws, power)))
                np.testing.assert_allclose(_ct(wt, grid), [0.0] + list(np.interp(grid[1:], ws, ct)))

    def test_turbine_slowed_below_cut_in_by_a_wake_stops(self):
        from py_wake import NOJ
        from py_wake.site import UniformSite

        wt = _build()
        sim = NOJ(UniformSite(p_wd=[1.0], ti=0.1), wt)([0.0, 500.0], [0.0, 0.0], wd=[270.0], ws=[3.2])
        ws_eff = np.asarray(sim.WS_eff).ravel()
        self.assertGreater(ws_eff[0], 3.0)
        self.assertLess(ws_eff[1], 3.0)
        power = np.asarray(sim.Power).ravel()
        ct = np.asarray(sim.CT).ravel()
        self.assertGreater(power[0], 0.0)
        self.assertEqual(power[1], 0.0)
        self.assertEqual(ct[1], 0.0)


class DensityAndYawTest(unittest.TestCase):
    def test_curve_does_not_declare_air_density(self):
        required, optional = _build().function_inputs
        self.assertNotIn("Air_density", list(required) + list(optional))

    def test_yaw_model_is_still_active(self):
        wt = _build()
        co = math.cos(math.radians(30.0))
        ws = np.array([10.0, 15.0])
        np.testing.assert_allclose(_power_kw(wt, ws, yaw=30.0), _power_kw(wt, ws * co))
        np.testing.assert_allclose(_ct(wt, ws, yaw=30.0), _ct(wt, ws * co) * co ** 2)


class CtValidationTest(unittest.TestCase):
    def test_ct_up_to_the_admission_threshold_is_kept(self):
        for value in (1.05, 1.2):
            with self.subTest(value=value):
                wt = _build(ct=[0.89, value, 0.06, 0.02])
                self.assertAlmostEqual(float(_ct(wt, 10.0)[0]), value, places=12)

    def test_invalid_ct_fails_naming_the_point(self):
        for value in (1.2000001, 5.0, -0.1, float("nan"), float("inf"), 10 ** 400, "abc", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as ctx:
                    _build(ct=[0.89, value, 0.06, 0.02])
                message = str(ctx.exception)
                self.assertIn("10.0 m/s", message)
                self.assertIn(str(value), message)
                self.assertIn("umbral de admisión", message)
                template, data = ctx.exception.template_item
                self.assertEqual(template.format(**data), message)
                self.assertEqual(data["ws"], 10.0)


class EstimatedCtTest(unittest.TestCase):
    def test_list_without_ct_has_no_thrust_where_power_is_zero(self):
        wt = _build([2.0, 4.0, 8.0, 16.5, 20.0, 26.0], [0.0, 100.0, 2000.0, 3000.0, 0.0, 0.0], None)
        np.testing.assert_allclose(_ct(wt, [2.0, 4.0, 8.0, 16.5, 20.0, 26.0]), [0.0, 0.8, 0.8, 0.5, 0.0, 0.0])

    def test_csv_without_ct_column_is_still_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_csv(folder, [(3, 0), (8, 2000), (25, 3000), (26, 0)], header="ws,power_kw")
            ws, power_w, ct = load_curves_from_txt(path, TxtSpec(ws_col=0, power_col=1, delimiter=",", skip_header=1))
        self.assertEqual(ct, [0.0, 0.8, 0.2, 0.0])
        wt = build_wt_from_manual("Synthetic WT", 100.0, 100.0, ws, [p / 1000.0 for p in power_w], ct)
        np.testing.assert_allclose(_power_kw(wt, [8.0, 25.0, 27.0]), [2000.0, 3000.0, 0.0])


class CtErrorTranslationTest(unittest.TestCase):
    def test_dialog_translates_the_template_and_fills_in_the_values(self):
        from unittest import mock
        from VelantisWind.ag_core import turbine_ui

        with self.assertRaises(ValueError) as ctx:
            _build(ct=[0.89, 5.0, 0.06, 0.02])
        template, data = ctx.exception.template_item
        with mock.patch.object(turbine_ui, "tr_text", side_effect=lambda text: "[tr] " + text) as tr:
            shown = turbine_ui._error_text(ctx.exception)
        tr.assert_called_once_with(template)
        self.assertEqual(shown, "[tr] " + str(ctx.exception))
        self.assertEqual(turbine_ui._error_text(ValueError("sin plantilla")), "sin plantilla")


# A family tabulated by air density. At 15 m/s both curves are at rated power, as
# real tables are: a DensityScale left in place would show there as power ∝ ρ/1.225.
FAMILY_WS = (3.0, 8.0, 15.0, 25.0)
FAMILY_RHO = (1.0, 1.1, 1.225)
FAMILY_POWER = ((40.0, 45.0, 50.0), (1100.0, 1229.0, 1375.0), (3000.0, 3000.0, 3000.0), (3000.0, 3000.0, 3000.0))
FAMILY_CT = ((0.81, 0.81, 0.82), (0.80, 0.798, 0.794), (0.2, 0.2, 0.2), (0.05, 0.05, 0.05))


def _family(**changes):
    from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable

    data = dict(
        name="Family", diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=FAMILY_WS, air_densities=FAMILY_RHO,
        power_kw=FAMILY_POWER, ct=FAMILY_CT, default_air_density=1.225, cut_in_ms=3.0, cut_out_ms=25.0,
    )
    data.update(changes)
    return TurbineCurveTable(**data)


def _build_family(**changes):
    from VelantisWind.ag_core.turbine import build_wt_from_curve_table

    return build_wt_from_curve_table(_family(**changes))


class DensityTableInterpolationTest(unittest.TestCase):
    def test_tabulated_density_is_reproduced_exactly(self):
        wt = _build_family()
        for j, rho in enumerate(FAMILY_RHO):
            with self.subTest(rho=rho):
                np.testing.assert_allclose(
                    _power_kw(wt, FAMILY_WS, Air_density=np.full(4, rho)), [row[j] for row in FAMILY_POWER])
                np.testing.assert_allclose(_ct(wt, FAMILY_WS, Air_density=np.full(4, rho)), [row[j] for row in FAMILY_CT])

    def test_intermediate_density_is_linear_between_its_neighbours(self):
        wt = _build_family()
        self.assertAlmostEqual(float(_power_kw(wt, 8.0, Air_density=[1.05])[0]), 1164.5)
        self.assertAlmostEqual(float(_power_kw(wt, 8.0, Air_density=[1.1625])[0]), 1302.0)
        self.assertAlmostEqual(float(_ct(wt, 8.0, Air_density=[1.1625])[0]), 0.796)

    def test_rated_power_does_not_scale_with_density(self):
        wt = _build_family()
        # With DensityScale(1.225) this would be 3000 * 1.0 / 1.225 = 2449 kW.
        self.assertAlmostEqual(float(_power_kw(wt, 15.0, Air_density=[1.0])[0]), 3000.0)

    def test_without_air_density_the_default_curve_is_used(self):
        wt = _build_family(default_air_density=1.1)
        self.assertAlmostEqual(float(_power_kw(wt, 8.0)[0]), 1229.0)

    def test_yaw_model_is_still_active(self):
        wt = _build_family()
        co = math.cos(math.radians(30.0))
        rho = np.array([1.1, 1.1])
        ws = np.array([8.0, 12.0])
        np.testing.assert_allclose(_power_kw(wt, ws, yaw=30.0, Air_density=rho), _power_kw(wt, ws * co, Air_density=rho))
        np.testing.assert_allclose(_ct(wt, ws, yaw=30.0, Air_density=rho), _ct(wt, ws * co, Air_density=rho) * co ** 2)


class DensityTableBandTest(unittest.TestCase):
    def test_declared_band_steps_to_zero_at_every_density(self):
        wt = _build_family(cut_out_ms=20.0)
        ws = [0.0, 3.0 - 1e-3, 3.0, 20.0, 20.0 + 1e-3, 25.0, 70.0]
        for rho in FAMILY_RHO:
            with self.subTest(rho=rho):
                power = _power_kw(wt, ws, Air_density=np.full(len(ws), rho))
                self.assertEqual(list(power[[0, 1, 4, 5, 6]]), [0.0] * 5)
                self.assertGreater(power[2], 0.0)
                self.assertAlmostEqual(power[3], 3000.0)
                self.assertEqual(list(_ct(wt, ws, Air_density=np.full(len(ws), rho))[[0, 1, 4, 5, 6]]), [0.0] * 5)

    def test_declared_band_wins_over_tabulated_values(self):
        # The table still tabulates power up to 25 m/s; the file says the machine stops at 20.
        wt = _build_family(cut_out_ms=20.0)
        self.assertEqual(float(_power_kw(wt, 22.0, Air_density=[1.1])[0]), 0.0)


    def test_table_reaching_the_end_of_the_padding_still_builds(self):
        ws = FAMILY_WS[:-1] + (1000.0,)
        wt = _build_family(wind_speeds_ms=ws, cut_out_ms=1000.0)
        self.assertAlmostEqual(float(_power_kw(wt, 500.0, Air_density=[1.1])[0]), 3000.0)


class SingleDensityTableTest(unittest.TestCase):
    def _single(self, ct_value):
        ct = ((0.8,), (ct_value,), (0.2,), (0.05,))
        return _build_family(air_densities=(1.225,), power_kw=tuple((row[2],) for row in FAMILY_POWER), ct=ct)

    def test_ct_above_one_reaches_pywake_intact(self):
        wt = self._single(1.1)
        self.assertAlmostEqual(float(_ct(wt, 8.0)[0]), 1.1, places=12)
        required, optional = wt.function_inputs
        self.assertNotIn("Air_density", list(required) + list(optional))

    def test_invalid_ct_fails_naming_the_point(self):
        from VelantisWind.ag_core.turbines.density_curve import CurveTableError

        for value in (5.0, -0.1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(CurveTableError) as ctx:
                    self._single(value)
                self.assertIn("a 8 m/s y 1.225 kg/m³", str(ctx.exception))


class MixedDensityParkTest(unittest.TestCase):
    def test_density_of_one_type_outside_the_other_table_does_not_break_the_park(self):
        from VelantisWind.ag_core.turbines.factory import combine_wt

        low = _build_family(air_densities=(0.9, 1.0, 1.1))
        high = _build_family(air_densities=(1.1, 1.2, 1.3))
        wt, _ = combine_wt([
            {"name": "low", "wt": low, "meta": {"hh": 90.0, "diam": 100.0}},
            {"name": "high", "wt": high, "meta": {"hh": 90.0, "diam": 100.0}},
        ])
        power = np.asarray(wt.power(np.array([8.0, 8.0]), type=np.array([0, 1]), Air_density=np.array([0.95, 1.25])))
        np.testing.assert_allclose(power / 1000.0, [1164.5, 1302.0])


if __name__ == "__main__":
    unittest.main()
