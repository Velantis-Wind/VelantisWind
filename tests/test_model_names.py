# -*- coding: utf-8 -*-
import unittest
from unittest import mock

from VelantisWind import i18n
from VelantisWind.energy_core.dialog_state import DialogStateError, check_unique_model_names
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput
from VelantisWind.energy_core.validation import validate_energy_config

# Los mensajes se comprueban en español, sea cual sea el idioma guardado.
_SPANISH = mock.patch.object(i18n, "current_language", return_value="es")


def setUpModule():
    _SPANISH.start()


def tearDownModule():
    _SPANISH.stop()


class UniqueModelNamesTest(unittest.TestCase):
    def test_distinct_and_empty_names_are_accepted(self):
        check_unique_model_names([{"name": "A"}, {"name": "B"}, {"name": ""}, {}])

    def test_empty_name_uses_the_row_layer_name(self):
        with self.assertRaisesRegex(DialogStateError, "Modelo 2"):
            check_unique_model_names([{"name": "Modelo 2"}, {"name": ""}])

    def test_repeated_name_is_rejected(self):
        with self.assertRaisesRegex(DialogStateError, "Custom WT"):
            check_unique_model_names([{"name": "Custom WT (CSV)"}, {"name": "B"}, {"name": " Custom WT (CSV) "}])



class ValidationModelNamesTest(unittest.TestCase):
    def _name_errors(self, models):
        config = EnergyRunConfig(models=models)
        return [i for i in validate_energy_config(config) if i.is_error and "nombre distinto" in i.message]

    def test_same_name_in_different_rows_is_an_error(self):
        models = [
            TurbineModelInput(name="A", wt=object(), coords_xy=[(0, 0)], source_row_index=0),
            TurbineModelInput(name="A", wt=object(), coords_xy=[(1, 1)], source_row_index=1),
        ]
        self.assertEqual(len(self._name_errors(models)), 1)

    def test_same_name_without_row_index_is_an_error(self):
        for row in (None, -1, float("inf")):
            with self.subTest(row=row):
                models = [TurbineModelInput(name="A", wt=object(), coords_xy=[(i, i)], source_row_index=row) for i in range(2)]
                self.assertEqual(len(self._name_errors(models)), 1)

    def test_empty_names_count_as_the_default_name(self):
        models = [
            TurbineModelInput(name="", wt=object(), coords_xy=[(0, 0)], source_row_index=0),
            TurbineModelInput(name="Custom WT", wt=object(), coords_xy=[(1, 1)], source_row_index=1),
        ]
        self.assertEqual(len(self._name_errors(models)), 1)

    def test_layers_of_one_row_may_share_the_name(self):
        models = [
            TurbineModelInput(name="A", wt=object(), coords_xy=[(i, i)], source_row_index=0) for i in range(2)
        ]
        self.assertEqual(self._name_errors(models), [])


if __name__ == "__main__":
    unittest.main()
