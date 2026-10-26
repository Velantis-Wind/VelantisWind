"""QGIS-free comparison of user selections and executed physics."""
import re
from html import escape
from ..log_text import shown
from ..wake_setup.readers import PASSED, WS_REFERENCE_TEXT, executed_ws_reference
from ..wake_setup.api import legacy_note
from ..simulation.zero_node import AUXILIARY_LABEL, zero_node_note


# The positions of the configuration in the report (schema 2), with their labels.
POSITIONS_V2 = (("engine", "Motor"), ("deficit", "Déficit de estela"), ("rotor", "Promedio rotor"),
                ("ground", "Efecto suelo (estela)"), ("superposition", "Superposición"),
                ("turbulence", "Modelo de turbulencia"), ("blockage", "Modelo de bloqueo"),
                ("blockage_superposition", "Superposición del bloqueo"))
# The positions of a schema-1 result (``selection_*``), with their labels: the report and the comparator.
POSITIONS_V1 = (("engine", "Motor"), ("wake_deficit", "Déficit de estela"), ("turbulence", "Modelo de turbulencia"),
                ("blockage", "Modelo de bloqueo"), ("rotor_avg", "Promedio rotor"), ("superposition", "Superposición"),
                ("ground", "Efecto suelo (estela)"))


_URL = re.compile(r"https?://[^\s<]+")


def linked(text):
    """``text`` escaped for HTML, with its web addresses as links (the documentation of a predefined model)."""
    return _URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', escape(str(text)))


def _value_text(value):
    if isinstance(value, list):
        return "[" + ", ".join(_value_text(v) for v in value) + "]"
    return str(value)


def _component_text(entry, tr):
    """``Class(arg=value, …)`` of a component of the configuration (``{class, params}``); «Ninguno» if absent.

    In what was executed, an argument the object does not keep is marked as the argument passed (P0, section 7).
    A nested component (#64) is shown the same way, recursively: in the selection it is ``{class, params}``; in what
    was executed, ``{value: {class, params, …}, source}``.
    """
    if not entry:
        return tr("Ninguno")
    values = []
    for k, v in (entry.get("params") or {}).items():
        value, source = (v.get("value"), v.get("source")) if isinstance(v, dict) and "source" in v else (v, None)
        text = _component_text(value, tr) if isinstance(value, dict) and "class" in value else _value_text(value)
        values.append(f"{k}={text}" + (f" [{tr('argumento pasado')}]" if source == PASSED else ""))
    if "nodes" in entry:  # also 0: EqGridRotorAvg with n ≤ 0 keeps no node
        values.append(f"{tr('nodos')}={entry['nodes']}")
    if "WS_key" in entry:  # the reference of the deficit's scaling (TurbOPark), observed
        values.append(f"WS_key={entry['WS_key']}")
    return entry["class"] + (f"({', '.join(values)})" if values else "")


def _reference_text(reference, tr):
    """«velocidad libre de la turbina de destino (WS_jlk)», or that of its class."""
    if reference is None:
        return tr("La de la clase (use_effective_ws)")
    from ..wake_setup.factory import WS_KEYS
    return f"{tr(WS_REFERENCE_TEXT.get(reference, reference))} ({WS_KEYS.get(reference, '?')})"


def executed_rows(result):
    """The executed class of each position of a schema-2 result, ``None`` for an absent one (the comparator's)."""
    executed = (result.get("wake_config") or {}).get("executed") or {}
    return {p: (executed.get(p) or {}).get("class") for p, _l in POSITIONS_V2}


