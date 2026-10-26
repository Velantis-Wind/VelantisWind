# -*- coding: utf-8 -*-
"""Reader for ``.owtg`` turbine files into a `TurbineCurveTable`.

A thin adapter that follows the contract of ``density_curve.py``: it produces a
`TurbineCurveTable`, validates strictly and never resamples. The format is
matrix-shaped: one list of wind speeds, one list of air densities and a matrix
of values, and everything goes by position, so a reordered or mislabelled
column would swap whole curves without anything failing. Hence the cross-checks.

Supported variant
-----------------
Root ``<TurbineType>`` with:

* ``HubHeight``, ``RotorDiameter``, ``LowCutIn``, ``HighCutOut`` and
  ``DesignAirDensity`` (``@value``): geometry, the declared operating band,
  which must lie within the tabulated wind speeds, and the default density;
* ``Power_Tables`` with a ``Count`` of 1 and one ``Power_Table0``, and one
  ``Thrust_Table``, both of ``Type`` ``TurbineTable`` and with the same grid:
  ``Velocities`` (``VelocityN``), ``AirDensities`` (``RhoN``) and ``Values``,
  with one ``<RhoX.XXXXXX>`` column per density, tagged with that density, and
  one ``v{column}-{row}`` cell per wind speed, and nothing else in those
  elements. Every declared ``Count``, ``Columns`` and ``Rows`` matches what is
  there, and the indices run from zero without gaps or repetitions;
* power in kW, at most 5 % above the rated power (``CapacityKW``, or
  ``PeakOutputKW`` without it). Without either, at most 30 MW, the ceiling of
  a plausible turbine: above it the table looks written in W.

Rejected, because the model does not represent them and reading the curves
without them would describe another machine:

* curves that depend on turbulence: ``AdjustPowerCurvesForTI`` or
  ``SwitchPowerCurvesOnIref`` set, or more than one power table;
* active operating modifications: ``HighWindHysteresis``, ``Derate``,
  ``PowerCurveAdjustment`` and ``Consumption`` with ``Enable`` set (a block
  present must say whether it is enabled), ``TemperatureShutDownEnabled`` set
  and a non-zero ``PerformanceShiftWS``. A flag that is absent is off.

``IEC_adjustment`` (0 or 1) is informational: the file already carries the
curves by density, which are used as they are. The rest (RPM, IEC class, costs, icing,
noise, the turbulence range of the curves...) is not read as calculation data.

Anything else is rejected as an unsupported variant, naming the element.
"""
from __future__ import annotations

import math
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

from ..log_text import log_text
from ..turbine import _error
from .density_curve import CurveTableError, TurbineCurveTable

try:  # pragma: no cover - depends on the environment
    # defusedxml hardens the parser against entity expansion. It is not a hard
    # dependency: these files are local and chosen by the user.
    from defusedxml.ElementTree import parse as _xml_parse  # type: ignore
except Exception:  # pragma: no cover
    from xml.etree.ElementTree import parse as _xml_parse  # nosec B405 B314 - local user-selected file

__all__ = ["OwtgFormatError", "OWTG_EXTENSIONS", "is_owtg_path", "load_owtg"]

OWTG_EXTENSIONS = (".owtg",)

# Tolerances and thresholds fixed here, not left to each comparison.
_SPEED_TOLERANCE_MS = 1e-6     # same wind speed in the power and the thrust table
_DENSITY_TOLERANCE = 1e-6      # same density in both tables, and in a column tag
_RATED_MARGIN = 1.05           # the table may exceed the rated power by 5 %
_MAX_PLAUSIBLE_KW = 30000.0    # without a rated power, the largest plausible turbine
_RATED_TOLERANCE_KW = 1e-6     # CapacityKW and PeakOutputKW are the same
_LOW_OUTPUT_FRACTION = 0.5     # a table below half the rated power gets a note

