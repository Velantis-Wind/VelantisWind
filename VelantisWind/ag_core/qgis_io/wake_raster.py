# -*- coding: utf-8 -*-
"""Export PyWake flow maps as georeferenced QGIS raster-layer packages.

The worker-safe side writes a small set of GeoTIFFs for one flow case:
free-flow speed, effective speed, wake deficit, relative deficit and, when
available, terrain elevation. QGIS layer creation and styling remain on the
main thread.
"""
from __future__ import annotations

import logging

import json
import math
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from ..log_text import log_error, log_text


_FIELD_INFO: Dict[str, Dict[str, str]] = {
    "WS": {
        "slug": "free_ws",
        "label": "WS libre",
        "units": "m/s",
        "description": "Velocidad libre local WS [m/s]",
    },
    "WS_eff": {
        "slug": "ws_eff",
        "label": "WS efectiva",
        "units": "m/s",
        "description": "Velocidad efectiva WS_eff [m/s]",
    },
    "wake_deficit": {
        "slug": "wake_deficit",
        "label": "Déficit de estela",
        "units": "m/s",
        "description": "Déficit de velocidad por estelas [m/s]",
    },
    "wake_deficit_pct": {
        "slug": "wake_deficit_pct",
        "label": "Déficit de estela",
        "units": "%",
        "description": "Déficit relativo de velocidad por estelas [%]",
    },
    "Elevation": {
        "slug": "terrain_elevation",
        "label": "Elevación del recurso",
        "units": "m",
        "description": "Elevación del terreno [m]",
    },
}


def _extract_coord(obj: Any, name: str) -> np.ndarray:
    """Return a finite one-dimensional coordinate from an xarray-like object."""
    coord = None
    try:
        coord = obj.coords[name]
    except Exception:
        try:
            coord = getattr(obj, name)
        except Exception:
            coord = None
    if coord is None:
        raise log_error(RuntimeError, "El mapa de flujo no contiene la coordenada '{name}'.", name=name)
    try:
        values = np.asarray(getattr(coord, "values", coord), dtype=float).ravel()
    except Exception as exc:
        raise log_error(RuntimeError, "No se pudo leer la coordenada '{name}': {error}", name=name, error=exc) from exc
    if values.size < 2 or not np.all(np.isfinite(values)):
        raise log_error(RuntimeError, "La coordenada '{name}' no contiene una malla ráster válida.", name=name)
    return values


def _find_data_array(container: Any, candidates: Iterable[str]) -> Any:
    for key in candidates:
        try:
            return container[key]
        except Exception:
            try:
                return getattr(container, key)
            except Exception as _ignored_exc:
                logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 86, _ignored_exc)
    return None


