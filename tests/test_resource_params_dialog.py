# -*- coding: utf-8 -*-
"""«Parámetros del recurso» in the energy dialog: shown under a readable WRG, folded, with the choice in its button,
the band of the models and their step, the help of each parameter, nothing saved, and what reaches the calculation."""
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

from VelantisWind import aep_setup_dialog, i18n  # noqa: E402
from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.ag_core import aep_compute  # noqa: E402
from VelantisWind.ag_core.resource_grid import speed_grid  # noqa: E402
from VelantisWind.ag_core.simulation import runner  # noqa: E402
from VelantisWind.ag_core.turbine import build_wt_from_curve_table, build_wt_from_manual  # noqa: E402
from VelantisWind.ag_core.turbines.owtg import load_owtg  # noqa: E402
from VelantisWind.energy_core import dialog_controller, dialog_state  # noqa: E402
from VelantisWind.energy_core.runner import EnergyRunner  # noqa: E402
from tests.test_owtg import BLOCKS, HEAD, turbine_table  # noqa: E402
from tests.test_resource_settings import idle_turbine, wide_turbine, write_wrg  # noqa: E402
from py_wake.wind_turbines import WindTurbines  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("en", "fr", "de")
TITLE = "Parámetros del recurso (nearest, 126 direcciones, 3–24 m/s cada 0,5 m/s)"
NO_BAND = "No se pueden deducir las velocidades de cálculo de la curva de algún modelo: no tiene velocidades tabuladas válidas, su potencia es cero en todos sus nodos, su banda de operación no es válida o su tipo de curva no se admite. Revisa los modelos."
HELP = {
    "count": aep_setup_dialog._WD_COUNT_HELP,
    "interp": aep_setup_dialog._WD_INTERP_HELP,
    "speedup": aep_setup_dialog._SPEEDUP_HELP,
    "speeds": aep_setup_dialog._SPEEDS_HELP,
}


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def owtg_turbine(folder):
    """A synthetic .owtg turbine (the format of tests/test_owtg.py): band 3-24 m/s, tabulated every 0.5 m/s."""
    ws = [float(v) for v in np.arange(0.0, 30.5, 0.5)]
    power = [0.0 if v < 3.0 else min(3000.0, 3000.0 * ((v - 3.0) / 9.0) ** 2) for v in ws]
    ct = [0.0 if v < 3.0 else (0.8 if v < 10.0 else 0.3) for v in ws]
    fields = dict(HEAD, LowCutIn=3, HighCutOut=24)
    values = "".join(f'<{tag} value="{value}"/>' for tag, value in fields.items())
    blocks = "".join(f'<{tag}><Enable value="0"/></{tag}>' for tag in BLOCKS)
    tables = (turbine_table("Power_Table0", {1.0: power, 1.225: power}, ws=ws, extra='<TI_min value="6"/><TI_max value="12"/>'),
              turbine_table("Thrust_Table", {1.0: ct, 1.225: ct}, ws=ws))
    path = os.path.join(folder, "synthetic.owtg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f'<?xml version="1.0" encoding="UTF-8"?><TurbineType><Name>Synthetic</Name>{values}'
                 f'<Power_Tables><Count value="1"/>{tables[0]}</Power_Tables>{tables[1]}{blocks}</TurbineType>')
    return build_wt_from_curve_table(load_owtg(path), name="Synthetic", diameter_m=100.0, hub_height_m=90.0)


def manual_turbine(name="M", ws=(4.0, 8.0, 12.0, 20.0)):
    return build_wt_from_manual(name, 100.0, 90.0, list(ws), [0.0, 800.0, 3000.0, 3000.0], [0.8, 0.8, 0.4, 0.2])


