import unittest
from unittest.mock import patch
from html import escape

from VelantisWind import i18n
from VelantisWind.ag_core.results.model_config_html import model_config_html, format_report_note
from VelantisWind.ag_core.log_text import log_text
from VelantisWind.ag_core.results.model_config_translations import (
    TRANSLATIONS, register_model_config_translations,
)


class ModelConfigTranslationsTest(unittest.TestCase):
    def setUp(self):
        register_model_config_translations()

    def test_every_new_string_has_a_complete_translation(self):
        for language, mapping in TRANSLATIONS.items():
            with self.subTest(language=language), patch.object(i18n, 'current_language', return_value=language):
                for source, expected in mapping.items():
                    self.assertEqual(i18n.tr_text(source), expected)

    def test_ui_and_export_html_keep_translated_status_and_model_names(self):
        cases = (
            ({'selection_user': {'blockage': 'SS2020'}}, 'No se ha registrado la configuración ejecutada.'),
            ({'selection_executed': {'blockage': 'SelfSimilarityDeficit2020'}}, 'Configuración ejecutada registrada.'),
            ({'selection_requested': {'blockage': 'SS2020'}, 'selection_executed': {'blockage': 'None'}},
             'Se han aplicado ajustes automáticos o valores de fábrica del modelo.'),
            ({'selection_user': {'blockage': 'SS2020'}, 'selection_executed': {'blockage': 'None'},
              'simulation_degraded': True, 'simulation_degradation_label': 'sin bloqueo'},
             'El cálculo ha utilizado una configuración alternativa.'),
        )
        for language in ('es', 'en', 'fr', 'de'):
            for result, status in cases:
                with self.subTest(language=language, status=status), patch.object(i18n, 'current_language', return_value=language):
                    report = model_config_html(result, i18n.tr_text)
                    exported = i18n.translate_html(report)
                    expected = status if language == 'es' else TRANSLATIONS[language][status]
                    self.assertIn(escape(expected), report)
                    self.assertIn(escape(expected), exported)
                    if language != 'es':
                        self.assertNotIn(status, report)
                        self.assertNotIn(status, exported)
                    if result.get('selection_user'):
                        self.assertIn('SS2020', report)

    def test_dynamic_blockage_name_is_preserved_and_escaped(self):
        result = {'selection_executed': {'blockage': 'VortexDipole'},
                  'simulation_degraded': True, 'simulation_degradation_label': 'bloqueo alternativo: <VortexDipole>'}
        for language in ('en', 'fr', 'de'):
            with self.subTest(language=language), patch.object(i18n, 'current_language', return_value=language):
                html = model_config_html(result, i18n.tr_text)
                self.assertIn('&lt;VortexDipole&gt;', html)
                self.assertNotIn('<VortexDipole>', html)
                self.assertNotIn('bloqueo alternativo:', html)

    def test_dynamic_notes_translate_templates_and_keep_error_details(self):
        error = "AssertionError: Invalid keyword argument(s): turbulence_model"
        note = log_text("Intento fallido '{attempt}': {error}",
                        attempt=log_text('sin bloqueo'), error=error)
        template = ("Sustitución del modelo de bloqueo: no se pudo ejecutar la configuración con {requested}. "
                    "Se ha utilizado {executed}; consulta los errores de los intentos anteriores.")
        substitution = log_text(template, requested='SS2020', executed='VortexDipole')
        for language in ('es', 'en', 'fr', 'de'):
            with self.subTest(language=language), patch.object(i18n, 'current_language', return_value=language):
                result = format_report_note(note, i18n.tr_text)
                self.assertIn(error, result)
                expected = 'sin bloqueo' if language == 'es' else TRANSLATIONS[language]['sin bloqueo']
                self.assertIn(expected, result)
                result = format_report_note(substitution, i18n.tr_text)
                self.assertIn('SS2020', result)
                self.assertIn('VortexDipole', result)
                if language != 'es':
                    self.assertNotIn('Sustitución del modelo de bloqueo:', result)
