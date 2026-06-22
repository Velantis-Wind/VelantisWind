# -*- coding: utf-8 -*-
"""
Motor de cálculo de Shadow Flicker.

Implementa el cálculo de sombra y parpadeo producido por aerogeneradores
siguiendo la física estándar documentada en la literatura técnica.
"""

from __future__ import annotations

from .debug import debug_print

import numpy as np
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .solar_geometry import (
    get_sun_position, 
    calculate_flicker_angles, 
    is_shadow_at_angles,
    get_sun_positions_vectorized,
    calculate_shadow_vectorized,
)
from .timezone_utils import timezone_label
from .shadow_common import (
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_MAX_SUN_ELEVATION,
    DEFAULT_OBSERVER_HEIGHT,
    DEFAULT_TIME_STEP_MINUTES,
    DEFAULT_MAX_SHADOW_DISTANCE_M,
)


@dataclass
class ShadowFlickerResult:
    """Resultados del cálculo de shadow flicker para un receptor."""
    
    receptor_name: str
    receptor_x: float
    receptor_y: float
    receptor_z: float
    
    # Métricas principales
    hours_per_year_astronomical: float  # Worst case (sin factores)
    minutes_per_year: int
    days_affected: int
    max_minutes_per_day: int
    
    # Calendario detallado: {fecha: [lista de horas con sombra]}
    calendar: Dict[date, List[time]] = field(default_factory=dict)
    
    # Con factores de corrección (opcional)
    hours_per_year_realistic: Optional[float] = None
    
    # Información de turbinas que afectan
    turbine_contributions: Dict[str, float] = field(default_factory=dict)  # {turbine_name: hours}
    
    # Additional fixed-offset compatibility metrics
    max_shadow_date: Optional[date] = None  # Fecha del día con más sombra
    hourly_monthly_matrix: Optional[np.ndarray] = None  # Array [12, 24] - minutos por mes-hora
    
    # Optional integration fields
    feat_id: Optional[int] = None

    # Minutos representados por cada timestamp del calendario.
    # Importante: el calendario guarda instantes discretos, no minutos unitarios.
    time_step_minutes: int = DEFAULT_TIME_STEP_MINUTES
    
    def exceeds_threshold(self, max_hours_year: float = 30.0, max_minutes_day: float = 30.0) -> bool:
        """Verifica si se exceden umbrales regulatorios."""
        if self.hours_per_year_astronomical > max_hours_year:
            return True
        if self.max_minutes_per_day > max_minutes_day:
            return True
        return False
    
    def monthly_breakdown(self) -> Dict[int, float]:
        """
        Calcula desglose mensual de horas de shadow flicker.
        
        Returns:
            Dict[int, float]: {mes (1-12): horas}
        """
        monthly_hours = {month: 0.0 for month in range(1, 13)}

        for fecha, times in self.calendar.items():
            month = fecha.month
            monthly_hours[month] += (len(times) * self.time_step_minutes) / 60.0  # timesteps a horas

        return monthly_hours
    
    def calculate_max_shadow_date(self) -> Optional[date]:
        """
        Calcula la fecha del día con más sombra.
        
        Returns:
            date: Fecha del día con más minutos de sombra, o None si no hay sombra
        """
        if not self.calendar:
            return None
        
        max_minutes = 0
        max_date = None
        
        for fecha, times in self.calendar.items():
            daily_minutes = len(times) * self.time_step_minutes
            if daily_minutes > max_minutes:
                max_minutes = daily_minutes
                max_date = fecha
        
        return max_date
    
    def calculate_hourly_monthly_matrix(self, time_step_minutes: int = 1) -> np.ndarray:
        """
        Calcula matriz 12x24 de minutos de sombra por mes y hora.
        
        Args:
            time_step_minutes: Minutos por timestep (default 1)
        
        Returns:
            np.ndarray: Array [12, 24] con minutos de sombra por mes-hora
        """
        matrix = np.zeros((12, 24), dtype=int)
        
        for fecha, times in self.calendar.items():
            month_idx = fecha.month - 1  # 0-11
            for t in times:
                hour_idx = t.hour  # 0-23
                matrix[month_idx, hour_idx] += time_step_minutes
        
        return matrix


