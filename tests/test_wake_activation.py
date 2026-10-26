# -*- coding: utf-8 -*-
"""The new physics connected: the dialog, the API, the calculation, the variants and the raster use the factory, and
the old path is gone (#46 P5b). One test per row of #75 assigned to P5, and the dialog tests of the plan.

Rows: 1.1 and 3.7 ``ExactClassesTest.test_each_blockage_builds_its_class``; 1.2, 2.6 and 3.9
``test_the_superposition_is_the_one_chosen``; 2.4 and 3.6 ``test_the_turbulence_asked_for``; 2.5 and 3.5
``test_the_rotor_asked_for``; 6.1 ``test_what_was_executed_is_read_from_the_objects``; 2.2, 2.7, 3.2 and 3.3
``RefusalTest``; 4.1, 4.2 and 3.14 ``NoDegradationTest``; 3.11 ``NoGlobalStateTest``; 1.3-1.8 ``DialogTest``; 1.6
``test_wake_group.MirrorTest`` and ``DialogTest.test_the_interactive_map_mirrors_the_group``; 1.7
``test_wake_api``; 6.8 ``AmbientTiTest``; 6.5 ``ReportTest.test_the_comparator_tells_the_ground_apart``; 6.9
``ReportTest.test_the_html_export_with_another_tab``.
"""
import os
import tempfile
import types
import unittest
import warnings
from unittest import mock

import numpy as np
from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
# The plugin keeps its settings in a file shared by every QGIS profile: never touch it from a test.
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind.ag_core import aep_compute as ac  # noqa: E402
from VelantisWind.ag_core.results.model_config_html import model_config_html  # noqa: E402
from VelantisWind.ag_core.simulation import runner  # noqa: E402
from VelantisWind.ag_core.wake_setup import api  # noqa: E402
from VelantisWind.ag_core.wake_setup import catalog as cat  # noqa: E402
from VelantisWind.ag_core.wake_setup import config as cfg  # noqa: E402
from VelantisWind.ag_core.wake_setup import factory as fac  # noqa: E402
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput  # noqa: E402
from VelantisWind.energy_core.runner import EnergyRunner  # noqa: E402
from VelantisWind.wake_core import raster  # noqa: E402
from tests.test_resource_settings import model, write_wrg  # noqa: E402

warnings.filterwarnings("ignore", module="py_wake")
_CWD = os.getcwd()


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

    def aep(self, physics=None, **kwargs):
        kwargs.setdefault("fixed_ti", 0.08)
        if physics is not None:
            kwargs["wake_physics"] = dict({"version": 1}, **physics)
        return ac.compute_aep_from_ui("", [model()], wrg_paths=[self.wrg], **kwargs)

    def executed(self, result):
        return {p: (e or {}).get("class") for p, e in result["wake_config"]["executed"].items()}


class ExactClassesTest(_Case):
    def test_each_blockage_builds_its_class(self):
        for name in ("SelfSimilarityDeficit", "SelfSimilarityDeficit2020", "VortexCylinder"):
            with self.subTest(blockage=name):
                r = self.aep({"engine": "All2AllIterative", "blockage": name})
                self.assertEqual(self.executed(r)["blockage"], name)

    def test_the_superposition_is_the_one_chosen(self):
        cases = ((("NiayifarGaussianDeficit", "WeightedSum", None), "WeightedSum"),
                 (("TurboGaussianDeficit", "LinearSum", None), "LinearSum"),
                 (("BastankhahGaussianDeficit", "SquaredSum", "SelfSimilarityDeficit2020"), "SquaredSum"))
        for (deficit, sup, blockage), expected in cases:
            physics = {"engine": "All2AllIterative", "deficit": deficit, "superposition": sup,
                       "turbulence": "STF2017TurbulenceModel"}
            if deficit == "TurboGaussianDeficit":
                physics["ground"] = None  # the WeightedSum rules do not apply; its Mirror() is kept otherwise
            if blockage:
                physics["blockage"] = blockage
            with self.subTest(deficit=deficit, sup=sup):
                self.assertEqual(self.executed(self.aep(physics))["superposition"], expected)

    def test_the_turbulence_asked_for(self):
        r = self.aep({"turbulence": "CrespoHernandez"})
        self.assertEqual(self.executed(r)["turbulence"], "CrespoHernandez")
        # The previous schema: the class asked for, never another one of a list.
        r = self.aep(None, include_turbulence=True, turbulence_model="GCL")
        self.assertEqual(self.executed(r)["turbulence"], "GCLTurbulence")

    def test_the_rotor_asked_for(self):
        r = self.aep({"rotor": {"class": "CGIRotorAvg", "n": 9}})
        self.assertEqual(r["wake_config"]["executed"]["rotor"]["nodes"], 9)
        with mock.patch.object(api, "check_calculable"), \
                mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                           return_value=[]):
            r = self.aep({"rotor": "GaussianOverlapAvgModel"})
        self.assertEqual(self.executed(r)["rotor"], "GaussianOverlapAvgModel")  # never CGIRotorAvg(7) in silence

    def test_the_log_writes_every_executed_argument(self):
        with mock.patch.object(ac, "_log") as log:
            r = self.aep({"rotor": "EqGridRotorAvg", "turbulence": "STF2017TurbulenceModel"})
        written = [str(c.args[0]) for c in log.call_args_list]
        from VelantisWind.ag_core.wake_setup import readers
        for line in readers.executed_lines(r["wake_config"]["executed"]):
            self.assertIn("[REPORT]   " + line, written)
        self.assertIn("[REPORT]   promedio de rotor: EqGridRotorAvg (n=4 [argumento pasado]); nodos: 16", written)

    def test_what_was_executed_is_read_from_the_objects(self):
        r = self.aep({"deficit": "NOJDeficit", "deficit_params": {"k": 0.04}})
        executed = r["wake_config"]["executed"]
        self.assertEqual(executed["deficit"]["class"], "NOJDeficit")
        self.assertEqual(executed["deficit"]["params"]["k"], {"value": 0.04, "source": "observed"})
        self.assertEqual(executed["rotor"]["class"], "AreaOverlapAvgModel")  # its signature, read from the object
        self.assertEqual(r["wake_config"]["differences_vs_selection"], [])


