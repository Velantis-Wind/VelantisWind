# -*- coding: utf-8 -*-
"""Regression: all modules have window actions without losing their live QGIS state."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.hub_dialog import VelantisHubDialog  # noqa: E402
from VelantisWind.ui_core import window_controls as wc  # noqa: E402
from VelantisWind.ui_core.window_controls import (  # noqa: E402
    ModuleWindowControls, attach_dialog_window_controls, enable_native_window_controls,
)

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class ModuleWindowControlTest(unittest.TestCase):
    def make_dialog(self):
        window = QtWidgets.QDialog()
        window.setLayout(QtWidgets.QVBoxLayout())
        window.setWindowTitle("Test module")
        self.addCleanup(window.deleteLater)
        return window

    def test_energy_installs_buttons_only_once_and_preserves_existing_form(self):
        dlg = self.make_dialog()
        entry = QtWidgets.QLineEdit(dlg)
        entry.setText("Saved turbine")
        dlg.layout().addWidget(entry)
        attach_dialog_window_controls(dlg)
        attach_dialog_window_controls(dlg)
        bar = dlg.findChild(ModuleWindowControls, "velantisEnergyWindowControls")
        self.assertIsNotNone(bar)
        self.assertEqual(len(dlg.findChildren(ModuleWindowControls)), 1)
        self.assertEqual(dlg.layout().indexOf(bar), 0)
        self.assertEqual(entry.text(), "Saved turbine")
        self.assertTrue(dlg.windowFlags() & QtCore.Qt.WindowMinimizeButtonHint)
        self.assertTrue(dlg.windowFlags() & QtCore.Qt.WindowMaximizeButtonHint)
        self.assertTrue(dlg.windowFlags() & QtCore.Qt.WindowCloseButtonHint)

    def test_noise_and_shadow_controls_act_on_parent_hub_not_page(self):
        hub = self.make_dialog()
        hub.show()
        page = QtWidgets.QWidget(hub)
        hub.layout().addWidget(page)
        bar = ModuleWindowControls(page, target=hub)
        page.setLayout(QtWidgets.QVBoxLayout())
        page.layout().addWidget(bar)
        self.assertEqual(bar.btn_close.objectName(), "velantisWindowClose")
        self.assertEqual(bar.btn_minimize.objectName(), "velantisWindowMinimize")
        self.assertEqual(bar.btn_maximize.objectName(), "velantisWindowMaximize")
        with mock.patch.object(wc, "current_language", return_value="es"):
            bar.btn_maximize.click()
            self.assertTrue(hub.isMaximized())
            self.assertEqual(bar.btn_maximize.toolTip(), "Restaurar")
            bar.btn_maximize.click()
        self.assertFalse(hub.isMaximized())
        bar.btn_close.click()
        self.assertFalse(hub.isVisible())

    def test_minimize_restores_the_same_live_energy_dialog(self):
        dlg = self.make_dialog()
        state = QtWidgets.QLineEdit(dlg)
        state.setText("AEP input kept")
        dlg.layout().addWidget(state)
        attach_dialog_window_controls(dlg)
        bar = dlg.findChild(ModuleWindowControls, "velantisEnergyWindowControls")
        finished = []
        dlg.finished.connect(lambda result: finished.append(result))
        dlg.show()
        bar.btn_minimize.click()
        self.assertTrue(dlg.isMinimized())
        self.assertEqual(finished, [])
        dlg.showNormal()
        self.assertFalse(dlg.isMinimized())
        self.assertTrue(dlg.isVisible())
        self.assertEqual(state.text(), "AEP input kept")

    def test_native_buttons_for_parented_energy_dialog(self):
        parent = self.make_dialog()
        child = QtWidgets.QDialog(parent)
        self.addCleanup(child.deleteLater)
        enable_native_window_controls(child)
        # Qt.Dialog includes the Qt.Window bit: the type itself must be a window.
        self.assertEqual(child.windowType(), QtCore.Qt.Window)
        self.assertTrue(child.windowFlags() & QtCore.Qt.WindowMaximizeButtonHint)
        self.assertTrue(child.windowFlags() & QtCore.Qt.WindowCloseButtonHint)
        child.show()
        self.assertTrue(child.isWindow())
        self.assertTrue(child.isVisible())

    def test_no_layout_fallback_keeps_native_buttons(self):
        dlg = QtWidgets.QDialog()
        self.addCleanup(dlg.deleteLater)
        attach_dialog_window_controls(dlg)
        self.assertIsNone(dlg.findChild(ModuleWindowControls))
        self.assertTrue(dlg.windowFlags() & QtCore.Qt.WindowMinimizeButtonHint)

    def test_all_window_actions_are_localized_without_changing_state(self):
        dlg = self.make_dialog()
        bar = ModuleWindowControls(dlg, dlg)
        for lang, expected in (("es", ("Minimizar", "Maximizar", "Cerrar")), ("en", ("Minimize", "Maximize", "Close")),
                               ("fr", ("Réduire", "Agrandir", "Fermer")), ("de", ("Minimieren", "Maximieren", "Schließen"))):
            with self.subTest(lang=lang), mock.patch.object(wc, "current_language", return_value=lang):
                bar.refresh_labels()
                buttons = (bar.btn_minimize, bar.btn_maximize, bar.btn_close)
                self.assertEqual(tuple(b.toolTip() for b in buttons), expected)
                self.assertEqual(tuple(b.accessibleName() for b in buttons), expected)


class QtSixNamesTest(unittest.TestCase):
    """Qt 6 has the window names only under their enum classes: qt_compat gives back the ones these controls use."""

    def test_qt_compat_copies_the_window_names_from_their_enum_classes(self):
        from VelantisWind import qt_compat

        qt = QtCore.Qt
        scoped_qt = type("Qt", (), {"WindowType": qt.WindowType, "WindowState": qt.WindowState, "FocusPolicy": qt.FocusPolicy})
        scoped_event = type("QEvent", (), {"Type": QtCore.QEvent.Type})
        scoped_style = type("QStyle", (), {"StandardPixmap": QtWidgets.QStyle.StandardPixmap})
        with mock.patch.object(qt_compat.QtCore, "Qt", scoped_qt), \
                mock.patch.object(qt_compat.QtCore, "QEvent", scoped_event), \
                mock.patch.object(qt_compat.QtWidgets, "QStyle", scoped_style):
            qt_compat._patch_qtcore()
            qt_compat._patch_qtwidgets()
        for name in ("Window", "WindowType_Mask", "WindowTitleHint", "WindowSystemMenuHint", "WindowMinimizeButtonHint",
                     "WindowMaximizeButtonHint", "WindowCloseButtonHint", "WindowMinimized", "StrongFocus"):
            self.assertEqual(getattr(scoped_qt, name), getattr(qt, name), name)
        self.assertEqual(scoped_event.WindowStateChange, QtCore.QEvent.WindowStateChange)
        for name in ("SP_TitleBarMinButton", "SP_TitleBarMaxButton", "SP_TitleBarNormalButton", "SP_TitleBarCloseButton"):
            self.assertEqual(getattr(scoped_style, name), getattr(QtWidgets.QStyle, name), name)


class HubWindowControlTest(unittest.TestCase):
    """The controls on the real hub: its Noise and Shadow pages, and the Energy dialog it opens and reopens."""

    def setUp(self):
        self.energy = []

        def factory(parent):
            dlg = QtWidgets.QDialog(parent)
            dlg.setLayout(QtWidgets.QVBoxLayout())
            dlg.retranslate_ui = lambda: None  # the hub retranslates Energy when it opens it again (#37)
            self.energy.append(dlg)
            return dlg

        self.hub = VelantisHubDialog(None, energy_dialog_factory=factory)
        self.addCleanup(self.hub.deleteLater)
        self.bar = self.hub.module_window_controls

    def test_the_bar_is_on_noise_and_shadow_and_not_on_home_and_closes_the_hub(self):
        self.hub.show()
        self.assertFalse(self.bar.isVisible())
        for page in (self.hub.page_noise, self.hub.page_flicker):
            self.hub.stack.setCurrentWidget(page)
            self.assertTrue(self.bar.isVisible())
        self.hub._go_home()
        self.assertFalse(self.bar.isVisible())
        self.hub.stack.setCurrentWidget(self.hub.page_noise)
        self.bar.btn_close.click()
        self.assertFalse(self.hub.isVisible())

    def test_energy_is_reopened_with_one_bar_and_closing_it_returns_to_the_hub(self):
        self.hub.show()
        self.hub._open_energy_module()
        dlg = self.energy[0]
        self.assertTrue(dlg.isVisible())
        self.assertFalse(self.hub.isVisible())
        # «← Inicio» hides the dialog and shows the hub; entering again shows the same instance.
        dlg.hide()
        self.hub.show()
        self.hub._open_energy_module()
        self.assertEqual(len(self.energy), 1)
        self.assertTrue(dlg.isVisible())
        bars = dlg.findChildren(ModuleWindowControls)
        self.assertEqual(len(bars), 1)
        bar = bars[0]
        with mock.patch.object(wc, "current_language", return_value="es"):
            bar.btn_maximize.click()
            self.assertTrue(dlg.isMaximized())
            self.assertEqual(bar.btn_maximize.toolTip(), "Restaurar")
            bar.btn_maximize.click()
            self.assertFalse(dlg.isMaximized())
            self.assertEqual(bar.btn_maximize.toolTip(), "Maximizar")
        finished = []
        dlg.finished.connect(lambda result: finished.append(result))
        bar.btn_close.click()
        self.assertEqual(len(finished), 1)
        self.assertTrue(self.hub.isVisible())
        self.assertIsNone(self.hub._energy_dialog)


class RealEnergyDialogTest(unittest.TestCase):
    """The controls on the real Energy dialog, which «← Inicio» hides for the hub to show it again."""

    def test_home_hides_the_real_dialog_and_the_hub_opens_it_again_with_one_bar(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog

        created = []

        def factory(parent):
            created.append(AEPSetupDialog(parent=parent))
            return created[-1]

        hub = VelantisHubDialog(None, energy_dialog_factory=factory)
        self.addCleanup(hub.deleteLater)
        hub.show()
        hub._open_energy_module()
        dlg = created[0]
        self.assertEqual(len(dlg.findChildren(ModuleWindowControls)), 1)
        dlg.btn_return_hub.click()
        self.assertFalse(dlg.isVisible())
        self.assertTrue(hub.isVisible())
        hub._open_energy_module()
        self.assertEqual(len(created), 1)
        self.assertTrue(dlg.isVisible())
        self.assertEqual(len(dlg.findChildren(ModuleWindowControls)), 1)
        finished = []
        dlg.finished.connect(lambda result: finished.append(result))
        dlg.findChild(ModuleWindowControls).btn_close.click()
        self.assertEqual(len(finished), 1)
        self.assertTrue(hub.isVisible())
        self.assertIsNone(hub._energy_dialog)
        # Closed, it is deleted (WA_DeleteOnClose); the next opening creates a new dialog, with one bar.
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        with self.assertRaises(RuntimeError):
            dlg.objectName()  # the C++ dialog is gone
        hub._open_energy_module()
        self.assertEqual(len(created), 2)
        self.assertEqual(len(created[1].findChildren(ModuleWindowControls)), 1)
        created[1].close()


class InteractiveMapDockRestoresMinimizedTest(unittest.TestCase):
    """«Volver al diálogo» of the interactive map brings back an Energy dialog minimized with the new controls."""

    def test_both_buttons_bring_back_the_same_dialog_maximized_as_it_was(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        from VelantisWind.mapa_interactivo_dock import InteractiveMapDock

        window = QtWidgets.QMainWindow()
        self.addCleanup(window.deleteLater)
        dlg = AEPSetupDialog(parent=window)
        self.addCleanup(dlg.deleteLater)
        attach_dialog_window_controls(dlg)
        with mock.patch("VelantisWind.mapa_interactivo_dock.iface"):
            dock = InteractiveMapDock(dlg, parent=window)
        self.addCleanup(dock.deleteLater)
        bar = dlg.findChild(ModuleWindowControls)
        dlg.show()
        bar.btn_maximize.click()
        for button in (dock.btn_show_dialog_top, dock.btn_show_dialog):
            with self.subTest(button=button.objectName() or button.text()):
                bar.btn_minimize.click()
                self.assertTrue(dlg.isMinimized())
                button.click()
                self.assertFalse(dlg.isMinimized())
                self.assertTrue(dlg.isMaximized())
                self.assertTrue(dlg.isVisible())


    def test_closed_while_minimized_in_the_interactive_mode_it_comes_back_on_leaving_it(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog

        dlg = AEPSetupDialog(parent=None)
        self.addCleanup(dlg.deleteLater)
        attach_dialog_window_controls(dlg)
        bar = dlg.findChild(ModuleWindowControls)
        dlg.show()
        bar.btn_maximize.click()
        bar.btn_minimize.click()
        dlg._interactive_tool = object()  # the interactive mode is on: closing only hides the dialog
        dlg.close()
        self.assertFalse(dlg.isVisible())
        dlg._interactive_tool = None
        dlg._show_dialog_after_interactive_map()  # what leaving the mode does
        self.assertTrue(dlg.isVisible())
        self.assertFalse(dlg.isMinimized())
        self.assertTrue(dlg.isMaximized())


class PluginRunRestoresMinimizedTest(unittest.TestCase):
    """The plugin's toolbar action brings back a window minimized with the new controls."""

    def setUp(self):
        from VelantisWind import plugin as plugin_module

        main = QtWidgets.QMainWindow()
        self.addCleanup(main.deleteLater)
        iface = mock.Mock()
        iface.mainWindow.return_value = main
        patcher = mock.patch.object(plugin_module.deps, "ensure_dependencies", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        QtCore.QSettings().setValue("locale/userLocale", "es_ES")  # QGIS sets it; the constructor reads it
        self.plugin = plugin_module.VelantisWindPlugin(iface)
        self.energy = []

        def factory(parent):
            dlg = QtWidgets.QDialog(parent)
            dlg.setLayout(QtWidgets.QVBoxLayout())
            self.energy.append(dlg)
            return dlg

        self.plugin.first_start = False
        self.plugin.dlg = VelantisHubDialog(main, energy_dialog_factory=factory)
        self.addCleanup(self.plugin.dlg.deleteLater)

    def test_a_minimized_hub_comes_back_maximized_as_it_was(self):
        hub = self.plugin.dlg
        hub.show()
        hub.stack.setCurrentWidget(hub.page_noise)
        hub.module_window_controls.btn_maximize.click()
        hub.module_window_controls.btn_minimize.click()
        self.assertTrue(hub.isMinimized())
        self.plugin.run()
        self.assertIs(self.plugin.dlg, hub)
        self.assertFalse(hub.isMinimized())
        self.assertTrue(hub.isMaximized())
        self.assertTrue(hub.isVisible())

    def test_a_minimized_energy_dialog_comes_back_and_the_hub_stays_hidden(self):
        hub = self.plugin.dlg
        hub.show()
        hub._open_energy_module()
        dlg = self.energy[0]
        dlg.findChild(ModuleWindowControls).btn_minimize.click()
        self.assertTrue(dlg.isMinimized())
        self.plugin.run()
        self.assertEqual(len(self.energy), 1)
        self.assertIs(hub._energy_dialog, dlg)
        self.assertFalse(dlg.isMinimized())
        self.assertTrue(dlg.isVisible())
        self.assertFalse(hub.isVisible())


if __name__ == "__main__":
    unittest.main()
