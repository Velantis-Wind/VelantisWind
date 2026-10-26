# -*- coding: utf-8 -*-
"""Support for the project: the GitHub Sponsors profile of FUNDING.yml, the links of the support dialog, and the shared
«♥ Sponsors» button that opens it from the hub (home, Noise and Shadow) and from Energy."""
import os
import re
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtTest import QTest

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n, support_dialog  # noqa: E402
from VelantisWind.hub_dialog import VelantisHubDialog  # noqa: E402
from VelantisWind.ui_core.sponsor_button import SponsorButton  # noqa: E402
from VelantisWind.ui_core.window_controls import ModuleWindowControls, attach_dialog_window_controls  # noqa: E402

_CWD = os.getcwd()
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _funding_profile():
    with open(os.path.join(_ROOT, ".github", "FUNDING.yml"), encoding="utf-8") as handle:
        match = re.search(r"^github:\s*(\S+)\s*$", handle.read(), re.MULTILINE)
    return match.group(1) if match else None


class FundingLinksTest(unittest.TestCase):
    def test_funding_names_the_github_sponsors_profile(self):
        self.assertEqual(_funding_profile(), "VelantisWind")

    def test_the_dialog_links_only_to_files_of_the_repository(self):
        prefix = "https://github.com/Velantis-Wind/VelantisWind/blob/main/"
        urls = [value for name, value in vars(support_dialog).items() if name.endswith("_URL") and isinstance(value, str)]
        files = [url[len(prefix):] for url in urls if url.startswith(prefix)]
        self.assertIn("SUPPORT.md", files)
        self.assertIn("VelantisWind/SUPPORTERS.md", files)
        for name in files:
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(os.path.join(_ROOT, name)))


