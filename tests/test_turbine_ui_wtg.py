# -*- coding: utf-8 -*-
"""The .wtg tab of the turbine dialog builds the turbine with the file's geometry."""
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

WS = [3.0, 8.0, 15.0, 25.0]


def wtg(diameter, hub, densities=(1.225, 1.0), heights=None, ct=0.8):
    tables = ""
    for rho in densities:
        points = "".join(
            f'<DataPoint WindSpeed="{w}" PowerOutput="{p * rho / 1.225}" ThrustCoEfficient="{c}"/>'
            for w, p, c in zip(WS, [30000.0, 1400000.0, 3000000.0, 3000000.0], [ct, 0.79, 0.2, 0.05])
        )
        tables += (f'<PerformanceTable AirDensity="{rho}" StationaryThrustCoEfficient="0.05">'
                   '<StartStopStrategy LowSpeedCutIn="3" HighSpeedCutOut="25"/>'
                   f"<DataTable>{points}</DataTable></PerformanceTable>")
    heights = heights or [hub]
    suggested = "".join(f"<Height>{h}</Height>" for h in heights)
    return (f'<WindTurbineGenerator FormatVersion="1.01" Description="Synthetic D{diameter:g}" RotorDiameter="{diameter}">'
            f"<SuggestedHeights>{suggested}</SuggestedHeights>{tables}</WindTurbineGenerator>")


class WtgTabTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.first = self.write("first.wtg", wtg(112.0, 84.0))
        self.second = self.write("second.wtg", wtg(54.2, 50.0, densities=(1.225,)))
        self.dialog = turbine_ui.CustomTurbineDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.shown = []
        for name in ("information", "critical", "warning"):
            patcher = mock.patch.object(QtWidgets.QMessageBox, name, side_effect=lambda *a, _n=name: self.shown.append((_n, a[2])))
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, name, text):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def build(self):
        self.dialog._on_build_wtg()
        return self.dialog.result_data()

    def browse(self, path):
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(path, "")):
            self.dialog._browse_wtg()

    def assertGeometry(self, data, diameter, hub):
        self.assertEqual((data["diam"], data["hh"]), (diameter, hub))
        wt = self.dialog.get_wind_turbine()
        self.assertEqual((float(wt.diameter(0)), float(wt.hub_height(0))), (diameter, hub))

    def test_selector_path(self):
        self.browse(self.first)
        data = self.build()
        self.assertGeometry(data, 112.0, 84.0)
        self.assertEqual(data["mode"], "wtg")
        self.assertIn("2 densidades", self.dialog.lbl_wtg_info.text())
        self.assertIn("primera tabla", self.dialog.lbl_wtg_info.text())

    def test_typed_or_pasted_path_without_the_selector(self):
        self.dialog.ed_path_w.setText(self.first)
        self.assertGeometry(self.build(), 112.0, 84.0)
        self.assertNotIn("Atención", self.shown[-1][1])

    def test_typed_path_is_read_when_the_field_is_left(self):
        self.dialog.ed_path_w.setText(self.first)
        self.dialog.ed_path_w.editingFinished.emit()
        self.assertEqual(self.dialog.sp_diam_w.value(), 112.0)
        self.assertEqual(self.dialog.ed_name_w.text(), "Synthetic D112")

    def test_switching_files_takes_the_new_geometry(self):
        self.browse(self.first)
        self.build()
        self.dialog.ed_path_w.setText(self.second)
        data = self.build()
        self.assertGeometry(data, 54.2, 50.0)
        self.assertEqual(data["name"], "Synthetic D54.2")

    def test_geometry_warning_only_after_a_user_edit(self):
        self.browse(self.first)
        self.build()
        self.assertNotIn("Atención", self.shown[-1][1])
        self.dialog.sp_hub_w.setValue(119.0)
        data = self.build()
        self.assertGeometry(data, 112.0, 119.0)
        self.assertIn("Atención: has cambiado la geometría respecto al fichero (D=112 m, HH=84 m)", self.shown[-1][1])
        # A new file brings its own geometry and clears the edit.
        self.browse(self.second)
        self.build()
        self.assertNotIn("Atención", self.shown[-1][1])

    def test_metadata_carries_height_and_diameter(self):
        self.browse(self.first)
        data = self.build()
        for key in ("hh", "diam", "p_rated_kw", "ws", "power_kw", "ct"):
            self.assertIn(key, data)
        self.assertEqual(data["p_rated_kw"], 3000.0)
        self.assertEqual(data["default_air_density"], 1.225)

    def test_a_new_file_discards_the_turbine_of_the_previous_one(self):
        self.browse(self.first)
        self.build()
        self.browse(self.second)
        self.assertIsNone(self.dialog.get_wind_turbine())
        self.dialog.accept()
        self.assertEqual(self.shown[-1][0], "warning")
        self.assertEqual(self.dialog.result(), 0)

    def test_typing_another_path_discards_the_turbine_before_leaving_the_field(self):
        self.browse(self.first)
        self.build()
        # Without editingFinished: the field still has the focus when Accept is pressed (e.g. from the keyboard).
        self.dialog.ed_path_w.setText(self.second)
        self.assertIsNone(self.dialog.get_wind_turbine())
        self.dialog.accept()
        self.assertEqual(self.shown[-1][0], "warning")
        self.assertEqual(self.dialog.result(), 0)

    def test_a_path_to_nothing_discards_the_turbine_too(self):
        self.browse(self.first)
        self.build()
        self.dialog.ed_path_w.setText(os.path.join(self.folder, "missing.wtg"))
        self.dialog.ed_path_w.editingFinished.emit()
        self.assertIsNone(self.dialog.get_wind_turbine())
        self.dialog.accept()
        self.assertEqual(self.dialog.result(), 0)

    def test_geometry_the_controls_cannot_hold_is_rejected(self):
        path = self.write("tall.wtg", wtg(112.0, 310.0))
        self.browse(path)
        kind, text = self.shown[-1]
        self.assertEqual(kind, "critical")
        self.assertIn("La geometría del fichero (D=112 m, HH=310 m) no cabe en los controles del diálogo", text)
        self.dialog.ed_path_w.setText(path)
        self.dialog._on_build_wtg()
        self.assertIsNone(self.dialog.get_wind_turbine())

    def test_one_of_several_heights_is_chosen(self):
        path = self.write("heights.wtg", wtg(112.0, 84.0, heights=[84.0, 119.0]))
        with mock.patch.object(QtWidgets.QInputDialog, "getItem", return_value=("119 m", True)):
            self.browse(path)
        self.assertEqual(self.dialog.sp_hub_w.value(), 119.0)
        self.assertGeometry(self.build(), 112.0, 119.0)

    def test_rejections_reach_the_user_translated(self):
        path = self.write("broken.wtg", wtg(112.0, 84.0, ct=1.3))
        with mock.patch.object(turbine_ui, "tr_text", side_effect=lambda text: "[tr] " + text):
            self.browse(path)
        kind, text = self.shown[-1]
        self.assertEqual(kind, "critical")
        # Every template is translated and the variable parts stay as they are.
        self.assertTrue(text.startswith("[tr] Variante de .wtg no soportada en broken.wtg: [tr] Valor de [tr] Ct fuera de rango a 3 m/s y 1 kg/m³: 1.3 > 1.2."), text)
        self.assertIsNone(self.dialog.get_wind_turbine())


if __name__ == "__main__":
    unittest.main()