class ShadowFlickerCalculator:
    """Motor de cálculo de shadow flicker."""
    
    def __init__(
        self,
        latitude: float,
        longitude: float,
        year: int,
        timezone_offset: float = 0.0,
        min_sun_elevation: float = DEFAULT_MIN_SUN_ELEVATION,
        max_sun_elevation: float = DEFAULT_MAX_SUN_ELEVATION,
        time_step_minutes: int = DEFAULT_TIME_STEP_MINUTES,
        turbine_availability: float = 1.0,
        timezone_mode: str = "fixed",
        timezone_name: Optional[str] = None,
        max_shadow_distance_m: float = DEFAULT_MAX_SHADOW_DISTANCE_M,
    ):
        """
        Inicializa el calculador de shadow flicker.
        
        Args:
            latitude: Latitud del sitio [grados]
            longitude: Longitud del sitio [grados]
            year: Año de análisis
            timezone_offset: Offset UTC [horas] (ej: CET = +1)
            min_sun_elevation: Elevación solar mínima [grados]
            max_sun_elevation: Elevación solar máxima [grados]
            time_step_minutes: Paso temporal [minutos]
            turbine_availability: Disponibilidad turbina [0-1]
            timezone_mode: "fixed" para offset UTC fijo o "iana" para hora civil local con DST
            timezone_name: Zona IANA, por ejemplo "Europe/Madrid"
        """
        self.latitude = latitude
        self.longitude = longitude
        self.year = year
        self.timezone_offset = timezone_offset
        self.min_sun_elevation = min_sun_elevation
        self.max_sun_elevation = max_sun_elevation
        self.time_step_minutes = time_step_minutes
        self.turbine_availability = max(0.0, min(1.0, turbine_availability))
        self.timezone_mode = (timezone_mode or "fixed").lower().strip()
        self.timezone_name = (timezone_name or "UTC").strip() or "UTC"
        self.max_shadow_distance_m = float(max_shadow_distance_m)
        
        # Cache vectorizado de posiciones solares (calculado bajo demanda)
        self._solar_cache = None
    
    def _ensure_solar_cache(self):
        """Pre-calcula posiciones solares vectorizadas (UNA VEZ por calculator)."""
        if self._solar_cache is not None:
            return
        
        debug_print(f"[Shadow] Pre-calculando posiciones solares vectorizadas para año {self.year}...")
        debug_print(f"[Shadow] Base horaria: {timezone_label(self.timezone_mode, self.timezone_name, self.timezone_offset)}")
        import time
        t0 = time.time()
        
        timestamps, azimuths, altitudes, is_up, _, _ = get_sun_positions_vectorized(
            self.year,
            self.latitude,
            self.longitude,
            self.timezone_offset,
            self.time_step_minutes,
            timezone_mode=self.timezone_mode,
            timezone_name=self.timezone_name,
        )
        
        # Solo guardar timesteps con sol válido (filtrado pre-cálculo)
        valid_mask = is_up & (altitudes >= self.min_sun_elevation) & (altitudes <= self.max_sun_elevation)
        
        self._solar_cache = {
            'timestamps': timestamps[valid_mask],
            'azimuths': azimuths[valid_mask],
            'altitudes': altitudes[valid_mask],
            'is_up': is_up[valid_mask],
            'total_steps': len(timestamps),
            'valid_steps': int(valid_mask.sum()),
        }
        
        elapsed = time.time() - t0
        debug_print(f"[Shadow] ✅ Solar cache: {self._solar_cache['valid_steps']:,}/{self._solar_cache['total_steps']:,} timesteps válidos en {elapsed:.2f}s")
    
    def calculate_for_receptor(
        self,
        receptor_x: float,
        receptor_y: float,
        receptor_z: float,
        receptor_name: str,
        turbines: List[Dict],  # [{'x', 'y', 'hub_height', 'rotor_diameter', 'name', 'ground_elev'(opt)}]
        callback: Optional[callable] = None,
        receptor_ground_elev: float = 0.0,
    ) -> ShadowFlickerResult:
        """
        Calcula shadow flicker para un receptor considerando múltiples turbinas.

        Args:
            receptor_x: Coordenada Este del receptor [m]
            receptor_y: Coordenada Norte del receptor [m]
            receptor_z: Altura del receptor sobre el suelo (AGL) [m]
            receptor_name: Nombre del receptor
            turbines: Lista de turbinas. Cada dict debe contener
                'x', 'y', 'hub_height', 'rotor_diameter', 'name', y opcionalmente
                'ground_elev' (cota del terreno en la base de la torre, m).
            callback: Función opcional para reportar progreso callback(progress: float, message: str)
            receptor_ground_elev: Cota del terreno en el receptor [m]. Default 0.0
                (asume terreno plano, comportamiento previo). Cuando se proporciona
                un MDT, las cotas absolutas (terreno + altura) se usan para calcular
                ``elev_diff`` con corrección de elevación del terreno (``hubHeight + thisTurb.elev - zoneElev``).

        Returns:
            ShadowFlickerResult con métricas y calendario
        """
        # Posición absoluta del receptor (Z = cota del terreno + altura del observador)
        receptor_pos = np.array([receptor_x, receptor_y, receptor_z + receptor_ground_elev])

        # ===================================================================
        # ONE-SHOT VERIFICATION on first call of this calculator instance.
        # In parallel mode each worker has its own calculator → each prints once,
        # so you'll see one diagnostic per worker confirming receptor_ground_elev
        # and turbine ground_elev are reaching the physics layer.
        # ===================================================================
        first_call = not getattr(self, '_first_call_logged', False)
        if first_call:
            self._first_call_logged = True
            debug_print(f"[ShadowCalc] First call diagnostic — calculator instance verified")
            debug_print(f"[ShadowCalc]   receptor='{receptor_name}'  "
                  f"xyz=({receptor_x:.1f}, {receptor_y:.1f}, {receptor_z:.1f}m AGL)  "
                  f"ground_elev={receptor_ground_elev:+.1f}m  "
                  f"→ absolute_z={receptor_z + receptor_ground_elev:.1f}m")
            if turbines:
                t_first = turbines[0]
                t_ground = float(t_first.get('ground_elev', 0.0))
                t_abs = float(t_first['hub_height']) + t_ground
                dz = t_abs - (receptor_z + receptor_ground_elev)
                horiz = ((t_first['x'] - receptor_x)**2 + (t_first['y'] - receptor_y)**2) ** 0.5
                debug_print(f"[ShadowCalc]   first turbine '{t_first.get('name','T0')}': "
                      f"hub={t_first['hub_height']:.1f}m + ground={t_ground:+.1f}m = "
                      f"abs_hub_z={t_abs:.1f}m")
                debug_print(f"[ShadowCalc]   geometry: Δz_turb-recv={dz:+.1f}m  horiz_dist={horiz:.1f}m  "
                      f"→ target_altitude={np.degrees(np.arctan2(dz, horiz)):+.3f}°")

        # Calendario consolidado (unión de sombras de todas las turbinas)
        calendar_combined: Dict[date, set] = {}  # {fecha: set(horas)}
        turbine_contributions: Dict[str, float] = {}

        # Iterar sobre todas las turbinas
        total_turbines = len(turbines)

        for i, turbine in enumerate(turbines):
            if callback:
                progress = (i + 1) / total_turbines
                callback(progress, f"Procesando turbina {i+1}/{total_turbines}: {turbine.get('name', '?')}")

            # Cota absoluta del hub: cota del terreno (si la hay) + altura de buje.
            # Si no se ha proporcionado MDT, ground_elev = 0 → comportamiento previo (terreno plano).
            turbine_ground_elev = float(turbine.get('ground_elev', 0.0))
            absolute_hub_z = float(turbine['hub_height']) + turbine_ground_elev

            # fixed-offset compatibility: ignore turbines beyond maxShadowDistance
            # before the angular test. This also avoids very small far-field
            # alignments being counted as flicker.
            horizontal_distance = float(np.hypot(float(turbine['x']) - receptor_x, float(turbine['y']) - receptor_y))
            if horizontal_distance > self.max_shadow_distance_m:
                turbine_contributions[turbine.get('name', f"T_{i}")] = 0.0
                continue

            # Calcular sombra de esta turbina
            calendar_turbine = self._calculate_single_turbine_annual(
                turbine_x=turbine['x'],
                turbine_y=turbine['y'],
                turbine_hub_height=absolute_hub_z,
                turbine_rotor_diameter=turbine['rotor_diameter'],
                receptor_pos=receptor_pos,
            )
            
            # Acumular contribución
            hours_turbine = sum(len(times) * self.time_step_minutes for times in calendar_turbine.values()) / 60.0
            turbine_contributions[turbine.get('name', f"T_{i}")] = hours_turbine
            
            # Unir calendarios (evitar doble conteo)
            for fecha, times in calendar_turbine.items():
                if fecha not in calendar_combined:
                    calendar_combined[fecha] = set()
                calendar_combined[fecha].update(times)
        
        # Convertir sets a listas ordenadas
        calendar_final = {
            fecha: sorted(list(times))
            for fecha, times in calendar_combined.items()
        }
        
        # Calcular métricas
        total_minutes = int(sum(len(times) * self.time_step_minutes for times in calendar_final.values()))
        hours_astronomical = total_minutes / 60.0
        hours_realistic = hours_astronomical * self.turbine_availability
        
        max_minutes_day = int(max((len(times) * self.time_step_minutes for times in calendar_final.values()), default=0))
        
        # Calcular fecha del día con más sombra
        max_shadow_date = None
        if calendar_final:
            max_shadow_date = max(calendar_final.keys(), key=lambda d: len(calendar_final[d]) * self.time_step_minutes)
        
        # Calcular matriz 12x24
        hourly_matrix = np.zeros((12, 24), dtype=int)
        for fecha, times in calendar_final.items():
            month_idx = fecha.month - 1
            for t in times:
                hourly_matrix[month_idx, t.hour] += self.time_step_minutes
        
        return ShadowFlickerResult(
            receptor_name=receptor_name,
            receptor_x=receptor_x,
            receptor_y=receptor_y,
            receptor_z=receptor_z,
            hours_per_year_astronomical=hours_astronomical,
            minutes_per_year=total_minutes,
            days_affected=len(calendar_final),
            max_minutes_per_day=max_minutes_day,
            calendar=calendar_final,
            hours_per_year_realistic=hours_realistic,
            turbine_contributions=turbine_contributions,
            max_shadow_date=max_shadow_date,
            hourly_monthly_matrix=hourly_matrix,
            time_step_minutes=self.time_step_minutes,
        )
    
    def _calculate_single_turbine_annual(
        self,
        turbine_x: float,
        turbine_y: float,
        turbine_hub_height: float,
        turbine_rotor_diameter: float,
        receptor_pos: np.ndarray,
    ) -> Dict[date, List[time]]:
        """
        Calcula sombra de una turbina durante todo el año (VECTORIZADO).
        
        Versión optimizada que usa NumPy para calcular TODOS los timesteps a la vez.
        50-100x más rápido que la versión iterativa.
        
        Returns:
            Dict[date, List[time]]: Calendario con horas de sombra por fecha
        """
        # Asegurar que el cache solar está calculado
        self._ensure_solar_cache()
        
        # Pre-calcular ángulos turbina→receptor (UNA SOLA VEZ - eficiencia)
        target_azimuth, target_altitude, angle_variance = calculate_flicker_angles(
            turbine_x, turbine_y, turbine_hub_height,
            receptor_pos[0], receptor_pos[1], receptor_pos[2],
            turbine_rotor_diameter,
            receptor_size=2.0  # Tamaño de ventana típico
        )
        
        # COMPARACIÓN VECTORIZADA - Procesa TODOS los timesteps de golpe
        sun_az = self._solar_cache['azimuths']
        sun_alt = self._solar_cache['altitudes']
        timestamps = self._solar_cache['timestamps']
        
        # Diferencias angulares (vectorizado) con wrap a [-180, 180]
        # para evitar saltos espurios cerca de target_azimuth ≈ ±180°.
        azi_diff = ((sun_az - target_azimuth + 180.0) % 360.0) - 180.0
        alt_diff = sun_alt - target_altitude
        
        # Distancia angular cuadrada (vectorizado)
        angle_error_sqr = azi_diff ** 2 + alt_diff ** 2
        
        # Boolean array: True donde hay sombra
        has_shadow = angle_error_sqr <= angle_variance ** 2
        
        # Extraer solo los timestamps con sombra
        shadow_timestamps = timestamps[has_shadow]
        
        # Construir calendario
        calendar: Dict[date, List[time]] = {}
        for ts in shadow_timestamps:
            d = ts.date()
            t = ts.time()
            if d not in calendar:
                calendar[d] = []
            calendar[d].append(t)
        
        return calendar
    
    def _calculate_single_day_angles(
        self,
        fecha: date,
        target_azimuth: float,
        target_altitude: float,
        angle_variance: float,
    ) -> List[time]:
        """
        DEPRECATED: Versión iterativa, mantenida por compatibilidad.
        
        Usa _calculate_single_turbine_annual (vectorizada) en su lugar.
        
            target_azimuth: Azimuth turbina→receptor [degrees]
            target_altitude: Altitude turbina→receptor [degrees]
            angle_variance: Tolerancia angular [degrees]
        
        Returns:
            List[time]: Lista de horas con sombra
        """
        shadow_times: List[time] = []
        
        # Iterar a lo largo del día (solo horas diurnas)
        # Optimización: saltar la noche (asumiendo sol no visible antes de 5am ni después de 10pm)
        current = datetime.combine(fecha, datetime.min.time().replace(hour=5))
        end = datetime.combine(fecha, datetime.min.time().replace(hour=22))
        step = timedelta(minutes=self.time_step_minutes)
        
        while current <= end:
            # Posición solar (NOAA equations)
            sun_azimuth, sun_altitude, is_sun_up = get_sun_position(
                current, self.latitude, self.longitude, self.timezone_offset
            )
            
            # Filtros rápidos
            if not is_sun_up:
                current += step
                continue
                
            if sun_altitude < self.min_sun_elevation or sun_altitude > self.max_sun_elevation:
                current += step
                continue
            
            # Comparación de ángulos (angular method)
            if is_shadow_at_angles(sun_azimuth, sun_altitude, 
                                  target_azimuth, target_altitude, 
                                  angle_variance):
                shadow_times.append(current.time())
            
            current += step
        
        return shadow_times


