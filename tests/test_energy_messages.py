# -*- coding: utf-8 -*-
import ast
import inspect
import re
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from VelantisWind import aep_setup_dialog, i18n, results_dialog
from VelantisWind.aep_setup_dialog import AEPSetupDialog
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput
from VelantisWind.energy_core.runner import EnergyRunner
from VelantisWind.energy_core.validation import format_validation_issues, validate_energy_config

_LANGS = ("en", "fr", "de")
_PLUGIN = Path(aep_setup_dialog.__file__).parent
_PLACEHOLDER = re.compile(r"\{\w+\}")

# Texts passed to the translator through a variable, not as a literal.
_INDIRECT = [
    "Calculando AEP",
    "Inicializando cálculo…",
    "Valor PyWake por defecto ({default})",
]


# Dialogs and messages outside the calculation: resource, layers, scenarios, interactive map, exports.
_DIALOG_METHODS = [getattr(AEPSetupDialog, name) for name in (
    "_open_pywake_docs", "_define_model", "_show_curve_for_model",
    "_maybe_warn_about_ti_setup", "_pick_dir", "_pick_wrg", "_pick_wrg_ti", "_update_wrg_ti_meta",
    "_update_wrg_meta", "_clear_resource_extent", "_draw_current_resource_extent", "_on_generate_layers_clicked",
    "_load_new_layer", "_register_last_aep_result", "_store_current_scenario",
    "_compare_scenarios", "_export_edited_layouts_dialog", "_refresh_project_state", "_open_spacing_config",
    "_activate_map_interactive", "_show_interactive_messagebar", "_recalc_aep_from_interactive", "_accept",
    "_open_union_recurso", "_wake_physics_for_run", "_libraries_text",
    "_collect_layer_points_for_row", "_build_resource_params_group", "_update_resource_params_view",
    "_update_wind_speeds",
)] + [
    results_dialog.AEPResultsDialog._export_turbines_csv,
    results_dialog.AEPResultsDialog._export_report_html,
    results_dialog.ScenarioComparisonDialog._init_ui,
]
_DIALOG_INDIRECT = [
    # The row's layer selector, its badge and the buttons' tips, built in _rebuild_rows and the dialog's constructor.
    "Capa de turbinas:",
    "Cargar nueva capa",
    "Importar un fichero de coordenadas como capa nueva y elegirla en esta fila",
    "● editado en el mapa",
    'Has movido/añadido/borrado turbinas en el mapa interactivo.\nLos cambios están en la capa seleccionada en esta fila, y en su fichero si lo tiene.\nPulsa «Exportar disposición editada…» si quieres guardarlos en un CSV.',
    "Activa edición en el lienzo del mapa: clic izq añade turbina, clic der borra. "
    "Las ediciones se escriben en la capa de turbinas seleccionada, y en su fichero si lo tiene; "
    "el cálculo de AEP usa esa capa.",
    "Guardar a CSV los puntos editados en el mapa interactivo.\nPor defecto: <nombre de la capa>_edited.csv.",
    "AEP neto", "AEP bruto", "Pérdidas totales", "Pérdidas por estela", "Impacto TI/turbulencia",
    "Pérdidas por bloqueo", "Nº aerogeneradores", "Potencia instalada", "Factor de capacidad neto",
]
# Shown literally (not a format field).
_SHOWN_BRACES: set = set()


