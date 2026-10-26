# -*- coding: utf-8 -*-
"""The configuration and the warnings of a result of schema 2 in every place it is shown or exported (#46a, the
findings 6, 7 and 12 of the adversarial round, with the design agreed): the CSV and the JSON next to it, the summary
layer, the point layers, the results window and the scenario comparator."""
import csv
import json
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorFileWriter, QgsVectorLayer  # noqa: E402

from VelantisWind import results_dialog  # noqa: E402
from VelantisWind.ag_core import aep_compute as ac  # noqa: E402
from VelantisWind.ag_core.qgis_io import export, layers  # noqa: E402
from tests.test_resource_settings import model  # noqa: E402
from tests.test_wake_activation import _Case  # noqa: E402

_CWD = os.getcwd()
# CumulativeWakeSum carries a persistent warning (decision 19); CGI7 and CGI21 differ only in their nodes.
WARNED = {"superposition": "CumulativeWakeSum", "rotor": {"class": "CGIRotorAvg", "n": 7}}


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class ExportsTest(_Case):
    def test_the_csv_and_its_json(self):
        r = self.aep(WARNED)
        path = os.path.join(self.folder, "t.csv")
        export.export_per_turbine_to_csv(r["per_turbine_table"], path, r)
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        texts = export.wake_texts(r)
        self.assertEqual(list(rows[0])[-2:], ["Wake configuration", "Wake warnings"])  # the last two columns
        self.assertTrue(rows and all(row["Wake configuration"] == texts["wake_id"] for row in rows))
        self.assertTrue(all(row["Wake warnings"] == texts["wake_warn"] for row in rows))
        self.assertIn("CumulativeWakeSum", texts["wake_warn"])
        with open(export.wake_json_path(path), encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertEqual(record["result_schema_version"], 2)
        self.assertEqual(set(record["wake_config"]), set(r["wake_config"]))
        self.assertEqual(record["wake_config"]["executed"]["rotor"]["params"]["n"]["value"], 7)
        self.assertEqual(record["ti_aggregation"], r["ti_aggregation"])
        self.assertTrue(record["persistent_warnings"])
        # Without a result (or with one of schema 1), the CSV as before and no JSON.
        other = os.path.join(self.folder, "u.csv")
        export.export_per_turbine_to_csv(r["per_turbine_table"], other)
        with open(other, encoding="utf-8-sig") as fh:
            self.assertNotIn("Wake configuration", next(csv.reader(fh)))
        self.assertFalse(os.path.exists(export.wake_json_path(other)))

    def test_the_export_fails_without_its_json(self):
        r = self.aep(WARNED)
        path = os.path.join(self.folder, "t.csv")
        os.mkdir(export.wake_json_path(path))  # the JSON cannot be written
        with self.assertRaises(OSError):
            export.export_per_turbine_to_csv(r["per_turbine_table"], path, r)

    def test_the_summary_layer(self):
        r = self.aep(WARNED)
        layer = export.create_summary_layer(r, "resumen")
        self.addCleanup(QgsProject.instance().removeMapLayer, layer.id())
        texts = export.wake_texts(r)
        for f in layer.getFeatures():
            self.assertEqual(f["wake_id"], texts["wake_id"])
            self.assertEqual(f["wake_warn"], texts["wake_warn"])
            self.assertEqual(json.loads(f["wake_cfg"])["wake_config"]["executed"]["rotor"]["class"], "CGIRotorAvg")


class PointLayersTest(_Case):
    def layer(self, path=None):
        r = self.aep(WARNED)
        rows = [dict(row, **export.wake_texts(r)) for row in r["per_turbine_table"]]
        memory = QgsVectorLayer("Point?crs=EPSG:32630", "turbinas", "memory")
        feats = []
        for row in rows:
            f = QgsFeature(memory.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row["x"], row["y"])))
            feats.append(f)
        memory.dataProvider().addFeatures(feats)
        if path is None:
            return memory, rows
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "MapInfo File"
        QgsVectorFileWriter.writeAsVectorFormatV3(memory, path, QgsProject.instance().transformContext(), options)
        return QgsVectorLayer(path, "turbinas", "ogr"), rows

    def test_the_aep_gives_them_to_the_layers_it_updates(self):
        # The ordinary path of the dialog: compute_and_update with update_project_layers (its default).
        with mock.patch.object(ac, "update_layers_from_results") as update:
            r = ac.compute_and_update("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08,
                                      wake_physics=dict({"version": 1}, **WARNED))
        rows = update.call_args.args[0]
        texts = export.wake_texts(r)
        self.assertEqual(len(rows), len(r["per_turbine_table"]))
        self.assertTrue(all(row["wake_id"] == texts["wake_id"] and row["wake_warn"] == texts["wake_warn"]
                            for row in rows))
        self.assertNotIn("wake_id", r["per_turbine_table"][0])  # the result itself is not changed

    def test_each_entity_carries_the_texts(self):
        layer, rows = self.layer()
        self.assertEqual(layers.push_results_to_point_layer(layer, rows), len(rows))
        for f in layer.getFeatures():
            self.assertEqual(f["wake_id"], rows[0]["wake_id"])
            self.assertEqual(f["wake_warn"], rows[0]["wake_warn"])

    def test_a_text_a_mapinfo_table_cannot_keep_is_refused(self):
        # (A shapefile does not take the results of schema 2 at all: their field names are longer than 10 characters.)
        layer, rows = self.layer(os.path.join(self.folder, "t.tab"))
        self.assertTrue(layer.isValid())
        rows = [dict(row, wake_warn=row["wake_warn"] + " | " + "á" * 60) for row in rows]  # 255 or more bytes
        self.assertGreater(len(rows[0]["wake_warn"].encode("utf-8")), 254)
        with self.assertRaisesRegex(RuntimeError, "254 bytes"):
            layers.push_results_to_point_layer(layer, rows)
        self.assertNotIn("aep_mwh", [f.name() for f in layer.fields()])  # nothing written
        # A text that fits is kept whole.
        short = [dict(row, wake_warn="x" * 200) for row in rows]
        layers.push_results_to_point_layer(layer, short)
        layer = QgsVectorLayer(layer.source(), "turbinas", "ogr")
        self.assertEqual({f["wake_warn"] for f in layer.getFeatures()}, {"x" * 200})


