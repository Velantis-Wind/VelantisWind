# -*- coding: utf-8 -*-
"""Power of a wind-speed bin as the mean of the curve over the translated bin (``turbines/bin_power.py``)."""
import pickle
import unittest

import numpy as np

from VelantisWind.ag_core.turbine import build_wt_from_curve_table, build_wt_from_manual
from VelantisWind.ag_core.turbines.bin_power import (
    BIN_MEAN, POINT, bin_edges, bin_mean_power_ct, check_grid, simulation_wind_turbines,
)
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable

G = np.arange(0.0, 71.0)  # the 0-70 m/s grid, step 1
# The IEA37 CS4 grid (VelantisOptimizer/data/iea37/cs4/iea37-windrose-cs4.yaml), not uniform.
IEA37 = np.array([0.90, 1.98, 3.18, 4.40, 5.64, 6.87, 8.11, 9.35, 10.59, 11.83, 13.07, 14.31,
                  15.56, 16.80, 18.04, 19.28, 20.52, 21.77, 23.01, 24.25])
IEA37_15 = IEA37[:15]
C1_WS, C1_KW = [3, 4.5, 5, 5.5, 10, 25], [0, 0, 100, 300, 2000, 2000]


def manual(ws, kw, ct=None):
    return build_wt_from_manual("m", 100, 100, ws, kw, ct if ct is not None else [0.8] * len(ws))


def table(ws, rho, rows, **kwargs):
    """``build_wt_from_curve_table`` of a family with these speeds, densities and power rows (kW), Ct 0.8."""
    return build_wt_from_curve_table(TurbineCurveTable(
        name="t", diameter_m=100, hub_height_m=100, wind_speeds_ms=tuple(ws), air_densities=tuple(rho),
        power_kw=tuple(tuple(r) for r in rows), ct=tuple((0.8,) * len(rho) for _ in ws), **kwargs))


def curve(wt):
    """The curve inside a turbine (a ``type`` list wraps it)."""
    pcf = wt.powerCtFunction
    return pcf.windTurbineFunction_lst[0] if hasattr(pcf, "windTurbineFunction_lst") else pcf


def T(wt):
    return {"type": 0} if getattr(wt.powerCtFunction, "key", None) == "type" else {}


def kw(wt, v, **inputs):
    """Power in kW at the speeds ``v``."""
    inputs = {**T(wt), **inputs}
    return np.asarray(wt.power(np.atleast_1d(np.asarray(v, dtype=float)), **inputs), dtype=float) / 1e3


def numeric_mean(wt, lo, hi, band=(None, None), n=200001, **inputs):
    """Mean over [lo, hi] (kW) of the point curve, zero outside ``band``: trapezoids on ``n`` points."""
    a = max(lo, band[0]) if band[0] is not None else lo
    b = min(hi, band[1]) if band[1] is not None else hi
    if b <= a:
        return 0.0
    x = np.linspace(a, b, n)
    p = kw(wt, x, **inputs)
    return float(np.sum((p[1:] + p[:-1]) / 2 * np.diff(x)) / (hi - lo))


class EdgesTest(unittest.TestCase):
    """C20 and the grids C19 refuses."""

    def test_uniform_grid_from_zero_clips_the_first_bin(self):
        grid, edges = bin_edges(G)
        np.testing.assert_allclose(edges, np.r_[0.0, np.arange(0.5, 71.0)], rtol=0, atol=1e-12)
        self.assertEqual((grid.shape, edges.shape), ((71,), (72,)))

    def test_non_uniform_grid_has_its_midpoints(self):
        _, edges = bin_edges(IEA37_15)
        mids = (IEA37_15[1:] + IEA37_15[:-1]) / 2
        np.testing.assert_allclose(edges, np.r_[0.90 - 0.54, mids, 18.04 + 0.62], rtol=0, atol=1e-12)

    def test_grid_with_its_maximum_appended(self):
        _, edges = bin_edges(np.r_[np.arange(0, 69.76, 0.75), 70])
        np.testing.assert_allclose(np.diff(edges)[-3:], [0.75, 0.5, 0.25], rtol=0, atol=1e-12)

    def test_one_speed_is_one_unclipped_metre_per_second(self):
        np.testing.assert_allclose(bin_edges([8])[1], [7.5, 8.5], rtol=0, atol=1e-12)
        np.testing.assert_allclose(bin_edges([0])[1], [-0.5, 0.5], rtol=0, atol=1e-12)

    def test_the_grid_is_a_copy(self):
        ws = np.array([3, 5, 8])
        grid, _ = bin_edges(ws)
        ws[1] = 6
        np.testing.assert_array_equal(grid, [3.0, 5.0, 8.0])
        self.assertEqual(grid.dtype, float)

    def test_invalid_grids_are_refused(self):
        for grid in ([], [3, 3], [5, 4], [3, np.nan], None, [-2, -1]):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                bin_edges(grid)


