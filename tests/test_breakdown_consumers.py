# -*- coding: utf-8 -*-
"""Every consumer of the loss breakdown with a schema-2 result of known values, and a schema-1 result read with its
own fields (#46 P3; closes #58).

Rows of #75: 4.5 ``ExportsTest.test_csv_with_signed_columns``; 4.6 ``test_summary_layer_null_not_zero``; 4.7 and 4.14
``LogTest``; 4.8 ``DialogTest.test_tables_and_sector`` and ``LayersTest``; 4.9 ``ResultTest.test_the_same_figure_in_
every_consumer``; 4.10 ``DialogTest.test_summary_with_gains_and_the_balance``; 4.11 ``test_tables_and_sector``; 4.12
``test_breakdown.BreakdownTest.test_a_failed_variant_is_not_available_never_zero_nor_the_total``; 4.13
``test_a_breakdown_not_available_is_not_zero`` and ``ComparatorTest``. Rows 4.3-4.4: ``test_breakdown.VariantsTest``
and ``BuiltVariantsTest``.
"""
import csv
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

from VelantisWind import i18n, results_dialog  # noqa: E402
from VelantisWind.ag_core.qgis_io import export, layers  # noqa: E402
from VelantisWind.ag_core.results import breakdown as bd  # noqa: E402
from VelantisWind.ag_core.results import result_v2  # noqa: E402
from VelantisWind.ag_core.results.breakdown_translations import TRANSLATIONS  # noqa: E402
from VelantisWind.energy_core import dialog_controller  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Three turbines of two models; a gain by blockage at the third and by turbulence at the first.
A0 = np.array([100.0, 100.0, 100.0])
AW = np.array([90.0, 80.0, 100.0])
AWT = np.array([92.0, 79.0, 100.0])
AWB = np.array([89.0, 79.5, 100.5])
AWTB = np.array([91.0, 78.0, 100.6])
XY = [(500000.0, 4400000.0), (501000.0, 4400000.0), (502000.0, 4400000.0)]
MODELS = [{"name": "WTG-A", "meta": {"diam": 120, "hh": 100, "p_rated_mw": 4.0}},
          {"name": "WTG-B", "meta": {"diam": 150, "hh": 120, "p_rated_mw": 5.0}}]


def v2_result(aep=None, aep_states=None, turbulence=True, blockage=True, errors=None):
    aep = dict({"A_0": A0, "A_W": AW, "A_WT": AWT, "A_WB": AWB, "A_WTB": AWTB}, **(aep or {}))
    aep_states = dict({k: bd.OK for k in bd.AEP_TERMS}, **(aep_states or {}))
    states = bd.term_states(aep_states=aep_states, turbulence=turbulence, blockage=blockage,
                            turbulence_changes_deficit=True)
    return result_v2.build_result(
        models=MODELS, xs=[x for x, _ in XY], ys=[y for _, y in XY], use_types=True, type_i=np.array([0, 0, 1]),
        skipped=0, skipped_by_model={}, aep=aep, aep_states=aep_states, term_states=states, errors=errors or {},
        ti_ambient=np.array([0.08, 0.08, 0.09]), ti_effective=np.array([0.11, np.nan, 0.12]),
        aep_per_wd_wake_mwh=[150.0, 119.6], aep_per_wd_free_mwh=[140.0, 160.0], sector_directions_deg=[0.0, 180.0],
        resource_settings={"hours_per_year": 8766.0})


