"""WRG errors reach readers and UI fully translated, with data unchanged."""
import contextlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from unittest import mock

from qgis.PyQt.QtWidgets import QLabel, QLineEdit

from VelantisWind import aep_setup_dialog, i18n
from VelantisWind.aep_setup_dialog import AEPSetupDialog
from VelantisWind.ag_core.wrg_reader import read_wrg_meta
from VelantisWind.ag_core.wrg_site import _build_ds_from_wrg_text, load_wrg_site
from VelantisWind.energy_core.dialog_controller import _error_text
from VelantisWind.spacing_core.orientation import _sector_energy_from_lines
from tests.test_issue_47 import resource


_REASONS = {
    "es": (
        "Fila WRG inválida: el número de campos no coincide con los sectores declarados.",
        "Identificador WRG convertible a número finito no admitido: puede confundirse con los datos de una fila sin identificador.",
        "Nº sectores inconsistente: esperado 4, leído 3.",
        "campos WRG no numéricos.",
        "campos WRG no finitos.",
        "los campos del nodo deben ser números finitos.",
    ),
    "en": (
        "Invalid WRG row: the field count does not match the declared sectors.",
        "WRG identifiers convertible to a finite number are not supported: they can be confused with the data of a row without an identifier.",
        "Inconsistent sector count: expected 4, read 3.",
        "non-numeric WRG fields.",
        "non-finite WRG fields.",
        "node fields must be finite numbers.",
    ),
    "fr": (
        "Ligne WRG invalide : le nombre de champs ne correspond pas aux secteurs déclarés.",
        "Les identifiants WRG convertibles en un nombre fini ne sont pas pris en charge : ils peuvent être confondus avec les données d’une ligne sans identifiant.",
        "Nombre de secteurs incohérent : 4 attendu, 3 lu.",
        "champs WRG non numériques.",
        "champs WRG non finis.",
        "les champs du nœud doivent être des nombres finis.",
    ),
    "de": (
        "Ungültige WRG-Zeile: Die Anzahl der Felder stimmt nicht mit den angegebenen Sektoren überein.",
        "WRG-Kennungen, die in eine endliche Zahl umgewandelt werden können, werden nicht unterstützt: Sie können mit den Daten einer Zeile ohne Kennung verwechselt werden.",
        "Abweichende Sektoranzahl: erwartet 4, gelesen 3.",
        "nicht numerische WRG-Felder.",
        "nicht endliche WRG-Felder.",
        "die Knotenfelder müssen endliche Zahlen sein.",
    ),
}
_CONTEXT = {
    "es": "{source}, línea {line}: ",
    "en": "{source}, line {line}: ",
    "fr": "{source}, ligne {line} : ",
    "de": "{source}, Zeile {line}: ",
}


def malformed(kind, node=0):
    rows = resource().splitlines()
    tokens = rows[node + 1].split()
    if kind == 0:
        tokens.pop()
    elif kind == 1:
        tokens.insert(0, "001")
    elif kind == 2:
        tokens[7] = "3"
        tokens = tokens[:-3]
    else:
        tokens[8 if kind < 5 else 3] = {3: "junk", 4: "nan", 5: "inf"}[kind]
    rows[node + 1] = " ".join(tokens)
    return "\n".join(rows)


class WrgErrorTranslationsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = os.path.join(self.folder.name, "línea {line} énergie.wrg")

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return self.path

    def expected(self, lang, kind, source=None, line=2):
        return _CONTEXT[lang].format(source=source or self.path, line=line) + _REASONS[lang][kind]

    def test_scientific_reader_translates_all_errors_in_both_routes(self):
        for lang in _REASONS:
            for kind in range(5):
                # A different sector count is meaningful after the first node.
                node = 3 if kind == 2 else 0
                for force in (False, True):
                    with self.subTest(lang=lang, kind=kind, force=force), \
                            mock.patch.object(i18n, "current_language", return_value=lang):
                        cm = mock.patch("VelantisWind.ag_core.wrg_site.np.fromstring", side_effect=ValueError) if force else contextlib.nullcontext()
                        with cm, self.assertRaises(ValueError) as raised:
                            _build_ds_from_wrg_text(malformed(kind, node), source=self.path)
                        self.assertEqual(str(raised.exception), self.expected(lang, kind, line=node + 2))

    def test_metadata_reader_translates_structure_identifier_and_finite_header(self):
        for lang in _REASONS:
            for kind in (0, 1, 5):
                with self.subTest(lang=lang, kind=kind), \
                        mock.patch.object(i18n, "current_language", return_value=lang):
                    with self.assertRaises(ValueError) as raised:
                        read_wrg_meta(self.write(malformed(kind)))
                    self.assertEqual(str(raised.exception), self.expected(lang, kind))

    def test_zip_errors_preserve_member_name_and_physical_line(self):
        path = os.path.join(self.folder.name, "línea {line}.zip")
        member = "nested/línea {reason} énergie.wrg"
        text = "\r\n" + "\r\n\r\n".join(malformed(1).splitlines())
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("valid.wrg", resource())
            archive.writestr(member, text)
        for lang in _REASONS:
            for reader in (read_wrg_meta, lambda p: load_wrg_site([p], speedup_method="none")):
                with self.subTest(lang=lang, reader=reader), \
                        mock.patch.object(i18n, "current_language", return_value=lang):
                    with self.assertRaises(ValueError) as raised:
                        reader(path)
                    self.assertEqual(str(raised.exception), self.expected(lang, 1, path + "::" + member, 4))

    def test_orientation_translates_errors_without_line_context(self):
        for lang in _REASONS:
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                with self.assertRaises(ValueError) as raised:
                    _sector_energy_from_lines(malformed(1).splitlines())
                separator = " : " if lang == "fr" else ": "
                self.assertEqual(str(raised.exception), "WRG" + separator + _REASONS[lang][1])

    def test_calculation_error_uses_the_language_active_when_displayed(self):
        with mock.patch.object(i18n, "current_language", return_value="es"):
            with self.assertRaises(ValueError) as raised:
                _build_ds_from_wrg_text(malformed(1), source=self.path)
        for lang in _REASONS:
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                self.assertEqual(_error_text(raised.exception), self.expected(lang, 1))

    def test_metadata_ui_displays_the_complete_translated_error(self):
        self.write(malformed(1))
        dialog = types.SimpleNamespace(ed_wrg=QLineEdit(self.path), lbl_wrg_meta=QLabel(),
                                       _show_wrg_parameters=mock.Mock())
        for lang in _REASONS:
            with self.subTest(lang=lang), \
                    mock.patch.object(i18n, "current_language", return_value=lang), \
                    mock.patch.object(aep_setup_dialog, "current_language", return_value=lang):
                AEPSetupDialog._update_wrg_meta(dialog)
                expected = i18n.tr_text("WRG inválido o no legible: {error}").format(error=self.expected(lang, 1))
                self.assertEqual(dialog.lbl_wrg_meta.text(), expected)

    def test_standalone_reader_errors_do_not_require_qgis_or_scientific_packages(self):
        # A fresh process prevents the UI imports above from hiding a dependency.
        code = """
import os, sys, types
pkg = types.ModuleType('VelantisWind')
pkg.__path__ = [os.path.join(os.getcwd(), 'VelantisWind')]
sys.modules['VelantisWind'] = pkg
sys.modules['VelantisWind.i18n'] = None
from VelantisWind.ag_core.wrg_nodes import node_tokens
try:
    node_tokens([], source='site.wrg', line_number=7)
except ValueError as exc:
    assert str(exc) == 'site.wrg, línea 7: Fila WRG inválida: el número de campos no coincide con los sectores declarados.'
else:
    raise AssertionError('Malformed row accepted')
assert not any(name in sys.modules for name in ('qgis', 'numpy', 'py_wake'))
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
