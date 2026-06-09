# -*- coding: utf-8 -*-
"""
Constantes y utilidades comunes para el módulo de Shadow Flicker.
"""

# Umbrales solares (grados)
DEFAULT_MIN_SUN_ELEVATION = 3.0  # Sol demasiado bajo en horizonte
DEFAULT_MAX_SUN_ELEVATION = 90.0  # fixed-offset: no high-sun cut by default

# Configuración de receptor
DEFAULT_OBSERVER_HEIGHT = 2.0  # m AGL (altura ventana típica)

# Configuración temporal
DEFAULT_TIME_STEP_MINUTES = 5  # Resolución temporal del cálculo (5 min = buen balance velocidad/precisión)

# Parámetros geométricos / física geométrica
SUN_ANGULAR_RADIUS_DEG = 0.2725  # solar angular radius: semi-diámetro angular solar [deg]
DEFAULT_MAX_SHADOW_DISTANCE_M = 2000.0  # maximum shadow distance [m]

# Umbrales regulatorios típicos (Europa)
REGULATORY_LIMITS = {
    'germany': {
        'max_hours_year': 30.0,
        'max_minutes_day': 30.0,
        'description': 'Alemania - WEA-Schattenwurf-Hinweise',
    },
    'denmark': {
        'max_hours_year': 10.0,
        'max_minutes_day': None,
        'description': 'Dinamarca - Con factores realistas',
    },
    'uk': {
        'max_hours_year': 30.0,
        'max_minutes_day': None,
        'description': 'Reino Unido - ETSU-R-97',
    },
    'netherlands': {
        'max_days_year': 17,  # días con >20 min/día
        'max_minutes_day': 20.0,
        'description': 'Holanda',
    },
}

def exceeds_regulatory_limit(hours_year: float, minutes_day: float, country: str = 'germany') -> bool:
    """
    Verifica si se exceden los umbrales regulatorios.
    
    Args:
        hours_year: Horas de sombra al año
        minutes_day: Minutos máximos de sombra en un día
        country: País para aplicar normativa
    
    Returns:
        bool: True si se excede algún umbral
    """
    if country not in REGULATORY_LIMITS:
        country = 'germany'  # default
    
    limits = REGULATORY_LIMITS[country]
    
    if 'max_hours_year' in limits and limits['max_hours_year'] is not None:
        if hours_year > limits['max_hours_year']:
            return True
    
    if 'max_minutes_day' in limits and limits['max_minutes_day'] is not None:
        if minutes_day > limits['max_minutes_day']:
            return True
    
    return False
