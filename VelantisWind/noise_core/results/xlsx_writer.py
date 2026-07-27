# -*- coding: utf-8 -*-
"""Small dependency-free XLSX writer for the Noise results package.

The QGIS Windows process can load native XML libraries from several bundled
packages.  ``openpyxl`` prefers ``lxml`` when it is present and, in some QGIS
installations, saving a workbook can then terminate the process before Python
has a chance to report an exception.  This module writes the small subset of
OOXML needed by VelantisWind using only the Python standard library.

It intentionally supports plain cells, a formatted header row, column widths
and frozen headers.  Formula strings are stored as text, which also avoids
spreadsheet-formula injection from user supplied receiver attributes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import re
import tempfile
from typing import Iterable, Sequence
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile


_INVALID_XML_CHARS = re.compile(
    "[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
)
_INVALID_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def _clean_text(value) -> str:
    text = "" if value is None else str(value)
    return _INVALID_XML_CHARS.sub("", text)


def _column_name(index: int) -> str:
    """Return the one-based Excel column name (1 -> A, 27 -> AA)."""
    if index < 1:
        raise ValueError("Excel column indices are one-based")
    chars = []
    while index:
        index, rem = divmod(index - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def _safe_sheet_names(titles: Iterable[str]) -> list[str]:
    names: list[str] = []
    used: set[str] = set()
    for pos, title in enumerate(titles, start=1):
        base = _INVALID_SHEET_CHARS.sub("-", _clean_text(title)).strip().strip("'")
        base = (base or f"Sheet {pos}")[:31]
        candidate = base
        suffix = 2
        while candidate.casefold() in used:
            marker = f" ({suffix})"
            candidate = base[: max(1, 31 - len(marker))] + marker
            suffix += 1
        used.add(candidate.casefold())
        names.append(candidate)
    return names


def _cell_xml(row: int, col: int, value, header: bool = False) -> str:
    ref = f"{_column_name(col)}{row}"
    style = ' s="1"' if header else ""
    if isinstance(value, bool):
        return f'<c r="{ref}"{style} t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            number = float(value)
        except Exception:
            number = math.nan
        if math.isfinite(number):
            rendered = str(value) if isinstance(value, int) else format(number, ".15g")
            return f'<c r="{ref}"{style}><v>{rendered}</v></c>'
    text = escape(_clean_text(value))
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}"{style} t="inlineStr"><is><t{preserve}>{text}</t></is></c>'


def _sheet_xml(rows: Sequence[Sequence[object]], freeze_header: bool) -> str:
    normalized = [list(row or []) for row in rows]
    max_cols = max((len(row) for row in normalized), default=1)
    max_rows = max(1, len(normalized))
    dimension = f"A1:{_column_name(max_cols)}{max_rows}" if max_cols > 1 or max_rows > 1 else "A1"
    widths = [10] * max_cols
    for row in normalized[:2000]:
        for col, value in enumerate(row):
            longest = max((len(part) for part in _clean_text(value).splitlines()), default=0)
            widths[col] = min(55, max(widths[col], longest + 2))

    cols = "".join(
        f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>'
        for idx, width in enumerate(widths, start=1)
    )
    pane = (
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        if freeze_header and normalized
        else ""
    )
    row_xml = []
    for row_idx, values in enumerate(normalized, start=1):
        cells = "".join(
            _cell_xml(row_idx, col_idx, value, header=bool(freeze_header and row_idx == 1))
            for col_idx, value in enumerate(values, start=1)
        )
        row_xml.append(f'<row r="{row_idx}">{cells}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        f'<sheetViews><sheetView workbookViewId="0">{pane}</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{cols}</cols><sheetData>{"".join(row_xml)}</sheetData>'
        '</worksheet>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="0"/>'
        '<fonts count="2">'
        '<font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>'
        '</fonts>'
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1E3A5F"/><bgColor indexed="64"/></patternFill></fill>'
        '</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '<dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>'
        '</styleSheet>'
    )


def write_xlsx_workbook(path: str, sheets: Sequence[dict]) -> str:
    """Write an XLSX workbook atomically and return its absolute path.

    Each sheet dictionary accepts ``title``, ``rows`` and ``freeze_header``.
    The destination is replaced only after a complete ZIP package has been
    produced, so an interrupted export cannot destroy an existing workbook.
    """
    if not sheets:
        raise ValueError("At least one worksheet is required")
    output_path = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(output_path) or os.getcwd()
    if not os.path.isdir(parent):
        raise OSError(f"Destination folder does not exist: {parent}")

    names = _safe_sheet_names(sheet.get("title", "") for sheet in sheets)
    temp_handle = tempfile.NamedTemporaryFile(
        mode="wb", prefix=".velantis_xlsx_", suffix=".tmp", dir=parent, delete=False
    )
    temp_path = temp_handle.name
    temp_handle.close()
    try:
        sheet_overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for idx in range(1, len(sheets) + 1)
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            f'{sheet_overrides}</Types>'
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'
        )
        sheet_entries = "".join(
            f'<sheet name={quoteattr(name)} sheetId="{idx}" r:id="rId{idx}"/>'
            for idx, name in enumerate(names, start=1)
        )
        workbook = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<bookViews><workbookView/></bookViews><sheets>{sheet_entries}</sheets></workbook>'
        )
        workbook_rels_entries = "".join(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
            for idx in range(1, len(sheets) + 1)
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{workbook_rels_entries}'
            f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>'
        )
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        core = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:creator>VelantisWind</dc:creator><cp:lastModifiedBy>VelantisWind</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'
        )
        app = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>VelantisWind</Application><AppVersion>0.1.16</AppVersion></Properties>'
        )

        with ZipFile(temp_path, "w", compression=ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", root_rels)
            archive.writestr("docProps/core.xml", core)
            archive.writestr("docProps/app.xml", app)
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            archive.writestr("xl/styles.xml", _styles_xml())
            for idx, sheet in enumerate(sheets, start=1):
                rows = list(sheet.get("rows") or [])
                archive.writestr(
                    f"xl/worksheets/sheet{idx}.xml",
                    _sheet_xml(rows, bool(sheet.get("freeze_header", False))),
                )
        os.replace(temp_path, output_path)
        return output_path
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


__all__ = ["write_xlsx_workbook"]
