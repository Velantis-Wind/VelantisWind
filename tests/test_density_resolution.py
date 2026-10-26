# -*- coding: utf-8 -*-
"""The single decision of which air density each turbine receives."""
import unittest

import numpy as np
import xarray as xr

from VelantisWind.ag_core.physics.air_density import AirDensityError, SiteAirDensityError, calibrated_air_density
from VelantisWind.ag_core.turbine import build_wt_from_curve_table, build_wt_from_manual
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.turbines.density_resolution import consumes_air_density, resolve_air_density

WS = (3.0, 8.0, 15.0, 25.0)


def table_turbine(name, densities, *, default=None, hub_height=90.0):
    n = len(densities)
    power = tuple(tuple(p * (1.0 + 0.1 * j) for j in range(n)) for p in (40.0, 1100.0, 3000.0, 3000.0))
    ct = tuple((c,) * n for c in (0.8, 0.79, 0.2, 0.05))
    table = TurbineCurveTable(
        name=name, diameter_m=100.0, hub_height_m=hub_height, wind_speeds_ms=WS, air_densities=tuple(densities),
        power_kw=power, ct=ct, default_air_density=default, cut_in_ms=3.0, cut_out_ms=25.0,
    )
    return build_wt_from_curve_table(table)


def one_density_turbine(name, hub_height=90.0):
    return build_wt_from_manual(name, 100.0, hub_height, list(WS), [40.0, 1100.0, 3000.0, 3000.0], [0.8, 0.79, 0.2, 0.05])


def park(*turbines):
    """Several single-type turbines combined with PyWake's own type selector."""
    from py_wake.wind_turbines import WindTurbine, WindTurbines

    def curve(wt):
        return getattr(wt.powerCtFunction, "windTurbineFunction_lst", [wt.powerCtFunction])[0]

    return WindTurbines.from_WindTurbine_lst([
        WindTurbine(name=wt.name(0), diameter=wt.diameter(0), hub_height=wt.hub_height(0), powerCtFunction=curve(wt))
        for wt in turbines
    ])


def resource_site(*, elevation=True, air_density=None):
    """A 3x3 resource grid (0–1000 m) whose terrain rises 100 m per 500 m in x."""
    from py_wake.site.xrsite import XRSite

    shape = (3, 3, 5)
    data = {
        "Sector_frequency": (("x", "y", "wd"), np.full(shape, 0.25)),
        "Weibull_A": (("x", "y", "wd"), np.full(shape, 9.0)),
        "Weibull_k": (("x", "y", "wd"), np.full(shape, 2.0)),
        "TI": 0.1,
    }
    if elevation:
        data["Elevation"] = (("x", "y"), np.array([[0.0] * 3, [100.0] * 3, [200.0] * 3]))
    if air_density is not None:
        data["Air_density"] = air_density
    coords = {"x": [0.0, 500.0, 1000.0], "y": [0.0, 500.0, 1000.0], "wd": [0.0, 90.0, 180.0, 270.0, 360.0]}
    return XRSite(xr.Dataset(data, coords=coords))


XS, YS = [0.0, 1000.0], [500.0, 500.0]
REF = dict(reference_density=1.15, reference_altitude_m=150.0)


def resolve(wt, mode, *, site=None, xs=XS, ys=YS, type_i=None, **reference):
    return resolve_air_density(site=site or resource_site(), wt=wt, xs=xs, ys=ys, type_i=type_i, mode=mode, **(reference or REF))


class PerTurbineTest(unittest.TestCase):
    def test_turbines_at_different_altitudes_get_their_calibrated_density(self):
        decision = resolve(table_turbine("A", (1.0, 1.1, 1.2)), "per_turbine")
        expected = calibrated_air_density(np.array([90.0, 290.0]), reference_density=1.15, reference_altitude_m=150.0)
        np.testing.assert_allclose(decision.values, expected)
        self.assertGreater(decision.values[0], decision.values[1])
        info = decision.info
        self.assertEqual(info["mode"], "per_turbine")
        self.assertEqual(info["terrain_elevation_m"], [0.0, 200.0])
        self.assertEqual(info["hub_altitude_m"], [90.0, 290.0])
        self.assertEqual(info["clamped"], [False, False])
        self.assertEqual((info["reference_density_kg_m3"], info["reference_altitude_m"]), (1.15, 150.0))
        self.assertEqual(decision.warnings, ())

    def test_hub_altitude_uses_the_real_height_of_each_type(self):
        wt = park(table_turbine("A", (1.0, 1.2), hub_height=84.0), table_turbine("B", (1.0, 1.2), hub_height=119.0))
        decision = resolve(wt, "per_turbine", xs=[0.0, 0.0], ys=[0.0, 500.0], type_i=[0, 1])
        self.assertEqual(decision.info["hub_altitude_m"], [84.0, 119.0])

    def test_each_type_is_clamped_to_its_own_table_only(self):
        wt = park(table_turbine("low", (0.95, 1.15)), table_turbine("high", (1.15, 1.25)))
        # Uniform 1.18: valid for "high", above the table of "low".
        decision = resolve(wt, "uniform", type_i=[0, 1], reference_density=1.18)
        np.testing.assert_allclose(decision.values, [1.15, 1.18])
        self.assertEqual(decision.info["clamped"], [True, False])
        self.assertEqual(decision.info["table_range_by_type"], [[0.95, 1.15], [1.15, 1.25]])
        self.assertEqual(len(decision.warnings), 1)
        self.assertIn("1 turbina(s)", decision.warnings[0])
        # Inside its own table nobody is clamped, even outside the other type's table.
        decision = resolve(wt, "uniform", type_i=[0, 0], reference_density=1.0)
        self.assertEqual(decision.info["clamped"], [False, False])

    def test_one_density_curve_in_a_mixed_park_is_left_alone(self):
        wt = park(table_turbine("table", (1.0, 1.2)), one_density_turbine("curve"))
        decision = resolve(wt, "per_turbine", type_i=[0, 1])
        self.assertIsNone(decision.info["values_kg_m3"][1])
        self.assertIsNotNone(decision.info["values_kg_m3"][0])
        self.assertIn("curve", decision.notes[0])


