# -*- coding: utf-8 -*-
"""The AEP results are written into the layer each row computed with, matched in the project CRS, or not at all with
a warning."""
import math
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
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDefaultValue,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsProviderRegistry,
    QgsRenderContext,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant  # noqa: E402

# Without an initialised QGIS the registry only has the built-in providers; delimited text is a plugin of the install.
QgsProviderRegistry.instance(os.environ.get("QGIS_PLUGINPATH") or "/usr/lib/qgis/plugins")

from VelantisWind.ag_core import aep_compute  # noqa: E402
from VelantisWind.ag_core.qgis_io import layers  # noqa: E402
from VelantisWind.energy_core import dialog_controller  # noqa: E402
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


P = [(500000.0, 4400000.0), (501000.0, 4400000.0), (502000.0, 4400000.0)]


def point_layer(name, points, crs="EPSG:32630"):
    layer = QgsVectorLayer(f"Point?crs={crs}", name, "memory")
    features = []
    for x, y in points:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    return layer


def rows(model, points, aep=1000.0):
    return [{"model": model, "x": x, "y": y, "aep_mwh": aep + i} for i, (x, y) in enumerate(points)]


def model(name, layer):
    return {"name": name, "meta": {}, "source_layer_id": layer.id(), "source_layer_name": layer.name()}


def names(layer):
    return [f.name() for f in layer.fields()]


def values(layer, field="aep_mwh"):
    if layer.fields().indexFromName(field) < 0:
        return None
    return [f[field] for f in layer.getFeatures()]


