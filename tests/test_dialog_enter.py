# -*- coding: utf-8 -*-
"""The Enter key in the dialog of Energy and in the windows of the wake group (piece E1 of #64).

Return and Enter act on the control with the focus and never launch the AEP nor accept a window from it; a push button
with the focus presses itself; with no control with the focus, or the dialog itself, the default action. Offscreen, with
the settings in a temporary directory and the calculation replaced by a spy before building the dialog; the focus is
checked before each key. The enumerations go by their scoped names, valid in Qt5 and Qt6.
"""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.PyQt.QtTest import QTest

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.Format.NativeFormat, QtCore.QSettings.Scope.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsProject, QgsVectorLayer  # noqa: E402

from VelantisWind.ag_core.wake_setup import catalog as cat  # noqa: E402
from VelantisWind.aep_setup_dialog import AEPSetupDialog  # noqa: E402
from VelantisWind.ui_core.dialog_keys import enter_reaches_default  # noqa: E402

Key = QtCore.Qt.Key
KEYS = (Key.Key_Return, Key.Key_Enter)
ACCEPTED, REJECTED = QtWidgets.QDialog.DialogCode.Accepted, QtWidgets.QDialog.DialogCode.Rejected
STRONG = QtCore.Qt.FocusPolicy.StrongFocus
_CWD = os.getcwd()


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def focused():
    return QtWidgets.QApplication.focusWidget()


def focus(widget):
    """Give ``widget`` the focus of its active window; the focus of the application, to be checked."""
    window = widget.window()
    window.activateWindow()
    QtWidgets.QApplication.setActiveWindow(window)
    widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    QtWidgets.QApplication.processEvents()
    return focused()


def press(widget, key):
    QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


class DialogCase(unittest.TestCase):
    def setUp(self):
        # The manual mode, chosen: without preferences the dialog opens with the predefined models, whose view hides
        # the controls these tests press (the adversarial round on the branch of the predefined models, r4).
        from VelantisWind.ui_core import wake_group as wg
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        settings.setValue(wg.MODE_KEY, wg.MANUAL)
        self.addCleanup(settings.remove, wg.MODE_KEY)
        patcher = mock.patch.object(AEPSetupDialog, "_run_compute_and_update")
        self.compute = patcher.start()  # before building the dialog: the button connects to the spy
        self.addCleanup(patcher.stop)
        self.d = AEPSetupDialog()
        self.addCleanup(self.d.deleteLater)
        self.d.show()
        QtWidgets.QApplication.processEvents()

    def visible(self, kind):
        return [w for w in self.d.findChildren(kind) if w.isVisible() and w.isEnabled()]

    def add(self, widget):
        self.d.layout().addWidget(widget)
        widget.show()
        QtWidgets.QApplication.processEvents()
        return widget


