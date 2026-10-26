# -*- coding: utf-8 -*-
"""The Noise results dialog and its exports in the four languages: the CSV keep their columns and follow the language of
the plugin, the XLSX translates its headers, the receivers CSV and the receivers sheet share their rows, and the names of
the user (groups, wind farms, models, layers, file names) come out as written in the table, the CSV, the XLSX and the
report."""
import csv
import os
import re
import tempfile
import unittest
import zipfile
from unittest import mock
from xml.etree import ElementTree

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind.ag_core import turbine_ui  # noqa: E402,F401
from VelantisWind.noise_core import project_watch  # noqa: E402,F401
from VelantisWind.spacing_core import controller  # noqa: E402,F401
from VelantisWind import noise_page  # noqa: E402,F401
from VelantisWind import noise_results_dialog as nrd  # noqa: E402
from VelantisWind.noise_core.results.xlsx_writer import write_xlsx_workbook  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("es", "en", "fr", "de")


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


# Names of the user that are also texts of the interface or contain words the translator knows.
_USER_TEXTS = ["Plantilla: Norte", "Modelo Norte", "Turbinas", "Parque", "Plantilla: Bosques", "MDT desde capa",
               "/tmp/modelo/Turbinas sin nombre.gpkg", "curva genérica desde capa.csv", "Plantilla Norte.csv"]
# What the translator or the old clean-up made of them.
_DEFORMED = ["Template: Norte", "Gabarit : Norte", "Vorlage: Norte", "Model Norte", "Modèle Norte", "Modell Norte",
             "Template: Bosques", "Gabarit : Bosques", "Vorlage: Bosques", "MDT from layer", "MDT depuis couche",
             "MDT aus Layer", "/tmp/model/", "unnamed.gpkg", "sans nom.gpkg", "ohne Namen.gpkg", "generic curve",
             "courbe générique", "generische Kennlinie", "Wind farm", "Parc éolien", "Windpark Parque"]


def _result():
    lw = {63: 95.0, 125: 98.0, 250: 99.0, 500: 98.0, 1000: 96.0, 2000: 93.0, 4000: 88.0, 8000: 82.0}
    spectrum = "Biblioteca: Plantilla Norte.csv · normalizado a LwA del grupo"
    rows = [
        {"rec_id": "R-7", "rec_type": "Parque", "noise_dba": 46.2, "limit_dba": 45.0, "margin_db": 1.2, "state": "supera",
         "exceeds": 1, "n_src": 3, "near_m": 500.0, "dom_model": "Plantilla: Norte", "dom_group": "Turbinas",
         "dom_park": "Parque", "src_lwa": 105.0, "adiv_db": 65.0, "aatm_db": 2.0, "aground_db": 1.0, "abar_max_db": 0.0,
         "ground_g": 0.5, "ground_md": "from_layer", "rec_h_m": 4.0, "rec_z_m": 100.0, "rec_ac_z_m": 104.0,
         "dom_src_lyr": "/tmp/modelo/Turbinas sin nombre.gpkg"},
        {"rec_id": "R-8", "rec_type": "", "noise_dba": 40.0, "limit_dba": 45.0, "margin_db": -5.0, "state": "cumple",
         "exceeds": 0, "n_src": 2, "near_m": 900.0, "dom_model": "Modelo Norte", "dom_group": "Turbinas",
         "dom_park": "Parque", "src_lwa": 105.0, "adiv_db": 70.0, "aatm_db": 3.0, "aground_db": 1.5, "abar_max_db": 0.0,
         "ground_g": 0.5, "ground_md": "global", "rec_h_m": 4.0, "rec_z_m": 90.0, "rec_ac_z_m": 94.0,
         "dom_src_lyr": "Turbinas"},
    ]
    group = {"count": 3, "lwa": 105.0, "hub_height": 100.0, "diameter": 120.0}
    return {
        "n_sources": 5, "n_receivers": 3, "n_receivers_with_sources": 2, "n_uncovered_receivers": 1,
        "n_receivers_exceeding_limit": 1, "max_noise_dba": 46.2,
        "model_diag": {
            "Plantilla: Norte": dict(group, name="Turbinas", model_name="Plantilla: Norte", park_name="Parque",
                                     acoustic_mode="curve", curve_path="/tmp/modelo/curva genérica desde capa.csv",
                                     curve_note="Curva @ 8.0 m/s (curva genérica desde capa.csv)"),
            "Modelo Norte": dict(group, name="Parque", model_name="Modelo Norte", acoustic_mode="fixed"),
            "Turbinas": dict(group, name="Turbinas", model_name="Turbinas", acoustic_mode="curve",
                             curve_path="/tmp/modelo/curva.csv", curve_note=""),
        },
        "receiver_type_counts": {"Parque": 1, "no_type": 2},
        "receiver_type_compliance": {"Parque": {"exceed": 1, "total": 1, "covered": 1}},
        "critical_receiver": {"rec_id": "R-7", "total_level_dba": 46.2, "limite_aplicado_dba": 45.0,
                              "limit_margin_db": 1.2, "modelo_dominante": "Plantilla: Norte",
                              "grupo_fuente_dominante": "Turbinas", "parque_dominante": "Parque",
                              "turbines_in_radius": 3, "banda_dominante_hz": 500, "spectrum_source": spectrum},
        "report_meta": {"engine": "iso_aligned", "dem_used": True, "dem_layer_name": "MDT desde capa",
                        "landuse_used": True, "landuse_layer_name": "Plantilla: Bosques", "ground_mode": "landuse",
                        "spectrum_sources": [{"group_name": "Turbinas", "model_name": "Plantilla: Norte",
                                              "spectrum_source": spectrum, "lw_octave": lw,
                                              "spectrum_template_ref": {}, "spectrum_delta_db": float("nan")}]},
        "acoustic_scenario": {"mode": "fixed", "effective_models": [
            {"name": "Turbinas", "model_name": "Plantilla: Norte", "park_name": "Parque", "lwa_effective": 105.0}]},
        "receiver_rows": rows,
        "top_receivers": rows,
    }


