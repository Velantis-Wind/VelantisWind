# -*- coding: utf-8 -*-
import unittest

import numpy as np
import xarray as xr

from VelantisWind.ag_core.results.aep_arrays import aep_per_turb, extract_directional_breakdown

# GWh a 8760 h por turbina (2), dirección (3) y velocidad (2).
BASE = np.arange(1.0, 13.0).reshape(2, 3, 2)
WD = [0.0, 120.0, 240.0]


def _da(hours):
    return xr.DataArray(BASE * hours / 8760.0, dims=("wt", "wd", "ws"), coords={"wd": WD})


class _Sim:
    """Resultado con ``aep(hours_pr_year=...)``, como PyWake."""

    def aep(self, hours_pr_year=8760.0):
        return _da(hours_pr_year)


class _OldSim:
    """Resultado cuyo ``aep`` no admite ``hours_pr_year``."""

    def aep(self):
        return _da(8760.0)


class AnnualisationTest(unittest.TestCase):
    def test_aep_per_turbine_uses_hours(self):
        expected = BASE.sum(axis=(1, 2)) * 1000.0
        for sim in (_Sim(), _OldSim()):
            with self.subTest(sim=type(sim).__name__):
                np.testing.assert_allclose(aep_per_turb(sim), expected)
                np.testing.assert_allclose(aep_per_turb(sim, hours_per_year=8766.0), expected * 8766.0 / 8760.0)

    def test_directional_breakdown_uses_hours(self):
        wake, free, dirs = extract_directional_breakdown(_Sim(), _Sim(), hours_per_year=8766.0)
        np.testing.assert_allclose(wake, BASE.sum(axis=(0, 2)) * 1000.0 * 8766.0 / 8760.0)
        np.testing.assert_allclose(free, wake)
        self.assertEqual(dirs, WD)


if __name__ == "__main__":
    unittest.main()