def calculate_shadow_for_receptor(
    receptor_x: float,
    receptor_y: float,
    receptor_z: float,
    receptor_name: str,
    turbines: List[Dict],
    latitude: float,
    longitude: float,
    year: int,
    timezone_offset: float = 0.0,
    callback: Optional[callable] = None,
    timezone_mode: str = "fixed",
    timezone_name: Optional[str] = None,
    receptor_ground_elev: float = 0.0,
    max_shadow_distance_m: float = DEFAULT_MAX_SHADOW_DISTANCE_M,
) -> ShadowFlickerResult:
    """
    Función de conveniencia para calcular shadow flicker.
    
    Args:
        receptor_x, receptor_y, receptor_z: Posición del receptor [m]
            (receptor_z = altura sobre el terreno, ej. 2 m)
        receptor_name: Nombre del receptor
        turbines: Lista de turbinas (dict con x, y, hub_height, rotor_diameter, name,
            y opcionalmente 'ground_elev' = cota del terreno en la base de la torre [m])
        latitude, longitude: Coordenadas del sitio [grados]
        year: Año de análisis
        timezone_offset: Offset UTC [horas]
        callback: Función para reportar progreso
        timezone_mode: "fixed" o "iana"
        timezone_name: Zona IANA para modo "iana"
        receptor_ground_elev: Cota del terreno en el receptor [m]. Default 0.0
            (asume terreno plano - retro-compatible).
    
    Returns:
        ShadowFlickerResult
    """
    calc = ShadowFlickerCalculator(
        latitude=latitude,
        longitude=longitude,
        year=year,
        timezone_offset=timezone_offset,
        timezone_mode=timezone_mode,
        timezone_name=timezone_name,
        max_shadow_distance_m=max_shadow_distance_m,
    )
    
    return calc.calculate_for_receptor(
        receptor_x=receptor_x,
        receptor_y=receptor_y,
        receptor_z=receptor_z,
        receptor_name=receptor_name,
        turbines=turbines,
        callback=callback,
        receptor_ground_elev=receptor_ground_elev,
    )