def model_config_html_v2(result, tr=lambda text: text):
    """The configuration of a schema-2 result: what the user selected against what was executed, read from the
    built objects, with the differences highlighted, the accepted adaptations, the persistent warnings and the
    convergence (#46: never «preset» nor «referencia»)."""
    wc = result.get("wake_config") or {}
    selected, executed = wc.get("selected") or {}, wc.get("executed") or {}
    differing = {d.get("position") for d in wc.get("differences_vs_selection") or []}
    rows = []
    for position, label in POSITIONS_V2:
        style = "background:#fff3cd;" if position in differing else ""
        cells = [tr(label), _component_text(selected.get(position), tr), _component_text(executed.get(position), tr)]
        rows.append(f"<tr style='{style}'>" + "".join(
            f"<td style='border:1px solid #ccd9d4;padding:6px;'>{escape(cell)}</td>" for cell in cells) + "</tr>")
    # The reference of the deficit's scaling (TurbOPark), a row of its own only where it is used.
    chosen, done = selected.get("deficit_ws_reference"), executed_ws_reference(executed)
    if chosen is not None or done is not None:
        style = ("background:#fff3cd;" if any(d.get("param") == "deficit_ws_reference"
                                              for d in wc.get("differences_vs_selection") or []) else "")
        cells = [tr("Referencia del escalado"), _reference_text(chosen, tr), _reference_text(done, tr)]
        rows.append(f"<tr style='{style}'>" + "".join(
            f"<td style='border:1px solid #ccd9d4;padding:6px;'>{escape(cell)}</td>" for cell in cells) + "</tr>")
    status = (tr("Lo ejecutado difiere de la selección en las filas resaltadas.") if differing
              else tr("Lo ejecutado es exactamente la selección."))
    parts = ["<h4>" + escape(tr("Modelos seleccionados y utilizados en el cálculo")) + "</h4>",
             "<p><b>" + escape(status) + "</b></p>",
             "<p>" + escape(str(shown(wc.get("identification") or "", tr))) + "</p>",
             "<table width='100%' cellspacing='0' cellpadding='6' style='border-collapse:collapse;'>"
             "<tr style='background:#eef5f2;'>" + "".join(
                 "<th>" + escape(tr(h)) + "</th>" for h in ("Componente", "Selección del usuario",
                                                             "Configuración ejecutada (leída de los objetos)"))
             + "</tr>" + "".join(rows) + "</table>"]
    # The persistent warnings carry the accepted adaptations too (with how to install what was missing).
    items = [str(shown(w, tr)) for w in result.get("persistent_warnings") or []]
    for part, label in (("main", "Cálculo principal"), ("variants", "Variantes del desglose"),
                        ("auxiliary_zero", AUXILIARY_LABEL)):
        for loop, entry in ((result.get("convergence") or {}).get(part) or {}).items():
            if entry.get("converged"):
                continue
            # A state that could not be read is not available, never «not converged» (decision 6.5 of #64).
            # The states of the calls that were read, with their counts; the others, apart.
            states = {k: v for k, v in (entry.get("states") or {}).items() if k != "unavailable"}
            if "unavailable" in (entry.get("states") or {}):
                text = tr("{part}: convergencia de {loop} no disponible en {count} de {calls} ({reasons}).")
                items.append(text.format(part=tr(label), loop=loop, count=entry["states"]["unavailable"],
                                         calls=entry.get("calls"),
                                         reasons="; ".join(entry.get("unavailable_reasons") or [])
                                         or tr("causa no registrada")))  # a result saved before 6.5
            if entry.get("non_finite_residuals"):
                items.append(tr("{part}: {loop}, {count} residuo(s) no finito(s).").format(
                    part=tr(label), loop=loop, count=entry["non_finite_residuals"]))
            if set(states) <= {"converged"}:
                continue
            if set(states) == {"no_check"}:  # one iteration: never «converged» (#64)
                items.append(tr("{part}: {loop}, una iteración; convergencia no comprobada.").format(
                    part=tr(label), loop=loop))
            else:
                states_text = ", ".join(f"{k} × {v}" for k, v in sorted(states.items()))
                items.append(tr("{part}: {loop} no convergió ({states}).").format(part=tr(label), loop=loop,
                                                                                  states=states_text))
    if wc.get("legacy_request"):
        items.append(str(shown(legacy_note(wc["legacy_request"]), tr)))
    # The edge cases (#63), only when the result has them: their warnings, and the note of the exception of WeightedSum.
    items += [str(shown(w, tr)) for w in (result.get("edge_cases") or {}).get("warnings") or []]
    if result.get("executed_ws"):
        items.append(str(shown(zero_node_note(result["executed_ws"]), tr)))
    if items:
        parts.append("<ul>" + "".join(f"<li>{linked(i)}</li>" for i in items) + "</ul>")
    return "".join(parts)


def model_config_html(result, tr=lambda text: text):
    if result.get("wake_config"):
        return model_config_html_v2(result, tr)
    user = result.get("selection_user") or {}
    requested = result.get("selection_requested") or {}
    executed = result.get("selection_executed") or {}
    if not (user or requested or executed):
        return ""
    missing = tr("No registrado")
    rows = []
    changed = []
    for key, label in POSITIONS_V1:
        if not any(key in cfg for cfg in (user, requested, executed)):
            continue
        differs = key in requested and key in executed and str(requested[key]) != str(executed[key])
        if differs:
            changed.append(label)
        style = "background:#fff3cd;" if differs else ""
        cells = [tr(label)] + [str(cfg.get(key, missing)) for cfg in (user, requested, executed)]
        rows.append(f"<tr style='{style}'>" + "".join(
            f"<td style='border:1px solid #ccd9d4;padding:6px;'>{escape(cell)}</td>" for cell in cells
        ) + "</tr>")
    degraded = bool(result.get("simulation_degraded"))
    if degraded:
        status = tr("El cálculo ha utilizado una configuración alternativa.")
    elif changed:
        status = tr("Se han aplicado ajustes automáticos o valores de fábrica del modelo.")
    elif executed:
        status = tr("Configuración ejecutada registrada.")
    else:
        status = tr("No se ha registrado la configuración ejecutada.")
    reason = str(result.get("simulation_degradation_label") or "")
    if degraded and reason:
        if reason.startswith("bloqueo alternativo:"):
            reason = tr("bloqueo alternativo: {model}").format(model=reason.split(":", 1)[1].strip())
        else:
            reason = tr(reason)
        status += " " + tr("Paso aplicado: {step}.").format(step=reason)
    description = (
        "El AEP neto corresponde a la columna «Configuración finalmente ejecutada». "
        "La configuración solicitada al solver incluye la resolución de AUTO y los ajustes de compatibilidad. "
        "Las filas resaltadas muestran diferencias respecto a esa configuración."
    )
    headers = ("Componente", "Selección del usuario", "Configuración solicitada al solver",
               "Configuración finalmente ejecutada")
    return (
        "<h4>" + escape(tr("Modelos seleccionados y utilizados en el cálculo")) + "</h4>"
        "<p><b>" + escape(status) + "</b></p>"
        "<p>" + escape(tr(description)) + "</p>"
        "<table width='100%' cellspacing='0' cellpadding='6' style='border-collapse:collapse;'>"
        "<tr style='background:#eef5f2;'>" + "".join("<th>" + escape(tr(h)) + "</th>" for h in headers) + "</tr>"
        + "".join(rows) + "</table>"
    )


def format_report_note(note, tr=lambda text: text):
    """Translate application templates while preserving technical diagnostic data."""
    return str(shown(note, tr))