_RECEIVER_HEADERS = {
    "es": [label for _key, label in nrd.CONSULTANCY_RECEIVER_COLUMNS],
    "en": ["receiver ID", "type", "total level dB(A)", "limit dB(A)", "margin to limit dB", "status", "exceeds limit",
           "no. wind turbines", "nearest wind turbine dist. (m)", "dominant model", "dominant source group",
           "dominant wind farm", "dominant source LwA dB(A)", "Adiv dB", "Aatm dB", "Agr/Aground dB", "max. Abar dB",
           "ground G", "ground mode", "receiver height m", "receiver terrain z m", "receiver acoustic z m",
           "dominant source layer"],
    "fr": ["ID récepteur", "type", "niveau total dB(A)", "limite dB(A)", "marge par rapport à la limite dB", "état",
           "dépasse la limite", "nb éoliennes", "dist. éolienne proche (m)", "modèle dominant", "groupe de sources dom.",
           "parc dom.", "LwA source dom. dB(A)", "Adiv dB", "Aatm dB", "Agr/Aground dB", "Abar max. dB", "G sol",
           "mode sol", "h récepteur m", "z terrain récepteur m", "z acoustique récepteur m", "couche source dominante"],
    "de": ["Rezeptor-ID", "Typ", "Gesamtpegel dB(A)", "Grenzwert dB(A)", "Abstand zum Grenzwert dB", "Status",
           "überschreitet Grenzwert", "Anz. Windturbinen", "nächste Windturbine (m)", "dominantes Modell",
           "dominante Quellgruppe", "dominanter Windpark", "LwA der dominanten Quelle dB(A)", "Adiv dB", "Aatm dB",
           "Agr/Aground dB", "max. Abar dB", "Boden-G", "Bodenmodus", "Rezeptorhöhe m", "Geländehöhe Rezeptor m",
           "akustische Höhe Rezeptor m", "dominanter Quellen-Layer"],
}
_SHEETS = {
    "es": ["Resumen", "Modelos", "Receptores", "Excedencias", "Capas creadas"],
    "en": ["Summary", "Models", "Receivers", "Exceedances", "Created layers"],
    "fr": ["Résumé", "Modèles", "Récepteurs", "Dépassements", "Couches créées"],
    "de": ["Übersicht", "Modelle", "Rezeptoren", "Überschreitungen", "Erzeugte Layer"],
}
_MODEL_HEADERS = {
    "es": ["Modelo de aerogenerador", "Aerogeneradores", "LwA efectivo", "HH", "D", "Notas"],
    "en": ["Wind turbine model", "Wind turbines", "Effective LwA", "HH", "D", "Notes"],
    "fr": ["Modèle d’éolienne", "Éoliennes", "LwA effectif", "HH", "D", "Notes"],
    "de": ["Windturbinenmodell", "Windturbinen", "Effektiver LwA", "NH", "D", "Notizen"],
}
_NOTES = {  # curve note, fixed LwA, curve without a note
    "es": ["Curva @ 8.0 m/s (curva genérica desde capa.csv)", "LwA fijo por grupo de fuente acústica", "Curva acústica activa"],
    "en": ["Curve at 8.0 m/s (curva genérica desde capa.csv)", "Fixed LwA per acoustic source group", "Active acoustic curve"],
    "fr": ["Courbe à 8.0 m/s (curva genérica desde capa.csv)", "LwA fixe par groupe de sources acoustiques", "Courbe acoustique active"],
    "de": ["Kurve bei 8.0 m/s (curva genérica desde capa.csv)", "Fester LwA je akustischer Quellgruppe", "Aktive akustische Kurve"],
}
_LAYER_TABLE = {
    "es": [["Capa", "Estado"], "creada", "no creada"],
    "en": [["Layer", "Status"], "created", "not created"],
    "fr": [["Couche", "État"], "créée", "non créée"],
    "de": [["Layer", "Status"], "erzeugt", "nicht erzeugt"],
}
_LAYER_NAMES = ["Noise · Receivers", "Noise · Sources", "Noise · Dominant links", "Noise · Receivers outside radius",
                "Noise · Map", "Noise · Isophones"]
