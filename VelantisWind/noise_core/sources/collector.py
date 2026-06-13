# -*- coding: utf-8 -*-
"""Source-layer discovery and turbine acoustic-source collection."""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes

from ..noise_common import NoiseSource, log as _log
from ..noise_spectrum import get_template_for_model
from ..acoustics.curves import load_acoustic_curve_csv, evaluate_acoustic_curve
from ..qgis_io.common import _sample_dem, _layer_crs_matches

_GROUP_NAME = "AEP · Coordenadas por modelo"

def _is_model_layer(lyr: QgsVectorLayer) -> bool:
    try:
        if not isinstance(lyr, QgsVectorLayer):
            return False
        if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            return False
        if bool(lyr.customProperty("velantis/noise_output", False)):
            return False
        if bool(lyr.customProperty("velantis/shadow_output", False)):
            return False
        name = (lyr.name() or "").strip()
        if name.startswith("Noise ·") or name.startswith("Shadow ·"):
            return False
        model_name = (lyr.customProperty("velantis/model_name", "") or "").strip()
        coords_csv = (lyr.customProperty("velantis/coords_csv", "") or "").strip()
        if model_name or coords_csv:
            return True
        if name.endswith(" (CSV)"):
            return True
    except Exception:
        return False
    return False


def _iter_group_layers_recursive(node):
    try:
        children = node.children()
    except Exception:
        children = []
    for child in children:
        try:
            lyr = child.layer()
        except Exception:
            lyr = None
        if lyr is not None:
            yield lyr
        else:
            yield from _iter_group_layers_recursive(child)


def _iter_model_layers(prj: QgsProject, source_layer_ids: Optional[List[str]] = None) -> List[QgsVectorLayer]:
    out: List[QgsVectorLayer] = []
    seen = set()
    wanted = set(str(x) for x in (source_layer_ids or []) if str(x))
    try:
        root = prj.layerTreeRoot()
        for child in root.children():
            if getattr(child, "name", lambda: None)() not in (_GROUP_NAME, "VelantisWind · Turbine layouts"):
                continue
            for lyr in _iter_group_layers_recursive(child):
                if not _is_model_layer(lyr):
                    continue
                lid = str(lyr.id())
                if wanted and lid not in wanted:
                    continue
                if lid in seen:
                    continue
                out.append(lyr)
                seen.add(lid)
    except Exception:
        pass
    for lyr in prj.mapLayers().values():
        if not _is_model_layer(lyr):
            continue
        lid = str(lyr.id())
        if wanted and lid not in wanted:
            continue
        if lid in seen:
            continue
        out.append(lyr)
        seen.add(lid)
    return out


