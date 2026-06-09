# -*- coding: utf-8 -*-
"""QGIS output layers for the noise module."""
from __future__ import annotations

import math
import os
import tempfile
from typing import Dict, List, Optional

from osgeo import gdal, osr, ogr
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt import QtGui
from qgis.core import (
    QgsColorRampShader,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsVectorLayer,
)

from ..noise_common import NoiseSource, NoiseReceiver, log as _log
from .common import _remove_existing_layers_by_name, _set_field_aliases, _unique_temp_output

def _build_source_layer(prj: QgsProject, sources: List[NoiseSource], src_stats: Dict[int, Dict[str, object]], layer_name: str) -> Optional[QgsVectorLayer]:
    _remove_existing_layers_by_name(prj, [layer_name])
    lyr = QgsVectorLayer(f"Point?crs={prj.crs().authid() or 'EPSG:25830'}", layer_name, 'memory')
    pr = lyr.dataProvider()
    fields = QgsFields()
    fields.append(QgsField('src_id', QVariant.Int))
    fields.append(QgsField('src_fid', QVariant.Int))
    fields.append(QgsField('model', QVariant.String))
    fields.append(QgsField('src_group', QVariant.String))
    fields.append(QgsField('park', QVariant.String))
    fields.append(QgsField('layer', QVariant.String))
    fields.append(QgsField('lwa_dba', QVariant.Double))
    fields.append(QgsField('hh_m', QVariant.Double))
    fields.append(QgsField('d_m', QVariant.Double))
    fields.append(QgsField('z_ground', QVariant.Double))
    fields.append(QgsField('n_recv', QVariant.Int))
    fields.append(QgsField('max_lp_db', QVariant.Double))
    fields.append(QgsField('near_rec_m', QVariant.Double))
    fields.append(QgsField('dom_rec_id', QVariant.Int))
    pr.addAttributes(fields)
    lyr.updateFields()
    feats=[]
    for i, src in enumerate(sources):
        st = src_stats.get(i, {})
        f = QgsFeature(fields)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(src.x, src.y)))
        f.setAttributes([
            int(i), int(src.feature_id), src.model_name, src.source_group, src.park_name, src.layer_name, float(src.lwa),
            float(src.hub_height), None if src.diameter is None else float(src.diameter),
            None if src.z_ground is None else float(src.z_ground),
            int(st.get('n_recv', 0)),
            None if st.get('max_lp_db') is None else float(st.get('max_lp_db')),
            None if st.get('near_rec_m') is None else float(st.get('near_rec_m')),
            None if st.get('dom_rec_id') is None else int(st.get('dom_rec_id')),
        ])
        feats.append(f)
    pr.addFeatures(feats)
    prj.addMapLayer(lyr)
    _set_field_aliases(lyr, {'src_group':'source_group','park':'wind_farm','lwa_dba':'lwa_modelo_dba','n_recv':'affected_receivers','max_lp_db':'max_contribution_dba','near_rec_m':'nearest_receiver_m','dom_rec_id':'critical_receiver_id'})
    return lyr


def _build_dominant_links_layer(prj: QgsProject, links: List[Dict[str, object]], layer_name: str) -> Optional[QgsVectorLayer]:
    _remove_existing_layers_by_name(prj, [layer_name])
    lyr = QgsVectorLayer(f"LineString?crs={prj.crs().authid() or 'EPSG:25830'}", layer_name, 'memory')
    pr = lyr.dataProvider()
    fields = QgsFields()
    fields.append(QgsField('rec_id', QVariant.Int))
    fields.append(QgsField('src_id', QVariant.Int))
    fields.append(QgsField('model', QVariant.String))
    fields.append(QgsField('src_group', QVariant.String))
    fields.append(QgsField('park', QVariant.String))
    fields.append(QgsField('lp_dom_db', QVariant.Double))
    fields.append(QgsField('dist_m', QVariant.Double))
    fields.append(QgsField('dist3d_m', QVariant.Double))
    fields.append(QgsField('src_lwa', QVariant.Double))
    fields.append(QgsField('adiv_db', QVariant.Double))
    fields.append(QgsField('aatm_db', QVariant.Double))
    fields.append(QgsField('aground_db', QVariant.Double))
    fields.append(QgsField('ground_g', QVariant.Double))
    pr.addAttributes(fields)
    lyr.updateFields()
    feats=[]
    for ln in links:
        geom = QgsGeometry.fromPolylineXY([QgsPointXY(float(ln['src_x']), float(ln['src_y'])), QgsPointXY(float(ln['rec_x']), float(ln['rec_y']))])
        f=QgsFeature(fields)
        f.setGeometry(geom)
        f.setAttributes([int(ln['rec_id']), int(ln['src_id']), str(ln['model']), str(ln.get('source_group','')), str(ln.get('park_name','')), float(ln['lp_dom_db']), float(ln['dist_m']), None if ln.get('dist3d_m') is None else float(ln['dist3d_m']), None if ln.get('src_lwa') is None else float(ln['src_lwa']), None if ln.get('adiv_db') is None else float(ln['adiv_db']), None if ln.get('aatm_db') is None else float(ln['aatm_db']), None if ln.get('aground_db') is None else float(ln['aground_db']), None if ln.get('ground_g') is None else float(ln['ground_g'])])
        feats.append(f)
    pr.addFeatures(feats)
    prj.addMapLayer(lyr)
    _set_field_aliases(lyr, {'src_group':'source_group','park':'wind_farm','lp_dom_db':'dominant_contribution_dba','dist_m':'source_receiver_2d_m','dist3d_m':'source_receiver_3d_m','src_lwa':'source_lwa_dba','adiv_db':'divergence_loss_db','aatm_db':'atmospheric_loss_db','aground_db':'ground_loss_db','ground_g':'ground_factor_g'})
    return lyr




