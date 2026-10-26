# -*- coding: utf-8 -*-
"""#54, points 4 to 6: the outputs keep a CRS without WKT1 (a derived projected one) in their files."""
import contextlib
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from osgeo import gdal, ogr, osr  # noqa: E402
from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer  # noqa: E402

from tests.test_energy_project_crs import DERIVED_PROJECTED  # noqa: E402
from VelantisWind.crs_utils import preferred_wkt  # noqa: E402
from VelantisWind.ag_core.qgis_io import wake_raster as exporter  # noqa: E402
from VelantisWind.noise_core.qgis_io import layers as noise_layers  # noqa: E402
from VelantisWind.noise_core.qgis_io.apply_results import apply_noise_task_result  # noqa: E402
from VelantisWind.noise_core.result_status import append_result_status  # noqa: E402

_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


@contextlib.contextmanager
def gdal_exceptions(on=True):
    """GDAL, OGR and OSR with their exceptions on (as in QGIS 3.44) or off; each module keeps its own state.

    GDAL has ``ExceptionMgr`` only since 3.7 (QGIS 3.28 may come with an older one); before, each module's
    ``UseExceptions`` set only its own state.
    """
    if hasattr(gdal, "ExceptionMgr"):
        with gdal.ExceptionMgr(useExceptions=on), ogr.ExceptionMgr(useExceptions=on), \
                osr.ExceptionMgr(useExceptions=on):
            yield
        return
    modules = (gdal, ogr, osr)
    before = [m.GetUseExceptions() for m in modules]
    try:
        for m in modules:
            m.UseExceptions() if on else m.DontUseExceptions()
        yield
    finally:
        for m, was in zip(modules, before):
            m.UseExceptions() if was else m.DontUseExceptions()


def file_srs(path):
    """The CRS of a raster file opened on its own, as another session or program would."""
    with gdal_exceptions():
        return gdal.Open(path).GetSpatialRef()


class WakeRasterFileCRSTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.folder = tempfile.mkdtemp(dir=_SETTINGS.name)
        self.addCleanup(shutil.rmtree, self.folder, True)
        # Cleanups run in reverse: the layers are let go before their files are removed (open files on Windows).
        self.addCleanup(QgsProject.instance().clear)
        self.derived = QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED)
        self.derived_srs = osr.SpatialReference()
        self.derived_srs.ImportFromWkt(preferred_wkt(self.derived))

    def package(self, crs_wkt, **kwargs):
        x = 500000.0 + 100.0 * np.arange(4.0)
        y = 4400000.0 + 100.0 * np.arange(3.0)
        fields = {"WS_eff": np.full((3, 4), 7.5), "WS": np.full((3, 4), 8.0)}

        def extract(_flow, _names, label):
            return fields[label], x, y
        with mock.patch.object(exporter, "_extract_field_2d", side_effect=extract), gdal_exceptions():
            return exporter.build_wake_raster_file(types.SimpleNamespace(), wd=270.0, ws=8.0, output_dir=self.folder,
                                                   crs_wkt=crs_wkt, **kwargs)

    def leftovers(self):
        return sorted(f for f in os.listdir(self.folder) if f.endswith((".tif", ".aux.xml", ".json")) or ".part" in f)

    def test_every_raster_of_a_derived_crs_keeps_it_in_its_file(self):
        result = self.package(preferred_wkt(self.derived))
        self.assertEqual(len(result["rasters"]), 4)
        for entry in result["rasters"]:
            srs = file_srs(entry["path"])
            self.assertIsNotNone(srs, entry["variable"])
            self.assertTrue(srs.IsSame(self.derived_srs), entry["variable"])
            self.assertEqual(QgsRasterLayer(entry["path"], "alone", "gdal").crs(), self.derived)
        self.assertEqual([f for f in os.listdir(self.folder) if ".part" in f], [])

    def test_an_identified_crs_is_the_one_of_always(self):
        result = self.package(preferred_wkt(QgsCoordinateReferenceSystem("EPSG:32630")))
        for entry in result["rasters"]:
            srs = file_srs(entry["path"])
            self.assertEqual((srs.GetAuthorityName(None), srs.GetAuthorityCode(None)), ("EPSG", "32630"))
        self.assertEqual([f for f in os.listdir(self.folder) if ".part" in f], [])

    def test_a_raster_written_over_another_does_not_take_its_old_crs(self):
        target = os.path.join(self.folder, "park_ws_eff.tif")
        utm = preferred_wkt(QgsCoordinateReferenceSystem("EPSG:32630"))
        first = self.package(utm, output_path=target)
        # Each destination with the .aux.xml of a raster in the derived CRS, as an earlier run would leave it.
        for entry in first["rasters"]:
            with open(entry["path"] + ".aux.xml", "w", encoding="utf-8") as handle:
                handle.write('<PAMDataset><SRS dataAxisToSRSAxisMapping="1,2">%s</SRS></PAMDataset>'
                             % preferred_wkt(self.derived))
            self.assertTrue(file_srs(entry["path"]).IsSame(self.derived_srs))
        second = self.package(utm, output_path=target)
        for entry in second["rasters"]:
            srs = file_srs(entry["path"])
            self.assertEqual(srs.GetAuthorityCode(None), "32630", entry["variable"])
            self.assertFalse(os.path.isfile(entry["path"] + ".aux.xml"), entry["variable"])

    def test_a_failure_moving_the_crs_leaves_no_raster_without_it(self):
        replace = os.replace

        def failing(src, dst):
            if src.endswith(".aux.xml"):
                raise OSError("disk full")
            return replace(src, dst)
        with mock.patch.object(exporter.os, "replace", side_effect=failing), self.assertRaises(OSError):
            self.package(preferred_wkt(self.derived))
        self.assertEqual(self.leftovers(), [])

    def test_a_later_failure_of_the_package_leaves_nothing_of_it(self):
        write = exporter._write_geotiff
        calls = []

        def failing(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 3:
                raise RuntimeError("GDAL failed")
            return write(*args, **kwargs)
        with mock.patch.object(exporter, "_write_geotiff", side_effect=failing), self.assertRaises(RuntimeError):
            self.package(preferred_wkt(self.derived))
        self.assertEqual(self.leftovers(), [])

    def test_a_raster_the_cleanup_cannot_remove_keeps_its_crs(self):
        write, remove = exporter._write_geotiff, os.remove
        calls = []

        def failing(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 2:
                raise RuntimeError("GDAL failed")
            return write(*args, **kwargs)

        def locked(path):  # the first raster, open in another program (Windows)
            if path == calls[0][:-len(".part.tif")]:
                raise PermissionError(path)
            return remove(path)
        with mock.patch.object(exporter, "_write_geotiff", side_effect=failing), \
                mock.patch.object(exporter.os, "remove", side_effect=locked), self.assertRaises(RuntimeError):
            self.package(preferred_wkt(self.derived))
        first = calls[0][:-len(".part.tif")]
        self.assertEqual(self.leftovers(), sorted(os.path.basename(p) for p in (first, first + ".aux.xml")))
        self.assertTrue(file_srs(first).IsSame(self.derived_srs))

    def test_a_temporary_raster_the_cleanup_cannot_remove_keeps_its_crs(self):
        replace, remove = os.replace, os.remove

        def locked(operation):  # the temporary raster, open in another program (Windows)
            def call(path, *args):
                if path.endswith(".part.tif"):
                    raise PermissionError(path)
                return operation(path, *args)
            return call
        with mock.patch.object(exporter.os, "replace", side_effect=locked(replace)), \
                mock.patch.object(exporter.os, "remove", side_effect=locked(remove)), self.assertRaises(PermissionError):
            self.package(preferred_wkt(self.derived))
        temp = [f for f in self.leftovers() if f.endswith(".part.tif")]
        self.assertEqual(self.leftovers(), [temp[0], temp[0] + ".aux.xml"])
        self.assertTrue(file_srs(os.path.join(self.folder, temp[0])).IsSame(self.derived_srs))


class IsophonesCRSTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.project = QgsProject.instance()
        self.project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.folder = tempfile.mkdtemp(dir=_SETTINGS.name)
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.addCleanup(QgsProject.instance().clear)  # before the folder is removed, as above
        # The isophones go to tempfile.gettempdir()/velantis_noise: here, to this test's folder.
        patcher = mock.patch.object(noise_layers.tempfile, "gettempdir", return_value=self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.derived = QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED)
        self.raster = os.path.join(self.folder, "grid.tif")
        with gdal_exceptions():
            ds = gdal.GetDriverByName("GTiff").Create(self.raster, 20, 20, 1, gdal.GDT_Float32)
            ds.SetGeoTransform((500000.0, 10.0, 0.0, 4000200.0, 0.0, -10.0))
            ds.SetProjection(preferred_wkt(self.derived))  # as Noise writes it: in its .aux.xml
            ds.GetRasterBand(1).WriteArray(np.add.outer(np.arange(20.0), np.arange(20.0)) + 30.0)
            ds = None

    def isophones(self, on=True):
        with gdal_exceptions(on):
            iso = noise_layers._build_isophones_layer_from_raster(self.project, self.raster, [40.0, 50.0],
                                                                  "Noise · Isophones")
            self.pending = gdal.GetLastErrorType()  # before switching the exceptions back, which clears it
            return iso

    def outputs(self):
        folder = os.path.join(self.folder, "velantis_noise")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def test_the_isophones_of_a_derived_crs_have_it(self):
        for on in (True, False):
            with self.subTest(gdal_exceptions=on):
                iso = self.isophones(on)
                self.assertIsNotNone(iso)
                self.assertTrue(iso.isValid())
                self.assertEqual(iso.crs(), self.derived)
                self.assertEqual({f["level_db"] for f in iso.getFeatures()}, {40.0, 50.0})

    def test_a_layer_that_cannot_be_created_gives_no_isophones_and_no_file(self):
        failing = mock.Mock()
        failing.CreateDataSource.return_value.CreateLayer.return_value = None
        for on in (True, False):
            with self.subTest(gdal_exceptions=on), mock.patch.object(noise_layers.ogr, "GetDriverByName",
                                                                    return_value=failing):
                self.assertIsNone(self.isophones(on))
        self.assertEqual(self.outputs(), [])

    def test_a_gdal_error_creating_the_layer_gives_no_isophones(self):
        failing = mock.Mock()
        failing.CreateDataSource.return_value.CreateLayer.side_effect = RuntimeError("PROJ: proj_as_wkt")
        with mock.patch.object(noise_layers.ogr, "GetDriverByName", return_value=failing):
            self.assertIsNone(self.isophones(True))

    def test_contours_that_fail_without_exceptions_give_no_isophones_and_no_file(self):
        with mock.patch.object(noise_layers.gdal, "ContourGenerate", return_value=1):
            self.assertIsNone(self.isophones(False))
        self.assertEqual(self.outputs(), [])

    def test_an_error_left_by_the_contours_gives_no_isophones_and_is_not_left_pending(self):
        def contours(*_args):
            gdal.Error(gdal.CE_Failure, 1, "cannot write linestring")
            return 0
        with mock.patch.object(noise_layers.gdal, "ContourGenerate", side_effect=contours):
            self.assertIsNone(self.isophones(False))
        self.assertEqual(self.outputs(), [])
        self.assertLess(self.pending, gdal.CE_Failure)

    def test_a_full_disk_gives_no_isophones_and_leaves_no_error_pending(self):
        # An in-memory GDAL file with a size limit as the full disk: one byte short of the whole file, the contours fit
        # and writing the file on close fails (QGIS would open what was written); with 1000 bytes the contours fail and
        # the close too.
        full = "/vsimem/iso_full.fgb"
        self.addCleanup(gdal.Unlink, full)
        with mock.patch.object(noise_layers, "_unique_temp_output", return_value=full):
            self.assertIsNotNone(self.isophones())
        size = gdal.VSIStatL(full).size
        for limit in (size - 1, 1000):
            for on in (True, False):
                path = f"/vsimem/iso_{limit}_{on}||maxlength={limit}.fgb"
                self.addCleanup(gdal.Unlink, path)
                with self.subTest(limit=limit, gdal_exceptions=on), \
                        mock.patch.object(noise_layers, "_unique_temp_output", return_value=path):
                    self.assertIsNone(self.isophones(on))
                    self.assertLess(self.pending, gdal.CE_Failure)
        self.assertEqual(self.project.mapLayersByName("Noise · Isophones"), [])

    def test_without_the_driver_or_a_layer_qgis_can_open_there_are_no_isophones_and_no_file(self):
        with mock.patch.object(noise_layers.ogr, "GetDriverByName", return_value=None):
            self.assertIsNone(self.isophones())
        with mock.patch.object(noise_layers, "QgsVectorLayer", return_value=mock.Mock(isValid=lambda: False)):
            self.assertIsNone(self.isophones())
        self.assertEqual(self.outputs(), [])

    def test_levels_without_contours_give_a_valid_empty_layer(self):
        with gdal_exceptions():
            iso = noise_layers._build_isophones_layer_from_raster(self.project, self.raster, [10.0], "Noise · Isophones")
        self.assertIsNotNone(iso)
        self.assertTrue(iso.isValid())
        self.assertEqual(iso.featureCount(), 0)

    def apply(self):
        snapshot = {"crs_wkt": DERIVED_PROJECTED, "receivers": [{"feature_id": 1, "x": 500050.0, "y": 4000050.0}],
                    "sources": [{"model_name": "M1", "x": 500100.0, "y": 4000100.0, "hub_height": 100.0, "lwa": 105.0,
                                 "feature_id": 7}],
                    "params": {"create_grid_layer": True, "create_iso_layer": True, "iso_levels": [40.0, 50.0]}}
        # A row as the task gives it: its attributes in the order of the output fields (noise_dba, n_src, near_m,
        # max_src_dba, dom_model, …).
        evaluation = {"rows": [{"feature_id": 1, "geometry_wkt": "Point (500050 4000050)",
                                "attrs": [41.8, 1, 70.7, 41.5, "M1"]}],
                      "src_stats": {"0": {"n_recv": 1, "max_lp_db": 41.5}},
                      "dom_links": [{"rec_id": 1, "src_id": 0, "model": "M1", "lp_dom_db": 41.5, "dist_m": 70.7,
                                     "src_x": 500100.0, "src_y": 4000100.0, "rec_x": 500050.0, "rec_y": 4000050.0}]}
        task_result = {"evaluation": evaluation, "grid_diag": {"grid_path": self.raster, "grid_min_noise": 30.0,
                                                               "grid_max_noise": 68.0}}
        with gdal_exceptions():
            return apply_noise_task_result(snapshot, task_result)

    def status(self, payload):
        dialog = mock.Mock()
        dialog.txt_status.toPlainText.return_value = ""
        dialog.chk_multi_receivers.isChecked.return_value = False
        dialog.chk_iso.isChecked.return_value = False  # the request is the one of the calculation, not the box now
        dialog.chk_generate_grid.isChecked.return_value = True
        dialog._current_acoustic_mode.return_value = "fixed"
        append_result_status(dialog, payload, [])
        return dialog.txt_status.setPlainText.call_args.args[0]

    def test_a_background_result_in_a_derived_crs_has_its_isophones(self):
        payload = self.apply()
        self.assertIsNotNone(payload["iso_layer"])
        self.assertEqual(self.project.mapLayersByName("Noise · Isophones")[0].crs(), self.derived)
        self.assertNotIn("se solicitaron las isófonas", self.status(payload))

    def test_isophones_that_fail_keep_the_rest_of_the_result_and_say_so(self):
        failing = mock.Mock()
        failing.CreateDataSource.return_value.CreateLayer.side_effect = RuntimeError("PROJ: proj_as_wkt")
        with mock.patch.object(noise_layers.ogr, "GetDriverByName", return_value=failing):
            payload = self.apply()
        self.assertIsNone(payload["iso_layer"])
        self.assertIsNotNone(payload["grid_layer"])
        for name in ("Noise · Receivers", "Noise · Sources", "Noise · Dominant links", "Noise · Map"):
            self.assertEqual(len(self.project.mapLayersByName(name)), 1, name)

        def features(name):
            return list(self.project.mapLayersByName(name)[0].getFeatures())
        [receiver] = features("Noise · Receivers")
        self.assertEqual((receiver.geometry().asWkt(0), receiver["noise_dba"], receiver["n_src"], receiver["max_src_dba"],
                          receiver["dom_model"]), ("Point (500050 4000050)", 41.8, 1, 41.5, "M1"))
        [source] = features("Noise · Sources")
        self.assertEqual((source.geometry().asWkt(0), source["src_fid"], source["lwa_dba"], source["max_lp_db"]),
                         ("Point (500100 4000100)", 7, 105.0, 41.5))
        [link] = features("Noise · Dominant links")
        self.assertEqual((link.geometry().asWkt(0), link["rec_id"], link["lp_dom_db"]),
                         ("LineString (500100 4000100, 500050 4000050)", 1, 41.5))
        self.assertEqual(self.project.mapLayersByName("Noise · Map")[0].source(), self.raster)
        self.assertEqual(self.project.mapLayersByName("Noise · Isophones"), [])
        self.assertIn("• AVISO: se solicitaron las isófonas pero no se pudieron generar.", self.status(payload))

    def test_the_isophone_warning_is_translated(self):
        from VelantisWind import i18n
        line = "• AVISO: se solicitaron las isófonas pero no se pudieron generar."
        blob = "Resultado acústico:\n" + line + "\n• Calculated receivers: 2"
        expected = {"en": "• WARNING: the isophones were requested but could not be generated.",
                    "fr": "• AVERTISSEMENT : les isophones ont été demandées mais n’ont pas pu être générées.",
                    "de": "• HINWEIS: Isophonen wurden angefordert, konnten aber nicht erstellt werden."}
        for lang, text in expected.items():
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                self.assertEqual(i18n.tr_text(line), text)
                self.assertIn(text, i18n.translate_fragment(blob))


class TIRasterCRSTextTest(unittest.TestCase):
    """The line and the note of the TI raster name the CRS of the project, never an EPSG it is not."""

    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.ti = os.path.join(tempfile.mkdtemp(dir=_SETTINGS.name), "ti_90m.tif")
        open(self.ti, "wb").close()

    def texts(self, crs):
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        QgsProject.instance().setCrs(crs)
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        note = [w.text() for w in dialog.findChildren(QtWidgets.QLabel) if "Los ráster(s) TI se reproyectarán" in w.text()]
        dialog.ed_wrg_ti.setText(self.ti)
        dialog._update_wrg_ti_meta()
        return note, dialog.lbl_wrg_ti_meta.text()

    def test_each_crs_is_named_by_what_it_has(self):
        custom = QgsCoordinateReferenceSystem.fromProj(
            "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs")
        self.assertEqual((custom.authid(), custom.description()), ("", ""))
        cases = {"EPSG:32630": QgsCoordinateReferenceSystem("EPSG:32630"),
                 "UTM shifted 100 m": QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED),
                 "sin identificador": custom,
                 "sin definir": QgsCoordinateReferenceSystem()}
        for name, crs in cases.items():
            with self.subTest(crs=name):
                note, line = self.texts(crs)
                self.assertEqual(len(note), 1)
                self.assertIn(f"al CRS del proyecto actual ({name})", note[0])
                self.assertTrue(line.endswith(f"· CRS destino previsto: {name}"), line)
                if name != "EPSG:32630":
                    self.assertNotIn("EPSG:25830", note[0] + line)

    def test_the_note_and_the_line_keep_the_name_of_the_crs_and_the_note_is_translated_whole(self):
        from VelantisWind import i18n
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        # A description that is also Spanish text the translation by fragments would change («Parque» is «Wind farm»).
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem.fromWkt(
            DERIVED_PROJECTED.replace('"UTM shifted 100 m"', '"Parque Norte"', 1)))
        texts = {
            "es": "La TI es la intensidad de turbulencia ambiente: una medida de lo variable o 'mezclado' que llega el "
                  "viento al rotor. Si no cargas ráster TI, se usa el valor manual de arriba como hipótesis uniforme. La TI "
                  "no siempre cambia mucho el AEP: se nota sobre todo en modelos sensibles a la TI como Niayifar, Zong, "
                  "TurboGaussian o TurboNOJ. Los ráster(s) TI se reproyectarán al CRS del proyecto actual (Parque Norte) "
                  "si hace falta.",
            "en": "TI is ambient turbulence intensity: a measure of how variable or mixed the wind is when it reaches the "
                  "rotor. If you do not load a TI raster, the manual value above is used as a uniform assumption. TI does "
                  "not always change AEP strongly: it is mainly visible in TI-sensitive models such as Niayifar, Zong, "
                  "TurboGaussian or TurboNOJ. TI raster(s) will be reprojected to the current project CRS (Parque Norte) "
                  "if needed.",
            "fr": "La TI est l’intensité de turbulence ambiante : une mesure de la variabilité ou du mélange du vent "
                  "lorsqu’il atteint le rotor. Si aucun raster TI n’est chargé, la valeur manuelle ci-dessus est utilisée "
                  "comme hypothèse uniforme. La TI ne modifie pas toujours fortement l’AEP : son effet est surtout visible "
                  "avec les modèles sensibles à la TI comme Niayifar, Zong, TurboGaussian ou TurboNOJ. Les raster(s) TI "
                  "seront reprojetés vers le SCR du projet actuel (Parque Norte) si nécessaire.",
            "de": "Die TI ist die Umgebungsturbulenzintensität: ein Maß dafür, wie stark der Wind am Rotor schwankt bzw. "
                  "gemischt ist. Wenn kein TI-Raster geladen wird, verwendet das Plugin den oben angegebenen manuellen Wert "
                  "als einheitliche Annahme. Die TI verändert die AEP nicht immer stark; sie wirkt sich vor allem bei "
                  "TI-empfindlichen Modellen wie Niayifar, Zong, TurboGaussian oder TurboNOJ aus. Die TI-Raster werden bei "
                  "Bedarf in das KBS des aktuellen Projekts (Parque Norte) reprojiziert.",
        }

        lines = {"es": "· CRS destino previsto: Parque Norte", "en": "· Expected target CRS: Parque Norte",
                 "fr": "· SCR cible prévu : Parque Norte", "de": "· Vorgesehenes Ziel-KBS: Parque Norte"}

        def check(dialog, lang):
            note = [w.text() for w in dialog.findChildren(QtWidgets.QLabel) if "TurboNOJ" in w.text()]
            self.assertEqual(note, [texts[lang]])
            self.assertTrue(dialog.lbl_wrg_ti_meta.text().endswith(lines[lang]), dialog.lbl_wrg_ti_meta.text())
        for lang in texts:
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                dialog = AEPSetupDialog()
                self.addCleanup(dialog.deleteLater)
                dialog.ed_wrg_ti.setText(self.ti)
                dialog._update_wrg_ti_meta()
                check(dialog, lang)
                dialog._rebuild_rows()  # the dialog translates its texts again, e.g. with another number of models
                check(dialog, lang)
        # The same dialog after a change of language, kept by the hub, when it translates its texts again.
        with mock.patch.object(i18n, "current_language", return_value="en"):
            dialog = AEPSetupDialog()
            self.addCleanup(dialog.deleteLater)
            dialog.ed_wrg_ti.setText(self.ti)
            dialog._update_wrg_ti_meta()
        with mock.patch.object(i18n, "current_language", return_value="fr"):
            dialog._rebuild_rows()
            check(dialog, "fr")

    def test_a_name_of_the_crs_that_looks_like_html_is_shown_as_it_is(self):
        name = "Local <b>Norte</b> &amp; Sur"
        crs = QgsCoordinateReferenceSystem.fromWkt(DERIVED_PROJECTED.replace('"UTM shifted 100 m"', '"%s"' % name, 1))
        self.assertEqual(crs.description(), name)
        note, line = self.texts(crs)
        self.assertIn(f"({name})", note[0])
        self.assertTrue(line.endswith(name), line)
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        dialog = AEPSetupDialog()
        self.addCleanup(dialog.deleteLater)
        labels = [w for w in dialog.findChildren(QtWidgets.QLabel) if "TurboNOJ" in w.text()] + [dialog.lbl_wrg_ti_meta]
        self.assertEqual([w.textFormat() for w in labels], [QtCore.Qt.PlainText] * 2)  # not rich text: no <b>, no &amp;

    def test_the_names_without_a_crs_are_translated(self):
        import VelantisWind.crs_utils  # noqa: F401  (registers the CRS texts)
        from VelantisWind import i18n
        expected = {"en": ("no identifier", "not defined"), "fr": ("sans identifiant", "non défini"),
                    "de": ("ohne Kennung", "nicht definiert")}
        for lang, (no_id, undefined) in expected.items():
            with self.subTest(lang=lang), mock.patch.object(i18n, "current_language", return_value=lang):
                self.assertEqual(i18n.tr_text("sin identificador"), no_id)
                self.assertEqual(i18n.tr_text("sin definir"), undefined)


if __name__ == "__main__":
    unittest.main()
