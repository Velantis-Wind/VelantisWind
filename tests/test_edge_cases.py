# -*- coding: utf-8 -*-
"""The module of the edge cases (#63, P1): read-only diagnosis of negative speeds, non-finite values, the reasons of
the effective TI and the predicates of WeightedSum, with synthetic arrays."""
import math
import unittest

import numpy as np

from VelantisWind.ag_core import edge_cases as ec

NAN, INF = math.nan, math.inf


def cube(values):
    """A (turbine, direction, speed) array from nested lists."""
    return np.asarray(values, dtype=float)


class ReadOnlyTest(unittest.TestCase):
    def test_a_view_cannot_write_and_the_original_stays_writable(self):
        a = np.arange(6.0)
        view = ec.read_only(a)
        with self.assertRaises(ValueError):
            view[0] = 1.0
        a[0] = 5.0  # the caller's array is not changed by the module
        self.assertEqual(view[0], 5.0)
        self.assertTrue(a.flags.writeable)

    def test_the_functions_do_not_change_what_they_receive(self):
        ws = cube([[[1.0, -2.0], [NAN, 3.0]], [[INF, 4.0], [5.0, 6.0]]])
        aep = cube([[[NAN, 1.0], [2.0, 3.0]], [[INF, 1.0], [0.0, NAN]]])
        p = cube([[[0.0, 0.1], [0.2, 0.3]], [[0.4, 0.1], [0.0, NAN]]])
        freq = cube([[[0.0], [0.5]], [[0.5], [0.0]]])
        before = [x.copy() for x in (ws, aep, p, freq)]
        diag = ec.simulation_diagnosis(ws_eff=ws, aep=aep, p=p, power=aep, frequency=freq, directions=[0.0, 90.0])
        ec.diagnosis_warnings(diag, "X")
        ec.ti_reasons(ws, p, np.array([NAN, 1.0]), 2)
        for x, y in zip((ws, aep, p, freq), before):
            np.testing.assert_array_equal(x, y)
            self.assertTrue(x.flags.writeable)

    def test_guarded_logs_a_failure_and_returns_none(self):
        logged = []

        def broken():
            raise RuntimeError("roto")
        self.assertIsNone(ec.guarded(logged.append, broken))
        self.assertEqual(logged, ["Aviso no disponible: RuntimeError: roto"])
        self.assertEqual(ec.guarded(logged.append, lambda x: x + 1, 1), 2)
        self.assertEqual(len(logged), 1)


class OrdinaryTest(unittest.TestCase):
    def test_finite_and_positive_gives_nothing(self):
        ws = np.linspace(0.0, 25.0, 60).reshape(2, 3, 10)
        aep = np.linspace(0.0, 1.0, 60).reshape(2, 3, 10)
        self.assertIsNone(ec.speed_diagnosis(ws))
        self.assertIsNone(ec.simulation_diagnosis(ws_eff=ws, aep=aep, p=aep, power=aep, frequency=aep[..., :1]))
        self.assertEqual(ec.diagnosis_warnings(None, "X"), {"warnings": [], "notes": []})
        self.assertIsNone(ec.ti_reasons(aep, aep, np.array([0.1, 0.2]), 2))

    def test_zero_is_not_negative_nor_is_minus_zero(self):
        self.assertIsNone(ec.speed_diagnosis(np.array([[[0.0, -0.0, 1.0]]])))


class SpeedTest(unittest.TestCase):
    def test_negatives_their_minimum_and_turbines(self):
        ws = cube([[[1.0, 2.0]], [[-0.5, 3.0]], [[-6016.0, -INF]]])
        d = ec.speed_diagnosis(ws)
        self.assertEqual(d["negative"], 3)
        self.assertEqual(d["min_m_s"], -6016.0)
        self.assertEqual(d["turbines"], [2, 3])
        self.assertEqual((d["nan"], d["+inf"], d["-inf"]), (0, 0, 1))
        self.assertEqual(d["cells"], 6)

    def test_non_finite_without_negatives(self):
        d = ec.speed_diagnosis(cube([[[NAN, INF, 1.0]]]))
        self.assertEqual((d["negative"], d["nan"], d["+inf"]), (0, 1, 1))
        self.assertNotIn("turbines", d)

    def test_a_field_of_the_raster(self):
        d = ec.speed_diagnosis(np.array([[1.0, -1.0], [NAN, 2.0]]), turbines=False)
        self.assertEqual((d["negative"], d["nan"]), (1, 1))
        self.assertNotIn("turbines", d)


