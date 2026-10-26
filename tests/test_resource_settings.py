# -*- coding: utf-8 -*-
"""The resource settings of the AEP: the directions, interpolation, Speedup, wind speeds and hours each simulation
receives, with a WRG and with a GRD, their errors, and what the log and the result record."""
import inspect
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np

from VelantisWind.ag_core import aep_compute, wrg_site
from VelantisWind.ag_core.orchestration import resource_loader
from VelantisWind.ag_core.resource_grid import WrgContractError, direction_grid, speed_grid
from VelantisWind.ag_core.results.aep_arrays import _aggregate_to_sector_centers
from VelantisWind.ag_core.simulation import runner
from VelantisWind.ag_core.turbine import build_wt_from_manual
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput
from VelantisWind.energy_core.runner import EnergyRunner, EnergyValidationError
from py_wake.wind_turbines import WindTurbine, WindTurbines
from py_wake.wind_turbines.power_ct_functions import PowerCtFunction, PowerCtTabular

LAYOUT = [(1200.0, 1300.0), (1700.0, 1450.0)]
# Band 3-25 m/s with nodes every 3 m/s or more: initial step 1.
WS = [3.0, 6.0, 9.0, 12.0, 25.0]
POWER_KW = [0.0, 400.0, 1500.0, 3000.0, 3000.0]
CT = [0.8, 0.8, 0.7, 0.4, 0.1]


def wrg_text(nsec, height=90.0, a_shift=0.0):
    """A WRG of ``nsec`` sectors, 5×5 nodes every 500 m, with sector frequencies and A that change in space."""
    lines = ["5 5 1000 1000 500"]
    for iy in range(5):
        for ix in range(5):
            sectors = " ".join(
                f"{100 + 10 * ((s + ix) % nsec)} {int(round(10 * (8.0 + a_shift + 0.2 * ix + np.cos(2 * np.pi * s / nsec))))} 210"
                for s in range(nsec))
            lines.append(f"{1000 + 500 * ix} {1000 + 500 * iy} {10 * iy} {height:g} 9.0 2.1 300 {nsec} {sectors}")
    return "\n".join(lines) + "\n"


def write_wrg(folder, nsec, name="site.wrg", **kwargs):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(wrg_text(nsec, **kwargs))
    return path


def write_zip(folder, members, name="site.zip"):
    path = os.path.join(folder, name)
    with zipfile.ZipFile(path, "w") as z:
        for member, (nsec, height) in members.items():
            z.writestr(member, wrg_text(nsec, height=height))
    return path


def model(name="T", ws=WS, power=POWER_KW, ct=CT, layout=LAYOUT):
    return {"name": name, "wt": build_wt_from_manual(name, 100.0, 90.0, ws, power, ct),
            "meta": {"hh": 90.0, "diam": 100.0, "mode": "manual"}, "coords_xy": list(layout)}


def composite_model(other):
    """A model whose turbine is a composite of two types, of which the calculation takes the first (``A``)."""
    first = build_wt_from_manual("A", 100.0, 90.0, WS, POWER_KW, CT)
    return {"name": "A", "wt": WindTurbines.from_WindTurbine_lst([first, other]),
            "meta": {"hh": 90.0, "diam": 100.0, "mode": "manual"}, "coords_xy": list(LAYOUT), "source_type_index": 0}


def idle_turbine():
    """A turbine type with zero power at every node: no band of its own."""
    curve = PowerCtTabular([3.0, 8.0, 15.0, 25.0], [0.0, 0.0, 0.0, 0.0], "kW", [0.8, 0.8, 0.3, 0.1])
    curve.operating_band = (3.0, 25.0)
    return WindTurbine("B", 120.0, 90.0, curve)


def wide_turbine():
    """A turbine type with another band (2-28 m/s) and a finer initial step (0.5)."""
    ws = list(np.arange(2.0, 28.5, 0.5))
    return build_wt_from_manual("B", 120.0, 90.0, ws, list(np.linspace(0.0, 3000.0, len(ws))), [0.8] * len(ws))


