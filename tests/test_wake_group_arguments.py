# -*- coding: utf-8 -*-
"""The arguments of the subordinate objects in the «Modelo de estela» group (#64, Q3).

The dialog tests of the plan for Q3: a control for each kind (``ControlsTest``), the minimum of EqGrid corrected in
view and a large value kept; limits and warnings at their selector; «Restablecer» and the draft of each class
(``DraftTest``); the configuration reaching the calculation; the help of every new option and argument, not empty, in
four languages, and one shown in the group (``HelpTest``); the new sections folded at the start; a conflict whose
cause is inside a window, and the window itself: «Restablecer» then «Cancelar», «Aceptar» in a child then
«Cancelar» in its mother, an unreadable value and a conflict with an outer selector (``WindowTest``).
"""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
from VelantisWind.ag_core.wake_setup import catalog as cat  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import subordinates as sub  # noqa: E402
from VelantisWind.ag_core.wake_setup.subordinates_translations import SOURCES as SUB_SOURCES  # noqa: E402
from VelantisWind.ag_core.wake_setup.subordinates_translations import TRANSLATIONS as SUB_TRANSLATIONS  # noqa: E402
from VelantisWind.ui_core import wake_group as wg  # noqa: E402
from VelantisWind.ui_core.wake_controls import ComponentWindow, SubordinateEditor  # noqa: E402
from VelantisWind.ui_core.wake_group_translations import TRANSLATIONS  # noqa: E402

_CWD = os.getcwd()


def C(name, **params):
    return cfg.Component(name, params)


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class _Case(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".ini", dir=_SETTINGS.name)
        os.close(fd)
        self.settings = QtCore.QSettings(path, QtCore.QSettings.IniFormat)
        # The manual mode, chosen: without preferences the group opens with the predefined models.
        self.settings.setValue(wg.MODE_KEY, wg.MANUAL)
        self.g = self.group()

    def group(self, **kwargs):
        g = wg.WakeModelGroup(settings=self.settings, **kwargs)
        self.addCleanup(g.deleteLater)
        return g

    def choose(self, position, data, g=None):
        g = g or self.g
        i = g.combo[position].findData(data)
        self.assertGreaterEqual(i, 0, data)
        g.combo[position].setCurrentIndex(i)

    @staticmethod
    def pick(combo, data):
        combo.setCurrentIndex(combo.findData(data))

    def codes(self, g=None):
        return {i.code for i in (g or self.g).issues()}


class ControlsTest(_Case):
    def editor(self, comp):
        ed = SubordinateEditor(cfg.complete(comp), minimum=wg.SPIN_MINIMUM)
        self.addCleanup(ed.deleteLater)
        return ed

    def test_one_control_for_each_kind(self):
        ed = self.editor(C("CrespoHernandez"))  # ct2a, a list, nested components (one with its own arguments)
        self.assertIsInstance(ed.control("ct2a"), QtWidgets.QComboBox)
        box, fields = ed.control("c")
        self.assertEqual(len(fields), 4)  # one field for each coefficient (decision 4)
        fields[1].setText("0,9")  # a comma is the decimal point
        self.pick(ed.control("addedTurbulenceSuperpositionModel"), "MaxSum")
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        ed.nested("rotorAvgModel").control("n").setValue(3)  # its argument in the same line
        value = ed.value()
        self.assertEqual(value.params["c"][1], 0.9)
        self.assertEqual(value.params["addedTurbulenceSuperpositionModel"], C("MaxSum"))
        self.assertEqual(value.params["rotorAvgModel"], C("EqGridRotorAvg", n=3))
        fields[0].setText("x")
        self.assertEqual(ed.errors(), ["c"])  # an unreadable field is reported, never replaced
        ed = self.editor(C("RankineHalfBody"))
        self.assertEqual(ed.control("high_ct_mod").currentData(), False)  # True/False
        ed = self.editor(C("CGIRotorAvg"))
        self.assertEqual([ed.control("n").itemData(i) for i in range(ed.control("n").count())], [4, 7, 9, 21])
        self.assertEqual(ed.control("n").currentData(), 7)

    def test_a_number_or_none(self):
        ed = self.editor(C("All2AllIterative"))
        box, mode, field = ed.control("convergence_tolerance")
        self.assertEqual((mode.currentData(), field.text(), field.isEnabled()), ("check", "1e-06", True))
        self.pick(mode, "none")
        self.assertFalse(field.isEnabled())
        self.assertIsNone(ed.value().params["convergence_tolerance"])
        field.setText("x")  # a field not used is not read
        self.assertEqual(ed.errors(), [])
        self.pick(mode, "check")
        self.assertEqual(ed.errors(), ["convergence_tolerance"])

    def test_the_minimum_of_eqgrid_is_corrected_in_view_and_a_large_value_kept(self):
        # Decision 5 of #64: PyWake builds n from −2 (without nodes from −2 to 0, warned) and refuses −3 or less.
        ed = self.editor(C("EqGridRotorAvg"))
        spin = ed.control("n")
        for typed, shown in (("0", 0), ("-2", -2), ("-5", -2)):
            spin.lineEdit().setText(str(typed))
            spin.interpretText()
            spin.clearFocus()
            QtWidgets.QApplication.sendEvent(spin, QtCore.QEvent(QtCore.QEvent.FocusOut))
            self.assertEqual(spin.text(), str(shown))  # what is shown is what is calculated
            self.assertEqual(ed.value().params["n"], shown)
        ed = self.editor(C("EqGridRotorAvg", n=10 ** 6))
        self.assertEqual(ed.control("n").value(), 10 ** 6)  # no maximum of its own: not clipped
        ed = self.editor(C("MultiMirror", n_reps=-3))  # an integer without a minimum keeps a negative
        self.assertEqual(ed.value().params["n_reps"], -3)


    def test_a_negative_typed_is_corrected_to_the_minimum(self):
        # With real key presses: the minus sign is let through and −3 corrected to −2 when leaving the field.
        from qgis.PyQt.QtTest import QTest
        ed = self.editor(C("EqGridRotorAvg"))
        ed.show()
        spin = ed.control("n")
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), "-3")
        QTest.keyClick(spin.lineEdit(), QtCore.Qt.Key_Tab)
        spin.interpretText()
        self.assertEqual((spin.value(), spin.text()), (-2, "-2"))  # what is shown is what is calculated
        self.assertEqual(ed.value().params["n"], -2)
        ed.hide()


