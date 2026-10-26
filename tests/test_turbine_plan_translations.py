# -*- coding: utf-8 -*-
"""User-facing texts of the turbine plan (air density, .wtg/.owtg/CSV readers, turbine dialog) in EN/FR/DE."""
import ast
import html
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from VelantisWind import i18n
from VelantisWind.ag_core.log_text import log_text, shown
from VelantisWind.ag_core.turbine import CT_ESTIMATED_WARNING, TxtSpec, load_curves_from_txt
from VelantisWind.ag_core.turbines.density_curve import CurveTableError, TurbineCurveTable
from VelantisWind.ag_core.turbines.wtg import WtgFormatError, load_wtg

_LANGS = ("en", "fr", "de")
_PLUGIN = Path(i18n.__file__).parent
# A placeholder with its conversion and format spec ({value!r}, {low:g}) stays as it is.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")

# Every literal these modules give to _error, _fail or log_text is a template the interface translates.
_TEMPLATE_MODULES = (
    "ag_core/turbine.py",
    "ag_core/physics/air_density.py",
    "ag_core/turbines/density_curve.py",
    "ag_core/turbines/density_resolution.py",
    "ag_core/turbines/wtg.py",
    "ag_core/turbines/owtg.py",
)
# Texts of the dialogs, the results and the wake raster.
_SHOWN_TEXTS = [
    # AEP dialog, air-density controls
    "Ajustar las curvas a la densidad del aire",
    "Solo actúa sobre turbinas con curvas tabuladas por densidad (.wtg, .owtg). Cada aerogenerador usa la curva "
    "interpolada a la densidad del aire en la cota de su buje.",
    "Por turbina (según la cota de su buje)",
    "Uniforme en todo el parque",
    "«Por turbina» lleva la densidad de referencia a la cota de cada buje con el perfil ISA. «Uniforme» aplica la "
    "densidad de referencia a todo el parque.",
    "Densidad del aire de referencia del proyecto.",
    "Cota sobre el nivel del mar a la que está dada la densidad de referencia.",
    "Densidad de referencia:",
    "a la cota:",
    "La potencia y el empuje dependen de la densidad del aire, y cada aerogenerador está a una cota distinta. Con "
    "una turbina de curvas tabuladas por densidad (.wtg, .owtg), se calcula la densidad en la cota de cada buje a "
    "partir de la referencia del proyecto y se interpola la curva que le corresponde. La cota del terreno la aporta "
    "el recurso (WRG). Las curvas de una sola densidad no se corrigen.",
    "No se pudieron leer los controles de densidad del aire: {error}",
    # Turbine dialog
    "CT (0–1,2):",
    "Fichero .wtg:", "Fichero .owtg:", "Fichero .wtg", "Fichero .owtg",
    "Selecciona un fichero .wtg…", "Selecciona un fichero .owtg…",
    "Selecciona un fichero .wtg válido.", "Selecciona un fichero .owtg válido.",
    "Abrir fichero .wtg", "Abrir fichero .owtg",
    "Turbina .wtg (*.wtg);;Todos (*.*)", "Turbina .owtg (*.owtg);;Todos (*.*)",
    "Crear turbina (.wtg)", "Crear turbina (.owtg)",
    "No se pudo leer el fichero .wtg.", "No se pudo leer el fichero .owtg.",
    "Turbina creada desde el fichero .wtg.", "Turbina creada desde el fichero .owtg.",
    "Pulsa Aceptar para usarla.",
    "El diámetro, la altura de buje y las curvas se leen del propio fichero.",
    "Se rellena con la altura del fichero. Cámbiala solo si el proyecto usa otra torre: la curva no cambia, pero sí "
    "la cota a la que se evalúan el viento y la densidad del aire.",
    "Altura de buje",
    "El fichero sugiere varias alturas de buje. Elige la del proyecto:",
    "La geometría del fichero (D={diam} m, HH={hub} m) no cabe en los controles del diálogo (D hasta {diam_max} m, "
    "HH hasta {hub_max} m).",
    "Atención: has cambiado la geometría respecto al fichero (D={diam} m, HH={hub} m).",
    "Trae {n} curvas entre {low} y {high} kg/m³; la vista previa se muestra a {preview} kg/m³.",
    "Cada aerogenerador podrá usar la curva de su densidad entre {low} y {high} kg/m³, activando el ajuste por "
    "densidad en la pantalla de energía.",
    "El fichero solo trae una densidad: la curva será la misma para todo el parque.",
    "Datos cambiados",
    "Has cambiado {datos} desde que creaste la turbina.",
    "En la pestaña {pestana} has cambiado {datos}, pero la turbina creada es la de la pestaña {creada}.",
    "Si continúas, se usará la última turbina que creaste, sin esos cambios. Para aplicarlos, vuelve y pulsa "
    "«Crear turbina».",
    "Continuar", "Volver",
    CT_ESTIMATED_WARNING,
    # Calculation notes
    "Modelo «{name}»: {warning}",
    "Densidad del aire: {summary}.",
    # Wake raster
    "Densidad del aire:",
    "El ráster se ha calculado con las entradas actuales del diálogo, que difieren del último AEP en: {categories}. "
    "Vuelve a calcular el AEP para que el informe corresponda al mapa.",
    "turbinas y posiciones", "recurso eólico y turbulencia", "modelo de estela", "densidad del aire",
    "sistema de coordenadas del proyecto",
    "No se aplicó la densidad del aire al ráster: {error} El mapa se calcula con la densidad del recurso, que puede "
    "no coincidir con la del informe de energía.",
    "No se aplicó la densidad del aire al ráster: {error} El mapa se calcula con la densidad por defecto de cada "
    "curva, que puede no coincidir con la del informe de energía.",
]
# Kept as they are on purpose: format names, file fields, units and symbols.
_KEPT_TERMS = (
    ".wtg", ".owtg", "Ct", "CT", "ISA", "WRG", "PyWake", "Air_density", "IEC", "D=", "HH=",
    "kg/m³", "m/s", "kW", "%",
    "LowSpeedCutIn", "HighSpeedCutOut", "AirDensity", "PowerOutput", "WindSpeed", "RotorDiameter",
    "SuggestedHeights", "Height", "PerformanceTable", "DataTable", "DataPoint", "StationaryThrustCoEfficient",
    "Description", "FormatVersion", "WindTurbineGenerator", "TurbineType", "CapacityKW", "PeakOutputKW",
    "DesignAirDensity", "IEC_adjustment", "AirDensities", "Velocities", "Columns", "Rows", "Count", "RhoX",
    "Power_Table0", "Name", "Type",
)
# Texts whose translation is the Spanish text itself.
_SAME_TEXT = {"Ct": _LANGS, "CT (0–1,2):": ("de",), "uniforme": ("fr",)}


