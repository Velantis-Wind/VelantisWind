# -*- coding: utf-8 -*-
"""Noise speaks the language of the plugin (#37): the page, the messages of the calculation and the status box after it
come out whole in each language, with the names of the user's layers and groups inside them as they are."""
import os
import json
import re
import string
import tempfile
import unittest
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsProject, QgsVectorLayer  # noqa: E402

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401
from VelantisWind import noise_page  # noqa: E402
from VelantisWind.noise_core import dialog_controller, result_status, task_controller, ui_feedback, validation  # noqa: E402
from VelantisWind.noise_core.acoustics.curves import evaluate_acoustic_curve  # noqa: E402
from VelantisWind.noise_core.domain import NoiseRunConfig  # noqa: E402
from VelantisWind.noise_core.noise_common import validate_octave_spectrum  # noqa: E402
from VelantisWind.noise_core.noise_spectrum import load_spectrum_from_csv  # noqa: E402
from VelantisWind.noise_core.raster.task import NoiseGridTask  # noqa: E402
from VelantisWind.noise_core.tasks.noise_task import NoiseCalculationTask  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")
_PAIRS = json.loads((Path(__file__).resolve().parent / "data/i18n_z7_pares.json").read_text(encoding="utf-8"))


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _layer(name):
    return SimpleNamespace(name=lambda: name)


# A result with names that are also texts of the interface: they must come out as they are.
_RESULT = {
    "acoustic_scenario": {"mode": "fixed", "effective_models": [{"name": "Parque Norte", "lwa_effective": 104.0}]},
    "result_layer": _layer("Noise · Receivers"),
    "uncovered_layer": _layer("Noise · Receivers outside radius"),
    "n_uncovered_receivers": 2,
    "receiver_type_counts": {"vivienda": 3},
    "n_receivers": 5,
    "n_receivers_with_sources": 4,
    "n_receivers_exceeding_limit": 1,
    "max_noise_dba": 46.5,
    "alpha_db_per_m": 0.005,
    "ground_factor_g": 0.5,
    "dem_used": False,
}

_STATUS = {
    "es": ["Resultado acústico:",
           "• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con LwA fijo por grupo fuente acústico.",
           "• Escenario acústico efectivo por grupo fuente:",
           "   - Parque Norte: LwA efectivo = 104.00 dB(A)",
           "• Capa de salida principal: Noise · Receivers",
           "• Capa GIS de receptores fuera de radio creada: Noise · Receivers outside radius (2 receptor(es)).",
           "• Receptores por categoría: vivienda=3",
           "• Receptores calculados: 5",
           "• Receptores con al menos una turbina dentro del radio: 4",
           "• Receptores que superan el límite: 1 / 5",
           "• Nivel máximo calculado: 46.50 dB(A)",
           "• α usado: 0.0050 dB/m",
           "• G usado: 0.50",
           "• Suelo efectivo: modo global, G=0.50 aplicado en todos los trayectos.",
           "• Sin MDT/DSM: el cálculo usa coordenadas planas con alturas relativas de fuente/receptor."],
    "en": ["Acoustic result:",
           "• Method used: wind source-receiver model (Adiv + Aatm + Aground) with fixed LwA by acoustic source group.",
           "• Effective acoustic scenario by source group:",
           "   - Parque Norte: effective LwA = 104.00 dB(A)",
           "• Main output layer: Noise · Receivers",
           "• GIS layer of receivers outside the radius created: Noise · Receivers outside radius (2 receiver(s)).",
           "• Receivers by category: vivienda=3",
           "• Calculated receivers: 5",
           "• Receivers with at least one turbine inside the radius: 4",
           "• Receivers exceeding the limit: 1 / 5",
           "• Maximum calculated level: 46.50 dB(A)",
           "• α used: 0.0050 dB/m",
           "• G used: 0.50",
           "• Effective ground: global mode, G=0.50 applied on all paths.",
           "• No DEM/DSM: the calculation uses flat coordinates with relative source/receiver heights."],
    "fr": ["Résultat acoustique :",
           "• Méthode utilisée : modèle éolien source-récepteur (Adiv + Aatm + Aground) avec LwA fixe par groupe de sources "
           "acoustiques.",
           "• Scénario acoustique effectif par groupe de sources :",
           "   - Parque Norte : LwA effectif = 104.00 dB(A)",
           "• Couche de sortie principale : Noise · Receivers",
           "• Couche SIG des récepteurs hors rayon créée : Noise · Receivers outside radius (2 récepteur(s)).",
           "• Récepteurs par catégorie : vivienda=3",
           "• Récepteurs calculés : 5",
           "• Récepteurs avec au moins une éolienne dans le rayon : 4",
           "• Récepteurs dépassant la limite : 1 / 5",
           "• Niveau maximal calculé : 46.50 dB(A)",
           "• α utilisé : 0.0050 dB/m",
           "• G utilisé : 0.50",
           "• Sol effectif : mode global, G=0.50 appliqué sur tous les trajets.",
           "• Sans MNT/MNS : le calcul utilise des coordonnées planes avec des hauteurs relatives source/récepteur."],
    "de": ["Schallergebnis:",
           "• Verwendete Methode: Windenergie-Quelle-Rezeptor-Modell (Adiv + Aatm + Aground) mit festem LwA je akustischer "
           "Quellgruppe.",
           "• Effektives akustisches Szenario je Quellgruppe:",
           "   - Parque Norte: effektiver LwA = 104.00 dB(A)",
           "• Haupt-Ausgabe-Layer: Noise · Receivers",
           "• GIS-Layer der Rezeptoren außerhalb des Radius erstellt: Noise · Receivers outside radius (2 Rezeptor(en)).",
           "• Rezeptoren nach Kategorie: vivienda=3",
           "• Berechnete Rezeptoren: 5",
           "• Rezeptoren mit mindestens einer Windturbine innerhalb des Radius: 4",
           "• Rezeptoren über dem Grenzwert: 1 / 5",
           "• Maximaler berechneter Pegel: 46.50 dB(A)",
           "• Verwendetes α: 0.0050 dB/m",
           "• Verwendetes G: 0.50",
           "• Effektiver Boden: globaler Modus, G=0.50 auf allen Pfaden angewendet.",
           "• Kein DGM/DOM: Die Berechnung verwendet ebene Koordinaten mit relativen Quell-/Rezeptorhöhen."],
}