_ROOT = "TurbineType"
_TABLE_TYPE = "TurbineTable"
_CELL = re.compile(r"v(\d+)-(\d+)")
_COLUMN = re.compile(r"Rho\d+\.\d{6}")
_POWER_TABLE = re.compile(r"Power_Table(\d+)")
# Words that go inside other messages as data: a template of their own, so they can be translated.
_TURBULENCE = log_text("de la intensidad de turbulencia")
_IREF = log_text("de la clase de turbulencia Iref")
# Operating modifications: the element, where it says it is active, and what it changes.
_OPERATING_BLOCKS = (
    ("HighWindHysteresis", log_text("la histéresis de viento fuerte")),
    ("Derate", log_text("la reducción de potencia por temperatura y altitud")),
    ("PowerCurveAdjustment", log_text("el ajuste de la curva de potencia")),
    ("Consumption", log_text("el consumo propio de la turbina")),
)
_OPERATING_FLAGS = (
    ("TemperatureShutDownEnabled", log_text("la parada por temperatura")),
    ("PerformanceShiftWS", log_text("el desplazamiento de la curva en velocidad")),
)


class OwtgFormatError(CurveTableError):
    """A ``.owtg`` file that does not match the supported variant."""


def is_owtg_path(path: str) -> bool:
    return str(path or "").lower().endswith(OWTG_EXTENSIONS)


def _fail(template: str, **data) -> OwtgFormatError:
    return _error(OwtgFormatError, template, **data)


def _number(raw, where: str) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        value = math.nan
    if not math.isfinite(value):
        raise _fail("Variante de .owtg no soportada: {where} no es un número finito: {raw!r}.", where=where, raw=raw)
    return value


def _single(parent, tag: str, where: str):
    found = parent.findall(tag)
    if not found:
        raise _fail("Variante de .owtg no soportada: falta el elemento <{tag}> en {where}.", tag=tag, where=where)
    if len(found) > 1:
        raise _fail(
            "Variante de .owtg no soportada: {where} tiene {n} elementos <{tag}> donde se espera uno.",
            where=where, n=len(found), tag=tag,
        )
    return found[0]


def _value(parent, tag: str, where: str, *, required: bool = True) -> Optional[float]:
    """``<tag value="..."/>`` as a number. Optional elements may be absent or empty."""
    if not required and not parent.findall(tag):
        return None
    raw = _single(parent, tag, where).get("value")
    if raw is None or not str(raw).strip():
        if not required:
            return None
        raise _fail("Variante de .owtg no soportada: {where}/{tag} no tiene valor.", where=where, tag=tag)
    return _number(raw, f"{where}/{tag}")


def _count(parent, tag: str, where: str) -> int:
    value = _value(parent, tag, where)
    if value < 0 or value != int(value):
        raise _fail(
            "Variante de .owtg no soportada: {where}/{tag} debe ser un entero no negativo: {value:g}.",
            where=where, tag=tag, value=value,
        )
    return int(value)


def _flag(parent, tag: str, where: str) -> float:
    """A flag or setting that is off (0) when absent."""
    value = _value(parent, tag, where, required=False) if parent.findall(tag) else 0.0
    if value is None:
        raise _fail("Variante de .owtg no soportada: {where}/{tag} no tiene valor.", where=where, tag=tag)
    return value


def _indexed(parent, prefix: str, count: int, where: str) -> List[float]:
    """``<Prefix0 value=".."/> .. <PrefixN-1 value=".."/>``, in index order, exactly ``count`` of them."""
    found: Dict[int, str] = {}
    for child in parent:
        match = re.fullmatch(re.escape(prefix) + r"(\d+)", str(child.tag))
        if not match:
            if child.tag != "Count":
                raise _unexpected(child, where)
            continue
        index = int(match.group(1))
        if index in found:
            raise _fail("Variante de .owtg no soportada: índice duplicado <{tag}> en {where}.", tag=child.tag, where=where)
        found[index] = child.get("value")
    if len(found) != count or sorted(found) != list(range(count)):
        raise _fail(
            "Variante de .owtg no soportada: {where} declara Count={count} y contiene los índices {indices} de "
            "<{prefix}N>; deben ir de 0 a {last} sin huecos.",
            where=where, count=count, indices=_listing(sorted(found)), prefix=prefix, last=count - 1,
        )
    return [_number(found[i], f"{where}/{prefix}{i}") for i in range(count)]


def _unexpected(child, where: str) -> OwtgFormatError:
    return _fail("Variante de .owtg no soportada: elemento inesperado <{tag}> en {where}.", tag=child.tag, where=where)


def _listing(values: Sequence[int]) -> str:
    shown = ", ".join(str(v) for v in values[:8])
    return (shown + ", …" if len(values) > 8 else shown) or "—"


