# -*- coding: utf-8 -*-
"""Build primitive snapshots for background noise calculations.

QgsTask worker threads should not use live QGIS layers, project objects or
widgets.  This module runs on the main QGIS thread, reads all required layer
content, and returns plain Python dictionaries that can safely be consumed by a
background task.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from qgis.core import QgsProject, QgsRasterLayer, QgsWkbTypes

from ..domain import NoiseRunConfig
from ..noise_spectrum import SpectrumLibrary
from ..sources.collector import _collect_sources
from ..receivers.collector import _build_receiver_feature_list
from ..qgis_io.common import _is_valid_dem_value


def _primitive(value: Any) -> Any:
    """Best-effort conversion of QVariant/Qt values to primitive values."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        # QDate/QDateTime/QTime have ISO helpers.
        if hasattr(value, "toString"):
            return str(value.toString())
    except Exception:
        pass
    try:
        return value.item()  # numpy scalar
    except Exception:
        pass
    try:
        return str(value)
    except Exception:
        return None


def _field_specs(fields) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fld in fields:
        try:
            out.append({
                "name": str(fld.name()),
                "type": int(fld.type()),
                "type_name": str(fld.typeName() or ""),
                "length": int(fld.length()),
                "precision": int(fld.precision()),
            })
        except Exception:
            out.append({"name": str(getattr(fld, "name", lambda: "field")()), "type": 10, "type_name": "", "length": 0, "precision": 0})
    return out


def _source_snapshot(src: Any) -> Dict[str, Any]:
    lw_octave = {}
    try:
        lw_octave = {int(k): float(v) for k, v in ((getattr(src, "lw_octave", None) or {}).items())}
    except Exception:
        lw_octave = {}
    return {
        "model_name": str(getattr(src, "model_name", "") or ""),
        "source_group": str(getattr(src, "source_group", "") or ""),
        "park_name": str(getattr(src, "park_name", "") or ""),
        "layer_name": str(getattr(src, "layer_name", "") or ""),
        "x": float(getattr(src, "x", 0.0) or 0.0),
        "y": float(getattr(src, "y", 0.0) or 0.0),
        "hub_height": float(getattr(src, "hub_height", 0.0) or 0.0),
        "diameter": None if getattr(src, "diameter", None) is None else float(getattr(src, "diameter")),
        "lwa": float(getattr(src, "lwa", 0.0) or 0.0),
        "feature_id": int(getattr(src, "feature_id", -1) or -1),
        "z_ground": None if getattr(src, "z_ground", None) is None else float(getattr(src, "z_ground")),
        "lw_octave": lw_octave,
        "spectrum_source": str(getattr(src, "spectrum_source", "") or ""),
    }


def _receiver_snapshot(rec: Any) -> Dict[str, Any]:
    try:
        geom_wkt = rec.geometry.asWkt() if rec.geometry is not None else ""
    except Exception:
        geom_wkt = ""
    meta: Dict[str, Any] = {}
    for k, v in ((getattr(rec, "meta", None) or {}).items()):
        meta[str(k)] = _primitive(v)
    return {
        "feature_id": int(getattr(rec, "feature_id", -1) or -1),
        "x": float(getattr(rec, "x", 0.0) or 0.0),
        "y": float(getattr(rec, "y", 0.0) or 0.0),
        "z_ground": None if getattr(rec, "z_ground", None) is None else float(getattr(rec, "z_ground")),
        "receiver_height": float(getattr(rec, "receiver_height", 0.0) or 0.0),
        "eval_mode": str(getattr(rec, "eval_mode", "point") or "point"),
        "geometry_wkt": geom_wkt,
        "attrs": [_primitive(v) for v in list(getattr(rec, "attrs", []) or [])],
        "meta": meta,
    }





def _gdal_can_open(path: str) -> bool:
    """Return whether GDAL can open this path from a worker thread."""
    try:
        import os
        if not path or not isinstance(path, str):
            return False
        # Some QGIS Processing temporary outputs expose a layer name such as
        # "OUTPUT" as source(); this is not a GDAL-readable path.
        if path.strip().upper() == "OUTPUT":
            return False
        from osgeo import gdal
        ds = gdal.Open(path)
        ok = ds is not None
        ds = None
        return bool(ok)
    except Exception:
        return False


