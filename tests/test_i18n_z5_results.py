# -*- coding: utf-8 -*-
"""The texts of the AEP results, the comparator and the CSV in each language (zone Z5 of the translation plan).

The fixed texts of the report are translated when composed, data after the template, and kept from the second
translation of the report, which only translates by fragments; the user's model names stay as they are; and the
headers of the Energy CSV stay fixed in English in every language (decision of the user).
"""
import csv
import os
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind import results_dialog  # noqa: E402
from VelantisWind.ag_core.qgis_io import export  # noqa: E402
from tests.test_breakdown_consumers import v1_result, v2_result  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")
_fmt = results_dialog._fmt_mwh


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Model names that are also texts of the interface: they must come out as the user wrote them.
_NAMES = ("Bloqueo Norte", "Parque")


def v1_report_result():
    """A result of the previous schema with two models, the TI fallback, a plain note and a schema-1 selection."""
    r = v1_result()
    row = r["per_turbine_table"][0]
    r.update(ti_fallback_10pct=True, simulation_notes=["PropagateDownwind no admite bloqueo."],
             selection_user={"engine": "PropagateDownwind"},
             per_model_aep_MWh={_NAMES[0]: 91.0, _NAMES[1]: 80.0},
             per_model_aep_free_MWh={_NAMES[0]: 100.0, _NAMES[1]: 95.0},
             per_model_n_turbines={_NAMES[0]: 1, _NAMES[1]: 1},
             per_model_p_inst_MW={_NAMES[0]: 4.0, _NAMES[1]: 4.0},
             per_model_geom={_NAMES[0]: {"D": 120, "HH": 100}, _NAMES[1]: {"D": 150, "HH": 120}},
             per_turbine_table=[dict(row, model=_NAMES[0]), dict(row, id=2, model=_NAMES[1], aep_mwh=80.0,
                                                                aep_free_mwh=95.0)])
    return r


def exported(dlg):
    return dlg._wrap_report_document(dlg._build_full_report_html())


class _LanguageTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")

    def dialog(self, result, lang):
        i18n.set_language(lang)
        dlg = results_dialog.AEPResultsDialog(None, result)
        self.addCleanup(dlg.deleteLater)
        return dlg


class EnergyCsvHeadersTest(_LanguageTest):
    """The headers of the Energy CSV are fixed in English: they do not change with the language (decision 8)."""

    V2 = ["Turbine ID", "Turbine model", "X [m]", "Y [m]", "Rated power [MW]", "Net AEP [MWh/year]",
          "Free-flow AEP [MWh/year]", "Wake loss L_W [MWh/year]", "Turbulence impact Δ_T [MWh/year]",
          "Blockage impact Δ_B [MWh/year]", "Total loss [MWh/year]", "Ambient TI [-]", "Effective TI [-]", "diam",
          "hh", "aep_w_mwh", "aep_wt_mwh", "aep_wb_mwh", "l_wake_pct", "d_turb_pct", "d_blk_pct", "l_total_pct",
          "wake_states", "res_schema", "air_density_kg_m3", "hub_altitude_m", "Wake configuration", "Wake warnings"]
    V1 = ["Turbine ID", "Turbine model", "X [m]", "Y [m]", "Rated power [MW]", "Net AEP [MWh/year]",
          "Free-flow AEP [MWh/year]", "Wake losses [MWh/year]", "Blockage losses [MWh/year]",
          "TI/turbulence impact [MWh/year]", "loss_ti_mwh", "ti_eff"]

    def csv_contents(self, rows, result=None):
        path = os.path.join(_SETTINGS.name, "aep.csv")
        export.export_per_turbine_to_csv(rows, path, result)
        with open(path, encoding="utf-8-sig") as fh:
            return list(csv.reader(fh))

    def test_the_headers_do_not_change_in_any_language(self):
        r = v2_result()
        r["wake_config"] = {"identification": "Modelo predefinido: Parque Norte"}
        legacy = v1_result()
        for result in (r, legacy):
            for row in result["per_turbine_table"]:
                row["model"] = "Turbinas"
        for lang in _LANGS:
            i18n.set_language(lang)
            for result, metadata, expected in ((r, r, self.V2), (legacy, None, self.V1)):
                with self.subTest(lang=lang, schema=2 if metadata else 1):
                    header, *rows = self.csv_contents(result["per_turbine_table"], metadata)
                    self.assertEqual(header, expected)
                    model_column = header.index("Turbine model")
                    self.assertEqual([row[model_column] for row in rows],
                                     ["Turbinas"] * len(result["per_turbine_table"]))


