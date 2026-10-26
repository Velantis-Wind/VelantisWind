"""Regression tests for aligned acoustic curves and coordinate TXT files."""
import os
import tempfile
import unittest
from itertools import permutations
from unittest.mock import patch
import csv

from VelantisWind.noise_core.acoustics.curves import load_acoustic_curve_csv, evaluate_acoustic_curve
from VelantisWind.ui_core.layout_sources import read_xy_table


class WhitespaceTableReadersTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def write(self, text):
        path = os.path.join(self.folder, "table.txt")
        with open(path, "w", encoding="utf-8-sig") as handle:
            handle.write(text)
        return path

    def test_acoustic_whitespace_variants_keep_all_points(self):
        for separator, indent in ((" ", ""), ("  ", ""), ("   ", "  "),
                                  ("\t", ""), (" \t ", "  ")):
            for header in ("", "ws" + separator + "lwa\n"):
                with self.subTest(separator=separator, header=header):
                    text = header + "\n".join(indent + separator.join(row)
                        for row in (("3", "100"), ("4", "101"))) + "\n"
                    ws, lwa = load_acoustic_curve_csv(self.write(text))
                    self.assertEqual(ws.tolist(), [3., 4.])
                    self.assertEqual(lwa.tolist(), [100., 101.])

    def test_coordinate_whitespace_variants_with_and_without_header(self):
        for separator, indent in ((" ", ""), ("  ", ""), ("   ", "  "),
                                  ("\t", ""), (" \t ", "  ")):
            for header in ("", "X" + separator + "Y\n"):
                with self.subTest(separator=separator, header=header):
                    text = header + "\n".join(indent + separator.join(row)
                        for row in (("500000", "4700000"), ("500500", "4700500"))) + "\n"
                    self.assertEqual(read_xy_table(self.write(text)),
                                     [(500000., 4700000.), (500500., 4700500.)])

    def test_quoted_csv_delimiters_remain_supported(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                text = delimiter.join(("ws", "lwa")) + "\n"
                text += delimiter.join(('"3"', '"100"')) + "\n"
                text += delimiter.join(('"4"', '"101"')) + "\n"
                ws, lwa = load_acoustic_curve_csv(self.write(text))
                self.assertEqual(ws.tolist(), [3., 4.])
                self.assertEqual(lwa.tolist(), [100., 101.])
                text = delimiter.join(("X", "Y")) + "\n"
                text += delimiter.join(('"500000"', '"4700000"')) + "\n"
                self.assertEqual(read_xy_table(self.write(text)), [(500000., 4700000.)])

    def test_acoustic_duplicate_speeds_still_keep_maximum_noise(self):
        ws, lwa = load_acoustic_curve_csv(self.write("3  100\n3  105\n4  101\n"))
        self.assertEqual(ws.tolist(), [3., 4.])
        self.assertEqual(lwa.tolist(), [105., 101.])

    def test_coordinate_named_columns_and_decimal_commas(self):
        self.assertEqual(read_xy_table(self.write('id;Y;X\n"T 1";40,25;-3,5\n')),
                         [(-3.5, 40.25)])

    def test_invalid_rows_do_not_shift_valid_pairs(self):
        text = "3   100\nbad   900\n4   bad\n5\n6   102\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 6.])
        self.assertEqual(lwa.tolist(), [100., 102.])
        with self.assertRaisesRegex(ValueError, r": 2, 3, 4\."):
            read_xy_table(self.write(text))

    def test_empty_tsv_cells_are_not_compacted_into_valid_data(self):
        text = "X\tY\tZ\n500000 \t\t4700000\n500500 \t4700500\t0\n"
        with self.assertRaisesRegex(ValueError, r": 2\."):
            read_xy_table(self.write(text))
        text = "ws\tlwa\textra\n3 \t\t100\n4 \t101\t0\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [4.])
        self.assertEqual(lwa.tolist(), [101.])

    def test_unquoted_multiword_tsv_names_keep_named_columns(self):
        text = "Name\tX\tY\nTurbine One \t500000\t4700000\nTurbine Two \t500500\t4700500\n"
        self.assertEqual(read_xy_table(self.write(text)),
                         [(500000., 4700000.), (500500., 4700500.)])

    def test_review_empty_identifier_preserves_named_tsv_coordinates(self):
        text = "id\tX\tY\tZ\nA \t500000\t4700000\t0\n\t500500\t4700500\t0\n"
        self.assertEqual(read_xy_table(self.write(text)),
                         [(500000., 4700000.), (500500., 4700500.)])
        self.assertEqual(read_xy_table(self.write(text.replace("\tZ", "").replace("\t0", ""))),
                         [(500000., 4700000.), (500500., 4700500.)])

    def test_review_empty_acoustic_cell_beyond_sniffer_sample_is_not_shifted(self):
        text = "ws\tlwa\textra\n" + "3 \t100\t0\n" * 600 + "4 \t\t102\n5 \t101\t0\n"
        self.assertGreater(text.index("4 "), 4096)
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 5.])
        self.assertEqual(lwa.tolist(), [100., 101.])

    def test_review_quoted_names_in_space_delimited_coordinates(self):
        text = 'Name X Y\n"Turbine One" 500000 4700000\n"Turbine Two" 500500 4700500\n'
        self.assertEqual(read_xy_table(self.write(text)),
                         [(500000., 4700000.), (500500., 4700500.)])

    def test_review_separators_changing_between_rows_preserve_acoustic_peak(self):
        for separators in permutations((" ", "\t", "   ")):
            with self.subTest(separators=separators):
                text = "".join(separator.join(pair) + "\n" for separator, pair in zip(
                    separators, (("3", "100"), ("4", "110"), ("5", "102"))))
                ws, lwa = load_acoustic_curve_csv(self.write(text))
                self.assertEqual(ws.tolist(), [3., 4., 5.])
                self.assertEqual(lwa.tolist(), [100., 110., 102.])
                self.assertEqual(evaluate_acoustic_curve(ws, lwa, 4), 110.)
                self.assertEqual(evaluate_acoustic_curve(ws, lwa, use_worst_case=True), 110.)

    def test_inconsistent_separators_still_preserve_empty_tab_cells(self):
        text = "3 100\n4\t\t110\n5   102\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 5.])
        self.assertEqual(lwa.tolist(), [100., 102.])

    def test_review_trailing_tab_preserves_acoustic_peak(self):
        text = "3 100\n4 110\t\n5   102\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 4., 5.])
        self.assertEqual(lwa.tolist(), [100., 110., 102.])
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, 4), 110.)
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, use_worst_case=True), 110.)

    def test_fallback_padding_and_quoted_tabs_do_not_identify_tsv(self):
        for peak in ('4 110\t', '4   110 \t\t  ', '"4" "110"\t',
                     '4 "110\t"', '4\t"110\t"\t'):
            with self.subTest(peak=peak), patch("csv.Sniffer.sniff", side_effect=csv.Error):
                ws, lwa = load_acoustic_curve_csv(self.write("3 100\n" + peak + "\n5 102\n"))
                self.assertEqual(ws.tolist(), [3., 4., 5.])
                self.assertEqual(lwa.tolist(), [100., 110., 102.])

    def test_fallback_preserves_leading_interior_and_trailing_empty_tsv_cells(self):
        text = "3 100\n\t110\n4\t\t115\n5\t \t116\n6\t\t\n7 102\n8\t104\t\n"
        with patch("csv.Sniffer.sniff", side_effect=csv.Error):
            ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 7., 8.])
        self.assertEqual(lwa.tolist(), [100., 102., 104.])

    def test_review_mixed_separators_with_extra_column_preserve_acoustic_peak(self):
        text = "3 100\n4 110\t0\n5   102\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 4., 5.])
        self.assertEqual(lwa.tolist(), [100., 110., 102.])
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, 4), 110.)
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, use_worst_case=True), 110.)

    def test_fallback_mixed_separators_and_quotes_with_extra_columns(self):
        for peak in ('4 110\t0', '4\t110 0', '4  110 \t "extra\tinfo"',
                     '"4" "110"\t0', '4\t"110" 0'):
            with self.subTest(peak=peak), patch("csv.Sniffer.sniff", side_effect=csv.Error):
                ws, lwa = load_acoustic_curve_csv(self.write("3 100\n" + peak + "\n5 102\n"))
                self.assertEqual(ws.tolist(), [3., 4., 5.])
                self.assertEqual(lwa.tolist(), [100., 110., 102.])

    def test_inconsistent_separators_keep_quoted_numeric_values(self):
        text = '3 100\n"4"\t"110"\n"5"   "102"\n'
        with patch("csv.Sniffer.sniff", side_effect=csv.Error):
            ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 4., 5.])
        self.assertEqual(lwa.tolist(), [100., 110., 102.])

    def test_mixed_acoustic_rows_with_header_crlf_and_duplicates(self):
        text = "ws lwa\r\n\r\n3 100\r\n4\t110\r\n4   105\r\n5 102\r\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 4., 5.])
        self.assertEqual(lwa.tolist(), [100., 110., 102.])
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, 4), 110.)

    def test_mixed_acoustic_rows_do_not_promote_missing_tsv_values(self):
        text = "3 100\n\t110\n4\t\t115\n5   102\n6\t104\n"
        ws, lwa = load_acoustic_curve_csv(self.write(text))
        self.assertEqual(ws.tolist(), [3., 5., 6.])
        self.assertEqual(lwa.tolist(), [100., 102., 104.])
        self.assertEqual(evaluate_acoustic_curve(ws, lwa, use_worst_case=True), 104.)