class DialogEnterTest(DialogCase):
    def test_a_field_confirms_its_value_and_does_not_calculate(self):
        edit = next(w for w in self.visible(QtWidgets.QLineEdit)
                    if not isinstance(w.parent(), (QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox)) and not w.isReadOnly())
        for key in KEYS:
            with self.subTest(key=key):
                finished = mock.Mock()
                edit.editingFinished.connect(finished)
                self.assertIs(focus(edit), edit)
                QTest.keyClicks(edit, "1")  # text pending
                self.assertIs(focused(), edit)
                press(edit, key)
                finished.assert_called_once()
                edit.editingFinished.disconnect(finished)
                self.compute.assert_not_called()
                self.assertTrue(self.d.isVisible())

    def test_a_spin_box_takes_the_typed_value_and_does_not_calculate(self):
        spin = self.visible(QtWidgets.QDoubleSpinBox)[0]
        spin.setKeyboardTracking(False)
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIs(focus(spin), spin)
                before = spin.value()
                target = spin.minimum() if before != spin.minimum() else spin.maximum()
                spin.lineEdit().selectAll()
                QTest.keyClicks(spin, spin.textFromValue(target))
                self.assertIs(focused(), spin)
                self.assertEqual(spin.value(), before)  # not yet
                press(spin, key)
                self.assertEqual(spin.value(), target)
                self.compute.assert_not_called()

    def test_a_closed_combo_box_opens_and_an_open_one_chooses(self):
        combo = self.d.wake_group.combo[cat.SUPERPOSITION]
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIs(focus(combo), combo)
                self.assertFalse(combo.view().isVisible())
                press(combo, key)
                self.assertTrue(combo.view().isVisible())
                before = combo.currentIndex()
                self.assertIs(focused(), combo.view())  # the open list has the focus and receives the keys
                press(combo.view(), Key.Key_Down)
                self.assertIs(focused(), combo.view())
                press(combo.view(), key)
                self.assertFalse(combo.view().isVisible())
                self.assertEqual(combo.currentIndex(), before + 1)
                self.compute.assert_not_called()
                combo.setCurrentIndex(before)
        # Escape with the list open closes only the list.
        self.assertIs(focus(combo), combo)
        press(combo, Key.Key_Return)
        self.assertIs(focused(), combo.view())
        press(combo.view(), Key.Key_Escape)
        self.assertFalse(combo.view().isVisible())
        self.assertTrue(self.d.isVisible())

    def test_a_disabled_combo_box_does_not_open_and_the_key_goes_by_the_focus_qt_leaves(self):
        combo = self.d.wake_group.combo[cat.SUPERPOSITION]
        for key in KEYS:
            with self.subTest(key=key):
                combo.setEnabled(True)
                self.assertIs(focus(combo), combo)
                combo.setEnabled(False)
                QtWidgets.QApplication.processEvents()
                left = focused()
                self.assertIsNot(left, combo)
                # Kept deterministic: Qt leaves it on another control, not on a push button that would do its own.
                self.assertNotIsInstance(left, QtWidgets.QPushButton)
                press(left or self.d, key)
                self.assertFalse(combo.view().isVisible())
                default = left is None or left is self.d
                self.assertEqual(self.compute.call_count, 1 if default else 0)
                self.compute.reset_mock()
                if isinstance(left, QtWidgets.QComboBox):  # the table: a closed combo box of the dialog opens
                    self.assertTrue(left.view().isVisible())
                    left.hidePopup()
        combo.setEnabled(True)

    def test_the_layer_selector_of_a_row_opens(self):
        layers = [QgsVectorLayer("Point?crs=EPSG:32630", name, "memory") for name in ("A", "B")]
        QgsProject.instance().addMapLayers(layers)
        self.addCleanup(QgsProject.instance().removeMapLayers, [layer.id() for layer in layers])
        QtWidgets.QApplication.processEvents()
        combo = self.d._rows[0]["layer_cb"]
        self.assertGreaterEqual(combo.count(), 3)
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIs(focus(combo), combo)
                press(combo, key)
                self.assertTrue(combo.view().isVisible())
                combo.hidePopup()
                self.compute.assert_not_called()

    def test_an_editable_combo_box_confirms_its_text_and_opens(self):
        combo = self.add(QtWidgets.QComboBox(self.d))
        combo.setEditable(True)
        combo.addItems(["alpha", "beta"])
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIn(focus(combo.lineEdit()), (combo, combo.lineEdit()))
                combo.lineEdit().clear()
                QTest.keyClicks(combo.lineEdit(), f"gamma{key}")
                self.assertIn(focused(), (combo, combo.lineEdit()))
                press(combo.lineEdit(), key)
                self.assertEqual(combo.currentText(), f"gamma{key}")  # its own confirmation: the item is added
                self.assertGreaterEqual(combo.findText(f"gamma{key}"), 0)
                self.assertTrue(combo.view().isVisible())
                combo.hidePopup()
                self.compute.assert_not_called()

    def test_the_completer_of_an_editable_combo_box_keeps_its_own_route(self):
        combo = self.add(QtWidgets.QComboBox(self.d))
        combo.setEditable(True)
        combo.addItems(["alpha", "beta"])
        combo.completer().setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        popup = combo.completer().popup()
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIn(focus(combo.lineEdit()), (combo, combo.lineEdit()))
                combo.lineEdit().clear()
                QTest.keyClicks(combo.lineEdit(), "al")
                self.assertTrue(popup.isVisible())
                # The focus stays on the combo box; on a real screen the popup grabs the keyboard and receives the
                # keys, which the offscreen platform cannot grab: they are given to the popup, as the grab would.
                self.assertIn(focused(), (combo, combo.lineEdit()))
                press(popup, Key.Key_Down)
                self.assertIn(focused(), (combo, combo.lineEdit()))
                self.assertTrue(popup.isVisible())
                press(popup, key)  # the completer takes the key (it filters the events of its popup)
                self.assertFalse(popup.isVisible())
                self.assertEqual(combo.lineEdit().text(), "alpha")
                self.assertFalse(combo.view().isVisible())  # the list of the combo does not open
                self.compute.assert_not_called()

    def test_enter_in_the_view_of_a_model_changes_nothing(self):
        # The values of a predefined model are read, not edited: Enter in one of them neither launches the AEP nor
        # changes anything.
        from VelantisWind.ui_core import wake_group as wg
        g = self.d.wake_group
        g.set_mode(wg.PREDEFINED)
        g.combo_preset.setCurrentIndex(g.combo_preset.findData("NiayifarGaussian"))
        g.preset_sections[cat.DEFICIT].setExpanded(True)
        QtWidgets.QApplication.processEvents()
        field = g.preset_editors[cat.DEFICIT].control("ceps")
        before = g.config()
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIs(focus(field), field)
                press(field, key)
                QTest.keyClicks(field, "9")
                self.assertEqual(field.text(), "0.2")
                self.assertEqual(g.config(), before)
                self.compute.assert_not_called()

    def test_other_controls_do_nothing(self):
        box = self.visible(QtWidgets.QCheckBox)[0]
        header = self.d.wake_group.sec_deficit.header
        area = self.visible(QtWidgets.QScrollArea)[0]
        area.setFocusPolicy(STRONG)
        for widget in (box, header, area):
            for key in KEYS:
                with self.subTest(widget=type(widget).__name__, key=key):
                    state = box.isChecked(), self.d.wake_group.sec_deficit.isExpanded()
                    self.assertIs(focus(widget), widget)
                    press(widget, key)
                    self.assertEqual((box.isChecked(), self.d.wake_group.sec_deficit.isExpanded()), state)
                    self.compute.assert_not_called()
                    self.assertTrue(self.d.isVisible())

    def test_the_default_action_with_the_dialog_or_no_control_with_the_focus(self):
        self.d.setFocusPolicy(STRONG)
        for key in KEYS:
            with self.subTest(key=key, focus="dialog"):
                self.compute.reset_mock()
                self.assertIs(focus(self.d), self.d)
                press(self.d, key)
                self.compute.assert_called_once()
            with self.subTest(key=key, focus="none"):
                self.compute.reset_mock()
                focus(self.d).clearFocus()
                QtWidgets.QApplication.processEvents()
                self.assertIsNone(focused())
                press(self.d, key)
                self.compute.assert_called_once()

    def test_a_push_button_with_the_focus_presses_itself(self):
        other = self.add(QtWidgets.QPushButton("other", self.d))
        clicked = mock.Mock()
        other.clicked.connect(clicked)
        for key in KEYS:
            with self.subTest(key=key, button="Calcular AEP"):
                self.compute.reset_mock()
                self.assertIs(focus(self.d.btn_calc_update), self.d.btn_calc_update)
                press(self.d.btn_calc_update, key)
                self.compute.assert_called_once()
            with self.subTest(key=key, button="other"):
                self.compute.reset_mock()
                clicked.reset_mock()
                self.assertIs(focus(other), other)
                press(other, key)
                clicked.assert_called_once()
                self.compute.assert_not_called()

    def test_escape_without_a_list_open_closes_the_dialog(self):
        self.d.setFocusPolicy(STRONG)
        self.assertIs(focus(self.d), self.d)
        press(self.d, Key.Key_Escape)
        self.assertFalse(self.d.isVisible())
        self.compute.assert_not_called()


