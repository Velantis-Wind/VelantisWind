# -*- coding: utf-8 -*-
"""The texts of the «Modelo de estela» group and of ``ag_core/wake_setup`` in each language (zone Z4 of the plan of
translations): the Energy dialog opens in every language with a saved predefined model that no longer exists, the texts
that had no translation have theirs, no translation changes the placeholders of its template, and the German and French
texts address the user as «Sie» and «vous»."""
import ast
import os
import re
import string
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

import VelantisWind  # noqa: E402
from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401
from VelantisWind import aep_setup_dialog  # noqa: E402
from VelantisWind.ui_core import wake_group as wg  # noqa: E402
from VelantisWind.ag_core.wake_setup import presets as ps  # noqa: E402

_CWD = os.getcwd()
LANGS = ("en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


_STALE = {
    "es": "El modelo predefinido guardado «NoExiste» ya no es una opción: se abre con NOJ.",
    "en": "The saved predefined model «NoExiste» is no longer an option: it opens with NOJ.",
    "fr": "Le modèle prédéfini enregistré « NoExiste » n’est plus une option : il s’ouvre avec NOJ.",
    "de": "Das gespeicherte vordefinierte Modell «NoExiste» ist keine Option mehr: es wird mit NOJ geöffnet.",
}
# The texts of the zone that had no translation: (en, fr, de).
_EXPECTED = {
    "Parámetros del bloqueo": ("Blockage parameters", "Paramètres du blocage", "Parameter der Blockade"),
    # The glossary: «Überlagerung».
    "Parámetros de la superposición": (
        "Superposition parameters", "Paramètres de la superposition", "Parameter der Überlagerung"),
    "Referencia del escalado: {reference} ({key})": (
        "Scaling reference: {reference} ({key})", "Référence de mise à l’échelle : {reference} ({key})",
        "Skalierungsreferenz: {reference} ({key})"),
    "velocidad libre de la turbina de destino": (
        "free-stream speed of the destination turbine", "vitesse en écoulement libre de l’éolienne de destination",
        "Geschwindigkeit der freien Anströmung an der Zielturbine"),
    "Se hereda la superposición de estelas ({cls})": (
        "The wake superposition is inherited ({cls})", "La superposition des sillages est héritée ({cls})",
        "Die Nachlaufüberlagerung wird geerbt ({cls})"),
    "Se hereda la superposición del bloqueo ({cls})": (
        "The blockage superposition is inherited ({cls})", "La superposition du blocage est héritée ({cls})",
        "Die Überlagerung der Blockade wird geerbt ({cls})"),
    "Marca use_effective_ws en los parámetros del bloqueo.": (
        "Set use_effective_ws in the blockage parameters.", "Cochez use_effective_ws dans les paramètres du blocage.",
        "Setzen Sie use_effective_ws in den Parametern der Blockade."),
    "wake_physics.deficit_ws_reference: {value!r} no es una opción ({options}, o None).": (
        "wake_physics.deficit_ws_reference: {value!r} is not an option ({options}, or None).",
        "wake_physics.deficit_ws_reference : {value!r} n’est pas une option ({options}, ou None).",
        "wake_physics.deficit_ws_reference: {value!r} ist keine Option ({options} oder None)."),
    "Procedencia de modelo predefinido no reconocida: {value!r}.": (
        "Unrecognised predefined model provenance: {value!r}.",
        "Provenance de modèle prédéfini non reconnue : {value!r}.",
        "Nicht erkannte Herkunft eines vordefinierten Modells: {value!r}."),
    "La configuración no es la del modelo predefinido {preset} (revisión {revision}) que dice su procedencia.": (
        "The configuration is not that of the predefined model {preset} (revision {revision}) stated in its provenance.",
        "La configuration n’est pas celle du modèle prédéfini {preset} (révision {revision}) qu’indique sa provenance.",
        "Die Konfiguration ist nicht die des vordefinierten Modells {preset} (Revision {revision}), das in ihrer "
        "Herkunftsangabe genannt wird."),
    "Modelo predefinido: {preset}": (
        "Predefined model: {preset}", "Modèle prédéfini : {preset}", "Vordefiniertes Modell: {preset}"),
    # Address of the user (S3-15): «Sie» and «vous».
    "Elige LinearSum para el bloqueo, o quita el bloqueo.": (
        "Choose LinearSum for the blockage, or remove the blockage.",
        "Choisissez LinearSum pour le blocage, ou retirez le blocage.",
        "Wählen Sie LinearSum für die Blockade oder entfernen Sie die Blockade."),
    "Marca use_effective_ws en los parámetros del déficit.": (
        "Set use_effective_ws in the deficit parameters.", "Cochez use_effective_ws dans les paramètres du déficit.",
        "Setzen Sie use_effective_ws in den Parametern des Defizits."),
}

_ZONE = ["ui_core/wake_group.py", "ui_core/wake_controls.py"] + [
    "ag_core/wake_setup/" + f for f in ("api.py", "catalog.py", "config.py", "factory.py", "instrumentation.py",
                                        "notices.py", "presets.py", "readers.py", "subordinates.py", "validation.py")]


def _zone_texts():
    """Every string constant of the zone's files that is not a docstring: what can reach the translator."""
    root = os.path.dirname(VelantisWind.__file__)
    out = set()
    for rel in _ZONE:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        out |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docs and " " in n.value.strip()}
    return sorted(out)


