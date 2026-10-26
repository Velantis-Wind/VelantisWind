# -*- coding: utf-8 -*-
"""Ensure XML imports are safe and work without user-installed defusedxml."""

import io
import unittest

from VelantisWind._vendor.defusedxml.ElementTree import parse as bundled_parse
from VelantisWind._vendor.defusedxml.common import EntitiesForbidden
from VelantisWind.ag_core.turbines.wtg import _xml_parse as wtg_parse
from VelantisWind.ag_core.turbines.owtg import _xml_parse as owtg_parse


class BundledXMLTest(unittest.TestCase):
    def test_readers_use_bundled_parser(self):
        self.assertIs(wtg_parse, bundled_parse)
        self.assertIs(owtg_parse, bundled_parse)

    def test_valid_xml_without_external_dependency(self):
        root = bundled_parse(io.StringIO("<root><item/></root>"), forbid_dtd=True).getroot()
        self.assertEqual(root.tag, "root")
        self.assertIsNotNone(root.find("item"))

    def test_benign_dtd_is_accepted(self):
        xml = '<?xml version="1.0"?><!DOCTYPE root [<!ELEMENT root ANY>]><root/>'
        root = bundled_parse(
            io.StringIO(xml), forbid_dtd=False, forbid_entities=True, forbid_external=True
        ).getroot()
        self.assertEqual(root.tag, "root")

    def test_entity_declaration_is_rejected(self):
        xml = '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY content "bad">]><root>&content;</root>'
        with self.assertRaises(EntitiesForbidden):
            bundled_parse(
                io.StringIO(xml), forbid_dtd=False, forbid_entities=True, forbid_external=True
            )

    def test_external_entity_declaration_is_rejected(self):
        xml = '<!DOCTYPE root [<!ENTITY file SYSTEM "file:///etc/passwd">]><root>&file;</root>'
        with self.assertRaises(EntitiesForbidden):
            bundled_parse(
                io.StringIO(xml), forbid_dtd=False, forbid_entities=True, forbid_external=True
            )


if __name__ == "__main__":
    unittest.main()
