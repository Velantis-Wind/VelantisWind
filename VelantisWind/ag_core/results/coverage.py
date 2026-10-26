# -*- coding: utf-8 -*-
"""User-facing coverage warning for partial AEP computations.

Keep this warning in one place so the message bar, the result view and the
exported technical HTML never disagree about which turbines were calculated.
"""

from typing import Any, Callable, Dict, Optional


def partial_aep_warning(result: Dict[str, Any], tr: Optional[Callable[[str], str]] = None) -> str:
    """Return a visible explanation of excluded turbines, or '' for full coverage."""
    skipped = int(result.get("skipped_outside_grid") or 0)
    if skipped <= 0:
        return ""
    translate = tr if tr is not None else (lambda s: s)
    inside = int(result.get("turbines_inside_grid", len(result.get("per_turbine_table") or [])))
    by_model = result.get("skipped_by_model") or {}
    details = ", ".join(f"{name}: {count}" for name, count in by_model.items() if int(count) > 0)
    message = translate(
        "Cálculo parcial: {inside} de {total} turbinas dentro del recurso; "
        "{skipped} fuera. El AEP, la potencia instalada y las pérdidas corresponden "
        "solo a las turbinas calculadas."
    ).format(inside=inside, total=inside + skipped, skipped=skipped)
    if details:
        message += " " + translate("Turbinas excluidas por modelo: {details}.").format(details=details)
    message += " " + translate(
        "Las turbinas no calculadas pueden conservar resultados anteriores en su capa; "
        "esos valores no pertenecen a esta simulación."
    )
    return message