class ReportTest(_LanguageTest):
    # The fixed texts of a schema-1 report, without the figures (their format is another step).
    EXPECTED_V1 = {
        "es": ["<title>Velantis Wind · Informe técnico AEP</title>",
               "Generado por Velantis Wind · Módulo Energía de QGIS · Flujo AEP basado en PyWake.",
               "Modelos / clusters de aerogeneradores", "1 aerogenerador(es)", "Altura de buje = ",
               "AEP neto del cluster: ", "% del AEP neto del parque", "Pérdida total (estelas/TI/bloqueo): ",
               "no se ha proporcionado un ráster de TI. El cálculo ha usado <b>TI = ",
               "frente al caso con solo estelas", "AEP bruto (flujo libre)", "PropagateDownwind no admite bloqueo."],
        "en": ["<title>Velantis Wind · AEP technical report</title>",
               "Generated by Velantis Wind · QGIS energy module · PyWake-based AEP workflow.",
               "Turbine models / clusters", "1 turbine(s)", "Hub height = ", "Net AEP of the cluster: ",
               "% of the wind farm net AEP", "Total loss (wakes/TI/blockage): ",
               "no TI raster has been provided. The calculation used a uniform <b>TI = ",
               "compared with the wakes-only case", "Gross AEP (free-stream)", "Blockage:", "Net capacity factor:",
               "PropagateDownwind does not support blockage.", "By turbine model",
               "This table mirrors the per-turbine summary visible in the interface."],
        "fr": ["<title>Velantis Wind · Rapport technique AEP</title>",
               "Généré avec Velantis Wind · Module Énergie de QGIS · Flux de calcul AEP basé sur PyWake.",
               "Modèles / clusters d’éoliennes", "1 éolienne(s)", "Hauteur de moyeu = ", "AEP net du cluster : ",
               "% de l’AEP net du parc", "Perte totale (sillages/TI/blocage) : ", "Avertissement TI ambiante :",
               "aucun raster de TI n’a été fourni. Le calcul a utilisé une <b>TI = ",
               "par rapport au cas avec sillages seuls", "AEP brut (écoulement libre)", "AEP net (en exploitation)",
               "Blocage :", "PropagateDownwind n’admet pas le blocage.", "Par modèle d’éolienne",
               "Ce tableau reprend le résumé par éolienne visible dans l’interface."],
        "de": ["<title>Velantis Wind · Technischer AEP-Bericht</title>",
               "Erstellt mit Velantis Wind · QGIS-Energiemodul · PyWake-basierter AEP-Workflow.",
               "Windturbinenmodelle / Cluster", "1 Windturbine(n)", "Nabenhöhe = ", "Netto-AEP des Clusters: ",
               "% der Netto-AEP des Windparks", "Gesamtverlust (Nachläufe/TI/Blockade): ",
               "Es wurde kein TI-Raster angegeben. Die Berechnung hat eine einheitliche <b>TI = ",
               "gegenüber dem Fall nur mit Nachläufen", "Brutto-AEP (freie Anströmung)", "Blockade:",
               "PropagateDownwind unterstützt keine Blockade.", "Nach Windturbinenmodell",
               "Diese Tabelle entspricht der in der Oberfläche sichtbaren Übersicht je Turbine."],
    }
    # Spanish left in the other languages, and English (or a typo) in the Spanish source.
    SPANISH = ["aerogenerador", "no se ha proporcionado", "Esta tabla", "no admite", "Generado por", "AEP bruto",
               "del cluster", "Diagnóstico", "Bloqueo:", "Modelo de"]
    NOT_IN_SPANISH = ["free-stream", "wake-only", "Hub =", "Hub [m]", "technical report", "Generated by", "fallback",
                      "wake/TI", "AEP neta", "raster "]

    def test_the_fixed_texts_of_a_schema_1_report(self):
        for lang in _LANGS:
            html = exported(self.dialog(v1_report_result(), lang))
            for text in self.EXPECTED_V1[lang]:
                with self.subTest(lang=lang, text=text):
                    self.assertIn(text, html)
            for text in (self.NOT_IN_SPANISH if lang == "es" else self.SPANISH):
                with self.subTest(lang=lang, absent=text):
                    self.assertNotIn(text, html)

    def test_the_sections_of_a_schema_2_report(self):
        sections = {"es": ("Por modelo de aerogenerador", "Por sector de viento"),
                    "en": ("By turbine model", "By wind sector"),
                    "fr": ("Par modèle d’éolienne", "Par secteur de vent"),
                    "de": ("Nach Windturbinenmodell", "Nach Windsektor")}
        for lang in _LANGS:
            html = exported(self.dialog(v2_result(), lang))
            for text in sections[lang]:
                with self.subTest(lang=lang, text=text):
                    self.assertIn(f"<h3>{text}</h3>", html)

    def test_the_user_model_names_stay_as_written(self):
        for lang in _LANGS:
            dlg = self.dialog(v1_report_result(), lang)
            html = exported(dlg)
            names = [dlg.table_models.item(row, 0).text() for row in range(dlg.table_models.rowCount())]
            with self.subTest(lang=lang):
                self.assertEqual(sorted(names), sorted(_NAMES))
                for name in _NAMES:
                    self.assertIn(f"<b>{name}</b>", html)
                self.assertNotIn("Blockage Norte", html)
                self.assertNotIn("Blockade Norte", html)