def _extract_field_2d(flow_map: Any, candidates: Iterable[str], display_name: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract a PyWake field as a 2-D array ordered as ``(y, x)``."""
    data = _find_data_array(flow_map, candidates)
    if data is None:
        names: List[str] = []
        try:
            names = list(getattr(flow_map, "data_vars", {}).keys())
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 98, _ignored_exc)
        raise log_error(RuntimeError, "PyWake no devolvió el campo {field}. Variables disponibles: {names}.",
                        field=display_name, names=", ".join(map(str, names)) or log_text("desconocidas"))

    try:
        dims = list(getattr(data, "dims", ()))
        for dim in list(dims):
            if dim in ("x", "y"):
                continue
            size = int(getattr(data, "sizes", {}).get(dim, 1))
            data = data.isel({dim: 0}, drop=True) if size >= 1 else data
        if hasattr(data, "transpose"):
            data = data.transpose("y", "x")
        values = np.asarray(getattr(data, "values", data), dtype=np.float32)
    except Exception as exc:
        raise log_error(RuntimeError, "No se pudo convertir {field} a una matriz 2-D: {error}", field=display_name,
                        error=exc) from exc

    values = np.squeeze(values)
    if values.ndim != 2:
        raise log_error(RuntimeError, "{field} tiene una forma no compatible con ráster: {shape}.", field=display_name,
                        shape=repr(values.shape))

    x = _extract_coord(data, "x")
    y = _extract_coord(data, "y")
    if values.shape != (y.size, x.size):
        if values.shape == (x.size, y.size):
            values = values.T
        else:
            raise log_error(
                RuntimeError, "La forma de {field} no coincide con las coordenadas del grid: array={shape}, y={ny}, x={nx}.",
                field=display_name, shape=values.shape, ny=y.size, nx=x.size,
            )

    if x[0] > x[-1]:
        x = x[::-1].copy()
        values = values[:, ::-1]
    if y[0] > y[-1]:
        y = y[::-1].copy()
        values = values[::-1, :]
    return values, x, y


def _extract_ws_eff_2d(flow_map: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Backward-compatible helper retained for external imports."""
    return _extract_field_2d(flow_map, ("WS_eff", "WS_eff_xylk"), "WS_eff")


def _regular_step(values: np.ndarray, axis_name: str) -> float:
    diffs = np.diff(np.asarray(values, dtype=float))
    diffs = diffs[np.isfinite(diffs) & (np.abs(diffs) > 0)]
    if diffs.size == 0:
        raise log_error(RuntimeError, "No se pudo determinar la resolución del eje {axis}.", axis=axis_name)
    step = float(np.median(np.abs(diffs)))
    tolerance = max(step * 1e-5, 1e-7)
    if np.max(np.abs(np.abs(diffs) - step)) > tolerance:
        raise log_error(RuntimeError, "El eje {axis} del mapa de flujo no es regular.", axis=axis_name)
    return step


def _safe_name(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", str(text or "wake_raster")).strip("_.")
    return text or "wake_raster"


def output_directory_for_project(project_home: str = "") -> str:
    """Return a persistent output directory without reading QGIS objects."""
    root = str(project_home or "").strip()
    if root and os.path.isdir(root) and os.access(root, os.W_OK):
        root = os.path.join(root, "VelantisWind_outputs", "wake_rasters")
    else:
        root = os.path.join(tempfile.gettempdir(), "VelantisWind", "wake_rasters")
    os.makedirs(root, exist_ok=True)
    return root


def default_output_path(wd: float, ws: float, *, output_dir: str = "") -> str:
    root = str(output_dir or "").strip() or output_directory_for_project("")
    os.makedirs(root, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = _safe_name(f"wake_ws_eff_wd_{wd:.1f}_ws_{ws:.1f}_{stamp}.tif")
    return os.path.join(root, filename)


def _write_geotiff(
    path: str,
    values_yx: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    *,
    crs_wkt: str = "",
    nodata: float = -9999.0,
    description: str = "",
) -> Tuple[float, float]:
    try:
        from osgeo import gdal
    except Exception as exc:
        raise log_error(RuntimeError, "GDAL no está disponible en el Python de QGIS: {error}", error=exc) from exc

    try:
        from ...raster_io import write_float32_band
    except Exception:
        try:
            from raster_io import write_float32_band  # type: ignore
        except Exception as exc:
            raise log_error(RuntimeError, "No se pudo importar el escritor ráster seguro: {error}", error=exc) from exc

    dx = _regular_step(x, "X")
    dy = _regular_step(y, "Y")
    width = int(x.size)
    height = int(y.size)
    x_min_corner = float(np.min(x) - dx / 2.0)
    y_max_corner = float(np.max(y) + dy / 2.0)

    clean = np.asarray(values_yx, dtype=np.float32)
    finite_mask = np.isfinite(clean)
    if not np.all(finite_mask):
        clean = clean.copy()
        clean[~finite_mask] = np.float32(nodata)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        raise log_error(RuntimeError, "GDAL no dispone del driver GTiff.")
    ds = driver.Create(
        path,
        width,
        height,
        1,
        gdal.GDT_Float32,
        options=[
            "TILED=YES",
            "COMPRESS=LZW",
            "PREDICTOR=3",
            "NUM_THREADS=ALL_CPUS",
            "BIGTIFF=IF_SAFER",
        ],
    )
    if ds is None:
        raise log_error(RuntimeError, "GDAL no pudo crear el GeoTIFF: {path}", path=path)
    try:
        ds.SetGeoTransform((x_min_corner, dx, 0.0, y_max_corner, 0.0, -dy))
        if crs_wkt:
            ds.SetProjection(str(crs_wkt))
        band = ds.GetRasterBand(1)
        if description:
            band.SetDescription(str(description))
        write_float32_band(
            band,
            clean,
            gdal_module=gdal,
            flip_vertical=True,
            nodata=nodata,
        )
        band.FlushCache()
        ds.FlushCache()
    finally:
        ds = None

    finite = values_yx[np.isfinite(values_yx)]
    if finite.size == 0:  # written entirely as NoData
        return None, None
    return float(np.min(finite)), float(np.max(finite))


def _field_stats(values: np.ndarray) -> Dict[str, Any]:
    array = np.asarray(values)
    finite = array[np.isfinite(array)]
    if finite.size == 0:  # a layer without finite cells: no statistics, no style
        return {"min": None, "max": None, "mean": None, "p05": None, "p50": None, "p95": None,
                "percentile_sample_cells": 0, "percentiles_approximate": False, "valid_cells": 0}
    # Exact min/max/mean are retained. Percentiles only drive styling and audit
    # summaries, so a deterministic sample avoids repeatedly sorting very large
    # arrays without changing the physical raster values.
    max_percentile_sample = 120_000
    stride = max(1, int(math.ceil(finite.size / max_percentile_sample)))
    percentile_values = finite[::stride]
    percentiles = np.percentile(percentile_values, [5.0, 50.0, 95.0])
    return {
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite, dtype=np.float64)),
        "p05": float(percentiles[0]),
        "p50": float(percentiles[1]),
        "p95": float(percentiles[2]),
        "percentile_sample_cells": int(percentile_values.size),
        "percentiles_approximate": bool(stride > 1),
        "valid_cells": int(finite.size),
    }


def _apply_style(layer: Any, entry: Dict[str, Any]) -> None:
    if entry.get("valid_cells") == 0:  # a layer without finite cells has no style
        return
    variable = str(entry.get("variable") or "")
    min_value = float(entry.get("style_min", entry.get("min", 0.0)))
    max_value = float(entry.get("style_max", entry.get("max", 1.0)))
    if not (math.isfinite(min_value) and math.isfinite(max_value)):
        return
    if max_value <= min_value:
        max_value = min_value + 1e-6
    try:
        from qgis.PyQt import QtGui
        from qgis.core import (
            QgsColorRampShader,
            QgsRasterShader,
            QgsSingleBandGrayRenderer,
            QgsSingleBandPseudoColorRenderer,
        )
        try:
            from qgis.core import QgsHillshadeRenderer
        except Exception:  # pragma: no cover - depends on QGIS version/build
            QgsHillshadeRenderer = None

        provider = layer.dataProvider()
        if variable == "Elevation":
            renderer = None
            if QgsHillshadeRenderer is not None:
                try:
                    renderer = QgsHillshadeRenderer(provider, 1, 315.0, 45.0)
                    if hasattr(renderer, "setMultiDirectional"):
                        renderer.setMultiDirectional(True)
                except Exception:
                    renderer = None
            if renderer is None:
                renderer = QgsSingleBandGrayRenderer(provider, 1)
            layer.setRenderer(renderer)
            if hasattr(layer, "setOpacity"):
                layer.setOpacity(0.42)
            layer.triggerRepaint()
            return

        span = max_value - min_value
        shader_fn = QgsColorRampShader()
        shader_fn.setColorRampType(QgsColorRampShader.Interpolated)
        units = str(entry.get("units") or "")
        if variable in {"wake_deficit", "wake_deficit_pct"}:
            shader_fn.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(min_value, QtGui.QColor(255, 255, 255), f"{min_value:.2f} {units}"),
                QgsColorRampShader.ColorRampItem(min_value + 0.25 * span, QtGui.QColor(254, 224, 210), ""),
                QgsColorRampShader.ColorRampItem(min_value + 0.50 * span, QtGui.QColor(252, 146, 114), ""),
                QgsColorRampShader.ColorRampItem(min_value + 0.75 * span, QtGui.QColor(222, 45, 38), ""),
                QgsColorRampShader.ColorRampItem(max_value, QtGui.QColor(103, 0, 13), f"{max_value:.2f} {units}"),
            ])
        else:
            shader_fn.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(min_value, QtGui.QColor(180, 4, 38), f"{min_value:.2f} {units}"),
                QgsColorRampShader.ColorRampItem(min_value + 0.25 * span, QtGui.QColor(244, 109, 67), ""),
                QgsColorRampShader.ColorRampItem(min_value + 0.50 * span, QtGui.QColor(254, 224, 144), ""),
                QgsColorRampShader.ColorRampItem(min_value + 0.75 * span, QtGui.QColor(116, 173, 209), ""),
                QgsColorRampShader.ColorRampItem(max_value, QtGui.QColor(49, 54, 149), f"{max_value:.2f} {units}"),
            ])
        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader_fn)
        renderer = QgsSingleBandPseudoColorRenderer(provider, 1, raster_shader)
        if hasattr(renderer, "setClassificationMin"):
            renderer.setClassificationMin(min_value)
        if hasattr(renderer, "setClassificationMax"):
            renderer.setClassificationMax(max_value)
        layer.setRenderer(renderer)
        opacity = 0.72 if variable == "WS_eff" else 0.62
        if hasattr(layer, "setOpacity"):
            layer.setOpacity(opacity)
        elif hasattr(renderer, "setOpacity"):
            renderer.setOpacity(opacity)
        layer.triggerRepaint()
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 365, _ignored_exc)