class HelperTest(unittest.TestCase):
    """The routes a real key press reaches only through Qt's own focus: the focus in another window, and the inner
    editor of an editable combo box as the focus of the application."""

    def setUp(self):
        self.d = QtWidgets.QDialog()
        self.editable = QtWidgets.QComboBox(self.d)
        self.editable.setEditable(True)
        self.editable.addItems(["a", "b"])
        self.other = QtWidgets.QDialog()
        self.other_combo = QtWidgets.QComboBox(self.other)
        self.other_combo.addItems(["a", "b"])
        for w in (self.d, self.other):
            self.addCleanup(w.deleteLater)
            w.show()

    def enter(self, focus_widget, key):
        event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key, QtCore.Qt.KeyboardModifier.NoModifier)
        with mock.patch.object(QtWidgets.QApplication, "focusWidget", return_value=focus_widget):
            return enter_reaches_default(self.d, event), event.isAccepted()

    def test_the_inner_editor_of_an_editable_combo_box_opens_it(self):
        for key in KEYS:
            with self.subTest(key=key):
                self.assertEqual(self.enter(self.editable.lineEdit(), key), (False, True))
                self.assertTrue(self.editable.view().isVisible())
                self.editable.hidePopup()

    def test_the_focus_in_another_window(self):
        for key in KEYS:
            with self.subTest(key=key):
                self.assertEqual(self.enter(self.other_combo, key), (False, True))
                self.assertFalse(self.other_combo.view().isVisible())

    def test_another_key_goes_on(self):
        event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, Key.Key_Escape, QtCore.Qt.KeyboardModifier.NoModifier)
        self.assertTrue(enter_reaches_default(self.d, event))


