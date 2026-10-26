# -*- coding: utf-8 -*-
"""Validation, band and interpolation of a power/Ct family tabulated by air density."""
import math
import unittest

import numpy as np

from VelantisWind.ag_core.log_text import shown
from VelantisWind.ag_core.turbines.density_curve import BAND_EDGE_EPS_MS, CurveTableError, TurbineCurveTable

WS = (3.0, 8.0, 15.0, 25.0)
RHO = (1.0, 1.2)
POWER = ((50.0, 60.0), (1000.0, 1200.0), (3000.0, 3000.0), (3000.0, 3000.0))
CT = ((0.8, 0.8), (0.79, 0.8), (0.2, 0.21), (0.05, 0.05))


def table(**changes):
    data = dict(
        name="Synthetic", diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=WS, air_densities=RHO,
        power_kw=POWER, ct=CT, default_air_density=1.2, cut_in_ms=3.0, cut_out_ms=25.0,
    )
    data.update(changes)
    return TurbineCurveTable(**data)


def replace_cell(matrix, i, j, value):
    rows = [list(row) for row in matrix]
    rows[i][j] = value
    return tuple(tuple(row) for row in rows)


class ValidationTest(unittest.TestCase):
    def assertRejected(self, pattern, **changes):
        with self.assertRaisesRegex(CurveTableError, pattern):
            table(**changes)

    def test_a_valid_family_is_accepted(self):
        t = table()
        self.assertTrue(t.is_density_dependent)
        self.assertEqual(t.density_range, (1.0, 1.2))
        self.assertEqual(t.max_power_kw, 3000.0)

    def test_ct_above_the_admission_threshold_names_the_point(self):
        self.assertRejected(r"Ct fuera de rango a 8 m/s y 1\.2 kg/m³: 1\.3 > 1\.2.*umbral de admisión",
                            ct=replace_cell(CT, 1, 1, 1.3))

    def test_ct_up_to_the_threshold_is_accepted(self):
        self.assertEqual(table(ct=replace_cell(CT, 1, 1, 1.2)).ct[1][1], 1.2)

    def test_negative_nan_and_infinite_values_name_the_point(self):
        self.assertRejected(r"potencia negativo a 15 m/s y 1 kg/m³", power_kw=replace_cell(POWER, 2, 0, -1.0))
        self.assertRejected(r"Ct negativo a 3 m/s y 1\.2 kg/m³", ct=replace_cell(CT, 0, 1, -0.1))
        self.assertRejected(r"Ct no numérico a 8 m/s y 1 kg/m³: nan", ct=replace_cell(CT, 1, 0, math.nan))
        self.assertRejected(r"potencia no numérico a 25 m/s y 1\.2 kg/m³: inf", power_kw=replace_cell(POWER, 3, 1, math.inf))

    def test_a_density_whose_curve_is_all_zero_is_rejected(self):
        self.assertRejected(r"curva de Ct a 1\.2 kg/m³ es cero en todos los puntos", ct=tuple((r[0], 0.0) for r in CT))
        self.assertRejected(r"curva de potencia a 1 kg/m³ es cero en todos los puntos",
                            power_kw=tuple((0.0, r[1]) for r in POWER))
        self.assertRejected(r"curva de Ct a 1 kg/m³ es cero", ct=tuple((0.0, 0.0) for _ in WS))

    def test_grids_must_be_strictly_increasing(self):
        self.assertRejected("velocidades de viento debe ser estrictamente creciente", wind_speeds_ms=(3.0, 8.0, 8.0, 25.0))
        self.assertRejected("densidades de aire debe ser estrictamente creciente", air_densities=(1.2, 1.0))

    def test_geometry_and_sizes(self):
        self.assertRejected("diámetro de rotor debe ser un número positivo", diameter_m=0.0)
        self.assertRejected("altura de buje debe ser un número positivo", hub_height_m=math.nan)
        self.assertRejected("al menos 2 velocidades", wind_speeds_ms=(3.0,), power_kw=((50.0, 60.0),), ct=((0.8, 0.8),),
                            cut_out_ms=None)
        self.assertRejected("tiene 3 filas y se esperaban 4", power_kw=POWER[:3])
        self.assertRejected("tiene 1 columnas y se esperaban 2", ct=((0.8,),) + CT[1:])

    def test_band_must_be_ordered_and_inside_the_table(self):
        self.assertRejected("cut-in .* debe ser menor que el cut-out", cut_in_ms=10.0, cut_out_ms=10.0)
        for changes in (dict(cut_in_ms=2.0), dict(cut_in_ms=26.0, cut_out_ms=None),
                        dict(cut_out_ms=26.0), dict(cut_in_ms=None, cut_out_ms=2.0)):
            with self.subTest(**changes):
                edge = "cut-in" if "cut_in_ms" in changes and changes["cut_in_ms"] is not None else "cut-out"
                self.assertRejected(rf"{edge} declarado \(\d+ m/s\) queda fuera de las velocidades tabuladas "
                                    r"\(3–25 m/s\): la tabla no cubre su propia banda", **changes)

    def test_error_keeps_its_template_and_data_for_the_translator(self):
        with self.assertRaises(CurveTableError) as ctx:
            table(ct=replace_cell(CT, 1, 1, 1.3))
        template, data = ctx.exception.template_item
        self.assertIn("{value:g} > {maximum:g}", template)
        self.assertEqual((data["ws"], data["rho"], data["value"], data["maximum"]), (8.0, 1.2, 1.3, 1.2))
        # Every piece is translated on its own and the numbers stay as they are.
        translated = shown(ctx.exception, lambda text: text.replace("Valor de", "Value of").replace("Ct", "CT"))
        self.assertTrue(translated.startswith("Value of CT fuera de rango a 8 m/s y 1.2 kg/m³: 1.3 > 1.2."))


