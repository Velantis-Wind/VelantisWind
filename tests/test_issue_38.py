"""Regression coverage for real PyWake interpolation of irregular density axes."""
import unittest
import numpy as np
from VelantisWind.ag_core.turbine import build_wt_from_curve_table
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable


def turbine(densities=(1.0, 1.1, 1.3)):
    table = TurbineCurveTable(
        name="Density regression", diameter_m=100, hub_height_m=100,
        wind_speeds_ms=(3, 8, 25), air_densities=densities,
        power_kw=((0, 0, 0), (900, 1000, 1100), (2000, 2000, 2000)),
        ct=((0.7, 0.75, 0.8),) * 3, default_air_density=densities[1],
    )
    return build_wt_from_curve_table(table)


class DensityAxisRegressionTest(unittest.TestCase):
    def test_irregular_axis_clamps_upper_and_lower_bounds_for_power_and_ct(self):
        wt = turbine()
        rho = np.array([0.5, 1.0, 1.3, 1.35, 2.3, 2.5])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=0, Air_density=rho), [900000, 900000, 1100000, 1100000, 1100000, 1100000])
        np.testing.assert_allclose(wt.ct(ws, type=0, Air_density=rho), [0.7, 0.7, 0.8, 0.8, 0.8, 0.8])

    def test_regular_axis_keeps_existing_clamping(self):
        wt = turbine((1.0, 1.1, 1.2))
        rho = np.array([0.5, 1.0, 1.2, 1.35, 2.5])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=0, Air_density=rho), [900000, 900000, 1100000, 1100000, 1100000])
        np.testing.assert_allclose(wt.ct(ws, type=0, Air_density=rho), [0.7, 0.7, 0.8, 0.8, 0.8])

    def test_interior_interpolation_and_default_density_are_unchanged(self):
        wt = turbine()
        rho = np.array([1.0, 1.05, 1.1, 1.2, 1.3])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=0, Air_density=rho), [900000, 950000, 1000000, 1050000, 1100000])
        np.testing.assert_allclose(wt.ct(ws, type=0, Air_density=rho), [0.7, 0.725, 0.75, 0.775, 0.8])
        np.testing.assert_allclose(wt.power(np.array([8.0]), type=0), [1000000])
        np.testing.assert_allclose(wt.ct(np.array([8.0]), type=0), [0.75])

    def test_multidimensional_density_input_preserves_shape_and_values(self):
        wt = turbine()
        rho = np.array([[0.5, 1.05, 1.35], [1.1, 1.2, 2.5]])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=0, Air_density=rho), [[900000, 950000, 1100000], [1000000, 1050000, 1100000]])
        np.testing.assert_allclose(wt.ct(ws, type=0, Air_density=rho), [[0.7, 0.725, 0.8], [0.75, 0.775, 0.8]])

    def test_scalar_density_broadcasts_and_does_not_mutate_input(self):
        wt = turbine()
        np.testing.assert_allclose(wt.power(np.array([8.0, 8.0]), type=0, Air_density=1.35), [1100000, 1100000])
        rho = np.array([0.5, 1.35])
        original = rho.copy()
        wt.ct(np.array([8.0, 8.0]), type=0, Air_density=rho)
        np.testing.assert_array_equal(rho, original)

    def test_mixed_turbine_types_with_different_density_ranges(self):
        from py_wake.wind_turbines import WindTurbines
        a, b = turbine(), turbine((1.1, 1.2, 1.5))
        wt = WindTurbines(
            names=["A", "B"], diameters=[100, 100], hub_heights=[100, 100],
            powerCtFunctions=[a.powerCtFunction.windTurbineFunction_lst[0],
                              b.powerCtFunction.windTurbineFunction_lst[0]],
        )
        # Each type sees densities outside its own range during dispatch.
        rho = np.array([1.5, 1.0, 1.2, 1.35])
        types = np.array([0, 1, 0, 1])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=types, Air_density=rho),
                                   [1100000, 900000, 1050000, 1050000])
        np.testing.assert_allclose(wt.ct(ws, type=types, Air_density=rho),
                                   [0.8, 0.7, 0.775, 0.775])

    def test_other_irregular_spacing_clamps_to_its_own_bounds(self):
        wt = turbine((0.9, 1.05, 1.4))
        rho = np.array([0.8, 0.9, 1.4, 1.41, 2.4, 5.0])
        ws = np.full(rho.shape, 8.0)
        np.testing.assert_allclose(wt.power(ws, type=0, Air_density=rho),
                                   [900000, 900000, 1100000, 1100000, 1100000, 1100000])
        np.testing.assert_allclose(wt.ct(ws, type=0, Air_density=rho),
                                   [0.7, 0.7, 0.8, 0.8, 0.8, 0.8])

    def test_clamping_matches_endpoint_curve_at_intermediate_wind_speeds(self):
        wt = turbine()
        ws = np.array([4.0, 6.0, 8.0, 12.0, 20.0, 24.0])
        for outside, endpoint in ((0.5, 1.0), (1.35, 1.3), (2.5, 1.3)):
            with self.subTest(outside=outside):
                for evaluate in (wt.power, wt.ct):
                    actual = evaluate(ws, type=0, Air_density=outside)
                    expected = evaluate(ws, type=0, Air_density=endpoint)
                    np.testing.assert_allclose(actual, expected)


if __name__ == "__main__":
    unittest.main()
