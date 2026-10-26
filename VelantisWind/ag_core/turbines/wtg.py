# -*- coding: utf-8 -*-
"""Reader for WAsP turbine files (``.wtg``) into a `TurbineCurveTable`.

A thin adapter that follows the contract of ``density_curve.py``: it produces a
`TurbineCurveTable`, validates strictly and never resamples. PyWake's own
``WindTurbines.from_WAsP_wtg`` is not used: it loads the tables as operating
modes, ignores their air density and takes the last Ct as the idle Ct.

Supported variant
-----------------
Identity is decided by the fields, read at their known relative paths, not by
the root tag or ``FormatVersion`` (those only improve the messages and the
notes):

* ``@RotorDiameter`` of the root, finite and positive;
* ``SuggestedHeights/Height``: one height, or the one chosen explicitly among
  several (``hub_height_m``);
* one or more ``PerformanceTable``, each with a finite, positive and distinct
  ``@AirDensity``, one ``StartStopStrategy`` and one ``DataTable`` of at least
  two ``DataPoint``;
* every ``DataPoint`` with numeric and finite ``@WindSpeed`` (increasing, not
  negative), ``@PowerOutput`` in W (not negative) and ``@ThrustCoEfficient``;
* the same wind-speed grid and the same band in every table, without
  hysteresis: ``LowSpeedCutOut`` equal to ``LowSpeedCutIn`` (the cut-in) and
  ``HighSpeedCutIn`` equal to ``HighSpeedCutOut`` (the cut-out).

Policies:

* the density of the first table is the default one (a convention observed in
  the files, not a specification), taken before sorting the tables;
* repeated densities are ambiguous (most probably operating modes, but the file
  does not say how many complete sets it holds) and are rejected, as are tables
  whose comments name different modes;
* the declared band wins over the tabulated values; outside it power and Ct are
  zero, so ``StationaryThrustCoEfficient`` is not used;
* there is no rated power in the format, so an implausible implied power
  coefficient is reported as a note (power, diameter or density suspicious),
  never corrected.

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

# Bundled, pure-Python safe XML parser. No additional pip installation needed.
from ..._vendor.defusedxml.ElementTree import parse as _xml_parse

__all__ = ["WtgFormatError", "WTG_EXTENSIONS", "is_wtg_path", "load_wtg"]

WTG_EXTENSIONS = (".wtg",)

# Tolerances and thresholds fixed here, not left to each comparison.
_SPEED_TOLERANCE_MS = 1e-6     # same wind speed in two tables, same band edge
_DENSITY_TOLERANCE = 1e-6      # two tables at the same density
_CP_PLAUSIBLE = (0.2, 0.593)   # implied power coefficient: below, or above Betz, is suspicious

_UNUSED_TABLE_ATTRIBUTES = ("MaximumNoiseLevel", "BladePitchAngle", "DataSource", "ReleaseDate", "ReferenceURI")
# The mode a table declares in its comments, e.g. "Noise Mode 0".
# Words that go inside other messages as data: a template of their own, so they can be translated.
_ROOT = log_text("la raíz")
_MODE = re.compile(r"(?:\w+\s+)?\b(?:mode|modo)\b\s*[-:#]?\s*[\w.-]+", re.IGNORECASE)


class WtgFormatError(CurveTableError):
    """A ``.wtg`` file that does not match the supported variant."""


def is_wtg_path(path: str) -> bool:
    return str(path or "").lower().endswith(WTG_EXTENSIONS)


def _fail(template: str, **data) -> WtgFormatError:
    return _error(WtgFormatError, template, **data)


def _number(node, attribute: str, where: str) -> float:
    raw = node.get(attribute)
    if raw is None or not str(raw).strip():
        raise _fail("Variante de .wtg no soportada: falta el atributo {attribute} en {where}.", attribute=attribute, where=where)
    try:
        value = float(str(raw).strip())
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise _fail(
            "Variante de .wtg no soportada: {where}/@{attribute} no es un número finito: {raw!r}.",
            where=where, attribute=attribute, raw=raw,
        )
    return value


def _single(parent, tag: str, where: str):
    found = parent.findall(tag)
    if not found:
        raise _fail("Variante de .wtg no soportada: falta el elemento <{tag}> en {where}.", tag=tag, where=where)
    if len(found) > 1:
        raise _fail(
            "Variante de .wtg no soportada: {where} tiene {n} elementos <{tag}> donde se espera uno.",
            where=where, n=len(found), tag=tag,
        )
    return found[0]


def _hub_height(root, chosen: Optional[float]) -> float:
    heights_node = _single(root, "SuggestedHeights", _ROOT)
    heights = []
    for i, node in enumerate(heights_node.findall("Height"), start=1):
        text = (node.text or "").strip()
        try:
            value = float(text)
        except ValueError:
            value = math.nan
        if not math.isfinite(value) or value <= 0.0:
            raise _fail(
                "Variante de .wtg no soportada: SuggestedHeights/Height[{index}] no es una altura positiva: {text!r}.",
                index=i, text=text,
            )
        heights.append(value)
    if not heights:
        raise _fail("Variante de .wtg no soportada: SuggestedHeights no contiene ningún <Height>.")
    if chosen is not None:
        if not any(abs(float(chosen) - h) <= _SPEED_TOLERANCE_MS for h in heights):
            raise _fail(
                "La altura elegida ({chosen:g} m) no es una de las alturas sugeridas del fichero ({heights}).",
                chosen=float(chosen), heights=", ".join(f"{h:g} m" for h in heights),
            )
        return float(chosen)
    if len(heights) > 1:
        exc = _fail(
            "El fichero sugiere varias alturas de buje ({heights}): hay que elegir una explícitamente.",
            heights=", ".join(f"{h:g} m" for h in heights),
        )
        exc.suggested_heights = tuple(heights)
        raise exc
    return heights[0]


def _read_table(node, index: int) -> Dict[str, object]:
    where = f"PerformanceTable[{index}]"
    rho = _number(node, "AirDensity", where)
    if rho <= 0.0:
        raise _fail("Variante de .wtg no soportada: {where}/@AirDensity debe ser positiva: {value:g}.", where=where, value=rho)

    strategy = _single(node, "StartStopStrategy", where)
    band_where = f"{where}/StartStopStrategy"
    cut_in = _number(strategy, "LowSpeedCutIn", band_where)
    cut_out = _number(strategy, "HighSpeedCutOut", band_where)
    if cut_in < 0.0 or cut_out < 0.0 or not cut_in < cut_out:
        raise _fail(
            "Variante de .wtg no soportada: {where} declara LowSpeedCutIn={cut_in:g} y HighSpeedCutOut={cut_out:g}; "
            "deben ser no negativos y el primero menor que el segundo.",
            where=band_where, cut_in=cut_in, cut_out=cut_out,
        )
    for stop, start in (("LowSpeedCutOut", "LowSpeedCutIn"), ("HighSpeedCutIn", "HighSpeedCutOut")):
        if strategy.get(stop) is not None and abs(_number(strategy, stop, band_where) - _number(strategy, start, band_where)) > _SPEED_TOLERANCE_MS:
            raise _fail(
                "Variante de .wtg no soportada: {where} declara histéresis ({stop}={stop_value:g} frente a "
                "{start}={start_value:g}), que este cálculo no modela.",
                where=band_where, stop=stop, stop_value=_number(strategy, stop, band_where),
                start=start, start_value=_number(strategy, start, band_where),
            )

    points = _single(node, "DataTable", where).findall("DataPoint")
    if len(points) < 2:
        raise _fail(
            "Variante de .wtg no soportada: {where}/DataTable tiene {n} DataPoint; hacen falta al menos 2.",
            where=where, n=len(points),
        )
    ws: List[float] = []
    power_kw: List[float] = []
    ct: List[float] = []
    for j, point in enumerate(points, start=1):
        point_where = f"{where}/DataTable/DataPoint[{j}]"
        speed = _number(point, "WindSpeed", point_where)
        power = _number(point, "PowerOutput", point_where)
        thrust = _number(point, "ThrustCoEfficient", point_where)
        if speed < 0.0 or (ws and not speed > ws[-1]):
            raise _fail(
                "Variante de .wtg no soportada: {where}/@WindSpeed={value:g} no es mayor que la velocidad anterior "
                "ni positiva: las velocidades deben ser crecientes y no negativas.",
                where=point_where, value=speed,
            )
        if power < 0.0:
            raise _fail("Variante de .wtg no soportada: {where}/@PowerOutput es negativa: {value:g}.", where=point_where, value=power)
        ws.append(speed)
        power_kw.append(power / 1000.0)  # W -> kW
        ct.append(thrust)
    comments = node.find("Comments")
    return {
        "rho": rho, "ws": ws, "power_kw": power_kw, "ct": ct, "cut_in": cut_in, "cut_out": cut_out,
        "comment": (comments.text or "").strip() if comments is not None else "",
        "stationary_ct": node.get("StationaryThrustCoEfficient"),
        "unused": [name for name in _UNUSED_TABLE_ATTRIBUTES if node.get(name) is not None],
    }


def _max_implied_cp(ws: Sequence[float], power_kw: Sequence[float], rho: float, diameter: float) -> float:
    """Highest ``P / (0.5·ρ·A·v³)`` of one table, at positive wind speeds."""
    area = math.pi * (diameter / 2.0) ** 2
    available = [(p * 1000.0, 0.5 * rho * area * v ** 3) for v, p in zip(ws, power_kw)]
    return max((p / wind for p, wind in available if wind > 0.0), default=0.0)


def load_wtg(path: str, *, hub_height_m: Optional[float] = None) -> TurbineCurveTable:
    """Read a ``.wtg`` file of the supported variant (see the module docstring).

    ``hub_height_m`` chooses among several ``SuggestedHeights``. Raises
    `WtgFormatError` naming the offending element otherwise.
    """
    if not path or not os.path.isfile(path):
        raise _fail("No existe el fichero .wtg: {path!r}.", path=path)
    name_of_file = os.path.basename(path)
    try:
        root = _xml_parse(path, forbid_dtd=True, forbid_entities=True, forbid_external=True).getroot()
    except Exception as exc:
        raise _fail("No se pudo leer el XML de {file}: {error}", file=name_of_file, error=exc) from exc

    notes: List[str] = []
    if not root.findall("PerformanceTable"):
        if str(root.tag) == "TurbineType":
            raise _fail(
                "{file} no tiene los campos de un .wtg (<PerformanceTable>) y su raíz es <TurbineType>: parece un "
                ".owtg, que se lee con su propio lector.",
                file=name_of_file,
            )
        raise _fail(
            "Variante de .wtg no soportada: {file} no tiene ningún <PerformanceTable> (raíz <{root}>).",
            file=name_of_file, root=root.tag,
        )
    if str(root.tag) != "WindTurbineGenerator":
        notes.append(log_text(
            "La raíz del fichero es <{root}> y no <WindTurbineGenerator>; se lee porque tiene los campos de un .wtg.",
            root=root.tag,
        ))
    if root.get("FormatVersion") is not None:
        notes.append(log_text("FormatVersion del fichero: {version}.", version=root.get("FormatVersion")))

    diameter = _number(root, "RotorDiameter", _ROOT)
    if diameter <= 0.0:
        raise _fail("Variante de .wtg no soportada: @RotorDiameter debe ser positivo: {value:g}.", value=diameter)
    hub_height = _hub_height(root, hub_height_m)

    name = str(root.get("Description") or "").strip()
    if not name:
        name = os.path.splitext(name_of_file)[0]
        notes.append(log_text("El fichero no trae Description; se usa el nombre del fichero."))

    tables = [_read_table(node, i) for i, node in enumerate(root.findall("PerformanceTable"), start=1)]
    first_density = tables[0]["rho"]
    for i, a in enumerate(tables, start=1):
        for j, b in enumerate(tables[i:], start=i + 1):
            if abs(a["rho"] - b["rho"]) <= _DENSITY_TOLERANCE:
                raise _fail(
                    "Variante de .wtg no soportada: las tablas {i} y {j} tienen la misma densidad ({rho:g} kg/m³). "
                    "Es ambiguo qué curva usar: no se puede saber cuántos juegos completos de tablas contiene.",
                    i=i, j=j, rho=a["rho"],
                )
    declared = [{" ".join(m.split()) for m in _MODE.findall(t["comment"])} for t in tables]
    modes = sorted(set().union(*declared))
    without_mode = any(not d for d in declared)
    if len({mode.lower() for mode in modes}) > 1 or (modes and without_mode):
        raise _fail(
            "Variante de .wtg no soportada: los comentarios de las tablas nombran modos de operación distintos "
            "({modes}); solo se admite un modo.",
            modes=log_text("{modes} / sin modo", modes=" / ".join(modes)) if without_mode else " / ".join(modes),
        )
    reference = tables[0]
    for i, table in enumerate(tables[1:], start=2):
        if len(table["ws"]) != len(reference["ws"]) or any(
            abs(a - b) > _SPEED_TOLERANCE_MS for a, b in zip(table["ws"], reference["ws"])
        ):
            raise _fail(
                "Variante de .wtg no soportada: la tabla {index} ({rho:g} kg/m³) no tiene las mismas velocidades que la "
                "primera; no se interpola entre mallas distintas.",
                index=i, rho=table["rho"],
            )
        if abs(table["cut_in"] - reference["cut_in"]) > _SPEED_TOLERANCE_MS or abs(table["cut_out"] - reference["cut_out"]) > _SPEED_TOLERANCE_MS:
            raise _fail(
                "Variante de .wtg no soportada: la tabla {index} ({rho:g} kg/m³) declara la banda {cut_in:g}–{cut_out:g} m/s "
                "y la primera, {first_in:g}–{first_out:g} m/s; todas deben tener la misma.",
                index=i, rho=table["rho"], cut_in=table["cut_in"], cut_out=table["cut_out"],
                first_in=reference["cut_in"], first_out=reference["cut_out"],
            )

    if modes:
        notes.append(log_text("Todas las tablas declaran el mismo modo en sus comentarios: {mode}.", mode=modes[0]))
    notes.append(log_text(
        "Densidad por defecto: la de la primera tabla ({rho:g} kg/m³), por convención; el formato no declara una "
        "densidad de diseño.",
        rho=first_density,
    ))
    if any(t["stationary_ct"] is not None for t in tables):
        notes.append(log_text(
            "No se usa el StationaryThrustCoEfficient (Ct con la turbina parada): fuera de la banda el modelo impone "
            "Ct = 0, una aproximación que afecta a las estelas."
        ))
    outside = [
        t["rho"] for t in tables
        if any((v < t["cut_in"] or v > t["cut_out"]) and (p > 0.0 or c > 0.0) for v, p, c in zip(t["ws"], t["power_kw"], t["ct"]))
    ]
    if outside:
        notes.append(log_text(
            "Hay valores no nulos fuera de la banda declarada en {n} tabla(s); la banda manda y fuera de ella la "
            "potencia y el Ct son cero (un Ct fuera de banda puede ser el empuje con la turbina parada).",
            n=len(outside),
        ))
    for t in tables:
        cp = _max_implied_cp(t["ws"], t["power_kw"], t["rho"], diameter)
        if not _CP_PLAUSIBLE[0] <= cp <= _CP_PLAUSIBLE[1]:
            notes.append(log_text(
                "Cp implícito máximo de {cp:.3f} en la tabla de {rho:g} kg/m³, fuera de {low:g}–{high:g}: potencia, "
                "diámetro o densidad sospechosos. El formato no trae potencia nominal con la que contrastarlo.",
                cp=cp, rho=t["rho"], low=_CP_PLAUSIBLE[0], high=_CP_PLAUSIBLE[1],
            ))
    unused = sorted({name for t in tables for name in t["unused"]})
    if unused:
        notes.append(log_text("No se usan estos atributos de las tablas: {names}.", names=", ".join(unused)))

    tables.sort(key=lambda t: t["rho"])
    try:
        table = TurbineCurveTable(
            name=name,
            diameter_m=diameter,
            hub_height_m=hub_height,
            wind_speeds_ms=tuple(reference["ws"]),
            air_densities=tuple(t["rho"] for t in tables),
            power_kw=tuple(tuple(t["power_kw"][i] for t in tables) for i in range(len(reference["ws"]))),
            ct=tuple(tuple(t["ct"][i] for t in tables) for i in range(len(reference["ws"]))),
            default_air_density=first_density,
            cut_in_ms=reference["cut_in"],
            cut_out_ms=reference["cut_out"],
            source_format="wtg",
            source_path=os.path.abspath(path),
            notes=tuple(notes),
        )
        return table.with_operating_band_enforced()
    except WtgFormatError:
        raise
    except CurveTableError as exc:
        # One contract: anything wrong with a .wtg is reported as a .wtg problem
        # that names the file, even when the shared validation caught it.
        raise _fail("Variante de .wtg no soportada en {file}: {error}", file=name_of_file, error=exc) from exc