def _run_in(lang, fn, *args):
    with mock.patch.object(i18n, "current_language", return_value=lang):
        return fn(*args)


def _templates():
    texts = []
    for module in _TEMPLATE_MODULES:
        for node in ast.walk(ast.parse((_PLUGIN / module).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args:
                arg = {"_error": 1, "_fail": 0, "log_text": 0}.get(node.func.id)
                if arg is not None and isinstance(node.args[arg], ast.Constant):
                    texts.append(node.args[arg].value)
    return texts


def _tr(lang):
    return lambda text: _run_in(lang, i18n.tr_text, text)


class TurbinePlanTextsTest(unittest.TestCase):
    def test_every_text_has_its_translation(self):
        i18n._ensure()
        texts = sorted(set(_templates() + _SHOWN_TEXTS))
        self.assertGreater(len(texts), 190)
        for lang in _LANGS:
            table = i18n._STATE["full"][lang]
            for text in texts:
                with self.subTest(lang=lang, text=text[:60]):
                    self.assertIn(text, table)
                    translated = table[text]
                    # No cleanup rewrites it, whether shown whole or as a tooltip.
                    self.assertEqual(_run_in(lang, i18n.tr_text, text), translated)
                    self.assertEqual(_run_in(lang, i18n.translate_fragment, text), translated)
                    if lang in _SAME_TEXT.get(text, ()):
                        self.assertEqual(translated, text)
                    else:
                        self.assertNotEqual(translated, text)
                    self.assertEqual(sorted(_PLACEHOLDER.findall(translated)), sorted(_PLACEHOLDER.findall(text)))
                    for term in (t for t in _KEPT_TERMS if t in text):
                        self.assertEqual(translated.count(term), text.count(term), term)

    def test_reader_errors_are_shown_translated_with_their_data(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        csv_path = os.path.join(folder.name, "curva.csv")
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("ws,power_kw,ct\n3,100,0.80\n4,200,ERROR\n5,300,0.82\n")
        with self.assertRaises(ValueError) as csv_error:
            load_curves_from_txt(csv_path, TxtSpec(ws_col=0, power_col=1, delimiter=",", skip_header=1, ct_col=2))
        wtg_path = os.path.join(folder.name, "turbine.wtg")
        with open(wtg_path, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0"?><WindTurbineGenerator RotorDiameter="100"><PerformanceTable AirDensity="1.225">'
                     '<StartStopStrategy LowSpeedCutIn="3" HighSpeedCutOut="25"/><DataTable/></PerformanceTable>'
                     "</WindTurbineGenerator>")
        with self.assertRaises(WtgFormatError) as wtg_error:
            load_wtg(wtg_path)
        with self.assertRaises(CurveTableError) as table_error:
            TurbineCurveTable(name="T", diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=(3.0, 8.0),
                              air_densities=(1.225,), power_kw=((50.0,), (1000.0,)), ct=((0.8,), (1.3,)),
                              default_air_density=1.225, cut_in_ms=3.0, cut_out_ms=8.0)
        expected = {
            "en": [
                "Invalid Ct in curva.csv, line 3, column 2: 'ERROR'. Each Ct must be a finite number between 0 and 1.2; "
                "1.2 is not a physical ceiling but the admission threshold above which the data must be reviewed.",
                "Unsupported .wtg variant: element <SuggestedHeights> is missing in the root.",
                "Out-of-range Ct value at 8 m/s and 1.225 kg/m³: 1.3 > 1.2. 1.2 is not a physical ceiling but the "
                "admission threshold above which the data must be reviewed.",
            ],
            "fr": [
                "Ct non valide dans curva.csv, ligne 3, colonne 2 : 'ERROR'. Chaque Ct doit être un nombre fini entre 0 "
                "et 1.2 ; 1.2 n’est pas un plafond physique, mais le seuil d’admission au-delà duquel la donnée doit "
                "être vérifiée.",
                "Variante .wtg non prise en charge : l’élément <SuggestedHeights> manque dans la racine.",
                "Valeur de Ct hors plage à 8 m/s et 1.225 kg/m³ : 1.3 > 1.2. 1.2 n’est pas un plafond physique, mais "
                "le seuil d’admission au-delà duquel la donnée doit être vérifiée.",
            ],
            "de": [
                "Ungültiger Ct in curva.csv, Zeile 3, Spalte 2: 'ERROR'. Jeder Ct muss eine endliche Zahl zwischen 0 "
                "und 1.2 sein; 1.2 ist keine physikalische Obergrenze, sondern die Zulassungsschwelle, ab der der Wert "
                "geprüft werden muss.",
                "Nicht unterstützte .wtg-Variante: Element <SuggestedHeights> fehlt in Wurzelelement.",
                "Wert für Ct außerhalb des Bereichs bei 8 m/s und 1.225 kg/m³: 1.3 > 1.2. 1.2 ist keine physikalische "
                "Obergrenze, sondern die Zulassungsschwelle, ab der der Wert geprüft werden muss.",
            ],
        }
        errors = (csv_error.exception, wtg_error.exception, table_error.exception)
        for lang, messages in expected.items():
            with self.subTest(lang=lang):
                self.assertEqual([shown(error, _tr(lang)) for error in errors], messages)

    def test_words_inside_other_messages_are_translated(self):
        rejection = log_text(
            "Variante de .owtg no soportada: {tag}={value:g}. Las curvas de potencia dependen {what}, que este cálculo "
            "no representa.",
            tag="AdjustPowerCurvesForTI", value=1.0, what=log_text("de la intensidad de turbulencia"),
        )
        expected = {
            "en": "Unsupported .owtg variant: AdjustPowerCurvesForTI=1. The power curves depend on the turbulence "
                  "intensity, which this calculation does not represent.",
            "fr": "Variante .owtg non prise en charge : AdjustPowerCurvesForTI=1. Les courbes de puissance dépendent de "
                  "l’intensité de turbulence, ce que ce calcul ne représente pas.",
            "de": "Nicht unterstützte .owtg-Variante: AdjustPowerCurvesForTI=1. Die Leistungskurven hängen von der "
                  "Turbulenzintensität ab; diese Berechnung bildet das nicht ab.",
        }
        for lang, text in expected.items():
            with self.subTest(lang=lang):
                self.assertEqual(shown(rejection, _tr(lang)), text)

    def test_calculation_notes_are_translated_in_results_html(self):
        # The results dialog shows the notes already filled in and translates its HTML by fragments.
        per_turbine = log_text(
            "densidad por turbina (ISA calibrado, referencia {reference:.4f} kg/m³ a {altitude:g} m s.n.m.): "
            "{densities}; cota de buje {low:.0f}–{high:.0f} m s.n.m.",
            reference=1.099, altitude=1093.0, densities="1.0716–1.1052 kg/m³", low=1036.0, high=1349.0,
        )
        notes = [
            log_text("Densidad del aire: {summary}.", summary=per_turbine),
            log_text("Densidad del aire: {summary}.", summary=log_text(
                "{summary}; {n} turbina(s) acotada(s) al rango de su curva", summary=per_turbine, n=3)),
            log_text("Densidad del aire: {summary}.", summary=log_text("densidad uniforme {reference:.4f} kg/m³",
                                                                        reference=1.225)),
            log_text("Densidad del aire: {summary}.", summary=log_text(
                "ajuste por densidad desactivado: cada turbina usa la densidad por defecto de su curva ({densities})",
                densities="1.2250 kg/m³")),
            log_text("Las curvas de potencia están tabuladas por densidad, pero el ajuste está desactivado: cada "
                     "turbina se evalúa a la densidad por defecto de su curva ({densities}), sin tener en cuenta la "
                     "cota de su buje.", densities="1.1000–1.2250 kg/m³"),
            log_text("{n} turbina(s) quedan fuera del rango de densidad tabulado por su curva y se acotan a su extremo, "
                     "sin extrapolar.", n=3),
            log_text("Las turbinas de {names} tienen una curva de una sola densidad: no se corrigen con la densidad del "
                     "aire.", names="T-2"),
            log_text("Se pidió ajustar las curvas a la densidad del aire, pero ninguna curva del parque está tabulada "
                     "por densidad: se usan tal cual, sin corregir."),
            log_text("Modelo «{name}»: {warning}", name="T", warning=log_text(CT_ESTIMATED_WARNING)),
        ]
        for lang in _LANGS:
            for note in notes:
                with self.subTest(lang=lang, note=str(note)[:50]):
                    # The same text as the message bar, which translates the template.
                    self.assertEqual(_run_in(lang, i18n.translate_html, f"<li>{html.escape(str(note))}</li>"),
                                     f"<li>{html.escape(shown(note, _tr(lang)))}</li>")
        expected = {
            "en": "Air density: per-turbine density (calibrated ISA, reference 1.0990 kg/m³ at 1093 m asl): "
                  "1.0716–1.1052 kg/m³; hub altitude 1036–1349 m asl.",
            "fr": "Densité de l’air : densité par éolienne (ISA calibré, référence 1.0990 kg/m³ à 1093 m d’altitude) : "
                  "1.0716–1.1052 kg/m³ ; moyeux à 1036–1349 m d’altitude.",
            "de": "Luftdichte: Dichte je Windturbine (kalibrierte ISA, Referenz 1.0990 kg/m³ in 1093 m ü. NN): "
                  "1.0716–1.1052 kg/m³; Naben in 1036–1349 m ü. NN.",
        }
        for lang, text in expected.items():
            with self.subTest(lang=lang, note="per turbine, expected"):
                self.assertEqual(_run_in(lang, i18n.translate_html, str(notes[0])), text)

    def test_dialog_and_report_texts_read_as_expected(self):
        texts = {
            "Ajustar las curvas a la densidad del aire": (
                "Adjust the curves to the air density", "Ajuster les courbes à la densité de l’air",
                "Kurven an die Luftdichte anpassen"),
            "Por turbina (según la cota de su buje)": (
                "Per turbine (from its hub altitude)", "Par éolienne (selon l’altitude de son moyeu)",
                "Je Windturbine (nach der Höhe ihrer Nabe über NN)"),
            "Datos cambiados": ("Data changed", "Données modifiées", "Daten geändert"),
            "Continuar": ("Continue", "Continuer", "Fortfahren"),
            "Volver": ("Go back", "Revenir", "Zurück"),
            "Crear turbina (.owtg)": ("Create turbine (.owtg)", "Créer l’éolienne (.owtg)", "Windturbine erstellen (.owtg)"),
            "Turbina creada desde el fichero .wtg.": (
                "Turbine created from the .wtg file.", "Éolienne créée à partir du fichier .wtg.",
                "Windturbine aus der .wtg-Datei erstellt."),
            "Falta la densidad de aire de referencia del proyecto.": (
                "The project’s reference air density is missing.",
                "La densité de l’air de référence du projet est manquante.", "Die Referenz-Luftdichte des Projekts fehlt."),
            "El ráster se ha calculado con las entradas actuales del diálogo, que difieren del último AEP en: "
            "{categories}. Vuelve a calcular el AEP para que el informe corresponda al mapa.": (
                "The raster was calculated with the current inputs of the dialog, which differ from the last AEP in: "
                "{categories}. Calculate the AEP again so that the report matches the map.",
                "Le raster a été calculé avec les entrées actuelles de la boîte de dialogue, qui diffèrent du dernier "
                "AEP sur : {categories}. Recalculez l’AEP pour que le rapport corresponde à la carte.",
                "Das Raster wurde mit den aktuellen Eingaben des Dialogs berechnet, die sich von der letzten AEP "
                "unterscheiden in: {categories}. Berechnen Sie die AEP erneut, damit der Bericht der Karte entspricht."),
            "turbinas y posiciones": ("turbines and positions", "éoliennes et positions", "Windturbinen und Positionen"),
            "recurso eólico y turbulencia": ("wind resource and turbulence", "ressource éolienne et turbulence",
                                             "Windressource und Turbulenz"),
            "modelo de estela": ("wake model", "modèle de sillage", "Nachlaufmodell"),
            "densidad del aire": ("air density", "densité de l’air", "Luftdichte"),
            "sistema de coordenadas del proyecto": ("coordinate reference system of the project",
                                                    "système de coordonnées de référence du projet",
                                                    "Koordinatenbezugssystem des Projekts"),
        }
        for text, translations in texts.items():
            for lang, translated in zip(_LANGS, translations):
                with self.subTest(lang=lang, text=text[:40]):
                    self.assertEqual(_run_in(lang, i18n.tr_text, text), translated)

    def test_note_fragments_leave_other_texts_alone(self):
        # Fragments are also read backwards, from any language to Spanish, inside every translated blob.
        texts = [
            "La resolución del raster debe ser mayor que 0 m.",
            "Solo hay un raster TI a 100 m; se aplicará a todas las alturas.",
            "For quick tests use 100–200 m; for finer outputs use 50 m.",
            "100 m ; 200 m; 300 m.",
        ]
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(i18n._fragment_impl(text, "es"), text)


if __name__ == "__main__":
    unittest.main()
