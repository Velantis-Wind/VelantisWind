"""WRG records: structure, unit scales and agreement between all readers."""
import contextlib
import math
import os
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

import numpy as np

from VelantisWind.ag_core.wrg_site import _build_ds_from_wrg_text, _parse_node, load_wrg_site
from VelantisWind.ag_core.wrg_reader import read_wrg_meta
from VelantisWind.spacing_core.orientation import (
    _sector_energy_from_lines, most_energetic_angle, sector_energy_from_wrg,
)


def resource(formats=None, identifiers=None, freqs=(1, 333, 333, 333), x0=1000, height=90):
    rows = [f"2 2 {x0} 2000 500"]
    formats = formats or [str] * 4
    for i in range(4):
        x = x0 + (i % 2) * 500
        # Deliberately different sector A/k values and total A/k: column shifts
        # and confusing raw sector units with physical units must be observable.
        sectors = " ".join(f"{f} {97 + 7*s + 3*i} {215 + 11*s + i}"
                           for s, f in enumerate(freqs))
        row = (f"{formats[i](x)} {2000 + (i // 2)*500} {10+i} {height} "
               f"9.0 2.1 300 {len(freqs)} {sectors}")
        if identifiers and identifiers[i] is not None:
            row = identifiers[i] + " " + row
        rows.append(row)
    return "\n".join(rows) + "\n"


class WrgNodeRegressionTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.serial = 0

    def write(self, text):
        self.serial += 1
        path = os.path.join(self.folder.name, f"synthetic_{self.serial}.wrg")
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def build(self, text, force=False, source="example.wrg"):
        cm = patch("VelantisWind.ag_core.wrg_site.np.fromstring", side_effect=ValueError) if force else contextlib.nullcontext()
        with cm:
            return _build_ds_from_wrg_text(text, source=source)

    def assert_same(self, got, expected):
        for name in ("x", "y", "h", "wd", "Elevation", "Sector_frequency", "Weibull_A", "Weibull_k"):
            np.testing.assert_allclose(got[name].values, expected[name].values, rtol=1e-6)

    def assert_bad(self, text, line, check_meta=False, reason=None):
        for force in (False, True):
            with self.subTest(force_fallback=force):
                with self.assertRaisesRegex(ValueError, rf"example.wrg, línea {line}:") as raised:
                    self.build(text, force)
                if reason:
                    self.assertIn(reason, str(raised.exception))
        if check_meta:
            path = self.write(text)
            with self.assertRaisesRegex(ValueError, rf"{os.path.basename(path)}, línea {line}:"):
                read_wrg_meta(path)

    def test_numeric_formats_and_parsed_coordinates_in_both_routes(self):
        formats = (lambda x: f"{x:.4E}", lambda x: f"{x}.", lambda x: f"{x:+d}", str)
        for freqs in ((250, 250, 250, 250), (1, 333, 333, 333)):
            expected = self.build(resource(freqs=freqs))
            for fmts in ([fmt]*4 for fmt in formats):
                for chosen in (fmts, list(formats)):
                    text = resource(formats=chosen, freqs=freqs)
                    for force in (False, True):
                        ds = self.build(text, force)
                        self.assertEqual(ds.attrs["parser"], "python_fallback" if force else "numpy_bulk")
                        self.assert_same(ds, expected)
                    # Dataset axes come from the grid header. Inspect the node
                    # parser too, so that rebuilt axes cannot hide a shifted X/Y.
                    for i, row in enumerate(text.splitlines()[1:]):
                        parsed = _parse_node(row.split(), 4)
                        self.assertEqual(parsed[:4], (1000+(i % 2)*500, 2000+(i // 2)*500, 10+i, 90))
                    meta = read_wrg_meta(self.write(text))
                    self.assertEqual((meta["height_m"], meta["n_sectors"]), (90, 4))

    def test_fractional_coordinates_without_integer_part(self):
        text = resource(x0=.5, formats=[lambda x: str(x).lstrip("0")]*4)
        expected = self.build(resource(x0=.5))
        for force in (False, True):
            self.assert_same(self.build(text, force), expected)
        self.assertEqual(_parse_node(text.splitlines()[1].split(), 4)[:2], (.5, 2000))
        self.assertEqual(read_wrg_meta(self.write(text))["height_m"], 90)

    def test_numpy_route_preserves_the_actual_parsed_node_coordinates(self):
        # The dataset reconstructs its axes from the grid header. Capture the
        # real NumPy conversion too, so those axes cannot mask a misread X/Y.
        convert = np.fromstring
        for x0 in (-1000, 1000):
            formats = [lambda x: f"{x:.4E}", lambda x: f"{x}.",
                       lambda x: f"{x:+d}", str]
            parsed_coordinates = []

            def recording_conversion(*args, **kwargs):
                raw = convert(*args, **kwargs)
                parsed_coordinates.append(raw.reshape(4, -1)[:, :2].copy())
                return raw

            with patch("VelantisWind.ag_core.wrg_site.np.fromstring", side_effect=recording_conversion):
                ds = self.build(resource(formats=formats, x0=x0))
            self.assertEqual(ds.attrs["parser"], "numpy_bulk")
            self.assertEqual(len(parsed_coordinates), 1)
            np.testing.assert_array_equal(parsed_coordinates[0],
                [(x0+(i % 2)*500, 2000+(i // 2)*500) for i in range(4)])

    def test_rounding_and_small_height_differences_do_not_impose_grid_heuristics(self):
        rows = resource(x0=1000.123).splitlines()
        for i in range(4):
            tokens = rows[i+1].split()
            tokens[0] = f"{float(tokens[0]):.1f}"
            tokens[3] = str(90 + i*1e-7)
            rows[i+1] = " ".join(tokens)
        text = "\n".join(rows)
        expected = self.build(resource(x0=1000.123))
        for force in (False, True):
            self.assert_same(self.build(text, force), expected)
        # This is an intentional precision difference, not a shifted field.
        self.assertEqual(_parse_node(rows[1].split(), 4)[0], 1000.1)
        self.assertEqual(read_wrg_meta(self.write(text))["height_m"], 90)

    def test_single_and_many_sectors_keep_their_scales(self):
        for nsec in (1, 16, 72):
            freqs = tuple(1000//nsec + (s < 1000 % nsec) for s in range(nsec))
            for identifier in (None, "GridPoint"):
                text = resource(freqs=freqs, identifiers=[identifier]*4)
                for force in (False, True):
                    ds = self.build(text, force)
                    index = (1, 1, 0, slice(0, nsec))  # fourth grid node
                    np.testing.assert_allclose(ds.Sector_frequency.values[index],
                                               np.asarray(freqs)/sum(freqs), rtol=1e-6)
                    np.testing.assert_allclose(ds.Weibull_A.values[index],
                                               [(106+7*s)/10 for s in range(nsec)], rtol=1e-6)
                    np.testing.assert_allclose(ds.Weibull_k.values[index],
                                               [(218+11*s)/100 for s in range(nsec)], rtol=1e-6)
                    self.assertEqual(ds.attrs["sector_width"], 360/nsec)
                self.assertEqual(read_wrg_meta(self.write(text))["n_sectors"], nsec)

    def test_invalid_sector_declarations_are_rejected_on_first_and_later_nodes(self):
        for declaration in ("0", "-4", "4.25", "nan", "inf", "1e999", "junk"):
            for identifier in (None, "GridPoint"):
                for node in (0, 3):
                    rows = resource(identifiers=[identifier]*4).splitlines()
                    tokens = rows[node+1].split()
                    tokens[7 + bool(identifier)] = declaration
                    rows[node+1] = " ".join(tokens)
                    with self.subTest(declaration=declaration, identifier=identifier, node=node):
                        self.assert_bad("\n".join(rows), node+2, check_meta=node == 0)

    def test_metadata_checks_only_the_first_node_and_errors_keep_crlf_line_numbers(self):
        rows = resource().splitlines()
        rows[3] = "001 " + rows[3]
        text = "\r\n" + "\r\n\r\n".join(rows) + "\r\n"
        meta = read_wrg_meta(self.write(text))
        self.assertEqual((meta["height_m"], meta["n_sectors"]), (90, 4))
        self.assert_bad(text, 8, reason="número finito")

    def test_invalid_identifier_in_a_later_zip_member_names_that_member(self):
        rows = resource(identifiers=["1e-999"]*4, height=130).splitlines()
        bad = "\r\n" + "\r\n\r\n".join(rows) + "\r\n"
        path = os.path.join(self.folder.name, "multiple.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("low.wrg", resource(identifiers=["nan"]*4))
            archive.writestr("nested/high.wrg", bad)
        for force in (False, True):
            cm = patch("VelantisWind.ag_core.wrg_site.np.fromstring", side_effect=ValueError) if force else contextlib.nullcontext()
            with cm:
                with self.assertRaises(ValueError) as raised:
                    load_wrg_site([path], speedup_method="none")
            self.assertTrue(str(raised.exception).startswith(path + "::nested/high.wrg, línea 4:"))
            self.assertIn("número finito", str(raised.exception))
        with self.assertRaises(ValueError) as raised:
            read_wrg_meta(path)
        self.assertTrue(str(raised.exception).startswith(path + "::nested/high.wrg, línea 4:"))

    def test_partial_conversion_restores_warning_filters_and_allows_the_next_load(self):
        rows = resource().splitlines()
        rows[-1] = " ".join(rows[-1].split()[:-1] + ["210junk"])
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always", DeprecationWarning)
            filters = list(warnings.filters)
            self.assert_bad("\n".join(rows), 5)
            self.assertEqual(warnings.filters, filters)
            self.assertEqual(self.build(resource()).attrs["parser"], "numpy_bulk")
            warnings.warn("unrelated warning after WRG load", DeprecationWarning)
            self.assertEqual([str(item.message) for item in seen],
                             ["unrelated warning after WRG load"])

    def test_raw_sector_scales_and_frequency_rounding(self):
        for freqs in ((250, 250, 250, 250), (1, 333, 333, 332)):
            for identifiers in (None, ["nan"]*4):
                for force in (False, True):
                    ds = self.build(resource(freqs=freqs, identifiers=identifiers), force)
                    for i in range(4):
                        index = (i % 2, i // 2, 0, slice(0, 4))
                        np.testing.assert_allclose(ds.Sector_frequency.values[index], np.asarray(freqs)/sum(freqs), rtol=1e-6)
                        np.testing.assert_allclose(ds.Weibull_A.values[index], [(97+7*s+3*i)/10 for s in range(4)], rtol=1e-6)
                        np.testing.assert_allclose(ds.Weibull_k.values[index], [(215+11*s+i)/100 for s in range(4)], rtol=1e-6)
                        self.assertEqual(ds.Elevation.values[i % 2, i // 2], 10+i)
                    self.assertEqual(ds.h.values[0], 90)
                    for name in ("Sector_frequency", "Weibull_A", "Weibull_k"):
                        np.testing.assert_array_equal(ds[name].values[..., -1], ds[name].values[..., 0])

    def test_supported_identifiers_and_mixed_rows(self):
        expected = self.build(resource())
        for ident in ("GridPoint", "nan", "inf", "Infinity", "1e999", "0x10"):
            text = resource(identifiers=[ident]*4)
            for force in (False, True):
                ds = self.build(text, force)
                self.assertEqual(ds.attrs["parser"], "python_fallback")
                self.assert_same(ds, expected)
            meta = read_wrg_meta(self.write(text))
            self.assertEqual((meta["height_m"], meta["n_sectors"]), (90, 4))
        text = resource(identifiers=[None, "GridPoint", "nan", "inf"])
        self.assert_same(self.build(text), expected)

    def test_finite_numeric_identifiers_rejected_on_first_and_later_nodes(self):
        for ident in ("001", "1e3", "+5", "1.", "1_000", "1e-999", "-5", "12.5"):
            for i in (0, 2):
                ids = [None]*4
                ids[i] = ident
                with self.subTest(identifier=ident, node=i):
                    self.assert_bad(resource(identifiers=ids), i+2, check_meta=i == 0, reason="número finito")

    def test_one_extra_finite_token_rejected_at_every_position(self):
        # First frequency equals N: an extra token can look structurally like
        # an ID row. This is the silent regression reported in the PR review.
        for node in (0, 2):
            original = resource(freqs=(4, 332, 332, 332)).splitlines()
            tokens = original[node+1].split()
            for extra in ("210", "1_000", "+5", "1e-999"):
                for position in range(len(tokens)+1):
                    rows = list(original)
                    changed = tokens[:position] + [extra] + tokens[position:]
                    rows[node+1] = " ".join(changed)
                    with self.subTest(node=node, token=extra, position=position):
                        self.assert_bad("\n".join(rows), node+2, check_meta=node == 0)

    def test_documented_ambiguity_can_match_another_accepted_structure(self):
        # Removing z and inserting a different value after the sector count can
        # leave an accepted 20-field record when the first frequency equals N.
        # Structure alone cannot identify every damaged record; no grid/height
        # heuristic or guesses from physical magnitudes are imposed here.
        rows = resource(freqs=(4, 332, 332, 332)).splitlines()
        for i in range(1, len(rows)):
            tokens = rows[i].split()
            del tokens[2]
            tokens.insert(8, "210")
            rows[i] = " ".join(tokens)
        text = "\n".join(rows)
        for force in (False, True):
            self.assertEqual(self.build(text, force).h.values[0], 9)
        self.assertEqual(read_wrg_meta(self.write(text))["height_m"], 9)

    def test_bad_later_rows_report_source_and_physical_line(self):
        for change in (lambda s: s + " extra", lambda s: " ".join(s.split()[:-1]),
                       lambda s: s.replace("300 4 ", "300 3 "),
                       lambda s: s.replace("300 4 ", "300 4.5 "),
                       lambda s: s.replace("333", "nan", 1)):
            rows = resource().splitlines()
            rows[3] = change(rows[3])
            rows.insert(2, "")
            self.assert_bad("\n".join(rows), 5)

    def test_compensating_missing_and_extra_fields_are_not_flattened(self):
        rows = resource().splitlines()
        rows[2] += " 210"
        rows[3] = " ".join(rows[3].split()[:-1])
        self.assert_bad("\n".join(rows), 3)

    def test_bad_first_row_is_rejected_by_metadata_and_full_loader(self):
        for transform in (lambda s: s + " extra", lambda s: " ".join(s.split()[:-1])):
            rows = resource().splitlines()
            rows[1] = transform(rows[1])
            rows.insert(1, "")
            text = "\n".join(rows)
            self.assert_bad(text, 3, check_meta=True)
            with self.assertRaisesRegex(ValueError, r"synthetic_.*\.wrg, línea 3"):
                load_wrg_site([self.write(text)], speedup_method="none")

    def test_nonfinite_and_nonnumeric_node_values_are_rejected(self):
        for column in (0, 1, 2, 3, 4, 5, 6, 8, 9, 10):
            for value in ("nan", "inf", "junk"):
                for identifiers in (None, ["GridPoint"]*4):
                    rows = resource(identifiers=identifiers).splitlines()
                    toks = rows[1].split()
                    toks[column + bool(identifiers)] = value
                    rows[1] = " ".join(toks)
                    with self.subTest(column=column, value=value, ids=identifiers):
                        self.assert_bad("\n".join(rows), 2, check_meta=column < 8)

    def test_fallback_still_checks_rows_after_the_first_identifier(self):
        rows = resource(identifiers=[None, "GridPoint", None, None]).splitlines()
        rows[4] += " extra"
        self.assert_bad("\n".join(rows), 5)

    def test_partial_last_numeric_token_is_rejected_in_both_routes(self):
        rows = resource().splitlines()
        rows[-1] = " ".join(rows[-1].split()[:-1] + ["210junk"])
        self.assert_bad("\n".join(rows), 5)

    def test_real_pywake_load_matches_light_metadata(self):
        path = self.write(resource(formats=[lambda x: f"{x:.4E}"]*4))
        meta = read_wrg_meta(path)
        site, ds, _ = load_wrg_site([path], speedup_method="none")
        self.assertEqual(round(360/ds.attrs["sector_width"]), meta["n_sectors"])
        self.assertEqual(ds.attrs["wrg_reference_height_m"], meta["height_m"])
        np.testing.assert_allclose(ds.Weibull_A.values[0, 0, 0], 9.7)
        self.assertIsNotNone(site)

    def test_zip_metadata_full_load_and_canonical_error_sources(self):
        path = os.path.join(self.folder.name, "resource.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("nested/resource.wrg", resource(identifiers=["GridPoint", "nan", "inf", "Infinity"]))
        meta = read_wrg_meta(path)
        _, ds, _ = load_wrg_site([path], speedup_method="none")
        self.assertEqual(meta["n_sectors"], round(360/ds.attrs["sector_width"]))
        rows = resource().splitlines()
        rows[1] += " extra"
        bad = "\n".join(rows)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("nested/bad.wrg", bad)
        for read in (read_wrg_meta, lambda p: load_wrg_site([p], speedup_method="none")):
            with self.assertRaises(ValueError) as raised:
                read(path)
            self.assertTrue(str(raised.exception).startswith(path + "::nested/bad.wrg, línea 2:"))
            direct = self.write(bad)
            with self.assertRaises(ValueError) as raised:
                read(direct)
            self.assertTrue(str(raised.exception).startswith(direct + ", línea 2:"))

    def test_orientation_identifiers_numeric_formats_and_scales(self):
        plain = sector_energy_from_wrg(self.write(resource()))
        energy = [sum(f*((97+7*s+3*i)/10)**3*math.gamma(1+3/((215+11*s+i)/100))
                      for i in range(4)) for s, f in enumerate((1, 333, 333, 333))]
        np.testing.assert_allclose(plain.energy_rel, np.asarray(energy)/sum(energy))
        for ident in (None, "GridPoint", "nan", "inf", "Infinity", "1e999", "0x10"):
            for fmt in (str, lambda x: f"{x:.4E}", lambda x: f"{x}.", lambda x: f"{x:+d}"):
                text = resource(identifiers=[ident]*4, formats=[fmt]*4)
                path = self.write(text)
                result = sector_energy_from_wrg(path)
                self.assertEqual(result.n_sectors, plain.n_sectors)
                np.testing.assert_allclose(result.energy_rel, plain.energy_rel)
                self.assertEqual(most_energetic_angle(path), plain.best_angle_deg)
        path = self.write(resource(x0=.5, formats=[lambda x: str(x).lstrip("0")]*4))
        self.assertEqual(most_energetic_angle(path), plain.best_angle_deg)

    def test_orientation_rejects_first_finite_identifier(self):
        for ident in ("1e3", "001", "1_000"):
            path = self.write(resource(identifiers=[ident]*4))
            with self.assertRaisesRegex(ValueError, "número finito"):
                sector_energy_from_wrg(path)
            self.assertIsNone(most_energetic_angle(path))

    def test_orientation_omits_rejected_later_nodes_and_can_change_angle(self):
        rows = resource(freqs=(250,)*4).splitlines()
        for i in range(4):
            tokens = rows[i+1].split()
            tokens[8:] = [str(v) for a in (70, 100, 200 if i == 2 else 80, 90) for v in (250, a, 200)]
            rows[i+1] = " ".join(tokens)
        self.assertEqual(_sector_energy_from_lines(rows).best_angle_deg, 180)
        rows[3] = "001 " + rows[3]
        result = _sector_energy_from_lines(rows)
        self.assertEqual(result.best_angle_deg, 90)
        weights = np.asarray((70, 100, 80, 90), dtype=float)**3
        np.testing.assert_allclose(result.energy_rel, weights/weights.sum())
        # A valid first node with no energy plus rejected later nodes cannot
        # yield an angle: retain the tolerant wrapper's existing None result.
        empty = resource(freqs=(0,)*4, identifiers=[None, "001", "001", "001"])
        self.assertIsNone(most_energetic_angle(self.write(empty)))

    def test_orientation_preserves_sector_limit(self):
        for nsec in (1, 72):
            self.assertEqual(sector_energy_from_wrg(self.write(resource(freqs=(1,)*nsec))).n_sectors, nsec)
        self.assertIsNone(most_energetic_angle(self.write(resource(freqs=(1,)*73))))


if __name__ == "__main__":
    unittest.main()
