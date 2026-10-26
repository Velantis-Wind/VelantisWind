"""Synthetic screen data and traversal. Importing this module does not initialize Qt."""
from . import i18n_m4b_fixture as f


def aep_result():
    import numpy as np
    from VelantisWind.ag_core.results import breakdown as bd, result_v2
    A0 = np.array([100.0, 100.0, 100.0])
    AW = np.array([90.0, 80.0, 100.0])
    AWT = np.array([92.0, 79.0, 100.0])
    AWB = np.array([89.0, 79.5, 100.5])
    AWTB = np.array([91.0, 78.0, 100.6])
    XY = [(500000.0, 4400000.0), (501000.0, 4400000.0), (502000.0, 4400000.0)]
    MODELS = [{"name": "WTG-A", "meta": {"diam": 120, "hh": 100, "p_rated_mw": 4.0}},
              {"name": "WTG-B", "meta": {"diam": 150, "hh": 120, "p_rated_mw": 5.0}}]
    aep = {"A_0": A0, "A_W": AW, "A_WT": AWT, "A_WB": AWB, "A_WTB": AWTB}
    aep_states = {k: bd.OK for k in bd.AEP_TERMS}
    states = bd.term_states(aep_states=aep_states, turbulence=True, blockage=True,
                            turbulence_changes_deficit=True)
    return result_v2.build_result(
        models=MODELS, xs=[x for x, _ in XY], ys=[y for _, y in XY], use_types=True, type_i=np.array([0, 0, 1]),
        skipped=0, skipped_by_model={}, aep=aep, aep_states=aep_states, term_states=states, errors={},
        ti_ambient=np.array([0.08, 0.08, 0.09]), ti_effective=np.array([0.11, np.nan, 0.12]),
        aep_per_wd_wake_mwh=[150.0, 119.6], aep_per_wd_free_mwh=[140.0, 160.0], sector_directions_deg=[0.0, 180.0],
        resource_settings={"hours_per_year": 8766.0})

def noise_result():
    lw = {63: 95.0, 125: 98.0, 250: 99.0, 500: 98.0, 1000: 96.0, 2000: 93.0, 4000: 88.0, 8000: 82.0}
    spectrum = "Biblioteca: S-01.csv · normalizado a LwA del grupo"
    rows = [
        {"rec_id": "R-7", "rec_type": "P-01", "noise_dba": 46.2, "limit_dba": 45.0, "margin_db": 1.2, "state": "supera",
         "exceeds": 1, "n_src": 3, "near_m": 500.0, "dom_model": "M-01", "dom_group": "G-01",
         "dom_park": "P-01", "src_lwa": 105.0, "adiv_db": 65.0, "aatm_db": 2.0, "aground_db": 1.0, "abar_max_db": 0.0,
         "ground_g": 0.5, "ground_md": "from_layer", "rec_h_m": 4.0, "rec_z_m": 100.0, "rec_ac_z_m": 104.0,
         "dom_src_lyr": "/synthetic/L-01.gpkg"},
        {"rec_id": "R-8", "rec_type": "", "noise_dba": 40.0, "limit_dba": 45.0, "margin_db": -5.0, "state": "cumple",
         "exceeds": 0, "n_src": 2, "near_m": 900.0, "dom_model": "M-02", "dom_group": "G-01",
         "dom_park": "P-01", "src_lwa": 105.0, "adiv_db": 70.0, "aatm_db": 3.0, "aground_db": 1.5, "abar_max_db": 0.0,
         "ground_g": 0.5, "ground_md": "global", "rec_h_m": 4.0, "rec_z_m": 90.0, "rec_ac_z_m": 94.0,
         "dom_src_lyr": "G-01"},
    ]
    group = {"count": 3, "lwa": 105.0, "hub_height": 100.0, "diameter": 120.0}
    return {
        "n_sources": 5, "n_receivers": 3, "n_receivers_with_sources": 2, "n_uncovered_receivers": 1,
        "n_receivers_exceeding_limit": 1, "max_noise_dba": 46.2,
        "model_diag": {
            "M-01": dict(group, name="G-01", model_name="M-01", park_name="P-01",
                                     acoustic_mode="curve", curve_path="/synthetic/C-01.csv",
                                     curve_note="Curva @ 8.0 m/s (C-01.csv)"),
            "M-02": dict(group, name="P-01", model_name="M-02", acoustic_mode="fixed"),
            "G-01": dict(group, name="G-01", model_name="G-01", acoustic_mode="curve",
                             curve_path="/synthetic/C-02.csv", curve_note=""),
        },
        "receiver_type_counts": {"P-01": 1, "no_type": 2},
        "receiver_type_compliance": {"P-01": {"exceed": 1, "total": 1, "covered": 1}},
        "critical_receiver": {"rec_id": "R-7", "total_level_dba": 46.2, "limite_aplicado_dba": 45.0,
                              "limit_margin_db": 1.2, "modelo_dominante": "M-01",
                              "grupo_fuente_dominante": "G-01", "parque_dominante": "P-01",
                              "turbines_in_radius": 3, "banda_dominante_hz": 500, "spectrum_source": spectrum},
        "report_meta": {"engine": "iso_aligned", "dem_used": True, "dem_layer_name": "L-04",
                        "landuse_used": True, "landuse_layer_name": "L-03", "ground_mode": "landuse",
                        "spectrum_sources": [{"group_name": "G-01", "model_name": "M-01",
                                              "spectrum_source": spectrum, "lw_octave": lw,
                                              "spectrum_template_ref": {}, "spectrum_delta_db": float("nan")}]},
        "acoustic_scenario": {"mode": "fixed", "effective_models": [
            {"name": "G-01", "model_name": "M-01", "park_name": "P-01", "lwa_effective": 105.0}]},
        "receiver_rows": rows,
        "top_receivers": rows,
    }