class _DialogCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self.settings.remove("last_wrg_path")
        patch = mock.patch.object(QtWidgets.QMessageBox, "warning")
        patch.start()
        self.addCleanup(patch.stop)
        self.dialog = self.new_dialog()
        self.wrg18 = write_wrg(self.folder, 18, name="n18.wrg")
        self.wrg12 = write_wrg(self.folder, 12, name="n12.wrg")

    def new_dialog(self):
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        return dialog

    def pick(self, path, dialog=None):
        """The «Elegir WRG/ZIP…» button with the file dialog simulated."""
        dialog = dialog or self.dialog
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileNames", return_value=([path], "")), \
                mock.patch.object(dialog, "_draw_current_resource_extent"):
            dialog._pick_wrg()

    def define(self, idx, wt, mode="owtg", diam=100.0):
        """A row's model, as «Definir…» leaves it."""
        dialog = self.dialog
        fake = mock.Mock(Accepted=QtWidgets.QDialog.Accepted)
        fake.exec_.return_value = QtWidgets.QDialog.Accepted
        fake.get_wind_turbine.return_value = wt
        fake.result_data.return_value = {"name": f"T{idx}", "mode": mode, "hh": 90.0, "diam": diam}
        with mock.patch.object(dialog, "_custom_dialog_factory", lambda parent: fake):
            dialog._define_model(idx)

    def group(self, dialog=None):
        dialog = dialog or self.dialog
        return dialog.grp_resource_params

    def combo_values(self, combo):
        return [combo.itemData(i) for i in range(combo.count())]


