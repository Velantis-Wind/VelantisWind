# -*- coding: utf-8 -*-
"""The energy dialog computes with the layer chosen in each row's «Capa de turbinas» selector, and only with it."""
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

from qgis.core import (  # noqa: E402
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeature,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapCanvas  # noqa: E402

from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.energy_core import dialog_controller  # noqa: E402
from VelantisWind.mapa_interactivo import _TurbineInteractiveTool  # noqa: E402
from VelantisWind.mapa_interactivo_dock import InteractiveMapDock  # noqa: E402
from VelantisWind.spacing_core import map_tool  # noqa: E402
from VelantisWind.spacing_core.envelope_manager import read_overrides  # noqa: E402
from VelantisWind.spacing_core.auto_envelope import ensure_spacing_envelope_for_layer  # noqa: E402
from VelantisWind.ui_core import layout_sources  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


A = [(500000.0, 4400000.0), (500500.0, 4400000.0)]
B = [(501000.0, 4401000.0), (501500.0, 4401000.0), (502000.0, 4401000.0)]
# A projected CRS in metres without an authority id.
CUSTOM = "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"


def point_layer(name, points, crs="EPSG:32630", geometry="Point"):
    """A memory layer added to the project; each item of ``points`` is (x, y) or a ready QgsGeometry."""
    layer = QgsVectorLayer(f"{geometry}?crs={crs}", name, "memory")
    features = []
    for item in points:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(item if isinstance(item, QgsGeometry) else QgsGeometry.fromPointXY(QgsPointXY(*item)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    return layer


def fake_iface(active=None):
    """QGIS's interface with ``active`` as the active layer and no map canvas."""
    return mock.Mock(activeLayer=lambda: active, mapCanvas=lambda: None, mainWindow=lambda: None)


def points_of(layer):
    return [(f.geometry().asPoint().x(), f.geometry().asPoint().y()) for f in layer.getFeatures()]


def to_project(points, crs):
    transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(crs), QgsProject.instance().crs(), QgsProject.instance())
    return [(p.x(), p.y()) for p in (transform.transform(QgsPointXY(x, y)) for x, y in points)]


class _NoLayerWindow(AssertionError):
    pass


class DialogCase(unittest.TestCase):
    """A real energy dialog over an empty project, with every blocking window simulated."""

    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.wrg = os.path.join(folder.name, "resource.wrg")
        open(self.wrg, "w").close()
        self.shown = []
        patches = [
            mock.patch.object(QtWidgets.QMessageBox, name, side_effect=lambda *a, _n=name: self.shown.append((_n, a[2])))
            for name in ("information", "warning", "critical")
        ]
        # A layer-selection window would be a QDialog run with exec_: none may open.
        patches.append(mock.patch.object(QtWidgets.QDialog, "exec_", side_effect=_NoLayerWindow("a window was opened")))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = AEPSetupDialog()
        self.addCleanup(self.dialog.deleteLater)
        # The dialog outlives the test (no event loop to delete it): it must not react to later projects, neither does
        # it nor its row selectors, which would follow the removals of the next project on their own.
        self.addCleanup(QgsProject.instance().layersWillBeRemoved.disconnect, self.dialog._on_project_layers_will_be_removed)
        self.addCleanup(lambda: [row["layer_cb"].blockSignals(True) for row in self.dialog._rows])
        self.dialog.ed_wrg.setText(self.wrg)
        self.define_row(0, "T1")

    def define_row(self, idx, name, meta=None):
        row = self.dialog._rows[idx]
        row["wt"], row["name"], row["meta"] = object(), name, dict(meta or {})

    def select(self, idx, layer):
        self.dialog._rows[idx]["layer_cb"].setLayer(layer)

    def selector(self, idx):
        return self.dialog._rows[idx]["layer_cb"]

    def set_rows(self, n):
        self.dialog.sp_n.setValue(n)

    def aep_models(self, run=None):
        """The models that «Calcular AEP» (or ``run``) would send to the calculation."""
        configs = []
        with mock.patch.object(dialog_controller, "_validate_before_run", side_effect=lambda d, c: configs.append(c) or False):
            (run or self.dialog._run_compute_and_update)()
        self.assertEqual(len(configs), 1, self.shown)
        return configs[0].models

    def raster_models(self):
        sent = []
        with mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(300, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a: (a[3][0], True)), \
                mock.patch("VelantisWind.wake_core.controller.start_wake_raster_from_dialog",
                           side_effect=lambda dialog, **kw: sent.append(kw["models"])):
            self.dialog._run_plot_wakes()
        self.assertEqual(len(sent), 1, self.shown)
        return sent[0]

    def assertNothingComputed(self, *texts):
        # The raster's resolution windows are answered, so that a raster wrongly let through reaches the assertion.
        with mock.patch.object(dialog_controller, "_validate_before_run") as validate, \
                mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(300, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a: (a[3][0], True)), \
                mock.patch("VelantisWind.wake_core.controller.start_wake_raster_from_dialog") as start:
            self.dialog._run_compute_and_update()
            self.dialog._run_plot_wakes()
        validate.assert_not_called()
        start.assert_not_called()
        self.assertEqual([kind for kind, _ in self.shown], ["warning", "warning"])
        for _kind, text in self.shown:
            for expected in texts:
                self.assertIn(expected, text)

    def compute(self):
        """«Calcular AEP» with a simulated engine whose results sit on the computed points; the layers are written."""
        def engine(models, **_kw):
            table = [{"model": m["name"], "x": x, "y": y, "aep_mwh": 1000.0} for m in models for x, y in m["coords_xy"]]
            return {"per_turbine_table": table, "aep_wake_MWh": 1.0, "aep_free_MWh": 1.0, "wake_loss_MWh": 0.0, "wake_loss_pct": 0.0}

        bar = []
        with mock.patch("VelantisWind.ag_core.aep_compute.compute_aep_from_ui", side_effect=lambda **kw: engine(**kw)), \
                mock.patch("VelantisWind.energy_core.runner.validate_energy_config", return_value=[]), \
                mock.patch.object(dialog_controller, "_validate_before_run", return_value=True), \
                mock.patch.object(dialog_controller, "create_progress_dialog"), \
                mock.patch.object(dialog_controller, "close_progress_dialog"), \
                mock.patch.object(dialog_controller, "export_results_from_dialog"), \
                mock.patch.object(dialog_controller, "show_message_bar", side_effect=lambda *a, **k: bar.append(a[1])), \
                mock.patch.object(dialog_controller, "_show_results_dialog"):
            self.dialog._run_compute_and_update()
        return bar


class NoLayerSelectionWindowTest(DialogCase):
    def setUp(self):
        super().setUp()
        self.layer = point_layer("T1 (CSV)", A)
        self.select(0, self.layer)

    def test_aep_uses_the_row_layer(self):
        models = self.aep_models()
        self.assertEqual([m.coords_xy for m in models], [A])

    def test_recalculate_from_the_interactive_map_uses_the_row_layer(self):
        models = self.aep_models(self.dialog._recalc_aep_from_interactive)
        self.assertEqual([m.coords_xy for m in models], [A])

    def test_raster_uses_the_row_layer(self):
        models = self.raster_models()
        self.assertEqual([(m["coords_xy"], m["source_layer_id"], m["source_layer_name"]) for m in models],
                         [(A, self.layer.id(), "T1 (CSV)")])

    def test_aep_rows_carry_their_layer(self):
        from VelantisWind.energy_core.dialog_state import build_energy_dialog_state

        models = build_energy_dialog_state(self.dialog, "EPSG:32630").models
        self.assertEqual([(m["source_layer_id"], m["source_layer_name"]) for m in models], [(self.layer.id(), "T1 (CSV)")])

    def test_another_layer_of_the_model_is_not_sent(self):
        point_layer("Modelo 1 (CSV)", B)
        self.assertEqual([m.coords_xy for m in self.aep_models()], [A])
        self.assertEqual([(m["coords_xy"], m["source_layer_id"]) for m in self.raster_models()], [(A, self.layer.id())])


LONLAT = [(-3.0, 40.0), (-2.99, 40.01)]


class LayerReadingTest(DialogCase):
    """Each row's layer is read in the project CRS, or the calculation stops saying which row and layer fail."""

    def read(self, layer):
        self.select(0, layer)
        return self.dialog._collect_layer_points_for_row(0)

    def assertReadError(self, layer, *texts):
        from VelantisWind.energy_core.dialog_state import DialogStateError

        with self.assertRaises(DialogStateError) as caught:
            self.read(layer)
        for text in ("Modelo 1", f"«{layer.name()}»") + texts:
            self.assertIn(text, caught.exception.message)

    def assertPointsAlmostEqual(self, got, expected):
        self.assertEqual(len(got), len(expected))
        for (x, y), (ex, ey) in zip(got, expected):
            self.assertAlmostEqual(x, ex, delta=1e-6)
            self.assertAlmostEqual(y, ey, delta=1e-6)

    def test_layer_in_degrees_is_transformed_to_the_project_crs(self):
        layer = point_layer("T1 (CSV)", LONLAT, crs="EPSG:4326")
        points = self.read(layer)
        self.assertPointsAlmostEqual(points, to_project(LONLAT, "EPSG:4326"))
        self.assertGreater(points[0][0], 400000.0)

    def test_layer_in_the_project_crs_keeps_its_points(self):
        self.assertEqual(self.read(point_layer("T1 (CSV)", A)), A)

    def test_single_part_multipoint_reads_as_a_point(self):
        single = QgsGeometry.fromMultiPointXY([QgsPointXY(*A[0])])
        self.assertEqual(self.read(point_layer("T1 (CSV)", [single], geometry="MultiPoint")), [A[0]])

    def test_unreadable_features_stop_the_reading_with_their_count(self):
        two_parts = QgsGeometry.fromMultiPointXY([QgsPointXY(*A[0]), QgsPointXY(*A[1])])
        layer = point_layer("T1 (CSV)", [two_parts, QgsGeometry(), QgsGeometry.fromMultiPointXY([QgsPointXY(*B[0])])],
                            geometry="MultiPoint")
        self.assertReadError(layer, "2 entidad(es)")

    def test_layer_without_a_valid_crs_stops_the_reading(self):
        layer = point_layer("T1 (CSV)", A, crs="")
        self.assertFalse(layer.crs().isValid())
        self.assertReadError(layer, "sistema de coordenadas válido")

    def test_failed_transformation_stops_the_reading(self):
        layer = point_layer("T1 (CSV)", LONLAT, crs="EPSG:4326")
        failing = mock.Mock()
        failing.return_value.transform.side_effect = QgsCsException("out of bounds")
        with mock.patch("VelantisWind.ag_core.qgis_io.layers.QgsCoordinateTransform", failing):
            self.assertReadError(layer, "out of bounds")

    def test_aep_and_raster_show_the_error_and_compute_nothing(self):
        self.select(0, point_layer("T1 (CSV)", [QgsGeometry()], geometry="MultiPoint"))
        self.assertNothingComputed("Modelo 1, capa «T1 (CSV)»: 1 entidad(es)")

    def test_raster_takes_a_layer_in_degrees_through_the_real_controller(self):
        layer = point_layer("T1 (CSV)", LONLAT, crs="EPSG:4326")
        self.select(0, layer)
        sent = []

        def start(config, **callbacks):
            sent.append(config)
            self.addCleanup(callbacks["on_finished"], False, {}, "cancelled")
            return mock.Mock()

        with mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(300, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a: (a[3][0], True)), \
                mock.patch("VelantisWind.wake_core.controller.start_wake_raster_task",
                           side_effect=start):
            self.dialog._run_plot_wakes()
        self.assertEqual(self.shown, [])
        [model] = sent[0].models
        self.assertEqual(model["source_layer_id"], layer.id())
        self.assertPointsAlmostEqual(model["coords_xy"], to_project(LONLAT, "EPSG:4326"))


class ScenarioSnapshotsTest(DialogCase):
    def store(self, slot):
        with mock.patch.object(QtWidgets.QInputDialog, "getText", return_value=(slot, True)):
            self.dialog._store_current_scenario(slot)

    def test_a_and_b_keep_their_own_results(self):
        first, second = point_layer("A", A), point_layer("B", B)
        self.select(0, first)
        self.compute()
        self.store("A")
        self.select(0, second)
        self.compute()
        self.store("B")
        points = {slot: [(r["x"], r["y"]) for r in getattr(self.dialog, f"_scenario_{slot.lower()}")["result"]["per_turbine_table"]]
                  for slot in "AB"}
        self.assertEqual(points, {"A": A, "B": B})
        self.assertEqual([f["aep_mwh"] for f in second.getFeatures()], [1000.0] * 3)


class ExportEditedLayoutTest(DialogCase):
    def test_proposed_name_comes_from_the_layer(self):
        layer = point_layer("My layout", A)
        self.select(0, layer)
        self.dialog._mark_turbines_layer_dirty(layer)
        self.dialog._last_csv_dir = self.folder
        with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=("", "")) as ask:
            self.dialog._export_edited_layouts_dialog()
        self.assertEqual(ask.call_args[0][2], os.path.join(self.folder, "My layout_edited.csv"))

    def export(self, layer):
        self.select(0, layer)
        self.dialog._mark_turbines_layer_dirty(layer)
        path = os.path.join(self.folder, "out.csv")
        with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(path, "")):
            self.dialog._export_edited_layouts_dialog()
        return path

    def test_every_point_is_exported(self):
        path = self.export(point_layer("My layout", A))
        with open(path) as fh:
            self.assertEqual(fh.read().splitlines(), ["x,y"] + [f"{x:.3f},{y:.3f}" for x, y in A])

    def test_a_feature_without_a_single_point_exports_nothing(self):
        # A multipoint of two parts used to be skipped and the CSV came out short, announced as exported.
        two_parts = QgsGeometry.fromMultiPointXY([QgsPointXY(*A[0]), QgsPointXY(*A[1])])
        layer = point_layer("Parts", [QgsGeometry.fromMultiPointXY([QgsPointXY(*B[0])]), two_parts], geometry="MultiPoint")
        path = self.export(layer)
        self.assertFalse(os.path.exists(path))
        self.assertIn("1 entidad(es) de la capa no tienen un único punto", self.shown[-1][1])
        self.assertTrue(self.dialog._layer_is_dirty_for_row(0))


