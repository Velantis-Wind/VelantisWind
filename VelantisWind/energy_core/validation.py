# -*- coding: utf-8 -*-
"""Validaciones desacopladas para el módulo de energía."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
import os

from ..ag_core.resource_grid import (
    WD_INTERP_METHODS, WrgContractError, direction_options, initial_direction_count, validate_request,
    validate_speed_step,
)
from ..ag_core.log_text import shown
from ..ag_core.wake_setup.api import LEGACY_FIELDS, RequestError, resolve_request
from ..ag_core.wake_setup.validation import validate as validate_wake
from .domain import EnergyRunConfig, TurbineModelInput
from ..ag_core.wake_setup.messages_translations import register_messages_translations

register_messages_translations()  # the reasons of the physics, translated before the calculation
from .translation import tr


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity.lower() == "error"


def _has_live_points(model: TurbineModelInput) -> bool:
    try:
        return bool(model.coords_xy) and len(model.coords_xy or []) > 0
    except Exception:
        return False


def validate_energy_config(config: EnergyRunConfig) -> List[ValidationIssue]:
    """Valida configuración antes de invocar PyWake/ag_core.

    La idea es fallar pronto con mensajes claros de usuario, en vez de dejar que
    PyWake falle varios niveles más abajo con trazas difíciles de interpretar.
    """
    issues: List[ValidationIssue] = []

    if not config.models:
        issues.append(ValidationIssue("error", tr("No se ha definido ningún modelo de aerogenerador.")))

    for idx, model in enumerate(config.models, start=1):
        label = model.name or tr("Modelo {n}").format(n=idx)
        if model.wt is None:
            issues.append(ValidationIssue("error", tr("{label}: falta definir la turbina/curva de potencia.").format(label=label)))
        if not _has_live_points(model):
            csv_path = (model.coords_csv or "").strip()
            if not csv_path:
                issues.append(ValidationIssue("error", tr("{label}: faltan coordenadas. Elige su capa de turbinas o añade puntos en el mapa.").format(label=label)))
            elif not os.path.isfile(csv_path):
                issues.append(ValidationIssue("error", tr("{label}: el CSV de coordenadas no existe: {path}").format(label=label, path=csv_path)))

    # Los resultados por modelo se indexan por nombre (vacío = "Custom WT").
    # Varias capas de una misma fila (mismo source_row_index >= 0, como en
    # canonicalize_models) sí pueden compartirlo.
    rows_by_name = {}
    for idx, model in enumerate(config.models):
        name = str(model.name or "Custom WT").strip()
        try:
            row = int(model.source_row_index)
        except Exception:
            row = -1
        rows_by_name.setdefault(name, set()).add(row if row >= 0 else ("entry", idx))
    for name, rows in rows_by_name.items():
        if len(rows) > 1:
            issues.append(ValidationIssue("error", tr("Hay varios modelos llamados «{name}». Usa un nombre distinto para cada modelo.").format(name=name)))

    wrg_paths = [p for p in (config.wrg_paths or []) if str(p).strip()]
    if wrg_paths:
        for p in wrg_paths:
            if not os.path.isfile(p):
                issues.append(ValidationIssue("error", tr("WRG/ZIP no existe: {path}").format(path=p)))
            elif not str(p).lower().endswith((".wrg", ".zip")):
                issues.append(ValidationIssue("error", tr("Extensión WRG no soportada. Usa .wrg o .zip: {path}").format(path=p)))
    else:
        if not config.wasp_dir or not os.path.isdir(config.wasp_dir):
            issues.append(ValidationIssue("error", tr("Selecciona una carpeta WAsP válida o un WRG/ZIP.")))

    for p in (config.wrg_ti_paths or []):
        if p and not os.path.isfile(p):
            issues.append(ValidationIssue("error", tr("Ráster TI no existe: {path}").format(path=p)))

    # The wake physics, read with the contract of the API and validated with the rules of PyWake and the plugin
    # (the calculation reads it the same way): what cannot be calculated is refused, never changed.
    try:
        physics, _notes = resolve_request(config.wake_physics,
                                          **{n: getattr(config, n) for n in LEGACY_FIELDS if n != "wake_model"})
    except RequestError as exc:
        issues.append(ValidationIssue("error", shown(exc.args[0], tr)))
    else:
        for issue in validate_wake(physics):
            issues.append(ValidationIssue("error", issue.translated(tr)))
        if config.use_wrg and not config.wrg_ti_paths and physics.turbulence is not None:
            issues.append(ValidationIssue("warning", tr("No se ha seleccionado ráster TI para WRG; se usará TI fija/de respaldo si el modelo lo necesita.")))

    issues += _resource_issues(config, wrg_paths)

    return issues


def _wrg_sectors(path: str) -> List[int]:
    """The sectors of each WRG in ``path`` (each member of a ZIP), from their light metadata; none if they cannot
    be read (loading reports why)."""
    try:
        from ..ag_core.wrg_reader import read_wrg_meta

        return list(read_wrg_meta(path).get("n_sectors_list") or [])
    except Exception:
        return []


def _resource_issues(config: EnergyRunConfig, wrg_paths: List[str]) -> List[ValidationIssue]:
    """The resource settings, checked with the rules of ``resource_grid`` and never rounded.

    The Speedup is always ``none``; with a WRG, the interpolation, the step of the
    wind speeds and the number of directions (against the sectors of each WRG) too.
    """
    issues: List[ValidationIssue] = []
    if config.wrg_speedup_method != "none":
        issues.append(ValidationIssue("error", tr(
            "Speedup no válido: {value}. Con un WRG solo se admite none: se conservan en cada punto las Weibull y "
            "frecuencias locales del WRG."
        ).format(value=repr(config.wrg_speedup_method))))
    if not wrg_paths:
        return issues
    method = config.wrg_wd_interp
    if not (isinstance(method, str) and method in WD_INTERP_METHODS):
        issues.append(ValidationIssue("error", tr(
            "Interpolación direccional no válida: {value}. Se admiten nearest y linear."
        ).format(value=repr(method))))
        method = "nearest"  # only to go on checking the directions
    if config.energy_ws_step is not None:
        try:
            validate_speed_step(config.energy_ws_step, "")
        except WrgContractError:
            issues.append(ValidationIssue("error", tr(
                "Paso de las velocidades de cálculo no válido: {value}. Se admiten 1, 0,5 y 0,25 m/s."
            ).format(value=repr(config.energy_ws_step))))
    sectors = {p: _wrg_sectors(p) for p in wrg_paths if os.path.isfile(p)}
    sectors = {p: ns for p, ns in sectors.items() if ns}
    if len({n for ns in sectors.values() for n in ns}) > 1:
        issues.append(ValidationIssue("error", tr(
            "Los WRG no tienen los mismos sectores ({sectors}): no se pueden combinar."
        ).format(sectors=", ".join(f"{os.path.basename(p)}: {'/'.join(str(n) for n in ns)}" for p, ns in sectors.items()))))
    elif sectors:
        path, (n, *_rest) = next(iter(sectors.items()))
        count = initial_direction_count(n) if config.wrg_direction_count is None else config.wrg_direction_count
        try:
            validate_request(n, count, method, path)
        except WrgContractError:
            issues.append(ValidationIssue("error", tr(
                "Número de direcciones de cálculo no válido: {value}. El WRG «{path}» tiene {n} sectores: se admiten "
                "{options}."
            ).format(value=repr(config.wrg_direction_count), path=os.path.basename(path), n=n,
                     options=", ".join(str(o) for o in direction_options(n)))))
    return issues


def format_validation_issues(issues: List[ValidationIssue]) -> str:
    if not issues:
        return ""
    lines = []
    for issue in issues:
        prefix = tr("ERROR") if issue.is_error else tr("AVISO")
        lines.append(f"[{prefix}] {issue.message}")
    return "\n".join(lines)