class AepTest(unittest.TestCase):
    """Two turbines, two directions (0 and 90), two speeds."""

    def diag(self, aep, p, freq=None, **kw):
        return ec.simulation_diagnosis(ws_eff=np.ones_like(aep), aep=aep, p=p, power=np.ones_like(aep),
                                       frequency=freq, directions=[0.0, 90.0], **kw)["aep"]

    def test_group_1_by_zero_probability(self):
        aep = cube([[[NAN, 1.0], [1.0, 1.0]], [[1.0, 1.0], [1.0, 1.0]]])
        p = cube([[[0.0, 0.1], [0.1, 0.1]], [[0.1, 0.1], [0.1, 0.1]]])
        d = self.diag(aep, p)
        self.assertEqual((d["group1"], d["group2"]), (1, 0))
        self.assertEqual((d["partial_turbines"], d["non_finite_turbines"], d["partial_sectors_deg"]), ([], [], []))
        self.assertEqual(ec.diagnosis_warnings({"aep": d}, "X")["warnings"], [])

    def test_group_1_by_a_sector_of_zero_frequency(self):
        """An empty sector of a WRG: P NaN in the 0 m/s case of the direction with frequency 0."""
        aep = cube([[[1.0, 1.0], [NAN, 1.0]], [[1.0, 1.0], [NAN, 1.0]]])
        p = cube([[[0.1, 0.1], [NAN, 0.0]], [[0.1, 0.1], [NAN, 0.0]]])
        freq = cube([[[0.6], [0.0]], [[0.6], [0.0]]])
        d = self.diag(aep, p, freq)
        self.assertEqual((d["group1"], d["group2"]), (2, 0))

    def test_without_evidence_of_zero_frequency_it_is_group_2(self):
        """A row without any finite P (a WRG with A negative): without a frequency of 0, it has energy."""
        aep = cube([[[1.0, 1.0], [NAN, NAN]], [[1.0, 1.0], [1.0, 1.0]]])
        p = cube([[[0.1, 0.1], [NAN, NAN]], [[0.1, 0.1], [0.1, 0.1]]])
        for freq in (None, cube([[[0.6], [0.4]], [[0.6], [0.4]]])):
            d = self.diag(aep, p, freq)
            self.assertEqual((d["group1"], d["group2"]), (0, 2))
            self.assertEqual(d["partial_turbines"], [1])
            self.assertEqual(d["partial_sectors_deg"], [90.0])

    def test_an_infinite_case_is_kept_by_nansum_and_the_total_is_not_finite(self):
        aep = cube([[[INF, 1.0], [1.0, 1.0]], [[NAN, 1.0], [1.0, -INF]]])
        p = np.full_like(aep, 0.1)
        d = self.diag(aep, p)
        self.assertEqual(d["non_finite_turbines"], [1, 2])
        self.assertEqual(d["partial_turbines"], [2])  # it leaves out its NaN, although its total is −inf (Sol, final r3)
        # A direction whose sum is infinite is skipped whole by the aggregation to the sectors.
        self.assertEqual(d["lost_directions_deg"], [0.0, 90.0])
        self.assertEqual(d["partial_sectors_deg"], [0.0, 90.0])
        self.assertEqual((d["nan"], d["+inf"], d["-inf"]), (1, 1, 1))
        self.assertFalse(d["farm_finite"])
        self.assertFalse(d["overflow"])

    def test_a_direction_with_an_infinite_case_loses_its_finite_energy(self):
        """[+inf, 4] in one direction: np.nansum gives +inf, and the sector gets 0 (Sol, P1 r1)."""
        from VelantisWind.ag_core.results import aep_arrays
        aep = cube([[[INF, 4.0], [1.0, 1.0]]])
        d = self.diag(aep, np.full_like(aep, 0.1))
        values, _ = aep_arrays._aggregate_to_sector_centers(list(np.nansum(aep, axis=(0, 2)) * 1000.0), [0.0, 90.0],
                                                             [0.0, 90.0])
        self.assertEqual(values[0], 0.0)
        self.assertEqual((d["lost_directions_deg"], d["partial_sectors_deg"]), ([0.0], [0.0]))
        text = "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"])
        self.assertIn("toda la energía de las direcciones cuya suma no es finita (0°)", text)

    def test_the_counts_of_group_2_are_its_own(self):
        """A NaN without energy and an infinite case with energy: «1 case with energy (NaN 0, +inf 1)»."""
        aep = cube([[[NAN, INF]]])
        d = self.diag(aep, cube([[[0.0, 0.1]]]))
        self.assertEqual(d["group2_counts"], {"nan": 0, "+inf": 1, "-inf": 0})
        text = "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"])
        self.assertIn("AEP no finito en 1 casos que pueden tener energía (NaN 0, +inf 1, −inf 0)", text)

    def test_an_overflow_of_finite_cases_is_said(self):
        aep = cube([[[1e308, 1e308]], [[1.0, 1.0]]])
        d = self.diag(aep, np.full_like(aep, 0.1))
        self.assertTrue(d["overflow"])
        self.assertEqual(d["non_finite_turbines"], [1])
        self.assertEqual((d["group1"], d["group2"]), (0, 0))
        text = "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"])
        self.assertIn("X: una suma del AEP desborda", text)
        self.assertIn("X: AEP no finito en las turbinas 1, y en el total del parque.", text)

    def test_an_overflow_of_the_farm_only(self):
        """Two turbines of 1.5e308 MWh each: each total is finite, the farm's is not."""
        aep = cube([[[1.5e305]], [[1.5e305]]])
        d = ec.simulation_diagnosis(ws_eff=np.ones_like(aep), aep=aep, p=np.full_like(aep, 0.1))["aep"]
        self.assertEqual(d["non_finite_turbines"], [])
        self.assertFalse(d["farm_finite"])
        self.assertTrue(d["overflow"])
        self.assertIn("X: AEP total del parque no finito.", "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"]))

    def test_an_overflow_inside_a_sector_is_said(self):
        """Four directions, two per sector, with finite totals whose sum per sector overflows (Sol, P1 r2)."""
        from VelantisWind.ag_core.results import aep_arrays
        big = 1.2e305
        aep = cube([[[big], [big], [-big], [-big]]])
        dirs, centers = [350.0, 10.0, 170.0, 190.0], [0.0, 180.0]
        values, _ = aep_arrays._aggregate_to_sector_centers(list(np.nansum(aep, axis=(0, 2)) * 1000.0), dirs, centers)
        self.assertEqual(values, [INF, -INF])
        d = ec.simulation_diagnosis(ws_eff=np.ones_like(aep), aep=aep, p=np.full_like(aep, 0.1), directions=dirs,
                                    sector_centers=centers)["aep"]
        self.assertTrue(d["overflow"])
        self.assertEqual(d["non_finite_sectors_deg"], [0.0, 180.0])
        self.assertTrue(d["farm_finite"])
        text = "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"])
        self.assertIn("X: AEP por sector no finito en los sectores 0, 180° (su suma desborda).", text)

    def test_partial_turbines_with_a_non_finite_farm(self):
        aep = cube([[[NAN, 1.0]], [[INF, 1.0]]])
        text = "\n".join(ec.diagnosis_warnings({"aep": self.diag(aep, np.full_like(aep, 0.1))}, "X")["warnings"])
        self.assertIn("X: AEP parcial (omite casos no finitos con energía) en las turbinas 1, y en el total del parque.",
                      text)
        self.assertIn("X: AEP no finito en las turbinas 2, y en el total del parque.", text)

    def test_a_total_that_leaves_out_a_case_is_partial_whatever_its_state(self):
        """``[NaN, +inf]`` with energy: ``nansum`` leaves out the NaN and gives +inf; ``[NaN, 1e306]``: it leaves out
        the NaN and overflows. Both partial and not finite, and the overflow does not say every case is finite (Sol,
        final r3)."""
        for cells in ([NAN, INF], [NAN, 1e306]):
            aep = cube([[cells]])
            with self.subTest(cells=cells):
                d = self.diag(aep, np.full_like(aep, 0.1))
                self.assertEqual((d["partial_turbines"], d["non_finite_turbines"]), ([1], [1]))
                text = "\n".join(ec.diagnosis_warnings({"aep": d}, "X")["warnings"])
                self.assertIn("X: AEP parcial (omite casos no finitos con energía) en las turbinas 1, y en el total "
                              "del parque.", text)
                self.assertNotIn("son finitos", text)
        d = self.diag(cube([[[NAN, 1e306]]]), np.full((1, 1, 2), 0.1))
        self.assertTrue(d["overflow"])
        self.assertIn("X: una suma del AEP desborda: da un infinito sin ningún caso infinito.",
                      ec.diagnosis_warnings({"aep": d}, "X")["warnings"])

    def test_sectors_of_the_resource(self):
        aep = cube([[[1.0, 1.0], [NAN, 1.0]]])
        p = np.full_like(aep, 0.1)
        d = ec.simulation_diagnosis(ws_eff=np.ones_like(aep), aep=aep, p=p, directions=[350.0, 100.0],
                                    sector_centers=[0.0, 90.0, 180.0, 270.0])["aep"]
        self.assertEqual(d["partial_sectors_deg"], [90.0])

    def test_probability_broadcast_from_direction_and_speed(self):
        aep = cube([[[NAN, 1.0]], [[NAN, 1.0]]])
        d = self.diag(aep, np.array([[[0.0, 0.2]]]))
        self.assertEqual(d["group1"], 2)

    def test_a_frequency_per_direction_must_be_aligned_with_the_directions(self):
        """Two directions and two speeds: a frequency of shape (wd,) would broadcast on the speeds (Sol, P1 r1 of the
        Optimizer)."""
        aep = cube([[[NAN, 2.0], [NAN, 3.0]]])
        p = cube([[[NAN, 0.1], [0.1, 0.1]]])
        d = self.diag(aep, p, np.array([0.0, 1.0]))
        self.assertIn("no alineada", d["classification"])
        self.assertEqual((d["group1"], d["group2"]), (0, 2))
        d = self.diag(aep, p, np.array([0.0, 1.0]).reshape(1, 2, 1))
        self.assertEqual((d["group1"], d["group2"]), (1, 1))
        self.assertNotIn("classification", d)

    def test_a_failed_classification_counts_every_case_with_energy(self):
        aep = cube([[[NAN, 1.0]]])
        d = self.diag(aep, np.ones((3, 3, 3)))  # cannot broadcast
        self.assertIn("classification", d)
        self.assertEqual((d["group1"], d["group2"]), (0, 1))

    def test_non_finite_probability_and_power_are_counted(self):
        aep = cube([[[1.0, 1.0]]])
        d = ec.simulation_diagnosis(ws_eff=aep, aep=aep, p=cube([[[NAN, 0.1]]]), power=cube([[[INF, 1.0]]]))
        self.assertEqual(d["p"]["nan"], 1)
        self.assertEqual(d["power"]["+inf"], 1)
        self.assertNotIn("aep", d)

    def test_ws_eff_not_finite_with_a_finite_aep_is_counted(self):
        """A2A with blockage and ss_gamma = −inf (Astra, round 8): WS_eff = +inf with power 0 and a finite AEP."""
        aep = cube([[[0.0, 1.0]]])
        d = ec.simulation_diagnosis(ws_eff=cube([[[INF, 5.0]]]), aep=aep, p=aep, power=aep)
        self.assertEqual(d["ws_eff"]["+inf"], 1)
        self.assertNotIn("aep", d)