_YES_NO = {"es": ("sí", "no"), "en": ("yes", "no"), "fr": ("oui", "non"), "de": ("ja", "nein")}
_TEXTS = {  # window title, title label, tab of the receivers, its tooltip, tooltip of the exceedances button
    "es": ["Ruido · Resumen técnico", "Ruido · Resumen del cálculo", 'Receptores principales',
           "Tabla sintética para consultoría: resultados acústicos por receptor, cumplimiento, fuente dominante y "
           "atenuaciones principales. Los diagnósticos internos MDT por pares se conservan en memoria, pero no se "
           "muestran por defecto.", "Guarda únicamente los receptores que superan su límite acústico."],
    "en": ["Noise · Technical summary", "Noise · Calculation summary", "Top receivers",
           "Summary table for consultancy: acoustic results per receiver, compliance, dominant source and main "
           "attenuations. The internal pairwise DEM diagnostics are kept in memory but are not shown by default.",
           "Save only the receivers that exceed their acoustic limit."],
    "fr": ["Bruit · Résumé technique", "Bruit · Résumé du calcul", "Principaux récepteurs",
           "Tableau synthétique pour le conseil : résultats acoustiques par récepteur, conformité, source dominante et "
           "principales atténuations. Les diagnostics internes MNT par paires sont conservés en mémoire, mais ne sont "
           "pas affichés par défaut.", "Enregistre uniquement les récepteurs qui dépassent leur limite acoustique."],
    "de": ["Schall · Technische Übersicht", "Schall · Berechnungsübersicht", "Top-Rezeptoren",
           "Übersichtstabelle für die Beratung: akustische Ergebnisse je Rezeptor, Konformität, dominante Quelle und "
           "wichtigste Dämpfungen. Die internen paarweisen DGM-Diagnosen werden im Speicher gehalten, aber "
           "standardmäßig nicht angezeigt.",
           "Speichert nur die Rezeptoren, die ihren akustischen Grenzwert überschreiten."],
}
_SAVE_DIALOGS = {  # summary, receivers, exceedances, package: (title, default file name, filter)
    "es": [("Exportar resumen", "ruido_resumen.html", "HTML (*.html);;Texto (*.txt)"),
           ("Exportar receptores CSV", "ruido_receptores.csv", "CSV (*.csv)"),
           ("Exportar excedencias CSV", "ruido_excedencias.csv", "CSV (*.csv)"),
           ("Exportar paquete XLSX", "ruido_paquete.xlsx", "Excel (*.xlsx)")],
    "en": [("Export summary", "noise_summary.html", "HTML (*.html);;Text (*.txt)"),
           ("Export receivers CSV", "noise_receivers.csv", "CSV (*.csv)"),
           ("Export exceedances CSV", "noise_exceedances.csv", "CSV (*.csv)"),
           ("Export XLSX package", "noise_package.xlsx", "Excel (*.xlsx)")],
    "fr": [("Exporter le résumé", "bruit_resume.html", "HTML (*.html);;Texte (*.txt)"),
           ("Exporter les récepteurs en CSV", "bruit_recepteurs.csv", "CSV (*.csv)"),
           ("Exporter les dépassements en CSV", "bruit_depassements.csv", "CSV (*.csv)"),
           ("Exporter le paquet XLSX", "bruit_paquet.xlsx", "Excel (*.xlsx)")],
    "de": [("Zusammenfassung exportieren", "schall_zusammenfassung.html", "HTML (*.html);;Text (*.txt)"),
           ("Rezeptoren als CSV exportieren", "schall_rezeptoren.csv", "CSV (*.csv)"),
           ("Überschreitungen als CSV exportieren", "schall_ueberschreitungen.csv", "CSV (*.csv)"),
           ("XLSX-Paket exportieren", "schall_paket.xlsx", "Excel (*.xlsx)")],
}
_NO_EXCEEDANCES = {
    "es": ("Exportar excedencias", "Ningún receptor supera el límite en este cálculo."),
    "en": ("Export exceedances", "No receiver exceeds the limit in this calculation."),
    "fr": ("Exporter les dépassements", "Aucun récepteur ne dépasse la limite dans ce calcul."),
    "de": ("Überschreitungen exportieren", "Kein Rezeptor überschreitet in dieser Berechnung den Grenzwert."),
}
# Glossary in the report: what has to be there and what must not.
_REPORT_TERMS = {
    "es": (["Motor ISO por bandas de octava", "MDT/MDS: habilitado · capa: MDT desde capa", "sin categoría: 2"],
           ["ISO-aligned", "Screening", "MDT/DSM", "raster"]),
    "en": (["ISO engine by octave bands", "DEM/DSM: enabled · layer: MDT desde capa", "uncategorized: 2"],
           ["ISO-aligned", "Screening mode", "DTM"]),
    # The plain text of the report turns the non-breaking space before the French colon into a space.
    "fr": (["Moteur ISO par bandes d’octave", "MNT/MNS : activé · couche : MDT desde capa", "sans catégorie : 2",
            "Mode sol : depuis la couche (Plantilla: Bosques)", "Groupe de sources : Turbinas"],
           ["ISO-aligned", "Screening", "MDT/DSM", "criblage"]),
    "de": (["ISO-Rechenkern nach Oktavbändern", "DGM/DOM: aktiviert · Layer: MDT desde capa", "ohne Kategorie: 2",
            "Rezeptor-ID: R-7"], ["ISO-aligned", "Screening-Modus", "Windenergieanlage"]),
}


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh, delimiter=";"))