def _dialog_texts():
    texts = list(_DIALOG_INDIRECT)
    for method in _DIALOG_METHODS:
        texts += _call_literals(ast.parse(textwrap.dedent(inspect.getsource(method))), {"_tr"})
    for path in (_PLUGIN / "union_recurso.py", _PLUGIN / "ag_core" / "qgis_io" / "resource_extent.py"):
        texts += _call_literals(ast.parse(path.read_text(encoding="utf-8")), {"_tr"})
    # Shared import window: its explorer and its errors, seen from «Cargar nueva capa».
    texts += _call_literals(ast.parse((_PLUGIN / "ui_core" / "layout_sources.py").read_text(encoding="utf-8")), {"tr_text"})
    # Wake-raster warnings and errors, translated from their template when shown.
    engine = ast.parse((_PLUGIN / "wake_core" / "engine.py").read_text(encoding="utf-8"))
    texts += _call_literals(engine, {"_warn"}) + _call_literals(engine, {"_error"}, arg=1)
    texts.append("El cálculo terminó sin generar un GeoTIFF de estelas.")
    # The dialog's texts of the physics (decision 10, the old preferences), translated with _tr where shown.
    texts += [AEPSetupDialog.OLD_PHYSICS_NOTE, AEPSetupDialog.GO_MISSING_QUESTION]
    # AEP log warnings, shown translated in the message bar; and those of the wake raster (wake_core/raster.py).
    for path in sorted((_PLUGIN / "ag_core").rglob("*.py")) + [_PLUGIN / "wake_core" / "raster.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "log_text":
                if isinstance(node.args[0], ast.Constant):
                    texts.append(node.args[0].value)
    texts += [
        "[AEP] [REPORT] No se pudo calcular la variante TI ambiente only para el modelo TI-driven; "
        "se mantiene el AEP principal. Error: {error}",
    ]
    # Separators inside f-strings (", ") are not texts; the texts waiting for the final sweep of translations, apart.
    from tests.pending_translations import PENDING
    return sorted(set(t for t in texts if any(c.isalpha() for c in t)) - PENDING)


def _run_in(lang, fn, *args, **kwargs):
    with mock.patch.object(i18n, "current_language", return_value=lang):
        return fn(*args, **kwargs)


def _call_literals(tree, names, arg=0):
    """String literals passed as argument ``arg`` to calls named ``names``."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and len(node.args) > arg:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name in names:
                found += [n.value for n in ast.walk(node.args[arg]) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return found


def _translated_texts():
    texts = list(_INDIRECT)
    for path in sorted((_PLUGIN / "energy_core").glob("*.py")):
        texts += _call_literals(ast.parse(path.read_text(encoding="utf-8")), {"tr"})
    texts += _call_literals(ast.parse(textwrap.dedent(inspect.getsource(AEPSetupDialog._run_plot_wakes))), {"_tr"})
    # Progress messages of the calculation, translated by EnergyRunner.
    compute = ast.parse((_PLUGIN / "ag_core" / "aep_compute.py").read_text(encoding="utf-8"))
    texts += _call_literals(compute, {"_progress", "progress_callback"}, arg=1)
    return sorted(set(t for t in texts if t.strip()))


class EnergyMessagesTest(unittest.TestCase):
    def test_every_text_has_an_exact_translation(self):
        i18n._ensure()
        texts = _translated_texts()
        self.assertGreater(len(texts), 80)
        for lang in _LANGS:
            table = i18n._STATE["full"][lang]
            for text in texts:
                with self.subTest(lang=lang, text=text[:60]):
                    self.assertIn(text, table)
                    translated = _run_in(lang, i18n.tr_text, text)
                    # No cleanup rewrites the value, and the placeholders survive.
                    self.assertEqual(translated, table[text])
                    self.assertEqual(sorted(_PLACEHOLDER.findall(translated)), sorted(_PLACEHOLDER.findall(text)))

    def test_every_dialog_text_has_an_exact_translation(self):
        i18n._ensure()
        texts = _dialog_texts()
        self.assertGreater(len(texts), 120)
        for lang in _LANGS:
            table = i18n._STATE["full"][lang]
            for text in texts:
                with self.subTest(lang=lang, text=text[:60]):
                    self.assertIn(text, table)
                    translated = _run_in(lang, i18n.tr_text, text)
                    self.assertEqual(translated, table[text])
                    if text not in _SHOWN_BRACES:
                        self.assertEqual(sorted(_PLACEHOLDER.findall(translated)), sorted(_PLACEHOLDER.findall(text)))

    def test_filled_labels_survive_retranslation(self):
        # apply_i18n translates the dialog labels again when the model rows are rebuilt.
        labels = [
            ("Ráster(s) TI no seleccionado(s) → respaldo automático a {ti}% si usas WRG.", {"ti": "10.0"}),
            ("Ráster(s) TI: {files} · CRS destino previsto: {crs}", {"files": None, "crs": "EPSG:25830"}),
            ("Malla: {nx}×{ny} | celda={cell} m | h={heights} m | sectores={sectors} | extensión={extent}",
             {"nx": 120, "ny": 80, "cell": 50.0, "heights": "100.0, 140.0", "sectors": 12, "extent": "(0,0)–(6000,4000)"}),
            ("Perímetro WAsP/Surfer dibujado: envolvente de {n} grid(s) sin intersección común.", {"n": 3}),
        ]
        for lang in ("es",) + _LANGS:
            for template, data in labels:
                with self.subTest(lang=lang, text=template[:40]):
                    if data.get("files", "") is None:
                        data = dict(data, files=_run_in(lang, i18n.tr_text, "{file} ({height} m, nombre)").format(file="a.tif", height=90)
                                    + " ; " + _run_in(lang, i18n.tr_text, "{file} ({ext}, sin altura)").format(file="b.vrt", ext=".vrt"))
                    shown = _run_in(lang, i18n.tr_text, template).format(**data)
                    self.assertEqual(_run_in(lang, i18n.tr_text, shown), shown)

    def test_raster_error_keeps_its_text_and_template(self):
        from VelantisWind.wake_core import engine, raster
        from VelantisWind.wake_core.task import WakeRasterTask

        error = engine._error(ValueError, "No se pudo leer '{name}' del dataset.", name="Speedup")
        self.assertIsInstance(error, ValueError)
        self.assertEqual(str(error), "No se pudo leer 'Speedup' del dataset.")
        config = mock.Mock(to_engine_kwargs=lambda: {})
        task = WakeRasterTask(config=config)
        with mock.patch.object(raster, "compute_wake_raster_config", side_effect=error):
            self.assertFalse(task.run())
        self.assertEqual(task.error, "No se pudo leer 'Speedup' del dataset.")
        template, data = task.result["error_item"]
        shown = _run_in("fr", i18n.tr_text, template).format(**data)
        self.assertEqual(shown, "Impossible de lire 'Speedup' dans le jeu de données.")

    def test_validation_messages_follow_the_language(self):
        config = EnergyRunConfig(models=[TurbineModelInput(name="", wt=None)], wasp_dir="")
        spanish = _run_in("es", lambda: format_validation_issues(validate_energy_config(config)))
        self.assertIn("[ERROR] Modelo 1: falta definir la turbina/curva de potencia.", spanish)
        french = _run_in("fr", lambda: format_validation_issues(validate_energy_config(config)))
        self.assertIn("[ERREUR] Modèle 1 : l’éolienne ou la courbe de puissance n’est pas définie.", french)
        self.assertNotIn("Selecciona", french)

    def test_progress_messages_are_translated_only_for_display(self):
        seen = []

        def fake_compute(**kwargs):
            kwargs["progress_callback"](2, "Inicializando cálculo…")
            return {}

        with mock.patch("VelantisWind.energy_core.runner.validate_energy_config", return_value=[]), \
                mock.patch("VelantisWind.ag_core.aep_compute.compute_and_update", fake_compute):
            _run_in("de", EnergyRunner().run, EnergyRunConfig(), lambda value, message: seen.append((value, message)))
        self.assertEqual(seen, [(2, "Berechnung wird initialisiert…")])

    def test_missing_rotor_package_error_is_translated(self):
        error = (
            "GaussianOverlapAvgModel lee una tabla NetCDF de PyWake y necesita los paquetes de Python "
            "h5py y h5netcdf; falta: h5py, h5netcdf. Instálalos en el Python de QGIS o elige otro promedio de rotor."
        )
        expected = {
            "en": "GaussianOverlapAvgModel reads a PyWake NetCDF table and needs the Python packages h5py and h5netcdf; "
                  "missing: h5py, h5netcdf. Install them in the QGIS Python or choose another rotor average.",
            "fr": "GaussianOverlapAvgModel lit une table NetCDF de PyWake et nécessite les paquets Python h5py et h5netcdf ; "
                  "manquant : h5py, h5netcdf. Installez-les dans le Python de QGIS ou choisissez une autre moyenne sur le rotor.",
            "de": "GaussianOverlapAvgModel liest eine NetCDF-Tabelle von PyWake und benötigt die Python-Pakete h5py und "
                  "h5netcdf; es fehlt: h5py, h5netcdf. Installieren Sie sie im Python von QGIS oder wählen Sie eine andere "
                  "Rotormittelung.",
        }
        for lang, text in expected.items():
            with self.subTest(lang=lang):
                self.assertEqual(_run_in(lang, aep_setup_dialog._tr, error), text)


if __name__ == "__main__":
    unittest.main()