class GroupTest(_DialogCase):
    """V11."""

    def test_shown_folded_with_the_choice_in_its_button(self):
        self.pick(self.wrg18)
        self.define(0, owtg_turbine(self.folder))
        d = self.dialog
        self.assertTrue(self.group().isVisibleTo(d))
        self.assertFalse(d.resource_params.isVisibleTo(d))
        self.assertFalse(d.btn_resource_params.isChecked())
        self.assertEqual(d.btn_resource_params.arrowType(), QtCore.Qt.RightArrow)
        self.assertFalse(d.btn_resource_params.font().bold())
        self.assertEqual(d.btn_resource_params.text(), TITLE)
        # The choices: only the multiples of 18, 126 selected, nearest, no editable field.
        self.assertEqual(self.combo_values(d.cb_wd_count), list(range(18, 361, 18)))
        self.assertEqual([d.cb_wd_count.itemText(i) for i in range(d.cb_wd_count.count())],
                         [str(v) for v in range(18, 361, 18)])
        self.assertEqual(d.cb_wd_count.currentData(), 126)
        self.assertFalse(d.cb_wd_count.isEditable())
        self.assertEqual(self.combo_values(d.cb_wd_interp), ["nearest", "linear"])
        self.assertEqual(d.cb_wd_interp.currentData(), "nearest")
        self.assertEqual(d.lbl_speedup.text(), 'Aceleración: ninguna ⓘ')
        self.assertEqual(d.lbl_wind_speeds.text(), "3–24 m/s, cada")
        self.assertEqual(d.cb_ws_step.currentData(), 0.5)
        self.assertTrue(d.cb_ws_step.isEnabled())
        self.assertIn("sectores=18", d.lbl_wrg_meta.text())
        # Unfolded: the 2×2 of the plan, interpolation and Speedup on the left, directions and speeds on the right.
        d.btn_resource_params.setChecked(True)
        self.assertTrue(d.resource_params.isVisibleTo(d))
        self.assertEqual(d.btn_resource_params.arrowType(), QtCore.Qt.DownArrow)
        grid = d.resource_params.layout()
        position = {}
        for i in range(grid.count()):
            item = grid.itemAt(i)
            widget = item.widget()
            row, column, _rs, _cs = grid.getItemPosition(i)
            if widget is not None:
                position[widget] = (row, column)
            elif item.layout() is not None:
                for j in range(item.layout().count()):
                    w = item.layout().itemAt(j).widget()
                    if w is not None:
                        position[w] = (row, column)
        self.assertEqual(position[d.cb_wd_interp], (1, 0))
        self.assertEqual(position[d.cb_wd_count], (1, 1))
        self.assertEqual(position[d.lbl_speedup], (2, 0))
        self.assertEqual(position[d.cb_ws_step], (2, 1))
        self.assertEqual(position[d.lbl_wind_speeds], (2, 1))
        # Other choices change the button.
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("linear"))
        d.cb_wd_count.setCurrentIndex(d.cb_wd_count.findData(36))
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(1.0))
        self.assertEqual(d.btn_resource_params.text(), "Parámetros del recurso (linear, 36 direcciones, 3–24 m/s cada 1 m/s)")
        # Opening the dialog again: folded and with the initial values.
        other = self.new_dialog()
        self.pick(self.wrg18, other)
        self.assertFalse(other.btn_resource_params.isChecked())
        self.assertEqual(other.cb_wd_count.currentData(), 126)
        self.assertEqual(other.cb_wd_interp.currentData(), "nearest")

    def test_metadata_line_right_under_the_wrg_row(self):
        d = self.dialog
        self.pick(self.wrg18)
        meta_parent = d.lbl_wrg_meta.parentWidget().layout()
        cell = next(l for l in _layouts(meta_parent) if l.indexOf(d.lbl_wrg_meta) >= 0)
        self.assertEqual(cell.spacing(), 0)
        self.assertEqual(cell.indexOf(d.ed_wrg.parentWidget()), 0)
        self.assertEqual(cell.indexOf(d.lbl_wrg_meta), 1)

    def test_without_readable_models_no_speeds(self):
        d = self.dialog
        self.pick(self.wrg18)
        self.assertEqual(d.lbl_wind_speeds.text(), "—")
        self.assertFalse(d.cb_ws_step.isEnabled())
        self.assertEqual(d.btn_resource_params.text(), "Parámetros del recurso (nearest, 126 direcciones)")
        # A row with a model that gives no band (no power anywhere): «—» too.
        self.define(0, build_wt_from_manual("Z", 100.0, 90.0, [3.0, 10.0, 25.0], [0.0, 0.0, 0.0], [0.8, 0.8, 0.1]))
        self.assertEqual(d.lbl_wind_speeds.text(), "—")
        self.assertFalse(d.cb_ws_step.isEnabled())

    def test_models_added_replaced_and_removed(self):
        d = self.dialog
        self.pick(self.wrg18)
        self.define(0, owtg_turbine(self.folder))
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(1.0))
        # A second row, not yet defined: «—», no step; the launch still refuses an undefined model.
        d.sp_n.setValue(2)
        self.assertEqual(d.lbl_wind_speeds.text(), "—")
        self.assertFalse(d.cb_ws_step.isEnabled())
        with self.assertRaises(dialog_state.DialogStateError):
            dialog_state._models_from_dialog_rows(d)
        # Defined: the union of the bands (3-24 and 4-20) and the finer initial step, 0.5.
        self.define(1, manual_turbine())
        self.assertEqual(d.lbl_wind_speeds.text(), "3–24 m/s, cada")
        self.assertEqual(d.cb_ws_step.currentData(), 0.5)
        # Replaced by a wider band: the range follows and the step goes back to the initial one.
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(0.25))
        self.define(1, manual_turbine(ws=(2.0, 8.0, 12.0, 28.0)))
        self.assertEqual(d.lbl_wind_speeds.text(), "2–28 m/s, cada")
        self.assertEqual(d.cb_ws_step.currentData(), 0.5)
        self.assertEqual(d.btn_resource_params.text(), "Parámetros del recurso (nearest, 126 direcciones, 2–28 m/s cada 0,5 m/s)")
        # Removed: back to the first model alone.
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(1.0))
        d.sp_n.setValue(1)
        self.assertEqual(d.lbl_wind_speeds.text(), "3–24 m/s, cada")
        self.assertEqual(d.cb_ws_step.currentData(), 0.5)

    def test_composite_turbine_of_a_row(self):
        # The row's turbine is a composite: the speeds are those of the type the calculation takes (the first).
        d = self.dialog
        self.pick(self.wrg18)
        self.define(0, WindTurbines.from_WindTurbine_lst([manual_turbine(), idle_turbine()]), mode="manual")
        self.assertEqual(d.lbl_wind_speeds.text(), "4–20 m/s, cada")
        self.assertTrue(d.cb_ws_step.isEnabled())

    def test_hidden_without_a_wrg(self):
        d = self.dialog
        self.assertFalse(self.group().isVisibleTo(d))
        self.pick(self.wrg18)
        self.assertTrue(self.group().isVisibleTo(d))
        d._clear_wrg()
        self.assertFalse(self.group().isVisibleTo(d))
        # A GRD folder alone: hidden; with a WRG as well, the WRG prevails and the group shows.
        d.ed_dir.setText(self.folder)
        self.assertFalse(self.group().isVisibleTo(d))
        self.pick(self.wrg18)
        self.assertTrue(self.group().isVisibleTo(d))
        # A WRG that cannot be read: hidden.
        bad = os.path.join(self.folder, "bad.wrg")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("not a wrg\n")
        self.pick(bad)
        self.assertFalse(self.group().isVisibleTo(d))

    def test_help_on_each_control_and_its_label(self):
        d = self.dialog
        self.pick(self.wrg18)
        labels = {w.text(): w for w in d.resource_params.findChildren(QtWidgets.QLabel)}
        expected = {
            d.cb_wd_count: HELP["count"], labels["Direcciones de cálculo"]: HELP["count"],
            d.cb_wd_interp: HELP["interp"], labels["Interpolación direccional"]: HELP["interp"],
            d.lbl_speedup: HELP["speedup"],
            d.cb_ws_step: HELP["speeds"], d.lbl_wind_speeds: HELP["speeds"], labels["Velocidades de cálculo:"]: HELP["speeds"],
        }
        for widget, text in expected.items():
            with self.subTest(widget=widget.objectName() or type(widget).__name__):
                self.assertEqual(widget.toolTip(), text)