def _columns(values_node, densities: Sequence[float], n_ws: int, where: str) -> List[List[float]]:
    """``<Values>`` as ``matrix[speed][density]``, each column and cell checked against its declared place."""
    columns = _count(values_node, "Columns", where)
    nodes = [child for child in values_node if _COLUMN.fullmatch(str(child.tag))]
    for child in values_node:
        if child.tag != "Columns" and child not in nodes:
            raise _unexpected(child, where)
    if columns != len(densities) or len(nodes) != len(densities):
        raise _fail(
            "Variante de .owtg no soportada: {where} declara Columns={columns} y contiene {found} columnas <RhoX>, "
            "pero AirDensities declara {expected} densidades.",
            where=where, columns=columns, found=len(nodes), expected=len(densities),
        )
    matrix = [[0.0] * len(densities) for _ in range(n_ws)]
    for j, node in enumerate(nodes):
        column = f"{where}/{node.tag}"
        tagged = _number(str(node.tag)[len("Rho"):], f"{where}/<{node.tag}>")
        if abs(tagged - densities[j]) > _DENSITY_TOLERANCE:
            raise _fail(
                "Variante de .owtg no soportada: la columna {index} de {where} es <{tag}>, pero AirDensities declara "
                "{expected:g} kg/m³ en esa posición.",
                index=j, where=where, tag=node.tag, expected=densities[j],
            )
        rows = _count(node, "Rows", column)
        cells: Dict[int, str] = {}
        for cell in node:
            match = _CELL.fullmatch(str(cell.tag))
            if not match:
                if cell.tag != "Rows":
                    raise _unexpected(cell, column)
                continue
            if int(match.group(1)) != j:
                raise _fail(
                    "Variante de .owtg no soportada: la celda <{tag}> está en la columna {index} de {where}.",
                    tag=cell.tag, index=j, where=where,
                )
            row = int(match.group(2))
            if row in cells:
                raise _fail("Variante de .owtg no soportada: celda duplicada <{tag}> en {where}.", tag=cell.tag, where=column)
            cells[row] = cell.get("value")
        if rows != n_ws or sorted(cells) != list(range(n_ws)):
            raise _fail(
                "Variante de .owtg no soportada: {where} declara Rows={rows} y contiene las filas {indices}; "
                "Velocities declara {expected} velocidades.",
                where=column, rows=rows, indices=_listing(sorted(cells)), expected=n_ws,
            )
        for i in range(n_ws):
            matrix[i][j] = _number(cells[i], f"{column}/v{j}-{i}")
    return matrix


def _read_table(node, where: str) -> Tuple[List[float], List[float], List[List[float]]]:
    """One ``TurbineTable``: ``(wind speeds, densities, matrix[speed][density])``."""
    kind = (_single(node, "Type", where).text or "").strip()
    if kind != _TABLE_TYPE:
        raise _fail(
            "Variante de .owtg no soportada: {where}/Type es {kind!r}; solo se admite {expected!r}.",
            where=where, kind=kind, expected=_TABLE_TYPE,
        )
    speeds_node = _single(node, "Velocities", where)
    speeds = _indexed(speeds_node, "Velocity", _count(speeds_node, "Count", f"{where}/Velocities"), f"{where}/Velocities")
    densities_node = _single(node, "AirDensities", where)
    densities = _indexed(densities_node, "Rho", _count(densities_node, "Count", f"{where}/AirDensities"), f"{where}/AirDensities")
    matrix = _columns(_single(node, "Values", where), densities, len(speeds), f"{where}/Values")
    return speeds, densities, matrix


def _same(a: Sequence[float], b: Sequence[float], tolerance: float) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tolerance for x, y in zip(a, b))


