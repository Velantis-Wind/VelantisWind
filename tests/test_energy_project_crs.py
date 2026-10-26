# -*- coding: utf-8 -*-
"""The AEP needs a project CRS that is valid, projected and in metres, and passes it whole to the engine."""
import os
import tempfile
import types
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402

from VelantisWind.energy_core import dialog_controller  # noqa: E402
from VelantisWind.energy_core.domain import EnergyRunConfig  # noqa: E402

# Projected in metres without an authority id; the same with datum parameters (type Bound); geocentric Bound.
CUSTOM = "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"
BOUND = "+proj=tmerc +lat_0=0 +lon_0=-3.3 +k=0.9996 +x_0=500000 +y_0=0 +ellps=intl +towgs84=1,2,3,0,0,0,0 +units=m +no_defs"
GEOCENTRIC_BOUND = "+proj=geocent +ellps=GRS80 +towgs84=1,2,3,0,0,0,0 +units=m +no_defs"
# Vertical-only systems without WKT1: a derived vertical CRS, and a vertical one with a vertical offset (Bound).
_NAVD88 = 'VERTCRS["NAVD88 height",VDATUM["North American Vertical Datum 1988"],CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1]]'
_OFFSET = 'METHOD["Vertical Offset",ID["EPSG",9616]],PARAMETER["Vertical Offset",1,LENGTHUNIT["metre",1],ID["EPSG",8603]]'
DERIVED_VERTICAL = ('VERTCRS["Derived height",BASEVERTCRS["NAVD88 height",VDATUM["North American Vertical Datum 1988"]],'
                    'DERIVINGCONVERSION["Offset",' + _OFFSET + '],CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1]]')
BOUND_VERTICAL = ('BOUNDCRS[SOURCECRS[' + _NAVD88 + '],TARGETCRS[' + _NAVD88.replace("NAVD88 height", "Other height") + '],'
                  'ABRIDGEDTRANSFORMATION["Offset",' + _OFFSET + ']]')
