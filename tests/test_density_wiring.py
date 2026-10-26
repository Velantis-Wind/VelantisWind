# -*- coding: utf-8 -*-
"""Per-turbine air density in the AEP run and the wake raster."""
import copy
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem

from VelantisWind.ag_core import aep_compute
from VelantisWind.ag_core.log_text import log_text
from VelantisWind.ag_core.physics.air_density import AirDensityError, calibrated_air_density
from VelantisWind.ag_core.turbine import build_wt_from_curve_table, build_wt_from_manual
from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.wake_setup import api as wake_api
from VelantisWind.ag_core.wake_setup import config as wake_cfg
from VelantisWind.wake_core import raster as wake_raster

WS = (3.0, 6.0, 9.0, 12.0, 25.0)
# Two turbines on a terrain that rises 600 m per 500 m in x: hubs at 90 m and 1290 m.
LAYOUT = [(1000.0, 1500.0), (2000.0, 1500.0)]
PER_TURBINE = {"mode": "per_turbine", "reference_density_kg_m3": 1.2, "reference_altitude_m": 90.0}


def write_wrg(folder):
    path = os.path.join(folder, "site.wrg")
    lines = ["3 3 1000 1000 500"]
    for iy in range(3):
        for ix in range(3):
            sectors = " ".join("250 90 210" for _ in range(4))
            lines.append(f"{1000 + 500 * ix} {1000 + 500 * iy} {600 * ix} 90 9.0 2.1 300 4 {sectors}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def table_turbine(name="Table", densities=(1.0, 1.225), default=1.225):
    """Power and Ct that change strongly with density, so a lost density shows."""
    n = len(densities)
    power = tuple(tuple(p * (0.8 + 0.2 * j / max(n - 1, 1)) for j in range(n)) for p in (40.0, 600.0, 1900.0, 3000.0, 3000.0))
    ct = tuple(tuple(c * (1.0 - 0.4 * j / max(n - 1, 1)) for j in range(n)) for c in (0.8, 0.8, 0.7, 0.4, 0.1))
    table = TurbineCurveTable(
        name=name, diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=WS, air_densities=tuple(densities),
        power_kw=power, ct=ct, default_air_density=default, cut_in_ms=3.0, cut_out_ms=25.0,
    )
    return build_wt_from_curve_table(table)


def one_density_turbine(name="Curve"):
    return build_wt_from_manual(name, 100.0, 90.0, list(WS), [40.0, 600.0, 1900.0, 3000.0, 3000.0], [0.8, 0.8, 0.7, 0.4, 0.1])


def model(wt, coords, name=None):
    name = name or wt.name(0)
    return {"name": name, "wt": wt, "meta": {"hh": 90.0, "diam": 100.0, "p_rated_kw": 3000.0}, "coords_xy": list(coords)}


class DensityRunTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.wrg = write_wrg(self.folder)

    def aep(self, models, density, **kwargs):
        return aep_compute.compute_aep_from_ui(
            "", models, wrg_paths=[self.wrg], fixed_ti=0.1, compute_variants=False,
            air_density_mode=density.get("mode"), air_density_ref_kg_m3=density.get("reference_density_kg_m3"),
            air_density_ref_altitude_m=density.get("reference_altitude_m"), **kwargs,
        )

    def raster(self, models, density):
        """The raster with the configuration of the AEP (the default one) and its inputs."""
        return wake_raster.compute_wake_raster_config(
            models, wake_config=wake_cfg.default_config(), wrg_paths=[self.wrg], fixed_ti=0.1, resolution_m=250.0,
            wd_target=270.0, output_dir=self.folder, crs_authid="EPSG:32630", air_density=density,
        )

    @staticmethod
    def free_mwh(result):
        return [row["aep_free_mwh"] for row in result["per_turbine_table"]]


class PerTurbineAepTest(DensityRunTest):
    def test_turbines_at_different_altitudes_get_different_curves_in_the_simulation(self):
        result = self.aep([model(table_turbine(), LAYOUT)], PER_TURBINE)
        info = result["air_density"]
        expected = calibrated_air_density(np.array([90.0, 1290.0]), reference_density=1.2, reference_altitude_m=90.0)
        np.testing.assert_allclose(info["values_kg_m3"], expected)
        self.assertEqual(info["terrain_elevation_m"], [0.0, 1200.0])
        self.assertEqual(info["hub_altitude_m"], [90.0, 1290.0])
        # Each turbine produces what the whole park would produce at its own density.
        for i, rho in enumerate(expected):
            uniform = self.aep([model(table_turbine(), LAYOUT)], {"mode": "uniform", "reference_density_kg_m3": float(rho)})
            self.assertAlmostEqual(self.free_mwh(result)[i], self.free_mwh(uniform)[i], places=6)
        self.assertGreater(self.free_mwh(result)[0], self.free_mwh(result)[1])

    def test_table_and_notes_carry_the_density(self):
        result = self.aep([model(table_turbine(), LAYOUT)], PER_TURBINE)
        rows = result["per_turbine_table"]
        self.assertEqual([row["hub_altitude_m"] for row in rows], [90.0, 1290.0])
        self.assertAlmostEqual(rows[0]["air_density_kg_m3"], 1.2)
        self.assertTrue(any("ISA calibrado" in str(note) for note in result["simulation_notes"]))

    def record(self):
        from VelantisWind.ag_core.simulation import runner
        calls = []
        real = runner.simulate

        def recording(wfm, *args, **kwargs):
            calls.append(dict(kwargs.get("wt_inputs") or {}))
            return real(wfm, *args, **kwargs)
        return calls, mock.patch.object(runner, "simulate", recording)

    def test_every_simulation_receives_the_density(self):
        calls, patch = self.record()
        with patch:
            result = aep_compute.compute_aep_from_ui(
                "", [model(table_turbine(), LAYOUT)], wrg_paths=[self.wrg], fixed_ti=0.1, compute_variants=True,
                include_turbulence=True, turbulence_model="STF2017", include_blockage=True,
                blockage_deficit_model="SS2020", wfm_engine="A2A",
                air_density_mode="per_turbine", air_density_ref_kg_m3=1.2, air_density_ref_altitude_m=90.0,
            )
        expected = result["air_density"]["values_kg_m3"]
        # The main run, the free stream and the three variants of the breakdown (A_W, A_WT, A_WB).
        self.assertEqual(len(calls), 5)
        for call in calls:
            np.testing.assert_allclose(call["Air_density"], expected)

    def test_the_turbogaussian_class_receives_the_density(self):
        calls, patch = self.record()
        with patch:
            result = self.aep([model(table_turbine(), LAYOUT)], PER_TURBINE, wake_deficit_model="TG")
        self.assertGreaterEqual(len(calls), 2)
        for call in calls:
            np.testing.assert_allclose(call["Air_density"], result["air_density"]["values_kg_m3"])


class ErrorPolicyTest(DensityRunTest):
    def test_aep_and_raster_stop_on_the_same_input(self):
        # The raster is not calculated with another density than the AEP's (#46 P4): both stop with the cause.
        density = dict(PER_TURBINE, reference_altitude_m=None)
        models = [model(table_turbine(), LAYOUT)]
        with self.assertRaisesRegex(AirDensityError, "Falta la altitud"):
            self.aep(models, density)
        with self.assertRaisesRegex(AirDensityError, "Falta la altitud"):
            self.raster(models, density)
        self.assertFalse([f for f in os.listdir(self.folder) if f.endswith(".tif")])

    def test_resource_with_its_own_density(self):
        from VelantisWind.ag_core.wrg_site import load_wrg_site
        site, ds, _used = load_wrg_site([self.wrg])
        site.ds["Air_density"] = 1.0
        models = [model(table_turbine(), LAYOUT)]
        with mock.patch.object(aep_compute._orchestration, "load_energy_site",
                               return_value=(site, site.ds, "", 0.1, "")):
            for mode in ("off", "per_turbine"):
                with self.subTest(mode=mode), self.assertRaisesRegex(AirDensityError, "su propia variable"):
                    self.aep(models, dict(PER_TURBINE, mode=mode))
                with self.subTest(mode=mode, route="raster"), self.assertRaisesRegex(AirDensityError,
                                                                                     "su propia variable"):
                    self.raster(models, dict(PER_TURBINE, mode=mode))


class RasterTest(DensityRunTest):
    def test_raster_uses_the_densities_of_the_aep(self):
        models = [model(table_turbine(), LAYOUT)]
        aep = self.aep(models, PER_TURBINE)
        raster = self.raster(models, PER_TURBINE)
        self.assertFalse([w for w in raster["warnings"] if "densidad" in w])
        np.testing.assert_allclose(raster["air_density"]["values_kg_m3"], aep["air_density"]["values_kg_m3"])
        # The density changes the thrust, so it changes the map.
        off = self.raster(models, {"mode": "off"})
        self.assertNotAlmostEqual(raster["min_ws"], off["min_ws"], places=4)

    def test_raster_configuration_comes_from_the_run_not_from_settings(self):
        from VelantisWind.wake_core import controller
        from VelantisWind.wake_core.domain import WakeRasterTaskConfig

        captured = {}
        dialog = types.SimpleNamespace(_wake_raster_task=None, btn_plot_wakes=None)
        context = (self.folder, "", "EPSG:32630", True, False, True, QgsCoordinateReferenceSystem("EPSG:32630"))

        def start(config, **callbacks):
            captured["config"] = config
            # A real QgsTask retains and completes this callback. The mock must
            # do the same, otherwise project signals outlive their test.
            self.addCleanup(callbacks["on_finished"], False, {}, "cancelled")
            return config

        with mock.patch.object(controller, "_capture_project_context", return_value=context), \
                mock.patch.object(controller, "_message_bar"), \
                mock.patch.object(controller, "start_wake_raster_task", side_effect=start), \
                mock.patch("qgis.PyQt.QtCore.QSettings") as settings:
            controller.start_wake_raster_from_dialog(
                dialog, models=[], wasp_dir="", resolution_m=300.0, wrg_paths=[], wake_config=None,
                wd_target=None, air_density=dict(PER_TURBINE),
            )
        self.assertFalse([call for call in settings.mock_calls if "air_density" in str(call)])
        self.assertIsInstance(captured["config"], WakeRasterTaskConfig)
        self.assertEqual(captured["config"].to_engine_kwargs()["air_density"], PER_TURBINE)

    def test_dialog_reading_of_the_density_controls(self):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog

        def spin(value, minimum):
            return mock.Mock(value=mock.Mock(return_value=value), minimum=mock.Mock(return_value=minimum))

        def read(checked, density, altitude):
            controls = types.SimpleNamespace(
                chk_air_density=mock.Mock(isChecked=mock.Mock(return_value=checked)),
                cb_air_density_mode=mock.Mock(currentData=mock.Mock(return_value="uniform")),
                sp_air_density=spin(density, 0.0), sp_air_density_alt=spin(altitude, -1000.0),
            )
            return AEPSetupDialog._get_air_density_settings(controls)

        self.assertEqual(read(False, 1.1, 250.0), {"mode": "off"})
        # A control left at its minimum is "not set": the run then stops for the missing reference.
        self.assertEqual(read(True, 0.0, -1000.0), {"mode": "uniform", "reference_density_kg_m3": None, "reference_altitude_m": None})
        self.assertEqual(read(True, 1.1, 250.0), {"mode": "uniform", "reference_density_kg_m3": 1.1, "reference_altitude_m": 250.0})
        unreadable = types.SimpleNamespace(chk_air_density=mock.Mock(isChecked=mock.Mock(side_effect=RuntimeError("deleted"))))
        with self.assertRaisesRegex(RuntimeError, "No se pudieron leer los controles de densidad"):
            AEPSetupDialog._get_air_density_settings(unreadable)

    def dialog(self, inputs):
        """A dialog that the AEP and the raster read in the same way, with ``inputs`` as its controls."""
        return types.SimpleNamespace(
            _rows=[{"name": "A", "wt": inputs["wt"], "meta": {}}],
            _collect_layer_points_for_row=lambda idx: list(inputs["points"]),
            _find_interactive_layer_for_row=lambda idx: types.SimpleNamespace(id=lambda: "layer-a", name=lambda: "A"),
            ed_dir=mock.Mock(text=lambda: ""),
            ed_wrg=mock.Mock(text=lambda: inputs["wrg"]),
            _qsettings=mock.Mock(value=lambda *a, **k: 200),
            ed_wrg_ti=mock.Mock(text=lambda: ""),
            _wake_physics_for_run=lambda what="AEP", ask=True, n_turbines=None: copy.deepcopy(inputs["physics"]),
            _wake_provenance_for_run=lambda: None,
            _get_fixed_ti_fraction=lambda: 0.1,
            _get_air_density_settings=lambda: dict(inputs["density"]),
            _get_resource_params=lambda: dict(inputs["params"]),
        )

    @staticmethod
    def launch(dialog):
        """What «Crear ráster de estelas» passes to the controller."""
        from qgis.PyQt import QtWidgets
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        from VelantisWind.wake_core import controller

        start = mock.Mock()
        with mock.patch.object(controller, "start_wake_raster_from_dialog", start), \
                mock.patch.object(QtWidgets.QInputDialog, "getInt", return_value=(200, True)), \
                mock.patch.object(QtWidgets.QInputDialog, "getItem", side_effect=lambda *a, **k: (a[3][0], True)):
            AEPSetupDialog._run_plot_wakes(dialog)
        kwargs = start.call_args.kwargs
        return kwargs["air_density"], kwargs["changed_aep_inputs"], kwargs["last_aep_available"]

    def test_raster_reads_every_input_from_the_dialog_and_says_which_differ_from_the_last_aep(self):
        from VelantisWind.energy_core import dialog_controller
        from VelantisWind.energy_core.dialog_state import build_energy_dialog_state

        other_wrg = os.path.join(self.folder, "other.wrg")
        shutil.copy(self.wrg, other_wrg)
        physics = wake_api.to_wake_physics(wake_cfg.default_config())
        inputs = {"wt": one_density_turbine(), "points": [(1000.0, 1500.0)], "wrg": self.wrg, "physics": physics,
                  "density": dict(PER_TURBINE), "params": {"direction_count": None, "wd_interp": "nearest", "ws_step": None}}
        dialog = self.dialog(inputs)

        def aep():
            # What the AEP runs with, read from the dialog as run_compute_and_update_from_dialog does.
            state = build_energy_dialog_state(dialog, project_crs_authid=dialog_controller._project_crs_authid(),
                                              warn=False)
            dialog_controller._remember_aep_inputs(dialog, state.to_energy_config())

        # Without an AEP, the controls and nothing to compare.
        self.assertEqual(self.launch(dialog), (PER_TURBINE, [], False))
        # An AEP and a raster without touching anything: the two summaries are the same.
        aep()
        self.assertEqual(self.launch(dialog), (PER_TURBINE, [], True))
        # The speed step of the AEP does not change the raster.
        inputs["params"]["ws_step"] = 0.5
        self.assertEqual(self.launch(dialog)[1], [])
        # The density is always the controls', and a change is said.
        uniform = {"mode": "uniform", "reference_density_kg_m3": 1.15, "reference_altitude_m": None}
        inputs["density"] = dict(uniform)
        self.assertEqual(self.launch(dialog), (uniform, ["densidad del aire"], True))
        aep()
        self.assertEqual(self.launch(dialog), (uniform, [], True))
        # Every category, in order.
        inputs.update(points=[(1500.0, 1500.0)], wrg=other_wrg,
                      physics=dict(physics, deficit_params=dict(physics["deficit_params"], k=0.04)),
                      density={"mode": "off"})
        with mock.patch.object(dialog_controller, "_project_crs_authid", return_value="EPSG:25830"):
            self.assertEqual(self.launch(dialog)[1], ["turbinas y posiciones", "recurso eólico y turbulencia",
                                                      "modelo de estela", "densidad del aire",
                                                      "sistema de coordenadas del proyecto"])

    def test_a_failed_aep_keeps_the_inputs_of_the_previous_one(self):
        from VelantisWind.energy_core import dialog_controller
        from VelantisWind.energy_core.dialog_state import build_energy_dialog_state

        inputs = {"wt": one_density_turbine(), "points": [(1000.0, 1500.0)], "wrg": self.wrg,
                  "physics": wake_api.to_wake_physics(wake_cfg.default_config()), "density": dict(PER_TURBINE),
                  "params": {"direction_count": None, "wd_interp": "nearest", "ws_step": None}}
        dialog = self.dialog(inputs)
        state = build_energy_dialog_state(dialog, project_crs_authid=dialog_controller._project_crs_authid(), warn=False)
        dialog_controller._remember_aep_inputs(dialog, state.to_energy_config())
        remembered = dialog._last_aep_inputs
        inputs["density"] = {"mode": "off"}
        with mock.patch.object(dialog_controller, "_project_crs_problem", return_value=None), \
                mock.patch.object(dialog_controller, "_read_dialog_state", side_effect=lambda d, warn=True:
                                  build_energy_dialog_state(d, project_crs_authid="EPSG:32630", warn=False)), \
                mock.patch.object(dialog_controller, "_validate_before_run", return_value=True), \
                mock.patch.object(dialog_controller, "_resolve_layers_in_edit_mode", return_value=False), \
                mock.patch.object(dialog_controller, "_run_energy_calculation", side_effect=RuntimeError("failed")), \
                mock.patch.object(dialog_controller, "show_user_critical") as error:
            dialog_controller.run_compute_and_update_from_dialog(dialog)
        error.assert_called_once()
        self.assertIs(dialog._last_aep_inputs, remembered)
        self.assertEqual(self.launch(dialog)[1], ["densidad del aire"])

    def final_window(self, result, changed, last_aep=True):
        """The text of the final window of a raster that has finished."""
        from VelantisWind.wake_core import controller

        captured = {}
        dialog = types.SimpleNamespace(_wake_raster_task=None, btn_plot_wakes=None)
        context = (self.folder, "", "EPSG:32630", True, False, True, QgsCoordinateReferenceSystem("EPSG:32630"))
        with mock.patch.object(controller, "_capture_project_context", return_value=context), \
                mock.patch.object(controller, "_message_bar"), \
                mock.patch.object(controller, "start_wake_raster_task",
                                  side_effect=lambda config, **kwargs: captured.update(kwargs, config=config)), \
                mock.patch.object(controller, "add_wake_raster_result_to_qgis", return_value=[]), \
                mock.patch.object(controller.QtWidgets.QMessageBox, "information") as window:
            controller.start_wake_raster_from_dialog(
                dialog, models=[], wasp_dir="", resolution_m=300.0, wrg_paths=[], wake_config=None,
                wd_target=None, air_density={"mode": "uniform", "reference_density_kg_m3": 1.15},
                changed_aep_inputs=changed, last_aep_available=last_aep,
            )
            captured["on_finished"](True, result, None)
        return window.call_args.args[2], captured["config"].to_engine_kwargs()["aep_comparison"]

    def test_final_window_shows_the_density_and_the_inputs_that_differ_from_the_last_aep(self):
        result = {
            "path": os.path.join(self.folder, "wake.tif"),
            "air_density": {"summary": log_text("densidad uniforme {reference:.4f} kg/m³", reference=1.15)},
            "warning_items": [],
        }
        same, comparison = self.final_window(result, [])
        self.assertIn("Densidad del aire: densidad uniforme 1.1500 kg/m³\n", same)
        self.assertNotIn("Avisos:", same)
        self.assertEqual(comparison, {"last_aep_available": True, "same_inputs_as_last_aep": True, "changed_inputs": []})
        _text, comparison = self.final_window(result, [], last_aep=False)
        self.assertEqual(comparison, {"last_aep_available": False, "same_inputs_as_last_aep": None, "changed_inputs": []})

        changed, comparison = self.final_window(result, ["densidad del aire", "modelo de estela"])
        self.assertIn("Avisos:\n• El ráster se ha calculado con las entradas actuales del diálogo, que difieren del "
                      "último AEP en: densidad del aire, modelo de estela. Vuelve a calcular el AEP", changed)
        self.assertEqual(comparison, {"last_aep_available": True, "same_inputs_as_last_aep": False,
                                      "changed_inputs": ["densidad del aire", "modelo de estela"]})
        # Every warning of the engine is shown after it: a density one after five others is not cut off.
        result["warning_items"] = [("Aviso {n}.", {"n": n}) for n in range(1, 6)] + [
            ("{n} turbina(s) quedan fuera del rango de densidad tabulado por su curva.", {"n": 3})
        ]
        many, _comparison = self.final_window(result, ["densidad del aire"])
        self.assertIn("Avisos:\n• El ráster se ha calculado con las entradas actuales", many)
        for n in range(1, 6):
            self.assertIn(f"• Aviso {n}.", many)
        self.assertIn("• 3 turbina(s) quedan fuera del rango de densidad", many)
        # The density could not be applied: the engine says which one was used, no density line, and the
        # differences are still said.
        result["air_density"] = None
        result["warning_items"] = [("No se aplicó la densidad del aire al ráster: {error}", {"error": "x"})]
        failed, _comparison = self.final_window(result, ["densidad del aire"])
        self.assertIn("No se aplicó la densidad del aire al ráster", failed)
        self.assertIn("difieren del último AEP en: densidad del aire.", failed)
        self.assertNotIn("Densidad del aire:", failed)

    def test_the_differences_are_said_in_the_language_of_the_interface(self):
        from VelantisWind.wake_core import controller

        result = {"path": os.path.join(self.folder, "wake.tif"), "warning_items": []}
        with mock.patch.object(controller, "tr_text", side_effect=lambda text: {
                "densidad del aire": "air density",
                "El ráster se ha calculado con las entradas actuales del diálogo, que difieren del último AEP en: "
                "{categories}. Vuelve a calcular el AEP para que el informe corresponda al mapa.":
                    "Differ in: {categories}."}.get(text, text)):
            text, _comparison = self.final_window(result, ["densidad del aire"])
        self.assertIn("• Differ in: air density.", text)


class MixedParkTest(DensityRunTest):
    def test_each_type_inside_its_own_table_is_not_clamped(self):
        low = table_turbine("Low", (0.95, 1.07))
        high = table_turbine("High", (1.07, 1.25))
        # Hub densities 1.2 (x=1000) and 1.067 (x=2000): each inside its own table only.
        models = [model(high, LAYOUT[:1]), model(low, LAYOUT[1:])]
        result = self.aep(models, PER_TURBINE)
        info = result["air_density"]
        self.assertEqual(info["clamped"], [False, False])
        alone = [self.aep([m], PER_TURBINE) for m in models]
        self.assertAlmostEqual(self.free_mwh(result)[0], self.free_mwh(alone[0])[0], places=6)
        self.assertAlmostEqual(self.free_mwh(result)[1], self.free_mwh(alone[1])[0], places=6)
        # Power and Ct of each turbine, as PyWake dispatches them by type.
        wt, _ = aep_compute._combine_wt(models)
        rho = np.asarray(info["values_kg_m3"])
        for i, single in enumerate((high, low)):
            mixed_power = wt.power(np.array([9.0, 9.0]), type=np.array([0, 1]), Air_density=rho)[i]
            self.assertAlmostEqual(float(mixed_power), float(single.power(np.array([9.0]), type=0, Air_density=rho[i:i + 1])[0]))
            mixed_ct = wt.ct(np.array([9.0, 9.0]), type=np.array([0, 1]), Air_density=rho)[i]
            self.assertAlmostEqual(float(mixed_ct), float(single.ct(np.array([9.0]), type=0, Air_density=rho[i:i + 1])[0]))
        raster = self.raster(models, PER_TURBINE)
        self.assertFalse(any("densidad" in warning for warning in raster["warnings"]))
        np.testing.assert_allclose(raster["air_density"]["values_kg_m3"], info["values_kg_m3"])

    def test_one_density_curve_keeps_its_power_and_ct(self):
        models = [model(table_turbine(), LAYOUT[:1]), model(one_density_turbine(), LAYOUT[1:])]
        with_density = self.aep(models, PER_TURBINE)
        without = self.aep(models, {"mode": "off"})
        self.assertAlmostEqual(self.free_mwh(with_density)[1], self.free_mwh(without)[1], places=6)
        # Its Ct, as PyWake dispatches it in the park, is the same with and without the density.
        rho = np.asarray(with_density["air_density"]["values_kg_m3"][:1] + [1.0])
        wt, _ = aep_compute._combine_wt(models)
        ws = np.arange(3.0, 25.0, 0.5)
        types = np.array([0, 1])
        for v in ws:
            on = wt.ct(np.array([v, v]), type=types, Air_density=rho)[1]
            off = wt.ct(np.array([v, v]), type=types)[1]
            self.assertEqual(float(on), float(off))
        self.assertIsNone(with_density["per_turbine_table"][1]["air_density_kg_m3"])
        wt, _ = aep_compute._combine_wt(models)
        curve = wt.powerCtFunction.windTurbineFunction_lst[1]
        self.assertNotIn("Air_density", list(curve.required_inputs) + list(curve.optional_inputs))

    def test_off_reports_each_type_default_by_position(self):
        a = table_turbine("A", default=1.225)
        b = table_turbine("B", default=1.0)
        models = [model(a, LAYOUT[1:]), model(b, LAYOUT[:1])]
        result = self.aep(models, {"mode": "off"})
        by_name = {row["model"]: row["air_density_kg_m3"] for row in result["per_turbine_table"]}
        self.assertEqual(by_name, {"A": 1.225, "B": 1.0})
        self.assertTrue(any("ajuste está desactivado" in str(note) for note in result["simulation_notes"]))


if __name__ == "__main__":
    unittest.main()