def _format_turbine_geometry_for_export(turbines: Optional[List[Dict[str, object]]], key: str, unit: str = "m") -> str:
    """Format the turbine geometry values passed to the shadow calculation."""
    values = []
    for turbine in turbines or []:
        try:
            value = float(turbine.get(key))
        except Exception:
            continue
        if np.isfinite(value):
            values.append(value)

    if not values:
        return "N/A"

    unique_values = sorted({round(v, 6) for v in values})
    if len(unique_values) == 1:
        return f"{unique_values[0]:.2f} {unit}"

    return f"{min(values):.2f}-{max(values):.2f} {unit} ({len(unique_values)} unique values)"



def _shadow_export_lang_labels():
    try:
        from ..i18n import current_language
        lang = str(current_language()).lower()
    except Exception:
        lang = "es"
    if lang.startswith("de"):
        return {
            "months": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
            "title": "Schattenwurfstunden nach Monat und Tagesstunde",
            "config": "BERECHNUNGSKONFIGURATION",
            "year": "Jahr", "timezone": "Zeitzone", "time_step": "Zeitschritt", "availability": "Verfügbarkeit",
            "max_dist": "Maximaler Schattenabstand", "solar_limits": "Grenzwerte der Sonnenhöhe",
            "n_turbines": "Anzahl Windturbinen", "hub": "Verwendete Nabenhöhe", "diam": "Verwendeter Rotordurchmesser",
            "receiver": "Rezeptor", "hour": "Stunde", "summary": "ZUSAMMENFASSUNG",
            "total": "Gesamt h/Jahr", "max_min": "Max. Minuten/Tag", "max_date": "Datum des stärksten Schattenwurfs", "days": "Betroffene Tage",
        }
    if lang.startswith("fr"):
        return {
            "months": ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
            "title": "Heures d’ombres et scintillement par mois et heure de la journée",
            "config": "CONFIGURATION DU CALCUL",
            "year": "Année", "timezone": "Fuseau horaire", "time_step": "Pas temporel", "availability": "Disponibilité",
            "max_dist": "Distance maximale d’ombre", "solar_limits": "Limites d’élévation solaire",
            "n_turbines": "Nombre d’éoliennes", "hub": "Hauteur de moyeu utilisée", "diam": "Diamètre du rotor utilisé",
            "receiver": "Récepteur", "hour": "Heure", "summary": "RÉSUMÉ",
            "total": "Total h/an", "max_min": "Max minutes/jour", "max_date": "Date d’ombre max.", "days": "Jours affectés",
        }
    return {
        "months": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        "title": "Horas de sombra y parpadeo por mes y hora del día",
        "config": "CONFIGURACIÓN DEL CÁLCULO",
        "year": "Año", "timezone": "Zona horaria", "time_step": "Paso temporal", "availability": "Disponibilidad",
        "max_dist": "Distancia máxima de sombra", "solar_limits": "Límites de elevación solar",
        "n_turbines": "Número de aerogeneradores", "hub": "Altura de buje utilizada", "diam": "Diámetro de rotor utilizado",
        "receiver": "Receptor", "hour": "Hora", "summary": "RESUMEN",
        "total": "Total h/año", "max_min": "Máx. minutos/día", "max_date": "Fecha de sombra máxima", "days": "Días afectados",
    }


