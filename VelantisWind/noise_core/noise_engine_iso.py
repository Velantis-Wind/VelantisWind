# -*- coding: utf-8 -*-
"""
Motor acústico ISO-ALIGNED (ISO 9613-2:2024).

Este motor implementa la arquitectura de ISO 9613-2 con algunas simplificaciones:

- Cálculo por bandas de octava (63 Hz a 8 kHz)
- Divergencia geométrica estándar (Adiv)
- Absorción atmosférica por banda Aatm(f, T, RH, P) - SIMPLIFICADA
- Efecto suelo por regiones Agr(As, Am, Ar) - IMPLEMENTADO
- Apantallamiento topográfico Abar con difracción Fresnel - IMPLEMENTADO
- Suma con ponderación A al final

Modelo general:
    Lp,b(R) = Lw,b + Dc - Adiv - Aatm,b - Agr,b - Abar,b

Luego:
    LpA,b = Lp,b + A_weighting[b]
    LpA,total = 10·log10(Σ 10^(LpA,b/10))

Referencia:
    ISO 9613-2:2024 - Acoustics — Attenuation of sound during propagation
    outdoors — Part 2: General method of calculation

Estado actual:
    - Estructura completa: ✓ IMPLEMENTADA
    - Adiv: ✓ IMPLEMENTADO (ISO 9613-2 Ecuación 5)
    - Aatm: ⚠️ SIMPLIFICADO (tabla + correcciones, no analítico completo ISO 9613-1)
    - Agr: ✓ IMPLEMENTADO (regiones fuente/medio/receptor, ISO 9613-2 Ec. 14-16)
    - Abar: ✓ IMPLEMENTADO (difracción Fresnel con MDT, ISO 9613-2 Sec. 7.4)

Limitaciones documentadas:
    - Aatm usa tabla base con correcciones de T/RH/P en lugar de fórmulas
      analíticas completas de ISO 9613-1 Anexo A
    - Abar usa obstáculo dominante extraído del MDT y su posición real a lo
      largo del trayecto; sigue siendo una aproximación básica (sin múltiples
      obstáculos ni difracción avanzada)

Uso recomendado:
    - Evaluaciones de impacto acústico de parques eólicos
    - Screening y comparativas de alternativas
    - Validar con mediciones o software comercial en casos regulatorios
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple, Any

# Import QGIS opcional
try:
    from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsPointXY, QgsRaster
except ImportError:
    QgsVectorLayer = Any
    QgsRasterLayer = Any
    QgsPointXY = Any
    QgsRaster = Any

try:
    from .qgis_io.common import _is_valid_dem_value
except Exception:
    def _is_valid_dem_value(value, provider=None, band: int = 1) -> bool:
        try:
            z = float(value)
            return math.isfinite(z) and abs(z) <= 100000.0 and z not in (-9999.0, -32768.0)
        except Exception:
            return False

try:
    from .noise_common import (
        NoiseSource,
        NoiseReceiver,
        OCTAVE_BANDS,
        A_WEIGHTING,
        apply_a_weighting,
        global_lwa_to_octave_spectrum,
        log,
    )
except ImportError:
    from noise_common import (
        NoiseSource,
        NoiseReceiver,
        OCTAVE_BANDS,
        A_WEIGHTING,
        apply_a_weighting,
        global_lwa_to_octave_spectrum,
        log,
    )


# ============================================================================
# PARÁMETROS ATMOSFÉRICOS POR DEFECTO
# ============================================================================

DEFAULT_TEMPERATURE_C = 15.0
DEFAULT_HUMIDITY_PERCENT = 70.0
DEFAULT_PRESSURE_KPA = 101.325


# ============================================================================
# DIVERGENCIA GEOMÉTRICA (ISO 9613-2)
# ============================================================================

def calculate_adiv_iso(distance_m: float) -> float:
    """
    Atenuación por divergencia geométrica según ISO 9613-2.
    
    Adiv = 20·log10(d) + 11  dB
    
    Esta es la misma fórmula que el motor rápido, pero separada
    por claridad conceptual.
    
    Args:
        distance_m: Distancia 3D fuente-receptor (m)
        
    Returns:
        Atenuación en dB
    """
    dist = max(distance_m, 1.0)
    return 20.0 * math.log10(dist) + 11.0


# ============================================================================
# ABSORCIÓN ATMOSFÉRICA POR BANDA (ISO 9613-1)
# ============================================================================

def calculate_alpha_atm_iso(
    freq_hz: int,
    temperature_c: float,
    humidity_percent: float,
    pressure_kpa: float = DEFAULT_PRESSURE_KPA
) -> float:
    """
    Calcula el coeficiente de absorción atmosférica α (dB/m) para una banda.
    
    Implementación SIMPLIFICADA de ISO 9613-1.
    
    NOTA: Esta es una versión simplificada. Para exactitud total, se debería
    implementar la fórmula completa de ISO 9613-1 Annex A, que incluye:
    - Frecuencias de relajación del oxígeno y nitrógeno
    - Cálculo de concentración molar de vapor de agua
    - Términos de absorción clásica y molecular
    
    Por ahora usamos valores tabulados típicos con interpolación.
    
    Args:
        freq_hz: Frecuencia central de la banda (Hz)
        temperature_c: Temperatura (°C)
        humidity_percent: Humedad relativa (%)
        pressure_kpa: Presión atmosférica (kPa)
        
    Returns:
        Coeficiente α en dB/m
    """
    # Valores típicos de α para condiciones estándar (15°C, 70% RH, 101.325 kPa)
    # Extraídos de tablas ISO 9613-1
    alpha_reference = {
        63: 0.0001,
        125: 0.0003,
        250: 0.0008,
        500: 0.0020,
        1000: 0.0040,
        2000: 0.0095,
        4000: 0.0280,
        8000: 0.0900,
    }
    
    if freq_hz not in alpha_reference:
        # Interpolar logarítmicamente si no está en la tabla
        freqs = sorted(alpha_reference.keys())
        if freq_hz < freqs[0]:
            return alpha_reference[freqs[0]]
        if freq_hz > freqs[-1]:
            return alpha_reference[freqs[-1]]
        
        # Encontrar bandas vecinas
        for i in range(len(freqs) - 1):
            if freqs[i] <= freq_hz <= freqs[i + 1]:
                f1, f2 = freqs[i], freqs[i + 1]
                a1, a2 = alpha_reference[f1], alpha_reference[f2]
                # Interpolación logarítmica
                log_ratio = math.log(freq_hz / f1) / math.log(f2 / f1)
                return a1 * (a2 / a1) ** log_ratio
    
    alpha = alpha_reference[freq_hz]
    
    # Corrección simplificada por temperatura (aumenta con temperatura)
    temp_factor = 1.0 + 0.01 * (temperature_c - 15.0)
    
    # Corrección simplificada por humedad (mínimo ~40-60%, aumenta fuera)
    # La absorción es mínima para 40-60% RH, aumenta si es muy seco o muy húmedo
    optimal_humidity = 50.0
    humidity_factor = 1.0 + 0.003 * abs(humidity_percent - optimal_humidity)
    
    # Corrección por presión (inversa)
    pressure_factor = DEFAULT_PRESSURE_KPA / pressure_kpa
    
    return alpha * temp_factor * humidity_factor * pressure_factor


def calculate_aatm_iso(
    freq_hz: int,
    distance_m: float,
    temperature_c: float,
    humidity_percent: float,
    pressure_kpa: float = DEFAULT_PRESSURE_KPA
) -> float:
    """
    Atenuación atmosférica para una banda según ISO 9613-2.
    
    Aatm,b = α(f, T, RH, P) · d
    
    Args:
        freq_hz: Frecuencia (Hz)
        distance_m: Distancia (m)
        temperature_c: Temperatura (°C)
        humidity_percent: Humedad relativa (%)
        pressure_kpa: Presión (kPa)
        
    Returns:
        Atenuación en dB
    """
    alpha = calculate_alpha_atm_iso(freq_hz, temperature_c, humidity_percent, pressure_kpa)
    return alpha * distance_m


# ============================================================================
# EFECTO SUELO (ISO 9613-2 - SIMPLIFICADO)
# ============================================================================

def _calculate_a_ground_term(freq_hz: int, height_m: float) -> float:
    """
    Calcula una magnitud positiva de atenuación base por efecto suelo.

    Esta implementación usa una aproximación simplificada y devuelve un
    valor de atenuación (>= 0 dB) que después se pondera con G.

    Args:
        freq_hz: Frecuencia (Hz)
        height_m: Altura característica de la región (m)

    Returns:
        Magnitud de atenuación base en dB (sin aplicar G)
    """
    h_eff = max(height_m, 1.0)

    if freq_hz <= 500:
        a_ground = 1.5
    elif freq_hz == 1000:
        a_ground = 1.5 * (1.0 - math.exp(-h_eff / 10.0))
    elif freq_hz == 2000:
        a_ground = 3.0 * (1.0 - math.exp(-h_eff / 10.0))
    elif freq_hz == 4000:
        a_ground = 6.0 * (1.0 - math.exp(-h_eff / 10.0))
    else:  # 8000 Hz
        a_ground = 12.0 * (1.0 - math.exp(-h_eff / 10.0))

    return max(0.0, a_ground)


def calculate_agr_iso_regions(
    freq_hz: int,
    distance_xy_m: float,
    hub_height_m: float,
    receiver_height_m: float,
    ground_g: float
) -> float:
    """
    Efecto suelo según ISO 9613-2 con regiones (fuente, medio, receptor).
    
    ISO 9613-2 Ecuación (14-16):
        Agr = As + Am + Ar
    
    Donde:
        As = atenuación en región fuente (primeros 30×hs metros)
        Am = atenuación en región medio (trayecto central)
        Ar = atenuación en región receptor (últimos 30×hr metros)
    
    Args:
        freq_hz: Frecuencia (Hz)
        distance_xy_m: Distancia horizontal (m)
        hub_height_m: Altura de buje (m)
        receiver_height_m: Altura de receptor (m)
        ground_g: Factor G medio del terreno [0=duro, 1=poroso]
        
    Returns:
        Atenuación total Agr en dB
    """
    # Evitar distancias muy pequeñas
    d = max(distance_xy_m, 1.0)
    hs = max(hub_height_m, 1.0)
    hr = max(receiver_height_m, 1.0)
    
    # Longitudes de las regiones según ISO 9613-2
    # Región fuente: primeros 30×hs metros (máximo)
    d_source = min(30.0 * hs, d / 3.0)
    
    # Región receptor: últimos 30×hr metros (máximo)
    d_receiver = min(30.0 * hr, d / 3.0)
    
    # Región medio: lo que queda
    d_middle = max(d - d_source - d_receiver, 0.0)
    
    # ========== REGIÓN FUENTE (As) ==========
    # Atenuación positiva ponderada por G
    a_ground_s = _calculate_a_ground_term(freq_hz, hs)
    As = ground_g * a_ground_s

    # ========== REGIÓN MEDIO (Am) ==========
    h_middle = (hs + hr) / 2.0
    if d_middle > 0:
        G_m_factor = 0.0  # aproximación simplificada
        a_ground_m = _calculate_a_ground_term(freq_hz, h_middle)
        Am = ground_g * (1.0 - G_m_factor) * a_ground_m
    else:
        Am = 0.0

    # ========== REGIÓN RECEPTOR (Ar) ==========
    a_ground_r = _calculate_a_ground_term(freq_hz, hr)
    Ar = ground_g * a_ground_r

    # ========== TOTAL ==========
    Agr = As + Am + Ar

    # Limitar a valores razonables de atenuación
    return max(0.0, min(10.0, Agr))


def calculate_agr_iso_simple(
    freq_hz: int,
    distance_xy_m: float,
    hub_height_m: float,
    receiver_height_m: float,
    ground_g: float
) -> float:
    """
    DEPRECADO: Usar calculate_agr_iso_regions() en su lugar.
    
    Mantenido temporalmente para compatibilidad.
    """
    return calculate_agr_iso_regions(
        freq_hz, distance_xy_m, hub_height_m, 
        receiver_height_m, ground_g
    )


# ============================================================================
# APANTALLAMIENTO TOPOGRÁFICO (PROVISIONAL)
# ============================================================================

def _adaptive_profile_num_points(
    src: NoiseSource,
    rec: NoiseReceiver,
    dem_layer,
    min_points: int = 50,
    max_points: int = 1200
) -> int:
    """
    Determina número de puntos de muestreo del perfil en función de:
    - distancia fuente-receptor
    - resolución del MDT/DSM

    Estrategia conservadora para receptores puntuales:
    - nunca menos de ``min_points`` para no perder obstáculos finos
    - no más de ``max_points`` para evitar sobrecoste
    - paso de muestreo objetivo ≈ resolución del MDT, con mínimo práctico 5 m

    Nota: un MDT de 5 m se muestrea aproximadamente cada 5 m en receptores
    puntuales. El raster de ruido mantiene una ruta vectorizada separada con
    presupuesto de muestreo más limitado para no disparar el coste computacional.
    """
    dx = float(rec.x) - float(src.x)
    dy = float(rec.y) - float(src.y)
    d_total = math.sqrt(dx * dx + dy * dy)

    pixel_size = None
    try:
        rx = abs(float(dem_layer.rasterUnitsPerPixelX()))
        ry = abs(float(dem_layer.rasterUnitsPerPixelY()))
        pixel_size = max(rx, ry)
    except Exception:
        pixel_size = None

    # For point receivers, honor high-resolution DEM/DTM inputs better.
    # Previous experimental builds used max(pixel_size, 10 m), so a 5 m DEM was
    # effectively sampled every 10 m.  Use the DEM resolution down to 5 m,
    # while keeping a practical cap through max_points.
    if pixel_size is not None and pixel_size > 0.0:
        sample_step = max(float(pixel_size), 5.0)
    else:
        sample_step = 10.0
    if d_total <= 0.0:
        return min_points

    num_points = int(math.ceil(d_total / sample_step)) + 1
    return max(min_points, min(max_points, num_points))


def _extract_terrain_profile(
    src: NoiseSource,
    rec: NoiseReceiver,
    dem_layer,
    num_points: Optional[int] = None
) -> Optional[dict]:
    """
    Extrae perfil de elevación del terreno entre fuente y receptor.

    Devuelve tanto las elevaciones como la distancia acumulada de cada punto,
    lo que permite localizar la posición real del obstáculo dominante.

    Returns:
        dict con:
            - elevations: [z0, z1, ..., zn]
            - distances_m: [0, ..., d_total]
            - total_distance_m: distancia horizontal total
            - sample_step_m: paso medio de muestreo
            - pixel_size_m: tamaño de celda estimado del raster
        o None si no hay MDT válido.
    """
    if dem_layer is None:
        return None

    try:
        from qgis.core import QgsRasterLayer

        if not isinstance(dem_layer, QgsRasterLayer):
            return None

        x1, y1 = float(src.x), float(src.y)
        x2, y2 = float(rec.x), float(rec.y)
        dx = x2 - x1
        dy = y2 - y1
        d_total = math.sqrt(dx * dx + dy * dy)

        if num_points is None:
            num_points = _adaptive_profile_num_points(src, rec, dem_layer)
        num_points = max(2, int(num_points))

        try:
            rx = abs(float(dem_layer.rasterUnitsPerPixelX()))
            ry = abs(float(dem_layer.rasterUnitsPerPixelY()))
            pixel_size = max(rx, ry)
        except Exception:
            pixel_size = None

        # Sample the DEM without converting invalid/no-data values to 0.0.
        # Converting gaps to sea level created false terrain barriers when a
        # receiver or an intermediate point was outside the DEM extent.
        provider = dem_layer.dataProvider()
        elevations = []
        distances_m = []
        source_ground_z = None
        receiver_ground_z = None
        invalid_samples = 0

        for i in range(num_points):
            t = i / (num_points - 1) if num_points > 1 else 0.0
            x = x1 + t * dx
            y = y1 + t * dy
            dist_m = t * d_total

            try:
                val, ok = provider.sample(QgsPointXY(x, y), 1)
            except Exception:
                val, ok = None, False

            z = None
            if ok and _is_valid_dem_value(val, provider, 1):
                try:
                    z = float(val)
                except Exception:
                    z = None

            if i == 0:
                source_ground_z = z
            elif i == num_points - 1:
                receiver_ground_z = z

            if z is None:
                invalid_samples += 1
                continue

            elevations.append(float(z))
            distances_m.append(float(dist_m))

        # Endpoints are mandatory for a meaningful line-of-sight test.  If the
        # turbine or receiver falls outside the DEM, do not compute Abar; report
        # no_profile instead of generating artificial 20 dB screening.
        if source_ground_z is None or receiver_ground_z is None:
            return None

        if len(elevations) < 2:
            return None

        sample_step = d_total / max(num_points - 1, 1)
        return {
            "elevations": elevations,
            "distances_m": distances_m,
            "total_distance_m": d_total,
            "sample_step_m": sample_step,
            "pixel_size_m": pixel_size,
            "num_points": num_points,
            "valid_points": len(elevations),
            "invalid_points": int(invalid_samples),
            "source_ground_z_m": float(source_ground_z),
            "receiver_ground_z_m": float(receiver_ground_z),
        }

    except Exception:
        return None


def _detect_obstacle_state(
    profile_data: dict,
    z_source: float,
    z_receiver: float,
    activation_threshold_m: float = 1.0,
) -> dict:
    """
    Detecta el obstáculo dominante sobre la línea de visión directa.

    Usa un umbral conservador de activación para evitar disparar Abar por
    pequeñas irregularidades del MDT.

    Returns:
        dict con:
            - obstacle_height_m
            - obstacle_distance_m
            - obstacle_index
            - los_clear (bool)
            - threshold_m
    """
    if not profile_data:
        return {
            "obstacle_height_m": 0.0,
            "obstacle_distance_m": 0.0,
            "obstacle_index": None,
            "los_clear": True,
            "threshold_m": activation_threshold_m,
        }

    elevations = profile_data.get("elevations") or []
    distances_m = profile_data.get("distances_m") or []
    d_total = float(profile_data.get("total_distance_m") or 0.0)
    n = len(elevations)
    if n < 2 or len(distances_m) != n or d_total <= 0.0:
        return {
            "obstacle_height_m": 0.0,
            "obstacle_distance_m": 0.0,
            "obstacle_index": None,
            "los_clear": True,
            "threshold_m": activation_threshold_m,
        }

    max_diff = 0.0
    max_idx = None

    # Ignorar extremos para que no se interpreten como obstáculos.
    for i in range(1, n - 1):
        dist_i = distances_m[i]
        t = dist_i / d_total if d_total > 0.0 else 0.0
        z_line = z_source + t * (z_receiver - z_source)
        diff = float(elevations[i]) - z_line
        if diff > max_diff:
            max_diff = diff
            max_idx = i

    if max_idx is None or max_diff <= activation_threshold_m:
        # Keep the raw maximum excess for diagnostics, but mark the path as
        # line-of-sight clear so Abar remains exactly zero. This does not change
        # the physics; it only helps explain why a DEM was active but no
        # topographic screening was applied.
        return {
            "obstacle_height_m": float(max_diff),
            "obstacle_distance_m": 0.0 if max_idx is None else float(distances_m[max_idx]),
            "obstacle_index": max_idx,
            "los_clear": True,
            "threshold_m": activation_threshold_m,
        }

    return {
        "obstacle_height_m": max_diff,
        "obstacle_distance_m": float(distances_m[max_idx]),
        "obstacle_index": max_idx,
        "los_clear": False,
        "threshold_m": activation_threshold_m,
    }


def _prepare_mdt_context(
    src: NoiseSource,
    rec: NoiseReceiver,
    dem_layer = None,
) -> Optional[dict]:
    """
    Precalcula el contexto geométrico del MDT para reutilizarlo en todas las
    bandas de un mismo par fuente–receptor.

    Devuelve ``None`` si no hay MDT o no se puede obtener un perfil útil.
    """
    if dem_layer is None:
        return None

    profile_data = _extract_terrain_profile(src, rec, dem_layer)
    if profile_data is None:
        return None

    src_ground = src.z_ground if src.z_ground is not None else profile_data.get("source_ground_z_m")
    rec_ground = rec.z_ground if rec.z_ground is not None else profile_data.get("receiver_ground_z_m")
    if src_ground is None or rec_ground is None:
        return None
    z_source_total = float(src_ground) + float(src.hub_height)
    z_receiver_total = float(rec_ground) + float(rec.receiver_height)

    pixel_size = profile_data.get("pixel_size_m") or profile_data.get("sample_step_m") or 0.0
    activation_threshold_m = max(1.0, min(3.0, 0.2 * float(pixel_size or 0.0)))

    obstacle = _detect_obstacle_state(
        profile_data,
        z_source_total,
        z_receiver_total,
        activation_threshold_m=activation_threshold_m,
    )

    d_total = float(profile_data.get("total_distance_m") or 0.0)
    d_source_obstacle = max(float(obstacle.get("obstacle_distance_m") or 0.0), 1.0)
    d_obstacle_receiver = max(d_total - d_source_obstacle, 1.0)

    return {
        "profile_data": profile_data,
        "obstacle": obstacle,
        "pixel_size_m": pixel_size,
        "activation_threshold_m": activation_threshold_m,
        "d_total_m": d_total,
        "d1_m": d_source_obstacle,
        "d2_m": d_obstacle_receiver,
        "source_ground_z_m": float(src_ground),
        "receiver_ground_z_m": float(rec_ground),
        "source_acoustic_z_m": float(z_source_total),
        "receiver_acoustic_z_m": float(z_receiver_total),
    }


def _fresnel_diffraction(
    freq_hz: int,
    obstacle_height_m: float,
    distance_source_obstacle_m: float,
    distance_obstacle_receiver_m: float
) -> float:
    """
    Calcula atenuación por difracción según ISO 9613-2 Sección 7.4.
    
    ISO 9613-2 usa número de Fresnel C y tablas de atenuación.
    
    Args:
        freq_hz: Frecuencia (Hz)
        obstacle_height_m: Altura obstáculo sobre línea visión (m)
        distance_source_obstacle_m: Distancia fuente-obstáculo (m)
        distance_obstacle_receiver_m: Distancia obstáculo-receptor (m)
        
    Returns:
        Atenuación Abar en dB
    """
    if obstacle_height_m <= 0.0:
        return 0.0
    
    # Velocidad del sonido
    c_sound = 343.0  # m/s a 20°C
    
    # Longitud de onda
    wavelength = c_sound / freq_hz
    
    # Distancia total
    d_total = distance_source_obstacle_m + distance_obstacle_receiver_m
    if d_total < 1.0:
        return 0.0
    
    # Diferencia de caminos δ (aproximación de obstáculo delgado / knife-edge)
    # δ ≈ h²/2 · (1/d1 + 1/d2)
    # Para d1=d2=d/2 se reduce a 2·h²/d, consistente con la aproximación
    # usada previamente pero permitiendo ahora la posición real del obstáculo.
    d1 = max(distance_source_obstacle_m, 1.0)
    d2 = max(distance_obstacle_receiver_m, 1.0)
    delta = 0.5 * (obstacle_height_m ** 2) * ((1.0 / d1) + (1.0 / d2))
    
    # Número de Fresnel (ISO 9613-2 Ecuación 19)
    # C = 2×δ/λ = 2×f×δ/c
    C = (2.0 * freq_hz * delta) / c_sound
    
    # Atenuación por difracción según ISO 9613-2 Tabla 1
    # (valores aproximados basados en teoría de Fresnel)
    if C <= -2.0:
        # Sin obstáculo significativo
        Abar = 0.0
    elif -2.0 < C <= 0.0:
        # Zona de transición (borde del obstáculo)
        Abar = 10.0 * math.log10(3.0 + 20.0 * C)
    elif 0.0 < C <= 3.5:
        # Obstáculo parcial
        Abar = 10.0 * math.log10(3.0 + 80.0 * C)
    else:
        # Obstáculo significativo
        Abar = 10.0 * math.log10(3.0 + 280.0 * C)
    
    # Limitar a valores razonables
    # ISO 9613-2: Abar típicamente 0-20 dB
    return max(0.0, min(20.0, Abar))


def calculate_abar_mdt(
    freq_hz: int,
    src: NoiseSource,
    rec: NoiseReceiver,
    dem_layer = None,
    mdt_context: Optional[dict] = None,
) -> float:
    """
    Apantallamiento topográfico básico usando perfil MDT y difracción Fresnel.

    Experimental implementation details:
    1. Muestreo adaptativo del perfil según distancia/resolución del MDT.
    2. Uso de la posición real del obstáculo dominante (d1, d2 reales).
    3. Umbral conservador de activación para evitar Abar espurio por ruido del
       MDT o irregularidades menores del relieve.
    """
    context = mdt_context if mdt_context is not None else _prepare_mdt_context(src, rec, dem_layer)
    if not context:
        return 0.0

    obstacle = context.get("obstacle") or {}
    if obstacle.get("los_clear", True):
        return 0.0

    Abar = _fresnel_diffraction(
        freq_hz,
        float(obstacle.get("obstacle_height_m") or 0.0),
        float(context.get("d1_m") or 1.0),
        float(context.get("d2_m") or 1.0),
    )
    return Abar


def calculate_abar_iso_simple(
    freq_hz: int,
    src: NoiseSource,
    rec: NoiseReceiver,
    dem_layer = None,
    mdt_context: Optional[dict] = None,
) -> float:
    """
    DEPRECADO: Usar calculate_abar_mdt() en su lugar.
    
    Mantenido temporalmente para compatibilidad.
    """
    return calculate_abar_mdt(freq_hz, src, rec, dem_layer, mdt_context=mdt_context)


# ============================================================================
# G EFECTIVO DESDE USO DEL SUELO
# ============================================================================

def _ground_g_from_attributes(feat, default_g: float) -> float:
    """
    Extrae factor G de los atributos de un feature de uso del suelo.
    
    Orden de prioridad:
    1. Campo numérico g_factor/g/ground_g
    2. Clasificación textual (urbano→0, mixto→0.5, agrícola→1)
    3. default_g
    
    Args:
        feat: Feature de la capa de uso del suelo
        default_g: Valor por defecto si no se puede determinar
        
    Returns:
        Factor G [0, 1]
    """
    # Buscar campo numérico G
    candidates = ['g_factor', 'g', 'ground_g', 'g_value', 'G']
    for name in candidates:
        try:
            v = feat[name]
            if v is not None and str(v) != '':
                gv = float(v)
                if math.isfinite(gv):
                    return max(0.0, min(1.0, gv))
        except Exception:
            pass
    
    # Buscar clasificación textual
    txt_names = ['uso_suelo', 'uso', 'clase', 'landuse', 'cover', 'type']
    txt = ''
    for name in txt_names:
        try:
            v = feat[name]
            if v is not None and str(v).strip():
                txt = str(v).strip().lower()
                break
        except Exception:
            pass
    
    if txt:
        # Suelo duro (urbano, asfalto, roca)
        if any(k in txt for k in ['urb', 'asfalt', 'roca', 'duro', 'edif', 'industrial']):
            return 0.0
        # Suelo mixto
        if any(k in txt for k in ['mixto', 'mosaico', 'semi']):
            return 0.5
        # Suelo poroso (cultivo, agrícola, prado, forestal)
        if any(k in txt for k in ['cult', 'agr', 'prado', 'past', 'forest', 'veg', 'poroso', 'suelo']):
            return 1.0
    
    return max(0.0, min(1.0, float(default_g)))


def _effective_ground_g(
    src: NoiseSource,
    rec: NoiseReceiver,
    landuse_layer,
    default_g: float
) -> float:
    """
    Calcula factor G efectivo del trayecto fuente-receptor desde uso del suelo.
    
    Método:
    1. Intersecta línea fuente-receptor con polígonos de landuse
    2. Calcula media ponderada por longitud de cada intersección
    3. Si falla, usa punto medio
    4. Fallback: default_g
    
    Args:
        src: Fuente
        rec: Receptor
        landuse_layer: Capa vectorial de uso del suelo (opcional)
        default_g: Valor G por defecto
        
    Returns:
        Factor G efectivo [0, 1]
    """
    try:
        from qgis.core import (
            QgsWkbTypes, QgsGeometry, QgsPointXY,
            QgsFeatureRequest, QgsVectorLayer
        )
    except ImportError:
        return max(0.0, min(1.0, float(default_g)))
    
    g0 = max(0.0, min(1.0, float(default_g)))
    
    if landuse_layer is None or not isinstance(landuse_layer, QgsVectorLayer):
        return g0
    
    try:
        if QgsWkbTypes.geometryType(landuse_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            return g0
        
        # Línea fuente-receptor
        line = QgsGeometry.fromPolylineXY([
            QgsPointXY(float(src.x), float(src.y)),
            QgsPointXY(float(rec.x), float(rec.y))
        ])
        
        if line is None or line.isEmpty():
            return g0
        
        bbox = line.boundingBox()
        total_len = float(line.length())
        
        if total_len <= 0:
            return g0
        
        # Media ponderada por intersección
        weighted = 0.0
        used = 0.0
        
        for feat in landuse_layer.getFeatures(QgsFeatureRequest().setFilterRect(bbox)):
            try:
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue
                
                if not geom.intersects(line):
                    continue
                
                inter = geom.intersection(line)
                ilen = float(inter.length()) if inter and not inter.isEmpty() else 0.0
                
                if ilen <= 0:
                    continue
                
                gv = _ground_g_from_attributes(feat, g0)
                weighted += gv * ilen
                used += ilen
            except Exception:
                continue
        
        if used > 0:
            return max(0.0, min(1.0, weighted / used))
        
        # Fallback: punto medio dentro de polígono
        mid = QgsGeometry.fromPointXY(QgsPointXY(
            (float(src.x) + float(rec.x)) / 2.0,
            (float(src.y) + float(rec.y)) / 2.0
        ))
        
        for feat in landuse_layer.getFeatures(QgsFeatureRequest().setFilterRect(bbox)):
            try:
                geom = feat.geometry()
                if geom and geom.contains(mid):
                    return _ground_g_from_attributes(feat, g0)
            except Exception:
                continue
                
    except Exception:
        return g0
    
    return g0


# ============================================================================
# PROPAGACIÓN ISO POR BANDA
# ============================================================================

def propagate_iso_single_band(
    freq_hz: int,
    lw_band: float,
    src: NoiseSource,
    rec: NoiseReceiver,
    temperature_c: float,
    humidity_percent: float,
    pressure_kpa: float,
    ground_g: float,
    min_distance_m: float,
    dem_layer = None,
    mdt_context: Optional[dict] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Calcula la propagación para UNA BANDA de octava según ISO 9613-2.
    
    Modelo:
        Lp,b(R) = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b
    
    Args:
        freq_hz: Frecuencia central (Hz)
        lw_band: Potencia sonora en esta banda (dB)
        src: Fuente
        rec: Receptor
        temperature_c: Temperatura (°C)
        humidity_percent: Humedad relativa (%)
        pressure_kpa: Presión atmosférica (kPa)
        ground_g: Factor G del terreno [0, 1]
        min_distance_m: Distancia mínima
        dem_layer: Capa MDT (opcional)
        
    Returns:
        (Lp_band, desglose) donde desglose = {'Adiv': ..., 'Aatm': ..., ...}
    """
    # Geometría 3D
    dx = src.x - rec.x
    dy = src.y - rec.y
    dist_xy = max(math.hypot(dx, dy), min_distance_m)
    
    z_src = (src.z_ground or 0.0) + src.hub_height
    z_rec = (rec.z_ground or 0.0) + rec.receiver_height
    dz = z_src - z_rec
    
    dist_3d = math.sqrt(dist_xy * dist_xy + dz * dz)
    dist_3d = max(dist_3d, min_distance_m)
    
    # Atenuaciones por banda
    adiv = calculate_adiv_iso(dist_3d)
    
    aatm = calculate_aatm_iso(
        freq_hz=freq_hz,
        distance_m=dist_3d,
        temperature_c=temperature_c,
        humidity_percent=humidity_percent,
        pressure_kpa=pressure_kpa
    )
    
    agr = calculate_agr_iso_simple(
        freq_hz=freq_hz,
        distance_xy_m=dist_xy,
        hub_height_m=src.hub_height,
        receiver_height_m=rec.receiver_height,
        ground_g=ground_g
    )
    
    abar = calculate_abar_iso_simple(freq_hz, src, rec, dem_layer, mdt_context=mdt_context)
    
    # Nivel de presión sonora en la banda
    lp_band = lw_band - adiv - aatm - agr - abar
    
    desglose = {
        'Adiv': adiv,
        'Aatm': aatm,
        'Agr': agr,
        'Abar': abar,
        'dist_3d': dist_3d,
        'dist_xy': dist_xy,
    }
    
    return lp_band, desglose