class WindowEnterTest(DialogCase):
    def window(self, blockage=False):
        g = self.d.wake_group
        g._select(cat.ENGINE, "All2AllIterative")
        if blockage:
            g._select(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
            combo = g.args_editor(cat.BLOCKAGE).control("groundModel")
            combo.setCurrentIndex(combo.findData("MultiMirror"))
            QtWidgets.QApplication.processEvents()
            w = g.args_editor(cat.BLOCKAGE).open_window("groundModel", exec_=False)
        else:
            g._select(cat.GROUND, "MultiMirror")
            w = g.open_ground_window(exec_=False)
        self.addCleanup(w.deleteLater)
        w.show()
        QtWidgets.QApplication.processEvents()
        return w

    def test_enter_in_a_field_does_not_accept_the_window(self):
        for blockage in (False, True):
            for key in KEYS:
                with self.subTest(blockage=blockage, key=key):
                    w = self.window(blockage)
                    accepted = mock.Mock()
                    w.accepted.connect(accepted)
                    edit = w.editor.control("mirror_height")
                    self.assertIs(focus(edit), edit)
                    press(edit, key)
                    accepted.assert_not_called()
                    self.assertTrue(w.isVisible())
                    combo = w.editor.control("superpositionModel")
                    self.assertIs(focus(combo), combo)
                    press(combo, key)
                    self.assertTrue(combo.view().isVisible())
                    combo.hidePopup()
                    accepted.assert_not_called()
                    w.reject()

    def test_the_window_with_the_focus_accepts_and_its_buttons_do_their_own(self):
        for blockage in (False, True):
            for key in KEYS:
                with self.subTest(blockage=blockage, key=key, focus="window"):
                    w = self.window(blockage)
                    w.setFocusPolicy(STRONG)
                    self.assertIs(focus(w), w)
                    press(w, key)
                    self.assertEqual(w.result(), ACCEPTED)
                    self.assertTrue(self.d.isVisible())  # the dialog behind is neither accepted nor calculated
                    self.compute.assert_not_called()
                for button, result in (("btn_accept", ACCEPTED), ("btn_cancel", REJECTED)):
                    with self.subTest(blockage=blockage, key=key, button=button):
                        w = self.window(blockage)
                        self.assertIs(focus(getattr(w, button)), getattr(w, button))
                        press(getattr(w, button), key)
                        self.assertEqual(w.result(), result)
                        self.assertFalse(w.isVisible())
                        self.compute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