class WindowTest(_LanguageTest):
    TOTALS = {
        "es": "<b>Total sectores:</b> AEP bruto {g} MWh · AEP neto {n} MWh · pérdidas {l} MWh. Comparación con "
              "resumen: Δ neto = {d} MWh (OK).",
        "en": "<b>Sector totals:</b> Gross AEP {g} MWh · Net AEP {n} MWh · losses {l} MWh. Comparison with the "
              "summary: Δ net = {d} MWh (OK).",
        "fr": "<b>Total des secteurs :</b> AEP brut {g} MWh · AEP net {n} MWh · pertes {l} MWh. Comparaison avec le "
              "résumé : Δ net = {d} MWh (OK).",
        "de": "<b>Summe der Sektoren:</b> Brutto-AEP {g} MWh · Netto-AEP {n} MWh · Verluste {l} MWh. Vergleich mit "
              "der Übersicht: Δ netto = {d} MWh (OK).",
    }
    BALANCE = {
        "es": "Bruto: <b>{g} MWh</b> · Neto + pérdidas: <b>{b} MWh</b> · Δ = {d} MWh (OK)",
        "en": "Gross: <b>{g} MWh</b> · Net + losses: <b>{b} MWh</b> · Δ = {d} MWh (OK)",
        "fr": "Brut : <b>{g} MWh</b> · Net + pertes : <b>{b} MWh</b> · Δ = {d} MWh (OK)",
        "de": "Brutto: <b>{g} MWh</b> · Netto + Verluste: <b>{b} MWh</b> · Δ = {d} MWh (OK)",
    }
    CLOSE = {"es": "Cerrar", "en": "Close", "fr": "Fermer", "de": "Schließen"}

    def labels(self, dlg):
        return [w.text() for w in dlg.findChildren(QtWidgets.QLabel)]

    def test_the_sector_totals(self):
        # The sectors of the fixture: gross 140 + 160, net 150 + 119.6, the same net as the summary.
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self.dialog(v2_result(), lang)
                expected = self.TOTALS[lang].format(g=_fmt(300.0), n=_fmt(269.6), l=_fmt(30.4), d=_fmt(0.0))
                self.assertIn(expected, self.labels(dlg))

    def test_the_balance_of_a_schema_1_result(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self.dialog(v1_result(), lang)
                self.assertIn(self.BALANCE[lang].format(g=_fmt(100.0), b=_fmt(100.0), d=_fmt(0.0)),
                              self.labels(dlg))

    def test_the_headers(self):
        de = ["Modell", "D [m]", "Nabenhöhe [m]", "Anzahl Turbinen", "Installierte Leistung [MW]", "Brutto-AEP [MWh]",
              "Netto-AEP [MWh]", "Nachlaufverlust L_W [MWh]", "Turbulenzwirkung Δ_T [MWh]",
              "Blockadewirkung Δ_B [MWh]", "Gesamtverlust [MWh]", "Netto-Kapazitätsfaktor [%]",
              "AEP/MW [MWh/MW·Jahr]", "Nachlaufverlust L_W [%]"]
        dlg = self.dialog(v2_result(), "de")
        table = dlg.table_models
        self.assertEqual([table.horizontalHeaderItem(c).text() for c in range(table.columnCount())], de)
        for lang, column, text in (("es", 2, "Altura de buje [m]"), ("en", 2, "Hub height [m]"),
                                   ("en", 3, "No. of turbines")):
            with self.subTest(lang=lang, text=text):
                self.assertEqual(self.dialog(v2_result(), lang).table_models.horizontalHeaderItem(column).text(), text)
        for lang, column, text in (("en", 11, "Ambient TI"), ("fr", 4, "Puissance nominale [MW]"),
                                   ("de", 4, "Nennleistung [MW]")):
            with self.subTest(lang=lang, text=text):
                self.assertEqual(self.dialog(v2_result(), lang).table_turbines.horizontalHeaderItem(column).text(),
                                 text)
        for lang, text in (("es", "AEP bruto [MWh]"), ("en", "Gross AEP [MWh]")):
            with self.subTest(lang=lang, sector=text):
                self.assertEqual(self.dialog(v2_result(), lang).table_sector.horizontalHeaderItem(1).text(), text)

    def test_the_close_button_follows_the_plugin(self):
        a, b = v2_result(), v1_result()
        for lang in _LANGS:
            dlg = self.dialog(v2_result(), lang)
            comparator = results_dialog.ScenarioComparisonDialog(None, a, b, "A", "B")
            self.addCleanup(comparator.deleteLater)
            for window in (dlg, comparator):
                box = window.findChild(QtWidgets.QDialogButtonBox)
                with self.subTest(lang=lang, window=type(window).__name__):
                    self.assertEqual(box.button(QtWidgets.QDialogButtonBox.Close).text(), self.CLOSE[lang])


class ComparatorTest(_LanguageTest):
    def test_a_schema_2_configuration_uses_french_punctuation(self):
        r = v2_result()
        r["wake_config"] = {"executed": {"engine": {"class": "All2AllIterative"},
                                          "blockage": {"class": "SelfSimilarityDeficit2020"}}}
        i18n.set_language("fr")
        dlg = results_dialog.ScenarioComparisonDialog(None, r, v1_result(), "A", "B")
        self.addCleanup(dlg.deleteLater)
        html = results_dialog._fill_slots(dlg._user_texts, dlg._config_html())
        self.assertIn("<b>Moteur :</b> All2AllIterative", html)
        self.assertIn("<b>Modèle de blocage :</b> SelfSimilarityDeficit2020", html)

    def test_a_schema_1_configuration_by_its_labels(self):
        b = v1_result()
        b["selection_executed"] = {"engine": "All2AllIterative", "blockage": "SelfSimilarityDeficit2020"}
        labels = {"es": ("Motor:", "Modelo de bloqueo:"), "en": ("Engine:", "Blockage model:"),
                  "fr": ("Moteur :", "Modèle de blocage :"), "de": ("Rechenkern:", "Blockademodell:")}
        for lang in _LANGS:
            i18n.set_language(lang)
            dlg = results_dialog.ScenarioComparisonDialog(None, v2_result(), b, "A", "B")
            self.addCleanup(dlg.deleteLater)
            html = results_dialog._fill_slots(dlg._user_texts, dlg._config_html())
            with self.subTest(lang=lang):
                self.assertIn(f"<b>{labels[lang][0]}</b> All2AllIterative", html)
                self.assertIn(f"<b>{labels[lang][1]}</b> SelfSimilarityDeficit2020", html)
                self.assertNotIn("engine:", html)
                self.assertNotIn("blockage:", html)


if __name__ == "__main__":
    unittest.main()