def _collect_sources(
    prj: QgsProject,
    model_cfg: Dict[str, Dict[str, float]],
    dem_layer: Optional[QgsRasterLayer],
    spectrum_library=None,
    source_layer_ids: Optional[List[str]] = None,
) -> Tuple[List[NoiseSource], Dict[str, Dict[str, float]]]:
    project_crs = prj.crs()
    layers = _iter_model_layers(prj, source_layer_ids=source_layer_ids)
    sources: List[NoiseSource] = []
    diag: Dict[str, Dict[str, float]] = {}

    for lyr in layers:
        if not _layer_crs_matches(lyr, project_crs):
            _log(f"[WARN] La capa de layout '{lyr.name()}' no está en el mismo CRS que el proyecto. Se ignora en el cálculo de ruido.")
            continue
        lname = lyr.name() or ""
        model_name = str((lyr.customProperty('velantis/model_name', '') or '').strip())
        if not model_name:
            model_name = lname[:-6] if lname.endswith(" (CSV)") else lname
        cfg = model_cfg.get(str(lyr.id()), {}) or model_cfg.get(model_name, {})
        source_group = str(cfg.get('source_group_name') or (lyr.customProperty('velantis/noise_group_name', '') or '').strip() or lname)
        park_name = str(cfg.get('park_name') or (lyr.customProperty('velantis/park_name', '') or '').strip())
        lwa_fixed = float(cfg.get("lwa", 105.0))
        hub_h = float(cfg.get("hub_height") or 100.0)
        diameter = cfg.get("diameter")
        acoustic_mode = str(cfg.get("acoustic_mode") or "fixed").strip().lower()
        curve_path = str(cfg.get("curve_path") or "").strip()
        eval_ws_m_s = cfg.get("eval_ws_m_s")
        use_curve_worst_case = bool(cfg.get("use_curve_worst_case", False))
        curve_note = ""
        lwa = lwa_fixed
        if acoustic_mode == "curve" and curve_path:
            try:
                ws_arr, lwa_arr = load_acoustic_curve_csv(curve_path)
                lwa = evaluate_acoustic_curve(ws_arr, lwa_arr, eval_ws_m_s=eval_ws_m_s, use_worst_case=use_curve_worst_case)
                curve_note = (
                    f"Curva peor caso ({os.path.basename(curve_path)})"
                    if use_curve_worst_case else
                    f"Curva @ {float(eval_ws_m_s):.1f} m/s ({os.path.basename(curve_path)})"
                )
            except Exception as e:
                curve_note = f"Curva inválida -> fallback LwA fijo ({e})"
                lwa = lwa_fixed
        if diameter is not None:
            try:
                diameter = float(diameter)
            except Exception:
                diameter = None

        n = 0
        # Valores por defecto a nivel de capa.
        # En algunos proyectos la capa seleccionada puede no tener entidades válidas
        # o todas sus geometrías pueden fallar al leerse; en ese caso el bucle de
        # features no asigna estas variables y Python lanzaba:
        # "cannot access local variable 'spectrum_source' where it is not associated with a value".
        lw_octave = None
        spectrum_source = "Sin fuentes válidas en la capa"
        spectrum_template_ref = None
        spectrum_delta_db = None
        for feat in lyr.getFeatures():
            try:
                pt = feat.geometry().asPoint()
                x, y = float(pt.x()), float(pt.y())
            except Exception:
                continue
            z_ground = _sample_dem(dem_layer, x, y)

            # Resolve octave-band spectrum
            lw_octave = None
            spectrum_source = ""
            if spectrum_library is not None:
                try:
                    lw_octave, spectrum_source = spectrum_library.get_spectrum(
                        model_name=model_name,
                        lwa_global=lwa,
                        rated_power_mw=cfg.get("rated_power_mw"),
                        custom_csv=cfg.get("spectrum_csv_path")
                    )
                except Exception as e:
                    _log(f"[ISO][WARN] Espectro '{model_name}': {e}")
                    spectrum_source = f"Error espectro → fallback LwA ({e})"
            if not spectrum_source:
                spectrum_source = "Sin espectro cargado (fallback LwA si motor ISO)"
            # End spectrum resolution
            spectrum_template_ref = None
            spectrum_delta_db = None
            try:
                if str(spectrum_source).startswith("Plantilla:") and lw_octave:
                    spectrum_template_ref = get_template_for_model(model_name, cfg.get("rated_power_mw"))
                    diffs = [float(lw_octave.get(f, 0.0)) - float(spectrum_template_ref.get(f, 0.0)) for f in spectrum_template_ref.keys() if f in lw_octave]
                    if diffs:
                        spectrum_delta_db = float(sum(diffs) / len(diffs))
            except Exception:
                spectrum_template_ref = None
                spectrum_delta_db = None
            sources.append(
                NoiseSource(
                    model_name=model_name,
                    source_group=source_group,
                    park_name=park_name,
                    x=x,
                    y=y,
                    hub_height=hub_h,
                    diameter=diameter,
                    lwa=lwa,
                    lw_octave=lw_octave,  # ← CORREGIDO: pasar espectro obtenido
                    feature_id=int(feat.id()),
                    layer_name=lyr.name(),
                    z_ground=z_ground,
                    spectrum_source=spectrum_source,
                )
            )
            n += 1
        diag[str(lyr.id())] = {
            "name": source_group,
            "model_name": model_name,
            "park_name": park_name,
            "layer_name": lyr.name(),
            "count": float(n),
            "lwa": float(lwa),
            "lwa_fixed": float(lwa_fixed),
            "hub_height": float(hub_h),
            "diameter": float(diameter) if diameter is not None else float("nan"),
            "acoustic_mode": acoustic_mode,
            "curve_path": curve_path,
            "curve_note": curve_note,
            "eval_ws_m_s": float(eval_ws_m_s) if eval_ws_m_s is not None and math.isfinite(float(eval_ws_m_s)) else float('nan'),
            "use_curve_worst_case": bool(use_curve_worst_case),
            "spectrum_source": str(spectrum_source),
            "lw_octave": {int(k): float(v) for k, v in (lw_octave or {}).items()} if lw_octave else {},
            "spectrum_template_ref": {int(k): float(v) for k, v in (spectrum_template_ref or {}).items()} if spectrum_template_ref else {},
            "spectrum_delta_db": float(spectrum_delta_db) if spectrum_delta_db is not None and math.isfinite(float(spectrum_delta_db)) else float('nan'),
        }
    return sources, diag
