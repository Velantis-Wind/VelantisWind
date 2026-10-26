# -*- coding: utf-8 -*-
"""The wake raster with the configuration of the AEP: the same factory, the same physical inputs (#46 P4).

One flow map of PyWake, for one wind direction and speed, of the wind farm model the factory builds from a
validated ``WakeConfig`` (engine, deficit with its rotor average and ground model, superposition, turbulence and
blockage, as for the AEP; #75 rows 5.1-5.3), with the class check before simulating and what was executed read from
the built objects for the JSON (row 5.4). The resource, WRG or GRD, is loaded with the AEP's functions, with its TI
(the fixed TI or the TI rasters of a WRG, row 5.5), and the hub heights are checked as the AEP checks them; the own
TI of a GRD resource (``ti15ms``) is #49's and keeps the treatment of the previous raster, which the JSON declares. The air density, read from the dialog's controls, is decided as in the AEP: if it cannot be
established, the raster stops with the cause, it is not replaced (row 5.5 of the earlier inventory, «sustitución de densidad»).

The raster calculates in float64, as the AEP (in ``Numpy32`` the projected coordinates of the turbines would be
rounded). It holds ``PYWAKE_LOCK`` from loading the site to the terrain of the grid, and the AEP holds the same lock,
so they never calculate at the same time (row 5.6). There is no global state. The flow map with blockage is the one of
PyWake 2.6.18 for every engine and blockage model offered; the explicit «escenario recalculado sin bloqueo»
(``without_blockage``) is another product, labelled in the layer and in the JSON. The cancellation, the memory
retry and the grid budget are those of the previous raster.
"""
from __future__ import annotations

import inspect
import os
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from . import engine as _engine
from ..ag_core import edge_cases as _edge_cases
from ..ag_core.log_text import log_text
from ..ag_core.simulation.pywake_lock import PYWAKE_LOCK
from ..ag_core.wake_setup import factory as _factory
from ..ag_core.wake_setup import presets as _presets
from ..ag_core.wake_setup import readers as _readers
from ..ag_core.wake_setup import validation as _validation
from ..ag_core.wake_setup.config import WakeConfig
from ..ag_core.wake_setup.api import user_selection
from ..ag_core.wake_setup.instrumentation import ConvergenceRecorder
from ..ag_core.wake_setup.notices import adaptation_notes, convergence_warnings, persistent_warnings
from ..ag_core.turbines.bin_power import POINT
from ..version import plugin_version

__all__ = ["compute_wake_raster_config", "WITHOUT_BLOCKAGE_LABEL", "persistent_warnings", "convergence_warnings"]

WITHOUT_BLOCKAGE_LABEL = "escenario recalculado sin bloqueo; no representa el campo de la configuración del diálogo"


class RasterError(RuntimeError):
    """The raster could not be calculated: the cause, never a substitute."""