class ResultsCase(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.logged = []

    def update(self, table, models):
        return layers.update_layers_from_results(
            table, models, tol_m=30.0, log=lambda msg, level=None: self.logged.append((str(msg), level)),
            warning_level=Qgis.Warning,
        )

    def warnings(self):
        return [msg for msg, level in self.logged if level == Qgis.Warning]


class TargetLayerTest(ResultsCase):
    def test_results_go_to_the_row_layer_whatever_its_name(self):
        named = point_layer("T1 (CSV)", P)
        chosen = point_layer("My layout", P)
        self.assertEqual(self.update(rows("T1", P), [model("T1", chosen)]), ["My layout"])
        self.assertEqual(values(chosen), [1000.0, 1001.0, 1002.0])
        self.assertIsNone(values(named))

    def test_layer_in_degrees_gets_the_values_on_its_points(self):
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        to_layer = QgsCoordinateTransform(QgsProject.instance().crs(), crs, QgsProject.instance())
        lonlat = [(p.x(), p.y()) for p in (to_layer.transform(QgsPointXY(x, y)) for x, y in reversed(P))]
        layer = point_layer("Degrees", lonlat, crs="EPSG:4326")
        # The results come in project metres, in the original order: each lands on its own point.
        self.assertEqual(self.update(rows("T1", P), [model("T1", layer)]), ["Degrees"])
        self.assertEqual(values(layer), [1002.0, 1001.0, 1000.0])

    def test_default_values_on_update_do_not_rewrite_the_layer(self):
        layer = point_layer("Rules", P)
        layer.dataProvider().addAttributes([QgsField("note", QVariant.String)])
        layer.updateFields()
        note = layer.fields().indexFromName("note")
        layer.dataProvider().changeAttributeValues({f.id(): {note: "original"} for f in layer.getFeatures()})
        layers.ensure_result_fields(layer)
        layer.setDefaultValueDefinition(note, QgsDefaultValue("'overwritten'", True))
        layer.setDefaultValueDefinition(layer.fields().indexFromName("aep_mwh"), QgsDefaultValue("42", True))
        self.assertEqual(self.update(rows("T1", P), [model("T1", layer)]), ["Rules"])
        self.assertEqual(values(layer), [1000.0, 1001.0, 1002.0])
        self.assertEqual(values(layer, "note"), ["original"] * 3)

    def test_existing_result_fields_that_keep_the_values(self):
        for rank_type in (QVariant.Int, QVariant.LongLong, QVariant.Double):
            with self.subTest(rank_type=rank_type):
                QgsProject.instance().clear()
                layer = point_layer("Typed", P)
                layer.dataProvider().addAttributes([QgsField("model", QVariant.String), QgsField("aep_mwh", QVariant.Double),
                                                    QgsField("model_rank", rank_type)])
                layer.updateFields()
                self.assertEqual(self.update(rows("T1", P), [model("T1", layer)]), ["Typed"])
                self.assertEqual(values(layer), [1000.0, 1001.0, 1002.0])
                self.assertEqual(sorted(values(layer, "model_rank")), [1, 2, 3])

    def test_geopackage_takes_the_results_again(self):
        # The fields the plugin created, read back from the file, keep their types and take the next results.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.gpkg")
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"), "GPKG")
        for x, y in P:
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            writer.addFeature(feature)
        del writer
        first = QgsVectorLayer(path, "Package", "ogr")
        QgsProject.instance().addMapLayer(first)
        self.assertEqual(self.update(rows("T1", P), [model("T1", first)]), ["Package"])
        again = QgsVectorLayer(path, "Package again", "ogr")
        self.assertTrue(again.isValid())
        QgsProject.instance().addMapLayer(again)
        self.assertEqual(self.update(rows("T1", P, aep=2000.0), [model("T1", again)]), ["Package again"])
        self.assertEqual(values(again), [2000.0, 2001.0, 2002.0])
        self.assertEqual(self.warnings(), [])

    def test_geojson_reads_fields_that_were_always_empty_as_text(self):
        # The first results leave the optional fields empty; reopened, GeoJSON reads them as text. They still only get
        # NULLs, so the next results are written.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.geojson")
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"), "GeoJSON")
        for x, y in P:
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            writer.addFeature(feature)
        del writer
        first = QgsVectorLayer(path, "Json", "ogr")
        QgsProject.instance().addMapLayer(first)
        self.assertEqual(self.update(rows("T1", P, aep=1000.25), [model("T1", first)]), ["Json"])
        again = QgsVectorLayer(path, "Json again", "ogr")
        self.assertTrue(again.isValid())
        self.assertEqual(again.fields().field("loss_ti_mwh").type(), QVariant.String)
        QgsProject.instance().addMapLayer(again)
        self.assertEqual(self.update(rows("T1", P, aep=2000.25), [model("T1", again)]), ["Json again"])
        self.assertEqual(values(again), [2000.25, 2001.25, 2002.25])
        self.assertEqual(self.warnings(), [])

    def test_csv_takes_the_results_again_as_text(self):
        # A CSV keeps no field types: reopened, the result fields are text. The next results are written as text, as
        # before, since the text reads back as the same number.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.csv")
        with open(path, "w") as fh:
            fh.write("WKT,name\n" + "".join(f'"POINT ({x} {y})",t{i}\n' for i, (x, y) in enumerate(P)))

        def opened(name):
            layer = QgsVectorLayer(path, name, "ogr")
            layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
            QgsProject.instance().addMapLayer(layer)
            return layer

        self.assertEqual(self.update(rows("T1", P, aep=1000.25), [model("T1", opened("Csv"))]), ["Csv"])
        again = opened("Csv again")
        self.assertEqual(again.fields().field("aep_mwh").typeName(), "String")
        # Their text order differs from their numeric order: every turbine still gets a symbol of its class.
        table = [dict(row, aep_mwh=aep) for row, aep in zip(rows("T1", P), (1000.0, 900.0, 1100.0))]
        self.assertEqual(self.update(table, [model("T1", again)]), ["Csv again"])
        self.assertEqual(self.warnings(), [])
        self.assertEqual([float(v) for v in values(opened("Csv read"))], [1000.0, 900.0, 1100.0])
        renderer = again.renderer()
        context = QgsRenderContext()
        context.expressionContext().appendScope(QgsExpressionContextUtils.layerScope(again))
        renderer.startRender(context, again.fields())
        symbols = []
        for feature in again.getFeatures():
            # As when the map is drawn: the feature in the expression context.
            context.expressionContext().setFeature(feature)
            symbols.append(renderer.symbolForFeature(feature, context))
        renderer.stopRender(context)
        self.assertTrue(all(symbol is not None for symbol in symbols))

    def test_a_large_whole_number_kept_as_text(self):
        field = QgsField("model_rank", QVariant.String)
        for number in (9007199254740993, 2 ** 63 - 1):
            with self.subTest(number=number):
                self.assertTrue(layers._text_keeps_number(field, number))

    def test_two_models_on_the_same_layer_keep_the_last(self):
        layer = point_layer("Shared", P)
        table = rows("T1", P, aep=1000.0) + rows("T2", P, aep=2000.0)
        self.update(table, [model("T1", layer), model("T2", layer)])
        self.assertEqual(values(layer), [2000.0, 2001.0, 2002.0])

    def test_shared_layer_keeps_the_turbine_data_of_the_first_model(self):
        layer = point_layer("Shared", P)
        first, second = model("T1", layer), model("T2", layer)
        first["meta"], second["meta"] = {"diam": 100.0}, {"diam": 200.0}
        table = rows("T1", P, aep=1000.0) + rows("T2", P, aep=2000.0)
        real, calls = layers.push_results_to_point_layer, []

        def first_refused(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("refused")
            return real(*args, **kwargs)

        # Even when the first model's results cannot be written and the second's can.
        with mock.patch.object(layers, "push_results_to_point_layer", side_effect=first_refused):
            self.assertEqual(self.update(table, [first, second]), ["Shared"])
        self.assertEqual(values(layer), [2000.0, 2001.0, 2002.0])
        self.assertIsNone(layer.customProperty("velantis/diameter_m", None))
        self.assertIsNone(layer.customProperty("velantis/model_name", None))
        self.update(table, [first, second])
        self.assertEqual(float(layer.customProperty("velantis/diameter_m")), 100.0)
        self.assertEqual(layer.customProperty("velantis/model_name"), "T1")

    def test_missing_layer_is_reported_by_its_name(self):
        layer = point_layer("Gone", P)
        gone = TurbineModelInput("T1", object(), source_layer_id=layer.id(), source_layer_name="Gone").to_compute_model_dict()
        QgsProject.instance().removeMapLayer(layer.id())
        self.assertEqual(self.update(rows("T1", P), [gone]), [])
        self.assertIn("'Gone'", self.warnings()[0])


class MatchingDistanceTest(ResultsCase):
    def test_up_to_thirty_metres_inclusive(self):
        layer = point_layer("L", P)
        shifted = [(P[0][0] + 29.9, P[0][1]), (P[1][0] + 30.0, P[1][1]), (P[2][0] + 30.1, P[2][1])]
        self.assertEqual(self.update(rows("T1", shifted), [model("T1", layer)]), ["L"])
        self.assertEqual(values(layer), [1000.0, 1001.0, None])
        self.assertIn("2 de 3", self.warnings()[0])

    def shared_filtered_layer(self):
        """A layer whose two points, 20 m apart, start with aep_mwh 0 and are filtered by "aep_mwh" < 1500."""
        layer = QgsVectorLayer("Point?crs=EPSG:32630&field=aep_mwh:double", "Shared", "memory")
        features = []
        for x in (500000.0, 500020.0):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([0.0])
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 4400000.0)))
            features.append(feature)
        layer.dataProvider().addFeatures(features)
        QgsProject.instance().addMapLayer(layer)
        layer.setSubsetString('"aep_mwh" < 1500')
        return layer

    def final(self, layer):
        layer.setSubsetString("")
        return [(f.geometry().asPoint().x(), f["model"], f["aep_mwh"]) for f in layer.getFeatures()]

    def test_results_land_on_the_points_they_were_computed_on(self):
        # The layer is in two rows. The first write hides the second point; the second row's results still land on
        # their own points, matched with the points read before any write (C13: the last row's results).
        layer = self.shared_filtered_layer()
        points = [(500000.0, 4400000.0), (500020.0, 4400000.0)]
        table = [dict(r, aep_mwh=a) for r, a in zip(rows("M1", points), (1000.0, 2000.0))]
        table += [dict(r, aep_mwh=a) for r, a in zip(rows("M2", points), (1100.0, 1200.0))]
        self.update(table, [model("M1", layer), model("M2", layer)])
        self.assertEqual(self.final(layer), [(500000.0, "M2", 1100.0), (500020.0, "M2", 1200.0)])

    def test_a_point_without_its_own_result_does_not_take_its_neighbours(self):
        # Only the second point was computed (the first fell outside the resource): its results must not land on the
        # first point when the first write hides it.
        layer = self.shared_filtered_layer()
        table = [dict(rows("M1", [(500020.0, 4400000.0)])[0], aep_mwh=2000.0), dict(rows("M2", [(500020.0, 4400000.0)])[0], aep_mwh=1200.0)]
        self.update(table, [model("M1", layer), model("M2", layer)])
        self.assertEqual(self.final(layer), [(500000.0, None, 0.0), (500020.0, "M2", 1200.0)])

    def test_a_point_takes_the_nearest_result_not_the_last(self):
        # Two results of one row next to one point: the nearest wins, whatever their order.
        layer = point_layer("Close", P[:1])
        near, far = rows("T1", [(P[0][0] + 5.0, P[0][1])], aep=1.0)[0], rows("T1", [(P[0][0] + 20.0, P[0][1])], aep=2.0)[0]
        for table in ([near, far], [far, near]):
            with self.subTest(order=[r["aep_mwh"] for r in table]):
                self.update(table, [model("T1", layer)])
                self.assertEqual(values(layer), [1.0])

    def test_nothing_matched_is_reported_and_not_counted(self):
        layer = point_layer("L", P[:1])
        self.assertEqual(self.update(rows("T1", [(P[0][0] + 30.1, P[0][1])]), [model("T1", layer)]), [])
        self.assertIn("no se ha escrito nada", self.warnings()[0])
        self.assertFalse([msg for msg, _ in self.logged if msg.startswith("Capas actualizadas")])
        # Nothing written, not even the result fields.
        self.assertEqual(names(layer), [])

    def test_partial_write_is_reported(self):
        layer = point_layer("L", P[:2])
        table = rows("T1", [(P[0][0] + 10.0, P[0][1]), (P[1][0] + 30.1, P[1][1])])
        self.assertEqual(self.update(table, [model("T1", layer)]), ["L"])
        self.assertIn("1 de 2", self.warnings()[0])


