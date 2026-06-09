# -*- coding: utf-8 -*-
"""
Utilidades y estructuras de datos comunes para todos los motores acústicos.

Este módulo contiene:
- Dataclasses compartidas (NoiseSource, NoiseReceiver)
- Funciones de conversión dB
- Constantes acústicas
- Utilidades de logging
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# Import QGIS opcional (para permitir testing sin QGIS)
try:
    from qgis.core import QgsGeometry
except ImportError:
    QgsGeometry = Any  # Type hint placeholder cuando QGIS no está disponible


# ============================================================================
# LOGGING
# ============================================================================

def log(msg: str) -> None:
    """Write debug logs only when VELANTISWIND_DEBUG=1 is enabled."""
    if str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}:
        print(f"[NOISE] {msg}")


# ============================================================================
# CONSTANTES ACÚSTICAS
# ============================================================================

# Bandas de octava ISO 9613-2 (Hz)
OCTAVE_BANDS = [63, 125, 250, 500, 1000, 2000, 4000, 8000]

# Ponderación A por banda de octava (dB)
# Valores aproximados de la ponderación A para cada banda central
A_WEIGHTING = {
    63: -26.2,
    125: -16.1,
    250: -8.6,
    500: -3.2,
    1000: 0.0,
    2000: 1.2,
    4000: 1.0,
    8000: -1.1,
}


# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class NoiseSource:
    """
    Fuente acústica (turbina eólica).
    
    Atributos:
        model_name: Nombre del modelo de aerogenerador
        source_group: Grupo de fuentes al que pertenece
        park_name: Nombre del parque eólico
        x, y: Coordenadas UTM (m)
        hub_height: Altura de buje (m)
        diameter: Diámetro del rotor (m), opcional
        lwa: Potencia sonora A-ponderada global (dB(A))
        feature_id: ID de la feature en la capa QGIS
        layer_name: Nombre de la capa de origen
        z_ground: Elevación del terreno en la posición de la turbina (m)
        lw_octave: Potencia sonora por banda de octava {freq_hz: Lw_dB}
        spectrum_source: Origen del espectro usado (CSV, biblioteca, plantilla, fallback)
    """
    model_name: str
    source_group: str
    park_name: str
    x: float
    y: float
    hub_height: float
    diameter: Optional[float]
    lwa: float
    feature_id: int
    layer_name: str = ""
    z_ground: Optional[float] = None
    lw_octave: Optional[Dict[int, float]] = None  # {63: Lw, 125: Lw, ...}
    spectrum_source: str = ""


@dataclass
class NoiseReceiver:
    """
    Receptor acústico (punto o centroide de polígono).
    
    Atributos:
        feature_id: ID único del receptor
        x, y: Coordenadas UTM (m)
        z_ground: Elevación del terreno (m)
        receiver_height: Altura del receptor sobre el suelo (m)
        eval_mode: 'point', 'centroid' o 'grid'
        geometry: Geometría QGIS original
        attrs: Atributos originales de la feature
        meta: Metadatos adicionales (límites, tipo, etc.)
    """
    feature_id: int
    x: float
    y: float
    z_ground: Optional[float]
    receiver_height: float
    eval_mode: str
    geometry: QgsGeometry
    attrs: List[object]
    meta: Dict[str, object] = field(default_factory=dict)


# ============================================================================
# FUNCIONES DE CONVERSIÓN dB
# ============================================================================

def db_sum(levels_db: List[float]) -> float:
    """
    Suma energética de niveles en dB.
    
    Args:
        levels_db: Lista de niveles en dB
        
    Returns:
        Nivel total en dB
        
    Example:
        >>> db_sum([60, 60, 60])
        64.77...
    """
    if not levels_db:
        return 0.0
    
    energy_sum = sum(10.0 ** (lp / 10.0) for lp in levels_db)
    
    if energy_sum <= 0.0:
        return 0.0
    
    return 10.0 * math.log10(energy_sum)


def apply_a_weighting(lp_octave: Dict[int, float]) -> float:
    """
    Aplica ponderación A a un espectro de octava y devuelve el nivel A-ponderado.
    
    Args:
        lp_octave: Niveles de presión sonora por banda {freq: Lp_dB}
        
    Returns:
        Nivel A-ponderado total en dB(A)
        
    Example:
        >>> spectrum = {500: 60, 1000: 65, 2000: 58}
        >>> apply_a_weighting(spectrum)
        66.8...
    """
    lpa_bands = []
    
    for freq, lp in lp_octave.items():
        if freq in A_WEIGHTING:
            lpa = lp + A_WEIGHTING[freq]
            lpa_bands.append(lpa)
    
    return db_sum(lpa_bands)


def global_lwa_to_octave_spectrum(
    lwa_global: float,
    spectrum_template: Optional[Dict[int, float]] = None
) -> Dict[int, float]:
    """
    Convierte un LwA global a espectro de octava usando una plantilla.
    
    Si no se proporciona plantilla, usa un espectro genérico de aerogenerador
    basado en literatura (IEC 61400-11, Danish EPA).
    
    Args:
        lwa_global: Potencia sonora A-ponderada global (dB(A))
        spectrum_template: Plantilla relativa por banda {freq: dB_relativo}
        
    Returns:
        Espectro absoluto {freq: Lw_dB}
    """
    # Espectro genérico de aerogenerador moderno (3-5 MW)
    # Basado en mediciones típicas - máximo en bajas frecuencias
    # Estos son valores relativos respecto al total
    if spectrum_template is None:
        # Distribución típica: pico en 63-250 Hz, caída en altas frecuencias
        default_template = {
            63: -3.0,     # Contribución importante en muy bajas frecuencias
            125: -1.5,    # Pico típico
            250: -2.0,    # Segunda contribución importante
            500: -4.0,    # Comienza a caer
            1000: -6.0,   # Caída significativa
            2000: -9.0,   # Baja contribución
            4000: -13.0,  # Muy baja
            8000: -17.0,  # Muy baja
        }
        spectrum_template = default_template
    
    # Calcular el nivel global sin ponderar que daría este espectro
    # con la ponderación A aplicada
    lw_bands_unweighted = {freq: lwa_global + rel for freq, rel in spectrum_template.items()}
    
    # Aplicar ponderación A para obtener LwA_calculado
    lwa_calculated = apply_a_weighting(lw_bands_unweighted)
    
    # Ajustar todas las bandas para que den exactamente lwa_global
    correction = lwa_global - lwa_calculated
    
    lw_octave = {freq: lw + correction for freq, lw in lw_bands_unweighted.items()}
    
    return lw_octave


# ============================================================================
# VALIDACIONES
# ============================================================================

def is_finite_positive(value: float, allow_zero: bool = False) -> bool:
    """
    Verifica que un valor sea finito y positivo (o cero si se permite).
    
    Args:
        value: Valor a verificar
        allow_zero: Si True, acepta 0.0
        
    Returns:
        True si el valor es válido
    """
    try:
        v = float(value)
        if not math.isfinite(v):
            return False
        if allow_zero:
            return v >= 0.0
        return v > 0.0
    except (TypeError, ValueError):
        return False


def validate_octave_spectrum(lw_octave: Dict[int, float]) -> List[str]:
    """
    Valida un espectro de octava.
    
    Args:
        lw_octave: Espectro {freq: Lw_dB}
        
    Returns:
        Lista de errores (vacía si es válido)
    """
    errors = []
    
    if not lw_octave:
        errors.append("Espectro vacío")
        return errors
    
    for freq in OCTAVE_BANDS:
        if freq not in lw_octave:
            errors.append(f"Falta banda {freq} Hz")
        else:
            if not is_finite_positive(lw_octave[freq], allow_zero=True):
                errors.append(f"Valor inválido en banda {freq} Hz: {lw_octave[freq]}")
    
    return errors
