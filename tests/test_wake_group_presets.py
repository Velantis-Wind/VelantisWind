# -*- coding: utf-8 -*-
"""The predefined models in the «Modelo de estela» group, in the dialog and in the interactive map's mirror (plan of the
predefined models, M3)."""
import json
import os
import tempfile
import types
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core.wake_setup import api  # noqa: E402
from VelantisWind.ag_core.wake_setup import catalog as cat  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import presets as ps  # noqa: E402
from VelantisWind.ag_core.wake_setup import validation as val  # noqa: E402
from VelantisWind.ui_core import wake_group as wg  # noqa: E402
from VelantisWind.ui_core.wake_controls import ParamEditor, SubordinateEditor  # noqa: E402

_CWD = os.getcwd()
COMPONENTS = (cat.ENGINE, cat.DEFICIT, cat.SUPERPOSITION, cat.TURBULENCE)
MISSING = "VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules"


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class _Case(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".ini", dir=_SETTINGS.name)
        os.close(fd)
        self.settings = QtCore.QSettings(path, QtCore.QSettings.IniFormat)

    def group(self):
        g = wg.WakeModelGroup(settings=self.settings)
        self.addCleanup(g.deleteLater)
        return g

    def choose_preset(self, g, id_):
        g.combo_preset.setCurrentIndex(g.combo_preset.findData(id_))

    def keys(self):
        return {k: self.settings.value(k) for k in self.settings.allKeys()}


class ModeTest(_Case):
    def test_a_new_installation_opens_with_noj(self):
        g = self.group()
        self.assertEqual((g.mode(), g.combo_preset.currentData()), (wg.PREDEFINED, "NOJ"))
        self.assertTrue(g.btn_mode[wg.PREDEFINED].isChecked())
        self.assertEqual(g.config(), ps.config("NOJ"))
        self.assertEqual(g.provenance(), ps.provenance("NOJ"))
        self.assertEqual(self.keys(), {})  # opening writes nothing

    def test_with_choices_of_the_manual_mode_saved_it_opens_with_them(self):
        self.settings.setValue(wg.SETTINGS_PREFIX + cat.DEFICIT, "NiayifarGaussianDeficit")
        g = self.group()
        self.assertEqual(g.mode(), wg.MANUAL)
        self.assertEqual(g.config().deficit.name, "NiayifarGaussianDeficit")
        self.assertIsNone(g.provenance())
        self.assertEqual(set(self.keys()), {wg.SETTINGS_PREFIX + cat.DEFICIT})
        # The mode chosen is remembered over that.
        g.set_mode(wg.PREDEFINED)
        self.assertEqual(self.group().mode(), wg.PREDEFINED)

    def test_the_model_is_remembered_and_a_stale_one_is_said(self):
        g = self.group()
        self.choose_preset(g, "ZongGaussian")
        self.assertEqual(self.group().combo_preset.currentData(), "ZongGaussian")
        self.settings.setValue(wg.PRESET_KEY, "Fuga")
        g = self.group()
        self.assertEqual(g.combo_preset.currentData(), "NOJ")
        self.assertIn("«Fuga» ya no es una opción", g.preset_note.text())

    def test_changing_the_mode_keeps_the_other_and_writes_no_manual_choice(self):
        g = self.group()
        self.choose_preset(g, "SuperGaussian")
        self.assertEqual(set(self.keys()), {wg.PRESET_KEY})
        g.set_mode(wg.MANUAL)
        self.assertEqual(g.config(), cfg.default_config())  # its own, untouched by the model shown
        self.assertEqual(set(self.keys()), {wg.PRESET_KEY, wg.MODE_KEY})
        g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("NOJDeficit"))
        g.set_mode(wg.PREDEFINED)
        self.assertEqual(g.config(), ps.config("SuperGaussian"))
        g.set_mode(wg.MANUAL)
        self.assertEqual(g.config().deficit.name, "NOJDeficit")
        self.assertFalse([k for k in self.keys() if k.startswith(wg.SETTINGS_PREFIX) and k != wg.SETTINGS_PREFIX +
                          cat.DEFICIT])

    def test_the_manual_mode_keeps_its_own_conflicts_when_the_group_opens_with_a_model(self):
        # The adversarial round on the branch: opened with the predefined models, the conflicts and notes of the manual
        # mode were calculated with the model, and the manual mode was shown without its own.
        self.settings.setValue(wg.MODE_KEY, wg.MANUAL)
        g = self.group()
        g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("NiayifarGaussianDeficit"))
        self.assertEqual([i.code for i in g.issues()], ["R2"])  # it uses the effective TI and has no turbulence
        expected = g.conflict[cat.TURBULENCE].text()
        g.set_mode(wg.PREDEFINED)
        self.choose_preset(g, "NOJ")
        again = self.group()
        self.assertEqual(again.mode(), wg.PREDEFINED)
        self.assertEqual(again.issues(), [])
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        mirror = wg.WakeGroupMirror(again, QtWidgets.QFormLayout(holder))
        again.set_mode(wg.MANUAL)
        self.assertEqual(again.config().deficit.name, "NiayifarGaussianDeficit")
        self.assertEqual([i.code for i in again.issues()], ["R2"])
        self.assertEqual(again.conflict[cat.TURBULENCE].text(), expected)
        self.assertEqual(mirror.notes[cat.TURBULENCE].text(), expected)
        # And the windows of the manual mode say what the manual mode has.
        self.assertIsNotNone(again._provisional(cat.ENGINE, again.config().engine))

    def test_a_saved_model_whose_class_this_pywake_does_not_have(self):
        # The adversarial round on the branch (r2): the group was not built, not even in the manual mode.
        from VelantisWind.ag_core.wake_setup import catalog as cat_
        real = cat_.resolve_class

        def missing(e):
            if e.name == "ZongGaussianDeficit":
                raise cat_.ClassUnavailable("La instalación de PyWake no tiene la clase ZongGaussianDeficit.")
            return real(e)
        self.settings.setValue(wg.MODE_KEY, wg.MANUAL)
        self.settings.setValue(wg.PRESET_KEY, "ZongGaussian")
        with mock.patch.object(cat_, "resolve_class", side_effect=missing):
            g = self.group()
            self.assertEqual((g.mode(), g.config(), g.issues()), (wg.MANUAL, cfg.default_config(), []))
            g.set_mode(wg.PREDEFINED)
            self.assertEqual(g.config(), ps.config("ZongGaussian"))
            self.assertEqual([(i.code, i.origin, i.resolution) for i in g.issues()],
                             [("R14", val.ENVIRONMENT, wg.PRESET_RESOLUTION)])
            self.assertIn("ZongGaussianDeficit", g.preset_note.text())
            self.assertEqual(g.preset_combo, {})  # no controls of a class it does not have
            self.choose_preset(g, "NOJ")  # another model, as the resolution says
            self.assertEqual((g.issues(), g.config()), ([], ps.config("NOJ")))

    def test_a_saved_model_with_a_nested_class_this_pywake_does_not_have(self):
        # The adversarial round on the branch (r3): a nested class (the SqrMaxSum of the CrespoHernandez of
        # NiayifarGaussian, ZongGaussian and SuperGaussian) was imported when reading the model, before the validation.
        from VelantisWind.ag_core.wake_setup import subordinates as sub_
        real = sub_.resolve_name

        def missing(name):
            if name == "SqrMaxSum":
                raise AttributeError("module 'py_wake.superposition_models' has no attribute 'SqrMaxSum'")
            return real(name)
        self.settings.setValue(wg.MODE_KEY, wg.MANUAL)
        self.settings.setValue(wg.PRESET_KEY, "NiayifarGaussian")
        with mock.patch.object(sub_, "resolve_name", side_effect=missing):
            g = self.group()
            self.assertEqual((g.mode(), g.config(), g.issues()), (wg.MANUAL, cfg.default_config(), []))
            g.set_mode(wg.PREDEFINED)
            self.assertEqual(g.config(), ps.config("NiayifarGaussian"))
            self.assertEqual([(i.code, i.origin, i.resolution) for i in g.issues()],
                             [("R14", val.ENVIRONMENT, wg.PRESET_RESOLUTION)])
            self.assertIn("SqrMaxSum", g.preset_note.text())
            self.assertEqual(g.preset_combo, {})
            self.choose_preset(g, "NOJ")  # a model without it
            self.assertEqual(g.issues(), [])
        # An unknown name is still refused by the contract's reading, as before; None is not a class.
        self.assertIsNone(cfg._expected_params(None, "NoSuchClass"))
        self.assertFalse(sub_.known_name(None))
        self.assertTrue(sub_.known_name("SqrMaxSum") and sub_.known_name("CrespoHernandez"))

    def test_the_boxes_of_each_mode(self):
        g = self.group()
        g.show()
        self.addCleanup(g.hide)
        self.assertTrue(g.preset_box.isVisible())
        self.assertFalse(g.manual_box.isVisible())
        g.btn_mode[wg.MANUAL].click()
        self.assertEqual(g.mode(), wg.MANUAL)
        self.assertFalse(g.preset_box.isVisible())
        self.assertTrue(g.manual_box.isVisible())


