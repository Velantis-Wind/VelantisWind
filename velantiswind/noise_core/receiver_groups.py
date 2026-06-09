# -*- coding: utf-8 -*-
"""
Utilities for normalized receiver-group metadata.

The current UI can work with one or several receiver layers depending on the
selected workflow. This module keeps group serialization and normalization
helpers isolated from the calculation engine.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from typing import Dict, List, Tuple


@dataclass
class ReceiverGroupConfig:
    layer_name: str
    receiver_type: str
    limit_day_dba: float
    limit_night_dba: float
    receiver_height_m: float = 4.0
    enabled: bool = True
    layer_id: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class ReceiverGroupPrepared:
    layer_name: str
    receiver_type: str
    limit_day_dba: float
    limit_night_dba: float
    receiver_height_m: float
    enabled: bool
    layer_id: str = ""
    feature_count: int = 0
    source: str = "manual"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def default_receiver_group_fields() -> List[Tuple[str, str]]:
    """Campos recomendados para una capa de receptores si se quiere usar una sola
    capa avanzada en el futuro. Se devuelven pares (nombre, tipo lógico).
    """
    return [
        ("id_rec", "str"),
        ("nombre", "str"),
        ("tipo_rec", "str"),
        ("h_rec_m", "float"),
        ("lim_d_db", "float"),
        ("lim_n_db", "float"),
        ("obs", "str"),
    ]


def example_receiver_groups() -> List[ReceiverGroupConfig]:
    return [
        ReceiverGroupConfig("receptores_residenciales", "residencial", 45.0, 35.0, 4.0, True),
        ReceiverGroupConfig("receptores_industriales", "industrial", 55.0, 45.0, 4.0, True),
        ReceiverGroupConfig("receptores_sensibles", "sensible", 40.0, 30.0, 4.0, True),
    ]


def save_receiver_groups_json(path: str, groups: List[ReceiverGroupConfig]) -> str:
    data = {"receiver_groups": [g.to_dict() for g in groups]}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_receiver_groups_json(path: str) -> List[ReceiverGroupConfig]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: List[ReceiverGroupConfig] = []
    for raw in list(data.get("receiver_groups") or []):
        out.append(
            ReceiverGroupConfig(
                layer_name=str(raw.get("layer_name") or "").strip(),
                receiver_type=str(raw.get("receiver_type") or "").strip() or "general",
                limit_day_dba=float(raw.get("limit_day_dba", 45.0)),
                limit_night_dba=float(raw.get("limit_night_dba", 35.0)),
                receiver_height_m=float(raw.get("receiver_height_m", 4.0)),
                enabled=bool(raw.get("enabled", True)),
                layer_id=str(raw.get("layer_id") or "").strip(),
                notes=str(raw.get("notes") or "").strip(),
            )
        )
    return out


def validate_receiver_group_configs(groups: List[ReceiverGroupConfig]) -> List[str]:
    issues: List[str] = []
    seen = set()
    for i, g in enumerate(groups, start=1):
        key = g.layer_name.strip().lower()
        if not g.layer_name.strip():
            issues.append(f"Grupo {i}: falta el nombre de capa.")
        if key in seen:
            issues.append(f"Grupo {i}: nombre de capa duplicado '{g.layer_name}'.")
        seen.add(key)
        if g.limit_day_dba < 0 or g.limit_night_dba < 0:
            issues.append(f"Grupo {i} ({g.layer_name}): límites negativos no válidos.")
        if g.receiver_height_m < 0:
            issues.append(f"Grupo {i} ({g.layer_name}): altura negativa no válida.")
    return issues


def prepare_receiver_groups_for_ui(groups: List[ReceiverGroupConfig]) -> List[ReceiverGroupPrepared]:
    """Devuelve una lista normalizada para la futura tabla de UI o validación.
    Aquí todavía no se resuelven capas QGIS; solo se deja la estructura común.
    """
    out: List[ReceiverGroupPrepared] = []
    for g in groups:
        out.append(
            ReceiverGroupPrepared(
                layer_name=g.layer_name,
                receiver_type=g.receiver_type,
                limit_day_dba=float(g.limit_day_dba),
                limit_night_dba=float(g.limit_night_dba),
                receiver_height_m=float(g.receiver_height_m),
                enabled=bool(g.enabled),
                layer_id=g.layer_id,
                feature_count=0,
                source="json-example",
            )
        )
    return out


def receiver_groups_debug_text(groups: List[ReceiverGroupConfig]) -> str:
    lines = ["[Noise][Receiver groups] Configuración preparada:"]
    for i, g in enumerate(groups, start=1):
        lines.append(
            f"  - Grupo {i}: capa='{g.layer_name}' | tipo={g.receiver_type} | día={g.limit_day_dba:.1f} | noche={g.limit_night_dba:.1f} | h={g.receiver_height_m:.1f} m | usar={'sí' if g.enabled else 'no'}"
        )
    return "\n".join(lines)
