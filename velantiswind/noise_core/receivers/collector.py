# -*- coding: utf-8 -*-
"""Receiver feature extraction for the noise module."""
from __future__ import annotations

from typing import Dict, List, Optional

from qgis.core import QgsGeometry, QgsRasterLayer, QgsVectorLayer

from ..noise_common import NoiseReceiver
from ..qgis_io.common import _sample_dem

def _build_receiver_feature_list(
    receiver_layer: QgsVectorLayer,
    receiver_height_m: float,
    dem_layer: Optional[QgsRasterLayer],
    receiver_height_field: Optional[str] = None,
    receiver_type_field: Optional[str] = None,
    receiver_limit_day_field: Optional[str] = None,
    receiver_limit_night_field: Optional[str] = None,
    receiver_limit_custom_field: Optional[str] = None,
    receiver_source_field: Optional[str] = None,
) -> List[NoiseReceiver]:
    out: List[NoiseReceiver] = []
    fields = receiver_layer.fields()
    field_names = {a.name() for a in fields}

    def _safe_float(v, default=None):
        try:
            if v is None or v == '':
                return default
            return float(v)
        except Exception:
            return default

    for feat in receiver_layer.getFeatures():
        try:
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            if geom.type() == 0:  # point
                pt = geom.asPoint()
                eval_mode = "point"
            else:
                pt = geom.centroid().asPoint()
                eval_mode = "centroid"
            x, y = float(pt.x()), float(pt.y())
        except Exception:
            continue
        z_ground = _sample_dem(dem_layer, x, y)
        attrs = [feat[a.name()] for a in fields]
        meta: Dict[str, object] = {}
        if receiver_height_field and receiver_height_field in field_names:
            meta['receiver_height_m'] = _safe_float(feat[receiver_height_field], float(receiver_height_m))
        if receiver_type_field and receiver_type_field in field_names:
            meta['receiver_type'] = str(feat[receiver_type_field] or '').strip()
        if receiver_limit_day_field and receiver_limit_day_field in field_names:
            meta['limit_day_dba'] = _safe_float(feat[receiver_limit_day_field], None)
        if receiver_limit_night_field and receiver_limit_night_field in field_names:
            meta['limit_night_dba'] = _safe_float(feat[receiver_limit_night_field], None)
        if receiver_limit_custom_field and receiver_limit_custom_field in field_names:
            meta['limit_custom_dba'] = _safe_float(feat[receiver_limit_custom_field], None)
        if receiver_source_field and receiver_source_field in field_names:
            meta['source_layer_name'] = str(feat[receiver_source_field] or '').strip()
        out.append(
            NoiseReceiver(
                feature_id=int(feat.id()),
                x=x,
                y=y,
                z_ground=z_ground,
                receiver_height=float(meta.get('receiver_height_m', receiver_height_m)),
                eval_mode=eval_mode,
                geometry=QgsGeometry(geom),
                attrs=attrs,
                meta=meta,
            )
        )
    return out
