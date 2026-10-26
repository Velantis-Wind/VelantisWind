"""Regenerators keep the live data and drafts; no physics calculation or real settings."""
import unittest
from unittest import mock
from . import i18n_m4b_fixture as f

def setUpModule():
    global QtGui, SubordinateEditor, SpacingSpec
    f.initialize_child()
    from qgis.PyQt import QtGui
    from VelantisWind.ui_core.wake_controls import SubordinateEditor
    from VelantisWind.spacing_core.geometry import SpacingSpec


class RegeneratorTest(unittest.TestCase):
    def setUp(self):
        self.environment = f.environment()
        self.addCleanup(self.environment.close)
        self.ui = f.build('es')
        self.addCleanup(f.dispose, self.ui)
        self.hub, self.energy, self.dock = self.ui[:3]

    def test_energy_rows_ti_and_reopening_keep_identity_and_drafts(self):
        row = self.energy._rows[0]
        wt, layer = row['wt'], row['layer_cb'].currentLayer()
        row['name'] = 'Parque Norte <A>'
        self.energy.sp_fixed_ti.setValue(12.3)
        self.energy._show_wrg_parameters('/synthetic/previous.wrg', 12)
        self.energy.cb_wd_count.setCurrentIndex(self.energy.cb_wd_count.count() - 1)
        directions = self.energy.cb_wd_count.currentData()
        self.energy.ed_wrg.setText('/synthetic/unfinished')
        for lang in ('fr', 'de', 'en', 'es'):
            self.hub.cb_language.setCurrentIndex(self.hub.cb_language.findData(lang))
            self.assertIs(self.energy._rows[0], row)
            self.assertIs(row['wt'], wt)
            self.assertEqual(row['layer_cb'].currentLayer(), layer)
            self.assertIn('Parque Norte &lt;A&gt;', row['name_lbl'].text())
            self.assertEqual(self.energy.ed_wrg_ti_heights.text(), '90;draft')
            self.assertEqual(self.energy.sp_fixed_ti.value(), 12.3)
            self.assertEqual(self.energy.cb_wd_count.currentData(), directions)
            self.assertEqual(self.energy.ed_wrg.text(), '/synthetic/unfinished')
            self.assertEqual(self.energy.lbl_wrg_ti_meta.text(),
                             f.i18n.tr_text('Ráster(s) TI no encontrado(s): {files}').format(files='ti_90.asc'))
            self.assertIn('EPSG:32630', self.energy._note_ti.text())
        self.energy.hide()
        f.i18n.set_language('de')  # reopening also translates if no hub signal was delivered
        self.hub._open_energy_module()
        self.assertIs(self.hub._energy_dialog, self.energy)
        self.assertIs(self.energy._rows[0], row)
        self.assertTrue(row['name_lbl'].text().startswith('Modell 1:'))
        row['name'] = 'Turbinas'
        self.energy.retranslate_ui()
        self.assertIn('<b>Turbinas</b>', row['name_lbl'].text())

    def test_wake_preferences_preset_mirror_and_invalid_editor_drafts(self):
        group = self.energy.wake_group
        editor = group.deficit_editor
        editor.control('k').setText('unfinished,')
        group.sec_deficit.setExpanded(True)
        combo = group.combo[f.cat.ENGINE]
        combo.setCurrentIndex(combo.findData('All2AllIterative'))
        engine = group._sub_editors[(f.cat.ENGINE, 'All2AllIterative')]
        convergence = engine._controls['convergence_tolerance'][2]
        convergence.setText('unfinished,')
        combo.setCurrentIndex(combo.findData('PropagateDownwind'))
        selections = {p:c.currentData() for p,c in group.combo.items()}
        nested = SubordinateEditor(f.wg._cfg.component_signature('CrespoHernandez'), group, **group._editor_kw())
        rotor = nested._nested['rotorAvgModel']
        rotor['combo'].setCurrentIndex(rotor['combo'].findData('EqGridRotorAvg'))
        rotor_editor = rotor['inner']
        rotor_editor.control('n').lineEdit().setText('unfinished')
        rotor['combo'].setCurrentIndex(rotor['combo'].findData('CGIRotorAvg'))
        for lang in ('en', 'fr', 'de', 'es'):
            f.i18n.set_language(lang)
            group.retranslate()
            self.assertIs(group.deficit_editor, editor)
            self.assertIs(group._sub_editors[(f.cat.ENGINE, 'All2AllIterative')], engine)
            self.assertEqual(convergence.text(), 'unfinished,')
            self.assertIs(rotor['editors']['EqGridRotorAvg'], rotor_editor)
            self.assertEqual(rotor_editor.control('n').lineEdit().text(), 'unfinished')
            self.assertEqual(editor.control('k').text(), 'unfinished,')
            self.assertTrue(group.sec_deficit.isExpanded())
            self.assertEqual({p:c.currentData() for p,c in group.combo.items()}, selections)
            self.assertEqual(group.lbl_preferences.text(), group._tr_template(
                f.wg.STALE_PREFERENCE, value='Removed class', position=f.cat.position_label(f.cat.TURBULENCE),
                default=group._tr(f.wg.NONE_LABEL[f.cat.TURBULENCE])) + '\n' +
                group._tr(self.energy.OLD_PHYSICS_NOTE))
            self.assertEqual(group._preset_stale, group._tr_template(
                f.wg.STALE_PRESET, value='Removed preset', default=f.wg.DEFAULT_PRESET))
            mirror = self.dock._wake_mirror
            note = QtGui.QTextDocument()
            note.setHtml(mirror.lbl_preferences.text())
            self.assertEqual(note.toPlainText(), group.lbl_preferences.text())
            self.assertEqual(mirror.labels[f.cat.DEFICIT].text(), group._row_label[f.cat.DEFICIT].text())
            self.assertEqual(mirror.combo[f.cat.TURBULENCE].itemText(0), group.combo[f.cat.TURBULENCE].itemText(0))

    def test_noise_keeps_result_cells_selection_and_receiver_groups(self):
        page = self.hub.page_noise
        result = page._result_status[0]
        page.tbl_models.selectRow(0)
        item = page.tbl_models.item(0, 0)
        item.setText('Turbinas')
        lwa = page.tbl_models.cellWidget(0, 6)
        lwa.setValue(111.5)
        receiver = page.cb_receivers.currentData()
        for lang in ('en', 'fr', 'de', 'es'):
            f.i18n.set_language(lang)
            page.retranslate()
            self.assertIs(page._result_status[0], result)
            self.assertIs(page.tbl_models.item(0, 0), item)
            self.assertIs(page.tbl_models.cellWidget(0, 6), lwa)
            self.assertEqual(item.text(), 'Turbinas')
            self.assertEqual(lwa.value(), 111.5)
            self.assertEqual(page.tbl_models.currentRow(), 0)
            self.assertEqual(page.cb_receivers.currentData(), receiver)
            self.assertIn(f.i18n.tr_text('Resultado acústico:'), page.txt_status.toPlainText())
            self.assertIn('104.50', page.txt_status.toPlainText())
            self.assertIn('Unit A', page.txt_status.toPlainText())
            self.assertIn(f.i18n.tr_text(f.NOISE_WARNING), page.txt_status.toPlainText())
            self.assertIn(f.i18n.tr_text(f.GRID_WARNING), page.txt_status.toPlainText())
            self.assertIn(f.i18n.tr_text(f.CURVE_SOURCE['template']).format(**f.CURVE_SOURCE['values']),
                          page.txt_status.toPlainText())
            self.assertEqual(result['n_receivers'], 3)

    def test_page_retranslation_never_writes_settings(self):
        # Fail on attempted writes too, including writes of the same value.
        with mock.patch.object(f.QtCore.QSettings, 'setValue') as write, \
             mock.patch.object(f.QtCore.QSettings, 'remove') as remove, \
             mock.patch.object(f.QtCore.QSettings, 'clear') as clear:
            for lang in ('en', 'fr', 'de', 'es'):
                # set_language itself persists the language; only watch the regenerators.
                f.i18n.set_language(lang)
                write.reset_mock()
                self.hub.page_noise.retranslate()
                self.hub.page_flicker.retranslate()
                write.assert_not_called()
                remove.assert_not_called()
                clear.assert_not_called()

    def test_noise_warning_producers_retain_spanish_sources(self):
        from VelantisWind.noise_core import validation, task_controller
        from VelantisWind.noise_core.domain import NoiseRunConfig
        from VelantisWind.noise_core.raster import task
        from VelantisWind.noise_core.qgis_io import apply_results
        page = self.hub.page_noise
        f.i18n.set_language('de')
        config = NoiseRunConfig(receiver_layer=None, model_cfg={}, dem_layer=object(), landuse_layer=object())
        _, warnings = validation.validate_run_config(config)
        self.assertEqual(warnings, [f.NOISE_WARNING, 'La capa de suelo no es vectorial válida y se ignorará.'])
        page.cb_ground_mode.setCurrentIndex(page.cb_ground_mode.findData('landuse'))
        page.cb_landuse.setCurrentIndex(0)
        _, ui_warnings = page._validate_inputs_for_run()
        self.assertEqual(ui_warnings, [
            'El modo de suelo por capa está activo sin una capa válida: se usará el G global como respaldo.'])
        config = NoiseRunConfig(receiver_layer=None, model_cfg={}, create_grid_layer=True, ground_mode='landuse')
        result = {'_runtime_sources_snapshot': [{'x': 500000, 'y': 4400000}]}
        with mock.patch.object(task, 'compute_noise_grid_file_from_snapshot', return_value={}), \
             mock.patch.object(apply_results, '_add_grid_layer_from_diag', return_value=(mock.Mock(), None)), \
             mock.patch.object(task_controller, '_refresh_raster_layer_on_canvas'), \
             mock.patch.object(task_controller, '_set_dialog_progress'):
            self.assertTrue(task_controller._fallback_grid_from_runtime_snapshot(page, config, result))
        self.assertEqual(result['grid_warnings'], [f.GRID_WARNING])
        f.append_result_status(page, result, warnings + ui_warnings)
        ground_warning = {
            'es': ui_warnings[0],
            'en': 'Layer-based ground mode is active without a valid layer: global G will be used as fallback.',
            'fr': 'Le mode de sol par couche est actif sans couche valide : le G global sera utilisé en secours.',
            'de': 'Der Layer-basierte Bodenmodus ist ohne gültigen Layer aktiv: Der globale G-Wert wird als Fallback verwendet.',
        }
        for lang in ('en', 'fr', 'de', 'es'):
            f.i18n.set_language(lang)
            page.retranslate()
            for source in warnings + ui_warnings + [f.GRID_WARNING]:
                self.assertIn(f.i18n.tr_text(source), page.txt_status.toPlainText())
            self.assertIn(ground_warning[lang], page.txt_status.toPlainText())

    def test_noise_curve_sources_survive_collection_and_payload(self):
        from VelantisWind.noise_core.sources import collector
        from VelantisWind.noise_core.results.payload import build_noise_result_payload
        layer = self.energy._rows[0]['layer_cb'].currentLayer()
        page = self.hub.page_noise
        for worst, error, template, values in (
            (False, None, f.CURVE_SOURCE['template'], f.CURVE_SOURCE['values']),
            (True, None, 'Curva peor caso ({file})', {'file': 'Turbinas {Norte}.csv'}),
            (False, ValueError('Turbinas {Norte}'), 'Curva inválida -> LwA fijo de respaldo ({error})',
             {'error': 'Turbinas {Norte}'})):
            f.i18n.set_language('fr')
            cfg = {layer.id(): {'acoustic_mode': 'curve', 'curve_path': '/synthetic/Turbinas {Norte}.csv',
                                'eval_ws_m_s': 8.5, 'use_curve_worst_case': worst}}
            with mock.patch.object(collector, 'load_acoustic_curve_csv', return_value=([8, 9], [104, 105]),
                                   side_effect=error), \
                 mock.patch.object(collector, 'evaluate_acoustic_curve', return_value=104.5):
                sources, diag = collector._collect_sources(f.QgsProject.instance(), cfg, None)
            self.assertEqual(len(sources), 1)
            expected_source = {'template': template, 'values': values}
            self.assertEqual(diag[layer.id()]['curve_note_source'], expected_source)
            result = build_noise_result_payload(
                result=layer, src_layer=None, link_layer=None, grid_layer=None, iso_layer=None,
                uncovered_layer=None, sources=sources, receivers=[], src_diag=diag, out_feats=[],
                dom_links=[], uncovered_ids=[], zero_receivers=0, n_exceed=0, max_noise=0,
                max_noise_fid=None, grid_diag={}, alpha_db_per_m=.005, ground_factor_g=.5,
                ground_mode='global', active_landuse_layer=None, receiver_height_m=4,
                max_radius_m=5000, dem_layer=None, adiv_vals=[], aatm_vals=[], aground_vals=[],
                abar_vals=[], ground_g_values=[], critical_receiver=None, ground_from_landuse_count=0,
                ground_fallback_count=0, applied_limits=[], receiver_type_counts={},
                receiver_type_compliance={}, receiver_limit_dba=45, receiver_limit_mode='global',
                receiver_limit_scenario='day', calculation_engine='fast', temperature_c=15,
                humidity_percent=70, pressure_kpa=101.325, model_cfg=cfg)
            self.assertEqual(result['acoustic_scenario']['effective_models'][0]['curve_note_source'], expected_source)
            f.append_result_status(page, result, [])
            for lang in ('en', 'fr', 'de', 'es'):
                f.i18n.set_language(lang)
                page.retranslate()
                self.assertIn(f.i18n.tr_text(template).format(**values), page.txt_status.toPlainText())

    def test_spacing_retranslation_does_not_migrate_legacy_layers(self):
        from VelantisWind.spacing_core import controller as spacing
        controller = self.energy._spacing_ctl
        layer = self.energy._rows[0]['layer_cb'].currentLayer()
        for key in (spacing.MODEL_LONG_D_PROP, spacing.MODEL_TRANS_D_PROP,
                    spacing.MODEL_MODE_PROP, spacing.MODEL_ANGLE_PROP):
            layer.removeCustomProperty(key)
        properties = {key: layer.customProperty(key) for key in layer.customPropertyKeys()}
        f.QgsProject.instance().setDirty(False)
        with mock.patch.object(controller, '_ensure_model_properties') as migrate, \
             mock.patch.object(f.QgsVectorLayer, 'setCustomProperty') as write:
            for lang in ('en', 'fr', 'de', 'es'):
                f.i18n.set_language(lang)
                controller.retranslate()
                migrate.assert_not_called()
                write.assert_not_called()
                self.assertEqual({key: layer.customProperty(key) for key in layer.customPropertyKeys()}, properties)
                self.assertFalse(f.QgsProject.instance().isDirty())

    def test_energy_clears_transient_resource_extent(self):
        for lang in ('en', 'fr', 'de', 'es'):
            self.energy.lbl_resource_extent.setText('Mensaje de la acción anterior · EPSG:32630')
            f.i18n.set_language(lang)
            self.energy.retranslate_ui()
            self.assertEqual(self.energy.lbl_resource_extent.text(), '')

    def test_active_spacing_tool_recomposes_each_phase_and_keeps_values(self):
        from VelantisWind.spacing_core import map_tool
        controller = self.energy._spacing_ctl
        panel = controller.panel
        panel.set_enabled(True, emit=False)
        controller.canvas.setDestinationCrs(f.QgsCoordinateReferenceSystem('EPSG:32630'))
        controller._start_define_tool()
        tool = controller._tool
        self.assertIsNotNone(tool)
        tool._angle_deg, tool._a_m, tool._b_m = 37.5, 510.0, 210.0
        tool._fid, tool._center = 1, f.QgsPointXY(500000, 4400000)
        states = (
            (map_tool._ST_CENTER, 'Clic sobre una turbina para definir su envolvente · Esc cancela', {}),
            (map_tool._ST_MAJOR, 'Eje mayor · Ángulo: {angle_deg}° · Long: {long_d} · '
             'Ctrl=ajuste a 5°/sector, Mayús=ajuste a 0,5D', {'angle_deg': '37.5', 'long_d': tool._fmt_d(510)}),
            (map_tool._ST_MINOR, 'Eje menor · Ángulo: {angle_deg}° · Long: {long_d} · '
             'Trans: {trans_d} · Clic para confirmar',
             {'angle_deg': '37.5', 'long_d': tool._fmt_d(510), 'trans_d': tool._fmt_d(210)}))
        for summary in (None, ({'a': {1: 'near'}}, 45, SpacingSpec())):
            controller._last_summary = summary
            for state, source, values in states:
                tool._state = state
                tool._push_status()
                before = (tool._state, tool._fid, tool._center, tool._angle_deg, tool._a_m, tool._b_m)
                with mock.patch.object(tool, '_redraw') as redraw, \
                     mock.patch.object(controller.manager, 'rebuild_many') as rebuild:
                    for lang in ('en', 'fr', 'de', 'es'):
                        f.i18n.set_language(lang)
                        controller.retranslate()
                        self.assertEqual(panel.lbl_status.text(), f.i18n.tr_text(source).format(**values))
                        self.assertEqual((tool._state, tool._fid, tool._center, tool._angle_deg, tool._a_m, tool._b_m), before)
                        self.assertIs(controller.canvas.mapTool(), tool)
                    redraw.assert_not_called()
                    rebuild.assert_not_called()

    def test_spacing_status_templates_keep_names_and_paths(self):
        panel = self.energy._spacing_ctl.panel
        path = '/synthetic/Parque/Modelo.gpkg'
        panel.set_status('{layer_count} capa(s) de modelo exportadas: {file_path}', layer_count=2, file_path=path)
        for lang in ('en', 'fr', 'de', 'es'):
            f.i18n.set_language(lang)
            panel.retranslate()
            self.assertEqual(panel.lbl_status.text(), f.i18n.tr_text(
                '{layer_count} capa(s) de modelo exportadas: {file_path}').format(layer_count=2, file_path=path))
        controller = self.energy._spacing_ctl
        panel.set_enabled(False, emit=False)
        with mock.patch.object(controller.manager, 'remove') as remove:
            controller.retranslate()
            remove.assert_not_called()
        self.assertEqual(panel.lbl_status.text(), '—')

    def test_shadow_keeps_models_filters_and_raster_result(self):
        page = self.hub.page_flicker
        cell = page.tbl_models.item(0, 2)
        cell.setText('123.4')
        page.tbl_models.selectRow(0)
        page._last_npz_path = '/synthetic/result.npz'
        selected = (page.cb_turbines.currentData(), page.cb_receivers.currentData(),
                    page.cb_filter_month.currentData(), page.cb_filter_hour.currentData())
        for lang, prefix in (('en', 'Time basis:'), ('fr', 'Base temporelle'), ('de', 'Zeitbasis:'), ('es', 'Base temporal:')):
            f.i18n.set_language(lang)
            page.retranslate()
            self.assertTrue(page.lbl_timezone_status.text().startswith(prefix))
            self.assertIn('Europe/Madrid', page.lbl_timezone_status.text())
            self.assertIs(page.tbl_models.item(0, 2), cell)
            self.assertEqual(cell.text(), '123.4' if lang == 'en' else '123,4')
            self.assertEqual(float(cell.text().replace(',', '.')), 123.4)
            self.assertEqual(page.tbl_models.currentRow(), 0)
            self.assertEqual(page._last_npz_path, '/synthetic/result.npz')
            self.assertEqual((page.cb_turbines.currentData(), page.cb_receivers.currentData(),
                              page.cb_filter_month.currentData(), page.cb_filter_hour.currentData()), selected)
            self.assertEqual(page.cb_filter_month.itemText(0), f.i18n.tr_text('Todos'))
            self.assertEqual(page.cb_filter_hour.itemText(0), f.i18n.tr_text('Todas'))

    def test_spacing_and_dock_follow_hub_without_rebuilding_layers_or_losing_pending_dimensions(self):
        controller = self.energy._spacing_ctl
        panel = controller.panel
        panel.chk_enable.setChecked(True)
        controller._summarize({'a': {1:'near'}}, 45, SpacingSpec(), notify=False)
        blocker = f.QtCore.QSignalBlocker(panel.sp_long)
        panel.sp_long.setValue(8.5)
        del blocker
        selected = panel.selected_model_id()
        with mock.patch.object(controller.manager, 'rebuild_many') as rebuild, \
             mock.patch.object(controller.manager, 'remove') as remove:
            for lang in ('en', 'fr', 'de', 'es'):
                self.hub.cb_language.setCurrentIndex(self.hub.cb_language.findData(lang))
                self.assertEqual(panel.sp_long.value(), 8.5)
                self.assertEqual(panel.selected_model_id(), selected)
                self.assertIn(f.i18n.tr_text('{n} cerca del límite').format(n=1), panel.lbl_status.text())
                self.assertIn('Unit A', panel.lbl_model_info.text())
                self.assertIn('ti_90.asc', self.dock.lbl_ti_status.text())
                self.assertIn('Layout A', self.dock.lbl_layer_status.text())
            rebuild.assert_not_called()
            remove.assert_not_called()