def _apply_raster_heatmap_style(layer: QgsRasterLayer, min_val: float, max_val: float) -> None:
    try:
        provider = layer.dataProvider()
        shader = QgsRasterShader()
        color_shader = QgsColorRampShader()
        color_shader.setColorRampType(QgsColorRampShader.Interpolated)
        if not math.isfinite(min_val) or not math.isfinite(max_val) or max_val <= min_val:
            min_val, max_val = 0.0, 60.0
        items = [
            QgsColorRampShader.ColorRampItem(float(min_val), QtGui.QColor(49, 163, 84), f"{min_val:.1f}"),
            QgsColorRampShader.ColorRampItem(float(min_val + 0.5 * (max_val - min_val)), QtGui.QColor(255, 255, 102), "medio"),
            QgsColorRampShader.ColorRampItem(float(max_val), QtGui.QColor(215, 48, 39), f"{max_val:.1f}"),
        ]
        color_shader.setColorRampItemList(items)
        shader.setRasterShaderFunction(color_shader)
        renderer = QgsSingleBandPseudoColorRenderer(provider, 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
    except Exception:
        pass


def _apply_line_style(layer: QgsVectorLayer) -> None:
    try:
        sym = layer.renderer().symbol()
        sym.setWidth(0.8)
    except Exception:
        pass


def _build_isophones_layer_from_raster(prj: QgsProject, raster_path: str, levels: List[float], layer_name: str) -> Optional[QgsVectorLayer]:
    levels = sorted({float(v) for v in levels if math.isfinite(float(v))})
    if not raster_path or not levels:
        return None
    _remove_existing_layers_by_name(prj, [layer_name])
    tmpdir = os.path.join(tempfile.gettempdir(), 'velantis_noise')
    os.makedirs(tmpdir, exist_ok=True)
    out_path = _unique_temp_output(tmpdir, layer_name.replace(' · ', '_').replace(' ', '_'), '.gpkg')
    src_ds = gdal.Open(raster_path)
    if src_ds is None:
        return None
    band = src_ds.GetRasterBand(1)
    drv = ogr.GetDriverByName('GPKG')
    dst_ds = drv.CreateDataSource(out_path)
    if dst_ds is None:
        return None
    srs = osr.SpatialReference()
    try:
        srs.ImportFromWkt(prj.crs().toWkt())
    except Exception:
        srs = None
    dst_layer = dst_ds.CreateLayer('isophones', srs, ogr.wkbLineString)
    fld = ogr.FieldDefn('level_db', ogr.OFTReal)
    dst_layer.CreateField(fld)
    try:
        # Python GDAL bindings expect the fixed contour levels as a sequence,
        # not as (count, levels). Passing len(levels) here triggers the runtime
        # error: 'not a sequence'.
        gdal.ContourGenerate(band, 0.0, 0.0, tuple(levels), 0, 0.0, dst_layer, -1, 0)
    except Exception as e:
        try:
            _log(f"[NOISE][ISO][WARN] No se pudieron generar las isófonas con GDAL: {e}")
        except Exception:
            pass
        dst_ds = None
        src_ds = None
        return None
    dst_ds = None
    src_ds = None
    lyr = QgsVectorLayer(out_path + '|layername=isophones', layer_name, 'ogr')
    if not lyr.isValid():
        return None
    try:
        lyr.setCustomProperty('velantis/noise_output', True)
    except Exception:
        pass
    _apply_line_style(lyr)
    prj.addMapLayer(lyr)
    return lyr


def _build_uncovered_receivers_layer(prj: QgsProject, receivers: List[NoiseReceiver], uncovered_ids: List[int], layer_name: str) -> Optional[QgsVectorLayer]:
    if not uncovered_ids:
        return None
    _remove_existing_layers_by_name(prj, [layer_name])
    lyr = QgsVectorLayer(f"Point?crs={prj.crs().authid() or 'EPSG:25830'}", layer_name, 'memory')
    pr = lyr.dataProvider()
    fields = QgsFields()
    fields.append(QgsField('rec_id', QVariant.Int))
    fields.append(QgsField('reason', QVariant.String))
    pr.addAttributes(fields)
    lyr.updateFields()
    feats=[]
    wanted=set(int(x) for x in uncovered_ids)
    for rec in receivers:
        if int(rec.feature_id) not in wanted:
            continue
        f=QgsFeature(fields)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(rec.x, rec.y)))
        f.setAttributes([int(rec.feature_id), 'sin fuentes dentro del radio'])
        feats.append(f)
    pr.addFeatures(feats)
    try:
        lyr.setCustomProperty('velantis/noise_output', True)
    except Exception:
        pass
    prj.addMapLayer(lyr)
    return lyr
