# -*- coding: utf-8 -*-
import unittest

from VelantisWind import i18n, i18n_de, i18n_fr


class GermanPolishTest(unittest.TestCase):
    def test_whole_words_are_replaced(self):
        self.assertEqual(i18n_de._de_final_polish_value("the model and the source"), "the Modell and the Quelle")
        self.assertEqual(i18n_de._de_final_polish_value("Layer de"), "Layer")

    def test_german_compounds_are_kept(self):
        for text in ("Turbinenmodell", "Nachlaufmodelle", "Windressource", "validiert", "Berechnungsmethodik", "Layer der"):
            with self.subTest(text=text):
                self.assertEqual(i18n_de._de_final_polish_value(text), text)

    def test_published_values_have_no_broken_compounds(self):
        values = list(i18n_de.TO_DE.values()) + list(i18n_de.FRAGMENT_TO_DE.values())
        for broken in ("Modelll", "resQuelle", "ResQuelle", "gültigiert", "Methodeik", "Layerr "):
            with self.subTest(broken=broken):
                self.assertFalse([v for v in values if isinstance(v, str) and broken in v])


class FrenchPolishTest(unittest.TestCase):
    def test_corrected_text_is_not_corrected_again(self):
        self.assertEqual(i18n_fr._fr_final_polish_value("Méthode utilisée :"), "Méthode utilisée :")
        self.assertEqual(i18n_fr._fr_final_polish_value("Méthode utilisé:"), "Méthode utilisée :")

    def test_plurals_are_still_corrected(self):
        self.assertEqual(i18n_fr._fr_final_polish_value("des layouts"), "des implantations")

    def test_published_values_have_no_repeated_correction(self):
        values = list(i18n_fr.TO_FR.values()) + list(i18n_fr.FRAGMENT_TO_FR.values())
        self.assertFalse([v for v in values if isinstance(v, str) and "utiliséee" in v])


class RuntimeCleanupTest(unittest.TestCase):
    def test_english_words_are_kept(self):
        for text in ("Net capacity factor", "If none is provided", "canonical value", "zoneinfo error", "non-standard model"):
            with self.subTest(text=text):
                self.assertEqual(i18n._final_language_cleanup(text, "en"), text)
        self.assertEqual(i18n._final_language_cleanup("zoneinfo", "fr"), "zoneinfo")

    def test_leftover_words_are_still_replaced(self):
        self.assertEqual(i18n._final_language_cleanup("la capa sí", "en"), "la layer yes")
        self.assertEqual(i18n._final_language_cleanup("Turbinen contribuyentes", "de"), "Turbinen beitragend")
        self.assertEqual(i18n._final_language_cleanup("DEM/DSM-Raster", "de"), "DGM/DOM-Raster")


if __name__ == "__main__":
    unittest.main()