def _layer_name(entry: Dict[str, Any], wd: float, ws: float, without_blockage: bool = False) -> str:
    variable = str(entry.get("variable") or "")
    info = _FIELD_INFO.get(variable, {})
    label = str(info.get("label") or variable)
    units = str(entry.get("units") or info.get("units") or "")
    if variable == "Elevation":
        return f"VelantisWind · {label} [{units}]"
    # The explicit scenario without blockage is another product: its name says so (#75, row 5.3), in the language.
    suffix = ""
    if without_blockage:
        try:
            from ...i18n import tr_text as tr
        except Exception:  # without the plugin's language layer, the source text
            def tr(text):
                return text
        suffix = " · " + tr("sin bloqueo (no es el campo del AEP)")
    return f"VelantisWind · {label} [{units}] · wd {wd:.1f}° · ref {ws:.1f} m/s{suffix}"


def _add_one_to_qgis(entry: Dict[str, Any], result: Dict[str, Any], subgroup: Any) -> Any:
    try:
        from qgis.core import QgsProject, QgsRasterLayer
    except Exception as exc:
        raise log_error(RuntimeError, "No se pudo importar la API ráster de QGIS: {error}", error=exc) from exc

    project = QgsProject.instance()
    path = str(entry.get("path") or "")
    wd = float(result.get("wd", 0.0))
    ws = float(result.get("ws", 0.0))
    layer = QgsRasterLayer(path, _layer_name(entry, wd, ws, bool(result.get("without_blockage"))), "gdal")
    if not layer.isValid():
        raise log_error(RuntimeError, "QGIS no pudo abrir el GeoTIFF generado: {path}", path=path)
    try:
        if (not layer.crs().isValid()) and project.crs().isValid():
            layer.setCrs(project.crs())
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 404, _ignored_exc)

    variable = str(entry.get("variable") or "")
    layer.setCustomProperty("velantiswind/layer_type", "wake_raster")
    layer.setCustomProperty("velantiswind/source_path", path)
    layer.setCustomProperty("velantiswind/variable", variable)
    layer.setCustomProperty("velantiswind/unit", str(entry.get("units") or ""))
    layer.setCustomProperty("velantiswind/wind_direction_deg", wd)
    layer.setCustomProperty("velantiswind/wind_speed_ms", ws)
    for key, value in dict(result or {}).items():
        # The variable and the unit are the layer's own (set above), not the package's (#75, row 5.9).
        if value is None or isinstance(value, (dict, list, tuple)) or key in ("variable", "units", "unit"):
            continue
        try:
            layer.setCustomProperty(f"velantiswind/{key}", value)
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 420, _ignored_exc)

    project.addMapLayer(layer, False)
    node = subgroup.insertLayer(0, layer)
    # Keep the comparison layers available without drawing every raster at once.
    # The effective field is shown over a subtle terrain hillshade by default.
    try:
        node.setItemVisibilityChecked(variable in {"WS_eff", "Elevation"})
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 429, _ignored_exc)
    _apply_style(layer, entry)
    return layer


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        return value.item()
    except Exception:
        return str(value)