def build(lang, history):
    """Real widgets, neutral data, synthetic numerical results, no physical engine."""
    from VelantisWind.ag_core.turbine_ui import CustomTurbineDialog
    from VelantisWind.results_dialog import AEPResultsDialog
    from VelantisWind.noise_results_dialog import NoiseResultsDialog
    from VelantisWind import plugin  # Registers the same tables as plugin startup.
    from unittest import mock
    # Reuse the M4b setup; replace its deliberately adversarial curve filename.
    source = {'template': 'Curva @ {speed} m/s ({file})',
              'values': {'speed': '8.5', 'file': 'C-01.csv'}}
    original = f.point_layer
    def layer(name, model=False):
        result = original('L-01' if model else 'L-02', model)
        if model:
            result.setCustomProperty('velantis/model_name', 'M-01')
        return result
    original_set = f.QtCore.QSettings.setValue
    def set_value(settings, key, value):
        if isinstance(value, str):
            value = {'Removed preset': 'P-00', 'Removed class': 'C-00'}.get(value, value)
        return original_set(settings, key, value)
    with mock.patch.object(f, 'point_layer', side_effect=layer), \
            mock.patch.object(f, 'CURVE_SOURCE', source), \
            mock.patch.object(f.QtCore.QSettings, 'setValue', new=set_value):
        ui = f.build(lang, history)
    hub, energy = ui[:2]
    f.QgsProject.instance().setTitle('P-01')
    energy._rows[0]['name'] = 'M-01'
    energy._refresh_model_row_header(0)
    energy.ed_wrg_ti_heights.setText('90;?')
    hub.page_noise.refresh_from_project()
    hub.page_flicker.refresh_from_project()
    f.append_result_status(hub.page_noise, noise_result(), [f.NOISE_WARNING])
    roots = dict(hub=hub, energy=energy, turbine=CustomTurbineDialog(),
                 aep=AEPResultsDialog(None, aep_result()), noise=NoiseResultsDialog(None, noise_result()))
    return ui, roots


def capture(root):
    """Exercise every tab/page and fold, including hidden contents, then read public texts."""
    from VelantisWind.ui_core.wake_controls import CollapsibleSection
    QtWidgets = f.QtWidgets
    counts = dict(tabs=0, pages=0, folds=0)
    observed = {}
    def record():
        for key, value in f.snapshot(root).items():
            values = [(key + '/' + attr, text) for attr, text in zip(('text', 'toolTip'), value)] \
                if isinstance(value, (tuple, list)) else [(key, value)]
            for path, text in values:
                if text and text not in observed.setdefault(path, []):
                    observed[path].append(text)
    root.show()
    record()
    for tabs in root.findChildren(QtWidgets.QTabWidget):
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            f._APP.processEvents()
            counts['tabs'] += 1
            record()
    for stack in root.findChildren(QtWidgets.QStackedWidget):
        for i in range(stack.count()):
            stack.setCurrentIndex(i)
            f._APP.processEvents()
            counts['pages'] += 1
            record()
    for fold in root.findChildren(CollapsibleSection):
        fold.setExpanded(False)
        record()
        fold.setExpanded(True)
        f._APP.processEvents()
        counts['folds'] += 1
        record()
    # These two folds have dedicated owners instead of CollapsibleSection.
    if hasattr(root, 'btn_resource_params'):
        for expanded in (False, True):
            root.btn_resource_params.setChecked(expanded)
            f._APP.processEvents()
            record()
        counts['folds'] += 1
    if hasattr(root, 'btn_layout_optimization_info'):
        for _ in range(2):
            root.btn_layout_optimization_info.click()
            f._APP.processEvents()
            record()
        counts['folds'] += 1
    root.hide()
    return observed, counts


def snapshot(lang, history):
    f.initialize_child()
    with f.environment():
        ui, roots = build(lang, history)
        try:
            texts, coverage = {}, {}
            for name, root in roots.items():
                texts[name], coverage[name] = capture(root)
            return dict(texts=texts, coverage=coverage)
        finally:
            for name in ('turbine', 'aep', 'noise'):
                roots[name].deleteLater()
            f.dispose(ui)
