"""Run every UI regenerator case in a disposable process, leaving the suite untouched."""
import subprocess
import sys
import unittest
from . import i18n_m4b_fixture as f


class RegeneratorTest(unittest.TestCase):
    def test_regenerators_in_child_process(self):
        run = subprocess.run([sys.executable, '-m', 'unittest', '-v',
                              'tests.i18n_m4b_regenerator_cases'],
                             cwd=f._ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
