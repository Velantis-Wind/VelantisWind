# -*- coding: utf-8 -*-
"""Summary/statistics helpers for noise result layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from qgis.core import QgsVectorLayer


@dataclass
class NoiseLayerStats:
    adiv_vals: List[float] = field(default_factory=list)
    aatm_vals: List[float] = field(default_factory=list)
    aground_vals: List[float] = field(default_factory=list)
    abar_vals: List[float] = field(default_factory=list)
    critical_receiver: Optional[Dict[str, Any]] = None


def extract_result_layer_statistics(result: QgsVectorLayer, max_noise_fid: Optional[int]) -> NoiseLayerStats:
    """Extract reporting statistics from the receiver result layer.

    The result-layer feature ids are not always the original receiver ids,
    especially when results are reconstructed from a background QgsTask.  For
    that reason the critical receiver is resolved in three steps:

    1. try to match ``max_noise_fid`` against the QGIS feature id;
    2. try to match it against receiver-id-like fields if present;
    3. fall back to the highest ``noise_dba`` feature in the result layer.

    This keeps the visual report robust when schemas are extended with new MDT
    diagnostic columns.
    """
    stats = NoiseLayerStats()
    if not isinstance(result, QgsVectorLayer):
        return stats

    def _fields(feat):
        try:
            return feat.fields()
        except Exception:
            return None

    def _has(feat, name: str) -> bool:
        try:
            fs = _fields(feat)
            return fs is not None and fs.indexFromName(name) >= 0
        except Exception:
            return False

    def _val(feat, name: str, default=None):
        if not _has(feat, name):
            return default
        try:
            v = feat[name]
            return default if v is None else v
        except Exception:
            return default

    def _float(feat, name: str, default=float('nan')):
        try:
            return float(_val(feat, name, default))
        except Exception:
            return default

    def _int(feat, name: str, default=None):
        try:
            v = _val(feat, name, default)
            return default if v is None else int(v)
        except Exception:
            return default

    def _is_covered(feat) -> bool:
        # Prefer the explicit field. If older/broken layers do not contain it,
        # use a positive level / at least one source as a safe fallback.
        try:
            return int(_val(feat, 'covered', 0)) == 1
        except Exception:
            pass
        try:
            return float(_val(feat, 'noise_dba', 0.0) or 0.0) > 0.0
        except Exception:
            return False

    def _receiver_id_candidates(feat) -> List[int]:
        vals: List[int] = []
        try:
            vals.append(int(feat.id()))
        except Exception:
            pass
        for name in ('rec_id', 'receiver_id', 'id', 'fid'):
            try:
                if _has(feat, name):
                    vals.append(int(_val(feat, name)))
            except Exception:
                pass
        return vals

    def _critical_dict(feat) -> Dict[str, Any]:
        rec_id_val = None
        for name in ('rec_id', 'receiver_id', 'id', 'fid'):
            try:
                if _has(feat, name):
                    rec_id_val = int(_val(feat, name))
                    break
            except Exception:
                pass
        if rec_id_val is None:
            try:
                rec_id_val = int(feat.id())
            except Exception:
                rec_id_val = -1
        return {
            'rec_id': rec_id_val,
            'total_level_dba': _float(feat, 'noise_dba'),
            'limit_margin_db': _float(feat, 'margin_db'),
            'modelo_dominante': str(_val(feat, 'dom_model', '')),
            'grupo_fuente_dominante': str(_val(feat, 'dom_group', '')),
            'parque_dominante': str(_val(feat, 'dom_park', '')),
            'turbines_in_radius': _int(feat, 'n_src', 0),
            'lwa_fuente_dom_dba': _float(feat, 'src_lwa'),
            'dist_fuente_dom_3d_m': _float(feat, 'dist3d_m', _float(feat, 'near_m')),
            'divergence_loss_db': _float(feat, 'adiv_db'),
            'atmospheric_loss_db': _float(feat, 'aatm_db'),
            'ground_loss_db': _float(feat, 'aground_db'),
            'barrier_loss_db': _float(feat, 'abar_db'),
            'barrier_loss_max_contributors_db': _float(feat, 'abar_max_db', _float(feat, 'abar_db')),
            'barrier_loss_mean_contributors_db': _float(feat, 'abar_mean_db', _float(feat, 'abar_db')),
            'barrier_loss_energy_weighted_db': _float(feat, 'abar_ew_db', _float(feat, 'abar_db')),
            'barrier_screened_sources_n': _int(feat, 'abar_screen_n', 0),
            'mdt_abar_state': str(_val(feat, 'abar_state', '')),
            'mdt_obstacle_height_m': _float(feat, 'obs_h_m', 0.0),
            'mdt_d1_m': _float(feat, 'obs_d1_m', 0.0),
            'mdt_d2_m': _float(feat, 'obs_d2_m', 0.0),
            'mdt_obstacle_threshold_m': _float(feat, 'obs_thr_m', 0.0),
            'dominant_source_ground_z_m': _float(feat, 'src_z_m'),
            'dominant_source_hub_height_m': _float(feat, 'hub_h_m'),
            'dominant_source_acoustic_z_m': _float(feat, 'src_ac_z_m'),
            'receiver_ground_z_m': _float(feat, 'rec_z_m'),
            'receiver_height_agl_m': _float(feat, 'rec_h_m'),
            'receiver_acoustic_z_m': _float(feat, 'rec_ac_z_m'),
            'max_abar_source_index': _int(feat, 'maxab_src', None),
            'max_abar_mdt_state': str(_val(feat, 'maxab_state', '')),
            'max_abar_obstacle_height_m': _float(feat, 'maxab_obs_h', 0.0),
            'max_abar_threshold_m': _float(feat, 'maxab_thr', 0.0),
            'max_abar_source_obstacle_m': _float(feat, 'maxab_d1', 0.0),
            'max_abar_obstacle_receiver_m': _float(feat, 'maxab_d2', 0.0),
            'max_abar_source_ground_z_m': _float(feat, 'maxab_src_z'),
            'max_abar_source_hub_height_m': _float(feat, 'maxab_hub_h'),
            'max_abar_source_acoustic_z_m': _float(feat, 'maxab_src_ac_z'),
            'ground_factor_g': _float(feat, 'ground_g'),
            'banda_dominante_hz': _int(feat, 'dom_freq', None),
            'spectrum_source': str(_val(feat, 'spec_src', '')),
            'motor_calculo': str(_val(feat, 'calc_meth', '')),
            'limite_aplicado_dba': _float(feat, 'limit_dba'),
            'limit_source': str(_val(feat, 'limit_src', '')),
            'limit_scenario': str(_val(feat, 'limit_scn', '')),
        }

    best_feat = None
    best_noise = -1.0e99
    matched_feat = None

    try:
        features = list(result.getFeatures())
    except Exception:
        features = []

    for f in features:
        try:
            noise = _float(f, 'noise_dba', -1.0e99)
            if noise == noise and noise > best_noise:
                best_noise = noise
                best_feat = f
        except Exception:
            pass

        if _is_covered(f):
            for key, target in [
                ('adiv_db', stats.adiv_vals),
                ('aatm_db', stats.aatm_vals),
                ('aground_db', stats.aground_vals),
            ]:
                try:
                    v = _float(f, key)
                    if v == v:
                        target.append(float(v))
                except Exception:
                    pass
            try:
                v_abar = _float(f, 'abar_max_db', _float(f, 'abar_db'))
                if v_abar == v_abar:
                    stats.abar_vals.append(float(v_abar))
            except Exception:
                pass

        if max_noise_fid is not None and matched_feat is None:
            try:
                if int(max_noise_fid) in _receiver_id_candidates(f):
                    matched_feat = f
            except Exception:
                pass

    if matched_feat is not None:
        stats.critical_receiver = _critical_dict(matched_feat)
    elif best_feat is not None:
        stats.critical_receiver = _critical_dict(best_feat)

    return stats