class MeanTest(unittest.TestCase):
    def test_issue_example(self):
        """C1: 125 kW instead of the centre's 100."""
        wt = manual(C1_WS, C1_KW)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G), 5)[0], 125.0, delta=1e-9)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G, POINT), 5)[0], 100.0, delta=1e-9)

    def test_slope_that_changes_inside_the_bin(self):
        """C2: the slope changes at 7.3, inside [6.5, 7.5]."""
        wt = manual([3, 6.5, 7.3, 9, 25], [0, 100, 420, 505, 505])
        expected = (100 + 420) / 2 * 0.8 + (420 + 430) / 2 * 0.2
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G), 7)[0], expected, delta=1e-9)
        self.assertAlmostEqual(expected, 293.0, delta=1e-9)

    def test_each_bin_of_a_non_uniform_grid_has_its_own_interval(self):
        """C3: on the IEA37 CS4 grid, every centre gets the mean over its real edges."""
        wt = manual([3, 6, 12, 25], [0, 400, 3000, 3000])
        ad = simulation_wind_turbines(wt, IEA37_15)
        _, e = bin_edges(IEA37_15)
        got = kw(ad, IEA37_15)
        for k, v in enumerate(IEA37_15):
            with self.subTest(ws=v):
                self.assertAlmostEqual(got[k], numeric_mean(wt, e[k], e[k + 1], band=(3, 25)), delta=1e-4)

    def test_first_bin_clipped_at_zero_with_power_in_it(self):
        """C4: the bin of 0 m/s is [0, 0.5]."""
        wt = manual([0.1, 1, 25], [40, 40, 40])
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G), 0)[0], 40 * 0.4 / 0.5, delta=1e-9)

    def test_last_bin_of_a_grid_with_its_maximum_appended(self):
        grid = np.r_[np.arange(0, 69.76, 0.75), 70]
        wt = manual([0, 70, 100], [0, 700, 0])
        _, e = bin_edges(grid)
        got = kw(simulation_wind_turbines(wt, grid), grid[-3:])
        for k, v in zip(range(grid.size - 3, grid.size), got):
            self.assertAlmostEqual(v, numeric_mean(wt, e[k], e[k + 1]), delta=1e-6)

    def test_one_speed_grid(self):
        wt = manual([0, 20], [0, 2000])
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, [8]), 8.3)[0], 100 * 8.3, delta=1e-9)

    def test_bin_that_contains_the_speed_translated(self):
        """C5: grid [3, 5, 8], bins [2, 4], [4, 6.5], [6.5, 9.5]; P = 100 v kW."""
        wt = manual([0, 20], [0, 2000])
        got = kw(simulation_wind_turbines(wt, [3, 5, 8]), [5.2, 4.0, 1.0, 12.0])
        # 5.2: [4.2, 6.7]; 4.0, an edge, the bin above, [4, 6.5], moved to [3, 5.5];
        # 1.0, below: [0, 2]; 12.0, above: [10.5, 13.5].
        np.testing.assert_allclose(got, [545.0, 425.0, 100.0, 1200.0], rtol=0, atol=1e-9)

    def test_curve_without_band_is_flat_outside_its_table(self):
        """C12: as PyWake evaluates it (np.interp)."""
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

        wt = WindTurbine("p", 100, 100, PowerCtTabular([3, 10, 25], [60, 2000, 2000], "kW", [0.8] * 3))
        np.testing.assert_allclose(kw(simulation_wind_turbines(wt, G), [30, 2]), [2000.0, 60.0], rtol=0, atol=1e-9)

    def test_cube_power(self):
        """C15: CubePowerSimpleCt, against its integral."""
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import CubePowerSimpleCt

        wt = WindTurbine("c", 100, 100, CubePowerSimpleCt(ws_cutin=4, ws_cutout=25, ws_rated=9.8,
                                                          power_rated=3350, power_unit="kW"))
        ad = simulation_wind_turbines(wt, G)
        for v in (4, 6, 9.8, 10, 25):
            with self.subTest(ws=v):
                self.assertAlmostEqual(kw(ad, v)[0], numeric_mean(wt, v - 0.5, v + 0.5), delta=0.01)