class CumulativeWakeSumTest(_Case):
    def test_the_warning_reaches_the_result_and_the_breakdown_keeps_its_turbulence(self):
        # Decision 23(a): the arguments without effect are named in the result; the turbulence contrast of the
        # breakdown is not made zero (the effective TI enters the width of Niayifar).
        aligned = [(1200.0, 1300.0), (1700.0, 1300.0), (2200.0, 1300.0)]  # in each other's wake
        r = ac.compute_aep_from_ui("", [model(layout=aligned)], wrg_paths=[self.wrg], fixed_ti=0.08,
                                   compute_variants=True,
                                   wake_physics={"version": 1, "deficit": "NiayifarGaussianDeficit",
                                                 "superposition": "CumulativeWakeSum", "turbulence": "CrespoHernandez"})
        warnings_ = [str(w) for w in r["persistent_warnings"]]
        self.assertTrue(any("no afectan al resultado numérico por esta ruta: ct2a, use_effective_ws." in w
                            for w in warnings_), warnings_)
        self.assertTrue(any("orden de las turbinas" in w for w in warnings_))
        d_t = r["breakdown"]["D_T"]
        self.assertEqual(d_t["state"], "ok")
        self.assertTrue(np.isfinite(d_t["mwh"]))
        self.assertNotEqual(d_t["mwh"], 0.0)
        # What was executed keeps every argument, with its provenance.
        self.assertEqual(r["wake_config"]["executed"]["deficit"]["params"]["ct2a"]["source"], "observed")

    def test_the_downstream_blockage_warning_of_pud_reaches_the_result(self):
        # Decision 23(c), end to end.
        r = self.aep({"engine": "PropagateUpDownIterative", "deficit_params": {"use_effective_ws": True},
                      "superposition": "CumulativeWakeSum", "blockage": "SelfSimilarityDeficit2020",
                      "blockage_params": {"use_effective_ws": True}})
        warnings_ = [str(w) for w in r["persistent_warnings"]]
        self.assertTrue(any("la simulación de las turbinas omite el bloqueo aguas abajo" in w for w in warnings_),
                        warnings_)


class ArgumentWarningsEndToEndTest(_Case):
    def test_the_mirror_below_the_hub_reaches_the_result(self):
        # #64, Q2: the height of the mirror against the hubs is checked with the turbines of the calculation (90 m).
        from VelantisWind.ag_core.wake_setup import config as cfg2
        config = cfg2.WakeConfig(**{**cfg2.default_config().__dict__,
                                    "ground": cfg2.Component("MultiMirror", {"mirror_height": 50.0})})
        with mock.patch.object(api, "resolve_request", return_value=(config, None)):
            r = self.aep({"engine": "PropagateDownwind"})
        warnings_ = [str(w) for w in r["persistent_warnings"]]
        self.assertTrue(any("mirror_height = 50.0 m" in w and "(90.0 m)" in w for w in warnings_), warnings_)
        self.assertFalse(any("se comprueba con las turbinas" in w for w in warnings_))

    def test_the_turbulence_without_effect_without_the_breakdown(self):
        # Decision 16, persistent also without the breakdown (decision 6.6 of #64): in the result, its exports and the
        # comparator; use_effective_ti read as PyWake reads it (0 is false, 1 is true: Q5c).
        from VelantisWind import i18n
        from VelantisWind.ag_core.qgis_io.export import wake_texts
        from VelantisWind.results_dialog import ScenarioComparisonDialog
        fragment = "NiayifarGaussianDeficit no usa la TI efectiva"
        for value, said in ((False, True), (0, True), (True, False), (1, False)):
            with self.subTest(use_effective_ti=value), mock.patch.object(i18n, "current_language", return_value="es"):
                r = self.aep({"deficit": "NiayifarGaussianDeficit", "deficit_params": {"use_effective_ti": value},
                              "turbulence": "STF2017TurbulenceModel"}, compute_variants=False)
                self.assertEqual(any(fragment in str(w) for w in r["persistent_warnings"]), said)
                self.assertEqual(fragment in wake_texts(r)["wake_warn"], said)
                dlg = ScenarioComparisonDialog(None, r, r, "A", "B")
                self.addCleanup(dlg.deleteLater)
                from VelantisWind.results_dialog import _fill_slots
                self.assertEqual(fragment in _fill_slots(dlg._user_texts, dlg._config_html()), said)
        r = self.aep({"deficit": "NiayifarGaussianDeficit", "deficit_params": {"use_effective_ti": False},
                      "turbulence": None}, compute_variants=False)  # without turbulence: nothing
        self.assertFalse(any(fragment in str(w) for w in r["persistent_warnings"]))


