"""Regression tests for #44 and #52.4, runnable without a QGIS installation.

Execute the production methods with provider/project doubles. Disk providers
reject every write, so accidental schema changes or truncation fail the tests.
"""
import ast
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / 'VelantisWind/spacing_core/envelope_manager.py'
CONTROLLER = ROOT / 'VelantisWind/spacing_core/controller.py'
GEOMETRY = ROOT / 'VelantisWind/spacing_core/geometry.py'


def load_nodes(path, names, namespace, class_name=None):
    tree = ast.parse(path.read_text())
    nodes = tree.body
    if class_name:
        nodes = next(n.body for n in nodes if isinstance(n, ast.ClassDef) and n.name == class_name)
    chosen = [n for n in nodes if (
        isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names
    ) or (
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)
    )]
    assert len(chosen) == len(names)
    for node in chosen:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + chosen, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace


class Layer:
    def __init__(self, provider='memory', crs='UTM'):
        self.properties = {}
        self.provider = provider
        self.system = crs
        self.repaint = Mock()
        self.backend = Mock()
        if provider != 'memory':
            for name in ('truncate', 'addAttributes', 'addFeatures'):
                getattr(self.backend, name).side_effect = AssertionError('disk write')
    def id(self): return str(id(self))
    def providerType(self): return self.provider
    def crs(self): return self.system
    def setCrs(self, value): self.system = value
    def customProperty(self, key, default=None): return self.properties.get(key, default)
    def setCustomProperty(self, key, value): self.properties[key] = value
    def removeCustomProperty(self, key): self.properties.pop(key, None)
    def dataProvider(self): return self.backend
    def updateFields(self): pass
    def triggerRepaint(self): self.repaint()


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        self.ns = load_nodes(MANAGER, ['set_spacing_property', 'write_overrides'], {
            'QgsProject': SimpleNamespace(instance=lambda: self.project),
            'json': json, 'OVERRIDES_PROP': 'overrides',
            'read_overrides': lambda layer: json.loads(layer.customProperty('overrides', '{}')),
        })
    def test_changed_property_marks_project_dirty_and_same_value_does_not(self):
        layer = Layer()
        self.assertTrue(self.ns['set_spacing_property'](layer, 'long', 8.0))
        self.project.setDirty.assert_called_once_with(True)
        self.project.reset_mock()
        self.assertFalse(self.ns['set_spacing_property'](layer, 'long', 8.0))
        self.project.setDirty.assert_not_called()
    def test_reset_marks_dirty_only_when_overrides_existed(self):
        layer = Layer()
        self.ns['write_overrides'](layer, {})
        self.project.setDirty.assert_not_called()
        layer.properties['overrides'] = '{"3": {"long_d": 8}}'
        self.ns['write_overrides'](layer, {})
        self.assertEqual(layer.properties['overrides'], '{}')
        self.project.setDirty.assert_called_once_with(True)
        self.project.reset_mock()
        self.ns['write_overrides'](layer, {})
        self.project.setDirty.assert_not_called()
    def test_apply_persists_all_four_properties_and_is_idempotent(self):
        layer = Layer()
        spec = SimpleNamespace(long_d=8, trans_d=5, mode='fixed', angle_deg=30)
        ctl = SimpleNamespace(_turbine_layer=lambda: layer, panel=SimpleNamespace(defaults_spec=lambda: spec),
                              _selected_row_index=lambda layer: None)
        ns = load_nodes(CONTROLLER, ['_persist_selected_model_spec'], {
            **self.ns, 'MODEL_LONG_D_PROP': 'long', 'MODEL_TRANS_D_PROP': 'trans',
            'MODEL_MODE_PROP': 'mode', 'MODEL_ANGLE_PROP': 'angle'}, 'SpacingController')
        ns['_persist_selected_model_spec'](ctl)
        self.assertEqual(layer.properties, {'long': 8., 'trans': 5., 'mode': 'fixed', 'angle': 30.})
        self.assertEqual(self.project.setDirty.call_count, 4)
        self.project.reset_mock()
        ns['_persist_selected_model_spec'](ctl)
        self.project.setDirty.assert_not_called()