def export_shadow_12x24_csv(
    results: List[ShadowFlickerResult],
    filepath: str,
    turbines: Optional[List[Dict[str, object]]] = None,
    calculator: Optional["ShadowFlickerCalculator"] = None,
) -> None:
    """
    Exporta matriz 12x24 (meses x horas) a CSV (formato hora × mes).

    Args:
        results: Lista de resultados de shadow flicker
        filepath: Ruta del archivo CSV de salida
        turbines: Turbinas usadas en el cálculo, para documentar la geometría exportada
        calculator: Calculadora usada en el cálculo, para documentar la configuración del escenario
    """
    import csv

    # Exported labels follow the language selected in the hub.
    try:
        from .. import i18n as _i18n
        _t = _i18n.tr_text
    except Exception:
        try:
            import i18n as _i18n  # type: ignore
            _t = _i18n.tr_text
        except Exception:
            _t = lambda s: s  # type: ignore

    labels = _shadow_export_lang_labels()
    months = labels["months"]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([labels['title']])
        writer.writerow([])  # Línea vacía

        # Calculation metadata / exported summary context
        writer.writerow([labels['config']])
        if calculator is not None:
            writer.writerow(['Latitude', f"{getattr(calculator, 'latitude', 0.0):.5f}"])
            writer.writerow(['Longitude', f"{getattr(calculator, 'longitude', 0.0):.5f}"])
            writer.writerow([labels['year'], getattr(calculator, 'year', 'N/A')])
            writer.writerow([
                labels['timezone'],
                timezone_label(
                    getattr(calculator, 'timezone_mode', 'fixed'),
                    getattr(calculator, 'timezone_name', None),
                    getattr(calculator, 'timezone_offset', 0),
                ),
            ])
            writer.writerow([labels['time_step'], f"{getattr(calculator, 'time_step_minutes', 'N/A')} min"])
            writer.writerow([labels['availability'], f"{getattr(calculator, 'turbine_availability', 'N/A')}"])
            writer.writerow([labels['max_dist'], f"{getattr(calculator, 'max_shadow_distance_m', 'N/A')} m"])
            writer.writerow([
                labels['solar_limits'],
                f"{getattr(calculator, 'min_sun_elevation', 'N/A')}° à {getattr(calculator, 'max_sun_elevation', 'N/A')}°",
            ])
        writer.writerow([labels['n_turbines'], len(turbines or [])])
        writer.writerow([labels['hub'], _format_turbine_geometry_for_export(turbines, 'hub_height')])
        writer.writerow([labels['diam'], _format_turbine_geometry_for_export(turbines, 'rotor_diameter')])
        writer.writerow([])  # Línea vacía

        for result in results:
            if result.hourly_monthly_matrix is None:
                continue

            # Header del receptor
            writer.writerow([f"{labels['receiver']} : {result.receptor_name}"])
            writer.writerow([labels['hour']] + months)

            # 24 filas (una por hora)
            for hour in range(24):
                row = [f"{hour:02d}:00"]
                for month_idx in range(12):
                    minutes = result.hourly_monthly_matrix[month_idx, hour]
                    hours = minutes / 60.0
                    row.append(f"{hours:.2f}")
                writer.writerow(row)

            writer.writerow([])  # Separador entre receptores

        # Resumen al final
        writer.writerow([labels['summary']])
        writer.writerow([labels['receiver'], labels['total'], labels['max_min'], labels['max_date'], labels['days']])
        for result in results:
            max_date = result.max_shadow_date.strftime('%Y-%m-%d') if result.max_shadow_date else 'N/A'
            writer.writerow([
                result.receptor_name,
                f"{result.hours_per_year_astronomical:.2f}",
                result.max_minutes_per_day,
                max_date,
                result.days_affected,
            ])
