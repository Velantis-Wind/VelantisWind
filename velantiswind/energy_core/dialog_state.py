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
        self.message = str(message or "Configuración no válida.")
        super().__init__(self.message)


@dataclass
class EnergyDialogState:
    """Estado normalizado leído desde la pantalla de energía."""

    models: List[Dict[str, Any]]
    wasp_dir: str
    wrg_paths: List[str]
    wrg_ti_paths: List[str]
    wrg_ti_heights_m: List[Optional[float]]
    compute_variants: bool
    include_turbulence: bool
    include_blockage: bool
    include_rotor_avg: bool
    rotor_avg_model: str
    superposition_model: str
    wfm_engine: str
    wake_deficit_model: str
    wake_deficit_kwargs: Dict[str, Any]
    turbulence_model: str
    blockage_deficit_model: str
    fixed_ti: Optional[float]
    project_crs_authid: str
    tol_m: float
    use_selected_layers: bool = False
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
                )
                for m in self.models
            ],
            wasp_dir=self.wasp_dir if not self.use_wrg else "",
            wrg_paths=self.wrg_paths if self.use_wrg else None,
            compute_variants=self.compute_variants,
            include_turbulence=self.include_turbulence,
            include_blockage=self.include_blockage,
            include_rotor_avg=self.include_rotor_avg,
            rotor_avg_model=self.rotor_avg_model,
            superposition_model=self.superposition_model,
            wfm_engine=self.wfm_engine,
            wake_deficit_model=self.wake_deficit_model,
            wake_deficit_kwargs=dict(self.wake_deficit_kwargs or {}),
            turbulence_model=self.turbulence_model,
            blockage_deficit_model=self.blockage_deficit_model,
            fixed_ti=self.fixed_ti,
            wrg_ti_paths=self.wrg_ti_paths if self.use_wrg and self.wrg_ti_paths else None,
            wrg_ti_heights_m=self.wrg_ti_heights_m if self.use_wrg and self.wrg_ti_paths else None,
            project_crs_authid=self.project_crs_authid,
            tol_m=self.tol_m,
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


def _consume_selected_models(dialog: Any, messages: List[DialogStateMessage]) -> List[Dict[str, Any]]:
    """Lee la selección puntual de capas hecha desde el mapa interactivo."""
    try:
        fn_selected = getattr(dialog, "_consume_selected_models_from_turbine_layers", None)
        if callable(fn_selected):
            return list(fn_selected() or [])
    except Exception as exc:
        messages.append(
            DialogStateMessage(
                severity="warning",
                title="AEP",
                message=f"No se pudo usar la selección de capas; se usará el flujo normal: {exc}",
                duration=8,
            )
        )
    return []


