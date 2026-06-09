# -*- coding: utf-8 -*-
"""Read the Noise page state and build ``NoiseRunConfig``.

The dialog class owns widgets and user interaction.  This module converts the
current widget/layer state into a typed configuration object used by the runner.
Keeping this logic outside the Qt page makes the public plugin easier to test and
reduces coupling between UI layout code and the acoustic calculation workflow.
"""
from __future__ import annotations

from typing import List, Tuple

from qgis.PyQt import QtCore
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from .domain import NoiseRunConfig
from .noise_common import log as _log


def _parse_iso_levels(text: str) -> List[float]:
    levels: List[float] = []
    for tok in (text or "").replace(";", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            levels.append(float(tok))
        except Exception:
            continue
    return levels or [35.0, 40.0, 45.0, 50.0]


def _prepare_receiver_context(dialog) -> Tuple[QgsVectorLayer, str, str, str, str, str, str, str, str]:
    receiver_limit_mode = "global"
    receiver_limit_scenario = "custom"
    receiver_height_field = None
    receiver_type_field = None
    receiver_limit_field_day = None
    receiver_limit_field_night = None
    receiver_limit_field_custom = None
    receiver_source_field = None

    if dialog.chk_multi_receivers.isChecked():
        receiver_layer, n_multi = dialog._build_multi_receiver_layer()
        if receiver_layer is None or n_multi <= 0:
            raise ValueError("Configura al menos una capa válida en la tabla de receptores por categoría.")
        receiver_limit_mode = "by_field"
        receiver_limit_scenario = str(dialog.cb_limit_scenario.currentData(QtCore.Qt.UserRole) or "day")
        receiver_height_field = "grp_h_m"
        receiver_type_field = "grp_type"
        receiver_limit_field_day = "grp_lim_d"
        receiver_limit_field_night = "grp_lim_n"
        receiver_limit_field_custom = "grp_lim_c"
        receiver_source_field = "grp_src"
        _log(f"UI multi-receiver context: {n_multi} normalized receiver(s) from {dialog.tbl_receiver_groups.rowCount()} row(s).")
    else:
        receiver_id = dialog.cb_receivers.currentData(QtCore.Qt.UserRole)
        receiver_layer = QgsProject.instance().mapLayer(receiver_id) if receiver_id else None
        if not isinstance(receiver_layer, QgsVectorLayer):
            raise ValueError("Selecciona una capa válida de receptores.")

    return (
        receiver_layer,
        receiver_limit_mode,
        receiver_limit_scenario,
        receiver_height_field,
        receiver_type_field,
        receiver_limit_field_day,
        receiver_limit_field_night,
        receiver_limit_field_custom,
        receiver_source_field,
    )


def build_config_from_dialog(dialog) -> NoiseRunConfig:
    (
        receiver_layer,
        receiver_limit_mode,
        receiver_limit_scenario,
        receiver_height_field,
        receiver_type_field,
        receiver_limit_field_day,
        receiver_limit_field_night,
        receiver_limit_field_custom,
        receiver_source_field,
    ) = _prepare_receiver_context(dialog)

    dem_id = dialog.cb_dem.currentData(QtCore.Qt.UserRole)
    dem_layer = QgsProject.instance().mapLayer(dem_id) if dem_id else None
    if dem_layer is not None and not isinstance(dem_layer, QgsRasterLayer):
        dem_layer = None

    landuse_id = dialog.cb_landuse.currentData(QtCore.Qt.UserRole)
    landuse_layer = QgsProject.instance().mapLayer(landuse_id) if landuse_id else None
    if landuse_layer is not None and not isinstance(landuse_layer, QgsVectorLayer):
        landuse_layer = None

    acoustic_mode = dialog._current_acoustic_mode()
    dialog._acoustic_mode_state = acoustic_mode
    dialog._qsettings.setValue("noise/acoustic_mode", acoustic_mode)
    model_cfg = dialog._collect_model_cfg()

    try:
        _log(
            f"UI acoustic scenario: {acoustic_mode} | "
            f"text='{dialog.cb_acoustic_mode.currentText()}' | idx={dialog.cb_acoustic_mode.currentIndex()} | "
            f"ws={float(dialog.sp_eval_ws.value()):.1f} | worst={bool(dialog.chk_curve_worst.isChecked())}"
        )
        for model_name, cfg in model_cfg.items():
            _log(
                f"UI model={model_name} | acoustic_mode={cfg.get('acoustic_mode')} | "
                f"curve_path={cfg.get('curve_path','')} | fixed_lwa={cfg.get('lwa')}"
            )
    except Exception:
        pass

    return NoiseRunConfig(
        receiver_layer=receiver_layer,
        model_cfg=model_cfg,
        source_layer_ids=dialog._selected_source_layer_ids(),
        receiver_height_m=float(dialog.sp_receiver_h.value()),
        max_radius_m=float(dialog.sp_max_radius.value()),
        dem_layer=dem_layer,
        alpha_db_per_m=float(dialog.sp_alpha.value()),
        ground_factor_g=float(dialog.sp_ground_g.value()),
        ground_mode=str(dialog.cb_ground_mode.currentData(QtCore.Qt.UserRole) or "global"),
        landuse_layer=landuse_layer,
        receiver_limit_dba=float(dialog.sp_limit.value()),
        receiver_limit_mode=str(receiver_limit_mode),
        receiver_limit_scenario=str(receiver_limit_scenario),
        receiver_limit_field_day=receiver_limit_field_day,
        receiver_limit_field_night=receiver_limit_field_night,
        receiver_limit_field_custom=receiver_limit_field_custom,
        receiver_type_field=receiver_type_field,
        receiver_height_field=receiver_height_field,
        receiver_source_field=receiver_source_field,
        result_layer_name="Noise · Receivers",
        sources_layer_name="Noise · Sources",
        links_layer_name="Noise · Dominant links",
        grid_layer_name="Noise · Map",
        iso_layer_name="Noise · Isophones",
        create_sources_layer=True,
        create_links_layer=True,
        create_grid_layer=bool(dialog.chk_generate_grid.isChecked()),
        create_iso_layer=bool(dialog.chk_iso.isChecked()),
        iso_levels=_parse_iso_levels(dialog.le_iso_levels.text().strip() or "35,40,45,50"),
        grid_resolution_m=float(dialog.sp_grid_res.value()),
        calculation_engine=str(dialog.cb_engine.currentData(QtCore.Qt.UserRole) or "fast"),
        temperature_c=float(dialog.sp_temperature.value()),
        humidity_percent=float(dialog.sp_humidity.value()),
        pressure_kpa=float(dialog.sp_pressure.value()),
    )