class LayersThatCannotTakeResultsTest(ResultsCase):
    """Nothing is written, there is a warning naming the layer, and the other layers are still written."""

    def assertSkipped(self, layer, text):
        other = point_layer("Other", P)
        table = rows("T1", P) + rows("T2", P, aep=2000.0)
        updated = self.update(table, [model("T1", layer), model("T2", other)])
        self.assertEqual(updated, ["Other"])
        self.assertEqual(values(other), [2000.0, 2001.0, 2002.0])
        [warning] = self.warnings()
        self.assertIn(layer.name(), warning)
        self.assertIn(text, warning)

    def test_delimited_text_layer(self):
        if "delimitedtext" not in QgsProviderRegistry.instance().providerList():
            self.skipTest("QGIS delimited-text provider not found")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.csv")
        with open(path, "w") as fh:
            fh.write("x,y\n" + "".join(f"{x},{y}\n" for x, y in P))
        layer = QgsVectorLayer(f"file://{path}?type=csv&xField=x&yField=y&crs=EPSG:32630", "Text", "delimitedtext")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        self.assertSkipped(layer, "no admite añadir o cambiar sus campos")

    def test_layer_in_edit_mode(self):
        layer = point_layer("Editing", P)
        for pending in (False, True):
            with self.subTest(pending=pending):
                self.logged.clear()
                layer.startEditing()
                if pending:
                    layer.changeGeometry(next(layer.getFeatures()).id(), QgsGeometry.fromPointXY(QgsPointXY(*P[0])))
                self.assertSkipped(layer, "modo edición")
                self.assertIsNone(values(layer))
                layer.rollBack()

    def test_shapefile_with_shortened_field_names(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "layout.shp")
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"), "ESRI Shapefile")
        for x, y in P:
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            writer.addFeature(feature)
        del writer
        layer = QgsVectorLayer(path, "Shape", "ogr")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        self.assertSkipped(layer, "aep_free_mwh")
        # Refused before writing: no partial write and no field added, shortened or not.
        self.assertEqual(names(QgsVectorLayer(path, "Again", "ogr")), ["name"])

    def test_writes_that_return_false(self):
        for method, fields_exist in (("addAttribute", False), ("changeAttributeValues", False), ("changeAttributeValues", True)):
            with self.subTest(method=method, fields_exist=fields_exist):
                QgsProject.instance().clear()
                self.logged.clear()
                layer = point_layer("Failing", P)
                if fields_exist:
                    layers.ensure_result_fields(layer)
                schema = names(layer.dataProvider())
                setattr(layer, method, lambda *a: False)
                self.assertSkipped(layer, "Failing")
                self.assertEqual(values(layer) or [None] * 3, [None] * 3)
                self.assertFalse(layer.isEditable())
                self.assertEqual(names(layer.dataProvider()), schema)

    def test_fields_the_layer_has_not_reloaded_are_kept(self):
        for failure in ("commit", "startEditing"):
            with self.subTest(failure=failure):
                QgsProject.instance().clear()
                self.logged.clear()
                layer = point_layer("Stale", P)
                provider = layer.dataProvider()
                # Fields added to the provider behind the layer's back, with values, and no updateFields().
                provider.addAttributes([QgsField("user_note", QVariant.String), QgsField("aep_mwh", QVariant.Double)])
                provider.changeAttributeValues({f.id(): {0: "KEEP", 1: 123.0} for f in provider.getFeatures()})
                setattr(layer, "commitChanges" if failure == "commit" else "startEditing", lambda *a: False)
                self.assertSkipped(layer, "Stale")
                self.assertEqual(names(provider)[:2], ["user_note", "aep_mwh"])
                self.assertEqual([(f["user_note"], f["aep_mwh"]) for f in provider.getFeatures()], [("KEEP", 123.0)] * 3)

    def test_two_layers_on_the_same_table(self):
        # A field of the user's, added through one layer, is unknown to another layer opened before on the same table:
        # the second fails on fields that already exist, and nothing of the user's nor of the first layer is removed.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "shared.gpkg")
        fields = QgsFields()
        fields.append(QgsField("group", QVariant.Int))
        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"), "GPKG")
        for group, (x, y) in enumerate(P[:2], start=1):
            feature = QgsFeature(fields)
            feature.setAttributes([group])
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            writer.addFeature(feature)
        del writer
        first, second = QgsVectorLayer(path, "First", "ogr"), QgsVectorLayer(path, "Second", "ogr")
        first.setSubsetString('"group" = 1')
        second.setSubsetString('"group" = 2')
        QgsProject.instance().addMapLayers([first, second])
        first.startEditing()
        first.addAttribute(QgsField("note", QVariant.String))
        first.changeAttributeValue(next(first.getFeatures()).id(), first.fields().indexFromName("note"), "KEEP")
        self.assertTrue(first.commitChanges())
        table = rows("T1", P[:1]) + rows("T2", P[1:2], aep=2000.0)
        self.assertEqual(self.update(table, [model("T1", first), model("T2", second)]), ["First"])
        [warning] = self.warnings()
        self.assertIn("Second", warning)
        again = QgsVectorLayer(path, "Again", "ogr")
        self.assertIn("note", names(again))
        self.assertEqual([(f["group"], f["note"], f["aep_mwh"]) for f in again.getFeatures()], [(1, "KEEP", 1000.0), (2, None, None)])

    def test_fields_a_failed_commit_leaves_are_reported_and_kept(self):
        # The commit reaches the provider, which adds the fields, and then reports a failure. No field is removed: the
        # schema read before cannot tell them from fields another layer on the same table added since.
        layer = point_layer("Sticky", P)
        real_commit = layer.commitChanges
        layer.commitChanges = lambda *a: (real_commit(*a), False)[1]
        real = layer.dataProvider()
        provider = mock.Mock(wraps=real)
        provider.capabilities.return_value = real.capabilities()
        provider.fields.side_effect = real.fields
        provider.getFeatures.side_effect = real.getFeatures
        layer.dataProvider = lambda: provider
        self.assertSkipped(layer, "tiene ahora los campos de resultados")
        self.assertIn("aep_mwh", self.warnings()[0])
        provider.deleteAttributes.assert_not_called()
        self.assertIn("aep_mwh", names(real))

    def test_calculated_field_that_cannot_be_written(self):
        layer = point_layer("Calculated", P)
        layer.addExpressionField("42", QgsField("aep_mwh", QVariant.Double))
        self.assertSkipped(layer, "Calculated")
        self.assertEqual(values(layer), [42.0] * 3)

    def test_result_field_of_another_type(self):
        for name, typ, value in (("aep_mwh", QVariant.Int, 7), ("aep_mwh", QVariant.Bool, False),
                                 ("model", QVariant.Int, 7), ("model_rank", QVariant.String, "first")):
            with self.subTest(field=name, type=typ):
                QgsProject.instance().clear()
                self.logged.clear()
                layer = point_layer("Typed", P)
                layer.dataProvider().addAttributes([QgsField(name, typ)])
                layer.updateFields()
                self.assertEqual(int(layer.fields().field(name).type()), int(typ))
                layer.dataProvider().changeAttributeValues({f.id(): {0: value} for f in layer.getFeatures()})
                self.assertSkipped(layer, name)
                self.assertIn("otro tipo", self.warnings()[0])
                # Nothing written and no field added.
                self.assertEqual(names(layer), [name])
                self.assertEqual(values(layer, name), [value] * 3)

    def test_result_field_with_fewer_decimals_or_a_shorter_text(self):
        # A field of the right type that would round or cut a value: a turbulence of 0.073 kept as 0.1.
        for field, row_value, kept in ((QgsField("ti_eff", QVariant.Double, "", 10, 1), 0.073, 0.5),
                                       (QgsField("model", QVariant.String, "", 3), "T1-long", "old")):
            with self.subTest(field=field.name()):
                QgsProject.instance().clear()
                self.logged.clear()
                layer = point_layer("Narrow", P)
                layer.dataProvider().addAttributes([field])
                layer.updateFields()
                layer.dataProvider().changeAttributeValues({f.id(): {0: kept} for f in layer.getFeatures()})
                other = point_layer("Other", P)
                table = [dict(row, model="T1-long", ti_eff=0.073) for row in rows("T1", P)]
                updated = self.update(table + rows("T2", P, aep=2000.0), [model("T1-long", layer), model("T2", other)])
                self.assertEqual(updated, ["Other"])
                [warning] = self.warnings()
                self.assertIn(field.name(), warning)
                self.assertIn("menos decimales", warning)
                self.assertEqual(names(layer), [field.name()])
                self.assertEqual(values(layer, field.name()), [kept] * 3)

    def test_mapinfo_fixed_fields_that_would_cut_the_values(self):
        # A decimal without decimals truncates 0.073 to 0, and a text field of 3 bytes cuts "ñé" (4 bytes).
        for field, value in ((QgsField("ti_eff", QVariant.Double, "", 10, 0), 0.073),
                             (QgsField("model", QVariant.String, "", 3), "ñé")):
            with self.subTest(field=field.name()):
                QgsProject.instance().clear()
                self.logged.clear()
                folder = tempfile.TemporaryDirectory()
                self.addCleanup(folder.cleanup)
                path = os.path.join(folder.name, "fixed.tab")
                fields = QgsFields()
                fields.append(field)
                writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"),
                                             "MapInfo File")
                for x, y in P:
                    feature = QgsFeature(fields)
                    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                    writer.addFeature(feature)
                del writer
                layer = QgsVectorLayer(path, "Fixed", "ogr")
                self.assertTrue(layer.isValid())
                QgsProject.instance().addMapLayer(layer)
                before = values(layer, field.name())
                table = [dict(row, model=value if field.name() == "model" else "T1", ti_eff=0.073) for row in rows("T1", P)]
                name = value if field.name() == "model" else "T1"
                self.assertEqual(self.update(table, [model(name, layer)]), [])
                self.assertIn(field.name(), self.warnings()[0])
                again = QgsVectorLayer(path, "Again", "ogr")
                self.assertEqual(names(again), [field.name()])
                self.assertEqual(values(again, field.name()), before)

    def mapinfo_with_a_narrow_aep(self, folder):
        """A MapInfo layer whose aep_mwh holds 7, 8 and 9 in a field of width 6 (999999.5 does not fit), and whose
        ti_eff holds NaN."""
        path = os.path.join(folder, "narrow.tab")
        fields = QgsFields()
        fields.append(QgsField("aep_mwh", QVariant.Double, "", 6, 1))
        fields.append(QgsField("ti_eff", QVariant.Double))
        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32630"),
                                     "MapInfo File")
        for (x, y), aep in zip(P, (7.0, 8.0, 9.0)):
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            feature.setAttribute("aep_mwh", aep)
            feature.setAttribute("ti_eff", float("nan"))
            writer.addFeature(feature)
        del writer
        layer = QgsVectorLayer(path, "Narrow", "ogr")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        return path, layer

    def test_failed_write_without_transactions_is_reported_not_written_back(self):
        # MapInfo writes some values and refuses another. Nothing is written back nor removed (what was read before
        # cannot tell this write from another layer's): the warning says which points and fields may be half-written.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path, layer = self.mapinfo_with_a_narrow_aep(folder.name)
        real = layer.dataProvider()
        provider = mock.Mock(wraps=real)
        provider.capabilities.return_value = real.capabilities()
        provider.fields.side_effect = real.fields
        provider.getFeatures.side_effect = real.getFeatures
        provider.storageType.side_effect = real.storageType
        layer.dataProvider = lambda: provider
        table = [dict(row, aep_mwh=aep) for row, aep in zip(rows("T1", P), (100.0, 999999.5, 300.0))]
        self.assertEqual(self.update(table, [model("T1", layer)]), [])
        [warning] = self.warnings()
        # The provider kept part of the write: the warning does not say that nothing was written.
        self.assertNotIn("no se han escrito los resultados", warning)
        self.assertIn("punto(s) de la capa 'Narrow' pueden tener resultados escritos a medias", warning)
        self.assertIn("tiene ahora los campos de resultados model, aep_free_mwh", warning)
        provider.changeAttributeValues.assert_not_called()
        provider.deleteAttributes.assert_not_called()
        again = QgsVectorLayer(path, "Again", "ogr")
        self.assertEqual(names(again)[:3], ["aep_mwh", "ti_eff", "model"])
        self.assertNotEqual(values(again), [7.0, 8.0, 9.0])

    def test_nothing_changed_is_not_written_back(self):
        # A failure before writing anything: no point is reported as half-written, although NaN never equals NaN.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        _path, layer = self.mapinfo_with_a_narrow_aep(folder.name)
        real = layer.dataProvider()
        provider = mock.Mock(wraps=real)
        provider.capabilities.return_value = real.capabilities()
        provider.fields.side_effect = real.fields
        provider.getFeatures.side_effect = real.getFeatures
        layer.dataProvider = lambda: provider
        layer.startEditing = lambda: False
        self.assertEqual(self.update(rows("T1", P), [model("T1", layer)]), [])
        provider.changeAttributeValues.assert_not_called()
        self.assertNotIn("a medias", self.warnings()[0])

    def test_result_field_with_room_for_the_values(self):
        layer = point_layer("Roomy", P)
        layer.dataProvider().addAttributes([QgsField("ti_eff", QVariant.Double, "", 10, 3), QgsField("model", QVariant.String, "", 10)])
        layer.updateFields()
        table = [dict(row, ti_eff=v) for row, v in zip(rows("T1", P), (0.073, float("nan"), None))]
        self.assertEqual(self.update(table, [model("T1", layer)]), ["Roomy"])
        self.assertEqual(self.warnings(), [])
        self.assertEqual(values(layer, "model"), ["T1"] * 3)
        self.assertEqual(values(layer, "ti_eff")[0], 0.073)

    def test_joined_result_field_leaves_the_joined_layer_untouched(self):
        joined = QgsVectorLayer("None", "Joined", "memory")
        joined.dataProvider().addAttributes([QgsField("key", QVariant.Int), QgsField("aep_mwh", QVariant.Double)])
        joined.updateFields()
        feature = QgsFeature(joined.fields())
        feature.setAttributes([1, 7.0])
        joined.dataProvider().addFeatures([feature])
        QgsProject.instance().addMapLayer(joined)
        layer = point_layer("Joining", P)
        layer.dataProvider().addAttributes([QgsField("key", QVariant.Int)])
        layer.updateFields()
        layer.dataProvider().changeAttributeValues({f.id(): {0: 1} for f in layer.getFeatures()})
        info = QgsVectorLayerJoinInfo()
        info.setJoinLayer(joined)
        info.setJoinFieldName("key")
        info.setTargetFieldName("key")
        info.setPrefix("")
        info.setEditable(True)
        self.assertTrue(layer.addJoin(info))
        joined.startEditing()
        self.addCleanup(lambda: joined.rollBack() if joined.isEditable() else None)
        self.assertSkipped(layer, "aep_mwh")
        self.assertEqual([f["aep_mwh"] for f in joined.getFeatures()], [7.0])
        self.assertFalse(joined.isModified())

    def test_project_editing_layers_in_groups_leaves_other_layers_alone(self):
        pending = point_layer("Pending", P[:1])
        QgsProject.instance().setTransactionMode(Qgis.TransactionMode.BufferedGroups)
        pending.startEditing()
        self.addCleanup(lambda: pending.rollBack() if pending.isEditable() else None)
        pending.changeGeometry(next(pending.getFeatures()).id(), QgsGeometry.fromPointXY(QgsPointXY(1.0, 1.0)))
        layer = point_layer("Grouped", P)
        self.assertEqual(self.update(rows("T1", P), [model("T1", layer)]), [])
        self.assertIn("en grupo", self.warnings()[0])
        self.assertIsNone(values(layer))
        self.assertTrue(pending.isEditable())
        self.assertTrue(pending.isModified())

    def test_edit_session_that_cannot_open(self):
        layer = point_layer("Locked", P)
        layer.startEditing = lambda: False
        self.assertSkipped(layer, "Locked")
        self.assertIsNone(values(layer))

    def test_commit_that_fails_leaves_nothing_written_nor_open(self):
        for fields_exist in (False, True):
            with self.subTest(fields_exist=fields_exist):
                QgsProject.instance().clear()
                self.logged.clear()
                layer = point_layer("Locked", P)
                if fields_exist:
                    layers.ensure_result_fields(layer)
                schema = names(layer.dataProvider())
                layer.commitChanges = lambda *a: False
                self.assertSkipped(layer, "Locked")
                self.assertFalse(layer.isEditable())
                self.assertEqual(values(layer) or [None] * 3, [None] * 3)
                self.assertEqual(names(layer.dataProvider()), schema)


