# -*- coding: utf-8 -*-
"""
Gestión de espectros acústicos por bandas de octava.

Este módulo maneja:
- Carga de espectros desde CSV
- Plantillas espectrales por modelo de turbina
- Validación de espectros
- Conversión entre formatos
"""
from __future__ import annotations

import os
import csv
import json
import math
from typing import Dict, List, Optional, Tuple

try:
    from .noise_common import (
        OCTAVE_BANDS,
        A_WEIGHTING,
        apply_a_weighting,
        global_lwa_to_octave_spectrum,
        validate_octave_spectrum,
        log,
    )
except ImportError:
    from noise_common import (
        OCTAVE_BANDS,
        A_WEIGHTING,
        apply_a_weighting,
        global_lwa_to_octave_spectrum,
        validate_octave_spectrum,
        log,
    )


# ============================================================================
# PLANTILLAS ESPECTRALES POR MODELO
# ============================================================================

# Espectro genérico para aerogenerador moderno (2-5 MW)
GENERIC_SPECTRUM_MODERN = {
    63: -3.0, 125: -1.5, 250: -2.0, 500: -4.0,
    1000: -6.0, 2000: -9.0, 4000: -13.0, 8000: -17.0,
}

GENERIC_SPECTRUM_LARGE = {
    63: -2.0, 125: -0.5, 250: -1.0, 500: -3.5,
    1000: -6.5, 2000: -10.0, 4000: -14.0, 8000: -18.0,
}

GENERIC_SPECTRUM_SMALL = {
    63: -4.0, 125: -2.5, 250: -2.5, 500: -4.0,
    1000: -5.5, 2000: -8.0, 4000: -12.0, 8000: -16.0,
}

# Base de datos de plantillas
SPECTRAL_TEMPLATES: Dict[str, Dict[int, float]] = {
    'generic_modern': GENERIC_SPECTRUM_MODERN,
    'generic_large': GENERIC_SPECTRUM_LARGE,
    'generic_small': GENERIC_SPECTRUM_SMALL,
    
    # Vestas (reference template shapes; not manufacturer-certified)
    'vestas_v112': {
        63: -3.2, 125: -1.7, 250: -2.1, 500: -4.1,
        1000: -6.0, 2000: -9.0, 4000: -13.0, 8000: -17.0,
    },
    'vestas_v136': {
        63: -2.8, 125: -1.2, 250: -1.8, 500: -3.8,
        1000: -6.2, 2000: -9.8, 4000: -13.8, 8000: -17.8,
    },
    'vestas_v150': {
        63: -2.5, 125: -1.0, 250: -1.5, 500: -3.5,
        1000: -6.0, 2000: -9.5, 4000: -13.5, 8000: -17.5,
    },
    
    # Siemens Gamesa
    'siemens_sg_5': {
        63: -2.0, 125: -0.5, 250: -1.0, 500: -3.5,
        1000: -6.5, 2000: -10.0, 4000: -14.0, 8000: -18.0,
    },
    
    # Nordex
    'nordex_n163': {
        63: -2.2, 125: -0.8, 250: -1.3, 500: -3.6,
        1000: -6.3, 2000: -9.7, 4000: -13.7, 8000: -17.7,
    },
}


