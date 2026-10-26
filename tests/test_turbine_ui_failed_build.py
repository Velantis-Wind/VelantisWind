# -*- coding: utf-8 -*-
"""A failed attempt to create a turbine leaves nothing to accept, whatever was created before."""
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

from VelantisWind.ag_core import turbine_ui  # noqa: E402

CURVE = "ws,power_kw,ct\n3,40,0.8\n8,1400,0.79\n15,3000,0.2\n25,3000,0.05\n"
# A minimal .wtg with two density tables.
WTG = (
    '<WindTurbineGenerator FormatVersion="1.01" Description="Synthetic" RotorDiameter="112">'
    "<SuggestedHeights><Height>84</Height></SuggestedHeights>"
    + "".join(
        f'<PerformanceTable AirDensity="{rho}" StationaryThrustCoEfficient="0.05">'
        '<StartStopStrategy LowSpeedCutIn="3" HighSpeedCutOut="25"/><DataTable>'
        + "".join(f'<DataPoint WindSpeed="{w}" PowerOutput="{p * rho / 1.225}" ThrustCoEfficient="{c}"/>'
                  for w, p, c in ((3, 30000.0, 0.8), (8, 1400000.0, 0.79), (15, 3000000.0, 0.2), (25, 3000000.0, 0.05)))
        + "</DataTable></PerformanceTable>"
        for rho in (1.225, 1.0)
    )
    + "</WindTurbineGenerator>"
)


class FailedBuildTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.dialog = turbine_ui.CustomTurbineDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.shown = []
        for name in ("information", "critical", "warning"):
            patcher = mock.patch.object(QtWidgets.QMessageBox, name, side_effect=lambda *a, _n=name: self.shown.append(_n))
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, name, text):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def build_csv(self, text):
        self.dialog.ed_path.setText(self.write("curve.csv", text))
        self.dialog.cb_delim.setCurrentIndex(1)
        self.dialog.sp_skip.setValue(1)
        self.dialog.chk_ct_col.setChecked(True)
        self.dialog.sp_ct_col.setValue(2)
        self.dialog._on_build_csv()

    def build_manual(self, ct):
        self.dialog.te_ws.setPlainText("3 8 15 25")
        self.dialog.te_power.setPlainText("40 1400 3000 3000")
        self.dialog.te_ct.setPlainText(ct)
        self.dialog._on_build_manual()

    def assertNothingToAccept(self):
        self.assertEqual(self.shown[-1], "critical")
        self.assertIsNone(self.dialog.get_wind_turbine())
        self.assertIsNone(self.dialog.result_data())
        self.assertIsNone(self.dialog.get_last_curves())
        with mock.patch.object(QtWidgets.QDialog, "accept") as accepted:
            self.dialog.accept()
        accepted.assert_not_called()
        self.assertEqual(self.shown[-1], "warning")

    def test_every_tab_after_a_valid_turbine(self):
        attempts = {
            "manual": lambda: self.build_manual("0.8 5 0.2 0.05"),
            "csv": lambda: self.build_csv(CURVE.replace("0.79", "ERROR")),
            "wtg": lambda: (self.dialog.ed_path_w.setText(self.write("bad.wtg", "not xml")), self.dialog._on_build_wtg()),
            "owtg": lambda: (self.dialog.ed_path_o.setText(self.write("bad.owtg", "not xml")), self.dialog._on_build_owtg()),
        }
        for valid in ("manual", "csv"):
            for tab, attempt in attempts.items():
                with self.subTest(valid=valid, failed=tab):
                    self.build_manual("0.8 0.79 0.2 0.05") if valid == "manual" else self.build_csv(CURVE)
                    self.assertEqual(self.shown[-1], "information")
                    self.assertIsNotNone(self.dialog.get_wind_turbine())
                    attempt()
                    self.assertNothingToAccept()

    def test_a_failure_after_the_turbine_is_built_leaves_nothing(self):
        # The manual tab builds the turbine and then reads the catalogue candidate's geometry.
        self.dialog._active_catalogue_candidate = {"diam": "not a number"}
        self.build_manual("0.8 0.79 0.2 0.05")
        self.assertNothingToAccept()

    def test_a_failed_attempt_keeps_the_loaded_wtg_and_its_edited_height(self):
        self.dialog.ed_path_w.setText(self.write("turbine.wtg", WTG))
        self.dialog._on_wtg_path_edited()
        table = self.dialog._wtg_table
        self.dialog.sp_hub_w.setValue(100.0)
        self.build_csv(CURVE.replace("0.79", "ERROR"))
        self.assertNothingToAccept()
        self.dialog._on_build_wtg()
        self.assertEqual(self.shown[-1], "information")
        self.assertIs(self.dialog._wtg_table, table)
        self.assertEqual(self.dialog.result_data()["hh"], 100.0)


if __name__ == "__main__":
    unittest.main()