def v1_result():
    """A result of the previous schema, as aep_compute produced it."""
    row = {"id": 1, "x": XY[0][0], "y": XY[0][1], "model": "WTG-A", "p_nom_mw": 4.0, "aep_mwh": 91.0,
           "aep_free_mwh": 100.0, "loss_wake_mwh": 10.0, "loss_blk_mwh": 1.0, "loss_ti_mwh": 0.0, "ti_impact_mwh": 2.0,
           "ti_eff": 0.08}
    return {"aep_wake_MWh": 91.0, "aep_free_MWh": 100.0, "wake_loss_MWh": 10.0, "wake_loss_pct": 10.0,
            "loss_ti_MWh": 0.0, "ti_impact_MWh": 2.0, "loss_blk_MWh": 1.0, "per_turbine_table": [row],
            "per_model_aep_MWh": {"WTG-A": 91.0}, "per_model_aep_free_MWh": {"WTG-A": 100.0},
            "per_model_n_turbines": {"WTG-A": 1}, "per_model_p_inst_MW": {"WTG-A": 4.0}}


class ResultTest(unittest.TestCase):
    def test_the_result_carries_the_schema_and_the_signed_breakdown(self):
        r = v2_result()
        self.assertEqual(r["result_schema_version"], 2)
        self.assertEqual(result_v2.result_schema(r), 2)
        self.assertEqual(result_v2.result_schema(v1_result()), 1)
        b = r["breakdown"]
        self.assertAlmostEqual(b["L_total"]["mwh"], b["L_W"]["mwh"] - b["D_T"]["mwh"] - b["D_B"]["mwh"])
        self.assertAlmostEqual(r["aep_wake_MWh"], float(AWTB.sum()))
        self.assertEqual(set(r["per_model_breakdown"]), {"WTG-A", "WTG-B"})
        self.assertAlmostEqual(r["per_model_breakdown"]["WTG-B"]["D_B"]["mwh"], 0.6)
        row = r["per_turbine_table"][1]
        self.assertEqual((row["ti_ambient"], row["ti_effective"], row["res_schema"]), (0.08, None, 2))
        for old in ("loss_wake_mwh", "loss_ti_mwh", "ti_impact_mwh", "loss_blk_mwh", "aep_wake_only_mwh", "ti_eff"):
            self.assertNotIn(old, row)
        for old in ("wake_loss_MWh", "loss_ti_MWh", "loss_blk_MWh", "per_model_loss_wake_MWh"):
            self.assertNotIn(old, r)
        self.assertIn("ti_effective", r["ti_aggregation"])

    def test_the_same_figure_in_every_consumer(self):
        """L_total is the same in the summary, the models, the turbines, the CSV, the message bar and the report."""
        r = v2_result()
        total = r["breakdown"]["L_total"]["mwh"]
        self.assertAlmostEqual(sum(e["L_total"]["mwh"] for e in r["per_model_breakdown"].values()), total)
        self.assertAlmostEqual(sum(row["l_total_mwh"] for row in r["per_turbine_table"]), total)
        msg = dialog_controller._summary_message(r)
        self.assertIn(f"{total:,.0f}", msg)
        # The message bar gives the total loss (gross minus net), not the wake loss (#75, row 4.9).
        self.assertIn("Pérdida total", msg)
        # A percentage not available (A_0 ≤ 0) is said in the language.
        r["breakdown"]["L_total"]["pct"] = None
        for language, missing in (("en", "n/a"), ("fr", "n.d."), ("de", "n. v.")):
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                msg = dialog_controller._summary_message(r)
                self.assertIn(f"({missing} %)", msg)
                self.assertNotIn("n/d", msg)