def _normalize_model_token(text: str) -> str:
    """Normaliza nombres de modelo para matching conservador."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")


def _template_matches_model(template_name: str, model_normalized: str) -> bool:
    """
    Devuelve True solo para coincidencias suficientemente específicas.

    Antes bastaba con que coincidiera el fabricante (por ejemplo, "vestas"),
    lo que podía asignar una plantilla V150 a una V112. Para pruebas/publicación
    es más seguro exigir fabricante + familia/modelo cuando existe.
    """
    template_normalized = _normalize_model_token(template_name)
    if template_normalized in model_normalized:
        return True

    tokens = [t for t in template_normalized.split('_') if t and not t.startswith('generic')]
    if not tokens:
        return False

    # Requiere todos los tokens relevantes del nombre de plantilla. Así se evita
    # que "vestas" solo active cualquier plantilla Vestas.
    return all(t in model_normalized for t in tokens)


def get_template_for_model(model_name: str, rated_power_mw: Optional[float] = None) -> Dict[int, float]:
    """Obtiene plantilla espectral para un modelo."""
    model_normalized = _normalize_model_token(model_name)

    # Buscar coincidencia exacta o suficientemente específica
    for template_name, template_data in SPECTRAL_TEMPLATES.items():
        if template_name.startswith('generic'):
            continue
        if _template_matches_model(template_name, model_normalized):
            log(f"[SPECTRUM] Plantilla '{template_name}' para '{model_name}'")
            return template_data.copy()

    # Genérica según potencia
    if rated_power_mw is not None:
        if rated_power_mw >= 5.0:
            return GENERIC_SPECTRUM_LARGE.copy()
        elif rated_power_mw < 2.0:
            return GENERIC_SPECTRUM_SMALL.copy()

    return GENERIC_SPECTRUM_MODERN.copy()


# ============================================================================
# CARGA DESDE CSV
# ============================================================================

def load_spectrum_from_csv(
    filepath: str,
    lwa_global: Optional[float] = None
) -> Tuple[Dict[int, float], Dict[str, object]]:
    """
    Carga espectro desde CSV.
    
    Formatos:
    1. Absoluto: freq_hz, Lw_dB
    2. Relativo: freq_hz, Lw_dB_rel (requiere lwa_global)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")
    
    rows: List[Tuple[int, float]] = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        sample = f.read(1024)
        f.seek(0)
        
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            delim = dialect.delimiter
        except:
            delim = ',' if ',' in sample else ';'
        
        reader = csv.DictReader(f, delimiter=delim)
        
        for row in reader:
            try:
                freq = None
                lw = None
                
                for key in ['freq_hz', 'frequency', 'freq', 'Hz']:
                    if key in row and row[key]:
                        freq = int(float(row[key]))
                        break
                
                for key in ['Lw_dB', 'lw', 'Lw', 'level', 'dB', 'Lw_rel', 'Lw_dB_rel', 'relative']:
                    if key in row and row[key]:
                        lw = float(row[key])
                        break
                
                if freq and lw is not None:
                    rows.append((freq, lw))
            except:
                continue
    
    if not rows:
        raise ValueError(f"No se pudieron leer datos válidos de {filepath}")
    
    # Detectar si es absoluto o relativo
    values = [lw for _, lw in rows]
    max_val = max(values)
    min_val = min(values)
    
    is_relative = max_val < 20.0 or (min_val < 0 and max_val < 50.0)
    
    metadata = {
        'filepath': filepath,
        'n_bands': len(rows),
        'format': 'relative' if is_relative else 'absolute',
    }
    
    # Construir espectro
    spectrum_raw = {freq: lw for freq, lw in rows}
    
    if is_relative:
        if lwa_global is None:
            raise ValueError("Espectro relativo requiere lwa_global")
        spectrum_abs = global_lwa_to_octave_spectrum(lwa_global, spectrum_raw)
        metadata['lwa_global'] = lwa_global
    else:
        # Interpolar a bandas estándar si falta alguna
        spectrum_abs = {}
        for target_freq in OCTAVE_BANDS:
            if target_freq in spectrum_raw:
                spectrum_abs[target_freq] = spectrum_raw[target_freq]
            else:
                # Interpolar
                freqs = sorted(spectrum_raw.keys())
                if target_freq < freqs[0]:
                    spectrum_abs[target_freq] = spectrum_raw[freqs[0]]
                elif target_freq > freqs[-1]:
                    spectrum_abs[target_freq] = spectrum_raw[freqs[-1]]
                else:
                    for i in range(len(freqs) - 1):
                        if freqs[i] < target_freq < freqs[i + 1]:
                            ratio = math.log(target_freq / freqs[i]) / math.log(freqs[i + 1] / freqs[i])
                            spectrum_abs[target_freq] = spectrum_raw[freqs[i]] + ratio * (
                                spectrum_raw[freqs[i + 1]] - spectrum_raw[freqs[i]]
                            )
                            break
        
        metadata['lwa_calculated'] = apply_a_weighting(spectrum_abs)
    
    # Validar
    errors = validate_octave_spectrum(spectrum_abs)
    if errors:
        raise ValueError(f"Espectro inválido: {', '.join(errors)}")
    
    return spectrum_abs, metadata


