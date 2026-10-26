# -*- coding: utf-8 -*-
import os
import re
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

import VelantisWind
from VelantisWind import version
from VelantisWind.noise_core.results.xlsx_writer import write_xlsx_workbook


def _metadata_version():
    path = os.path.join(os.path.dirname(VelantisWind.__file__), "metadata.txt")
    with open(path, encoding="utf-8") as handle:
        return re.search(r"^version\s*=\s*(\S+)\s*$", handle.read(), re.MULTILINE).group(1)


class PluginVersionTest(unittest.TestCase):
    def test_reads_metadata_version(self):
        self.assertEqual(version.plugin_version(), _metadata_version())

    def test_xlsx_app_version_follows_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = os.path.join(folder, "metadata.txt")
            with open(metadata, "w", encoding="utf-8") as handle:
                handle.write("[general]\nname=Test\nversion=9.8.7\n")
            with mock.patch.object(version, "_METADATA_PATH", metadata):
                path = write_xlsx_workbook(os.path.join(folder, "out.xlsx"), [{"title": "S", "rows": [["a"]]}])
            with ZipFile(path) as archive:
                app = archive.read("docProps/app.xml").decode("utf-8")
        self.assertIn("<AppVersion>9.8.7</AppVersion>", app)


if __name__ == "__main__":
    unittest.main()