class SavedEnvelopeTest(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        self.ns = load_nodes(MANAGER, ['_is_regenerable', '_ensure_layer', 'clear', 'remove_for_source', '_drop_envelope', 'rebuild_many'], {
            'QgsProject': SimpleNamespace(instance=lambda: self.project),
            'QgsVectorLayer': lambda *args: Layer(), 'QgsField': lambda *args: args,
            '_REQUIRED_FIELDS': [], 'tr_text': lambda s: s, 'LAYER_PREFIX': 'Envelopes',
            'layer_model_name': lambda layer: 'Model', 'TURBINE_ENVELOPE_LAYER_PROP': 'link',
            'is_projected_in_metres': lambda crs: True,
            'layer_diameter_m': lambda *args: 120, 'layer_spacing_spec': lambda source, defaults: defaults,
            'read_overrides': lambda source: {}, 'layer_model_index': lambda source: 0,
        }, 'EnvelopeManager')
    def manager(self, saved, cached=True):
        source = Layer()
        source.properties['link'] = saved.id()
        mgr = SimpleNamespace(_layers={source.id(): saved} if cached else {}, _sources={source.id(): source},
                              _last_source_id=source.id(), last_status={}, _layer_alive=lambda layer: layer is not None,
                              _find_existing_layer=lambda layer: saved, _ensure_fields=Mock(),
                              _apply_symbology=Mock(), _register_below_source=Mock(),
                              _is_regenerable=self.ns['_is_regenerable'])
        def bind(layer, source):
            mgr._layers[source.id()] = layer
            source.properties['link'] = layer.id()
        mgr._bind_layer = bind
        return mgr, source
    def test_disk_snapshot_replaced_by_memory_for_cached_and_recovered_links(self):
        for cached in (True, False):
            for crs in ('UTM', 'other'):
                with self.subTest(cached=cached, crs=crs):
                    saved = Layer('ogr', crs)
                    mgr, source = self.manager(saved, cached)
                    result = self.ns['_ensure_layer'](mgr, source)
                    self.assertEqual(result.providerType(), 'memory')
                    self.assertEqual(result.crs(), source.crs())
                    self.assertIs(mgr._layers[source.id()], result)
                    self.assertEqual(source.properties['link'], result.id())
                    saved.backend.assert_not_called()
                    self.assertEqual(saved.backend.mock_calls, [])
                    mgr._ensure_fields.assert_not_called()
                    self.project.removeMapLayer.assert_not_called()
                    # The saved snapshot is hidden, not changed, so its old ellipses are not drawn over the update.
                    node = self.project.layerTreeRoot.return_value.findLayer.return_value
                    self.project.layerTreeRoot.return_value.findLayer.assert_called_once_with(saved.id())
                    node.setItemVisibilityChecked.assert_called_once_with(False)
                    # Subsequent regeneration reuses the temporary layer.
                    self.assertIs(self.ns['_ensure_layer'](mgr, source), result)
                    node.setItemVisibilityChecked.assert_called_once_with(False)
                    self.project.reset_mock()
    def test_clear_never_truncates_saved_provider_but_clears_memory(self):
        saved, memory = Layer('ogr'), Layer()
        mgr = SimpleNamespace(envelope_layers=lambda: [saved, memory],
                              _is_regenerable=self.ns['_is_regenerable'], last_status={'x': {}})
        self.ns['clear'](mgr)
        saved.backend.truncate.assert_not_called()
        memory.backend.truncate.assert_called_once()
        self.assertEqual(mgr.last_status, {})
    def test_remove_source_keeps_saved_snapshot_in_project(self):
        saved = Layer('ogr')
        mgr, source = self.manager(saved)
        self.ns['remove_for_source'](mgr, source.id())
        self.project.removeMapLayer.assert_not_called()
        self.assertEqual(mgr._layers, {})
        self.assertNotIn('link', source.properties)

    def test_invalid_crs_drop_keeps_saved_snapshot(self):
        saved = Layer('ogr')
        mgr, source = self.manager(saved)
        mgr.remove_for_source = lambda sid: self.ns['remove_for_source'](mgr, sid)
        self.ns['_drop_envelope'](mgr, source)
        self.project.removeMapLayer.assert_not_called()
        self.assertEqual(saved.backend.mock_calls, [])

    def test_rebuild_final_write_guard_rejects_nonmemory_provider(self):
        # Even if an integration bypasses _ensure_layer, the final write is safe.
        saved = Layer('ogr')
        mgr, source = self.manager(saved)
        source.isValid = lambda: True
        source.getFeatures = lambda: []
        mgr._ensure_layer = lambda source: saved
        mgr.remove_missing_sources = Mock()
        self.ns['QgsVectorLayer'] = Layer
        result = self.ns['rebuild_many'](mgr, [source], object(), None)
        self.assertEqual(result, {source.id(): {}})
        self.assertEqual(saved.backend.mock_calls, [])

    def test_clear_rejects_other_persistent_providers_too(self):
        for provider in ('postgres', 'spatialite', 'virtual'):
            with self.subTest(provider=provider):
                layer = Layer(provider)
                mgr = SimpleNamespace(envelope_layers=lambda: [layer],
                                      _is_regenerable=self.ns['_is_regenerable'])
                self.ns['clear'](mgr)
                self.assertEqual(layer.backend.mock_calls, [])


class RealOverridesPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        geometry = load_nodes(GEOMETRY, [
            'SpacingSpec', 'normalize_azimuth', 'MODE_AUTO', 'MODE_MANUAL_ANGLE',
            'MODE_MANUAL_SCREEN', 'SHAPE_ELLIPTICAL',
        ], {'dataclass': dataclass, 'asdict': asdict, '__name__': __name__})
        self.Spec = geometry['SpacingSpec']
        self.ns = load_nodes(MANAGER, [
            'OVERRIDES_PROP', 'set_spacing_property', 'read_overrides', 'write_overrides',
        ], {'QgsProject': SimpleNamespace(instance=lambda: self.project),
            'json': json, 'SpacingSpec': self.Spec})
        self.layer = Layer()

    def write(self, values):
        self.ns['write_overrides'](self.layer, values)

    def read(self):
        return self.ns['read_overrides'](self.layer)

    def test_real_specs_roundtrip_with_integer_feature_ids(self):
        values = {3: self.Spec(8, 5, 30, 'manual_angle'),
                  11: self.Spec(9, 4, 75, 'manual_screen')}
        self.write(values)
        self.assertEqual(self.read(), values)
        self.assertTrue(all(isinstance(spec, self.Spec) for spec in self.read().values()))
        stored = json.loads(self.layer.customProperty(self.ns['OVERRIDES_PROP']))
        self.assertEqual(stored, {str(fid): spec.to_dict() for fid, spec in values.items()})
        self.project.setDirty.assert_called_once_with(True)

    def test_repeating_real_specs_in_a_different_order_is_not_a_change(self):
        values = {3: self.Spec(8, 5, 30, 'manual_angle'), 11: self.Spec(9, 4)}
        self.write(values)
        stored = self.layer.customProperty(self.ns['OVERRIDES_PROP'])
        self.project.reset_mock()
        self.write(self.read())
        self.write(dict(reversed(list(self.read().items()))))
        self.project.setDirty.assert_not_called()
        self.assertEqual(self.layer.customProperty(self.ns['OVERRIDES_PROP']), stored)

    def test_modification_and_reset_mark_dirty_once_each(self):
        self.write({3: self.Spec(8, 5)})
        self.project.reset_mock()
        changed = {3: self.Spec(9, 5)}
        self.write(changed)
        self.assertEqual(self.read(), changed)
        self.project.setDirty.assert_called_once_with(True)
        self.project.reset_mock()
        self.write({})
        self.assertEqual(self.read(), {})
        self.assertEqual(self.layer.customProperty(self.ns['OVERRIDES_PROP']), '{}')
        self.project.setDirty.assert_called_once_with(True)
        self.project.reset_mock()
        self.write({})
        self.project.setDirty.assert_not_called()


class ProjectLayer(Layer):
    def __init__(self, uri='Polygon', name='Envelopes', provider='memory'):
        super().__init__(provider)
        self.label = name

    def isValid(self): return True
    def name(self): return self.label
    def setName(self, value): self.label = value


class RealEnvelopeLinksTest(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        self.layers = {}
        self.project.mapLayer.side_effect = self.layers.get
        self.project.mapLayers.side_effect = lambda: self.layers.copy()
        self.project.addMapLayer.side_effect = lambda layer, *args: self.layers.setdefault(layer.id(), layer)
        self.project.removeMapLayer.side_effect = lambda layer_id: self.layers.pop(layer_id, None)
        ns = load_nodes(MANAGER, [
            'TURBINE_ENVELOPE_LAYER_PROP', 'ENVELOPE_ROLE_PROP', 'ENVELOPE_ROLE',
            'ENVELOPE_SOURCE_LAYER_PROP', 'ENVELOPE_MODEL_NAME_PROP', 'ENVELOPE_MODEL_INDEX_PROP',
            'DIAMETER_PROP', 'MODEL_LONG_D_PROP', 'MODEL_TRANS_D_PROP', 'MODEL_MODE_PROP',
            'MODEL_ANGLE_PROP', 'MODEL_NAME_PROP', 'MODEL_INDEX_PROP', 'ROW_INDEX_PROP',
            'LAYER_PREFIX', 'layer_model_name', 'layer_model_index', 'layer_diameter_m',
        ], {'re': re})
        ns.update(QgsProject=SimpleNamespace(instance=lambda: self.project),
                  QgsVectorLayer=ProjectLayer, QgsField=lambda *args: args,
                  _REQUIRED_FIELDS=[], tr_text=lambda text: text, MODE_AUTO='auto_energy')
        methods = ['__init__', '_layer_alive', '_is_regenerable', '_find_existing_layer',
                   '_register_below_source', '_bind_layer', '_ensure_layer']
        load_nodes(MANAGER, methods, ns, 'EnvelopeManager')
        attrs = {name: ns[name] for name in methods}
        for name in ('_layer_alive', '_is_regenerable', '_register_below_source'):
            attrs[name] = staticmethod(attrs[name])
        self.Manager = type('EnvelopeManager', (), attrs)
        self.ns = ns
        self.source = ProjectLayer('Point', 'Turbines')
        self.project.addMapLayer(self.source)

    def manager(self):
        manager = self.Manager()
        manager._ensure_fields = Mock()
        manager._apply_symbology = Mock()
        return manager

    def test_fresh_manager_recovers_temporary_by_direct_link_or_metadata(self):
        temporary = self.manager()._ensure_layer(self.source)
        self.assertIsNotNone(temporary)
        for direct_link in (True, False):
            with self.subTest(direct_link=direct_link):
                if not direct_link:
                    self.source.removeCustomProperty(self.ns['TURBINE_ENVELOPE_LAYER_PROP'])
                manager = self.manager()
                self.project.addMapLayer.reset_mock()
                self.assertIs(manager._ensure_layer(self.source), temporary)
                self.assertIs(manager._layers[self.source.id()], temporary)
                self.assertIs(manager._sources[self.source.id()], self.source)
                self.assertEqual(self.source.customProperty(self.ns['TURBINE_ENVELOPE_LAYER_PROP']), temporary.id())
                self.assertEqual(temporary.customProperty(self.ns['ENVELOPE_SOURCE_LAYER_PROP']), self.source.id())
                self.project.addMapLayer.assert_not_called()

    def test_saving_temporary_with_same_id_preserves_snapshot_and_creates_another(self):
        for recovered in (False, True):
            with self.subTest(recovered=recovered):
                manager = self.manager()
                saved = manager._ensure_layer(self.source)
                saved_id = saved.id()
                saved.provider = 'ogr'
                for name in ('truncate', 'addAttributes', 'addFeatures'):
                    getattr(saved.backend, name).side_effect = AssertionError('disk write')
                saved.backend.reset_mock()
                properties, label, crs = saved.properties.copy(), saved.name(), saved.crs()
                if recovered:
                    manager = self.manager()
                self.project.removeMapLayer.reset_mock()
                temporary = manager._ensure_layer(self.source)
                self.assertIsNotNone(temporary)
                self.assertIsNot(temporary, saved)
                self.assertEqual(temporary.providerType(), 'memory')
                self.assertEqual(saved.id(), saved_id)
                self.assertIs(self.layers[saved_id], saved)
                self.assertEqual((saved.properties, saved.name(), saved.crs()), (properties, label, crs))
                self.assertEqual(saved.backend.mock_calls, [])
                self.project.removeMapLayer.assert_not_called()
                self.assertEqual(self.source.customProperty(self.ns['TURBINE_ENVELOPE_LAYER_PROP']), temporary.id())
                self.assertIs(manager._ensure_layer(self.source), temporary)
                self.assertIs(self.manager()._ensure_layer(self.source), temporary)


if __name__ == '__main__':
    unittest.main()