class RefusalTest(_Case):
    def test_pdw_with_blockage_is_refused_before_calculating(self):
        with mock.patch.object(runner, "simulate") as simulate:
            with self.assertRaises(api.ConfigRejected) as ctx:
                self.aep(None, wfm_engine="PDW", include_blockage=True, blockage_deficit_model="SS2020")
            simulate.assert_not_called()
        self.assertIn("PropagateDownwind no admite bloqueo", str(ctx.exception.args[0]))

    def test_r9f_is_refused_before_simulating_with_two_turbines_or_more(self):
        physics = {"engine": "PropagateUpDownIterative", "deficit_params": {"use_effective_ws": True},
                   "superposition": "CumulativeWakeSum", "blockage": "SelfSimilarityDeficit2020",
                   "blockage_params": {"use_effective_ws": True}, "blockage_superposition": "MaxSum"}
        with mock.patch.object(runner, "simulate") as simulate:
            with self.assertRaises(api.ConfigRejected) as ctx:
                self.aep(physics)  # two turbines
            simulate.assert_not_called()
        self.assertEqual([i.code for i in ctx.exception.issues], ["R9f"])
        # With one turbine PyWake calculates it.
        one = ac.compute_aep_from_ui("", [model(layout=[(1200.0, 1300.0)])], wrg_paths=[self.wrg], fixed_ti=0.08,
                                     wake_physics=dict({"version": 1}, **physics))
        self.assertGreater(one["breakdown"]["A_WTB"]["mwh"], 0.0)

    def test_a_constructor_that_fails_leaves_its_cause_and_no_aep(self):
        real = fac._construct

        def failing(position, cls, kwargs):
            if cls.__name__ == "SelfSimilarityDeficit2020":
                raise RuntimeError("constructor roto")
            return real(position, cls, kwargs)
        with mock.patch.object(fac, "_construct", side_effect=failing), self.assertRaises(api.ConfigRejected) as ctx:
            self.aep({"engine": "All2AllIterative", "blockage": "SelfSimilarityDeficit2020"})
        self.assertIn("constructor roto", str(ctx.exception.args[0]))

    def test_a_class_the_installation_does_not_have(self):
        real = cat.resolve_class

        def missing(e):
            if e.name in ("All2AllIterative", "ZongGaussianDeficit"):
                raise cat.ClassUnavailable(f"La instalación de PyWake no tiene la clase {e.name} en {e.module}.")
            return real(e)
        for physics in ({"engine": "All2AllIterative"}, {"deficit": "ZongGaussianDeficit",
                                                         "turbulence": "STF2017TurbulenceModel"}):
            with self.subTest(physics=physics), mock.patch.object(cat, "resolve_class", side_effect=missing):
                with self.assertRaises(api.ConfigRejected) as ctx:
                    self.aep(physics)
                self.assertIn("no tiene la clase", str(ctx.exception.args[0]))

    def test_both_direct_entries_share_the_contract(self):
        for entry in (ac.compute_aep_from_ui, ac.compute_and_update):
            with self.subTest(entry=entry.__name__), self.assertRaisesRegex(api.RequestError, "wake_model ya no se usa"):
                entry("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08, wake_model="gauss")

    def test_through_the_runner_the_invalid_request_is_refused(self):
        config = EnergyRunConfig(models=[TurbineModelInput(**model())], wrg_paths=[self.wrg], fixed_ti=0.08,
                                 update_project_layers=False, superposition_model="AUTO")
        from VelantisWind.energy_core.runner import EnergyValidationError
        with self.assertRaisesRegex(EnergyValidationError, "«AUTO» ya no es una opción"):
            EnergyRunner().run(config)
        # The fields of the previous schema are passed as given, never converted with bool() or dict(... or {}).
        kwargs = EnergyRunConfig().to_compute_kwargs()
        for name in api.LEGACY_FIELDS:
            if name != "wake_model":
                self.assertIs(kwargs[name], api.NOT_SET)


class NoDegradationTest(_Case):
    def test_a_failure_of_pywake_is_the_error_of_the_calculation(self):
        def broken(wfm, *a, **k):
            raise ValueError("PyWake falló")
        with mock.patch.object(runner, "simulate", side_effect=broken), self.assertRaisesRegex(ValueError,
                                                                                                "PyWake falló"):
            self.aep({"engine": "All2AllIterative", "blockage": "SelfSimilarityDeficit2020"})

    def test_a_failed_variant_is_not_available_and_the_main_result_is_kept(self):
        real = runner.simulate

        def variant_fails(wfm, *a, **k):
            if wfm.__dict__.get("blockage_deficitModel") is None and type(wfm.wake_deficitModel).__name__ != "NoWakeDeficit":
                raise ValueError("variante rota")
            return real(wfm, *a, **k)
        with mock.patch.object(runner, "simulate", side_effect=variant_fails):
            r = self.aep({"engine": "All2AllIterative", "blockage": "SelfSimilarityDeficit2020"}, compute_variants=True)
        self.assertEqual(r["breakdown"]["L_W"]["state"], "failed")
        self.assertIsNone(r["breakdown"]["L_W"]["mwh"])
        self.assertIn("variante rota", r["breakdown"]["L_W"]["error"])
        self.assertEqual(self.executed(r)["blockage"], "SelfSimilarityDeficit2020")  # the main one, as asked

    def test_no_note_of_a_deficit_that_was_not_calculated(self):
        r = self.aep({"deficit": "ZongGaussianDeficit", "turbulence": "STF2017TurbulenceModel"})
        notes = " ".join(str(n) for n in r["simulation_notes"])
        self.assertNotIn("usa una k fija", notes)
        self.assertNotIn("puede ser sensible a la TI", notes)


class AmbientTiTest(_Case):
    """The ambient TI of the result is the value read from the resource, or NULL: never 0.10 nor clipped."""

    def test_the_reading_gives_the_value_or_nan(self):
        from types import SimpleNamespace
        import xarray as xr
        from VelantisWind.ag_core.resources.turbulence_grid import compute_ti_per_turbine
        xs, ys = np.array([0.0, 10.0]), np.array([0.0, 0.0])
        high = SimpleNamespace(ds=xr.Dataset({"TI": 1.2}))
        np.testing.assert_allclose(compute_ti_per_turbine(high, xs, ys), [1.2, 1.2], rtol=1e-6)
        for name, site in (("no dataset", SimpleNamespace()),
                           ("no TI", SimpleNamespace(ds=xr.Dataset({"WS": 8.0}))),
                           ("a mean that fails", SimpleNamespace(ds=xr.Dataset({"TI": (("wd",), [0.2, "bad"])}))),
                           ("unreadable", SimpleNamespace(ds=xr.Dataset({"TI": (("x", "y"), [["a"]])},
                                                                       coords={"x": [0.0], "y": [0.0]})))):
            with self.subTest(name):
                self.assertTrue(np.isnan(compute_ti_per_turbine(site, xs, ys)).all())

    def test_the_cyclic_copy_of_a_sector_is_not_counted(self):
        # XRSite closes the directions with a copy of 0° at 360°, to interpolate: the mean is over the two sectors.
        import xarray as xr
        from py_wake.site import XRSite
        from VelantisWind.ag_core.resources.turbulence_grid import compute_ti_per_turbine
        site = XRSite(xr.Dataset({"TI": ("wd", [0.1, 0.3]), "P": ("wd", [0.5, 0.5])}, coords={"wd": [0, 180]}))
        self.assertEqual(site.ds["wd"].values.tolist(), [0, 180, 360])  # PyWake's closure
        np.testing.assert_allclose(compute_ti_per_turbine(site, np.array([0.0]), np.array([0.0])), [0.2], rtol=1e-6)

    def test_the_height_of_the_hub(self):
        from types import SimpleNamespace
        import xarray as xr
        from VelantisWind.ag_core.resources.turbulence_grid import compute_ti_per_turbine
        xs, ys, hub = np.array([0.0, 10.0]), np.array([0.0, 0.0]), np.array([100.0, 100.0])

        def site(heights, values):
            ti = [[[v for v in values]] * 2] * 2
            return SimpleNamespace(ds=xr.Dataset({"TI": (("x", "y", "h"), ti)},
                                                 coords={"x": [-1.0, 20.0], "y": [-1.0, 1.0], "h": heights}))
        # Several heights: interpolated at the hub; a single one is the reference for any hub height (as the wind
        # climate of a single-height WRG).
        np.testing.assert_allclose(compute_ti_per_turbine(site([80.0, 120.0], [0.10, 0.14]), xs, ys, hh_per_turb=hub),
                                   [0.12, 0.12], rtol=1e-6)
        np.testing.assert_allclose(compute_ti_per_turbine(site([131.0], [0.13]), xs, ys, hh_per_turb=hub),
                                   [0.13, 0.13], rtol=1e-6)
        # Not readable at the hub height: NULL, never the mean of the heights.
        for name, s, hh in (("repeated heights", site([50.0, 50.0], [0.1, 0.3]), hub),
                            ("no hub heights", site([80.0, 120.0], [0.10, 0.14]), None),
                            ("outside the heights", site([80.0, 90.0], [0.10, 0.14]), hub)):
            with self.subTest(name):
                self.assertTrue(np.isnan(compute_ti_per_turbine(s, xs, ys, hh_per_turb=hh)).all())

    def test_the_result_carries_it(self):
        rows = self.aep({}, fixed_ti=0.07)["per_turbine_table"]
        self.assertTrue(all(abs(r["ti_ambient"] - 0.07) < 1e-6 for r in rows))
        with mock.patch.object(ac, "_compute_ti_per_turbine",
                               side_effect=lambda site, xs, ys, **k: np.full(len(xs), np.nan, dtype=np.float32)):
            rows = self.aep({})["per_turbine_table"]
        self.assertEqual({r["ti_ambient"] for r in rows}, {None})


class NoGlobalStateTest(_Case):
    def raster(self):
        out = tempfile.mkdtemp(dir=self.folder)
        return raster.compute_wake_raster_config([model()], wake_config=cfg.default_config(), wrg_paths=[self.wrg],
                                                 fixed_ti=0.08, wd_target=270.0, resolution_m=250.0, output_dir=out)

    def test_an_aep_with_pud_does_not_change_the_raster_after_it(self):
        before = self.raster()["mean_ws"]
        self.aep({"engine": "PropagateUpDownIterative", "deficit_params": {"use_effective_ws": True}})
        self.assertEqual(self.raster()["mean_ws"], before)
        self.assertFalse(hasattr(ac, "_FORCE_EFFECTIVE_WS"))

    def test_the_aep_holds_the_shared_lock(self):
        from VelantisWind.ag_core.simulation.pywake_lock import PYWAKE_LOCK
        owned = []
        real = runner.simulate

        def spy(*a, **k):
            owned.append(PYWAKE_LOCK._is_owned())
            return real(*a, **k)
        with mock.patch.object(runner, "simulate", side_effect=spy):
            self.aep()
        self.assertTrue(owned and all(owned))


class ReportTest(_Case):
    # The pip command of the hint, as off Windows (in QGIS for Windows, h5py is not installed with pip).
    @mock.patch("VelantisWind.ag_core.wake_setup.validation.sys", types.SimpleNamespace(platform="linux"))
    def test_the_report_shows_the_selection_and_what_was_executed(self):
        config = api.gaussian_overlap_adaptation(
            cfg.WakeConfig(**{**cfg.default_config().__dict__, "rotor": cfg.Component("GaussianOverlapAvgModel", {})}),
            ["h5py"])
        r = self.aep(None, wake_physics=api.to_wake_physics(config))
        html = model_config_html(r)
        self.assertIn("GaussianOverlapAvgModel", html)  # the user's selection
        self.assertIn("CGIRotorAvg(n=7, nodos=7)", html)  # what was executed, read from the object
        self.assertIn("background:#fff3cd", html)  # the difference, highlighted
        self.assertEqual(html.count("porque no está disponible h5py"), 1)
        self.assertIn("python -m pip install h5py", html)
        self.assertIn("si ya está instalado y no carga", html)  # pip is not promised (decision 22, predefined models)
        self.assertNotIn("preset", html.lower())
        # The raster's JSON says the same: the user's selection and the adaptation.
        import json
        out = raster.compute_wake_raster_config([model()], wake_config=config, wrg_paths=[self.wrg], fixed_ti=0.08,
                                                wd_target=270.0, resolution_m=250.0,
                                                output_dir=tempfile.mkdtemp(dir=self.folder))
        with open(out["metadata_path"], encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertEqual(meta["wake_config"]["selected"]["rotor"]["class"], "GaussianOverlapAvgModel")
        self.assertEqual(meta["wake_config"]["effective"]["rotor"], {"class": "CGIRotorAvg", "params": {"n": 7}})
        self.assertEqual(meta["wake_config"]["adaptations"][0]["missing"], "h5py")
        self.assertTrue(any("porque no está disponible h5py" in w for w in meta["warnings"]))
        from VelantisWind import i18n
        from VelantisWind.ag_core.results.model_config_translations import register_model_config_translations
        register_model_config_translations()
        with mock.patch.object(i18n, "current_language", return_value="en"):
            english = model_config_html(r, i18n.tr_text)
        self.assertIn("What was executed differs from the selection", english)
        self.assertIn("Executed configuration (read from the objects)", english)

    def test_the_configuration_follows_its_contract(self):
        # P0, section 8: the keys of wake_config, with the request of the previous schema and its translation.
        keys = {"selected", "effective", "expected_classes", "executed", "differences_vs_signature",
                "differences_vs_selection", "adaptations", "legacy_request", "identification"}
        r = self.aep(None, wfm_engine="PDW", wake_deficit_model="NOJ")
        self.assertEqual(set(r["wake_config"]), keys)
        self.assertEqual(r["wake_config"]["legacy_request"]["given"], {"wfm_engine": "PDW", "wake_deficit_model": "NOJ"})
        self.assertEqual(r["wake_config"]["legacy_request"]["translated"],
                         {"version": 1, "engine": "PropagateDownwind", "deficit": "NOJDeficit"})
        self.assertEqual(r["wake_config"]["effective"], cfg.WakeConfig.from_dict(r["wake_config"]["effective"]).to_dict())
        self.assertIn("wfm_engine = &#x27;PDW&#x27;", model_config_html(r))  # escaped in the HTML
        r = self.aep({})
        self.assertEqual(set(r["wake_config"]), keys)
        self.assertIsNone(r["wake_config"]["legacy_request"])
        self.assertNotIn("esquema anterior", model_config_html(r))

    def test_the_identification_is_translated(self):
        from VelantisWind import i18n
        from VelantisWind.ag_core.results.model_config_translations import register_model_config_translations
        from VelantisWind.ag_core.wake_setup.messages_translations import register_messages_translations
        register_messages_translations()
        register_model_config_translations()
        r = self.aep({"deficit": "NOJDeficit", "rotor": {"class": "CGIRotorAvg", "n": 7}})
        self.assertEqual(str(r["wake_config"]["identification"]),
                         "NOJDeficit · motor PropagateDownwind · superposición LinearSum · turbulencia ninguna · "
                         "bloqueo ninguno · valores de su firma salvo: rotor = CGIRotorAvg(n=7)")
        expected = {"en": "NOJDeficit · engine PropagateDownwind · superposition LinearSum · turbulence none · "
                          "blockage none · values of its signature except: rotor = CGIRotorAvg(n=7)",
                    "fr": "NOJDeficit · moteur PropagateDownwind · superposition LinearSum · turbulence aucune · "
                          "blocage aucun · valeurs de sa signature sauf : rotor = CGIRotorAvg(n=7)",
                    "de": "NOJDeficit · Rechenkern PropagateDownwind · Überlagerung LinearSum · Turbulenz keine · "
                          "Blockade keiner · Werte seiner Signatur außer: rotor = CGIRotorAvg(n=7)"}
        for language, text in expected.items():
            with self.subTest(language=language), mock.patch.object(i18n, "current_language", return_value=language):
                html = model_config_html(r, i18n.tr_text)
                self.assertIn(text, html)
                self.assertNotIn("valores de su firma", html)
                self.assertNotIn("nodos", html)  # the nodes of the rotor, translated too
                self.assertIn("CGIRotorAvg(n=7, {}=7)".format({"en": "nodes", "fr": "nœuds", "de": "Knoten"}[language]),
                              html)

    def test_the_report_marks_the_argument_passed(self):
        # An argument the object does not keep is the argument passed, and the report says so.
        html = model_config_html(self.aep({"rotor": "EqGridRotorAvg"}))
        self.assertIn("EqGridRotorAvg(n=4 [argumento pasado], nodos=16)", html)

    def test_the_comparator_tells_the_ground_apart(self):
        from VelantisWind.results_dialog import ScenarioComparisonDialog
        a = self.aep({"deficit": "TurboGaussianDeficit"})
        b = self.aep({"deficit": "TurboGaussianDeficit", "ground": None})
        dlg = ScenarioComparisonDialog(None, a, b, "A", "B")
        self.addCleanup(dlg.deleteLater)
        from VelantisWind.results_dialog import _fill_slots
        html = _fill_slots(dlg._user_texts, dlg._config_html())
        self.assertIn("Mirror", html)
        self.assertIn("Efecto suelo", html)

    def test_the_html_export_with_another_tab(self):
        from VelantisWind.results_dialog import AEPResultsDialog
        from tests.test_breakdown_consumers import v1_result
        for result in (self.aep(), v1_result()):
            with self.subTest(schema=result.get("result_schema_version", 1)):
                dlg = AEPResultsDialog(None, result)
                self.addCleanup(dlg.deleteLater)
                dlg.show()
                dlg.tabs.setCurrentIndex(dlg.tabs.count() - 1)  # another tab active
                kpis = dlg._global_kpi_html()
                dlg.hide()
                self.assertGreater(kpis.count("<tr>"), 2)


    def test_the_installation_texts_do_not_promise_pip(self):
        # Decision 22 of the predefined models: what is missing may be installed but not load: «not available», pip as
        # a possibility and the installation instructions, in the four languages; in QGIS for Windows, h5py is not
        # installed with pip (its HDF5 may conflict with the one QGIS loads), as the installation instructions say.
        # Translated now, never left for the final sweep.
        from VelantisWind import i18n
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        from VelantisWind.ag_core.log_text import shown
        from VelantisWind.ag_core.wake_setup import notices, validation
        from VelantisWind.ag_core.wake_setup.messages_translations import register_messages_translations
        from VelantisWind.ag_core.wake_setup.validation import layout_issues, validate
        from tests.pending_translations import PENDING
        register_messages_translations()
        go = cfg.WakeConfig(**{**cfg.default_config().__dict__, "rotor": cfg.Component("GaussianOverlapAvgModel", {})})
        expected = {  # the cause, the old cause, it may not load, the instructions, and h5py without pip on Windows
            "es": ("no están disponibles", "que no están instaladas", ("no carga",), "instrucciones de instalación",
                   ("QGIS para Windows", "h5py no se instala con pip", "puede chocar con la que ya carga QGIS")),
            "en": ("not available", "which are not installed", ("not load",), "installation instructions",
                   ("QGIS on Windows", "h5py is not installed with pip", "may conflict with the one QGIS")),
            "fr": ("pas disponibles", "qui ne sont pas installées", ("ne se charge",), "instructions d’installation",
                   ("QGIS sous Windows", "h5py ne s’installe pas avec pip", "peut entrer en conflit avec celle")),
            "de": ("nicht verfügbar", "die nicht installiert sind", ("nicht lädt", "nicht laden"),
                   "Installationsanleitung",
                   ("QGIS unter Windows", "h5py nicht mit pip installiert", "mit der kollidieren kann")),
        }
        for platform in ("linux", "win32"):
            for language, (cause, old, load, instructions, windows) in expected.items():
                for missing in (["h5py"], ["h5py", "h5netcdf"]):
                    with self.subTest(platform=platform, language=language, missing=missing), \
                            mock.patch.object(validation, "sys", types.SimpleNamespace(platform=platform)), \
                            mock.patch.object(i18n, "current_language", return_value=language), \
                            mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                                       return_value=missing):
                        r13 = [i for i in validate(go) + layout_issues(go, 2) if i.code == "R13"]
                        note = notices.adaptation_notes(api.gaussian_overlap_adaptation(go, missing))
                        texts = [i.translated(i18n.tr_text) for i in r13] + [str(shown(n, i18n.tr_text)) for n in note]
                        self.assertEqual(len(texts), 2)
                        self.assertIn(cause, texts[0])
                        self.assertNotIn(old, texts[0])
                        for text in texts:
                            self.assertIn(instructions, text)
                            if platform == "win32":
                                for part in windows:
                                    self.assertIn(part, text)
                                self.assertNotIn("pip install h5py", text)
                                if "h5netcdf" in missing:
                                    self.assertIn('python -m pip install "h5netcdf>=1.8"', text)
                                else:
                                    self.assertNotIn("-m pip", text)
                            else:
                                self.assertNotIn("Windows", text)
                                self.assertTrue(any(w in text for w in load), text)
                                self.assertIn("python -m pip install " + " ".join(
                                    '"h5netcdf>=1.8"' if m == "h5netcdf" else m for m in missing), text)
        sources = [i.message for i in r13] + [
            notices.GO_ADAPTATION_NOTE, notices.GO_ADAPTATION_NOTE_PLURAL, notices.GO_SAVED_NOTE,
            notices.GO_SAVED_NOTE_PLURAL, validation.INSTALL_PIP, validation.INSTALL_PIP_PLURAL,
            validation.INSTALL_WINDOWS_H5PY, validation.INSTALL_WINDOWS_H5PY_AND_PIP,
            AEPSetupDialog.GO_MISSING_QUESTION, AEPSetupDialog.GO_MISSING_QUESTION_PLURAL,
            AEPSetupDialog.GO_MISSING_PRESET]
        self.assertEqual([s for s in sources if s in PENDING], [])  # PENDING is left out of the completeness tests

    # The pip command of the hint, as off Windows (in QGIS for Windows, h5py is not installed with pip).
    @mock.patch("VelantisWind.ag_core.wake_setup.validation.sys", types.SimpleNamespace(platform="linux"))
    def test_the_adaptation_note_agrees_in_number(self):
        from VelantisWind import i18n
        from VelantisWind.ag_core.log_text import shown
        from VelantisWind.ag_core.wake_setup.messages_translations import register_messages_translations
        from VelantisWind.ag_core.wake_setup.notices import adaptation_notes
        register_messages_translations()
        go = cfg.WakeConfig(**{**cfg.default_config().__dict__, "rotor": cfg.Component("GaussianOverlapAvgModel", {})})
        expected = {
            "es": ("porque no está disponible h5py (", "porque no están disponibles h5py, h5netcdf ("),
            "en": ("because h5py is not available", "because h5py, h5netcdf are not available"),
            "fr": ("car h5py n’est pas disponible", "car h5py, h5netcdf ne sont pas disponibles"),
            "de": ("weil h5py nicht verfügbar ist", "weil h5py, h5netcdf nicht verfügbar sind"),
        }
        for language, (one, two) in expected.items():
            for missing, text in ((["h5py"], one), (["h5py", "h5netcdf"], two)):
                with self.subTest(language=language, missing=missing), \
                        mock.patch.object(i18n, "current_language", return_value=language):
                    notes = adaptation_notes(api.gaussian_overlap_adaptation(go, missing))
                    self.assertEqual(len(notes), 1)
                    note = str(shown(notes[0], i18n.tr_text))
                    self.assertIn(text, note)
                    self.assertIn("pip install " + " ".join(
                        '"h5netcdf>=1.8"' if m == "h5netcdf" else m for m in missing), note)


class DialogTest(unittest.TestCase):
    def setUp(self):
        from qgis.core import QgsProject
        QgsProject.instance().clear()
        self.settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        for key in self.settings.allKeys():
            self.settings.remove(key)
        self.addCleanup(lambda: [self.settings.remove(k) for k in self.settings.allKeys()])
        # The manual mode, chosen: without preferences the group opens with the predefined models.
        from VelantisWind.ui_core import wake_group as wg
        self.settings.setValue(wg.MODE_KEY, wg.MANUAL)

    def dialog(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        d = AEPSetupDialog()
        self.addCleanup(d.deleteLater)
        return d

    def test_the_old_preferences_are_inactive_and_said_once(self):
        old = {"last_wfm_engine": "A2A", "last_wake_deficit": "TURBOPARK", "last_superposition_model": "AUTO",
               "wake_param/BG/k": 0.05}
        for key, value in old.items():
            self.settings.setValue(key, value)
        first = self.dialog()
        self.assertEqual(first.wake_group.config(), cfg.default_config())  # nothing of them is read
        self.assertIn("ya no se usan", first.wake_group.lbl_preferences.text())
        second = self.dialog()
        self.assertNotIn("ya no se usan", second.wake_group.lbl_preferences.text())
        self.assertEqual(set(old) - set(self.settings.allKeys()), set())  # never deleted

    def test_the_new_choices_are_remembered(self):
        d = self.dialog()
        d.wake_group.combo[cat.ENGINE].setCurrentIndex(d.wake_group.combo[cat.ENGINE].findData("All2AllIterative"))
        self.assertEqual(self.dialog().wake_group.config().engine.name, "All2AllIterative")

    def test_the_configuration_reaches_the_calculation(self):
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("NiayifarGaussianDeficit"))
        g.combo[cat.TURBULENCE].setCurrentIndex(g.combo[cat.TURBULENCE].findData("STF2017TurbulenceModel"))
        g.deficit_editor.control("ceps").setText("0.2149")  # exactly as typed (#75, row 1.4)
        with mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            physics = d._wake_physics_for_run()
        warning.assert_not_called()
        self.assertEqual(api.resolve_request(physics)[0], g.config())
        self.assertEqual(api.resolve_request(physics)[0].deficit.params["ceps"], 0.2149)

    def test_the_settings_of_the_engine_accepted_in_its_window_reach_the_calculation(self):
        # D5 of #64: what «Aceptar» keeps in the window of the engine is what _wake_physics_for_run gives.
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("PropagateUpDownIterative"))
        g.deficit_editor.set_values({"use_effective_ws": True})
        window = g.open_engine_window(exec_=False)
        self.addCleanup(window.deleteLater)
        window.editor.control("max_iter").setText("7")
        g.accept_engine_window(window)
        with mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            physics = d._wake_physics_for_run()
        warning.assert_not_called()
        self.assertEqual(api.resolve_request(physics)[0].engine.params["max_iter"], 7)

    def test_a_conflict_stops_with_its_reasons(self):
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("ZongGaussianDeficit"))
        with mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            self.assertIsNone(d._wake_physics_for_run())
        self.assertIn("PyWake exige un modelo de turbulencia", warning.call_args.args[2])

    def test_the_dependency_question_in_its_three_cases(self):
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        for missing, libs in ((["h5py"], "la librería h5py"), (["h5netcdf"], "la librería h5netcdf"),
                              (["h5py", "h5netcdf"], "las librerías h5py y h5netcdf")):
            for choice in ("Continuar", "Cancelar"):
                texts = []

                def exec_(box, choice=choice):
                    texts.append(box.text())

                def clicked(box, choice=choice):
                    return next(b for b in box.buttons() if b.text() == choice)
                with self.subTest(missing=missing, choice=choice), \
                        mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                                   return_value=missing), \
                        mock.patch.object(QtWidgets.QMessageBox, "exec_", exec_), \
                        mock.patch.object(QtWidgets.QMessageBox, "clickedButton", clicked):
                    physics = d._wake_physics_for_run()
                    self.assertIn(libs, texts[0])
                    # The verb agrees with what is missing.
                    self.assertIn(("no están disponibles " if len(missing) > 1 else "no está disponible ") + libs,
                                  texts[0])
                    self.assertIn("Pulsa Continuar para calcular el AEP con CGIRotorAvg(7)", texts[0])
                    if choice == "Cancelar":
                        self.assertIsNone(physics)
                    else:
                        config = api.resolve_request(physics)[0]
                        self.assertEqual(config.rotor, cfg.Component("CGIRotorAvg", {"n": 7}))
                        self.assertEqual(config.adaptations[0]["missing"], ", ".join(missing))
                        self.assertEqual(api.user_selection(config).rotor.name, "GaussianOverlapAvgModel")

    def test_the_answer_of_the_dependency_question_is_for_one_launch(self):
        # Decision 20 of the predefined models: «Continuar» authorizes its launch; the second reading (``ask`` false,
        # after saving the edits of a layer) keeps it only with the same context, and asks again otherwise.
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        asked, missing = [], ["h5py"]

        def run(**kwargs):
            with mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                            side_effect=lambda: list(missing)), \
                    mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda box: asked.append(box.text())), \
                    mock.patch.object(QtWidgets.QMessageBox, "clickedButton",
                                      lambda box: next(b for b in box.buttons() if b.text() == "Continuar")):
                physics = d._wake_physics_for_run(**kwargs)
            return api.resolve_request(physics)[0].rotor.name
        self.assertEqual(run(n_turbines=2), "CGIRotorAvg")
        self.assertEqual(len(asked), 1)
        self.assertEqual(run(ask=False, n_turbines=3), "CGIRotorAvg")  # the same launch: not asked again
        self.assertEqual(len(asked), 1)
        # A new launch that does not ask (one turbine) forgets it: its second reading with two asks.
        self.assertEqual(run(n_turbines=1), "GaussianOverlapAvgModel")
        self.assertEqual(run(ask=False, n_turbines=2), "CGIRotorAvg")
        self.assertEqual(len(asked), 2)
        # Another product, other missing libraries or another configuration in the second reading: asked again.
        run(n_turbines=2)
        asked.clear()
        run(what="ráster", ask=False, n_turbines=2)
        missing.append("h5netcdf")
        run(what="ráster", ask=False, n_turbines=2)
        g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("All2AllIterative"))
        run(what="ráster", ask=False, n_turbines=2)
        self.assertEqual(len(asked), 3)
        # The libraries available in the second reading: GaussianOverlap, nothing asked.
        missing.clear()
        self.assertEqual(run(what="ráster", ask=False, n_turbines=2), "GaussianOverlapAvgModel")
        self.assertEqual(len(asked), 3)

    def test_the_dependency_question_only_where_pywake_reads_the_table(self):
        # Decision 6.1 of #64: with PropagateDownwind, from the second turbine, and in the raster; with All2AllIterative,
        # always; never when GaussianOverlap is refused before reading its table (R11, NOJ).
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        asked = []
        with mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules",
                        return_value=["h5py"]), \
                mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda box: asked.append(box.text())), \
                mock.patch.object(QtWidgets.QMessageBox, "clickedButton", lambda box: None):
            for what, n, expected in (("AEP", 1, False), ("AEP", 2, True), ("AEP", None, True), ("ráster", 1, True)):
                with self.subTest(what=what, turbines=n):
                    asked.clear()
                    d._wake_physics_for_run(what, n_turbines=n)
                    self.assertEqual(bool(asked), expected)
            g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("All2AllIterative"))
            asked.clear()
            d._wake_physics_for_run(n_turbines=1)
            self.assertTrue(asked)
            g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("PropagateDownwind"))
            g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("NOJDeficit"))
            g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
            asked.clear()
            with mock.patch.object(QtWidgets.QMessageBox, "warning"):
                d._wake_physics_for_run(n_turbines=2)
            self.assertEqual(asked, [])  # R11: a note of the group, checked with the turbines when calculating
            # With another cause from the second turbine (R17): asked too (the resource may leave one turbine, where
            # R13 is the only reason of the raster).
            g.combo[cat.DEFICIT].setCurrentIndex(g.combo[cat.DEFICIT].findData("NiayifarGaussianDeficit"))
            g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
            g.combo[cat.TURBULENCE].setCurrentIndex(g.combo[cat.TURBULENCE].findData("STF2017TurbulenceModel"))
            editor = g.args_editor(cat.TURBULENCE)
            editor.control("rotorAvgModel").setCurrentIndex(editor.control("rotorAvgModel").findData("AreaOverlapAvgModel"))
            for n, expected in ((1, True), (2, True)):
                with self.subTest(raster_turbines=n):
                    asked.clear()
                    d._wake_physics_for_run("ráster", n_turbines=n)
                    self.assertEqual(bool(asked), expected)

    def test_the_dependency_question_agrees_in_each_language(self):
        from VelantisWind import i18n
        d = self.dialog()
        g = d.wake_group
        g.combo[cat.ROTOR].setCurrentIndex(g.combo[cat.ROTOR].findData("GaussianOverlapAvgModel"))
        cases = (("en", ["h5py"], "because the library h5py is not available"),
                 ("en", ["h5py", "h5netcdf"], "because the libraries h5py and h5netcdf are not available"),
                 ("fr", ["h5py"], "car la bibliothèque h5py n’est pas disponible"),
                 ("fr", ["h5py", "h5netcdf"], "car les bibliothèques h5py et h5netcdf ne sont pas disponibles"),
                 ("de", ["h5py"], "weil die Bibliothek h5py nicht verfügbar ist"),
                 ("de", ["h5py", "h5netcdf"], "weil die Bibliotheken h5py und h5netcdf nicht verfügbar sind"))
        for language, missing, expected in cases:
            texts = []
            with self.subTest(language=language, missing=missing), \
                    mock.patch.object(i18n, "current_language", return_value=language), \
                    mock.patch("VelantisWind.ag_core.wake_setup.validation.missing_gaussian_overlap_modules", return_value=missing), \
                    mock.patch.object(QtWidgets.QMessageBox, "exec_", lambda box: texts.append(box.text())), \
                    mock.patch.object(QtWidgets.QMessageBox, "clickedButton", lambda box: None):
                d._wake_physics_for_run()
                self.assertIn(expected, texts[0])

    def test_the_group_is_not_translated_twice(self):
        # The dialog and the dock translate their widgets again (apply_i18n); the group sets its texts translated,
        # so they are left alone (a second translation reads them back as Spanish fragments).
        from VelantisWind import i18n
        from VelantisWind.mapa_interactivo_dock import InteractiveMapDock

        def texts(widget):
            out = []
            for w in [widget] + widget.findChildren(QtWidgets.QWidget):
                out.append(w.toolTip())
                if hasattr(w, "text"):
                    out.append(w.text())
            return " ".join(t for t in out if t)
        for language, spoiled in (("en", ("efectiva", "Bloqueo")), ("fr", ("Modèle =", "superpositionModèle")),
                                  ("de", ("Jahr der", "Modell ="))):
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                d = self.dialog()
                g = d.wake_group
                g.combo[cat.ENGINE].setCurrentIndex(g.combo[cat.ENGINE].findData("PropagateUpDownIterative"))
                g.combo[cat.BLOCKAGE].setCurrentIndex(g.combo[cat.BLOCKAGE].findData("SelfSimilarityDeficit2020"))
                i18n.apply_i18n(d)  # as the dialog does when it rebuilds its rows
                window = QtWidgets.QMainWindow()
                self.addCleanup(window.deleteLater)
                with mock.patch("VelantisWind.mapa_interactivo_dock.iface"):
                    dock = InteractiveMapDock(d, parent=window)
                shown_texts = texts(g) + " " + " ".join(l.text() for l in dock._wake_mirror.labels.values())
                for bad in spoiled:
                    self.assertNotIn(bad, shown_texts)
                self.assertIn("groundModel", texts(g))  # an argument of the blockage (#64), by its PyWake name
                if language == "en":
                    self.assertIn("effective wind speed", texts(g))
                    self.assertEqual(dock._wake_mirror.labels[cat.BLOCKAGE].text(), "Blockage")  # no colon (D2)

    def test_the_interactive_map_mirrors_the_group(self):
        from VelantisWind.mapa_interactivo_dock import InteractiveMapDock
        d = self.dialog()
        window = QtWidgets.QMainWindow()
        self.addCleanup(window.deleteLater)
        with mock.patch("VelantisWind.mapa_interactivo_dock.iface"):
            dock = InteractiveMapDock(d, parent=window)
        mirror = dock._wake_mirror
        self.assertIs(mirror.group, d.wake_group)
        mirror.combo[cat.ENGINE].setCurrentIndex(mirror.combo[cat.ENGINE].findData("PropagateUpDownIterative"))
        self.assertEqual(d.wake_group.config().engine.name, "PropagateUpDownIterative")
        self.assertIn("velocidad efectiva", mirror.notes[cat.DEFICIT].text())  # under «Déficit de estela» (R3)


if __name__ == "__main__":
    unittest.main()