def _export_dem_layer_for_task(dem_layer: QgsRasterLayer) -> str:
    """Materialise a QGIS raster layer to a temporary GeoTIFF for QgsTask.

    Background tasks must not use live QgsRasterLayer objects.  If the selected
    MDT/DSM has a normal file path, that path is reused.  If it is a Processing
    output/memory/provider layer whose ``source()`` is not GDAL-readable, this
    function writes an equivalent GeoTIFF on the main thread and returns that
    file path.  This is critical for ISO + MDT Abar in the worker: without a
    real raster path the task silently falls back to no topographic screening.
    """
    try:
        if dem_layer is None or not isinstance(dem_layer, QgsRasterLayer):
            return ""
        src = str(dem_layer.source() or "")
        if _gdal_can_open(src):
            return src

        import os
        import tempfile
        from qgis.core import QgsRasterFileWriter, QgsRasterPipe

        tmpdir = os.path.join(tempfile.gettempdir(), "velantis_noise")
        os.makedirs(tmpdir, exist_ok=True)
        out_path = os.path.join(tmpdir, "velantis_noise_mdt_task.tif")
        base, ext = os.path.splitext(out_path)
        i = 1
        while os.path.exists(out_path):
            out_path = f"{base}_{i}{ext}"
            i += 1

        provider = dem_layer.dataProvider()
        pipe = QgsRasterPipe()
        try:
            cloned = provider.clone()
        except Exception:
            cloned = None
        if cloned is not None and pipe.set(cloned):
            writer = QgsRasterFileWriter(out_path)
            try:
                writer.setCreateOptions(["COMPRESS=LZW"])
            except Exception:
                pass
            res = writer.writeRaster(
                pipe,
                int(dem_layer.width()),
                int(dem_layer.height()),
                dem_layer.extent(),
                dem_layer.crs(),
            )
            # Different QGIS versions expose writer results differently.  If a
            # file was produced and GDAL can open it, accept it.
            if _gdal_can_open(out_path):
                return out_path

        # Conservative fallback: sample every output pixel with the provider and
        # write a simple GeoTIFF.  This is slower, but it happens once on the
        # main thread before the heavy acoustic task and preserves MDT physics.
        try:
            import numpy as np
            from osgeo import gdal, osr
            width = int(dem_layer.width())
            height = int(dem_layer.height())
            if width <= 0 or height <= 0:
                return ""
            ext = dem_layer.extent()
            px = float(ext.width()) / float(width)
            py = float(ext.height()) / float(height)
            arr = np.full((height, width), -9999.0, dtype=np.float32)
            for iy in range(height):
                y = float(ext.yMaximum()) - (iy + 0.5) * py
                for ix in range(width):
                    x = float(ext.xMinimum()) + (ix + 0.5) * px
                    try:
                        val, ok = provider.sample(__import__('qgis').core.QgsPointXY(x, y), 1)
                        if ok and _is_valid_dem_value(val, provider, 1):
                            fv = float(val)
                            arr[iy, ix] = fv
                    except Exception:
                        pass
            driver = gdal.GetDriverByName("GTiff")
            ds = driver.Create(out_path, width, height, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"])
            if ds is None:
                return ""
            ds.SetGeoTransform((float(ext.xMinimum()), px, 0.0, float(ext.yMaximum()), 0.0, -py))
            try:
                srs = osr.SpatialReference()
                srs.ImportFromWkt(str(dem_layer.crs().toWkt() or ""))
                ds.SetProjection(srs.ExportToWkt())
            except Exception:
                pass
            band = ds.GetRasterBand(1)
            band.WriteArray(arr)
            band.SetNoDataValue(-9999.0)
            band.FlushCache()
            ds.FlushCache()
            ds = None
            return out_path if _gdal_can_open(out_path) else ""
        except Exception:
            return ""
    except Exception:
        return ""


def build_noise_calculation_snapshot(config: NoiseRunConfig) -> Dict[str, Any]:
    """Read QGIS inputs on the main thread and return primitive-only data."""
    prj = QgsProject.instance()

    spectrum_library = None
    if str(config.calculation_engine or "fast").lower() == "iso":
        try:
            import os
            spectrum_library_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spectrum_library")
            spectrum_library = SpectrumLibrary(library_dir=spectrum_library_dir)
        except Exception:
            spectrum_library = None

    sources, src_diag = _collect_sources(
        prj,
        config.model_cfg,
        config.dem_layer,
        spectrum_library=spectrum_library,
        source_layer_ids=config.source_layer_ids,
    )
    if not sources:
        raise ValueError("No se han detectado turbinas/layout válidos para el cálculo acústico.")

    receivers = _build_receiver_feature_list(
        config.receiver_layer,
        config.receiver_height_m,
        config.dem_layer,
        receiver_height_field=config.receiver_height_field,
        receiver_type_field=config.receiver_type_field,
        receiver_limit_day_field=config.receiver_limit_field_day,
        receiver_limit_night_field=config.receiver_limit_field_night,
        receiver_limit_custom_field=config.receiver_limit_field_custom,
        receiver_source_field=config.receiver_source_field,
    )
    if not receivers:
        raise ValueError("The receiver layer contains no valid features for calculation.")

    dem_path = ""
    dem_name = ""
    dem_source = ""
    try:
        if isinstance(config.dem_layer, QgsRasterLayer):
            dem_source = str(config.dem_layer.source() or "")
            dem_name = str(config.dem_layer.name() or "")
            dem_path = _export_dem_layer_for_task(config.dem_layer)
    except Exception:
        dem_path = ""
        dem_name = ""
        dem_source = ""

    crs = prj.crs()
    return {
        "sources": [_source_snapshot(s) for s in sources],
        "receivers": [_receiver_snapshot(r) for r in receivers],
        "src_diag": src_diag,
        "field_specs": _field_specs(config.receiver_layer.fields()),
        "receiver_layer_name": str(config.receiver_layer.name() or ""),
        "geometry_type": str(QgsWkbTypes.displayString(config.receiver_layer.wkbType())),
        "crs_authid": str(crs.authid() or "EPSG:25830"),
        "crs_wkt": str(crs.toWkt() or ""),
        "params": {
            "receiver_height_m": float(config.receiver_height_m),
            "max_radius_m": float(config.max_radius_m),
            "alpha_db_per_m": float(config.alpha_db_per_m),
            "ground_factor_g": float(config.ground_factor_g),
            "ground_mode": str(config.ground_mode or "global"),
            "receiver_limit_dba": float(config.receiver_limit_dba),
            "receiver_limit_mode": str(config.receiver_limit_mode or "global"),
            "receiver_limit_scenario": str(config.receiver_limit_scenario or "custom"),
            "receiver_limit_field_day": config.receiver_limit_field_day,
            "receiver_limit_field_night": config.receiver_limit_field_night,
            "receiver_limit_field_custom": config.receiver_limit_field_custom,
            "min_distance_m": float(config.min_distance_m),
            "result_layer_name": str(config.result_layer_name),
            "sources_layer_name": str(config.sources_layer_name),
            "links_layer_name": str(config.links_layer_name),
            "grid_layer_name": str(config.grid_layer_name),
            "iso_layer_name": str(config.iso_layer_name),
            "uncovered_layer_name": str(config.uncovered_layer_name),
            "create_sources_layer": bool(config.create_sources_layer),
            "create_links_layer": bool(config.create_links_layer),
            "create_grid_layer": bool(config.create_grid_layer),
            "create_iso_layer": bool(config.create_iso_layer),
            "iso_levels": list(config.iso_levels or [35.0, 40.0, 45.0, 50.0]),
            "grid_resolution_m": float(config.grid_resolution_m),
            "calculation_engine": str(config.calculation_engine or "fast"),
            "temperature_c": float(config.temperature_c),
            "humidity_percent": float(config.humidity_percent),
            "pressure_kpa": float(config.pressure_kpa),
            "dem_path": dem_path,
            "dem_source": dem_source,
            "dem_name": dem_name,
            "dem_used": bool(config.dem_layer is not None),
            "dem_task_file_available": bool(dem_path),
            "model_cfg": config.model_cfg,
        },
    }
