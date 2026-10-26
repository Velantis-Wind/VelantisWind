# -*- coding: utf-8 -*-
"""The reference air density is kept in the QGIS project, not in the plugin's settings (#36)."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsProject  # noqa: E402

from VelantisWind.energy_core.project_density import UNDEFINED, read_project_density, write_project_density  # noqa: E402

SITE = {"enabled": True, "mode": "uniform", "reference_density_kg_m3": 1.1, "reference_altitude_m": 250.0}


class ProjectDensityTest(unittest.TestCase):
    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        self.addCleanup(self.project.clear)

    def test_a_project_without_a_reference_starts_undefined(self):
        self.assertEqual(read_project_density(self.project), UNDEFINED)

    def test_the_reference_is_saved_with_the_project_and_marks_it_modified(self):
        self.project.setDirty(False)
        write_project_density(self.project, SITE)
        self.assertEqual(read_project_density(self.project), SITE)
        self.assertTrue(self.project.isDirty())
        self.project.setDirty(False)
        write_project_density(self.project, SITE)  # the same values: nothing changes
        self.assertFalse(self.project.isDirty())

    def test_the_reference_survives_saving_and_opening_the_project(self):
        path = os.path.join(_SETTINGS.name, "site.qgz")
        write_project_density(self.project, SITE)
        self.assertTrue(self.project.write(path))
        self.project.clear()
        self.assertEqual(read_project_density(self.project), UNDEFINED)  # another project: not this one's
        self.assertTrue(self.project.read(path))
        self.assertEqual(read_project_density(self.project), SITE)

    def test_an_unknown_mode_is_read_as_per_turbine(self):
        self.project.writeEntry("VelantisWind", "/air_density_mode", "something")
        self.assertEqual(read_project_density(self.project)["mode"], "per_turbine")


class DialogDensityTest(unittest.TestCase):
    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        self.addCleanup(self.project.clear)

    def dialog(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        return dialog

    @staticmethod
    def enabled(dialog):
        return [w.isEnabled() for w in (dialog.sp_air_density, dialog.sp_air_density_alt, dialog.cb_air_density_mode)]

    def controls(self, dialog):
        return {"enabled": dialog.chk_air_density.isChecked(), "mode": dialog.cb_air_density_mode.currentData(),
                "reference_density_kg_m3": dialog.sp_air_density.value(),
                "reference_altitude_m": dialog.sp_air_density_alt.value()}

    def test_the_dialog_opens_with_the_reference_of_the_project_without_modifying_it(self):
        write_project_density(self.project, SITE)
        self.project.setDirty(False)
        dialog = self.dialog()
        self.assertEqual(self.controls(dialog), SITE)
        self.assertEqual(self.enabled(dialog), [True, True, True])
        self.assertFalse(self.project.isDirty())

    def test_a_project_without_a_reference_opens_undefined_and_unmodified(self):
        self.project.setDirty(False)
        dialog = self.dialog()
        self.assertEqual(self.controls(dialog), UNDEFINED)
        self.assertEqual(self.enabled(dialog), [False, False, False])
        self.assertFalse(self.project.isDirty())

    def test_the_settings_of_the_plugin_are_not_used(self):
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        for key, value in (("air_density_enabled", True), ("air_density_ref_kg_m3", 1.3),
                           ("air_density_ref_altitude_m", 900.0), ("air_density_mode", "uniform")):
            settings.setValue(key, value)
        self.addCleanup(lambda: [settings.remove(k) for k in ("air_density_enabled", "air_density_ref_kg_m3",
                                                              "air_density_ref_altitude_m", "air_density_mode")])
        dialog = self.dialog()
        self.assertEqual(self.controls(dialog), UNDEFINED)
        self.assertEqual(self.enabled(dialog), [False, False, False])
        dialog.chk_air_density.setChecked(True)
        dialog.sp_air_density.setValue(1.05)
        # The settings of the plugin keep their old values: neither read nor written.
        self.assertEqual(float(settings.value("air_density_ref_kg_m3")), 1.3)
        self.assertEqual(float(settings.value("air_density_ref_altitude_m")), 900.0)

    def test_changing_a_control_saves_it_in_the_project(self):
        dialog = self.dialog()
        self.project.setDirty(False)
        dialog.chk_air_density.setChecked(True)
        dialog.sp_air_density.setValue(1.15)
        dialog.sp_air_density_alt.setValue(300.0)
        dialog.cb_air_density_mode.setCurrentIndex(dialog.cb_air_density_mode.findData("uniform"))
        self.assertEqual(read_project_density(self.project), {"enabled": True, "mode": "uniform",
                                                              "reference_density_kg_m3": 1.15,
                                                              "reference_altitude_m": 300.0})
        self.assertTrue(self.project.isDirty())



OTHER = {"enabled": True, "mode": "per_turbine", "reference_density_kg_m3": 1.2, "reference_altitude_m": 40.0}


class ProjectSwitchTest(DialogDensityTest):
    """The dialog can outlive its project (hidden with «← Inicio»): another project brings its own density."""

    def save(self, name, values):
        path = os.path.join(_SETTINGS.name, name)
        self.project.clear()
        write_project_density(self.project, values)
        self.assertTrue(self.project.write(path))
        return path

    def test_opening_another_project_takes_its_reference_without_modifying_it(self):
        site, other = self.save("a.qgz", SITE), self.save("b.qgz", OTHER)
        self.project.read(site)
        dialog = self.dialog()
        dialog.hide()  # as with «← Inicio»
        self.project.read(other)
        self.assertEqual(self.controls(dialog), OTHER)
        self.assertEqual(self.enabled(dialog), [True, True, True])
        self.assertFalse(self.project.isDirty())
        self.assertEqual(read_project_density(self.project), OTHER)  # nothing of the previous one written into it

    def test_a_cleared_project_leaves_the_controls_undefined_and_back(self):
        site = self.save("a.qgz", SITE)
        self.project.read(site)
        dialog = self.dialog()
        self.project.clear()
        self.assertEqual(self.controls(dialog), UNDEFINED)
        self.assertEqual(self.enabled(dialog), [False, False, False])
        self.assertFalse(self.project.isDirty())
        self.project.read(site)
        self.assertEqual(self.controls(dialog), SITE)
        self.assertEqual(self.enabled(dialog), [True, True, True])
        self.assertFalse(self.project.isDirty())

    def test_what_the_dialog_remembers_of_the_last_aep_is_forgotten(self):
        dialog = self.dialog()
        dialog._last_aep_inputs = {"density": (("mode", "uniform"),)}
        dialog._register_last_aep_result({"aep_net_mwh": 1.0}, "Cálculo AEP")
        dialog._scenario_a = dialog._scenario_b = {"label": "Base", "result": {"aep_net_mwh": 1.0}}
        self.project.clear()
        self.assertIsNone(dialog._last_aep_inputs)
        self.assertEqual((dialog._last_aep_result, dialog._last_aep_label), (None, "Último cálculo"))
        self.assertEqual((dialog._scenario_a, dialog._scenario_b), (None, None))
        # The comparator then asks for a calculation of this project, as a new dialog does.
        with mock.patch.object(QtWidgets.QMessageBox, "information") as message:
            dialog._store_current_scenario("A")
            dialog._compare_scenarios()
        self.assertEqual(message.call_count, 2)
        self.assertIn("Primero lanza un cálculo AEP", message.call_args_list[0].args[2])
        self.assertIn("Guarda primero un escenario A y un escenario B", message.call_args_list[1].args[2])
        self.assertIsNone(dialog._scenario_a)

    def test_a_destroyed_dialog_leaves_no_connection_to_the_project(self):
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)  # the dialogs of earlier tests
        before = (self.project.receivers(self.project.cleared), self.project.receivers(self.project.readProject))
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        dialog = AEPSetupDialog()
        self.assertEqual(self.project.receivers(self.project.cleared), before[0] + 1)
        dialog.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.assertEqual((self.project.receivers(self.project.cleared),
                          self.project.receivers(self.project.readProject)), before)
        self.project.clear()  # nothing reaches the deleted dialog


    def test_between_two_saved_projects_with_and_without_the_adjustment(self):
        off = dict(UNDEFINED, reference_density_kg_m3=1.0, reference_altitude_m=10.0)  # saved, switched off
        site, plain = self.save("a.qgz", SITE), self.save("off.qgz", off)
        self.project.read(site)
        dialog = self.dialog()
        for path, values, enabled in ((plain, off, False), (site, SITE, True)):
            with self.subTest(project=os.path.basename(path)):
                self.project.read(path)
                self.assertEqual(self.controls(dialog), values)
                self.assertEqual(self.enabled(dialog), [enabled] * 3)
                self.assertFalse(self.project.isDirty())

    def test_reloading_never_clears_a_modified_project(self):
        dialog = self.dialog()
        self.project.setDirty(True)
        dialog._on_project_switched()
        self.assertTrue(self.project.isDirty())

    def test_another_dialog_keeps_following_the_project_when_one_is_destroyed(self):
        site = self.save("a.qgz", SITE)
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        gone, kept = AEPSetupDialog(), self.dialog()
        gone.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.project.read(site)
        self.assertEqual(self.controls(kept), SITE)


if __name__ == "__main__":
    unittest.main()