class WindowTest(_Case):
    def dialog(self, result):
        dlg = results_dialog.AEPResultsDialog(None, result)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_the_identification_and_the_warnings_before_the_figures(self):
        r = self.aep(WARNED)
        dlg = self.dialog(r)
        layout = dlg.tab_global.layout()
        self.assertEqual(dlg.lbl_wake_id.text(), str(r["wake_config"]["identification"]))
        self.assertFalse(dlg.lbl_wake_id.isHidden())
        self.assertIn("CumulativeWakeSum", dlg.lbl_wake_warnings.text())
        self.assertFalse(dlg.lbl_wake_warnings.isHidden())
        group = dlg.lbl_aep_free.parentWidget()
        self.assertLess(layout.indexOf(dlg.lbl_wake_id), layout.indexOf(group))
        self.assertLess(layout.indexOf(dlg.lbl_wake_warnings), layout.indexOf(group))
        # The executed configuration, folded, after the figures.
        self.assertEqual(layout.indexOf(dlg.sec_executed), layout.indexOf(group) + 1)
        self.assertFalse(dlg.sec_executed.isExpanded())
        self.assertIn("CGIRotorAvg(n=7", dlg.txt_executed.toPlainText())
        # Without warnings, no block.
        self.assertTrue(self.dialog(self.aep({})).lbl_wake_warnings.isHidden())

    def test_each_ti_says_its_aggregation(self):
        r = self.aep({})
        dlg = self.dialog(r)
        headers = dlg._TURBINE_HEADERS_V2
        for key, header in (("ti_ambient", "TI ambiente"), ("ti_effective", "TI efectiva")):
            item = dlg.table_turbines.horizontalHeaderItem(headers.index(header))
            self.assertEqual(item.toolTip(), r["ti_aggregation"][key])
        html = dlg._wrap_report_document(dlg._build_full_report_html())  # the exported report
        self.assertIn(r["ti_aggregation"]["ti_ambient"], html)
        self.assertIn(r["ti_aggregation"]["ti_effective"], html)


class TranslatedOnceTest(_Case):
    """The configuration, translated, is not translated a second time by the localization of the report's HTML (which
    reads English back as Spanish fragments: «Blockage superposition» became «Bloqueo superposition»)."""

    def test_the_report_and_the_comparator_in_english(self):
        from VelantisWind import i18n
        r = self.aep(WARNED)
        with mock.patch.object(i18n, "current_language", return_value="en"):
            dlg = results_dialog.AEPResultsDialog(None, r)
            self.addCleanup(dlg.deleteLater)
            cmp_dlg = results_dialog.ScenarioComparisonDialog(None, r, self.aep({}))
            self.addCleanup(cmp_dlg.deleteLater)
            texts = {"report": dlg._last_report_html,
                     "exported": dlg._wrap_report_document(dlg._build_full_report_html()),
                     "comparator": results_dialog._fill_slots(cmp_dlg._user_texts,
                                                              i18n.translate_html(cmp_dlg._config_html()))}
        for name, html in texts.items():
            with self.subTest(name):
                self.assertIn("Blockage superposition", html)
                self.assertNotIn("Bloqueo superposition", html)
                self.assertIn("CGIRotorAvg(n=7, nodes=7)", html)


