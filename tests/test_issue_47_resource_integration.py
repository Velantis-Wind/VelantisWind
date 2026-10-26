"""Enable the real #48 consumers once resource parameters reach the PR base.

This branch must be merged after #48 under #53. Until then these integration
cases are explicitly skipped; they run without replacing the WRG metadata when
both changes are present. The scientific parser cases live in test_issue_47.
"""
import importlib.util
import os
import tempfile
import unittest
import zipfile
from unittest import mock

import numpy as np

from tests.test_issue_47 import resource

HAS_RESOURCE_PARAMS = importlib.util.find_spec("VelantisWind.ag_core.resource_grid") is not None


@unittest.skipUnless(HAS_RESOURCE_PARAMS, "Requires the #48 resource-parameters base (integration order in #53)")
class WrgResourceConsumersTest(unittest.TestCase):
    def setUp(self):
        from qgis.PyQt import QtCore, QtWidgets

        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.folder.name)
        QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, self.folder.name)
        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, self.folder.name)
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        warning = mock.patch.object(QtWidgets.QMessageBox, "warning")
        warning.start()
        self.addCleanup(warning.stop)
        from VelantisWind.aep_setup_dialog import AEPSetupDialog
        self.dialog = AEPSetupDialog()
        self.addCleanup(self.dialog.deleteLater)

    def text(self, nsec, ident, height=90):
        return resource(identifiers=[ident]*4, freqs=(1,)*nsec, height=height)

    def write(self, nsec, ident):
        path = os.path.join(self.folder.name, f"{nsec}_{ident}.wrg")
        with open(path, "w") as fh:
            fh.write(self.text(nsec, ident))
        return path

    def config_errors(self, path, count):
        from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput
        from VelantisWind.energy_core.validation import validate_energy_config
        config = EnergyRunConfig(
            models=[TurbineModelInput(name="T", wt=object(), coords_xy=[(1200, 2200)])],
            wrg_paths=[path], wrg_direction_count=count,
        )
        return [i for i in validate_energy_config(config) if i.is_error]

    def show_resource(self, path):
        # Only input is the file path. _update_wrg_meta reads the real file and
        # passes its sector count to the real _show_wrg_parameters implementation.
        self.dialog.ed_wrg.setText(path)
        self.dialog._update_wrg_meta()
        combo = self.dialog.cb_wd_count
        return [combo.itemData(i) for i in range(combo.count())]

    def test_sixteen_sector_metadata_drives_dialog_and_configuration(self):
        from VelantisWind.ag_core.wrg_reader import read_wrg_meta
        for ident in ("nan", "inf"):
            path = self.write(16, ident)
            self.assertEqual(read_wrg_meta(path)["n_sectors"], 16)
            self.assertEqual(self.show_resource(path), list(range(16, 353, 16)))
            self.assertEqual(self.dialog.cb_wd_count.currentData(), 112)
            self.assertNotIn(300, self.show_resource(path))  # 300 is power density, not N.
            self.assertEqual(self.config_errors(path, 112), [])
            self.assertTrue(self.config_errors(path, 300))

    def test_consistent_multiheight_zip_metadata_and_full_loader_agree(self):
        from VelantisWind.ag_core.wrg_reader import read_wrg_meta
        from VelantisWind.ag_core.wrg_site import load_wrg_site
        path = os.path.join(self.folder.name, "heights.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("low.wrg", self.text(16, "nan", 90))
            archive.writestr("nested/high.wrg", self.text(16, "inf", 130))
        meta = read_wrg_meta(path)
        self.assertEqual(meta["n_sectors_list"], [16, 16])
        self.assertEqual(meta["height_m_list"], [90, 130])
        self.assertEqual(self.config_errors(path, 112), [])
        _, ds, _ = load_wrg_site([path], speedup_method="none")
        np.testing.assert_array_equal(ds.h.values, meta["height_m_list"])
        self.assertEqual(round(360/ds.attrs["sector_width"]), meta["n_sectors"])

    def test_differing_sector_counts_rejected_in_either_zip_order(self):
        from VelantisWind.ag_core.wrg_reader import read_wrg_meta
        from VelantisWind.ag_core.wrg_site import load_wrg_site
        for counts in ((16, 12), (12, 16)):
            path = os.path.join(self.folder.name, f"mixed_{counts[0]}.zip")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("first.wrg", self.text(counts[0], "nan", 90))
                archive.writestr("nested/second.wrg", self.text(counts[1], "inf", 130))
            self.assertEqual(read_wrg_meta(path)["n_sectors_list"], list(counts))
            self.assertTrue(self.config_errors(path, 112))
            with self.assertRaises(ValueError):
                load_wrg_site([path], speedup_method="none")

    def test_four_hundred_sectors_remain_the_only_option_with_numeric_looking_ids(self):
        from VelantisWind.ag_core.wrg_reader import read_wrg_meta
        from VelantisWind.ag_core.wrg_site import load_wrg_site
        for ident in ("nan", "inf"):
            path = self.write(400, ident)
            self.assertEqual(read_wrg_meta(path)["n_sectors_list"], [400])
            self.assertEqual(self.show_resource(path), [400])
            self.assertEqual(self.dialog.cb_wd_count.currentData(), 400)
            self.assertEqual(self.config_errors(path, 400), [])
            self.assertTrue(self.config_errors(path, 300))
            _, ds, _ = load_wrg_site([path], speedup_method="none")
            self.assertEqual(ds.wd.dtype, np.dtype("float64"))
            np.testing.assert_allclose(np.diff(ds.wd.values), .9, atol=1e-10, rtol=0)
