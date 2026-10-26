# -*- coding: utf-8 -*-
"""Texts of the spacing envelopes, the interactive map and the CRS helpers in each language (zone Z10 of the
translations): a status or a warning with data (the name of a model or a layer, a path, a number) translates its
template and inserts the data afterwards, so the data never go through the translator, also when the panel or the
dock is translated again; and the Spanish sources are in Spanish («ráster», «clic», no «spacing» nor «OK»)."""
import os
import tempfile
import types
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind import noise_page  # noqa: E402,F401
from VelantisWind import crs_utils, mapa_interactivo_dock  # noqa: E402
from VelantisWind.spacing_core import controller as controller_module  # noqa: E402
from VelantisWind.spacing_core.config_dialog import SpacingConfigDialog  # noqa: E402
from VelantisWind.spacing_core.controller import SpacingController  # noqa: E402
from VelantisWind.spacing_core.envelope_manager import EnvelopeManager  # noqa: E402
from VelantisWind.spacing_core.geometry import SpacingSpec  # noqa: E402
from VelantisWind.spacing_core import map_tool  # noqa: E402
from VelantisWind.spacing_core.panel import VALIDATE_BLOCK  # noqa: E402

_CWD = os.getcwd()
LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Names of the user made of words that the tables translate («Parque» -> «Wind farm», «capas» -> «layers»...).
MODEL = "Parque Norte"
LAYER = "Estelas capas"
PATH = "/tmp/Proyecto parque/Estelas capas.gpkg"
# Turbines 1000 m apart with D = 100 m: 7D × 4D envelopes do not overlap.
LAYOUT = [(500000.0, 4400000.0), (501000.0, 4400000.0), (502000.0, 4400000.0)]


def turbine_layer():
    layer = QgsVectorLayer("Point?crs=EPSG:32630", LAYER, "memory")
    features = []
    for x, y in LAYOUT:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.setCustomProperty("velantis/model_name", MODEL)
    layer.setCustomProperty("velantis/diameter_m", 100.0)
    layer.setCustomProperty("velantis/spacing_mode", "manual_angle")
    QgsProject.instance().addMapLayer(layer)
    return layer


