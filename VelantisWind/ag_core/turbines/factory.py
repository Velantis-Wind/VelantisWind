# -*- coding: utf-8 -*-
"""Construcción robusta de turbinas PyWake.

Extraído desde ``ag_core.aep_compute`` para que el motor principal no mezcle
orquestación AEP con detalles de PowerCtFunction / WindTurbines. Mantiene
compatibilidad con varias versiones de PyWake y con los diccionarios que crea
la UI del plugin.
"""
from __future__ import annotations

import logging

import inspect
from inspect import signature
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..physics.common.compat import emit
from ..log_text import log_text
from ..turbine import _error

try:  # pragma: no cover - depende del entorno QGIS/PyWake del usuario
    from py_wake.wind_turbines import WindTurbine, WindTurbines
except Exception:  # pragma: no cover
    try:
        from py_wake.wind_turbines._wind_turbines import WindTurbine, WindTurbines
    except Exception:
        WindTurbine = None  # type: ignore
        WindTurbines = None  # type: ignore
try:  # pragma: no cover
    from py_wake.wind_turbines.power_ct_functions import PowerCtFunctionList
except Exception:  # pragma: no cover
    PowerCtFunctionList = None  # type: ignore


class _QgisLevels:
    Info: Any = None
    Warning: Any = None


Qgis = _QgisLevels()
_LOG: Optional[Callable[..., None]] = None


def configure_logging(log: Optional[Callable[..., None]] = None, *, warning_level: Any = None, info_level: Any = None) -> None:
    """Inyecta logger/QGIS levels desde ``aep_compute`` sin acoplar este módulo a QGIS."""
    global _LOG
    _LOG = log
    Qgis.Warning = warning_level
    Qgis.Info = info_level


def _log(msg: str, level: Any = None) -> None:
    emit(_LOG, msg, level)


def _dump_obj_signature(tag: str, obj: Any) -> None:
    try:
        mod = getattr(obj, "__module__", "?")
        name = obj.__class__.__name__ if not inspect.isclass(obj) else obj.__name__
        try:
            sig = str(inspect.signature(obj.__init__ if not inspect.isclass(obj) else obj))
        except Exception:
            sig = "n/d"
        _log(f"[{tag}] clase={name} | módulo={mod} | firma={sig}")
        _log(f"[{tag}] repr={repr(obj)}")
    except Exception as e:
        _log(log_text("[{tag}] No se pudo obtener firma/repr: {error}", tag=tag, error=e), Qgis.Warning)


def _pcf_list_items(pcf: Any) -> Optional[List[Any]]:
    """Return the functions stored by a PyWake PowerCtFunctionList.

    PyWake 2.6.x stores them in ``windTurbineFunction_lst``. Older builds and
    wrappers used other names, so keep a small compatibility table.
    """
    for attr in (
        "windTurbineFunction_lst",
        "powerCtFunction_lst",
        "powerCtFunctions",
        "funcs",
        "functions",
        "function_list",
        "pcfs",
    ):
        inner = getattr(pcf, attr, None)
        if inner is None:
            continue
        try:
            return list(inner)
        except Exception:
            try:
                return [inner]
            except Exception as _ignored_exc:
                logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 93, _ignored_exc)
                continue
    return None


def _pcf_selector_key(pcf: Any) -> Optional[str]:
    for attr in ("key", "input_key", "selector_key"):
        value = getattr(pcf, attr, None)
        if value is not None:
            return str(value)
    for attr in ("required_inputs", "input_keys"):
        value = getattr(pcf, attr, None)
        try:
            values = [str(v) for v in value]
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 107, _ignored_exc)
            continue
        if len(values) == 1:
            return values[0]
    return None


def is_pcf_list(pcf: Any) -> bool:
    try:
        cls = pcf.__class__.__name__.lower()
    except Exception:
        cls = ""
    if "powerctfunctionlist" in cls:
        return True
    return _pcf_list_items(pcf) is not None


def unwrap_pcf_list(pcf: Any) -> Any:
    items = _pcf_list_items(pcf)
    if items:
        return items[0]
    try:
        it = iter(pcf)
        return next(it)
    except Exception:
        return pcf