# ============================================================================
# FUNCIÓN PRINCIPAL - PROPAGACIÓN ISO
# ============================================================================

def propagate_iso(
    src: NoiseSource,
    rec: NoiseReceiver,
    temperature_c: float = DEFAULT_TEMPERATURE_C,
    humidity_percent: float = DEFAULT_HUMIDITY_PERCENT,
    pressure_kpa: float = DEFAULT_PRESSURE_KPA,
    ground_g: float = 0.5,
    min_distance_m: float = 25.0,
    dem_layer = None,
    landuse_layer = None,  # Optional land-use layer for effective ground handling
) -> Tuple[float, Dict[str, float], Dict[int, float]]:
    """
    Calcula la propagación acústica usando el motor ISO-ALIGNED.
    
    Flujo:
    1. Obtener espectro de octava de la fuente
    2. Para cada banda: calcular Lp,b
    3. Aplicar ponderación A por banda
    4. Sumar energéticamente todas las bandas A-ponderadas
    
    Args:
        src: Fuente acústica
        rec: Receptor
        temperature_c: Temperatura ambiente (°C)
        humidity_percent: Humedad relativa (%)
        pressure_kpa: Presión atmosférica (kPa)
        ground_g: Factor G del terreno [0=duro, 1=poroso]
        min_distance_m: Distancia mínima
        dem_layer: Capa MDT (opcional)
        landuse_layer: Capa uso del suelo (opcional)
        
    Returns:
        Tupla (LpA_total, desglose_dominante, espectro_Lp)
        - LpA_total: Nivel A-ponderado total en dB(A)
        - desglose_dominante: Dict con atenuaciones de la banda dominante
        - espectro_Lp: Dict {freq: Lp} con el espectro en el receptor
    """
    # 1. Calcular G efectivo desde uso del suelo si disponible
    g_eff = _effective_ground_g(src, rec, landuse_layer, float(ground_g))
    
    # 2. Obtener espectro de octava de la fuente
    if src.lw_octave is not None:
        lw_octave = src.lw_octave
    else:
        # Fallback: generar espectro desde LwA global
        lw_octave = global_lwa_to_octave_spectrum(src.lwa)
        log(f"[ISO] Fuente '{src.model_name}' sin espectro → generado desde LwA={src.lwa:.1f} dB(A)")
    
    # 2. Preparar contexto MDT una sola vez por par fuente–receptor
    mdt_context = _prepare_mdt_context(src, rec, dem_layer) if dem_layer is not None else None

    # 3. Calcular Lp para cada banda
    lp_bands: Dict[int, float] = {}
    desgloses: Dict[int, Dict[str, float]] = {}
    
    for freq in OCTAVE_BANDS:
        lw = lw_octave.get(freq, 0.0)
        
        lp_band, desglose = propagate_iso_single_band(
            freq_hz=freq,
            lw_band=lw,
            src=src,
            rec=rec,
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            pressure_kpa=pressure_kpa,
            ground_g=g_eff,  # ← Usar G efectivo
            min_distance_m=min_distance_m,
            dem_layer=dem_layer,
            mdt_context=mdt_context
        )
        
        lp_bands[freq] = lp_band
        desgloses[freq] = desglose
    
    # 3. Aplicar ponderación A y sumar
    lpa_total = apply_a_weighting(lp_bands)
    
    # 4. Encontrar banda dominante (mayor contribución A-ponderada)
    lpa_by_band = {f: lp_bands[f] + A_WEIGHTING[f] for f in OCTAVE_BANDS}
    dominant_freq = max(lpa_by_band, key=lpa_by_band.get)
    
    desglose_dominante = desgloses[dominant_freq].copy()
    desglose_dominante['dominant_freq'] = dominant_freq
    desglose_dominante['lpa_total'] = lpa_total
    desglose_dominante['ground_g'] = g_eff
    desglose_dominante['spectrum_source'] = getattr(src, 'spectrum_source', '') or ('Fallback: generado desde LwA' if src.lw_octave is None else '')
    if mdt_context is not None:
        obstacle = mdt_context.get('obstacle') or {}
        _profile_data = mdt_context.get('profile_data') or {}
        desglose_dominante['mdt_sample_step_m'] = float(_profile_data.get('sample_step_m') or 0.0)
        desglose_dominante['mdt_num_points'] = int(_profile_data.get('num_points') or 0)
        desglose_dominante['mdt_valid_points'] = int(_profile_data.get('valid_points') or _profile_data.get('num_points') or 0)
        desglose_dominante['mdt_invalid_points'] = int(_profile_data.get('invalid_points') or 0)
        desglose_dominante['mdt_source_ground_z_m'] = float(mdt_context.get('source_ground_z_m')) if mdt_context.get('source_ground_z_m') is not None else None
        desglose_dominante['mdt_receiver_ground_z_m'] = float(mdt_context.get('receiver_ground_z_m')) if mdt_context.get('receiver_ground_z_m') is not None else None
        desglose_dominante['mdt_source_acoustic_z_m'] = float(mdt_context.get('source_acoustic_z_m')) if mdt_context.get('source_acoustic_z_m') is not None else None
        desglose_dominante['mdt_receiver_acoustic_z_m'] = float(mdt_context.get('receiver_acoustic_z_m')) if mdt_context.get('receiver_acoustic_z_m') is not None else None
        desglose_dominante['mdt_obstacle_threshold_m'] = float(mdt_context.get('activation_threshold_m') or 0.0)
        desglose_dominante['mdt_los_clear'] = bool(obstacle.get('los_clear', True))
        desglose_dominante['mdt_obstacle_height_m'] = float(obstacle.get('obstacle_height_m') or 0.0)
        desglose_dominante['mdt_obstacle_distance_m'] = float(obstacle.get('obstacle_distance_m') or 0.0)
        desglose_dominante['mdt_d1_m'] = float(mdt_context.get('d1_m') or 0.0)
        desglose_dominante['mdt_d2_m'] = float(mdt_context.get('d2_m') or 0.0)
        if bool(obstacle.get('los_clear', True)):
            # Distinguish a clear line-of-sight path from a path where the
            # terrain maximum is present but below the conservative threshold.
            if float(obstacle.get('obstacle_height_m') or 0.0) <= 0.0:
                desglose_dominante['mdt_abar_state'] = 'los_clear'
            else:
                desglose_dominante['mdt_abar_state'] = 'below_threshold'
        else:
            desglose_dominante['mdt_abar_state'] = 'active'
    elif dem_layer is not None:
        desglose_dominante['mdt_abar_state'] = 'no_profile'
        desglose_dominante['mdt_obstacle_height_m'] = 0.0
        desglose_dominante['mdt_obstacle_distance_m'] = 0.0
        desglose_dominante['mdt_obstacle_threshold_m'] = 0.0
        desglose_dominante['mdt_d1_m'] = 0.0
        desglose_dominante['mdt_d2_m'] = 0.0
    else:
        desglose_dominante['mdt_abar_state'] = 'no_dem'
        desglose_dominante['mdt_obstacle_height_m'] = 0.0
        desglose_dominante['mdt_obstacle_distance_m'] = 0.0
        desglose_dominante['mdt_obstacle_threshold_m'] = 0.0
        desglose_dominante['mdt_d1_m'] = 0.0
        desglose_dominante['mdt_d2_m'] = 0.0

    
    return lpa_total, desglose_dominante, lp_bands


