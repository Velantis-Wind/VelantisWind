# -*- coding: utf-8 -*-
"""Texts of the Shadow flicker module in the four languages: the time-basis label, the names of the project that the
page shows, the summary of the calculation and the French term of the module ("ombres portées")."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401
from VelantisWind import shadow_page  # noqa: E402
from VelantisWind.shadow_core.results import summary  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


_TIME_BASIS = {
    ("es", "fixed"): "Base temporal: desfase UTC fijo UTC+1,0. Útil para cálculos reproducibles con desfase fijo; no se "
                     "aplica horario de verano.",
    ("en", "fixed"): "Time basis: fixed UTC offset UTC+1.0. Useful for reproducible fixed-offset calculations; daylight "
                     "saving time is not applied.",
    ("fr", "fixed"): "Base temporelle : décalage UTC fixe UTC+1,0. Utile pour des calculs reproductibles à décalage fixe ; "
                     "l’heure d’été n’est pas appliquée.",
    ("de", "fixed"): "Zeitbasis: fester UTC-Offset UTC+1,0. Nützlich für reproduzierbare Berechnungen mit festem Offset; "
                     "Sommerzeit wird nicht angewendet.",
    ("es", "iana"): "Base temporal: hora civil local con DST · Zona: Europe/Madrid. El cálculo solar usa UTC internamente "
                    "y acumula resultados por mes/hora local.",
    ("en", "iana"): "Time basis: local civil time with DST · Zone: Europe/Madrid. The solar calculation uses UTC internally "
                    "and aggregates results by local month/hour.",
    ("fr", "iana"): "Base temporelle : heure civile locale avec DST · Zone : Europe/Madrid. Le calcul solaire utilise UTC en "
                    "interne et accumule les résultats par mois/heure locaux.",
    ("de", "iana"): "Zeitbasis: lokale Uhrzeit mit DST · Zone: Europe/Madrid. Die Sonnenberechnung verwendet intern UTC und "
                    "aggregiert die Ergebnisse nach lokalen Monaten/Stunden.",
}


def _settings():
    return QtCore.QSettings("VelantisWind", "VelantisWindPlugin")


def _page(test, lang, mode="fixed"):
    i18n.set_language(lang)
    s = _settings()
    s.setValue("shadow/timezone_mode", mode)
    s.setValue("shadow/timezone_name", "Europe/Madrid")
    s.setValue("shadow/timezone_offset", 1.0)
    page = shadow_page.ShadowPage()
    test.addCleanup(page.deleteLater)
    return page


def _point_layer(name, model_name=None):
    lyr = QgsVectorLayer("Point?crs=EPSG:32630", name, "memory")
    feature = QgsFeature(lyr.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000.0, 4400000.0)))
    lyr.dataProvider().addFeatures([feature])
    if model_name:
        lyr.setCustomProperty("velantis/model_name", model_name)
        lyr.setCustomProperty("velantis/hub_height_m", 100.0)
        lyr.setCustomProperty("velantis/diameter_m", 120.0)
    QgsProject.instance().addMapLayer(lyr)
    return lyr


class _ShadowTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        _settings().clear()
        self.addCleanup(i18n.set_language, "es")


class TimeBasisLabelTest(_ShadowTest):
    def test_the_label_in_each_language_and_mode(self):
        for (lang, mode), expected in _TIME_BASIS.items():
            with self.subTest(lang=lang, mode=mode):
                page = _page(self, lang, mode)
                self.assertEqual(page.lbl_timezone_status.text(), expected)
                # The hub translates the page again when it refreshes it: the label, composed already, stays.
                i18n.apply_i18n(page)
                self.assertEqual(page.lbl_timezone_status.text(), expected)


class TimeBasisLabelAfterLanguageChangeTest(_ShadowTest):
    """Depends on M4: the page's retranslate(), which the hub calls when the language changes."""

    def test_the_label_follows_a_language_change_without_changing_the_mode(self):
        for mode in ("fixed", "iana"):
            for start in _LANGS:
                page = _page(self, start, mode)
                for target in _LANGS:
                    if target == start:
                        continue
                    with self.subTest(mode=mode, start=start, target=target):
                        i18n.set_language(target)
                        i18n.apply_i18n(page)
                        page.retranslate()
                        i18n.apply_i18n(page)
                        self.assertEqual(page.lbl_timezone_status.text(), _TIME_BASIS[(target, mode)])


