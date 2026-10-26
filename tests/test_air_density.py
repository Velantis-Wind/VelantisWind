# -*- coding: utf-8 -*-
"""Calibrated ISA profile and terrain elevation of each hub."""
import types
import unittest

import numpy as np
import xarray as xr

from VelantisWind.ag_core.physics.air_density import (
    AirDensityError,
    air_density_per_turbine,
    calibrated_air_density,
    isa_density,
    site_defines_air_density,
    terrain_elevation_from_site,
)


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


class CalibratedIsaTest(unittest.TestCase):
    def test_reference_density_is_reproduced_exactly_at_its_altitude(self):
        for rho, z in ((1.105, 1250.0), (1.18, 300.0), (1.0, -300.0)):
            with self.subTest(rho=rho, z=z):
                self.assertEqual(float(calibrated_air_density(z, reference_density=rho, reference_altitude_m=z)), rho)

    def test_profile_is_the_isa_lapse_scaled_to_the_reference(self):
        rho = calibrated_air_density(np.array([500.0, 1500.0]), reference_density=1.1, reference_altitude_m=1000.0)
        np.testing.assert_allclose(rho, 1.1 * isa_density(np.array([500.0, 1500.0])) / isa_density(1000.0))
        self.assertGreater(rho[0], 1.1)
        self.assertLess(rho[1], 1.1)

    def test_hub_altitude_is_terrain_plus_real_hub_height(self):
        density, hub_altitude = air_density_per_turbine(
            [100.0, 250.0], [84.0, 119.0], reference_density=1.2, reference_altitude_m=184.0)
        np.testing.assert_allclose(hub_altitude, [184.0, 369.0])
        self.assertEqual(float(density[0]), 1.2)
        self.assertLess(density[1], density[0])

    def test_implausible_altitudes_and_references_are_rejected(self):
        with self.assertRaisesRegex(AirDensityError, "fuera del rango plausible"):
            air_density_per_turbine([9500.0], [100.0], reference_density=1.2, reference_altitude_m=0.0)
        with self.assertRaisesRegex(AirDensityError, "altitud de referencia queda fuera del rango plausible"):
            calibrated_air_density(0.0, reference_density=1.2, reference_altitude_m=12000.0)
        with self.assertRaisesRegex(AirDensityError, "densidad de referencia debe ser un número positivo"):
            calibrated_air_density(0.0, reference_density=0.0, reference_altitude_m=0.0)
        with self.assertRaisesRegex(AirDensityError, "altitud de referencia debe ser un número finito; se recibió 'x'"):
            calibrated_air_density(0.0, reference_density=1.2, reference_altitude_m="x")
        with self.assertRaisesRegex(AirDensityError, "sin cota de terreno válida"):
            air_density_per_turbine([np.nan], [100.0], reference_density=1.2, reference_altitude_m=0.0)


class TerrainElevationTest(unittest.TestCase):
    def test_elevation_is_read_at_each_position(self):
        elevation = terrain_elevation_from_site(resource_site(), [0.0, 500.0, 1000.0], [400.0, 400.0, 400.0])
        np.testing.assert_allclose(elevation, [0.0, 100.0, 200.0])

    def test_resource_without_elevation_is_not_sea_level(self):
        site = resource_site(elevation=False)
        # PyWake itself would answer 0 m here.
        np.testing.assert_allclose(site.elevation(np.array([500.0]), np.array([500.0])), [0.0])
        with self.assertRaisesRegex(AirDensityError, "no incluye una superficie de elevación"):
            terrain_elevation_from_site(site, [500.0], [500.0])

    def test_position_one_grid_step_outside_does_not_wrap_to_the_other_edge(self):
        site = resource_site()
        # PyWake returns the finite elevation of the opposite edge for this point.
        self.assertTrue(np.isfinite(site.elevation(np.array([-500.0]), np.array([0.0]))).all())
        with self.assertRaisesRegex(AirDensityError, r"1 de 2 turbina\(s\) caen fuera de la malla .* turbina 1 en \(-500\.0, 0\.0\)"):
            terrain_elevation_from_site(site, [500.0, -500.0], [0.0, 0.0])

    def test_resource_with_its_own_air_density_is_detected(self):
        self.assertTrue(site_defines_air_density(resource_site(air_density=1.1)))
        self.assertFalse(site_defines_air_density(resource_site()))
        self.assertFalse(site_defines_air_density(types.SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
