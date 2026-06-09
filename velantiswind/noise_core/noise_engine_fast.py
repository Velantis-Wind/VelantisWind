# -*- coding: utf-8 -*-
"""
Motor acústico RÁPIDO (actual).

Este es el motor original del plugin, refactorizado como módulo independiente.
Implementa un enfoque simplificado fuente-receptor:
- LwA global por turbina
- Divergencia geométrica esférica
- Absorción atmosférica lineal (α fija)
- Efecto suelo simplificado con factor G
- Suma energética en dB(A)

Ventajas:
- Rápido
- Pocas entradas requeridas
- Bueno para estimaciones preliminares

Limitaciones:
- No usa bandas de octava
- Absorción atmosférica no depende de condiciones meteorológicas
- Efecto suelo es empírico, no sigue ISO 9613-2
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, Any

# Import QGIS opcional
try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = Any

try:
    from .noise_common import NoiseSource, NoiseReceiver, log
except ImportError:
    from noise_common import NoiseSource, NoiseReceiver, log


# ============================================================================
# FUNCIONES DE PROPAGACIÓN - MOTOR RÁPIDO
# ============================================================================

def calculate_adiv(distance_m: float) -> float:
    """
    Atenuación por divergencia geométrica esférica.
    
    ISO 9613-2 usa:
        Adiv = 20·log10(d) + 11  dB
    
    donde d es la distancia fuente-receptor en 3D (m).
    
    Args:
        distance_m: Distancia 3D fuente-receptor (m)
        
    Returns:
        Atenuación en dB
    """
    dist = max(distance_m, 1.0)  # Evitar log(0)
    return 20.0 * math.log10(dist) + 11.0


def calculate_aatm_simple(
    distance_m: float,
    alpha_db_per_m: float = 0.005
) -> float:
    """
    Atenuación atmosférica SIMPLIFICADA.
    
    Usa un coeficiente α fijo, independiente de frecuencia y condiciones.
    
    Args:
        distance_m: Distancia fuente-receptor (m)
        alpha_db_per_m: Coeficiente de absorción (dB/m)
        
    Returns:
        Atenuación en dB
    """
    return float(alpha_db_per_m) * distance_m


def calculate_aground_simple(
    distance_xy_m: float,
    hub_height_m: float,
    receiver_height_m: float,
    ground_factor_g: float
) -> float:
    """
    Atenuación por efecto suelo SIMPLIFICADA.
    
    Este es un modelo empírico diseñado para consultoría eólica:
    - G=0: suelo duro (asfalto, roca) → sin efecto
    - G=1: suelo poroso (vegetación, cultivos) → máximo efecto
    - G=0.5: mixto
    
    El efecto:
    - Aumenta con la distancia horizontal
    - Se reduce con alturas grandes (turbinas altas)
    - Está limitado a un máximo de 6 dB
    
    Args:
        distance_xy_m: Distancia horizontal 2D (m)
        hub_height_m: Altura de buje de la turbina (m)
        receiver_height_m: Altura del receptor (m)
        ground_factor_g: Factor de suelo [0=duro, 1=poroso]
        
    Returns:
        Atenuación en dB (siempre >= 0)
    """
    # Término base: aumenta logarítmicamente con la distancia
    base = 3.0 * math.log10(1.0 + max(distance_xy_m, 1.0) / 100.0)
    
    # Factor de altura: reduce el efecto cuando fuente/receptor están altos
    height_factor = 1.0 / (1.0 + ((hub_height_m + receiver_height_m) / 80.0))
    
    # Aplicar factor G y limitar
    aground = ground_factor_g * base * height_factor
    
    return max(0.0, min(6.0, aground))


def effective_ground_g(
    src: NoiseSource,
    rec: NoiseReceiver,
    landuse_layer: Optional[QgsVectorLayer],
    global_g: float
) -> float:
    """
    Determina el factor G efectivo para la propagación fuente-receptor.
    
    Orden de prioridad:
    1. Si hay capa de uso del suelo → deriva G del recorrido
    2. Si no → usa global_g
    
    Args:
        src: Fuente acústica
        rec: Receptor
        landuse_layer: Capa vectorial de uso del suelo (puede ser None)
        global_g: Valor G global de respaldo
        
    Returns:
        Factor G efectivo [0, 1]
    """
    # El motor rápido usa el G global como aproximación de screening.
    # La ruta ISO/QGIS puede calcular G_eff por trayecto desde land-use.
    return max(0.0, min(1.0, float(global_g)))


# ============================================================================
# FUNCIÓN PRINCIPAL - PROPAGACIÓN RÁPIDA
# ============================================================================

def propagate_fast(
    src: NoiseSource,
    rec: NoiseReceiver,
    alpha_db_per_m: float,
    ground_factor_g: float,
    min_distance_m: float,
    landuse_layer: Optional[QgsVectorLayer] = None,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    """
    Calcula la propagación acústica usando el motor RÁPIDO.
    
    Modelo:
        Lp(R) = LwA - Adiv - Aatm - Aground
    
    Args:
        src: Fuente acústica
        rec: Receptor
        alpha_db_per_m: Coeficiente de absorción atmosférica (dB/m)
        ground_factor_g: Factor de suelo global [0=duro, 1=poroso]
        min_distance_m: Distancia mínima para evitar singularidades (m)
        landuse_layer: Capa de uso del suelo (opcional)
        
    Returns:
        Tupla (Lp, dist_2D, dist_3D, Adiv, Aatm, Aground, G_efectivo)
        o None si el cálculo falla
    """
    # Geometría 3D
    dx = src.x - rec.x
    dy = src.y - rec.y
    dist_xy = math.hypot(dx, dy)
    
    if dist_xy <= 0.0:
        dist_xy = min_distance_m
    
    # Elevaciones
    z_src = (src.z_ground or 0.0) + src.hub_height
    z_rec = (rec.z_ground or 0.0) + rec.receiver_height
    dz = z_src - z_rec
    
    # Distancia 3D
    dist_3d = math.sqrt(max(min_distance_m ** 2, dist_xy * dist_xy + dz * dz))
    
    # Atenuaciones
    adiv = calculate_adiv(dist_3d)
    aatm = calculate_aatm_simple(dist_3d, alpha_db_per_m)
    
    # Factor G efectivo
    g_eff = effective_ground_g(src, rec, landuse_layer, ground_factor_g)
    
    # Efecto suelo
    aground = calculate_aground_simple(
        distance_xy_m=dist_xy,
        hub_height_m=src.hub_height,
        receiver_height_m=rec.receiver_height,
        ground_factor_g=g_eff
    )
    
    # Nivel de presión sonora en el receptor
    lp = src.lwa - adiv - aatm - aground
    
    return (lp, dist_xy, dist_3d, adiv, aatm, aground, g_eff)


# ============================================================================
# INFORMACIÓN DEL MOTOR
# ============================================================================

def get_engine_info() -> dict:
    """
    Devuelve información sobre el motor rápido.
    
    Returns:
        Diccionario con metadata del motor
    """
    return {
        'name': 'fast',
        'display_name': 'Motor Rápido (actual)',
        'description': 'Modelo simplificado LwA global, absorción fija, efecto suelo empírico',
        'version': '2.3.2',
        'iso_aligned': False,
        'requires_octave_spectrum': False,
        'requires_meteo': False,
        'typical_speed': 'rápido (<5 seg para 100 receptores)',
    }