class LogTest(unittest.TestCase):
    def test_the_log_says_what_failed_and_never_blames_the_user(self):
        # #75, row 4.7: with the variants asked for and one failed, the log says it failed, not «not activated»;
        # row 4.14: the same figures as the window (one formula for every consumer).
        lines = []
        r = v2_result(aep={"A_W": None}, aep_states={"A_W": bd.FAILED}, errors={"A_W": "RuntimeError: x"})
        result_v2.log_breakdown(r, lines.append)
        text = "\n".join(lines)
        self.assertIn("no disponible (falló: A_W: RuntimeError: x)", text)  # with its cause
        # Δ_B is measured from A_WT: a failure of A_WT is its cause, not one of A_W.
        both = v2_result(aep={"A_W": None, "A_WT": None}, aep_states={"A_W": bd.FAILED, "A_WT": bd.FAILED},
                         errors={"A_W": "RuntimeError: w", "A_WT": "RuntimeError: wt"})
        self.assertEqual(both["breakdown"]["D_B"]["error"], "A_WT: RuntimeError: wt")
        self.assertNotIn("compute_variants", text)
        self.assertIn(f"{r['breakdown']['D_B']['mwh']:,.1f} MWh", text)
        # Every line is a template, translated when shown.
        from VelantisWind.ag_core.log_text import shown
        for language in ("en", "fr", "de"):
            with mock.patch.object(i18n, "current_language", return_value=language):
                shown_text = "\n".join(shown(line, i18n.tr_text) for line in lines)
            self.assertNotIn("no disponible", shown_text)
            self.assertNotIn("Pérdida por estelas", shown_text)


