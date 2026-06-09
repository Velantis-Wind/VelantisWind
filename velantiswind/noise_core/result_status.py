# -*- coding: utf-8 -*-
"""Status text builder for completed Noise calculations."""
from __future__ import annotations

from typing import List


def append_result_status(dialog, res: dict, warnings: List[str], grid_async_pending: bool = False) -> None:
    """Append a human-readable summary to the Noise page status box."""
    dialog._check_configuration()
    ac = res.get("acoustic_scenario", {}) or {}
    mode_eff = str(ac.get("mode") or dialog._current_acoustic_mode() or "fixed").lower()
    msgs = [dialog.txt_status.toPlainText().strip(), "", "Resultado acústico:"]

    for warning in warnings:
        msgs.append(f"• AVISO: {warning}")

    if mode_eff == "curve":
        if bool(ac.get("use_curve_worst_case", False)):
            msgs.append("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas en peor caso.")
        else:
            try:
                msgs.append(f"• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas a {float(ac.get('eval_ws_m_s')):.1f} m/s.")
            except Exception:
                msgs.append("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con curvas acústicas.")
    else:
        msgs.append("• Método usado: Modelo fuente-receptor eólico (Adiv + Aatm + Aground) con LwA fijo por grupo fuente acústico.")

    eff_models = list(ac.get("effective_models") or [])
    if eff_models:
        msgs.append("• Escenario acústico efectivo por grupo fuente:")
        for d in eff_models:
            name = str(d.get("name") or "Modelo")
            lwa_eff = d.get("lwa_effective")
            note = str(d.get("curve_note") or "")
            try:
                msgs.append(f"   - {name}: LwA efectivo = {float(lwa_eff):.2f} dB(A){(' · ' + note) if note else ''}")
            except Exception:
                msgs.append(f"   - {name}: {note or 'sin detalle'}")

    result_layer = res.get("result_layer")
    layer_name = result_layer.name() if result_layer is not None and hasattr(result_layer, "name") else "Noise · Receivers"
    msgs.append(f"• Main output layer: {layer_name}")
    if dialog.chk_multi_receivers.isChecked():
        msgs.append(f"• Receivers by category: activos {dialog.tbl_receiver_groups.rowCount()} grupo(s) con criterio {dialog.cb_limit_scenario.currentText().lower()}.")
    if res.get("sources_layer") is not None:
        msgs.append("• GIS source layer created: Noise · Sources")
    if res.get("links_layer") is not None:
        msgs.append(f"• GIS dominant-links layer created: Noise · Dominant links ({int(res.get('n_dom_links', 0))} enlace(s)).")
    if res.get("uncovered_layer") is not None:
        msgs.append(f"• GIS receivers-outside-radius layer created: Noise · Receivers fuera de radio ({int(res.get('n_uncovered_receivers', 0))} receptor(es)).")

    grid_diag = res.get("grid_diag", {}) or {}
    if res.get("grid_layer") is not None:
        extra_grid = " · resolución autoajustada" if bool(grid_diag.get("auto_adjusted", False)) else ""
        msgs.append(
            f"• Mapa GIS creado: Noise · Map (raster {int(res.get('grid_cells', 0))} celdas | "
            f"resolución pedida {float(grid_diag.get('requested_resolution_m',0.0)):.1f} m | "
            f"efectiva {float(grid_diag.get('effective_resolution_m',0.0)):.1f} m{extra_grid})."
        )
    elif grid_async_pending:
        msgs.append("• Raster de ruido: lanzado en segundo plano con QgsTask. Los resultados por receptor ya están disponibles; la capa 'Noise · Map' se añadirá al terminar.")
        if bool(dialog.chk_iso.isChecked()):
            msgs.append("• Isófonas: se generarán al finalizar el raster en segundo plano.")
    elif bool(dialog.chk_generate_grid.isChecked()):
        msgs.append("• AVISO: se solicitó el raster pero no se pudo generar. Revisa la resolución, el CRS y el extent de las fuentes.")
    for gw in list(res.get("grid_warnings") or []):
        msgs.append(f"• AVISO: {gw}")
    if res.get("iso_layer") is not None:
        msgs.append(f"• GIS isophone layer created: Noise · Isophones ({int(res.get('n_iso_features', 0))} entidades).")

    rtypes = res.get("receiver_type_counts", {}) or {}
    if rtypes:
        msgs.append("• Receivers by category: " + ", ".join([f"{k}={v}" for k, v in sorted(rtypes.items())]))
    n_all = int(res.get("n_receivers", 0))
    n_with = int(res.get("n_receivers_with_sources", 0))
    msgs.append(f"• Calculated receivers: {n_all}")
    msgs.append(f"• Receivers with at least one turbine inside the radius: {n_with}")
    if n_all > 0 and n_with == 0:
        msgs.append("• AVISO: todos los receptores han quedado fuera del radio máximo. Revisa radio, layout o ubicación de receptores.")
    msgs.append(f"• Receivers exceeding the limit: {int(res.get('n_receivers_exceeding_limit', 0))} / {n_all}")
    msgs.append(f"• Maximum calculated level: {float(res.get('max_noise_dba', 0.0)):.2f} dB(A)")
    msgs.append(f"• α usado: {float(res.get('alpha_db_per_m', 0.0)):.4f} dB/m")
    msgs.append(f"• G usado: {float(res.get('ground_factor_g', 0.0)):.2f}")

    gd = res.get("ground_diag", {}) or {}
    gs = res.get("g_eff_stats", {}) or {}
    if str(res.get("ground_mode") or "global").lower() == "landuse":
        msgs.append(f"• Effective ground: G_eff medio {float(gs.get('mean', res.get('ground_factor_g', 0.0))):.2f} | critical G_eff {float(gs.get('critical', res.get('ground_factor_g', 0.0))):.2f}.")
        msgs.append(f"• Ground traceability: {int(gd.get('from_landuse_count',0))} receptor(es) con G distinto del global y {int(gd.get('fallback_count',0))} en fallback/global.")
    else:
        msgs.append(f"• Effective ground: modo global, G={float(res.get('ground_factor_g', 0.0)):.2f} aplicado en todos los trayectos.")
    if bool(res.get("dem_used", False)):
        msgs.append("• DEM/DSM was used to sample terrain elevation at sources and receivers.")
        msgs.append("• Aground representa la pérdida simplificada asociada al efecto suelo/terreno en el método acústico.")
    else:
        msgs.append("• No DEM/DSM: calculation uses flat coordinates with relative source/receiver heights.")

    dialog.txt_status.setPlainText("\n".join([m for m in msgs if m]))