def _write_metadata_sidecar(metadata_path: str, payload: Dict[str, Any]) -> str:
    tmp_path = metadata_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_json_safe(payload), f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, metadata_path)
    except Exception:
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 459, _ignored_exc)
        raise
    return metadata_path


def _derive_output_paths(
    wd: float,
    ws: float,
    *,
    output_path: Optional[str],
    output_dir: str,
    variables: Iterable[str],
) -> Tuple[Dict[str, str], str]:
    if output_path:
        eff_path = os.path.abspath(output_path)
        root = os.path.dirname(eff_path)
        stem = os.path.splitext(os.path.basename(eff_path))[0]
        if stem.endswith("_ws_eff"):
            prefix = stem[:-7]
        elif "ws_eff" in stem:
            prefix = stem.replace("ws_eff", "").strip("_-")
        else:
            prefix = stem
    else:
        root = str(output_dir or "").strip() or output_directory_for_project("")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = _safe_name(f"wake_wd_{wd:.1f}_ws_{ws:.1f}_{stamp}")
    os.makedirs(root, exist_ok=True)

    paths: Dict[str, str] = {}
    for variable in variables:
        slug = _FIELD_INFO[variable]["slug"]
        if output_path and variable == "WS_eff":
            paths[variable] = os.path.abspath(output_path)
        else:
            paths[variable] = os.path.join(root, _safe_name(f"{prefix}_{slug}.tif"))
    return paths, os.path.join(root, _safe_name(f"{prefix}.json"))


