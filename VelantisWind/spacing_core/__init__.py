# -*- coding: utf-8 -*-
"""spacing_core — Envolvente elíptica de separación entre turbinas.

Paquete autocontenido que añade al modo "Mapa interactivo" una envolvente
semitransparente y elíptica alrededor de cada aerogenerador para
visualizar y validar la separación mínima entre turbinas.

Componentes:
  - geometry:          construcción de elipses y evaluación de conflictos
  - orientation:       sector más energético a partir del WRG
  - envelope_manager:  capa en memoria + simbología por estado
  - map_tool:          definición interactiva de la elipse en pantalla
  - panel:             grupo de controles para el dock del mapa interactivo
  - controller:        pegamento entre panel, capa y herramienta de mapa

Ver docs/SPACING_ENVELOPE_MODULE.md y docs/SPACING_ENVELOPE_ARCHITECTURE.md.
"""

from .geometry import SpacingSpec, ellipse_polygon, evaluate_conflicts  # noqa: F401
from .controller import SpacingController  # noqa: F401
from .config_dialog import SpacingConfigDialog  # noqa: F401