class PathTest(_DialogCase):
    """V12: the button, a path typed and confirmed, the saved path at opening and clearing update the group."""

    def test_sources_of_the_path(self):
        d = self.dialog
        self.pick(self.wrg18)
        self.assertEqual(d.cb_wd_count.currentData(), 126)
        d.cb_wd_count.setCurrentIndex(d.cb_wd_count.findData(36))
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("linear"))
        # The same path confirmed again keeps the choice.
        d.ed_wrg.setText(self.wrg18)
        d.ed_wrg.editingFinished.emit()
        self.assertEqual((d.cb_wd_count.currentData(), d.cb_wd_interp.currentData()), (36, "linear"))
        # With a model, the step chosen is also kept for the same path.
        self.define(0, manual_turbine())
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(0.25))
        d.ed_wrg.setText(self.wrg18)
        d.ed_wrg.editingFinished.emit()
        self.assertEqual((d.cb_wd_count.currentData(), d.cb_wd_interp.currentData(), d.cb_ws_step.currentData()),
                         (36, "linear", 0.25))
        # Another WRG typed and confirmed: its options and the initial choice of directions and interpolation.
        # The step belongs to the turbines, not to the WRG (decision of the user): another WRG keeps the chosen one.
        d.ed_wrg.setText(self.wrg12)
        d.ed_wrg.editingFinished.emit()
        self.assertEqual(self.combo_values(d.cb_wd_count), list(range(12, 361, 12)))
        self.assertEqual((d.cb_wd_count.currentData(), d.cb_wd_interp.currentData()), (84, "nearest"))
        self.assertEqual(d.cb_ws_step.currentData(), 0.25)
        self.assertIn("sectores=12", d.lbl_wrg_meta.text())
        # Cleared: hidden.
        d._clear_wrg()
        self.assertFalse(self.group().isVisibleTo(d))
        # The path saved at opening.
        self.settings.setValue("last_wrg_path", self.wrg12)
        self.settings.sync()
        self.addCleanup(self.settings.remove, "last_wrg_path")
        opened = self.new_dialog()
        self.assertEqual(opened.ed_wrg.text(), self.wrg12)
        self.assertTrue(opened.grp_resource_params.isVisibleTo(opened))
        self.assertEqual(opened.cb_wd_count.currentData(), 84)