def _models_from_selected_layers(selected_models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for idx, model in enumerate(selected_models, start=1):
        if model.get("wt") is None:
            raise DialogStateError("Faltan modelos", f"La capa seleccionada {idx} no tiene modelo de turbina asociado.")
        if not model.get("coords_xy"):
            raise DialogStateError("Coordenadas", f"La capa seleccionada {idx} no tiene aerogeneradores.")
    return list(selected_models)


def _models_from_dialog_rows(dialog: Any) -> List[Dict[str, Any]]:
    rows = list(getattr(dialog, "_rows", []) or [])
    if any(row.get("wt") is None for row in rows):
        raise DialogStateError("Faltan modelos", "Define todos los modelos antes de continuar.")

    # Asegura capas de puntos sin pisar ediciones vivas del mapa interactivo.
    generate_layers = getattr(dialog, "_generate_point_layers_all", None)
    if callable(generate_layers):
        generate_layers(force_reload_csv=False, activate_interactive=False)

    models: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        collect_points = getattr(dialog, "_collect_layer_points_for_row", None)
        live_pts = collect_points(idx) if callable(collect_points) else []
        csv_path = ""
        try:
            csv_widget = row.get("coords_csv_le")
            csv_path = csv_widget.text().strip() if csv_widget else ""
        except Exception:
            csv_path = ""

        if not live_pts and not (csv_path and os.path.isfile(csv_path)):
            raise DialogStateError(
                "Coordenadas",
                f"El Modelo {idx + 1} no tiene coordenadas. Añade turbinas en el mapa interactivo o selecciona un CSV X,Y válido.",
            )

        models.append(
            {
                "name": row.get("name") or "Custom WT",
                "wt": row.get("wt"),
                "meta": row.get("meta"),
                "coords_csv": csv_path,
                "coords_xy": live_pts,
            }
        )
    return models


def _read_resource_inputs(dialog: Any) -> tuple[str, List[str], List[str], List[Optional[float]]]:
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
                raise DialogStateError("WRG", f"El archivo no existe:\n{path}")
            if not path.lower().endswith((".wrg", ".zip")):
                raise DialogStateError("WRG", f"Extensión no soportada (use .wrg o .zip):\n{path}")

        missing_ti = [path for path in wrg_ti_paths if not os.path.isfile(path)]
        if missing_ti:
            raise DialogStateError("Turbulencia WRG", "El/los raster(s) TI no existen:\n" + "\n".join(missing_ti))

        warn_ti_setup = getattr(dialog, "_maybe_warn_about_ti_setup", None)
        if callable(warn_ti_setup):
            warn_ti_setup(use_wrg=True, wrg_ti_paths=wrg_ti_paths, wrg_ti_heights_m=wrg_ti_heights_m)
    else:
        if not wasp_dir or not os.path.isdir(wasp_dir):
            raise DialogStateError("Recurso eólico", "Selecciona una carpeta WAsP válida o un WRG/ZIP.")

    return wasp_dir, wrg_paths, wrg_ti_paths, wrg_ti_heights_m


def build_energy_dialog_state(dialog: Any, project_crs_authid: str) -> EnergyDialogState:
    """Lee el diálogo AEP actual y devuelve un estado normalizado.

    No ejecuta el cálculo. Solo valida mínimos de UI/rutas que antes estaban en
    ``dialog_controller.py`` y prepara la información para ``EnergyRunner``.
    """
    messages: List[DialogStateMessage] = []

    selected_models = _consume_selected_models(dialog, messages)
    use_selected_layers = bool(selected_models)
    if use_selected_layers:
        models = _models_from_selected_layers(selected_models)
        messages.append(
            DialogStateMessage(
                severity="info",
                title="AEP",
                message=f"Cálculo con {len(models)} capa(s) seleccionada(s) desde el mapa interactivo.",
                duration=6,
            )
        )
    else:
        models = _models_from_dialog_rows(dialog)

    wasp_dir, wrg_paths, wrg_ti_paths, wrg_ti_heights_m = _read_resource_inputs(dialog)
    use_wrg = bool(wrg_paths)

    compute_variants = True
    turbulence_model = dialog._get_selected_turbulence_model()
    wfm_engine = dialog._get_selected_wfm_engine() or "PDW"
    blockage_selected = dialog._get_selected_blockage_deficit()
    rotor_avg_model = dialog._get_selected_rotor_avg_model()

    engine_upper = wfm_engine.upper()
    include_turbulence = turbulence_model.upper() not in ("NONE", "NINGUNO")
    include_blockage = engine_upper != "PDW" and blockage_selected.upper() not in ("NONE", "NINGUNO")
    include_rotor_avg = rotor_avg_model.upper() not in ("NONE", "NINGUNO", "NONE (NOOP)")

    fixed_ti = None
    if use_wrg and not wrg_ti_paths:
        fixed_ti_fn = getattr(dialog, "_get_fixed_ti_fraction", None)
        fixed_ti = fixed_ti_fn() if callable(fixed_ti_fn) else None

    return EnergyDialogState(
        models=models,
        wasp_dir=wasp_dir,
        wrg_paths=wrg_paths,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m,
        compute_variants=compute_variants,
        include_turbulence=include_turbulence,
        include_blockage=include_blockage,
        include_rotor_avg=include_rotor_avg,
        rotor_avg_model=rotor_avg_model,
        superposition_model=dialog._get_selected_superposition_model(),
        wfm_engine=wfm_engine,
        wake_deficit_model=dialog._get_selected_wake_deficit(),
        wake_deficit_kwargs=dialog._get_wake_deficit_kwargs(),
        turbulence_model=turbulence_model,
        blockage_deficit_model=("NONE" if engine_upper == "PDW" else blockage_selected),
        fixed_ti=fixed_ti,
        project_crs_authid=project_crs_authid,
        tol_m=30.0,
        use_selected_layers=use_selected_layers,
        messages=messages,
    )