def _energy_site(*, wasp_dir: str, wrg_paths: Optional[List[str]], models, wrg_speedup_method: str,
                 wrg_direction_count: Optional[int], wrg_wd_interp: str, wrg_ti_paths: Optional[List[str]],
                 wrg_ti_heights_m, project_crs_authid: Optional[str], fixed_ti: Optional[float]):
    """The site and the record of its TI, loaded exactly as the AEP loads it (the same functions: for a WRG, its
    direction count, interpolation, Speedup and TI). The TI of a GRD keeps the treatment of the previous raster,
    which is #49's: a dataset without ``TI`` gets a uniform 0.10 in ``TI``, ``ti`` and ``ti15ms`` (also over its
    own ``ti15ms``), and the record says which of the three cases it was."""
    from ..ag_core import aep_compute as ac

    use_wrg, paths, ti_paths = ac._orchestration.normalize_resource_inputs(
        wasp_dir=wasp_dir, models=models, wrg_paths=wrg_paths, wrg_ti_paths=wrg_ti_paths, wrg_ti_path=None)
    site, ds, _used, fixed_used, _dir = ac._orchestration.load_energy_site(
        use_wrg=use_wrg, wasp_dir=wasp_dir, wrg_paths=paths, wrg_speedup_method=wrg_speedup_method,
        wrg_direction_count=wrg_direction_count, wrg_wd_interp=wrg_wd_interp, wrg_ti_paths=ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m, project_crs_authid=project_crs_authid, fixed_ti=fixed_ti, log=ac._log,
        warning_level=ac.Qgis.Warning, info_level=ac.Qgis.Info,
        resolve_wasp_dir_for_pywake=ac._resolve_wasp_dir_for_pywake, sanitize_dir_for_pywake=ac._sanitize_dir_for_pywake,
        load_site_with_filter=ac._load_site_with_filter, ensure_wd_dim=ac._ensure_wd_dim,
        rebuild_xrsite_if_needed=ac._rebuild_xrsite_if_needed, apply_ti_raster_to_site=ac._apply_ti_raster_to_site)
    if not use_wrg:
        ds = getattr(site, "ds", None)
        had_ti, had_ti15 = _has(ds, "TI"), _has(ds, "ti15ms")
        _engine._ensure_dataset_has_ti(site, ti_value=0.10)
        source = ("grd_dataset_TI" if had_ti else "grd_ti15ms_replaced_by_0.10" if had_ti15
                  else "grd_without_ti_fixed_0.10")
        note = "El ráster usa la variable TI del recurso GRD si la tiene; si no, una TI fija de 0,10."
        return site, "WASP", {"source": source, "note": note}
    ac._orchestration.ensure_ti_available(site=site, ds=ds, fixed_ti=fixed_used, log=ac._log,
                                          warning_level=ac.Qgis.Warning, apply_fixed_ti=ac._apply_fixed_ti)
    if fixed_used is not None:
        ac._apply_fixed_ti(site, float(fixed_used), prefer_var="TI")
    record = ({"source": "ti_rasters", "paths": list(ti_paths or [])} if ti_paths and fixed_used is None
              else {"source": "fixed", "value": float(fixed_used)})
    return site, "WRG", record


def _has(ds, name: str) -> bool:
    try:
        return ds is not None and name in ds
    except Exception:
        return False


