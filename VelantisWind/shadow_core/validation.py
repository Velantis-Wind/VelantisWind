# -*- coding: utf-8 -*-
"""Validation helpers for the shadow-flicker module."""

from __future__ import annotations

from typing import List

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes

from .domain import ShadowRunConfig
try:
    from ..i18n import current_language
except Exception:
    def current_language(): return "fr"

def _is_de() -> bool:
    return str(current_language()).lower().startswith("de")

def _msg(fr: str, de: str) -> str:
    return de if _is_de() else fr


def validate_shadow_run_config(config: ShadowRunConfig) -> List[str]:
    """Return a list of blocking validation errors for a shadow run."""

    errors: List[str] = []
    prj = QgsProject.instance()

    if not config.turbine_layer_id:
        errors.append(_msg("Sélectionnez une couche d’éoliennes.", "Wählen Sie einen Windturbinen-Layer aus."))
    else:
        lyr = prj.mapLayer(config.turbine_layer_id)
        if lyr is None:
            errors.append(_msg("Couche d’éoliennes introuvable dans le projet QGIS actuel.", "Der Windturbinen-Layer wurde im aktuellen QGIS-Projekt nicht gefunden."))
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append(_msg("La couche d’éoliennes sélectionnée n’est pas une couche vectorielle.", "Der ausgewählte Windturbinen-Layer ist kein Vektor-Layer."))
        elif lyr.featureCount() <= 0:
            errors.append(_msg("La couche d’éoliennes sélectionnée ne contient aucune entité.", "Der ausgewählte Windturbinen-Layer enthält keine Features."))
        elif QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            errors.append(_msg("La couche d’éoliennes doit contenir des géométries ponctuelles.", "Der Windturbinen-Layer muss Punktgeometrien enthalten."))

    if not config.receiver_layer_id:
        errors.append(_msg("Sélectionnez une couche de récepteurs.", "Wählen Sie einen Rezeptor-Layer aus."))
    else:
        lyr = prj.mapLayer(config.receiver_layer_id)
        if lyr is None:
            errors.append(_msg("Couche de récepteurs introuvable dans le projet QGIS actuel.", "Der Rezeptor-Layer wurde im aktuellen QGIS-Projekt nicht gefunden."))
        elif not isinstance(lyr, QgsVectorLayer):
            errors.append(_msg("La couche de récepteurs sélectionnée n’est pas une couche vectorielle.", "Der ausgewählte Rezeptor-Layer ist kein Vektor-Layer."))
        elif lyr.featureCount() <= 0:
            errors.append(_msg("La couche de récepteurs sélectionnée ne contient aucune entité.", "Der ausgewählte Rezeptor-Layer enthält keine Features."))

    if config.dem_layer_id:
        dem = prj.mapLayer(config.dem_layer_id)
        if dem is None:
            errors.append(_msg("La couche MDT/DSM sélectionnée est introuvable ; actualisez le module d’ombres.", "Der ausgewählte DGM/DSM-Layer wurde nicht gefunden; aktualisieren Sie das Schattenwurfmodul."))
        elif not isinstance(dem, QgsRasterLayer):
            errors.append(_msg("L’entrée MDT/DSM sélectionnée n’est pas une couche raster.", "Der ausgewählte DGM/DSM-Eintrag ist kein Raster-Layer."))
        elif not dem.isValid():
            errors.append(_msg("Le raster MDT/DSM sélectionné n’est pas valide.", "Das ausgewählte DGM/DSM-Raster ist nicht gültig."))

    if not (-90.0 <= config.latitude <= 90.0):
        errors.append(_msg("La latitude doit être comprise entre -90° et 90°.", "Der Breitengrad muss zwischen -90° und 90° liegen."))
    if not (-180.0 <= config.longitude <= 180.0):
        errors.append(_msg("La longitude doit être comprise entre -180° et 180°.", "Der Längengrad muss zwischen -180° und 180° liegen."))
    if config.time_step_minutes <= 0:
        errors.append(_msg("Le pas temporel des récepteurs doit être supérieur à 0 minute.", "Der Zeitschritt der Rezeptoren muss größer als 0 Minuten sein."))
    if config.max_shadow_distance_m <= 0:
        errors.append(_msg("La distance maximale d’ombre doit être supérieure à 0 m.", "Die maximale Schattenentfernung muss größer als 0 m sein."))
    if config.raster_resolution_m <= 0:
        errors.append(_msg("La résolution du raster doit être supérieure à 0 m.", "Die Rasterauflösung muss größer als 0 m sein."))
    if config.raster_timestep_minutes <= 0:
        errors.append(_msg("Le pas temporel du raster doit être supérieur à 0 minute.", "Der Raster-Zeitschritt muss größer als 0 Minuten sein."))
    if config.observer_height_m < 0:
        errors.append(_msg("La hauteur de l’observateur ne peut pas être négative.", "Die Beobachterhöhe darf nicht negativ sein."))
    if config.min_sun_elevation_deg >= config.max_sun_elevation_deg:
        errors.append(_msg("L’élévation solaire minimale doit être inférieure à l’élévation solaire maximale.", "Die minimale Sonnenhöhe muss kleiner als die maximale Sonnenhöhe sein."))
    if not (0.0 <= config.turbine_availability <= 1.0):
        errors.append(_msg("La disponibilité des éoliennes doit être comprise entre 0 et 1.", "Die Verfügbarkeit der Windturbinen muss zwischen 0 und 1 liegen."))
    if config.use_parallel and config.num_workers < 1:
        errors.append(_msg("Le mode parallèle nécessite au moins un worker.", "Der Parallelmodus benötigt mindestens einen Worker."))

    return errors