def extract_flat_pcf(obj: Any, type_index: Optional[int] = None) -> Any:
    """Return one physically complete Power/Ct function for one turbine type.

    Turbines created by the plugin are often represented as a one-type
    ``WindTurbines`` object. PyWake wraps their curve in
    ``PowerCtFunctionList('type', [curve])``. Some persisted/UI objects can also
    reference an already-combined ``WindTurbines``. In that case ``type_index``
    selects the physical branch before a new mixed set is built. Operational-
    mode lists (``mode``, ``my_mode``, etc.) are retained intact.
    """
    if isinstance(obj, dict):
        pcf = obj.get("powerCtFunction")
        if pcf is None:
            pcf = obj.get("pcf")
    else:
        pcf = getattr(obj, "powerCtFunction", None)
        if pcf is None:
            pcfs = getattr(obj, "powerCtFunctions", None)
            if pcfs:
                if len(pcfs) > 1:
                    _log(log_text("[WT] Varias powerCtFunctions internas; se usa la primera."), Qgis.Warning)
                pcf = pcfs[0]
    if pcf is None:
        raise _error(RuntimeError, "No se encontró una PowerCtFunction válida.")

    # Unwrap only the artificial one-type selector created by WindTurbines.
    # Preserve true multi-mode curves, which may also be PowerCtFunctionList.
    seen = set()
    while is_pcf_list(pcf) and id(pcf) not in seen:
        seen.add(id(pcf))
        items = _pcf_list_items(pcf)
        key = (_pcf_selector_key(pcf) or "").strip().lower()
        if not items:
            break
        if key in {"", "type", "type_i"}:
            if len(items) == 1:
                _log("[WT] Se elimina el envoltorio singleton PowerCtFunctionList('type').")
                pcf = items[0]
                continue
            if type_index is not None and 0 <= int(type_index) < len(items):
                _log(
                    f"[WT] Se extrae la rama type={int(type_index)} de un "
                    f"PowerCtFunctionList combinado ({len(items)} ramas)."
                )
                pcf = items[int(type_index)]
                type_index = None
                continue
        break

    if not hasattr(pcf, "__call__") and not hasattr(pcf, "power"):
        raise _error(RuntimeError, "La PowerCtFunction no es invocable tras normalizarla.")
    return pcf


def _explicit_geometry_value(m: Dict[str, Any], meta: Dict[str, Any],
                             keys: Tuple[str, ...], name: str) -> Optional[float]:
    for source in (meta, m):
        for key in keys:
            if key in source and source[key] is not None:
                try:
                    value = float(source[key])
                except (TypeError, ValueError, OverflowError):
                    raise _error(ValueError, "{name}: {key} no es numérico.", name=name, key=key) from None
                if not np.isfinite(value) or value <= 0:
                    raise _error(ValueError, "{name}: {key} debe ser finito y positivo.", name=name, key=key)
                return value
    return None


def _source_type_count(wt_obj: Any, pcf: Any) -> Optional[int]:
    try:
        count = int(np.asarray(getattr(wt_obj, "_hub_heights")).size)
        if count:
            return count
    except (TypeError, ValueError, AttributeError):
        pass
    items = _pcf_list_items(pcf) if is_pcf_list(pcf) else None
    key = (_pcf_selector_key(pcf) or "").strip().lower()
    if items and key in {"", "type", "type_i"}:
        return len(items)
    return None


def _geometry_value(m: Dict[str, Any], meta: Dict[str, Any], wt_obj: Any,
                    keys: Tuple[str, ...], accessor_name: str,
                    source_type_index: Optional[int], name: str) -> float:
    """Prefer explicit geometry, then the actual PyWake turbine; never invent it."""
    explicit_value = _explicit_geometry_value(m, meta, keys, name)
    if explicit_value is not None:
        return explicit_value

    accessor = getattr(wt_obj, accessor_name, None)
    if callable(accessor):
        type_count = _source_type_count(wt_obj, getattr(wt_obj, "powerCtFunction", None))
        if type_count is not None and type_count > 1 and source_type_index is None:
            raise _error(
                ValueError,
                "{name}: falta el índice de tipo para obtener {accessor} de una turbina combinada.",
                name=name, accessor=accessor_name,
            )
        index = 0 if source_type_index is None else source_type_index
        try:
            values = np.asarray(accessor(index), dtype=float).ravel()
            if values.size == 1 and np.isfinite(values[0]) and values[0] > 0:
                return float(values[0])
        except (TypeError, ValueError, IndexError, KeyError, OverflowError):
            pass

    raise _error(
        ValueError,
        "{name}: no se pudo determinar {accessor} real. "
        "Indica explícitamente diámetro y altura de buje o carga una turbina válida.",
        name=name, accessor=accessor_name,
    )