# validate_run_config with no receiver layer, a radius of 0 and a group named "Parque" with no LwA.
_ERRORS = {
    "es": ["Selecciona una capa válida de receptores.", "El radio máximo debe ser mayor que 0.", "Parque: LwA fijo no válido."],
    "en": ["Select a valid receiver layer.", "The maximum radius must be greater than 0.", "Parque: invalid fixed LwA."],
    "fr": ["Sélectionnez une couche de récepteurs valide.", "Le rayon maximal doit être supérieur à 0.",
           "Parque : LwA fixe non valide."],
    "de": ["Wählen Sie einen gültigen Rezeptor-Layer.", "Der maximale Radius muss größer als 0 sein.",
           "Parque: ungültiger fester LwA."],
}
_TITLE = {"es": "Ruido", "en": "Noise", "fr": "Bruit", "de": "Schall"}
_CANNOT_RUN = {"es": "No se puede lanzar el cálculo:", "en": "The calculation cannot be started:",
               "fr": "Impossible de lancer le calcul :", "de": "Die Berechnung kann nicht gestartet werden:"}

_PAGE = {
    "subtitle": {
        "es": 'Módulo de ruido: conectado a la disposición y modelos WT del proyecto, con cálculo sobre receptores, tabla de emisión por modelo, motores rápido e ISO, mapas ráster y salidas GIS. La física actual es un flujo de cribado experimental con limitaciones documentadas.',
        "en": "Noise module: connected to the project layout and WT models, with calculation at receivers, per-model "
              "emission table, fast and ISO engines, raster maps and GIS outputs. The current physics is an experimental "
              "screening workflow with documented limitations.",
        "fr": "Module de bruit : connecté à l’implantation et aux modèles d’éolienne du projet, avec calcul aux récepteurs, "
              "tableau d’émission par modèle, moteur rapide et moteur ISO, cartes raster et sorties SIG. La physique actuelle est "
              "un flux de présélection expérimental avec des limitations documentées.",
        "de": "Schallmodul: mit dem Layout und den WT-Modellen des Projekts verbunden, mit Berechnung an Rezeptoren, "
              "Emissionstabelle je Modell, schnellem Rechenkern und ISO-Rechenkern, Rasterkarten und GIS-Ausgaben. Die "
              "aktuelle Physik ist ein experimenteller Screening-Workflow mit dokumentierten Einschränkungen.",
    },
    "project": {"es": "Proyecto sin nombre", "en": "Unnamed project", "fr": "Projet sans nom", "de": "Unbenanntes Projekt"},
    "ti": {"es": "No seleccionado", "en": "Not selected", "fr": "Non sélectionné", "de": "Nicht ausgewählt"},
    "dem": {"es": "— Sin MDT/DSM —", "en": "— No DEM/DSM —", "fr": "— Aucun MNT/MNS —", "de": "— Kein DGM/DOM —"},
    "receivers": {"es": "— Selecciona la capa de receptores —", "en": "— Select receiver layer —",
                  "fr": "— Sélectionnez la couche de récepteurs —", "de": "— Rezeptor-Layer auswählen —"},
    "iso_method": {"es": "Método ISO: ISO 9613-2 con bandas de octava (Adiv + Aatm(T,RH,P) + Agr(f))",
                   "en": "ISO method: ISO 9613-2 with octave bands (Adiv + Aatm(T,RH,P) + Agr(f))",
                   "fr": "Méthode ISO : ISO 9613-2 par bandes d’octave (Adiv + Aatm(T,RH,P) + Agr(f))",
                   "de": "ISO-Methode: ISO 9613-2 mit Oktavbändern (Adiv + Aatm(T,RH,P) + Agr(f))"},
    "alpha_iso": {"es": "α se calcula automáticamente por banda en el motor ISO",
                  "en": "α is calculated automatically per band in the ISO engine",
                  "fr": "α est calculé automatiquement par bande dans le moteur ISO",
                  "de": "α wird im ISO-Rechenkern automatisch je Band berechnet"},
    "help_sources": {"es": "Explica qué capas de turbinas se usan como fuentes acústicas",
                     "en": "Explain which turbine layers are used as acoustic sources",
                     "fr": "Explique quelles couches d’éoliennes sont utilisées comme sources acoustiques",
                     "de": "Erklärt, welche Windturbinen-Layer als akustische Quellen verwendet werden"},
    "import_title": {"es": "Ruido · Importar layout", "en": "Noise · Import layout", "fr": "Bruit · Importer une implantation",
                     "de": "Schall · Layout importieren"},
    "import_error": {"es": "No se pudo importar el layout de turbinas:", "en": "Could not import the turbine layout:",
                     "fr": "Impossible d’importer l’implantation d’éoliennes :",
                     "de": "Das Windturbinenlayout konnte nicht importiert werden:"},
    "ok": {"es": "Aceptar", "en": "OK", "fr": "OK", "de": "OK"},
    "cancel": {"es": "Cancelar", "en": "Cancel", "fr": "Annuler", "de": "Abbrechen"},
}