def column(t, matrix, j, ws):
    """What a consumer reads from the table: linear interpolation in wind speed at density column ``j``."""
    return np.interp(ws, t.wind_speeds_ms, [row[j] for row in matrix])


class OperatingBandTest(unittest.TestCase):
    FINE = np.arange(0.0, 30.0, 0.01)

    def assertSameCurves(self, a, b):
        for j in range(len(RHO)):
            np.testing.assert_array_equal(column(a, a.power_kw, j, self.FINE), column(b, b.power_kw, j, self.FINE))
            np.testing.assert_array_equal(column(a, a.ct, j, self.FINE), column(b, b.ct, j, self.FINE))

    def test_table_that_agrees_with_its_band_is_unchanged(self):
        t = table()
        enforced = t.with_operating_band_enforced()
        self.assertSameCurves(enforced, t)
        self.assertEqual(enforced.notes, t.notes)

    def test_cut_out_inside_the_table_steps_to_zero(self):
        t = table(cut_out_ms=20.0).with_operating_band_enforced()
        for j in range(len(RHO)):
            self.assertEqual(column(t, t.power_kw, j, 20.0), 3000.0)
            self.assertEqual(column(t, t.power_kw, j, 20.0 + 2 * BAND_EDGE_EPS_MS), 0.0)
            self.assertEqual(column(t, t.ct, j, 20.0 + 2 * BAND_EDGE_EPS_MS), 0.0)
            self.assertEqual(column(t, t.power_kw, j, 25.0), 0.0)
        self.assertIn("banda declarada", t.notes[-1])

    def test_cut_in_between_nodes_is_interpolated_with_zero_just_below(self):
        t = table(cut_in_ms=5.5).with_operating_band_enforced()
        self.assertEqual(column(t, t.power_kw, 0, 5.5 - 2 * BAND_EDGE_EPS_MS), 0.0)
        self.assertEqual(column(t, t.power_kw, 1, 3.0), 0.0)
        self.assertAlmostEqual(column(t, t.power_kw, 0, 5.5), 525.0)
        self.assertAlmostEqual(column(t, t.power_kw, 1, 5.5), 630.0)
        self.assertAlmostEqual(column(t, t.ct, 0, 5.5), 0.795)

    def test_a_node_just_outside_the_band_is_zeroed(self):
        t = table(cut_in_ms=3.00002, cut_out_ms=24.99998).with_operating_band_enforced()
        for matrix in (t.power_kw, t.ct):
            self.assertEqual(column(t, matrix, 0, 3.0), 0.0)
            self.assertEqual(column(t, matrix, 1, 25.0), 0.0)
        self.assertAlmostEqual(column(t, t.power_kw, 1, 24.99998), 3000.0)

    def test_enforcing_twice_changes_nothing(self):
        once = table(cut_in_ms=5.5, cut_out_ms=20.0).with_operating_band_enforced()
        twice = once.with_operating_band_enforced()
        self.assertSameCurves(twice, once)
        self.assertEqual(twice.notes, once.notes)


class InterpolationTest(unittest.TestCase):
    def test_tabulated_density_is_exact_and_intermediate_is_linear(self):
        t = table()
        self.assertEqual(t.curve_at_density(1.0)[1], [50.0, 1000.0, 3000.0, 3000.0])
        ws, power, ct = t.curve_at_density(1.1)
        self.assertEqual(ws, list(WS))
        for got, want in zip(power, [55.0, 1100.0, 3000.0, 3000.0]):
            self.assertAlmostEqual(got, want)
        self.assertAlmostEqual(ct[1], 0.795)

    def test_density_outside_the_table_is_clamped_not_extrapolated(self):
        t = table()
        self.assertEqual(t.clamp_density(0.9), (1.0, True))
        self.assertEqual(t.clamp_density(1.1), (1.1, False))
        self.assertEqual(t.curve_at_density(1.4)[1], [60.0, 1200.0, 3000.0, 3000.0])

    def test_single_density_family_is_valid(self):
        t = table(air_densities=(1.225,), power_kw=tuple((r[0],) for r in POWER), ct=tuple((r[0],) for r in CT))
        self.assertFalse(t.is_density_dependent)
        self.assertEqual(t.curve_at_density(1.0)[1], [50.0, 1000.0, 3000.0, 3000.0])


if __name__ == "__main__":
    unittest.main()