class BandTest(unittest.TestCase):
    def test_band_declared_by_each_builder(self):
        """C6."""
        rows = ((0, 0), (60, 60), (2000, 2000), (2000, 2000), (2000, 2000))
        cases = [
            (manual([3, 10, 25], [0, 1, 1]), (3.0, 25.0)),
            (manual([0, 10, 25], [0, 1, 1]), (0.0, 25.0)),
            (manual([3, 10, 120], [0, 1, 1]), (3.0, None)),
            (table((2, 3, 10, 25, 30), (1, 1.225), rows, cut_in_ms=3, cut_out_ms=25), (3.0, 25.0)),
            (table((2, 3, 10, 25, 30), (1, 1.225), rows), (2.0, 30.0)),
            (table((2, 3, 10, 25, 30), (1.225,), [r[:1] for r in rows], cut_in_ms=3, cut_out_ms=25), (3.0, 25.0)),
        ]
        for i, (wt, band) in enumerate(cases):
            with self.subTest(case=i):
                self.assertEqual(curve(wt).operating_band, band)

    def test_the_band_does_not_change_the_point_power(self):
        x = np.linspace(0, 40, 4001)
        for wt in (manual(C1_WS, C1_KW),
                   table((2, 3, 10, 25, 30), (1, 1.225), ((0, 0), (60, 60), (2000, 2000), (2000, 2000), (2000, 2000)),
                         cut_in_ms=3, cut_out_ms=25)):
            before = kw(wt, x, Air_density=1.1) if "Air_density" in curve(wt).inputs else kw(wt, x)
            del curve(wt).operating_band
            after = kw(wt, x, Air_density=1.1) if "Air_density" in curve(wt).inputs else kw(wt, x)
            np.testing.assert_array_equal(before, after)

    def test_steps_instead_of_guard_ramps(self):
        """C7: the 1e-4 m/s guards of a density table (two columns and one) and PyWake's 1e-8 ones, as steps."""
        rows = ((0, 0), (60, 60), (2000, 2000), (2000, 2000), (2000, 2000))
        two = table((2, 3, 10, 25, 30), (1, 1.225), rows, cut_in_ms=3, cut_out_ms=25)
        one = table((2, 3, 10, 25, 30), (1.225,), [r[:1] for r in rows], cut_in_ms=3, cut_out_ms=25)
        pywake = manual([3, 10, 25], [60, 2000, 2000])
        expected = [(60 + 60 + 1940 * 0.5 / 7) / 2 * 0.5, 1000.0]
        for name, wt in (("two", two), ("one", one), ("manual", pywake)):
            with self.subTest(curve=name):
                inputs = {"Air_density": np.array([1.1, 1.1])} if name == "two" else {}
                got = kw(simulation_wind_turbines(wt, G), [3, 25], **inputs)
                np.testing.assert_allclose(got, expected, rtol=0, atol=1e-9)

    def test_short_real_ramps_are_integrated(self):
        """C8, C8b, C8c (problem 3): a real 1e-4 m/s ramp next to the power is not a guard."""
        c8 = manual([3, 4, 5, 5.0001, 6, 8], [0, 0, 0, 100, 100, 0])
        c8b = manual([3, 4, 6, 6.0001, 8], [0, 100, 100, 0, 0])
        c8c = table((3, 5, 5.0001, 6, 8), (1, 1.225), ((0, 0), (0, 0), (100, 100), (100, 100), (0, 0)))
        self.assertAlmostEqual(kw(simulation_wind_turbines(c8, [5.5]), 5.5)[0], 99.995, delta=1e-9)
        self.assertAlmostEqual(kw(simulation_wind_turbines(c8b, [6.0]), 6.0)[0], 50.005, delta=1e-9)
        self.assertAlmostEqual(kw(simulation_wind_turbines(c8c, [5.5]), 5.5, Air_density=1.1)[0], 99.995, delta=1e-9)

    def test_repeated_speed_is_a_jump(self):
        """C9 (problem 4)."""
        wt = manual([3, 5, 5, 6, 8], [0, 0, 100, 100, 0])
        for lo, hi, expected in ((4, 5, 0.0), (5, 6, 100.0), (4.5, 5.5, 50.0)):
            with self.subTest(interval=(lo, hi)):
                mid = (lo + hi) / 2
                got = kw(simulation_wind_turbines(wt, [mid]), mid)[0]
                self.assertAlmostEqual(got, numeric_mean(wt, lo, hi, band=(3, 8)), delta=2e-3)
                self.assertAlmostEqual(got, expected, delta=2e-3)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, [5.5], POINT), 5.5)[0], 100.0, delta=1e-9)

    def test_table_from_zero_without_declared_band(self):
        """C10 (problem 5): nothing below 0 m/s, with two densities and with one."""
        two = table((0, 1, 2), (1, 1.225), ((100, 100),) * 3)
        one = table((0, 1, 2), (1.225,), ((100,),) * 3)
        self.assertEqual(curve(two).operating_band, (0.0, 2.0))
        self.assertEqual(curve(one).operating_band, (0.0, 2.0))
        self.assertAlmostEqual(kw(simulation_wind_turbines(two, [0]), 0, Air_density=1.1)[0], 50.0, delta=1e-9)
        self.assertAlmostEqual(kw(simulation_wind_turbines(one, [0]), 0)[0], 50.0, delta=1e-9)

    def test_one_row_curve(self):
        """C11 (problem 14): a band without width, mean 0."""
        wt = manual([5], [100])
        self.assertEqual(curve(wt).operating_band, (5.0, 5.0))
        self.assertEqual(kw(simulation_wind_turbines(wt, G), 5)[0], 0.0)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G, POINT), 5)[0], 100.0, delta=1e-9)

    def test_band_outside_the_table_is_refused(self):
        """C19 (problem 13)."""
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

        pct = PowerCtTabular([3, 5, 8], [0, 100, 200], "kW", [0.8] * 3)
        pct.operating_band = (2, 9)
        with self.assertRaises(ValueError):
            simulation_wind_turbines(WindTurbine("p", 100, 100, pct), G)
        pct.operating_band = (6, 5)
        with self.assertRaises(ValueError):
            simulation_wind_turbines(WindTurbine("p", 100, 100, pct), G)