class Recorder:
    """Every simulation (its wd, ws and Site), every annualisation and the AEP log, while active."""

    def __enter__(self):
        self.sims, self.hours, self.logs = [], [], []
        call, aep_per_turb, log = runner.simulate, aep_compute._aep_per_turb, aep_compute._log

        def recording_call(wfm, *args, **kwargs):
            self.sims.append({"wd": kwargs.get("wd"), "ws": kwargs.get("ws"), "site": wfm.site,
                              "free": type(wfm.wake_deficitModel).__name__ == "NoWakeDeficit"})
            return call(wfm, *args, **kwargs)

        def recording_aep(sim, hours_per_year=8760.0):
            self.hours.append(hours_per_year)
            return aep_per_turb(sim, hours_per_year=hours_per_year)

        self._patches = [mock.patch.object(runner, "simulate", recording_call),
                         mock.patch.object(aep_compute, "_aep_per_turb", recording_aep),
                         mock.patch.object(aep_compute, "_log", lambda msg, *a, **k: self.logs.append(str(msg)))]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False


class _Case(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def compute(self, wrg_paths, models=None, **kwargs):
        kwargs.setdefault("fixed_ti", 0.08)
        kwargs.setdefault("compute_variants", True)
        # With an added turbulence, so that a variant of the loss breakdown is calculated too.
        kwargs.setdefault("wake_physics", {"version": 1, "turbulence": "STF2017TurbulenceModel"})
        with Recorder() as rec:
            result = aep_compute.compute_aep_from_ui("", models or [model()], wrg_paths=wrg_paths, **kwargs)
        return result, rec


class WrgSettingsTest(_Case):
    """V06: what the three simulations receive with a WRG."""

    def check(self, nsec, count, expected_count, method="nearest", models=None, ws_step=None, expected_ws=None):
        path = write_wrg(self.folder, nsec, name=f"n{nsec}_{count}_{method}.wrg")
        result, rec = self.compute([path], models=models, wrg_direction_count=count, wrg_wd_interp=method,
                                   energy_ws_step=ws_step)
        wd = direction_grid(nsec, expected_count)
        ws = speed_grid(3.0, 25.0, 1.0) if expected_ws is None else expected_ws
        self.assertGreaterEqual(len(rec.sims), 3)  # main, free stream and at least one variant
        self.assertEqual(sum(s["free"] for s in rec.sims), 1)
        for s in rec.sims:
            np.testing.assert_array_equal(s["wd"], wd)
            np.testing.assert_array_equal(s["ws"], ws)
            self.assertEqual(s["site"].interp_method["wd"], method)
            self.assertNotIn("Speedup", s["site"].ds)
            self.assertEqual(s["site"].ds.attrs["wrg_speedup_method"], "none")
        # Main, free stream and every variant are annualised with 8766 h.
        self.assertGreaterEqual(len(rec.hours), 3)
        self.assertEqual(set(rec.hours), {8766.0})
        self.assertEqual(result["hours_per_year"], 8766.0)
        # The breakdown: the N native sectors, without 360°, adding up to the gross and net AEP.
        np.testing.assert_allclose(result["sector_directions_deg"], np.arange(nsec) * 360.0 / nsec, rtol=0, atol=1e-9)
        self.assertNotIn(360.0, result["sector_directions_deg"])
        np.testing.assert_allclose(sum(result["aep_per_wd_free_MWh"]), result["aep_free_MWh"], rtol=1e-10, atol=1e-6)
        np.testing.assert_allclose(sum(result["aep_per_wd_wake_MWh"]), result["aep_wake_MWh"], rtol=1e-10, atol=1e-6)
        return result

    def test_initial_choice(self):
        for nsec, initial in ((12, 84), (16, 112), (7, 49)):
            with self.subTest(nsec=nsec):
                self.check(nsec, None, initial)

    def test_chosen_count_even_and_odd(self):
        for nsec, count in ((12, 24), (12, 36), (16, 32), (16, 48), (7, 14), (7, 21)):
            with self.subTest(nsec=nsec, count=count):
                self.check(nsec, count, count, method="linear")

    def test_wind_speeds_of_the_models(self):
        with self.subTest("chosen step"):
            self.check(12, None, 84, ws_step=0.5, expected_ws=speed_grid(3.0, 25.0, 0.5))
        with self.subTest("the union of two bands"):
            narrow = model("N", ws=[4.0, 8.0, 12.0, 20.0], power=[0.0, 800.0, 3000.0, 3000.0], ct=[0.8, 0.8, 0.4, 0.2],
                           layout=[(2100.0, 1900.0)])
            wide = model("W", ws=[2.0, 6.0, 10.0, 28.0], power=[0.0, 800.0, 3000.0, 3000.0], ct=[0.8, 0.8, 0.4, 0.1])
            self.check(12, None, 84, models=[narrow, wide], expected_ws=speed_grid(2.0, 28.0, 1.0))
        with self.subTest("the finer initial step"):
            fine = model("F", ws=list(np.arange(3.0, 25.5, 0.5)), power=list(np.linspace(0.0, 3000.0, 45)),
                         ct=[0.8] * 45, layout=[(2100.0, 1900.0)])
            self.check(12, None, 84, models=[model(), fine], expected_ws=speed_grid(3.0, 25.0, 0.5))

    def test_extreme_sectors(self):
        # One sector: 7 directions (7N); 360 sectors: 7N passes 360, so N.
        self.check(1, None, 7)
        self.check(360, None, 360)

    def test_composite_turbine(self):
        # The policy reads the type the calculation takes (A, 3-25 m/s, step 1), never the unused branch.
        with self.subTest("unused branch without power"):
            self.check(12, None, 84, models=[composite_model(idle_turbine())], expected_ws=speed_grid(3.0, 25.0, 1.0))
        with self.subTest("unused branch with another band and step"):
            self.check(12, None, 84, models=[composite_model(wide_turbine())], expected_ws=speed_grid(3.0, 25.0, 1.0))

    def test_point_keeps_a_curve_the_bin_mean_does_not_take(self):
        # POINT keeps the curve as it is (a pchip table too) and only reads its band; the bin mean refuses it.
        curve = PowerCtTabular(WS, POWER_KW, "kW", CT, method="pchip")
        curve.operating_band = (3.0, 25.0)
        pchip = dict(model(), name="P", wt=WindTurbine("P", 100.0, 90.0, curve))
        path = write_wrg(self.folder, 12)
        result, rec = self.compute([path], models=[pchip], power_bin_mode="point", compute_variants=False)
        self.assertTrue(rec.sims)
        for s in rec.sims:
            np.testing.assert_array_equal(s["ws"], speed_grid(3.0, 25.0, 1.0))
        self.assertEqual(result["resource_settings"]["turbine_band_m_s"], [3.0, 25.0])
        self.assertGreater(result["aep_wake_MWh"], 0.0)
        with self.assertRaises(WrgContractError):
            self.compute([path], models=[pchip], compute_variants=False)
        # A curve whose band cannot be read: refused with POINT too.
        free_form = PowerCtFunction(["ws"], lambda ws, run_only: np.zeros_like(ws), "w")
        with self.assertRaises(WrgContractError):
            self.compute([path], models=[dict(pchip, wt=WindTurbine("F", 100.0, 90.0, free_form))],
                         power_bin_mode="point", compute_variants=False)

    def test_four_hundred_sectors(self):
        # The axis in float64: XRSite accepts its sectors (in float32 it did not), with 400 as the only option.
        result = self.check(400, None, 400)
        self.assertEqual(result["resource_settings"]["direction_count"], 400)
        with self.assertRaises(WrgContractError):
            wrg_site.load_wrg_site([write_wrg(self.folder, 400, name="n400.wrg")], direction_count=800)


class GrdSettingsTest(_Case):
    """V07: a GRD uses the directions and wind speeds of its Site, with 8766 h."""

    def setUp(self):
        super().setUp()
        from py_wake.examples.data.ParqueFicticio import ParqueFicticio_path

        # A copy without any cache: the loader may write next to the files.
        self.grd = os.path.join(self.folder, "grd")
        shutil.copytree(ParqueFicticio_path, self.grd, ignore=shutil.ignore_patterns("*.pkl", "*.py", "__pycache__"))
        from py_wake.site import WaspGridSite

        ds = WaspGridSite.from_wasp_grd(self.grd, speedup_using_pickle=False).ds
        self.layout = [(float(ds.x.values[i]), float(ds.y.values[j])) for i, j in ((15, 8), (10, 10))]

    def test_site_defaults(self):
        with Recorder() as rec:
            result = aep_compute.compute_aep_from_ui(self.grd, [model(layout=self.layout)], compute_variants=True,
                                                     include_turbulence=True, turbulence_model="CrespoHernandez")
        self.assertGreaterEqual(len(rec.sims), 3)
        for s in rec.sims:
            self.assertIsNone(s["wd"])
            self.assertIsNone(s["ws"])
            np.testing.assert_array_equal(s["site"].default_wd, np.arange(360))
            np.testing.assert_array_equal(s["site"].default_ws, np.arange(3, 26))
        self.assertEqual(set(rec.hours), {8766.0})
        # Breakdown by the 12 sectors: the directions on a border go to the sector of lower index.
        centres = result["sector_directions_deg"]
        np.testing.assert_allclose(centres, np.arange(12) * 30.0)
        counts, _ = _aggregate_to_sector_centers([1.0] * 360, list(range(360)), centres)
        self.assertEqual(counts, [31.0] + [30.0] * 10 + [29.0])
        np.testing.assert_allclose(sum(result["aep_per_wd_free_MWh"]), result["aep_free_MWh"], rtol=1e-10, atol=1e-6)
        np.testing.assert_allclose(sum(result["aep_per_wd_wake_MWh"]), result["aep_wake_MWh"], rtol=1e-10, atol=1e-6)
        settings = result["resource_settings"]
        self.assertEqual(settings["kind"], "GRD")
        # The WRG parameters passed with a GRD are accepted and do not change what its simulations receive.
        with Recorder() as rec_params:
            aep_compute.compute_aep_from_ui(self.grd, [model(layout=self.layout)], compute_variants=False,
                                            wrg_direction_count=36, wrg_wd_interp="linear", energy_ws_step=0.5)
        self.assertTrue(rec_params.sims)
        for s in rec_params.sims:
            self.assertIsNone(s["wd"])
            self.assertIsNone(s["ws"])
            np.testing.assert_array_equal(s["site"].default_wd, np.arange(360))
            np.testing.assert_array_equal(s["site"].default_ws, np.arange(3, 26))
        self.assertTrue(os.path.samefile(settings["source"], self.grd) or settings["source"].startswith(self.grd))
        self.assertEqual(settings["direction_count"], 360)
        self.assertEqual(result["hours_per_year"], 8766.0)
        self.assertNotIn("global_weibull", repr(result))
        self.assertTrue(any(line.startswith("[RECURSO] GRD") for line in rec.logs))


class ErrorsTest(_Case):
    """V08: every request outside the options stops before combining resources and before simulating; never rounded."""

    def setUp(self):
        super().setUp()
        self.wrg = write_wrg(self.folder, 12)
        no_simulation = mock.patch.object(runner, "simulate",
                                          side_effect=AssertionError("a simulation was started"))
        no_simulation.start()
        self.addCleanup(no_simulation.stop)

    def config(self, wrg_paths=None, **kwargs):
        models = [TurbineModelInput(**{k: v for k, v in model().items()})]
        return EnergyRunConfig(models=models, wrg_paths=wrg_paths or [self.wrg], fixed_ti=0.08,
                               update_project_layers=False, **kwargs)

    BAD = (
        dict(wrg_direction_count=13), dict(wrg_direction_count=84.0), dict(wrg_direction_count=372),
        dict(wrg_direction_count=0), dict(wrg_direction_count=True),
        dict(wrg_wd_interp="cubic"), dict(wrg_wd_interp="Nearest"),
        dict(wrg_speedup_method="global_weibull"), dict(wrg_speedup_method="weibull"),
        dict(wrg_speedup_method="pywake_global_weibull"), dict(wrg_speedup_method=None),
        dict(energy_ws_step=0.3), dict(energy_ws_step=0.5000001), dict(energy_ws_step=float("nan")),
        dict(energy_ws_step=float("inf")), dict(energy_ws_step=True), dict(energy_ws_step=2.0),
    )

    def test_through_the_runner(self):
        for bad in self.BAD:
            with self.subTest(**{k: repr(v) for k, v in bad.items()}), self.assertRaises(EnergyValidationError):
                EnergyRunner().run(self.config(**bad))

    def test_through_the_direct_api(self):
        for bad in self.BAD:
            with self.subTest(**{k: repr(v) for k, v in bad.items()}), self.assertRaises(WrgContractError):
                aep_compute.compute_and_update("", [model()], wrg_paths=[self.wrg], fixed_ti=0.08,
                                               update_project_layers=False, **bad)

    def test_a_wrg_without_models(self):
        with self.assertRaises(WrgContractError):
            aep_compute.compute_and_update("", [], wrg_paths=[self.wrg], update_project_layers=False)

    def test_the_loader_refuses_another_speedup(self):
        for method in ("global_weibull", "weibull", "pywake_global_weibull", "local_weibull", None):
            with self.subTest(method=method), self.assertRaises(WrgContractError):
                wrg_site.load_wrg_site([self.wrg], speedup_method=method)

    def test_wrg_lists_and_zips_with_other_sectors(self):
        other = write_wrg(self.folder, 16, name="other.wrg", height=120.0)
        mixed = write_zip(self.folder, {"a.wrg": (12, 90.0), "b.wrg": (16, 120.0)}, name="mixed.zip")
        combine = mock.patch.object(wrg_site.xr, "concat", side_effect=AssertionError("combined"))
        for paths in ([self.wrg, other], [mixed]):
            with self.subTest(paths=[os.path.basename(p) for p in paths]):
                with self.assertRaises(EnergyValidationError):
                    EnergyRunner().run(self.config(wrg_paths=paths))
                with combine, self.assertRaises(WrgContractError):
                    aep_compute.compute_and_update("", [model()], wrg_paths=paths, fixed_ti=0.08,
                                                   update_project_layers=False)

    def test_an_invalid_request_before_combining(self):
        # Two heights with the same sectors: the request is refused before the heights are combined.
        second = write_wrg(self.folder, 12, name="h120.wrg", height=120.0)
        heights = write_zip(self.folder, {"a.wrg": (12, 90.0), "b.wrg": (12, 120.0)}, name="heights.zip")
        combine = mock.patch.object(wrg_site.xr, "concat", side_effect=AssertionError("combined"))
        for paths in ([self.wrg, second], [heights]):
            for bad in (dict(direction_count=13), dict(wd_interp="cubic")):
                with self.subTest(paths=[os.path.basename(p) for p in paths], **bad), combine, \
                        self.assertRaises(WrgContractError):
                    wrg_site.load_wrg_site(paths, **bad)

    def test_compatible_lists_and_zips_still_load(self):
        second = write_wrg(self.folder, 12, name="h120.wrg", height=120.0, a_shift=0.5)
        heights = write_zip(self.folder, {"a.wrg": (12, 90.0), "b.wrg": (12, 120.0)}, name="heights.zip")
        for paths in ([self.wrg, second], [heights]):
            with self.subTest(paths=[os.path.basename(p) for p in paths]):
                site, ds, _label = wrg_site.load_wrg_site(paths)
                self.assertEqual(ds.attrs["n_sectors"], 12)
                self.assertEqual(ds.attrs["wrg_direction_count"], 84)
                self.assertEqual(list(ds["h"].values), [90.0, 120.0])
                self.assertEqual(ds["wd"].dtype, np.float64)

    def test_none_is_the_default_speedup(self):
        for fn, name in ((aep_compute.compute_aep_from_ui, "wrg_speedup_method"),
                         (aep_compute.compute_and_update, "wrg_speedup_method"),
                         (wrg_site.load_wrg_site, "speedup_method")):
            with self.subTest(function=fn.__name__):
                self.assertEqual(inspect.signature(fn).parameters[name].default, "none")
        self.assertEqual(EnergyRunConfig().wrg_speedup_method, "none")
        self.assertNotIn("global_weibull", Path(resource_loader.__file__).read_text(encoding="utf-8"))


class RecordTest(_Case):
    """V09: the [RECURSO] line, the notes and the result describe the Site and the grids the simulation receives."""

    def test_wrg(self):
        path = write_wrg(self.folder, 12)
        result, rec = self.compute([path], wrg_direction_count=36, wrg_wd_interp="linear", energy_ws_step=0.5)
        main = rec.sims[0]
        [line] = [line for line in rec.logs if line.startswith("[RECURSO]")]
        ws = main["ws"]
        self.assertEqual(
            line,
            f"[RECURSO] WRG | sectores=12 | direcciones={len(main['wd'])} | subdivisiones=3 | "
            f"wd={main['site'].interp_method['wd']} | centros de subdivisión | speedup=none | "
            f"ws={ws[0]:g}–{ws[-1]:g}/0.5 m/s | horas=8766",
        )
        settings = result["resource_settings"]
        self.assertEqual(settings["wd_eval_deg"], [float(v) for v in main["wd"]])
        self.assertEqual(settings["ws_m_s"], [float(v) for v in ws])
        self.assertEqual((settings["n_sectors"], settings["direction_count"], settings["subdivisions"]), (12, 36, 3))
        self.assertEqual((settings["wd_interp"], settings["speedup"], settings["ws_step_m_s"]), ("linear", "none", 0.5))
        self.assertEqual(settings["turbine_band_m_s"], [3.0, 25.0])
        self.assertEqual(settings["turbine_bands"], [{"model": "T", "band_m_s": [3.0, 25.0], "origin": "deduced"}])
        self.assertEqual(settings["source"], os.path.abspath(path))
        self.assertEqual(result["hours_per_year"], 8766.0)
        [note] = [n for n in result["simulation_notes"] if str(n).startswith("Parámetros del recurso")]
        self.assertEqual(
            str(note),
            "Parámetros del recurso (WRG): 36 direcciones (12 sectores × 3), interpolación linear, Speedup none, "
            "velocidades 3–25 m/s cada 0.5 m/s (banda de las turbinas 3–25 m/s); 8766 h/año.",
        )
        for gone in ("energy_profile", "energy_direction_mode", "energy_grid", "global_weibull", "pywake_version"):
            self.assertNotIn(gone, repr(result))

    def test_band_of_a_composite_turbine(self):
        path = write_wrg(self.folder, 12)
        result, _rec = self.compute([path], models=[composite_model(wide_turbine())], compute_variants=False)
        settings = result["resource_settings"]
        self.assertEqual(settings["turbine_band_m_s"], [3.0, 25.0])
        self.assertEqual(settings["turbine_bands"], [{"model": "A", "band_m_s": [3.0, 25.0], "origin": "deduced"}])


if __name__ == "__main__":
    unittest.main()
