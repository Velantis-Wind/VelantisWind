# -*- coding: utf-8 -*-
"""Texts of the hub, the support dialog, the plugin action, the layout import window and the WAsP grid merge: Spanish
sources, the same text in each language, defaults that are not English data, and the plugin action that follows a
language change made in the hub."""
import os
import tempfile
import unittest
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qgis.core import QgsCoordinateReferenceSystem, QgsProject  # noqa: E402

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts.
from VelantisWind import plugin  # noqa: E402
from VelantisWind import support_dialog, union_recurso  # noqa: E402
from VelantisWind.hub_dialog import VelantisHubDialog  # noqa: E402
from VelantisWind.ui_core import layout_sources  # noqa: E402
from VelantisWind.ui_core.layout_sources import TurbineLayoutImportDialog  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _form_labels(dialog):
    form = dialog.layout().itemAt(0).layout()
    labels = []
    for row in range(form.rowCount()):
        item = form.itemAt(row, QtWidgets.QFormLayout.LabelRole)
        if item is not None and item.widget() is not None:
            labels.append(item.widget().text())
    return labels


# The import window of Noise (Shadow has the same rows but the last two).
_IMPORT = {
    "es": {
        "labels": ["Nombre de la capa:", "Modelo / familia de aerogenerador:", "Parque eólico:", "Fichero de coordenadas:",
                   "Sistema de coordenadas:", "Altura buje:", "Diámetro rotor:", "Separación longitudinal:",
                   "Separación transversal:", "Grupo fuente de ruido:", "LwA fijo por defecto:"],
        "park": "Opcional", "model": "Modelo de aerogenerador", "group": "Grupo fuente acústico",
        "buttons": ["Aceptar", "Cancelar"],
        "note": "La capa se añadirá a QGIS como layout de turbinas de VelantisWind. Antes de calcular, aún puedes editar "
                "los valores propios del módulo en su tabla.",
    },
    "en": {
        "labels": ["Layer name:", "Wind turbine model / family:", "Wind farm:", "Coordinates file:", "Coordinates CRS:",
                   "Hub height:", "Rotor diameter:", "Downwind spacing:", "Crosswind spacing:", "Noise source group:",
                   "Default fixed LwA:"],
        "park": "Optional", "model": "Wind turbine model", "group": "Acoustic source group",
        "buttons": ["OK", "Cancel"],
        "note": "The layer will be added to QGIS as a VelantisWind turbine layout. You can still edit module-specific "
                "values in the module table before calculating.",
    },
    "fr": {
        "labels": ["Nom de la couche :", "Modèle / famille d’éolienne :", "Parc éolien :", "Fichier de coordonnées :",
                   "SCR des coordonnées :", "Hauteur de moyeu :", "Diamètre du rotor :", "Espacement longitudinal :",
                   "Espacement transversal :", "Groupe de sources de bruit :", "LwA fixe par défaut :"],
        "park": "Facultatif", "model": "Modèle d’éolienne", "group": "Groupe de sources acoustiques",
        "buttons": ["OK", "Annuler"],
        "note": "La couche sera ajoutée à QGIS comme implantation d’éoliennes VelantisWind. Vous pourrez encore modifier "
                "les valeurs propres au module dans son tableau avant le calcul.",
    },
    "de": {
        "labels": ["Layer-Name:", "Windturbinenmodell / -familie:", "Windpark:", "Koordinatendatei:", "KBS der Koordinaten:",
                   "Nabenhöhe:", "Rotordurchmesser:", "Längsabstand:", "Querabstand:", "Schallquellgruppe:",
                   "Fester Standard-LwA:"],
        "park": "Optional", "model": "Windturbinenmodell", "group": "Akustische Quellgruppe",
        "buttons": ["OK", "Abbrechen"],
        "note": "Der Layer wird in QGIS als VelantisWind-Turbinenlayout hinzugefügt. Vor der Berechnung können Sie die "
                "modulspezifischen Werte weiterhin in der Modultabelle bearbeiten.",
    },
}


