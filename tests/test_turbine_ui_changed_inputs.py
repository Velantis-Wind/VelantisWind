# -*- coding: utf-8 -*-
"""Accept warns, and lets the user go back, when the data changed after the turbine was created."""
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
WS = [0.0, 3.0, 8.0, 15.0, 25.0]
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


def owtg():
    def table(tag, values):
        speeds = "".join(f'<Velocity{i} value="{v}"/>' for i, v in enumerate(WS))
        rho = "".join(f'<Rho{j} value="{r}"/>' for j, r in enumerate((1.0, 1.225)))
        columns = "".join(f'<Rho{r:.6f}><Rows value="{len(WS)}"/>'
                          + "".join(f'<v{j}-{i} value="{v}"/>' for i, v in enumerate(values(r))) + f"</Rho{r:.6f}>"
                          for j, r in enumerate((1.0, 1.225)))
        return (f'<{tag}><Type>TurbineTable</Type><Velocities><Count value="{len(WS)}"/>{speeds}</Velocities>'
                f'<AirDensities><Count value="2"/>{rho}</AirDensities>'
                f'<Values><Columns value="2"/>{columns}</Values></{tag}>')

    power = table("Power_Table0", lambda r: [0.0, 30.0 * r / 1.225, 1400.0 * r / 1.225, 2950.0, 2950.0])
    thrust = table("Thrust_Table", lambda r: [0.0, 0.8, 0.79, 0.2, 0.05])
    return ('<TurbineType><Name>Synthetic</Name><HubHeight value="126"/><RotorDiameter value="163"/>'
            '<CapacityKW value="3000"/><LowCutIn value="3"/><HighCutOut value="25"/><DesignAirDensity value="1.225"/>'
            f'<Power_Tables><Count value="1"/>{power}</Power_Tables>{thrust}</TurbineType>')


def edit(widget):
    """Change a control the way a user would."""
    if isinstance(widget, QtWidgets.QCheckBox):
        widget.toggle()
    elif isinstance(widget, QtWidgets.QComboBox):
        widget.setCurrentIndex((widget.currentIndex() + 1) % widget.count())
    elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
        widget.setValue(widget.value() + 1)
    elif isinstance(widget, QtWidgets.QPlainTextEdit):
        widget.setPlainText(widget.toPlainText() + " 1")
    else:
        widget.setText(widget.text() + "x")


def label(text):
    return "«" + text.rstrip(" :") + "»"


class ChangedInputsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.csv = self.write("curve.csv", CURVE)
        self.wtg = self.write("turbine.wtg", WTG)
        self.owtg = self.write("turbine.owtg", owtg())
        self.dialog = turbine_ui.CustomTurbineDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.shown = []
        for name in ("information", "critical", "warning"):
            patcher = mock.patch.object(QtWidgets.QMessageBox, name, side_effect=lambda *a, _n=name: self.shown.append(_n))
            patcher.start()
            self.addCleanup(patcher.stop)
        if hasattr(turbine_ui, "tr_text"):  # the texts in Spanish, whatever the language of the machine
            patcher = mock.patch.object(turbine_ui, "tr_text", side_effect=lambda text: text)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.inputs = {mode: (tab, inputs) for mode, tab, inputs in turbine_ui.CustomTurbineDialog._TAB_INPUTS}

    def write(self, name, text):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def build(self, mode):
        d = self.dialog
        if mode == "manual":
            d.te_ws.setPlainText("3 8 15 25")
            d.te_power.setPlainText("40 1400 3000 3000")
            d.te_ct.setPlainText("0.8 0.79 0.2 0.05")
            d._on_build_manual()
        elif mode == "csv":
            d.ed_path.setText(self.csv)
            d.cb_delim.setCurrentIndex(1)
            d.sp_ws_col.setValue(0)
            d.sp_pw_col.setValue(1)
            d.sp_skip.setValue(1)
            d.chk_ct_col.setChecked(True)
            d.sp_ct_col.setValue(2)
            d._on_build_csv()
        elif mode == "wtg":
            d.ed_path_w.setText(self.wtg)
            d._on_build_wtg()
        else:
            d.ed_path_o.setText(self.owtg)
            d._on_build_owtg()
        self.assertEqual(self.shown[-1], "information")
        self.assertEqual(d.result_data()["mode"], mode)

    def accept(self, answer):
        """Press Accept; ``answer`` is what the user chooses if asked. Returns (question text or None, accepted)."""
        with mock.patch.object(self.dialog, "_ask_continue", return_value=answer) as ask, \
                mock.patch.object(QtWidgets.QDialog, "accept") as accepted:
            self.dialog.accept()
        if ask.called:
            self.assertEqual(ask.call_args.args[0], "Datos cambiados")
        return (ask.call_args.args[1] if ask.called else None), accepted.called

    def test_every_control_of_the_turbine_tab_asks_before_using_the_previous_turbine(self):
        for mode, (tab, inputs) in self.inputs.items():
            for attr, text in inputs:
                if attr in ("ed_path_w", "ed_path_o"):
                    continue  # a new file discards the turbine: «Sin turbina» (tested with the tabs)
                for answer in (False, True):
                    with self.subTest(tab=mode, control=attr, go_on=answer):
                        self.build(mode)
                        built = dict(self.dialog.result_data())
                        edit(getattr(self.dialog, attr))
                        question, accepted = self.accept(answer)
                        self.assertEqual(question, f"Has cambiado {label(text)} desde que creaste la turbina. "
                                                   "Si continúas, se usará la última turbina que creaste, sin esos "
                                                   "cambios. Para aplicarlos, vuelve y pulsa «Crear turbina».")
                        self.assertEqual(accepted, answer)
                        # Going on delivers the turbine that was created, untouched.
                        self.assertEqual(self.dialog.result_data(), built)

    def test_no_question_without_changes_or_after_creating_again(self):
        self.build("csv")
        self.assertEqual(self.accept(False), (None, True))
        self.dialog.sp_hub_c.setValue(140.0)
        self.dialog.sp_hub_c.setValue(90.0)  # back to the value the turbine was created with
        self.assertEqual(self.accept(False), (None, True))
        self.dialog.sp_hub_c.setValue(140.0)
        self.dialog._on_build_csv()
        self.assertEqual(self.accept(False), (None, True))
        self.assertEqual(self.dialog.result_data()["hh"], 140.0)

    def test_changes_in_another_tab_name_both_tabs(self):
        self.build("csv")
        self.dialog.te_ws.setPlainText("3 8 15 25")
        self.dialog.sp_hub_m.setValue(140.0)
        question, accepted = self.accept(False)
        self.assertFalse(accepted)
        self.assertEqual(question, f"En la pestaña Manual has cambiado {label('Altura buje:')}, "
                                   f"{label('Velocidad del viento (m/s):')}, pero la turbina creada es la de la pestaña TXT/CSV. "
                                   "Si continúas, se usará la última turbina que creaste, sin esos cambios. "
                                   "Para aplicarlos, vuelve y pulsa «Crear turbina».")

    def test_changes_in_the_turbine_tab_come_first(self):
        self.build("manual")
        self.dialog.ed_path_w.setText(self.wtg)
        self.dialog.sp_diam_m.setValue(150.0)
        question, _ = self.accept(False)
        self.assertTrue(question.startswith(f"Has cambiado {label('Diámetro rotor:')} desde que creaste la turbina. "
                                            f"En la pestaña .wtg has cambiado {label('Fichero .wtg:')}"), question)

    def test_a_new_wtg_or_owtg_file_still_leaves_no_turbine(self):
        for mode, attr, path in (("wtg", "ed_path_w", "other.wtg"), ("owtg", "ed_path_o", "other.owtg")):
            with self.subTest(tab=mode):
                self.build(mode)
                getattr(self.dialog, attr).setText(os.path.join(self.folder, path))
                self.assertEqual(self.accept(True), (None, False))
                self.assertEqual(self.shown[-1], "warning")

    def test_what_the_dialog_does_by_itself_is_not_a_change(self):
        self.build("manual")
        self.dialog.te_ws.setPlainText("3   8\t15, 25")  # the same numbers, written differently
        if hasattr(turbine_ui, "apply_i18n"):
            turbine_ui.apply_i18n(self.dialog)  # rótulos y elementos del combo traducidos otra vez
        self.assertEqual(self.accept(False), (None, True))

    def test_an_unchanged_list_with_nan_is_not_a_change(self):
        self.dialog.te_ct.setPlainText("0.8 nan 0.2 0.05")  # Manual: left as it is while CSV is created
        self.build("csv")
        self.assertEqual(self.accept(False), (None, True))

    def test_a_discarded_turbine_leaves_nothing_to_compare(self):
        self.build("wtg")
        self.dialog.ed_path_w.setText(os.path.join(self.folder, "other.wtg"))  # discards it
        self.build("csv")
        self.assertEqual(self.accept(False), (None, True))
        self.assertEqual(self.dialog.result_data()["mode"], "csv")

    def test_a_catalogue_choice_is_a_change_of_the_manual_tab(self):
        if not hasattr(self.dialog, "cb_generic_preset"):
            self.skipTest("this dialog has no turbine catalogue")
        self.build("csv")
        self.dialog.cb_generic_preset.setCurrentIndex(1)
        question, accepted = self.accept(False)
        self.assertFalse(accepted)
        self.assertTrue(question.startswith("En la pestaña Manual has cambiado"), question)

    def test_the_question_defaults_to_going_back(self):
        boxes = []

        class Box(QtWidgets.QMessageBox):
            def exec_(self):  # closed without choosing, like Escape
                boxes.append(self)
                return 0

        with mock.patch.object(QtWidgets, "QMessageBox", Box):
            self.assertFalse(self.dialog._ask_continue("Datos cambiados", "texto"))
        box = boxes[0]
        self.assertEqual(box.icon(), QtWidgets.QMessageBox.Warning)
        self.assertEqual([b.text() for b in box.buttons()], ["Continuar", "Volver"])
        self.assertEqual(box.defaultButton().text(), "Volver")
        self.assertEqual(box.escapeButton().text(), "Volver")


if __name__ == "__main__":
    unittest.main()