class InteractivePanelCalculateButtonTest(DialogCase):
    def dock(self):
        self.window = QtWidgets.QMainWindow()
        dock = InteractiveMapDock(self.dialog, parent=self.window)
        self.addCleanup(dock._teardown)
        return dock

    def test_enabled_with_a_row_layer_with_points(self):
        self.select(0, point_layer("T1 (CSV)", A))
        dock = self.dock()
        self.assertTrue(dock.btn_calc.isEnabled())
        self.assertIn("2", dock.lbl_layer_status.text())

    def test_disabled_with_an_empty_row_layer(self):
        self.select(0, point_layer("T1 (CSV)", []))
        point_layer("Other", A)
        dock = self.dock()
        self.assertFalse(dock.btn_calc.isEnabled())
        self.assertIn("T1 (CSV)", dock.lbl_layer_status.text())

    def test_disabled_without_a_row_layer_and_asks_to_choose_one(self):
        point_layer("Other", A)
        dock = self.dock()
        self.assertFalse(dock.btn_calc.isEnabled())
        self.assertIn("Ninguna fila tiene capa de turbinas.", dock.lbl_layer_status.text())
        self.assertIn("selector «Capa de turbinas»", dock.lbl_layer_status.text())

    def test_disabled_while_another_row_has_no_layer_with_points(self):
        # The AEP and the raster use every row and stop at the first one without a layer with turbines.
        self.set_rows(2)
        self.select(0, point_layer("Mine", A))
        empty = point_layer("Other", [])
        self.select(1, empty)
        dock = self.dock()
        self.assertFalse(dock.btn_calc.isEnabled())
        self.assertFalse(dock.btn_plot_wakes.isEnabled())
        self.assertIn("Modelos sin capa con turbinas: 2.", dock.lbl_layer_status.text())
        # A turbine added with QGIS's own editing, not from the panel: the status follows without a manual refresh.
        empty.startEditing()
        feature = QgsFeature(empty.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*B[0])))
        empty.addFeature(feature)
        empty.commitChanges()
        QtWidgets.QApplication.processEvents()
        self.assertTrue(dock.btn_calc.isEnabled())
        self.assertTrue(dock.btn_plot_wakes.isEnabled())
        self.assertNotIn("Modelos sin capa", dock.lbl_layer_status.text())

    def test_correcting_a_row_layer_crs_enables_it(self):
        self.set_rows(2)
        self.select(0, point_layer("Mine", A))
        no_crs = point_layer("No CRS", B, crs="")
        self.assertFalse(no_crs.crs().isValid())
        self.select(1, no_crs)
        dock = self.dock()
        self.assertFalse(dock.btn_calc.isEnabled())
        no_crs.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        QtWidgets.QApplication.processEvents()
        self.assertTrue(dock.btn_calc.isEnabled())

    def test_a_layer_that_leaves_the_rows_is_no_longer_followed(self):
        first, second = point_layer("First", A), point_layer("Second", B)
        self.select(0, first)
        # The dialog's own panel, refreshed when a row changes its layer.
        self.dialog._interactive_dock = dock = self.dock()
        self.addCleanup(setattr, self.dialog, "_interactive_dock", None)
        self.select(0, second)
        with mock.patch.object(self.dialog, "_collect_layer_points_for_row", wraps=self.dialog._collect_layer_points_for_row) as read:
            first.triggerRepaint()
            QtWidgets.QApplication.processEvents()
            read.assert_not_called()
            second.triggerRepaint()
            QtWidgets.QApplication.processEvents()
            read.assert_called()

    def test_removing_a_row_layer_updates_the_dialog_panel(self):
        # The selector goes back to «---» without emitting layerChanged (QGIS emits it on removal only when no other
        # layer is left in the selector): the row and the dialog's panel follow anyway.
        layer = point_layer("Mine", A)
        point_layer("Other", B)
        self.select(0, layer)
        self.dialog._interactive_dock = dock = self.dock()
        self.addCleanup(setattr, self.dialog, "_interactive_dock", None)
        self.assertTrue(dock.btn_calc.isEnabled())
        QgsProject.instance().removeMapLayer(layer.id())
        self.assertEqual(self.dialog._rows[0]["layer_id"], "")
        self.assertFalse(dock.btn_calc.isEnabled())
        self.assertFalse(dock.btn_plot_wakes.isEnabled())
        self.assertIn("Ninguna fila tiene capa de turbinas.", dock.lbl_layer_status.text())

    def test_closing_after_a_followed_layer_left_the_project(self):
        # Disconnecting through a signal object kept from a destroyed layer brings QGIS down. The panel is not the
        # dialog's, so it is not refreshed when the row loses the layer and still follows it when it is destroyed.
        layer = point_layer("Gone", A)
        self.select(0, layer)
        dock = self.dock()
        QgsProject.instance().removeMapLayer(layer.id())
        QtWidgets.QApplication.processEvents()
        dock._teardown()
        self.assertEqual(dock._watched_layers, {})

    def test_every_row_on_dashes_is_named(self):
        self.set_rows(2)
        dock = self.dock()
        self.assertFalse(dock.btn_calc.isEnabled())
        self.assertIn("Ninguna fila tiene capa de turbinas.", dock.lbl_layer_status.text())
        self.assertIn("Modelos sin capa con turbinas: 1, 2.", dock.lbl_layer_status.text())

    def test_the_active_layer_does_not_enable_it(self):
        # The row computes with its empty layer, although another layer, active and with points, is not in any row.
        empty = point_layer("T1 (CSV)", [])
        active = point_layer("Modelo 1 (CSV)", B)
        self.select(0, empty)
        with mock.patch("VelantisWind.aep_setup_dialog.iface", fake_iface(active)):
            dock = self.dock()
            self.assertIn("T1 (CSV)", dock.lbl_layer_status.text())
            self.assertFalse(dock.btn_calc.isEnabled())
            self.assertFalse(dock.btn_plot_wakes.isEnabled())