class SupportDialogTest(unittest.TestCase):
    def make_dialog(self, language="es"):
        with mock.patch.object(support_dialog, "current_language", return_value=language):
            dlg = support_dialog.SupportDialog()
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_the_sponsor_button_opens_the_profile_of_funding(self):
        self.assertEqual(support_dialog.SPONSOR_URL, f"https://github.com/sponsors/{_funding_profile()}")
        dlg = self.make_dialog()
        self.assertTrue(dlg.btn_sponsor.toolTip())
        opened = []
        with mock.patch.object(support_dialog.QtGui.QDesktopServices, "openUrl",
                               side_effect=lambda url: opened.append(url) or True):
            for button in (dlg.btn_sponsor, dlg.btn_support_doc, dlg.btn_project, dlg.btn_contact,
                           dlg.btn_supporters):
                button.click()
        urls = (support_dialog.SPONSOR_URL, support_dialog.SUPPORT_DOC_URL, support_dialog.GITHUB_PROJECT_URL,
                support_dialog.CONTACT_URL, support_dialog.SUPPORTERS_URL)
        self.assertEqual(opened, [QtCore.QUrl(url) for url in urls])
        self.assertFalse(dlg.findChildren(QtWidgets.QMessageBox))

    def test_the_levels_are_folded_until_asked_for(self):
        dlg = self.make_dialog()
        self.assertTrue(dlg.tiers_panel.isHidden())
        self.assertEqual(dlg.btn_toggle_tiers.text(), "Ver niveles de apoyo")
        self.assertEqual(len(dlg.tiers_panel.findChildren(QtWidgets.QFrame, "supportTierBox")), 10)
        dlg.btn_toggle_tiers.click()
        self.assertFalse(dlg.tiers_panel.isHidden())
        self.assertEqual(dlg.btn_toggle_tiers.text(), "Ocultar niveles de apoyo")
        dlg.btn_toggle_tiers.click()
        self.assertTrue(dlg.tiers_panel.isHidden())
        self.assertEqual(dlg.btn_toggle_tiers.text(), "Ver niveles de apoyo")

    def test_a_link_the_browser_does_not_open_is_shown_to_copy(self):
        dlg = self.make_dialog()
        with mock.patch.object(support_dialog.QtGui.QDesktopServices, "openUrl", return_value=False), \
                mock.patch.object(QtWidgets.QMessageBox, "exec_") as shown:
            dlg.btn_sponsor.click()
        shown.assert_called_once()
        (msg,) = dlg.findChildren(QtWidgets.QMessageBox)
        self.assertIn(support_dialog.SPONSOR_URL, msg.text())
        self.assertTrue(msg.textInteractionFlags() & QtCore.Qt.TextSelectableByMouse)

    def test_the_fallback_url_can_be_selected_and_copied_with_the_keyboard(self):
        dlg = self.make_dialog()
        with mock.patch.object(support_dialog.QtGui.QDesktopServices, "openUrl", return_value=False), \
                mock.patch.object(QtWidgets.QMessageBox, "exec_"):
            dlg.btn_sponsor.click()
        (msg,) = dlg.findChildren(QtWidgets.QMessageBox)
        self.assertTrue(msg.textInteractionFlags() & QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard)
        msg.show()
        msg.activateWindow()
        _APP.processEvents()
        ok = msg.button(QtWidgets.QMessageBox.Ok)
        ok.setFocus()
        QTest.keyClick(ok, QtCore.Qt.Key.Key_Tab)
        label = msg.focusWidget()
        self.assertIsInstance(label, QtWidgets.QLabel)
        self.assertIn(support_dialog.SPONSOR_URL, label.text())
        self.addCleanup(_APP.clipboard().setText, _APP.clipboard().text())
        _APP.clipboard().clear()
        QTest.keyClick(label, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(label, QtCore.Qt.Key.Key_C, QtCore.Qt.KeyboardModifier.ControlModifier)
        self.assertIn(support_dialog.SPONSOR_URL, _APP.clipboard().text())
        msg.close()

    def test_the_buttons_are_whole_at_the_width_of_the_dialog_in_each_language(self):
        for language in ("es", "en", "fr", "de"):
            with self.subTest(language=language):
                dlg = self.make_dialog(language)
                dlg.show()
                _APP.processEvents()
                for button in dlg.findChildren(QtWidgets.QPushButton):
                    if button.isVisible():
                        self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
                # Tab goes along the first row, then the second.
                row = [dlg.btn_sponsor, dlg.btn_support_doc, dlg.btn_project, dlg.btn_contact, dlg.btn_supporters]
                self.assertEqual([widget.nextInFocusChain() for widget in row[:-1]], row[1:])
                dlg.close()

    def test_the_new_texts_in_each_language(self):
        expected = {
            "es": ("Documentación del proyecto", "Ver niveles de apoyo", "No se ha podido abrir el enlace. Copia esta dirección:"),
            "en": ("Project documentation", "Show support levels", "The link could not be opened. Copy this address:"),
            "fr": ("Documentation du projet", "Voir les niveaux de soutien", "Le lien n’a pas pu être ouvert. Copiez cette adresse :"),
            "de": ("Projektdokumentation", "Unterstützungsstufen anzeigen",
                   "Der Link konnte nicht geöffnet werden. Kopieren Sie diese Adresse:"),
        }
        for language, (project, levels, fallback) in expected.items():
            with self.subTest(language=language):
                dlg = self.make_dialog(language)
                self.assertEqual((dlg.btn_project.text(), dlg.btn_toggle_tiers.text()), (project, levels))
                with mock.patch.object(support_dialog.QtGui.QDesktopServices, "openUrl", return_value=False), \
                        mock.patch.object(QtWidgets.QMessageBox, "exec_"):
                    dlg.btn_project.click()
                self.assertEqual(dlg.findChild(QtWidgets.QMessageBox).text(),
                                 f"{fallback}\n{support_dialog.GITHUB_PROJECT_URL}")


def _energy_dialog(test):
    dlg = QtWidgets.QDialog()
    dlg.setLayout(QtWidgets.QVBoxLayout())
    test.addCleanup(dlg.deleteLater)
    return dlg


class SponsorButtonTest(unittest.TestCase):
    def assert_keyboard_opens_support(self, window, button):
        window.show()
        window.activateWindow()
        _APP.processEvents()
        button.setFocus()
        self.assertTrue(button.hasFocus())
        self.assertFalse(button.autoDefault())
        self.assertFalse(button.isDefault())
        for key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Space):
            with self.subTest(key=key), mock.patch.object(support_dialog, "show_support_dialog") as show, \
                    mock.patch.object(window, "keyPressEvent") as parent_key:
                QTest.keyClick(button, key)
                show.assert_called_once_with(window)
                parent_key.assert_not_called()
        self.assertFalse(button.isDefault())

    def test_return_opens_support_on_home_noise_and_shadow_without_reaching_the_hub(self):
        hub = VelantisHubDialog(None)
        self.addCleanup(hub.deleteLater)
        for page in (hub.page_home, hub.page_noise, hub.page_flicker):
            with self.subTest(page=page.objectName() or type(page).__name__):
                hub.stack.setCurrentWidget(page)
                self.assert_keyboard_opens_support(hub, hub.btn_support_velantis)
        hub.close()

    def test_return_opens_support_in_the_real_energy_dialog(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog

        dlg = AEPSetupDialog(parent=None)
        self.addCleanup(dlg.deleteLater)
        attach_dialog_window_controls(dlg)
        self.assert_keyboard_opens_support(dlg, dlg.findChild(SponsorButton))
        dlg.close()

    def test_the_button_is_accessible_and_opens_the_support_dialog_on_its_window(self):
        window = _energy_dialog(self)
        button = SponsorButton(window)
        self.assertEqual(button.text(), "♥ Sponsors")
        self.assertEqual(button.accessibleName(), "Sponsors")
        self.assertTrue(button.toolTip())
        self.assertEqual(button.accessibleDescription(), button.toolTip())
        self.assertEqual(button.focusPolicy(), QtCore.Qt.StrongFocus)
        self.assertFalse(button.autoDefault())  # Enter in another field of the window does not open the dialog
        with mock.patch.object(support_dialog, "show_support_dialog") as show:
            button.click()
        show.assert_called_once_with(window)

    def test_a_dialog_that_fails_is_reported(self):
        window = _energy_dialog(self)
        button = SponsorButton(window)
        with mock.patch.object(support_dialog, "show_support_dialog", side_effect=RuntimeError("boom")), \
                mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            button.click()
        self.assertEqual(warning.call_args.args[0], window)
        self.assertEqual(warning.call_args.args[2], "boom")

    def test_the_hub_has_one_button_at_the_top_right_on_its_three_pages_and_no_footer(self):
        hub = VelantisHubDialog(None)
        self.addCleanup(hub.deleteLater)
        hub.show()
        hub.activateWindow()
        _APP.processEvents()
        (button,) = hub.findChildren(SponsorButton)
        self.assertIs(button, hub.btn_support_velantis)
        self.assertIsNotNone(hub.focusWidget())
        self.assertIsNot(hub.focusWidget(), button)  # the hub does not open with the focus on it
        top_bar = hub.layout().itemAt(0).layout()
        self.assertEqual([top_bar.itemAt(i).widget() for i in range(1, top_bar.count())],
                         [button, hub.module_window_controls])
        self.assertIsNone(hub.findChild(QtWidgets.QPushButton, "supportVelantisButton"))
        for page in (hub.page_home, hub.page_noise, hub.page_flicker):
            with self.subTest(page=page.objectName() or type(page).__name__):
                hub.stack.setCurrentWidget(page)
                self.assertTrue(button.isVisible())
                self.assertEqual(button.text(), "♥ Sponsors")
        with mock.patch.object(support_dialog, "show_support_dialog") as show:
            button.click()
        show.assert_called_once_with(hub)

    def test_energy_has_one_button_before_its_window_controls_also_when_opened_again(self):
        dlg = _energy_dialog(self)
        attach_dialog_window_controls(dlg)
        attach_dialog_window_controls(dlg)
        bar = dlg.findChild(ModuleWindowControls, "velantisEnergyWindowControls")
        (button,) = dlg.findChildren(SponsorButton)
        self.assertIs(bar.sponsor_button, button)
        self.assertEqual(bar.layout().indexOf(button), 0)
        with mock.patch.object(support_dialog, "show_support_dialog") as show:
            button.click()
        show.assert_called_once_with(dlg)

    def test_window_controls_of_the_hub_pages_have_no_button_of_their_own(self):
        hub = _energy_dialog(self)
        self.assertIsNone(ModuleWindowControls(hub, target=hub).sponsor_button)


class SponsorButtonTranslationTest(unittest.TestCase):
    """The button follows language changes independently of the real translation tables."""

    def setUp(self):
        self.addCleanup(i18n.set_language, i18n.current_language())
        i18n.set_language("es")

    def test_the_button_follows_the_language_in_the_hub_and_in_energy(self):
        expected = {
            "en": ("♥ Sponsors", "Optionally support the development, maintenance and validation of VelantisWind."),
            "fr": ("♥ Sponsors", "Soutenez librement le développement, la maintenance et la validation de VelantisWind."),
            "de": ("♥ Sponsoren", "Unterstützen Sie freiwillig die Entwicklung, Wartung und Validierung von VelantisWind."),
            "es": ("♥ Sponsors", "Apoya voluntariamente el desarrollo, el mantenimiento y la validación de VelantisWind."),
        }
        translations = {language: dict(zip(expected["es"], labels)) for language, labels in expected.items()}
        translator = mock.patch(
            "VelantisWind.ui_core.sponsor_button._tr",
            side_effect=lambda text: translations[i18n.current_language()].get(text, text),
        )
        translator.start()
        self.addCleanup(translator.stop)
        hub = VelantisHubDialog(None)
        self.addCleanup(hub.deleteLater)
        energy = _energy_dialog(self)
        attach_dialog_window_controls(energy)
        for language, (text, tooltip) in expected.items():
            with self.subTest(language=language):
                i18n.set_language(language)
                hub._apply_home_texts()
                attach_dialog_window_controls(energy)  # what the hub does when it opens Energy again
                for button in (hub.btn_support_velantis, energy.findChild(SponsorButton)):
                    self.assertEqual((button.text(), button.toolTip()), (text, tooltip))
                    self.assertEqual(button.accessibleName(), text.replace("♥", "").strip())


if __name__ == "__main__":
    unittest.main()
