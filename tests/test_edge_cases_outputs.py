# -*- coding: utf-8 -*-
"""The warnings of the edge cases in every output of Dev (#63, P3, decision 10): the results window, the message
bar, the comparator, the CSV, the summary layer, the JSON and the report; none when there is nothing; and the
non-finite values with their label («NaN», «+inf», «−inf») where they are shown."""
import csv
import html
import json
import math
import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer  # noqa: E402
from qgis.PyQt.QtCore import QVariant  # noqa: E402

from VelantisWind import results_dialog  # noqa: E402
from VelantisWind.ag_core import edge_cases as ec  # noqa: E402
from VelantisWind.ag_core.log_text import log_text, shown  # noqa: E402
from VelantisWind.ag_core.qgis_io import export, layers  # noqa: E402
from VelantisWind.ag_core.results.model_config_html import model_config_html_v2  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import notices  # noqa: E402
from VelantisWind.energy_core import dialog_controller  # noqa: E402
from VelantisWind.i18n import tr_text  # noqa: E402
from tests import test_breakdown_consumers as consumers  # noqa: E402
from tests.test_edge_cases_calculation import LINEAR, WS, _AepCase, physics  # noqa: E402

NAN, INF = math.nan, math.inf
ORDINARY_RECORD = {"result_schema_version", "wake_config", "convergence", "persistent_warnings", "ti_aggregation"}
_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _no_constants(name):
    raise ValueError(f"constante no estándar en el JSON: {name}")