class NestedOptionTest(_Case):
    def test_an_integer_being_typed_never_replaces_the_option_chosen(self):
        # The editor of the old option commits its integer when hidden: it keeps it, the new option stays chosen.
        from qgis.PyQt.QtTest import QTest
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.g.show()
        self.g.sec_turbulence.setExpanded(True)
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        spin = ed.nested("rotorAvgModel").control("n")
        spin.setFocus()
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), "8")  # not committed yet
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        QtWidgets.QApplication.processEvents()
        self.assertEqual(ed.control("rotorAvgModel").currentData(), "CGIRotorAvg")
        self.assertEqual(self.g.config().turbulence.params["rotorAvgModel"], C("CGIRotorAvg", n=7))
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")  # and the old option kept what was typed
        self.assertEqual(self.g.config().turbulence.params["rotorAvgModel"], C("EqGridRotorAvg", n=8))
        self.g.hide()


class RotorBeingTypedTest(_Case):
    def test_an_integer_being_typed_is_kept_when_the_deficit_class_changes(self):
        # Typed and not committed (keyboard tracking off): changing the class keeps it in the draft of its class.
        from qgis.PyQt.QtTest import QTest
        self.g.show()
        self.g.sec_deficit.setExpanded(True)
        self.choose(cat.ROTOR, "EqGridRotorAvg")
        spin = self.g.rotor_editor.control("n")
        spin.setFocus()
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), "8")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.assertEqual(self.g.config().rotor, C("EqGridRotorAvg", n=8))
        self.assertEqual(self.g.rotor_editor.control("n").value(), 8)
        self.g.hide()


class GroupTest(_Case):
    def test_the_new_sections_start_folded(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        for sec in (self.g.sec_superposition, self.g.sec_turbulence, self.g.sec_blockage, self.g.sec_deficit):
            self.assertFalse(sec.isExpanded())
        self.assertIsNotNone(self.g.args_editor(cat.ENGINE))
        self.assertFalse(hasattr(self.g, "sec_engine"))  # its arguments: the button of its line (D5)

    def test_the_rotor_and_its_n_in_its_line(self):
        self.choose(cat.ROTOR, "CGIRotorAvg")  # one option since #64, with its n (7 in its signature)
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=7))
        self.pick(self.g.rotor_editor.control("n"), 21)
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=21))

    def test_the_configuration_reaches_the_calculation(self):
        from tests.test_wake_setup_factory import build
        self.choose(cat.ENGINE, "All2AllIterative")
        self.pick(self.g.args_editor(cat.ENGINE).control("convergence_tolerance")[1], "none")
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.g.args_editor(cat.SUPERPOSITION).control("alpha").setText("1.5")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.g.args_editor(cat.TURBULENCE).control("c")[1][0].setText("1.2")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.args_editor(cat.BLOCKAGE).control("ss_alpha").setText("0.7")
        config = self.g.config()
        self.assertEqual(self.codes(), set())
        wfm = build(config)
        self.assertIsNone(wfm.convergence_tolerance)
        self.assertEqual(wfm.superpositionModel.alpha, 1.5)
        self.assertEqual(list(wfm.turbulenceModel.c), [1.2, 0.8])
        self.assertEqual(wfm.blockage_deficitModel.ss_alpha, 0.7)
        # The result says it, never «converged» (decision 19); the differences with their routes are in the result
        # (the dialog has no summary since decision 7 of #64).
        self.assertIn("no comprueba la convergencia", self.g.conflict[cat.ENGINE].text())
        self.assertFalse(hasattr(self.g, "lbl_summary") or hasattr(self.g, "lbl_differences"))

    def test_what_pywake_calculates_is_a_warning_at_its_selector_not_a_conflict(self):
        # Decision 5 of #64: c = [0, 0] calculates in PyWake (non-finite results): warned, never refused.
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        before = self.g.config()
        for field in self.g.args_editor(cat.TURBULENCE).control("c")[1]:
            field.setText("0")
        self.assertEqual(self.codes(), set())
        self.assertIn("c = [0, 0]", self.g.conflict[cat.TURBULENCE].text())
        self.assertEqual(self.g.config().turbulence.params["c"], [0.0, 0.0])
        self.assertEqual(self.g.combo[cat.TURBULENCE].currentData(), before.turbulence.name)  # nothing changed

    def test_a_warning_at_its_selector(self):
        self.choose(cat.GROUND, "MultiMirror")
        self.assertIn("MultiMirror", self.g.conflict[cat.DEFICIT].text())  # its cost (decision 19)
        self.assertEqual(self.codes(), set())

    def test_the_excluded_arguments_with_their_reason(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "HybridInduction")
        self.assertIn("near_rotor", self.g.lbl_blockage_info.text())
        self.assertIn("Todavía no se ofrece: PyWake calcula con él", self.g.lbl_blockage_info.text())
        self.choose(cat.TURBULENCE, "STF2005TurbulenceModel")
        self.assertIn("No se ofrece c = ", self.g.lbl_turbulence_info.text())


