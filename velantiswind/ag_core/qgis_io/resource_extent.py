# -*- coding: utf-8 -*-
"""Draw wind-resource domain extents in the QGIS map canvas.

This module is deliberately lightweight and QGIS-only.  It is used by the
Energy/AEP dialog to help users see the limits of the selected WRG or
WAsP/Surfer grid resource before running PyWake.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsFillSymbol,
    QgsLayerTreeGroup,
)
try:
    from qgis.utils import iface  # type: ignore
except Exception:  # pragma: no cover - only when imported outside QGIS
    iface = None  # type: ignore

_LAYER_PROP = "velantis/resource_extent"
_LAYER_NAME = "Velantis · perímetro recurso eólico"
_GROUP_NAME = "Velantis · Recurso eólico"
_RASTER_EXTS = {".grd", ".asc", ".tif", ".tiff", ".vrt"}

ExtentTuple = Tuple[float, float, float, float]  # xmin, xmax, ymin, ymax


def _project_crs_authid() -> str:
    try:
        crs = QgsProject.instance().crs()
        if crs is not None and crs.isValid() and crs.authid():
            return crs.authid()
    except Exception:
        pass
    return "EPSG:25830"


def _valid_extent(ext: ExtentTuple) -> bool:
    try:
        xmin, xmax, ymin, ymax = [float(v) for v in ext]
        return xmax > xmin and ymax > ymin
    except Exception:
        return False


def _union_extents(extents: Sequence[ExtentTuple]) -> Optional[ExtentTuple]:
    valid = [e for e in extents if _valid_extent(e)]
    if not valid:
        return None
    return (
        min(e[0] for e in valid),
        max(e[1] for e in valid),
        min(e[2] for e in valid),
        max(e[3] for e in valid),
    )


def _intersection_extents(extents: Sequence[ExtentTuple]) -> Optional[ExtentTuple]:
    valid = [e for e in extents if _valid_extent(e)]
    if not valid:
        return None
    out = (
        max(e[0] for e in valid),
        min(e[1] for e in valid),
        max(e[2] for e in valid),
        min(e[3] for e in valid),
    )
    return out if _valid_extent(out) else None


def _ensure_group() -> QgsLayerTreeGroup:
    root = QgsProject.instance().layerTreeRoot()
    for child in root.children():
        if isinstance(child, QgsLayerTreeGroup) and child.name() == _GROUP_NAME:
            return child
    return root.addGroup(_GROUP_NAME)


def clear_resource_extent_layers() -> int:
    """Remove existing Velantis resource extent layers from the project."""
    prj = QgsProject.instance()
    to_remove: List[str] = []
    for lyr in prj.mapLayers().values():
        try:
            if lyr.customProperty(_LAYER_PROP, False):
                to_remove.append(lyr.id())
        except Exception:
            continue
    if to_remove:
        prj.removeMapLayers(to_remove)
    return len(to_remove)


def _apply_extent_style(layer: QgsVectorLayer, source_type: str) -> None:
    """Apply a transparent, dashed outline style."""
    try:
        if source_type.lower().startswith("wrg"):
            outline = "22,117,88,255"   # green
            fill = "22,117,88,18"
        else:
            outline = "32,100,164,255"  # blue
            fill = "32,100,164,16"
        symbol = QgsFillSymbol.createSimple({
            "style": "solid",
            "color": fill,
            "outline_color": outline,
            "outline_width": "0.7",
            "outline_style": "dash",
        })
        layer.renderer().setSymbol(symbol)
        layer.triggerRepaint()
    except Exception:
        pass


def add_extent_layer(
    extent: ExtentTuple,
    *,
    source_type: str,
    label: str = "",
    crs_authid: Optional[str] = None,
    zoom: bool = False,
) -> QgsVectorLayer:
    """Create/replace a memory polygon layer with the supplied extent."""
    if not _valid_extent(extent):
        raise ValueError(f"Extensión no válida: {extent}")

    clear_resource_extent_layers()

    xmin, xmax, ymin, ymax = [float(v) for v in extent]
    crs_authid = crs_authid or _project_crs_authid()
    uri = f"Polygon?crs={crs_authid}" if crs_authid else "Polygon"
    layer = QgsVectorLayer(uri, _LAYER_NAME, "memory")
    if not layer.isValid():
        raise RuntimeError("No se pudo crear la capa temporal de perímetro del recurso.")

    prov = layer.dataProvider()
    prov.addAttributes([
        QgsField("tipo", QVariant.String),
        QgsField("fuente", QVariant.String),
        QgsField("xmin", QVariant.Double),
        QgsField("xmax", QVariant.Double),
        QgsField("ymin", QVariant.Double),
        QgsField("ymax", QVariant.Double),
    ])
    layer.updateFields()

    pts = [
        QgsPointXY(xmin, ymin),
        QgsPointXY(xmax, ymin),
        QgsPointXY(xmax, ymax),
        QgsPointXY(xmin, ymax),
        QgsPointXY(xmin, ymin),
    ]
    feat = QgsFeature(layer.fields())
    feat.setGeometry(QgsGeometry.fromPolygonXY([pts]))
    feat.setAttributes([source_type, label or source_type, xmin, xmax, ymin, ymax])
    prov.addFeature(feat)
    layer.updateExtents()
    layer.setCustomProperty(_LAYER_PROP, True)
    layer.setCustomProperty("velantis/resource_type", source_type)
    layer.setCustomProperty("velantis/resource_label", label or source_type)
    layer.setCustomProperty("velantis/resource_extent", f"{xmin},{xmax},{ymin},{ymax}")

    _apply_extent_style(layer, source_type)

    prj = QgsProject.instance()
    prj.addMapLayer(layer, False)
    try:
        group = _ensure_group()
        group.addLayer(layer)
    except Exception:
        prj.addMapLayer(layer, True)

    if zoom and iface is not None:
        try:
            canvas = iface.mapCanvas()
            canvas.setExtent(QgsRectangle(xmin, ymin, xmax, ymax))
            canvas.refresh()
        except Exception:
            pass

    return layer


def _parse_dsaa_extent(path: str) -> Optional[ExtentTuple]:
    """Read Surfer ASCII DSAA extent: DSAA, nx ny, xmin xmax, ymin ymax."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            first = f.readline().strip()
            if first.upper() != "DSAA":
                return None
            _nxny = f.readline().split()
            xs = f.readline().split()
            ys = f.readline().split()
            if len(xs) >= 2 and len(ys) >= 2:
                xmin, xmax = float(xs[0]), float(xs[1])
                ymin, ymax = float(ys[0]), float(ys[1])
                return (xmin, xmax, ymin, ymax)
    except Exception:
        return None
    return None


