import unittest
from unittest.mock import patch

from VelantisWind import i18n
from VelantisWind.ag_core.curve_text_translations import (
    SPACE_TOOLTIP, TRANSLATIONS, register_curve_text_translations,
)


class CurveTextTranslationsTest(unittest.TestCase):
    def test_space_tooltip_in_all_supported_languages(self):
        register_curve_text_translations()
        for language in ('es', 'en', 'fr', 'de'):
            with self.subTest(language=language), patch.object(i18n, 'current_language', return_value=language):
                expected = SPACE_TOOLTIP if language == 'es' else TRANSLATIONS[language][SPACE_TOOLTIP]
                self.assertEqual(i18n.tr_text(SPACE_TOOLTIP), expected)
                self.assertEqual(i18n.translate_html(SPACE_TOOLTIP), expected)