class DensityTest(unittest.TestCase):
    def setUp(self):
        """C13."""
        self.wt = table((3, 5, 8, 12, 25), (1, 1.225), ((0, 0), (100, 130), (900, 1100), (2000, 2000), (2000, 2000)),
                        cut_in_ms=3, cut_out_ms=25, default_air_density=1.225)
        self.ad = simulation_wind_turbines(self.wt, G)

    def expected(self, rho):
        return numeric_mean(self.wt, 5.5, 6.5, band=(3, 25), Air_density=rho)

    def test_in_a_column_and_between_two(self):
        for rho in (1.0, 1.1, 1.225):
            with self.subTest(rho=rho):
                self.assertAlmostEqual(kw(self.ad, 6, Air_density=rho)[0], self.expected(rho), delta=1e-6)

    def test_clipped_to_the_table(self):
        self.assertAlmostEqual(kw(self.ad, 6, Air_density=1.4)[0], self.expected(1.225), delta=1e-6)
        self.assertAlmostEqual(kw(self.ad, 6, Air_density=0.8)[0], self.expected(1.0), delta=1e-6)

    def test_default_density(self):
        self.assertAlmostEqual(kw(self.ad, 6)[0], self.expected(1.225), delta=1e-6)

    def test_irregular_axis_without_its_sentinel(self):
        """C14: the density is clipped to 1.3, not to GridInterpolator's sentinel."""
        wt = table((3, 8, 25), (1, 1.1, 1.3), ((0, 0, 0), (900, 1000, 1100), (2000, 2000, 2000)),
                   default_air_density=1.1)
        ad = simulation_wind_turbines(wt, G)
        expected = numeric_mean(wt, 7.5, 8.5, band=(3, 25), Air_density=1.3)
        for rho in (1.3, 2.0):
            with self.subTest(rho=rho):
                self.assertAlmostEqual(kw(ad, 8, Air_density=rho)[0], expected, delta=1e-6)

    def test_shapes_of_speed_and_density(self):
        v = np.array([4.0, 6.3, 9.0, 13.2, 7.7, 20.0, 24.6, 3.1])
        rho = np.array([1.0, 1.05, 1.1, 1.15, 1.2, 1.225, 1.01, 1.12])
        flat = kw(self.ad, v, Air_density=rho)
        for shape in ((2, 4), (2, 2, 2)):
            with self.subTest(shape=shape):
                got = self.ad.power(v.reshape(shape), type=0, Air_density=rho.reshape(shape)) / 1e3
                self.assertEqual(got.shape, shape)
                np.testing.assert_array_equal(got.ravel(), flat)
        np.testing.assert_allclose(kw(self.ad, v, Air_density=1.1), [kw(self.ad, x, Air_density=1.1)[0] for x in v],
                                   rtol=1e-12, atol=0)


