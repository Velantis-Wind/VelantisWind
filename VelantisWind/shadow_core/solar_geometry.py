# -*- coding: utf-8 -*-
"""
Solar geometry calculations for shadow flicker analysis.
NOAA-based solar position calculations for shadow flicker screening.

References:
- NOAA Solar Calculations: https://www.esrl.noaa.gov/gmd/grad/solcalc/calcdetails.html
- 
"""

import numpy as np
from datetime import datetime
from typing import Tuple, Optional, Union

try:
    from .shadow_common import SUN_ANGULAR_RADIUS_DEG
except Exception:  # permite usar este archivo como script suelto en pruebas
    SUN_ANGULAR_RADIUS_DEG = 0.2725


def get_sun_position(dt: datetime, latitude: float, longitude: float, utc_offset: float) -> Tuple[float, float, bool]:
    """
    Calculate sun position using NOAA equations (NOAA-based).
    
    This is the exact implementation using NOAA solar equations.
    
    Args:
        dt: datetime object (local time)
        latitude: Site latitude in degrees (positive = North)
        longitude: Site longitude in degrees (positive = East, negative = West)
        utc_offset: UTC offset in hours (e.g., +1.0 for CET, -5.0 for EST)
    
    Returns:
        Tuple of (azimuth, altitude, is_sun_up):
            azimuth: Solar azimuth in degrees (0=N, 90=E, 180=S, -90=W)
            altitude: Solar altitude in degrees (0=horizon, 90=zenith)
            is_sun_up: Boolean indicating if sun is above horizon
    """
    degs_to_rad = np.pi / 180.0
    rad_to_degs = 180.0 / np.pi
    
    # Calculate Julian Day
    julian_day = ((dt.year - 1900) * 365.2422) + (dt.timetuple().tm_yday + 1) + 2415018.5 + \
                 dt.hour / 24.0 + dt.minute / (24.0 * 60) - utc_offset / 24.0
    julian_century = (julian_day - 2451545) / 36525
    
    # Mean Longitude (L)
    L = (280.460 + 36000.769 * julian_century) % 360
    
    # Geom Mean Anomaly (M)
    geom_mean_anom = 357.52911 + julian_century * (35999.05029 - 0.0001537 * julian_century)
    
    # Eccentricity of Earth orbit
    eccentric_earth_orbit = 0.016708634 - julian_century * (0.000042037 + 0.0000001267 * julian_century)
    
    # Longitude Anomaly (M) - simplified
    M = (357.528 + 35999.050 * julian_century) % 360
    
    # True/Ecliptic Longitude (lambda)
    lambda_val = (L + (1.915 - 0.005 * julian_century) * np.sin(M * degs_to_rad) + \
                  0.02 * np.sin(2 * M * degs_to_rad)) % 360
    
    # Obliquity (epsilon) - tilt of Earth's axis
    epsilon = 23.452 - 0.013 * julian_century
    
    # Solar Declination (dec)
    dec = np.arcsin(np.sin(lambda_val * degs_to_rad) * np.sin(epsilon * degs_to_rad))
    
    # Equation of Time
    var_y = np.tan(epsilon / 2 * degs_to_rad) * np.tan(epsilon / 2 * degs_to_rad)
    eq_of_time = 4 * rad_to_degs * (
        var_y * np.sin(2 * degs_to_rad * L) - 
        2 * eccentric_earth_orbit * np.sin(degs_to_rad * geom_mean_anom) + 
        4 * eccentric_earth_orbit * var_y * np.sin(degs_to_rad * geom_mean_anom) * np.cos(2 * degs_to_rad * L) - 
        0.5 * var_y * var_y * np.sin(4 * degs_to_rad * L) - 
        1.25 * eccentric_earth_orbit * eccentric_earth_orbit * np.sin(2 * degs_to_rad * geom_mean_anom)
    )
    
    # True Solar Time
    true_solar_time = ((dt.hour / 24.0 + dt.minute / (24.0 * 60)) * 1440 + eq_of_time + \
                      4 * longitude - 60 * utc_offset) % 1440
    
    # Hour Angle
    hour_angle = true_solar_time / 4.0 - 180
    if hour_angle < -180:
        hour_angle = hour_angle + 360
    
    # Solar Altitude
    altitude = np.arcsin(
        np.sin(latitude * degs_to_rad) * np.sin(dec) + \
        np.cos(latitude * degs_to_rad) * np.cos(dec) * np.cos(hour_angle * degs_to_rad)
    ) * rad_to_degs
    
    # Solar Zenith
    cos_zenith = (
        np.sin(degs_to_rad * latitude) * np.sin(dec) +
        np.cos(degs_to_rad * latitude) * np.cos(dec) * np.cos(degs_to_rad * hour_angle)
    )
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    solar_zenith = rad_to_degs * np.arccos(cos_zenith)

    sin_zenith = np.sin(degs_to_rad * solar_zenith)
    if abs(float(sin_zenith)) < 1e-10:
        sin_zenith = 1e-10

    cos_az = ((np.sin(degs_to_rad * latitude) * np.cos(degs_to_rad * solar_zenith)) - np.sin(dec)) / \
             (np.cos(degs_to_rad * latitude) * sin_zenith)
    cos_az = np.clip(cos_az, -1.0, 1.0)

    # Solar Azimuth
    if hour_angle > 0:
        azimuth = (rad_to_degs * np.arccos(cos_az) + 180) % 360
    else:
        azimuth = (540 - rad_to_degs * np.arccos(cos_az)) % 360
    
    # Normalize azimuth to -180 to 180 range
    if azimuth > 180:
        azimuth = azimuth - 360
    
    # Robust horizon criterion. Avoids arccos-domain issues near polar
    # latitudes (midnight sun / polar night) where arccos(-tan(lat)*tan(dec))
    # can receive an argument outside [-1, 1] and return NaN. This matches
    # the criterion already used by the vectorized branch.
    is_sun_up = bool(altitude > 0.0)
    
    return azimuth, altitude, is_sun_up