class ViewTest(_Case):
    def test_the_titles_in_their_order_and_the_page(self):
        g = self.group()
        self.assertEqual([g.combo_preset.itemData(i) for i in range(g.combo_preset.count())], list(ps.ids()))
        self.assertEqual([g.combo_preset.itemText(i) for i in range(g.combo_preset.count())], list(ps.ids()))
        self.assertIn(f'href="{ps.PAGE}"', g.lbl_presets_page.text())
        self.assertIn("Modelos de parque con la configuración de PyWake:", g.lbl_presets_page.text())
        self.assertTrue(g.lbl_presets_page.openExternalLinks())
        self.assertEqual(g.lbl_presets_footer.text(), "Para cambiar valores, usa el «Modo manual».")

    def test_every_argument_of_each_model_with_its_value(self):
        g = self.group()
        for id_ in ps.ids():
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                c = ps.config(id_)
                for position in COMPONENTS + (cat.ROTOR, cat.GROUND):
                    comp = c.component(position)
                    self.assertEqual(g.preset_combo[position].currentData(), wg._option(position, comp))
                self.assertEqual(g.preset_editors[cat.DEFICIT].values(), dict(c.deficit.params))
                for position in (cat.SUPERPOSITION, cat.TURBULENCE, cat.ROTOR):
                    comp = c.component(position)
                    if comp is not None and comp.params:
                        self.assertEqual(g.preset_editors[position].value(), comp)  # nested ones included
        self.choose_preset(g, "NiayifarGaussian")
        nested = g.preset_editors[cat.TURBULENCE]
        self.assertEqual(nested.control("rotorAvgModel").currentData(), "AreaOverlapAvgModel")
        self.assertEqual(nested.control("addedTurbulenceSuperpositionModel").currentData(), "SqrMaxSum")
        self.assertEqual([e.text() for e in nested.control("c")[1]], ["0.73", "0.8325", "0.0325", "-0.32"])

    def test_nothing_can_be_changed_and_everything_can_be_read(self):
        g = self.group()
        for id_ in ps.ids():
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                for position, combo in g.preset_combo.items():
                    self.assertFalse(combo.isEnabled())
                    self.assertEqual(combo.count(), 1)
                    self.assertTrue(combo.toolTip())
                for editor in g.preset_editors.values():
                    for w in editor.findChildren(QtWidgets.QLineEdit):
                        self.assertTrue(w.isReadOnly())
                    for w in editor.findChildren(QtWidgets.QComboBox):
                        self.assertFalse(w.isEnabled())
                    for w in editor.findChildren(QtWidgets.QAbstractSpinBox):
                        self.assertTrue(w.isReadOnly())
                labels = [w for e in g.preset_editors.values() for w in e.findChildren(QtWidgets.QLabel)]
                self.assertTrue(all(w.toolTip() for w in labels))
                # The sections unfold; there is nothing to reset.
                for section in g.preset_sections.values():
                    section.setExpanded(True)
                    self.assertTrue(section.isExpanded())
                    section.setExpanded(False)
                self.assertFalse([b for b in g.preset_box.findChildren(QtWidgets.QPushButton)
                                  if b.text() == "Restablecer"])
                self.assertEqual(g.config(), ps.config(id_))

    def test_nothing_of_the_previous_model_is_left(self):
        def widgets(g):
            return sorted((type(w).__name__, w.text() if hasattr(w, "text") else w.currentText())
                          for w in g.preset_details.findChildren((QtWidgets.QLabel, QtWidgets.QComboBox,
                                                                  QtWidgets.QAbstractButton)))
        g = self.group()
        fresh = widgets(g)
        for id_ in ps.ids()[::-1] + ("NOJ",):
            self.choose_preset(g, id_)
        self.assertEqual(widgets(g), fresh)
        g.show()
        self.addCleanup(g.hide)
        _APP.processEvents()
        shown = [w for w in g.preset_details.findChildren(QtWidgets.QLabel) if w.isVisible()]
        self.assertEqual(sum(w.text() == "Turbulencia añadida" for w in shown), 1)

    def test_the_selectors_start_at_the_same_x_as_in_the_manual_mode(self):
        # QGIS tests of the predefined models: «Modelo» and the selectors of the first level, aligned; in the deficit's
        # section, the rotor and the ground with its arguments.
        g = self.group()
        g.show()
        self.addCleanup(g.hide)
        for id_ in ps.ids():
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                g.preset_sections[cat.DEFICIT].setExpanded(True)
                QtWidgets.QApplication.processEvents()

                def x(w):
                    return w.mapTo(g, QtCore.QPoint(0, 0)).x()
                self.assertEqual(len({x(g.combo_preset)} | {x(g.preset_combo[p]) for p in COMPONENTS}), 1)
                form = g.preset_editors[cat.DEFICIT].layout()
                fields = [form.itemAt(i, QtWidgets.QFormLayout.FieldRole).widget() for i in range(form.rowCount())]
                self.assertEqual(len({x(w) for w in fields} | {x(g.preset_combo[p]) for p in (cat.ROTOR, cat.GROUND)}), 1)

    def test_the_values_are_read_as_text(self):
        # The user's tests in QGIS: greyed out, the values looked blocked; read-only, they are read as text in a frame,
        # without the arrow of a menu, everywhere in the view and in its windows («Modelo» is a selector: not).
        from VelantisWind.ui_core.wake_controls import READ_ONLY_STYLE
        g = self.group()
        for id_ in ("NiayifarGaussian", "TurbOPark"):
            self.choose_preset(g, id_)
            self.assertEqual(g._preset_content.styleSheet(), READ_ONLY_STYLE)
            self.assertTrue(all(c.window() is g.window() and c.parentWidget() is not None
                                for c in g.preset_combo.values()))
            self.assertTrue(all(g._preset_content.isAncestorOf(c) for c in g.preset_combo.values()))
        self.assertFalse(g.preset_box.styleSheet() or g.combo_preset.styleSheet())
        for position in (cat.ENGINE, cat.GROUND):
            window = g.open_preset_window(position, exec_=False)
            self.addCleanup(window.deleteLater)
            self.assertEqual(window.styleSheet(), READ_ONLY_STYLE)
            # Shown and styled again, «Aceptar» and «Restablecer» stay out of its box and hidden.
            window.show()
            window.setStyleSheet("")
            window.setStyleSheet(READ_ONLY_STYLE)
            QtWidgets.QApplication.processEvents()
            box = window.btn_cancel.parentWidget()
            for button in (window.btn_accept, window.btn_reset):
                self.assertFalse(button.isVisible())
                self.assertNotIn(button, box.buttons())
            window.reject()

    def test_the_mode_chosen_is_highlighted(self):
        g = self.group()
        self.assertTrue(all("QPushButton:checked" in b.styleSheet() for b in g.btn_mode.values()))

    def test_the_window_of_the_engine_is_read_and_closed(self):
        g = self.group()
        self.choose_preset(g, "ZongGaussian")
        before = self.keys()
        window = g.open_preset_window(cat.ENGINE, exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertFalse(window.btn_accept.isVisibleTo(window))
        self.assertFalse(window.btn_reset.isVisibleTo(window))
        self.assertEqual(window.btn_cancel.text(), "Cerrar")
        self.assertIn("externalWindFarms", window.lbl_info.text())  # as in the manual mode
        window.reject()
        self.assertEqual((g.config(), self.keys()), (ps.config("ZongGaussian"), before))

    def test_the_window_of_the_ground_of_turbopark(self):
        g = self.group()
        self.choose_preset(g, "TurbOPark")
        self.assertEqual(g.preset_combo[cat.GROUND].currentData(), "Mirror")
        window = g.open_preset_window(cat.GROUND, exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertEqual(window.value(), ps.config("TurbOPark").ground)  # Mirror(superpositionModel=SquaredSum())
        self.assertFalse(window.editor.control("superpositionModel").isEnabled())
        self.assertFalse(window.btn_accept.isVisibleTo(window))
        self.assertEqual(window.btn_cancel.text(), "Cerrar")
        window.reject()
        self.assertEqual(g.config(), ps.config("TurbOPark"))

    def test_a_read_only_window_of_a_ground(self):
        # No model of the first step has a ground model with arguments: the window, with one (TurbOPark's).
        from VelantisWind.ui_core.wake_controls import ComponentWindow
        ground = cfg.Component("Mirror", {"superpositionModel": cfg.Component("SquaredSum", {})})
        window = ComponentWindow(ground, read_only=True, inherited="SquaredSum")
        self.addCleanup(window.deleteLater)
        self.assertFalse(window.editor.control("superpositionModel").isEnabled())
        self.assertFalse(window.btn_accept.isVisibleTo(window))
        self.assertEqual(window.value(), ground)

    def test_the_notes_of_the_models(self):
        g = self.group()
        expected = {"BastankhahGaussian": "k = 0,0324555", "IEA37SimpleBastankhahGaussian": "obsoleto",
                    "SuperGaussian": "Usa CrespoHernandez"}
        for id_ in ps.ids():
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                text = g.preset_note.text()
                self.assertEqual(bool(text), id_ in expected)
                if id_ in expected:
                    self.assertIn(expected[id_], text)
                    self.assertIn("#b9770e", text)  # a note, in orange
        self.choose_preset(g, "SuperGaussian")
        self.assertIn(f'href="{ps.preset("SuperGaussian").url}"', g.preset_note.text())
        # Neither the PyWake class nor the version in what the view shows.
        shown = [w.text() for w in g.preset_box.findChildren(QtWidgets.QLabel)]
        self.assertFalse([t for t in shown if "Blondel_Cathelain_2020" in t])

    def test_a_refusal_proposes_only_what_a_model_can_do(self):
        g = self.group()
        issue = val.Issue("R3", cat.DEFICIT, val.PYWAKE_CALC, "Un rechazo.", "Marca use_effective_ws.")
        with mock.patch.object(wg._val, "validate", return_value=[issue]):
            self.choose_preset(g, "BastankhahGaussian")
        self.assertEqual([i.resolution for i in g.issues()], [wg.PRESET_RESOLUTION])
        self.assertIn(wg.PRESET_RESOLUTION, g.preset_conflict[cat.DEFICIT].text())
        self.assertNotIn("Marca use_effective_ws", g.preset_conflict[cat.DEFICIT].text())

    def test_the_view_says_nothing_of_a_saved_decision(self):
        # The menu stays clean (the user, after seeing it in QGIS): the decision is said by the question and the result.
        g = self.group()
        wg.save_consent(self.settings, "NiayifarGaussian", ["h5py"])
        with mock.patch(MISSING, return_value=["h5py"]):
            self.choose_preset(g, "NiayifarGaussian")
        self.assertNotIn("CGIRotorAvg(7)", g.preset_note.text())
        self.assertFalse(hasattr(g, "btn_ask_again"))
        self.assertEqual(g.config(), ps.config("NiayifarGaussian"))  # the view, the model itself

    def test_the_saved_decision_this_version_reads(self):
        # One this version cannot read, or next to another key it does not know, authorizes nothing; saving a new one
        # removes every earlier one of the model.
        future = "wake_adaptation_consent/gaussian_overlap_cgi7/v2/NiayifarGaussian"
        wg.save_consent(self.settings, "NiayifarGaussian", ["h5py"])
        self.assertIsNotNone(wg.saved_consent(self.settings, "NiayifarGaussian"))
        self.settings.setValue(future, "{}")
        self.assertIsNone(wg.saved_consent(self.settings, "NiayifarGaussian"))
        wg.save_consent(self.settings, "NiayifarGaussian", ["h5py"])
        self.assertEqual([k for k in self.keys() if k.startswith(wg.CONSENT_PREFIX)],
                         [wg.CONSENT_KEY.format(preset="NiayifarGaussian")])
        wg.clear_consent(self.settings, "NiayifarGaussian")
        self.assertEqual([k for k in self.keys() if k.startswith(wg.CONSENT_PREFIX)], [])

    def test_without_the_libraries_the_view_says_nothing_of_it(self):
        # The dialog asks when calculating (decision 17); the view of the model says nothing of the missing libraries.
        g = self.group()
        with mock.patch(MISSING, return_value=["h5py"]):
            for preset in ("NiayifarGaussian", "TurbOPark"):
                self.choose_preset(g, preset)
                shown = " ".join(g.preset_conflict[p].text() for p in COMPONENTS) + g.preset_note.text()
                self.assertNotIn("h5py", shown)
                self.assertNotIn("GaussianOverlapAvgModel necesita", shown)



class DialogTest(_Case):
    def setUp(self):
        from qgis.core import QgsProject
        QgsProject.instance().clear()
        self.settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        for key in self.settings.allKeys():
            self.settings.remove(key)
        self.addCleanup(lambda: [self.settings.remove(k) for k in self.settings.allKeys()])

    def dialog(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        d = AEPSetupDialog()
        self.addCleanup(d.deleteLater)
        return d

    def test_the_model_and_its_provenance_reach_the_calculation(self):
        d = self.dialog()
        self.choose_preset(d.wake_group, "ZongGaussian")
        with mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            physics = d._wake_physics_for_run()
        warning.assert_not_called()
        self.assertEqual(api.resolve_request(physics)[0], ps.config("ZongGaussian"))
        self.assertEqual(d._wake_provenance_for_run(), ps.provenance("ZongGaussian"))
        d.wake_group.set_mode(wg.MANUAL)
        d._wake_physics_for_run()
        self.assertIsNone(d._wake_provenance_for_run())

    def launch(self, d, missing, choice="Continuar", asked=None, **kwargs):
        """``_wake_physics_for_run`` with ``missing`` libraries, answering ``choice`` (the texts asked, in ``asked``)."""
        asked = [] if asked is None else asked
        with mock.patch(MISSING, return_value=list(missing)), \
                mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda box: asked.append(box.text())), \
                mock.patch.object(QtWidgets.QMessageBox, "clickedButton",
                                  lambda box: next(b for b in box.buttons() if b.text() == choice)), \
                mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            physics = d._wake_physics_for_run(**kwargs)
        warning.assert_not_called()
        return physics

    def test_without_the_libraries_of_gaussian_overlap_the_question(self):
        # Decision 17: a predefined model is asked as the manual mode, and with «Continuar» it is adapted, recorded,
        # with its provenance; with one turbine (PyWake does not read the table) nothing is asked.
        for preset in ("NiayifarGaussian", "TurbOPark"):  # the two models with GaussianOverlapAvgModel
            with self.subTest(preset=preset):
                self.without_the_libraries(preset)

    def without_the_libraries(self, preset):
        d = self.dialog()
        self.choose_preset(d.wake_group, preset)
        for missing in (["h5py"], ["h5netcdf"], ["h5py", "h5netcdf"]):
            for what, n, asks in (("AEP", 1, False), ("AEP", 2, True), ("ráster", 1, True)):
                for choice in ("Continuar", "Cancelar"):
                    asked = []
                    with self.subTest(missing=missing, what=what, turbines=n, choice=choice):
                        physics = self.launch(d, missing, choice, asked, what=what, n_turbines=n)
                        self.assertEqual(bool(asked), asks)
                        if not asks:
                            self.assertEqual(api.resolve_request(physics)[0], ps.config(preset))
                            self.assertEqual(d._wake_provenance_for_run(), ps.provenance(preset))
                        elif choice == "Cancelar":
                            self.assertIsNone(physics)
                            self.assertIsNone(d._wake_provenance_for_run())
                        else:
                            self.assertIn(" ".join(missing).replace(" ", " y "), asked[0])
                            self.assertIn(f"configuración adaptada a partir de {preset}", asked[0])
                            config = api.resolve_request(physics)[0]
                            self.assertEqual(config, api.gaussian_overlap_adaptation(ps.config(preset), missing,
                                                                                     api.ACCEPTED_NOW))
                            self.assertEqual(config.rotor, cfg.Component("CGIRotorAvg", {"n": 7}))
                            self.assertEqual(api.user_selection(config).rotor.name, "GaussianOverlapAvgModel")
                            provenance = d._wake_provenance_for_run()
                            self.assertEqual(provenance, ps.provenance(preset))
                            self.assertEqual(ps.checked_provenance(config, provenance), provenance)

    def test_the_answer_is_for_one_model_and_one_launch(self):
        # Decision 20: the second reading of a launch keeps the answer only for the same mode and model.
        d = self.dialog()
        g = d.wake_group
        asked = []
        self.choose_preset(g, "NiayifarGaussian")
        self.launch(d, ["h5py"], asked=asked, n_turbines=2)
        self.launch(d, ["h5py"], asked=asked, ask=False, n_turbines=3)
        self.assertEqual(len(asked), 1)
        self.choose_preset(g, "TurbOPark")
        physics = self.launch(d, ["h5py"], asked=asked, ask=False, n_turbines=2)
        self.assertEqual(len(asked), 2)
        self.assertTrue(ps.adapted("TurbOPark", api.resolve_request(physics)[0]))
        g.set_mode(wg.MANUAL)
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        self.launch(d, ["h5py"], asked=asked, ask=False, n_turbines=2)
        self.assertEqual(len(asked), 3)
        self.assertNotIn("configuración adaptada a partir de", asked[2])  # the manual mode, as before
        self.assertIsNone(d._wake_provenance_for_run())
        # An answer of the manual mode is not one of a model.
        g.set_mode(wg.PREDEFINED)
        self.launch(d, ["h5py"], asked=asked, ask=False, n_turbines=2)
        self.assertEqual(len(asked), 4)

    def answer(self, d, missing, check, asked=None, boxes=None, **kwargs):
        """«Continuar» with the box of the decision ``check``ed (when there is one); the texts asked and whether each
        box started unchecked, in ``asked`` and ``boxes``."""
        asked = [] if asked is None else asked
        boxes = [] if boxes is None else boxes

        def exec_(box):
            asked.append(box.text() + " " + box.informativeText())
            if box.checkBox() is not None:
                boxes.append((box.checkBox().text(), box.checkBox().isChecked()))
                box.checkBox().setChecked(check)
        with mock.patch(MISSING, return_value=list(missing)), mock.patch.object(QtWidgets.QMessageBox, "exec_", exec_), \
                mock.patch.object(QtWidgets.QMessageBox, "clickedButton",
                                  lambda box: next(b for b in box.buttons() if b.text() == "Continuar")):
            physics = d._wake_physics_for_run(**kwargs)
        return api.resolve_request(physics)[0]

    def test_the_decision_remembered_for_a_model(self):
        # Decision 21: «Continuar» with the box checked saves it for that model; while it applies (the same revision and
        # libraries, any order), the AEP and the raster are adapted without asking, recorded as such.
        d = self.dialog()
        g = d.wake_group
        self.choose_preset(g, "NiayifarGaussian")
        others = dict(self.keys())
        asked, boxes = [], []
        config = self.answer(d, ["h5py"], True, asked, boxes, n_turbines=2)
        self.assertEqual(boxes, [("Recordar esta decisión para NiayifarGaussian en futuros AEP y rásteres", False)])
        self.assertIn("se usará CGIRotorAvg(7) sin preguntar", asked[0])
        self.assertEqual(config.adaptations[0]["acceptance"], "continue")
        self.assertEqual(json.loads(self.settings.value(wg.CONSENT_KEY.format(preset="NiayifarGaussian"))),
                         {"version": 1, "revision": ps.preset("NiayifarGaussian").revision, "modules": ["h5py"]})
        self.assertEqual({k: v for k, v in self.keys().items() if not k.startswith("wake_adaptation_consent/")}, others)
        for kwargs in ({"n_turbines": 2}, {"what": "ráster", "n_turbines": 1}, {"ask": False, "n_turbines": 3}):
            with self.subTest(**kwargs):
                config = self.answer(d, ["h5py"], False, asked, **kwargs)
                self.assertEqual(len(asked), 1)
                self.assertEqual(config.adaptations[0]["acceptance"], "saved_preference")
                self.assertTrue(ps.adapted("NiayifarGaussian", config))
        self.assertEqual(self.answer(self.dialog(), ["h5py"], False, asked, n_turbines=2).adaptations[0]["acceptance"],
                         "saved_preference")  # kept between sessions
        # Inert: one turbine, or the libraries available, calculate the model itself.
        self.assertEqual(self.answer(d, ["h5py"], False, asked, n_turbines=1), ps.config("NiayifarGaussian"))
        self.assertEqual(self.answer(d, [], False, asked, n_turbines=2), ps.config("NiayifarGaussian"))
        self.assertEqual(len(asked), 1)
        # Another model has its own; the manual mode never uses them.
        self.choose_preset(g, "TurbOPark")
        self.answer(d, ["h5py"], False, asked, n_turbines=2)
        self.assertEqual(len(asked), 2)
        g.set_mode(wg.MANUAL)
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        boxes.clear()
        config = self.answer(d, ["h5py"], True, asked, boxes, n_turbines=2)
        self.assertEqual((len(asked), boxes), (3, []))
        self.assertNotIn("acceptance", config.adaptations[0])  # the manual mode records as before
        # Other libraries missing: asked again; «Continuar» without the box forgets the decision.
        g.set_mode(wg.PREDEFINED)
        self.choose_preset(g, "NiayifarGaussian")
        self.answer(d, ["h5py", "h5netcdf"], False, asked, n_turbines=2)
        self.assertEqual(len(asked), 4)
        self.assertIsNone(wg.saved_consent(self.settings, "NiayifarGaussian"))

    def test_a_decision_that_does_not_apply(self):
        d = self.dialog()
        self.choose_preset(d.wake_group, "NiayifarGaussian")
        key = wg.CONSENT_KEY.format(preset="NiayifarGaussian")
        revision = ps.preset("NiayifarGaussian").revision
        wg.save_consent(self.settings, "NiayifarGaussian", ["h5netcdf", "h5py"])  # the same libraries, another order
        asked = []
        self.answer(d, ["h5py", "h5netcdf"], False, asked, n_turbines=2)
        self.assertEqual(asked, [])
        good = {"version": 1, "revision": revision, "modules": ["h5py"]}
        for value in ["x", json.dumps(["h5py"])] + [json.dumps(dict(good, **change)) for change in (
                {"version": 2}, {"version": True}, {"revision": revision + 1}, {"revision": True}, {"modules": []},
                {"modules": ["numpy"]}, {"modules": {"h5py": 1}}, {"modules": ["h5py", "h5py"]}, {"modules": [{}]},
                {"other": 1})]:
            with self.subTest(value=value):
                self.settings.setValue(key, value)
                asked.clear()
                self.answer(d, ["h5py"], True, asked, n_turbines=2)
                self.assertEqual(len(asked), 1)
        # «Cancelar» changes nothing saved.
        self.settings.setValue(key, "x")
        with mock.patch(MISSING, return_value=["h5py"]), mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda b: None), \
                mock.patch.object(QtWidgets.QMessageBox, "clickedButton", lambda box: None):
            self.assertIsNone(d._wake_physics_for_run(n_turbines=2))
        self.assertEqual(self.settings.value(key), "x")

    def test_a_decision_forgotten_between_the_two_readings(self):
        d = self.dialog()
        self.choose_preset(d.wake_group, "TurbOPark")
        wg.save_consent(self.settings, "TurbOPark", ["h5py"])
        asked = []
        self.assertEqual(self.answer(d, ["h5py"], False, asked, n_turbines=2).adaptations[0]["acceptance"],
                         "saved_preference")
        wg.clear_consent(self.settings, "TurbOPark")
        self.answer(d, ["h5py"], False, asked, ask=False, n_turbines=2)
        self.assertEqual(len(asked), 1)

    def test_a_saved_decision_replaced_and_from_one_to_two_turbines(self):
        d = self.dialog()
        self.choose_preset(d.wake_group, "NiayifarGaussian")
        wg.save_consent(self.settings, "NiayifarGaussian", ["h5py"])
        asked = []
        # The first reading with one turbine does not need it; the second, with two, applies it without asking.
        self.assertEqual(self.answer(d, ["h5py"], False, asked, n_turbines=1), ps.config("NiayifarGaussian"))
        config = self.answer(d, ["h5py"], False, asked, ask=False, n_turbines=2)
        self.assertEqual((asked, config.adaptations[0]["acceptance"]), ([], "saved_preference"))
        # Other libraries: asked, and «Continuar» with the box replaces it.
        self.answer(d, ["h5py", "h5netcdf"], True, asked, n_turbines=2)
        self.assertEqual(len(asked), 1)
        self.assertEqual(wg.saved_consent(self.settings, "NiayifarGaussian")["modules"], ["h5netcdf", "h5py"])

    def test_the_note_of_the_old_preferences_when_the_manual_mode_is_shown(self):
        self.settings.setValue("last_wfm_engine", "A2A")  # a preference of the previous version
        d = self.dialog()
        self.assertEqual(d.wake_group.mode(), wg.PREDEFINED)
        self.choose_preset(d.wake_group, "ZongGaussian")
        self.assertFalse(self.settings.value(d._OLD_PHYSICS_NOTED, False, type=bool))  # not said yet
        d.wake_group.set_mode(wg.MANUAL)
        self.assertIn("ya no se usan", d.wake_group.lbl_preferences.text())
        self.assertTrue(self.settings.value(d._OLD_PHYSICS_NOTED, False, type=bool))
        d.wake_group.set_mode(wg.PREDEFINED)
        d.wake_group.set_mode(wg.MANUAL)
        self.assertEqual(d.wake_group.lbl_preferences.text().count("ya no se usan"), 1)  # once

    def test_the_raster_is_launched_with_the_model_and_its_provenance(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        from VelantisWind.wake_core import controller
        from tests.test_resource_settings import write_wrg
        folder = tempfile.mkdtemp(dir=_SETTINGS.name)
        wrg = write_wrg(folder, 12)
        physics = api.to_wake_physics(ps.config("SuperGaussian"))
        dialog = types.SimpleNamespace(
            _rows=[{"name": "A", "wt": object(), "meta": {}}],
            _collect_layer_points_for_row=lambda idx: [(0.0, 0.0)],
            _find_interactive_layer_for_row=lambda idx: types.SimpleNamespace(id=lambda: "layer-a", name=lambda: "A"),
            ed_dir=mock.Mock(text=lambda: ""), ed_wrg=mock.Mock(text=lambda: wrg),
            _qsettings=mock.Mock(value=lambda *a, **k: 200), ed_wrg_ti=mock.Mock(text=lambda: ""),
            _wake_physics_for_run=lambda what="AEP", ask=True, n_turbines=None: physics,
            _wake_provenance_for_run=lambda: ps.provenance("SuperGaussian"),
            _get_fixed_ti_fraction=lambda: 0.1, _get_air_density_settings=lambda: {"mode": "off"},
            _get_resource_params=lambda: {"direction_count": None, "wd_interp": "nearest", "ws_step": None})
        start = mock.Mock()
        with mock.patch.object(controller, "start_wake_raster_from_dialog", start), \
                mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(200, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a, **k: (a[3][0], True)):
            AEPSetupDialog._run_plot_wakes(dialog)
        kwargs = start.call_args.kwargs
        self.assertEqual(kwargs["wake_config"], ps.config("SuperGaussian"))
        self.assertEqual(kwargs["wake_provenance"], ps.provenance("SuperGaussian"))


def said(m):
    return " ".join(n.text() for n in m.notes.values()) + " " + m.preset_note.text()


class MirrorTest(_Case):
    def mirror(self, g):
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        return wg.WakeGroupMirror(g, QtWidgets.QFormLayout(holder))

    def test_the_model_both_ways(self):
        g = self.group()
        m = self.mirror(g)
        self.assertEqual([m.combo_preset.itemData(i) for i in range(m.combo_preset.count())], list(ps.ids()))
        self.assertFalse(m.combo_preset.isHidden())
        m.combo_preset.setCurrentIndex(m.combo_preset.findData("ZongGaussian"))
        self.assertEqual(g.combo_preset.currentData(), "ZongGaussian")
        self.choose_preset(g, "NOJ")
        self.assertEqual(m.combo_preset.currentData(), "NOJ")

    def test_the_components_are_shown_disabled_and_forward_nothing(self):
        g = self.group()
        m = self.mirror(g)
        self.choose_preset(g, "NiayifarGaussian")
        manual = {p: c.currentData() for p, c in g.combo.items()}
        for position in COMPONENTS:
            self.assertEqual(m.combo[position].currentData(), g.preset_combo[position].currentData())
            self.assertFalse(m.combo[position].isEnabled())
        self.assertTrue(m.combo[cat.BLOCKAGE].isHidden())
        for position in COMPONENTS:
            m.combo[position].addItem("x", "NOJDeficit")
            m.combo[position].setCurrentIndex(1)
            m.combo[position].currentIndexChanged.emit(0)
        self.assertEqual(g.config(), ps.config("NiayifarGaussian"))
        self.assertEqual({p: c.currentData() for p, c in g.combo.items()}, manual)

    def test_the_components_of_a_model_are_read_as_in_the_dialog(self):
        from VelantisWind.ui_core.wake_controls import READ_ONLY_STYLE
        g = self.group()
        m = self.mirror(g)
        self.assertTrue(all(m.combo[p].styleSheet() == READ_ONLY_STYLE for p in COMPONENTS))
        self.assertFalse(m.combo_preset.styleSheet())
        g.set_mode(wg.MANUAL)
        self.assertFalse([p for p in wg.SHOWN_POSITIONS if m.combo[p].styleSheet()])  # as today

    def test_the_mode_changed_in_the_dialog_rebuilds_it_and_nothing_is_left(self):
        g = self.group()
        m = self.mirror(g)
        for step in ("SuperGaussian", "NOJ", wg.MANUAL, wg.PREDEFINED, "BastankhahGaussian"):
            with self.subTest(step=step):
                if step in (wg.MANUAL, wg.PREDEFINED):
                    g.set_mode(step)
                else:
                    self.choose_preset(g, step)
                predefined = g.mode() == wg.PREDEFINED
                self.assertEqual(m.combo_preset.isHidden(), not predefined)
                self.assertEqual(m.preset_note.text(), g.preset_note.text() if predefined else "")
                for position in COMPONENTS:
                    theirs = g.preset_combo[position] if predefined else g.combo[position]
                    self.assertEqual(m.combo[position].currentData(), theirs.currentData())
                    self.assertEqual(m.combo[position].count(), theirs.count())
                    self.assertEqual(m.combo[position].isEnabled(), not predefined)
                    note = g.preset_conflict[position] if predefined else g.conflict[position]
                    self.assertEqual(m.notes[position].text(), note.text() if not note.isHidden() else "")
                note = {"SuperGaussian": "Usa CrespoHernandez", "BastankhahGaussian": "k = 0,0324555"}.get(
                    g.combo_preset.currentData()) if predefined else None
                if note:
                    self.assertIn(note, m.preset_note.text())
                    self.assertIn("#b9770e", m.preset_note.text())
                    self.assertFalse(m.preset_note.isHidden())
                else:
                    self.assertNotIn("CrespoHernandez", said(m))
                    self.assertNotIn("0,0324555", said(m))
        # Back in the manual mode, its selectors enabled and forwarding as today.
        g.set_mode(wg.MANUAL)
        m.combo[cat.DEFICIT].setCurrentIndex(m.combo[cat.DEFICIT].findData("ZongGaussianDeficit"))
        self.assertEqual(g.combo[cat.DEFICIT].currentData(), "ZongGaussianDeficit")
        self.assertIn("PyWake exige un modelo de turbulencia", said(m))

    def test_the_mirror_says_nothing_of_the_saved_decision(self):
        g = self.group()
        m = self.mirror(g)
        wg.save_consent(self.settings, "TurbOPark", ["h5py"])
        with mock.patch(MISSING, return_value=["h5py"]):
            self.choose_preset(g, "TurbOPark")
        self.assertNotIn("CGIRotorAvg(7)", said(m))

    def test_without_the_libraries_the_mirror_says_nothing_of_it(self):
        g = self.group()
        m = self.mirror(g)
        with mock.patch(MISSING, return_value=["h5py"]):
            self.choose_preset(g, "TurbOPark")
            self.assertNotIn("h5py", said(m))

class WakeHelpPointsTest(_Case):
    def setUp(self):
        super().setUp()
        self.patcher = mock.patch.object(wg.WakeModelGroup, "_show_info_dialog")
        self.show = self.patcher.start()
        self.addCleanup(mock.patch.stopall)

    def shown(self):
        return self.show.call_args.args[1]

    def test_help_of_either_mode_changes_neither_the_mode_nor_the_configuration_nor_the_preferences(self):
        for mode in (wg.PREDEFINED, wg.MANUAL):
            with self.subTest(active=mode):
                g = self.group()
                g.set_mode(mode)
                before = (g.mode(), g.config(), self.keys(), {m: b.isChecked() for m, b in g.btn_mode.items()})
                g.btn_modes_info.click()  # a general tab first, then both modes, the inactive one too
                self.assertEqual(self.shown(), [("General", g._tr(wg.GENERAL_HELP)),
                                                (wg.MODE_LABELS[wg.PREDEFINED], g._mode_help(wg.PREDEFINED)),
                                                (wg.MODE_LABELS[wg.MANUAL], g._mode_help(wg.MANUAL))])
                g.btn_preset_model_info.click()
                g.btn_preset_info[cat.ENGINE].click()
                g.btn_row_info[cat.ENGINE].click()
                self.assertEqual((g.mode(), g.config(), self.keys(), {m: b.isChecked() for m, b in g.btn_mode.items()}),
                                 before)

    def test_the_segments_stay_joined_and_exclusive_with_the_help_point_right_after_them(self):
        g = self.group()
        g.show()
        self.addCleanup(g.hide)
        QtWidgets.QApplication.processEvents()
        plain = QtWidgets.QPushButton()
        self.addCleanup(plain.deleteLater)
        info = g.btn_modes_info
        segments = [g.btn_mode[m].geometry() for m in (wg.PREDEFINED, wg.MANUAL)]
        self.assertEqual(segments[0].right() + 1, segments[1].left())  # joined
        self.assertEqual(info.geometry().left(), segments[1].right() + 1)  # right after them
        self.assertLessEqual(abs(info.geometry().center().y() - segments[1].center().y()), 1)
        self.assertTrue(info.toolTip())
        self.assertTrue(info.accessibleName())
        self.assertTrue(info.focusPolicy() & QtCore.Qt.TabFocus)
        for mode in (wg.PREDEFINED, wg.MANUAL):
            button = g.btn_mode[mode]
            with self.subTest(mode=mode):
                plain.setText(button.text())
                plain.setStyleSheet(button.styleSheet())
                self.assertEqual(button.width(), plain.sizeHint().width())  # the size of modelos-estela
                button.click()
                self.assertEqual(g.mode(), mode)
                self.assertEqual([m for m, b in g.btn_mode.items() if b.isChecked()], [mode])

    def test_the_help_point_of_the_modes_answers_the_keyboard_without_choosing_a_mode(self):
        from qgis.PyQt import QtTest
        for active in (wg.PREDEFINED, wg.MANUAL):
            with self.subTest(active=active):
                dialog = QtWidgets.QDialog()
                self.addCleanup(dialog.deleteLater)
                g = wg.WakeModelGroup(dialog, settings=self.settings)
                QtWidgets.QVBoxLayout(dialog).addWidget(g)
                g.set_mode(active)
                dialog.show()
                QtWidgets.QApplication.setActiveWindow(dialog)
                before = (g.mode(), g.config(), self.keys())
                self.show.reset_mock()
                g.btn_modes_info.setFocus()
                self.assertTrue(g.btn_modes_info.hasFocus())
                QtTest.QTest.keyClick(g.btn_modes_info, QtCore.Qt.Key_Space)
                self.assertEqual(self.show.call_count, 1)
                self.assertEqual((g.mode(), g.config(), self.keys()), before)
                self.assertEqual([m for m, b in g.btn_mode.items() if b.isChecked()], [active])
                dialog.hide()

    def test_the_information_points_form_a_column_in_both_modes(self):
        # Whatever a line shows after its selector (the engine's settings, the n of a rotor average, the ground's
        # window), its information point is the last widget, at the right edge of the line.
        g = self.group()
        g.resize(700, 600)
        g.show()
        self.addCleanup(g.hide)

        def rights(buttons):
            QtWidgets.QApplication.processEvents()
            return {b.mapTo(g, b.rect().topRight()).x() for b in buttons if b.isVisible()}

        g.set_mode(wg.MANUAL)
        g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("All2AllIterative"))
        self.assertEqual(len(rights([g.btn_row_info[p] for p in (cat.ENGINE, cat.DEFICIT, cat.SUPERPOSITION,
                                                                 cat.BLOCKAGE, cat.TURBULENCE)])), 1)
        g.set_mode(wg.PREDEFINED)
        for id_ in ("TurbOPark", "NiayifarGaussian"):  # with the ground's window, with the rotor's n
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                for section in g.preset_sections.values():
                    section.setExpanded(True)
                main = [g.btn_preset_model_info] + [g.btn_preset_info[p] for p in (cat.ENGINE, cat.DEFICIT,
                                                                                  cat.SUPERPOSITION, cat.TURBULENCE)]
                self.assertEqual(len(rights(main)), 1)
                inner = [g.btn_preset_info[p] for p in (cat.ROTOR, cat.GROUND) if p in g.btn_preset_info]
                self.assertLessEqual(len(rights(inner)), 1)

    def test_the_notes_of_the_predefined_models_are_translated(self):
        from VelantisWind.ag_core.wake_setup.messages_translations import TRANSLATIONS
        from tests.pending_translations import PENDING
        for note in ps.NOTES:
            self.assertNotIn(note, PENDING)
            for lang in ("en", "fr", "de"):
                with self.subTest(note=note[:30], language=lang):
                    self.assertTrue(TRANSLATIONS[lang][note].strip())
                    self.assertNotEqual(TRANSLATIONS[lang][note], note)
                    for name in ("BastankhahGaussianDeficit", "CrespoHernandez", "PyWake"):
                        self.assertEqual(name in note, name in TRANSLATIONS[lang][note])

    def test_the_help_of_a_predefined_model_is_its_own(self):
        g = self.group()
        mode_help = g._mode_help(wg.PREDEFINED)
        for id_ in ps.ids():
            with self.subTest(preset=id_):
                self.choose_preset(g, id_)
                text = g._preset_model_help()
                model = ps.preset(id_)
                self.assertNotIn(mode_help, text)
                self.assertIn(model.reference_class, text)
                self.assertIn(model.url, text)
                for _kind, citation, url in wg.PRESET_HELP[id_][1]:
                    self.assertIn(citation, text)
                    self.assertIn(url, text)
                for note in ps.NOTES:  # each note with its model only
                    self.assertEqual(note in text, note in model.notes)
                self.assertEqual("Nygaard_2022 es la composición completa" in text, id_ == "TurbOPark")
                self.assertEqual(wg.PRESET_ADAPTATION in text,
                                 model.definition["rotor"] is not None
                                 and model.definition["rotor"]["class"] == "GaussianOverlapAvgModel")
        self.assertEqual(set(wg.PRESET_HELP), set(ps.ids()))

    def test_the_manual_help_separates_wakes_blockage_examples_and_checks(self):
        text = self.group()._mode_help(wg.MANUAL)
        headings = ("¿Qué permite este modo?", "Configuración de estelas", "Ejemplos de configuración",
                    "Emplazamientos marinos y terrestres",
                    "Estudiar el bloqueo", "Comparar con y sin bloqueo", "Comprobar los resultados")
        for heading in headings:
            self.assertIn(heading + "\n", text)
        self.assertEqual([text.index(h) for h in headings], sorted(text.index(h) for h in headings))  # in this order
        self.assertNotIn("Bloqueo (opcional)", text)
        self.assertIn("puede usar la misma regla.\n\nPara una primera prueba", text)  # the recommendation, apart
        self.assertNotIn("PARQUE", text)

    @staticmethod
    def example(deficit_name, turbulence, blockage, **deficit_params):
        """An example of the manual mode's help as it describes it: the manual mode's defaults with its deficit, its
        turbulence and, to study blockage, All2AllIterative and SelfSimilarityDeficit2020 with nothing else changed."""
        config = cfg.default_config(deficit=deficit_name)
        deficit = cfg.Component(deficit_name, {**config.deficit.params, **deficit_params})
        changes = dict(deficit=deficit, turbulence=turbulence)
        if blockage:
            changes.update(engine=cfg.Component("All2AllIterative", {}),
                           blockage=cfg.blockage_signature("SelfSimilarityDeficit2020"),
                           blockage_superposition=cfg.Component(cfg.DEFAULT_BLOCKAGE_SUPERPOSITION, {}))
        return cfg.WakeConfig(**{**config.__dict__, **changes})

    def test_the_examples_are_the_configurations_they_describe(self):
        # They can be calculated and the program says the same of their turbulence; this is not a validation.
        from VelantisWind.ag_core.wake_setup import notices
        crespo = cfg.component_signature("CrespoHernandez")
        for blockage in (False, True):
            with self.subTest(blockage=blockage):
                for config in (self.example("BastankhahGaussianDeficit", None, blockage),
                               self.example("NiayifarGaussianDeficit", crespo, blockage, use_effective_ti=True)):
                    self.assertEqual(val.validate(config, check_environment=False), [])
                    self.assertEqual(val.layout_issues(config, n_turbines=2), [])
        self.assertTrue(notices.turbulence_without_effect(self.example("BastankhahGaussianDeficit", crespo, False)))
        self.assertFalse(notices.turbulence_without_effect(
            self.example("NiayifarGaussianDeficit", crespo, False, use_effective_ti=True)))
        self.assertTrue(notices.turbulence_without_effect(
            self.example("NiayifarGaussianDeficit", crespo, False, use_effective_ti=False)))
        for name in ("BastankhahGaussianDeficit", "NiayifarGaussianDeficit", "use_effective_ti = True",
                     "CrespoHernandez", "All2AllIterative", "PropagateUpDownIterative", "SelfSimilarityDeficit2020"):
            self.assertIn(name, wg.EXAMPLES_HELP)

    def test_the_examples_behave_as_the_help_says(self):
        # Three aligned turbines of PyWake's example data, built by the plugin's factory: what the help says of the
        # turbulence holds numerically. A functional check of the text, not a validation of the models.
        import numpy as np
        from VelantisWind.ag_core.wake_setup import factory
        from tests.test_wake_setup_factory import SITE, WT, X, Y
        crespo = cfg.component_signature("CrespoHernandez")

        def ws_eff(config):
            wfm = factory.build_wind_farm_model(config, SITE, WT, ws_grid=np.array([10.0]))
            ws = wfm(X[:3], Y[:3], wd=[270.0], ws=[10.0]).WS_eff.values.ravel()
            self.assertTrue(np.all(np.isfinite(ws)))
            return ws

        for blockage in (False, True):
            with self.subTest(blockage=blockage):
                # A: adding a turbulence model leaves a deficit with a fixed k unchanged.
                np.testing.assert_allclose(ws_eff(self.example("BastankhahGaussianDeficit", crespo, blockage)),
                                           ws_eff(self.example("BastankhahGaussianDeficit", None, blockage)))
                # B: the effective TI changes the expansion, so the speeds downstream.
                with_ti = ws_eff(self.example("NiayifarGaussianDeficit", crespo, blockage, use_effective_ti=True))
                ambient = ws_eff(self.example("NiayifarGaussianDeficit", crespo, blockage, use_effective_ti=False))
                self.assertFalse(np.allclose(with_ti, ambient))

    def test_the_help_of_a_selector_follows_its_option(self):
        g = self.group()
        g.set_mode(wg.MANUAL)
        g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("All2AllIterative"))
        text = g._row_help(cat.ENGINE)
        self.assertIn(wg.ROW_EXPLANATIONS[cat.ENGINE], text)
        self.assertIn("Opción seleccionada: All2AllIterative", text)
        g.set_mode(wg.PREDEFINED)
        self.choose_preset(g, "TurbOPark")
        text = g._selector_help(cat.DEFICIT, g.preset_combo[cat.DEFICIT])
        self.assertIn("Opción seleccionada: " + g.preset_combo[cat.DEFICIT].currentText(), text)
        self.assertIn("Nygaard_2022", text)

    def test_the_window_shows_paragraphs_headings_and_links(self):
        html = wg.help_html("Título\nVer https://doi.org/10.1/a<b> y más\n\nSolo")
        self.assertIn("<b>Título</b>", html)
        self.assertIn('<a href="https://doi.org/10.1/a&lt;b&gt;">', html)
        self.assertIn("<p>Solo</p>", html)
        self.assertEqual(wg.help_html("Título\nIntro\n• uno\n• dos"),
                         "<p><b>Título</b><br>Intro</p><ul><li>uno</li><li>dos</li></ul>")
        self.patcher.stop()
        g = self.group()
        with mock.patch.object(QtWidgets.QDialog, "exec_", return_value=0) as run:
            g._show_info_dialog("Manual", g._preset_model_help())
            run.assert_called_once()
        dialog = g.findChildren(QtWidgets.QDialog, "wakeInfoDialog")[-1]
        browser = dialog.findChild(QtWidgets.QTextBrowser, "wakeInfoText")
        self.assertTrue(browser.openExternalLinks())
        self.assertIn(ps.preset("NOJ").url, browser.toHtml())
        self.assertTrue(browser.textInteractionFlags() & QtCore.Qt.TextSelectableByMouse)
        # The help of the modes: one tab each, the general one first.
        with mock.patch.object(QtWidgets.QDialog, "exec_", return_value=0):
            g._show_info_dialog("Modos", g._modes_help())
        tabs = g.findChildren(QtWidgets.QDialog, "wakeInfoDialog")[-1].findChild(QtWidgets.QTabWidget, "wakeInfoTabs")
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["General", wg.MODE_LABELS[wg.PREDEFINED], wg.MODE_LABELS[wg.MANUAL]])
        self.assertEqual(tabs.currentIndex(), 0)
        self.assertIn("Ejemplos de configuración", tabs.widget(2).toPlainText())

    def test_information_icons_match_noise_and_shadow_modules(self):
        g = self.group()
        for button in [g.btn_modes_info, *g.btn_row_info.values(),
                       g.btn_preset_model_info, *g.btn_preset_info.values()]:
            with self.subTest(widget=button.accessibleName()):
                self.assertTrue(button.autoRaise())
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.cursor().shape(), QtCore.Qt.PointingHandCursor)

    def test_the_help_is_translated_with_its_markers_and_names(self):
        import re
        from VelantisWind import i18n
        # R2 source corrections are registered in the general tables by aplicar_pares.
        # Check the complete registry, preserving the same required keys and assertions.
        i18n._ensure()
        translations = i18n._STATE["full"]
        sources = [*wg.MODE_LABELS.values(), "General", wg.GENERAL_HELP, wg.PRESETS_PAGE, wg.PRESETS_FOOTER,
                   wg.PRESET_RESOLUTION,
                   wg.PREDEFINED_HELP, wg.MANUAL_HELP, wg.EXAMPLES_HELP, wg.VALIDATION_HELP, wg.PRESET_MODEL_HELP,
                   wg.PRESET_SCOPE, wg.PRESET_REFERENCES, wg.PRESET_DOCUMENTATION, wg.PRESET_PARTICULARS,
                   wg.PRESET_ADAPTATION, wg.SELECTED_HELP, wg.INFO_TOOLTIP, *wg.ROW_EXPLANATIONS.values(),
                   *(f for f, _ in wg.PRESET_HELP.values()),
                   *{kind for _, refs in wg.PRESET_HELP.values() for kind, _, _ in refs}]
        names = re.compile(r"\{\w+\}|\b(?:[A-Z][a-z0-9]+){2,}\w*|\b\w+_\w+\b|\b\w+ = (?:True|False)\b")
        for lang in ("en", "fr", "de"):
            for source in sources:
                with self.subTest(language=lang, source=source[:40]):
                    translated = translations[lang][source]
                    for name in set(names.findall(source)):
                        self.assertIn(name, translated)
                    self.assertEqual(source.count("\n\n"), translated.count("\n\n"))
            g = self.group()
            g._tr = lambda source, table=translations[lang]: table.get(source, source)
            for id_ in ps.ids():
                self.choose_preset(g, id_)
                text = g._preset_model_help()
                self.assertNotIn("{", text)
                self.assertIn(ps.preset(id_).url, text)
            self.assertNotIn("¿", g._mode_help(wg.MANUAL) + g._mode_help(wg.PREDEFINED))


if __name__ == "__main__":
    unittest.main()