class _LanguageTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")


class PairDeliveryTest(_LanguageTest):
    def test_schema_placeholders_and_html(self):
        seen = set()
        for pair in _PAIRS:
            with self.subTest(lang=pair["idioma"], source=pair["es"]):
                self.assertLessEqual({"idioma", "es", "valor", "tabla", "motivo"}, pair.keys())
                self.assertIn(pair["idioma"], _LANGS[1:])
                self.assertIn(pair["tabla"], ("full", "frag"))
                self.assertTrue(all(isinstance(v, str) and v for v in pair.values()))
                key = (pair["idioma"], pair["es"], pair["tabla"])
                self.assertNotIn(key, seen)
                seen.add(key)
                fields = lambda text: Counter((f, spec, conv) for _, f, spec, conv
                                              in string.Formatter().parse(text) if f is not None)
                self.assertEqual(fields(pair["es"]), fields(pair["valor"]))
                tags = lambda text: re.findall(r"</?[A-Za-z][^>]*>", text)
                self.assertEqual(tags(pair["es"]), tags(pair["valor"]))

    def test_delivered_translations_are_available_without_registering_them(self):
        # The delivery is the expected contract, never installed by this test.
        # Until the central tables receive these pairs, only this content is missing.
        for pair in _PAIRS:
            i18n.set_language(pair["idioma"])
            with self.subTest(lang=pair["idioma"], source=pair["es"]):
                translate = i18n.tr_text if pair["tabla"] == "full" else i18n.translate_fragment
                self.assertEqual(translate(pair["es"]), pair["valor"])


