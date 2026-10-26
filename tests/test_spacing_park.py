# -*- coding: utf-8 -*-
"""The spacing envelopes of Energy are those of the layers chosen in its rows, and of no other layer (#96)."""
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

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer  # noqa: E402
from qgis.gui import QgsMapCanvas  # noqa: E402

from VelantisWind.i18n import apply_i18n, set_language  # noqa: E402
from VelantisWind.spacing_core.controller import SpacingController  # noqa: E402
from VelantisWind.spacing_core import envelope_manager  # noqa: E402
from VelantisWind.spacing_core.envelope_manager import EnvelopeManager, read_overrides, write_overrides  # noqa: E402
from VelantisWind.spacing_core.auto_envelope import ensure_spacing_envelope_for_layer  # noqa: E402
from VelantisWind.spacing_core.config_dialog import SpacingConfigDialog  # noqa: E402
from VelantisWind.spacing_core.geometry import SpacingSpec  # noqa: E402
from VelantisWind.ui_core import layout_sources  # noqa: E402
import tests.test_energy_turbine_layers as dialog_tests  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Turbines 1000 m apart with D = 100 m (7D × 4D envelopes: 700 m × 400 m), so a layout alone has no conflict.
LAYOUT = [(500000.0, 4400000.0), (501000.0, 4400000.0), (502000.0, 4400000.0)]


def turbine_layer(name, dx=0.0, role=True):
    """A turbine layer of the project; ``dx`` shifts the layout, as an alternative of the same site."""
    layer = QgsVectorLayer("Point?crs=EPSG:32630", name, "memory")
    features = []
    for x, y in LAYOUT:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x + dx, y)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    if role:  # what a row of Energy or an import leaves on a layer, and nothing removes
        layer.setCustomProperty("velantis/layer_role", "energy_turbines")
    layer.setCustomProperty("velantis/diameter_m", 100.0)
    layer.setCustomProperty("velantis/spacing_mode", "manual_angle")
    QgsProject.instance().addMapLayer(layer)
    return layer


def statuses_of_layer(envelope_layer):
    return sorted({feature["spacing_status"] for feature in envelope_layer.getFeatures()})


def statuses_of(source):
    """The status of each envelope of ``source``, read from its envelope layer in memory."""
    for layer in QgsProject.instance().mapLayers().values():
        if layer.customProperty("velantis/source_turbine_layer_id") == source.id() and layer.providerType() == "memory":
            return statuses_of_layer(layer)
    return None


def envelopes():
    """The envelope layers of the project, by the name of their source layer."""
    project = QgsProject.instance()
    return sorted(project.mapLayer(layer.customProperty("velantis/source_turbine_layer_id")).name()
                  for layer in project.mapLayers().values() if layer.customProperty("velantis/layer_role") == "spacing_envelopes")


class ParkTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        self.rows = []

    def controller(self, *rows):
        """A controller over an Energy dialog whose rows have ``rows`` as their layers."""
        self.rows[:] = rows
        ctl = types.SimpleNamespace(
            _rows=[{"name": f"T{i + 1}"} for i in range(len(rows))], ed_wrg=mock.Mock(text=lambda: ""),
            _find_interactive_layer_for_row=lambda idx: self.rows[idx],
            _get_interactive_target_layer=lambda allow_auto_pick=True: next((lyr for lyr in self.rows if lyr), None),
            _row_index_for_layer=lambda layer: next((i for i, lyr in enumerate(self.rows) if lyr is layer), None))
        controller = SpacingController(ctl, self.canvas)
        self.addCleanup(controller.teardown)
        controller.panel.set_enabled(True, emit=False)
        return controller

    @staticmethod
    def statuses(controller):
        controller.refresh()
        project = QgsProject.instance()
        return {project.mapLayer(source).name(): sorted(set(by_fid.values()))
                for source, by_fid in controller.manager.last_status.items()}

    def test_an_alternative_with_the_role_is_not_compared(self):
        # The case of the issue: A in the row; B, another alternative 50 m away, was in a row before.
        a, _b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        self.assertEqual(self.statuses(controller), {"A": ["ok"]})
        self.assertEqual(envelopes(), ["A"])

    def test_the_layers_of_several_rows_are_compared(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a, b)
        self.assertEqual(self.statuses(controller), {"A": ["conflict"], "B": ["conflict"]})
        self.assertEqual(envelopes(), ["A", "B"])

    def test_a_layer_in_two_rows_counts_once(self):
        a = turbine_layer("A")
        controller = self.controller(a, a)
        self.assertEqual(self.statuses(controller), {"A": ["ok"]})
        self.assertEqual(envelopes(), ["A"])
        # Once in the selector too: it belongs to its first row.
        controller._refresh_model_selector()
        combo = controller.panel.cb_model
        self.assertEqual([combo.itemData(i) for i in range(combo.count())], [a.id()])

    def test_a_layer_in_two_rows_is_edited_in_its_first_row(self):
        # The first row has no model yet, the second one has: the selector does not show the second row's model, since
        # «Aplicar» writes into the first row, which the layer belongs to.
        a = turbine_layer("A")
        a.setCustomProperty("velantis/model_name", "T2")  # left by the second row, where it was before
        controller = self.controller(a, a)
        controller.ctl._rows[0] = {}
        controller._refresh_model_selector()
        combo = controller.panel.cb_model
        self.assertEqual([combo.itemData(i) for i in range(combo.count())], [a.id()])
        self.assertEqual(combo.itemText(0), "Modelo 1 · A (3)")
        controller.panel.sp_long.setValue(12.0)
        controller._apply_selected_configuration()
        self.assertEqual(controller.ctl._rows[0]["meta"]["spacing_long_d"], 12.0)
        self.assertNotIn("meta", controller.ctl._rows[1])

    def test_the_selector_shows_only_the_rows(self):
        a, _b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        controller._refresh_model_selector()
        combo = controller.panel.cb_model
        self.assertEqual([combo.itemData(i) for i in range(combo.count())], [a.id()])

    def test_a_layer_selected_before_and_out_of_the_rows_is_not_used(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        write = {0: SpacingSpec(9.0, 5.0, 0.0, "manual_screen")}
        write_overrides(b, write)
        controller._selected_layer_id = b.id()
        self.assertIsNot(controller._turbine_layer(), b)
        controller._reset_overrides()
        self.assertEqual(read_overrides(b), write)
        controller._selected_layer_id = b.id()
        self.canvas.setDestinationCrs(b.crs())
        controller._start_define_tool()
        self.assertIsNone(controller._tool)

    def test_a_layout_change_on_a_layer_out_of_the_rows_selects_nothing(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        controller._on_layout_changed(b)
        self.assertNotEqual(controller._selected_layer_id, b.id())
        self.assertEqual(envelopes(), ["A"])

    def test_a_layout_change_does_not_switch_the_envelopes_on(self):
        a = turbine_layer("A")
        controller = self.controller(a)
        controller.panel.set_enabled(False, emit=False)
        controller._on_layout_changed(a)
        self.assertFalse(controller.panel.is_enabled())
        self.assertEqual(envelopes(), [])

    def test_an_ellipse_finished_on_a_layer_that_left_the_rows_is_not_saved(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        self.canvas.setDestinationCrs(a.crs())
        controller._selected_layer_id = a.id()
        controller._start_define_tool()
        self.assertIsNotNone(controller._tool)
        self.rows[0] = b  # the row now has another layer
        controller._on_ellipse_defined(0, SpacingSpec(9.0, 5.0, 0.0, "manual_screen"))
        self.assertEqual(read_overrides(a), {})
        self.assertIsNone(controller._tool)

    def test_the_block_mode_compares_only_with_the_rows(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        controller.panel.cb_validation.setCurrentIndex(controller.panel.cb_validation.findData("block"))
        controller.refresh()
        # 425 m from A's turbines, clear of their 400 m crosswind spacing, and 375 m from one of B's.
        with mock.patch("VelantisWind.spacing_core.controller.iface"):
            self.assertTrue(controller.check_candidate(a, LAYOUT[0][0] + 425.0, LAYOUT[0][1]))
            self.assertFalse(controller.check_candidate(a, LAYOUT[0][0] + 100.0, LAYOUT[0][1]))
        self.assertNotIn(b.id(), {lyr.customProperty("velantis/source_turbine_layer_id")
                                  for lyr in controller.manager.envelope_layers()})

    def test_the_export_takes_only_the_rows(self):
        a, _b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a)
        controller.refresh()
        path = os.path.join(_SETTINGS.name, "envelopes.gpkg")
        with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(path, "")), \
                mock.patch("VelantisWind.spacing_core.controller.iface"):
            controller._export_envelopes()
        exported = QgsVectorLayer(path, "", "ogr")
        self.assertEqual(len(exported.dataProvider().subLayers()), 1)
        self.assertEqual({feature["turbine_layer_id"] for feature in exported.getFeatures()}, {a.id()})

    def test_the_tooltips_say_what_is_compared_in_every_language(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        controller = self.controller(a, b)
        panel = controller.panel
        self.assertIn("filas de Energía", panel.cb_validation.toolTip())
        self.assertIn("filas de Energía", panel.btn_refresh_models.toolTip())
        self.addCleanup(set_language, "es")
        for language, words in (("en", "Energy rows"), ("fr", "lignes d’Énergie"), ("de", "Energie-Zeilen")):
            with self.subTest(language=language):
                set_language(language)
                apply_i18n(panel)
                self.assertIn(words, panel.cb_validation.toolTip())
                self.assertIn(words, panel.btn_refresh_models.toolTip())


class LoadNewLayerTest(dialog_tests.DialogCase):
    """«Cargar nueva capa» in a row of the real Energy dialog."""

    def setUp(self):
        super().setUp()
        # As in a profile where the spacing envelopes were never switched on or off.
        QtCore.QSettings("VelantisWind", "VelantisWindPlugin").remove("spacing/enabled")

    def load(self, idx, points):
        csv = os.path.join(self.folder, f"row{idx}.csv")
        with open(csv, "w") as fh:
            fh.write("x,y\n" + "".join(f"{x},{y}\n" for x, y in points))
        with mock.patch.object(layout_sources, "exec_dialog",
                               side_effect=lambda window: (window.ed_csv.setText(csv), QtWidgets.QDialog.Accepted)[1]):
            self.dialog._load_new_layer(idx)
        return self.dialog._find_interactive_layer_for_row(idx)

    def test_it_compares_with_the_other_rows_and_not_with_layers_out_of_them(self):
        _other = turbine_layer("Other", dx=-50.0)
        self.set_rows(2)
        self.define_row(1, "T2")
        a = self.load(0, LAYOUT)
        self.assertEqual(statuses_of(a), ["ok"])
        b = self.load(1, [(x + 50.0, y) for x, y in LAYOUT])
        self.assertEqual(statuses_of(a), ["conflict"])
        self.assertEqual(statuses_of(b), ["conflict"])
        self.assertNotIn("Other", envelopes())

    def test_switched_off_before_and_with_the_spacing_closed_it_makes_none(self):
        # Switched off, then the spacing controller is closed (as when the Energy dialog closes): the setting, not the
        # controller, says that they are off.
        canvas = QgsMapCanvas()
        self.addCleanup(canvas.deleteLater)
        with mock.patch("VelantisWind.aep_setup_dialog.iface", mock.Mock(mapCanvas=lambda: canvas)):
            spacing = self.dialog._ensure_spacing_controller()
        spacing.panel.set_enabled(False)
        self.dialog._teardown_spacing_controller()
        self.assertIsNone(getattr(self.dialog, "_spacing_notify_layout_changed", None))
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self.load(0, LAYOUT)
        self.assertEqual(envelopes(), [])
        self.assertFalse(settings.value("spacing/enabled", True, type=bool))

    def test_with_the_envelopes_switched_off_it_makes_none(self):
        canvas = QgsMapCanvas()
        self.addCleanup(canvas.deleteLater)
        with mock.patch("VelantisWind.aep_setup_dialog.iface", mock.Mock(mapCanvas=lambda: canvas)):
            spacing = self.dialog._ensure_spacing_controller()
        self.addCleanup(spacing.teardown)
        spacing.panel.set_enabled(False)
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self.load(0, LAYOUT)
        self.assertEqual(envelopes(), [])
        self.assertFalse(spacing.panel.is_enabled())
        self.assertFalse(settings.value("spacing/enabled", False, type=bool))


class ClearingTest(dialog_tests.DialogCase):
    """Closing the project with the envelopes on never removes an envelope QGIS is already removing (#96)."""

    def test_clearing_the_project_with_the_envelopes_on(self):
        for rows in (1, 2):
            with self.subTest(rows=rows):
                canvas = QgsMapCanvas()
                self.addCleanup(canvas.deleteLater)
                with mock.patch("VelantisWind.aep_setup_dialog.iface", mock.Mock(mapCanvas=lambda: canvas)):
                    spacing = self.dialog._ensure_spacing_controller()
                self.set_rows(rows)
                self.define_row(rows - 1, f"T{rows}")
                layers = [turbine_layer("A"), turbine_layer("B", dx=3000.0)][:rows]
                for idx, layer in enumerate(layers):
                    self.select(idx, layer)
                spacing.panel.set_enabled(True)
                self.assertEqual(envelopes(), ["A", "B"][:rows])
                # The rows react to the removal and the envelopes of the first ones leave the park while QGIS removes
                # them: removing them again from there broke QGIS.
                QgsProject.instance().clear()
                self.assertEqual(QgsProject.instance().mapLayers(), {})
                self.assertEqual(envelope_manager._BEING_REMOVED, set())
                spacing.teardown()
                self.dialog._spacing_ctl = None



class ParkChangeTest(dialog_tests.DialogCase):
    """The dialog keeps the envelopes up to date when the park of its rows changes (#96), with the spacing controller
    on, with it off (also after closing its window) and without it."""

    MODES = ("on", "off", "none")

    def setUp(self):
        super().setUp()
        self.set_rows(2)
        self.define_row(1, "T2")
        self.spacing = None

    def start(self, mode):
        if mode == "none":
            return
        canvas = QgsMapCanvas()
        self.addCleanup(canvas.deleteLater)
        with mock.patch("VelantisWind.aep_setup_dialog.iface", mock.Mock(mapCanvas=lambda: canvas)):
            self.spacing = self.dialog._ensure_spacing_controller()
        self.addCleanup(self.spacing.teardown)
        window = SpacingConfigDialog(self.spacing, main_dialog=self.dialog, parent=self.dialog)
        window.show()
        self.spacing.panel.set_enabled(mode == "on")
        window.close()  # the controller outlives its window

    def park(self, mode, *layers):
        """``layers`` in the rows, with their envelopes made as each mode makes them."""
        for idx, layer in enumerate(layers):
            self.select(idx, layer)
        if mode != "on":
            ensure_spacing_envelope_for_layer(layers[0], park_layers=list(layers))

    def each_mode(self, check):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                QgsProject.instance().clear()
                self.set_rows(2)
                self.start(mode)
                check(mode)
                if self.spacing is not None:
                    self.spacing.teardown()
                    self.dialog._spacing_ctl = self.spacing = None

    def test_a_row_left_on_dashes(self):
        def check(mode):
            a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
            self.park(mode, a, b)
            self.assertEqual((statuses_of(a), statuses_of(b)), (["conflict"], ["conflict"]))
            self.select(1, None)
            self.assertIsNone(statuses_of(b))
            self.assertEqual(statuses_of(a), ["ok"])
        self.each_mode(check)

    def test_a_row_given_a_layer_without_an_envelope(self):
        def check(mode):
            a, b, c = turbine_layer("A"), turbine_layer("B", dx=3000.0), turbine_layer("C", dx=50.0)
            self.park(mode, a, b)
            self.assertEqual(statuses_of(a), ["ok"])
            self.select(1, c)
            self.assertIsNone(statuses_of(b))
            self.assertEqual(statuses_of(a), ["conflict"])
            # With the envelopes on, the new layer gets its own; otherwise it counts, but has none.
            self.assertEqual(statuses_of(c), ["conflict"] if mode == "on" else None)
        self.each_mode(check)

    def test_a_row_given_a_layer_whose_envelope_another_manager_made(self):
        def check(mode):
            a, b, d = turbine_layer("A"), turbine_layer("B", dx=3000.0), turbine_layer("D", dx=50.0)
            self.park(mode, a, b)
            ensure_spacing_envelope_for_layer(d)
            self.assertEqual(statuses_of(d), ["ok"])
            self.select(1, d)
            self.assertEqual((statuses_of(a), statuses_of(d)), (["conflict"], ["conflict"]))
            self.select(1, b)
            self.assertIsNone(statuses_of(d))
            self.assertEqual(statuses_of(a), ["ok"])
        self.each_mode(check)

    def test_fewer_rows(self):
        def check(mode):
            a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
            self.park(mode, a, b)
            self.set_rows(1)
            self.assertIsNone(statuses_of(b))
            self.assertEqual(statuses_of(a), ["ok"])
        self.each_mode(check)

    def test_a_turbine_removed_on_the_map(self):
        # With the envelopes on, off or never opened, the existing ones follow an edit on the interactive map, and the
        # envelopes are not switched on.
        from VelantisWind.mapa_interactivo import _TurbineInteractiveTool

        def check(mode):
            a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
            self.park(mode, a, b)
            self.assertEqual(statuses_of(b), ["conflict"])
            settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
            settings.setValue("spacing/enabled", mode == "on")
            canvas = QgsMapCanvas()
            self.addCleanup(canvas.deleteLater)
            canvas.setDestinationCrs(a.crs())
            tool = _TurbineInteractiveTool(self.dialog, canvas)
            event = mock.Mock(button=lambda: QtCore.Qt.RightButton, mapPoint=lambda: QgsPointXY(*LAYOUT[0]))
            with mock.patch("VelantisWind.aep_setup_dialog.iface", dialog_tests.fake_iface(a)), \
                    mock.patch("VelantisWind.mapa_interactivo.iface"):
                tool.canvasPressEvent(event)
            self.assertEqual(a.featureCount(), len(LAYOUT) - 1)
            self.assertEqual(statuses_of(b), ["conflict", "ok"])  # its first turbine has no neighbour any more
            self.assertEqual(settings.value("spacing/enabled", type=bool), mode == "on")
            if self.spacing is not None:
                self.assertEqual(self.spacing.panel.is_enabled(), mode == "on")
        self.each_mode(check)

    def test_fewer_rows_without_a_layer_update_the_selector(self):
        self.start("on")
        a = turbine_layer("A")
        self.select(0, a)
        combo = self.spacing.panel.cb_model
        self.assertEqual(combo.count(), 2)  # the second model, «sin capa»
        self.set_rows(1)
        self.assertEqual([combo.itemData(i) for i in range(combo.count())], [a.id()])

    def test_a_layer_removed_from_the_project(self):
        def check(mode):
            a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
            self.park(mode, a, b)
            QgsProject.instance().removeMapLayer(b.id())
            self.assertEqual(statuses_of(a), ["ok"])
            self.assertEqual(envelopes(), ["A"])
        self.each_mode(check)

    def test_clearing_the_project_with_one_and_two_rows(self):
        def check(mode):
            for rows in (1, 2):
                layers = [turbine_layer("A"), turbine_layer("B", dx=50.0)][:rows]
                self.park(mode, *layers)
                QgsProject.instance().clear()
                self.assertEqual(QgsProject.instance().mapLayers(), {})
        self.each_mode(check)

    def test_a_layer_still_in_another_row_keeps_its_envelope(self):
        def check(mode):
            a, b = turbine_layer("A"), turbine_layer("B", dx=3000.0)
            self.park(mode, a, a)
            self.select(0, b)
            self.assertEqual(statuses_of(a), ["ok"])
        self.each_mode(check)

    def test_an_envelope_removed_by_hand_is_forgotten_with_its_layer(self):
        self.start("on")
        a = turbine_layer("A")
        self.park("on", a)
        envelope = next(layer for layer in QgsProject.instance().mapLayers().values()
                        if layer.customProperty("velantis/source_turbine_layer_id") == a.id())
        QgsProject.instance().removeMapLayer(envelope.id())
        self.select(0, None)
        self.assertNotIn(a.id(), self.spacing.manager._sources)
        self.assertNotIn(a.id(), self.spacing.manager._layers)
        QgsProject.instance().clear()
        self.assertEqual(QgsProject.instance().mapLayers(), {})

    def test_a_saved_envelope_is_kept(self):
        a, b = turbine_layer("A"), turbine_layer("B", dx=50.0)
        self.park("none", a)
        temporary = next(layer for layer in QgsProject.instance().mapLayers().values()
                         if layer.customProperty("velantis/source_turbine_layer_id") == a.id())
        path = os.path.join(self.folder, "saved_envelope.gpkg")
        self.assertEqual(EnvelopeManager._write_layer_to_gpkg(temporary, path, "envelopes", True), (True, ""))
        saved = QgsVectorLayer(path, "Saved envelopes", "ogr")
        for key in temporary.customPropertyKeys():
            saved.setCustomProperty(key, temporary.customProperty(key))
        QgsProject.instance().addMapLayer(saved)
        QgsProject.instance().removeMapLayer(temporary.id())
        a.setCustomProperty("velantis/spacing_envelope_layer_id", saved.id())
        # Out of the rows and back, then compared with B: the file stays as it was, the update goes to a temporary.
        self.select(0, None)
        self.assertIsNotNone(QgsProject.instance().mapLayer(saved.id()))
        with mock.patch("qgis.utils.iface"):
            self.select(0, a)
            self.select(1, b)
        self.assertEqual(statuses_of(a), ["conflict"])
        self.assertEqual(statuses_of_layer(QgsVectorLayer(path, "", "ogr")), ["ok"])
        self.assertIsNotNone(QgsProject.instance().mapLayer(saved.id()))

    def test_a_definition_on_a_removed_row_is_cancelled(self):
        self.start("on")
        a, b = turbine_layer("A"), turbine_layer("B", dx=3000.0)
        self.park("on", a, b)
        self.spacing.canvas.setDestinationCrs(b.crs())
        self.spacing._selected_layer_id = b.id()
        self.spacing._start_define_tool()
        tool = self.spacing._tool
        self.assertIsNotNone(tool)
        self.set_rows(1)
        self.assertIsNone(self.spacing._tool)
        tool._fid, tool._center, tool._state = 0, QgsPointXY(*LAYOUT[0]), dialog_tests.map_tool._ST_MINOR
        tool._finish()
        self.assertEqual(read_overrides(b), {})

    def test_loading_a_layer_with_the_envelopes_off(self):
        self.start("off")
        a = turbine_layer("A")
        self.park("off", a)
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        settings.setValue("spacing/enabled", False)
        loaded = LoadNewLayerTest.load(self, 1, [(x + 50.0, y) for x, y in LAYOUT])
        self.assertEqual(statuses_of(a), ["conflict"])
        self.assertIsNone(statuses_of(loaded))
        self.assertFalse(self.spacing.panel.is_enabled())
        self.assertFalse(settings.value("spacing/enabled", False, type=bool))


if __name__ == "__main__":
    unittest.main()