class DraftTest(_Case):
    def test_the_draft_of_each_class(self):
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.g.args_editor(cat.SUPERPOSITION).control("delta").setText("0.02")
        self.choose(cat.SUPERPOSITION, "LinearSum")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.assertEqual(self.g.config().superposition.params["delta"], 0.02)
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 9)
        self.choose(cat.ROTOR, "EqGridRotorAvg")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=9))
        # A text that cannot be read stays as it was while another class is chosen.
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.g.args_editor(cat.TURBULENCE).control("c")[1][0].setText("x")
        self.assertEqual(self.codes(), {"field"})
        self.choose(cat.TURBULENCE, "GCLTurbulence")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.assertEqual(self.g.args_editor(cat.TURBULENCE).control("c")[1][0].text(), "x")

    def test_reset_goes_back_to_the_signatures_and_keeps_the_choices(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.g.args_editor(cat.ENGINE).control("convergence_tolerance")[2].setText("1e-3")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.g.args_editor(cat.SUPERPOSITION).control("delta").setText("0.02")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 9)
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.args_editor(cat.BLOCKAGE).control("ss_alpha").setText("0.7")
        # Decision 7 of #64: each section, its own; the selector above it and the other sections stay.
        self.g.btn_reset_section[cat.SUPERPOSITION].click()
        config = self.g.config()
        self.assertEqual(config.superposition, cfg.complete(C("WeightedSum")))
        self.assertEqual(config.rotor, C("CGIRotorAvg", n=9))
        self.assertEqual(config.blockage.params["ss_alpha"], 0.7)
        self.g.btn_reset_section[cat.DEFICIT].click()
        config = self.g.config()
        self.assertEqual(config.rotor, cfg.deficit_signature(config.deficit.name)[1])
        self.assertEqual(config.blockage.params["ss_alpha"], 0.7)
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=7))  # the one it had chosen, its signature
        self.g.btn_reset_section[cat.BLOCKAGE].click()
        config = self.g.config()
        self.assertEqual(config.blockage, cfg.blockage_signature("SelfSimilarityDeficit2020"))
        self.assertEqual((config.engine.name, config.superposition.name, config.blockage.name),
                         ("All2AllIterative", "WeightedSum", "SelfSimilarityDeficit2020"))  # the choices are kept
        self.assertEqual(config.engine.params["convergence_tolerance"], 1e-3)  # not in a section: its window


    def test_the_rotor_of_each_deficit_class_is_its_own(self):
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 9)
        self.choose(cat.ROTOR, wg.NONE)
        self.choose(cat.DEFICIT, "NOJDeficit")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 21)
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=9))  # the one of this class

    def test_reset_keeps_the_drafts_of_the_other_classes(self):
        # Decision 7 of #64: only the class that is shown (the general reset reached every class).
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 9)
        self.choose(cat.BLOCKAGE, "VortexDipole")
        self.g.args_editor(cat.BLOCKAGE).control("sct").setText("1.5")
        self.choose(cat.DEFICIT, "NOJDeficit")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.btn_reset_section[cat.DEFICIT].click()
        self.g.btn_reset_section[cat.BLOCKAGE].click()
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=9))
        self.choose(cat.BLOCKAGE, "VortexDipole")
        self.assertEqual(self.g.config().blockage.params["sct"], 1.5)

    def test_reset_of_a_section_keeps_the_drafts_of_the_alternatives_not_chosen(self):
        # With CGI and EqGrid edited in the same deficit and CGI chosen, the deficit reset leaves CGI with its
        # signature and EqGrid with its draft; an unreadable text of the section goes too.
        self.choose(cat.ROTOR, "EqGridRotorAvg")
        self.g.rotor_editor.control("n").setValue(6)
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.pick(self.g.rotor_editor.control("n"), 21)
        self.g.deficit_editor.control("k").setText("0,03x")
        self.assertEqual(self.codes(), {"field"})
        self.g.btn_reset_section[cat.DEFICIT].click()
        self.assertEqual(self.codes(), set())
        self.assertEqual(self.g.config().deficit, cfg.deficit_signature("BastankhahGaussianDeficit")[0])
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.assertEqual(self.g.config().rotor, C("CGIRotorAvg", n=7))
        self.choose(cat.ROTOR, "EqGridRotorAvg")
        self.assertEqual(self.g.config().rotor, C("EqGridRotorAvg", n=6))
        # In an editor of arguments: the weight of STF2017 chosen (IECWeight) back to the signature (FrandsenWeight),
        # and the draft of IECWeight... it was the chosen one: its signature; another option keeps its draft.
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        ed.nested("rotorAvgModel").control("n").setValue(6)
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        self.pick(ed.nested("rotorAvgModel").control("n"), 21)
        ed.control("c")[1][0].setText("1.2")
        self.g.btn_reset_section[cat.TURBULENCE].click()
        config = self.g.config()
        self.assertEqual(config.turbulence, cfg.complete(C("STF2017TurbulenceModel")))
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        self.assertEqual(self.g.config().turbulence.params["rotorAvgModel"], C("EqGridRotorAvg", n=6))
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        self.assertEqual(self.g.config().turbulence.params["rotorAvgModel"], C("CGIRotorAvg", n=7))

    def test_reset_reaches_the_ground_chosen_and_keeps_the_others(self):
        # The ground of the deficit: MultiMirror edited in its window (an alternative) and Mirror chosen with a sum of
        # its own; after the reset, Mirror inherits again and MultiMirror keeps its draft.
        self.choose(cat.GROUND, "MultiMirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("n_reps").setValue(1)
        self.g.accept_ground_window(window)
        self.choose(cat.GROUND, "Mirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.g.accept_ground_window(window)
        self.g.btn_reset_section[cat.DEFICIT].click()
        self.assertIsNone(self.g.config().ground)  # the signature of BastankhahGaussianDeficit
        self.choose(cat.GROUND, "Mirror")
        self.assertEqual(self.g.config().ground, cfg.complete(C("Mirror")))
        self.choose(cat.GROUND, "MultiMirror")
        self.assertEqual(self.g.config().ground.params["n_reps"], 1)

    def test_reset_of_the_blockage_reaches_its_nested_rotor_and_ground(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        ed = self.g.args_editor(cat.BLOCKAGE)
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        ed.nested("rotorAvgModel").control("n").setValue(6)
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        self.pick(ed.nested("rotorAvgModel").control("n"), 21)
        self.pick(ed.control("groundModel"), "MultiMirror")
        window = ed.open_window("groundModel", exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("n_reps").setValue(1)
        ed.accept_window("groundModel", window)
        self.pick(ed.control("groundModel"), "Mirror")
        window = ed.open_window("groundModel", exec_=False)  # the one chosen, edited: a sum of its own
        self.addCleanup(window.deleteLater)
        self.pick(window.editor.control("superpositionModel"), "MaxSum")
        ed.accept_window("groundModel", window)
        self.assertEqual(self.g.config().blockage.params["groundModel"].params["superpositionModel"], C("MaxSum"))
        self.g.btn_reset_section[cat.BLOCKAGE].click()
        blockage = self.g.config().blockage
        self.assertEqual(blockage, cfg.blockage_signature("SelfSimilarityDeficit2020"))
        ed = self.g.args_editor(cat.BLOCKAGE)
        self.pick(ed.control("rotorAvgModel"), "EqGridRotorAvg")
        self.assertEqual(self.g.config().blockage.params["rotorAvgModel"], C("EqGridRotorAvg", n=6))
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        self.assertEqual(self.g.config().blockage.params["rotorAvgModel"], C("CGIRotorAvg", n=7))
        self.pick(ed.control("groundModel"), "MultiMirror")
        self.assertEqual(self.g.config().blockage.params["groundModel"].params["n_reps"], 1)
        self.pick(ed.control("groundModel"), "Mirror")
        self.assertEqual(self.g.config().blockage.params["groundModel"], cfg.complete(C("Mirror")))

    def test_reset_keeps_an_unreadable_text_of_an_alternative_not_chosen(self):
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("weight_function"), "IECWeight")
        ed.nested("weight_function").control("distance_limit").setText("x")
        self.pick(ed.control("weight_function"), "FrandsenWeight")
        self.assertEqual(self.codes(), set())
        self.g.btn_reset_section[cat.TURBULENCE].click()
        self.assertEqual(self.codes(), set())
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("weight_function"), "IECWeight")
        self.assertEqual(ed.nested("weight_function").control("distance_limit").text(), "x")
        self.assertEqual(self.codes(), {"field"})

    def test_the_reset_button_of_each_section(self):
        self.g.show()
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        for position, sec in ((cat.DEFICIT, self.g.sec_deficit), (cat.SUPERPOSITION, self.g.sec_superposition),
                              (cat.BLOCKAGE, self.g.sec_blockage), (cat.TURBULENCE, self.g.sec_turbulence)):
            with self.subTest(position=position):
                sec.setExpanded(True)
                QtWidgets.QApplication.processEvents()
                button = self.g.btn_reset_section[position]
                self.assertEqual(button.text(), "Restablecer")
                self.assertTrue(button.isVisible())
                corner = button.mapTo(sec.body, QtCore.QPoint(button.width(), button.height()))
                self.assertGreater(corner.x(), sec.body.width() - 30)  # at its bottom right
                self.assertGreater(corner.y(), sec.body.height() - 30)
        self.assertFalse(hasattr(self.g, "btn_reset") or hasattr(self.g, "sec_differences"))
        self.g.hide()

    def test_an_unreadable_text_of_a_nested_option_is_kept(self):
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        ed = self.g.args_editor(cat.TURBULENCE)
        self.pick(ed.control("weight_function"), "IECWeight")
        ed.nested("weight_function").control("distance_limit").setText("x")
        self.assertEqual(self.codes(), {"field"})
        self.pick(ed.control("weight_function"), "FrandsenWeight")
        self.pick(ed.control("weight_function"), "IECWeight")
        self.assertEqual(ed.nested("weight_function").control("distance_limit").text(), "x")
        self.assertEqual(self.codes(), {"field"})


class EngineWindowTest(_Case):
    def test_the_button_of_the_engine_and_its_window(self):
        # Decision 7 of #64 (point 9): a small button at the end of the line of the engine, with the three engines;
        # its window has the arguments and what is not offered; «Aceptar» keeps them for the class of the engine.
        self.g.show()
        for engine, args in (("PropagateDownwind", []), ("All2AllIterative", ["convergence_tolerance"]),
                             ("PropagateUpDownIterative", ["convergence_tolerance", "max_iter"])):
            with self.subTest(engine=engine):
                self.choose(cat.ENGINE, engine)
                self.assertTrue(self.g.btn_engine.isVisible())
                self.assertIs(self.g.btn_engine.parent(), self.g._inline[cat.ENGINE])
                self.assertEqual(self.g.btn_engine.toolTip(), "Ajustes numéricos del motor")
                window = self.g.open_engine_window(exec_=False)
                self.addCleanup(window.deleteLater)
                self.assertEqual([a.name for a in window.editor._args], args)
                self.assertEqual("externalWindFarms" in window.lbl_info.text(),
                                 engine in ("PropagateDownwind", "All2AllIterative"))
                self.assertTrue(window.windowTitle().startswith("Ajustes numéricos del motor"))
        self.g.hide()

    def test_accept_cancel_reset_and_the_drafts_of_each_engine(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        window = self.g.open_engine_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("convergence_tolerance")[2].setText("1e-3")
        self.g.accept_engine_window(window)
        self.assertEqual(self.g.config().engine.params["convergence_tolerance"], 1e-3)
        again = self.g.open_engine_window(exec_=False)  # reopened, with what was accepted
        self.addCleanup(again.deleteLater)
        self.assertEqual(again.editor.control("convergence_tolerance")[2].text(), "0.001")
        again.reset()  # Restablecer, then Cancelar: nothing changes
        again.reject()
        self.assertEqual(self.g.config().engine.params["convergence_tolerance"], 1e-3)
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        w = self.g.open_engine_window(exec_=False)
        self.addCleanup(w.deleteLater)
        w.editor.control("max_iter").setText("5")
        self.g.accept_engine_window(w)
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertEqual(self.g.config().engine.params["convergence_tolerance"], 1e-3)
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.assertEqual(self.g.config().engine.params["max_iter"], 5)
        # An unreadable field keeps «Aceptar» disabled.
        w = self.g.open_engine_window(exec_=False)
        self.addCleanup(w.deleteLater)
        w.editor.control("convergence_tolerance").setText("x")  # a number in PUD
        self.assertFalse(w.btn_accept.isEnabled())

    def test_a_warning_of_an_argument_of_the_engine_marks_its_button(self):
        # Its warning in the note of the line of the engine and the button marked; the window shows it, never opens.
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertEqual(self.g.btn_engine.styleSheet(), "")
        side = self.g.btn_engine.width()
        self.assertEqual(self.g.btn_engine.height(), side)
        window = self.g.open_engine_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.pick(window.editor.control("convergence_tolerance")[1], "none")
        self.g.accept_engine_window(window)
        self.assertIn("una sola iteración", self.g.conflict[cat.ENGINE].text())
        self.assertIn("b9770e", self.g.btn_engine.styleSheet())
        self.assertEqual((self.g.btn_engine.width(), self.g.btn_engine.height()), (side, side))  # still square
        self.assertEqual([w for w in QtWidgets.QApplication.topLevelWidgets()
                          if isinstance(w, ComponentWindow) and w.isVisible()], [])
        shown = self.g.open_engine_window(exec_=False)
        self.addCleanup(shown.deleteLater)
        self.assertIn("una sola iteración", shown.lbl_conflicts.text())
        # A conflict of its arguments (here, a field of PUD that cannot be read): red, in the note of the engine.
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.g.args_editor(cat.ENGINE).control("convergence_tolerance").setText("x")
        self.assertEqual(self.codes(), {"field"})
        self.assertIn("c0392b", self.g.btn_engine.styleSheet())
        self.assertIn("convergence_tolerance", self.g.conflict[cat.ENGINE].text())
        self.assertEqual((self.g.btn_engine.width(), self.g.btn_engine.height()), (side, side))

    def test_what_is_accepted_reaches_the_calculation(self):
        from unittest import mock
        from VelantisWind.ag_core.wake_setup import api
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        w = self.g.open_engine_window(exec_=False)
        self.addCleanup(w.deleteLater)
        w.editor.control("max_iter").setText("7")
        self.g.accept_engine_window(w)
        physics = api.to_wake_physics(self.g.config())
        self.assertEqual(api.resolve_request(physics)[0].engine.params["max_iter"], 7)


class AlignmentTest(_Case):
    def x(self, widget):
        return widget.mapTo(self.g, QtCore.QPoint(0, 0)).x()

    def fields(self, editor):
        form = editor.layout()
        return [form.itemAt(i, QtWidgets.QFormLayout.FieldRole).widget() for i in range(form.rowCount())]

    def test_one_left_margin_per_section_and_the_same_width_for_the_n_and_the_ground_button(self):
        # Decision 7 of #64 (points 2, 3 and 7): with the sections unfolded and laid out, the controls of a section
        # start at the same x (with respect to the group), also when the class or the rotor change.
        self.g.show()
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        for sec in (self.g.sec_deficit, self.g.sec_blockage):
            sec.setExpanded(True)
        for deficit, rotor in (("BastankhahGaussianDeficit", "CGIRotorAvg"), ("NiayifarGaussianDeficit", "EqGridRotorAvg"),
                               ("TurboGaussianDeficit", "CGIRotorAvg")):
            with self.subTest(deficit=deficit, rotor=rotor):
                self.choose(cat.DEFICIT, deficit)
                self.choose(cat.ROTOR, rotor)
                self.choose(cat.GROUND, "Mirror")
                QtWidgets.QApplication.processEvents()
                deficit_x = {self.x(self.g.combo[cat.ROTOR]), self.x(self.g.combo[cat.GROUND])}
                deficit_x |= {self.x(w) for w in self.fields(self.g.deficit_editor) if w is not None}
                self.assertEqual(len(deficit_x), 1, deficit_x)
                blockage_x = {self.x(self.g.combo[cat.BLOCKAGE_SUPERPOSITION])}
                blockage_x |= {self.x(w) for e in (self.g.blockage_editor, self.g.args_editor(cat.BLOCKAGE))
                               for w in self.fields(e) if w is not None}
                self.assertEqual(len(blockage_x), 1, blockage_x)
                n = self.g.rotor_editor.control("n")
                self.assertEqual(n.width(), self.g.btn_ground.width())
                self.assertGreaterEqual(self.g.btn_ground.width(), self.g.btn_ground.sizeHint().width())  # it fits
                self.assertGreaterEqual(n.width(), n.sizeHint().width())
        # Marked, the button keeps its width (it was measured with its mark), and neither it nor the n moves.
        n = self.g.rotor_editor.control("n")
        before = (self.x(n), self.x(self.g.btn_ground), self.x(self.g.combo[cat.ROTOR]), self.x(self.g.combo[cat.GROUND]))
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        QtWidgets.QApplication.processEvents()
        self.assertTrue(self.g.btn_ground.text().startswith("⚠"))
        self.assertEqual((self.x(n), self.x(self.g.btn_ground), self.x(self.g.combo[cat.ROTOR]),
                          self.x(self.g.combo[cat.GROUND])), before)
        self.assertEqual(n.width(), self.g.btn_ground.width())
        self.assertGreaterEqual(self.g.btn_ground.width(), self.g.btn_ground.sizeHint().width())
        self.assertGreaterEqual(n.width(), n.sizeHint().width())
        self.g.hide()

    def test_the_nested_rotor_and_ground_of_the_blockage_and_of_the_turbulence_as_wide(self):
        # QGIS tests of #64 (QG1): in «Parámetros del bloqueo» the n of a nested rotor was 298 px, the button of its
        # ground 240 and the selector narrow, with a gap after the label n. As in the line of the rotor of the deficit:
        # the n and the buttons as wide as the button of the ground of the deficit, the selector taking the rest.
        self.g.show()
        self.g.resize(1000, 900)
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        for sec in (self.g.sec_deficit, self.g.sec_blockage, self.g.sec_turbulence):
            sec.setExpanded(True)
        width = self.g.btn_ground.width()
        for rotor in ("CGIRotorAvg", "EqGridRotorAvg"):
            for position in (cat.BLOCKAGE, cat.TURBULENCE):
                with self.subTest(rotor=rotor, position=position):
                    self.pick(self.g.args_editor(position).control("rotorAvgModel"), rotor)
                    if position == cat.BLOCKAGE:
                        self.pick(self.g.args_editor(position).control("groundModel"), "MultiMirror")  # marked
                    QtWidgets.QApplication.processEvents()
                    ed = self.g.args_editor(position)
                    inner = ed._nested["rotorAvgModel"]["inner"]
                    n = inner.control("n")
                    self.assertEqual(n.width(), width)
                    self.assertGreaterEqual(n.width(), n.sizeHint().width())
                    combo = ed.control("rotorAvgModel")
                    # The selector ends where the label n starts: no gap.
                    label = [w for w in inner.findChildren(QtWidgets.QLabel) if w.text() == "n"][0]
                    gap = self.x(label) - (self.x(combo) + combo.width())
                    self.assertLess(gap, 2 * label.sizeHint().width(), gap)
                    if position == cat.BLOCKAGE:
                        button = ed.window_button("groundModel")
                        self.assertTrue(button.text().startswith("⚠"))
                        self.assertEqual(button.width(), width)
                        self.assertGreaterEqual(button.width(), button.sizeHint().width())
        self.g.hide()


class FirstLevelTest(_Case):
    def test_the_selectors_of_the_first_level_start_at_the_same_x(self):
        # Decision 7 of #64 (point 11): the five selectors of the first level, aligned; what goes in their line (the
        # button of the engine, the n of a rotor) stays in it.
        self.g.show()
        for engine in ("All2AllIterative", "PropagateUpDownIterative"):
            with self.subTest(engine=engine):
                self.choose(cat.ENGINE, engine)
                QtWidgets.QApplication.processEvents()
                xs = {self.g.combo[p].mapTo(self.g, QtCore.QPoint(0, 0)).x()
                      for p in (cat.ENGINE, cat.DEFICIT, cat.SUPERPOSITION, cat.BLOCKAGE, cat.TURBULENCE)}
                self.assertEqual(len(xs), 1, xs)
                engine_y = self.g.combo[cat.ENGINE].mapTo(self.g, QtCore.QPoint(0, 0)).y()
                button_y = self.g.btn_engine.mapTo(self.g, QtCore.QPoint(0, 0)).y()
                self.assertLess(abs(engine_y - button_y), self.g.combo[cat.ENGINE].height())
        self.g.hide()


class WindowTest(_Case):
    def a2a_cumulative_with_mirror(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.choose(cat.GROUND, "Mirror")  # it inherits CumulativeWakeSum: R9d

    def test_a_cause_inside_the_window_marks_its_button_and_does_not_open_it(self):
        self.g.show()
        self.a2a_cumulative_with_mirror()
        config = self.g.config()
        self.assertEqual(self.codes(), {"R9d"})
        self.assertTrue(self.g.sec_deficit.isExpanded())  # the section that holds the button
        self.assertTrue(self.g.btn_ground.text().startswith("⚠"))
        self.assertIn("Parámetros del modelo de suelo…", self.g.conflict[cat.DEFICIT].text())  # names the window
        self.assertEqual([w for w in QtWidgets.QApplication.topLevelWidgets()
                          if isinstance(w, ComponentWindow) and w.isVisible()], [])
        self.assertEqual(self.g.config(), config)
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn("CumulativeWakeSum", window.lbl_conflicts.text())  # the same conflict, in the window
        # A sum of its own resolves it; the button follows.
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.g.accept_ground_window(window)
        self.assertEqual(self.codes(), set())
        self.assertFalse(self.g.btn_ground.text().startswith("⚠"))
        self.assertEqual(self.g.config().ground.params["superpositionModel"], C("LinearSum"))
        self.g.hide()

    def test_a_note_of_the_layout_inside_the_window_marks_its_button_in_orange(self):
        # R12 with PropagateDownwind is refused from the second turbine (decision 6.1 of #64): a note, at the deficit
        # and at the window of the ground, in orange; never a barrier.
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.choose(cat.GROUND, "MultiMirror")
        self.assertEqual(self.codes(), set())
        self.assertTrue(self.g.btn_ground.text().startswith("⚠"))
        self.assertIn("b9770e", self.g.btn_ground.styleSheet())
        self.assertIn("Parámetros del modelo de suelo…", self.g.conflict[cat.DEFICIT].text())
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn("MultiMirror sin superposición propia", window.lbl_conflicts.text())
        self.assertIn('<span style="color: #b9770e;">MultiMirror sin superposición propia', window.lbl_conflicts.text())

    def test_the_warnings_of_the_arguments_of_a_ground_mark_its_button(self):
        # Discrete round 1, C1: the warnings whose cause is in the window of a ground (its arguments; SquaredSum as the
        # sum of its own of the ground of the blockage) mark its button in orange and are shown in the window, as those
        # of the engine; at the selector, as before.
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.GROUND, "MultiMirror")
        self.assertEqual(self.codes(), set())
        self.assertTrue(self.g.btn_ground.text().startswith("⚠"))
        self.assertIn("b9770e", self.g.btn_ground.styleSheet())
        self.assertIn("representa cada turbina", self.g.conflict[cat.DEFICIT].text())
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn('<span style="color: #b9770e;">En «suelo · MultiMirror», MultiMirror representa cada turbina',
                      window.lbl_conflicts.text())
        self.choose(cat.GROUND, "Mirror")  # nothing to say: no mark
        self.assertFalse(self.g.btn_ground.text().startswith("⚠"))
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        for ground, own, fragment in (("MultiMirror", None, "representa cada turbina"),
                                      ("Mirror", "SquaredSum", "con SquaredSum en «bloqueo · groundModel")):
            with self.subTest(ground=ground):
                ed = self.g.args_editor(cat.BLOCKAGE)
                self.pick(ed.control("groundModel"), ground)
                if own:
                    window = ed.open_window("groundModel", exec_=False)
                    self.addCleanup(window.deleteLater)
                    self.pick(window.editor.control("superpositionModel"), own)
                    ed.accept_window("groundModel", window)
                ed = self.g.args_editor(cat.BLOCKAGE)
                self.assertEqual(self.codes(), set())
                self.assertTrue(ed.window_button("groundModel").text().startswith("⚠"))
                self.assertIn("b9770e", ed.window_button("groundModel").styleSheet())
                self.assertIn(fragment, self.g.conflict[cat.BLOCKAGE].text())
                window = ed.open_window("groundModel", exec_=False)
                self.addCleanup(window.deleteLater)
                self.assertIn(fragment, window.lbl_conflicts.text())

    def test_a_window_says_its_messages_for_what_is_being_edited(self):
        # Discrete round 1, C2: a change in the window or «Restablecer» says the messages again for what is edited;
        # «Cancelar» changes nothing.
        self.a2a_cumulative_with_mirror()
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn("CumulativeWakeSum", window.lbl_conflicts.text())  # R9d: it inherits CumulativeWakeSum
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.assertTrue(window.lbl_conflicts.isHidden())
        self.assertEqual(window.lbl_conflicts.text(), "")
        window.reset()  # «Heredar» again
        self.assertIn("#c0392b", window.lbl_conflicts.text())
        self.assertFalse(window.lbl_conflicts.isHidden())
        window.reject()
        self.assertEqual(self.codes(), {"R9d"})
        # The window of the engine: a warning of its arguments, before accepting, and gone with «Restablecer».
        engine = self.g.open_engine_window(exec_=False)
        self.addCleanup(engine.deleteLater)
        self.assertNotIn("una sola iteración", engine.lbl_conflicts.text())
        self.pick(engine.editor.control("convergence_tolerance")[1], "none")
        self.assertIn("una sola iteración", engine.lbl_conflicts.text())
        engine.reset()
        self.assertNotIn("una sola iteración", engine.lbl_conflicts.text())
        # The window of the ground of the blockage: R12 (a rotor in the blockage, MultiMirror inheriting) goes with a
        # sum of its own; the warning of MultiMirror stays.
        self.choose(cat.SUPERPOSITION, "LinearSum")
        self.choose(cat.GROUND, wg.NONE)
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        ed = self.g.args_editor(cat.BLOCKAGE)
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        ed = self.g.args_editor(cat.BLOCKAGE)
        self.pick(ed.control("groundModel"), "MultiMirror")
        self.assertEqual(self.codes(), {"R12"})
        ed = self.g.args_editor(cat.BLOCKAGE)
        window = ed.open_window("groundModel", exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn("#c0392b", window.lbl_conflicts.text())
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.assertNotIn("#c0392b", window.lbl_conflicts.text())
        self.assertIn("representa cada turbina", window.lbl_conflicts.text())

    def test_a_window_with_a_field_that_cannot_be_read_leaves_no_messages_of_another_selection(self):
        # Discrete round 2, C: with an unreadable field the messages cannot be said for what is edited; those of the
        # selection before are not left (here R9d, after a sum of its own that takes it away). «Aceptar» waits.
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.choose(cat.GROUND, "MultiMirror")  # it inherits CumulativeWakeSum: R9d
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.assertIn("#c0392b", window.lbl_conflicts.text())
        window.editor.control("mirror_height").setText("x")
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.assertFalse(window.btn_accept.isEnabled())
        self.assertTrue(window.lbl_conflicts.isHidden())
        self.assertNotIn("CumulativeWakeSum", window.lbl_conflicts.text())
        window.editor.control("mirror_height").setText("1000")  # readable again: said for what is edited
        self.assertTrue(window.btn_accept.isEnabled())
        self.assertNotIn("#c0392b", window.lbl_conflicts.text())
        self.assertIn("representa cada turbina", window.lbl_conflicts.text())

    def test_a_new_conflict_inside_a_section_unfolds_it(self):
        # R17 (an overlap as the rotor of STF2017) is a conflict with All2AllIterative: its section unfolds.
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.pick(self.g.args_editor(cat.TURBULENCE).control("rotorAvgModel"), "AreaOverlapAvgModel")
        self.g.sec_turbulence.setExpanded(False)
        self.assertEqual(self.codes(), set())  # with PropagateDownwind, a note
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertEqual(self.codes(), {"R17"})
        self.assertTrue(self.g.sec_turbulence.isExpanded())

    def test_the_window_says_what_is_inherited_and_there_is_no_summary(self):
        # Decision 7 of #64 (points 4, 5 and 15): no grey line next to the button; in the window, under «Heredar»,
        # the sum the ground of the deficit inherits (the superposition of the wakes), and it is still None.
        for ground in ("Mirror", "MultiMirror"):
            for sup in ("LinearSum", "SquaredSum"):
                with self.subTest(ground=ground, sup=sup):
                    self.choose(cat.SUPERPOSITION, sup)
                    self.choose(cat.GROUND, ground)
                    self.assertFalse([w for w in self.g.row[cat.GROUND].findChildren(QtWidgets.QLabel)
                                      if "hereda" in w.text() or w.text().startswith(ground)])
                    window = self.g.open_ground_window(exec_=False)
                    self.addCleanup(window.deleteLater)
                    self.assertFalse(window.lbl_inherit.isHidden())
                    self.assertEqual(window.lbl_inherit.text(), f"Se hereda la superposición de estelas ({sup})")
                    self.pick(window.editor.control("superpositionModel"), "MaxSum")  # a sum of its own: no help
                    self.assertTrue(window.lbl_inherit.isHidden())
                    window.reset()  # back to «Heredar»
                    self.assertFalse(window.lbl_inherit.isHidden())
                    window.reject()  # Cancelar: nothing changes
                    self.assertIsNone(self.g.config().ground.params["superpositionModel"])

    def test_the_window_of_the_ground_of_the_blockage_says_what_it_inherits(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        ed = self.g.args_editor(cat.BLOCKAGE)
        for ground in ("Mirror", "MultiMirror"):
            for bsup in ("LinearSum", "MaxSum"):
                with self.subTest(ground=ground, bsup=bsup):
                    self.choose(cat.BLOCKAGE_SUPERPOSITION, bsup)
                    ed = self.g.args_editor(cat.BLOCKAGE)
                    self.pick(ed.control("groundModel"), ground)
                    window = ed.open_window("groundModel", exec_=False)
                    self.addCleanup(window.deleteLater)
                    self.assertEqual(window.lbl_inherit.text(), f"Se hereda la superposición del bloqueo ({bsup})")
                    self.assertFalse(window.lbl_inherit.isHidden())
                    self.pick(window.editor.control("superpositionModel"), "LinearSum")
                    self.assertTrue(window.lbl_inherit.isHidden())
                    window.reset()
                    self.assertFalse(window.lbl_inherit.isHidden())
                    window.reject()
                    self.assertIsNone(self.g.config().blockage.params["groundModel"].params["superpositionModel"])

    def test_reset_then_cancel_and_an_unreadable_value(self):
        self.choose(cat.GROUND, "MultiMirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("n_reps").setValue(2)
        self.g.accept_ground_window(window)
        draft = self.g.config()
        self.assertEqual(draft.ground.params["n_reps"], 2)
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.reset()
        self.assertEqual(window.value(), cfg.complete(C("MultiMirror")))
        window.reject()  # «Cancelar»: nothing taken
        self.assertEqual(self.g.config(), draft)
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("mirror_height").setText("x")
        self.assertFalse(window.btn_accept.isEnabled())  # an unreadable value is marked here, not accepted
        self.assertIn("border", window.editor.control("mirror_height").styleSheet())
        self.assertEqual(self.g.config(), draft)

    def test_accept_in_a_child_then_cancel_in_its_mother(self):
        # A window inside a window: the ground of a blockage, edited from a window of the blockage itself.
        mother = ComponentWindow(cfg.complete(C("SelfSimilarityDeficit2020", groundModel=C("MultiMirror"))))
        self.addCleanup(mother.deleteLater)
        before = mother.value()
        child = mother.editor.open_window("groundModel", exec_=False)
        self.addCleanup(child.deleteLater)
        child.editor.control("n_reps").setValue(3)
        mother.editor.accept_window("groundModel", child)
        self.assertEqual(mother.value().params["groundModel"].params["n_reps"], 3)
        mother.reject()
        # The mother's caller keeps its value: nothing of the child reaches it without «Aceptar» in the mother.
        self.assertEqual(before.params["groundModel"].params["n_reps"], 0)

    def test_a_conflict_with_an_outer_selector_is_accepted_and_shown_in_the_group(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.choose(cat.GROUND, "Mirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        self.g.accept_ground_window(window)
        self.assertEqual(self.codes(), set())
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        self.pick(window.editor.control("superpositionModel"), "")  # back to inherit: R9d with the outer selectors
        self.assertTrue(window.btn_accept.isEnabled())
        self.g.accept_ground_window(window)
        self.assertEqual(self.codes(), {"R9d"})
        self.assertIn("CumulativeWakeSum", self.g.conflict[cat.DEFICIT].text())

    def test_the_ground_of_the_blockage(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        ed = self.g.args_editor(cat.BLOCKAGE)
        self.pick(ed.control("rotorAvgModel"), "CGIRotorAvg")
        self.pick(ed.control("groundModel"), "MultiMirror")  # without a sum of its own, with a rotor: R12
        self.assertEqual(self.codes(), {"R12"})
        self.assertTrue(ed.window_button("groundModel").text().startswith("⚠"))
        self.assertTrue(self.g.sec_blockage.isExpanded())
        window = ed.open_window("groundModel", exec_=False)
        self.addCleanup(window.deleteLater)
        # The ground of the blockage inherits the blockage superposition, and says so (no summary next to the button),
        # in the row under superpositionModel, above the conflict of the window.
        self.assertEqual(window.lbl_inherit.text(), "Se hereda la superposición del bloqueo (LinearSum)")
        self.assertFalse(window.lbl_inherit.isHidden())
        self.assertIs(window.lbl_inherit.parent(), window.editor)
        self.assertFalse([w for w in ed.findChildren(QtWidgets.QLabel) if "hereda" in w.text() and w.window() is not window])
        self.assertIn("MultiMirror", window.lbl_conflicts.text())
        self.pick(window.editor.control("superpositionModel"), "LinearSum")
        ed.accept_window("groundModel", window)
        self.assertEqual(self.codes(), set())
        self.assertEqual(self.g.config().blockage.params["groundModel"],
                         C("MultiMirror", mirror_height=1000.0, n_reps=0, superpositionModel=C("LinearSum")))


class HelpTest(_Case):
    def test_every_new_option_and_argument_has_its_help_in_four_languages(self):
        g = self.g
        sources = {}
        for a in sub.ARGS:
            text = a.doc or wg.FAMILY_HELP[a.family]
            sources[(a.owner, a.name)] = text
            if a.kind == sub.COMPONENT:
                for o in sub.options(a):
                    key = (a.family, o.name)
                    if key in wg.OPTION_HELP:
                        sources[key] = wg.OPTION_HELP[key]
                    else:
                        self.assertTrue(g._option_help(a, o).strip(), key)  # a help of a selector of the group
        for language in ("en", "fr", "de"):
            table = {**TRANSLATIONS[language], **SUB_TRANSLATIONS[language]}
            for key, text in sources.items():
                with self.subTest(language=language, key=key):
                    self.assertTrue(text.strip())
                    self.assertIn(text, table)
                    self.assertTrue(table[text].strip())  # a quotation of PyWake stays in its English
        for language in ("en", "fr", "de"):
            self.assertEqual(set(SUB_TRANSLATIONS[language]), set(SUB_SOURCES))

    def test_one_help_shown_in_the_group(self):
        with mock.patch.object(i18n, "current_language", return_value="en"):
            g = self.group(tr=i18n.tr_text)
            self.choose(cat.ROTOR, "EqGridRotorAvg", g)
            tip = g.rotor_editor.control("n").toolTip()
            self.assertIn("Minimum −2: from −2 to 0 there are no nodes and PyWake can give NaN; with −3 or less it does not "
                      "build it.", tip)
            self.assertIn("Signature value: 4.", tip)
            self.choose(cat.GROUND, "Mirror", g)
            self.assertEqual(g.btn_ground.text(), "Parameters of the ground model…")


if __name__ == "__main__":
    unittest.main()