class DialogTest(unittest.TestCase):
    def dialog(self, result):
        dlg = results_dialog.AEPResultsDialog(None, result)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_summary_with_gains_and_the_balance(self):
        dlg = self.dialog(v2_result())
        self.assertTrue(dlg.lbl_loss_ti.text().startswith("+1,0 MWh"))  # D_T = (92 - 90) + (79 - 80) = +1
        b = dlg.results["breakdown"]
        self.assertEqual(dlg.lbl_loss_ti.text(), results_dialog._term_text(b["D_T"]))
        self.assertEqual(dlg.lbl_loss_blk.text(), results_dialog._term_text(b["D_B"]))
        self.assertTrue(dlg.lbl_loss_blk.text().startswith("-1,4 MWh"))  # (91 - 92) + (78 - 79) + (100.6 - 100)
        self.assertTrue(dlg.lbl_loss_other.isVisibleTo(dlg))  # the interaction diagnostic
        balance = [dlg.balance_layout.itemAt(i).widget() for i in range(dlg.balance_layout.count())]
        self.assertIn("(OK)", balance[0].text())  # gross - wakes + turbulence + blockage = net, exactly
        html = results_dialog._fill_slots(dlg._user_texts, dlg._global_kpi_html())  # as the export shows it
        self.assertIn("Δ_T", html)
        self.assertNotIn("Otras pérdidas", html)

    def test_a_breakdown_not_available_is_not_zero(self):
        r = v2_result(aep={"A_W": None}, aep_states={"A_W": bd.FAILED}, errors={"A_W": "RuntimeError: x"})
        dlg = self.dialog(r)
        self.assertEqual(dlg.lbl_loss_wake.text(), "no disponible (falló su cálculo)")
        self.assertNotIn("0,0", dlg.lbl_loss_wake.text())
        balance = [dlg.balance_layout.itemAt(i).widget() for i in range(dlg.balance_layout.count())]
        self.assertIn("no se puede dibujar", balance[0].text())
        self.assertIn("RuntimeError: x", dlg._last_report_html)
        models = {dlg.table_models.item(i, 0).text(): dlg.table_models.item(i, 7).text()
                  for i in range(dlg.table_models.rowCount())}
        self.assertEqual(models, {"WTG-A": "n/d", "WTG-B": "n/d"})
        self.assertEqual(dlg.table_turbines.item(0, 7).text(), "n/d")

    def test_a_capacity_factor_of_zero_is_shown(self):
        # A net AEP of zero gives a capacity factor and a specific yield of 0, not "-".
        dlg = self.dialog(v2_result(aep={"A_WTB": np.zeros(3)}))
        self.assertEqual(dlg.lbl_cf_net.text(), results_dialog._fmt_pct(0.0))
        self.assertTrue(dlg.lbl_spec_yield.text().startswith(results_dialog._fmt_mwh(0.0)))
        for row in range(dlg.table_models.rowCount()):
            self.assertEqual(dlg.table_models.item(row, 11).text(), results_dialog._fmt_pct(0.0))
            self.assertEqual(dlg.table_models.item(row, 12).text(), results_dialog._fmt_mwh(0.0))
        last = dlg.table_turbines.columnCount() - 1
        for row in range(dlg.table_turbines.rowCount()):
            self.assertEqual(dlg.table_turbines.item(row, last).text(), results_dialog._fmt_pct(0.0))

    def test_a_balance_that_cannot_be_drawn_says_so_in_the_language(self):
        from matplotlib.figure import Figure
        for language, text in (("en", "Could not render the total balance: x"),
                               ("fr", "Impossible d’afficher le bilan total : x"),
                               ("de", "Die Gesamtbilanz konnte nicht dargestellt werden: x")):
            with self.subTest(language=language), mock.patch.object(i18n, "current_language", return_value=language), \
                    mock.patch.object(Figure, "add_subplot", side_effect=RuntimeError("x")):
                dlg = self.dialog(v2_result())
                labels = [dlg.balance_layout.itemAt(i).widget() for i in range(dlg.balance_layout.count())]
                self.assertIn(text, [w.text() for w in labels if isinstance(w, QtWidgets.QLabel)])

    def test_without_blockage_it_is_not_modelled(self):
        r = v2_result(aep={"A_WB": None, "A_WTB": AWT}, aep_states={"A_WB": bd.NOT_MODELLED}, blockage=False)
        dlg = self.dialog(r)
        self.assertEqual(dlg.lbl_loss_blk.text(), "no modelado")
        self.assertFalse(dlg.lbl_loss_other.isVisibleTo(dlg))

    def test_tables_and_sector(self):
        dlg = self.dialog(v2_result())
        headers = [dlg.table_turbines.horizontalHeaderItem(c).text() for c in range(dlg.table_turbines.columnCount())]
        self.assertIn("TI efectiva", headers)
        self.assertEqual(dlg.table_turbines.item(1, headers.index("TI efectiva")).text(), "n/d")
        self.assertEqual(dlg.table_turbines.item(2, headers.index("Impacto bloqueo Δ_B [MWh]")).text(), "+0,6")
        sector = dlg.table_sector
        self.assertEqual(sector.horizontalHeaderItem(3).text(), "Pérd. total [MWh]")
        # The first sector gains production: its loss is negative, not clipped to zero (#75, row 4.11).
        self.assertTrue(sector.item(0, 3).text().startswith("-"))

    def test_a_sector_without_gross_aep_has_no_percentage(self):
        # A percentage over a gross AEP that is not positive is not available, never 0 (P0, section 8).
        r = v2_result()
        r["aep_per_wd_free_MWh"], r["aep_per_wd_wake_MWh"] = [0.0, 160.0], [0.0, 119.6]
        dlg = self.dialog(r)
        sector = dlg.table_sector
        self.assertEqual(sector.item(0, 4).text(), "n/d")
        self.assertNotEqual(sector.item(1, 4).text(), "n/d")
        r["aep_per_wd_free_MWh"], r["aep_per_wd_wake_MWh"] = [0.0, 0.0], [0.0, 0.0]
        dlg = self.dialog(r)
        self.assertEqual(dlg.table_sector.item(2, 4).text(), "n/d")  # the total

    def test_the_report_and_its_translation(self):
        dlg = self.dialog(v2_result())
        self.assertIn("L_total = A_0 − A_WTB = L_W − Δ_T − Δ_B", dlg._last_report_html)
        for language in ("en", "fr", "de"):
            with self.subTest(language=language), mock.patch.object(i18n, "current_language", return_value=language):
                self.assertEqual(i18n.tr_text("Pérdida por estelas (L_W)"), TRANSLATIONS[language]["Pérdida por estelas (L_W)"])

    def test_every_new_text_is_translated(self):
        from VelantisWind.ag_core.results.breakdown_translations import SOURCES
        i18n._ensure()
        for language in ("en", "fr", "de"):
            table = i18n._STATE["full"][language]
            for source in SOURCES:
                with self.subTest(language=language, text=source[:40]):
                    self.assertIn(source, table)
                    self.assertTrue(table[source].strip())

    def test_a_schema_1_result_is_read_with_its_own_fields(self):
        dlg = self.dialog(v1_result())
        self.assertIn("10,0", dlg.lbl_loss_wake.text())
        self.assertEqual(dlg.table_turbines.columnCount(), 10)
        # Labelled as a result of the previous schema, in the window and in the report.
        self.assertTrue(dlg.lbl_schema_note.isVisibleTo(dlg))
        self.assertIn("esquema anterior", dlg.lbl_schema_note.text())
        self.assertIn("esquema anterior", dlg._last_report_html)
        self.assertFalse(self.dialog(v2_result()).lbl_schema_note.isVisibleTo(dlg))


