# -*- coding: utf-8 -*-
"""The turbine dialog in the four languages: its texts, the catalogue (whose proper names do not go through the
translator and whose proposed name carries no quality label) and the errors of the turbine builders, shown from their
Spanish templates."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine, turbine_ui  # noqa: E402
from VelantisWind.ag_core.log_text import shown  # noqa: E402
from VelantisWind.ag_core.turbines import factory, library  # noqa: E402
from VelantisWind.ag_core.turbines.wtg import WtgFormatError, load_wtg  # noqa: E402
from tests.test_wtg import TABLES, document, table  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _by_lang(*values):
    return dict(zip(_LANGS, values))


def _candidate(candidate_id):
    return next(c for c in library.load_builtin_candidates() if c["candidate_id"] == candidate_id)


class _LanguageTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")

    def dialog(self, lang):
        i18n.set_language(lang)
        dialog = turbine_ui.CustomTurbineDialog()
        self.addCleanup(dialog.deleteLater)
        return dialog


def _label(widget):
    return widget.parentWidget().layout().labelForField(widget).text()


class TurbineDialogTextsTest(_LanguageTest):
    EXPECTED = {
        "title": _by_lang("Definir turbina", "Define turbine", "Définir une éolienne", "Windturbine definieren"),
        "tab": _by_lang("Manual", "Manual", "Manuel", "Manuell"),
        "name": _by_lang("Nombre:", "Name:", "Nom :", "Name:"),
        "ws": _by_lang("Velocidad del viento (m/s):", "Wind speed (m/s):", "Vitesse du vent (m/s) :",
                       "Windgeschwindigkeit (m/s):"),
        "ct": _by_lang("CT (0–1,2):", "CT (0–1.2):", "CT (0–1,2) :", "CT (0–1,2):"),
        "delimiter": _by_lang("Delimitador:", "Delimiter:", "Séparateur :", "Trennzeichen:"),
        "ws_col": _by_lang("Columna ws (contando desde 0):", "ws column (0-based):", "Colonne ws (à partir de 0) :",
                           "Spalte ws (ab 0 gezählt):"),
        "ct_col": _by_lang("Incluir columna CT", "Include CT column", "Inclure la colonne CT", "CT-Spalte einbeziehen"),
        "delimiters": _by_lang(
            ["Tabulación (\\t)", "Coma (,)", "Punto y coma (;)", "Espacio ( )"],
            ["Tab (\\t)", "Comma (,)", "Semicolon (;)", "Space ( )"],
            ["Tabulation (\\t)", "Virgule (,)", "Point-virgule (;)", "Espace ( )"],
            ["Tabulator (\\t)", "Komma (,)", "Semikolon (;)", "Leerzeichen ( )"],
        ),
        "placeholders": _by_lang(
            ["Ej.: 3 4 5 6 7 8 9 10 11 12 13 14", "Potencia en kW, misma longitud que ws", "(opcional)"],
            ["E.g. 3 4 5 6 7 8 9 10 11 12 13 14", "Power in kW, same length as ws", "(optional)"],
            ["Ex. : 3 4 5 6 7 8 9 10 11 12 13 14", "Puissance en kW, même longueur que ws", "(facultatif)"],
            ["z. B. 3 4 5 6 7 8 9 10 11 12 13 14", "Leistung in kW, gleiche Länge wie ws", "(optional)"],
        ),
        "default_names": _by_lang(
            ["Turbina personalizada", "Turbina personalizada (CSV)"],
            ["Custom turbine", "Custom turbine (CSV)"],
            ["Éolienne personnalisée", "Éolienne personnalisée (CSV)"],
            ["Benutzerdefinierte Windturbine", "Benutzerdefinierte Windturbine (CSV)"],
        ),
        "build_buttons": _by_lang(
            ["Crear turbina (Manual)", "Crear turbina (TXT/CSV)"],
            ["Create turbine (Manual)", "Create turbine (TXT/CSV)"],
            ["Créer l’éolienne (Manuel)", "Créer l’éolienne (TXT/CSV)"],
            ["Windturbine erstellen (Manuell)", "Windturbine erstellen (TXT/CSV)"],
        ),
    }

    def test_texts_in_each_language(self):
        for lang in _LANGS:
            d = self.dialog(lang)
            tabs = d.findChild(QtWidgets.QTabWidget)
            shown_texts = {
                "title": d.windowTitle(),
                "tab": tabs.tabText(0),
                "name": _label(d.ed_name_m),
                "ws": _label(d.te_ws),
                "ct": _label(d.te_ct),
                "delimiter": _label(d.cb_delim),
                "ws_col": _label(d.sp_ws_col),
                "ct_col": d.chk_ct_col.text(),
                "delimiters": [d.cb_delim.itemText(i) for i in range(d.cb_delim.count())],
                "placeholders": [w.placeholderText() for w in (d.te_ws, d.te_power, d.te_ct)],
                "default_names": [d.ed_name_m.text(), d.ed_name_c.text()],
                "build_buttons": [b.text() for b in d.findChildren(QtWidgets.QPushButton)
                                  if b.text() in self.EXPECTED["build_buttons"][lang]],
            }
            for key, expected in self.EXPECTED.items():
                with self.subTest(lang=lang, key=key):
                    value = shown_texts[key]
                    if key == "build_buttons":
                        value = sorted(value)
                        expected = sorted(expected[lang])
                    else:
                        expected = expected[lang]
                    self.assertEqual(value, expected)

    def test_the_changed_inputs_name_the_labels_and_the_tab(self):
        expected = _by_lang(
            "En la pestaña Manual has cambiado «Velocidad del viento (m/s)», pero la turbina creada es la de la pestaña "
            "TXT/CSV.",
            "In the Manual tab you have changed “Wind speed (m/s)”, but the turbine created is the one from the TXT/CSV "
            "tab.",
            "Dans l’onglet Manuel, vous avez modifié « Vitesse du vent (m/s) », mais l’éolienne créée est celle de "
            "l’onglet TXT/CSV.",
            "Im Reiter Manuell haben Sie „Windgeschwindigkeit (m/s)“ geändert, aber die erstellte Windturbine stammt aus "
            "dem Reiter TXT/CSV.",
        )
        for lang in _LANGS:
            d = self.dialog(lang)
            d._result_data = {"mode": "csv"}
            text = d._changed_inputs_text([("manual", "Manual", ["Velocidad del viento (m/s):"])])
            with self.subTest(lang=lang):
                self.assertTrue(text.startswith(expected[lang] + " "), text)

    def test_file_filter_keeps_its_patterns_in_each_language(self):
        endings = _by_lang("Todos", "All", "Tous", "Alle")
        for lang in _LANGS:
            d = self.dialog(lang)
            with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=("", "")) as browse:
                d._browse_file()
            with self.subTest(lang=lang):
                self.assertEqual(browse.call_args.args[3], f"TXT/CSV (*.txt *.csv);;{endings[lang]} (*.*)")

    def test_success_message_uses_the_translated_text(self):
        expected = _by_lang(
            "Turbina creada (manual). Pulsa Aceptar para usarla.",
            "Turbine created (manual). Press OK to use it.",
            "Éolienne créée (manuel). Cliquez sur OK pour l’utiliser.",
            "Windturbine erstellt (manuell). Klicken Sie auf OK, um sie zu verwenden.",
        )
        for lang in _LANGS:
            d = self.dialog(lang)
            d.te_ws.setPlainText("3 8")
            d.te_power.setPlainText("100 1000")
            d.te_ct.setPlainText("0.8 0.8")
            with mock.patch.object(turbine_ui, "build_wt_from_manual", return_value=object()), \
                    mock.patch.object(QtWidgets.QMessageBox, "information") as box:
                d._on_build_manual()
            with self.subTest(lang=lang):
                self.assertEqual(box.call_args.args[2], expected[lang])


class TurbineCatalogueTest(_LanguageTest):
    SPEC_PHRASE = _by_lang("aproximación por ficha pública", "approximation from public specifications",
                           "approximation d’après la fiche publique", "Näherung nach öffentlichem Datenblatt")
    DATASHEET = _by_lang("ficha técnica pública", "public datasheet", "fiche technique publique",
                         "öffentliches Datenblatt")
    REFERENCE = _by_lang("aerogenerador de referencia", "reference turbine", "éolienne de référence",
                         "Referenzwindturbine")
    GENERIC = _by_lang("Genérica terrestre", "Generic onshore", "Éolienne terrestre générique",
                       "Generische Onshore-Windturbine")
    GENERIC_SOURCE = _by_lang("Modelo paramétrico de cribado de Velantis", "Velantis parametric screening model",
                              "Modèle paramétrique de présélection de Velantis",
                              "Parametrisches Screening-Modell von Velantis")
    GENERIC_NOTE = _by_lang(
        "Aproximación paramétrica físicamente plausible a ρ=1,225 kg/m³, construida con potencia nominal, diámetro y "
        "control genérico de Cp/CT. No es una curva OEM ni certificada.",
        "Physically plausible parametric approximation at ρ=1.225 kg/m³, built from the rated power, the diameter and "
        "a generic Cp/CT control. It is not an OEM or certified curve.",
        "Approximation paramétrique physiquement plausible à ρ=1,225 kg/m³, construite à partir de la puissance "
        "nominale, du diamètre et d’un contrôle générique de Cp/CT. Ce n’est ni une courbe OEM ni une courbe certifiée.",
        "Physikalisch plausible parametrische Näherung bei ρ=1,225 kg/m³, aufgebaut aus Nennleistung, Durchmesser und "
        "einer generischen Cp/CT-Regelung. Keine OEM- oder zertifizierte Kurve.",
    )

    def select(self, dialog, candidate_id):
        combo = dialog.cb_generic_preset
        index = next(i for i in range(combo.count())
                     if isinstance(combo.itemData(i), dict) and combo.itemData(i)["candidate_id"] == candidate_id)
        combo.setCurrentIndex(index)
        return combo.itemText(index)

    def test_a_spec_based_model_keeps_its_name_and_translates_only_its_phrases(self):
        data = next(c for c in library.load_builtin_candidates()
                    if c["curve_quality"] == "spec_based_approximation")
        head = data["name"].rsplit(" · ", 1)[0]
        for lang in _LANGS:
            d = self.dialog(lang)
            item = self.select(d, data["candidate_id"])
            with self.subTest(lang=lang):
                name = f"{head} · {self.SPEC_PHRASE[lang]}"
                # The proposed name is the catalogue's, without a quality label: the quality is shown apart.
                self.assertEqual(d.ed_name_m.text(), head)
                self.assertTrue(item.endswith("] " + name), item)
                source = data["source_name"].replace("ficha técnica pública", self.DATASHEET[lang])
                self.assertIn(source, d.lbl_curve_provenance.text())
                self.assertEqual(d.lbl_curve_provenance.toolTip(), data["source_url"])

    def test_a_public_reference_keeps_its_name_in_each_language(self):
        for lang in _LANGS:
            d = self.dialog(lang)
            item = self.select(d, "ref_iea_10mw_198")
            with self.subTest(lang=lang):
                self.assertEqual(d.ed_name_m.text(), "IEA 10 MW · D198 m")
                self.assertIn(self.REFERENCE[lang], item)

    def test_a_generic_class_has_its_source_and_note_translated(self):
        for lang in _LANGS:
            d = self.dialog(lang)
            item = self.select(d, "gen_onshore_1p5_77")
            with self.subTest(lang=lang):
                self.assertEqual(d.ed_name_m.text(), _candidate("gen_onshore_1p5_77")["name"])
                self.assertIn(self.GENERIC[lang], item)
                self.assertIn(self.GENERIC_SOURCE[lang], d.lbl_curve_provenance.text())
                self.assertEqual(d.lbl_curve_provenance.toolTip(), self.GENERIC_NOTE[lang])

    def test_catalogue_data_survives_translation_and_building(self):
        data = dict(_candidate("gen_onshore_1p5_77"), name="Parque · Turbinas", category="reference",
                    source_name="Plantilla: Norte", source_url="/tmp/modelo/Parque.csv",
                    curve_quality="public_reference")
        for lang in _LANGS:
            with mock.patch.object(turbine_ui, "_catalogue_presets", return_value=[data]):
                d = self.dialog(lang)
            self.select(d, data["candidate_id"])
            before = (d.cb_generic_preset.currentText(), d.lbl_curve_provenance.text(),
                      d.lbl_curve_provenance.toolTip())
            i18n.apply_i18n(d)
            with self.subTest(lang=lang):
                self.assertIn(data["name"], before[0])
                self.assertIn(data["source_name"], before[1])
                self.assertEqual(before, (d.cb_generic_preset.currentText(), d.lbl_curve_provenance.text(),
                                          d.lbl_curve_provenance.toolTip()))
                with mock.patch.object(turbine_ui, "build_wt_from_manual", return_value=object()) as build, \
                        mock.patch.object(QtWidgets.QMessageBox, "information"):
                    d._on_build_manual()
                self.assertEqual(build.call_args.args[0], data["name"])
                self.assertEqual(d.result_data()["name"], data["name"])


class TurbineErrorsTest(_LanguageTest):
    def build_manual(self, lang, ws, power):
        d = self.dialog(lang)
        d.te_ws.setPlainText(ws)
        d.te_power.setPlainText(power)
        with mock.patch.object(turbine_ui.QtWidgets.QMessageBox, "critical") as critical:
            d._on_build_manual()
        title, text = critical.call_args[0][1:3]
        return title, text

    def test_lists_of_different_length(self):
        expected = _by_lang(
            ("Error creando turbina", "Listas `ws` y `power_kw` deben tener la misma longitud y no estar vacías."),
            ("Error creating turbine", "The `ws` and `power_kw` lists must have the same length and must not be empty."),
            ("Erreur lors de la création de l’éolienne",
             "Les listes `ws` et `power_kw` doivent avoir la même longueur et ne pas être vides."),
            ("Fehler beim Erstellen der Windturbine",
             "Die Listen `ws` und `power_kw` müssen gleich lang sein und dürfen nicht leer sein."),
        )
        for lang in _LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(self.build_manual(lang, "3 8 15", "100 1400"), expected[lang])

    def test_a_value_that_is_not_a_number(self):
        expected = _by_lang("«a» no es un número.", "“a” is not a number.", "« a » n’est pas un nombre.",
                            "„a“ ist keine Zahl.")
        for lang in _LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(self.build_manual(lang, "3 a 15", "100 1400 3000")[1], expected[lang])

    def check(self, exc, expected):
        self.assertTrue(getattr(exc, "template_item", None), exc)
        for lang in _LANGS:
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                self.assertEqual(shown(exc, i18n.tr_text), expected[lang])

    def test_library_errors(self):
        path = os.path.join(_SETTINGS.name, "missing.csv")
        with self.assertRaises(FileNotFoundError) as ctx:
            library.load_candidate_curve({"curve_path": path})
        self.check(ctx.exception, _by_lang(
            f"No se encuentra la curva de la turbina: {path}", f"The turbine curve was not found: {path}",
            f"La courbe de l’éolienne est introuvable : {path}", f"Die Kurve der Windturbine wurde nicht gefunden: {path}",
        ))

    def test_builder_and_factory_errors(self):
        with self.assertRaises(TypeError) as ctx:
            turbine.build_wt_from_curve_table(object())
        self.check(ctx.exception, _by_lang(
            "Se esperaba un TurbineCurveTable y se recibió object.", "A TurbineCurveTable was expected and object was received.",
            "Un TurbineCurveTable était attendu et object a été reçu.", "Erwartet wurde eine TurbineCurveTable, erhalten wurde object.",
        ))
        with self.assertRaises(ValueError) as ctx:
            factory._explicit_geometry_value({}, {"diameter": "x"}, ("diameter",), "M")
        self.check(ctx.exception, _by_lang("M: diameter no es numérico.", "M: diameter is not numeric.",
                                           "M : diameter n’est pas numérique.", "M: diameter ist nicht numerisch."))

    def test_a_wtg_table_without_mode(self):
        path = os.path.join(_SETTINGS.name, "modes.wtg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(document(tables=table(1.0, *TABLES[1.0], comment="Noise Mode 0") + table(1.1, *TABLES[1.1])))
        with self.assertRaises(WtgFormatError) as ctx:
            load_wtg(path)
        for lang, words in _by_lang("(Noise Mode 0 / sin modo)", "(Noise Mode 0 / no mode)", "(Noise Mode 0 / sans mode)",
                                    "(Noise Mode 0 / ohne Modus)").items():
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                self.assertIn(words, shown(ctx.exception, i18n.tr_text))


if __name__ == "__main__":
    unittest.main()
