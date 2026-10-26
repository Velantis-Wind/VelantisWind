"""Isolated UI fixture; synthetic signatures replace PyWake, no calculation is run."""
import os
import sys
import tempfile
import time
import inspect
import re
import types
from contextlib import ExitStack, chdir
from datetime import datetime
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def initialize_child():
    """Prepare the disposable UI process; importing this fixture has no UI/global effects."""
    global _TEMP, _APP, QtCore, QtWidgets, QgsProject, QgsVectorLayer
    global QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsMapCanvas
    global i18n, aep_setup_dialog, hub_dialog, shadow_page, cat, sub, val, wg
    global SpacingController, InteractiveMapDock, append_result_status, LEAF_TYPES
    _TEMP = tempfile.TemporaryDirectory(prefix='velantis-m4b-')
    os.environ.update(QT_QPA_PLATFORM='offscreen', XDG_CONFIG_HOME=_TEMP.name,
                      MPLCONFIGDIR=_TEMP.name, TZ='UTC')
    time.tzset()
    from qgis.PyQt import QtCore, QtWidgets
    QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _TEMP.name)
    QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _TEMP.name)
    QtCore.QLocale.setDefault(QtCore.QLocale.c())
    with chdir(_TEMP.name):
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    # Reject actual imports before importing any plugin module.
    sys.modules['py_wake'] = types.ModuleType('py_wake')
    sys.modules['py_wake'].__version__ = 'synthetic'
    from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY
    from qgis.gui import QgsMapCanvas
    from VelantisWind import i18n, aep_setup_dialog, hub_dialog, shadow_page
    from VelantisWind.ag_core.wake_setup import catalog as cat, subordinates as sub, validation as val
    from VelantisWind.spacing_core.controller import SpacingController
    from VelantisWind.mapa_interactivo_dock import InteractiveMapDock
    from VelantisWind.noise_core.result_status import append_result_status
    from VelantisWind.ui_core import wake_group as wg

    LEAF_TYPES = (QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox, QtWidgets.QAbstractItemView,
                  QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QLineEdit)

LANGS = ('es', 'en', 'fr', 'de')
NOISE_WARNING = 'El MDT/DSM seleccionado no es un ráster válido y se ignorará.'
GRID_WARNING = 'Ráster de respaldo creado con G global porque el ráster exacto con uso del suelo no se pudo materializar.'
CURVE_SOURCE = {'template': 'Curva @ {speed} m/s ({file})',
                'values': {'speed': '8.5', 'file': 'Turbinas {Norte}.csv'}}

class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2025, 2, 3, 12, 0, tzinfo=tz)


def synthetic_classes():
    classes = {}
    names = {e.name for e in cat.all_entries()} | set(sub._MODULES)
    names |= {o.name for options in sub.FAMILIES.values() for o in options if o.name}
    for name in names:
        classes[name] = type(name, (), {})
    for name, cls in classes.items():
        defaults = {}
        for entry in cat.all_entries():
            if entry.name == name:
                for p in entry.params:
                    defaults[p] = ('ct2a_madsen' if p == 'ct2a' else False if p.startswith('use_')
                                   else [0.1, 0.02] if p == 'a' else 0.1)
        for a in sub.args_of(name):
            defaults[a.name] = (False if a.kind == sub.BOOL else 'ct2a_madsen' if a.kind == sub.CT2A
                                else list(a.choices)[0] if a.kind == sub.CHOICE
                                else [0.1] * a.length if a.kind == sub.LIST
                                else None if a.kind == sub.COMPONENT else 7 if a.kind == sub.INT else 0.01)
        if name in ('PropagateDownwind', 'All2AllIterative', 'PropagateUpDownIterative'):
            defaults['superpositionModel'] = classes['SquaredSum']()
        def init(self, **kwargs):
            self.__dict__.update(kwargs)
        init.__signature__ = inspect.Signature([inspect.Parameter('self', inspect.Parameter.POSITIONAL_OR_KEYWORD)] +
            [inspect.Parameter(k, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=v) for k, v in defaults.items()])
        cls.__init__ = init
    return classes