def global_rows(dlg):
    table = [t for t in dlg.findChildren(QtWidgets.QTableWidget) if t.item(0, 0) and t.item(0, 0).text() == "AEP neto"][0]
    return {table.item(i, 0).text(): [table.item(i, c).text() for c in range(1, 5)] for i in range(table.rowCount())}


class ComparatorTest(unittest.TestCase):
    def test_not_available_gives_no_delta(self):
        a = v2_result()
        b = v2_result(aep={"A_WB": None, "A_WTB": AWT}, aep_states={"A_WB": bd.NOT_MODELLED}, blockage=False)
        dlg = results_dialog.ScenarioComparisonDialog(None, a, b)
        self.addCleanup(dlg.deleteLater)
        rows = global_rows(dlg)
        self.assertEqual(rows["Impacto del bloqueo (Δ_B)"][1:], ["n/d", "n/d", "n/d"])
        self.assertNotIn("-100", " ".join(rows["Impacto del bloqueo (Δ_B)"]))

    def test_a_capacity_factor_of_zero_is_compared(self):
        a = v2_result(aep={"A_WTB": np.zeros(3)})
        dlg = results_dialog.ScenarioComparisonDialog(None, a, v2_result())
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._summary(a)["cf_net"], 0.0)
        rows = global_rows(dlg)
        cf = next(v for k, v in rows.items() if "capacidad" in k.lower())
        self.assertNotEqual(cf[0], "n/d")  # scenario A: 0 %, a value
        self.assertNotEqual(cf[2], "n/d")  # the absolute difference
        self.assertEqual(cf[3], "n/d")  # the change relative to a base of zero is not available

    def test_not_available_is_said_in_the_language(self):
        a = v2_result()
        b = v2_result(aep={"A_WB": None, "A_WTB": AWT}, aep_states={"A_WB": bd.NOT_MODELLED}, blockage=False)
        for language, missing in (("en", "n/a"), ("fr", "n.d."), ("de", "n. v.")):
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                dlg = results_dialog.ScenarioComparisonDialog(None, a, b)
                self.addCleanup(dlg.deleteLater)
                cells = [t.item(i, c).text() for t in dlg.findChildren(QtWidgets.QTableWidget)
                         for i in range(t.rowCount()) for c in range(1, t.columnCount()) if t.item(i, c)]
                self.assertIn(missing, cells)
                self.assertNotIn("n/d", cells)

    def test_two_schemas_only_compare_what_means_the_same(self):
        dlg = results_dialog.ScenarioComparisonDialog(None, v1_result(), v2_result())
        self.addCleanup(dlg.deleteLater)
        notes = [w.text() for w in dlg.findChildren(QtWidgets.QLabel) if "esquema anterior" in w.text()]
        self.assertTrue(notes and notes[0].startswith("A:"))
        rows = global_rows(dlg)
        self.assertEqual(rows["Pérdida por estelas (L_W)"], ["n/d", "n/d", "n/d", "n/d"])
        self.assertNotEqual(rows["AEP neto"][2], "n/d")


