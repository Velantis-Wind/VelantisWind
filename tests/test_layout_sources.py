# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest
from unittest import mock

from openpyxl import Workbook

from VelantisWind.ui_core.layout_sources import _rows_to_points, _validated_crs, read_xy_table


def _write(folder: str, name: str, text: str) -> str:
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class RowsToPointsTest(unittest.TestCase):
    def test_named_columns_in_any_position(self):
        rows = [("id", "Northing", "Easting"), ("T1", "4400000", "500000"), ("T2", "4400300.5", "500250,5")]
        self.assertEqual(_rows_to_points(rows), [(500000.0, 4400000.0), (500250.5, 4400300.5)])

    def test_projected_pair_before_geographic_whatever_the_order(self):
        for header in (("id", "longitude", "latitude", "x", "y"), ("lon", "northing", "easting", "lat"),
                       ("y", "lat", "lon", "x")):
            with self.subTest(header=header):
                values = {"x": "500000", "easting": "500000", "y": "4400000", "northing": "4400000",
                          "lon": "-3", "longitude": "-3", "lat": "40", "latitude": "40", "id": "T1"}
                self.assertEqual(_rows_to_points([header, tuple(values[h] for h in header)]), [(500000.0, 4400000.0)])

    def test_geographic_pair_alone(self):
        self.assertEqual(_rows_to_points([("Latitude", "Longitude"), ("40", "-3")]), [(-3.0, 40.0)])

    def test_incomplete_pairs_and_repeated_aliases(self):
        # One pair incomplete and no name of the other: the first two columns, as before.
        self.assertEqual(_rows_to_points([("x", "y_utm"), ("500000", "4400000")]), [(500000.0, 4400000.0)])
        # Only the geographic pair is complete.
        self.assertEqual(_rows_to_points([("x", "lat", "lon"), ("500000", "40", "-3")]), [(-3.0, 40.0)])
        # Several names of one axis: the first in the header.
        self.assertEqual(_rows_to_points([("easting", "x", "y"), ("500000", "1", "4400000")]), [(500000.0, 4400000.0)])

    def test_empty_rows_before_the_header(self):
        # As openpyxl gives an empty first row: the header below still names the columns.
        self.assertEqual(_rows_to_points([(None, None), ("Y", "X"), (4400000, 500000)]), [(500000.0, 4400000.0)])

    def test_axes_of_two_systems_are_never_mixed(self):
        # Neither pair complete: reading the first two columns would take a longitude and a northing.
        with self.assertRaises(ValueError):
            _rows_to_points([("lon", "northing"), ("-3", "4400000")])

    def test_coordinates_that_are_not_finite_are_unreadable(self):
        for bad in ("nan", "inf", "-inf", "1e999"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, r": 3\."):
                    _rows_to_points([("x", "y"), ("500000", "4400000"), (bad, "4400100")])
                # Without named columns either: a first row of such numbers is data, not a header.
                with self.assertRaisesRegex(ValueError, r": 1\."):
                    _rows_to_points([(bad, bad), ("500100", "4400100")])

    def test_without_header_uses_first_two_columns(self):
        rows = [("500000", "4400000", "T1"), ("500250", "4400300", "T2")]
        self.assertEqual(_rows_to_points(rows), [(500000.0, 4400000.0), (500250.0, 4400300.0)])

    def test_blank_rows_are_skipped_and_unreadable_ones_refused(self):
        # A short or non-numeric row is a turbine whose coordinates cannot be read: the import stops and names its row
        # in the file, instead of leaving the turbine out.
        rows = [("x", "y"), (None, None), ("", " "), ("500000",), ("n/a", "4400000"), (500100, 4400100)]
        with self.assertRaisesRegex(ValueError, r"\b4, 5\b"):
            _rows_to_points(rows)
        self.assertEqual(_rows_to_points([("x", "y"), (None, None), ("", " "), (500100, 4400100)]), [(500100.0, 4400100.0)])

    def test_without_named_columns_the_first_row_may_be_a_header(self):
        self.assertEqual(_rows_to_points([("E", "N"), ("500000", "4400000")]), [(500000.0, 4400000.0)])
        with self.assertRaisesRegex(ValueError, r"\b3\b"):
            _rows_to_points([("E", "N"), ("500000", "4400000"), ("n/a", "4400050")])
        # A first row with one coordinate that reads as a number is a turbine, not a header.
        for first in (("500000", ""), ("500000",), ("n/a", "4400000")):
            with self.subTest(first=first):
                with self.assertRaisesRegex(ValueError, r": 1\."):
                    _rows_to_points([first, ("500100", "4400100")])

    def test_empty_or_without_coordinates_is_rejected(self):
        with self.assertRaises(ValueError):
            _rows_to_points([("", ""), ()])
        with self.assertRaises(ValueError):
            _rows_to_points([("x", "y"), ("a", "b")])