def _fields(text):
    """The named placeholders of a template, or ``None`` if it is not one (a style sheet, a dictionary literal)."""
    try:
        names = [f for _t, f, _s, _c in string.Formatter().parse(text) if f is not None]
    except ValueError:
        return None
    return sorted(names) if all(re.fullmatch(r"\w*", f) for f in names) else None


class _Lang(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")


class StalePresetTest(_Lang):
    """S3-1: without its translation the fragments turned {default} into {par défaut} / {standardmäßig}, and the Energy
    dialog did not open (KeyError)."""

    def setUp(self):
        from qgis.core import QgsProject
        QgsProject.instance().clear()
        self.settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self.addCleanup(lambda: [self.settings.remove(k) for k in self.settings.allKeys()])

    def test_energy_opens_with_a_saved_preset_that_no_longer_exists(self):
        for lang in ("es", "en", "fr", "de"):
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                self.settings.setValue(wg.PRESET_KEY, "NoExiste")
                d = aep_setup_dialog.AEPSetupDialog()
                self.addCleanup(d.deleteLater)
                g = d.wake_group
                self.assertEqual(g.combo_preset.currentData(), wg.DEFAULT_PRESET)
                self.assertEqual(g._preset_stale, _STALE[lang])
                self.assertIn(_STALE[lang], g.preset_note.text())


class ZoneTextsTest(_Lang):
    def test_texts_without_translation_have_theirs(self):
        for es, values in _EXPECTED.items():
            for lang, value in zip(LANGS, values):
                with self.subTest(lang=lang, es=es):
                    i18n.set_language(lang)
                    self.assertEqual(i18n.tr_text(es), value)

    def test_the_group_shows_them(self):
        for i, lang in enumerate(LANGS):
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                g = wg.WakeModelGroup(settings=None, tr=i18n.tr_text)
                self.addCleanup(g.deleteLater)
                self.assertEqual(g.sec_blockage.header.text(), _EXPECTED["Parámetros del bloqueo"][i])
                g.combo_preset.setCurrentIndex(g.combo_preset.findData("TurbOPark"))
                reference = _EXPECTED["velocidad libre de la turbina de destino"][i]
                self.assertEqual(g.lbl_preset_reference.text(), _EXPECTED[
                    "Referencia del escalado: {reference} ({key})"][i].format(reference=reference, key="WS_jlk"))
                window = g.open_preset_window(wg.GROUND, exec_=False)
                self.addCleanup(window.deleteLater)
                self.assertEqual(window.lbl_inherit.text(), _EXPECTED[
                    "Se hereda la superposición de estelas ({cls})"][i].format(cls=ps.config("TurbOPark").superposition.name))
                # The citations of the help of a model are not translated (S1-24).
                g.combo_preset.setCurrentIndex(g.combo_preset.findData("NiayifarGaussian"))
                self.assertIn(wg.PRESET_HELP["NiayifarGaussian"][1][0][1], g._preset_model_help())

    def test_no_translation_changes_the_placeholders(self):
        for text in _zone_texts():
            fields = _fields(text)
            if not fields:
                continue
            for lang in LANGS:
                i18n.set_language(lang)
                with self.subTest(lang=lang, text=text):
                    self.assertEqual(_fields(i18n.tr_text(text)), fields)

    def test_german_and_french_address_the_user_formally(self):
        informal = {
            "de": re.compile(r"\b(du|dich|dir|dein\w*|kannst|musst|[Ww]ähle|[Ss]etze|[Gg]ib|[Ll]ass|[Ee]ntferne|"
                             r"[Vv]erwende|[Ww]echsle|[Dd]eaktiviere)\b(?! Sie)"),
            "fr": re.compile(r"\b(tu|toi|ton|ta|tes|peux|[Cc]hoisis|[Cc]oche|[Dd]écoche|[Rr]etire|[Cc]onsulte)\b|"
                             r"(?:^|[:;,] |ou )(?:passe|donne|indique|utilise) "),
        }
        for text in _zone_texts():
            for lang, pattern in informal.items():
                i18n.set_language(lang)
                with self.subTest(lang=lang, text=text):
                    self.assertIsNone(pattern.search(i18n.tr_text(text)))


if __name__ == "__main__":
    unittest.main()