class ProjectNamesTest(_ShadowTest):
    def test_the_names_of_the_layers_are_shown_as_written(self):
        # Names that are also texts of the interface: the translator would change them.
        for lang, name, expected in (("es", "Source A", "Source A · 1 receptor(es)"),
                                     ("de", "Receptores", "Receptores · 1 Rezeptor(en)"),
                                     ("en", "Receptores", "Receptores · 1 receiver(s)")):
            with self.subTest(lang=lang, name=name):
                QgsProject.instance().clear()
                receivers = _point_layer(name)
                _settings().setValue("shadow/receiver_layer_id", receivers.id())
                page = _page(self, lang)
                self.assertEqual(page.lbl_receptor_info.text(), expected)
                i18n.apply_i18n(page)
                self.assertEqual(page.lbl_receptor_info.text(), expected)

    def test_the_status_is_not_translated_again(self):
        # L9-1: the German status line came out "Entfernung máxima de Schatten".
        page = _page(self, "de")
        i18n.apply_i18n(page)
        self.assertIn("✓ Maximale Schattenentfernung: 2000 m", page.txt_status.toPlainText().splitlines())

    def test_the_model_settings_are_saved_under_the_model_name(self):
        # The visible cell can be translated ("Turbinas" -> "Windturbinen"); the settings key is the name.
        turbines = _point_layer("Turbinas", model_name="Turbinas")
        _settings().setValue("shadow/turbine_layer_id", turbines.id())
        page = _page(self, "de")
        page.tbl_models.item(0, 0).setText("Windturbinen")
        page.tbl_models.item(0, 2).setText("110.0")
        self.assertEqual(_settings().value("shadow/model_Turbinas_hh"), 110.0)
        self.assertIsNone(_settings().value("shadow/model_Windturbinen_hh"))

    def test_invalid_dimensions_are_saved_and_remain_visible_after_repopulation(self):
        turbines = _point_layer("Turbinas", model_name="Turbinas")
        _settings().setValue("shadow/turbine_layer_id", turbines.id())
        for lang in _LANGS:
            page = _page(self, lang)
            for column, suffix in ((2, "hh"), (3, "d")):
                for invalid in ("  altura,diámetro inválidos  ", ""):
                    with self.subTest(lang=lang, column=column, invalid=invalid):
                        key = f"shadow/model_Turbinas_{suffix}"
                        page.tbl_models.item(0, column).setText("110.0")
                        self.assertEqual(_settings().value(key), 110.0)
                        page.tbl_models.item(0, column).setText(invalid)
                        self.assertEqual(_settings().value(key), invalid)
                        page._populate_models_table()
                        self.assertEqual(page.tbl_models.item(0, column).text(), invalid)


class DetectedTimeZoneTest(_ShadowTest):
    def test_the_method_is_named_in_words(self):
        # S10-12: "Método: bundled approximate bbox".
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        turbines = _point_layer("T", model_name="T")
        expected = {"es": "Método: aproximación por recuadro geográfico", "en": "Method: approximation by geographic box",
                    "fr": "Méthode : approximation par zone géographique",
                    "de": "Methode: Näherung über einen geografischen Rahmen"}
        for lang in _LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                page = mock.Mock(_model_rows=[])
                page.cb_turbines.currentData.return_value = turbines.id()
                page.cb_timezone_mode.findData.return_value = -1
                with mock.patch.object(shadow_page, "detect_timezone_name",
                                       return_value=("Europe/Madrid", "bundled approximate bbox", "")), \
                        mock.patch.object(QtWidgets.QMessageBox, "information") as information:
                    shadow_page.ShadowPage._auto_detect_coordinates(page)
                message = information.call_args.args[2]
                self.assertIn(expected[lang], message.splitlines())
                self.assertNotIn("bundled", message)


