# -*- coding: utf-8 -*-
"""A turbine whose Ct is estimated says so when it is created and in the result notes."""
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

from VelantisWind.ag_core import aep_compute, turbine_ui  # noqa: E402
from VelantisWind.ag_core.turbine import CT_ESTIMATED_WARNING, _estimate_ct, build_wt_from_manual  # noqa: E402

WS = [3.0, 8.0, 15.0, 25.0]
POWER_KW = [40.0, 1400.0, 3000.0, 3000.0]
CT = [0.8, 0.79, 0.2, 0.05]


def _tr(text):
    return "[tr] " + text


class DialogWarningTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "curve.csv")
        self.dialog = turbine_ui.CustomTurbineDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.shown = []
        for name in ("information", "critical", "warning"):
            patcher = mock.patch.object(QtWidgets.QMessageBox, name, side_effect=lambda *a, _n=name: self.shown.append((_n, a[2])))
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(turbine_ui, "tr_text", side_effect=_tr)
        patcher.start()
        self.addCleanup(patcher.stop)

    def build_csv(self, rows, ct_col):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("ws,power_kw,ct\n" + "\n".join(rows) + "\n")
        self.dialog.ed_path.setText(self.path)
        self.dialog.cb_delim.setCurrentIndex(1)
        self.dialog.sp_skip.setValue(1)
        self.dialog.chk_ct_col.setChecked(ct_col is not None)
        self.dialog.sp_ct_col.setValue(ct_col or 0)
        self.dialog._on_build_csv()
        return self.dialog.result_data()

    def build_manual(self, ct):
        self.dialog.te_ws.setPlainText(" ".join(str(v) for v in WS))
        self.dialog.te_power.setPlainText(" ".join(str(v) for v in POWER_KW))
        self.dialog.te_ct.setPlainText(" ".join(str(v) for v in ct or []))
        self.dialog._on_build_manual()
        return self.dialog.result_data()

    def test_csv_without_ct_column_warns_through_the_translator(self):
        data = self.build_csv([f"{w},{p},{c}" for w, p, c in zip(WS, POWER_KW, CT)], None)
        self.assertEqual(self.shown, [("information", "[tr] Turbina creada desde TXT/CSV. Pulsa Aceptar para usarla.\n\n"
                                                      + _tr(CT_ESTIMATED_WARNING))])
        self.assertTrue(data["ct_estimated"])
        self.assertEqual(data["ct"], _estimate_ct(WS, [p * 1000.0 for p in POWER_KW]))

    def test_manual_list_without_ct_warns(self):
        data = self.build_manual(None)
        self.assertEqual(self.shown, [("information", "[tr] Turbina creada (manual). Pulsa Aceptar para usarla.\n\n"
                                                      + _tr(CT_ESTIMATED_WARNING))])
        self.assertTrue(data["ct_estimated"])

    def test_measured_ct_does_not_warn(self):
        csv_data = self.build_csv([f"{w},{p},{c}" for w, p, c in zip(WS, POWER_KW, CT)], 2)
        manual_data = self.build_manual(CT)
        self.assertEqual([kind for kind, _ in self.shown], ["information", "information"])
        self.assertFalse(any(CT_ESTIMATED_WARNING in text for _, text in self.shown))
        self.assertFalse(csv_data["ct_estimated"] or manual_data["ct_estimated"])
        self.assertEqual(csv_data["ct"], CT)

    def test_reader_error_reaches_the_translator_with_its_values_intact(self):
        self.build_csv(["3,40,0.8", "8,1400,ERROR", "15,3000,0.2"], 2)
        kind, text = self.shown[-1]
        self.assertEqual(kind, "critical")
        self.assertTrue(text.startswith("[tr] Ct no válido en curve.csv, línea 3, columna 2: 'ERROR'."), text)
        self.assertIsNone(self.dialog.result_data())


def _write_wrg(folder):
    path = os.path.join(folder, "site.wrg")
    lines = ["3 3 1000 1000 500"]
    for iy in range(3):
        for ix in range(3):
            sectors = " ".join("250 90 210" for _ in range(4))
            lines.append(f"{1000 + 500 * ix} {1000 + 500 * iy} 0 90 9.0 2.1 300 4 {sectors}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


class ResultNoteTest(unittest.TestCase):
    def notes(self, ct_estimated):
        wt = build_wt_from_manual("Synthetic WT", 100.0, 90.0, WS, POWER_KW, None if ct_estimated else CT)
        meta = {"name": "Synthetic WT", "hh": 90.0, "diam": 100.0, "p_rated_kw": 3000.0, "ct_estimated": ct_estimated}
        with tempfile.TemporaryDirectory() as folder:
            result = aep_compute.compute_aep_from_ui(
                "", [{"name": "Synthetic WT", "wt": wt, "meta": meta, "coords_xy": [(1000.0, 1500.0), (2000.0, 1500.0)]}],
                wrg_paths=[_write_wrg(folder)], fixed_ti=0.1, compute_variants=False,
            )
        return [note for note in result["simulation_notes"] if CT_ESTIMATED_WARNING in str(note)]

    def test_estimated_ct_is_in_the_notes_with_its_template(self):
        notes = self.notes(True)
        self.assertEqual([str(note) for note in notes], ["Modelo «Synthetic WT»: " + CT_ESTIMATED_WARNING])
        template, data = notes[0].template_item
        self.assertEqual(template, "Modelo «{name}»: {warning}")
        self.assertEqual(data["warning"].template_item, (CT_ESTIMATED_WARNING, {}))

    def test_measured_ct_adds_no_note(self):
        self.assertEqual(self.notes(False), [])


if __name__ == "__main__":
    unittest.main()