def ensure_wt_entry(m: Dict[str, Any]) -> Tuple[str, float, float, Any]:
    """Normaliza una entrada de turbina creada por UI/preset/CSV."""
    meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
    name = m.get("name") or meta.get("name") or "Custom WT"
    wt_obj = m.get("wt", m)
    try:
        source_index = int(m["source_type_index"]) if m.get("source_type_index") is not None else None
    except (TypeError, ValueError, OverflowError):
        source_index = None
    pcf = m.get("powerCtFunction")
    if pcf is None:
        pcf = m.get("pcf")
    if pcf is None:
        pcf = getattr(wt_obj, "powerCtFunction", None)
    source_index = _infer_source_type_index(
        wt_obj,
        pcf,
        diameter=_explicit_geometry_value(m, meta, ("diam", "diameter"), name),
        hub_height=_explicit_geometry_value(m, meta, ("hh", "hub_height"), name),
        requested_index=source_index,
    )
    diam = _geometry_value(m, meta, wt_obj, ("diam", "diameter"), "diameter", source_index, name)
    hh = _geometry_value(m, meta, wt_obj, ("hh", "hub_height"), "hub_height", source_index, name)
    pcf = extract_flat_pcf(wt_obj, type_index=source_index)
    _log(f"[WT] {name}: D={diam}, Hub={hh} -> PowerCtFunction OK")
    return name, diam, hh, pcf




def _csv_only(model: Dict[str, Any]) -> bool:
    return not model.get("coords_xy") and bool(str(model.get("coords_csv") or "").strip())


def _has_coords(model: Dict[str, Any]) -> bool:
    return bool(model.get("coords_xy")) or _csv_only(model)


