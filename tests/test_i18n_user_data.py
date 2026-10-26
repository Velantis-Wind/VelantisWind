# -*- coding: utf-8 -*-
"""The user's data does not go through the translator: a change of language leaves the names in the tables and the
layer combos as they are and does not make them save or rebuild anything, and the last cleanup only goes over
translations."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsProject, QgsVectorLayer  # noqa: E402
from qgis.gui import QgsMapLayerComboBox  # noqa: E402

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.noise_page import NoisePage  # noqa: E402
from VelantisWind.shadow_page import ShadowPage  # noqa: E402
from VelantisWind.hub_dialog import VelantisHubDialog  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Names of the user's that are also texts of the interface.
_NAMES = ("Turbinas", "Parque", "Aerogeneradores")


class UserDataTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.addCleanup(i18n.set_language, "es")

    def test_noise_source_groups_keep_their_names_through_language_changes(self):
        page = NoisePage()
        self.addCleanup(page.deleteLater)
        page._model_rows = [{"name": "Turbinas", "park_name": "Parque", "model_name": "Aerogeneradores", "n_turbines": 2}]
        page._populate_models_table()
        page.tbl_models.item(0, 8).setText("Wind farm=Parque · Model=Aerogeneradores")
        with mock.patch.object(page, "_save_source_group_meta_settings") as save:
            for lang in ("en", "fr", "de", "es"):
                i18n.set_language(lang)
                i18n.apply_i18n(page)
                self.assertEqual([page.tbl_models.item(0, c).text() for c in range(3)], list(_NAMES), lang)
                self.assertEqual(page.tbl_models.item(0, 8).text(), "Wind farm=Parque · Model=Aerogeneradores", lang)
        save.assert_not_called()

    def test_noise_and_shadow_summaries_keep_the_project_and_model_names(self):
        QgsProject.instance().setFileName(os.path.join(_SETTINGS.name, "Turbinas.qgz"))
        for page_cls in (NoisePage, ShadowPage):
            page = page_cls()
            self.addCleanup(page.deleteLater)
            page.lbl_models.setText("Aerogeneradores, Parque")
            page.lbl_receptor_info.setText("Turbinas · 2")
            for lang in ("en", "de"):
                i18n.set_language(lang)
                i18n.apply_i18n(page)
                with self.subTest(page=page_cls.__name__, lang=lang):
                    self.assertEqual(page.lbl_project.text(), "Turbinas")
                    self.assertEqual(page.lbl_models.text(), "Aerogeneradores, Parque")
                    self.assertEqual(page.lbl_receptor_info.text(), "Turbinas · 2")
            i18n.set_language("es")

    def test_the_noise_note_translates_its_labels_around_the_names(self):
        page = NoisePage()
        self.addCleanup(page.deleteLater)
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "Turbinas", "memory")
        layer.setCustomProperty("velantis/park_name", "Parque")
        layer.setCustomProperty("velantis/coords_csv", "x.csv")
        for lang in ("fr", "de"):
            i18n.set_language(lang)
            with mock.patch.object(page, "_iter_model_layers", return_value=[layer]):
                note = page._detect_models(QgsProject.instance())[0]["notes"]
            with self.subTest(lang=lang):
                self.assertTrue(note.startswith(f"{i18n.tr_text('Wind farm')}=Parque · {i18n.tr_text('Model')}=Turbinas"), note)
                self.assertNotIn("Wind farm", note)
                self.assertTrue(note.endswith(i18n.translate_fragment("layout imported from CSV")), note)

    def test_the_noise_curve_preview_translates_its_labels_around_the_file_name(self):
        page = NoisePage()
        self.addCleanup(page.deleteLater)
        page.chk_curve_worst.setChecked(True)
        i18n.set_language("en")
        with mock.patch("VelantisWind.noise_page.load_acoustic_curve_csv", return_value=([5.0], [105.0])), \
                mock.patch("VelantisWind.noise_page.evaluate_acoustic_curve", return_value=105.0):
            self.assertEqual(page._curve_preview_text("/x/Parque.csv"),
                             f"Parque.csv · {i18n.translate_fragment('peor caso')}=105.0 dB(A)")
        with mock.patch("VelantisWind.noise_page.load_acoustic_curve_csv", side_effect=ValueError("Turbinas")):
            self.assertEqual(page._curve_preview_text("/x/Parque.csv"),
                             f"Parque.csv · {i18n.translate_fragment('inválida')} (Turbinas)")
        self.assertNotIn("peor", i18n.translate_fragment("peor caso"))

    def test_fixed_labels_next_to_layer_names_follow_the_language(self):
        from qgis.core import QgsWkbTypes
        page = NoisePage()
        self.addCleanup(page.deleteLater)
        hub = VelantisHubDialog()
        self.addCleanup(hub.deleteLater)
        i18n.set_language("fr")
        self.assertEqual(page._geom_label(QgsWkbTypes.PolygonGeometry), "polygones")
        for settings in (page._qsettings, hub._qsettings):
            settings.setValue("last_wasp_dir", "/x/Parque")
            self.addCleanup(settings.remove, "last_wasp_dir")
        page._populate_context(QgsProject.instance())
        hub._refresh_summary()
        for label in (page.lbl_resource, hub.lbl_resource):
            self.assertEqual(label.text(), f"{i18n.tr_text('WAsP grids:')} /x/Parque")
        self.assertNotIn("WAsP grids", i18n.tr_text("WAsP grids:"))

    def test_noise_acoustic_combo_does_not_fire_while_it_is_translated(self):
        page = NoisePage()
        self.addCleanup(page.deleteLater)
        fired = []
        page.cb_acoustic_mode.currentTextChanged.connect(fired.append)
        page.cb_acoustic_mode.currentIndexChanged.connect(fired.append)
        before = page.cb_acoustic_mode.signalsBlocked()
        i18n.set_language("en")
        i18n.apply_i18n(page)
        self.assertEqual(fired, [])
        self.assertEqual(page.cb_acoustic_mode.signalsBlocked(), before)
        self.assertNotEqual(page.cb_acoustic_mode.currentText(), "LwA fijo por grupo fuente")

    def test_shadow_models_table_keeps_the_name_and_the_notes(self):
        page = ShadowPage()
        self.addCleanup(page.deleteLater)
        page.cb_turbines.addItem("Turbinas", "lyr1")
        page.cb_turbines.setCurrentIndex(page.cb_turbines.count() - 1)
        page._model_rows = [{"layer_id": "lyr1", "name": "Turbinas", "n_turbines": 2}]
        page._populate_models_table()
        page.tbl_models.item(0, 4).setText("Parque")
        for lang in ("en", "de"):
            i18n.set_language(lang)
            i18n.apply_i18n(page)
            self.assertEqual(page.tbl_models.item(0, 0).text(), "Turbinas", lang)
            self.assertEqual(page.tbl_models.item(0, 4).text(), "Parque", lang)

    def test_layer_combos_keep_the_layer_names(self):
        box = QtWidgets.QWidget()
        self.addCleanup(box.deleteLater)
        combo = QtWidgets.QComboBox(box)
        combo.addItem("Turbinas")
        combo.addItem("Turbinas")
        i18n.mark_data(combo, 1)
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "Turbinas", "memory")
        QgsProject.instance().addMapLayer(layer)
        qgis_combo = QgsMapLayerComboBox(box)
        qgis_combo.setLayer(layer)
        i18n.set_language("en")
        i18n.apply_i18n(box)
        self.assertNotEqual(combo.itemText(0), "Turbinas")
        self.assertEqual(combo.itemText(1), "Turbinas")
        self.assertEqual(qgis_combo.currentText(), "Turbinas")

    def test_the_hub_keeps_the_project_name(self):
        QgsProject.instance().setFileName(os.path.join(_SETTINGS.name, "Turbinas.qgz"))
        hub = VelantisHubDialog()
        self.addCleanup(hub.deleteLater)
        self.assertEqual(hub.lbl_project.text(), "Turbinas")
        for lang in ("en", "fr"):
            i18n.set_language(lang)
            i18n.apply_i18n(hub)
            self.assertEqual(hub.lbl_project.text(), "Turbinas", lang)

    def test_a_marked_cell_is_left_alone_and_an_unmarked_one_is_translated(self):
        table = QtWidgets.QTableWidget(1, 2)
        self.addCleanup(table.deleteLater)
        data, text = QtWidgets.QTableWidgetItem("Turbinas"), QtWidgets.QTableWidgetItem("Turbinas")
        i18n.mark_data(data)
        table.setItem(0, 0, data)
        table.setItem(0, 1, text)
        i18n.set_language("en")
        i18n.apply_i18n(table)
        self.assertEqual(table.item(0, 0).text(), "Turbinas")
        self.assertNotEqual(table.item(0, 1).text(), "Turbinas")

    def test_the_last_cleanup_only_goes_over_translations(self):
        i18n.set_language("es")
        self.assertEqual(i18n.tr_text("Source A"), "Source A")
        self.assertEqual(i18n.translate_fragment("Source A"), "Source A")
        # The German entries whose value the cleanup still corrects come out corrected (the table cleanup fixed most).
        i18n._ensure()
        cleaned = {es: i18n._final_language_cleanup(de, "de") for es, de in i18n._STATE["full"]["de"].items()
                   if isinstance(de, str) and i18n._final_language_cleanup(de, "de") != de}
        # Z7 supplies DGM/DOM directly in the receiver-height tooltip; it no longer needs cleanup.
        i18n.set_language("de")
        for es, expected in cleaned.items():
            with self.subTest(es=es[:60]):
                self.assertEqual(i18n.tr_text(es), expected)


if __name__ == "__main__":
    unittest.main()