class _Result:
    receptor_name = "R1"
    hours_per_year_astronomical = 12.0
    hours_per_year_realistic = 9.0
    days_affected = 20
    max_minutes_per_day = 25
    max_shadow_date = None
    turbine_contributions = {"T1": 12.0}
    hourly_monthly_matrix = None
    calendar = {}
    time_step_minutes = 5


class _Calculator:
    latitude = 42.0
    longitude = -2.0
    year = 2025
    timezone_mode = "fixed"
    timezone_name = None
    timezone_offset = 1.0
    time_step_minutes = 5
    turbine_availability = 0.97
    max_shadow_distance_m = 2000
    min_sun_elevation = 3.0
    max_sun_elevation = 90.0


def _summary_texts():
    """The labels, group titles, card titles and receiver-table headers of the summary dialog."""
    shown = []

    def capture(dialog):
        shown.append(dialog)
        return 0

    with mock.patch.object(QtWidgets.QDialog, "exec_", capture):
        summary.show_summary_dialog_for_page(None, [_Result()], [{"hub_height": 100.0, "rotor_diameter": 120.0}],
                                             _Calculator())
    [dialog] = shown
    texts = [w.text() for w in dialog.findChildren(QtWidgets.QLabel)]
    texts += [w.title() for w in dialog.findChildren(QtWidgets.QGroupBox)]
    texts.append(dialog.windowTitle())
    tables = dialog.findChildren(QtWidgets.QTableWidget)
    table_rec = [t for t in tables if t.columnCount() == 10][0]
    headers = [table_rec.horizontalHeaderItem(c).text() for c in range(table_rec.columnCount())]
    texts += [b.text() for b in dialog.findChildren(QtWidgets.QPushButton)]
    dialog.deleteLater()
    return texts, headers