class CtAndWakesTest(unittest.TestCase):
    def test_ct_is_the_original(self):
        """C16."""
        wt = manual(C1_WS, C1_KW, [0.8, 0.82, 0.81, 0.8, 0.6, 0.1])
        x = np.linspace(0, 30, 3001)
        np.testing.assert_array_equal(simulation_wind_turbines(wt, G).ct(x, type=0), wt.ct(x, type=0))

    def _mixed(self, second):
        from py_wake.wind_turbines import WindTurbine, WindTurbines

        a = curve(manual(C1_WS, C1_KW))
        return WindTurbines.from_WindTurbine_lst([WindTurbine("A", 100, 100, a), second])

    def test_mixed_park_with_wakes_yaw_and_density(self):
        """C17."""
        from py_wake.deficit_models.noj import NOJDeficit
        from py_wake.deflection_models.jimenez import JimenezWakeDeflection
        from py_wake.site import UniformWeibullSite
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import PropagateDownwind
        from py_wake.wind_turbines import WindTurbine

        d = curve(table((3, 6, 12, 25), (1, 1.225), ((20, 30), (400, 500), (3000, 3000), (3000, 3000)),
                        cut_in_ms=3, cut_out_ms=25))
        mixed = self._mixed(WindTurbine("D", 120, 100, d))
        site = UniformWeibullSite(p_wd=[1], a=[8], k=[2], ti=0.1)
        types, yaw = np.array([0, 1, 0]), np.array([25.0, 0.0, -10.0])
        sims = {}
        for mode in (BIN_MEAN, POINT):
            wf = PropagateDownwind(site, simulation_wind_turbines(mixed, IEA37_15, mode), NOJDeficit(), LinearSum(),
                                   deflectionModel=JimenezWakeDeflection())
            sims[mode] = wf([0, 400, 800], [0, 0, 0], type=types, wd=[270], ws=IEA37_15, yaw=yaw, tilt=0,
                            Air_density=1.1)
        mean, point = sims[BIN_MEAN], sims[POINT]
        for name in ("WS_eff", "CT", "P"):
            np.testing.assert_array_equal(mean[name].values, point[name].values, err_msg=name)
        self.assertFalse(np.allclose(mean.Power.values, point.Power.values))
        _, e = bin_edges(IEA37_15)
        ws_eff = mean.WS_eff.ilk()
        power = mean.Power.ilk()
        for i in range(3):
            for k in range(IEA37_15.size):
                v = ws_eff[i, 0, k] * np.cos(np.deg2rad(yaw[i]))
                j = int(np.clip(np.searchsorted(e, v, side="right") - 1, 0, IEA37_15.size - 1))
                lo, hi = e[j] + v - IEA37_15[j], e[j + 1] + v - IEA37_15[j]
                expected = numeric_mean(mixed, lo, hi, band=(3, 25), type=types[i], Air_density=1.1) * 1e3
                with self.subTest(turbine=i, ws=IEA37_15[k]):
                    self.assertAlmostEqual(power[i, 0, k], expected, delta=1e-3)

    def test_gross_power_of_a_mixed_park_without_yaw(self):
        """C17b: what sim.aep(with_wake_loss=False) weighs is the exact mean of each type over [a_k, b_k]."""
        from py_wake.deficit_models.noj import NOJDeficit
        from py_wake.site import UniformWeibullSite
        from py_wake.superposition_models import LinearSum
        from py_wake.wind_farm_models import PropagateDownwind
        from py_wake.wind_turbines import WindTurbine

        b = curve(build_wt_from_manual("B", 120, 110, [3, 6, 12, 25], [0, 400, 3000, 3000], [0.75] * 4))
        mixed = self._mixed(WindTurbine("B", 120, 110, b))
        site = UniformWeibullSite(p_wd=[0.5, 0.5], a=[8, 9], k=[2, 2.2], ti=0.1)
        types = [0, 1, 0]
        ad = simulation_wind_turbines(mixed, IEA37)
        sim = PropagateDownwind(site, ad, NOJDeficit(), LinearSum())([0, 500, 1000], [0, 0, 0], type=types, wd=[0],
                                                                     ws=IEA37)
        _, e = bin_edges(IEA37)
        ws = np.broadcast_to(np.asarray(sim.WS.ilk(), float), (3, 1, IEA37.size))
        gross = ad.power(ws, type=np.array(types)[:, None, None])
        for i in range(3):
            for k in range(IEA37.size):
                with self.subTest(turbine=i, bin=k):
                    expected = numeric_mean(mixed, e[k], e[k + 1], band=(3, 25), type=types[i]) * 1e3
                    self.assertAlmostEqual(gross[i, 0, k], expected, delta=1e-3)


