# -*- coding: utf-8 -*-
"""The new «Modelo de estela» group and its mirror in the interactive map, not connected (#46 P5a).

The dialog tests of the plan that belong to the group: filtering by engine (``EngineTest``); the blockage absent
with PropagateDownwind and «Ninguno» by default with All2AllIterative and PropagateUpDownIterative, and its options
absent with «Ninguno» (``BlockageTest``); the mandatory turbulence and the requirements of PUD, with their cause and
resolution (``ConflictTest``); a PyWake refusal shown without changing the selection; the folded sections, and a
conflict inside one unfolding it without changing values; the draft per class and «Restablecer» (``DraftTest``);
the memory between sessions and a stale preference (``SessionTest``); the help of every option and parameter, and
the texts in four languages (``HelpTest``); the interactive map with the same options enabled (``MirrorTest``,
#75 row 1.6).
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
from VelantisWind.ui_core import wake_group as wg  # noqa: E402
from VelantisWind.ui_core.wake_group_translations import SOURCES, TRANSLATIONS  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def enabled(combo, data):
    i = combo.findData(data)
    return combo.model().item(i).isEnabled()


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

    def selection(self, g=None):
        g = g or self.g
        return {p: c.currentData() for p, c in g.combo.items()}

    def codes(self, g=None):
        return {i.code for i in (g or self.g).issues()}


class EngineTest(_Case):
    def test_the_default_is_the_signature_physics(self):
        self.assertEqual(self.g.config(), cfg.default_config())
        self.assertEqual(self.g.issues(), [])

    def test_with_pud_the_classes_without_use_effective_ws_are_disabled(self):
        for engine in ("PropagateDownwind", "All2AllIterative"):
            self.choose(cat.ENGINE, engine)
            self.assertTrue(all(enabled(self.g.combo[cat.DEFICIT], e.option) for e in cat.entries(cat.DEFICIT)))
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        for e in cat.entries(cat.DEFICIT):
            self.assertEqual(enabled(self.g.combo[cat.DEFICIT], e.option), "use_effective_ws" in e.params, e.name)
        i = self.g.combo[cat.DEFICIT].findData("NOJDeficit")
        self.assertIn("no tiene use_effective_ws", self.g.combo[cat.DEFICIT].itemData(i, QtCore.Qt.ToolTipRole))

    def test_changing_the_engine_never_changes_a_choice(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.DEFICIT, "NOJDeficit")
        before = self.selection()
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        after = self.selection()
        self.assertEqual(after.pop(cat.ENGINE), "PropagateUpDownIterative")
        before.pop(cat.ENGINE)
        self.assertEqual(after, before)  # NOJ stays chosen, disabled and in conflict
        self.assertIn("R3", self.codes())
        self.assertIn("NOJDeficit no tiene use_effective_ws", self.g.conflict[cat.DEFICIT].text())


class BlockageTest(_Case):
    def test_absent_with_pdw_and_none_by_default(self):
        self.g.show()
        self.assertFalse(self.g.row[cat.BLOCKAGE].isVisible())
        for engine in ("All2AllIterative", "PropagateUpDownIterative"):
            self.choose(cat.ENGINE, engine)
            self.assertTrue(self.g.row[cat.BLOCKAGE].isVisible())
            self.assertEqual(self.g.combo[cat.BLOCKAGE].currentData(), wg.NONE)
            self.assertFalse(self.g.sec_blockage.isVisible())  # no options under «Ninguno»
        self.g.hide()

    def test_the_blockage_options_and_its_superposition(self):
        self.g.show()
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.assertTrue(self.g.sec_blockage.isVisible())
        self.assertFalse(self.g.sec_blockage.isExpanded())
        config = self.g.config()
        self.assertEqual(config.blockage, cfg.blockage_signature("SelfSimilarityDeficit2020"))
        self.assertEqual(config.blockage_superposition, cfg.Component("LinearSum", {}))
        for name in ("WeightedSum", "CumulativeWakeSum"):  # R6, with its frontier: PUD calculates with one turbine
            self.assertTrue(enabled(self.g.combo[cat.BLOCKAGE_SUPERPOSITION], name))
        self.assertTrue(enabled(self.g.combo[cat.BLOCKAGE_SUPERPOSITION], "MaxSum"))
        # The other parameters of the blockage, with their signature, in its options (#64).
        editor = self.g.args_editor(cat.BLOCKAGE)
        self.assertEqual(editor.control("ss_alpha").text(), "0.8888888888888888")
        self.assertEqual([e.text() for e in editor.control("r12p")[1]], ["-0.672", "0.4897"])  # one field each
        self.assertFalse(editor.isVisibleTo(self.g))  # folded
        # Back to PDW (decision 7 of #64): the blockage is not shown and the configuration has none; its choice and
        # its draft come back with an engine that takes it.
        editor.control("ss_alpha").setText("0.7")
        self.choose(cat.ENGINE, "PropagateDownwind")
        config = self.g.config()
        self.assertIsNone(config.blockage)
        self.assertIsNone(config.blockage_superposition)
        self.assertEqual(self.codes(), set())
        self.assertFalse(self.g.row[cat.BLOCKAGE].isVisible())
        self.assertFalse(self.g.sec_blockage.isVisible())
        for engine in ("All2AllIterative", "PropagateUpDownIterative"):
            self.choose(cat.ENGINE, engine)
            self.assertEqual(self.g.combo[cat.BLOCKAGE].currentData(), "SelfSimilarityDeficit2020")
            self.assertEqual(self.g.config().blockage.params["ss_alpha"], 0.7)
            self.assertTrue(self.g.row[cat.BLOCKAGE].isVisible())
        self.g.hide()

    def test_the_parameters_of_the_superposition_and_the_turbulence(self):
        # Edited (#64), in folded sections that appear only when there is something.
        self.g.show()
        self.assertFalse(self.g.sec_superposition.isVisible())  # LinearSum has no parameters
        self.assertFalse(self.g.sec_turbulence.isVisible())  # no turbulence
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.assertTrue(self.g.sec_superposition.isVisible())
        self.assertFalse(self.g.sec_superposition.isExpanded())
        editor = self.g.args_editor(cat.SUPERPOSITION)
        self.assertEqual({n: editor.control(n).text() for n in ("delta", "max_err", "max_iter", "weight_limit")},
                         {"delta": "0.01", "max_err": "0.001", "max_iter": "5", "weight_limit": "10000000000"})
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.assertTrue(self.g.sec_turbulence.isVisible())
        self.assertFalse(self.g.sec_turbulence.isExpanded())
        editor = self.g.args_editor(cat.TURBULENCE)
        self.assertEqual(editor.control("addedTurbulenceSuperpositionModel").currentData(), "LinearSum")
        self.assertFalse(editor.isVisibleTo(self.g))  # folded
        self.g.hide()

    def test_the_notes_without_blockage(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertIn("PropagateDownwind y menor coste", self.g.conflict[cat.ENGINE].text())
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.assertFalse(self.g.conflict[cat.ENGINE].text())
        self.assertEqual(self.g.issues(), [])  # a note is not a conflict


class ConflictTest(_Case):
    def test_the_mandatory_turbulence(self):
        self.choose(cat.DEFICIT, "ZongGaussianDeficit")
        self.assertEqual(self.codes(), {"R2"})
        text = self.g.conflict[cat.TURBULENCE].text()
        self.assertIn("PyWake exige un modelo de turbulencia", text)  # the cause
        self.assertIn("Elige una turbulencia", text)  # and the resolution
        self.assertEqual(self.g.combo[cat.TURBULENCE].currentData(), wg.NONE)  # nothing chosen by itself
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        self.assertEqual(self.g.issues(), [])
        self.assertFalse(self.g.conflict[cat.TURBULENCE].isVisibleTo(self.g))

    def test_a_turbulence_that_does_not_change_the_deficit(self):
        # Decision 16 (#75, row 3.15): calculated, but the deficit does not use it; a note, not a conflict.
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        for deficit, says in (("TurboGaussianDeficit", True), ("BastankhahGaussianDeficit", True),
                              ("NiayifarGaussianDeficit", False)):
            with self.subTest(deficit=deficit):
                self.choose(cat.DEFICIT, deficit)
                self.assertEqual(self.g.issues(), [])
                text = self.g.conflict[cat.TURBULENCE].text()
                self.assertEqual("no cambia el déficit" in text, says)
                if says:
                    self.assertIn(deficit, text)
        # Niayifar with use_effective_ti unchecked: the deficit uses the ambient TI, and the note says so.
        self.g.deficit_editor.set_values({"use_effective_ti": False})
        self.assertIn("no cambia el déficit", self.g.conflict[cat.TURBULENCE].text())
        self.choose(cat.TURBULENCE, wg.NONE)
        self.assertFalse(self.g.conflict[cat.TURBULENCE].text())

    def test_the_note_of_the_turbulence_reads_use_effective_ti_as_the_result(self):
        # One predicate for the dialog and the persistent warning of the result (decision 6.6 of #64): as PyWake reads
        # it, 1 is true and 0 false (Q5c accepts them through the API).
        from VelantisWind.ag_core.wake_setup import notices
        from tests.test_wake_setup_factory import C, with_
        base = with_(cfg.default_config("PropagateDownwind", "NiayifarGaussianDeficit"),
                     turbulence=C("STF2017TurbulenceModel"))
        # As PyWake picks its key, ['TI_ilk', 'TI_eff_ilk'][use_effective_ti] (deficit_model.py:21).
        for value, says in ((1, False), (0, True), (True, False), (False, True), (-1, False), (-2, True)):
            with self.subTest(use_effective_ti=value):
                config = with_(base, deficit=C("NiayifarGaussianDeficit",
                                               **dict(base.deficit.params, use_effective_ti=value)))
                self.assertEqual(notices.turbulence_without_effect(config), says)
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.choose(cat.TURBULENCE, "STF2017TurbulenceModel")
        with mock.patch.object(wg._notices, "turbulence_without_effect", return_value=True):
            self.g.deficit_editor.set_values({"use_effective_ti": True})  # a refresh
            self.assertIn("no cambia el déficit", self.g.conflict[cat.TURBULENCE].text())

    def test_pud_requires_the_effective_speed_and_unfolds_its_section(self):
        self.assertFalse(self.g.sec_deficit.isExpanded())
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        params_before = dict(self.g.config().deficit.params)
        self.assertEqual(self.codes(), {"R3"})
        self.assertTrue(self.g.sec_deficit.isExpanded())  # the control that resolves it is shown
        self.assertIn("Marca use_effective_ws", self.g.conflict[cat.DEFICIT].text())
        self.assertEqual(dict(self.g.config().deficit.params), params_before)  # unchanged
        self.g.deficit_editor.set_values({"use_effective_ws": True})
        self.assertEqual(self.g.issues(), [])
        # And its blockage, inside «Parámetros del bloqueo».
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.assertFalse(self.g.config().blockage.params["use_effective_ws"])
        self.assertEqual(self.codes(), {"R4"})
        self.assertTrue(self.g.sec_blockage.isExpanded())
        self.assertIn("en los parámetros del bloqueo", self.g.conflict[cat.BLOCKAGE].text())
        self.g.blockage_editor.set_values({"use_effective_ws": True})
        self.assertEqual(self.g.issues(), [])

    def test_r9f_is_a_note_at_the_blockage(self):
        # R9f depends on the number of turbines, checked when calculating: here a note, never a barrier.
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.g.deficit_editor.set_values({"use_effective_ws": True})
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.blockage_editor.set_values({"use_effective_ws": True})
        before = self.selection()
        self.assertTrue(enabled(self.g.combo[cat.BLOCKAGE_SUPERPOSITION], "MaxSum"))
        self.choose(cat.BLOCKAGE_SUPERPOSITION, "MaxSum")
        self.assertEqual(self.g.issues(), [])
        note = self.g.conflict[cat.BLOCKAGE].text()
        self.assertIn("MaxSum como superposición del bloqueo", note)
        self.assertIn("se detiene desde la segunda turbina", note)
        self.assertEqual(self.selection(), dict(before, blockage_superposition="MaxSum"))
        self.choose(cat.BLOCKAGE_SUPERPOSITION, "LinearSum")
        self.assertNotIn("MaxSum como superposición del bloqueo", self.g.conflict[cat.BLOCKAGE].text())

    def test_the_cumulative_warning_follows_the_selection(self):
        # Decision 23(a): under «Superposición de estelas», what this configuration leaves without effect.
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        text = self.g.conflict[cat.SUPERPOSITION].text()
        self.assertIn("orden de las turbinas", text)
        self.assertIn("por esta ruta: ct2a, use_effective_ws.", text)
        self.choose(cat.GROUND, "Mirror")
        self.assertIn("por esta ruta: ct2a, use_effective_ws, groundModel (Mirror: superpositionModel).",
                      self.g.conflict[cat.SUPERPOSITION].text())
        self.assertEqual(self.g.issues(), [])  # a warning, never a barrier
        self.choose(cat.SUPERPOSITION, "LinearSum")
        self.assertFalse(self.g.conflict[cat.SUPERPOSITION].text())

    def test_the_downstream_blockage_warning_of_pud(self):
        # Decision 23(c): under «Bloqueo», in orange, never a barrier.
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.g.deficit_editor.set_values({"use_effective_ws": True})
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.blockage_editor.set_values({"use_effective_ws": True})
        self.assertNotIn("omite el bloqueo aguas abajo", self.g.conflict[cat.BLOCKAGE].text())
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.assertIn("omite el bloqueo aguas abajo", self.g.conflict[cat.BLOCKAGE].text())
        self.assertEqual(self.g.issues(), [])

    def test_the_warning_of_an_edited_engine_argument(self):
        # #64, Q2: shown at the engine, never a barrier (the controls come with Q3).
        self.choose(cat.ENGINE, "All2AllIterative")
        with mock.patch.object(self.g, "_manual_config", return_value=cfg.WakeConfig(**{  # what _refresh reads
                **cfg.default_config("All2AllIterative").__dict__,
                "engine": cfg.Component("All2AllIterative", {"convergence_tolerance": None})})):
            self.g._refresh()
        self.assertIn("una sola iteración", self.g.conflict[cat.ENGINE].text())

    def test_the_help_of_zong_ctlim_says_it_is_not_used(self):
        self.choose(cat.DEFICIT, "ZongGaussianDeficit")
        self.choose(cat.TURBULENCE, "CrespoHernandez")
        self.assertIn("no lo usa en el cálculo", self.g.deficit_editor.control("ctlim").toolTip())

    def test_a_refusal_is_shown_without_changing_the_selection(self):
        self.choose(cat.DEFICIT, "GCLDeficit")
        before = self.selection()
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.assertEqual(self.codes(), {"R7"})
        self.assertIn("ConvectionDeficitModel", self.g.conflict[cat.SUPERPOSITION].text())
        self.assertEqual(self.selection(), dict(before, superposition="WeightedSum"))

    def test_a_conflict_of_the_rotor_is_shown_at_the_deficit_and_unfolds(self):
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.assertFalse(self.g.sec_deficit.isExpanded())
        self.choose(cat.DEFICIT, "NOJDeficit")  # its signature rotor, AreaOverlapAvgModel, is not by nodes (R8)
        self.assertIn("R8", self.codes())
        self.assertTrue(self.g.sec_deficit.isExpanded())
        self.assertIn("promedios de rotor por nodos", self.g.conflict[cat.DEFICIT].text())
        self.assertEqual(self.g.combo[cat.ROTOR].currentData(), "AreaOverlapAvgModel")

    def test_an_unreadable_field_is_a_conflict_not_a_value(self):
        self.g.deficit_editor.control("k").setText("0,03x")
        self.assertIsNone(self.g.config())
        self.assertEqual(self.codes(), {"field"})
        self.assertIn("«k»", self.g.conflict[cat.DEFICIT].text())
        self.g.deficit_editor.control("k").setText("0,031")
        self.assertEqual(self.g.config().deficit.params["k"], 0.031)

    def test_a_class_the_installation_does_not_have(self):
        real = cat.resolve_class

        def missing(e):
            if e.name in ("ZongGaussianDeficit", "VortexDipole"):
                raise cat.ClassUnavailable("La instalación de PyWake no tiene la clase " + e.name)
            return real(e)
        with mock.patch.object(cat, "resolve_class", side_effect=missing):
            self.choose(cat.DEFICIT, "ZongGaussianDeficit")  # no exception
            self.assertIsNone(self.g.config())
            self.assertEqual([(i.code, i.origin) for i in self.g.issues()], [("R14", "environment")])
            self.assertIn("no tiene la clase ZongGaussianDeficit", self.g.conflict[cat.DEFICIT].text())
            self.assertIsNone(self.g.deficit_editor)
            self.choose(cat.ENGINE, "All2AllIterative")
            self.choose(cat.BLOCKAGE, "VortexDipole")
            self.assertEqual(len(self.g.issues()), 2)
            again = self.group()  # the remembered choices, restored without an exception
            self.assertIn("no tiene la clase ZongGaussianDeficit", again.conflict[cat.DEFICIT].text())
            self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
            self.choose(cat.BLOCKAGE, wg.NONE)
            self.assertEqual(self.g.issues(), [])

    def test_an_engine_the_installation_does_not_have(self):
        self.choose(cat.ENGINE, "PropagateUpDownIterative")  # remembered for the next group
        real = cat.resolve_class

        def missing(e):
            if e.name == "PropagateUpDownIterative":
                raise cat.ClassUnavailable("La instalación de PyWake no tiene la clase " + e.name)
            return real(e)
        with mock.patch.object(cat, "resolve_class", side_effect=missing):
            again = self.group()  # the remembered engine, restored without an exception
            self.assertIsNone(again.config())
            self.assertEqual([(i.code, i.position, i.origin) for i in again.issues()],
                             [("R14", cat.ENGINE, "environment")])
            self.assertIn("no tiene la clase PropagateUpDownIterative", again.conflict[cat.ENGINE].text())
            self.choose(cat.ENGINE, "PropagateDownwind", again)  # an installed engine resolves it
            self.assertEqual(again.issues(), [])
            self.assertIsNotNone(again.config())

    def test_the_sections_are_folded_by_default(self):
        for sec in (self.g.sec_deficit, self.g.sec_blockage):
            self.assertFalse(sec.isExpanded())


class DraftTest(_Case):
    def test_a_draft_per_class_that_the_engine_does_not_touch(self):
        self.g.deficit_editor.control("k").setText("0.05")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.assertEqual(self.g.config().deficit, cfg.deficit_signature("NiayifarGaussianDeficit")[0])
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.assertEqual(self.g.config().deficit.params["k"], 0.05)
        self.assertEqual(self.g.deficit_editor.control("k").text(), "0.05")

    def test_an_unreadable_text_comes_back_with_its_class(self):
        self.g.deficit_editor.control("k").setText("0,03x")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.assertIsNotNone(self.g.config())
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.assertEqual(self.g.deficit_editor.control("k").text(), "0,03x")
        self.assertEqual(self.codes(), {"field"})
        self.g.btn_reset_section[cat.DEFICIT].click()
        self.assertEqual(self.g.config(), cfg.default_config())

    def test_the_rotor_and_ground_of_each_class(self):
        self.choose(cat.DEFICIT, "TurboGaussianDeficit")
        self.assertEqual(self.g.combo[cat.GROUND].currentData(), "Mirror")  # its signature
        self.choose(cat.GROUND, wg.NONE)
        self.choose(cat.ROTOR, "CGIRotorAvg")
        n = self.g.rotor_editor.control("n")
        n.setCurrentIndex(n.findData(9))
        self.choose(cat.DEFICIT, "BastankhahGaussianDeficit")
        self.assertEqual(self.g.combo[cat.GROUND].currentData(), wg.NONE)
        self.choose(cat.DEFICIT, "TurboGaussianDeficit")
        config = self.g.config()
        self.assertIsNone(config.ground)
        self.assertEqual(config.rotor, cfg.Component("CGIRotorAvg", {"n": 9}))

    def test_reset_goes_back_to_the_signature_and_keeps_the_engine(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.DEFICIT, "NOJDeficit")
        self.g.deficit_editor.control("k").setText("0.04")
        self.choose(cat.ROTOR, wg.NONE)
        self.g.btn_reset_section[cat.DEFICIT].click()
        config = self.g.config()
        sig, rotor, ground = cfg.deficit_signature("NOJDeficit")
        self.assertEqual((config.deficit, config.rotor, config.ground), (sig, rotor, ground))
        self.assertEqual(config.engine.name, "All2AllIterative")
        self.assertEqual(self.g.deficit_editor.control("k").text(), repr(sig.params["k"]))

    def test_the_reset_of_the_blockage_puts_it_back_to_its_signature(self):
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.blockage_editor.set_values({"use_effective_ws": True})
        self.choose(cat.BLOCKAGE_SUPERPOSITION, "MaxSum")
        self.g.btn_reset_section[cat.BLOCKAGE].click()
        config = self.g.config()
        self.assertEqual(config.blockage, cfg.blockage_signature("SelfSimilarityDeficit2020"))
        self.assertEqual(config.blockage_superposition, cfg.Component("LinearSum", {}))
        self.assertEqual((config.engine.name, self.g.combo[cat.BLOCKAGE].currentData()),
                         ("PropagateUpDownIterative", "SelfSimilarityDeficit2020"))
        self.assertEqual(self.g.blockage_editor.values(), {"use_effective_ws": False})


class SessionTest(_Case):
    def test_the_choices_are_remembered_with_the_signature_values(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        self.g.deficit_editor.control("ceps").setText("0.3")
        self.choose(cat.SUPERPOSITION, "SquaredSum")
        self.choose(cat.TURBULENCE, "CrespoHernandez")
        self.choose(cat.BLOCKAGE, "VortexDipole")
        again = self.group()
        config = again.config()
        self.assertEqual((config.engine.name, config.deficit.name, config.superposition.name, config.turbulence.name,
                          config.blockage.name), ("All2AllIterative", "NiayifarGaussianDeficit", "SquaredSum",
                                                  "CrespoHernandez", "VortexDipole"))
        self.assertEqual(config.deficit, cfg.deficit_signature("NiayifarGaussianDeficit")[0])  # edits not kept
        self.assertFalse(again.lbl_preferences.text())

    def test_a_stale_preference_is_said(self):
        self.settings.setValue(wg.SETTINGS_PREFIX + cat.DEFICIT, "TurboParkDeficit")
        self.settings.setValue(wg.SETTINGS_PREFIX + cat.SUPERPOSITION, "AUTO")
        again = self.group()
        self.assertEqual(again.config(), cfg.default_config())
        text = again.lbl_preferences.text()
        self.assertIn("«TurboParkDeficit»", text)
        self.assertIn("«AUTO»", text)
        self.assertIn("ya no es una opción", text)


class HelpTest(_Case):
    def test_every_option_and_parameter_has_help(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        for position, combo in self.g.combo.items():
            for i in range(combo.count()):
                self.assertTrue(str(combo.itemData(i, QtCore.Qt.ToolTipRole) or "").strip(), (position, i))
        for e in cat.entries(cat.DEFICIT):
            self.choose(cat.DEFICIT, e.option)
            for p in e.params:
                c = self.g.deficit_editor.control(p)
                w = c[0] if isinstance(c, tuple) else c
                self.assertTrue(w.toolTip().strip(), (e.name, p))

    def test_the_help_of_the_arguments_that_change_what_the_deficit_uses(self):
        self.choose(cat.DEFICIT, "NiayifarGaussianDeficit")
        for p in ("ct2a", "use_effective_ws", "use_effective_ti"):
            tip = self.g.deficit_editor.control(p).toolTip()
            self.assertIn(cat.PARAM_HELP[p], tip)
            self.assertIn("Niayifar_PorteAgel_2016, con a = [0,3837; 0,003678], ct2a_mom1d, velocidad efectiva", tip)
        self.assertIn("PropagateUpDownIterative exige True", self.g.deficit_editor.control("use_effective_ws").toolTip())
        self.assertEqual(self.g.deficit_editor.control("ceps").toolTip(),
                         "ceps (PyWake). Valor de la firma: 0.2.")
        self.assertEqual(self.g.combo[cat.DEFICIT].toolTip(), cat.OUT_OF_CATALOGUE)

    def test_the_help_of_the_blockage_use_effective_ws(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        tip = self.g.blockage_editor.control("use_effective_ws").toolTip()
        self.assertIn("el bloqueo escala con la velocidad efectiva", tip)
        self.assertNotIn("el déficit", tip)

    def test_the_texts_of_the_group_in_four_languages(self):
        for lang in ("en", "fr", "de"):
            self.assertEqual(set(TRANSLATIONS[lang]), set(SOURCES))
            self.assertTrue(all(TRANSLATIONS[lang][s].strip() and TRANSLATIONS[lang][s] != s for s in SOURCES), lang)
        for text in (list(wg.NONE_HELP.values()) + list(wg.NOTES_WITHOUT_BLOCKAGE.values())
                     + list(wg.FAMILY_HELP.values()) + list(wg.OPTION_HELP.values())
                     + list(wg.SPIN_MINIMUM_HELP.values()) + [
                         wg.PUD_REFUSED, wg.STALE_PREFERENCE, wg.BLOCKAGE_PARAM_HELP["use_effective_ws"], wg.UNREADABLE,
                         wg.EXCLUDED_ARG, wg.SIGNATURE_VALUE, wg.WINDOW_CONFLICT]):
            self.assertIn(text, SOURCES)

    def test_shown_translated(self):
        with mock.patch.object(i18n, "current_language", return_value="en"):
            g = self.group(tr=i18n.tr_text)
            self.assertEqual(g.title(), "Wake model")
            self.choose(cat.DEFICIT, "ZongGaussianDeficit", g)
            self.assertIn("requires a turbulence model", g.conflict[cat.TURBULENCE].text())
            i = g.combo[cat.ENGINE].findData("PropagateDownwind")
            self.assertIn("Does not support blockage", g.combo[cat.ENGINE].itemData(i, QtCore.Qt.ToolTipRole))


class LabelsTest(_Case):
    def test_no_label_of_the_group_nor_of_the_map_has_a_colon(self):
        # Decision 7 of #64 (points 6, 8 and 12): «Parámetros del bloqueo», «Superposición» inside it, no colons.
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        labels = [w.text() for w in self.g.findChildren(QtWidgets.QLabel) if w.text() and w.parent() in
                  [self.g.row[p] for p in self.g.row]]
        self.assertTrue(labels)
        self.assertFalse([t for t in labels if t.endswith(":")], labels)
        self.assertEqual(self.g.sec_blockage.header.text(), "Parámetros del bloqueo")
        bsup = [w.text() for w in self.g.row[cat.BLOCKAGE_SUPERPOSITION].findChildren(QtWidgets.QLabel)]
        self.assertIn("Superposición", bsup)
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        m = wg.WakeGroupMirror(self.g, QtWidgets.QFormLayout(holder))
        self.assertFalse([l.text() for l in m.labels.values() if l.text().endswith(":")])
        # Outside the group, the report keeps the whole name.
        from VelantisWind.ag_core.results.model_config_html import model_config_html
        html = model_config_html({"wake_config": {"selected": {}, "executed": {}}})
        self.assertIn(">Superposición del bloqueo<", html)


class BlockageWithPdwTest(_Case):
    def test_an_unreadable_field_of_the_hidden_blockage_does_not_count(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        self.g.args_editor(cat.BLOCKAGE).control("ss_alpha").setText("0,7x")
        self.assertEqual(self.codes(), {"field"})
        self.choose(cat.ENGINE, "PropagateDownwind")
        self.assertEqual(self.codes(), set())
        self.assertIsNotNone(self.g.config())
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertEqual(self.codes(), {"field"})  # it is still there

    def test_reopened_with_pdw_and_a_remembered_blockage(self):
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "VortexDipole")
        self.choose(cat.ENGINE, "PropagateDownwind")
        again = self.group()
        self.assertEqual(again.combo[cat.ENGINE].currentData(), "PropagateDownwind")
        self.assertIsNone(again.config().blockage)
        self.assertEqual(again.issues(), [])
        self.choose(cat.ENGINE, "All2AllIterative", again)
        self.assertEqual(again.config().blockage, cfg.blockage_signature("VortexDipole"))  # with its signature

    def test_the_engine_changed_from_the_mirror(self):
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        m = wg.WakeGroupMirror(self.g, QtWidgets.QFormLayout(holder))
        holder.show()
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.BLOCKAGE, "SelfSimilarityDeficit2020")
        m.combo[cat.ENGINE].setCurrentIndex(m.combo[cat.ENGINE].findData("PropagateDownwind"))
        self.assertEqual(self.g.combo[cat.ENGINE].currentData(), "PropagateDownwind")
        self.assertIsNone(self.g.config().blockage)
        self.assertFalse(m.combo[cat.BLOCKAGE].isVisibleTo(holder))
        self.assertNotIn("PropagateDownwind no admite bloqueo", said(m))
        holder.hide()


from VelantisWind.ui_core.wake_controls import coloured_lines  # noqa: E402


def said(mirror):
    """Every note of the map, in its order."""
    return "<br>".join(n.text() for n in [mirror.lbl_preferences] + list(mirror.notes.values()) if n.text())


class ColoursTest(_Case):
    RED, ORANGE = "#c0392b", "#b9770e"

    @staticmethod
    def lines(html):
        """``(colour, text)`` of each line of a note, in its order."""
        import re
        from html import unescape
        return [(c, unescape(t)) for c, t in re.findall(r'<span style="color: (#[0-9a-f]{6});">(.*?)</span>', html)]

    def mirrored(self):
        """What the map shows under each selector: the note of the group under it, whole, or nothing."""
        return {p: self.g.conflict[p].text() if self.g.conflict[p].isVisibleTo(self.g) else ""
                for p in wg.SHOWN_POSITIONS}

    def test_a_conflict_in_red_and_a_warning_in_orange_in_the_same_note(self):
        # Decision 7 of #64 (point 13): under «Déficit de estela», the conflict of WeightedSum with a ground (R9, with
        # All2AllIterative) and the warnings of MultiMirror, each in its colour, all of them and in their order; the
        # map has the same lines.
        from VelantisWind.ag_core.wake_setup import notices
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        m = wg.WakeGroupMirror(self.g, QtWidgets.QFormLayout(holder))
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.GROUND, "MultiMirror")
        self.assertEqual(self.codes(), {"R9"})
        config = self.g.config()
        expected = ([(self.RED, i.text) for i in self.g.issues() if i.position in (cat.DEFICIT, cat.GROUND, cat.ROTOR)]
                    + [(self.ORANGE, str(w)) for w in notices.argument_warnings(config)[cat.DEFICIT]])
        self.assertEqual(len(expected), 3)  # R9 and two warnings of MultiMirror
        self.assertEqual(self.lines(self.g.conflict[cat.DEFICIT].text()), expected)
        self.assertEqual(self.g.conflict[cat.DEFICIT].text(),
                         coloured_lines([t for c, t in expected if c == self.RED],
                                        [t for c, t in expected if c == self.ORANGE]))  # whole, with its separators
        self.assertEqual({p: n.text() for p, n in m.notes.items()}, self.mirrored())

    def test_a_note_of_the_layout_is_orange_and_a_conflict_hides_it(self):
        # With PropagateDownwind, R9 is a note of the layout (orange), also in the map. A conflict (what fails with any
        # layout) is an earlier stage: the notes of the layout wait for it (decision 6.1 of #64), so they never share
        # a note.
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        m = wg.WakeGroupMirror(self.g, QtWidgets.QFormLayout(holder))
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.GROUND, "Mirror")
        self.assertEqual(self.codes(), set())
        from VelantisWind.ag_core.wake_setup import validation as val
        r9 = [i for i in val.layout_issues(self.g.config()) if i.code == "R9"][0]
        self.assertEqual(self.g.conflict[cat.DEFICIT].text(), coloured_lines([], [r9.text]))
        self.assertEqual({p: n.text() for p, n in m.notes.items()}, self.mirrored())
        self.assertEqual(m.notes[cat.DEFICIT].text(), self.g.conflict[cat.DEFICIT].text())  # under its selector
        self.choose(cat.ENGINE, "All2AllIterative")  # now a conflict, in red
        self.assertEqual([c for c, _t in self.lines(self.g.conflict[cat.DEFICIT].text())], [self.RED])

    def test_the_lines_of_the_windows_of_the_ground_and_of_the_engine(self):
        # The real windows: the ground with a conflict (R9d, red) and with a note of the layout (R12 with PDW, orange);
        # the engine with a warning of its arguments (orange).
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.choose(cat.GROUND, "Mirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        r9d = [i for i in self.g.issues() if i.code == "R9d"]
        self.assertEqual(self.lines(window.lbl_conflicts.text()), [(self.RED, r9d[0].text)])
        self.choose(cat.ENGINE, "PropagateDownwind")
        self.choose(cat.SUPERPOSITION, "LinearSum")
        self.choose(cat.ROTOR, "CGIRotorAvg")
        self.choose(cat.GROUND, "MultiMirror")
        window = self.g.open_ground_window(exec_=False)
        self.addCleanup(window.deleteLater)
        from VelantisWind.ag_core.wake_setup import notices, validation as val
        r12 = [i for i in val.layout_issues(self.g.config()) if i.code == "R12"][0]
        # Then the warnings of the arguments of MultiMirror, in orange too (discrete round 1, C1).
        mm = [str(w) for w in notices.ground_window_warnings(self.g.config())[cat.GROUND]]
        self.assertTrue(mm)
        self.assertEqual(self.lines(window.lbl_conflicts.text()),
                         [(self.ORANGE, r12.text)] + [(self.ORANGE, t) for t in mm])
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.ROTOR, wg.NONE)
        w = self.g.open_engine_window(exec_=False)
        self.addCleanup(w.deleteLater)
        w.editor.control("convergence_tolerance")[1].setCurrentIndex(
            w.editor.control("convergence_tolerance")[1].findData("none"))
        self.g.accept_engine_window(w)
        shown = self.g.open_engine_window(exec_=False)
        self.addCleanup(shown.deleteLater)
        warnings_ = [str(w) for w in notices.argument_warnings(self.g.config())[cat.ENGINE]]
        self.assertTrue(any("una sola iteración" in w for w in warnings_))
        self.assertEqual(shown.lbl_conflicts.text(), coloured_lines([], warnings_))

    def test_a_text_is_escaped(self):
        self.assertEqual(coloured_lines(["a <b> & c"], ["d"]),
                         '<span style="color: #c0392b;">a &lt;b&gt; &amp; c</span><br>'
                         '<span style="color: #b9770e;">d</span>')


class MirrorTest(_Case):
    def mirror(self):
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        return wg.WakeGroupMirror(self.g, QtWidgets.QFormLayout(holder))

    def test_the_same_options_enabled_as_the_group(self):
        m = self.mirror()
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        for position in wg.SHOWN_POSITIONS:
            mine, theirs = m.combo[position], self.g.combo[position]
            self.assertEqual([mine.itemData(i) for i in range(mine.count())],
                             [theirs.itemData(i) for i in range(theirs.count())])
            self.assertEqual([mine.model().item(i).isEnabled() for i in range(mine.count())],
                             [theirs.model().item(i).isEnabled() for i in range(theirs.count())])
            self.assertEqual(mine.currentData(), theirs.currentData())
            self.assertEqual(mine.toolTip(), theirs.toolTip())
        self.assertIn("velocidad efectiva", said(m))

    def test_the_map_says_the_warnings_and_notes_of_the_group(self):
        m = self.mirror()
        self.choose(cat.SUPERPOSITION, "CumulativeWakeSum")
        self.assertEqual(self.g.issues(), [])
        self.assertIn("dependen del orden de las turbinas", said(m))
        self.choose(cat.SUPERPOSITION, "LinearSum")
        self.choose(cat.ENGINE, "All2AllIterative")
        self.assertIn("PropagateDownwind y menor coste", said(m))
        self.choose(cat.ENGINE, "PropagateUpDownIterative")
        self.g.deficit_editor.set_values({"use_effective_ws": True})
        self.choose(cat.BLOCKAGE, "VortexDipole")
        self.g.blockage_editor.set_values({"use_effective_ws": True})
        self.assertEqual(self.g.issues(), [])
        self.assertIn("calcula con la velocidad libre aunque", said(m))

    def test_each_note_under_its_selector(self):
        # Discrete round 3, C1 (decision 7 of #64, D6: each line in its place): the engine warning under «Motor», the
        # conflict of WeightedSum with a ground under «Déficit de estela», not together after the last selector.
        holder = QtWidgets.QWidget()
        self.addCleanup(holder.deleteLater)
        form = QtWidgets.QFormLayout(holder)
        m = wg.WakeGroupMirror(self.g, form)
        self.choose(cat.ENGINE, "All2AllIterative")
        self.choose(cat.SUPERPOSITION, "WeightedSum")
        self.choose(cat.GROUND, "Mirror")
        self.assertEqual(self.codes(), {"R9"})
        for position in wg.SHOWN_POSITIONS:
            combo_row = form.getWidgetPosition(m.combo[position])[0]
            self.assertEqual(form.getWidgetPosition(m.notes[position])[0], combo_row + 1)
        self.assertEqual(form.getWidgetPosition(m.lbl_preferences)[0], 0)
        self.assertEqual(m.notes[cat.DEFICIT].text(), self.g.conflict[cat.DEFICIT].text())
        self.assertIn("#c0392b", m.notes[cat.DEFICIT].text())
        self.assertIn("PropagateDownwind y menor coste", m.notes[cat.ENGINE].text())
        self.assertFalse(m.notes[cat.DEFICIT].isHidden())
        self.assertTrue(m.notes[cat.SUPERPOSITION].isHidden() or m.notes[cat.SUPERPOSITION].text())
        # The note of the old preferences, first and orange, as in the group.
        self.assertTrue(m.lbl_preferences.isHidden())
        self.g.lbl_preferences.setText("ya no se usan")
        m.sync()
        self.assertEqual(m.lbl_preferences.text(), coloured_lines([], ["ya no se usan"]))
        self.assertFalse(m.lbl_preferences.isHidden())

    def test_a_change_in_the_map_is_a_change_of_the_group(self):
        m = self.mirror()
        m.combo[cat.DEFICIT].setCurrentIndex(m.combo[cat.DEFICIT].findData("ZongGaussianDeficit"))
        self.assertEqual(self.g.combo[cat.DEFICIT].currentData(), "ZongGaussianDeficit")
        self.assertIn("R2", self.codes())
        self.assertEqual(m.combo[cat.TURBULENCE].currentData(), wg.NONE)  # nothing chosen by itself


if __name__ == "__main__":
    unittest.main()
