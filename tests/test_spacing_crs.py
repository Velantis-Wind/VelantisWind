# -*- coding: utf-8 -*-
"""Spacing ellipses and «Definir elipse en pantalla» only on turbine layers in a projected CRS in metres."""
import os
import tempfile
import types
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsDatumTransform,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402

from VelantisWind import i18n  # noqa: E402
from VelantisWind.spacing_core import map_tool  # noqa: E402
from VelantisWind.spacing_core.config_dialog import SpacingConfigDialog  # noqa: E402
from VelantisWind.spacing_core.controller import _DEFINE_RULE_STATUS, SpacingController  # noqa: E402
from VelantisWind.spacing_core.envelope_manager import EnvelopeManager, read_overrides  # noqa: E402
from VelantisWind.spacing_core.geometry import MODE_AUTO, SpacingSpec  # noqa: E402
from VelantisWind.wake_core.controller import is_projected_in_metres  # noqa: E402

_CWD = os.getcwd()

# A projected CRS in metres without an authority id, and one with datum parameters (type Bound).
CUSTOM = "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"
BOUND = "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=intl +towgs84=1,2,3,0,0,0,0 +units=m +no_defs"
GEOCENTRIC_BOUND = "+proj=geocent +ellps=GRS80 +towgs84=1,2,3,0,0,0,0 +units=m +no_defs"


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def crs(definition):
    return QgsCoordinateReferenceSystem.fromProj(definition) if definition.startswith("+") else QgsCoordinateReferenceSystem(definition)


def turbine_layer(definition, points=((500000.0, 4400000.0), (501000.0, 4400000.0))):
    layer = QgsVectorLayer("Point", "Turbines", "memory")
    layer.setCrs(crs(definition))
    features = []
    for x, y in points:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.setCustomProperty("velantis/layer_role", "energy_turbines")
    QgsProject.instance().addMapLayer(layer)
    return layer


class ProjectedInMetresTest(unittest.TestCase):
    def test_rule(self):
        utm = "+proj=utm +zone=30 +datum=WGS84 +units={} +no_defs"
        for definition, expected in (("EPSG:32630", True), (CUSTOM, True), (BOUND, True), ("EPSG:4326", False),
                                     ("EPSG:4978", False), (GEOCENTRIC_BOUND, False), ("EPSG:2263", False),
                                     (utm.format("km"), False), (utm.format("cm"), False), (utm.format("mm"), False)):
            with self.subTest(crs=definition[:30]):
                self.assertTrue(crs(definition).isValid())
                self.assertIs(is_projected_in_metres(crs(definition)), expected)
        self.assertFalse(is_projected_in_metres(QgsCoordinateReferenceSystem()))


class EnvelopeCrsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.manager = EnvelopeManager()

    def rebuild(self, layer):
        self.manager.rebuild_many([layer], SpacingSpec(7.0, 4.0, 0.0, MODE_AUTO), None)
        return self.manager.envelope_layer(layer)

    def test_layers_not_in_metres_get_no_ellipses(self):
        for definition in ("EPSG:4326", "EPSG:4978"):
            with self.subTest(crs=definition):
                self.assertIsNone(self.rebuild(turbine_layer(definition)))
        self.assertEqual(len(QgsProject.instance().mapLayers()), 2)

    def test_existing_envelope_is_removed_when_its_layer_leaves_metres(self):
        layer = turbine_layer("EPSG:32630")
        envelope_id = self.rebuild(layer).id()
        layer.setCrs(crs("EPSG:4326"))
        # A fresh manager, as in another session of the dialog, still finds and removes it.
        self.manager = EnvelopeManager()
        self.assertIsNone(self.rebuild(layer))
        self.assertIsNone(QgsProject.instance().mapLayer(envelope_id))
        self.assertEqual(list(QgsProject.instance().mapLayers()), [layer.id()])

    def test_layer_in_metres_gets_them_in_its_crs(self):
        envelope = self.rebuild(turbine_layer("EPSG:32630"))
        self.assertEqual(envelope.crs().authid(), "EPSG:32630")
        self.assertEqual(envelope.featureCount(), 2)

    def test_crs_without_authority_id_is_kept_and_its_envelope_reused(self):
        layer = turbine_layer(CUSTOM)
        envelope = self.rebuild(layer)
        self.assertEqual(envelope.crs(), layer.crs())
        self.assertEqual(envelope.featureCount(), 2)
        # A fresh manager, as after reopening the panel, finds the same envelope instead of creating another.
        self.manager = EnvelopeManager()
        self.assertEqual(self.rebuild(layer).id(), envelope.id())
        self.assertEqual(len(QgsProject.instance().mapLayers()), 2)


