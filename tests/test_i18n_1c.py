"""Paso 1c: presentación numérica, CSV invariables y textos neutros por hallazgo."""
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import QgsProject, QgsVectorLayer

_SETTINGS = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = _SETTINGS.name
for fmt in (QtCore.QSettings.NativeFormat, QtCore.QSettings.IniFormat):
    QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n, plugin, results_dialog as rd, noise_page, shadow_page, aep_setup_dialog
from VelantisWind.aep_setup_dialog import _decimal
from VelantisWind.number_format import format_number
from VelantisWind.energy_core.dialog_controller import _summary_message
from VelantisWind.ag_core.qgis_io.export import export_per_turbine_to_csv
from VelantisWind.ui_core.wake_group import WakeModelGroup
from VelantisWind.spacing_core.controller import SpacingController
from VelantisWind.spacing_core.geometry import SpacingSpec
from tests.test_breakdown_consumers import v1_result, v2_result

_ROOT = Path(__file__).resolve().parents[1]
_CWD = os.getcwd()
_LANGS = ('es', 'en', 'fr', 'de')


def setUpModule():
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


class FormatsTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language('es')
        QgsProject.instance().clear()

    def test_issue_74_and_other_numeric_formats(self):
        expected = {
            'es': ('10,000', '1.234,500', '1.234,5', '14,1 %', '0,0800', '500.000,25', '0,5'),
            'en': ('10.000', '1,234.500', '1,234.5', '14.1 %', '0.0800', '500,000.25', '0.5'),
            'fr': ('10,000', '1\u202f234,500', '1\u202f234,5', '14,1 %', '0,0800', '500\u202f000,25', '0,5'),
            'de': ('10,000', '1.234,500', '1.234,5', '14,1 %', '0,0800', '500.000,25', '0,5'),
        }
        original = QtCore.QLocale()
        self.addCleanup(QtCore.QLocale.setDefault, original)
        for lang in _LANGS:
            QtCore.QLocale.setDefault(QtCore.QLocale('de_DE' if lang == 'en' else 'en_US'))
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                self.assertEqual((rd._fmt_mw(10), rd._fmt_mw(1234.5), rd._fmt_mwh(1234.5), rd._fmt_pct(14.1),
                                  format_number(.08, '.4f'), format_number(500000.25, ',.2f'), _decimal(.5)), expected[lang])
                self.assertEqual(rd._fmt_signed_pct(14.1), '+' + expected[lang][3])
                self.assertEqual(rd._fmt_signed_pct(-14.1), '-' + expected[lang][3])
                self.assertEqual(rd._fmt_signed_mwh(-1234.5), '-' + expected[lang][2])
                self.assertEqual(rd._fmt_signed_pct(0), '0.0 %' if lang == 'en' else '0,0 %')
                for fmt in (rd._fmt_mw, rd._fmt_mwh, rd._fmt_pct, rd._fmt_signed_pct, rd._fmt_signed_mwh):
                    self.assertEqual([fmt(v) for v in (None, 'invalid', float('nan'), float('inf'), -float('inf'))],
                                     ['-', '-', 'NaN', '+inf', '−inf'])
                self.assertEqual(rd._fmt_mw(0), '-')
                self.assertEqual(rd.ScenarioComparisonDialog._fmt_value(None, 1234.5, 'mw', True),
                                 '+' + expected[lang][1] + ' MW')

    def test_energy_tables_report_and_bar(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            for build in (v1_result, v2_result):
                result = build()
                result['per_model_p_inst_MW'] = {'WTG-A': 1234.5}
                dlg = rd.AEPResultsDialog(None, result)
                self.addCleanup(dlg.deleteLater)
                html = dlg._wrap_report_document(dlg._build_full_report_html())
                with self.subTest(lang=lang, schema=build.__name__):
                    self.assertIn(rd._fmt_mw(1234.5), html)
                    self.assertIn(format_number(500000, ',.2f'), html)
                    self.assertEqual(dlg.table_turbines.item(0, 2).text(), format_number(500000, ',.2f'))
                    if build is v2_result:
                        self.assertIn(format_number(.08, '.4f'), html)
                        self.assertIn(rd._fmt_signed_pct(result['breakdown']['L_total']['pct']), html)
                    result['aep_wake_MWh'] = 12345.0
                    message = _summary_message(result)
                    self.assertIn(format_number(12345, ',.0f') + ' MWh', message)
                    self.assertIn(' %)', message)

    def test_report_truncation_count(self):
        table = QtWidgets.QTableWidget(1234, 1)
        self.addCleanup(table.deleteLater)
        for lang in _LANGS:
            i18n.set_language(lang)
            holder = mock.Mock(_user_texts=[])
            html = rd.AEPResultsDialog._qtable_to_html(holder, table, max_rows=1)
            self.assertIn(format_number(1234, ',d'), rd._fill_slots(holder._user_texts, html))

    def test_csv_bytes_and_numeric_cells_are_independent_of_language(self):
        for build in (v1_result, v2_result):
            result = build()
            result['per_turbine_table'][0]['p_nom_mw'] = 1234.5
            baseline = None
            for lang in _LANGS:
                i18n.set_language(lang)
                path = Path(_SETTINGS.name) / 'numbers.csv'
                export_per_turbine_to_csv(result['per_turbine_table'], str(path), result if build is v2_result else None)
                data = path.read_bytes()
                if baseline is None:
                    baseline = data
                self.assertEqual(data, baseline)
                with path.open(encoding='utf-8-sig') as fh:
                    rows = list(csv.DictReader(fh))
                self.assertEqual(rows[0]['Rated power [MW]'], '1234.5')
                self.assertEqual(rows[0]['X [m]'], '500000.0')

    def test_s5_15_noise_status(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            page = noise_page.NoisePage(None)
            self.addCleanup(page.deleteLater)
            page.sp_receiver_h.setValue(4)
            page.sp_alpha.setValue(.005)
            page.sp_ground_g.setValue(.5)
            page._check_configuration()
            text = page.txt_status.toPlainText()
            with self.subTest(lang=lang):
                for value, spec, suffix in ((4., '.1f', ' m'), (.005, '.4f', ' dB/m'), (.5, '.2f', '')):
                    self.assertIn(format_number(value, spec) + suffix, text)

    def test_s5_15_shadow_status(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            page = shadow_page.ShadowPage()
            self.addCleanup(page.deleteLater)
            page.sp_min_elevation.setValue(3)
            page.sp_max_elevation.setValue(90)
            page._check_configuration()
            with self.subTest(lang=lang):
                self.assertIn('3.0° - 90.0°' if lang == 'en' else '3,0° - 90,0°', page.txt_status.toPlainText())
                page.cb_timezone_mode.setCurrentIndex(page.cb_timezone_mode.findData('fixed'))
                for offset in (5.5, -3.5, 0.0):
                    page.sp_timezone.setValue(offset)
                    expected = f'UTC{offset:+.1f}'
                    if lang != 'en':
                        expected = expected.replace('.', ',')
                    self.assertIn(expected, page.lbl_timezone_status.text())
                    self.assertEqual(page._get_timezone_settings()[2], offset)

    def test_wrg_metadata_numbers(self):
        meta = dict(nx=1234, ny=2345, cellsize=1250.5, n_sectors=12,
                    extent=(500000, 501000, 4400000, 4401000), height_m_list=[80.5, 120.25])
        for lang in _LANGS:
            i18n.set_language(lang)
            holder = mock.Mock()
            holder.ed_wrg.text.return_value = 'one.wrg;two.wrg'
            second = dict(meta, height_m_list=[], height_m=150.5)
            with mock.patch.object(aep_setup_dialog, 'read_wrg_meta', side_effect=[meta, second]):
                aep_setup_dialog.AEPSetupDialog._update_wrg_meta(holder, sync_parameters=False)
            text = holder.lbl_wrg_meta.setText.call_args.args[0]
            decimal = '.' if lang == 'en' else ','
            thousands = ',' if lang == 'en' else '\u202f' if lang == 'fr' else '.'
            with self.subTest(lang=lang):
                self.assertIn(f'1{thousands}234×2{thousands}345', text)
                self.assertIn(f'1{thousands}250{decimal}5 m', text)
                self.assertIn(f'80{decimal}5, 120{decimal}25, 150{decimal}5 m', text)
                self.assertIn(f'(500{thousands}000, 4{thousands}400{thousands}000)', text)
                self.assertIn(f'(501{thousands}000, 4{thousands}401{thousands}000)', text)

    def test_shadow_dimensions_defaults_saved_values_and_calculation_input(self):
        from VelantisWind.shadow_core.calculation import point_runner

        layer = QgsVectorLayer('Point?crs=EPSG:32630', 'Dimensions', 'memory')
        QgsProject.instance().addMapLayer(layer)
        page = shadow_page.ShadowPage()
        self.addCleanup(page.deleteLater)
        page.cb_turbines.addItem('Dimensions', layer.id())
        page.cb_turbines.setCurrentIndex(page.cb_turbines.findData(layer.id()))
        page.cb_receivers.addItem('Receiver', layer.id())
        page.cb_receivers.setCurrentIndex(page.cb_receivers.findData(layer.id()))
        page._model_rows = [dict(name='Dimensions', layer_id=layer.id(), n_turbines=1)]
        for lang in _LANGS:
            i18n.set_language(lang)
            decimal = '.' if lang == 'en' else ','
            with self.subTest(lang=lang):
                for defaults in ((None, None, 100.0, 120.0), (95.5, 145.5, 95.5, 145.5)):
                    hh, diameter, expected_hh, expected_d = defaults
                    page._qsettings.remove('shadow/model_Dimensions_hh')
                    page._qsettings.remove('shadow/model_Dimensions_d')
                    page._model_rows[0].update(hub_height=hh, diameter=diameter)
                    page._populate_models_table()
                    self.assertEqual(page.tbl_models.item(0, 2).text(), str(expected_hh).replace('.', decimal))
                    self.assertEqual(page.tbl_models.item(0, 3).text(), str(expected_d).replace('.', decimal))
                for separator in ('.', ','):
                    page.tbl_models.item(0, 2).setText('111' + separator + '25')
                    page.tbl_models.item(0, 3).setText('155' + separator + '75')
                    page._check_configuration()
                    self.assertIn('111' + decimal + '25 m', page.txt_status.toPlainText())
                    self.assertIn('155' + decimal + '75 m', page.txt_status.toPlainText())
                    self.assertEqual(float(page._qsettings.value('shadow/model_Dimensions_hh')), 111.25)
                    self.assertEqual(float(page._qsettings.value('shadow/model_Dimensions_d')), 155.75)
                    with mock.patch.object(point_runner, 'collect_shadow_turbines', return_value=([], 0)) as collect, \
                            mock.patch.object(QtWidgets.QMessageBox, 'warning'), \
                            mock.patch.object(QtWidgets.QMessageBox, 'critical') as critical:
                        point_runner.run_shadow_point_calculation_for_page(page)
                    critical.assert_not_called()
                    self.assertEqual(collect.call_args.kwargs['hub_height'], 111.25)
                    self.assertEqual(collect.call_args.kwargs['rotor_diameter'], 155.75)
                # Older persisted strings and numeric settings both reopen in the selected language.
                for saved in ('111.25', '111,25', 111.25):
                    page._qsettings.setValue('shadow/model_Dimensions_hh', saved)
                    page._populate_models_table()
                    self.assertEqual(page.tbl_models.item(0, 2).text(), '111' + decimal + '25')
        with mock.patch.object(page, '_qsettings', wraps=page._qsettings) as settings:
            for lang in _LANGS:
                i18n.set_language(lang)
                page.retranslate()
                decimal = '.' if lang == 'en' else ','
                self.assertEqual(page.tbl_models.item(0, 2).text(), '111' + decimal + '25')
                self.assertEqual(page.tbl_models.item(0, 3).text(), '155' + decimal + '75')
            settings.setValue.assert_not_called()
        page.tbl_models.item(0, 2).setText('draft')
        for lang in _LANGS:
            i18n.set_language(lang)
            page.retranslate()
            self.assertEqual(page.tbl_models.item(0, 2).text(), 'draft')

    def test_s2_8_spacing_summary(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            ctl = mock.Mock()
            ctl._turbine_layers.return_value = [object()]
            spec = SpacingSpec(long_d=7.5, trans_d=4.25)
            with mock.patch('VelantisWind.spacing_core.controller.layer_spacing_spec', return_value=spec):
                SpacingController._summarize(ctl, {}, 270., spec, notify=False)
            text = ctl.panel.set_status.call_args.args[0]
            self.assertIn('7.5D×4.25D' if lang == 'en' else '7,5D×4,25D', text)


class NeutralityTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language('es')

    def test_delivery_is_active_and_old_keys_are_retired(self):
        pairs = json.loads((_ROOT / 'tests/data/i18n_1c_pares.json').read_text())
        pairs += [
            {
                'id': 'S4-12/S5-12/S7-11',
                'idioma': 'de',
                'tabla': table,
                'es': 'Distancia máxima desde un aerogenerador para considerar sombras y parpadeo.\n'
                      'Valor por defecto: 2000 m, una distancia de cribado conservadora.\n'
                      'Se usa para filtrar receptores y para la extensión/máscara del ráster.',
                'valor': 'Maximaler Abstand von einer Windturbine zur Berücksichtigung von Schattenwurf.\n'
                         'Standardwert: 2000 m, ein konservativer Abstand für das Screening.\n'
                         'Dient zur Filterung der Rezeptoren und zur Festlegung der Rasterausdehnung/-maske.',
            }
            for table in ('frag', 'full')
        ]
        sources = [p.read_text() for p in (_ROOT / 'VelantisWind').rglob('*.py')]
        # The retired texts are kept as hashes: they held the names this step removes.
        literals = {hashlib.sha256(n.value.encode('utf-8', 'surrogatepass')).hexdigest() for source in sources
                    for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for pair in pairs:
            i18n.set_language(pair['idioma'])
            translate = i18n.tr_text if pair['tabla'] == 'full' else i18n.translate_fragment
            with self.subTest(id=pair['id'], lang=pair['idioma'], table=pair['tabla']):
                self.assertEqual(translate(pair['es']), pair['valor'])
                if 'antes_sha256' in pair:
                    self.assertNotIn(pair['antes_sha256'], literals)
                    for table in ('full', 'frag'):
                        keys = {hashlib.sha256(k.encode('utf-8')).hexdigest()
                                for k in i18n._STATE[table].get(pair['idioma'], {})}
                        self.assertNotIn(pair['antes_sha256'], keys)

    def test_s1_25_scientific_reference_is_kept_without_repository_link(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            group = mock.Mock(_tr=i18n.tr_text)
            group.combo_preset.currentData.return_value = 'TurbOPark'
            text = WakeModelGroup._preset_model_help(group)
            self.assertIn('Pedersen, J. G. et al. (2022).', text)
            self.assertIn('https://doi.org/10.1088/1742-6596/2265/2/022063', text)
            self.assertNotIn('github.com/', text)

    def test_s4_12_s5_12_s7_11_tooltip_and_s1_25_sources(self):
        pairs = json.loads((_ROOT / 'tests/data/i18n_1c_pares.json').read_text())
        for lang in _LANGS:
            i18n.set_language(lang)
            page = shadow_page.ShadowPage()
            self.addCleanup(page.deleteLater)
            pair = next(p for p in pairs if p['id'] == 'S4-12/S5-12/S7-11' and p['idioma'] == (lang if lang != 'es' else 'en'))
            self.assertEqual(page.sp_max_shadow_distance.toolTip(), pair['es'] if lang == 'es' else pair['valor'])
            if lang == 'de':
                self.assertIn('ein konservativer Abstand für das Screening', page.sp_max_shadow_distance.toolTip())
        sources = {
            'mapa_interactivo_dock.py': 'Selecciona uno o varios rásteres .asc/.tif de TI ambiente. Si no hay ninguno, se usa TI = 10 % como respaldo.',
            'ag_core/wake_setup/catalog.py': 'Déficit gaussiano TurbOPark (Nygaard, 2022): la expansión combina la TI ambiente y la generada por la propia estela.',
        }
        for path, expected in sources.items():
            tree = ast.parse((_ROOT / 'VelantisWind' / path).read_text())
            self.assertIn(expected, [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)])
        self.assertIn('| WRG / ZIP | Wind-resource grid in WRG format, optionally packaged in ZIP. |',
                      (_ROOT / 'VelantisWind/docs/ENERGY_MODULE.md').read_text())
        guide = (_ROOT / 'VelantisWind/docs/ENERGY_MODULE.md').read_text()
        self.assertIn('5. The same curve/resource assumptions are used when comparing with external tools.', guide)
        self.assertIn('When validating the module against external tools, record at least:', guide)
        self.assertIn('| Result dialog | Summary of AEP, losses, turbine counts and model diagnostics. |', guide)