class TextsTest(unittest.TestCase):
    def test_each_case_has_its_text_and_group_1_goes_to_the_log(self):
        aep = cube([[[NAN, 1.0], [NAN, INF]]])
        p = cube([[[0.0, 0.1], [0.1, 0.1]]])
        d = ec.simulation_diagnosis(ws_eff=cube([[[-1.0, NAN], [2.0, 3.0]]]), aep=aep, p=p, power=cube([[[1.0, 1.0], [1.0, INF]]]),
                                    directions=[0.0, 90.0])
        texts = ec.diagnosis_warnings(d, "Cálculo principal")
        joined = "\n".join(texts["warnings"])
        for part in ("velocidad efectiva negativa en 1 de 4 casos", "mínimo finito -1 m/s", "turbinas 1",
                     "velocidad efectiva no finita en 1 casos", "potencia no finita en 1 casos",
                     "AEP no finito en 2 casos que pueden tener energía", "AEP no finito en las turbinas 1",
                     "AEP por sector parcial", "sectores 90°"):
            self.assertIn(part, joined)
        self.assertEqual(len(texts["notes"]), 1)
        self.assertIn("1 casos sin energía", texts["notes"][0])
        self.assertTrue(all(w.template_item for w in texts["warnings"] + texts["notes"]))

    def test_partial_total(self):
        d = ec.simulation_diagnosis(ws_eff=cube([[[1.0, 1.0]]]), aep=cube([[[NAN, 1.0]]]), p=cube([[[0.1, 0.1]]]))
        text = "\n".join(ec.diagnosis_warnings(d, "A_0")["warnings"])
        self.assertIn("A_0: AEP parcial (omite casos no finitos con energía) en las turbinas 1", text)