def _check_flags(root) -> None:
    """Reject curves that depend on inputs the model does not represent."""
    for tag, what in (("AdjustPowerCurvesForTI", _TURBULENCE), ("SwitchPowerCurvesOnIref", _IREF)):
        value = _flag(root, tag, _ROOT)
        if value != 0.0:
            raise _fail(
                "Variante de .owtg no soportada: {tag}={value:g}. Las curvas de potencia dependen {what}, que este "
                "cálculo no representa.",
                tag=tag, value=value, what=what,
            )
    active = []
    for tag, what in _OPERATING_BLOCKS:
        if root.findall(tag):
            where = f"{tag}/Enable"
            value = _value(_single(root, tag, _ROOT), "Enable", tag)
            if value != 0.0:
                active.append((where, value, what))
    for tag, what in _OPERATING_FLAGS:
        value = _flag(root, tag, _ROOT)
        if value != 0.0:
            active.append((tag, value, what))
    if active:
        where, value, what = active[0]
        raise _fail(
            "Variante de .owtg no soportada: {where}={value:g} activa {what}, que este cálculo no representa; las "
            "curvas del fichero sin esa modificación describirían otra máquina.",
            where=where, value=value, what=what,
        )


def load_owtg(path: str) -> TurbineCurveTable:
    """Read a ``.owtg`` file of the supported variant (see the module docstring).

    Raises `OwtgFormatError` naming the offending element otherwise.
    """
    if not path or not os.path.isfile(path):
        raise _fail("No existe el fichero .owtg: {path!r}.", path=path)
    name_of_file = os.path.basename(path)
    try:
        root = _xml_parse(path).getroot()
    except Exception as exc:
        raise _fail("No se pudo leer el XML de {file}: {error}", file=name_of_file, error=exc) from exc

    if str(root.tag) != _ROOT:
        if root.findall("PerformanceTable"):
            raise _fail(
                "{file} tiene la raíz <{root}> y tablas <PerformanceTable>: parece un .wtg, que se lee con su propio "
                "lector.",
                file=name_of_file, root=root.tag,
            )
        raise _fail(
            "Variante de .owtg no soportada: la raíz de {file} es <{root}> y se esperaba <{expected}>.",
            file=name_of_file, root=root.tag, expected=_ROOT,
        )

    notes: List[str] = []
    _check_flags(root)

    names = root.findall("Name")
    name = (_single(root, "Name", _ROOT).text or "").strip() if names else ""
    if not name:
        name = os.path.splitext(name_of_file)[0]
        notes.append(log_text("El fichero no trae Name; se usa el nombre del fichero."))
    hub_height = _value(root, "HubHeight", _ROOT)
    diameter = _value(root, "RotorDiameter", _ROOT)
    cut_in = _value(root, "LowCutIn", _ROOT)
    cut_out = _value(root, "HighCutOut", _ROOT)
    design_density = _value(root, "DesignAirDensity", _ROOT)
    capacity = _value(root, "CapacityKW", _ROOT, required=False)
    peak = _value(root, "PeakOutputKW", _ROOT, required=False)

    tables_where = f"{_ROOT}/Power_Tables"
    power_tables = _single(root, "Power_Tables", _ROOT)
    declared = _count(power_tables, "Count", tables_where)
    for child in power_tables:
        if child.tag != "Count" and not _POWER_TABLE.fullmatch(str(child.tag)):
            raise _unexpected(child, tables_where)
    found = sorted(int(m.group(1)) for m in (_POWER_TABLE.fullmatch(str(c.tag)) for c in power_tables) if m)
    if declared > 1 or len(found) > 1:
        raise _fail(
            "Variante de .owtg no soportada: {where} declara Count={count} y contiene {n} tablas de potencia; solo se "
            "admite una. Varias tablas hacen depender la curva de la turbulencia, que este cálculo no representa.",
            where=tables_where, count=declared, n=len(found),
        )
    if declared != 1 or found != [0]:
        raise _fail(
            "Variante de .owtg no soportada: {where} declara Count={count} y contiene las tablas {indices}; se espera "
            "una sola, <Power_Table0>.",
            where=tables_where, count=declared, indices=_listing(found),
        )
    power_where = f"{tables_where}/Power_Table0"
    power_node = _single(power_tables, "Power_Table0", tables_where)
    speeds, densities, power = _read_table(power_node, power_where)
    thrust_speeds, thrust_densities, ct = _read_table(_single(root, "Thrust_Table", _ROOT), f"{_ROOT}/Thrust_Table")
    for label, a, b, tolerance in ((log_text("velocidades"), speeds, thrust_speeds, _SPEED_TOLERANCE_MS),
                                   (log_text("densidades"), densities, thrust_densities, _DENSITY_TOLERANCE)):
        if not _same(a, b, tolerance):
            raise _fail(
                "Variante de .owtg no soportada: las {label} de la tabla de empuje ({n_thrust} valores) no coinciden "
                "con las de la tabla de potencia ({n_power} valores); no se interpola entre mallas distintas.",
                label=label, n_thrust=len(b), n_power=len(a),
            )

    # Without speeds or densities there is no maximum: the shared validation rejects the table below.
    max_kw = max((value for row in power for value in row), default=0.0)
    rated = capacity if capacity is not None else peak
    rated_tag = "CapacityKW" if capacity is not None else "PeakOutputKW"
    if capacity is not None and peak is not None and abs(capacity - peak) > _RATED_TOLERANCE_KW:
        notes.append(log_text(
            "El fichero se contradice: declara CapacityKW={capacity:g} kW y PeakOutputKW={peak:g} kW. Se toma "
            "CapacityKW como potencia nominal.",
            capacity=capacity, peak=peak,
        ))
    if rated is None:
        if max_kw > _MAX_PLAUSIBLE_KW:
            raise _fail(
                "Variante de .owtg no soportada: la tabla de potencia llega a {max:g} y el fichero no declara CapacityKW "
                "ni PeakOutputKW con los que contrastarla. Supera los {ceiling:g} kW de la mayor turbina plausible: "
                "la tabla parece estar en W y no en kW.",
                max=max_kw, ceiling=_MAX_PLAUSIBLE_KW,
            )
        notes.append(log_text(
            "El fichero no declara potencia nominal (CapacityKW ni PeakOutputKW); se toma el máximo de la tabla, "
            "{max:g} kW.",
            max=max_kw,
        ))
    elif rated > 0.0 and max_kw > _RATED_MARGIN * rated:
        raise _fail(
            "Variante de .owtg no soportada: la tabla de potencia llega a {max:g}, más de un {margin:g} % por encima "
            "de la potencia nominal declarada ({tag}={rated:g} kW). Revisa las unidades de la tabla.",
            max=max_kw, margin=round((_RATED_MARGIN - 1.0) * 100.0), tag=rated_tag, rated=rated,
        )
    elif rated > 0.0 and max_kw < _LOW_OUTPUT_FRACTION * rated:
        notes.append(log_text(
            "La tabla de potencia llega a {max:g} kW, menos de la mitad de los {rated:g} kW nominales declarados.",
            max=max_kw, rated=rated,
        ))

    notes.append(log_text(
        "Densidad por defecto: la densidad de diseño del fichero (DesignAirDensity, {rho:g} kg/m³).", rho=design_density,
    ))
    iec = _flag(root, "IEC_adjustment", _ROOT)
    if iec not in (0.0, 1.0):
        raise _fail("Variante de .owtg no soportada: IEC_adjustment={value:g}; solo se admiten 0 y 1.", value=iec)
    if iec == 1.0:
        notes.append(log_text(
            "El fichero declara IEC_adjustment; se usan directamente sus curvas tabuladas por densidad, sin aplicar "
            "además la corrección IEC."
        ))
    ti_range = [power_node.find(tag) for tag in ("TI_min", "TI_max")]
    if all(node is not None and str(node.get("value") or "").strip() for node in ti_range):
        notes.append(log_text(
            "La tabla de potencia declara validez para una turbulencia entre {low} % y {high} %; no se comprueba.",
            low=ti_range[0].get("value").strip(), high=ti_range[1].get("value").strip(),
        ))

    try:
        table = TurbineCurveTable(
            name=name,
            diameter_m=diameter,
            hub_height_m=hub_height,
            wind_speeds_ms=tuple(speeds),
            air_densities=tuple(densities),
            power_kw=tuple(tuple(row) for row in power),
            ct=tuple(tuple(row) for row in ct),
            default_air_density=design_density,
            rated_power_kw=rated,
            cut_in_ms=cut_in,
            cut_out_ms=cut_out,
            source_format="owtg",
            source_path=os.path.abspath(path),
            notes=tuple(notes),
        )
        return table.with_operating_band_enforced()
    except OwtgFormatError:
        raise
    except CurveTableError as exc:
        # One contract: anything wrong with a .owtg is reported as a .owtg problem
        # that names the file, even when the shared validation caught it.
        raise _fail("Variante de .owtg no soportada en {file}: {error}", file=name_of_file, error=exc) from exc
