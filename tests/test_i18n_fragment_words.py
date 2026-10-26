# -*- coding: utf-8 -*-
"""The fragment translation does not deform text that is already right: an entry that starts or ends with a word only
replaces whole words, the short words that are also words of another language of the plugin are not fragments, and the
help texts of Noise, written in each language, do not go through the translator."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401
from VelantisWind import noise_page  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Texts the sweeps found deformed, already in their language. A line break sends them to the fragment translation.
_RIGHT = {
    "de": ["Die Berechnung wurde gestartet.", "Die Rezeptoren liegen außerhalb des Radius.", "Die Datei wurde geöffnet.",
           "Abstand zwischen an Quelle und Rezeptor", "Er arbeitet mit Oktavbändern und Agr an. Er benötigt mehr.",
           "Die Zeit wird gestartet "],
    "en": ["Help · Attenuation, ground and land use", "The wind-turbine layer was not found.",
           "In an area with sound below the limit and the background", "Compare with the real turbine.",
           "Loss: {loss} MWh, net: {net} MWh", "Hour"],
    "fr": ["Heures par an et par jour.", "Type"],
}


class FragmentWordsTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")

    def test_text_already_in_its_language_comes_out_intact(self):
        for lang, texts in _RIGHT.items():
            i18n.set_language(lang)
            for text in texts:
                for s in (text + "\n", "<p>" + text + "</p>\n", "1.\n" + text + " \n"):
                    with self.subTest(lang=lang, text=s):
                        self.assertEqual(i18n._fragment_impl(s, lang), s)

    def test_an_entry_does_not_take_part_of_a_longer_word(self):
        self.assertEqual(i18n._apply_fragments("gestartet und", [("et ", "und ")]), "gestartet und")
        self.assertEqual(i18n._apply_fragments("limit mit", [("mit ", "avec ")]), "limit mit")
        self.assertEqual(i18n._apply_fragments("A et B", [(" et ", " y ")]), "A y B")
        self.assertEqual(i18n._apply_fragments("Ver modelo: x", [("modelo:", "model:")]), "Ver model: x")

    def test_a_label_that_matched_inside_a_word_has_its_own_entry(self):
        # «Pérdidas por estela» used to match inside «Pérdidas por estelas» (results_dialog.py) and give «Wake lossess».
        for lang, expected in (("en", "Wake losses"), ("fr", "Pertes de sillage"), ("de", "Nachlaufverluste")):
            i18n.set_language(lang)
            self.assertEqual(i18n.translate_fragment("Pérdidas por estelas"), expected)

    def test_a_placeholder_of_a_template_is_left_as_it_is(self):
        # A fragment changing the name inside {…} makes the .format that fills it fail (KeyError).
        pairs = [("model", "modèle"), ("defecto", "défaut"), ("{n} turbina(s)", "{n} éolienne(s)")]
        self.assertEqual(i18n._apply_fragments("Ver {model} y model", pairs), "Ver {model} y modèle")
        self.assertEqual(i18n._apply_fragments("Valor {defecto:.1f} por defecto", pairs), "Valor {defecto:.1f} por défaut")
        self.assertEqual(i18n._apply_fragments("Hay {n} turbina(s)", pairs), "Hay {n} éolienne(s)")
        # Braces that are not a replacement field are text and are translated.
        self.assertEqual(i18n._apply_fragments("Texto { model } y {x}", pairs), "Texto { modèle } y {x}")
        self.assertEqual(i18n._apply_fragments('p { content: "model" }', pairs), 'p { content: "modèle" }')
        self.assertEqual(i18n._apply_fragments("Valor {model:{ancho}} y model", pairs), "Valor {model:{ancho}} y modèle")
        self.assertEqual(i18n._apply_fragments("{{model}} y {x}", pairs), "{{modèle}} y {x}")
        self.assertEqual(i18n._apply_fragments("{{{model}}} y model", pairs), "{{{model}}} y modèle")
        self.assertEqual(i18n._apply_fragments("{ model :{width}} y model", pairs), "{ modèle :{width}} y modèle")
        self.assertEqual(i18n._apply_fragments("A {model} y model", [("model} y", "modèle} et")]), "A {model} y model")
        self.assertEqual(i18n._apply_fragments("{model[}]} y model", pairs), "{model[}]} y modèle")
        # Not a template that str.format can read (a lone brace): nothing is held back.
        self.assertEqual(i18n._apply_fragments("Abre { y {model}", pairs), "Abre { y {modèle}")
        source = "No se encontró el modelo {modelo} ni {default}.\n"
        for lang in ("en", "fr", "de"):
            i18n.set_language(lang)
            text = i18n._fragment_impl(source, lang)
            with self.subTest(lang=lang):
                self.assertNotEqual(text, source)
                self.assertIn("{modelo}", text)
                self.assertIn("{default}", text)
                filled = text.format(modelo="Alfa", default="Beta")
                self.assertEqual((filled.count("Alfa"), filled.count("Beta")), (1, 1))

    def test_final_cleanup_preserves_template_fields_in_public_translators(self):
        cases = (
            ("No se pudo abrir {capa}.", {"capa": "Parque"}),
            ("No se pudo abrir {capa[fuente]!s:>{margen}}.",
             {"capa": {"fuente": "Parque"}, "margen": 10}),
        )
        for lang in ("en", "fr", "de"):
            i18n.set_language(lang)
            for translate in (i18n.tr_text, i18n.translate_fragment):
                for source, values in cases:
                    with self.subTest(lang=lang, translator=translate.__name__, source=source):
                        text = translate(source)
                        self.assertIn(source[source.index("{"):source.rindex("}") + 1], text)
                        self.assertIn("Parque", text.format(**values))
        # Visible words still receive the same last-resort cleanup.
        self.assertEqual(i18n._final_language_cleanup("capa {capa}", "en"), "layer {capa}")

    def test_the_spanish_sun_is_not_the_ground_in_german(self):
        i18n.set_language("de")
        self.assertNotIn("Boden", i18n._fragment_impl("Altura del sol sobre el horizonte\n", "de"))

    def test_noise_help_is_shown_as_written(self):
        page = mock.Mock()
        page._noise_help_text = lambda key: noise_page.NoisePage._noise_help_text(page, key)
        for lang in ("es", "en", "fr", "de"):
            i18n.set_language(lang)
            for key in ("sources", "groups", "receivers", "map", "engine", "ground", "terrain", "atmos", "acoustic"):
                title, body = page._noise_help_text(key)
                with self.subTest(lang=lang, key=key), mock.patch.object(noise_page.QtWidgets, "QMessageBox") as box:
                    noise_page.NoisePage._show_noise_help(page, key)
                    box.return_value.setWindowTitle.assert_called_once_with(title)
                    box.return_value.setText.assert_called_once_with(body.strip())


if __name__ == "__main__":
    unittest.main()