class ImportWindowTextsTest(unittest.TestCase):
    def setUp(self):
        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.addCleanup(project.clear)
        self.addCleanup(i18n.set_language, "es")

    def window(self, lang, module):
        i18n.set_language(lang)
        dialog = TurbineLayoutImportDialog(module=module)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_rows_note_and_buttons_in_each_language(self):
        for lang in _LANGS:
            expected = _IMPORT[lang]
            with self.subTest(lang=lang):
                noise = self.window(lang, "noise")
                self.assertEqual(_form_labels(noise), expected["labels"])
                self.assertEqual(_form_labels(self.window(lang, "shadow")), expected["labels"][:-2])
                self.assertEqual(noise.ed_park.placeholderText(), expected["park"])
                self.assertIn(expected["note"], [label.text() for label in noise.findChildren(QtWidgets.QLabel)])
                box = noise.findChild(QtWidgets.QDialogButtonBox)
                self.assertEqual([box.button(QtWidgets.QDialogButtonBox.Ok).text(),
                                  box.button(QtWidgets.QDialogButtonBox.Cancel).text()], expected["buttons"])

    def test_defaults_are_in_the_language_of_the_plugin(self):
        # They end up as data (the model and group names of the layer), so they are not English in every language.
        for lang in _LANGS:
            with self.subTest(lang=lang):
                noise = self.window(lang, "noise")
                self.assertEqual(noise.ed_model.text(), _IMPORT[lang]["model"])
                self.assertEqual(noise.ed_source_group.text(), _IMPORT[lang]["group"])
                noise.ed_model.clear()
                self.assertEqual(noise.values()["model_name"], _IMPORT[lang]["model"])

    def test_generated_layer_names_are_independent_of_language(self):
        for module in ("noise", "shadow", "energy"):
            names = []
            for lang in _LANGS:
                with self.subTest(module=module, lang=lang):
                    dialog = self.window(lang, module)
                    names.append(dialog.values()["layer_name"])
                    self.assertEqual(names[-1], f"WT model · {module} layout")
                    dialog.ed_model.clear()
                    self.assertEqual(dialog.values()["layer_name"], names[-1])
                    dialog.ed_model.setText("  Modelo personalizado  ")
                    self.assertEqual(dialog.values()["layer_name"], f"Modelo personalizado · {module} layout")
                    self.assertEqual(dialog.values()["model_name"], "Modelo personalizado")
                    dialog.ed_layer_name.setText("Mi capa")
                    self.assertEqual(dialog.values()["layer_name"], "Mi capa")
            self.assertEqual(names, [names[0]] * len(_LANGS))

    def test_a_layout_without_coordinates_is_refused_in_each_language(self):
        expected = {"es": "No se han indicado coordenadas de turbinas.", "en": "No turbine coordinates were provided.",
                    "fr": "Aucune coordonnée d’éolienne n’a été fournie.",
                    "de": "Es wurden keine Turbinenkoordinaten angegeben."}
        for lang in _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang), self.assertRaises(ValueError) as caught:
                layout_sources.create_turbine_layout_layer(coords=[], layer_name="L1", module="noise", model_name="M1")
            self.assertEqual(str(caught.exception), expected[lang])


