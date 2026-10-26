"""The report of the configuration of a result of the previous schema (#29), still read with its own fields."""
import unittest

from VelantisWind.ag_core.results.model_config_html import model_config_html


class ModelConfigHtmlTest(unittest.TestCase):
    def test_changed_physics_visible_and_escaped(self):
        html = model_config_html({
            'selection_user': {'blockage': 'SS2020'},
            'selection_requested': {'blockage': 'SelfSimilarityDeficit2020'},
            'selection_executed': {'blockage': 'None'},
            'simulation_degraded': True, 'simulation_degradation_label': '<sin bloqueo>',
        })
        self.assertIn('Selección del usuario', html)
        self.assertIn('Configuración finalmente ejecutada', html)
        self.assertIn('background:#fff3cd', html)
        self.assertIn('&lt;sin bloqueo&gt;', html)
        self.assertNotIn('<sin bloqueo>', html)

    def test_missing_execution_not_inferred_from_selection(self):
        html = model_config_html({'selection_user': {'blockage': 'SS2020'}})
        self.assertIn('No se ha registrado la configuración ejecutada', html)
        self.assertIn('No registrado', html)

    def test_empty_legacy_payload(self):
        self.assertEqual(model_config_html({}), '')


if __name__ == '__main__':
    unittest.main()