# ============================================================================
# EXPORTACIÓN
# ============================================================================

def save_spectrum_to_csv(spectrum: Dict[int, float], filepath: str, lwa_global: Optional[float] = None):
    """Guarda espectro a CSV."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_hz', 'Lw_dB', 'Lw_dB_rel', 'A_weight'])
        
        for freq in OCTAVE_BANDS:
            lw_abs = spectrum.get(freq, 0.0)
            lw_rel = lw_abs - lwa_global if lwa_global else 0.0
            a_weight = A_WEIGHTING.get(freq, 0.0)
            writer.writerow([freq, f"{lw_abs:.2f}", f"{lw_rel:.2f}", f"{a_weight:.1f}"])


# ============================================================================
# GESTIÓN DE BIBLIOTECA DE ESPECTROS
# ============================================================================

class SpectrumLibrary:
    """Biblioteca de espectros acústicos."""
    
    def __init__(self, library_dir: Optional[str] = None):
        self.library_dir = library_dir
        self._cache: Dict[str, Dict[int, float]] = {}
    
    def get_spectrum(
        self,
        model_name: str,
        lwa_global: float,
        rated_power_mw: Optional[float] = None,
        custom_csv: Optional[str] = None
    ) -> Tuple[Dict[int, float], str]:
        """
        Obtiene espectro para un modelo.
        
        Prioridad:
        1. CSV personalizado (si se proporciona)
        2. CSV en biblioteca (si existe)
        3. Plantilla por modelo
        4. Plantilla genérica
        
        Returns:
            (espectro, origen) donde origen describe la fuente del espectro
        """
        # 1. CSV personalizado
        if custom_csv and os.path.exists(custom_csv):
            try:
                spectrum, meta = load_spectrum_from_csv(custom_csv, lwa_global)
                return spectrum, f"CSV: {os.path.basename(custom_csv)}"
            except Exception as e:
                log(f"[SPECTRUM][WARN] Error cargando CSV: {e}")
        
        # 2. CSV en biblioteca
        if self.library_dir:
            csv_path = self._find_spectrum_file(model_name)
            if csv_path:
                try:
                    spectrum, meta = load_spectrum_from_csv(csv_path, lwa_global)
                    return spectrum, f"Biblioteca: {os.path.basename(csv_path)}"
                except Exception as e:
                    log(f"[SPECTRUM][WARN] Error cargando desde biblioteca: {e}")
        
        # 3. Plantilla
        template = get_template_for_model(model_name, rated_power_mw)
        spectrum = global_lwa_to_octave_spectrum(lwa_global, template)
        
        # Detectar tipo de plantilla usada con el mismo criterio conservador
        template_name = "genérica"
        model_norm = _normalize_model_token(model_name)
        for name in SPECTRAL_TEMPLATES.keys():
            if name.startswith('generic'):
                continue
            if _template_matches_model(name, model_norm):
                template_name = name
                break
        if template_name == "genérica":
            if rated_power_mw is not None and rated_power_mw >= 5.0:
                template_name = "generic_large"
            elif rated_power_mw is not None and rated_power_mw < 2.0:
                template_name = "generic_small"
            else:
                template_name = "generic_modern"

        return spectrum, f"Plantilla: {template_name}"
    
    def _find_spectrum_file(self, model_name: str) -> Optional[str]:
        """Busca archivo de espectro en la biblioteca."""
        if not self.library_dir or not os.path.exists(self.library_dir):
            return None
        
        model_normalized = model_name.lower().replace('-', '_').replace(' ', '_')
        
        for filename in os.listdir(self.library_dir):
            if not filename.endswith(('.csv', '.txt')):
                continue
            
            file_normalized = os.path.splitext(filename)[0].lower().replace('-', '_')
            
            if model_normalized in file_normalized or file_normalized in model_normalized:
                return os.path.join(self.library_dir, filename)
        
        return None