def _parse_esri_ascii_extent(path: str) -> Optional[ExtentTuple]:
    """Read a simple ESRI ASCII grid header extent when GDAL/QGIS cannot open it."""
    try:
        header = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(8):
                line = f.readline()
                if not line:
                    break
                parts = line.strip().split()
                if len(parts) >= 2:
                    header[parts[0].lower()] = float(parts[1])
        ncols = int(header.get("ncols", 0))
        nrows = int(header.get("nrows", 0))
        cell = float(header.get("cellsize", 0.0))
        if ncols <= 0 or nrows <= 0 or cell <= 0:
            return None
        x0 = header.get("xllcorner", header.get("xllcenter"))
        y0 = header.get("yllcorner", header.get("yllcenter"))
        if x0 is None or y0 is None:
            return None
        # If the header gives cell centers, convert to outer extent.
        if "xllcenter" in header:
            x0 = float(x0) - cell * 0.5
        if "yllcenter" in header:
            y0 = float(y0) - cell * 0.5
        xmin = float(x0)
        ymin = float(y0)
        xmax = xmin + ncols * cell
        ymax = ymin + nrows * cell
        return (xmin, xmax, ymin, ymax)
    except Exception:
        return None


def _extent_from_raster_file(path: str) -> Tuple[Optional[ExtentTuple], Optional[str]]:
    """Return extent and CRS authid for one raster/grid file."""
    try:
        r = QgsRasterLayer(path, os.path.basename(path))
        if r.isValid():
            e = r.extent()
            ext = (float(e.xMinimum()), float(e.xMaximum()), float(e.yMinimum()), float(e.yMaximum()))
            crs_authid = None
            try:
                if r.crs().isValid() and r.crs().authid():
                    crs_authid = r.crs().authid()
            except Exception:
                crs_authid = None
            if _valid_extent(ext):
                return ext, crs_authid
    except Exception:
        pass

    for parser in (_parse_dsaa_extent, _parse_esri_ascii_extent):
        ext = parser(path)
        if ext is not None and _valid_extent(ext):
            return ext, None
    return None, None


