# -*- coding: utf-8 -*-
"""The wake raster with its edge cases (#63, P4, decisions 2, 7 and 8): at 0 m/s the package is written, with the
relative deficit entirely NoData, its warning and that layer without a style; a layer without finite cells does not
stop the package; the counts of each kind of cell and their warnings, translated; «no wakes» under the cut-in; and an
ordinary map, the package of always."""
import json
import math
import os
import tempfile
import types
import unittest
import warnings
from unittest import mock

import numpy as np

from VelantisWind.ag_core import edge_cases as ec
from VelantisWind.ag_core.log_text import shown
from VelantisWind.ag_core.qgis_io import wake_raster as exporter
from VelantisWind.i18n import tr_text
from VelantisWind.wake_core import raster as wake_raster
from tests.test_edge_cases_calculation import LAYOUT, physics
from tests.test_zero_node import density_table, manual, model, write_wrg

NAN, INF = math.nan, math.inf


class DiagnosisTest(unittest.TestCase):
    def test_an_ordinary_map_has_nothing(self):
        ws = np.full((3, 4), 10.0)
        self.assertIsNone(ec.raster_diagnosis(ws - np.eye(3, 4), ws))
        self.assertEqual(ec.raster_warnings(None), [])

    def test_the_counts_of_each_kind(self):
        free = np.array([[0.0, 1e-9, -1.0, 10.0]])
        eff = np.array([[0.0, 1e-9, -2.0, NAN]])
        d = ec.raster_diagnosis(eff, free)
        self.assertEqual((d["ws_eff"]["negative"], d["ws_eff"]["nan"], d["ws"]["negative"], d["deficit_pct_undefined"]),
                         (1, 1, 1, 2))
        self.assertNotIn("empty_layers", d)
        self.assertNotIn("no_wakes", d)
        text = [str(shown(w, tr_text)) for w in ec.raster_warnings(d)]
        self.assertTrue(any("velocidad efectiva negativa en 1 de 4 celdas (mínimo finito -2 m/s)" in t for t in text))
        self.assertTrue(any("no finita en 1 celdas (NaN 1" in t and "solo cubren las celdas finitas" in t for t in text))
        self.assertTrue(any("cambia de signo en 1 celdas" in t for t in text))
        self.assertTrue(any("no está definido con velocidad libre nula: 2 celdas" in t for t in text))

    def test_layers_without_finite_cells_and_no_wakes(self):
        zero = np.zeros((2, 3))
        d = ec.raster_diagnosis(zero, zero)
        self.assertEqual((d["empty_layers"], d["no_wakes"]), (["wake_deficit_pct"], True))
        d = ec.raster_diagnosis(np.full((2, 3), NAN), np.full((2, 3), 5.0))
        self.assertEqual(d["empty_layers"], ["WS_eff", "wake_deficit", "wake_deficit_pct"])
        self.assertEqual(ec.raster_diagnosis(np.full((2, 3), NAN))["empty_layers"], ["WS_eff"])
        # finite speeds whose relative deficit overflows in float32, as the exporter writes it (Sol, P4 r1)
        self.assertEqual(ec.raster_diagnosis(np.full((2, 3), 1e30), np.full((2, 3), 1e-8))["empty_layers"],
                         ["wake_deficit_pct"])
        # a free speed over 1e-9 that float32 takes to 1e-9: undefined, as written (Sol, P4 r2)
        d = ec.raster_diagnosis(np.zeros((2, 3)), np.full((2, 3), 1.00000001e-9))
        self.assertEqual((d["deficit_pct_undefined"], d["empty_layers"]), (6, ["wake_deficit_pct"]))
        # but the speeds and «no wakes» are those of PyWake, not their float32 (Sol, P4 r3)
        d = ec.raster_diagnosis(np.full((2, 3), -1e-50), np.full((2, 3), 10.0))
        self.assertEqual(d["ws_eff"]["negative"], 6)
        self.assertIsNone(ec.raster_diagnosis(np.full((2, 3), 9.99999999), np.full((2, 3), 10.0)))

    def test_cells_that_float32_overflows_in_a_layer_with_finite_ones(self):
        # the relative deficit of the first cell overflows; the layer keeps the second (Sol, final review)
        d = ec.raster_diagnosis(np.array([[1e30, 9.0]]), np.array([[1e-8, 10.0]]))
        self.assertEqual(d["overflow_cells"], {"wake_deficit_pct": 1})
        self.assertNotIn("empty_layers", d)
        # a speed over the float32 range: its layer and the deficits, not the cells already said with the speeds
        d = ec.raster_diagnosis(np.array([[1e39, NAN, 8.0]]), np.array([[10.0, 10.0, 10.0]]))
        self.assertEqual(d["overflow_cells"], {"WS_eff": 1, "wake_deficit": 1, "wake_deficit_pct": 1})
        self.assertEqual(ec.raster_diagnosis(np.array([[1e39, 8.0]]))["overflow_cells"], {"WS_eff": 1})
        text = [str(shown(w, tr_text)) for w in ec.raster_warnings(d)]
        self.assertIn("Ráster: la capa WS_eff tiene 1 celdas no finitas por desbordamiento al escribirla en float32: son "
                      "NoData.", text)
        # the cells already said: undefined relative deficit, non-finite speeds, a whole layer
        self.assertNotIn("overflow_cells", ec.raster_diagnosis(np.array([[0.0, NAN, 9.0]]), np.array([[0.0, 10.0, 10.0]])))
        self.assertNotIn("overflow_cells", ec.raster_diagnosis(np.full((2, 3), 1e30), np.full((2, 3), 1e-8)))

    def test_the_texts_are_translated(self):
        d = ec.raster_diagnosis(np.array([[0.0, -1.0]]), np.array([[0.0, -1.0]]))
        overflow = ec.raster_diagnosis(np.array([[1e39, 8.0]]))
        from VelantisWind import i18n
        for language in ("en", "fr", "de"):
            with self.subTest(language), mock.patch.object(i18n, "current_language", return_value=language):
                for warning in ec.raster_warnings(d) + ec.raster_warnings(overflow):
                    self.assertFalse(str(shown(warning, tr_text)).startswith("Ráster:"))


class PackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        cls.folder = tempfile.TemporaryDirectory()
        cls.wrg = write_wrg(cls.folder.name, 90, "full.wrg", empty_sector=False)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def raster(self, ws, wt=None, name=None):
        out = os.path.join(self.folder.name, name or f"ws_{ws}")
        return wake_raster.compute_wake_raster_config(
            [model(wt or manual(), LAYOUT, 90.0)], wake_config=physics(), wrg_paths=[self.wrg], fixed_ti=0.1,
            resolution_m=250.0, ws_plot=ws, wd_target=270.0, output_dir=out, crs_authid="EPSG:32630")

    @staticmethod
    def entry(result, variable):
        return next(e for e in result["rasters"] if e["variable"] == variable)

    def test_at_0_m_s_the_package_is_written(self):
        r = self.raster(0.0)
        pct = self.entry(r, "wake_deficit_pct")
        self.assertTrue(os.path.isfile(pct["path"]))
        self.assertEqual((pct["valid_cells"], pct["min"], pct["p95"]), (0, None, None))
        self.assertNotIn("style_min", pct)
        self.assertEqual(self.entry(r, "WS")["mean"], 0.0)
        text = " ".join(r["warnings"])
        self.assertIn("no está definido con velocidad libre nula", text)
        self.assertIn("la capa wake_deficit_pct no tiene celdas finitas", text)
        with open(r["metadata_path"], encoding="utf-8") as fh:
            sidecar = json.load(fh)
        self.assertEqual(sidecar["edge_cases"]["empty_layers"], ["wake_deficit_pct"])
        self.assertTrue(any("wake_deficit_pct" in w for w in sidecar["warnings"]))
        from osgeo import gdal
        dataset = gdal.Open(pct["path"])
        band = dataset.GetRasterBand(1)
        cells = band.ReadAsArray()
        nodata = band.GetNoDataValue()
        self.assertIsNotNone(nodata)
        self.assertTrue(cells.size and np.array_equal(cells, np.full_like(cells, nodata), equal_nan=True))  # NoData

    def test_a_negative_speed(self):
        r = self.raster(-1.0)
        text = " ".join(r["warnings"])
        self.assertIn("velocidad libre negativa en", text)
        self.assertIn("el déficit relativo cambia de signo", text)

    def test_no_wakes_under_the_cut_in(self):
        r = self.raster(2.0, wt=density_table(first=3.0), name="cut_in")
        self.assertIn("sin estelas", " ".join(r["warnings"]))
        self.assertNotIn("sin estelas", " ".join(self.raster(10.0, wt=density_table(first=3.0), name="above")["warnings"]))

    def test_a_layer_without_finite_cells_does_not_stop_the_package(self):
        ws = np.full((2, 4), 8.0)
        flow = types.SimpleNamespace()

        def extract(_flow, names, label):
            return ({"WS_eff": np.full((2, 4), NAN), "WS": ws}[label], np.arange(4.0) * 100, np.arange(2.0) * 100)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        with mock.patch.object(exporter, "_extract_field_2d", side_effect=extract):
            r = exporter.build_wake_raster_file(flow, wd=270.0, ws=8.0, output_dir=folder.name)
        self.assertEqual((r["min_ws"], r["max_ws"], r["p95_ws"], r["valid_cells"]), (None, None, None, 0))
        self.assertEqual(r["free_flow_mean_ws"], 8.0)
        for entry in r["rasters"]:
            self.assertTrue(os.path.isfile(entry["path"]))
        self.assertEqual([e["variable"] for e in r["rasters"] if not e["valid_cells"]],
                         ["WS_eff", "wake_deficit", "wake_deficit_pct"])

    def test_an_ordinary_map_is_the_package_of_always(self):
        """At 10 m/s the same rasters to the bit and the same sidecar as with the diagnosis taken away, but for the
        diagnosis and its warnings (this map has two negative cells next to a rotor)."""
        r = self.raster(10.0, name="ordinary")
        with mock.patch.object(ec, "raster_diagnosis", return_value=None):
            o = self.raster(10.0, name="oracle")
        self.assertEqual(r["edge_cases"]["ws_eff"]["negative"], 2)
        new = [str(w) for w in ec.raster_warnings(r["edge_cases"])]
        self.assertEqual(r["warnings"], o["warnings"] + new)
        self.assertNotIn("edge_cases", o)
        for variable in ("WS", "WS_eff", "wake_deficit", "wake_deficit_pct"):
            from osgeo import gdal
            a = gdal.Open(self.entry(r, variable)["path"]).ReadAsArray()
            b = gdal.Open(self.entry(o, variable)["path"]).ReadAsArray()
            self.assertEqual(a.tobytes(), b.tobytes())
        with open(r["metadata_path"], encoding="utf-8") as fh, open(o["metadata_path"], encoding="utf-8") as gh:
            a, b = json.load(fh), json.load(gh)
        for record in (a, b):
            for key in ("created_utc", "timings_seconds", "path", "metadata_path", "rasters"):
                record.pop(key, None)
        a.pop("edge_cases")
        a["warnings"] = [w for w in a["warnings"] if w not in new]
        self.assertEqual(a, b)

    def test_a_diagnosis_that_writes_and_raises_changes_nothing(self):
        """Its inputs are read-only copies: a diagnosis that tries to write into them and then fails leaves the
        rasters as they are (Sol, P4 r1)."""
        attempts = []

        def writes(ws_eff, ws_free=None):
            for values in (ws_eff, ws_free):
                try:
                    values[...] = 123.0
                    attempts.append("written")
                except ValueError:
                    attempts.append("refused")
            raise RuntimeError("roto")
        with mock.patch.object(ec, "raster_diagnosis", side_effect=writes):
            r = self.raster(10.0, name="writes")
        with mock.patch.object(ec, "raster_diagnosis", return_value=None):
            o = self.raster(10.0, name="untouched")
        self.assertEqual(attempts, ["refused", "refused"])
        from osgeo import gdal
        for variable in ("WS", "WS_eff", "wake_deficit", "wake_deficit_pct"):
            a = gdal.Open(self.entry(r, variable)["path"]).ReadAsArray()
            b = gdal.Open(self.entry(o, variable)["path"]).ReadAsArray()
            self.assertEqual(a.tobytes(), b.tobytes())

    def test_a_failed_diagnosis_does_not_stop_the_raster(self):
        with mock.patch.object(ec, "raster_diagnosis", side_effect=RuntimeError("roto")):
            r = self.raster(10.0, name="failed")
        self.assertIn("Aviso no disponible: RuntimeError: roto", r["warnings"])


if __name__ == "__main__":
    unittest.main()
