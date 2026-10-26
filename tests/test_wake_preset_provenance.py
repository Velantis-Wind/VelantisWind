# -*- coding: utf-8 -*-
"""The provenance of a predefined model in the results: from the launch to the AEP, the raster, the report, the
comparator and the exports (plan of the predefined models, M2)."""
import json
import os
import tempfile
import types
import unittest
import warnings
from unittest import mock

from qgis.PyQt import QtCore, QtGui, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core import aep_compute as ac  # noqa: E402
from VelantisWind.ag_core.log_text import shown  # noqa: E402
from VelantisWind.ag_core.results.model_config_html import model_config_html  # noqa: E402
from VelantisWind.ag_core.wake_setup import api  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import presets as ps  # noqa: E402
from VelantisWind.energy_core.dialog_state import build_energy_dialog_state  # noqa: E402
from VelantisWind.wake_core import raster  # noqa: E402
from tests.test_resource_settings import model, write_wrg  # noqa: E402

warnings.filterwarnings("ignore", module="py_wake")
_CWD = os.getcwd()
CGI7 = cfg.Component("CGIRotorAvg", {"n": 7})


def adapted(id_, missing=("h5py",), acceptance="continue"):
    """The preset adapted with «Continuar» without the libraries of GaussianOverlapAvgModel (decision 17), or by the
    decision saved for it (decision 21)."""
    return api.gaussian_overlap_adaptation(ps.config(id_), list(missing), acceptance)