class SummaryTest(_ShadowTest):
    _LABELS = {
        "es": ["Latitud:", "Longitud:", "Máximo", "Capa de entrada"],
        "en": ["Latitude:", "Longitude:", "Maximum", "Input layer"],
        "fr": ["Latitude :", "Longitude :", "Maximum", "Couche d’entrée", "Ombres portées annuelles :",
               "Ombres portées - Résumé du calcul", "📊 Exporter le CSV 12×24"],
        "de": ["Breitengrad:", "Längengrad:", "Maximum", "Eingabe-Layer", "Am stärksten exponierter Rezeptor"],
    }
    _HEADERS = {
        "es": ["h realistas", "Día crítico", "Aerogeneradores afectados", "Aerogenerador dominante", "h dominantes"],
        "en": ["Realistic h", "Critical day", "Contributing turbines", "Dominant turbine", "Dominant h"],
        "fr": ["h réalistes", "Jour critique", "Éoliennes contributrices", "Éolienne dominante", "h dominantes"],
        "de": ["Realistische h", "Kritischer Tag", "Beitragende Windturbinen", "Dominante Windturbine", "Dominante h"],
    }

    def test_the_summary_in_each_language(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                texts, headers = _summary_texts()
                for label in self._LABELS[lang]:
                    self.assertIn(label, texts)
                self.assertEqual([headers[c] for c in (2, 5, 6, 7, 8)], self._HEADERS[lang])

    def test_distinct_values_in_german(self):
        i18n.set_language("de")
        self.assertEqual(summary._format_turbine_geometry([{"hub_height": 100.0}, {"hub_height": 120.0}], "hub_height"),
                         "100.00–120.00 m (2 verschiedene Werte)")


class FrenchModuleTermTest(_ShadowTest):
    """S5-10: the module and the phenomenon are "ombres portées" in French, never "scintillement"."""

    def test_help_texts(self):
        i18n.set_language("fr")
        page = mock.Mock()
        for key in ("site", "timezone", "layers", "dem", "parameters", "models", "raster", "filter"):
            with self.subTest(key=key):
                title, body = shadow_page.ShadowPage._shadow_help_text(page, key)
                for word in ("scintillement", "intermittent", "CRS", "MDT"):
                    self.assertNotIn(word, title + body)
        _, body = shadow_page.ShadowPage._shadow_help_text(page, "site")
        self.assertIn("calcul des ombres portées", body)
        self.assertIn("42,465 et -2,445", body)

    def test_summary_texts(self):
        i18n.set_language("fr")
        texts, _ = _summary_texts()
        self.assertFalse([t for t in texts if "scintillement" in t])

    def test_page_texts(self):
        page = _page(self, "fr")
        texts = [w.text() for w in page.findChildren((QtWidgets.QLabel, QtWidgets.QPushButton, QtWidgets.QCheckBox))]
        texts += [w.toolTip() for w in page.findChildren(QtWidgets.QWidget)]
        self.assertIn("Ombres portées", texts)
        self.assertIn("Calculer les ombres portées", texts)
        self.assertIn("Créer une carte raster d’ombres portées", texts)
        self.assertFalse([t for t in texts if "scintillement" in t])


class PageTextsTest(_ShadowTest):
    """Sources changed in Spanish ("ráster", decimal comma) and their translations."""

    _EXPECTED = {
        "es": {"sp_latitude": "Latitud del emplazamiento (ej. 42,465 para Logroño)",
               "sp_longitude": "Longitud del emplazamiento (ej. -2,445 para Logroño)",
               "sp_availability": "Fracción del tiempo durante la que el aerogenerador está en funcionamiento (0,97 = 97 %)",
               "chk_create_raster": "Crear mapa ráster de sombras y parpadeo"},
        "en": {"sp_latitude": "Site latitude (e.g. 42.465 for Logroño)",
               "sp_longitude": "Site longitude (e.g. -2.445 for Logroño)",
               "sp_availability": "Fraction of time the wind turbine is operating (0.97 = 97%)",
               "chk_create_raster": "Create shadow flicker raster map"},
        "fr": {"sp_latitude": "Latitude du site (ex. 42,465 pour Logroño)",
               "sp_longitude": "Longitude du site (ex. -2,445 pour Logroño)",
               "sp_availability": "Fraction du temps pendant laquelle l’éolienne est en fonctionnement (0,97 = 97 %)",
               "chk_create_raster": "Créer une carte raster d’ombres portées"},
        "de": {"sp_latitude": "Breitengrad des Standorts (z. B. 42,465 für Logroño)",
               "sp_longitude": "Längengrad des Standorts (z. B. -2,445 für Logroño)",
               "sp_availability": "Anteil der Zeit, in der die Windturbine in Betrieb ist (0,97 = 97 %)",
               "chk_create_raster": "Schattenwurf-Rasterkarte erstellen"},
    }
    _DEM_LABEL = {"es": "Ráster MDT/DEM (opcional):", "en": "DEM raster (optional):", "fr": "Raster MNT (optionnel) :",
                  "de": "DGM-Raster (optional):"}

    def test_texts_in_each_language(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                page = _page(self, lang)
                expected = self._EXPECTED[lang]
                for attr in ("sp_latitude", "sp_longitude", "sp_availability"):
                    self.assertEqual(getattr(page, attr).toolTip(), expected[attr])
                self.assertEqual(page.chk_create_raster.text(), expected["chk_create_raster"])
                self.assertIn(self._DEM_LABEL[lang], [w.text() for w in page.findChildren(QtWidgets.QLabel)])


if __name__ == "__main__":
    unittest.main()
