# -*- coding: utf-8 -*-
"""Regression checks for issue #43: partial AEP must never be silent."""
import html
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core.orchestration.layout_builder import build_layout_arrays  # noqa: E402
from VelantisWind.ag_core.results.coverage import partial_aep_warning  # noqa: E402


def _layout(models):
    return build_layout_arrays(
        models=models, site=object(), wasp_dir="", use_wrg=False, wrg_paths=[],
        dtype=float, read_xy_csv=lambda path: ([], []),
        bbox_from_site=lambda site: (0, 100, 0, 100),
    )


class PartialResourceCoverageTest(unittest.TestCase):
    def test_excluded_turbines_are_counted_by_model_before_filtering(self):
        result = _layout([
            {"name": "A", "coords_xy": [(5, 5), (200, 5), (10, 10)]},
            {"name": "B", "coords_xy": [(300, 300), (5, 5)]},
        ])
        self.assertEqual(result["skipped"], 2)
        self.assertEqual(result["skipped_by_model"], {"A": 1, "B": 1})
        self.assertEqual(result["xs"].tolist(), [5, 10, 5])
        self.assertEqual(result["type_i"].tolist(), [0, 0, 1])

    def test_excluded_turbines_use_the_model_names_of_the_rest_of_the_result(self):
        from VelantisWind.ag_core.results.summary import build_names_by_type
        models = [
            {"meta": {"name": "Modelo real"}, "coords_xy": [(5, 5), (200, 5)]},
            {"coords_xy": [(300, 300), (5, 5)]},
        ]
        result = _layout(models)
        self.assertEqual(result["skipped_by_model"], {"Modelo real": 1, "WT_1": 1})
        self.assertEqual(set(result["skipped_by_model"]), set(build_names_by_type(models).values()))

    def test_one_model_and_fully_covered_layout(self):
        result = _layout([{"name": "Only", "coords_xy": [(2, 2), (102, 102)]}])
        self.assertIsNone(result["type_i"])
        self.assertEqual(result["skipped_by_model"], {"Only": 1})
        ok = _layout([{"name": "Only", "coords_xy": [(2, 2)]}])
        self.assertEqual(ok["skipped"], 0)
        self.assertEqual(ok["skipped_by_model"], {})

    def test_all_turbines_outside_still_stop_the_aep(self):
        with self.assertRaisesRegex(RuntimeError, "fuera del área"):
            _layout([{"name": "Only", "coords_xy": [(500, 500)]}])

    def test_partial_warning_covers_totals_model_counts_and_stale_layer_results(self):
        res = {"skipped_outside_grid": 2, "skipped_by_model": {"A": 1, "B": 1},
               "turbines_inside_grid": 3}
        msg = partial_aep_warning(res)
        for fragment in ("3 de 5", "A: 1", "B: 1", "AEP", "potencia instalada",
                         "resultados anteriores", "no pertenecen"):
            self.assertIn(fragment, msg)

    def test_coverage_warning_has_translations_in_all_ui_languages(self):
        from VelantisWind import i18n, results_dialog  # registers the coverage translations
        from unittest import mock
        i18n._ensure()
        for language in ("en", "fr", "de"):
            with self.subTest(language=language), mock.patch.object(i18n, "current_language", return_value=language):
                translated = partial_aep_warning({
                    "skipped_outside_grid": 1, "turbines_inside_grid": 2,
                    "skipped_by_model": {"Custom WT": 1}
                }, i18n.tr_text)
                self.assertIn("Custom WT: 1", translated)
                self.assertIn("2", translated)
                self.assertNotIn("Cálculo parcial", translated)
                self.assertNotIn("Las turbinas no calculadas", translated)

    def test_warning_is_last_message_after_layer_information(self):
        from unittest import mock
        from qgis.core import Qgis
        from VelantisWind.energy_core import dialog_controller
        payload = {
            "aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0,
            "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0,
            "skipped_outside_grid": 1, "turbines_inside_grid": 2,
            "skipped_by_model": {"T1": 1},
        }
        with mock.patch.object(dialog_controller, "show_message_bar") as show:
            dialog_controller._show_result_summary(payload, layer_message="Rows: layer A")
        self.assertGreaterEqual(show.call_count, 3)
        self.assertEqual(show.call_args_list[-2].kwargs["level"], Qgis.Info)
        self.assertEqual(show.call_args_list[-1].kwargs["level"], Qgis.Warning)
        self.assertIn("T1: 1", show.call_args_list[-1].args[1])

    def test_the_bar_says_which_calculation_did_not_converge(self):
        # Discrete round 3, B2: the main calculation and the variants of the breakdown, each named, as in the results
        # window (notices.result_warnings).
        from unittest import mock
        from VelantisWind.energy_core import dialog_controller
        loop = {"All2AllIterative": {"converged": False, "calls": 1, "states": {"no_check": 1}}}
        payload = {"aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0, "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0,
                   "convergence": {"main": loop, "variants": loop}}
        with mock.patch.object(dialog_controller, "show_message_bar") as show:
            dialog_controller._show_result_summary(payload)
        texts = [str(c.args[1]) for c in show.call_args_list if "Convergencia" in str(c.args[1])]
        self.assertEqual(len(texts), 2, texts)
        self.assertTrue(texts[0].startswith("Cálculo principal: Convergencia de All2AllIterative"), texts)
        self.assertTrue(texts[1].startswith("Variantes del desglose: Convergencia de All2AllIterative"), texts)

    def test_model_names_with_markup_are_shown_literally_in_the_qgis_bar(self):
        from unittest import mock
        from qgis.PyQt import QtWidgets
        from qgis.gui import QgsMessageBar
        from VelantisWind.energy_core import dialog_controller, ui_feedback
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        name = "WT <b>Prototype</b> & <x>"
        payload = {
            "aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0,
            "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0,
            "skipped_outside_grid": 1, "turbines_inside_grid": 2,
            "skipped_by_model": {name: 1},
        }
        bar = QgsMessageBar()
        with mock.patch.object(ui_feedback, "iface") as iface:
            iface.messageBar.return_value = bar
            dialog_controller._show_result_summary(payload)
        shown = [b.toPlainText() for b in bar.currentItem().findChildren(QtWidgets.QTextBrowser)]
        self.assertIn(f"{name}: 1", " ".join(shown))
        # The shared text stays unescaped for the dialog label and the HTML report.
        self.assertIn(f"{name}: 1", partial_aep_warning(payload))

    def test_distinct_user_model_names_survive_dialog_and_export_localization(self):
        from unittest import mock
        from qgis.PyQt import QtWidgets
        from VelantisWind import i18n, results_dialog
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        result = {
            "aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0,
            "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0,
            "skipped_outside_grid": 3, "turbines_inside_grid": 2,
            "skipped_by_model": {"Modelo Norte": 1, "Model Norte": 2},
            "per_turbine_table": [],
        }
        expected = "Modelo Norte: 1, Model Norte: 2"
        for lang in ("en", "fr", "de"):
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang), \
                    mock.patch.object(results_dialog, "current_language", return_value=lang):
                dlg = results_dialog.AEPResultsDialog(None, result)
                try:
                    # A real dialog has already gone through apply_i18n in __init__.
                    self.assertIn(expected, dlg.lbl_coverage_warning.text())
                    self.assertIn(expected, dlg.txt_report.toPlainText())
                    report = dlg._wrap_report_document(dlg._build_full_report_html())
                    self.assertIn(expected, report)
                    self.assertNotIn(dlg._COVERAGE_PLACEHOLDER, report)
                    self.assertIn("Modelo Norte: 1", report)
                    self.assertIn("Model Norte: 2", report)
                finally:
                    dlg.close()

    def test_escaped_html_names_survive_the_final_export(self):
        from unittest import mock
        from qgis.PyQt import QtWidgets
        from VelantisWind import i18n, results_dialog
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        model = "Modelo <b>Norte</b> & <x>"
        result = {
            "aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0,
            "wake_loss_MWh": 100.0, "wake_loss_pct": 10.0,
            "skipped_outside_grid": 1, "turbines_inside_grid": 2,
            "skipped_by_model": {model: 1}, "per_turbine_table": [],
        }
        with mock.patch.object(i18n, "current_language", return_value="en"), \
                mock.patch.object(results_dialog, "current_language", return_value="en"):
            dlg = results_dialog.AEPResultsDialog(None, result)
            try:
                report = dlg._wrap_report_document(dlg._build_full_report_html())
                self.assertIn("Modelo &lt;b&gt;Norte&lt;/b&gt; &amp; &lt;x&gt;: 1", report)
                self.assertNotIn("<b>Norte</b>", report)
                self.assertIn(model + ": 1", dlg.lbl_coverage_warning.text())
            finally:
                dlg.close()

    def test_scenario_comparison_says_which_scenario_is_partial(self):
        from VelantisWind import results_dialog
        full = {"aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0}
        partial = dict(full, skipped_outside_grid=1, turbines_inside_grid=2,
                       skipped_by_model={"WT <b>Prototype</b> & <x>": 1})
        dlg = results_dialog.ScenarioComparisonDialog(None, partial, full)
        text = dlg.lbl_coverage_warning.text()
        self.assertTrue(text.startswith("A: " + partial_aep_warning(partial, results_dialog._tr)))
        self.assertIn("WT <b>Prototype</b> & <x>: 1", text)
        self.assertNotIn("B: ", text)
        self.assertEqual(dlg.lbl_coverage_warning.textFormat(), QtCore.Qt.PlainText)
        both = results_dialog.ScenarioComparisonDialog(None, partial, partial)
        self.assertEqual(both.lbl_coverage_warning.text().count("WT <b>Prototype</b> & <x>: 1"), 2)
        self.assertIn("\nB: ", both.lbl_coverage_warning.text())
        neither = results_dialog.ScenarioComparisonDialog(None, full, full)
        self.assertIsNone(neither.lbl_coverage_warning)

    def test_only_the_coverage_placeholder_is_filled(self):
        from VelantisWind import results_dialog
        mark = results_dialog.AEPResultsDialog._COVERAGE_PLACEHOLDER
        dlg = results_dialog.AEPResultsDialog.__new__(results_dialog.AEPResultsDialog)
        # A model may be named like the placeholder: its name stays when there is no warning...
        dlg.results = {"skipped_outside_grid": 0}
        self.assertEqual(dlg._insert_coverage_banner(f"<td>{mark}</td>"), f"<td>{mark}</td>")
        # ...and only the banner's placeholder, which comes first, is filled when there is one.
        dlg.results = {"skipped_outside_grid": 1, "turbines_inside_grid": 1, "skipped_by_model": {"A": 1}}
        filled = dlg._insert_coverage_banner(f"<p>{mark}</p><td>{mark}</td>")
        self.assertIn("A: 1", filled)
        self.assertTrue(filled.endswith(f"<td>{mark}</td>"))

    def test_model_names_stay_literal_in_the_tables_and_the_report(self):
        import os
        from unittest import mock
        from VelantisWind import i18n, results_dialog
        names = ["Model 1", "Blockage test", "WT <b>Prototype</b> & <x>"]
        result = {
            "aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0, "wake_loss_MWh": 100.0,
            "per_model_aep_MWh": {n: 300.0 for n in names}, "per_model_aep_free_MWh": {n: 330.0 for n in names},
            "per_model_n_turbines": {n: 1 for n in names},
            "per_turbine_table": [{"model": n, "x": 1.0, "y": 2.0, "aep_mwh": 300.0} for n in names],
        }
        path = os.path.join(_SETTINGS.name, "names.html")
        for lang in ("en", "fr", "de"):
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang), \
                    mock.patch.object(results_dialog, "current_language", return_value=lang):
                dlg = results_dialog.AEPResultsDialog(None, result)
                models = [dlg.table_models.item(r, 0).text() for r in range(dlg.table_models.rowCount())]
                turbines = [dlg.table_turbines.item(r, 1).text() for r in range(dlg.table_turbines.rowCount())]
                self.assertEqual(sorted(models), sorted(names))
                self.assertEqual(turbines, names)
                with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(path, "")), \
                        mock.patch.object(QtWidgets.QMessageBox, "information"), \
                        mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
                    dlg._export_report_html()
                warning.assert_not_called()
                with open(path, encoding="utf-8") as f:
                    exported = f.read()
                tab = dlg.txt_report.toPlainText()
                for name in names:
                    self.assertIn(name, tab)
                    # Per-model table, per-turbine table and cluster section.
                    self.assertGreaterEqual(exported.count(html.escape(name)), 3)
                self.assertNotIn("<b>Prototype</b>", exported)
                self.assertFalse(any("\ue100" <= ch <= "\ue1ff" for ch in exported + tab))

    def test_notes_and_scenario_labels_keep_user_data_literal(self):
        from unittest import mock
        from VelantisWind import i18n, results_dialog
        from VelantisWind.ag_core.log_text import log_text
        plain = "BastankhahGaussianDeficit usa una k fija: la TI ambiente y el modelo de turbulencia apenas cambian el déficit base del wake."
        note = log_text("Modelo «{name}»: {warning}", name="Model 1", warning=log_text("sin bloqueo"))
        result = {"aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0, "simulation_notes": [note, plain]}
        with mock.patch.object(i18n, "current_language", return_value="de"), \
                mock.patch.object(results_dialog, "current_language", return_value="de"):
            shown = results_dialog.format_report_note(note, results_dialog._tr)
            dlg = results_dialog.AEPResultsDialog(None, result)
            report = dlg._wrap_report_document(dlg._build_full_report_html())
            comparison = results_dialog.ScenarioComparisonDialog(None, result, result, label_a="Model 1", label_b="B")
            config = comparison.findChildren(QtWidgets.QTextBrowser)[0].toPlainText()
        self.assertIn("Model 1", shown)
        for text in (report, dlg.txt_report.toPlainText(), config):
            self.assertIn(shown, text)
            # A plain Spanish note is still translated.
            self.assertNotIn("usa una k fija", text)
        self.assertIn("Model 1", config.splitlines()[0])

    def test_slots_are_filled_in_one_pass_before_the_banner(self):
        from VelantisWind import results_dialog
        texts = []
        html = results_dialog._slot(texts, "<vw-slot-1>") + "|" + results_dialog._slot(texts, "Beta")
        self.assertEqual(results_dialog._fill_slots(texts, html), "&lt;vw-slot-1&gt;|Beta")
        # The warning, with its own user data, goes in after the slots are filled.
        result = {"aep_wake_MWh": 900.0, "aep_free_MWh": 1000.0, "per_model_aep_MWh": {"Alpha": 900.0},
                  "skipped_outside_grid": 1, "turbines_inside_grid": 1, "skipped_by_model": {"<vw-slot-0>x": 1},
                  "simulation_notes": ["Nota <vw-slot-0> original"], "selection_executed": {"engine": "<vw-slot-0>"}}
        dlg = results_dialog.AEPResultsDialog(None, result)
        report = dlg._wrap_report_document(dlg._build_full_report_html())
        # Text that looks like a slot is escaped, so it is never filled.
        self.assertIn("&lt;vw-slot-0&gt;x: 1", report)
        self.assertIn("Nota &lt;vw-slot-0&gt; original", report)
        self.assertNotIn("Alpha original", report)
        self.assertIn("Nota <vw-slot-0> original", dlg.txt_report.toPlainText())
        comparison = results_dialog.ScenarioComparisonDialog(None, result, result, label_a="Alpha")
        self.assertIn("<vw-slot-0>", comparison.findChildren(QtWidgets.QTextBrowser)[0].toPlainText())

    def test_full_resource_has_no_warning_and_old_payload_remains_supported(self):
        self.assertEqual(partial_aep_warning({"skipped_outside_grid": 0}), "")
        self.assertIn("1 de 2", partial_aep_warning({
            "skipped_outside_grid": 1, "per_turbine_table": [{"x": 2.0}]
        }))


if __name__ == "__main__":
    unittest.main()