class ResultsNeverStopTheAepTest(ResultsCase):
    """A failing layer does not stop the result from being registered, exported and shown."""

    def test_failing_layer_keeps_the_result(self):
        for failure in ("edit mode", "commit"):
            with self.subTest(failure=failure):
                QgsProject.instance().clear()
                QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
                layer = point_layer("Failing", P)
                if failure == "edit mode":
                    layer.startEditing()
                else:
                    layer.commitChanges = lambda *a: False
                self.assertResultShown(layer)
                layer.rollBack()

    def assertResultShown(self, layer):
        result = {"per_turbine_table": rows("T1", P), "aep_wake_MWh": 1.0, "aep_free_MWh": 1.0,
                  "wake_loss_MWh": 0.0, "wake_loss_pct": 0.0}
        config = EnergyRunConfig(models=[TurbineModelInput("T1", object(), source_layer_id=layer.id())])
        state = types.SimpleNamespace(messages=[], to_energy_config=lambda: config, base_export_dir="",
                                      models=[{"source_row_index": 0, "source_layer_name": layer.name()}])
        dialog = types.SimpleNamespace(_register_last_aep_result=mock.Mock())
        with mock.patch.object(dialog_controller, "build_energy_dialog_state", return_value=state), \
                mock.patch.object(dialog_controller, "_validate_before_run", return_value=True), \
                mock.patch.object(dialog_controller, "create_progress_dialog"), \
                mock.patch.object(dialog_controller, "close_progress_dialog"), \
                mock.patch("VelantisWind.energy_core.runner.validate_energy_config", return_value=[]), \
                mock.patch.object(aep_compute, "compute_aep_from_ui", return_value=result), \
                mock.patch.object(dialog_controller, "export_results_from_dialog") as export, \
                mock.patch.object(dialog_controller, "_show_results_dialog") as show, \
                mock.patch.object(QtWidgets.QMessageBox, "critical") as critical:
            dialog_controller.run_compute_and_update_from_dialog(dialog)
        critical.assert_not_called()
        dialog._register_last_aep_result.assert_called_once()
        export.assert_called_once()
        show.assert_called_once()
        self.assertIsNone(values(layer))

    def test_summary_layer_is_still_created(self):
        result = {"per_turbine_table": [], "per_model_table": [{"model": "T1", "aep_mwh": 1.0}]}
        with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=("", "")):
            dialog_controller.export_results_from_dialog(None, result, "")
        self.assertEqual([l.name() for l in QgsProject.instance().mapLayersByName("AEP resumen por modelo")],
                         ["AEP resumen por modelo"])


if __name__ == "__main__":
    unittest.main()
