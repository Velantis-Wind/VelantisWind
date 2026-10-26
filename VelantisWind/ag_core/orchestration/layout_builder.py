# -*- coding: utf-8 -*-
"""Layout construction helpers for the Energy/AEP module."""

from __future__ import annotations

import csv
import os
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

from ..log_text import log_error, log_text
from ..results.summary import build_names_by_type


def _read_fallback_turbines_csv(layout_csv: str) -> Tuple[List[float], List[float], List[int]]:
    """Read ``turbines.csv`` with columns x,y and optional model_id/type."""
    xs_tmp: List[float] = []
    ys_tmp: List[float] = []
    type_tmp: List[int] = []

    with open(layout_csv, newline="", encoding="utf-8") as handle:
        sniffer = csv.Sniffer()
        sample = handle.read(2048)
        handle.seek(0)
        try:
            has_header = sniffer.has_header(sample)
        except Exception:
            has_header = False
        reader = csv.reader(handle)
        ix = 0
        iy = 1
        it = None
        if has_header:
            header = next(reader, None) or []
            norm = [str(h).strip().lower() for h in header]
            ix = norm.index("x") if "x" in norm else (norm.index("easting") if "easting" in norm else 0)
            iy = norm.index("y") if "y" in norm else (norm.index("northing") if "northing" in norm else 1)
            if "model_id" in norm:
                it = norm.index("model_id")
            elif "type" in norm:
                it = norm.index("type")

        for row in reader:
            if len(row) < 2:
                continue
            try:
                x = float(row[ix])
                y = float(row[iy])
            except Exception:
                try:
                    x = float(row[0])
                    y = float(row[1])
                except Exception:  # nosec B112
                    continue
            xs_tmp.append(x)
            ys_tmp.append(y)
            if it is not None and it < len(row):
                try:
                    type_tmp.append(int(float(row[it])))
                except Exception:
                    type_tmp.append(0)
            else:
                type_tmp.append(0)

    return xs_tmp, ys_tmp, type_tmp


def build_layout_arrays(
    *,
    models: List[Dict[str, Any]],
    site: Any,
    wasp_dir: str,
    use_wrg: bool,
    wrg_paths: List[str],
    dtype: Any,
    read_xy_csv: Callable[[str], Tuple[List[float], List[float]]],
    bbox_from_site: Callable[[Any], Tuple[float, float, float, float]],
) -> Dict[str, Any]:
    """Build and clip turbine layout arrays for PyWake.

    Sources are tried in the same order as before:
    1. in-memory ``coords_xy`` per turbine model;
    2. per-model CSV paths;
    3. fallback ``turbines.csv`` beside the resource.
    """
    xs_all: List[float] = []
    ys_all: List[float] = []
    type_i_all: List[int] = []

    for index, model in enumerate(models):
        csv_path = (model.get("coords_csv") or "").strip()
        name = model.get("name") or log_text("Modelo {n}", n=index + 1)
        coords_xy = model.get("coords_xy")
        if coords_xy:
            try:
                xi = [float(point[0]) for point in coords_xy]
                yi = [float(point[1]) for point in coords_xy]
            except Exception as exc:
                raise log_error(RuntimeError, "coords_xy inválido para «{name}»: {error}", name=name, error=exc)
            if len(xi) != len(yi):
                raise log_error(RuntimeError, "coords_xy corrupto para «{name}» (longitudes distintas)", name=name)
            xs_all += xi
            ys_all += yi
            type_i_all += [index] * len(xi)
            continue

        if not csv_path:
            continue
        if not os.path.isfile(csv_path):
            raise log_error(RuntimeError, "CSV de coordenadas no válido para «{name}»: {path}", name=name, path=csv_path)
        xi, yi = read_xy_csv(csv_path)
        if len(xi) != len(yi):
            raise log_error(RuntimeError, "CSV de coordenadas corrupto para «{name}»: {path}", name=name, path=csv_path)
        xs_all += xi
        ys_all += yi
        type_i_all += [index] * len(xi)

    if not xs_all:
        base_layout_dir = ""
        if wasp_dir and os.path.isdir(wasp_dir):
            base_layout_dir = wasp_dir
        elif use_wrg and wrg_paths:
            try:
                base_layout_dir = os.path.dirname(os.path.abspath(wrg_paths[0]))
            except Exception:
                base_layout_dir = os.path.dirname(str(wrg_paths[0]))

        if not base_layout_dir:
            raise log_error(
                RuntimeError, "No se pudieron resolver las coordenadas del layout: faltan los CSV por modelo "
                "y no existe una carpeta base válida para buscar turbines.csv."
            )

        layout_csv = os.path.join(base_layout_dir, "turbines.csv")
        if not os.path.isfile(layout_csv):
            raise log_error(
                RuntimeError, "No se encuentra '{path}'. Selecciona los CSV de coordenadas por modelo en el diálogo "
                "o crea un turbines.csv con columnas x,y[,model_id].", path=layout_csv,
            )
        xs_all, ys_all, type_i_all = _read_fallback_turbines_csv(layout_csv)

    xs = np.asarray(xs_all, dtype=dtype)
    ys = np.asarray(ys_all, dtype=dtype)
    type_i = np.asarray(type_i_all, dtype=int)

    use_types = len(models) > 1
    x_min, x_max, y_min, y_max = bbox_from_site(site)
    inside_mask = (xs >= x_min) & (xs <= x_max) & (ys >= y_min) & (ys <= y_max)
    inside = np.where(inside_mask)[0]
    skipped = int((~inside_mask).sum())
    # Count excluded turbines by the input model index, before the filtering
    # removes their type information. Do not collapse all rows into model 0.
    # Same names as the rest of the result, so the breakdown matches the per-model tables.
    names = build_names_by_type(models)
    skipped_by_model: Dict[str, int] = {}
    for pos in np.flatnonzero(~inside_mask):
        model_index = int(type_i_all[pos]) if use_types else 0
        name = names.get(model_index, f"WT_{model_index}")
        skipped_by_model[name] = skipped_by_model.get(name, 0) + 1

    if inside.size == 0:
        raise log_error(
            RuntimeError, "Todas las turbinas del CSV están fuera del área del grid WAsP. "
            "Revisa unidades (m vs km) y reproyección."
        )

    xs = xs[inside]
    ys = ys[inside]
    type_i = type_i[inside] if use_types else None

    return {
        "xs": xs,
        "ys": ys,
        "type_i": type_i,
        "use_types": use_types,
        "skipped": skipped,
        "skipped_by_model": skipped_by_model,
    }
