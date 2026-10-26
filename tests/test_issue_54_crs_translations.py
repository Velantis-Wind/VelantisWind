# -*- coding: utf-8 -*-
"""PR77 messages follow the active language without changing layer names or paths."""
import os
import string
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402
from VelantisWind import crs_utils, i18n  # noqa: E402
from VelantisWind.ag_core.qgis_io import resource_extent  # noqa: E402
from VelantisWind.noise_core.qgis_io.apply_results import apply_noise_task_result  # noqa: E402
from VelantisWind.noise_core.results.evaluator import build_source_spatial_index  # noqa: E402
from VelantisWind.wake_core import controller  # noqa: E402

_LANGUAGES = ("es", "en", "fr", "de", "es")
_MEMORY_CRS = "No se puede crear una capa georreferenciada sin un CRS válido: {name}"
_MEMORY_LAYER = "No se pudo crear la capa en memoria de QGIS: {name}"
_RESOURCE_CRS = "CRS del recurso/proyecto no válido; no se dibuja un perímetro con CRS supuesto."
_RESULT_CRS = "El CRS del resultado acústico no es válido; no se asignará uno supuesto."
_SOURCE_CRS = "El CRS de las fuentes acústicas no es válido."
_WAKE_TITLE = "Ráster de estelas no cargado"
_WAKE_MESSAGE = (
    "El proyecto cambió durante el cálculo del ráster de estelas. "
    "No se han añadido capas al proyecto actual. "
    "Los archivos generados se conservan en:\n{path}"
)
_TEMPLATES = (_MEMORY_CRS, _MEMORY_LAYER, _RESOURCE_CRS, _RESULT_CRS,
              _SOURCE_CRS, _WAKE_TITLE, _WAKE_MESSAGE)


class Pr77TranslationsTest(unittest.TestCase):
    def setUp(self):
        previous_language = i18n.current_language()
        self.addCleanup(i18n.set_language, previous_language)
        self.project = QgsProject.instance()
        self.project.clear()
        self.addCleanup(self.project.clear)
        self.project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.name = "Ruido · Niño {modelo}"

    def expected(self, template, lang):
        i18n._ensure()
        return template if lang == "es" else i18n._STATE["full"][lang][template]

    def test_every_new_message_has_an_exact_translation_and_the_same_placeholders(self):
        formatter = string.Formatter()
        fields = lambda text: [field for _, field, _, _ in formatter.parse(text) if field is not None]
        for lang in ("en", "fr", "de"):
            for template in _TEMPLATES:
                with self.subTest(lang=lang, template=template):
                    translated = self.expected(template, lang)
                    self.assertNotEqual(translated, template)
                    self.assertEqual(fields(translated), fields(template))

    def test_real_crs_errors_follow_language_switches_and_keep_layer_names(self):
        for lang in _LANGUAGES:
            i18n.set_language(lang)
            cases = (
                (_MEMORY_CRS, ValueError, lambda: crs_utils.memory_layer_with_crs(
                    "Point", self.name, QgsCoordinateReferenceSystem()), {"name": self.name}),
                (_RESOURCE_CRS, ValueError, lambda: resource_extent.add_extent_layer(
                    (0, 1, 0, 1), source_type="WRG", crs_authid="not-a-crs"), {}),
                (_RESULT_CRS, ValueError, lambda: apply_noise_task_result(
                    {"crs_authid": "not-a-crs"}, {}), {}),
                (_SOURCE_CRS, ValueError, lambda: build_source_spatial_index([], "not-a-crs"), {}),
            )
            for template, error_type, call, values in cases:
                with self.subTest(lang=lang, template=template):
                    with self.assertRaises(error_type) as raised:
                        call()
                    self.assertEqual(str(raised.exception), self.expected(template, lang).format(**values))

    def test_failed_memory_layer_creation_is_translated_without_changing_its_name(self):
        failed_layer = mock.Mock()
        failed_layer.isValid.return_value = False
        for lang in _LANGUAGES:
            i18n.set_language(lang)
            with self.subTest(lang=lang), mock.patch.object(crs_utils, "QgsVectorLayer", return_value=failed_layer):
                with self.assertRaises(RuntimeError) as raised:
                    crs_utils.memory_layer_with_crs("Point", self.name, self.project.crs())
                self.assertEqual(str(raised.exception), self.expected(_MEMORY_LAYER, lang).format(name=self.name))

    def test_wake_warning_uses_the_language_at_completion_and_keeps_the_path(self):
        for lang in _LANGUAGES:
            i18n.set_language("es")
            self.project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
            callbacks = {}

            def start(_config, **kwargs):
                callbacks.update(kwargs)
                return mock.Mock()

            dialog = mock.Mock(_wake_raster_task=None)
            with mock.patch.object(controller, "start_wake_raster_task", side_effect=start):
                controller.start_wake_raster_from_dialog(
                    dialog, models=[], wasp_dir="", resolution_m=300, wrg_paths=[],
                    wake_config=None, wd_target=270,
                )
            i18n.set_language(lang)
            self.project.clear()
            path = os.path.join(_SETTINGS.name, self.name, "wake.tif")
            with self.subTest(lang=lang), \
                    mock.patch.object(controller.QtWidgets.QMessageBox, "warning") as warning, \
                    mock.patch.object(controller, "add_wake_raster_result_to_qgis") as load:
                callbacks["on_finished"](True, {"path": path}, None)
                load.assert_not_called()
                warning.assert_called_once()
                self.assertEqual(warning.call_args.args[1], self.expected(_WAKE_TITLE, lang))
                self.assertEqual(warning.call_args.args[2], self.expected(_WAKE_MESSAGE, lang).format(
                    path=os.path.dirname(path)))


if __name__ == "__main__":
    unittest.main()