class BlockAcrossCrsTest(unittest.TestCase):
    """«Bloquear inserción» compares the candidate with the envelopes of a layer in another CRS in metres."""

    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(crs("EPSG:32630"))
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)
        bar = mock.patch("VelantisWind.spacing_core.controller.iface")
        self.iface = bar.start()
        self.addCleanup(bar.stop)
        self.mine = turbine_layer("EPSG:32630", points=((500000.0, 4400000.0),))
        # The other row's turbine 3 km east, in the neighbouring UTM zone.
        to_31 = QgsCoordinateTransform(crs("EPSG:32630"), crs("EPSG:32631"), QgsProject.instance())
        there = to_31.transform(QgsPointXY(503000.0, 4400000.0))
        self.other = turbine_layer("EPSG:32631", points=((there.x(), there.y()),))
        for layer in (self.mine, self.other):
            layer.setCustomProperty("velantis/diameter_m", 100.0)
        # Both layers are rows of the park; the tests build their envelopes with a fixed geometry.
        self.rows = [self.mine, self.other]
        ctl = types.SimpleNamespace(_rows=[{}, {}], ed_wrg=mock.Mock(text=lambda: ""),
                                    _find_interactive_layer_for_row=lambda idx: self.rows[idx],
                                    _get_interactive_target_layer=lambda allow_auto_pick=True: self.rows[0])
        self.controller = SpacingController(ctl, self.canvas)
        self.addCleanup(self.controller.teardown)
        self.controller.panel.set_enabled(True)
        self.controller.panel.cb_validation.setCurrentIndex(self.controller.panel.cb_validation.findData("block"))
        self.controller.manager.rebuild_many(self.rows, SpacingSpec(7.0, 4.0, 0.0, "fixed"), None)

    def test_a_turbine_next_to_another_crs_layer_is_blocked(self):
        self.assertFalse(self.controller.check_candidate(self.mine, 503050.0, 4400000.0))
        self.assertTrue(self.controller.check_candidate(self.mine, 500000.0, 4410000.0))
        # The same through the controller, which takes the two rows (#96).
        self.controller.refresh()
        self.assertFalse(self.controller.check_candidate(self.mine, 503050.0, 4400000.0))
        self.assertTrue(self.controller.check_candidate(self.mine, 500000.0, 4410000.0))

    def test_an_ellipse_across_the_antimeridian_blocks(self):
        # Transformed to Web Mercator across 180°, the candidate ellipse is invalid although the transformation works.
        QgsProject.instance().removeMapLayers([self.mine.id(), self.other.id()])
        east = turbine_layer("EPSG:32660", points=((756000.0, 4300000.0),))
        to_3857 = QgsCoordinateTransform(crs("EPSG:32660"), crs("EPSG:3857"), QgsProject.instance())
        there = to_3857.transform(QgsPointXY(756050.0, 4432050.0))
        mercator = turbine_layer("EPSG:3857", points=((there.x(), there.y()),))
        for layer in (east, mercator):
            layer.setCustomProperty("velantis/diameter_m", 100.0)
        self.rows[:] = [east, mercator]
        self.controller.manager.rebuild_many(self.rows, SpacingSpec(7.0, 4.0, 0.0, "fixed"), None)
        self.assertFalse(self.controller.check_candidate(east, 756000.0, 4432050.0))

    def check_across(self, mine_crs, mine_turbine, other_crs, near, candidate, diameters=(100.0, 10.0), operation=""):
        """A row in ``mine_crs`` with a turbine, another in ``other_crs`` with one at ``near`` (given in ``mine_crs``),
        and the check of a candidate at ``candidate``; returns it and the warning shown. ``operation`` is the datum
        operation chosen in the project for the pair."""
        QgsProject.instance().clear()
        self.iface.reset_mock()
        if operation:
            context = QgsProject.instance().transformContext()
            context.addCoordinateOperation(crs(mine_crs), crs(other_crs), operation)
            QgsProject.instance().setTransformContext(context)
        mine = turbine_layer(mine_crs, points=(mine_turbine,))
        there = QgsCoordinateTransform(crs(mine_crs), crs(other_crs), QgsProject.instance()).transform(QgsPointXY(*near))
        other = turbine_layer(other_crs, points=((there.x(), there.y()),))
        mine.setCustomProperty("velantis/diameter_m", diameters[0])
        other.setCustomProperty("velantis/diameter_m", diameters[1])
        self.rows[:] = [mine, other]
        self.controller.manager.rebuild_many(self.rows, SpacingSpec(7.0, 4.0, 0.0, "fixed"), None)
        allowed = self.controller.check_candidate(mine, *candidate)
        warning = self.iface.messageBar().pushWarning.call_args
        return allowed, warning.args[1] if warning else None

    def test_an_ellipse_across_a_cut_of_the_other_crs_blocks(self):
        # In the other row's CRS the candidate's ellipse would go round the world (180°, a pole, the cut of a sinusoidal
        # projection), valid for GEOS, and miss the turbine 50 m away: it cannot be compared there.
        centred = "+proj=tmerc +lat_0=0 +lon_0=180 +k=1 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs"
        sinusoidal = "+proj=sinu +lon_0={} +datum=WGS84 +units=m +no_defs"
        for mine_crs, mine_turbine, other_crs, near, candidate in (
                (centred, (500000.0, 4403000.0), "EPSG:3857", (499950.0, 4400000.0), (500000.0, 4400000.0)),
                ("EPSG:32661", (2000000.0, 2003100.0), "EPSG:4087", (2000000.0, 2000150.0), (2000000.0, 2000100.0)),
                ("EPSG:32661", (2000000.0, 2008000.0), sinusoidal.format(0), (1999950.0, 2005000.0), (2000000.0, 2005000.0)),
                ("EPSG:32661", (1992000.0, 2000000.0), sinusoidal.format(90), (1995000.0, 2000050.0), (1995000.0, 2000000.0)),
        ):
            with self.subTest(mine=mine_crs[:20], other=other_crs[:20]):
                allowed, warning = self.check_across(mine_crs, mine_turbine, other_crs, near, candidate)
                self.assertFalse(allowed)
                self.assertIn("No se pudo comparar la turbina", warning)

    def test_without_a_cut_it_is_compared_also_where_much_distorted(self):
        # 30 km from the pole in an equirectangular projection, 10 km from 180°, and a turbine at the antipode: compared,
        # and let in.
        for mine_crs, mine_turbine, other_crs, near, candidate in (
                ("EPSG:32661", (2000000.0, 1960000.0), "EPSG:4087", (2000000.0, 1960000.0), (2000000.0, 1970000.0)),
                ("EPSG:32660", (756000.0, 4300000.0), "EPSG:3857", (756050.0, 4432050.0), (746000.0, 4432050.0)),
                ("EPSG:3857", (0.0, 5000.0), "EPSG:4087", (20037508.342789244, 0.0), (0.0, 0.0)),
        ):
            with self.subTest(mine=mine_crs, other=other_crs):
                self.assertEqual(self.check_across(mine_crs, mine_turbine, other_crs, near, candidate, (100.0, 100.0)),
                                 (True, None))

    def test_the_datum_operation_chosen_in_the_project_is_used(self):
        # ED50 to WGS 84 with the operation the project chose for the pair: the turbine is 17 m² inside the candidate's
        # ellipse with it, outside with the default one.
        [operation] = [op.proj for op in QgsDatumTransform.operations(crs("EPSG:23030"), crs("EPSG:32630"))
                       if op.name.endswith("ED50 to WGS 84 (23) + UTM zone 30N")]
        context = QgsCoordinateTransformContext()
        context.addCoordinateOperation(crs("EPSG:23030"), crs("EPSG:32630"), operation)
        to_32630 = QgsCoordinateTransform(crs("EPSG:23030"), crs("EPSG:32630"), context)
        near = to_32630.transform(QgsPointXY(500297.6607692888, 4399792.963864325), QgsCoordinateTransform.ReverseTransform)
        allowed, warning = self.check_across("EPSG:23030", (500000.0, 4410000.0), "EPSG:32630", (near.x(), near.y()),
                                             (500000.0, 4400000.0), (100.0, 100.0), operation)
        self.assertFalse(allowed)
        self.assertIn("invade la envolvente", warning)

    def test_a_geos_failure_blocks(self):
        # An envelope with a self-intersecting ring around the candidate: GEOS fails without an exception.
        envelope = self.controller.manager.envelope_layer(self.mine)
        bowtie = QgsGeometry.fromWkt("POLYGON((499900 4409900, 500100 4410100, 500100 4409900, 499900 4410100, 499900 4409900))")
        envelope.dataProvider().changeGeometryValues({next(envelope.getFeatures()).id(): bowtie})
        self.assertFalse(self.controller.check_candidate(self.mine, 500000.0, 4410000.0))
        self.assertIn("No se pudo comparar la turbina", self.iface.messageBar().pushWarning.call_args.args[1])

    def test_a_comparison_that_cannot_be_made_blocks_and_warns(self):
        # An invalid transformation, one that cannot even be built, or an envelope layer that cannot be read.
        invalid = mock.Mock()
        invalid.return_value.isValid.return_value = False
        envelope = self.controller.manager.envelope_layer(self.other)
        for case, patch in (
                ("invalid", mock.patch("VelantisWind.spacing_core.controller.QgsCoordinateTransform", invalid)),
                ("not built", mock.patch("VelantisWind.spacing_core.controller.QgsCoordinateTransform", side_effect=RuntimeError)),
                ("unreadable", mock.patch.object(envelope, "getFeatures", side_effect=RuntimeError))):
            with self.subTest(case=case), patch:
                self.iface.reset_mock()
                self.assertFalse(self.controller.check_candidate(self.mine, 500000.0, 4410000.0))
                self.assertIn("No se pudo comparar la turbina", self.iface.messageBar().pushWarning.call_args.args[1])


