# -*- coding: utf-8 -*-
"""Status text builder for completed Noise calculations."""
from __future__ import annotations

from typing import List

from ..i18n import register_language, tr_text


# Previously translated inline by NoisePage's validation. Keep those exact texts
# available when its retained Spanish warning is rendered after a language change.
for _language, _translation in {
    "en": "Layer-based ground mode is active without a valid layer: global G will be used as fallback.",
    "fr": "Le mode de sol par couche est actif sans couche valide : le G global sera utilisé en secours.",
    "de": "Der Layer-basierte Bodenmodus ist ohne gültigen Layer aktiv: Der globale G-Wert wird als Fallback verwendet.",
}.items():
    register_language(_language, {
        "El modo de suelo por capa está activo sin una capa válida: se usará el G global como respaldo.": _translation,
    }, {})


def _layer_name(res: dict, key: str, default: str) -> str:
    """The name of a layer the calculation created: the messages cite the layer as it is in the project."""
    try:
        return str(res.get(key).name() or default)
    except Exception:
        return default


def append_result_status(dialog, res: dict, warnings: List[str], grid_async_pending: bool = False) -> None:
    """Append a human-readable summary to the Noise page status box.

    Each line is a Spanish template translated before its data (layer, group and receiver-type names, numbers) go
    in, so the data never pass through the translator."""
    # Keep the inputs, not the rendered text: the page can recompose this result in another language.
    dialog._result_status = (res, list(warnings), grid_async_pending)
    dialog._check_configuration()
    ac = res.get("acoustic_scenario", {}) or {}
    mode_eff = str(ac.get("mode") or dialog._current_acoustic_mode() or "fixed").lower()
    msgs = [dialog.txt_status.toPlainText().strip(), "", tr_text("Resultado acústico:")]

    for warning in warnings:
        msgs.append(tr_text("• AVISO: {message}").format(message=tr_text(warning)))

    if mode_eff == "curve":
        if bool(ac.get("use_curve_worst_case", False)):
            msgs.append(tr_text("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas en peor caso."))
        else:
            try:
                msgs.append(tr_text("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas a {speed} m/s.").format(
                    speed=f"{float(ac.get('eval_ws_m_s')):.1f}"))
            except Exception:
                msgs.append(tr_text("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas."))
    else:
        msgs.append(tr_text("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con LwA fijo por grupo fuente acústico."))

    eff_models = list(ac.get("effective_models") or [])
    if eff_models:
        msgs.append(tr_text("• Escenario acústico efectivo por grupo fuente:"))
        for d in eff_models:
            name = str(d.get("name") or tr_text("Modelo"))
            lwa_eff = d.get("lwa_effective")
            note = str(d.get("curve_note") or "")
            source = d.get("curve_note_source")
            if source:
                note = tr_text(source["template"]).format(**source["values"])
            try:
                line = tr_text("{name}: LwA efectivo = {lwa} dB(A)").format(name=name, lwa=f"{float(lwa_eff):.2f}")
                msgs.append("   - " + line + ((" · " + note) if note else ""))
            except Exception:
                msgs.append("   - " + tr_text("{name}: {detail}").format(name=name, detail=note or tr_text('sin detalle')))

    msgs.append(tr_text("• Capa de salida principal: {layer}").format(layer=_layer_name(res, "result_layer", "Noise · Receivers")))
    if dialog.chk_multi_receivers.isChecked():
        msgs.append(tr_text("• Receptores por categoría: {n} grupo(s) activos con criterio {criterion}.").format(
            n=dialog.tbl_receiver_groups.rowCount(), criterion=dialog.cb_limit_scenario.currentText().lower()))
    if res.get("sources_layer") is not None:
        msgs.append(tr_text("• Capa GIS de fuentes creada: {layer}").format(layer=_layer_name(res, "sources_layer", "Noise · Sources")))
    if res.get("links_layer") is not None:
        msgs.append(tr_text("• Capa GIS de enlaces dominantes creada: {layer} ({n} enlace(s)).").format(
            layer=_layer_name(res, "links_layer", "Noise · Dominant links"), n=int(res.get("n_dom_links", 0))))
    if res.get("uncovered_layer") is not None:
        msgs.append(tr_text("• Capa GIS de receptores fuera de radio creada: {layer} ({n} receptor(es)).").format(
            layer=_layer_name(res, "uncovered_layer", "Noise · Receivers outside radius"), n=int(res.get("n_uncovered_receivers", 0))))

    grid_diag = res.get("grid_diag", {}) or {}
    if res.get("grid_layer") is not None:
        extra_grid = (" · " + tr_text("resolución autoajustada")) if bool(grid_diag.get("auto_adjusted", False)) else ""
        msgs.append(tr_text("• Mapa GIS creado: {layer} (ráster de {cells} celdas | resolución pedida {requested} m | efectiva {effective} m{extra}).").format(
            layer=_layer_name(res, "grid_layer", "Noise · Map"),
            cells=int(res.get("grid_cells", 0)),
            requested=f"{float(grid_diag.get('requested_resolution_m', 0.0)):.1f}",
            effective=f"{float(grid_diag.get('effective_resolution_m', 0.0)):.1f}",
            extra=extra_grid,
        ))
    elif grid_async_pending:
        msgs.append(tr_text("• Ráster de ruido: lanzado en segundo plano con QgsTask. Los resultados por receptor ya están disponibles; la capa «{layer}» se añadirá al terminar.").format(
            layer="Noise · Map"))
        if bool(dialog.chk_iso.isChecked()):
            msgs.append(tr_text("• Isófonas: se generarán al finalizar el ráster en segundo plano."))
    elif bool(dialog.chk_generate_grid.isChecked()):
        msgs.append(tr_text("• AVISO: se solicitó el ráster pero no se pudo generar. Revisa la resolución, el CRS y la extensión de las fuentes."))
    for gw in list(res.get("grid_warnings") or []):
        msgs.append(tr_text("• AVISO: {message}").format(message=tr_text(gw)))
    if res.get("iso_layer") is not None:
        msgs.append(tr_text("• Capa GIS de isófonas creada: {layer} ({n} entidades).").format(
            layer=_layer_name(res, "iso_layer", "Noise · Isophones"), n=int(res.get("n_iso_features", 0))))
    elif res.get("grid_layer") is not None and res.get("iso_requested"):
        msgs.append(tr_text("• AVISO: se solicitaron las isófonas pero no se pudieron generar."))

    rtypes = res.get("receiver_type_counts", {}) or {}
    if rtypes:
        msgs.append(tr_text("• Receptores por categoría: {counts}").format(counts=", ".join([f"{k}={v}" for k, v in sorted(rtypes.items())])))
    n_all = int(res.get("n_receivers", 0))
    n_with = int(res.get("n_receivers_with_sources", 0))
    msgs.append(tr_text("• Receptores calculados: {n}").format(n=n_all))
    msgs.append(tr_text("• Receptores con al menos una turbina dentro del radio: {n}").format(n=n_with))
    if n_all > 0 and n_with == 0:
        msgs.append(tr_text("• AVISO: todos los receptores han quedado fuera del radio máximo. Revisa radio, layout o ubicación de receptores."))
    msgs.append(tr_text("• Receptores que superan el límite: {n} / {total}").format(n=int(res.get("n_receivers_exceeding_limit", 0)), total=n_all))
    msgs.append(tr_text("• Nivel máximo calculado: {level} dB(A)").format(level=f"{float(res.get('max_noise_dba', 0.0)):.2f}"))
    msgs.append(tr_text("• α usado: {alpha} dB/m").format(alpha=f"{float(res.get('alpha_db_per_m', 0.0)):.4f}"))
    msgs.append(tr_text("• G usado: {g}").format(g=f"{float(res.get('ground_factor_g', 0.0)):.2f}"))

    gd = res.get("ground_diag", {}) or {}
    gs = res.get("g_eff_stats", {}) or {}
    if str(res.get("ground_mode") or "global").lower() == "landuse":
        msgs.append(tr_text("• Suelo efectivo: G_eff medio {mean} | G_eff crítico {critical}.").format(
            mean=f"{float(gs.get('mean', res.get('ground_factor_g', 0.0))):.2f}",
            critical=f"{float(gs.get('critical', res.get('ground_factor_g', 0.0))):.2f}"))
        msgs.append(tr_text("• Trazabilidad del suelo: {landuse} receptor(es) con G distinto del global y {fallback} con el G global de respaldo.").format(
            landuse=int(gd.get("from_landuse_count", 0)), fallback=int(gd.get("fallback_count", 0))))
    else:
        msgs.append(tr_text("• Suelo efectivo: modo global, G={g} aplicado en todos los trayectos.").format(g=f"{float(res.get('ground_factor_g', 0.0)):.2f}"))
    if bool(res.get("dem_used", False)):
        msgs.append(tr_text("• Se ha usado el MDT/DSM para muestrear la cota del terreno en fuentes y receptores."))
        msgs.append(tr_text("• Aground representa la pérdida simplificada asociada al efecto suelo/terreno en el método acústico."))
    else:
        msgs.append(tr_text("• Sin MDT/DSM: el cálculo usa coordenadas planas con alturas relativas de fuente/receptor."))

    dialog.txt_status.setPlainText("\n".join([m for m in msgs if m]))
