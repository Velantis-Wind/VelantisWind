"""Acceptance 5/7: screen language oracle, with all process mutations in children."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

from .i18n_screen_oracle import foreign_markers, plain

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name('data')


def exceptions():
    """Closed, reviewed list: language + screen + widget/attribute + exact fragment + reason."""
    return json.loads((DATA / 'i18n_screen_exceptions.json').read_text(encoding='utf-8'))


def check_text(text, lang, screen, path, entries, used):
    residual = plain(text)
    for index, entry in enumerate(entries):
        if (entry['language'], entry['screen'], entry['path']) == (lang, screen, path):
            if entry['text'] in residual:
                used.add(index)
                residual = residual.replace(entry['text'], '')
    return foreign_markers(residual, lang)


class ScreensTest(unittest.TestCase):
    maxDiff = None

    def child(self, *args, timeout=150):
        run = subprocess.run([sys.executable, '-m', 'tests.test_i18n_screens', *args],
                             cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run.stdout

    def test_screens(self):
        entries, used, failures = exceptions(), set(), []
        self.assertEqual(len(entries), len({(e['language'], e['screen'], e['path'], e['text']) for e in entries}))
        for entry in entries:
            self.assertTrue(entry['text'] and entry['reason'])
            self.assertNotIn('*', entry['path'])  # No subtree/wildcard exemptions.
        for lang in ('es', 'en', 'fr', 'de'):
            for history in ('manual', 'preset'):
                with self.subTest(language=lang, history=history):
                    data = json.loads(self.child('--snapshot', lang, history))
                    self.assertEqual(set(data['texts']), {'hub', 'energy', 'turbine', 'aep', 'noise'})
                    for screen, texts in data['texts'].items():
                        self.assertGreater(len(texts), 100, screen)
                        self.assertTrue(any(p.endswith('/toolTip') for p in texts), screen)
                        for path, variants in texts.items():
                            for text in variants:
                                markers = check_text(text, lang, screen, path, entries, used)
                                if markers:
                                    failures.append((lang, history, screen, path, markers, text))
                    for screen in ('turbine', 'aep', 'noise'):
                        self.assertGreaterEqual(data['coverage'][screen]['tabs'], 4, screen)
                    self.assertGreaterEqual(data['coverage']['hub']['pages'], 3)
                    for screen in ('hub', 'energy', 'aep'):
                        self.assertGreater(data['coverage'][screen]['folds'], 0, screen)
                    for screen in ('hub', 'aep', 'noise'):
                        self.assertTrue(any('/cell/' in p for p in data['texts'][screen]), screen)
                    self.assertTrue(any('/specialValueText' in p for p in data['texts']['energy']))
        self.assertEqual(failures, [])
        # Stale exemptions must be removed, not silently kept after a path/text changes.
        self.assertEqual(used, set(range(len(entries))), [entries[i] for i in set(range(len(entries))) - used])

    def test_oracle_and_exception_scope(self):
        for lang in ('en', 'fr', 'de'):
            for bad in ('á í ó ú ñ ¿ ¡', 'archivo guardar estelas', '<b>Parámetros del bloqueo</b>',
                        'texto pendiente', 'estado obstáculo'):
                self.assertTrue(foreign_markers(bad, lang), (lang, bad))
        for bad in ('Save settings', 'Scroll Left', 'layout and wake steering', '<p>white paper</p>'):
            self.assertTrue(foreign_markers(bad, 'es'), bad)
        self.assertEqual(foreign_markers('é de la nombre disponible disponibles', 'fr'), [])
        self.assertEqual(foreign_markers('rotor simple software', 'es'), [])
        for entry in exceptions():
            lang, screen, path = (entry[k] for k in ('language', 'screen', 'path'))
            self.assertEqual(check_text(entry['text'], lang, screen, path, [entry], set()), [])
            self.assertTrue(check_text(entry['text'], lang, screen, path + '/different', [entry], set()))
            # An allowed name cannot conceal a newly untranslated sentence beside it.
            bad = ' save settings' if lang == 'es' else ' guardar archivo'
            self.assertTrue(check_text(entry['text'] + bad, lang, screen, path, [entry], set()))

    def test_pending_is_empty_and_all_resolved_pairs_are_exact(self):
        from .pending_translations import PENDING
        self.assertEqual(PENDING, set())
        self.child('--pending')

    def test_imports_leave_process_state_unchanged(self):
        probe = r'''
import importlib, locale, logging, os, sys, time, warnings
from qgis.PyQt import QtCore, QtWidgets
import py_wake
QtCore.QLocale.setDefault(QtCore.QLocale('de_DE'))
os.environ['TZ'] = 'Europe/Berlin'
time.tzset()
def state():
    return (dict(os.environ), os.getcwd(), time.tzname, locale.setlocale(locale.LC_ALL),
            QtCore.QLocale().name(), QtWidgets.QApplication.instance(), list(sys.path),
            [(fmt, scope, QtCore.QSettings(fmt, scope, 'VelantisWind', 'VelantisWindPlugin').fileName())
             for fmt in (QtCore.QSettings.NativeFormat, QtCore.QSettings.IniFormat)
             for scope in (QtCore.QSettings.UserScope, QtCore.QSettings.SystemScope)],
            list(warnings.filters), list(logging.getLogger().handlers),
            {k: v for k, v in sys.modules.items() if k == 'py_wake' or k.startswith('py_wake.')})
before = state()
for name in ('tests.i18n_screens_fixture', 'tests.i18n_screen_oracle', 'tests.test_i18n_screens'):
    importlib.import_module(name)
    assert state() == before, name
assert py_wake.__version__ != 'synthetic'
assert 'VelantisWind.i18n' not in sys.modules
'''
        run = subprocess.run([sys.executable, '-c', probe], cwd=ROOT,
                             capture_output=True, text=True, timeout=90)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


def check_pending_in_child():
    from . import i18n_m4b_fixture as f
    f.initialize_child()
    with f.environment():
        from VelantisWind import plugin  # All plugin registrations, as in normal startup.
        from VelantisWind.ag_core import turbine_ui
        expected = json.loads((DATA / 'i18n_resolved_pending.json').read_text(encoding='utf-8'))
        assert len(expected) == 17
        for source, values in expected.items():
            for lang, target in values.items():
                f.i18n.set_language(lang)
                assert f.i18n.tr_text(source) == target, (lang, source, f.i18n.tr_text(source), target)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--snapshot']:
        from .i18n_screens_fixture import snapshot
        print(json.dumps(snapshot(*sys.argv[2:]), ensure_ascii=False))
    elif sys.argv[1:2] == ['--pending']:
        check_pending_in_child()
    else:
        unittest.main()
