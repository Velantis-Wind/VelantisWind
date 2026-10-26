# -*- coding: utf-8 -*-
"""The removed calculation profiles leave nothing behind: not in the dialog, the package or its documentation."""
import os
import tempfile
import unittest
from pathlib import Path

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

import VelantisWind  # noqa: E402
from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402

_PACKAGE = Path(VelantisWind.__file__).resolve().parent
_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _sources():
    """The package's code and documentation, and the repository README; the changelog keeps the history."""
    files = [p for p in sorted(_PACKAGE.rglob("*")) if p.suffix in (".py", ".md") and p.name != "CHANGELOG.md"]
    readme = _PACKAGE.parent / "README.md"
    return files + ([readme] if readme.is_file() else [])


def _found(needles):
    hits = []
    for path in _SOURCES:
        text = path.read_text(encoding="utf-8")
        hits += [f"{path.relative_to(_PACKAGE.parent)}: {n}" for n in needles if n in text]
    return hits


_SOURCES = _sources()


class WakeModelMatrixRemovedTest(unittest.TestCase):
    def test_nothing_of_the_matrix_is_left(self):
        needles = (
            "benchmark_matrix", "wake_model_matrix", "WAKE_MODEL_MATRIX", "BENCHMARK_MATRIX",
            "__velantis_bastankhah_2014__", "__velantis_jensen_1983__",
            "TURBOPARK_RC", "TURBOPARKRC", "TURBOPARK_CGI9", "TURBOPARKCGI9", "TURBOPARKROTORCENTER",
            "TURBOPARKCGIROTORAVG9",
            "Ejecutar matriz", "Matriz de comparación", "Matriz de modelos de estela", "Benchmark matrix",
            "Run model matrix", "Wake-model matrix", "wake-model matrix", "Wake-model comparison", "wake-model comparison",
        )
        self.assertEqual(_found(needles), [])


class TurboparkReferenceRemovedTest(unittest.TestCase):
    def test_nothing_of_the_reference_is_left(self):
        needles = (
            "TURBOPARK_REFERENCE", "TURBOPARK_BENCHMARK", "_apply_energy_profile_physics_preset", "_turbopark_ui_",
            "Referencia TurbOPark", "de referencia TurbOPark", "reference profile",
        )
        self.assertEqual(_found(needles), [])


class EnergyProfilesRemovedTest(unittest.TestCase):
    def test_nothing_of_the_profiles_is_left(self):
        needles = (
            "energy_profile", "EXTENDED_PROFILE", "PYWAKE_PROFILE", "PYWAKE_NATIVE", "DEFAULT_ENERGY_PROFILE",
            "normalize_profile", "resolve_energy_grid", "direction_steps", "max_wd_step", "energy_hours_per_year",
            "energy_ws_min", "energy_ws_max", "Perfil de cálculo", "Discretización energética", "Auto WRG",
            "Paso angular máximo", "Calculation profile", "Energy discretisation", "odd_multiple",
        )
        self.assertEqual(_found(needles), [])

    def test_the_dialog_ignores_the_old_settings(self):
        # V04 too: nothing locks the physics selectors, whatever was saved.
        old = {"energy_profile": "TURBOPARK_REFERENCE", "energy_direction_steps": 36, "energy_max_wd_step_deg": 3.0,
               "energy_ws_min": 4.0, "energy_ws_max": 20.0, "energy_ws_step": 0.5, "energy_hours_per_year": 8760.0}
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        for key, value in old.items():
            settings.setValue(key, value)
            self.addCleanup(settings.remove, key)
        settings.sync()
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(hasattr(dialog, "cb_energy_profile"))
        self.assertEqual(dialog.btn_calc_update.text(), "Calcular AEP")
        for position, combo in dialog.wake_group.combo.items():
            with self.subTest(selector=position):
                self.assertTrue(combo.isEnabled())
        settings.sync()
        self.assertEqual({key: settings.value(key) for key in old}, old)


if __name__ == "__main__":
    unittest.main()