class TranslatedOnceInTheWindowTest(_Case):
    def test_the_summary_the_breakdown_and_the_export(self):
        # A turbulence without effect on the deficit, and A_0 failing: the texts translated when they are set must
        # not be translated again, in the window (apply_i18n) nor in the report and its export.
        from VelantisWind import i18n
        from VelantisWind.ag_core.simulation import runner
        from VelantisWind.ag_core.wake_setup import factory as fac
        real = runner.simulate

        def a0_fails(wfm, *a, **k):
            if type(wfm.wake_deficitModel).__name__ == "NoWakeDeficit":
                raise fac.ClassMismatch("deficit", "NoWakeDeficit", "TurboGaussianDeficit")
            return real(wfm, *a, **k)
        with mock.patch.object(runner, "simulate", side_effect=a0_fails):
            r = self.aep({"deficit": "TurboGaussianDeficit", "turbulence": "STF2017TurbulenceModel"},
                         compute_variants=True)
        expected = {"en": ("the effective TI", "Capacity factor (net)", "n/a", "MWh/MW·year"),
                    "fr": ("Variantes qui n’ont pas pu être calculées", "au moyeu", "n.d.", "MWh/MW·an"),
                    "de": ("Varianten, die nicht berechnet werden konnten", "an der Nabe", "n. v.", "MWh/MW·Jahr")}
        for language, (in_report, in_export, missing, unit) in expected.items():
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                dlg = results_dialog.AEPResultsDialog(None, r)
                self.addCleanup(dlg.deleteLater)
                exported = dlg._wrap_report_document(dlg._build_full_report_html())
                self.assertIn(in_report, dlg._last_report_html)
                self.assertIn(in_report, exported)
                self.assertIn(in_export, exported)
                # The texts set from the data (a value not available, the unit), translated once too.
                gross = dlg._TURBINE_HEADERS_V2.index("AEP bruto [MWh]")
                self.assertEqual(dlg.table_turbines.item(0, gross).text(), missing)
                self.assertTrue(dlg.lbl_spec_yield.text().endswith(unit))
                self.assertIn(unit, exported)
                self.assertNotIn("n/d", exported)
                self.assertNotIn("año", exported)
                if language == "en":
                    self.assertIn("the effective TI", dlg.lbl_loss_ti.text())
                    self.assertNotIn("efectiva", dlg.lbl_loss_ti.text() + exported)


class ComparatorTest(_Case):
    def test_cgi7_and_cgi21_and_the_warnings(self):
        a = self.aep(WARNED)
        b = self.aep({"rotor": {"class": "CGIRotorAvg", "n": 21}})
        dlg = results_dialog.ScenarioComparisonDialog(None, a, b)
        self.addCleanup(dlg.deleteLater)
        html = results_dialog._fill_slots(dlg._user_texts, dlg._config_html())
        self.assertIn("CGIRotorAvg(n=7, nodos=7)", html)
        self.assertIn("CGIRotorAvg(n=21, nodos=21)", html)
        self.assertEqual(html.count("dependen del orden de las turbinas"), 1)  # the warning of the first scenario

    def test_the_selection_and_what_was_executed(self):
        from VelantisWind.ag_core.wake_setup import api, config as cfg
        config = api.gaussian_overlap_adaptation(
            cfg.WakeConfig(**{**cfg.default_config().__dict__, "rotor": cfg.Component("GaussianOverlapAvgModel", {})}),
            ["h5py"])
        a = self.aep(None, wake_physics=api.to_wake_physics(config))
        dlg = results_dialog.ScenarioComparisonDialog(None, a, self.aep({}))
        self.addCleanup(dlg.deleteLater)
        self.assertIn("GaussianOverlapAvgModel → CGIRotorAvg(n=7, nodos=7) ⚠",
                      results_dialog._fill_slots(dlg._user_texts, dlg._config_html()))


