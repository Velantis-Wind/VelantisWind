# -*- coding: utf-8 -*-
"""Validation helpers for the shadow-flicker module."""

from __future__ import annotations

from typing import List

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes

from .domain import ShadowRunConfig
from .i18n_local import tr4 as _ml


def validate_shadow_run_config(config: ShadowRunConfig) -> List[str]:
    """Return a list of blocking validation errors for a shadow run."""

    errors: List[str] = []
    prj = QgsProject.instance()

    if not config.turbine_layer_id:
        errors.append(_ml("Selecciona una capa de aerogeneradores.", "Select a wind-turbine layer.", "Sélectionnez une couche d’éoliennes.", "Wählen Sie einen Windturbinen-Layer aus."))
    else:
        lyr = prj.mapLayer(config.turbine_layer_id)
        if lyr is None:
            errors.append(_ml("No se encontró la capa de aerogeneradores en el proyecto QGIS actual.", "The wind-turbine layer was not found in the current QGIS project.", "Couche d’éoliennes introuvable dans le projet QGIS actuel.", "Der Windturbinen-Layer wurde im aktuellen QGIS-Projekt nicht gefunden."))
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append(_ml("La capa de aerogeneradores seleccionada no es una capa vectorial.", "The selected wind-turbine layer is not a vector layer.", "La couche d’éoliennes sélectionnée n’est pas une couche vectorielle.", "Der ausgewählte Windturbinen-Layer ist kein Vektor-Layer."))
        elif lyr.featureCount() <= 0:
            errors.append(_ml("La capa de aerogeneradores seleccionada no contiene entidades.", "The selected wind-turbine layer contains no features.", "La couche d’éoliennes sélectionnée ne contient aucune entité.", "Der ausgewählte Windturbinen-Layer enthält keine Features."))
        elif QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            errors.append(_ml("La capa de aerogeneradores debe contener geometrías de punto.", "The wind-turbine layer must contain point geometries.", "La couche d’éoliennes doit contenir des géométries ponctuelles.", "Der Windturbinen-Layer muss Punktgeometrien enthalten."))

    if not config.receiver_layer_id:
        errors.append(_ml("Selecciona una capa de receptores.", "Select a receiver layer.", "Sélectionnez une couche de récepteurs.", "Wählen Sie einen Rezeptor-Layer aus."))
    else:
        lyr = prj.mapLayer(config.receiver_layer_id)
        if lyr is None:
            errors.append(_ml("No se encontró la capa de receptores en el proyecto QGIS actual.", "The receiver layer was not found in the current QGIS project.", "Couche de récepteurs introuvable dans le projet QGIS actuel.", "Der Rezeptor-Layer wurde im aktuellen QGIS-Projekt nicht gefunden."))
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append(_ml("La capa de receptores seleccionada no es una capa vectorial.", "The selected receiver layer is not a vector layer.", "La couche de récepteurs sélectionnée n’est pas une couche vectorielle.", "Der ausgewählte Rezeptor-Layer ist kein Vektor-Layer."))
        elif lyr.featureCount() <= 0:
            errors.append(_ml("La capa de receptores seleccionada no contiene entidades.", "The selected receiver layer contains no features.", "La couche de récepteurs sélectionnée ne contient aucune entité.", "Der ausgewählte Rezeptor-Layer enthält keine Features."))

    if config.dem_layer_id:
        dem = prj.mapLayer(config.dem_layer_id)
        if dem is None:
            errors.append(_ml("No se encontró la capa MDT/DEM seleccionada; actualiza el módulo de sombras.", "The selected DEM/DTM layer was not found; refresh the shadow module.", "La couche MDT/DEM sélectionnée est introuvable ; actualisez le module d’ombres.", "Der ausgewählte DGM/DEM-Layer wurde nicht gefunden; aktualisieren Sie das Schattenwurfmodul."))
        elif not isinstance(dem, QgsRasterLayer):
            errors.append(_ml("La entrada MDT/DEM seleccionada no es una capa raster.", "The selected DEM/DTM entry is not a raster layer.", "L’entrée MDT/DEM sélectionnée n’est pas une couche raster.", "Der ausgewählte DGM/DEM-Eintrag ist kein Raster-Layer."))
        elif not dem.isValid():
            errors.append(_ml("El raster MDT/DEM seleccionado no es válido.", "The selected DEM/DTM raster is not valid.", "Le raster MDT/DEM sélectionné n’est pas valide.", "Das ausgewählte DGM/DEM-Raster ist nicht gültig."))

    if not (-90.0 <= config.latitude <= 90.0):
        errors.append(_ml("La latitud debe estar entre -90° y 90°.", "Latitude must be between -90° and 90°.", "La latitude doit être comprise entre -90° et 90°.", "Der Breitengrad muss zwischen -90° und 90° liegen."))
    if not (-180.0 <= config.longitude <= 180.0):
        errors.append(_ml("La longitud debe estar entre -180° y 180°.", "Longitude must be between -180° and 180°.", "La longitude doit être comprise entre -180° et 180°.", "Der Längengrad muss zwischen -180° und 180° liegen."))
    if config.time_step_minutes <= 0:
        errors.append(_ml("El paso temporal de receptores debe ser mayor que 0 minutos.", "The receiver time step must be greater than 0 minutes.", "Le pas temporel des récepteurs doit être supérieur à 0 minute.", "Der Zeitschritt der Rezeptoren muss größer als 0 Minuten sein."))
    if config.max_shadow_distance_m <= 0:
        errors.append(_ml("La distancia máxima de sombra debe ser mayor que 0 m.", "The maximum shadow distance must be greater than 0 m.", "La distance maximale d’ombre doit être supérieure à 0 m.", "Die maximale Schattenentfernung muss größer als 0 m sein."))
    if config.raster_resolution_m <= 0:
        errors.append(_ml("La resolución del raster debe ser mayor que 0 m.", "Raster resolution must be greater than 0 m.", "La résolution du raster doit être supérieure à 0 m.", "Die Rasterauflösung muss größer als 0 m sein."))
    if config.raster_timestep_minutes <= 0:
        errors.append(_ml("El paso temporal del raster debe ser mayor que 0 minutos.", "The raster time step must be greater than 0 minutes.", "Le pas temporel du raster doit être supérieur à 0 minute.", "Der Raster-Zeitschritt muss größer als 0 Minuten sein."))
    if config.observer_height_m < 0:
        errors.append(_ml("La altura del observador no puede ser negativa.", "Observer height cannot be negative.", "La hauteur de l’observateur ne peut pas être négative.", "Die Beobachterhöhe darf nicht negativ sein."))
    if config.min_sun_elevation_deg >= config.max_sun_elevation_deg:
        errors.append(_ml("La elevación solar mínima debe ser menor que la elevación solar máxima.", "Minimum solar elevation must be lower than maximum solar elevation.", "L’élévation solaire minimale doit être inférieure à l’élévation solaire maximale.", "Die minimale Sonnenhöhe muss kleiner als die maximale Sonnenhöhe sein."))
    if not (0.0 <= config.turbine_availability <= 1.0):
        errors.append(_ml("La disponibilidad de los aerogeneradores debe estar entre 0 y 1.", "Wind-turbine availability must be between 0 and 1.", "La disponibilité des éoliennes doit être comprise entre 0 et 1.", "Die Verfügbarkeit der Windturbinen muss zwischen 0 und 1 liegen."))
    if config.use_parallel and config.num_workers < 1:
        errors.append(_ml("El modo paralelo necesita al menos un worker.", "Parallel mode requires at least one worker.", "Le mode parallèle nécessite au moins un worker.", "Der Parallelmodus benötigt mindestens einen Worker."))

    return errors