# A projected CRS in metres without an authority id and without WKT1 (a derived projected CRS: UTM 30N shifted 100 m).
DERIVED_PROJECTED = 'DERIVEDPROJCRS["UTM shifted 100 m",BASEPROJCRS["WGS 84 / UTM zone 30N",BASEGEOGCRS["WGS 84",ENSEMBLE["World Geodetic System 1984 ensemble",MEMBER["World Geodetic System 1984 (Transit)"],MEMBER["World Geodetic System 1984 (G730)"],MEMBER["World Geodetic System 1984 (G873)"],MEMBER["World Geodetic System 1984 (G1150)"],MEMBER["World Geodetic System 1984 (G1674)"],MEMBER["World Geodetic System 1984 (G1762)"],MEMBER["World Geodetic System 1984 (G2139)"],ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]],ENSEMBLEACCURACY[2.0]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]]],CONVERSION["UTM zone 30N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-3,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]]],DERIVINGCONVERSION["Shift",METHOD["Affine parametric transformation",ID["EPSG",9624]],PARAMETER["A0",100,LENGTHUNIT["metre",1],ID["EPSG",8623]],PARAMETER["A1",1,SCALEUNIT["coefficient",1],ID["EPSG",8624]],PARAMETER["A2",0,SCALEUNIT["coefficient",1],ID["EPSG",8625]],PARAMETER["B0",0,LENGTHUNIT["metre",1],ID["EPSG",8639]],PARAMETER["B1",0,SCALEUNIT["coefficient",1],ID["EPSG",8640]],PARAMETER["B2",1,SCALEUNIT["coefficient",1],ID["EPSG",8641]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1,ID["EPSG",9001]]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1,ID["EPSG",9001]]]]'
# A derived geocentric CRS: no PROJ string, only its WKT2 tells it is geocentric.
DERIVED_GEOCENTRIC = (
    'GEODCRS["Derived geocentric",BASEGEODCRS["WGS84",DATUM["WGS84",ELLIPSOID["WGS84",6378137,298.257223563]]],'
    'DERIVINGCONVERSION["Shift",METHOD["Geocentric translations",ID["EPSG",1031]],'
    'PARAMETER["X-axis translation",1,LENGTHUNIT["metre",1],ID["EPSG",8605]],'
    'PARAMETER["Y-axis translation",0,LENGTHUNIT["metre",1],ID["EPSG",8606]],'
    'PARAMETER["Z-axis translation",0,LENGTHUNIT["metre",1],ID["EPSG",8607]]],'
    'CS[Cartesian,3],AXIS["X",geocentricX],AXIS["Y",geocentricY],AXIS["Z",geocentricZ],LENGTHUNIT["metre",1]]'
)
# Hidden behind a compound with a time axis: the compound itself is valid, not geographic and in metres.
COMPOUND_GEOCENTRIC = (
    'COMPOUNDCRS["Geocentric and time",' + DERIVED_GEOCENTRIC + ',TIMECRS["Time",TDATUM["Gregorian",'
    'CALENDAR["proleptic Gregorian"],TIMEORIGIN[2000-01-01]],CS[TemporalMeasure,1],AXIS["time",future],'
    'TIMEUNIT["day",86400]]]'
)
# A topocentric CRS (east, north, up in metres around an origin): a local horizontal plane, accepted.
TOPOCENTRIC = (
    'GEODCRS["Topocentric",BASEGEODCRS["WGS84",DATUM["WGS84",ELLIPSOID["WGS84",6378137,298.257223563]]],'
    'DERIVINGCONVERSION["Topocentric",METHOD["Geographic/topocentric conversions",ID["EPSG",9837]],'
    'PARAMETER["Latitude of topocentric origin",40,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8834]],'
    'PARAMETER["Longitude of topocentric origin",-3,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8835]],'
    'PARAMETER["Ellipsoidal height of topocentric origin",0,LENGTHUNIT["metre",1],ID["EPSG",8836]]],'
    'CS[Cartesian,3],AXIS["E",east],AXIS["N",north],AXIS["U",up],LENGTHUNIT["metre",1]]'
)
# The word in a name or a remark is not a geocentric axis.
NAMED_GEOCENTRIC = (
    DERIVED_PROJECTED.replace('"UTM shifted 100 m"', '"UTM shifted, not geocentricX"', 1),
    TOPOCENTRIC[:-1] + ',REMARK["converted from geocentricX to east/north/up"]]',
)
_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def crs(definition):
    if not definition:
        return QgsCoordinateReferenceSystem()
    if definition.startswith("+"):
        return QgsCoordinateReferenceSystem.fromProj(definition)
    if "[" in definition:
        return QgsCoordinateReferenceSystem.fromWkt(definition)
    return QgsCoordinateReferenceSystem(definition)


class ProjectCrsBeforeTheAepTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)

    def run_aep(self, definition):
        """«Calcular AEP» with the project in ``definition``; returns the warnings and what reached the engine."""
        QgsProject.instance().setCrs(crs(definition))
        warnings, reached = [], {}

        def build(dialog, project_crs_authid, warn=True):
            reached["crs"] = project_crs_authid
            config = EnergyRunConfig(project_crs_authid=project_crs_authid)
            return types.SimpleNamespace(messages=[], to_energy_config=lambda: config, base_export_dir="", models=[])

        def single(dialog, config):
            reached["single"] = config
            return {}

        with mock.patch.object(dialog_controller, "build_energy_dialog_state", side_effect=build), \
                mock.patch.object(dialog_controller, "show_user_warning", side_effect=lambda d, t, m: warnings.append((t, m))), \
                mock.patch.object(dialog_controller, "_validate_before_run", return_value=True), \
                mock.patch.object(dialog_controller, "_run_energy_calculation", side_effect=single), \
                mock.patch.object(dialog_controller, "_show_results_dialog"), \
                mock.patch.object(dialog_controller, "show_message_bar"):
            dialog_controller.run_compute_and_update_from_dialog(types.SimpleNamespace(_register_last_aep_result=mock.Mock()))
        return warnings, reached

    def test_refused_without_a_projected_crs_in_metres(self):
        for definition, title in (("", "CRS del proyecto"), ("EPSG:4326", "CRS no proyectado"),
                                  ("EPSG:4978", "CRS no proyectado"), (GEOCENTRIC_BOUND, "CRS no proyectado"),
                                  ("EPSG:5703", "CRS no proyectado"), (DERIVED_VERTICAL, "CRS no proyectado"),
                                  (BOUND_VERTICAL, "CRS no proyectado"),
                                  (DERIVED_GEOCENTRIC, "CRS no proyectado"), (COMPOUND_GEOCENTRIC, "CRS no proyectado"),
                                  ("EPSG:2263", "Unidades del CRS")):
            with self.subTest(crs=definition[:30]):
                warnings, reached = self.run_aep(definition)
                self.assertEqual(reached, {})
                [(shown_title, message)] = warnings
                self.assertEqual(shown_title, title)
                self.assertIn("proyectado y en metros", message)

    def test_projected_crs_in_metres_goes_on(self):
        # EPSG:3145 is projected in metres although its method has no PROJ string; EPSG:5972 is UTM with heights.
        for definition in ("EPSG:32630", CUSTOM, BOUND, "EPSG:3145", "EPSG:5972", TOPOCENTRIC, *NAMED_GEOCENTRIC):
            with self.subTest(crs=definition[:30]):
                warnings, reached = self.run_aep(definition)
                self.assertEqual(warnings, [])
                self.assertIn("single", reached)

    def test_qgis_user_crs_is_serialized_as_wkt_for_the_engine(self):
        # An id from QGIS' user CRS database is NOT a GDAL authority id.
        from VelantisWind.ag_core.resources import turbulence_grid
        source = crs(CUSTOM)
        wkt = source.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED)
        user_crs = mock.Mock()
        user_crs.authid.return_value = "USER:100000"
        user_crs.toWkt.return_value = wkt
        with mock.patch.object(dialog_controller, "QgsProject") as qgs_project:
            qgs_project.instance.return_value.crs.return_value = user_crs
            self.assertEqual(dialog_controller._project_crs_authid(), wkt)

        # GDAL receives and understands the full definition (not USER:100000).
        gd_wkt = turbulence_grid.authid_to_wkt(wkt)
        self.assertTrue(gd_wkt)
        self.assertIn("PROJCRS[", gd_wkt)
        with mock.patch("qgis.core.QgsCoordinateReferenceSystem") as qgs_crs:
            qgs_crs.return_value = user_crs
            self.assertTrue(turbulence_grid.authid_to_wkt("USER:100000"))
            user_crs.isValid.return_value = False
            self.assertIsNone(turbulence_grid.authid_to_wkt("USER:100000"))

    def test_derived_project_crs_is_valid_for_the_ti_raster(self):
        from VelantisWind.ag_core.resources import turbulence_grid
        derived = crs(DERIVED_PROJECTED)
        self.assertEqual(derived.authid(), "")
        self.assertEqual(derived.toWkt(), "")  # WKT1 is not available.
        wkt = turbulence_grid.authid_to_wkt(
            derived.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED)
        )
        # A non-null check was too weak: WKT1 loses DERIVEDPROJCRS.
        self.assertTrue(wkt)
        self.assertIn("DERIVEDPROJCRS[", wkt)
        srs = turbulence_grid.osr.SpatialReference()
        self.assertEqual(srs.ImportFromWkt(wkt), 0)

    def test_crs_without_authority_id_reaches_the_engine_whole(self):
        for definition in (CUSTOM, DERIVED_PROJECTED):
            with self.subTest(crs=definition[:30]):
                self.assertEqual(crs(definition).authid(), "")
                _warnings, reached = self.run_aep(definition)
                sent = reached["single"].project_crs_authid
                # WKT2: the derived CRS has no WKT1 and would reach the engine empty.
                self.assertEqual(sent, crs(definition).toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED))
                self.assertTrue(sent)
                self.assertNotEqual(sent, "EPSG:25830")
        self.assertEqual(crs(DERIVED_PROJECTED).toWkt(), "")
        _warnings, reached = self.run_aep("EPSG:32630")
        self.assertEqual(reached["single"].project_crs_authid, "EPSG:32630")


if __name__ == "__main__":
    unittest.main()