class SelectedLayerIsTheOneComputedTest(DialogCase):
    """The reproductions of V4, V5 and V6: what the row shows is what is computed, and nothing else changes."""

    def setUp(self):
        super().setUp()
        self.a = point_layer("T1 (CSV)", A)
        self.b = point_layer("Mine", B)
        self.select(0, self.b)

    def assertRowGetsB(self):
        self.assertEqual([m.coords_xy for m in self.aep_models()], [B])
        self.assertEqual([m["source_layer_id"] for m in self.raster_models()], [self.b.id()])

    def test_a_named_after_the_turbine(self):
        self.assertRowGetsB()

    def test_a_with_the_row_metadata(self):
        for key, value in (("velantis/model_index", 0), ("velantis/row_index", 0), ("velantis/model_name", "T1")):
            self.a.setCustomProperty(key, value)
        self.assertRowGetsB()

    def test_a_active(self):
        with mock.patch("VelantisWind.aep_setup_dialog.iface", fake_iface(self.a)):
            self.assertRowGetsB()

    def test_results_go_to_b_and_a_is_untouched(self):
        twin = point_layer("T1 (CSV)", B)
        self.compute()
        self.assertEqual([f["aep_mwh"] for f in self.b.getFeatures()], [1000.0] * 3)
        self.assertEqual(twin.fields().indexFromName("aep_mwh"), -1)
        self.assertEqual(self.a.fields().indexFromName("aep_mwh"), -1)

    def test_selected_geopackage_keeps_its_points_on_disk(self):
        path = os.path.join(self.folder, "layout.gpkg")
        writer = QgsVectorFileWriter(path, "UTF-8", QgsFields(), QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"), "GPKG")
        for x, y in A:
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            writer.addFeature(feature)
        del writer
        package = QgsVectorLayer(path, "Package", "ogr")
        self.assertTrue(package.isValid())
        QgsProject.instance().addMapLayer(package)
        self.select(0, package)
        self.compute()
        csv = os.path.join(self.folder, "other.csv")
        with open(csv, "w") as fh:
            fh.write("x,y\n" + "".join(f"{x},{y}\n" for x, y in B))

        def accept(dialog):
            dialog.ed_csv.setText(csv)
            return QtWidgets.QDialog.Accepted

        # «Cargar nueva capa» in the very row that has the GeoPackage: a new layer, the file untouched.
        with mock.patch.object(layout_sources, "exec_dialog", side_effect=accept):
            self.dialog._load_new_layer(0)
        loaded = self.dialog._find_interactive_layer_for_row(0)
        self.assertNotEqual(loaded.id(), package.id())
        self.assertEqual(points_of(loaded), B)
        self.compute()
        self.assertEqual(points_of(QgsVectorLayer(path, "Again", "ogr")), A)


class RowWithoutPointsTest(DialogCase):
    def test_row_on_dashes(self):
        point_layer("T1 (CSV)", A)
        self.assertNothingComputed("Modelo 1", "«Capa de turbinas»")

    def test_empty_layer(self):
        self.select(0, point_layer("Empty", []))
        self.assertNothingComputed("«Empty»", "Modelo 1", "no tiene turbinas")

    def test_row_without_a_turbine(self):
        # The raster would otherwise take an example turbine that nobody chose; the AEP already refused.
        self.set_rows(2)
        self.select(0, point_layer("Mine", A))
        self.select(1, point_layer("Other", B))
        self.assertNothingComputed("Define todos los modelos")


class SelectorTest(DialogCase):
    def test_a_new_row_starts_on_dashes_with_layers_in_the_project(self):
        point_layer("Existing", A)
        self.set_rows(2)
        for idx in (0, 1):
            self.assertEqual(self.selector(idx).currentText(), "---")
            self.assertIsNone(self.dialog._find_interactive_layer_for_row(idx))

    def test_removing_the_selected_layer_goes_back_to_dashes(self):
        layer, other = point_layer("Mine", A), point_layer("Other", B)
        self.select(0, layer)
        QgsProject.instance().removeMapLayer(layer.id())
        self.assertEqual(self.selector(0).currentText(), "---")
        self.assertIsNone(self.dialog._find_interactive_layer_for_row(0))
        self.assertIsNotNone(QgsProject.instance().mapLayer(other.id()))

    def test_clearing_the_project_goes_back_to_dashes_and_new_layers_do_not_change_it(self):
        self.select(0, point_layer("Mine", A))
        QgsProject.instance().clear()
        self.assertEqual(self.selector(0).currentText(), "---")
        point_layer("Mine", A)
        point_layer("Other", B)
        self.assertEqual(self.selector(0).currentText(), "---")
        self.assertIsNone(self.dialog._find_interactive_layer_for_row(0))

    def test_changing_the_number_of_rows_keeps_each_layer(self):
        layer = point_layer("Mine", A)
        self.select(0, layer)
        self.set_rows(3)
        self.assertEqual(self.dialog._find_interactive_layer_for_row(0).id(), layer.id())
        self.assertEqual([self.selector(i).currentText() for i in (1, 2)], ["---", "---"])
        self.set_rows(1)
        self.assertEqual(self.dialog._find_interactive_layer_for_row(0).id(), layer.id())


class TurbineDataTest(DialogCase):
    META = {"hh": 120.0, "diam": 150.0}

    def define(self, idx):
        turbine = mock.Mock(exec_=lambda: QtWidgets.QDialog.Accepted, Accepted=QtWidgets.QDialog.Accepted)
        turbine.get_wind_turbine.return_value = object()
        turbine.result_data.return_value = dict(self.META, name="Vendor X")
        self.dialog._custom_dialog_factory = lambda parent: turbine
        self.dialog._define_model(idx)

    def assertMetadata(self, layer):
        self.assertEqual(layer.name(), "My layout")
        self.assertEqual(layer.customProperty("velantis/model_name"), "Vendor X")
        self.assertEqual(float(layer.customProperty("velantis/hub_height_m")), 120.0)
        self.assertEqual(float(layer.customProperty("velantis/diameter_m")), 150.0)
        self.assertEqual(layer.customProperty("velantis/layer_role"), "energy_turbines")

    def test_define_with_the_layer_selected(self):
        layer = point_layer("My layout", A)
        self.select(0, layer)
        self.define(0)
        self.assertMetadata(layer)

    def test_select_after_defining(self):
        self.define(0)
        layer = point_layer("My layout", A)
        self.select(0, layer)
        self.assertMetadata(layer)

    def test_turbine_data_mark_the_project_as_modified(self):
        # They are saved in the project, not in the layer's file: closing without saving must ask.
        layer = point_layer("My layout", A)
        self.select(0, layer)
        QgsProject.instance().setDirty(False)
        self.define(0)
        self.assertTrue(QgsProject.instance().isDirty())
        QgsProject.instance().setDirty(False)
        self.select(0, None)
        self.select(0, layer)
        self.assertFalse(QgsProject.instance().isDirty())
        other = point_layer("Other", B)
        QgsProject.instance().setDirty(False)
        self.select(0, other)
        self.assertTrue(QgsProject.instance().isDirty())
        # A number kept as text by an older project is not a change.
        other.removeCustomProperty("velantis/hub_height_m")
        other.setCustomProperty("velantis/hub_height_m", "120")
        self.assertIsInstance(other.customProperty("velantis/hub_height_m"), str)
        QgsProject.instance().setDirty(False)
        self.select(0, None)
        self.select(0, other)
        self.assertFalse(QgsProject.instance().isDirty())

    def envelope_areas(self):
        return sorted(round(next(lyr.getFeatures()).geometry().area()) for lyr in QgsProject.instance().mapLayers().values()
                      if lyr.customProperty("velantis/source_turbine_layer_id") and lyr.featureCount())

    def test_define_after_loading_rebuilds_only_the_envelopes_there_are(self):
        # «Cargar nueva capa» before «Definir…»: the envelope drawn with the fallback diameter takes the turbine's. The
        # spacing envelopes, never switched on or off in this profile (switched off, the load makes none, #96).
        QtCore.QSettings("VelantisWind", "VelantisWindPlugin").remove("spacing/enabled")
        csv = os.path.join(self.folder, "single.csv")
        with open(csv, "w") as fh:
            fh.write("x,y\n500000,4400000\n")
        with mock.patch.object(layout_sources, "exec_dialog",
                               side_effect=lambda window: (window.ed_csv.setText(csv), QtWidgets.QDialog.Accepted)[1]):
            self.dialog._load_new_layer(0)
        layer = self.dialog._find_interactive_layer_for_row(0)
        loaded = self.envelope_areas()
        self.assertEqual(len(loaded), 1)
        # Another row's layer without an envelope, and the spacing switched off by the user.
        self.set_rows(2)
        self.select(1, point_layer("Other", B))
        self.define(1)
        self.assertEqual(self.envelope_areas(), loaded)
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        settings.setValue("spacing/enabled", False)
        self.define(0)
        defined = self.envelope_areas()
        self.assertEqual(len(defined), 1)
        self.assertNotEqual(defined, loaded)
        self.assertEqual(settings.value("spacing/enabled", type=bool), False)
        ensure_spacing_envelope_for_layer(layer, existing_only=True)
        self.assertEqual(self.envelope_areas(), defined)

    def test_selecting_a_layer_with_an_envelope_rebuilds_it(self):
        # A layer whose envelope was drawn for another turbine, chosen in a row already defined: the envelope takes the
        # row's diameter, also without the spacing panel.
        layer = point_layer("My layout", A[:1])
        layer.setCustomProperty("velantis/layer_role", "energy_turbines")
        layer.setCustomProperty("velantis/diameter_m", 100.0)
        ensure_spacing_envelope_for_layer(layer)
        drawn = self.envelope_areas()
        self.define(0)
        self.select(0, layer)
        self.assertEqual(float(layer.customProperty("velantis/diameter_m")), 150.0)
        rebuilt = self.envelope_areas()
        self.assertNotEqual(rebuilt, drawn)
        ensure_spacing_envelope_for_layer(layer, existing_only=True)
        self.assertEqual(self.envelope_areas(), rebuilt)

    def test_a_shared_layer_left_by_its_first_row_rebuilds_its_envelope(self):
        # The layer is in two rows; its envelope is the first row's. When the first row leaves it (for «---» or a layer
        # without an envelope), the layer takes the second row's turbine, and so does its envelope.
        for leave_for in ("---", "a layer without an envelope"):
            with self.subTest(leave_for=leave_for):
                QgsProject.instance().clear()
                self.set_rows(1)
                self.set_rows(2)
                shared = point_layer("Shared", A[:1])
                self.define_row(0, "T100", {"diam": 100.0})
                self.define_row(1, "T200", {"diam": 200.0})
                self.select(0, shared)
                self.select(1, shared)
                ensure_spacing_envelope_for_layer(shared)
                first = self.envelope_areas()
                self.select(0, point_layer("Other", B[:1]) if leave_for != "---" else None)
                self.assertEqual(float(shared.customProperty("velantis/diameter_m")), 200.0)
                rebuilt = self.envelope_areas()
                self.assertNotEqual(rebuilt, first)
                ensure_spacing_envelope_for_layer(shared, existing_only=True)
                self.assertEqual(self.envelope_areas(), rebuilt)

    def test_define_creates_no_envelope_for_a_layer_without_one(self):
        self.select(0, point_layer("My layout", A))
        self.define(0)
        self.assertEqual(self.envelope_areas(), [])


class GeneratePointLayersTest(DialogCase):
    def test_creates_an_empty_layer_selected_in_the_row(self):
        point_layer("Existing", A)
        with mock.patch.object(self.dialog, "_enter_or_refresh_interactive_after_layer_created"):
            self.dialog._on_generate_layers_clicked()
        layer = self.dialog._find_interactive_layer_for_row(0)
        self.assertIsNotNone(layer)
        self.assertNotEqual(layer.name(), "Existing")
        self.assertEqual(layer.featureCount(), 0)
        self.assertEqual(layer.crs().authid(), "EPSG:32630")

    def test_project_crs_without_authority_id(self):
        custom = QgsCoordinateReferenceSystem.fromProj(CUSTOM)
        self.assertEqual(custom.authid(), "")
        QgsProject.instance().setCrs(custom)
        with mock.patch.object(self.dialog, "_enter_or_refresh_interactive_after_layer_created"):
            self.dialog._on_generate_layers_clicked()
        self.assertEqual(self.dialog._find_interactive_layer_for_row(0).crs(), custom)


class AcceptTest(DialogCase):
    def test_a_row_on_dashes_does_not_close(self):
        with mock.patch.object(self.dialog, "accept") as accept:
            self.dialog._accept()
        accept.assert_not_called()
        self.assertIn("Modelo 1", self.shown[-1][1])

    def test_every_row_with_a_layer_closes(self):
        self.select(0, point_layer("Mine", A))
        with mock.patch.object(self.dialog, "accept") as accept:
            self.dialog._accept()
        accept.assert_called_once()


class InteractiveMapTargetTest(DialogCase):
    def setUp(self):
        super().setUp()
        self.set_rows(2)
        self.a, self.b = point_layer("A", A), point_layer("B", B)
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.window = QtWidgets.QMainWindow()

    def dock(self):
        dock = InteractiveMapDock(self.dialog, parent=self.window)
        self.addCleanup(dock._teardown)
        return dock

    def added_to(self):
        """The layer that really gets the point of a left click."""
        before = {layer.id(): layer.featureCount() for layer in (self.a, self.b)}
        tool = _TurbineInteractiveTool(self.dialog, self.canvas)
        self.clicks = getattr(self, "clicks", 0) + 1
        x = 505000.0 + 1000.0 * self.clicks
        event = mock.Mock(button=lambda: QtCore.Qt.LeftButton, mapPoint=lambda: QgsPointXY(x, 4405000.0))
        with mock.patch("VelantisWind.mapa_interactivo.iface"):
            tool.canvasPressEvent(event)
        [changed] = [layer for layer in (self.a, self.b) if layer.featureCount() != before[layer.id()]]
        return changed

    def test_selected_layer_wins_over_another_active_one(self):
        self.select(0, self.b)
        with mock.patch("VelantisWind.aep_setup_dialog.iface", fake_iface(self.a)):
            self.assertEqual(self.dialog._get_interactive_target_layer().id(), self.b.id())

    def test_panel_shows_the_layer_really_edited(self):
        # A in a row without turbine, B in a row with turbine.
        self.dialog._rows[1]["wt"], self.dialog._rows[1]["name"] = object(), "T2"
        self.dialog._rows[0]["wt"] = None
        self.select(0, self.a)
        self.select(1, self.b)
        for active in (self.a, None, self.b):
            with self.subTest(active=active.name() if active else None), \
                    mock.patch("VelantisWind.aep_setup_dialog.iface", fake_iface(active)):
                dock = self.dock()
                shown = dock.cb_edit_layer.currentData(QtCore.Qt.UserRole)
                self.assertEqual(shown, self.added_to().id())

    def test_panel_follows_the_selector(self):
        self.select(0, self.a)
        dock = self.dock()
        self.dialog._interactive_dock = dock
        self.addCleanup(setattr, self.dialog, "_interactive_dock", None)
        self.select(0, self.b)
        self.assertEqual(dock.cb_edit_layer.currentData(QtCore.Qt.UserRole), self.b.id())


class SpacingRowTest(DialogCase):
    def setUp(self):
        super().setUp()
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        with mock.patch("VelantisWind.aep_setup_dialog.iface", mock.Mock(mapCanvas=lambda: self.canvas)):
            self.spacing = self.dialog._ensure_spacing_controller()
        self.addCleanup(self.spacing.teardown)

    def test_the_selector_gives_the_row_not_the_metadata(self):
        self.set_rows(2)
        self.define_row(1, "T2")
        layer = point_layer("Mine", A)
        layer.setCustomProperty("velantis/row_index", 0)
        layer.setCustomProperty("velantis/model_index", 0)
        self.select(1, layer)
        self.spacing._selected_layer_id = layer.id()
        self.assertEqual(self.spacing._selected_row_index(layer), 1)
        self.spacing._persist_selected_model_spec()
        self.assertIn("spacing_long_d", self.dialog._rows[1]["meta"])
        self.assertNotIn("spacing_long_d", self.dialog._rows[0]["meta"])

    def start_on(self, layer):
        self.spacing._selected_layer_id = layer.id()
        self.spacing._start_define_tool()
        tool = self.spacing._tool
        self.assertIsNotNone(tool)
        tool._fid, tool._center, tool._state = 1, QgsPointXY(*A[0]), map_tool._ST_MINOR
        return tool

    def test_a_definition_in_progress_never_lands_in_another_layer(self):
        for change in ("selector", "remove", "clear"):
            with self.subTest(change=change):
                a, b = point_layer("A", A), point_layer("B", B)
                self.select(0, a)
                tool = self.start_on(a)
                if change == "selector":
                    self.select(0, b)
                elif change == "remove":
                    QgsProject.instance().removeMapLayer(a.id())
                else:
                    QgsProject.instance().clear()
                self.assertIsNone(self.spacing._tool)
                tool._finish()
                if change != "clear":
                    self.assertEqual(read_overrides(b), {})
                QgsProject.instance().clear()

    def test_a_finished_ellipse_is_saved_in_the_layer_it_started_on(self):
        a, b = point_layer("A", A), point_layer("B", B)
        self.select(0, a)
        tool = self.start_on(a)
        self.spacing._selected_layer_id = b.id()
        tool._finish()
        self.assertEqual(list(read_overrides(a)), [1])
        self.assertEqual(read_overrides(b), {})


class SameLayerInTwoRowsTest(DialogCase):
    def setUp(self):
        super().setUp()
        self.set_rows(2)
        self.define_row(0, "T1", {"diam": 100.0, "spacing_long_d": 7.0, "spacing_trans_d": 4.0})
        self.define_row(1, "T2", {"diam": 200.0, "spacing_long_d": 10.0, "spacing_trans_d": 5.0})
        self.layer = point_layer("Shared", A)
        self.select(0, self.layer)
        self.select(1, self.layer)

    def test_both_rows_take_it(self):
        self.assertEqual([(m.coords_xy, m.source_layer_id) for m in self.aep_models()], [(A, self.layer.id())] * 2)
        self.assertEqual([m["source_layer_id"] for m in self.raster_models()], [self.layer.id()] * 2)

    def test_map_and_spacing_give_it_to_the_first(self):
        from VelantisWind.spacing_core.envelope_manager import layer_diameter_m, layer_spacing_spec
        from VelantisWind.spacing_core.geometry import SpacingSpec

        self.assertEqual(self.dialog._row_index_for_layer(self.layer), 0)
        self.assertEqual([c["row_index"] for c in self.dialog._candidate_turbine_layers_for_edit()], [0])
        fallback = SpacingSpec(1.0, 1.0, 0.0, "auto_energy")
        # The ellipses and the insertion check read the turbine of the first row from the layer.
        self.assertEqual(layer_diameter_m(self.layer, 1.0), 100.0)
        self.assertEqual((layer_spacing_spec(self.layer, fallback).long_d, layer_spacing_spec(self.layer, fallback).trans_d), (7.0, 4.0))
        # Also after a calculation, whose results are the last row's.
        self.compute()
        self.assertEqual(layer_diameter_m(self.layer, 1.0), 100.0)
        self.assertEqual(layer_spacing_spec(self.layer, fallback).long_d, 7.0)
        self.assertEqual(self.layer.customProperty("velantis/model_name"), "T1")
        # When the first row takes another layer, the layer is the second row's.
        self.select(0, point_layer("Other", B))
        self.assertEqual(layer_diameter_m(self.layer, 1.0), 200.0)
        self.assertEqual(layer_spacing_spec(self.layer, fallback).long_d, 10.0)


class EditModeTest(DialogCase):
    """A selected layer in edit mode: save and compute, compute without writing into it, or cancel."""

    MOVED = (500010.0, 4400000.0)

    def setUp(self):
        super().setUp()
        self.layer = point_layer("Editing", A)
        self.select(0, self.layer)

    def answer(self, button, pending=True, commit_ok=True):
        """«Calcular AEP» with the layer in edit mode and ``button`` chosen; the points computed, or None."""
        self.dialog._last_aep_result = None
        self.layer.startEditing()
        if pending:
            first = next(self.layer.getFeatures()).id()
            self.layer.changeGeometry(first, QgsGeometry.fromPointXY(QgsPointXY(*self.MOVED)))
        if not commit_ok:
            self.layer.commitChanges = lambda *a: False
            self.layer.commitErrors = lambda: ["the provider refused"]
        asked = []

        def clicked(box):
            asked.append(sorted(b.text() for b in box.buttons()))
            return next(b for b in box.buttons() if b.text() == button)

        with mock.patch.object(QtWidgets.QMessageBox, "exec_", side_effect=lambda *a: 0), \
                mock.patch.object(QtWidgets.QMessageBox, "clickedButton", new=clicked):
            self.compute()
        self.assertEqual(asked, [sorted(["Guardar cambios y calcular", "Calcular sin escribir en la capa", "Cancelar"])])
        result = self.dialog._last_aep_result
        return [(r["x"], r["y"]) for r in result["per_turbine_table"]] if result else None

    def expected(self, pending):
        return [self.MOVED, A[1]] if pending else A

    def test_cancel(self):
        for pending in (True, False):
            with self.subTest(pending=pending):
                self.assertIsNone(self.answer("Cancelar", pending))
                self.assertTrue(self.layer.isEditable())
                self.layer.rollBack()

    def test_compute_without_writing_into_the_layer(self):
        for pending in (True, False):
            with self.subTest(pending=pending):
                self.assertEqual(self.answer("Calcular sin escribir en la capa", pending), self.expected(pending))
                self.assertTrue(self.layer.isEditable())
                self.assertEqual(self.layer.fields().indexFromName("aep_mwh"), -1)
                self.layer.rollBack()

    def test_save_and_compute(self):
        for pending in (True, False):
            with self.subTest(pending=pending):
                self.assertEqual(self.answer("Guardar cambios y calcular", pending), self.expected(pending))
                self.assertFalse(self.layer.isEditable())
                self.assertEqual(points_of(self.layer), self.expected(pending))
                self.assertEqual([f["aep_mwh"] for f in self.layer.getFeatures()], [1000.0, 1000.0])
                # Back to the original points for the next case.
                self.layer.startEditing()
                first = next(self.layer.getFeatures()).id()
                self.layer.changeGeometry(first, QgsGeometry.fromPointXY(QgsPointXY(*A[0])))
                self.layer.commitChanges()

    def test_save_and_compute_with_what_the_layer_keeps(self):
        # A filter on an edited field: while editing the layer still shows both turbines, once saved only one.
        layer = QgsVectorLayer("Point?crs=EPSG:32630&field=state:string", "Filtered", "memory")
        features = []
        for x, y in A:
            feature = QgsFeature(layer.fields())
            feature.setAttributes(["built"])
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            features.append(feature)
        layer.dataProvider().addFeatures(features)
        QgsProject.instance().addMapLayer(layer)
        layer.setSubsetString("\"state\" = 'built'")
        self.layer = layer
        self.select(0, layer)
        layer.startEditing()
        layer.changeAttributeValue(list(layer.getFeatures())[1].id(), 0, "removed")
        self.assertEqual(points_of(layer), A)
        with mock.patch.object(dialog_controller, "build_energy_dialog_state", wraps=dialog_controller.build_energy_dialog_state) as read:
            self.assertEqual(self.answer("Guardar cambios y calcular", pending=False), [A[0]])
        self.assertEqual(points_of(layer), [A[0]])
        # Read again after saving, without repeating the informational warnings of the first reading.
        self.assertEqual([c.kwargs.get("warn") for c in read.call_args_list], [True, False])

    def test_failed_save_computes_nothing(self):
        self.assertIsNone(self.answer("Guardar cambios y calcular", commit_ok=False))
        self.assertIn("«Editing»", self.shown[-1][1])
        self.assertIn("the provider refused", self.shown[-1][1])
        del self.layer.commitChanges
        self.layer.rollBack()

    def test_editing_in_groups_saves_nothing(self):
        # Another layer, not computed, with its own pending edit in the same group.
        other = point_layer("Other", B)
        QgsProject.instance().setTransactionMode(Qgis.TransactionMode.BufferedGroups)
        other.startEditing()
        other.changeGeometry(next(other.getFeatures()).id(), QgsGeometry.fromPointXY(QgsPointXY(1.0, 1.0)))
        self.assertIsNone(self.answer("Guardar cambios y calcular"))
        self.assertIn("en grupo", self.shown[-1][1])
        for layer in (self.layer, other):
            self.assertTrue(layer.isEditable())
            self.assertTrue(layer.isModified())
        self.assertEqual(points_of(other.dataProvider()), B)
        other.rollBack()
        self.layer.rollBack()

    def test_no_question_without_layers_in_edit_mode(self):
        with mock.patch.object(QtWidgets.QMessageBox, "exec_", side_effect=AssertionError("asked")):
            self.compute()
        self.assertIsNotNone(self.dialog._last_aep_result)


class ProjectCrsWithoutAuthorityIdTest(DialogCase):
    def test_engine_gets_the_whole_crs(self):
        custom = QgsCoordinateReferenceSystem.fromProj(CUSTOM)
        self.assertEqual(custom.authid(), "")
        QgsProject.instance().setCrs(custom)
        layer = QgsVectorLayer("Point", "Mine", "memory")
        layer.setCrs(custom)
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*A[0])))
        layer.dataProvider().addFeatures([feature])
        QgsProject.instance().addMapLayer(layer)
        self.select(0, layer)
        received = []

        def run(_runner, config, **_kw):
            received.append(config.project_crs_authid)
            raise RuntimeError("stop before the engine")

        with mock.patch("VelantisWind.energy_core.runner.EnergyRunner.run", run), \
                mock.patch.object(dialog_controller, "_validate_before_run", return_value=True), \
                mock.patch.object(dialog_controller, "create_progress_dialog"), \
                mock.patch.object(dialog_controller, "close_progress_dialog"):
            self.dialog._run_compute_and_update()
        self.assertEqual(received[:1], [custom.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED)])