def _iter_grid_files(folder: str) -> Iterable[str]:
    """Scan likely WAsP/Surfer grid files without walking huge projects."""
    if not os.path.isdir(folder):
        return []
    out: List[str] = []
    root_depth = folder.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(folder):
        depth = root.rstrip(os.sep).count(os.sep) - root_depth
        if depth > 2:
            dirs[:] = []
            continue
        # Ignore folders created for incompatible grids to avoid drawing a bad extent.
        base = os.path.basename(root).lower()
        if base.startswith("_bad") or base in {"_bad_for_pywake", "backup", "bak"}:
            continue
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _RASTER_EXTS:
                out.append(os.path.join(root, fn))
    return out


def show_wasp_resource_extent(folder: str, *, zoom: bool = False) -> Tuple[bool, str]:
    """Draw the common domain of WAsP/Surfer grids in a folder."""
    if not os.path.isdir(folder):
        return False, "La carpeta WAsP/Surfer no existe."

    candidates = list(_iter_grid_files(folder))
    if not candidates:
        return False, "No se han encontrado grids .grd/.asc/.tif en la carpeta seleccionada."

    extents: List[ExtentTuple] = []
    crs_authid: Optional[str] = None
    for p in candidates:
        ext, crs = _extent_from_raster_file(p)
        if ext is None:
            continue
        extents.append(ext)
        if crs and crs_authid is None:
            crs_authid = crs

    if not extents:
        return False, "No se pudo leer la extensión espacial de los grids seleccionados."

    common = _intersection_extents(extents)
    used_common = common is not None
    extent = common or _union_extents(extents)
    if extent is None:
        return False, "Las extensiones de los grids no tienen intersección válida."

    label = os.path.basename(os.path.normpath(folder)) or folder
    add_extent_layer(extent, source_type="WAsP/Surfer", label=label, crs_authid=crs_authid, zoom=zoom)
    if used_common:
        return True, f"Perímetro WAsP/Surfer dibujado: dominio común de {len(extents)} grid(s)."
    return True, f"Perímetro WAsP/Surfer dibujado: envolvente de {len(extents)} grid(s) sin intersección común."


def show_wrg_resource_extent(
    paths: Sequence[str],
    *,
    read_wrg_meta_func: Callable[[str], Any],
    zoom: bool = False,
) -> Tuple[bool, str]:
    """Draw the union of one or several WRG/ZIP extents."""
    clean_paths = [p.strip() for p in paths if p and str(p).strip()]
    if not clean_paths:
        return False, "No se ha seleccionado ningún WRG/ZIP."

    extents: List[ExtentTuple] = []
    labels: List[str] = []
    for p in clean_paths:
        if not os.path.isfile(p):
            return False, f"El archivo WRG/ZIP no existe: {p}"
        meta = read_wrg_meta_func(p)
        ext = meta.get("extent") if isinstance(meta, dict) else None
        if ext and len(ext) == 4:
            xmin, xmax, ymin, ymax = [float(v) for v in ext]
            extents.append((xmin, xmax, ymin, ymax))
            labels.append(os.path.basename(p))
    extent = _union_extents(extents)
    if extent is None:
        return False, "No se pudo leer una extensión válida desde el WRG/ZIP."

    label = "; ".join(labels[:3]) + ("…" if len(labels) > 3 else "")
    add_extent_layer(extent, source_type="WRG", label=label, crs_authid=_project_crs_authid(), zoom=zoom)
    return True, f"Perímetro WRG dibujado: {len(extents)} archivo(s)."


__all__ = [
    "add_extent_layer",
    "clear_resource_extent_layers",
    "show_wasp_resource_extent",
    "show_wrg_resource_extent",
]