class TiReasonsTest(unittest.TestCase):
    def test_each_reason_with_its_precedence(self):
        ti = cube([[[INF, NAN]], [[NAN, 0.1]], [[0.1, 0.1]], [[0.1, 0.1]], [[0.1, 0.1]], [[0.1, 0.1]]])
        p = cube([[[NAN, 0.1]], [[NAN, 0.1]], [[NAN, 0.1]], [[0.0, 0.0]], [[0.1, 0.1]], [[0.1, 0.1]]])
        values = np.array([NAN, NAN, NAN, NAN, NAN, 0.1])
        self.assertEqual(ec.ti_reasons(ti, p, values, 6),
                         {1: "infinite", 2: "nan", 3: "nan_weight", 4: "zero_weight", 5: "reduction"})

    def test_not_available(self):
        self.assertEqual(ec.ti_reasons(None, None, None, 2), {1: "unavailable", 2: "unavailable"})
        self.assertEqual(ec.ti_reasons(cube([[[0.1]]]), cube([[[0.1]]]), None, 1), {1: "unavailable"})

    def test_every_reason_has_its_text(self):
        self.assertEqual(set(ec.TI_REASON_TEXTS),
                         {"unavailable", "infinite", "nan", "nan_weight", "zero_weight", "reduction"})


