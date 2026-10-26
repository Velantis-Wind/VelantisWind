"""Live retranslations versus independent fresh processes, in all four languages."""
import json
import os
import subprocess
import sys
import unittest
from . import i18n_m4b_fixture as f

class IntegrationTest(unittest.TestCase):
    def test_imports_leave_process_state_unchanged(self):
        probe = r'''
import importlib, os, sys, time
from qgis.PyQt import QtCore, QtWidgets
import py_wake
QtCore.QLocale.setDefault(QtCore.QLocale('de_DE'))
os.environ['TZ'] = 'Europe/Berlin'
time.tzset()
def state():
    return (dict(os.environ), os.getcwd(), time.tzname, QtCore.QLocale().name(),
            QtWidgets.QApplication.instance(),
            QtCore.QSettings('VelantisWind', 'VelantisWindPlugin').fileName(),
            {k: v for k, v in sys.modules.items() if k == 'py_wake' or k.startswith('py_wake.')})
before = state()
for name in ('tests.i18n_m4b_fixture', 'tests.test_i18n_m4b',
             'tests.test_i18n_m4b_regenerators', 'tests.i18n_m4b_regenerator_cases'):
    importlib.import_module(name)
    assert state() == before, name
assert py_wake.__version__ != 'synthetic'
'''
        run = subprocess.run([sys.executable, '-c', probe], cwd=f._ROOT,
                             capture_output=True, text=True, timeout=90)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_all_start_and_target_languages(self):
        run = subprocess.run([sys.executable, '-m', 'tests.test_i18n_m4b', '--live'],
                             cwd=f._ROOT, capture_output=True, text=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def check_all_start_and_target_languages(self):
        with f.environment():
            for history in ('manual', 'preset'):
                fresh = {}
                for lang in f.LANGS:
                    run = subprocess.run([sys.executable, '-m', 'tests.test_i18n_m4b', '--snapshot', lang, history],
                                         cwd=f._ROOT, capture_output=True, text=True, timeout=90)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    fresh[lang] = json.loads(run.stdout)
                for start in f.LANGS:
                    ui = f.build(start, history)
                    self.addCleanup(f.dispose, ui)
                    hub, energy = ui[:2]
                    for target in f.LANGS:
                        if target == start:
                            continue
                        with self.subTest(history=history, start=start, target=target):
                            if history == 'preset':
                                # Refill layer selectors in the previous language before the next live switch.
                                # Each owner must preserve its Spanish sources and the selected layer.
                                hub.page_noise._populate_dem_combo(f.QgsProject.instance())
                                hub.page_noise._populate_receivers_combo(f.QgsProject.instance())
                                hub.page_flicker._populate_receivers_combo(f.QgsProject.instance())
                            hub.cb_language.setCurrentIndex(hub.cb_language.findData(target))
                            actual = json.loads(json.dumps(f.texts(ui)))
                            differences = {root: {k: (actual[root].get(k), fresh[target][root].get(k))
                                           for k in actual[root].keys() | fresh[target][root].keys()
                                           if actual[root].get(k) != fresh[target][root].get(k)} for root in actual}
                            differing = {k:v for k,v in differences.items() if v}
                            if differing:
                                with open(os.path.join(f._TEMP.name, f'diff-{history}-{start}-{target}.json'), 'w') as stream:
                                    json.dump(differing, stream, ensure_ascii=False, indent=2)
                            self.assertEqual(differing, {}, f'{history}/{start}/{target}: {differing!r}')
                    # Reopen the same hidden dialog; preserve objects and input drafts.
                    row = energy._rows[0]
                    energy.hide()
                    hub._open_energy_module()
                    self.assertIs(hub._energy_dialog, energy)
                    self.assertIs(energy._rows[0], row)
                    self.assertEqual(energy.ed_wrg_ti_heights.text(), '90;draft')
                    f.dispose(ui)
                    self._cleanups.pop()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('--snapshot', '--live'):
        f.initialize_child()
    if len(sys.argv) > 1 and sys.argv[1] == '--snapshot':
        with f.environment():
            ui = f.build(sys.argv[2], sys.argv[3])
            print(json.dumps(f.texts(ui), ensure_ascii=False))
            f.dispose(ui)
    elif len(sys.argv) > 1 and sys.argv[1] == '--live':
        unittest.main(argv=[sys.argv[0]], defaultTest='IntegrationTest.check_all_start_and_target_languages')
    else:
        unittest.main()