class UniformAndOffTest(unittest.TestCase):
    def test_uniform_needs_neither_elevation_nor_hub_height(self):
        decision = resolve(table_turbine("A", (1.0, 1.2)), "uniform", site=resource_site(elevation=False),
                           reference_density=1.1)
        np.testing.assert_allclose(decision.values, [1.1, 1.1])
        self.assertIsNone(decision.info["hub_altitude_m"])

    def test_off_passes_nothing_and_reports_each_type_default_by_position(self):
        wt = park(table_turbine("A", (1.0, 1.225), default=1.225), table_turbine("B", (1.0, 1.225), default=1.1))
        decision = resolve(wt, "off", xs=[0.0, 500.0, 1000.0], ys=[0.0, 0.0, 0.0], type_i=[1, 0, 1])
        self.assertIsNone(decision.values)
        self.assertEqual(decision.info["mode"], "off")
        self.assertEqual(decision.info["values_kg_m3"], [1.1, 1.225, 1.1])
        self.assertIn("ajuste está desactivado", decision.warnings[0])

    def test_without_density_tables_nothing_is_passed(self):
        wt = one_density_turbine("curve")
        self.assertFalse(consumes_air_density(wt))
        self.assertEqual(resolve(wt, "off"), resolve(wt, "off"))
        self.assertIsNone(resolve(wt, "off").info)
        decision = resolve(wt, "per_turbine")
        self.assertIsNone(decision.values)
        self.assertIn("ninguna curva del parque está tabulada por densidad", decision.warnings[0])


class ErrorTest(unittest.TestCase):
    def setUp(self):
        self.wt = table_turbine("A", (1.0, 1.2))

    def test_resource_with_its_own_air_density_is_refused_in_every_mode(self):
        for mode in ("off", "uniform", "per_turbine"):
            with self.subTest(mode=mode), self.assertRaisesRegex(SiteAirDensityError, "su propia variable 'Air_density'"):
                resolve(self.wt, mode, site=resource_site(air_density=1.0))

    def test_resource_density_is_refused_whenever_a_curve_would_take_it(self):
        from py_wake.examples.data.hornsrev1 import V80

        # A preset with PyWake's DensityScale would be rescaled by the resource's density.
        for mode in ("off", "per_turbine"):
            with self.subTest(mode=mode), self.assertRaises(SiteAirDensityError):
                resolve(V80(), mode, site=resource_site(air_density=1.0))
        # A curve that does not accept Air_density is not affected by it.
        self.assertIsNone(resolve(one_density_turbine("curve"), "off", site=resource_site(air_density=1.0)).info)

    def test_missing_references(self):
        for mode in ("uniform", "per_turbine"):
            with self.subTest(mode=mode), self.assertRaisesRegex(AirDensityError, "Falta la densidad de aire de referencia"):
                resolve(self.wt, mode, reference_density=None, reference_altitude_m=0.0)
        with self.assertRaisesRegex(AirDensityError, "Falta la altitud"):
            resolve(self.wt, "per_turbine", reference_density=1.1, reference_altitude_m=None)
        resolve(self.wt, "uniform", reference_density=1.1, reference_altitude_m=None)

    def test_per_turbine_needs_the_terrain_and_every_position_inside_it(self):
        with self.assertRaisesRegex(AirDensityError, "no incluye una superficie de elevación"):
            resolve(self.wt, "per_turbine", site=resource_site(elevation=False))
        with self.assertRaisesRegex(AirDensityError, "caen fuera de la malla"):
            resolve(self.wt, "per_turbine", xs=[0.0, -500.0])

    def test_per_turbine_does_not_invent_a_hub_height(self):
        class NoHeight:
            def __init__(self, wt):
                self.powerCtFunction = wt.powerCtFunction

            def hub_height(self, _type):
                raise AttributeError("no height")

        with self.assertRaisesRegex(AirDensityError, "altura de buje .* sería inventada"):
            resolve(NoHeight(self.wt), "per_turbine")
        resolve(NoHeight(self.wt), "uniform", reference_density=1.1)

    def test_unreadable_mode_is_not_off(self):
        with self.assertRaisesRegex(AirDensityError, "Modo de densidad de aire no reconocido"):
            resolve(self.wt, "on")

    def test_curve_that_would_rescale_itself_is_refused(self):
        from py_wake.examples.data.hornsrev1 import V80

        wt = park(self.wt, V80())
        with self.assertRaisesRegex(AirDensityError, "reescalar su potencia"):
            resolve(wt, "uniform", type_i=[0, 1], reference_density=1.1)
        self.assertIsNone(resolve(wt, "off", type_i=[0, 1]).values)


if __name__ == "__main__":
    unittest.main()