class WeightedSumPredicatesTest(unittest.TestCase):
    def test_the_unequivocal_cases_discard_the_weighting(self):
        for params, arg in (({"max_iter": 0}, "max_iter"), ({"max_iter": -INF}, "max_iter"),
                            ({"max_iter": False}, "max_iter"), ({"max_iter": NAN}, "max_iter"),
                            ({"max_err": NAN}, "max_err"), ({"max_err": 1}, "max_err"), ({"max_err": INF}, "max_err"),
                            ({"delta": NAN}, "delta"), ({"weight_limit": NAN}, "weight_limit")):
            with self.subTest(params=params):
                self.assertEqual(ec.weighting_discarded(params), arg)

    def test_the_rest_does_not_discard_it(self):
        for params in ({}, {"max_err": 0.95}, {"max_err": 0.9}, {"delta": INF}, {"delta": -1.0},
                       {"weight_limit": 0}, {"max_iter": INF}, {"max_err": -1.0}, {"max_iter": 1}):
            with self.subTest(params=params):
                self.assertIsNone(ec.weighting_discarded(params))

    def test_may_not_terminate(self):
        self.assertEqual(ec.may_not_terminate({"max_err": 1e-12}), ["max_err"])
        self.assertEqual(ec.may_not_terminate({"max_err": 0, "max_iter": INF}), ["max_err", "max_iter"])
        self.assertEqual(ec.may_not_terminate({"max_iter": INF}), ["max_iter"])
        self.assertEqual(ec.may_not_terminate({"max_err": 1e-11}), [])
        self.assertEqual(ec.may_not_terminate({}), [])
        # Without weighting, nothing to iterate: no warning of termination (precedence).
        self.assertEqual(ec.may_not_terminate({"max_err": -1.0, "max_iter": 0}), [])
        self.assertEqual(ec.may_not_terminate({"max_iter": INF, "delta": NAN}), [])


if __name__ == "__main__":
    unittest.main()
