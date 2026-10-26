# -*- coding: utf-8 -*-
"""The texts of the Energy dialog in the four languages (zone Z2 of the translations of 0.1.17): the name of a model is
shown as the user wrote it, the fixed texts have their translation, the Spanish sources have no English, and the
messages are translated from their template with the data inserted after."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import aep_setup_dialog, i18n  # noqa: E402
from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.ag_core.log_text import log_text  # noqa: E402
from VelantisWind.energy_core import dialog_controller  # noqa: E402
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput  # noqa: E402
from VelantisWind.energy_core.validation import format_validation_issues, validate_energy_config  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _texts(dialog):
    """Every visible text of the dialog but its group «Modelo de estela» (zone Z4): labels, buttons, titles, tooltips,
    placeholders and special values."""
    out = set()
    group = dialog.wake_group
    for w in [dialog] + dialog.findChildren(QtWidgets.QWidget):
        if w is group or group.isAncestorOf(w):
            continue
        for attr in ("text", "toolTip", "title", "placeholderText", "specialValueText"):
            fn = getattr(w, attr, None)
            if callable(fn):
                try:
                    value = fn()
                except TypeError:
                    continue
                if isinstance(value, str) and value:
                    out.add(value)
    return out


# Names that are also texts of the tables: the translator would change them («Parque» is «Wind farm», «Resumen»
# «Summary», «Capa» «Layer», «Mayo» «May»), and one with HTML.
_NAMES = ["Parque Norte", "Resumen", "Capa 1", "Modelo", "Custom WT", "Turbinas", "Mayo", "Estelas Bloqueo suelo",
          "Norte <b>2</b> & Sur"]
_ROW = {
    "es": "Modelo {n}: <b>{name}</b> · D=120 m, HH=90 m, P=4.00 MW, Separación=7D×4D",
    "en": "Model {n}: <b>{name}</b> · D=120 m, HH=90 m, P=4.00 MW, Spacing=7D×4D",
    "fr": "Modèle {n} : <b>{name}</b> · D=120 m, HH=90 m, P=4.00 MW, Espacement=7D×4D",
    "de": "Modell {n}: <b>{name}</b> · D=120 m, HH=90 m, P=4.00 MW, Abstand=7D×4D",
}
_UNDEFINED = {"es": "Modelo {n}: <i>(sin definir)</i>", "en": "Model {n}: <i>(not defined)</i>",
              "fr": "Modèle {n} : <i>(non défini)</i>", "de": "Modell {n}: <i>(nicht definiert)</i>"}

# Fixed texts corrected in Z2, as each language shows them.
_FIXED = {
    "es": [
        'Cálculo de AEP con PyWake: define los modelos de aerogenerador, selecciona el recurso eólico (mallas WAsP/Surfer o WRG), elige los modelos físicos (estela, turbulencia, bloqueo, promedio sobre el rotor) y lanza el cálculo. Los resultados se vuelcan automáticamente sobre las capas de coordenadas del proyecto.',
        "Configura la separación mínima entre turbinas: elipse semitransparente por aerogenerador (7D/4D por defecto), "
        "orientada al sector más energético o definida en pantalla, con detección de conflictos de separación.",
        "Elegir ráster(s) TI…", "Ráster(s) de turbulencia TI (opcional):", "TI ambiente manual si no hay ráster:",
        "Opcional: altura de cada ráster TI, ej. 90;120",
        "Valor de turbulencia ambiente que se usa si no cargas un ráster TI. Ejemplo: 10 % significa TI = 0,10 dentro del "
        "Site de PyWake.",
        "Aceptar", "Cancelar", "sin definir",
    ],
    "en": [
        "AEP calculation with PyWake: define the wind turbine models, select the wind resource (WAsP/Surfer grids or WRG), "
        "choose the physical models (wake, turbulence, blockage, rotor averaging) and run the calculation. The results are "
        "written automatically to the coordinate layers of the project.",
        "Configures the minimum spacing between turbines: a semi-transparent ellipse per wind turbine (7D/4D by default), "
        "aligned with the most energetic sector or defined on screen, with spacing-conflict detection.",
        "Choose folder…", "Manual ambient TI without a raster:", "OK", "Cancel", "not defined",
    ],
    "fr": [
        "Configure l’espacement minimal entre éoliennes : une ellipse semi-transparente par éolienne (7D/4D par défaut), "
        "orientée selon le secteur le plus énergétique ou définie à l’écran, avec détection des conflits d’espacement.",
        "Actualise l’état des couches et des modèles détectés dans le projet.", "Documentation PyWake",
        "Enveloppes d’espacement…", "Grilles WAsP/Surfer :", "Fusionner les ressources", "Hauteurs TI par fichier [m] :",
        "TI ambiante manuelle sans raster :", "Facultatif : hauteur de chaque raster TI, p. ex. 90;120",
        "Hauteur manuelle de chaque raster TI, dans le même ordre que les fichiers. Utile si le nom du fichier n’indique "
        "pas clairement 90 m, 120 m, etc.",
        "Affiche la courbe de puissance (et le Ct s’il est disponible) de l’éolienne définie.\nUtile pour détecter des "
        "erreurs de chargement (kW au lieu de W, colonnes inversées, etc.).",
        "Dessine une couche temporaire avec les limites du WRG ou des grilles WAsP/Surfer. Elle permet de vérifier si "
        "l’implantation reste dans le domaine de la ressource.",
        "OK", "Annuler", "non défini",
    ],
    "de": [
        "AEP-Berechnung mit PyWake: Definieren Sie die Windturbinenmodelle, wählen Sie die Windressource (WAsP/Surfer-Grids "
        "oder WRG), legen Sie die physikalischen Modelle fest (Nachlauf, Turbulenz, Blockade, Rotormittelung) und starten "
        "Sie die Berechnung. Die Ergebnisse werden automatisch in die Koordinaten-Layer des Projekts geschrieben.",
        "Konfiguriert den Mindestabstand zwischen Windturbinen: eine halbtransparente Ellipse je Windturbine (standardmäßig "
        "7D/4D), am energiereichsten Sektor ausgerichtet oder am Bildschirm festgelegt, mit Erkennung von "
        "Abstandskonflikten.",
        "Entfernt den temporären Layer der Ressourcengrenze aus dem Projekt.", "Manuelle Umgebungs-TI ohne Raster:",
        "Wert der Umgebungsturbulenz, der verwendet wird, wenn Sie kein TI-Raster laden. Beispiel: 10 % bedeutet "
        "TI = 0,10 im Standortmodell (Site) von PyWake.",
        "OK", "Abbrechen", "nicht definiert",
    ],
}
# Words that the corrected texts no longer show in each language.
_GONE = {
    "es": ["rotor-average", "conflictos de spacing", "raster(s)", "Raster(s)", "raster TI", "0.10", "click", "canvas"],
    "en": ["Choose folder...", "Ambient TI fallback"],
    "fr": ["Refresh le", "View le", "WAsP/Surfer grids", "Fusion ressource", "per fichier", "Optional:", "repli:",
           "le implantation", "d'espacement"],
    "de": ["Blockage", "Rotor-Mittelung", "die temporäre Grenz-Layer", "Windenergieanlage", "des PyWake-Site",
           "der AEP ", "den AEP ", "das CRS"],
}


class _LanguageCase(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")

    def dialog(self, lang):
        i18n.set_language(lang)
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        return dialog


class ModelRowTest(_LanguageCase):
    def test_the_name_of_each_model_is_shown_as_written(self):
        meta = {"diam": 120, "hh": 90, "p_rated_kw": 4000, "spacing_long_d": 7, "spacing_trans_d": 4}
        for lang in _LANGS:
            dialog = self.dialog(lang)
            dialog.sp_n.setValue(2)
            for name in _NAMES:
                with self.subTest(lang=lang, name=name):
                    dialog._rows[0].update(name=name, meta=dict(meta), wt=None)
                    dialog._refresh_model_row_header(0)
                    expected = _ROW[lang].format(n=1, name=name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                    self.assertEqual(dialog._rows[0]["name_lbl"].text(), expected)
                    # The dialog translates its texts again when the rows are rebuilt: the name is kept.
                    dialog._rebuild_rows()
                    self.assertEqual(dialog._rows[0]["name_lbl"].text(), expected)
                    self.assertEqual(dialog._rows[1]["name_lbl"].text(), _UNDEFINED[lang].format(n=2))


class FixedTextsTest(_LanguageCase):
    def test_absent_speedup_is_localized(self):
        expected = {
            "es": "Aceleración: ninguna ⓘ",
            "en": "Speedup: none ⓘ",
            "fr": "Accélération : aucune ⓘ",
            "de": "Beschleunigung: keine ⓘ",
        }
        for lang, text in expected.items():
            with self.subTest(lang=lang):
                dialog = self.dialog(lang)
                self.assertEqual(dialog.lbl_speedup.text(), text)
                dialog._rebuild_rows()
                self.assertEqual(dialog.lbl_speedup.text(), text)

    def test_the_corrected_texts_in_each_language(self):
        for lang in _LANGS:
            texts = _texts(self.dialog(lang))
            for expected in _FIXED[lang]:
                with self.subTest(lang=lang, text=expected[:50]):
                    self.assertIn(expected, texts)
            for gone in _GONE[lang]:
                with self.subTest(lang=lang, gone=gone):
                    self.assertEqual([t for t in texts if gone in t], [])

    def test_the_help_of_the_turbulence(self):
        captured = {}
        with mock.patch.object(aep_setup_dialog, "_show_help_dialog",
                               side_effect=lambda parent, title, body: captured.update(title=title, body=body)):
            for lang in _LANGS:
                dialog = self.dialog(lang)
                dialog._show_wrg_ti_help()
                with self.subTest(lang=lang):
                    body = captured["body"]
                    self.assertTrue(body.startswith({"es": "<b>Qué es TI</b>", "en": "<b>What TI is</b>",
                                                     "fr": "<b>Qu’est-ce que la TI ?</b>", "de": "<b>Was ist die TI?</b>"}[lang]))
                    for gone in {"es": ["raster", "correr", "onshore"], "en": ["ráster"], "fr": ["en onshore", "ráster"],
                                 "de": ["TI bedeutet <b>", "TI-sensitiv", "onshore", "ráster"]}[lang]:
                        self.assertNotIn(gone, body)
                    self.assertIn({"es": "permite ejecutar el cálculo", "en": "lets you run the calculation",
                                   "fr": "permet de lancer le calcul", "de": "(Turbulenzintensität)"}[lang], body)


class MessagesTest(_LanguageCase):
    def test_the_resource_button_names_the_unit_of_the_speed_step(self):
        expected = {
            "es": "Parámetros del recurso (nearest, 84 direcciones, 3–25 m/s cada 1 m/s)",
            "en": "Resource parameters (nearest, 84 directions, 3–25 m/s every 1 m/s)",
            "fr": "Paramètres de la ressource (nearest, 84 directions, 3–25 m/s par pas de 1 m/s)",
            "de": "Ressourcenparameter (nearest, 84 Richtungen, 3–25 m/s in Schritten von 1 m/s)",
        }
        for lang in _LANGS:
            dialog = self.dialog(lang)
            with self.subTest(lang=lang):
                dialog._turbine_speeds = ((3, 25), 1)
                dialog.cb_wd_count.clear()
                dialog.cb_wd_count.addItem("84", 84)
                dialog.cb_ws_step.setCurrentIndex(dialog.cb_ws_step.findData(1.0))
                dialog._update_resource_params_view()
                self.assertEqual(dialog.btn_resource_params.text(), expected[lang])

    def test_an_invalid_wrg_says_why_in_the_language_of_the_plugin(self):
        reasons = {
            "es": "WRG inválido o no legible: El archivo no existe:\n/tmp/Parque/modelo.wrg",
            "en": "Invalid or unreadable WRG: The file does not exist:\n/tmp/Parque/modelo.wrg",
            "fr": "WRG non valide ou illisible : Le fichier n’existe pas :\n/tmp/Parque/modelo.wrg",
            "de": "Ungültige oder nicht lesbare WRG-Datei: Die Datei existiert nicht:\n/tmp/Parque/modelo.wrg",
        }
        for lang in _LANGS:
            dialog = self.dialog(lang)
            with self.subTest(lang=lang):
                error = ValueError(log_text("El archivo no existe:\n{path}", path="/tmp/Parque/modelo.wrg"))
                with mock.patch.object(aep_setup_dialog, "read_wrg_meta", side_effect=error):
                    dialog.ed_wrg.setText("/tmp/Parque/modelo.wrg")
                    dialog._update_wrg_meta()
                self.assertEqual(dialog.lbl_wrg_meta.text(), reasons[lang])
                dialog._rebuild_rows()  # composed with its data: not translated again
                self.assertEqual(dialog.lbl_wrg_meta.text(), reasons[lang])

    def test_an_error_without_a_template_is_its_message(self):
        self.assertEqual(dialog_controller._error_text(ValueError("WRG vacío")), "WRG vacío")
        self.assertEqual(dialog_controller._error_text(ValueError()), "ValueError()")

    def test_the_summary_of_the_first_schema_names_the_gross_aep(self):
        result = {"aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0, "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0}
        expected = {
            "es": "AEP con estelas: 900 MWh | AEP bruto: 1.000 MWh | Pérdidas: 100 MWh (10,0 %)",
            "en": "AEP with wakes: 900 MWh | Gross AEP: 1,000 MWh | Losses: 100 MWh (10.0 %)",
            "fr": "AEP avec sillages : 900 MWh | AEP brut : 1\u202f000 MWh | Pertes : 100 MWh (10,0 %)",
            "de": "AEP mit Nachlauf: 900 MWh | Brutto-AEP: 1.000 MWh | Verluste: 100 MWh (10,0 %)",
        }
        for lang in _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                self.assertEqual(dialog_controller._summary_message(result), expected[lang])

    def test_the_messages_with_their_data(self):
        cases = [
            ("Malla: {nx}×{ny} | celda={cell} m | h={heights} m | sectores={sectors} | extensión={extent}",
             dict(nx=120, ny=80, cell=50.0, heights="100.0", sectors=12, extent="(0,0)–(6000,4000)"),
             {"es": "Malla: 120×80 | celda=50.0 m | h=100.0 m | sectores=12 | extensión=(0,0)–(6000,4000)",
              "en": "Grid: 120×80 | cell=50.0 m | h=100.0 m | sectors=12 | extent=(0,0)–(6000,4000)",
              "fr": "Grille : 120×80 | cellule=50.0 m | h=100.0 m | secteurs=12 | emprise=(0,0)–(6000,4000)",
              "de": "Gitter: 120×80 | Zelle=50.0 m | h=100.0 m | Sektoren=12 | Ausdehnung=(0,0)–(6000,4000)"}),
            ("{file} ({height} m, manual)", dict(file="ti_90m.tif", height=90),
             {"es": "ti_90m.tif (90 m, manual)", "en": "ti_90m.tif (90 m, manual)",
              "fr": "ti_90m.tif (90 m, valeur saisie)", "de": "ti_90m.tif (90 m, Eingabe)"}),
            (AEPSetupDialog.GO_MISSING_QUESTION, dict(libs="h5py", what=i18n.tr_text("el AEP")),
             {"fr": "CGIRotorAvg(7) sera utilisé à la place de GaussianOverlapAvgModel car h5py n’est pas disponible. "
                    "Cliquez sur Continuer pour calculer l’AEP avec CGIRotorAvg(7).",
              "de": "Statt GaussianOverlapAvgModel wird CGIRotorAvg(7) verwendet, weil h5py nicht verfügbar ist. Klicken "
                    "Sie auf Fortfahren, um die AEP mit CGIRotorAvg(7) zu berechnen."}),
        ]
        for template, data, expected in cases:
            for lang, text in expected.items():
                i18n.set_language(lang)
                with self.subTest(lang=lang, text=template[:30]):
                    if "what" in data:
                        data = dict(data, what=i18n.tr_text("el AEP"))
                    self.assertEqual(i18n.tr_text(template).format(**data), text)

    def test_the_coordinate_system_and_ti_warnings(self):
        cases = [
            ("de", "El proyecto usa un sistema de coordenadas no proyectado. El AEP necesita un sistema proyectado "
             "y en metros: cambia el del proyecto.",
             "Das Projekt verwendet ein nicht projiziertes Koordinatenbezugssystem. Die AEP benötigt ein projiziertes "
             "Koordinatenbezugssystem mit Metern als Einheit: Ändern Sie das Koordinatenbezugssystem des Projekts "
             "entsprechend."),
            ("de", "El sistema de coordenadas del proyecto no está en metros. El AEP necesita un sistema proyectado "
             "y en metros: cambia el del proyecto.",
             "Das Koordinatenbezugssystem des Projekts ist nicht in Metern. Die AEP benötigt ein projiziertes "
             "Koordinatenbezugssystem mit Metern als Einheit: Ändern Sie das Koordinatenbezugssystem des Projekts "
             "entsprechend."),
            ("fr", "No se ha seleccionado ráster TI para WRG; se usará TI fija/de respaldo si el modelo lo necesita.",
             "Aucun raster TI n’a été sélectionné pour le WRG ; une TI fixe ou de repli sera utilisée si le modèle "
             "en a besoin."),
        ]
        for lang, source, expected in cases:
            i18n.set_language(lang)
            with self.subTest(lang=lang, source=source):
                self.assertEqual(i18n.tr_text(source), expected)

    def test_the_validation_of_the_ti_raster(self):
        config = EnergyRunConfig(models=[TurbineModelInput(name="Parque", wt=None)], wasp_dir="",
                                 wrg_ti_paths=["/tmp/no/ti_90m.tif"])
        expected = {"es": "Ráster TI no existe: /tmp/no/ti_90m.tif", "en": "TI raster does not exist: /tmp/no/ti_90m.tif",
                    "fr": "Le raster TI n’existe pas : /tmp/no/ti_90m.tif", "de": "TI-Raster existiert nicht: /tmp/no/ti_90m.tif"}
        for lang in _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                self.assertIn(expected[lang], format_validation_issues(validate_energy_config(config)))


if __name__ == "__main__":
    unittest.main()