class OutputsTest(_AepCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ordinary = cls.compute(cls, LINEAR)
        # A2A with blockage and ss_gamma = −inf: WS_eff = +inf with a finite AEP, a warning of the edge cases.
        cls.edge = cls.compute(cls, physics(engine="All2AllIterative",
                                            blockage=cfg.Component("SelfSimilarityDeficit", {"ss_gamma": -INF}),
                                            blockage_superposition=cfg.Component("LinearSum", {})),
                               compute_variants=False)
        cls.weighted = cls.compute(cls, WS)  # the exception of WeightedSum, with its note

    def texts(self, result):
        return [str(shown(w, tr_text)) for w in (result.get("edge_cases") or {}).get("warnings") or []]

    def outputs(self, result):
        """Every output of a result, as text: window, message bar, CSV, JSON, summary layer and report."""
        dlg = results_dialog.AEPResultsDialog(None, result)
        self.addCleanup(dlg.deleteLater)
        bar = []
        with mock.patch.object(dialog_controller, "show_message_bar", side_effect=lambda *a, **k: bar.append(str(a[1]))):
            dialog_controller._show_result_summary(result)
        path = os.path.join(self.folder.name, "t.csv")
        export.export_per_turbine_to_csv(result["per_turbine_table"], path, result=result)
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        with open(export.wake_json_path(path), encoding="utf-8") as fh:
            record = json.loads(fh.read())
        for key in ("edge_cases", "executed_ws"):  # what P3 adds is strict JSON (the configuration is the user's)
            if key in record:
                json.loads(json.dumps(record[key], allow_nan=False), parse_constant=_no_constants)
        layer = export.create_summary_layer(result, "resumen")
        self.addCleanup(QgsProject.instance().removeMapLayer, layer.id())
        summary = [f["wake_warn"] for f in layer.getFeatures()]
        return {"window": dlg.lbl_wake_warnings.text(), "bar": " ".join(bar), "csv": rows[0]["Wake warnings"],
                "json": record, "layer": summary[0], "report": html.unescape(model_config_html_v2(result, tr_text))}

    def test_every_warning_in_every_output(self):
        warnings = self.texts(self.edge)
        self.assertTrue(any("velocidad efectiva no finita" in w for w in warnings))
        out = self.outputs(self.edge)
        self.assertEqual(out["json"]["edge_cases"]["warnings"], [str(w) for w in self.edge["edge_cases"]["warnings"]])
        self.assertEqual(out["json"]["edge_cases"]["diagnoses"], json.loads(json.dumps(self.edge["edge_cases"]["diagnoses"])))
        for warning in warnings:
            for name in ("window", "bar", "csv", "layer", "report"):
                with self.subTest(output=name, warning=warning):
                    self.assertIn(html.escape(warning) if name == "window" else warning, out[name])

    def test_each_kind_of_warning_in_every_output(self):
        """A synthetic result with a warning of each kind (negative and non-finite speeds, P and power not finite,
        AEP cases that may have energy, partial totals of turbines and sectors, the exception not applied) reaches
        every output, the comparator and the notes included (Sol, P3 r1)."""
        from VelantisWind.ag_core.simulation import zero_node
        ws = np.array([[[1.0, -2.0], [NAN, 3.0]], [[INF, 4.0], [5.0, 6.0]]])
        aep = np.array([[[NAN, 1.0], [2.0, 3.0]], [[1.0, 1.0], [2.0, 3.0]]])
        p = np.array([[[0.1, 0.1], [0.2, 0.3]], [[0.4, 0.1], [0.2, NAN]]])
        diagnosis = ec.simulation_diagnosis(ws_eff=ws, aep=aep, p=p, power=aep, frequency=np.full((2, 2, 1), 0.5),
                                            directions=[0.0, 90.0])
        raw = list(ec.diagnosis_warnings(diagnosis, "Cálculo principal")["warnings"])
        raw.append(log_text(zero_node.NOT_APPLIED, reason="prueba"))
        warnings = [str(shown(w, tr_text)) for w in raw]
        for piece in ("velocidad efectiva negativa", "velocidad efectiva no finita", "P no finita", "potencia no finita",
                      "casos que pueden tener energía", "AEP parcial", "AEP por sector parcial", "no aplicada"):
            self.assertTrue(any(piece in w for w in warnings), piece)
        r = dict(self.ordinary, edge_cases={"diagnoses": {"A_WTB": diagnosis}, "warnings": raw},
                 simulation_notes=list(self.ordinary["simulation_notes"]) + raw)
        out = self.outputs(r)
        self.assertEqual(out["json"]["edge_cases"]["warnings"], [str(w) for w in raw])
        dlg = results_dialog.ScenarioComparisonDialog(None, r, self.ordinary)
        self.addCleanup(dlg.deleteLater)
        out["comparator"] = dlg.findChild(QtWidgets.QTextBrowser).toPlainText()
        for warning in warnings:
            for name in ("window", "bar", "csv", "layer", "report", "comparator"):
                with self.subTest(output=name, warning=warning):
                    expected = {"window": html.escape(warning), "comparator": "⚠ " + warning}.get(name, warning)
                    self.assertIn(expected, out[name])  # in the comparator, its warning, not the note

    def test_the_warnings_of_a_calculation_go_to_the_notes(self):
        self.assertTrue(self.edge["edge_cases"]["warnings"])
        for warning in self.edge["edge_cases"]["warnings"]:
            self.assertIn(warning, self.edge["simulation_notes"])

    def test_the_log(self):
        """Each warning once, as a warning; the cases without energy (an empty sector at 0 m/s), only as a note."""
        from VelantisWind.ag_core import aep_compute as ac
        from qgis.core import Qgis
        logged = []
        with mock.patch.object(ac, "_log", side_effect=lambda msg, level=Qgis.Info: logged.append((str(msg), level))):
            r = self.compute(LINEAR, wrg=self.empty_wrg)
        notes = [m for m, level in logged if "casos sin energía" in m]
        self.assertTrue(notes)
        self.assertTrue(all(level == Qgis.Info for m, level in logged if "casos sin energía" in m))
        self.assertFalse(any("casos sin energía" in str(w) for w in notices.result_warnings(r)))
        with mock.patch.object(ac, "_log", side_effect=lambda msg, level=Qgis.Info: logged.append((str(msg), level))):
            del logged[:]
            r = self.compute(physics(engine="All2AllIterative",
                                     blockage=cfg.Component("SelfSimilarityDeficit", {"ss_gamma": -INF}),
                                     blockage_superposition=cfg.Component("LinearSum", {})), compute_variants=False)
        for warning in r["edge_cases"]["warnings"]:
            self.assertEqual([level for m, level in logged if m == str(warning)], [Qgis.Warning])

    def test_the_note_of_the_exception(self):
        raw = next(n for n in self.weighted["simulation_notes"] if "se calcula aparte" in str(n))
        note = str(shown(raw, tr_text))
        out = self.outputs(self.weighted)
        self.assertEqual(out["json"]["executed_ws"], dict(self.weighted["executed_ws"], note=str(raw)))
        self.assertIn(note, out["report"])
        self.assertNotIn(note, out["bar"])  # a note, not a warning

    def test_nothing_new_in_an_ordinary_result(self):
        self.assertNotIn("edge_cases", self.ordinary)
        out = self.outputs(self.ordinary)
        self.assertEqual(set(out["json"]), ORDINARY_RECORD)
        self.assertEqual(notices.result_warnings(self.ordinary), list(self.ordinary.get("persistent_warnings") or []))
        for name in ("window", "bar", "csv", "layer", "report"):
            self.assertNotIn("aparte", out[name])
            self.assertNotIn("no finit", out[name])

    def test_the_auxiliary_convergence_is_said(self):
        r = dict(self.weighted, convergence=dict(self.weighted["convergence"], auxiliary_zero={
            "PropagateUpDownIterative": {"converged": False, "calls": 1, "states": {"max_iter": 1}}}))
        warnings = [str(shown(w, tr_text)) for w in notices.result_warnings(r)]
        self.assertTrue(any(w.startswith("Simulación auxiliar de 0 m/s: Convergencia de PropagateUpDownIterative")
                            for w in warnings))
        self.assertIn("Simulación auxiliar de 0 m/s: PropagateUpDownIterative no convergió",
                      html.unescape(model_config_html_v2(r, tr_text)))


class LabelsTest(unittest.TestCase):
    """The non-finite values with their label, never «nan», «0.0 %» nor «OK»; the finite ones as always."""

    def test_the_label(self):
        self.assertEqual([ec.non_finite_label(v) for v in (NAN, INF, -INF, np.float32("nan"), 1.0, 0, None, "x")],
                         ["NaN", "+inf", "−inf", "NaN", None, None, None, None])

    def test_the_formats_of_the_window(self):
        for fmt in (results_dialog._fmt_mwh, results_dialog._fmt_mw, results_dialog._fmt_pct,
                    results_dialog._fmt_signed_mwh, results_dialog._fmt_signed_pct):
            with self.subTest(fmt=fmt.__name__):
                self.assertEqual([fmt(v) for v in (NAN, INF, -INF)], ["NaN", "+inf", "−inf"])
        self.assertEqual((results_dialog._fmt_mwh(12345.6), results_dialog._fmt_pct(12.34),
                          results_dialog._fmt_signed_mwh(1.0), results_dialog._fmt_mw(0.0)),
                         ("12.345,6", "12,3 %", "+1,0", "-"))

    def test_the_message_bar(self):
        r = consumers.v2_result()
        r["aep_wake_MWh"] = NAN
        r["breakdown"]["L_total"]["mwh"] = INF
        msg = dialog_controller._summary_message(r)
        self.assertIn("AEP neto: NaN MWh", msg)
        self.assertIn("Pérdida total: +inf MWh", msg)
        self.assertNotIn("nan", msg)

    def test_the_sectors_and_the_balance(self):
        r = consumers.v2_result()
        r["aep_wake_MWh"] = NAN
        dlg = results_dialog.AEPResultsDialog(None, r)
        self.addCleanup(dlg.deleteLater)
        texts = [w.text() for w in dlg.findChildren(QtWidgets.QLabel)]
        sectors = next(t for t in texts if "Total sectores" in t)
        self.assertIn("no comparable: valor no finito", sectors)
        self.assertNotIn("(OK)", sectors)
        balance = next(t for t in texts if "Bruto" in t and "Neto" in t)
        self.assertIn("Neto NaN MWh", balance)
        self.assertIn("no comparable: valor no finito", balance)

    def test_the_comparator(self):
        a, b = consumers.v2_result(), consumers.v2_result()
        a["per_model_aep_MWh"] = dict(a["per_model_aep_MWh"], **{"WTG-A": NAN})
        dlg = results_dialog.ScenarioComparisonDialog(None, a, b)
        self.addCleanup(dlg.deleteLater)
        cells = {t.item(i, 0).text(): [t.item(i, c).text() for c in range(1, t.columnCount())]
                 for t in dlg.findChildren(QtWidgets.QTableWidget) for i in range(t.rowCount())
                 if t.item(i, 0) and t.item(i, 0).text() == "WTG-A"}
        self.assertEqual(cells["WTG-A"][:4], ["NaN", results_dialog._fmt_mwh(b["per_model_aep_MWh"]["WTG-A"]), "NaN", "NaN"])

    def test_the_csv(self):
        rows = [dict(row) for row in consumers.v2_result()["per_turbine_table"]]
        rows[0]["aep_mwh"], rows[1]["aep_mwh"], rows[2]["aep_mwh"] = NAN, INF, 91.25
        path = os.path.join(_SETTINGS.name, "labels.csv")
        export.export_per_turbine_to_csv(rows, path)
        with open(path, encoding="utf-8-sig") as fh:
            values = [r["Net AEP [MWh/year]"] for r in csv.DictReader(fh)]
        self.assertEqual(values, ["NaN", "+inf", "91.25"])

    def test_the_layers(self):
        rows = [{"aep_mwh": v} for v in (NAN, INF, 5.0, 7.0, -INF)]
        layers._decorate_model_rows(rows)
        self.assertEqual([r.get("model_rank") for r in rows], [None, None, 2, 1, None])
        self.assertEqual(rows[3]["model_perf_pct"], 100.0)
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "turbinas", "memory")
        layer.dataProvider().addAttributes([QgsField("aep_mwh", QVariant.Double)])
        layer.updateFields()
        feats = []
        for i, v in enumerate((5.0, INF, 7.0, 9.0, NAN)):
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000.0 + 100.0 * i, 4400000.0)))
            f["aep_mwh"] = v
            feats.append(f)
        layer.dataProvider().addFeatures(feats)
        QgsProject.instance().addMapLayer(layer)
        self.addCleanup(QgsProject.instance().removeMapLayer, layer.id())
        # The default style of QGIS needs QgsApplication, which the tests do not start: a ramp of its own.
        from qgis.core import QgsGradientColorRamp
        from qgis.PyQt.QtGui import QColor
        style = mock.Mock()
        style.colorRamp.side_effect = lambda _name: QgsGradientColorRamp(QColor(255, 0, 0), QColor(0, 255, 0))
        with mock.patch.object(layers.QgsStyle, "defaultStyle", return_value=style):
            self.assertTrue(layers.apply_energy_renderer(layer))
        ranges = layer.renderer().ranges()
        self.assertEqual((ranges[0].lowerValue(), ranges[-1].upperValue(), len(ranges)), (5.0, 9.0, 5))
        self.assertIsNotNone(layer.renderer().sourceColorRamp())


if __name__ == "__main__":
    unittest.main()