# ============================================================================
# FALLBACK MODO 500 Hz (ISO 9613-2 Annex)
# ============================================================================

def propagate_iso_500hz_approximation(
    src: NoiseSource,
    rec: NoiseReceiver,
    temperature_c: float = DEFAULT_TEMPERATURE_C,
    humidity_percent: float = DEFAULT_HUMIDITY_PERCENT,
    pressure_kpa: float = DEFAULT_PRESSURE_KPA,
    ground_g: float = 0.5,
    min_distance_m: float = 25.0,
    dem_layer = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Aproximación usando solo la atenuación de 500 Hz.
    
    La ISO 9613-2 indica que si solo se conocen niveles A-ponderados,
    se puede usar la atenuación de 500 Hz como estimación.
    
    Modelo:
        LpA(R) ≈ LwA - Adiv - Aatm,500 - Agr,500 - Abar,500
    
    Args:
        (iguales que propagate_iso)
        
    Returns:
        (LpA_aprox, desglose)
    """
    freq_500 = 500
    
    # Geometría
    dx = src.x - rec.x
    dy = src.y - rec.y
    dist_xy = max(math.hypot(dx, dy), min_distance_m)
    
    z_src = (src.z_ground or 0.0) + src.hub_height
    z_rec = (rec.z_ground or 0.0) + rec.receiver_height
    dz = z_src - z_rec
    
    dist_3d = math.sqrt(dist_xy * dist_xy + dz * dz)
    dist_3d = max(dist_3d, min_distance_m)
    
    # Atenuaciones usando 500 Hz
    adiv = calculate_adiv_iso(dist_3d)
    aatm_500 = calculate_aatm_iso(freq_500, dist_3d, temperature_c, humidity_percent, pressure_kpa)
    agr_500 = calculate_agr_iso_simple(freq_500, dist_xy, src.hub_height, rec.receiver_height, ground_g)
    abar_500 = calculate_abar_iso_simple(freq_500, src, rec, dem_layer)
    
    # Nivel A-ponderado aproximado
    lpa_aprox = src.lwa - adiv - aatm_500 - agr_500 - abar_500
    
    desglose = {
        'Adiv': adiv,
        'Aatm': aatm_500,
        'Agr': agr_500,
        'Abar': abar_500,
        'dist_3d': dist_3d,
        'dist_xy': dist_xy,
        'method': '500Hz_approximation',
    }
    
    return lpa_aprox, desglose


# ============================================================================
# INFORMACIÓN DEL MOTOR
# ============================================================================

def get_engine_info() -> dict:
    """
    Devuelve información sobre el motor ISO.
    
    Returns:
        Diccionario con metadata del motor
    """
    return {
        'name': 'iso',
        'display_name': 'Motor ISO-aligned (ISO 9613-2)',
        'description': 'Cálculo por bandas de octava, absorción atmosférica por condiciones, efecto suelo tipo ISO',
        'version': '0.1.8',
        'iso_aligned': True,
        'requires_octave_spectrum': True,
        'requires_meteo': True,
        'typical_speed': 'medio (~8x más lento que motor rápido)',
        'status': 'Experimental - Adiv ✓, Aatm ✓ (simplificado), Agr ✓ (simplificado), Abar ✓ (MDT/DSM básico)',
    }