def compute_wake_raster_config(
    models: List[Dict[str, Any]], *, wake_config: WakeConfig, wasp_dir: str = "",
    wrg_paths: Optional[List[str]] = None, wrg_speedup_method: str = "none", wrg_direction_count: Optional[int] = None,
    wrg_wd_interp: str = "nearest", wrg_ti_paths: Optional[List[str]] = None, wrg_ti_heights_m=None,
    fixed_ti: Optional[float] = None, project_crs_authid: Optional[str] = None, resolution_m: float = 300.0,
    ws_plot: float = 10.0, wd_target: Optional[float] = None, output_dir: str = "", crs_wkt: str = "",
    crs_authid: str = "", air_density: Optional[Dict[str, Any]] = None, without_blockage: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None, cancel_callback: Optional[Callable[[], bool]] = None,
    wake_provenance: Optional[Dict[str, Any]] = None, aep_comparison: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute and write one wake raster of ``wake_config`` (see the module docstring).

    Raises ``RasterError`` with the reasons when the configuration cannot be calculated (the rules of the AEP), and
    ``factory.ClassMismatch``/``ReaderError``/``FactoryError`` from the class check and the factory; nothing is
    replaced. ``without_blockage`` asks for the other product, the same configuration without blockage.
    ``wake_provenance``, the provenance of a predefined model, is checked against ``wake_config`` (``ValueError``) and
    recorded in the JSON, with the notes of the preset among the warnings. ``aep_comparison``, how the inputs compare
    with the last AEP of the project (#36), is recorded as given (``None`` when not compared).
    """
    wake_provenance = _presets.checked_provenance(wake_config, wake_provenance)  # its own copy, checked
    params = dict(locals())
    # All the PyWake work, from loading the site to the terrain of the grid, under the lock shared with the AEP (row 5.6).
    with PYWAKE_LOCK:
        return _compute(**params)


def _compute(*, models, wake_config, wasp_dir, wrg_paths, wrg_speedup_method, wrg_direction_count, wrg_wd_interp,
             wrg_ti_paths, wrg_ti_heights_m, fixed_ti, project_crs_authid, resolution_m, ws_plot, wd_target,
             output_dir, crs_wkt, crs_authid, air_density, without_blockage, progress_callback, cancel_callback,
             wake_provenance, aep_comparison):
    warning_items: List[Any] = []

    def warn(text: Any) -> None:
        warning_items.append(text)

    def progress(value: float) -> None:
        if progress_callback is not None:
            try:
                progress_callback(float(max(0.0, min(100.0, value))))
            except Exception:  # nosec B110
                pass

    def check_cancel() -> None:
        if cancel_callback is not None and bool(cancel_callback()):
            raise RuntimeError("Tarea de ráster de estelas cancelada.")

    config = wake_config
    if without_blockage:
        config = WakeConfig(**{**wake_config.__dict__, "blockage": None, "blockage_superposition": None})
    # The stages in their order: what fails with any layout; then, with the turbines simulated, the simulation and the
    # map. What only the map refuses, here, before loading the resource, unless the simulation may stop before it.
    issues = _validation.validate(config) or ([] if _validation.layout_issues(config) else _validation.map_issues(config))
    if issues:
        # The reasons stay templates: the message is translated whole when it is shown.
        raise RasterError(log_text("No se puede calcular el ráster con esta configuración: {reasons}",
                                   reasons=_validation.issues_log_text(issues)))
    progress(2.0)
    if _engine._canonicalize_models is not None:
        models = _engine._canonicalize_models(list(models or []))
    coords, type_i_all, labels, counts = _engine._collect_coordinates_types_and_labels(models)
    x_all, y_all = coords[:, 0].astype(float), coords[:, 1].astype(float)
    check_cancel()

    site, kind, ti_record = _energy_site(
        wasp_dir=wasp_dir, wrg_paths=wrg_paths, models=models, wrg_speedup_method=wrg_speedup_method,
        wrg_direction_count=wrg_direction_count, wrg_wd_interp=wrg_wd_interp, wrg_ti_paths=wrg_ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m, project_crs_authid=project_crs_authid, fixed_ti=fixed_ti)
    sx_min, sx_max, sy_min, sy_max = _engine._get_site_bounds(site)
    inside = (x_all >= sx_min) & (x_all <= sx_max) & (y_all >= sy_min) & (y_all <= sy_max)
    n_total, n_inside = len(x_all), int(inside.sum())
    if n_inside == 0:
        raise RasterError(log_text("Todas las turbinas están fuera del dominio del recurso ({kind}).", kind=kind))
    if n_inside < n_total:
        warn(log_text("Se omitieron {n_out} de {n_total} turbinas fuera del dominio del recurso.",
                      n_out=n_total - n_inside, n_total=n_total))
    x_t, y_t, type_t = x_all[inside], y_all[inside], type_i_all[inside]
    # What PyWake refuses only from a number of turbines, with the ones the raster simulates (decision 6.1 of #64).
    issues = _validation.layout_issues(config, len(x_t)) or _validation.map_issues(config, len(x_t))
    if issues:
        raise RasterError(log_text("No se puede calcular el ráster con esta configuración: {reasons}",
                                   reasons=_validation.issues_log_text(issues)))
    progress(18.0)
    check_cancel()

    if _engine._combine_wt is None:
        raise RasterError(log_text("La fábrica de turbinas no está disponible."))
    wt, use_types = _engine._combine_wt(models)
    from ..ag_core import aep_compute as ac
    ac._clip_hub_heights_to_site(wt, site)  # the vertical check of the AEP: a hub height outside the WRG is refused
    if len([c for c in counts if c]) > 1 and not use_types:
        raise RasterError(log_text("Se detectaron varios modelos de turbina, pero PyWake no activó la selección por tipo."))

    # The air density: the AEP's decision on the same positions (float64, as the AEP's layout since #45). If it
    # cannot be established, the raster stops: a map with another density would be another calculation.
    density = dict(air_density or {"mode": "off"})
    decision = _engine.resolve_air_density(
        site=site, wt=wt, xs=np.asarray(x_t, dtype=np.float64), ys=np.asarray(y_t, dtype=np.float64),
        type_i=type_t if use_types else None, mode=density.get("mode"),
        reference_density=density.get("reference_density_kg_m3"), reference_altitude_m=density.get("reference_altitude_m"))
    for message in decision.warnings:
        warn(message)

    ws_real = float(ws_plot)  # the speed asked for, also under 0.1 m/s: PyWake calculates it (#63, decision 7)
    if wd_target is None:
        dominant = _engine._pick_resource_dominant_wd(site, x_t, y_t)
        if dominant is None:
            raise RasterError(log_text("No se pudo identificar el sector dominante del recurso: indica una dirección."))
        wd_real, sector_energy, mode_label = float(dominant[0]), dominant[1], "sector dominante del recurso"
    else:
        wd_real, sector_energy, mode_label = float(wd_target) % 360.0, None, f"dirección solicitada {float(wd_target) % 360.0:.1f}°"

    expected = _factory.expected_classes(config)
    wfm = _factory.build_wind_farm_model(config, site, wt, ws_grid=np.asarray([ws_real]), power_bin_mode=POINT)
    _factory.check_classes(expected, wfm)
    _factory.check_ws_reference(config, wfm)
    executed = _readers.executed_config(wfm, config)
    hubs = ac._hub_heights_per_turbine(wt, type_t if use_types else None, len(x_t))
    # A predefined model adapted by the user says so first (decision 19 of the predefined models).
    identification = _presets.identification(wake_provenance, wake_config) if wake_provenance else None
    for text in (([identification] if wake_config.adaptations and identification else [])
                 + persistent_warnings(config, flow_map=True, hub_heights=hubs) + adaptation_notes(config)
                 + (_presets.notes(wake_provenance) if wake_provenance else [])):
        warn(text)
    progress(30.0)
    check_cancel()

    # The grid: the budget and the domain-anchored grid of the previous raster.
    res_m = float(resolution_m) if resolution_m and float(resolution_m) > 0 else 300.0
    xmin, xmax, ymin, ymax = float(x_t.min()), float(x_t.max()), float(y_t.min()), float(y_t.max())
    dx, dy = max((xmax - xmin) * 0.10, 1000.0), max((ymax - ymin) * 0.10, 1000.0)
    gx_min_req, gx_max_req = _engine._pad_to_step(xmin - dx, xmax + dx, res_m)
    gy_min_req, gy_max_req = _engine._pad_to_step(ymin - dy, ymax + dy, res_m)
    max_cells = int(np.clip(10_000_000 // max(n_inside, 1), 50_000, 200_000))
    if use_types:
        max_cells = min(max_cells, 120_000)
    env_cap = str(os.environ.get("VELANTISWIND_WAKE_MAX_CELLS", "")).strip()
    if env_cap:  # the override of the previous raster (docs/WAKE_RASTER_ARCHITECTURE.md)
        try:
            max_cells = int(np.clip(int(env_cap), 25_000, 2_000_000))
        except ValueError:
            warn(log_text("VELANTISWIND_WAKE_MAX_CELLS no es válido: {value}.", value=repr(env_cap)))
    grid_x, grid_y, gx0, gx1, gy0, gy1, rx, ry = _engine._build_domain_anchored_grid(
        sx_min, sx_max, sy_min, sy_max, gx_min_req, gx_max_req, gy_min_req, gy_max_req, res_m, res_m,
        max_cells=max_cells, max_span_m=60_000.0)
    # Always in float64, as the AEP: in single precision (``Numpy32``) projected coordinates are rounded (to 0.5 m
    # at northings above 4 194 304 m, #45) and the turbines would not stand where they do in the AEP.
    sim_kwargs: Dict[str, Any] = {"x": np.asarray(x_t, dtype=float), "y": np.asarray(y_t, dtype=float),
                                  "wd": np.asarray([wd_real], dtype=float), "ws": np.asarray([ws_real], dtype=float)}
    if decision.values is not None:
        sim_kwargs["Air_density"] = np.asarray(decision.values, dtype=float)
    if use_types:
        sim_kwargs["type"] = np.asarray(type_t, dtype=np.int32)
    progress(40.0)

    def after_tile(done: int, total: int) -> None:
        progress(40.0 + 34.0 * done / total)
        check_cancel()

    tiles = {"count": 0}

    def flow_map_call(sim):
        kwargs: Dict[str, Any] = {"wd": wd_real, "ws": ws_real}
        params = inspect.signature(sim.flow_map).parameters
        if "memory_GB" in params:
            kwargs["memory_GB"] = 0.08
        if "n_cpu" in params:
            kwargs["n_cpu"] = 1

        def counted(done, total):
            tiles["count"] = total
            after_tile(done, total)
        return _engine._tiled_flow_map(sim.flow_map, grid_x, grid_y, n_inside, after_tile=counted, **kwargs)

    def memory_pressure(exc: BaseException) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        return isinstance(exc, MemoryError) or any(
            t in text for t in ("unable to allocate", "out of memory", "arraymemoryerror", "cannot allocate memory"))

    t0 = time.perf_counter()
    # The convergence of the simulation is always recorded; that of the flow map only with WeightedSum, the one
    # iterative loop that runs inside it (the engines iterate in the simulation): the trace function of the recorder
    # makes every Python call slower, and the map has many.
    recorder, map_recorder = ConvergenceRecorder(), ConvergenceRecorder()
    traced_map = config.superposition.name == "WeightedSum"
    with recorder:
        sim = wfm(**sim_kwargs)
    t1 = time.perf_counter()
    with (map_recorder if traced_map else nullcontext()):
        try:
            flow_map = flow_map_call(sim)
        except Exception as exc:
            if not memory_pressure(exc):
                raise
            # As the previous raster: one retry with a smaller grid, said in a warning; the same model.
            retry_cells = max(25_000, min(int(grid_x.size * grid_y.size // 4), 60_000))
            grid_x, grid_y, gx0, gx1, gy0, gy1, rx, ry = _engine._build_domain_anchored_grid(
                sx_min, sx_max, sy_min, sy_max, gx_min_req, gx_max_req, gy_min_req, gy_max_req, res_m, res_m,
                max_cells=retry_cells, max_span_m=60_000.0)
            warn(log_text("PyWake detectó presión de memoria y repitió automáticamente el mapa con {cells} "
                          "celdas ({nx}×{ny}, {res_x}×{res_y} m).", cells=f"{grid_x.size * grid_y.size:,}",
                          nx=grid_x.size, ny=grid_y.size, res_x=f"{rx:.1f}", res_y=f"{ry:.1f}"))
            try:
                flow_map = flow_map_call(sim)
            except Exception as retry_exc:
                if memory_pressure(retry_exc):
                    raise RasterError(log_text(
                        "No se pudo crear el ráster ni siquiera después de reducir automáticamente la malla a "
                        "{cells} celdas. Reduce la extensión del parque o aumenta la resolución del mapa. "
                        "Detalle: {error}", cells=f"{grid_x.size * grid_y.size:,}",
                        error=f"{type(retry_exc).__name__}: {retry_exc}")) from retry_exc
                raise
    try:
        ti_used = np.asarray(sim["TI"].values, dtype=float).ravel().tolist()
    except Exception:
        ti_used = None
    t2 = time.perf_counter()
    for loop, records in map_recorder.records.items():
        recorder.records[loop].extend(records)
    convergence = recorder.summary()
    for text in convergence_warnings(convergence):
        warn(text)
    # WeightedSum weighs only while it iterates (count < max_iter, superposition_models.py:143): with its weighting
    # discarded by the arguments (the predicate of decision 9 of #63) it adds linearly, and the tiles do not change
    # the map.
    if (config.superposition.name == "WeightedSum" and tiles["count"] > 1
            and not _edge_cases.weighting_discarded(config.superposition.params)):
        warn(log_text("Con WeightedSum, PyWake calcula sus pesos con un máximo global de cada cálculo: el mapa, "
                      "calculado en {tiles} teselas, puede diferir del calculado de una vez (sensibilidad de PyWake, "
                      "no un error del complemento).", tiles=tiles["count"]))
    # The edge cases of the map (decisions 2, 7 and 8), protected: its warnings go to the package and the dialog.
    def map_diagnosis() -> Any:
        def own(name: str) -> Any:  # read-only copies: nothing the module does can reach the map
            return _edge_cases.read_only(np.array(flow_map[name].values, dtype=float))
        return _edge_cases.raster_diagnosis(own("WS_eff"), own("WS") if "WS" in flow_map else None)
    raster_edge = _edge_cases.guarded(warn, map_diagnosis)
    for text in _edge_cases.guarded(warn, _edge_cases.raster_warnings, raster_edge) or []:
        warn(text)
    progress(74.0)
    check_cancel()

    metadata = {
        "analysis_type": "wake_raster_screening", "plugin_version": plugin_version(),
        "created_utc": datetime.now(timezone.utc).isoformat(), "crs_authid": str(crs_authid or ""),
        "crs_wkt": str(crs_wkt or ""), "resource_kind": kind,
        "resource_inputs": list(wrg_paths or []) if wrg_paths else [str(wasp_dir or "")],
        "direction_mode": mode_label, "requested_wind_direction_deg": None if wd_target is None else float(wd_target),
        "sector_energy_proxy": None if sector_energy is None else float(sector_energy),
        # What the user selected (an accepted adaptation undone, decision 10) and what was calculated.
        "wake_config": {"selected": user_selection(wake_config).to_dict(), "effective": config.to_dict(),
                        "adaptations": wake_config.to_dict()["adaptations"],
                        "expected_classes": {p: (c.__name__ if c else None) for p, c in expected.items()},
                        "executed": executed,
                        **({"provenance": dict(wake_provenance), "identification": str(identification)}
                           if wake_provenance else {})},
        "product": WITHOUT_BLOCKAGE_LABEL if without_blockage else "configuración del diálogo al crear el ráster",
        "without_blockage": bool(without_blockage),
        "aep_comparison": None if aep_comparison is None else dict(aep_comparison),
        "ti": dict(ti_record, values_at_turbines=ti_used),
        "convergence": convergence,
        "air_density": decision.info,
        "pywake_precision": "float64",
        "turbines_total": int(n_total), "turbines_used": int(n_inside), "turbines_excluded": int(n_total - n_inside),
        "grid_cells": int(grid_x.size * grid_y.size), "grid_nx": int(grid_x.size), "grid_ny": int(grid_y.size),
        "flow_map_tiles": int(tiles["count"]), "requested_resolution_m": res_m,
        "effective_resolution_x_m": float(rx), "effective_resolution_y_m": float(ry),
        "calculation_extent": {"xmin": float(gx0), "xmax": float(gx1), "ymin": float(gy0), "ymax": float(gy1)},
        "timings_seconds": {"turbine_interaction": round(t1 - t0, 6), "flow_map": round(t2 - t1, 6)},
        "warnings": [str(w) for w in warning_items],
    }
    if raster_edge:  # only for a map with edge cases: an ordinary package has none of it
        metadata["edge_cases"] = raster_edge
    terrain = _engine._terrain_on_grid(site, grid_x, grid_y)
    result = _engine._create_single_wake_raster_file(flow_map, wd_real=wd_real, ws_real=ws_real,
                                                     output_dir=output_dir, crs_wkt=crs_wkt, metadata=metadata,
                                                     terrain_values=terrain)
    try:
        check_cancel()
    except Exception:
        # Cancelled once written: nothing of it is left (as the previous raster).
        rasters = [e.get("path") for e in (result.get("rasters") or []) if isinstance(e, dict)]
        for path in [result.get("path"), result.get("metadata_path")] + rasters:
            try:
                if path and os.path.isfile(str(path)):
                    os.remove(str(path))
                # With each raster, its .aux.xml (where GDAL keeps a CRS without WKT1, #54).
                if path and path in rasters and os.path.isfile(str(path) + ".aux.xml"):
                    os.remove(str(path) + ".aux.xml")
            except Exception:  # nosec B110
                pass
        raise
    # The exporter's own warnings (e.g. a field PyWake did not give) are kept: they are merged, never replaced (5.8).
    exporter = [w for w in (result.get("warnings") or []) if str(w) not in {str(x) for x in warning_items}]
    result.update({"mode": mode_label, "sector_energy": sector_energy, "resource_kind": kind,
                   "warnings": [str(w) for w in warning_items] + [str(w) for w in exporter],
                   "warning_items": [getattr(w, "template_item", (str(w), {})) for w in warning_items + exporter],
                   "turbines_total": int(n_total), "turbines_used": int(n_inside),
                   "turbines_excluded": int(n_total - n_inside), "product": metadata["product"]})
    progress(100.0)
    return result