class ErrorsTest(_Case):
    def test_an_error_of_a_variant_is_shown_translated(self):
        # A_0 fails with an error of the class check; the AEP goes on, and the report (and the log) say why, in the
        # language of the interface, also in the terms that depend on it.
        from VelantisWind import i18n
        from VelantisWind.ag_core.log_text import shown
        from VelantisWind.ag_core.simulation import runner
        from VelantisWind.ag_core.wake_setup import factory as fac
        real = runner.simulate

        def a0_fails(wfm, *a, **k):
            if type(wfm.wake_deficitModel).__name__ == "NoWakeDeficit":
                raise fac.ClassMismatch("deficit", "NoWakeDeficit", "NOJDeficit")
            return real(wfm, *a, **k)
        # The message bar, as the AEP shows its warnings (translated from their template, in the main thread).
        with mock.patch.object(i18n, "current_language", return_value="en"), \
                mock.patch.object(runner, "simulate", side_effect=a0_fails), mock.patch.object(ac, "iface") as iface:
            r = self.aep({})
        shown_bar = [str(c.args[1]) for c in iface.messageBar().pushMessage.call_args_list]
        self.assertEqual(r["breakdown"]["A_0"]["state"], "failed")
        self.assertTrue(any("A_0" in line and "Class check" in line for line in shown_bar))
        self.assertFalse(any("Comprobación" in line for line in shown_bar))
        # An error whose text the second translation of the report spoiled, among them.
        r["breakdown"]["D_T"]["error"] = "ValueError: Blockage superposition"
        with mock.patch.object(i18n, "current_language", return_value="en"):
            dlg = results_dialog.AEPResultsDialog(None, r)
            self.addCleanup(dlg.deleteLater)
            for html in (dlg._last_report_html, dlg._wrap_report_document(dlg._build_full_report_html())):
                self.assertIn("A_0: ClassMismatch: Class check", html)
                self.assertIn("L_W: A_0: ClassMismatch: Class check", html)
                self.assertIn("D_T: ValueError: Blockage superposition", html)
                self.assertNotIn("Comprobación", html)
                self.assertNotIn("Bloqueo", html)


    def test_the_adaptation_of_the_api_reads_back(self):
        from VelantisWind.ag_core.wake_setup import api, config as cfg
        c, _ = api.resolve_request({"version": 1, "rotor": "GaussianOverlapAvgModel"})
        adapted = api.gaussian_overlap_adaptation(c, ["h5py"])
        self.assertEqual(cfg.WakeConfig.from_dict(json.loads(json.dumps(adapted.to_dict()))), adapted)
        # Its record is never shared: changing the dictionary written, or the one read, changes nothing else.
        written = adapted.to_dict()
        written["adaptations"][0]["used"]["n"] = 21
        self.assertEqual(adapted.adaptations[0]["used"], {"class": "CGIRotorAvg", "n": 7})
        source = adapted.to_dict()
        read = cfg.WakeConfig.from_dict(source)
        source["adaptations"][0]["used"]["n"] = 21
        self.assertEqual(read.adaptations[0]["used"], {"class": "CGIRotorAvg", "n": 7})

    def test_an_error_of_the_physics_is_shown_translated(self):
        # Through the dialog's path: the calculation raises an error of the factory, the class check or a reader.
        from VelantisWind import i18n
        from VelantisWind.ag_core.wake_setup import factory as fac
        from VelantisWind.energy_core import dialog_controller as dc
        from VelantisWind.ag_core.wake_setup import api, config as cfg
        rejected = cfg.WakeConfig(**{**cfg.default_config().__dict__,
                                     "blockage": cfg.blockage_signature("VortexDipole"),
                                     "blockage_superposition": cfg.Component("LinearSum", {})})
        with self.assertRaises(api.ConfigRejected) as ctx:
            api.check_calculable(rejected)  # PropagateDownwind with blockage: refused, with its reason (R1)
        errors = {ctx.exception: "PropagateDownwind does not support blockage",
                  fac.ClassMismatch("deficit", "BastankhahGaussianDeficit", "NOJDeficit"): "Class check",
                  fac.ReaderError("rotor", "x"): "Class check",
                  fac.FactoryError("deficit", "NOJDeficit", ValueError("x")): "PyWake could not build"}
        for exc, english in errors.items():
            shown_text = []
            with self.subTest(type(exc).__name__), mock.patch.object(i18n, "current_language", return_value="en"), \
                    mock.patch.object(dc, "_project_crs_problem", return_value=None), \
                    mock.patch.object(dc, "_read_dialog_state", return_value=mock.Mock()), \
                    mock.patch.object(dc, "_show_state_messages"), \
                    mock.patch.object(dc, "_validate_before_run", return_value=True), \
                    mock.patch.object(dc, "_resolve_layers_in_edit_mode", return_value=False), \
                    mock.patch.object(dc, "_run_energy_calculation", side_effect=exc), \
                    mock.patch.object(dc, "show_user_critical", side_effect=lambda d, t, m: shown_text.append(m)):
                dc.run_compute_and_update_from_dialog(mock.Mock())
                message = shown_text[0].split("\n\nDetails:")[0]  # the traceback that follows is technical
                self.assertIn(english, message)
                self.assertNotIn("Comprobación", message)
                self.assertNotIn("no pudo construir", message)
                self.assertNotIn("no admite bloqueo", message)


if __name__ == "__main__":
    unittest.main()
