"""Shared TXT/CSV row parsing for turbine curves, without QGIS dependencies."""
import csv


def autodetected_table_rows(stream, delimiter, dialect="excel"):
    """Preserve TSV cells and CSV quotes in automatically detected tables.

    Space-separated tables accept alignment via csv's skipinitialspace, while
    tab-separated tables retain every column, including empty identifiers.
    Unlike explicit numeric TXT curves, these tables may contain quoted names.
    """
    if delimiter == " ":
        return csv.reader(stream, dialect=dialect, delimiter=" ", skipinitialspace=True)
    return csv.reader(stream, dialect=dialect, delimiter=delimiter)


def numbered_curve_rows(stream, delimiter, skip_header=0, dialect="excel"):
    """Yield (physical start line, columns), retaining CSV quoting for other delimiters."""
    def rows():
        if delimiter == " ":
            for line, text in enumerate(stream, start=1):
                yield line, text.split()
        else:
            reader = csv.reader(stream, dialect=dialect, delimiter=delimiter)
            end = 0
            for row in reader:
                line, end = end + 1, reader.line_num
                yield line, row

    reader = rows()
    for _ in range(max(0, skip_header)):
        next(reader, None)
    yield from reader


def read_power_pairs(path, ws_col, power_col, delimiter, skip_header):
    """Read auxiliary power diagnostics, accepting or skipping each pair as a whole."""
    pairs = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        for _, row in numbered_curve_rows(stream, delimiter, skip_header):
            if len(row) <= max(ws_col, power_col):
                continue
            try:
                pair = float(row[ws_col]), float(row[power_col])
            except (ValueError, TypeError, IndexError):
                continue
            pairs.append(pair)
    if len(pairs) < 2:
        return None
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]