class ReadXyTableTest(unittest.TestCase):
    def test_csv_with_semicolons_and_decimal_commas(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write(folder, "layout.csv", "lon;lat\n-3,5;40,25\n-3,6;40,30\n")
            self.assertEqual(read_xy_table(path), [(-3.5, 40.25), (-3.6, 40.3)])

    def test_xlsx_reads_first_sheet(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "layout.xlsx")
            book = Workbook()
            sheet = book.active
            for row in (("Name", "X", "Y"), ("T1", 500000, 4400000), (None, None, None), ("T2", 500250.5, 4400300)):
                sheet.append(row)
            book.create_sheet("other").append((1, 2))
            book.save(path)
            self.assertEqual(read_xy_table(path), [(500000.0, 4400000.0), (500250.5, 4400300.0)])

    def test_xlsx_without_openpyxl_asks_for_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write(folder, "layout.xlsx", "")
            with mock.patch.dict(sys.modules, {"openpyxl": None}):
                with self.assertRaisesRegex(RuntimeError, "openpyxl"):
                    read_xy_table(path)

    def test_unreadable_rows_are_named_by_their_line_in_the_csv(self):
        # A quoted field over two lines: the unreadable record starts on line 4 of the file.
        with tempfile.TemporaryDirectory() as folder:
            path = _write(folder, "layout.csv", 'x,y,note\n500000,4400000,"a\nb"\n500100,,bad\n')
            with self.assertRaisesRegex(ValueError, r": 4\."):
                read_xy_table(path)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ValueError):
            read_xy_table(os.path.join(tempfile.gettempdir(), "does-not-exist.csv"))



# The 28 synthetic cases of plan_capa_turbinas V15. In the 20 where the energy dialog's former CSV reader
# and the shared one agreed, the values are the ones the former reader gave.
_TWO = [(500000.0, 4400000.0), (500300.0, 4400100.0)]
_SAME_AS_FORMER_READER = [
    ("x,y\n500000,4400000\n500300.5,4400100\n", [(500000.0, 4400000.0), (500300.5, 4400100.0)]),
    ("X,Y\n500000,4400000\n500300,4400100\n", _TWO),
    ("id,x,y\nT1,500000,4400000\nT2,500300,4400100\n", _TWO),
    ("id,x,y\n1,500000,4400000\n2,500300,4400100\n", _TWO),
    ("Easting,Northing\n500000,4400000\n500300,4400100\n", _TWO),
    ("name,easting,northing\nT1,500000,4400000\nT2,500300,4400100\n", _TWO),
    ("y,x\n4400000,500000\n4400100,500300\n", _TWO),
    ("x,y,model\n500000,4400000,A\n500300,4400100,A\n", _TWO),
    ("500000,4400000\n500300,4400100\n", _TWO),
    ("500000,4400000,100\n500300,4400100,100\n", _TWO),
    ("x, y\n500000, 4400000\n500300, 4400100\n", _TWO),
    ("x , y\n 500000 , 4400000 \n 500300 , 4400100 \n", _TWO),
    ("x,y\n\n500000,4400000\n\n500300,4400100\n\n", _TWO),
    ("\ufeffx,y\n500000,4400000\n500300,4400100\n", _TWO),
    ('"x","y"\n"500000","4400000"\n"500300","4400100"\n', _TWO),
    ("x,y\n5e5,4.4e6\n5.003e5,4.4001e6\n", _TWO),
    ("utm_x,utm_y\n500000,4400000\n500300,4400100\n", _TWO),
    ("E,N\n500000,4400000\n500300,4400100\n", _TWO),
    ("lon,lat\n-3.5,40.25\n-3.6,40.30\n", [(-3.5, 40.25), (-3.6, 40.3)]),
    ("x,y\n500000,4400000\n", [(500000.0, 4400000.0)]),
]
# The 8 where they differ: the former reader read 0 points, took the id as X, returned nothing without error, or left
# out a row it could not read (now refused, naming the row).
_READ_ONLY_BY_THE_SHARED_READER = [
    ("x,y\n500000,4400000\nn/a,4400050\n500300,4400100\n", ValueError),
    ("id,utm_x,utm_y\nT1,500000,4400000\nT2,500300,4400100\n", _TWO),
    ("id,utm_x,utm_y\n1,500000,4400000\n2,500300,4400100\n", _TWO),
    ("x;y\n500000;4400000\n500300;4400100\n", _TWO),
    ("x;y\n500000,5;4400000\n500300,5;4400100\n", [(500000.5, 4400000.0), (500300.5, 4400100.0)]),
    ("x\ty\n500000\t4400000\n500300\t4400100\n", _TWO),
    ("", ValueError),
    ("x,y\n", ValueError),
]


class FormerEnergyReaderCasesTest(unittest.TestCase):
    def test_the_28_cases(self):
        cases = _SAME_AS_FORMER_READER + _READ_ONLY_BY_THE_SHARED_READER
        self.assertEqual((len(_SAME_AS_FORMER_READER), len(cases)), (20, 28))
        with tempfile.TemporaryDirectory() as folder:
            for i, (text, expected) in enumerate(cases):
                with self.subTest(case=i, text=text[:30]):
                    path = os.path.join(folder, f"case{i}.csv")
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(text)
                    if expected is ValueError:
                        with self.assertRaises(ValueError):
                            read_xy_table(path)
                    else:
                        self.assertEqual(read_xy_table(path), expected)


class ValidatedCrsTest(unittest.TestCase):
    def test_valid_written_crs_is_used(self):
        self.assertEqual(_validated_crs("EPSG:32630").authid(), "EPSG:32630")

    def test_invalid_written_crs_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonsense"):
            _validated_crs("nonsense")


if __name__ == "__main__":
    unittest.main()
