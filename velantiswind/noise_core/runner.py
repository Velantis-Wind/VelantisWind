# -*- coding: utf-8 -*-
"""Runner facade for noise calculations.

The calculation façade still lives in ``noise_compute.py``. This class is the
public entry point used by the UI/controller so we can keep extracting internals
behind a stable experimental release entry point.
"""
from __future__ import annotations

from typing import Dict, Any

from .domain import NoiseRunConfig, NoiseRunResult
from .validation import validate_run_config
from .noise_compute import compute_noise


class NoiseRunner:
    """Validate and run one noise analysis."""

    def run(self, config: NoiseRunConfig) -> NoiseRunResult:
        errors, _warnings = validate_run_config(config)
        if errors:
            raise ValueError("Configuración acústica inválida:\n- " + "\n- ".join(errors[:12]))

        raw: Dict[str, Any] = compute_noise(
            receiver_layer=config.receiver_layer,
            model_cfg=config.model_cfg,
            source_layer_ids=config.source_layer_ids,
            receiver_height_m=config.receiver_height_m,
            max_radius_m=config.max_radius_m,
            dem_layer=config.dem_layer,
            alpha_db_per_m=config.alpha_db_per_m,
            ground_factor_g=config.ground_factor_g,
            ground_mode=config.ground_mode,
            landuse_layer=config.landuse_layer,
            receiver_limit_dba=config.receiver_limit_dba,
            receiver_limit_mode=config.receiver_limit_mode,
            receiver_limit_scenario=config.receiver_limit_scenario,
            receiver_limit_field_day=config.receiver_limit_field_day,
            receiver_limit_field_night=config.receiver_limit_field_night,
            receiver_limit_field_custom=config.receiver_limit_field_custom,
            receiver_type_field=config.receiver_type_field,
            receiver_height_field=config.receiver_height_field,
            receiver_source_field=config.receiver_source_field,
            min_distance_m=config.min_distance_m,
            result_layer_name=config.result_layer_name,
            sources_layer_name=config.sources_layer_name,
            links_layer_name=config.links_layer_name,
            grid_layer_name=config.grid_layer_name,
            iso_layer_name=config.iso_layer_name,
            uncovered_layer_name=config.uncovered_layer_name,
            create_sources_layer=config.create_sources_layer,
            create_links_layer=config.create_links_layer,
            create_grid_layer=config.create_grid_layer,
            create_iso_layer=config.create_iso_layer,
            iso_levels=config.iso_levels,
            grid_resolution_m=config.grid_resolution_m,
            calculation_engine=config.calculation_engine,
            temperature_c=config.temperature_c,
            humidity_percent=config.humidity_percent,
            pressure_kpa=config.pressure_kpa,
        )
        return NoiseRunResult(raw=raw)