def _read_xlsx(path):
    """Sheet names and, for each sheet, its rows as lists of texts."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        sheet_names = [s.get("name") for s in ElementTree.fromstring(archive.read("xl/workbook.xml")).iter(
            "{%s}sheet" % ns["m"])]
        sheets = []
        for idx in range(1, len(sheet_names) + 1):
            root = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{idx}.xml"))
            rows = []
            for row in root.iter("{%s}row" % ns["m"]):
                rows.append(["".join(t.itertext()) for t in row.iter("{%s}c" % ns["m"])])
            sheets.append(rows)
    return sheet_names, sheets


class NoiseResultsLanguagesTest(unittest.TestCase):
    def test_french_report_explanations_are_translated_in_full(self):
        cases = [
            (
                "Apantallamiento topográfico: si hay MDT/MDS, el complemento revisa la trayectoria fuente–receptor "
                "y estima Abar para obstáculos relevantes. Sin MDT/MDS u obstáculo relevante, Abar se fija en 0 dB.",
                "Écran topographique : si un MNT/MNS est disponible, l’extension examine le trajet source–récepteur "
                "et estime Abar pour les obstacles significatifs. En l’absence de MNT/MNS ou d’obstacle significatif, "
                "Abar est fixé à 0 dB.",
            ),
            (
                "Esta sección explica el flujo real seguido por el complemento para que el resultado por receptor "
                "sea trazable. El nivel final no procede de una resta única, sino de calcular todas las "
                "contribuciones fuente–receptor dentro del radio y sumarlas energéticamente.",
                "Cette section explique les étapes réellement suivies par l’extension pour assurer la traçabilité "
                "du résultat par récepteur. Le niveau final ne résulte pas d’une soustraction unique, mais du calcul "
                "de toutes les contributions source–récepteur dans le rayon de calcul et de leur somme énergétique.",
            ),
        ]
        i18n.set_language("fr")
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(i18n.tr_text(source), expected)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def tearDown(self):
        i18n.set_language("es")

    def _dialog(self, lang):
        i18n.set_language(lang)
        dlg = nrd.NoiseResultsDialog(None, _result())
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _export(self, dlg, method, name):
        path = os.path.join(self.tmp.name, name)
        with mock.patch.object(nrd.QtWidgets.QFileDialog, "getSaveFileName", return_value=(path, "")) as save, \
                mock.patch.object(nrd.QtWidgets, "QMessageBox") as box:
            getattr(dlg, method)()
        box.warning.assert_not_called()
        return path, save.call_args[0]

    def test_receiver_csv_and_xlsx_follow_the_language_with_the_same_columns(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self._dialog(lang)
                receivers = _read_csv(self._export(dlg, "_export_receivers_csv", f"rec_{lang}.csv")[0])
                exceed = _read_csv(self._export(dlg, "_export_exceedances_csv", f"exc_{lang}.csv")[0])
                _names, sheets = _read_xlsx(self._export(dlg, "_export_package_xlsx", f"pkg_{lang}.xlsx")[0])
                self.assertEqual(receivers[0], _RECEIVER_HEADERS[lang])
                self.assertEqual(len(receivers[0]), len(nrd.CONSULTANCY_RECEIVER_COLUMNS))
                self.assertEqual(exceed[0], _RECEIVER_HEADERS[lang])
                self.assertEqual(len(receivers), 3)
                self.assertEqual(len(exceed), 2)
                # The receivers sheet and the receivers CSV are the same rows, the exceedances too.
                self.assertEqual(sheets[2], receivers)
                self.assertEqual(sheets[3], exceed)
                self.assertEqual(receivers[1][6], _YES_NO[lang][0])
                self.assertEqual(receivers[2][6], _YES_NO[lang][1])
                self.assertEqual([dlg.tbl_top.horizontalHeaderItem(c).text() for c in range(dlg.tbl_top.columnCount())],
                                 _RECEIVER_HEADERS[lang])

    def test_xlsx_sheets_and_headers_are_translated(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self._dialog(lang)
                names, sheets = _read_xlsx(self._export(dlg, "_export_package_xlsx", f"pkg_{lang}.xlsx")[0])
                self.assertEqual(names, _SHEETS[lang])
                self.assertEqual(sheets[1][0], _MODEL_HEADERS[lang])
                self.assertEqual([row[5] for row in sheets[1][1:]], _NOTES[lang])
                self.assertEqual(sheets[4][0], _LAYER_TABLE[lang][0])
                self.assertEqual(sheets[4][1:], [[name, _LAYER_TABLE[lang][2]] for name in _LAYER_NAMES])

    def test_user_names_are_kept_as_written(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self._dialog(lang)
                outputs = {
                    "table": "\n".join(dlg.tbl_top.item(r, c).text() for r in range(dlg.tbl_top.rowCount())
                                       for c in range(dlg.tbl_top.columnCount())),
                    "models": "\n".join(dlg.tbl_models.item(r, c).text() for r in range(dlg.tbl_models.rowCount())
                                        for c in range(dlg.tbl_models.columnCount())),
                }
                for method, name in (("_export_receivers_csv", "rec.csv"), ("_export_exceedances_csv", "exc.csv"),
                                     ("_export_summary", "report.html"), ("_export_summary", "report.txt")):
                    path = self._export(dlg, method, f"{lang}_{name}")[0]
                    with open(path, encoding="utf-8-sig") as fh:
                        outputs[name] = fh.read()
                _names, sheets = _read_xlsx(self._export(dlg, "_export_package_xlsx", f"{lang}.xlsx")[0])
                outputs["xlsx"] = "\n".join(cell for sheet in sheets for row in sheet for cell in row)
                report = outputs["report.txt"]
                for text in ("Plantilla: Norte", "Turbinas", "Parque", "Plantilla: Bosques", "MDT desde capa",
                             "Plantilla Norte.csv"):
                    self.assertIn(text, report)
                for text in ("Plantilla: Norte", "Modelo Norte", "Turbinas", "Parque", "/tmp/modelo/Turbinas sin nombre.gpkg"):
                    self.assertIn(text, outputs["rec.csv"])
                    self.assertIn(text, outputs["table"])
                self.assertIn("curva genérica desde capa.csv", outputs["models"])
                for text in _USER_TEXTS:
                    self.assertIn(text, outputs["xlsx"])
                for where, out in outputs.items():
                    for bad in _DEFORMED:
                        self.assertNotIn(bad, out, (where, bad))

    def test_curve_notes_are_rebuilt_after_collecting_in_another_language(self):
        from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer
        from VelantisWind.noise_core.sources import collector

        project = QgsProject()
        layer = QgsVectorLayer("Point?crs=EPSG:32630", "Parque (CSV)", "memory")
        project.setCrs(layer.crs())
        project.addMapLayer(layer)
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POINT(500000 4400000)"))
        self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
        filename = "Parque · curva genérica desde capa {Norte}.csv"
        error_text = "No se pudo abrir " + filename
        for prepared, active in (("en", "de"), ("fr", "es"), ("es", "en"), ("de", "fr")):
            for worst, error in ((False, None), (True, None), (False, ValueError(error_text))):
                with self.subTest(prepared=prepared, active=active, worst=worst, error=error):
                    i18n.set_language(prepared)
                    cfg = {layer.id(): {"acoustic_mode": "curve", "curve_path": "/synthetic/" + filename,
                                        "eval_ws_m_s": 8.0, "use_curve_worst_case": worst}}
                    with mock.patch.object(collector, "load_acoustic_curve_csv",
                                           return_value=([8, 9], [104, 105]), side_effect=error), \
                            mock.patch.object(collector, "evaluate_acoustic_curve", return_value=104.0):
                        sources, diag = collector._collect_sources(project, cfg, None)
                    self.assertEqual(len(sources), 1)
                    old_note = diag[layer.id()]["curve_note"]
                    source = diag[layer.id()]["curve_note_source"]
                    result = _result()
                    result["model_diag"] = diag
                    i18n.set_language(active)
                    expected = i18n.tr_text(source["template"]).format(**source["values"])
                    self.assertNotEqual(expected, old_note)
                    self.assertIn(filename, expected)
                    if error:
                        self.assertIn(error_text, expected)
                    dlg = nrd.NoiseResultsDialog(None, result)
                    self.addCleanup(dlg.deleteLater)
                    self.assertEqual(dlg.tbl_models.item(0, 5).text(), expected)
                    self.assertEqual(dlg._xlsx_table_rows(dlg.tbl_models)[1][5], expected)
                    _, sheets = _read_xlsx(self._export(dlg, "_export_package_xlsx", "curve.xlsx")[0])
                    self.assertEqual(sheets[1][1][5], expected)
                    self.assertEqual(diag[layer.id()]["curve_note"], old_note)

    def test_a_closed_dialog_keeps_its_names_when_the_language_changes(self):
        # The dialog is created on the Noise page and stays its child after exec_(); the hub translates the page again
        # on every language change.
        page = QtWidgets.QWidget()
        self.addCleanup(page.deleteLater)
        i18n.set_language("es")
        dlg = nrd.NoiseResultsDialog(page, _result())
        cells = [dlg.tbl_top.item(0, c).text() for c in range(dlg.tbl_top.columnCount())]
        report = dlg.page_summary.toPlainText()
        for lang in ("en", "fr", "de", "es"):
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                i18n.apply_i18n(page)
                self.assertEqual([dlg.tbl_top.item(0, c).text() for c in range(dlg.tbl_top.columnCount())], cells)
                self.assertEqual(dlg.page_summary.toPlainText(), report)

    def test_dialog_texts_in_each_language(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                dlg = self._dialog(lang)
                title, label, tab, tip, exceed_tip = _TEXTS[lang]
                self.assertEqual(dlg.windowTitle(), title)
                self.assertIn(label, [w.text() for w in dlg.findChildren(QtWidgets.QLabel)])
                self.assertEqual(dlg.tabs.tabText(2), tab)
                self.assertEqual(dlg.tbl_top.toolTip(), tip)
                self.assertEqual(dlg.btn_export_exceed.toolTip(), exceed_tip)
                self.assertEqual([dlg.tbl_models.horizontalHeaderItem(c).text() for c in range(6)], _MODEL_HEADERS[lang])
                self.assertEqual([dlg.tbl_layers.item(r, 0).text() for r in range(dlg.tbl_layers.rowCount())],
                                 _LAYER_NAMES)
                for (method, name), (dlg_title, file_name, file_filter) in zip(
                        (("_export_summary", "a.html"), ("_export_receivers_csv", "a.csv"),
                         ("_export_exceedances_csv", "b.csv"), ("_export_package_xlsx", "a.xlsx")), _SAVE_DIALOGS[lang]):
                    args = self._export(dlg, method, name)[1]
                    self.assertEqual((args[1], os.path.basename(args[2]), args[3]), (dlg_title, file_name, file_filter))
                dlg._res["receiver_rows"] = [dict(r, exceeds=0) for r in dlg._res["receiver_rows"]]
                with mock.patch.object(nrd.QtWidgets, "QMessageBox") as box:
                    dlg._export_exceedances_csv()
                self.assertEqual(box.information.call_args[0][1:], _NO_EXCEEDANCES[lang])

    def test_report_follows_the_glossary(self):
        for lang in _LANGS:
            with self.subTest(lang=lang):
                report = self._dialog(lang).page_summary.toPlainText()
                present, absent = _REPORT_TERMS[lang]
                for text in present:
                    self.assertIn(text, report)
                for text in absent:
                    self.assertNotIn(text, report)
                if lang == "fr":
                    self.assertIsNone(re.search(r"\w:\s", report.replace("Plantilla: ", "")))

    def test_labels_of_the_spectrum_source_are_translated_and_the_file_names_kept(self):
        source = "Biblioteca: Plantilla: Norte.csv · normalizado a LwA del grupo · LwA(A) del espectro = 104.0 dB(A)"
        expected = {
            "es": source,
            "en": "Library: Plantilla: Norte.csv · normalized to the group LwA · spectrum LwA(A) = 104.0 dB(A)",
            "fr": "Bibliothèque : Plantilla: Norte.csv · normalisé au LwA du groupe · LwA(A) du spectre = 104.0 dB(A)",
            "de": "Bibliothek: Plantilla: Norte.csv · auf den Gruppen-LwA normiert · LwA(A) des Spektrums = 104.0 dB(A)",
        }
        for lang in _LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(nrd._noise_clean_value(source, lang), expected[lang])
                self.assertTrue(nrd._noise_clean_value("CSV: sin nombre desde capa.csv", lang).endswith(
                    ": sin nombre desde capa.csv"))
                self.assertEqual(nrd._noise_receiver_type("Plantilla: Norte", lang), "Plantilla: Norte")

    def test_file_names_with_label_fragments_and_middle_dots_are_opaque(self):
        prefixes = {
            "CSV: ": ("CSV: ", "CSV: ", "CSV : ", "CSV: "),
            "Biblioteca: ": ("Biblioteca: ", "Library: ", "Bibliothèque : ", "Bibliothek: "),
        }
        suffixes = ("normalizado a LwA del grupo", "normalized to the group LwA",
                    "normalisé au LwA du groupe", "auf den Gruppen-LwA normiert")
        for index, lang in enumerate(_LANGS):
            for prefix, translations in prefixes.items():
                for filename in ("archivo · Plantilla: Norte.csv",
                                 "archivo · normalizado a LwA del grupo · Plantilla: Norte.csv"):
                    for with_suffix in (False, True):
                        with self.subTest(lang=lang, prefix=prefix, filename=filename, suffix=with_suffix):
                            source = prefix + filename
                            expected = translations[index] + filename
                            if with_suffix:
                                source += " · " + suffixes[0]
                                expected += " · " + suffixes[index]
                            self.assertEqual(nrd._noise_clean_value(source, lang), expected)

    def test_xlsx_writer_error_follows_the_language(self):
        expected = {
            "es": "La carpeta de destino no existe: ", "en": "The destination folder does not exist: ",
            "fr": "Le dossier de destination n’existe pas : ", "de": "Der Zielordner existiert nicht: ",
        }
        missing = os.path.join(self.tmp.name, "no", "modelo")
        for lang in _LANGS:
            with self.subTest(lang=lang):
                i18n.set_language(lang)
                with self.assertRaises(OSError) as ctx:
                    write_xlsx_workbook(os.path.join(missing, "a.xlsx"), [{"title": "a", "rows": [["b"]]}])
                self.assertEqual(str(ctx.exception), expected[lang] + missing)


if __name__ == "__main__":
    unittest.main()
