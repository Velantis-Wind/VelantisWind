# -*- coding: utf-8 -*-
"""The wake raster takes only metres as metre units, not their multiples or fractions, and no geocentric project."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from VelantisWind.wake_core import controller
from VelantisWind.wake_core.controller import _uses_metre_units

GEOCENTRIC_BOUND = "+proj=geocent +ellps=GRS80 +towgs84=1,2,3,0,0,0,0 +units=m +no_defs"
_FOLDER = tempfile.TemporaryDirectory()
_CWD = os.getcwd()


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_FOLDER.name)


def tearDownModule():
    os.chdir(_CWD)


class MetreUnitsTest(unittest.TestCase):
    def test_metres_only(self):
        utm = "+proj=utm +zone=30 +datum=WGS84 +units={} +no_defs"
        for definition, expected in ((utm.format("m"), True), (utm.format("km"), False), (utm.format("cm"), False),
                                     (utm.format("mm"), False), (utm.format("us-ft"), False)):
            with self.subTest(crs=definition):
                crs = QgsCoordinateReferenceSystem.fromProj(definition)
                self.assertTrue(crs.isValid())
                self.assertIs(_uses_metre_units(crs), expected)
        self.assertTrue(_uses_metre_units(QgsCoordinateReferenceSystem("EPSG:32630")))
        self.assertFalse(_uses_metre_units(QgsCoordinateReferenceSystem("EPSG:2263")))


class GeocentricProjectTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(QgsProject.instance().setCrs, QgsProject.instance().crs())

    def start(self, crs):
        """Start the raster with the project in ``crs``; returns the warnings shown and whether a task started."""
        QgsProject.instance().setCrs(crs)
        dialog = mock.Mock(_wake_raster_task=None)
        with mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warning, \
                mock.patch.object(controller, "output_directory_for_project", return_value="/nonexistent"), \
                mock.patch.object(controller, "start_wake_raster_task") as task:
            controller.start_wake_raster_from_dialog(
                dialog, models=[], wasp_dir="", resolution_m=300.0, wrg_paths=[], wake_config=None,
                wd_target=None,
            )
        return [c.args[1] for c in warning.call_args_list], task.called

    def test_refused_like_the_aep(self):
        # Geocentric (also wrapped with datum parameters, derived or in a compound) and vertical-only (heights, no
        # horizontal plane).
        from tests.test_energy_project_crs import COMPOUND_GEOCENTRIC, DERIVED_GEOCENTRIC
        for crs in (QgsCoordinateReferenceSystem("EPSG:4978"), QgsCoordinateReferenceSystem.fromProj(GEOCENTRIC_BOUND),
                    QgsCoordinateReferenceSystem("EPSG:5703"), QgsCoordinateReferenceSystem.fromWkt(DERIVED_GEOCENTRIC),
                    QgsCoordinateReferenceSystem.fromWkt(COMPOUND_GEOCENTRIC)):
            with self.subTest(crs=crs.authid() or crs.description()):
                self.assertTrue(crs.isValid())
                self.assertEqual(self.start(crs), (["CRS no proyectado"], False))

    def test_projected_in_metres_starts(self):
        from tests.test_energy_project_crs import NAMED_GEOCENTRIC, TOPOCENTRIC
        self.assertEqual(self.start(QgsCoordinateReferenceSystem("EPSG:32630")), ([], True))
        for wkt in (TOPOCENTRIC, *NAMED_GEOCENTRIC):
            with self.subTest(crs=wkt[:30]):
                self.assertEqual(self.start(QgsCoordinateReferenceSystem.fromWkt(wkt)), ([], True))


if __name__ == "__main__":
    unittest.main()
