# -*- coding: utf-8 -*-
"""Reusable controls of the wake group (``ui_core/wake_controls.py``, #46 P1d), offscreen and unconnected."""
import os
import tempfile
import unittest

from qgis.PyQt import QtCore, QtGui, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core.wake_setup import catalog as cat  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ui_core import wake_controls as wc  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def zong_editor():
    e = cat.entry(cat.DEFICIT, "ZongGaussianDeficit")
    defaults = cat.signature_defaults(e)
    helps = {p: cat.PARAM_HELP.get(p) or cat.PARAM_HELP_TEMPLATE.format(name=p, value=cfg.plain_value(defaults[p]))
             for p in e.params}
    editor = wc.ParamEditor([(p, defaults[p]) for p in e.params], helps)
    editor.set_values(cfg.deficit_signature("ZongGaussianDeficit")[0].params)
    return editor


class ParamEditorTest(unittest.TestCase):
    def test_one_control_per_kind_with_the_signature_values(self):
        editor = zong_editor()
        self.assertIsInstance(editor.control("ct2a"), QtWidgets.QComboBox)
        self.assertEqual([editor.control("ct2a").itemData(i) for i in range(2)], ["ct2a_madsen", "ct2a_mom1d"])
        self.assertIsInstance(editor.control("use_effective_ti"), QtWidgets.QComboBox)
        box, fields = editor.control("a")
        self.assertEqual([f.text() for f in fields], ["0.38", "0.004"])
        self.assertIsInstance(editor.control("lam"), QtWidgets.QLineEdit)
        deltawd = cat.signature_defaults(cat.entry(cat.DEFICIT, "ZongGaussianDeficit"))["deltawD"]
        self.assertEqual(editor.control("deltawD").text(), repr(deltawd))  # every digit, never rounded
        self.assertEqual(editor.values(), cfg.deficit_signature("ZongGaussianDeficit")[0].params)
        self.assertEqual(editor.errors(), [])
        self.assertIn("velocidad efectiva", editor.control("use_effective_ws").toolTip())
        self.assertEqual(editor.control("lam").toolTip(), "lam (PyWake). Valor de la firma: 7.5.")

    def test_a_number_is_read_exactly_as_typed(self):
        editor = zong_editor()
        seen = []
        editor.changed.connect(lambda: seen.append(1))
        editor.control("lam").setText("0,2149")
        editor.control("ctlim").setText("1e3")
        editor.control("B").setText("4")
        v = editor.values()
        self.assertEqual((v["lam"], v["ctlim"], v["B"]), (0.2149, 1000.0, 4))
        self.assertIsInstance(v["B"], int)  # the signature value is an integer
        self.assertTrue(seen)
        # Nothing is clipped to a range nor brought back to the default.
        editor.control("lam").setText("-1e9")
        self.assertEqual(editor.values()["lam"], -1e9)

    def test_an_unreadable_field_is_reported_not_replaced(self):
        editor = zong_editor()
        editor.control("lam").setText("abc")
        editor.control("a")[1][1].setText("")
        self.assertEqual(editor.errors(), ["a", "lam"])
        self.assertNotIn("lam", editor.values())
        self.assertIn("border", editor.control("lam").styleSheet())
        editor.control("lam").setText("nan")
        self.assertIn("lam", editor.errors())

    def test_booleans_and_ct2a(self):
        editor = zong_editor()
        c = editor.control("use_effective_ws")
        c.setCurrentIndex(c.findData(True))
        f = editor.control("ct2a")
        f.setCurrentIndex(f.findData("ct2a_mom1d"))
        v = editor.values()
        self.assertIs(v["use_effective_ws"], True)
        self.assertEqual(v["ct2a"], "ct2a_mom1d")

    def test_the_controls_start_with_the_signature_values(self):
        editor = wc.ParamEditor([("flag", False), ("n", 3), ("x", 0.25), ("v", [1.5, 0.8]), ("ct2a", "ct2a_madsen")])
        self.assertEqual(editor.values(), {"flag": False, "n": 3, "x": 0.25, "v": [1.5, 0.8], "ct2a": "ct2a_madsen"})
        self.assertEqual(editor.errors(), [])

    def test_a_list_of_another_length_is_refused(self):
        editor = wc.ParamEditor([("v", [1.0, 2.0])])
        with self.assertRaises(ValueError):
            editor.set_values({"v": [9.0]})

    def test_a_fraction_in_an_integer_argument_is_kept_as_typed(self):
        editor = zong_editor()
        editor.control("B").setText("3.5")
        self.assertEqual(editor.values()["B"], 3.5)

    def test_read_only_mode(self):
        editor = zong_editor()
        editor.set_read_only(True)
        self.assertTrue(editor.control("lam").isReadOnly())
        self.assertFalse(editor.control("ct2a").isEnabled())


class SectionAndComboTest(unittest.TestCase):
    def test_section_folded_by_default(self):
        s = wc.CollapsibleSection("Parámetros del déficit")
        s.show()
        self.assertFalse(s.isExpanded())
        self.assertFalse(s.body.isVisible())
        s.setExpanded(True)
        self.assertTrue(s.body.isVisible())
        s.header.click()
        self.assertFalse(s.isExpanded())

    def test_options_with_help_and_disabled_with_their_reason(self):
        combo = QtWidgets.QComboBox()
        wc.fill_option_combo(combo, [("LinearSum", "LinearSum", "Suma de los bloqueos.", None),
                                     ("WeightedSum", "WeightedSum", "No se puede usar en el bloqueo…", "Motivo de PyWake")])
        self.assertEqual(combo.itemData(1, QtCore.Qt.ToolTipRole), "No se puede usar en el bloqueo…\nMotivo de PyWake")
        self.assertFalse(combo.model().item(1).isEnabled())
        self.assertTrue(combo.model().item(0).isEnabled())
        # A choice made before is kept when the options are filled again, also if it is now disabled.
        combo.setCurrentIndex(1)
        wc.fill_option_combo(combo, [("LinearSum", "LinearSum", "", None), ("WeightedSum", "WeightedSum", "", "x")])
        self.assertEqual(combo.currentData(), "WeightedSum")
        # «Ninguno» is a value of its own, kept like any other; None is not accepted as an option's data.
        wc.fill_option_combo(combo, [("RotorCenter", "RotorCenter", "", None), ("", "Ninguno", "", None)])
        combo.setCurrentIndex(1)
        wc.fill_option_combo(combo, [("RotorCenter", "RotorCenter", "", None), ("", "Ninguno", "", None)])
        self.assertEqual(combo.currentIndex(), 1)
        with self.assertRaises(ValueError):
            wc.fill_option_combo(combo, [(None, "Ninguno", "", None)])

    def test_the_qt_names_exist_in_qt5_and_qt6(self):
        import VelantisWind.qt_compat  # noqa: F401
        for name in ("RightArrow", "DownArrow", "ToolTipRole", "ToolButtonTextBesideIcon"):
            self.assertTrue(hasattr(QtCore.Qt, name), name)


if __name__ == "__main__":
    unittest.main()