def environment():
    stack = ExitStack()
    classes = synthetic_classes()
    stack.enter_context(mock.patch.object(cat, 'resolve_class', side_effect=lambda e: classes[e.name]))
    stack.enter_context(mock.patch.object(sub, 'resolve', side_effect=lambda name: classes[name]))
    stack.enter_context(mock.patch.object(sub, 'resolve_option', side_effect=lambda o: classes[o.name]))
    stack.enter_context(mock.patch.object(val, 'validate', return_value=[]))
    stack.enter_context(mock.patch.object(val, 'layout_issues', return_value=[]))
    stack.enter_context(mock.patch.object(shadow_page, 'datetime', Clock))
    stack.enter_context(mock.patch.object(time, 'time', return_value=1738584000.0))
    stack.enter_context(mock.patch.object(QtCore.QDateTime, 'currentDateTime',
                                        return_value=QtCore.QDateTime.fromSecsSinceEpoch(1738584000)))
    stack.enter_context(mock.patch.object(QtWidgets.QMessageBox, 'critical', side_effect=AssertionError('Unexpected dialog')))
    old = os.getcwd()
    os.chdir(_TEMP.name)
    stack.callback(os.chdir, old)
    return stack


def point_layer(name, model=False):
    layer = QgsVectorLayer('Point?crs=EPSG:32630', name, 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000, 4400000)))
    layer.dataProvider().addFeatures([feature])
    if model:
        layer.setCustomProperty('velantis/layer_role', 'energy_turbines')
        layer.setCustomProperty('velantis/model_name', 'Unit A')
        layer.setCustomProperty('velantis/hub_height_m', 90.0)
        layer.setCustomProperty('velantis/diameter_m', 120.0)
    QgsProject.instance().addMapLayer(layer)
    return layer


def build(lang, history='manual'):
    QgsProject.instance().clear()
    s = QtCore.QSettings('VelantisWind', 'VelantisWindPlugin')
    s.clear()
    i18n.set_language(lang)
    s.setValue('shadow/timezone_mode', 'iana')
    s.setValue('shadow/timezone_name', 'Europe/Madrid')
    s.setValue('shadow/year', 2025)
    s.setValue(wg.MODE_KEY, wg.MANUAL if history == 'manual' else wg.PREDEFINED)
    s.setValue(wg.PRESET_KEY, 'Removed preset')
    s.setValue(aep_setup_dialog.AEPSetupDialog._OLD_PHYSICS_KEYS[0], 'legacy')
    s.setValue(wg.SETTINGS_PREFIX + cat.TURBULENCE, 'Removed class')
    project = QgsProject.instance()
    project.setTitle('Synthetic project')
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:32630'))
    layer = point_layer('Layout A', model=True)
    receiver = point_layer('Receiver A')
    for prefix in ('noise', 'shadow'):
        s.setValue(prefix + '/receiver_layer_id', receiver.id())
    s.setValue('shadow/turbine_layer_id', layer.id())
    hub = hub_dialog.VelantisHubDialog(energy_dialog_factory=lambda parent: aep_setup_dialog.AEPSetupDialog(parent))
    hub._open_energy_module()
    energy = hub._energy_dialog
    energy._rows[0].update(name='Unit A', wt=object(), meta={'diam':120, 'hh':90, 'p_rated_kw':4000,
                                                           'spacing_long_d':7, 'spacing_trans_d':4})
    energy._rows[0]['layer_cb'].setLayer(layer)
    energy._refresh_model_row_header(0)
    energy.ed_wrg_ti.setText('/synthetic/ti_90.asc')
    energy.ed_wrg_ti_heights.setText('90;draft')
    energy._update_wrg_ti_meta()
    canvas = QgsMapCanvas()
    energy._spacing_ctl = SpacingController(energy, canvas, parent=energy)
    main = QtWidgets.QMainWindow()
    dock = InteractiveMapDock(energy, main)
    energy._interactive_dock = dock
    _APP.processEvents()
    # Same synthetic result at creation and after a live switch; never run the acoustic engine.
    result = dict(n_receivers=3, n_receivers_with_sources=2, n_exceedances=1,
                  grid_warnings=[GRID_WARNING],
                  acoustic_scenario={'mode':'fixed', 'effective_models':[
                      {'name':'Unit A', 'lwa_effective':104.5, 'curve_note_source': CURVE_SOURCE,
                       'curve_note': i18n.tr_text(CURVE_SOURCE['template']).format(**CURVE_SOURCE['values'])}]})
    append_result_status(hub.page_noise, result, [NOISE_WARNING])
    hub.page_flicker.cb_filter_month.setCurrentIndex(5)
    hub.page_flicker.cb_filter_hour.setCurrentIndex(7)
    return hub, energy, dock, canvas, main