class DefineOnScreenTest(unittest.TestCase):
    """The tool starts only with the layer and the map in the same CRS in metres, and never saves outside it."""

    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.canvas = QgsMapCanvas()
        self.addCleanup(self.canvas.deleteLater)

    def controller(self, layer, canvas_crs):
        self.canvas.setDestinationCrs(crs(canvas_crs))
        ctl = types.SimpleNamespace(_rows=[{}], ed_wrg=mock.Mock(text=lambda: ""),
                                    _find_interactive_layer_for_row=lambda idx: layer,
                                    _get_interactive_target_layer=lambda allow_auto_pick=True: layer)
        controller = SpacingController(ctl, self.canvas)
        self.addCleanup(controller.teardown)
        controller._selected_layer_id = layer.id()
        return controller

    def window(self, controller):
        main = mock.Mock()
        self.parent_window = QtWidgets.QWidget()
        self.addCleanup(self.parent_window.deleteLater)
        window = SpacingConfigDialog(controller, main_dialog=main, parent=self.parent_window)
        self.addCleanup(window.deleteLater)
        window.show()
        return window, main

    def test_refused_without_the_same_crs_in_metres(self):
        for layer_crs, canvas_crs in (("EPSG:4326", "EPSG:4326"), ("EPSG:32630", "EPSG:4326"),
                                      ("EPSG:32630", "EPSG:25830"), ("EPSG:4978", "EPSG:4978")):
            with self.subTest(layer=layer_crs, canvas=canvas_crs):
                layer = turbine_layer(layer_crs)
                controller = self.controller(layer, canvas_crs)
                window, main = self.window(controller)
                previous_tool = self.canvas.mapTool()
                controller.panel.define_on_screen.emit()
                self.assertIsNone(controller._tool)
                self.assertIs(self.canvas.mapTool(), previous_tool)
                self.assertTrue(window.isVisible())
                main._hide_dialog_for_interactive_map.assert_not_called()
                self.assertEqual(controller.panel.lbl_status.text(), _DEFINE_RULE_STATUS)
                self.assertEqual(read_overrides(layer), {})

    def test_started_with_the_same_crs_in_metres(self):
        for definition in ("EPSG:32630", BOUND):
            with self.subTest(crs=definition[:30]):
                layer = turbine_layer(definition)
                controller = self.controller(layer, definition)
                window, main = self.window(controller)
                controller.panel.define_on_screen.emit()
                self.assertIsNotNone(controller._tool)
                self.assertFalse(window.isVisible())
                main._hide_dialog_for_interactive_map.assert_called_once()
                controller._stop_define_tool()

    def start_and_pick_a_centre(self, layer):
        controller = self.controller(layer, "EPSG:32630")
        controller._start_define_tool()
        tool = controller._tool
        fid = next(layer.getFeatures()).id()
        tool._fid, tool._center, tool._state = fid, QgsPointXY(500000.0, 4400000.0), map_tool._ST_MAJOR
        tool._redraw()
        self.assertFalse(tool._rb_ellipse.asGeometry().isEmpty())
        return controller, tool, fid

    def test_a_crs_change_cancels_the_definition(self):
        for change in ("canvas", "layer"):
            with self.subTest(change=change):
                layer = turbine_layer("EPSG:32630")
                controller, tool, fid = self.start_and_pick_a_centre(layer)
                if change == "canvas":
                    self.canvas.setDestinationCrs(crs("EPSG:25830"))
                else:
                    layer.setCrs(crs("EPSG:25830"))
                self.assertIsNone(controller._tool)
                self.assertTrue(tool._rb_ellipse.asGeometry().isEmpty())
                # The tool would still finish its ellipse if it got a click: nothing reaches the layer.
                tool._finish()
                self.assertEqual(read_overrides(layer), {})

    def test_rule_checked_again_before_saving(self):
        layer = turbine_layer("EPSG:32630")
        controller, _tool, fid = self.start_and_pick_a_centre(layer)
        # The map changes CRS without its signal reaching the controller.
        self.canvas.blockSignals(True)
        self.canvas.setDestinationCrs(crs("EPSG:4326"))
        self.canvas.blockSignals(False)
        controller._on_ellipse_defined(fid, SpacingSpec(8.0, 5.0, 30.0, "manual_screen"))
        self.assertEqual(read_overrides(layer), {})
        self.assertIsNone(controller._tool)

    def test_messages_are_translated(self):
        texts = (_DEFINE_RULE_STATUS, "Definición cancelada: ha cambiado el sistema de coordenadas del mapa o de la capa.")
        for lang in ("en", "fr", "de"):
            with mock.patch.object(i18n, "current_language", return_value=lang):
                for text in texts:
                    with self.subTest(lang=lang, text=text[:30]):
                        self.assertNotEqual(i18n.tr_text(text), text)


if __name__ == "__main__":
    unittest.main()