class ExportsTest(unittest.TestCase):
    def test_csv_with_signed_columns(self):
        r = v2_result()
        path = os.path.join(_SETTINGS.name, "t.csv")
        export.export_per_turbine_to_csv(r["per_turbine_table"], path)
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(float(rows[2]["Blockage impact Δ_B [MWh/year]"]), 100.6 - 100.0)
        self.assertEqual(float(rows[0]["Turbulence impact Δ_T [MWh/year]"]), 2.0)
        self.assertNotIn("TI/turbulence impact [MWh/year]", rows[0])
        # Schema 1: the column takes the signed impact, not the clipped loss (#75, row 4.5).
        export.export_per_turbine_to_csv(v1_result()["per_turbine_table"], path)
        with open(path, encoding="utf-8-sig") as fh:
            old = list(csv.DictReader(fh))
        self.assertEqual(float(old[0]["TI/turbulence impact [MWh/year]"]), 2.0)

    def test_summary_layer_null_not_zero(self):
        r = v2_result(aep={"A_W": None}, aep_states={"A_W": bd.FAILED})
        layer = export.create_summary_layer(r, "resumen")
        self.addCleanup(QgsProject.instance().removeMapLayer, layer.id())
        feats = {f["model"]: f for f in layer.getFeatures()}
        self.assertTrue(feats["WTG-A"].attribute("l_wake_mwh") is None or str(feats["WTG-A"].attribute("l_wake_mwh")) == "NULL")
        self.assertAlmostEqual(feats["WTG-B"]["d_blk_mwh"], 0.6)
        self.assertIn("L_W=failed", feats["WTG-A"]["wake_states"])