class StatusBoxTest(_LanguageTest):
    def test_each_line_is_in_the_language_with_the_names_as_they_are(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            dialog = SimpleNamespace(
                _check_configuration=lambda: None, _current_acoustic_mode=lambda: "fixed",
                txt_status=QtWidgets.QTextEdit(), chk_multi_receivers=QtWidgets.QCheckBox(),
                chk_iso=QtWidgets.QCheckBox(), chk_generate_grid=QtWidgets.QCheckBox())
            result_status.append_result_status(dialog, dict(_RESULT), [])
            with self.subTest(lang=lang):
                self.assertEqual(dialog.txt_status.toPlainText().split("\n"), _STATUS[lang])

    def test_actual_layer_names_and_unknown_details_are_preserved(self):
        prefixes = {"es": "• Capa de salida principal: ", "en": "• Main output layer: ",
                    "fr": "• Couche de sortie principale : ", "de": "• Haupt-Ausgabe-Layer: "}
        for lang in _LANGS:
            i18n.set_language(lang)
            dialog = SimpleNamespace(
                _check_configuration=lambda: None, _current_acoustic_mode=lambda: "fixed",
                txt_status=QtWidgets.QTextEdit(), chk_multi_receivers=QtWidgets.QCheckBox(),
                chk_iso=QtWidgets.QCheckBox(), chk_generate_grid=QtWidgets.QCheckBox())
            result = dict(_RESULT, result_layer=_layer("Plantilla: Norte {modelo}"),
                          acoustic_scenario={"effective_models": [{"name": "Turbinas", "curve_note": "/tmp/modelo/Parque.csv"}]})
            result_status.append_result_status(dialog, result, [])
            with self.subTest(lang=lang):
                lines = dialog.txt_status.toPlainText().splitlines()
                self.assertIn(prefixes[lang] + "Plantilla: Norte {modelo}", lines)
                separator = " : " if lang == "fr" else ": "
                self.assertIn("   - Turbinas" + separator + "/tmp/modelo/Parque.csv", lines)


class CalculationMessagesTest(_LanguageTest):
    def setUp(self):
        QgsProject.instance().clear()
        self.config = NoiseRunConfig(receiver_layer=None, model_cfg={"Parque": {"lwa": 0}}, max_radius_m=0.0)

    def test_the_validation_errors_are_in_the_language_with_the_group_name_as_it_is(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            errors, _warnings = validation.validate_run_config(self.config)
            with self.subTest(lang=lang):
                self.assertEqual(errors, _ERRORS[lang])

    def test_the_calculation_that_cannot_run_says_why_in_the_language(self):
        dialog = mock.Mock()
        dialog._validate_inputs_for_run.return_value = ([], [])
        for lang in _LANGS:
            i18n.set_language(lang)
            with mock.patch.object(dialog_controller, "build_config_from_dialog", return_value=self.config), \
                    mock.patch.object(dialog_controller.QtWidgets, "QMessageBox") as box:
                dialog_controller.run_noise_from_dialog(dialog)
            with self.subTest(lang=lang):
                box.warning.assert_called_once_with(
                    dialog, _TITLE[lang], _CANNOT_RUN[lang] + "\n- " + "\n- ".join(_ERRORS[lang]))

    def test_the_acoustic_inputs_explain_their_errors_in_the_language(self):
        empty = {"es": "Curva acústica vacía", "en": "Empty acoustic curve", "fr": "Courbe acoustique vide",
                 "de": "Leere akustische Kurve"}
        band = {"es": "Falta banda 125 Hz", "en": "Missing band 125 Hz", "fr": "Bande 125 Hz manquante", "de": "Band 125 Hz fehlt"}
        for lang in _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                with self.assertRaises(ValueError) as raised:
                    evaluate_acoustic_curve(np.array([]), np.array([]))
                self.assertEqual(str(raised.exception), empty[lang])
                self.assertEqual(validate_octave_spectrum({63: 90.0})[0], band[lang])

    def test_relative_spectrum_without_total_explains_the_error(self):
        expected = {"es": "Espectro relativo requiere lwa_global", "en": "Relative spectrum requires lwa_global",
                    "fr": "Un spectre relatif nécessite lwa_global", "de": "Ein relatives Spektrum erfordert lwa_global"}
        path = Path(_SETTINGS.name) / "Parque.csv"
        path.write_text("freq_hz,Lw_dB_rel\n63,-5\n125,-2\n", encoding="utf-8")
        for lang in _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang), self.assertRaises(ValueError) as raised:
                load_spectrum_from_csv(str(path))
            self.assertEqual(str(raised.exception), expected[lang])


class TaskMessagesTest(_LanguageTest):
    def test_task_manager_titles_and_cancel_button(self):
        calculation = {"es": "cálculo de ruido", "en": "noise calculation", "fr": "calcul du bruit", "de": "Schallberechnung"}
        raster = {"es": "ráster de ruido", "en": "noise raster", "fr": "raster de bruit", "de": "Schallraster"}
        for lang in _LANGS:
            i18n.set_language(lang)
            task = NoiseCalculationTask(snapshot={})
            grid = NoiseGridTask(params={})
            try:
                with self.subTest(lang=lang):
                    self.assertEqual(task.description(), "Velantis Wind · " + calculation[lang])
                    self.assertEqual(grid.description(), "Velantis Wind · " + raster[lang])
                with mock.patch.object(ui_feedback.QtWidgets, "QProgressDialog") as progress:
                    ui_feedback._show_task_progress_dialog(None, "title", "label")
                with self.subTest(lang=lang, control="cancel"):
                    self.assertEqual(progress.call_args.args[1], _PAGE["cancel"][lang])
            finally:
                grid._project_watch.release()

    def test_background_progress_without_running_a_calculation(self):
        expected = {
            "es": ("Calculando ruido en segundo plano… 40%", "Generando ráster de ruido… 80%"),
            "en": ("Calculating noise in the background… 40%", "Generating noise raster… 80%"),
            "fr": ("Calcul du bruit en arrière-plan… 40 %", "Génération du raster de bruit… 80 %"),
            "de": ("Schall wird im Hintergrund berechnet… 40 %", "Schallraster wird erzeugt… 80 %"),
        }
        helpers = ("_set_dialog_busy", "_show_task_progress_dialog", "_update_task_progress_dialog",
                   "_close_task_progress_dialog", "_notify_qgis", "_append_status_line")
        for lang in _LANGS:
            i18n.set_language(lang)
            with ExitStack() as stack:
                for helper in helpers:
                    stack.enter_context(mock.patch.object(task_controller, helper))
                stack.enter_context(mock.patch.object(task_controller, "ProjectWatch"))
                stack.enter_context(mock.patch("VelantisWind.noise_core.snapshot.builder.build_noise_calculation_snapshot",
                                               return_value={"params": {"create_grid_layer": True}}))
                start = stack.enter_context(mock.patch("VelantisWind.noise_core.tasks.noise_task.start_noise_calculation_task"))
                progress = stack.enter_context(mock.patch.object(task_controller, "_set_dialog_progress"))
                dialog = mock.Mock()
                self.assertTrue(task_controller._run_full_noise_task_from_dialog(dialog, mock.Mock(), []))
                callback = start.call_args.kwargs["on_progress"]
                for value, text in zip((40.0, 80.0), expected[lang]):
                    callback(value)
                    with self.subTest(lang=lang, value=value):
                        progress.assert_called_with(dialog, text, value)


class NoisePageTest(_LanguageTest):
    def setUp(self):
        QgsProject.instance().clear()

    def page(self, lang):
        i18n.set_language(lang)
        page = noise_page.NoisePage(None)
        self.addCleanup(page.deleteLater)
        page.cb_engine.setCurrentIndex(page.cb_engine.findData("iso"))
        page._on_engine_changed()
        return page

    def test_the_page_is_in_the_language(self):
        for lang in _LANGS:
            page = self.page(lang)
            title = page.findChild(QtWidgets.QLabel, "noiseTitle")
            subtitle = page.findChild(QtWidgets.QLabel, "noiseSubtitle")
            help_sources = page.findChildren(QtWidgets.QToolButton)[0]
            with self.subTest(lang=lang):
                self.assertEqual(title.text(), _TITLE[lang])
                self.assertEqual(subtitle.text(), _PAGE["subtitle"][lang])
                self.assertEqual(page.lbl_project.text(), _PAGE["project"][lang])
                self.assertEqual(page.lbl_ti.text(), _PAGE["ti"][lang])
                self.assertEqual(page.cb_dem.itemText(0), _PAGE["dem"][lang])
                self.assertEqual(page.cb_receivers.itemText(0), _PAGE["receivers"][lang])
                self.assertEqual(page.lbl_method.text(), _PAGE["iso_method"][lang])
                self.assertEqual(page.sp_alpha.toolTip(), _PAGE["alpha_iso"][lang])
                self.assertEqual(help_sources.toolTip(), _PAGE["help_sources"][lang])

    def test_the_status_box_is_not_translated_twice(self):
        # The status is written in the active language; the translator would read it back as Spanish fragments.
        for lang in _LANGS:
            page = self.page(lang)
            i18n.apply_i18n(page)
            shown = page.txt_status.toPlainText()
            page._check_configuration()
            with self.subTest(lang=lang):
                self.assertEqual(shown, page.txt_status.toPlainText())

    def test_imported_layout_source_labels_keep_stored_identifiers_and_unknown_values(self):
        labels = {
            "es": ("Energía", "Ruido", "Sombras"),
            "en": ("Energy", "Noise", "Shadow flicker"),
            "fr": ("Énergie", "Bruit", "Ombres portées"),
            "de": ("Energie", "Schall", "Schattenwurf"),
        }
        prefixes = {"es": "layout importado desde ", "en": "layout imported from ",
                    "fr": "implantation importée depuis ", "de": "Layout importiert aus "}
        csv_notes = {"es": "layout importado desde CSV", "en": "layout imported from CSV",
                     "fr": "implantation importée depuis un CSV", "de": "Layout aus CSV importiert"}
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "Turbinas", "memory")
        layer.setCustomProperty("velantis/coords_csv", "Parque.csv")
        for lang in _LANGS:
            page = self.page(lang)
            cases = list(zip(("energy", "noise", "shadow"), labels[lang]))
            cases.extend((value, value) for value in ("Parque {source}", " noise ", ""))
            for source, label in cases:
                with self.subTest(lang=lang, source=source):
                    layer.setCustomProperty("velantis/source_module", source)
                    with mock.patch.object(page, "_iter_model_layers", return_value=[layer]):
                        page._model_rows = page._detect_models(QgsProject.instance())
                    expected = prefixes[lang] + label if source else csv_notes[lang]
                    self.assertTrue(page._model_rows[0]["notes"].endswith(expected))
                    page._populate_models_table()
                    before = page.tbl_models.item(0, 8).text()
                    self.assertIn(expected, before)
                    i18n.apply_i18n(page)
                    self.assertEqual(page.tbl_models.item(0, 8).text(), before)
                    self.assertEqual(layer.customProperty("velantis/source_module"), source)
                    self.assertEqual(layer.customProperty("velantis/coords_csv"), "Parque.csv")

    def test_a_layout_that_cannot_be_imported_says_why_in_the_language(self):
        for lang in _LANGS:
            page = self.page(lang)
            with mock.patch.object(noise_page, "import_turbine_layout_from_csv", side_effect=ValueError("x")), \
                    mock.patch.object(noise_page.QtWidgets.QMessageBox, "warning") as warning:
                page._import_turbine_layout_for_noise()
            with self.subTest(lang=lang):
                warning.assert_called_once_with(page, _PAGE["import_title"][lang], _PAGE["import_error"][lang] + "\nx")

    def test_the_spectrum_editor_buttons_are_in_the_language_of_the_plugin(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            dialog = noise_page.SpectrumEditorDialog(None, group_name="Parque")
            self.addCleanup(dialog.deleteLater)
            buttons = dialog.findChild(QtWidgets.QDialogButtonBox)
            with self.subTest(lang=lang):
                self.assertEqual(buttons.button(QtWidgets.QDialogButtonBox.Ok).text(), _PAGE["ok"][lang])
                self.assertEqual(buttons.button(QtWidgets.QDialogButtonBox.Cancel).text(), _PAGE["cancel"][lang])

    def test_spectrum_group_title_keeps_data_and_french_punctuation(self):
        titles = {"es": "<b>Grupo fuente:</b> ", "en": "<b>Source group:</b> ",
                  "fr": "<b>Groupe de sources :</b> ", "de": "<b>Quellgruppe:</b> "}
        for lang in _LANGS:
            i18n.set_language(lang)
            dialog = noise_page.SpectrumEditorDialog(None, group_name="Parque <Norte> {modelo}")
            self.addCleanup(dialog.deleteLater)
            i18n.apply_i18n(dialog)
            with self.subTest(lang=lang):
                self.assertIn(titles[lang] + "Parque &lt;Norte&gt; {modelo}",
                              [label.text() for label in dialog.findChildren(QtWidgets.QLabel)])


if __name__ == "__main__":
    unittest.main()
