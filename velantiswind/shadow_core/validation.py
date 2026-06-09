# -*- coding: utf-8 -*-
"""Validation helpers for the shadow-flicker module."""

from __future__ import annotations

from typing import List

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes

from .domain import ShadowRunConfig


def validate_shadow_run_config(config: ShadowRunConfig) -> List[str]:
    """Return a list of blocking validation errors for a shadow run."""

    errors: List[str] = []
    prj = QgsProject.instance()

    if not config.turbine_layer_id:
        errors.append("Select a turbine layer.")
    else:
        lyr = prj.mapLayer(config.turbine_layer_id)
        if lyr is None:
            errors.append("Turbine layer not found in the current QGIS project.")
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append("The selected turbine layer is not a vector layer.")
        elif lyr.featureCount() <= 0:
            errors.append("The selected turbine layer has no features.")
        elif QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            errors.append("The turbine layer must contain point geometries.")

    if not config.receiver_layer_id:
        errors.append("Select a receiver layer.")
    else:
        lyr = prj.mapLayer(config.receiver_layer_id)
        if lyr is None:
            errors.append("Receiver layer not found in the current QGIS project.")
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append("The selected receiver layer is not a vector layer.")
        elif lyr.featureCount() <= 0:
            errors.append("The selected receiver layer has no features.")

    if config.dem_layer_id:
        dem = prj.mapLayer(config.dem_layer_id)
        if dem is None:
            errors.append("The selected DEM/DSM layer was not found; refresh the shadow module.")
        elif not isinstance(dem, QgsRasterLayer):
            errors.append("The selected DEM/DSM input is not a raster layer.")
        elif not dem.isValid():
            errors.append("The selected DEM/DSM raster is not valid.")

    if not (-90.0 <= config.latitude <= 90.0):
        errors.append("Latitude must be between -90° and 90°.")
    if not (-180.0 <= config.longitude <= 180.0):
        errors.append("Longitude must be between -180° and 180°.")
    if config.time_step_minutes <= 0:
        errors.append("The receiver time step must be greater than 0 minutes.")
    if config.max_shadow_distance_m <= 0:
        errors.append("The maximum shadow distance must be greater than 0 m.")
    if config.raster_resolution_m <= 0:
        errors.append("The raster resolution must be greater than 0 m.")
    if config.raster_timestep_minutes <= 0:
        errors.append("The raster time step must be greater than 0 minutes.")
    if config.observer_height_m < 0:
        errors.append("Observer height cannot be negative.")
    if config.min_sun_elevation_deg >= config.max_sun_elevation_deg:
        errors.append("Minimum sun elevation must be lower than maximum sun elevation.")
    if not (0.0 <= config.turbine_availability <= 1.0):
        errors.append("Turbine availability must be between 0 and 1.")
    if config.use_parallel and config.num_workers < 1:
        errors.append("Parallel mode requires at least one worker.")

    return errors
