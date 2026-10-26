# -*- coding: utf-8 -*-
import html
import unittest
from unittest import mock

from VelantisWind import aep_setup_dialog, i18n

_LANGS = ("en", "fr", "de")


def _run_in(lang, fn, *args):
    with mock.patch.object(i18n, "current_language", return_value=lang), \
            mock.patch.object(aep_setup_dialog, "current_language", return_value=lang):
        return fn(*args)


class EnergyTranslationsTest(unittest.TestCase):
    def test_calculation_notes_are_translated_in_results_html(self):
        notes = [
            "WRG: alturas climáticas disponibles [100.0, 140.0]; PyWake interpola linealmente en altura "
            "cuando la HH está dentro del rango.",
            "Parámetros del recurso (WRG): 84 direcciones (12 sectores × 7), interpolación nearest, Speedup none, "
            "velocidades 3–25 m/s cada 0.5 m/s (banda de las turbinas 3–24.5 m/s); 8766 h/año.",
            "Recurso GRD, direcciones y velocidades del Site de PyWake: 360 direcciones (0–359°), 3–25 m/s, "
            "interpolación linear; 8766 h/año.",
            "Efecto suelo (wake): Mirror + SquaredSum; rotor-average TurbOPark: CGIRotorAvg(9).",
        ]
        body = "<ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>"
        for lang in _LANGS:
            with self.subTest(lang=lang):
                out = _run_in(lang, i18n.translate_html, body)
                for spanish in ("alturas climáticas", "Efecto suelo", "velocidades", "direcciones", "sectores",
                                "interpolación", "banda", "cada", "h/año"):
                    self.assertNotIn(spanish, out)
                self.assertIn("(12 ", out)


if __name__ == "__main__":
    unittest.main()