# No application text is excluded. Qt implementation children of input controls duplicate
# their public text and are not plugin widgets (popup models, spinbox line edits, scroll bars).

def snapshot(root):
    out = {}
    def walk(w, path):
        for attr in ('text', 'toolTip', 'title', 'windowTitle', 'placeholderText', 'specialValueText', 'accessibleName'):
            fn = getattr(w, attr, None)
            if callable(fn):
                try:
                    text = fn()
                except TypeError:
                    continue
                if isinstance(text, str) and text:
                    out[path + '/' + attr] = text
        if isinstance(w, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            out[path + '/plainText'] = w.toPlainText()
        if isinstance(w, QtWidgets.QComboBox):
            for i in range(w.count()):
                out[f'{path}/item/{i}'] = w.itemText(i)
                out[f'{path}/itemTip/{i}'] = w.itemData(i, QtCore.Qt.ToolTipRole)
        if isinstance(w, QtWidgets.QTabWidget):
            for i in range(w.count()):
                out[f'{path}/tab/{i}'] = w.tabText(i)
                out[f'{path}/tabTip/{i}'] = w.tabToolTip(i)
        if isinstance(w, QtWidgets.QTableWidget):
            for col in range(w.columnCount()):
                item = w.horizontalHeaderItem(col)
                if item:
                    out[f'{path}/header/{col}'] = (item.text(), item.toolTip())
            for row in range(w.rowCount()):
                item = w.verticalHeaderItem(row)
                if item:
                    out[f'{path}/row/{row}'] = (item.text(), item.toolTip())
                for col in range(w.columnCount()):
                    item = w.item(row, col)
                    if item:
                        out[f'{path}/cell/{row}/{col}'] = (item.text(), item.toolTip())
                    cell = w.cellWidget(row, col)
                    if cell:
                        walk(cell, f'{path}/widget/{row}/{col}')
        elif isinstance(w, QtWidgets.QListWidget):
            for i in range(w.count()):
                out[f'{path}/item/{i}'] = (w.item(i).text(), w.item(i).toolTip())
        if isinstance(w, LEAF_TYPES):
            return
        counts = {}
        for child in w.findChildren(QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly):
            if isinstance(child, QtWidgets.QDialog):
                continue  # energy is captured as a separate root
            cls = type(child).__name__
            n = counts.get(cls, 0)
            counts[cls] = n + 1
            walk(child, f'{path}/{cls}[{n}]')
    walk(root, type(root).__name__)
    return out


# Closed exception list: QGIS memory-provider UUIDs are random in each process.
# Normalize only that UUID, at these two item tooltip paths; compare the rest verbatim.
_UUID_TOOLTIPS = tuple('AEPSetupDialog/QScrollArea[0]/QWidget[0]/QWidget[0]/QGroupBox[0]/QWidget[0]/'
                       f'QgsMapLayerComboBox[0]/itemTip/{i}' for i in (1, 2))


def texts(ui):
    out = {name: snapshot(root) for name, root in zip(('hub','energy','dock'), ui[:3])}
    for key in _UUID_TOOLTIPS:
        value, count = re.subn(r'uid=\{[0-9a-f-]{36}\}', 'uid={memory-layer}', out['energy'][key])
        assert count == 1, (key, out['energy'][key])
        out['energy'][key] = value
    return out


def dispose(ui):
    hub, energy, dock, canvas, main = ui
    dock._teardown()
    energy._spacing_ctl.teardown()
    energy._spacing_ctl = None
    energy._interactive_dock = None
    for obj in (hub, energy, dock, canvas, main):
        obj.deleteLater()
    _APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    QgsProject.instance().clear()