def identification(id_):
    return f"Configuración adaptada a partir de {id_}: CGIRotorAvg(7)"


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class _Case(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.wrg = write_wrg(self.folder, 12)

    def aep(self, config, provenance=None):
        return ac.compute_aep_from_ui("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08,
                                      wake_physics=api.to_wake_physics(config), wake_provenance=provenance)

    def raster(self, config, provenance=None):
        out = tempfile.mkdtemp(dir=self.folder)
        result = raster.compute_wake_raster_config([model()], wake_config=config, wrg_paths=[self.wrg],
                                                   resolution_m=250.0, output_dir=out, fixed_ti=0.08,
                                                   wd_target=270.0, wake_provenance=provenance)
        with open(result["metadata_path"], encoding="utf-8") as fh:
            return result, json.load(fh)


class CheckedProvenanceTest(unittest.TestCase):
    def test_only_the_provenance_of_the_configuration(self):
        c = ps.config("NiayifarGaussian")
        self.assertIsNone(ps.checked_provenance(c, None))
        self.assertEqual(ps.checked_provenance(c, ps.provenance("NiayifarGaussian")), ps.provenance("NiayifarGaussian"))
        wrong = [("ZongGaussian", c), ("NiayifarGaussian", ps.config("NOJ")),
                 ("NiayifarGaussian", cfg.WakeConfig(**{**c.__dict__, "rotor": cfg.Component("CGIRotorAvg", {"n": 7})}))]
        for id_, config in wrong:
            with self.subTest(preset=id_), self.assertRaises(ValueError):
                ps.checked_provenance(config, ps.provenance(id_))
        for change in ({"revision": 0}, {"preset": "TurbOPark"}, {"notes": ["x"]}, {"reference_version": "2.6.21"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ps.checked_provenance(c, dict(ps.provenance("NiayifarGaussian"), **change))
        with self.assertRaises(ValueError):
            ps.checked_provenance(c, "NiayifarGaussian")

    def test_the_preset_adapted_and_nothing_else(self):
        # Decision 18: the preset with exactly the canonical adaptation; any other change, refused.
        for id_ in ("NiayifarGaussian", "TurbOPark"):
            provenance = ps.provenance(id_)
            for missing in (["h5py"], ["h5netcdf"], ["h5py", "h5netcdf"]):
                with self.subTest(preset=id_, missing=missing):
                    self.assertTrue(ps.adapted(id_, adapted(id_, missing)))
                    self.assertEqual(ps.checked_provenance(adapted(id_, missing), provenance), provenance)
            good = adapted(id_)
            record = dict(good.adaptations[0])
            wrong = {
                "CGI7 without its record": cfg.WakeConfig(**{**ps.config(id_).__dict__, "rotor": CGI7}),
                "another CGI": cfg.WakeConfig(**{**good.__dict__, "rotor": cfg.Component("CGIRotorAvg", {"n": 9})}),
                "an incomplete record": cfg.WakeConfig(**{**good.__dict__, "adaptations": (
                    {k: v for k, v in record.items() if k != "missing"},)}),
                "another module": cfg.WakeConfig(**{**good.__dict__, "adaptations": (dict(record, missing="numpy"),)}),
                "two records": cfg.WakeConfig(**{**good.__dict__, "adaptations": (record, record)}),
                "another change": cfg.WakeConfig(**{**good.__dict__, "superposition": cfg.Component("MaxSum", {})}),
                "the other preset adapted": adapted("TurbOPark" if id_ == "NiayifarGaussian" else "NiayifarGaussian"),
            }
            for name, config in wrong.items():
                with self.subTest(preset=id_, wrong=name), self.assertRaises(ValueError):
                    self.assertFalse(ps.adapted(id_, config))
                    ps.checked_provenance(config, provenance)
        # How it was accepted (decision 21): with «Continuar», by the saved decision, or not said (as before M8).
        for acceptance in ("continue", "saved_preference", None):
            with self.subTest(acceptance=acceptance):
                self.assertTrue(ps.adapted("TurbOPark", adapted("TurbOPark", acceptance=acceptance)))
        with self.assertRaises(ValueError):
            ps.checked_provenance(adapted("TurbOPark", acceptance="always"), ps.provenance("TurbOPark"))
        # A preset without GaussianOverlapAvgModel is never adapted.
        with self.assertRaises(ValueError):
            ps.checked_provenance(adapted("ZongGaussian"), ps.provenance("ZongGaussian"))


class AepTest(_Case):
    def test_a_preset_result(self):
        config, provenance = ps.config("BastankhahGaussian"), ps.provenance("BastankhahGaussian")
        r = self.aep(config, provenance)
        wc = r["wake_config"]
        self.assertEqual(wc["provenance"], provenance)
        self.assertEqual(str(wc["identification"]), "Modelo predefinido: BastankhahGaussian")
        # The complete configuration, as for any result; the differences with the signatures are recorded, not shown.
        self.assertEqual(cfg.WakeConfig.from_dict(wc["effective"]), config)
        self.assertTrue(wc["differences_vs_signature"])
        self.assertEqual(wc["differences_vs_selection"], [])
        self.assertIn(ps.K_NOTE, [str(w) for w in r["persistent_warnings"]])
        html = model_config_html(r)
        self.assertIn("Modelo predefinido: BastankhahGaussian", html)
        self.assertIn(ps.K_NOTE, html)
        self.assertNotIn("salvo", html)
        from VelantisWind.ag_core.qgis_io.export import wake_record, wake_texts
        texts = wake_texts(r)
        self.assertEqual(texts["wake_id"], "Modelo predefinido: BastankhahGaussian")
        self.assertIn("k = 0,0324555", texts["wake_warn"])
        self.assertEqual(json.loads(json.dumps(wake_record(r), default=str))["wake_config"]["provenance"], provenance)

    def test_the_log_says_where_it_comes_from(self):
        with mock.patch.object(ac, "_log") as log:
            self.aep(ps.config("NOJ"), ps.provenance("NOJ"))
        written = [str(c.args[0]) for c in log.call_args_list]
        import py_wake
        self.assertIn("[REPORT] Modelo predefinido NOJ, revisión 1: py_wake.literature.noj.Jensen_1983 de PyWake 2.6.18, "
                      f"calculado con PyWake {py_wake.__version__}.", written)
        self.assertIn("[REPORT] Configuración ejecutada: Modelo predefinido: NOJ", written)

    def test_the_note_of_supergaussian_with_its_link(self):
        # Decision 6: the note of SuperGaussian in the result, with the link to its documentation.
        r = self.aep(ps.config("SuperGaussian"), ps.provenance("SuperGaussian"))
        url = ps.preset("SuperGaussian").url
        self.assertIn(f"{ps.SUPERGAUSSIAN_NOTE} {url}", [str(w) for w in r["persistent_warnings"]])
        link = f'<a href="{url}">{url}</a>'
        self.assertIn(link, model_config_html(r))  # a link, opened from the report
        from VelantisWind import results_dialog
        dlg = results_dialog.AEPResultsDialog(None, r)
        self.addCleanup(dlg.deleteLater)
        self.assertIn(link, dlg.lbl_wake_warnings.text())
        self.assertTrue(dlg.lbl_wake_warnings.openExternalLinks())
        # A warning with a line break and characters of HTML keeps them, as in plain text.
        manual = self.aep(cfg.default_config())
        manual["persistent_warnings"] = ["línea 1 <b>\nlínea 2 & 3"]
        dlg = results_dialog.AEPResultsDialog(None, manual)
        self.addCleanup(dlg.deleteLater)
        self.assertIn("⚠ línea 1 &lt;b&gt;<br>línea 2 &amp; 3", dlg.lbl_wake_warnings.text())
        doc = QtGui.QTextDocument()
        doc.setHtml(dlg.lbl_wake_warnings.text())
        self.assertIn("línea 1 <b>\nlínea 2 & 3", doc.toPlainText())
        from VelantisWind.ag_core.qgis_io.export import wake_texts
        self.assertIn(url, wake_texts(r)["wake_warn"])
        # The others, as they are.
        self.assertEqual([str(w) for w in ps.notes(ps.provenance("BastankhahGaussian"))], [ps.K_NOTE])

    def test_an_adapted_preset_result(self):
        # Decision 19: never presented as the preset itself; what was selected and what was executed, the note of the
        # adaptation, in the result, the report, the log, the exports and once saved.
        config, provenance = adapted("NiayifarGaussian"), ps.provenance("NiayifarGaussian")
        with mock.patch.object(ac, "_log") as log:
            r = self.aep(config, provenance)
        wc = r["wake_config"]
        self.assertEqual(wc["provenance"], provenance)
        self.assertEqual(str(wc["identification"]), identification("NiayifarGaussian"))
        self.assertEqual(cfg.WakeConfig.from_dict(wc["selected"]), api.user_selection(config))
        self.assertEqual(cfg.WakeConfig.from_dict(wc["effective"]), config)
        self.assertEqual([d["position"] for d in wc["differences_vs_selection"]], ["rotor"])
        self.assertIn("Se ha usado CGIRotorAvg(7)", " ".join(str(w) for w in r["persistent_warnings"]))
        html = model_config_html(r)
        self.assertIn(identification("NiayifarGaussian"), html)
        self.assertNotIn("Modelo predefinido: NiayifarGaussian", html)
        self.assertIn("Lo ejecutado difiere de la selección", html)
        written = [str(c.args[0]) for c in log.call_args_list]
        self.assertTrue(any(w.startswith("[REPORT] Configuración adaptada a partir del modelo predefinido "
                                         "NiayifarGaussian, revisión") for w in written), written)
        self.assertIn("[REPORT] Configuración ejecutada: " + identification("NiayifarGaussian"), written)
        self.assertFalse(any(w.startswith("[REPORT] Modelo predefinido") for w in written))
        from VelantisWind.ag_core.qgis_io.export import wake_record, wake_texts
        self.assertEqual(wake_texts(r)["wake_id"], identification("NiayifarGaussian"))
        record = json.loads(json.dumps(wake_record(r), default=str))["wake_config"]
        self.assertEqual((record["provenance"], record["adaptations"]), (provenance, [dict(config.adaptations[0])]))
        saved = json.loads(json.dumps(r, default=str))
        self.assertEqual(model_config_html(saved), html)

    def test_a_result_adapted_by_the_saved_decision(self):
        # Decision 21: the result says it was applied by the decision saved for the model, and how to ask again; once
        # saved, it is shown as it was, whatever is saved now.
        r = self.aep(adapted("NiayifarGaussian", acceptance="saved_preference"), ps.provenance("NiayifarGaussian"))
        warnings_ = " ".join(str(w) for w in r["persistent_warnings"])
        self.assertIn("aplicado por la decisión guardada para este modelo", warnings_)
        self.assertNotIn("elegido con «Continuar»", warnings_)
        self.assertEqual(r["wake_config"]["adaptations"][0]["acceptance"], "saved_preference")
        from VelantisWind.ag_core.qgis_io.export import wake_record, wake_texts
        self.assertIn("aplicado por la decisión guardada", wake_texts(r)["wake_warn"])
        self.assertEqual(json.loads(json.dumps(wake_record(r), default=str))["wake_config"]["adaptations"][0][
            "acceptance"], "saved_preference")
        # Saved, it is shown as it was, whatever is decided afterwards (the settings and the libraries not read).
        from VelantisWind.ui_core import wake_group as wg
        saved, html = json.loads(json.dumps(r, default=str)), model_config_html(r)
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self.addCleanup(wg.clear_consent, settings, "NiayifarGaussian")
        for change in (lambda: wg.save_consent(settings, "NiayifarGaussian", ["h5netcdf"]),
                       lambda: wg.clear_consent(settings, "NiayifarGaussian")):
            change()
            with mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                            side_effect=AssertionError("not consulted")):
                self.assertEqual(model_config_html(saved), html)
        now = self.aep(adapted("NiayifarGaussian"), ps.provenance("NiayifarGaussian"))
        self.assertIn("elegido con «Continuar»", " ".join(str(w) for w in now["persistent_warnings"]))

    def test_a_manual_result_has_no_provenance(self):
        # The same configuration as a preset, without its provenance: a manual result as today.
        config = ps.config("NOJ")
        r = self.aep(config)
        self.assertNotIn("provenance", r["wake_config"])
        self.assertEqual(str(r["wake_config"]["identification"]), str(cfg.identification(config)))
        self.assertNotIn("Modelo predefinido", model_config_html(r))

    def test_a_provenance_that_is_not_the_configuration_is_refused(self):
        with mock.patch.object(ac, "_compute_aep") as compute, self.assertRaises(ValueError):
            self.aep(ps.config("NOJ"), ps.provenance("IEA37SimpleBastankhahGaussian"))
        compute.assert_not_called()

    def test_a_result_saved_without_provenance_is_shown_as_saved(self):
        r = self.aep(cfg.default_config())
        saved = json.loads(json.dumps(r, default=str))
        self.assertEqual(model_config_html(saved), model_config_html(r))


class LaunchTest(_Case):
    def dialog(self, provenance):
        config = ps.config("NOJ") if provenance else cfg.default_config()
        return types.SimpleNamespace(
            _rows=[{"name": "A", "wt": object(), "meta": {}}],
            _collect_layer_points_for_row=lambda idx: [(0.0, 0.0)],
            _find_interactive_layer_for_row=lambda idx: types.SimpleNamespace(id=lambda: "layer-a", name=lambda: "A"),
            ed_dir=mock.Mock(text=lambda: ""), ed_wrg=mock.Mock(text=lambda: self.wrg),
            ed_wrg_ti=mock.Mock(text=lambda: ""), _qsettings=mock.Mock(value=lambda *a, **k: 200),
            _wake_physics_for_run=lambda what="AEP", ask=True, n_turbines=None: api.to_wake_physics(config),
            _wake_provenance_for_run=lambda: provenance,
            _get_fixed_ti_fraction=lambda: 0.1,
            _get_air_density_settings=lambda: {"mode": "off"},
            _get_resource_params=lambda: {"direction_count": None, "wd_interp": "nearest", "ws_step": None})

    def test_from_the_dialog_to_the_calculation(self):
        for provenance in (ps.provenance("NOJ"), None):
            with self.subTest(preset=bool(provenance)):
                state = build_energy_dialog_state(self.dialog(provenance), "EPSG:32630")
                self.assertEqual(state.wake_provenance, provenance)
                kwargs = state.to_energy_config().to_compute_kwargs()
                self.assertEqual(kwargs["wake_provenance"], provenance)
                with mock.patch.object(ac, "compute_aep_from_ui", return_value={"per_turbine_table": []}) as compute:
                    ac.compute_and_update(**dict(kwargs, update_project_layers=False))
                self.assertEqual(compute.call_args.kwargs["wake_provenance"], provenance)

    def test_a_dialog_without_provenance(self):
        dialog = self.dialog(None)
        del dialog._wake_provenance_for_run
        self.assertIsNone(build_energy_dialog_state(dialog, "EPSG:32630").wake_provenance)


class RasterTest(_Case):
    def test_the_json_of_a_preset_raster(self):
        provenance = ps.provenance("IEA37SimpleBastankhahGaussian")
        result, meta = self.raster(ps.config("IEA37SimpleBastankhahGaussian"), provenance)
        self.assertEqual(meta["wake_config"]["provenance"], provenance)
        self.assertIn(ps.DEPRECATED_NOTE, result["warnings"])
        self.assertIn(ps.DEPRECATED_NOTE, meta["warnings"])

    def test_the_json_of_an_adapted_preset_raster(self):
        config, provenance = adapted("TurbOPark", ("h5py", "h5netcdf")), ps.provenance("TurbOPark")
        result, meta = self.raster(config, provenance)
        wc = meta["wake_config"]
        self.assertEqual((wc["provenance"], wc["identification"]), (provenance, identification("TurbOPark")))
        self.assertEqual(wc["adaptations"], [dict(config.adaptations[0])])
        self.assertEqual(cfg.WakeConfig.from_dict(wc["selected"]).rotor.name, "GaussianOverlapAvgModel")
        self.assertEqual(cfg.WakeConfig.from_dict(wc["effective"]).rotor, CGI7)
        self.assertEqual(result["warnings"][0], identification("TurbOPark"))  # said first
        self.assertIn(identification("TurbOPark"), meta["warnings"])
        # A preset raster says which one, without a warning of it.
        _result, pure = self.raster(ps.config("NOJ"), ps.provenance("NOJ"))
        self.assertEqual(pure["wake_config"]["identification"], "Modelo predefinido: NOJ")
        self.assertNotIn("Modelo predefinido: NOJ", pure["warnings"])

    def test_the_json_of_a_raster_adapted_by_the_saved_decision(self):
        result, meta = self.raster(adapted("NiayifarGaussian", acceptance="saved_preference"),
                                   ps.provenance("NiayifarGaussian"))
        self.assertEqual(meta["wake_config"]["adaptations"][0]["acceptance"], "saved_preference")
        self.assertTrue(any("aplicado por la decisión guardada" in w for w in meta["warnings"]))
        self.assertEqual(result["warnings"][0], identification("NiayifarGaussian"))

    def test_a_manual_raster_and_a_wrong_provenance(self):
        _result, meta = self.raster(ps.config("NOJ"))
        self.assertNotIn("provenance", meta["wake_config"])
        with self.assertRaises(ValueError):
            self.raster(ps.config("NOJ"), ps.provenance("BastankhahGaussian"))

    def test_the_json_records_the_checked_provenance(self):
        # What is recorded is the copy checked at the start, not the dictionary given.
        given = ps.provenance("NOJ")
        real = raster._compute

        def compute(**kwargs):
            given["preset"] = "BastankhahGaussian"
            return real(**kwargs)
        with mock.patch.object(raster, "_compute", compute):
            _result, meta = self.raster(ps.config("NOJ"), given)
        self.assertEqual(meta["wake_config"]["provenance"], ps.provenance("NOJ"))

    def test_the_task_carries_it(self):
        from VelantisWind.wake_core.domain import WakeRasterTaskConfig
        given = ps.provenance("NOJ")
        task = WakeRasterTaskConfig(models=[], wasp_dir="", wake_config=ps.config("NOJ"), wake_provenance=given)
        given["notes"].append("x")  # captured at the launch: what changes afterwards does not reach the task
        self.assertEqual(task.to_engine_kwargs()["wake_provenance"], ps.provenance("NOJ"))
        self.assertIsNone(WakeRasterTaskConfig(models=[], wasp_dir="").to_engine_kwargs()["wake_provenance"])


class WindowTest(_Case):
    def test_a_preset_result_and_a_saved_one(self):
        from VelantisWind import results_dialog
        preset = self.aep(ps.config("IEA37SimpleBastankhahGaussian"), ps.provenance("IEA37SimpleBastankhahGaussian"))
        # A result saved before the predefined models: no provenance, its identification as it was written.
        saved = json.loads(json.dumps(self.aep(cfg.default_config()), default=str))
        for result, identification, note in ((preset, "Modelo predefinido: IEA37SimpleBastankhahGaussian", True),
                                             (saved, saved["wake_config"]["identification"], False)):
            with self.subTest(preset=note):
                dlg = results_dialog.AEPResultsDialog(None, result)
                self.addCleanup(dlg.deleteLater)
                self.assertEqual(dlg.lbl_wake_id.text(), identification)
                self.assertEqual(ps.DEPRECATED_NOTE in dlg.lbl_wake_warnings.text(), note)
                self.assertEqual("Modelo predefinido" in dlg.txt_executed.toPlainText(), note)


class ComparatorTest(_Case):
    def test_the_comparator_names_the_preset(self):
        from VelantisWind.results_dialog import ScenarioComparisonDialog, _fill_slots
        a = self.aep(ps.config("NOJ"), ps.provenance("NOJ"))
        b = json.loads(json.dumps(self.aep(ps.config("NOJ")), default=str))  # also a result saved before
        dlg = ScenarioComparisonDialog(None, a, b, "A", "B")
        self.addCleanup(dlg.deleteLater)
        html = _fill_slots(dlg._user_texts, dlg._config_html())
        self.assertEqual(html.count("Modelo predefinido: NOJ"), 1)
        # The label of the last calculation, for the scenarios: the preset by its name.
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        for result, expected in ((a, " · NOJ"), (b, " · PropagateDownwind / NOJDeficit")):
            holder = types.SimpleNamespace()
            AEPSetupDialog._register_last_aep_result(holder, result)
            self.assertTrue(holder._last_aep_label.endswith(expected), holder._last_aep_label)

    def test_the_comparator_and_the_window_name_an_adapted_preset(self):
        from VelantisWind.results_dialog import AEPResultsDialog, ScenarioComparisonDialog, _fill_slots
        a = self.aep(adapted("NiayifarGaussian"), ps.provenance("NiayifarGaussian"))
        b = json.loads(json.dumps(a, default=str))  # the same, saved
        dlg = ScenarioComparisonDialog(None, a, b, "A", "B")
        self.addCleanup(dlg.deleteLater)
        html = _fill_slots(dlg._user_texts, dlg._config_html())
        self.assertIn(identification("NiayifarGaussian"), html)
        self.assertNotIn("Modelo predefinido: NiayifarGaussian", html)
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        for result in (a, b):
            holder = types.SimpleNamespace()
            AEPSetupDialog._register_last_aep_result(holder, result)
            self.assertTrue(holder._last_aep_label.endswith(" · " + identification("NiayifarGaussian")),
                            holder._last_aep_label)
            window = AEPResultsDialog(None, result)
            self.addCleanup(window.deleteLater)
            self.assertEqual(window.lbl_wake_id.text(), identification("NiayifarGaussian"))

    def test_the_link_of_a_note_opens_from_the_comparator(self):
        from VelantisWind.results_dialog import ScenarioComparisonDialog
        a = self.aep(ps.config("SuperGaussian"), ps.provenance("SuperGaussian"))
        dlg = ScenarioComparisonDialog(None, a, self.aep(ps.config("NOJ")), "A", "B")
        self.addCleanup(dlg.deleteLater)
        url = ps.preset("SuperGaussian").url
        browser, = [t for t in dlg.findChildren(QtWidgets.QTextBrowser) if url in t.toHtml()]
        self.assertTrue(browser.openExternalLinks())


if __name__ == "__main__":
    unittest.main()
