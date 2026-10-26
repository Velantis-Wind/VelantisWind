# -*- coding: utf-8 -*-
"""
Utilidades para gestionar turbinas en PyWake (v2.6.7 comprobado):

- Presets de PyWake listos para usar (p.ej. V80, IEA37) con carga perezosa.
- Creación de turbinas personalizadas a partir de:
    * Listas manuales de velocidades y potencias (kW).
    * Ficheros TXT/CSV (potencias en kW), con columnas configurables.
- Estimación de curva de CT cuando no se dispone de ella.

Notas:
- Todas las potencias de entrada se esperan en kW y se convierten a W para PyWake.
- Las curvas se ordenan por velocidad y se conserva exactamente la forma de potencia suministrada,
  incluyendo high-wind derating / storm-control y paradas explícitas.
- Optional console diagnostics are disabled by default and can be enabled with VELANTISWIND_DEBUG=1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Callable, Dict, Optional, Tuple, TYPE_CHECKING, Any
from .curve_text import numbered_curve_rows
import math
import os

# PyWake se importa de forma perezosa dentro de las funciones que lo necesitan.
# Motivo: en algunos entornos Windows/QGIS, cargar PyWake al abrir el diálogo
# puede disparar DLLs compiladas de dependencias externas (p. ej. *_compute.pyd)
# y hacer que el diálogo de turbina no llegue a abrirse.
if TYPE_CHECKING:  # solo para tipado; no se ejecuta en QGIS
    from py_wake.wind_turbines import WindTurbines  # pragma: no cover
else:
    WindTurbines = Any  # type: ignore

__all__ = [
    "TxtSpec",
    "load_curves_from_txt",
    "build_wt_from_manual",
    "build_wt_from_txt",
    "build_wt_from_curve_table",
    "list_pywake_presets",
]

def _debug_print(message: str) -> None:
    """Optional console diagnostics enabled with VELANTISWIND_DEBUG=1."""
    try:
        if os.environ.get("VELANTISWIND_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(message)
    except Exception:  # nosec B110
        pass


# ---------------------------------------------------------------------
# Helpers numéricos
# ---------------------------------------------------------------------
def _parse_float(s: str) -> float:
    """Convierte cadenas con coma o punto decimal a float."""
    return float(s.strip().replace(",", "."))


def _preserve_power_curve(values: List[float]) -> List[float]:
    """Preserve the supplied OEM/user power-curve shape.

    Real turbines may intentionally reduce power at high wind speed (storm
    control / high-wind derating) before cut-out. Older Velantis versions used
    a cumulative maximum here, which silently flattened those valid decreases
    and biased AEP high. Only negative/non-finite values are sanitized; genuine
    decreases are retained.
    """
    out: List[float] = []
    for value in values:
        try:
            v = float(value)
        except Exception:
            v = 0.0
        if not math.isfinite(v) or v < 0.0:
            v = 0.0
        out.append(v)
    return out


# Umbral de admisión del Ct, no un techo físico. La teoría del disco actuador da
# Ct <= 1, pero en estado de estela turbulenta las tablas de fabricante recogen a
# veces valores algo mayores; muy por encima, el dato apunta a un error.
CT_MAX_PLAUSIBLE = 1.2


def _error(cls, template: str, **data: Any) -> Exception:
    """Excepción con el texto en español y, aparte, su plantilla y datos para traducirla al mostrarla."""
    exc = cls(template.format(**data))
    exc.template_item = (template, data)
    return exc


def _validated_ct(ws: float, value: Any) -> float:
    """Devuelve el Ct tal cual si es un número finito en [0, CT_MAX_PLAUSIBLE]; si no, falla nombrando el punto.

    Nunca lo recorta: que el dato tenga sentido es cosa de quien lo escribe, y
    lo útil es decírselo. Que un modelo de estela acote después el Ct es cosa
    del modelo, no del dato.
    """
    try:
        c = float(value)
    except (TypeError, ValueError, OverflowError):
        c = math.nan
    if math.isfinite(c) and 0.0 <= c <= CT_MAX_PLAUSIBLE:
        return c
    raise _error(
        ValueError,
        "Ct no válido a {ws} m/s: {value}. Cada Ct debe ser un número finito entre 0 y {ct_max}; "
        "{ct_max} no es un techo físico, sino el umbral de admisión a partir del cual hay que revisar el dato.",
        ws=ws, value=value, ct_max=CT_MAX_PLAUSIBLE,
    )


def _no_density_scale_models() -> List[Any]:
    """Additional PyWake models for a curve that must NOT be rescaled by density.

    PyWake's default ``additional_models`` include ``DensityScale(1.225)``, which
    *consumes* the ``Air_density`` input and rescales power and Ct linearly
    instead of letting the curve itself decide. That is wrong twice over here:

    * a density-indexed table already interpolates between real, measured curves,
      so a linear rescale on top would both double-count and bypass the table;
    * a 1-D curve supplied by the user is already stated at one density, and in a
      park that mixes both kinds PyWake hands ``Air_density`` to every turbine
      type that declares it, which would silently rescale those curves.

    Yaw projection is kept (same exponent as PyWake's default), since it is
    unrelated to density.
    """
    from py_wake.wind_turbines.power_ct_functions import SimpleYawModel
    return [SimpleYawModel()]


# Aviso de que el Ct de una turbina es estimado (ver `_estimate_ct`), para quien la crea y para su resultado.
CT_ESTIMATED_WARNING = (
    "El Ct de esta turbina es estimado: la curva no lo trae y se ha calculado con una heurística que no depende "
    "de la curva de potencia ni del rotor (0,8 hasta 8 m/s, bajando hasta 0,2 a 25 m/s, y 0 donde la potencia es 0). "
    "Las pérdidas por estela calculadas con él son aproximadas; si tienes el Ct del fabricante, inclúyelo."
)


def _estimate_ct(ws: List[float], power_w: List[float]) -> List[float]:
    """
    Heurística suave para CT si no se facilita:
    ~0.8 para bajas velocidades, decay lineal hacia ~0.2 a 25 m/s.
    CT = 0 donde la potencia es 0 (bajo el arranque, paradas): sin producción
    la turbina no genera estela.

    Es el último recurso para una curva que llega sin Ct (CSV sin columna de Ct,
    lista manual sin Ct), con tres límites conocidos:

    - No depende de la curva de potencia ni del rotor: da el mismo Ct a cualquier
      turbina, sea cual sea su potencia nominal, su diámetro o su velocidad
      nominal. Por encima de la nominal, donde el Ct real cae deprisa, puede
      sobrestimar mucho la estela.
    - Ct = 0 fuera de operación es una convención nuestra, la misma que impone la
      banda de operación al construir la turbina. La turbina genérica de PyWake
      usa en cambio el último Ct de la curva (``ct_idle = ct[-1]``), el empuje
      pequeño de la turbina parada, que aquí se desprecia.
    - El resultado no es un dato del fabricante, y quien lo usa tiene que
      saberlo: quien crea la turbina avisa con ``CT_ESTIMATED_WARNING``.
    """
    out: List[float] = []
    for w, p in zip(ws, power_w):
        if p <= 0.0:
            c = 0.0
        elif w <= 8.0:
            c = 0.8
        elif w >= 25.0:
            c = 0.2
        else:
            c = 0.8 - (0.6 * (w - 8.0) / (25.0 - 8.0))
        out.append(max(0.0, min(1.0, c)))
    return out


# ---------------------------------------------------------------------
# Entrada desde fichero TXT/CSV
# ---------------------------------------------------------------------
@dataclass
class TxtSpec:
    """
    Especificación de parsing para TXT/CSV.
    Índices de columna son 0-based.
    """
    ws_col: int
    power_col: int
    delimiter: str = "\t"
    skip_header: int = 1
    ct_col: Optional[int] = None  # si existe columna CT


def load_curves_from_txt(path: str, spec: TxtSpec) -> Tuple[List[float], List[float], List[float]]:
    """
    Carga curvas desde TXT/CSV.
    - Potencia en el fichero: kW -> se convierte a W internamente.
    - Delimitador espacio: uno o varios blancos (espacios o tabuladores);
      la sangría no crea columnas y no se interpretan campos entre comillas.
    - Las filas sin una velocidad numérica, finita y no negativa (vacías, cabeceras
      repetidas, ruido) se ignoran. Las demás son filas de datos: cada una se lee
      entera (velocidad, potencia y Ct) antes de incorporarla, y entra con sus tres
      valores o no entra. Una potencia que falta, no es numérica o no es finita hace
      fallar la lectura nombrando archivo, línea, columna y valor.
    - Sin columna de Ct configurada, el Ct se estima entero (`_estimate_ct`).
      Con columna, cada fila de datos trae el suyo, válido como en el constructor
      (número finito en [0, CT_MAX_PLAUSIBLE]), y nunca se recorta ni se rellena.
      Un Ct no válido, una celda vacía o una fila que no llega a la columna hacen
      fallar la lectura nombrando archivo, línea, columna y valor; una columna
      vacía entera, nombrando archivo y columna.

    Returns:
        (ws, power_W, ct) ordenados por velocidad, conservando la forma OEM de la potencia.
    """
    _debug_print(f"[Energy turbine] Reading curve file: {path}")
    _debug_print(f"[Energy turbine] delimiter='{spec.delimiter}' skip={spec.skip_header} ws_col={spec.ws_col} power_col={spec.power_col} ct_col={spec.ct_col}")

    rows: List[Tuple[float, float, Optional[float]]] = []
    empty_ct: Optional[Tuple[int, str]] = None  # línea y celda del primer Ct vacío
    file = os.path.basename(path)

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = numbered_curve_rows(f, spec.delimiter, spec.skip_header)
        for line, row in reader:
            if not row:
                continue
            # 1) Sin una velocidad válida, la fila no es de datos: línea con ruido -> ignorar.
            try:
                w = _parse_float(row[spec.ws_col])
            except Exception:  # nosec B112
                continue
            if not math.isfinite(w) or w < 0:
                continue
            # 2) La potencia y el Ct de una fila de datos se interpretan fuera de ese except: si están mal, se falla.
            if spec.power_col >= len(row):
                raise _error(
                    ValueError,
                    "Fila incompleta en {file}, línea {line}: tiene {n} columna(s) y no llega a la columna {column}, "
                    "la de la potencia, así que le falta el valor.",
                    file=file, line=line, n=len(row), column=spec.power_col,
                )
            try:
                p_kw = _parse_float(row[spec.power_col])
            except ValueError:
                p_kw = math.nan
            if not math.isfinite(p_kw):
                raise _error(
                    ValueError,
                    "Potencia no válida en {file}, línea {line}, columna {column}: {value!r}. Cada fila con velocidad "
                    "debe traer su potencia en kW como un número finito.",
                    file=file, line=line, column=spec.power_col, value=row[spec.power_col],
                )
            c: Optional[float] = None
            if spec.ct_col is not None:
                if spec.ct_col >= len(row):
                    raise _error(
                        ValueError,
                        "Fila incompleta en {file}, línea {line}: tiene {n} columna(s) y no llega a la columna {column}, "
                        "la del Ct, así que le falta el valor. Si el archivo trae Ct, cada fila de datos debe traerlo.",
                        file=file, line=line, n=len(row), column=spec.ct_col,
                    )
                cell = row[spec.ct_col]
                if cell.strip() == "":
                    if empty_ct is None:
                        empty_ct = (line, cell)
                else:
                    try:
                        c = _validated_ct(w, _parse_float(cell))
                    except ValueError:
                        raise _error(
                            ValueError,
                            "Ct no válido en {file}, línea {line}, columna {column}: {value!r}. Cada Ct debe ser un "
                            "número finito entre 0 y {ct_max}; {ct_max} no es un techo físico, sino el umbral de "
                            "admisión a partir del cual hay que revisar el dato.",
                            file=file, line=line, column=spec.ct_col, value=cell, ct_max=CT_MAX_PLAUSIBLE,
                        ) from None
            # 3) La fila entra entera.
            rows.append((w, max(0.0, p_kw) * 1000.0, c))  # kW -> W

    if not rows:
        raise _error(ValueError, "No se han leído datos válidos de {path}", path=path)
    if empty_ct is not None:
        if all(c is None for _, _, c in rows):
            raise _error(
                ValueError,
                "La columna {column} de {file}, la del Ct, está vacía en todas las filas. Si el archivo no trae Ct, "
                "no configures esa columna y el Ct se estimará.",
                column=spec.ct_col, file=file,
            )
        raise _error(
            ValueError,
            "Ct vacío en {file}, línea {line}, columna {column}: {value!r}, entre filas que sí lo traen. Un hueco "
            "no se rellena ni se estima: complétalo en el archivo.",
            file=file, line=empty_ct[0], column=spec.ct_col, value=empty_ct[1],
        )

    merged = sorted(rows, key=lambda t: t[0])
    ws_s, pw_s, ct_s = map(list, zip(*merged))
    pw_s = _preserve_power_curve(pw_s)
    ct_f = _estimate_ct(ws_s, pw_s) if spec.ct_col is None else ct_s

    _debug_print(f"[Energy turbine] points={len(ws_s)} ws[min,max]=({min(ws_s):.3f},{max(ws_s):.3f}) P[max]={max(pw_s):.1f} W")
    return list(ws_s), list(pw_s), list(ct_f)


# ---------------------------------------------------------------------
# Construcción de turbinas personalizadas (PyWake 2.6.7)
# ---------------------------------------------------------------------
def build_wt_from_manual(
    name: str,
    diameter_m: float,
    hub_height_m: float,
    ws: List[float],
    power_kw: List[float],
    ct: Optional[List[float]] = None,
    operating_band: Optional[Tuple[Optional[float], Optional[float]]] = None,
) -> WindTurbines:
    """
    Crea un WindTurbines (plural) desde listas manuales (PyWake 2.6.7).
    - `power_kw` -> se pasa a W para PowerCtTabular. Se conserva la forma de la
      potencia (bajadas a viento alto, paradas); solo se sanean negativos y no finitos.
    - `ct`, si se da, se valida punto a punto (número finito en [0, CT_MAX_PLAUSIBLE])
      y nunca se recorta; si no se da, se estima tras ordenar y sanear la potencia.
    - Banda de operación: una lista o un CSV no la declaran aparte, así que se
      infiere de los extremos tabulados. El cut-in es la primera velocidad (si es
      mayor que 0) y el cut-out, la última. Fuera de la banda, potencia y Ct valen 0,
      con un escalón justo fuera de cada extremo. No se intenta adivinar una banda
      interior: si la real cae dentro del rango tabulado, la curva tiene que traer
      sus ceros. Si ya trae ceros en los extremos, el resultado no cambia.
      Excepción: si la tabla llega a 100 m/s o más, no se fija cut-out (PyWake pone
      su propio nodo de reposo en 100 m/s) y por encima del último nodo se repite
      su valor.
    - La curva lleva la banda en `operating_band` (`low`, `high`), para la potencia
      media del bin (`turbines/bin_power.py`): la que se reciba o, si no, desde la
      primera velocidad tabulada (también 0) hasta el cut-out que se pasa a PyWake
      (`None` sin cut-out). No cambia la evaluación puntual.
    - Sin `DensityScale`: la curva no declara `Air_density` (ver `_no_density_scale_models`).
    """
    # Logs
    _debug_print(f"[Energy turbine] build_wt_from_manual('{name}', D={diameter_m}, HH={hub_height_m})")
    _debug_print(f"[Energy turbine] len(ws)={len(ws)} len(power_kw)={len(power_kw)} len(ct)={(len(ct) if ct else 'None')}")

    if len(ws) != len(power_kw) or len(ws) == 0:
        raise _error(ValueError, "Listas `ws` y `power_kw` deben tener la misma longitud y no estar vacías.")

    ws_f = [float(x) for x in ws]
    pw_w = [max(0.0, float(p)) * 1000.0 for p in power_kw]  # kW -> W

    if ct is None:
        ct_f = [0.0] * len(ws_f)  # se estima tras ordenar y sanear la potencia
    else:
        if len(ct) != len(ws):
            raise _error(ValueError, "Si aportas `ct`, su longitud debe coincidir con `ws`.")
        ct_f = [_validated_ct(w, c) for w, c in zip(ws_f, ct)]

    z = sorted(zip(ws_f, pw_w, ct_f), key=lambda t: t[0])
    ws_sorted, pw_sorted, ct_sorted = map(list, zip(*z))
    pw_sorted = _preserve_power_curve(pw_sorted)
    if ct is None:
        ct_sorted = _estimate_ct(ws_sorted, pw_sorted)

    # Import perezoso: solo se carga PyWake cuando el usuario pulsa Crear/usar turbina.
    try:
        from py_wake.wind_turbines import WindTurbine, WindTurbines
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
    except Exception as e:
        raise _error(
            RuntimeError,
            "No se pudo cargar PyWake para construir la turbina. "
            "Comprueba que py_wake está instalado en el Python de QGIS y que "
            "Windows no está bloqueando alguna DLL/.pyd de sus dependencias."
        ) from e

    # Sin ws_cutin/ws_cutout, PowerCtTabular extrapola en plano fuera del rango
    # tabulado (repite el valor del extremo) en vez de dar 0. Ver el docstring.
    # Con ws_cutout, PyWake añade además un nodo de reposo fijo en 100 m/s: si la
    # tabla llega hasta ahí, caería dentro de ella, así que entonces no se pasa.
    ws_cutin = float(ws_sorted[0]) if ws_sorted[0] > 0.0 else None
    ws_cutout = float(ws_sorted[-1]) if ws_sorted[-1] < 100.0 else None

    pct = PowerCtTabular(
        ws_sorted, pw_sorted, 'W', ct_sorted,
        ws_cutin=ws_cutin, ws_cutout=ws_cutout,
        additional_models=_no_density_scale_models(),
    )
    pct.operating_band = operating_band if operating_band is not None else (float(ws_sorted[0]), ws_cutout)
    wt = WindTurbine(
        name=str(name),
        diameter=float(diameter_m),
        hub_height=float(hub_height_m),
        powerCtFunction=pct,
    )
    WT = WindTurbines.from_WindTurbine_lst([wt])

    # Logs
    try:
        _debug_print(f"[Energy turbine] WT ready. names={WT.names()} D0={WT.diameter(0)} HH0={WT.hub_height(0)}")
    except Exception as e:
        _debug_print(f"[Energy turbine] WT ready without property preview: {type(WT)} err={e}")

    return WT


def build_wt_from_txt(
    path: str,
    spec: TxtSpec,
    name: str,
    diameter_m: float,
    hub_height_m: float,
) -> WindTurbines:
    """Lee curvas TXT/CSV y construye la turbina."""
    ws, power_W, ct = load_curves_from_txt(path, spec)
    power_kW = [p / 1000.0 for p in power_W]
    return build_wt_from_manual(name, diameter_m, hub_height_m, ws, power_kW, ct)


# Gap placed around the tabulated wind speeds when padding a density-indexed
# curve with idle values, and upper end of that padding. PyWake's N-D tabular
# raises outside its grid, so the grid must cover every wind speed a
# simulation may ask for.
_WS_PAD_EPS = 1e-6
_WS_PAD_MAX = 1000.0
_DENSITY_TABULAR_CLS = None


def _pad_curve_grid(
    ws: List[float],
    power_rows: List[List[float]],
    ct_rows: List[List[float]],
) -> Tuple[List[float], List[List[float]], List[List[float]]]:
    """Extend a tabulated curve with idle values (zeros) outside its wind-speed range.

    The table only covers part of the wind speeds a simulation evaluates, and
    PyWake's N-D tabular raises outside its grid instead of clamping, so the
    grid is padded with explicit zeros: the turbine is not producing there.
    """
    zeros = [0.0] * len(power_rows[0])
    ws_out = list(ws)
    power_out = [list(row) for row in power_rows]
    ct_out = [list(row) for row in ct_rows]

    if ws_out[0] > 0.0:
        front = [0.0, ws_out[0] - _WS_PAD_EPS] if ws_out[0] > 2.0 * _WS_PAD_EPS else [0.0]
        ws_out = front + ws_out
        power_out = [list(zeros) for _ in front] + power_out
        ct_out = [list(zeros) for _ in front] + ct_out

    tail = [ws_out[-1] + _WS_PAD_EPS]
    if tail[0] + _WS_PAD_EPS < _WS_PAD_MAX:
        tail.append(_WS_PAD_MAX)
    ws_out = ws_out + tail
    power_out = power_out + [list(zeros) for _ in tail]
    ct_out = ct_out + [list(zeros) for _ in tail]
    return ws_out, power_out, ct_out


def _density_tabular_class():
    """``PowerCtNDTabular`` whose air density never leaves its own table.

    In a park with several turbine types, PyWake evaluates the curve of every
    type with the inputs of every turbine and then keeps, for each turbine, the
    value of its own type (``WindTurbineFunctionList`` with ``run_only`` 0 or 1).
    A density that is valid for one type can then fall outside the table of
    another type, and ``PowerCtNDTabular`` raises there. Clamping to the table
    only changes those values, which PyWake discards: each turbine's own density
    has already been clamped to its own table, with a warning, by the density
    resolution (``turbines/density_resolution.py``), which is the only code that
    passes ``Air_density`` to a simulation. A direct call with a density outside
    the table is clamped as well, without a warning. Created on first use, so
    PyWake is still imported lazily.
    """
    global _DENSITY_TABULAR_CLS
    if _DENSITY_TABULAR_CLS is None:
        import numpy as np
        from autograd.tracer import getval
        from py_wake.wind_turbines.power_ct_functions import PowerCtNDTabular

        class DensityCurveTabular(PowerCtNDTabular):
            def _power_ct(self, ws, run_only, **kwargs):
                if kwargs.get("Air_density") is not None:
                    axis = self.input_keys.index("Air_density")
                    # Irregular PyWake axes include a sentinel beyond the last
                    # tabulated value; only V.shape[axis] nodes contain data.
                    grid = self.interp[0].x[axis][:self.interp[0].V.shape[axis]]
                    kwargs["Air_density"] = np.clip(kwargs["Air_density"], grid[0], grid[-1])
                # A speed outside the wind-speed axis (negative, beyond its last node, ±inf) is evaluated at its
                # end, and a NaN gives NaN, as PyWake's 1-D tabular curve does with the same data (np.interp; #63,
                # decision 1); PyWake's N-D table raises there. Inside the axis, the call of always.
                speeds = self.interp[0].x[0][:self.interp[0].V.shape[0]]
                v = np.real(np.asarray(getval(ws)))  # the values of a traced ws (autograd, at any order), too
                if not np.all((v >= speeds[0]) & (v <= speeds[-1])):
                    import autograd.numpy as anp  # the clip keeps a traced ws traced

                    nan = np.isnan(v)
                    out = super()._power_ct(anp.where(nan, speeds[0], anp.clip(ws, speeds[0], speeds[-1])), run_only,
                                            **kwargs)
                    return anp.where(nan, np.nan, out)
                return super()._power_ct(ws, run_only, **kwargs)

        _DENSITY_TABULAR_CLS = DensityCurveTabular
    return _DENSITY_TABULAR_CLS


def build_wt_from_curve_table(
    table: Any,
    *,
    name: Optional[str] = None,
    diameter_m: Optional[float] = None,
    hub_height_m: Optional[float] = None,
) -> WindTurbines:
    """Build a PyWake turbine from a `TurbineCurveTable` (power/Ct vs wind speed and density).

    The whole density family is handed to PyWake as a 2-D table, so the curve
    is not resolved here: at simulation time each turbine supplies its own
    ``Air_density`` and PyWake interpolates linearly, in one vectorised call,
    the curve that corresponds to it. Without ``Air_density`` the table's
    default density is used. Geometry may be overridden (another tower) without
    touching the curves.

    - The declared band is applied again (it is idempotent): this is the single
      door into PyWake for every reader.
    - Outside the tabulated wind speeds, power and Ct are 0 (`_pad_curve_grid`).
    - No ``DensityScale`` (see `_no_density_scale_models`): the density
      dependence is the table's.
    - A single-density family goes through the 1-D builder, with its rules.
    - The curve carries its operating band in ``operating_band``, for the bin
      mean (``turbines/bin_power.py``): the declared cut-in and cut-out and,
      where the table declares none, its tabulated range. The 1-D builder gets
      it too, since the band it would infer would include the edge zeros.
    """
    from .turbines.density_curve import TurbineCurveTable

    if not isinstance(table, TurbineCurveTable):
        raise _error(TypeError, "Se esperaba un TurbineCurveTable y se recibió {kind}.", kind=type(table).__name__)

    wt_name = str(name or table.name)
    diameter = float(diameter_m if diameter_m is not None else table.diameter_m)
    hub_height = float(hub_height_m if hub_height_m is not None else table.hub_height_m)
    band = (
        float(table.cut_in_ms if table.cut_in_ms is not None else table.wind_speeds_ms[0]),
        float(table.cut_out_ms if table.cut_out_ms is not None else table.wind_speeds_ms[-1]),
    )
    table = table.with_operating_band_enforced()

    if not table.is_density_dependent:
        ws, power_kw, ct = table.curve_at_density(table.air_densities[0])
        _debug_print(f"[Energy turbine] curve table '{wt_name}' has one density; using the 1-D builder.")
        return build_wt_from_manual(wt_name, diameter, hub_height, ws, power_kw, ct, operating_band=band)

    default_rho = table.default_air_density
    if default_rho is None:
        default_rho = table.air_densities[0]
    default_rho, default_clamped = table.clamp_density(default_rho)

    ws_padded, power_rows, ct_rows = _pad_curve_grid(
        [float(v) for v in table.wind_speeds_ms],
        [[float(v) * 1000.0 for v in row] for row in table.power_kw],  # kW -> W
        [[float(v) for v in row] for row in table.ct],
    )

    try:
        from py_wake.wind_turbines import WindTurbine, WindTurbines
        density_tabular = _density_tabular_class()
    except Exception as e:
        raise _error(
            RuntimeError,
            "No se pudo cargar PyWake para construir la turbina. "
            "Comprueba que py_wake está instalado en el Python de QGIS."
        ) from e

    pcf = density_tabular(
        ["ws", "Air_density"],
        [ws_padded, [float(v) for v in table.air_densities]],
        power_rows,
        "W",
        ct_rows,
        default_value_dict={"Air_density": float(default_rho)},
        additional_models=_no_density_scale_models(),
    )
    pcf.operating_band = band
    _debug_print(
        f"[Energy turbine] build_wt_from_curve_table('{wt_name}', D={diameter}, HH={hub_height}) "
        f"-> {len(ws_padded)} ws x {table.n_densities} rho, default Air_density={default_rho:.4f}"
        + (" (clamped to the table)" if default_clamped else "")
    )
    wt = WindTurbine(name=wt_name, diameter=diameter, hub_height=hub_height, powerCtFunction=pcf)
    return WindTurbines.from_WindTurbine_lst([wt])


# ---------------------------------------------------------------------
# Presets de PyWake
# ---------------------------------------------------------------------
def _preset_v80():
    """Horns Rev 1 V80."""
    from py_wake.examples.data.hornsrev1 import V80
    return V80()


def _preset_iea37():
    """Conjunto IEA37 3.4 MW."""
    from py_wake.examples.data.iea37 import IEA37_WindTurbines
    return IEA37_WindTurbines()


def list_pywake_presets() -> Dict[str, Callable[[], WindTurbines]]:
    """Devuelve un diccionario {etiqueta -> factory()} con presets disponibles."""
    presets: Dict[str, Callable[[], WindTurbines]] = {}
    try:
        presets["PyWake: V80 (Horns Rev 1)"] = _preset_v80  # type: ignore[assignment]
    except Exception:  # nosec B110
        pass
    try:
        presets["PyWake: IEA37 (3.4MW)"] = _preset_iea37  # type: ignore[assignment]
    except Exception:  # nosec B110
        pass
    return presets