def _calculate_solar_arrays_from_components(
    years: np.ndarray,
    day_of_year: np.ndarray,
    hours: np.ndarray,
    minutes: np.ndarray,
    latitude: float,
    longitude: float,
    utc_offset: Union[float, np.ndarray] = 0.0,
    times_are_utc: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized NOAA-style solar position from date/time components.

    If ``times_are_utc`` is True, ``hours``/``minutes`` are UTC and the true
    solar time is computed directly from UTC. If False, components are local
    civil/fixed-offset time and ``utc_offset`` is applied with the selected fixed offset.
    """
    degs_to_rad = np.pi / 180.0
    rad_to_degs = 180.0 / np.pi

    years = np.asarray(years, dtype=float)
    day_of_year = np.asarray(day_of_year, dtype=float)
    hours = np.asarray(hours, dtype=float)
    minutes = np.asarray(minutes, dtype=float)

    local_or_utc_minutes = (hours * 60.0) + minutes

    if times_are_utc:
        julian_day = ((years - 1900.0) * 365.2422) + (day_of_year + 1.0) + 2415018.5 + local_or_utc_minutes / 1440.0
    else:
        utc_offset = np.asarray(utc_offset, dtype=float)
        julian_day = ((years - 1900.0) * 365.2422) + (day_of_year + 1.0) + 2415018.5 + local_or_utc_minutes / 1440.0 - utc_offset / 24.0

    julian_century = (julian_day - 2451545.0) / 36525.0

    # Mean longitude and anomaly
    L = (280.460 + 36000.769 * julian_century) % 360.0
    geom_mean_anom = 357.52911 + julian_century * (35999.05029 - 0.0001537 * julian_century)
    eccentric_earth_orbit = 0.016708634 - julian_century * (0.000042037 + 0.0000001267 * julian_century)
    M = (357.528 + 35999.050 * julian_century) % 360.0

    # Ecliptic longitude and obliquity
    lambda_val = (L + (1.915 - 0.005 * julian_century) * np.sin(M * degs_to_rad) +
                  0.02 * np.sin(2.0 * M * degs_to_rad)) % 360.0
    epsilon = 23.452 - 0.013 * julian_century
    dec = np.arcsin(np.sin(lambda_val * degs_to_rad) * np.sin(epsilon * degs_to_rad))

    # Equation of time
    var_y = np.tan(epsilon / 2.0 * degs_to_rad) ** 2
    eq_of_time = 4.0 * rad_to_degs * (
        var_y * np.sin(2.0 * degs_to_rad * L) -
        2.0 * eccentric_earth_orbit * np.sin(degs_to_rad * geom_mean_anom) +
        4.0 * eccentric_earth_orbit * var_y * np.sin(degs_to_rad * geom_mean_anom) * np.cos(2.0 * degs_to_rad * L) -
        0.5 * var_y * var_y * np.sin(4.0 * degs_to_rad * L) -
        1.25 * eccentric_earth_orbit * eccentric_earth_orbit * np.sin(2.0 * degs_to_rad * geom_mean_anom)
    )

    if times_are_utc:
        # NOAA equivalent: local_minutes - 60*tz = UTC_minutes.
        true_solar_time = (local_or_utc_minutes + eq_of_time + 4.0 * longitude) % 1440.0
    else:
        true_solar_time = (local_or_utc_minutes + eq_of_time + 4.0 * longitude - 60.0 * utc_offset) % 1440.0

    hour_angle = true_solar_time / 4.0 - 180.0
    hour_angle = np.where(hour_angle < -180.0, hour_angle + 360.0, hour_angle)

    sin_lat = np.sin(latitude * degs_to_rad)
    cos_lat = np.cos(latitude * degs_to_rad)

    altitude = np.arcsin(
        sin_lat * np.sin(dec) + cos_lat * np.cos(dec) * np.cos(hour_angle * degs_to_rad)
    ) * rad_to_degs

    cos_zenith = sin_lat * np.sin(dec) + cos_lat * np.cos(dec) * np.cos(hour_angle * degs_to_rad)
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    solar_zenith = rad_to_degs * np.arccos(cos_zenith)

    sin_zenith = np.sin(degs_to_rad * solar_zenith)
    sin_zenith = np.where(np.abs(sin_zenith) < 1e-10, 1e-10, sin_zenith)

    cos_az = ((sin_lat * np.cos(degs_to_rad * solar_zenith)) - np.sin(dec)) / (cos_lat * sin_zenith)
    cos_az = np.clip(cos_az, -1.0, 1.0)

    azimuth = np.where(
        hour_angle > 0.0,
        (rad_to_degs * np.arccos(cos_az) + 180.0) % 360.0,
        (540.0 - rad_to_degs * np.arccos(cos_az)) % 360.0,
    )
    azimuth = np.where(azimuth > 180.0, azimuth - 360.0, azimuth)

    # Robust horizon criterion. This avoids arccos domain issues near polar latitudes.
    is_sun_up = altitude > 0.0

    return azimuth, altitude, is_sun_up


def get_sun_positions_vectorized(
    year: int,
    latitude: float,
    longitude: float,
    utc_offset: float,
    time_step_minutes: int = 1,
    timezone_mode: str = "fixed",
    timezone_name: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calcula posiciones solares para TODO el año de una vez.

    Modes:
    - timezone_mode='fixed': fixed-offset fixed UTC offset all year.
    - timezone_mode='iana': local civil time using an IANA zone and DST.

    Returns:
        timestamps: local timestamps used for calendar/table aggregation
        azimuths: solar azimuth [degrees]
        altitudes: solar altitude [degrees]
        is_sun_up: boolean mask
        months_array: local month [1-12]
        hours_array: local civil hour [0-23]
    """
    from datetime import datetime, timedelta, timezone

    mode = (timezone_mode or "fixed").lower().strip()
    step = max(1, int(time_step_minutes))

    if mode == "iana":
        try:
            from .timezone_utils import get_tzinfo
            tz = get_tzinfo(timezone_name or "UTC")
        except Exception as e:
            raise RuntimeError(
                f"No se pudo inicializar la zona horaria IANA '{timezone_name}'. "
                "Instala tzdata en el Python de QGIS/OSGeo4W o usa modo UTC offset fijo. "
                f"Detalle: {e}"
            )

        # Iterate in UTC to avoid nonexistent/duplicated local civil times at DST transitions.
        start_local = datetime(year, 1, 1, 0, 0, tzinfo=tz)
        end_local = datetime(year + 1, 1, 1, 0, 0, tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        total_minutes = int((end_utc - start_utc).total_seconds() / 60)
        n_steps = max(0, total_minutes // step)
        minutes_array = np.arange(n_steps, dtype=np.int64) * step

        dt_utc = [start_utc + timedelta(minutes=int(m)) for m in minutes_array]
        dt_local = [d.astimezone(tz) for d in dt_utc]

        years_arr = np.array([d.year for d in dt_utc], dtype=np.int32)
        day_of_year = np.array([d.timetuple().tm_yday for d in dt_utc], dtype=np.int16)
        hours_utc = np.array([d.hour for d in dt_utc], dtype=np.int8)
        minutes_utc = np.array([d.minute for d in dt_utc], dtype=np.int8)

        azimuth, altitude, is_sun_up = _calculate_solar_arrays_from_components(
            years_arr, day_of_year, hours_utc, minutes_utc,
            latitude=latitude,
            longitude=longitude,
            utc_offset=0.0,
            times_are_utc=True,
        )

        timestamps = np.array([d.replace(tzinfo=None) for d in dt_local], dtype=object)
        months_array = np.array([d.month for d in dt_local], dtype=np.int8)
        hours_array = np.array([d.hour for d in dt_local], dtype=np.int8)

        return timestamps, azimuth, altitude, is_sun_up, months_array, hours_array

    # Fixed-offset mode: preserve the original fixed-offset behaviour.
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    total_minutes = int((end - start).total_seconds() / 60)
    n_steps = total_minutes // step
    minutes_array = np.arange(n_steps, dtype=np.int64) * step

    days_offset = minutes_array // (24 * 60)
    minutes_in_day = minutes_array % (24 * 60)
    hours = (minutes_in_day // 60).astype(np.int8)
    minutes = (minutes_in_day % 60).astype(np.int8)
    day_of_year = (days_offset + 1).astype(np.int16)
    years_arr = np.full(n_steps, year, dtype=np.int32)

    azimuth, altitude, is_sun_up = _calculate_solar_arrays_from_components(
        years_arr, day_of_year, hours, minutes,
        latitude=latitude,
        longitude=longitude,
        utc_offset=float(utc_offset),
        times_are_utc=False,
    )

    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    days_per_month = np.array([31, 29 if is_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    cumulative_days = np.cumsum(days_per_month)
    months_array = np.searchsorted(cumulative_days, day_of_year - 1, side='right') + 1
    months_array = np.clip(months_array, 1, 12).astype(np.int8)
    hours_array = hours.astype(np.int8)
    timestamps = np.array([start + timedelta(minutes=int(m)) for m in minutes_array], dtype=object)

    return timestamps, azimuth, altitude, is_sun_up, months_array, hours_array

def calculate_shadow_vectorized(
    sun_azimuths: np.ndarray,
    sun_altitudes: np.ndarray,
    is_sun_up: np.ndarray,
    target_azimuth: float,
    target_altitude: float,
    angle_variance: float,
    min_elevation: float = 3.0,
    max_elevation: float = 90.0,
) -> np.ndarray:
    """
    Comparación angular vectorizada para TODOS los timesteps de una vez.
    
    Args:
        sun_azimuths: Array [N] de azimuths solares
        sun_altitudes: Array [N] de altitudes solares
        is_sun_up: Array [N] de booleanos
        target_azimuth: Azimuth target del receptor
        target_altitude: Altitude target del receptor
        angle_variance: Tolerancia angular
        min_elevation: Elevación mínima del sol [grados]
        max_elevation: Elevación máxima del sol [grados]
    
    Returns:
        Array [N] booleano - True donde hay sombra
    """
    # Filtros básicos
    valid = is_sun_up & (sun_altitudes >= min_elevation) & (sun_altitudes <= max_elevation)
    
    # Diferencias angulares con wrap a [-180, 180] para evitar saltos cerca del
    # norte (target_azimuth ≈ ±180°). Sin esto, si target=-179° y sun=+179°
    # la diferencia bruta es 358°, cuando realmente son 2°.
    azi_diff = ((sun_azimuths - target_azimuth + 180.0) % 360.0) - 180.0
    alt_diff = sun_altitudes - target_altitude
    
    # Distancia angular cuadrada
    angle_error_sqr = azi_diff**2 + alt_diff**2
    
    # Sombra: dentro de variance Y sol válido
    has_shadow = (angle_error_sqr <= angle_variance**2) & valid
    
    return has_shadow


def calculate_flicker_angles(turbine_x: float, turbine_y: float, turbine_z: float,
                            receptor_x: float, receptor_y: float, receptor_z: float,
                            rotor_diameter: float,
                            receptor_size: float = 0.0) -> Tuple[float, float, float]:
    """
    Calculate angles between turbine and receptor (angular method).
    
    This matches the turbine-to-receptor angular geometry.
    
    Args:
        turbine_x, turbine_y: Turbine UTM coordinates [m]
        turbine_z: Hub height + ground elevation [m]
        receptor_x, receptor_y: Receptor UTM coordinates [m]
        receptor_z: Receptor height [m]
        rotor_diameter: Rotor diameter [m]
        receptor_size: Receptor/zone size [m] (for zones, use max(xSize, ySize); for points, use 0)
    
    Returns:
        Tuple of (target_azimuth, target_altitude, angle_variance):
            target_azimuth: Azimuth angle from turbine to receptor [degrees]
            target_altitude: Altitude angle from turbine to receptor [degrees]
            angle_variance: Angular tolerance [degrees]
    """
    degs_to_rad = np.pi / 180.0
    rad_to_degs = 180.0 / np.pi
    
    # Distance FROM turbine TO receptor (turbine-to-receptor convention)
    x_dist = turbine_x - receptor_x
    y_dist = turbine_y - receptor_y
    elev_diff = turbine_z - receptor_z
    
    # Target azimuth angle (0=N, 90=E, 180=S, -90=W)
    target_azimuth = 90 - np.arctan2(y_dist, x_dist) * rad_to_degs
    
    # Normalize to -180 to 180
    if target_azimuth > 180:
        target_azimuth = target_azimuth - 360
    
    # Horizontal distance
    distance_to_base = np.sqrt(x_dist**2 + y_dist**2)
    
    # Target altitude angle
    target_altitude = np.arctan2(elev_diff, distance_to_base) * rad_to_degs
    
    # Distance to hub (3D)
    distance_to_hub = np.sqrt(distance_to_base**2 + elev_diff**2)
    
    # Angle variance (includes rotor radius + receptor size + sun angular size)
    # Angular tolerance uses: atan2(RD/2 + receptorSize/2, distance) + sunVariation
    # Semi-diámetro angular medio del sol vista desde la Tierra ≈ 0.266°
    # (varía entre 0.262° en afelio y 0.272° en perihelio). Usamos 0.27° como
    # cota superior conservadora para screening.
    sun_variation = SUN_ANGULAR_RADIUS_DEG
    angle_variance = np.arctan2(rotor_diameter / 2 + receptor_size / 2, distance_to_hub) * rad_to_degs + sun_variation
    
    return target_azimuth, target_altitude, angle_variance


def is_shadow_at_angles(sun_azimuth: float, sun_altitude: float,
                        target_azimuth: float, target_altitude: float,
                        angle_variance: float) -> bool:
    """
    Determine if there is shadow based on angular comparison (angular method).
    
    Args:
        sun_azimuth: Solar azimuth [degrees]
        sun_altitude: Solar altitude [degrees]
        target_azimuth: Target azimuth from turbine to receptor [degrees]
        target_altitude: Target altitude from turbine to receptor [degrees]
        angle_variance: Angular tolerance [degrees]
    
    Returns:
        True if shadow occurs, False otherwise
    """
    # Calculate angular difference with wrap to [-180, 180]
    # (important near target_azimuth ≈ ±180°, e.g. turbine north of receptor
    # at low latitudes; without wrap a 358° gap reads as a 2° one).
    azi_diff = ((sun_azimuth - target_azimuth + 180.0) % 360.0) - 180.0
    alt_diff = sun_altitude - target_altitude
    
    # Angular error (squared for efficiency)
    angle_error_sqr = azi_diff**2 + alt_diff**2
    angle_var_sqr = angle_variance**2
    
    # Shadow occurs if angular error is within variance
    return angle_error_sqr <= angle_var_sqr


# Backward compatibility - mantener funciones antiguas por si acaso
solar_position = get_sun_position  # Alias para compatibilidad


def sun_vector(azimuth_deg: float, elevation_deg: float):
    """Return a 3D unit vector for the given solar azimuth/elevation.

    Kept for compatibility with older callers.  The main shadow/flicker engine
    uses angular comparison directly, but returning a vector is safer than
    raising at runtime if an external script still imports this helper.
    """
    az = np.radians(float(azimuth_deg))
    el = np.radians(float(elevation_deg))
    cos_el = np.cos(el)
    return np.array([cos_el * np.sin(az), cos_el * np.cos(az), np.sin(el)], dtype=float)