class LayersTest(unittest.TestCase):
    def layer(self, old_fields=False):
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "turbinas", "memory")
        if old_fields:
            layer.dataProvider().addAttributes([QgsField("loss_wake_mwh", QVariant.Double), QgsField("ti_eff", QVariant.Double),
                                                QgsField("loss_wake_pct", QVariant.Double),
                                                QgsField("aep_wake_only_mwh", QVariant.Double)])
            layer.updateFields()
        feats = []
        for i, (x, y) in enumerate(XY):
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            if old_fields:
                f["loss_wake_mwh"] = 55.0
                f["ti_eff"] = 0.07
                f["loss_wake_pct"] = 15.0
                f["aep_wake_only_mwh"] = 444.0
            feats.append(f)
        layer.dataProvider().addFeatures(feats)
        QgsProject.instance().addMapLayer(layer)
        self.addCleanup(QgsProject.instance().removeMapLayer, layer.id())
        return layer

    def test_schema_2_fields_and_an_old_layer_untouched(self):
        layer = self.layer(old_fields=True)
        rows = [dict(r, model="WTG-A") for r in v2_result()["per_turbine_table"][:2]]  # a partial recalculation
        messages = []
        updated = layers.update_layers_from_results(
            rows, [{"name": "WTG-A", "meta": {}, "source_layer_id": layer.id(), "source_layer_name": "turbinas"}],
            log=lambda m, *a: messages.append(str(m)))
        self.assertEqual(updated, ["turbinas"])
        names = [f.name() for f in layer.fields()]
        for field in ("l_wake_mwh", "d_turb_mwh", "d_blk_mwh", "l_total_mwh", "ti_ambient", "ti_effective", "wake_states",
                      "res_schema"):
            self.assertIn(field, names)
        feats = sorted(layer.getFeatures(), key=lambda f: f.geometry().asPoint().x())
        # The old fields are not reinterpreted nor touched; the entity not recalculated keeps what it had.
        self.assertEqual([f["loss_wake_mwh"] for f in feats], [55.0, 55.0, 55.0])
        self.assertEqual([f["res_schema"] for f in feats[:2]], [2, 2])
        self.assertIn(str(feats[2]["res_schema"]), ("NULL", "None"))
        self.assertAlmostEqual(feats[0]["d_turb_mwh"], 2.0)
        self.assertTrue(any("esquema anterior" in m and "loss_wake_mwh" in m for m in messages))
        # The map tip reads each entity with the fields of its own schema.
        from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
        def tip(feature):
            ctx = QgsExpressionContext()
            ctx.appendScope(QgsExpressionContextUtils.layerScope(layer))
            ctx.setFeature(feature)
            return QgsExpression.replaceExpressionText(layer.mapTipTemplate(), ctx)
        new, old = tip(feats[0]), tip(feats[2])
        self.assertIn("Impacto de la turbulencia (Δ_T)", new)
        self.assertIn("2</", new.replace(" MWh", "</"))  # d_turb_mwh = 2 for the first turbine
        self.assertNotIn("esquema anterior", new)
        self.assertIn("esquema anterior", old)
        self.assertIn("Pérdida por estelas</span>: 55 MWh (15%)", old)
        self.assertIn("AEP (sólo estela)</span>: 444", old)
        self.assertIn("TI efectiva</span>: 0.07", old)
        self.assertNotIn("Δ_T", old)
        # Translated when written in another language.
        with mock.patch.object(i18n, "current_language", return_value="en"):
            self.assertIn("Wake loss (L_W)", layers._map_tip_v2(layer))
        # Also the value not available and the units.
        for language, missing, unit in (("en", "n/a", "MWh/year"), ("fr", "n.d.", "MWh/an"),
                                        ("de", "n. v.", "MWh/Jahr")):
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                template = layers._map_tip_v2(layer)
                self.assertIn(f"'{missing}'", template)
                self.assertIn(unit, template)
                self.assertNotIn("n/d", template)
                self.assertNotIn("año", template)
        self.assertIn("Pérdida por estelas (L_W)</span>: 10 MWh (10%)", new)

    def test_translated_without_the_results_window(self):
        # In a process that never imports the results window (the API), the layer and the log are translated too.
        import subprocess
        import sys
        script = """
import os, sys
from qgis.PyQt import QtCore, QtWidgets
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, os.environ["XDG_CONFIG_HOME"])
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, os.environ["XDG_CONFIG_HOME"])
app = QtWidgets.QApplication([])
from unittest import mock
from qgis.core import QgsVectorLayer
from VelantisWind import i18n
from VelantisWind.ag_core.qgis_io import layers
from VelantisWind.ag_core.results import result_v2
from VelantisWind.ag_core.log_text import shown
assert "VelantisWind.results_dialog" not in sys.modules
lines = []
result_v2.log_breakdown({"breakdown": {t: {"mwh": None, "state": "not_modelled"} for t in
                         ("A_0", "A_WTB", "L_W", "D_T", "D_B", "L_total", "I_TB")}, "per_model_breakdown": {}},
                        lines.append)
with mock.patch.object(i18n, "current_language", return_value="en"):
    print(layers._map_tip_v2(QgsVectorLayer("Point?field=res_schema:integer", "t", "memory")))
    print("\\n".join(shown(line, i18n.tr_text) for line in lines))
"""
        # Run from the temporary folder: QGIS writes its style database in the working directory.
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=_SETTINGS.name,
                   PYTHONPATH=os.pathsep.join(filter(None, [_CWD, os.environ.get("PYTHONPATH")])))
        out = subprocess.run([sys.executable, "-c", script], cwd=_SETTINGS.name, env=env, capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("<b>Wind turbine</b>", out.stdout)  # the map tip
        self.assertIn("Wake loss (L_W = A_0 − A_W): not available (not modelled)", out.stdout)  # the log
        self.assertNotIn("no disponible", out.stdout)

    def test_schema_1_rows_keep_their_fields(self):
        layer = self.layer()
        layers.update_layers_from_results(
            v1_result()["per_turbine_table"], [{"name": "WTG-A", "meta": {}, "source_layer_id": layer.id()}])
        names = [f.name() for f in layer.fields()]
        self.assertIn("loss_wake_mwh", names)
        self.assertNotIn("res_schema", names)


if __name__ == "__main__":
    unittest.main()