class ContractTest(unittest.TestCase):
    """C18, C19 and C19b."""

    def test_originals_are_not_modified(self):
        wt = manual(C1_WS, C1_KW)
        pcf, inner = wt.powerCtFunction, curve(wt)
        power_ct, inner_dict = inner.power_ct, dict(inner.__dict__)
        x = np.linspace(0, 30, 301)
        before = kw(wt, x)
        simulation_wind_turbines(wt, G)
        self.assertIs(wt.powerCtFunction, pcf)
        self.assertIs(pcf.windTurbineFunction_lst[0], inner)
        self.assertIs(inner.power_ct, power_ct)
        self.assertEqual(inner.__dict__.keys(), inner_dict.keys())
        self.assertTrue(all(inner.__dict__[k] is v for k, v in inner_dict.items()))
        np.testing.assert_array_equal(kw(wt, x), before)

    def test_changing_the_grid_afterwards_changes_nothing(self):
        """Problem 10."""
        wt = manual(C1_WS, C1_KW)
        grid = np.array([3.0, 5.0, 8.0])
        ad = simulation_wind_turbines(wt, grid)
        before = kw(ad, 5.2)[0]
        grid[1] = 6.0
        self.assertEqual(kw(ad, 5.2)[0], before)

    def test_adapting_twice_is_adapting_the_original(self):
        wt = manual(C1_WS, C1_KW)
        half = np.arange(0, 70.01, 0.5)
        twice = simulation_wind_turbines(simulation_wind_turbines(wt, G), half)
        once = simulation_wind_turbines(wt, half)
        x = np.linspace(0, 30, 3001)
        np.testing.assert_array_equal(kw(twice, x), kw(once, x))
        self.assertIs(curve(twice).power_ct.curve, curve(wt))
        check_grid(twice, half)

    def test_pickle(self):
        wt = manual(C1_WS, C1_KW)
        ad = simulation_wind_turbines(wt, G)
        back = pickle.loads(pickle.dumps(ad))
        x = np.linspace(0, 30, 301)
        np.testing.assert_array_equal(kw(back, x), kw(ad, x))
        np.testing.assert_array_equal(back.ct(x, type=0), ad.ct(x, type=0))

    def test_check_grid(self):
        """Problem 7: the simulated grid has to be the adapted one."""
        wt = manual(C1_WS, C1_KW)
        ad = simulation_wind_turbines(wt, G)
        check_grid(ad, G.copy())
        for grid in ([3, 5, 8], np.arange(3, 26.0), None):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                check_grid(ad, grid)
        for grid in (G, [3, 5, 8], None):
            check_grid(wt, grid)

    def test_point_returns_the_same_object(self):
        """Problem 6: also without a grid."""
        wt = manual(C1_WS, C1_KW)
        self.assertIs(simulation_wind_turbines(wt, G, POINT), wt)
        self.assertIs(simulation_wind_turbines(wt, None, POINT), wt)
        self.assertIs(simulation_wind_turbines(wt, None, mode=POINT), wt)

    def test_bin_mean_is_the_default(self):
        wt = manual(C1_WS, C1_KW)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G), 5)[0], 125.0, delta=1e-9)
        self.assertAlmostEqual(kw(simulation_wind_turbines(wt, G, BIN_MEAN), 5)[0], 125.0, delta=1e-9)

    def test_single_curve_copy(self):
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

        pct = PowerCtTabular([3, 4.5, 5, 5.5, 10, 25], [0, 0, 100, 300, 2000, 2000], "kW", [0.8] * 6)
        out = bin_mean_power_ct(pct, G)
        self.assertIsNot(out, pct)
        self.assertAlmostEqual(float(out(np.array([5.0]), run_only=0)[0]), 125e3, delta=1e-6)
        self.assertEqual(float(pct(np.array([5.0]), run_only=0)[0]), 100e3)

    def test_errors(self):
        """C19."""
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

        wt = manual(C1_WS, C1_KW)
        for grid in (G, None):
            with self.subTest(mode="unknown", grid=grid), self.assertRaisesRegex(ValueError, "desconocido"):
                simulation_wind_turbines(wt, grid, "centre")
        with self.assertRaises(ValueError):
            simulation_wind_turbines(wt, None)
        for grid in ([], [3, 3], [5, 4], [3, np.nan], [-2, -1]):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                simulation_wind_turbines(wt, grid)
        pchip = WindTurbine("p", 100, 100, PowerCtTabular([3, 10, 25], [60, 2000, 2000], "kW", [0.8] * 3,
                                                          method="pchip"))
        with self.assertRaisesRegex(ValueError, "PowerCtTabular"):
            simulation_wind_turbines(pchip, G)

    def test_other_curves_are_refused(self):
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import PowerCtFunctions, PowerCtNDTabular

        other = PowerCtFunctions(lambda ws: ws * 0 + 1, "kW", lambda ws: ws * 0 + 0.8)
        nd = PowerCtNDTabular(["ws", "yaw"], [[3, 25], [0, 30]], [[0, 0], [1, 1]], "kW", [[0.8] * 2] * 2,
                              additional_models=[])
        for pcf in (other, nd):
            with self.subTest(curve=type(pcf).__name__), self.assertRaises(ValueError):
                simulation_wind_turbines(WindTurbine("x", 100, 100, pcf), G)

    def test_complex_and_missing_inputs(self):
        """C19b, with tables without DensityScale (problems 9, 11, 12 and 23)."""
        from py_wake.wind_turbines import WindTurbine
        from py_wake.wind_turbines.power_ct_functions import PowerCtNDTabular, PowerCtTabular

        ws = [3, 10, 25]
        two = PowerCtNDTabular(["ws", "Air_density"], [ws, [1.0, 1.225]], [[0, 0], [900, 1000], [2000, 2000]], "kW",
                               [[0.8, 0.8]] * 3, additional_models=[])
        one = PowerCtNDTabular(["ws", "Air_density"], [ws, [1.225]], [[0], [1000], [2000]], "kW", [[0.8]] * 3,
                               additional_models=[])
        flat = PowerCtTabular(ws, [0, 1000, 2000], "kW", [0.8] * 3, additional_models=[])
        with self.assertRaises(TypeError):
            simulation_wind_turbines(WindTurbine("f", 100, 100, flat), G).power(np.array([5.0 + 1e-20j]))
        for pcf in (two, one):
            ad = simulation_wind_turbines(WindTurbine("d", 100, 100, pcf), G)
            with self.subTest(columns=len(pcf.interp[0].x[1])):
                with self.assertRaises(TypeError):
                    ad.power(np.array([5.0]), Air_density=np.array([1.1 + 1e-20j]))
                with self.assertRaises(KeyError):
                    ad.power(np.array([5.0]))
                self.assertTrue(np.isfinite(ad.power(np.array([5.0]), Air_density=1.1)).all())


if __name__ == "__main__":
    unittest.main()
