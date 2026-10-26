# -*- coding: utf-8 -*-
"""Adapter de estado para la pantalla Energy/AEP.

Este módulo es el límite entre la pantalla Qt/QGIS y el dominio limpio del
módulo de energía. Lee el estado actual del diálogo, normaliza rutas/capas y
construye un :class:`EnergyRunConfig` sin ejecutar PyWake ni crear salidas.

La intención es mantener ``aep_setup_dialog.py`` como UI y
``dialog_controller.py`` como orquestador, dejando aquí toda la extracción de
inputs del diálogo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os

from .domain import EnergyRunConfig, TurbineModelInput
from .translation import tr


@dataclass(frozen=True)
class DialogStateMessage:
    """Mensaje no bloqueante generado al leer el estado del diálogo."""

    severity: str  # "info" | "warning"
    title: str
    message: str
    duration: int = 8


class DialogStateError(RuntimeError):
    """Error legible para el usuario al construir la configuración AEP."""

    def __init__(self, title: str, message: str):
        self.title = str(title or "AEP")
        self.message = str(message or tr("Configuración no válida."))
        super().__init__(self.message)


class DialogStateCancelled(RuntimeError):
    """The dialog said why it does not calculate (a conflict of the physics) or the user cancelled: nothing else."""


@dataclass
class EnergyDialogState:
    """Estado normalizado leído desde la pantalla de energía."""

    models: List[Dict[str, Any]]
    wasp_dir: str
    wrg_paths: List[str]
    wrg_ti_paths: List[str]
    wrg_ti_heights_m: List[Optional[float]]
    compute_variants: bool
    # The physics of the group «Modelo de estela», as a request of the API (ag_core/wake_setup/api.py).
    wake_physics: Dict[str, Any]
    fixed_ti: Optional[float]
    project_crs_authid: str
    tol_m: float
    wrg_direction_count: Optional[int] = None
    wrg_wd_interp: str = "nearest"
    energy_ws_step: Optional[float] = None
    air_density_mode: str = "off"
    air_density_ref_kg_m3: Optional[float] = None
    air_density_ref_altitude_m: Optional[float] = None
    # The provenance of the predefined model of the group, read with its physics; ``None`` in the manual mode.
    wake_provenance: Optional[Dict[str, Any]] = None
    messages: List[DialogStateMessage] = field(default_factory=list)

    @property
    def use_wrg(self) -> bool:
        return bool(self.wrg_paths)

    @property
    def base_export_dir(self) -> str:
        """Carpeta sugerida para exportaciones del cálculo."""
        if self.wasp_dir and os.path.isdir(self.wasp_dir):
            return self.wasp_dir
        if self.use_wrg and self.wrg_paths:
            return os.path.dirname(self.wrg_paths[0])
        return ""

    def to_energy_config(self) -> EnergyRunConfig:
        """Construye la configuración limpia usada por ``EnergyRunner``."""
        return EnergyRunConfig(
            models=[
                TurbineModelInput(
                    name=m.get("name") or "Custom WT",
                    wt=m.get("wt"),
                    meta=m.get("meta"),
                    coords_csv=m.get("coords_csv") or "",
                    coords_xy=m.get("coords_xy"),
                    source_row_index=m.get("source_row_index"),
                    source_type_index=m.get("source_type_index", m.get("source_row_index")),
                    source_layer_id=m.get("source_layer_id") or "",
                    source_layer_name=m.get("source_layer_name") or "",
                )
                for m in self.models
            ],
            wasp_dir=self.wasp_dir if not self.use_wrg else "",
            wrg_paths=self.wrg_paths if self.use_wrg else None,
            compute_variants=self.compute_variants,
            wake_physics=self.wake_physics,
            wake_provenance=self.wake_provenance,
            fixed_ti=self.fixed_ti,
            wrg_ti_paths=self.wrg_ti_paths if self.use_wrg and self.wrg_ti_paths else None,
            wrg_ti_heights_m=self.wrg_ti_heights_m if self.use_wrg and self.wrg_ti_paths else None,
            project_crs_authid=self.project_crs_authid,
            tol_m=self.tol_m,
            wrg_direction_count=self.wrg_direction_count,
            wrg_wd_interp=self.wrg_wd_interp,
            energy_ws_step=self.energy_ws_step,
            air_density_mode=self.air_density_mode,
            air_density_ref_kg_m3=self.air_density_ref_kg_m3,
            air_density_ref_altitude_m=self.air_density_ref_altitude_m,
        )


def _split_semicolon_paths(text: str) -> List[str]:
    return [p.strip() for p in str(text or "").split(";") if p.strip()]


def _line_edit_text(obj: Any, attr_name: str) -> str:
    try:
        widget = getattr(obj, attr_name, None)
        if widget is None:
            return ""
        return str(widget.text()).strip()
    except Exception:
        return ""


def check_unique_model_names(rows: List[Dict[str, Any]]) -> None:
    """Rechaza modelos con el mismo nombre: sus resultados se agrupan por nombre.

    Una fila sin nombre se llama «Modelo {n}», como en el diálogo.
    """
    seen = set()
    for idx, row in enumerate(rows or []):
        name = str((row or {}).get("name") or f"Modelo {idx + 1}").strip()
        if name in seen:
            raise DialogStateError(
                tr("Nombres de modelo"),
                tr(
                    "Hay varios modelos llamados «{name}». Usa un nombre distinto para cada modelo: "
                    "sus resultados se agrupan por nombre."
                ).format(name=name),
            )
        seen.add(name)


def missing_row_points(idx: int, layer: Any) -> DialogStateError:
    """Error de una fila sin capa seleccionada («---») o con su capa vacía."""
    if layer is None:
        return DialogStateError(
            tr("Coordenadas"),
            tr(
                "El Modelo {n} no tiene capa de turbinas: elige una en su selector «Capa de turbinas» "
                "o pulsa «Cargar nueva capa»."
            ).format(n=idx + 1),
        )
    return DialogStateError(
        tr("Coordenadas"),
        tr("La capa «{layer}» del Modelo {n} no tiene turbinas.").format(layer=layer.name(), n=idx + 1),
    )


def layers_used_message(models: List[Dict[str, Any]]) -> str:
    """Qué capa ha usado cada fila en el cálculo."""
    used = "; ".join(
        tr("Modelo {n}: «{layer}»").format(n=int(m.get("source_row_index") or 0) + 1, layer=m.get("source_layer_name") or "")
        for m in models
    )
    return tr("Capas de turbinas usadas: {layers}").format(layers=used)


def _models_from_dialog_rows(dialog: Any) -> List[Dict[str, Any]]:
    """Un modelo por fila, con los puntos de la capa seleccionada en su selector."""
    rows = list(getattr(dialog, "_rows", []) or [])
    if any(row.get("wt") is None for row in rows):
        raise DialogStateError(tr("Faltan modelos"), tr("Define todos los modelos antes de continuar."))

    models: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        layer = dialog._find_interactive_layer_for_row(idx)
        live_pts = dialog._collect_layer_points_for_row(idx) if layer is not None else None
        if not live_pts:
            raise missing_row_points(idx, layer)
        models.append(
            {
                "name": row.get("name") or "Custom WT",
                "wt": row.get("wt"),
                "meta": row.get("meta"),
                "coords_csv": "",
                "coords_xy": live_pts,
                "source_layer_id": layer.id(),
                "source_layer_name": layer.name(),
                "source_row_index": int(idx),
                "source_type_index": int(idx),
            }
        )
    return models


def _read_resource_inputs(dialog: Any, warn: bool = True) -> tuple[str, List[str], List[str], List[Optional[float]]]:
    wasp_dir = _line_edit_text(dialog, "ed_dir")
    wrg_paths = _split_semicolon_paths(_line_edit_text(dialog, "ed_wrg"))
    wrg_ti_paths = _split_semicolon_paths(_line_edit_text(dialog, "ed_wrg_ti"))

    parse_heights = getattr(dialog, "_parse_wrg_ti_height_overrides", None)
    try:
        wrg_ti_heights_m = list(parse_heights() if callable(parse_heights) else [])
    except Exception:
        wrg_ti_heights_m = []

    if wrg_paths:
        for path in wrg_paths:
            if not os.path.isfile(path):
                raise DialogStateError("WRG", tr("El archivo no existe:\n{path}").format(path=path))
            if not path.lower().endswith((".wrg", ".zip")):
                raise DialogStateError("WRG", tr("Extensión no soportada (use .wrg o .zip):\n{path}").format(path=path))

        missing_ti = [path for path in wrg_ti_paths if not os.path.isfile(path)]
        if missing_ti:
            raise DialogStateError(tr("Turbulencia WRG"), tr("El/los ráster(s) TI no existen:\n{paths}").format(paths="\n".join(missing_ti)))

        warn_ti_setup = getattr(dialog, "_maybe_warn_about_ti_setup", None)
        if warn and callable(warn_ti_setup):
            warn_ti_setup(use_wrg=True, wrg_ti_paths=wrg_ti_paths, wrg_ti_heights_m=wrg_ti_heights_m)
    else:
        if not wasp_dir or not os.path.isdir(wasp_dir):
            raise DialogStateError(tr("Recurso eólico"), tr("Selecciona una carpeta WAsP válida o un WRG/ZIP."))

    return wasp_dir, wrg_paths, wrg_ti_paths, wrg_ti_heights_m


def build_energy_dialog_state(dialog: Any, project_crs_authid: str, warn: bool = True) -> EnergyDialogState:
    """Lee el diálogo AEP actual y devuelve un estado normalizado.

    No ejecuta el cálculo. Solo valida mínimos de UI/rutas que antes estaban en
    ``dialog_controller.py`` y prepara la información para ``EnergyRunner``.
    Con ``warn`` falso no muestra los avisos informativos (una segunda lectura del mismo diálogo).
    """
    messages: List[DialogStateMessage] = []

    check_unique_model_names(list(getattr(dialog, "_rows", []) or []))
    models = _models_from_dialog_rows(dialog)

    wasp_dir, wrg_paths, wrg_ti_paths, wrg_ti_heights_m = _read_resource_inputs(dialog, warn)
    use_wrg = bool(wrg_paths)

    compute_variants = True
    # The physics of the group: a conflict, or a cancelled question, stops here (the dialog has said why).
    wake_physics = dialog._wake_physics_for_run(
        ask=warn, n_turbines=sum(len(m.get("coords_xy") or []) for m in models))
    if wake_physics is None:
        raise DialogStateCancelled()
    provenance_fn = getattr(dialog, "_wake_provenance_for_run", None)
    wake_provenance = provenance_fn() if callable(provenance_fn) else None

    fixed_ti = None
    if use_wrg and not wrg_ti_paths:
        fixed_ti_fn = getattr(dialog, "_get_fixed_ti_fraction", None)
        fixed_ti = fixed_ti_fn() if callable(fixed_ti_fn) else None

    # Los parámetros del recurso de un WRG, tal como los muestra el grupo (sin él, los iniciales).
    params_fn = getattr(dialog, "_get_resource_params", None)
    params = dict((params_fn() if callable(params_fn) else {}) or {})
    # Con un WRG, las velocidades de cálculo salen de las curvas de los modelos, como en el cálculo: si no se pueden
    # deducir, no se lanza. Cualquier otro error al leerlas lo informa el cálculo, como hasta ahora.
    if use_wrg:
        from ..ag_core.orchestration import effective_turbines, turbine_speed_grid
        from ..ag_core.resource_grid import WrgContractError

        try:
            turbine_speed_grid(effective_turbines(models))
        except WrgContractError:
            raise DialogStateError(
                tr("Velocidades de cálculo"),
                tr("No se pueden deducir las velocidades de cálculo de la curva de algún modelo: no tiene velocidades tabuladas válidas, su potencia es cero en todos sus nodos, su banda de operación no es válida o su tipo de curva no se admite. Revisa los modelos."),
            ) from None
        except Exception:  # nosec B110
            pass

    # Si el diálogo no puede leer sus controles de densidad, lanza: el cálculo no
    # sigue en silencio como si el ajuste estuviera desactivado.
    density_fn = getattr(dialog, "_get_air_density_settings", None)
    density = dict((density_fn() if callable(density_fn) else {}) or {})

    return EnergyDialogState(
        models=models,
        wasp_dir=wasp_dir,
        wrg_paths=wrg_paths,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m,
        compute_variants=compute_variants,
        wake_physics=wake_physics,
        wake_provenance=wake_provenance,
        fixed_ti=fixed_ti,
        project_crs_authid=project_crs_authid,
        tol_m=30.0,
        wrg_direction_count=params.get("direction_count"),
        wrg_wd_interp=params.get("wd_interp") or "nearest",
        energy_ws_step=params.get("ws_step"),
        air_density_mode=str(density.get("mode") or "off"),
        air_density_ref_kg_m3=density.get("reference_density_kg_m3"),
        air_density_ref_altitude_m=density.get("reference_altitude_m"),
        messages=messages,
    )
