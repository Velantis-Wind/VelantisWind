# -*- coding: utf-8 -*-
"""#37: a change of language translates each text from its Spanish source, kept per widget and attribute (and per cell
and combo item), and not from the text already translated; the session memory gives back a source only when one alone
produced the text; and the special value text of the spin boxes is translated too."""
import os
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401

_CWD = os.getcwd()
_LANGS = ("en", "fr", "de", "es", "de", "en", "es")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _in(lang, text):
    i18n.set_language(lang)
    return i18n.tr_text(text)


class LiveSourceTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("es")
        self.addCleanup(i18n.set_language, "es")
        self.box = QtWidgets.QWidget()
        self.addCleanup(self.box.deleteLater)

    def switch(self, lang):
        i18n.set_language(lang)
        i18n.apply_i18n(self.box)

    def test_the_source_survives_successive_changes(self):
        # «Todas» and «Todos» are both «All» in English: going back from «All» alone could not tell them apart.
        label = QtWidgets.QLabel("Todas", self.box)
        group = QtWidgets.QGroupBox("Turbinas", self.box)
        for lang in _LANGS:
            self.switch(lang)
            self.assertEqual(label.text(), _in(lang, "Todas"), lang)
            self.assertEqual(group.title(), _in(lang, "Turbinas"), lang)
        self.assertEqual(label.text(), "Todas")

    def test_a_text_the_code_changes_is_the_new_source(self):
        label = QtWidgets.QLabel("Turbinas", self.box)
        self.switch("en")
        label.setText("Parque")
        for lang in ("fr", "de", "es"):
            self.switch(lang)
            self.assertEqual(label.text(), _in(lang, "Parque"), lang)

    def test_set_source_fixes_the_source(self):
        label = QtWidgets.QLabel(self.box)
        i18n.set_language("fr")
        i18n.set_source(label, "text", "Todos")
        self.assertEqual(label.text(), _in("fr", "Todos"))
        for lang in _LANGS:
            self.switch(lang)
            self.assertEqual(label.text(), _in(lang, "Todos"), lang)

    def test_a_text_composed_with_data_keeps_the_data(self):
        # Its owner translates the template and inserts the data after, and marks the widget.
        label = QtWidgets.QLabel(self.box)
        i18n.mark_translated(label)
        names = iter(["Parque Norte", "Parque Norte", "Parque Sur", "Parque Sur"])

        def compose():
            label.setText(f"{i18n.tr_text('Modelo')} 1: <b>{next(names)}</b>")

        for lang in ("en", "de", "fr", "es"):
            self.switch(lang)
            compose()
            self.assertTrue(label.text().endswith("Norte</b>" if lang in ("en", "de") else "Sur</b>"), label.text())

    def test_html_that_qt_normalises(self):
        browser = QtWidgets.QTextBrowser(self.box)
        browser.setHtml("<p>Turbinas</p>")
        for lang in _LANGS:
            self.switch(lang)
            self.assertIn(_in(lang, "Turbinas"), browser.toPlainText(), lang)

    def test_a_combo_refilled_and_a_table_repopulated(self):
        combo = QtWidgets.QComboBox(self.box)
        combo.addItems(["Todas", "Turbinas"])
        table = QtWidgets.QTableWidget(1, 1, self.box)
        table.setItem(0, 0, QtWidgets.QTableWidgetItem("Todas"))
        self.switch("en")
        combo.clear()
        combo.addItems(["Todos", "Parque"])
        table.setItem(0, 0, QtWidgets.QTableWidgetItem("Todos"))
        for lang in ("de", "fr", "es"):
            self.switch(lang)
            self.assertEqual([combo.itemText(i) for i in range(2)], [_in(lang, "Todos"), _in(lang, "Parque")], lang)
            self.assertEqual(table.item(0, 0).text(), _in(lang, "Todos"), lang)

    def test_the_session_memory_only_gives_back_an_unambiguous_source(self):
        # A widget made in another language gives back its Spanish source, when only one source produced its text.
        label = QtWidgets.QLabel(_in("en", "Parque"), self.box)
        for lang in ("de", "fr", "es"):
            self.switch(lang)
            self.assertEqual(label.text(), _in(lang, "Parque"), lang)
        # «Todos» and «Todas» both give «All»: the memory does not choose between them.
        self.assertEqual({_in("en", "Todos"), _in("en", "Todas")}, {"All"})
        self.assertEqual(i18n._source_of("All"), "All")
        # «Turbinas» and «Aerogeneradores» both give «Éoliennes» in French: the same.
        self.assertEqual({_in("fr", "Turbinas"), _in("fr", "Aerogeneradores")}, {"Éoliennes"})
        self.assertEqual(i18n._source_of("Éoliennes"), "Éoliennes")
        # A text composed through fragments, not a key of the tables, is not kept as a source.
        i18n.set_language("en")
        composed = i18n.translate_fragment("<p>Parque y Turbinas sin entrada propia</p>")
        self.assertEqual(i18n._source_of(composed), composed)
        self.assertTrue(all(src in i18n._STATE["sources"] for sources in i18n._PRODUCED.values() for src in sources))

    def test_special_value_text(self):
        spin = QtWidgets.QSpinBox(self.box)
        spin.setSpecialValueText("Automático")
        for lang in _LANGS:
            self.switch(lang)
            self.assertEqual(spin.specialValueText(), _in(lang, "Automático"), lang)


if __name__ == "__main__":
    unittest.main()