# Complete expected messages, independent of the translation tables at test runtime.
_WASP_MESSAGES = {'es': {'intro': 'Se generará UNA carpeta con GRD mosaico (Sector/Altura/Variable).\n'
                 'Selecciona 2 o más carpetas de teselas exportadas desde WAsP.\n'
                 "• 'Sector All': se tomarán TODAS las variables presentes (mosaico por altura).\n"
                 "• Además, se crea subcarpeta 'pywake_compat' estricta (sin necesidad de parches).\n"
                 '• Salida en Surfer ASCII (DSAA) con formato WAsP.',
        'epsg_title': 'CRS de trabajo (EPSG)',
        'epsg_prompt': 'Introduce el EPSG en el que están las coordenadas de las teselas.\n'
                       'Por ejemplo:\n'
                       '  • 25829 → ETRS89 / UTM 29N (Galicia oeste)\n'
                       '  • 25830 → ETRS89 / UTM 30N (gran parte de España)\n'
                       '\n'
                       'Deja vacío para usar 25830.'},
 'en': {'intro': 'ONE folder with a GRD mosaic (Sector/Height/Variable) will be generated.\n'
                 'Select 2 or more tile folders exported from WAsP.\n'
                 "• 'Sector All': ALL present variables will be taken (mosaic by height).\n"
                 "• In addition, a strict 'pywake_compat' subfolder is created (no patches needed).\n"
                 '• Output in Surfer ASCII (DSAA) with WAsP format.',
        'epsg_title': 'Working CRS (EPSG)',
        'epsg_prompt': 'Enter the EPSG of the tile coordinates.\n'
                       'For example:\n'
                       '  • 25829 → ETRS89 / UTM 29N (western Galicia)\n'
                       '  • 25830 → ETRS89 / UTM 30N (most of Spain)\n'
                       '\n'
                       'Leave empty to use 25830.'},
 'fr': {'intro': 'Un dossier unique avec une mosaïque GRD (secteur/hauteur/variable) sera généré.\n'
                 'Sélectionnez au moins deux dossiers de tuiles exportés depuis WAsP.\n'
                 '• « Sector All » : toutes les variables présentes seront utilisées (mosaïque par '
                 'hauteur).\n'
                 '• Un sous-dossier strict « pywake_compat » est également créé, sans correction '
                 'supplémentaire nécessaire.\n'
                 '• Sortie en Surfer ASCII (DSAA) au format WAsP.',
        'epsg_title': 'SCR de travail (EPSG)',
        'epsg_prompt': 'Saisissez l’EPSG des coordonnées des tuiles.\n'
                       'Par exemple :\n'
                       '  • 25829 → ETRS89 / UTM 29N (ouest de la Galice)\n'
                       '  • 25830 → ETRS89 / UTM 30N (majeure partie de l’Espagne)\n'
                       '\n'
                       'Laissez vide pour utiliser 25830.'},
 'de': {'intro': 'Es wird EIN Ordner mit einem GRD-Mosaik erzeugt (Sektor/Höhe/Variable).\n'
                 'Wählen Sie mindestens zwei aus WAsP exportierte Kachelordner.\n'
                 "• 'Sector All': Alle vorhandenen Variablen werden übernommen (Mosaik nach Höhe).\n"
                 "• Zusätzlich wird ein strikter Unterordner 'pywake_compat' erstellt; Patches sind nicht "
                 'erforderlich.\n'
                 '• Ausgabe im Surfer-ASCII-Format (DSAA) mit WAsP-kompatiblem Format.',
        'epsg_title': 'Arbeits-KBS (EPSG)',
        'epsg_prompt': 'Geben Sie den EPSG-Code der Kachelkoordinaten ein.\n'
                       'Zum Beispiel:\n'
                       '  • 25829 → ETRS89 / UTM 29N (westliches Galicien)\n'
                       '  • 25830 → ETRS89 / UTM 30N (großer Teil Spaniens)\n'
                       '\n'
                       'Lassen Sie das Feld leer, um 25830 zu verwenden.'}}


class WaspMergeTextsTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_language, "es")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def test_errors_in_each_language(self):
        expected = {
            "es": ("No se encontraron GRD válidos en las carpetas indicadas.", "No se puede abrir: {path}",
                   "Mosaico: la lista de entrada está vacía."),
            "en": ("No valid GRD files were found in the given folders.", "Cannot open: {path}",
                   "Mosaic: the input list is empty."),
            "fr": ("Aucun fichier GRD valide n’a été trouvé dans les dossiers indiqués.", "Impossible d’ouvrir : {path}",
                   "Mosaïque : la liste d’entrée est vide."),
            "de": ("In den angegebenen Ordnern wurden keine gültigen GRD-Dateien gefunden.",
                   "Kann nicht geöffnet werden: {path}", "Mosaik: Die Eingabeliste ist leer."),
        }
        missing = os.path.join(self.folder, "g1.grd")
        for lang in _LANGS:
            i18n.set_language(lang)
            no_grd, cannot_open, empty = expected[lang]
            with self.subTest(lang=lang):
                with self.assertRaises(RuntimeError) as caught:
                    union_recurso._scan_tiles([self.folder])
                self.assertEqual(str(caught.exception), no_grd)
                with self.assertRaises(IOError) as caught:
                    union_recurso._read_grd(missing)
                self.assertEqual(str(caught.exception), cannot_open.format(path=missing))
                with self.assertRaises(ValueError) as caught:
                    union_recurso._mosaic_to_mem([])
                self.assertEqual(str(caught.exception), empty)

    def test_messages_in_each_language(self):
        expected = {
            "es": ("Selecciona carpetas de teselas (WAsP)",
                   "Controlador: GSAG\nCarpeta py_wake: (no creado)\nMovidos a _bad_for_pywake (para evitar un fallo): 0\n"),
            "en": ("Select tile folders (WAsP)",
                   "Driver: GSAG\npy_wake folder: (not created)\nMoved to _bad_for_pywake (to avoid a crash): 0\n"),
            "fr": ("Sélectionnez les dossiers de tuiles (WAsP)",
                   "Pilote : GSAG\nDossier py_wake : (non créé)\nDéplacés vers _bad_for_pywake (pour éviter un plantage) : 0\n"),
            "de": ("Kachelordner auswählen (WAsP)",
                   "Treiber: GSAG\npy_wake-Ordner: (nicht erstellt)\n"
                   "Nach _bad_for_pywake verschoben (um einen Absturz zu vermeiden): 0\n"),
        }
        result = {"n_out": 0, "n_skipped": 0, "n_sectors": 0, "n_heights": 0, "vars": 0, "driver": "GSAG",
                  "pywake_dir": "", "pywake_bad_moved": 0, "epsg": 25830}
        for lang in _LANGS:
            i18n.set_language(lang)
            title, summary = expected[lang]
            with self.subTest(lang=lang), \
                    mock.patch.object(union_recurso.QtWidgets, "QMessageBox") as box, \
                    mock.patch.object(union_recurso.QtWidgets, "QFileDialog") as files, \
                    mock.patch.object(union_recurso.QtWidgets, "QInputDialog") as ask, \
                    mock.patch.object(union_recurso, "_EPSG", 25830), \
                    mock.patch.object(union_recurso, "construir_waspgridsite", return_value=result):
                files.return_value.exec_.return_value = QtWidgets.QDialog.Accepted
                files.return_value.findChildren.return_value = []
                files.return_value.selectedUrls.return_value = [QtCore.QUrl.fromLocalFile(self.folder)]
                files.getExistingDirectory.return_value = self.folder
                ask.getText.return_value = ("", True)
                self.assertIs(union_recurso.ejecutar_waspgridsite(), result)
                shown = [c.args[2] for c in box.information.call_args_list]
                self.assertEqual(shown[0], _WASP_MESSAGES[lang]["intro"])
                ask.getText.assert_called_once_with(
                    None, _WASP_MESSAGES[lang]["epsg_title"], _WASP_MESSAGES[lang]["epsg_prompt"])
                self.assertEqual(files.call_args.args[1], title)
                self.assertTrue(shown[-1].endswith(summary), shown[-1])


# What the hub shows, created in each language and after a live change to it.
_HUB = {
    "es": {"subtitle": "Selecciona el módulo de trabajo. Los módulos están operativos: Energía (AEP y estelas), Ruido y "
                       "Sombras y parpadeo.",
           "energy": "Energía\nAEP y estelas", "flicker": "Sombras y\nparpadeo",
           "ti": "No seleccionado (TI=10% por defecto en el flujo WRG)", "resource": "Rejillas WAsP: /srv/g1",
           "support": "Apoya voluntariamente el desarrollo, el mantenimiento y la validación de VelantisWind."},
    "en": {"subtitle": "Select the work module. The available modules are: Energy (AEP and wakes), Noise and Shadow "
                       "flicker.",
           "energy": "Energy\nAEP and wakes", "flicker": "Shadow\nflicker",
           "ti": "Not selected (TI=10% by default in the WRG flow)", "resource": "WAsP grids: /srv/g1",
           "support": "Optionally support the development, maintenance and validation of VelantisWind."},
    "fr": {"subtitle": "Sélectionnez le module de travail. Les modules disponibles sont : Énergie (AEP et sillages), "
                       "Bruit et Ombres portées.",
           "energy": "Énergie\nAEP et sillages", "flicker": "Ombres\nportées",
           "ti": "Non sélectionné (TI=10 % par défaut dans le flux WRG)", "resource": "Grilles WAsP : /srv/g1",
           "support": "Soutenez librement le développement, la maintenance et la validation de VelantisWind."},
    "de": {"subtitle": "Wählen Sie das Arbeitsmodul. Verfügbar sind: Energie (AEP und Nachlauf), Schall und "
                       "Schattenwurf.",
           "energy": "Energie\nAEP und Nachlauf", "flicker": "Schattenwurf",
           "ti": "Nicht ausgewählt (standardmäßig TI=10 % im WRG-Ablauf)", "resource": "WAsP-Gitter: /srv/g1",
           "support": "Unterstützen Sie freiwillig die Entwicklung, Wartung und Validierung von VelantisWind."},
}

_HUB_DE_OPTIMIZATION = {
    "lbl_layout_optimization_hint": "Erweiterte Layout-Optimierung und Nachlaufsteuerung (Wake Steering) für mehr "
                                    "Energieertrag",
    "lbl_layout_optimization_title": "Erweiterter Rechenkern für Layout + Nachlaufsteuerung (Wake Steering)",
}


class HubTextsTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.addCleanup(i18n.set_language, "es")
        settings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        settings.setValue("last_wasp_dir", "/srv/g1")
        self.addCleanup(settings.remove, "last_wasp_dir")

    def hub(self, lang):
        i18n.set_language(lang)
        hub = VelantisHubDialog()
        self.addCleanup(hub.deleteLater)
        return hub

    def assertHubIn(self, hub, lang):
        expected = _HUB[lang]
        self.assertEqual(hub.lbl_hub_subtitle.text(), expected["subtitle"])
        self.assertEqual(hub.btn_energy.text(), expected["energy"])
        self.assertEqual(hub.btn_flicker.text(), expected["flicker"])
        self.assertEqual(hub.lbl_ti.text(), expected["ti"])
        self.assertEqual(hub.lbl_resource.text(), expected["resource"])
        self.assertEqual(hub.btn_support_velantis.toolTip(), expected["support"])
        if lang == "de":
            for name, text in _HUB_DE_OPTIMIZATION.items():
                self.assertEqual(getattr(hub, name).text(), text)
            self.assertNotIn("Motor", hub.lbl_layout_optimization_title.text())
            self.assertIn("Nachlaufsteuerung", hub.lbl_layout_optimization_text.text())

    def test_created_in_each_language(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                hub = self.hub(lang)
                self.assertHubIn(hub, lang)
                # The optimization block, written in each language, is not translated a second time when it is built.
                block = [hub.lbl_layout_optimization_hint, hub.lbl_layout_optimization_title,
                         hub.lbl_layout_optimization_text, hub.lbl_layout_optimization_contact,
                         hub.btn_layout_optimization_info, hub.btn_copy_optimization_contact, hub.btn_open_white_paper]
                built = [(w.text(), w.toolTip()) for w in block]
                hub._apply_home_texts()
                self.assertEqual(built, [(w.text(), w.toolTip()) for w in block])

    def test_after_a_live_change_from_spanish(self):
        for lang in _LANGS[1:]:
            with self.subTest(lang=lang):
                hub = self.hub("es")
                hub.cb_language.setCurrentIndex(hub.cb_language.findData(lang))
                self.assertHubIn(hub, lang)


class PluginActionTest(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)
        self.addCleanup(i18n.set_language, "es")
        QtCore.QSettings().setValue("locale/userLocale", "es_ES")

    def test_status_tip_follows_the_language_chosen_in_the_hub(self):
        expected = {"es": "Abrir el hub principal de Velantis Wind", "en": "Open the main Velantis Wind hub",
                    "fr": "Ouvrir le hub principal de Velantis Wind", "de": "Haupthub von Velantis Wind öffnen"}
        i18n.set_language("es")
        iface = mock.Mock()
        iface.mainWindow.return_value = None
        velantis = plugin.VelantisWindPlugin(iface)
        velantis.initGui()
        (action,) = velantis.actions
        self.assertEqual(action.statusTip(), expected["es"])
        with mock.patch.object(plugin.deps, "ensure_dependencies", return_value=True):
            velantis.run()
        self.addCleanup(velantis.dlg.deleteLater)
        self.addCleanup(velantis.dlg.hide)
        for lang in ("en", "fr", "de", "es"):
            with self.subTest(lang=lang):
                combo = velantis.dlg.cb_language
                combo.setCurrentIndex(combo.findData(lang))
                self.assertEqual(action.statusTip(), expected[lang])


# Full labels for the support fields corrected in Z1, in all four languages.
_SUPPORT = {'es': {'supportHero': 'Flujos de trabajo eólicos de código abierto, directamente dentro de QGIS.',
        'supportSubtitle': 'VelantisWind es un plugin gratuito y de código abierto para QGIS orientado al '
                           'análisis preliminar de parques eólicos, validación técnica y tareas SIG de '
                           'preevaluación. Tu apoyo ayuda a convertirlo en una herramienta más robusta, '
                           'documentada y validada para flujos de trabajo reales.',
        'supportDisclaimer': 'VelantisWind seguirá siendo gratuito y de código abierto. El apoyo es opcional '
                             'y no implica propiedad, exclusividad ni control sobre la hoja de ruta. El '
                             'reconocimiento público es opcional y puede omitirse si el patrocinador desea '
                             'permanecer anónimo. Contacto: info@velantiswind.com',
        'why_title': '¿Qué ayuda a financiar el apoyo?',
        'bodies': ['<ul><li>Mantenimiento del plugin, estabilidad y compatibilidad con '
                   'QGIS.</li><li>Documentación, tutoriales, ejemplos y traducciones.</li><li>Validación con '
                   'casos reales de parques eólicos.</li><li>Mejoras en los módulos de AEP, estelas, ruido y '
                   'sombras.</li><li>Soporte para quienes prueban las versiones beta, los primeros usuarios '
                   'y los socios técnicos.</li><li>Nuevas funcionalidades solicitadas por usuarios, '
                   'consultoras, universidades y socios.</li></ul>',
                   'El apoyo de usuarios, consultoras, universidades y probadores de versiones beta ayuda a '
                   'mejorar la documentación, la estabilidad, la validación con casos reales y las '
                   'funcionalidades futuras del proyecto de código abierto.',
                   'VelantisWind está abierto a universidades y grupos de investigación. TFG, TFM o trabajos '
                   'aplicados pueden ayudar a validar, documentar o ampliar el plugin con nuevos módulos, '
                   'siempre que estén técnicamente alineados con el proyecto de código abierto.',
                   '<ul><li>Pruebas de versiones beta y comentarios técnicos.</li><li>Validación frente a '
                   'proyectos reales o flujos de trabajo internos.</li><li>Contribuciones técnicas, '
                   'documentación o ejemplos.</li><li>Casos de uso, ejemplos de validación y comentarios '
                   'sobre la documentación.</li><li>Colaboración académica mediante TFG/TFM, investigación '
                   'aplicada o material docente.</li></ul>'],
        'tier_labels': ["<b>Project Supporter</b><br><span style='color:#5f6b76'>Nombre opcional en la lista "
                        'de patrocinadores.</span>',
                        "<b>Community Sponsor</b><br><span style='color:#5f6b76'>Nombre opcional en la lista "
                        'de patrocinadores.</span>',
                        "<b>Validation Sponsor</b><br><span style='color:#5f6b76'>Logo y mención como "
                        'patrocinador de validación.</span>'],
        'project': 'Documentación del proyecto', 'supporters': 'Patrocinadores'},
 'en': {'supportHero': 'Open-source wind energy workflows, directly inside QGIS.',
        'supportSubtitle': 'VelantisWind is a free and open-source QGIS plugin for early-stage wind farm '
                           'analysis, validation workflows and geospatial pre-assessment tasks. Your support '
                           'helps transform it into a more robust, documented and validated tool for '
                           'practical wind energy workflows.',
        'supportDisclaimer': 'VelantisWind will remain free and open source. Sponsorship is optional and '
                             'does not imply ownership, exclusivity or control over the roadmap. Public '
                             'recognition is optional and may be omitted if the supporter prefers to remain '
                             'anonymous. Contact: info@velantiswind.com',
        'why_title': 'What does your support help fund?',
        'bodies': ['<ul><li>Plugin maintenance, stability and QGIS compatibility.</li><li>Documentation, '
                   'tutorials, examples and translations.</li><li>Validation with real wind farm '
                   'cases.</li><li>Improvements in the AEP, wake, noise and shadow flicker '
                   'modules.</li><li>Support for beta testers, early adopters and technical '
                   'partners.</li><li>New features requested by users, consultants, universities and '
                   'technical partners.</li></ul>',
                   'Support from users, consultants, universities and beta testers helps improve '
                   'documentation, stability, validation with real cases and future open-source '
                   'functionality.',
                   'VelantisWind is open to universities and research groups. Bachelor’s and Master’s thesis '
                   'projects or applied research can help validate, document or extend the plugin with new '
                   'modules when technically aligned with the open-source project.',
                   '<ul><li>Beta testing and technical feedback.</li><li>Validation against real projects or '
                   'internal workflows.</li><li>Technical contributions, documentation or '
                   'examples.</li><li>Use cases, validation examples and documentation '
                   'feedback.</li><li>Academic collaboration through thesis projects, applied research or '
                   'teaching material.</li></ul>'],
        'tier_labels': ["<b>Project Supporter</b><br><span style='color:#5f6b76'>Optional name in the "
                        'supporters list.</span>',
                        "<b>Community Sponsor</b><br><span style='color:#5f6b76'>Optional name in the "
                        'supporters list.</span>',
                        "<b>Validation Sponsor</b><br><span style='color:#5f6b76'>Logo recognition and "
                        'validation sponsor mention.</span>'],
        'project': 'Project documentation', 'supporters': 'Supporters'},
 'fr': {'supportHero': 'Des flux de travail éoliens open source, directement dans QGIS.',
        'supportSubtitle': 'VelantisWind est un plugin QGIS gratuit et open source destiné à l’analyse '
                           'préliminaire des parcs éoliens, aux flux de validation et aux tâches de '
                           'préévaluation géospatiale. Votre soutien aide à en faire un outil plus robuste, '
                           'mieux documenté et mieux validé pour des flux de travail réels.',
        'supportDisclaimer': 'VelantisWind restera gratuit et open source. Le soutien est optionnel et '
                             'n’implique ni propriété, ni exclusivité, ni contrôle sur la feuille de route. '
                             'La reconnaissance publique est optionnelle et peut être omise si le supporter '
                             'souhaite rester anonyme. Contact : info@velantiswind.com',
        'why_title': 'Que permet de financer votre soutien ?',
        'bodies': ['<ul><li>Maintenance du plugin, stabilité et compatibilité avec '
                   'QGIS.</li><li>Documentation, tutoriels, exemples et traductions.</li><li>Validation avec '
                   'des cas réels de parcs éoliens.</li><li>Améliorations des modules AEP, sillages, bruit '
                   'et ombres portées.</li><li>Support pour les bêta-testeurs, les premiers utilisateurs et '
                   'les partenaires techniques.</li><li>Nouvelles fonctionnalités demandées par les '
                   'utilisateurs, bureaux d’études, universités et partenaires.</li></ul>',
                   'Le soutien des utilisateurs, bureaux d’études, universités et bêta-testeurs aide à '
                   'améliorer la documentation, la stabilité, la validation avec des cas réels et les '
                   'futures fonctionnalités open source.',
                   'VelantisWind est ouvert aux universités et aux groupes de recherche. Des projets de fin '
                   'd’études, mémoires ou travaux appliqués peuvent aider à valider, documenter ou étendre '
                   'le plugin avec de nouveaux modules, à condition qu’ils soient techniquement alignés avec '
                   'le projet open source.',
                   '<ul><li>Bêta-test et retours techniques.</li><li>Validation sur des projets réels ou des '
                   'flux de travail internes.</li><li>Contributions techniques, documentation ou '
                   'exemples.</li><li>Cas d’usage, exemples de validation et retours sur la '
                   'documentation.</li><li>Collaboration académique via projets de fin d’études, recherche '
                   'appliquée ou matériel pédagogique.</li></ul>'],
        'tier_labels': ["<b>Project Supporter</b><br><span style='color:#5f6b76'>Nom optionnel dans la liste "
                        'des supporters.</span>',
                        "<b>Community Sponsor</b><br><span style='color:#5f6b76'>Nom optionnel dans la liste "
                        'des supporters.</span>',
                        "<b>Validation Sponsor</b><br><span style='color:#5f6b76'>Logo et mention comme "
                        'sponsor de validation.</span>'],
        'project': 'Documentation du projet', 'supporters': 'Supporters'},
 'de': {'supportHero': 'Open-Source-Workflows für Windenergie, direkt in QGIS.',
        'supportSubtitle': 'VelantisWind ist ein kostenloses Open-Source-QGIS-Plugin für die frühe Analyse '
                           'von Windparks, Validierungsworkflows und georäumliche Vorbewertungen. Ihre '
                           'Unterstützung hilft dabei, daraus ein robusteres, besser dokumentiertes und '
                           'besser validiertes Werkzeug für praktische Windenergie-Workflows zu machen.',
        'supportDisclaimer': 'VelantisWind bleibt kostenlos und open source. Unterstützung ist optional und '
                             'bedeutet weder Eigentum, Exklusivität noch Kontrolle über die Roadmap. '
                             'Öffentliche Anerkennung ist optional und kann entfallen, wenn der Supporter '
                             'anonym bleiben möchte. Kontakt: info@velantiswind.com',
        'why_title': 'Wofür wird Ihre Unterstützung verwendet?',
        'bodies': ['<ul><li>Wartung des Plugins, Stabilität und QGIS-Kompatibilität.</li><li>Dokumentation, '
                   'Tutorials, Beispiele und Übersetzungen.</li><li>Validierung mit realen '
                   'Windpark-Fällen.</li><li>Verbesserungen an den Modulen AEP, Nachlauf, Schall und '
                   'Schattenwurf.</li><li>Support für Beta-Tester, frühe Anwender und technische '
                   'Partner.</li><li>Neue Funktionen, die von Nutzern, Beratungsunternehmen, Universitäten '
                   'und Partnern angefragt werden.</li></ul>',
                   'Die Unterstützung von Nutzern, Beratungsunternehmen, Universitäten und Beta-Testern '
                   'hilft, Dokumentation, Stabilität, Validierung mit realen Fällen und zukünftige '
                   'Open-Source-Funktionen zu verbessern.',
                   'VelantisWind ist offen für Universitäten und Forschungsgruppen. Bachelor- und '
                   'Masterarbeiten oder angewandte Forschungsprojekte können helfen, das Plugin zu '
                   'validieren, zu dokumentieren oder mit neuen Modulen zu erweitern, sofern sie technisch '
                   'zum Open-Source-Projekt passen.',
                   '<ul><li>Beta-Testing und technisches Feedback.</li><li>Validierung anhand realer '
                   'Projekte oder interner Workflows.</li><li>Technische Beiträge, Dokumentation oder '
                   'Beispiele.</li><li>Anwendungsfälle, Validierungsbeispiele und Feedback zur '
                   'Dokumentation.</li><li>Akademische Zusammenarbeit über Abschlussarbeiten, angewandte '
                   'Forschung oder Lehrmaterial.</li></ul>'],
        'tier_labels': ["<b>Project Supporter</b><br><span style='color:#5f6b76'>Optionaler Name in der "
                        'Supporter-Liste.</span>',
                        "<b>Community Sponsor</b><br><span style='color:#5f6b76'>Optionaler Name in der "
                        'Supporter-Liste.</span>',
                        "<b>Validation Sponsor</b><br><span style='color:#5f6b76'>Logo und Erwähnung als "
                        'Validierungssponsor.</span>'],
        'project': 'Projektdokumentation', 'supporters': 'Unterstützer'}}


class SupportDialogTextsTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_language, "es")

    def test_complete_corrected_texts_in_each_language(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                dialog = support_dialog.SupportDialog()
                self.addCleanup(dialog.deleteLater)
                expected = _SUPPORT[lang]
                for name in ("supportHero", "supportSubtitle", "supportDisclaimer"):
                    self.assertEqual(dialog.findChild(QtWidgets.QLabel, name).text(), expected[name])
                self.assertEqual(dialog.findChildren(QtWidgets.QLabel, "supportInfoTitle")[0].text(),
                                 expected["why_title"])
                self.assertEqual([w.text() for w in dialog.findChildren(QtWidgets.QLabel, "supportInfoBody")],
                                 expected["bodies"])
                tiers = dialog.findChildren(QtWidgets.QFrame, "supportTierBox")
                self.assertEqual([tiers[i].findChildren(QtWidgets.QLabel)[0].text() for i in (1, 5, 8)],
                                 expected["tier_labels"])
                self.assertEqual(dialog.btn_project.text(), expected["project"])
                self.assertEqual(dialog.btn_supporters.text(), expected["supporters"])

    def texts(self, lang):
        i18n.set_language(lang)
        dialog = support_dialog.SupportDialog()
        self.addCleanup(dialog.deleteLater)
        # The names of the support tiers are proper names, the same in every language.
        names = [name for name, _amount, _description in support_dialog._TEXTS[lang]["tiers"]]
        out = []
        for w in dialog.findChildren(QtWidgets.QLabel) + dialog.findChildren(QtWidgets.QPushButton):
            text = w.text()
            for name in names:
                text = text.replace(name, "")
            out.append(text)
        return " ".join(out)

    def test_spanish_without_english_words(self):
        text = self.texts("es").lower()
        for word in ("open source", "beta tester", "early adopter", "partner", "workflow", "feedback", "roadmap",
                     "supporter", " gis "):
            with self.subTest(word=word):
                self.assertNotIn(word, text)
        self.assertIn("código abierto", text)

    def test_french_without_english_workflow_words(self):
        text = self.texts("fr").lower()
        for word in ("workflow", "feedback"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)

    def test_german_uses_sie(self):
        text = self.texts("de")
        for word in ("Deine ", "deine ", "Dein ", "dein "):
            with self.subTest(word=word):
                self.assertNotIn(word, text)
        self.assertIn("Ihre Unterstützung", text)


if __name__ == "__main__":
    unittest.main()
