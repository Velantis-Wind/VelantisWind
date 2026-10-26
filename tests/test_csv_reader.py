# -*- coding: utf-8 -*-
"""The TXT/CSV reader takes each data row whole or fails naming it; noise lines are still skipped."""
import os
import tempfile
import unittest

from VelantisWind.ag_core.turbine import TxtSpec, _estimate_ct, load_curves_from_txt
from VelantisWind.ag_core.turbines.curves import read_curve_from_model_dict
from VelantisWind.ag_core.results.summary import _read_curve_from_model_dict, _estimate_p_rated_mw

HEADER = "ws,power_kw,ct"
ROWS = ["3,100,0.80", "4,200,0.81", "5,300,0.82", "6,400,0.83", "7,500,0.84"]
EXPECTED = [(3.0, 100000.0, 0.80), (4.0, 200000.0, 0.81), (5.0, 300000.0, 0.82), (6.0, 400000.0, 0.83), (7.0, 500000.0, 0.84)]


class CsvCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def read(self, rows, ct_col=2, header=HEADER):
        path = os.path.join(self.folder, "curve.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join([header, *rows]) + "\n")
        return load_curves_from_txt(path, TxtSpec(ws_col=0, power_col=1, delimiter=",", skip_header=1, ct_col=ct_col))

    def assertFails(self, rows, *parts):
        """The reading fails with a message naming each of ``parts``, and carries its template for the translator."""
        with self.assertRaises(ValueError) as ctx:
            self.read(rows)
        message = str(ctx.exception)
        for part in ("curve.csv", *parts):
            self.assertIn(part, message)
        template, data = ctx.exception.template_item
        self.assertEqual(template.format(**data), message)
        return message


class IssueReproductionTest(CsvCase):
    def test_invalid_ct_fails_naming_its_row_instead_of_shifting_the_rest(self):
        # Before: 5 m/s took the Ct of 6 m/s, 6 m/s the one of 7 m/s, and 7 m/s disappeared.
        rows = ["3,100,0.80", "4,200,0.81", "5,300,ERROR", "6,400,0.83", "7,500,0.84"]
        self.assertFails(rows, "línea 4", "columna 2", "'ERROR'")

    def test_invalid_ct_fails_in_the_first_middle_and_last_rows(self):
        for i in (0, 2, 4):
            with self.subTest(row=i):
                rows = list(ROWS)
                rows[i] = rows[i].rsplit(",", 1)[0] + ",0.8x"
                self.assertFails(rows, f"línea {i + 2}", "columna 2", "'0.8x'")


class WholeRowsTest(CsvCase):
    def test_every_valid_row_keeps_its_three_values_including_the_last(self):
        ws, power_w, ct = self.read([ROWS[2], ROWS[0], ROWS[4], ROWS[1], ROWS[3]])
        self.assertEqual(list(zip(ws, power_w, ct)), EXPECTED)

    def test_empty_ct_between_valid_values_fails_instead_of_becoming_zero(self):
        for cell in ("", "  "):
            with self.subTest(cell=cell):
                rows = list(ROWS)
                rows[2] = "5,300," + cell
                self.assertFails(rows, "línea 4", "columna 2", "vacío", repr(cell))

    def test_truncated_row_fails(self):
        rows = list(ROWS)
        rows[3] = "6,400"
        self.assertFails(rows, "línea 5", "columna 2", "2 columna(s)", "le falta el valor")

    def test_the_line_named_is_where_the_row_starts(self):
        # A quoted field may span several lines: the row starts at line 4 and ends at line 5.
        rows = ["3,100,0.80", "4,200,0.81", '5,300,"0.8\nx"', "6,400,0.83"]
        self.assertFails(rows, "línea 4,", "columna 2", repr("0.8\nx"))


class PowerTest(CsvCase):
    def test_malformed_power_fails_instead_of_dropping_the_row(self):
        # Before: the row was taken for noise and the curve interpolated over it.
        for cell in ("3OO", "", "nan", "inf"):
            for ct_col in (2, None):
                with self.subTest(cell=cell, ct_col=ct_col):
                    rows = list(ROWS)
                    rows[2] = f"5,{cell},0.82"
                    with self.assertRaises(ValueError) as ctx:
                        self.read(rows, ct_col=ct_col)
                    message = str(ctx.exception)
                    for part in ("Potencia no válida", "curve.csv", "línea 4", "columna 1", repr(cell)):
                        self.assertIn(part, message)

    def test_row_with_a_speed_and_nothing_else_fails(self):
        rows = list(ROWS)
        rows[2] = "5"
        self.assertFails(rows, "Fila incompleta", "línea 4", "columna 1", "1 columna(s)")


class CtRangeTest(CsvCase):
    def test_ct_above_one_up_to_the_admission_threshold_is_kept_intact(self):
        rows = ["3,100,0.80", "4,200,1.05", "5,300,1.2"]
        self.assertEqual(self.read(rows)[2], [0.80, 1.05, 1.2])

    def test_out_of_range_or_non_finite_ct_fails_naming_its_row(self):
        for value in ("1.3", "5", "-0.1", "nan", "inf", "-inf"):
            with self.subTest(value=value):
                rows = list(ROWS)
                rows[1] = "4,200," + value
                self.assertFails(rows, "línea 3", "columna 2", repr(value))


class NoiseTest(CsvCase):
    def test_blank_lines_and_repeated_headers_are_still_skipped(self):
        noisy = ["", ROWS[0], HEADER, ROWS[1], "m/s,kW,-", ",,", ROWS[2], "# note", "", ROWS[3], HEADER, ROWS[4], ""]
        self.assertEqual(self.read(noisy), self.read(ROWS))
        self.assertEqual(list(zip(*self.read(noisy))), EXPECTED)


class WithoutCtTest(CsvCase):
    def test_without_a_ct_column_the_whole_curve_is_estimated(self):
        for header, rows in (("ws,power_kw", [r.rsplit(",", 1)[0] for r in ROWS]), (HEADER, ROWS)):
            with self.subTest(header=header):
                ws, power_w, ct = self.read(rows, ct_col=None, header=header)
                self.assertEqual(ws, [3.0, 4.0, 5.0, 6.0, 7.0])
                self.assertEqual(ct, _estimate_ct(ws, power_w))

    def test_configured_ct_column_with_every_cell_empty_fails(self):
        self.assertFails([r.rsplit(",", 1)[0] + "," for r in ROWS], "columna 2", "vacía en todas las filas")


class WhitespaceDelimiterTest(CsvCase):
    def read_text(self, text, delimiter=" ", skip_header=1, ct_col=2):
        path = os.path.join(self.folder, "whitespace.txt")
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(text)
        return load_curves_from_txt(path, TxtSpec(
            ws_col=0, power_col=1, delimiter=delimiter, skip_header=skip_header, ct_col=ct_col,
        ))

    def test_whitespace_variants_preserve_every_point(self):
        reference = self.read_text("ws power ct\n3 100 0.80\n4 200 0.81\n5 300 0.82\n")
        for separator, indent, trailing in (
            ("  ", "", ""), ("   ", "", ""), (" ", "  ", "  "),
            ("\t", "", ""), (" \t  ", "\t  ", " \t"),
        ):
            with self.subTest(separator=separator, indent=indent):
                lines = [indent + separator.join(row.split()) + trailing
                         for row in ("3 100 0.80", "4 200 0.81", "5 300 0.82")]
                result = self.read_text("ws power ct\n" + "\n".join(lines) + "\n")
                self.assertEqual(result, reference)
                self.assertEqual(result[0], [3., 4., 5.])

    def test_noise_headers_and_crlf_keep_data(self):
        result = self.read_text("ws power ct\r\n\r\n   3 100 0.80\r\n# note\r\nws power ct\r\n\t4 200 0.81\r\n")
        self.assertEqual(result, ([3., 4.], [100000., 200000.], [0.8, 0.81]))

    def test_skip_header_and_no_header(self):
        data = " 3 100 0.80\n 4 200 0.81\n"
        self.assertEqual(self.read_text(data, skip_header=0),
                         self.read_text("description\nws power ct\n" + data, skip_header=2))

    def test_missing_values_and_invalid_cells_name_physical_line(self):
        for bad, expected in (("  4\t200", "columna 2"),
                              ("  4", "columna 1"),
                              ("  4 ERROR 0.81", "Potencia no válida"),
                              ("  4 200 9.0", "Ct no válido")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as ctx:
                    self.read_text("description\nws power ct\n\n3 100 0.80\n" + bad + "\n",
                                   skip_header=2)
                self.assertIn("línea 5", str(ctx.exception))
                self.assertIn(expected, str(ctx.exception))

    def test_without_ct_preserves_power_and_estimates_ct(self):
        ws, power, ct = self.read_text("ws power\n  3   100\n\t4\t200\n", ct_col=None)
        self.assertEqual(ct, _estimate_ct(ws, power))
        self.assertEqual(power, [100000., 200000.])

    def test_other_delimiters_keep_quoted_fields_and_spaces(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                text = delimiter.join(("ws", "power", "ct")) + "\n"
                text += delimiter.join(('" 3 "', '" 100 "', '"0.80"')) + "\n"
                text += delimiter.join(("4", "200", "0.81")) + "\n"
                self.assertEqual(self.read_text(text, delimiter=delimiter),
                                 ([3., 4.], [100000., 200000.], [0.8, 0.81]))

    def test_other_delimiters_preserve_empty_columns_and_multiline_row_numbers(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                header = delimiter.join(("ws", "power", "ct"))
                for power in ("", '"bad\npower"'):
                    text = header + "\n" + delimiter.join(("3", power, "0.80")) + "\n"
                    with self.assertRaises(ValueError) as ctx:
                        self.read_text(text, delimiter=delimiter)
                    self.assertIn("Potencia no válida", str(ctx.exception))
                    self.assertIn("línea 2", str(ctx.exception))


class AuxiliaryCurveReadersTest(CsvCase):
    def model(self, text, delimiter=" "):
        path = os.path.join(self.folder, "power.txt")
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write(text)
        return {"path": path, "delimiter": delimiter, "ws_col": 0,
                "power_col": 1, "skip_header": 1}

    def test_all_readers_agree_for_whitespace_and_bom(self):
        for separator, indent in (("  ", ""), ("   ", "  "), (" \t ", "\t")):
            with self.subTest(separator=separator):
                rows = [indent + separator.join(row.split())
                        for row in ("3 100 0.80", "4 200 0.81", "5 300 0.82")]
                model = self.model("ws power ct\n" + "\n".join(rows) + "\n")
                ws, power, _ = load_curves_from_txt(model["path"], TxtSpec(
                    ws_col=0, power_col=1, delimiter=" ", ct_col=2))
                for reader in (read_curve_from_model_dict, _read_curve_from_model_dict):
                    actual_ws, actual_power = reader(model)
                    self.assertEqual(actual_ws.tolist(), ws)
                    self.assertEqual((actual_power * 1000).tolist(), power)
                self.assertAlmostEqual(_estimate_p_rated_mw(model), 0.3)

    def test_invalid_pairs_are_skipped_whole_without_shifting_power(self):
        for delimiter in (" ", ",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                rows = [delimiter.join(row) for row in (
                    ("ws", "power"), ("3", "100"), ("4", "bad"),
                    ("bad", "500"), ("5", "300"), ("6",),
                )]
                model = self.model("\n".join(rows), delimiter)
                for reader in (read_curve_from_model_dict, _read_curve_from_model_dict):
                    ws, power = reader(model)
                    self.assertEqual(ws.tolist(), [3., 5.])
                    self.assertEqual(power.tolist(), [100., 300.])
                    self.assertEqual(len(ws), len(power))

    def test_not_enough_complete_pairs_returns_none(self):
        model = self.model("ws power\n3 bad\n4 200\n5 bad\n")
        for reader in (read_curve_from_model_dict, _read_curve_from_model_dict):
            self.assertIsNone(reader(model))

    def test_auxiliary_csv_readers_keep_quoted_numeric_fields(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                rows = [delimiter.join(row) for row in (
                    ("ws", "power"), ('"3"', '"100"'), ('"4"', '"200"'),
                )]
                model = self.model("\n".join(rows), delimiter)
                for reader in (read_curve_from_model_dict, _read_curve_from_model_dict):
                    ws, power = reader(model)
                    self.assertEqual(ws.tolist(), [3., 4.])
                    self.assertEqual(power.tolist(), [100., 200.])


if __name__ == "__main__":
    unittest.main()

