# -*- coding: utf-8 -*-
import unittest

import numpy as np

from VelantisWind.ag_core.simulation.runner import simulate


class _FakeSim:
    def __init__(self, types):
        self._types = np.asarray(types)

    def __getitem__(self, key):
        return type("Coord", (), {"values": self._types})()


class TypeArgumentTest(unittest.TestCase):
    xs = np.array([0.0, 500.0, 1000.0])
    ys = np.zeros(3)
    types = np.array([0, 1, 0])

    def test_public_type_argument_and_ws_are_passed(self):
        calls = []

        def wfm(x, y, wd=None, ws=None, type=0):
            calls.append({"wd": wd, "ws": ws, "type": type})
            return _FakeSim(type)

        simulate(wfm, self.xs, self.ys, type_i=self.types, wd=[270.0], ws=[8.0])
        np.testing.assert_array_equal(calls[0]["type"], self.types)
        np.testing.assert_array_equal(calls[0]["ws"], [8.0])

    def test_one_type_passes_nothing_and_there_is_no_retry(self):
        calls = []

        def wfm(x, y, wd=None, ws=None, **kwargs):
            calls.append(kwargs)
            raise ValueError("argument, type, required to calculate power and ct")

        with self.assertRaises(ValueError):
            simulate(wfm, self.xs, self.ys, wd=[270.0], ws=[8.0])
        self.assertEqual(calls, [{}])  # one call, without a type=0 retry

    def test_result_with_other_types_is_rejected(self):
        def wfm(x, y, type=0):
            return _FakeSim(np.zeros(3, dtype=int))

        with self.assertRaises(RuntimeError):
            simulate(wfm, self.xs, self.ys, type_i=self.types)

    def test_wrong_number_of_types(self):
        with self.assertRaises(ValueError):
            simulate(lambda **k: None, self.xs, self.ys, type_i=[0, 1])


if __name__ == "__main__":
    unittest.main()
