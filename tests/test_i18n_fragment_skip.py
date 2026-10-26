# -*- coding: utf-8 -*-
"""#66: the fragment translation skips the entries that are not in the text, and gives the same output as before."""
import functools
import os
import re
import tempfile
import unittest

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _apply_fragments_before(s, pairs):
    """``_apply_fragments`` without the skip of #66: every entry of one word is compiled, even if it is not in the text.
    The other entries match as they do now, on whole words at their ends and outside the placeholders."""
    replacements = []
    for src, dst in pairs:
        if not src:
            continue
        token = f"VW_I18N_{len(replacements)}"
        if all((ch.isalnum() or ch == "_") for ch in src):
            pattern = re.compile(r"(?<!\w)" + re.escape(src) + r"(?!\w)")
            s, n = i18n._sub_outside_placeholders(pattern, token, s, dst)
            if n:
                replacements.append((token, dst))
        else:
            pattern = re.compile(("(?<!\\w)" if src[0].isalnum() else "") + re.escape(src)
                                 + ("(?!\\w)" if src[-1].isalnum() else ""))
            s, n = i18n._sub_outside_placeholders(pattern, token, s, dst)
            if n:
                replacements.append((token, dst))
    for token, dst in replacements:
        s = s.replace(token, dst)
    return s


class FragmentSkipTest(unittest.TestCase):
    def outputs(self, texts, apply):
        original = i18n._apply_fragments
        i18n._apply_fragments = apply
        try:
            return {lang: [i18n._fragment_impl(t, lang) for t in texts] for lang in ("en", "fr", "de")}
        finally:
            i18n._apply_fragments = original

    def test_the_output_is_the_same_for_a_fixed_sample_of_the_tables(self):
        # Every text of the tables (more than 12 000) takes minutes with the old function: the PR records that run;
        # the suite keeps one text in 40, always the same.
        i18n._ensure()
        texts = sorted({x for m in i18n._STATE["full"].values() for k, v in m.items() for x in (k, v)
                        if isinstance(x, str)})
        self.assertGreater(len(texts), 10000)
        texts = texts[::40]
        compile_ = re.compile
        re.compile = functools.lru_cache(maxsize=None)(compile_)  # the same patterns, compiled once
        try:
            before = self.outputs(texts, _apply_fragments_before)
        finally:
            re.compile = compile_
        after = self.outputs(texts, i18n._apply_fragments)
        for lang in before:
            diff = [(t, b, a) for t, b, a in zip(texts, before[lang], after[lang]) if b != a]
            self.assertEqual(diff, [], lang)

    def test_overlaps_tokens_case_unicode_signs_and_word_limits(self):
        pairs = sorted({"Modelo": "Model", "Modelo de estela": "Wake model", "de": "of", "estela": "wake",
                        "Ñandú": "Rhea", "MW·h": "MWh", "(B)": "[B]", "año": "year"}.items(),
                       key=lambda kv: len(kv[0]), reverse=True)
        cases = ["Modelo de estela", "modelo de estela", "Modelos de estelas", "Ñandú y ñandú", "6 MW·h (B)",
                 "año·año", "ModeloVW_I18N_0", "", "sin coincidencias", "Modelo-de-estela", "estela_1"]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(i18n._apply_fragments(text, pairs), _apply_fragments_before(text, pairs))


if __name__ == "__main__":
    unittest.main()