def build_wake_raster_file(
    flow_map: Any,
    *,
    wd: float,
    ws: float,
    output_path: Optional[str] = None,
    output_dir: str = "",
    crs_wkt: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    terrain_values: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Write a worker-safe wake-raster package and one audit sidecar."""
    ws_eff, x, y = _extract_field_2d(flow_map, ("WS_eff", "WS_eff_xylk"), "WS_eff")
    package_warnings: List[str] = []
    fields: Dict[str, np.ndarray] = {"WS_eff": ws_eff}
    try:
        ws_free, x_free, y_free = _extract_field_2d(flow_map, ("WS", "WS_xylk", "WS_ilk"), "WS")
        if not (np.allclose(x, x_free) and np.allclose(y, y_free)):
            raise log_error(RuntimeError, "Las coordenadas de WS y WS_eff no coinciden.")
    except Exception as exc:
        # Without the free flow PyWake calculated, there is no deficit to give: a uniform speed in its place would
        # be another field (#75, row 5.7). The effective speed is written alone, and the warning says why.
        ws_free = None
        package_warnings.append(log_text(
            "PyWake no expuso el campo WS libre ({error}): no se han escrito el viento libre ni los déficits.",
            error=exc))
    if ws_free is not None:
        wake_deficit = np.asarray(ws_free - ws_eff, dtype=np.float32)
        with np.errstate(divide="ignore", invalid="ignore"):
            wake_deficit_pct = np.full_like(wake_deficit, np.nan, dtype=np.float32)
            np.divide(
                wake_deficit,
                ws_free,
                out=wake_deficit_pct,
                where=np.abs(ws_free) > 1e-9,
            )
            wake_deficit_pct *= np.float32(100.0)
        fields = {
            "WS": ws_free,
            "WS_eff": ws_eff,
            "wake_deficit": wake_deficit,
            "wake_deficit_pct": wake_deficit_pct,
        }
    if terrain_values is not None:
        terrain = np.asarray(terrain_values, dtype=np.float32)
        if terrain.shape == ws_eff.shape:
            fields["Elevation"] = terrain
        else:
            package_warnings.append(log_text(
                "La elevación interpolada no coincide con el grid y no se exportó: {terrain} != {field}.",
                terrain=terrain.shape, field=ws_eff.shape))

    paths, metadata_path = _derive_output_paths(
        wd,
        ws,
        output_path=output_path,
        output_dir=output_dir,
        variables=fields.keys(),
    )
    written_paths: List[str] = []
    entries: List[Dict[str, Any]] = []
    try:
        for variable, values in fields.items():
            path = os.path.abspath(paths[variable])
            temp_path = path + ".part.tif"
            info = _FIELD_INFO[variable]
            try:
                min_value, max_value = _write_geotiff(
                    temp_path,
                    values,
                    x,
                    y,
                    crs_wkt=crs_wkt,
                    description=info["description"],
                )
                os.replace(temp_path, path)
                written_paths.append(path)
                # GDAL keeps a CRS without WKT1 (a derived projected one, #54) in the .aux.xml of the file it wrote, the
                # temporary one: it goes with the raster, and an older one of the destination would describe another file.
                if os.path.isfile(temp_path + ".aux.xml"):
                    os.replace(temp_path + ".aux.xml", path + ".aux.xml")
                elif os.path.isfile(path + ".aux.xml"):
                    os.remove(path + ".aux.xml")
            except Exception:
                try:
                    if os.path.isfile(temp_path):
                        os.remove(temp_path)
                    # Its .aux.xml only once the temporary raster is gone, as for the final one below.
                    if os.path.isfile(temp_path + ".aux.xml"):
                        os.remove(temp_path + ".aux.xml")
                except Exception as _ignored_exc:
                    logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 589, _ignored_exc)
                raise
            stats = _field_stats(values)
            entry: Dict[str, Any] = {
                "variable": variable,
                "units": info["units"],
                "path": path,
                **stats,
            }
            entries.append(entry)

        # A layer without finite cells has no style.
        speed_entries = [e for e in entries if e["variable"] in {"WS", "WS_eff"} and e["valid_cells"]]
        if speed_entries:
            shared_min = min(float(e["min"]) for e in speed_entries)
            shared_max = max(float(e["max"]) for e in speed_entries)
            for entry in speed_entries:
                entry["style_min"] = shared_min
                entry["style_max"] = shared_max
        for entry in entries:
            if entry["variable"] in {"wake_deficit", "wake_deficit_pct"} and entry["valid_cells"]:
                entry["style_min"] = min(0.0, float(entry["min"]))
                entry["style_max"] = max(0.0, float(entry["p95"]), float(entry["max"]))

        effective = next(e for e in entries if e["variable"] == "WS_eff")
        free = next((e for e in entries if e["variable"] == "WS"), None)

        def number(entry: Optional[Dict[str, Any]], key: str) -> Optional[float]:
            """A statistic of a layer; ``None`` without the layer or without finite cells (#63, decision 7)."""
            return None if entry is None or entry[key] is None else float(entry[key])
        result: Dict[str, Any] = {
            "path": effective["path"],
            "rasters": entries,
            "wd": float(wd),
            "ws": float(ws),
            "min_ws": number(effective, "min"),
            "max_ws": number(effective, "max"),
            "mean_ws": number(effective, "mean"),
            "p05_ws": number(effective, "p05"),
            "p50_ws": number(effective, "p50"),
            "p95_ws": number(effective, "p95"),
            "free_flow_min_ws": number(free, "min"),
            "free_flow_max_ws": number(free, "max"),
            "free_flow_mean_ws": number(free, "mean"),
            "valid_cells": int(effective["valid_cells"]),
            "width": int(x.size),
            "height": int(y.size),
            "resolution_x_m": float(_regular_step(x, "X")),
            "resolution_y_m": float(_regular_step(y, "Y")),
            "extent": {
                "xmin": float(np.min(x)),
                "xmax": float(np.max(x)),
                "ymin": float(np.min(y)),
                "ymax": float(np.max(y)),
            },
        }
        result.update(dict(metadata or {}))
        warnings = [str(v) for v in (result.get("warnings") or []) if str(v).strip()]
        warnings.extend(package_warnings)
        result["warnings"] = warnings
        result["metadata_path"] = _write_metadata_sidecar(metadata_path, result)
        return result
    except Exception:
        for cleanup_path in written_paths + [metadata_path, metadata_path + ".tmp"]:
            try:
                if cleanup_path and os.path.isfile(cleanup_path):
                    os.remove(cleanup_path)
                # A raster's .aux.xml goes with it: kept if the raster could not be removed, which would lose its CRS.
                if cleanup_path in written_paths and os.path.isfile(cleanup_path + ".aux.xml"):
                    os.remove(cleanup_path + ".aux.xml")
            except Exception as _ignored_exc:
                logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 660, _ignored_exc)
        raise


def add_wake_raster_result_to_qgis(result: Dict[str, Any]) -> List[Any]:
    """Load and style a completed wake-raster package on QGIS' main thread."""
    try:
        from qgis.core import QgsProject
    except Exception as exc:
        raise log_error(RuntimeError, "No se pudo importar la API de QGIS: {error}", error=exc) from exc

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group_name = "VelantisWind · Estelas"
    group = root.findGroup(group_name)
    if group is None:
        group = root.insertGroup(0, group_name)

    wd = float(result.get("wd", 0.0))
    ws = float(result.get("ws", 0.0))
    suffix = datetime.now().strftime("%H:%M:%S")
    subgroup = group.insertGroup(0, f"wd {wd:.1f}° · ref {ws:.1f} m/s · {suffix}")

    entries = list(result.get("rasters") or [])
    if not entries:
        entries = [{
            "variable": "WS_eff",
            "units": "m/s",
            "path": str(result.get("path") or ""),
            "min": float(result.get("min_ws", 0.0)),
            "max": float(result.get("max_ws", 0.0)),
        }]

    # Insert bottom-to-top because insertLayer(0, ...) places each new layer above.
    order = {"Elevation": 0, "WS": 1, "wake_deficit": 2, "wake_deficit_pct": 3, "WS_eff": 4}
    entries = sorted(entries, key=lambda e: order.get(str(e.get("variable") or ""), 99))
    layers: List[Any] = []
    try:
        for entry in entries:
            layers.append(_add_one_to_qgis(entry, result, subgroup))
    except Exception:
        for layer in layers:
            try:
                project.removeMapLayer(layer.id())
            except Exception as _ignored_exc:
                logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 705, _ignored_exc)
        try:
            group.removeChildNode(subgroup)
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 709, _ignored_exc)
        raise
    subgroup.setExpanded(True)
    group.setExpanded(True)
    result["layers"] = layers
    result["layer"] = layers[-1] if layers else None
    return layers


def create_wake_raster_layer(
    flow_map: Any,
    *,
    wd: float,
    ws: float,
    output_path: Optional[str] = None,
) -> Tuple[str, Any, float, float]:
    """Compatibility wrapper for the former synchronous workflow."""
    project_home = ""
    crs_wkt = ""
    try:
        from qgis.core import QgsProject
        from ...crs_utils import preferred_wkt

        project = QgsProject.instance()
        project_home = str(project.homePath() or "")
        crs = project.crs()
        if crs is not None and crs.isValid():
            crs_wkt = preferred_wkt(crs)
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 738, _ignored_exc)
    result = build_wake_raster_file(
        flow_map,
        wd=wd,
        ws=ws,
        output_path=output_path,
        output_dir=output_directory_for_project(project_home),
        crs_wkt=crs_wkt,
    )
    layers = add_wake_raster_result_to_qgis(result)
    layer = result.get("layer") or (layers[-1] if layers else None)
    return str(result["path"]), layer, float(result["min_ws"]), float(result["max_ws"])


__all__ = [
    "add_wake_raster_result_to_qgis",
    "build_wake_raster_file",
    "create_wake_raster_layer",
    "default_output_path",
    "output_directory_for_project",
]
