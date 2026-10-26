# -*- coding: utf-8 -*-
"""#67: the translator gives the same maps and texts whatever the order in which the plugin's tables are imported, no
text has two translations in one language, and going back to Spanish always lands on a Spanish source."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Each order imports the same modules (every table the plugin registers, at start-up and when its windows open),
# in a different sequence: the plugin's, the one of the tests that used to fail together, and windows first.
_MODULES = ["VelantisWind.plugin", "VelantisWind.ag_core.turbine_ui", "VelantisWind.noise_core.project_watch",
            "VelantisWind.spacing_core.controller", "VelantisWind.mapa_interactivo_dock",
            "VelantisWind.results_dialog", "VelantisWind.noise_results_dialog", "VelantisWind.support_dialog"]
_ORDERS = {
    "plugin": _MODULES,
    "results first": ["VelantisWind.ag_core.results.model_config_translations", "VelantisWind.results_dialog"]
    + _MODULES,
    "windows first": list(reversed(_MODULES)),
}

_PROBE = r'''
import hashlib, json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
from qgis.PyQt import QtCore, QtWidgets
tmp = tempfile.mkdtemp()
for fmt in (QtCore.QSettings.NativeFormat, QtCore.QSettings.IniFormat):
    QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, tmp)
os.chdir(tmp)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
regs = []
def profile(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "register_language" and frame.f_code.co_filename.endswith("i18n.py"):
        loc = frame.f_locals
        full = dict(loc.get("full_map") or {})
        frag = loc.get("fragment_map")
        regs.append((str(loc.get("lang") or "").lower(), full, full if frag is None else dict(frag or {})))
sys.setprofile(profile)
for name in json.loads(sys.argv[2]):
    __import__(name)
sys.setprofile(None)
from VelantisWind import i18n
i18n._ensure()
st = i18n._STATE
digest = {k: hashlib.sha256(json.dumps(st[k], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
          for k in ("full", "frag", "src_full", "full_norm", "src_full_norm")}
for k in ("frag_sorted", "src_frag_sorted"):
    digest[k] = hashlib.sha256(json.dumps(st[k], ensure_ascii=False).encode()).hexdigest()
conflicts = []
for kind in (1, 2):
    seen = {}
    for r in regs:
        for es, tgt in r[kind].items():
            if isinstance(es, str) and isinstance(tgt, str):
                prev = seen.setdefault((r[0], es), tgt)
                if prev != tgt:
                    conflicts.append([r[0], es, prev, tgt])
outputs = {}
texts = sorted({k for kind in ("full", "frag") for m in st[kind].values() for k in m if isinstance(k, str)})
for lang in ("en", "fr", "de"):
    i18n.set_language(lang)
    outputs[lang] = i18n.translate_fragment("Modelo rotor-average (PyWake): altura negativa no válida.")
    every = json.dumps([[i18n.tr_text(t), i18n.translate_fragment(t)] for t in texts], ensure_ascii=False)
    outputs[lang + " (every text)"] = hashlib.sha256(every.encode()).hexdigest()
i18n.set_language("es")
reverse = {s: i18n._to_source(s) for s in ("Mai", "Analysejahr:", "May", "Analysis year:", "OK")}
foreign = sorted(set(st["src_full"].values()) & set(i18n.FOREIGN_KEYS))
print(json.dumps({"digest": digest, "conflicts": conflicts[:20], "n_conflicts": len(conflicts),
                  "outputs": outputs, "reverse": reverse, "foreign_pivots": foreign[:20]}, ensure_ascii=False))
'''


def _run(order):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run([sys.executable, "-c", _PROBE, _ROOT, json.dumps(order)], capture_output=True, text=True,
                             env=env, cwd=tmp, timeout=600)
    if out.returncode != 0:
        raise AssertionError(out.stderr[-3000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


class TranslatorDeterminismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {name: _run(order) for name, order in _ORDERS.items()}

    def test_no_text_has_two_translations_in_one_language(self):
        for name, run in self.runs.items():
            with self.subTest(order=name):
                self.assertEqual(run["n_conflicts"], 0, run["conflicts"])

    def test_the_maps_are_the_same_in_every_import_order(self):
        reference = self.runs["plugin"]
        for name, run in self.runs.items():
            with self.subTest(order=name):
                self.assertEqual(run["digest"], reference["digest"])
                self.assertEqual(run["outputs"], reference["outputs"])

    def test_going_back_to_spanish_lands_on_a_spanish_source(self):
        run = self.runs["plugin"]
        self.assertEqual(run["reverse"]["Mai"], "Mayo")
        self.assertEqual(run["reverse"]["Analysejahr:"], "Año de análisis:")
        self.assertEqual(run["reverse"]["OK"], "Aceptar")
        self.assertEqual(run["foreign_pivots"], [])


if __name__ == "__main__":
    unittest.main()