class LayersUsedMessageTest(DialogCase):
    def test_aep_names_each_layer(self):
        self.set_rows(2)
        self.define_row(1, "T2")
        self.select(0, point_layer("First", A))
        self.select(1, point_layer("Second", B))
        bar = self.compute()
        [message] = [m for m in bar if "Capas de turbinas usadas" in m]
        self.assertEqual(message, "Capas de turbinas usadas: Modelo 1: «First»; Modelo 2: «Second»")

    def launch_raster(self):
        """The raster through the real controller, with the task simulated; the texts of the message bar."""
        def start(config, **callbacks):
            self.addCleanup(callbacks["on_finished"], False, {}, "cancelled")
            return mock.Mock()

        with mock.patch("VelantisWind.aep_setup_dialog.iface") as iface, \
                mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(300, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a: (a[3][0], True)), \
                mock.patch("VelantisWind.wake_core.controller.start_wake_raster_task", side_effect=start):
            self.dialog._run_plot_wakes()
        return [c.args[1] for c in iface.messageBar().pushMessage.call_args_list]

    def test_raster_names_each_layer_only_when_a_task_starts(self):
        self.select(0, point_layer("First", A))
        used = "Capas de turbinas usadas: Modelo 1: «First»"
        self.assertIn(used, self.launch_raster())
        # A raster still running: the controller keeps it and starts nothing.
        self.dialog._wake_raster_task_finished = False
        self.assertNotIn(used, self.launch_raster())
        self.dialog._wake_raster_task, self.dialog._wake_raster_task_finished = None, True
        # The controller refuses the project CRS.
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem())
        self.assertNotIn(used, self.launch_raster())


if __name__ == "__main__":
    unittest.main()