def canonicalize_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return one model entry per physical turbine definition.

    The interactive map can expose several selected QGIS layers which belong
    to the same turbine row.  Those layers are spatial groups, not new PyWake
    turbine types.  Treating every selected layer as a type produces indices
    such as 217 for a park which may only contain two actual turbine models.

    ``source_row_index`` is the stable UI identity when available.  Normal
    dialog rows (without that field) remain independent entries.
    """
    source_models = list(models or [])
    wt_identity_count: Dict[int, int] = {}
    for model in source_models:
        wt_obj = model.get("wt")
        if wt_obj is not None:
            wt_identity_count[id(wt_obj)] = wt_identity_count.get(id(wt_obj), 0) + 1

    grouped: Dict[Tuple[str, int], Dict[str, Any]] = {}
    order: List[Tuple[str, int]] = []
    for entry_index, model in enumerate(source_models):
        try:
            row_index = int(model.get("source_row_index"))
            has_row_index = row_index >= 0
        except Exception:
            row_index = -1
            has_row_index = False
        if has_row_index:
            key = ("row", row_index)
        else:
            wt_obj = model.get("wt")
            if wt_obj is not None and wt_identity_count.get(id(wt_obj), 0) > 1:
                key = ("wt", id(wt_obj))
            else:
                key = ("entry", entry_index)

        if key not in grouped:
            clone = dict(model)
            clone["coords_xy"] = list(model.get("coords_xy") or [])
            clone["source_layer_ids"] = [str(model.get("source_layer_id") or "")] if model.get("source_layer_id") else []
            clone["source_layer_names"] = [str(model.get("source_layer_name") or "")] if model.get("source_layer_name") else []
            grouped[key] = clone
            order.append(key)
            continue

        target = grouped[key]
        # Grouping keeps coords_xy and one coords_csv: an entry whose turbines
        # come only from its CSV would lose them next to other coordinates.
        if (_csv_only(model) and _has_coords(target)) or (_csv_only(target) and _has_coords(model)):
            raise _error(
                RuntimeError,
                "No se pueden agrupar en un mismo tipo de turbina entradas cuyas coordenadas "
                "vienen solo de un CSV (se perderían turbinas): «{name}».",
                name=model.get('name') or target.get('name') or 'Custom WT',
            )
        target.setdefault("coords_xy", []).extend(list(model.get("coords_xy") or []))
        if model.get("source_layer_id"):
            target.setdefault("source_layer_ids", []).append(str(model.get("source_layer_id")))
        if model.get("source_layer_name"):
            target.setdefault("source_layer_names", []).append(str(model.get("source_layer_name")))
        # Keep the first physical turbine object/meta.  Fill only missing fields.
        for field in ("wt", "meta", "powerCtFunction", "pcf", "coords_csv"):
            if not target.get(field) and model.get(field):
                target[field] = model.get(field)

    result = [grouped[key] for key in order]
    if len(result) != len(source_models):
        _log(
            f"[WT] Se compactaron {len(source_models)} entradas de capa en "
            f"{len(result)} tipos físicos de turbina."
        )
    return result



def _infer_source_type_index(
    wt_obj: Any,
    pcf: Any,
    *,
    diameter: Optional[float],
    hub_height: Optional[float],
    requested_index: Optional[int],
) -> Optional[int]:
    """Resolve one branch of an already-combined turbine object.

    UI row/layer identifiers are not guaranteed to be valid PyWake type
    indices. Prefer a unique geometry match, then an explicitly valid source
    type. Never infer a source branch from its position in a new list.
    """
    type_count = _source_type_count(wt_obj, pcf)
    if type_count == 1:
        return 0

    items = _pcf_list_items(pcf) if is_pcf_list(pcf) else None
    key = (_pcf_selector_key(pcf) or "").strip().lower()
    if not items or key not in {"", "type", "type_i"} or len(items) <= 1:
        return requested_index

    n_items = len(items)
    if diameter is not None or hub_height is not None:
        try:
            types = np.arange(n_items, dtype=int)
            diameters = np.asarray(wt_obj.diameter(types), dtype=float).ravel()
            heights = np.asarray(wt_obj.hub_height(types), dtype=float).ravel()
            if diameters.size == n_items and heights.size == n_items:
                matches_mask = np.ones(n_items, dtype=bool)
                if diameter is not None:
                    matches_mask &= np.isclose(
                        diameters, float(diameter), rtol=0.0, atol=1e-6
                    )
                if hub_height is not None:
                    matches_mask &= np.isclose(
                        heights, float(hub_height), rtol=0.0, atol=1e-6
                    )
                matches = np.where(matches_mask)[0]
                if matches.size == 1:
                    inferred = int(matches[0])
                    _log(
                        f"[WT] Rama combinada inferida por geometría: type={inferred} "
                        f"(D={diameter}, HH={hub_height})."
                    )
                    return inferred
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 411, _ignored_exc)

    if requested_index is not None and 0 <= int(requested_index) < n_items:
        return int(requested_index)
    raise _error(
        RuntimeError,
        "No se pudo identificar la rama física de un WindTurbines ya combinado: "
        "índice_origen={index!r}, ramas={n}. "
        "Indica un índice de tipo válido o geometría que identifique una sola rama.",
        index=requested_index, n=n_items,
    )



def combine_wt(models: List[Dict[str, Any]]) -> Tuple[Any, bool]:
    """Build a PyWake turbine set with one flat curve per turbine type.

    PyWake exposes mixed turbine selection through the public ``type`` input.
    The source objects supplied by the UI may be one-type or already-combined
    ``WindTurbines`` objects. Their physical branches are normalized to one
    flat curve per type and combined with PyWake's native selector, without
    nested ``type`` lists.
    """
    if WindTurbines is None:
        raise _error(RuntimeError, "PyWake WindTurbines no está disponible en este entorno.")

    models = canonicalize_models(models)
    names: List[str] = []
    diams: List[float] = []
    hubs: List[float] = []
    pcfs: List[Any] = []
    for m in models:
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        name = m.get("name") or meta.get("name") or "Custom WT"
        pcf = m.get("powerCtFunction")
        if pcf is None:
            pcf = m.get("pcf")
        wt_obj = m.get("wt", m)
        try:
            source_type_index = int(m.get("source_type_index"))
            if source_type_index < 0:
                source_type_index = None
        except Exception:
            source_type_index = None

        raw_pcf = pcf
        if raw_pcf is None:
            raw_pcf = getattr(wt_obj, "powerCtFunction", None)
        resolved_type_index = _infer_source_type_index(
            wt_obj,
            raw_pcf,
            diameter=_explicit_geometry_value(m, meta, ("diam", "diameter"), name),
            hub_height=_explicit_geometry_value(m, meta, ("hh", "hub_height"), name),
            requested_index=source_type_index,
        )
        D = _geometry_value(
            m, meta, wt_obj, ("diam", "diameter"), "diameter", resolved_type_index, name
        )
        HH = _geometry_value(
            m, meta, wt_obj, ("hh", "hub_height"), "hub_height", resolved_type_index, name
        )
        if pcf is None:
            pcf = extract_flat_pcf(wt_obj, type_index=resolved_type_index)
        else:
            pcf = extract_flat_pcf({"powerCtFunction": pcf}, type_index=resolved_type_index)

        names.append(str(name))
        diams.append(float(D))
        hubs.append(float(HH))
        pcfs.append(pcf)

    n_types = len(pcfs)
    if n_types == 0:
        raise _error(RuntimeError, "No se proporcionaron modelos de turbina.")
    use_types = n_types > 1

    # Build the turbine set with PyWake's native multi-type implementation.
    #
    # Earlier wake-raster builds used a custom dispatcher. During ``flow_map``
    # PyWake may expose wind-speed arrays as very large broadcast views. The
    # custom dispatcher materialised a turbine-type array and output array with
    # that complete internal shape, which could request many GiB although the
    # final raster was modest. PyWake's own PowerCtFunctionList is designed for
    # this selector and works with its point chunking, so use the official path.
    wt_all = None
    native_items: List[Any] = []
    if WindTurbine is not None:
        try:
            native_items = [
                WindTurbine(
                    name=name,
                    diameter=diameter,
                    hub_height=hub_height,
                    powerCtFunction=pcf,
                )
                for name, diameter, hub_height, pcf in zip(names, diams, hubs, pcfs)
            ]
            if hasattr(WindTurbines, "from_WindTurbine_lst"):
                wt_all = WindTurbines.from_WindTurbine_lst(native_items)
            elif len(native_items) == 1:
                wt_all = native_items[0]
        except Exception as exc:
            _log(
                log_text(
                    "[WT] La fábrica nativa from_WindTurbine_lst falló; se prueba el constructor WindTurbines: {error}",
                    error=exc,
                ),
                Qgis.Warning,
            )

    if wt_all is None:
        params = signature(WindTurbines.__init__).parameters
        if "powerCtFunctions" in params:
            wt_all = WindTurbines(
                names=names,
                diameters=diams,
                hub_heights=hubs,
                powerCtFunctions=pcfs,
            )
        elif "power_ct_funcs" in params:
            wt_all = WindTurbines(
                names=names,
                diameters=diams,
                hub_heights=hubs,
                power_ct_funcs=pcfs,
            )
        elif not use_types:
            wt_all = WindTurbines(
                names=names,
                diameters=diams,
                hub_heights=hubs,
                powerCtFunction=pcfs[0],
            )
        else:
            raise _error(
                RuntimeError,
                "La versión instalada de PyWake no expone un constructor nativo "
                "compatible para parques con varios tipos de turbina."
            )

    if use_types:
        _log("[WT] Parque mixto creado con el selector nativo PowerCtFunctionList('type').")

    if use_types:
        test_types = np.arange(n_types, dtype=int)
        try:
            d_test = np.asarray(wt_all.diameter(test_types), dtype=float).ravel()
            h_test = np.asarray(wt_all.hub_height(test_types), dtype=float).ravel()
        except Exception as exc:
            raise _error(
                RuntimeError, "PyWake no pudo seleccionar diámetro/altura mediante el argumento 'type'."
            ) from exc
        if not (
            d_test.size == n_types
            and h_test.size == n_types
            and np.allclose(d_test, np.asarray(diams, dtype=float), rtol=0.0, atol=1e-7)
            and np.allclose(h_test, np.asarray(hubs, dtype=float), rtol=0.0, atol=1e-7)
        ):
            raise _error(RuntimeError, "El WindTurbines combinado no conserva el mapeo type→diámetro/altura.")

        # Force one CT evaluation per type. This detects nested singleton type
        # selectors before a long flow-map task is started.
        for type_index in range(n_types):
            try:
                ct_probe = np.asarray(
                    wt_all.ct(np.asarray([8.0], dtype=float), type=int(type_index)),
                    dtype=float,
                ).ravel()
            except Exception as exc:
                raise _error(
                    RuntimeError,
                    "La curva CT del modelo {n} no puede evaluarse como tipo independiente ({kind}: {error}).",
                    n=type_index + 1, kind=type(exc).__name__, error=exc,
                ) from exc
            if ct_probe.size == 0 or not np.all(np.isfinite(ct_probe)):
                raise _error(
                    RuntimeError, "La curva CT del modelo {n} devolvió valores no válidos.", n=type_index + 1
                )

    try:
        _log(f"[WT] n_tipos={n_types} | nombres={names}")
        _log(f"[WT] diametros={diams} | hub_heights={hubs}")
        _dump_obj_signature("WT.PowerCtFunction", wt_all.powerCtFunction)
        _log(f"WT combinado: {type(wt_all).__name__} | use_types={use_types}")
    except Exception:  # nosec B110
        pass

    return wt_all, use_types


# Aliases compatibles con el código histórico
_is_pcf_list = is_pcf_list
_unwrap_pcf_list = unwrap_pcf_list
_extract_flat_pcf = extract_flat_pcf
_ensure_wt_entry = ensure_wt_entry
_combine_wt = combine_wt

__all__ = [
    "configure_logging",
    "is_pcf_list",
    "unwrap_pcf_list",
    "extract_flat_pcf",
    "ensure_wt_entry",
    "canonicalize_models",
    "combine_wt",
    "_is_pcf_list",
    "_unwrap_pcf_list",
    "_extract_flat_pcf",
    "_ensure_wt_entry",
    "_combine_wt",
]