class LaunchTest(_DialogCase):
    """V13: the choice reaches the configuration and the calculation; nothing is saved."""

    def test_the_choice_reaches_the_calculation(self):
        d = self.dialog
        self.pick(self.wrg18)
        wt = owtg_turbine(self.folder)
        self.define(0, wt)
        d.cb_wd_count.setCurrentIndex(d.cb_wd_count.findData(54))
        d.cb_wd_interp.setCurrentIndex(d.cb_wd_interp.findData("linear"))
        d.cb_ws_step.setCurrentIndex(d.cb_ws_step.findData(0.25))
        before = set(self.settings.allKeys())
        with mock.patch.object(dialog_state, "_models_from_dialog_rows", return_value=[{
                "name": "T0", "wt": wt, "meta": {"mode": "owtg"}, "coords_xy": [(1200.0, 1300.0), (1700.0, 1450.0)],
                "source_row_index": 0, "source_type_index": 0}]):
            config = dialog_state.build_energy_dialog_state(d, project_crs_authid="EPSG:32630", warn=False).to_energy_config()
        self.assertEqual((config.wrg_direction_count, config.wrg_wd_interp, config.wrg_speedup_method, config.energy_ws_step),
                         (54, "linear", "none", 0.25))
        config.update_project_layers = False
        config.fixed_ti = 0.08
        sims = []
        call = runner.simulate

        def recording(wfm, *args, **kwargs):
            sims.append((kwargs.get("wd"), kwargs.get("ws"), wfm.site.interp_method["wd"]))
            return call(wfm, *args, **kwargs)

        with mock.patch.object(runner, "simulate", recording):
            EnergyRunner().run(config)
        self.assertTrue(sims)
        for wd, ws, method in sims:
            self.assertEqual(len(wd), 54)
            np.testing.assert_array_equal(ws, speed_grid(3.0, 24.0, 0.25))  # the band the dialog showed
            self.assertEqual(method, "linear")
        self.assertEqual(d.lbl_wind_speeds.text(), "3–24 m/s, cada")
        # Nothing new in the settings, and a new dialog shows the initial values.
        self.settings.sync()
        self.assertEqual(set(self.settings.allKeys()) - before, set())
        reopened = self.new_dialog()
        self.pick(self.wrg18, reopened)
        self.assertEqual((reopened.cb_wd_count.currentData(), reopened.cb_wd_interp.currentData()), (126, "nearest"))
        self.assertFalse(reopened.btn_resource_params.isChecked())

    def test_rows_sharing_a_composite_turbine(self):
        # Two rows with the same composite object, each taking its own type (4-20 m/s, step 1; 2-28 m/s, step 0.5):
        # the dialog shows, sends and the calculation records the same union and step.
        d = self.dialog
        self.pick(self.wrg18)
        shared = WindTurbines.from_WindTurbine_lst([manual_turbine(), wide_turbine()])
        d.sp_n.setValue(2)
        self.define(0, shared, mode="manual")
        self.define(1, shared, mode="manual", diam=120.0)
        self.assertEqual(d.lbl_wind_speeds.text(), "2–28 m/s, cada")
        self.assertEqual(d.cb_ws_step.currentData(), 0.5)
        layer = mock.Mock()
        layer.id.return_value, layer.name.return_value = "layer", "Layer"
        points = {0: [(1200.0, 1300.0)], 1: [(1700.0, 1450.0)]}
        with mock.patch.object(d, "_find_interactive_layer_for_row", return_value=layer), \
                mock.patch.object(d, "_collect_layer_points_for_row", side_effect=points.get):
            config = dialog_state.build_energy_dialog_state(d, project_crs_authid="EPSG:32630", warn=False).to_energy_config()
        self.assertEqual(config.energy_ws_step, 0.5)
        config.update_project_layers = False
        config.fixed_ti = 0.08
        result = EnergyRunner().run(config)
        settings = result["resource_settings"]
        self.assertEqual(settings["ws_m_s"], [float(v) for v in speed_grid(2.0, 28.0, 0.5)])
        self.assertEqual(settings["turbine_band_m_s"], [2.0, 28.0])
        self.assertEqual([b["band_m_s"] for b in settings["turbine_bands"]], [[4.0, 20.0], [2.0, 28.0]])

    def test_a_model_without_band_is_not_launched(self):
        # A curve with zero power at every node gives no band: «—» in the group and no launch, in the user's language.
        d = self.dialog
        self.pick(self.wrg18)
        self.define(0, build_wt_from_manual("Z", 100.0, 90.0, [3.0, 10.0, 25.0], [0.0, 0.0, 0.0], [0.8, 0.8, 0.1]),
                    mode="manual")
        self.assertEqual(d.lbl_wind_speeds.text(), "—")
        layer = mock.Mock()
        layer.id.return_value, layer.name.return_value = "layer", "Layer"
        self.addCleanup(i18n.set_language, i18n.current_language())
        english = ("Calculation wind speeds", "The calculation wind speeds cannot be deduced from the curve of a model: it "
                   "has no valid tabulated wind speeds, its power is zero at every node, its operating band is not valid "
                   "or its kind of curve is not supported. Check the models.")
        for lang, (title, message) in (("es", ("Velocidades de cálculo", NO_BAND)), ("en", english)):
            i18n.set_language(lang)
            with self.subTest(lang=lang), \
                    mock.patch.object(d, "_find_interactive_layer_for_row", return_value=layer), \
                    mock.patch.object(d, "_collect_layer_points_for_row", return_value=[(1200.0, 1300.0)]), \
                    self.assertRaises(dialog_state.DialogStateError) as raised:
                dialog_state.build_energy_dialog_state(d, project_crs_authid="EPSG:32630", warn=False)
            self.assertEqual((raised.exception.title, raised.exception.message), (title, message))
            # Launched from the dialog: the warning, and no calculation.
            with mock.patch.object(d, "_find_interactive_layer_for_row", return_value=layer), \
                    mock.patch.object(d, "_collect_layer_points_for_row", return_value=[(1200.0, 1300.0)]), \
                    mock.patch.object(dialog_controller, "_project_crs_authid", return_value="EPSG:32630"), \
                    mock.patch.object(dialog_controller, "show_user_warning") as warning:
                self.assertIsNone(dialog_controller._read_dialog_state(d, warn=False))
            warning.assert_called_once_with(d, title, message)

    def test_without_the_group_the_initial_values(self):
        params = self.dialog._get_resource_params()
        self.assertEqual(params, {"direction_count": None, "wd_interp": "nearest", "ws_step": None})


class TranslationTest(unittest.TestCase):
    """V14: every new text has its translation in the three languages."""

    def test_every_new_text(self):
        texts = [
            "Interpolación direccional", "Direcciones de cálculo", 'Aceleración: ninguna ⓘ', "Velocidades de cálculo:",
            "{low}–{high} m/s, cada", ", {low}–{high} m/s cada {step} m/s",
            "Parámetros del recurso ({interp}, {count} direcciones{speeds})", *HELP.values(),
            "Velocidades de cálculo", NO_BAND,
        ]
        i18n._ensure()
        for lang in _LANGS:
            table = i18n._STATE["full"][lang]
            for text in texts:
                with self.subTest(lang=lang, text=text[:40]):
                    self.assertIn(text, table)
                    self.assertNotEqual(table[text], "")


def _layouts(layout):
    """``layout`` and every layout inside it."""
    out = [layout]
    for i in range(layout.count()):
        child = layout.itemAt(i).layout()
        if child is not None:
            out += _layouts(child)
    return out


if __name__ == "__main__":
    unittest.main()