EXPECTED = {
    "applied": {
        "es": "Configuración aplicada al modelo «Parque Norte» · 7D×4D · capa de elipses actualizada.",
        "en": "Configuration applied to model “Parque Norte” · 7D×4D · ellipse layer updated.",
        "fr": "Configuration appliquée au modèle « Parque Norte » · 7D×4D · couche d’ellipses mise à jour.",
        "de": "Konfiguration auf Modell „Parque Norte“ angewendet · 7D×4D · Ellipsen-Layer aktualisiert.",
    },
    "saved": {
        "es": "Configuración guardada para el modelo «Parque Norte» · se utilizará automáticamente al elegir su capa de "
              "turbinas.",
        "en": "Configuration saved for model “Parque Norte” · it will be used automatically when its turbine layer is "
              "chosen.",
        "fr": "Configuration enregistrée pour le modèle « Parque Norte » · elle sera utilisée automatiquement lorsque sa "
              "couche d’éoliennes sera choisie.",
        "de": "Konfiguration für Modell „Parque Norte“ gespeichert · sie wird automatisch verwendet, sobald sein "
              "Windturbinen-Layer gewählt ist.",
    },
    "summary": {
        "es": "1 modelo · 3 envolvente(s) · dimensiones: 7D×4D · sector más energético: 270° · ⚠ 1 conflicto(s) de "
              "separación · 1 cerca del límite",
        "en": "1 model · 3 envelope(s) · dimensions: 7D×4D · most energetic sector: 270° · ⚠ 1 spacing conflict(s) · "
              "1 near the limit",
        "fr": "1 modèle · 3 enveloppe(s) · dimensions : 7D×4D · secteur le plus énergétique : 270° · ⚠ 1 conflit(s) "
              "d’espacement · 1 proche(s) de la limite",
        "de": "1 Modell · 3 Hülle(n) · Abmessungen: 7D×4D · energiereichster Sektor: 270° · ⚠ 1 Abstandskonflikt(e) · "
              "1 nahe am Grenzwert",
    },
    "summary_warning": {
        "es": "La disposición multimodelo incumple la separación mínima en 1 turbina(s).",
        "en": "The multi-model layout violates the minimum spacing at 1 turbine(s).",
        "fr": "La disposition multimodèle ne respecte pas l’espacement minimal pour 1 éolienne(s).",
        "de": "Das Mehrmodell-Layout verletzt den Mindestabstand bei 1 Windturbine(n).",
    },
    "exception": {
        "es": "Excepción guardada para la turbina 2 del modelo «Parque Norte».",
        "en": "Exception saved for turbine 2 of model “Parque Norte”.",
        "fr": "Exception enregistrée pour l’éolienne 2 du modèle « Parque Norte ».",
        "de": "Ausnahme für Windturbine 2 des Modells „Parque Norte“ gespeichert.",
    },
    "reset": {
        "es": "Excepciones del modelo «Parque Norte» eliminadas · usando su plantilla de modelo.",
        "en": "Exceptions of model “Parque Norte” cleared · using its model template.",
        "fr": "Exceptions du modèle « Parque Norte » supprimées · utilisation de son gabarit de modèle.",
        "de": "Ausnahmen des Modells „Parque Norte“ gelöscht · die Modellvorlage wird verwendet.",
    },
    "blocked": {
        "es": "La turbina invade la envolvente de una turbina del modelo «Parque Norte» · inserción bloqueada.",
        "en": "The turbine intrudes into the envelope of a turbine of model “Parque Norte” · insertion blocked.",
        "fr": "L’éolienne empiète sur l’enveloppe d’une éolienne du modèle « Parque Norte » · insertion bloquée.",
        "de": "Die Windturbine ragt in die Hülle einer Windturbine des Modells „Parque Norte“ hinein · Einfügen "
              "blockiert.",
    },
    "exported_status": {
        "es": f"3 capa(s) de modelo exportadas: {PATH}",
        "en": f"3 model layer(s) exported: {PATH}",
        "fr": f"3 couche(s) de modèle exportée(s) : {PATH}",
        "de": f"3 Modell-Layer exportiert: {PATH}",
    },
    "exported_bar": {
        "es": f"Se exportaron 3 capas de modelo a {PATH}",
        "en": f"Exported 3 model layers to {PATH}",
        "fr": f"3 couches de modèle exportées vers {PATH}",
        "de": f"3 Modell-Layer nach {PATH} exportiert",
    },
    "export_failed": {
        "es": "No se pudo exportar: Parque capas",
        "en": "Could not export: Parque capas",
        "fr": "Impossible d’exporter : Parque capas",
        "de": "Export fehlgeschlagen: Parque capas",
    },
    "model_info": {
        "es": "Parque Norte · D=100 m · 3 turbina(s)",
        "en": "Parque Norte · D=100 m · 3 turbine(s)",
        "fr": "Parque Norte · D=100 m · 3 éolienne(s)",
        "de": "Parque Norte · D=100 m · 3 Windturbine(n)",
    },
    "major": {
        "es": "Eje mayor · Ángulo: 270.0° · Long: 7.0 D (700 m) · Ctrl=ajuste a 5°/sector, Mayús=ajuste a 0,5D",
        "en": "Major axis · Angle: 270.0° · Downwind: 7.0 D (700 m) · Ctrl=snap to 5°/sector, Shift=snap to 0.5D",
        "fr": "Grand axe · Angle : 270.0° · Long. : 7.0 D (700 m) · Ctrl = accrochage à 5°/secteur, Maj = accrochage à "
              "0,5D",
        "de": "Hauptachse · Winkel: 270.0° · Längs: 7.0 D (700 m) · Strg=Einrasten auf 5°/Sektor, Umschalt=Einrasten auf "
              "0,5D",
    },
    "minor": {
        "es": "Eje menor · Ángulo: 270.0° · Long: 7.0 D (700 m) · Trans: 4.0 D (400 m) · Clic para confirmar",
        "en": "Minor axis · Angle: 270.0° · Downwind: 7.0 D (700 m) · Crosswind: 4.0 D (400 m) · Click to confirm",
        "fr": "Petit axe · Angle : 270.0° · Long. : 7.0 D (700 m) · Trans. : 4.0 D (400 m) · Cliquez pour confirmer",
        "de": "Nebenachse · Winkel: 270.0° · Längs: 7.0 D (700 m) · Quer: 4.0 D (400 m) · Klicken zum Bestätigen",
    },
    "legend": {
        "es": ["Sin conflicto", "Cerca del límite", "Conflicto de separación"],
        "en": ["No conflict", "Near the limit", "Spacing conflict"],
        "fr": ["Aucun conflit", "Proche de la limite", "Conflit d’espacement"],
        "de": ["Kein Konflikt", "Nahe am Grenzwert", "Abstandskonflikt"],
    },
    "hint": {
        "es": "Clic izq: añadir · Clic der: borrar · ESC: salir",
        "en": "Left click: add · Right click: delete · ESC: exit",
        "fr": "Clic gauche : ajouter · clic droit : supprimer · Échap : quitter",
        "de": "Linksklick: hinzufügen · Rechtsklick: löschen · ESC: beenden",
    },
    "ti_group": {
        "es": "TI ambiente (ráster)", "en": "Ambient TI (raster)", "fr": "TI ambiante (raster)", "de": "Umgebungs-TI (Raster)",
    },
    "ti_pick": {
        "es": "Elegir ráster TI…", "en": "Choose TI raster…", "fr": "Choisir un raster TI…", "de": "TI-Raster wählen…",
    },
    "no_ti": {"es": "Sin ráster TI", "en": "No TI raster", "fr": "Aucun raster TI", "de": "Kein TI-Raster"},
    "calc_tip": {
        "es": "Calcula el AEP con las capas de turbinas elegidas en las filas y sus modelos.",
        "en": "Calculates the AEP with the turbine layers chosen in the rows and their models.",
        "fr": "Calcule l’AEP avec les couches d’éoliennes choisies sur les lignes et leurs modèles.",
        "de": "Berechnet die AEP mit den in den Zeilen gewählten Windturbinen-Layern und ihren Modellen.",
    },
    "no_crs": {
        "es": "No se puede crear una capa georreferenciada sin un CRS válido: Estelas capas",
        "en": "Cannot create a georeferenced layer without a valid CRS: Estelas capas",
        "fr": "Impossible de créer une couche géoréférencée sans SCR valide : Estelas capas",
        "de": "Ohne gültiges KBS kann kein georeferenzierter Layer erstellt werden: Estelas capas",
    },
}


class SpacingTextsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.addCleanup(i18n.set_language, "es")
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        bar = mock.patch.object(controller_module, "iface")
        self.iface = bar.start()
        self.addCleanup(bar.stop)

    def controller(self, lang, layer=None):
        i18n.set_language(lang)
        self.layer = turbine_layer() if layer is None else layer
        rows = [self.layer]
        ctl = types.SimpleNamespace(
            _rows=[{"name": MODEL}], ed_wrg=mock.Mock(text=lambda: ""),
            _find_interactive_layer_for_row=lambda idx: rows[idx],
            _get_interactive_target_layer=lambda allow_auto_pick=True: rows[0],
            _row_index_for_layer=lambda layer: 0 if layer is rows[0] else None)
        controller = SpacingController(ctl, self.canvas)
        self.addCleanup(controller.teardown)
        controller.panel.set_enabled(True, emit=False)
        return controller

    def bar_texts(self, kind):
        return [c.args[1] for c in getattr(self.iface.messageBar(), kind).call_args_list]

    def check(self, controller, key, lang):
        """The status shown, and the same after the panel is translated again (the configuration dialog does it)."""
        self.assertEqual(controller.panel.lbl_status.text(), EXPECTED[key][lang])
        SpacingConfigDialog(controller).close()
        self.assertEqual(controller.panel.lbl_status.text(), EXPECTED[key][lang])

    def test_configuration_applied_and_saved(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                controller._apply_selected_configuration()
                self.check(controller, "applied", lang)
                # A model of a row still without a layer keeps its configuration in the row.
                controller._selected_layer_id = "row:0"
                controller._turbine_layer = lambda: None
                controller._apply_selected_configuration()
                self.assertEqual(controller.panel.lbl_status.text(), EXPECTED["saved"][lang])

    def test_summary_and_its_warning(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                self.iface.reset_mock()
                controller._summarize({"x": {1: "conflict", 2: "near", 3: "ok"}}, 270.0, controller._fallback_spec)
                self.check(controller, "summary", lang)
                self.assertEqual(self.bar_texts("pushWarning"), [EXPECTED["summary_warning"][lang]])

    def test_exception_saved_and_reset(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                controller._tool = types.SimpleNamespace(layer=self.layer)
                with mock.patch.object(controller, "_can_define_on", return_value=True):
                    controller._on_ellipse_defined(2, SpacingSpec(8.0, 5.0, 30.0, "manual_screen", "elliptical"))
                controller._tool = None
                self.check(controller, "exception", lang)
                controller._reset_overrides()
                self.check(controller, "reset", lang)

    def test_insertion_blocked(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                controller.panel.cb_validation.setCurrentIndex(controller.panel.cb_validation.findData(VALIDATE_BLOCK))
                controller.refresh()
                self.iface.reset_mock()
                x, y = LAYOUT[0]
                self.assertFalse(controller.check_candidate(self.layer, x + 10.0, y))
                self.assertEqual(self.bar_texts("pushWarning"), [EXPECTED["blocked"][lang]])

    def test_export(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                self.iface.reset_mock()
                layers = [mock.Mock(featureCount=lambda: 3) for _ in range(3)]
                with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(PATH, "")), \
                        mock.patch.object(controller.manager, "envelope_layers", return_value=layers), \
                        mock.patch.object(controller.manager, "export_all_to_gpkg", return_value=(True, "", len(layers))):
                    controller._export_envelopes()
                self.check(controller, "exported_status", lang)
                self.assertEqual(self.bar_texts("pushSuccess"), [EXPECTED["exported_bar"][lang]])
                with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(PATH, "")), \
                        mock.patch.object(controller.manager, "envelope_layers", return_value=layers), \
                        mock.patch.object(controller.manager, "export_all_to_gpkg", return_value=(False, "Parque capas", 0)):
                    controller._export_envelopes()
                self.check(controller, "export_failed", lang)

    def test_model_selector_and_info_keep_the_names(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                controller = self.controller(lang)
                SpacingConfigDialog(controller).close()
                self.assertEqual(controller.panel.lbl_model_info.text(), EXPECTED["model_info"][lang])
                self.assertEqual(controller.panel.cb_model.itemText(0), f"{MODEL} · {LAYER} (3)")

    def test_define_tool_status(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                shown = []
                tool = map_tool.EllipseDefineTool(
                    self.canvas, turbine_layer(), 100.0, SpacingSpec(7.0, 4.0, 270.0, "manual_screen", "elliptical"),
                    on_defined=lambda *_a: None, on_status=shown.append)
                for state, key in ((map_tool._ST_MAJOR, "major"), (map_tool._ST_MINOR, "minor")):
                    tool._state = state
                    tool._push_status()
                    self.assertEqual(shown[-1], EXPECTED[key][lang])

    def test_envelope_legend(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                layer = QgsVectorLayer("Polygon?crs=EPSG:32630&field=spacing_status:string", "e", "memory")
                EnvelopeManager()._apply_symbology(layer)
                self.assertEqual([c.label() for c in layer.renderer().categories()], EXPECTED["legend"][lang])

    def test_layer_without_crs(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                with self.assertRaises(ValueError) as raised:
                    crs_utils.memory_layer_with_crs("Point", LAYER, QgsCoordinateReferenceSystem())
                self.assertEqual(str(raised.exception), EXPECTED["no_crs"][lang])


class InteractiveDockTextsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.addCleanup(i18n.set_language, "es")
        self.parent = QtWidgets.QMainWindow()
        self.addCleanup(self.parent.deleteLater)

    def dock(self, lang, ti=""):
        i18n.set_language(lang)
        layer = turbine_layer()
        ed_ti, ed_heights = QtWidgets.QLineEdit(ti), QtWidgets.QLineEdit()
        ctl = types.SimpleNamespace(
            objectName=lambda: "ctl", ed_wrg_ti=ed_ti, ed_wrg_ti_heights=ed_heights, _rows=[{"name": MODEL}],
            _find_interactive_layer_for_row=lambda idx: layer, _collect_layer_points_for_row=lambda idx: LAYOUT,
            _get_interactive_target_layer=lambda: layer, _dirty_turbine_layer_ids={layer.id()},
            _candidate_turbine_layers_for_edit=lambda: [{"layer_id": layer.id(), "row_index": 0, "model_name": MODEL,
                                                         "n_points": 3, "layer_name": LAYER, "active": True}],
            _ensure_spacing_controller=lambda: None)
        with mock.patch.object(mapa_interactivo_dock, "SpacingController", None):
            dock = mapa_interactivo_dock.InteractiveMapDock(ctl, parent=self.parent)
        self.addCleanup(dock._teardown)
        return dock

    def test_fixed_texts(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                dock = self.dock(lang)
                self.assertEqual(dock.lbl_hint.text(), EXPECTED["hint"][lang])
                self.assertEqual(dock.btn_ti_pick.text(), EXPECTED["ti_pick"][lang])
                self.assertIn(EXPECTED["ti_group"][lang], [g.title() for g in dock.findChildren(QtWidgets.QGroupBox)])
                self.assertIn(EXPECTED["no_ti"][lang], dock.lbl_ti_status.text())
                self.assertEqual(dock.btn_calc.toolTip(), EXPECTED["calc_tip"][lang])

    def test_names_survive_a_new_translation(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                dock = self.dock(lang, ti="/tmp/Estelas/capa estelas.asc")
                i18n.apply_i18n(dock)
                self.assertEqual(dock.lbl_ti_status.text(), "<b>capa estelas.asc</b>")
                self.assertTrue(dock.lbl_layer_status.text().startswith(f"<b>{LAYER}</b>"))
                self.assertTrue(dock.cb_edit_layer.itemText(0).startswith(f"M1 · {MODEL} | 3 "), dock.cb_edit_layer.itemText(0))
                self.assertIn(f"| {LAYER} · ", dock.cb_edit_layer.itemText(0))


if __name__ == "__main__":
    unittest.main()
