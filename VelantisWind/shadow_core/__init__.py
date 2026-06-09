# -*- coding: utf-8 -*-
"""
Shadow Core - Motor de cálculo de Shadow Flicker para Velantis Wind
====================================================================

Módulo de cálculo de sombra y parpadeo (shadow flicker) producido por
aerogeneradores.

Componentes principales:
- solar_geometry: Cálculos astronómicos (posición solar)
- shadow_calculator: Motor de cálculo principal
- shadow_common: Constantes y utilidades comunes

Autor: Velantis Wind Plugin
Licencia: GPL-3.0
"""

from .solar_geometry import (
    get_sun_position, 
    calculate_flicker_angles, 
    is_shadow_at_angles,
    solar_position,  # Alias para backward compatibility
    sun_vector  # Deprecated - solo para evitar ImportError
)
from .shadow_calculator import (
    ShadowFlickerCalculator,
    ShadowFlickerResult,
    calculate_shadow_for_receptor,
    export_shadow_12x24_csv,
)
from .timezone_utils import (
    detect_timezone_name,
    load_iana_timezones,
    timezone_label,
)
from .shadow_common import (
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_MAX_SUN_ELEVATION,
    DEFAULT_OBSERVER_HEIGHT,
    DEFAULT_TIME_STEP_MINUTES,
    DEFAULT_MAX_SHADOW_DISTANCE_M,
)

__all__ = [
    'get_sun_position',
    'solar_position',  # Backward compatibility
    'sun_vector',  # Deprecated
    'calculate_flicker_angles',
    'is_shadow_at_angles',
    'ShadowFlickerCalculator',
    'ShadowFlickerResult',
    'calculate_shadow_for_receptor',
    'export_shadow_12x24_csv',
    'detect_timezone_name',
    'load_iana_timezones',
    'timezone_label',
    'DEFAULT_MIN_SUN_ELEVATION',
    'DEFAULT_MAX_SUN_ELEVATION',
    'DEFAULT_OBSERVER_HEIGHT',
    'DEFAULT_TIME_STEP_MINUTES',
    'DEFAULT_MAX_SHADOW_DISTANCE_M',
]

# Architecture layer exports
try:
    from .domain import ShadowRunConfig
    from .runner import ShadowRunner
except Exception:
    # Keep plugin import tolerant in partial QGIS environments.
    pass
