# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List
import csv
import os
import re

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtGui import QGuiApplication
from .i18n import apply_i18n, current_language, install_runtime_i18n_patches, translate_html, tr_text as _tr
from .ui_core.responsive import fit_to_screen, configure_table
from qgis.core import QgsFeatureRequest, QgsVectorLayer

try:
    from .noise_core.noise_common import OCTAVE_BANDS, A_WEIGHTING
except Exception:
    from noise_core.noise_common import OCTAVE_BANDS, A_WEIGHTING

try:
    from openpyxl import Workbook
except Exception:
    Workbook = None


# Client-facing receiver table/export schema.  Detailed MDT/path diagnostics are
# still kept internally in the result payload, but the default dialog and exports
# should stay readable for consultancy workflows.
CONSULTANCY_RECEIVER_COLUMNS = [
    ("rec_id", "ID récepteur"),
    ("rec_type", "type"),
    ("noise_dba", "niveau total dB(A)"),
    ("limit_dba", "limite dB(A)"),
    ("margin_db", "marge par rapport à la limite dB"),
    ("state", "état"),
    ("exceeds", "dépasse la limite"),
    ("n_src", "nb éoliennes"),
    ("near_m", "dist. éolienne proche (m)"),
    ("dom_model", "modèle dominant"),
    ("dom_group", "groupe source dom."),
    ("dom_park", "parc dom."),
    ("src_lwa", "LwA source dom. dB(A)"),
    ("adiv_db", "Adiv dB"),
    ("aatm_db", "Aatm dB"),
    ("aground_db", "Agr/Aground dB"),
    ("abar_max_db", "Abar max. dB"),
    ("ground_g", "G sol"),
    ("ground_md", "mode sol"),
    ("rec_h_m", "h récepteur m"),
    ("rec_z_m", "z terrain récepteur m"),
    ("rec_ac_z_m", "z acoustique récepteur m"),
    ("dom_src_lyr", "couche source dominante"),
]

CONSULTANCY_RECEIVER_KEYS = [key for key, _label in CONSULTANCY_RECEIVER_COLUMNS]
CONSULTANCY_RECEIVER_HEADERS = [label for _key, label in CONSULTANCY_RECEIVER_COLUMNS]



def _cleanup_german_noise_html(html: str) -> str:
    """Post-process German HTML generated from the French report template.

    The runtime translator is intentionally conservative and non-cascading to
    avoid corrupting short UI labels.  The noise report is long HTML assembled
    from older French text blocks, so a final DE-only cleanup makes the visible
    report much less mixed without affecting other languages.
    """
    repl = [

        ("Récepteur critique (niveau sonore le plus élevé)", "Kritischer Rezeptor (höchster Schallpegel)"),
        ("ID récepteur", "Rezeptor-ID"),
        ("Niveau total", "Gesamtpegel"),
        ("Limite applicable", "Anwendbarer Grenzwert"),
        ("Marge", "Abstand zum Grenzwert"),
        ("Modèle dominant", "Dominantes Modell"),
        ("Groupe source", "Quellgruppe"),
        ("Éoliennes contributrices dans le rayon", "Beitragende Windturbinen im Radius"),
        ("Décomposition des atténuations", "Aufschlüsselung der Dämpfungen"),
        ("Les valeurs affichées ci-dessous sont les amplitudes d’atténuation utilisées par le modèle. Dans l’équation principale, ces termes sont soustraits au niveau de source.", "Die unten angezeigten Werte sind die vom Modell verwendeten Dämpfungsbeträge. In der Hauptgleichung werden diese Terme vom Quellpegel abgezogen."),
        ("Puissance acoustique de l’éolienne", "Schallleistung der Windturbine"),
        ("Dispersion géométrique", "Geometrische Ausbreitungsdämpfung"),
        ("Absorption dans l’air", "Luftabsorption"),
        ("Effet du sol", "Bodeneffekt"),
        ("Diffraction topographique", "Topografische Abschirmung"),
        ("Abar maximal des contributeurs", "Maximaler Abar der Beitragenden"),
        ("Abar maximal parmi toutes les éoliennes qui contribuent au récepteur", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Abar pondéré par énergie", "Energiegewichteter Abar"),
        ("Moyenne pondérée par la contribution acoustique de chaque éolienne", "Mittelwert, gewichtet nach dem akustischen Beitrag jeder Windturbine"),
        ("Trajets écrantés", "Abgeschirmte Pfade"),
        ("Nombre d’éoliennes contributrices avec Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Note : le niveau résultant inclut la sommation énergétique multi-source et multi-bande ; ce n’est pas une soustraction directe depuis une seule éolienne.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; er ist keine direkte Subtraktion von einer einzelnen Windturbine."),
        ("Note : le niveau résultant inclut", "Hinweis: Der Ergebnispegel enthält"),
        ("sommation énergétique multi-source et multi-bande", "energetische Summierung über mehrere Quellen und Frequenzbänder"),
        ("ce n’est pas une soustraction directe depuis une seule éolienne", "dies ist keine direkte Subtraktion von einer einzelnen Windturbine"),
        ("Bande dominante", "Dominantes Band"),
        ("Origine du spectre", "Spektrumquelle"),
        ("Glossaire des symboles", "Symbolglossar"),
        ("Définition compacte des symboles qui apparaissent dans les formules et tableaux de ce rapport.", "Kompakte Definition der Symbole, die in Formeln und Tabellen dieses Berichts erscheinen."),
        ("Symbole", "Symbol"),
        ("Signification", "Bedeutung"),
        ("Portée de ce rapport — à lire avant d’utiliser les résultats", "Geltungsbereich dieses Berichts — vor Nutzung der Ergebnisse lesen"),
        ("Ce que c’est", "Was es ist"),
        ("Ce que ce n’est pas", "Was es nicht ist"),
        ("Simplifications appliquées dans ce mode", "In diesem Modus angewendete Vereinfachungen"),
        ("Recommandation", "Empfehlung"),
        ("Statistiques des atténuations", "Dämpfungsstatistik"),
        ("Statistiques des Dämpfungen", "Dämpfungsstatistik"),
        ("Estadísticos de Dämpfungen", "Dämpfungsstatistik"),
        ("Estadísticos de", "Statistik der"),
        ("Dämpfungen (Abgedeckte Rezeptoren)", "Dämpfungen (abgedeckte Rezeptoren)"),
        ("Abgedeckte Rezeptoren", "abgedeckte Rezeptoren"),
        ("Abar Maximum parmi les Turbinen contributrices", "Maximaler Abar-Wert unter den beitragenden Windturbinen"),
        ("Abar Maximum", "Maximaler Abar"),
        ("Abar moyen", "Mittlerer Abar"),
        ("au Rezeptor", "zum Rezeptor"),
        ("bandes", "Frequenzbänder"),
        ("bandes.", "Frequenzbänder."),
        ("Turbinen contributrices", "beitragende Windturbinen"),
        ("Turbinen contribuyentes", "beitragende Windturbinen"),
        ("con Turbinen", "mit Windturbinen"),
        ("con Abar", "mit Abar"),
        ("Numero de", "Anzahl"),
        ("Número de", "Anzahl"),
        ("numéro de", "Anzahl"),
        ("d’éoliennes", "Windturbinen"),
        ("de Windturbinen", "Windturbinen"),
        ("eólica", "Windenergie"),
        ("Turbine", "Windturbine"),
        ("Turbinen", "Windturbinen"),
        ("Rezeptor ne", "Rezeptor bedeutet nicht"),
        (" ne signifie pas que ", " bedeutet nicht, dass "),
        (" désactivé", " deaktiviert"),
        ("désactivé", "deaktiviert"),
        ("pour le dominanten Pfad", "für den dominanten Pfad"),
        ("für den dominanten Pfad konnte kein gültiges DGM-Profil extrahiert werden", "für den dominanten Pfad kein gültiges DGM-Profil extrahiert werden konnte"),
        ("Der Wert Abar dominanter Pfad", "Der Abar-Wert des dominanten Pfads"),
        ("la Wert", "Der Wert"),
        ("est obtenu par", "wird ermittelt durch"),
        ("par sommation énergétique", "durch energetische Summierung"),
        ("de toutes", "aller"),
        ("und Frequenzbänder.", "und Frequenzbänder."),
        ("Im ISO-orientierten Rechenkern, das DGM ändert nicht", "Im ISO-orientierten Rechenkern ändert das DGM nicht"),
        ("Im schnellen Rechenkern, das DGM", "Im schnellen Rechenkern das DGM"),
        ("In dieser Berechnung,", "In dieser Berechnung"),
        ("l’atmosphärische Absorption", "die atmosphärische Absorption"),
        ("l’Bodeneffekt", "der Bodeneffekt"),
        ("l’Landnutzung", "die Landnutzung"),
        ("l’Windturbine", "die Windturbine"),
        ("l’Emission", "die Emission"),
        ("l’équation", "die Gleichung"),
        ("l’itération", "die Iteration"),
        ("d’Dämpfung", "Dämpfung"),
        ("d’topografische", "topografische"),
        ("d’Landnutzung", "Landnutzung"),
        ("mit ein <b>einziger", "mit einem <b>einzigen"),
        ("ein <b>einziger manueller G-Wert</b>", "einem <b>einzigen manuellen G-Wert</b>"),
        ("ein <b>einziger G-Wert je Pfad</b>", "ein <b>einziger G-Wert je Pfad</b>"),
        ("with ein", "mit einem"),
        ("with eine", "mit einer"),
        ("with un", "mit einem"),
        ("with une", "mit einer"),
        ("with ", "mit "),
        ("Adiv représente la geometrische Divergenz", "Adiv steht für die geometrische Divergenz"),
        ("Aatm wird berechnet je Band", "Aatm wird je Band berechnet"),
        ("und dépend von", "und hängt ab von"),
        ("dépend von", "hängt ab von"),
        ("und des Drucks", "und vom Druck"),
        ("mit einer formulation vereinfacht", "mit einer vereinfachten Formulierung"),
        ("Agr ist appliqué comme terme", "Agr wird als Term angewendet"),
        ("terme de Boden/Gelände", "Boden-/Geländeterm"),
        ("topografische Abschirmung de base", "grundlegende topografische Abschirmung"),
        ("lorsqu’un MDT ist disponible", "wenn ein DGM verfügbar ist"),
        ("Table synthétique pour la Beratung", "Übersichtstabelle für die Beratung"),
        ("résultats acoustiques par Rezeptor", "akustische Ergebnisse je Rezeptor"),
        ("source dominante", "dominante Quelle"),
        ("atténuations principales", "wichtigste Dämpfungen"),
        ("Les diagnostics internes MDT par paire", "Die internen DGM-Paardiagnosen"),
        ("sind conservés en mémoire", "werden im Speicher gehalten"),
        ("mais ne sind pas affichés por defecto", "werden aber standardmäßig nicht angezeigt"),
        ("n’introduit pas de terme explicite", "führt keinen expliziten Term ein"),
        ("Même si une Layer de relief existe dans le projet", "Auch wenn im Projekt ein Gelände-Layer vorhanden ist"),
        ("ce mode ne calcule pas", "berechnet dieser Modus nicht"),
        ("n’extrait pas de ligne de visée", "extrahiert keine Sichtlinie"),
        ("n’applique pas de diffraction", "wendet keine Beugung an"),
        ("la Physik se base donc uniquement sur", "die Physik basiert daher nur auf"),
        ("la correction empirique de Gelände", "der empirischen Geländekorrektur"),
        ("Les Werte affichées ci-dessous", "Die unten angezeigten Werte"),
        ("sind les Beträge", "sind die Beträge"),
        ("verwendet par le Modell", "die vom Modell verwendet werden"),
        ("ces termes sind soustraits", "diese Terme werden abgezogen"),
        ("au niveau de source", "vom Quellpegel"),
        ("Entrées tatsächlich verwendet dans ce Berechnung", "In dieser Berechnung tatsächlich verwendete Eingaben"),
        ("Ce moteur travaille en", "Dieser Rechenkern arbeitet mit"),
        ("Les bandes ne sind pas un résultat", "Die Bänder sind kein Ergebnis"),
        ("mais la <b>grille fréquentielle de la Methode</b>", "sondern das <b>Frequenzraster der Methode</b>"),
        ("le Berechnung a besoin", "die Berechnung benötigt"),
        ("d’une <b>entrée acoustique je Band</b>", "einen <b>akustischen Eingang je Band</b>"),
        ("Cette entrée kann provenir", "Dieser Eingang kann stammen"),
        ("d’un Spektrum mesuré/importé", "aus einem gemessenen/importierten Spektrum"),
        ("ou d’un gabarit/fallback ajusté", "oder aus einer angepassten Vorlage/einem Fallback"),
        ("au niveau global opérationnel", "an den globalen Betriebspegel"),
        ("Der Term de Boden se décompose en", "Der Bodenterm wird aufgeteilt in"),
        ("trois paramètres de Boden indépendants", "drei unabhängige Bodenparameter"),
        ("werden nicht verwendet ;", "werden nicht verwendet;"),
        ("ist verwendet", "wird verwendet"),
        ("Mathématiquement, le plugin applique", "Mathematisch wendet das Plugin an"),
        ("Lecture correcte d’Abar", "Korrekte Interpretation von Abar"),
        ("correspond uniquement à", "bezieht sich nur auf"),
        ("qui contribue le plus", "die am stärksten beiträgt"),
        ("à sa bande dominante", "und auf ihr dominantes Band"),
        ("niveen total", "Gesamtpegel"),
        ("est obtenu par sommation énergétique", "wird durch energetische Summierung ermittelt"),
        ("Limites und recommandations", "Grenzen und Empfehlungen"),
        ("Engine rapide", "Schneller Rechenkern"),
        ("Engine ISO-orientiert", "ISO-orientierter Rechenkern"),
        ("Adapté au Screening préliminaire", "Geeignet für vorläufiges Screening"),
        ("aux cartes agiles", "und schnelle Karten"),
        ("Adapté aux études techniques préliminaires", "Geeignet für vorläufige technische Studien"),
        ("aux comparaisons", "Vergleiche"),
        ("à la conception", "für die Auslegung"),
        ("Simplifications connues", "Bekannte Vereinfachungen"),
        ("Modèles multiples", "Mehrere Modelle"),
        ("pris en charge", "unterstützt"),
        ("n’est pas activé", "ist nicht aktiviert"),
        ("peut être coûteux", "kann rechenintensiv sein"),
        ("sur de grandes cartes", "auf großen Karten"),
        ("Pour les études réglementaires critiques", "Für kritische regulatorische Studien"),
        ("valider avec des mesures", "mit Messungen validieren"),
        ("logiciel commercial certifié", "zertifizierte kommerzielle Software"),
        ("calculée", "berechnet"),
        ("calculé", "berechnet"),
        ("appliqué", "angewendet"),
        ("appliquée", "angewendet"),
        ("simplificada", "vereinfacht"),
        ("simplifié", "vereinfacht"),
        ("simplifiée", "vereinfacht"),
        ("terme de", "Term für"),
        ("de sol", "des Bodens"),
        ("de terrain", "des Geländes"),
        (" pour ", " für "),
        ("Acoustic sources", "Akustische Quellen"),
        ("Noise · Sources", "Schall · Quellen"),
        ("Sources", "Quellen"),
        ("Receptores", "Rezeptoren"),
        ("Rezeptor cubiertos", "abgedeckte Rezeptoren"),
        ("Rezeptoren cubiertos", "abgedeckte Rezeptoren"),
        ("Trayectorias apantalladas", "Abgeschirmte Pfade"),
        ("Número de Turbinen contribuyentes con Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Número de Turbinen contribuyentes con Abar > 0 dB", "Anzahl beitragender Windturbinen mit Abar > 0 dB"),
        ("NIVEL RESULTANTE", "ERGEBNISPEGEL"),
        ("NIVEAU RÉSULTANT", "ERGEBNISPEGEL"),
        ("Nivel resultante", "Ergebnispegel"),
        ("Banda dominante", "Dominantes Band"),
        ("Bande dominante", "Dominantes Band"),
        ("Origen Spektrum", "Spektrumquelle"),
        ("Origine du spectre", "Spektrumquelle"),
        ("Estadísticos de Dämpfungen (Abgedeckte Rezeptoren)", "Dämpfungsstatistik (abgedeckte Rezeptoren)"),
        ("Estadísticos de Dämpfungen", "Dämpfungsstatistik"),
        ("Statistiques des Dämpfungen", "Dämpfungsstatistik"),
        ("DGM-Lesart :", "DGM-Hinweis:"),
        ("au kritischer Rezeptor", "am kritischen Rezeptor"),
        ("ne signifie pas que das DGM ist désactivé", "bedeutet nicht, dass das DGM deaktiviert ist"),
        ("es bedeutet, dass für den dominanten Pfad konnte kein gültiges DGM-Profil extrahiert werden", "es bedeutet, dass für den dominanten Pfad kein gültiges DGM-Profil extrahiert werden konnte"),
        ("Korrekte Interpretation von Abar :", "Korrekte Interpretation von Abar:"),
        ("la Wert Abar dominanter Pfad", "Der Wert Abar des dominanten Pfads"),
        ("bezieht sich nur auf die Windturbine die am stärksten beiträgt", "bezieht sich nur auf die Windturbine, die am stärksten zum Rezeptor beiträgt"),
        ("und auf ihr dominantes Band", "und auf ihr dominantes Band"),
        ("Le Gesamtpegel des Rezeptors", "Der Gesamtpegel des Rezeptors"),
        ("de toutes die Windturbinen und bandes", "aller Windturbinen und Frequenzbänder"),
        ("toutes die Windturbinen und bandes", "aller Windturbinen und Frequenzbänder"),
        ("Abar Maximal entre les Turbinen contributrices", "Maximaler Abar-Wert unter den beitragenden Windturbinen"),
        ("Abar maximal parmi les Turbinen contributrices", "Maximaler Abar-Wert unter den beitragenden Windturbinen"),
        ("Abar moyen", "Mittlerer Abar"),
        ("nach akustischem Beitrag gewichtetes Abar", "Nach akustischem Beitrag gewichteter Abar"),
        ("trajets écrantés", "abgeschirmte Pfade"),
        ("Höhen des dominanten Pfads :", "Höhen des dominanten Pfads:"),
        ("Gelände Windturbine", "Gelände Turbine"),
        ("hub=", "Nabenhöhe="),
        ("akustische Turbinenhöhe", "akustische Turbinenhöhe"),
        ("Gelände Rezeptor", "Gelände Rezeptor"),
        ("h Rezeptor", "Rezeptorhöhe"),
        ("akustische Rezeptorhöhe", "akustische Rezeptorhöhe"),
        ("Nota: el nivel resultante incluye la suma energética multi-Quelle y multi-banda; no es una resta directa de una única Turbine.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; er ist keine direkte Subtraktion von einer einzelnen Turbine."),
        ("Nota: el nivel resultante incluye", "Hinweis: Der Ergebnispegel enthält"),
        ("la suma energética multi-Quelle y multi-banda", "die energetische Summierung über mehrere Quellen und Frequenzbänder"),
        ("no es una resta directa de una única Turbine", "er ist keine direkte Subtraktion von einer einzelnen Turbine"),
        ("Aatm (atmospheric)", "Aatm (Atmosphäre)"),
        ("Agr (sol)", "Agr (Boden)"),
        ("Abar trayectoria dominante", "Abar dominanter Pfad"),
        ("Maximum contributors Abar", "Maximaler Abar-Wert der beitragenden Turbinen"),
        ("Energy-weighted Abar", "Energiegewichteter Abar"),
        ("Average weighted by the acoustic contribution of each turbine", "Mittelwert, gewichtet nach dem akustischen Beitrag jeder Turbine"),
        ("Number de Windturbinen contributrices avec Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Number de Windturbinen contributrices avec Abar > 0 dB", "Anzahl beitragender Windturbinen mit Abar > 0 dB"),
        ("Description", "Beschreibung"),
        ("Valeur [dB]", "Wert [dB]"),
        ("Terme", "Term"),
        ("Moyenne [dB]", "Mittelwert [dB]"),
        ("Maximum [dB]", "Maximum [dB]"),
        ("Promedio ponderado por la contribución acústica de cada turbina", "Mittelwert, gewichtet nach dem akustischen Beitrag jeder Turbine"),
        ("Número de turbinas contribuyentes", "Anzahl beitragender Windturbinen"),
        ("contributrices", "beitragend"),
        ("contribuyentes", "beitragend"),
        (" avec ", " mit "),
    ]

    repl.extend([
        # Critical receptor table / visible summary leftovers
        ("Dämpfung due zur Bodeneffekt", "Dämpfung durch Bodeneffekt"),
        ("Dämpfung due zur Bodenefekt", "Dämpfung durch Bodeneffekt"),
        ("Dämpfung due zur Bodeneffekt", "Dämpfung durch Bodeneffekt"),
        ("Máximo Abar zwischen todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Máximo Abar entre todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Anzahl beitragenWindturbinen mit Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Anzahl beitragenWindturbinen mit Abar > 0 dB", "Anzahl beitragender Windturbinen mit Abar > 0 dB"),
        ("Anzahl beitragenWindturbinen", "Anzahl beitragender Windturbinen"),
        ("Número de Turbinen contribuyentes con Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Número de Turbinen contribuyentes con Abar > 0 dB", "Anzahl beitragender Windturbinen mit Abar > 0 dB"),
        ("Nota: el nivel resultante incluye la suma energética multi-Quelle y multi-banda; no es una resta directa de una única Turbine.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; er ist keine direkte Subtraktion von einer einzelnen Windturbine."),
        ("Nota: el nivel resultante incluye la suma energética multi-Quelle y multi-banda; no es una resta directa de una única Windturbine.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; er ist keine direkte Subtraktion von einer einzelnen Windturbine."),
        ("Banda dominante:", "Dominantes Band:"),
        ("Origen Spectrum:", "Spektrumquelle:"),
        ("Origen Spektrum:", "Spektrumquelle:"),
        ("Die unten angezeigten Werte sind die Beträge Dämpfung die vom Modell verwendet werden. In die Gleichung principale, diese Term werden abgezogen au niveau der Quelle.", "Die unten angezeigten Werte sind die vom Modell verwendeten Dämpfungsbeträge. In der Hauptgleichung werden diese Terme vom Quellpegel abgezogen."),
        ("Beträge Dämpfung", "Dämpfungsbeträge"),
        ("In die Gleichung principale", "In der Hauptgleichung"),
        ("diese Term werden abgezogen au niveau der Quelle", "diese Terme werden vom Quellpegel abgezogen"),
        ("Dämpfung die vom Modell verwendet werden", "Dämpfungsbeträge, die vom Modell verwendet werden"),

        # Topographic-screening section leftovers
        ("Écran topographique mit MDT", "Topografische Abschirmung mit DGM"),
        ("Écran topographique avec MDT", "Topografische Abschirmung mit DGM"),
        ("Das DGM ändert nicht die Emission der Windturbine noch die atmosphärische Absorption. Seine Funktion ist es, zu beschreiben la géométrie real des Pfads und d'alimenter der Term Abar,b.", "Das DGM ändert weder die Schallemission der Windturbine noch die atmosphärische Absorption. Seine Funktion besteht darin, die reale Geometrie des Quelle-Rezeptor-Pfads zu beschreiben und den topografischen Abschirmungsterm Abar,b zu speisen."),
        ("Das DGM ändert nicht die Emission der Windturbine", "Das DGM ändert die Schallemission der Windturbine nicht"),
        ("noch die atmosphärische Absorption", "und nicht die atmosphärische Absorption"),
        ("Seine Funktion ist es, zu beschreiben la géométrie real des Pfads und d'alimenter der Term Abar,b", "Seine Funktion besteht darin, die reale Geometrie des Quelle-Rezeptor-Pfads zu beschreiben und den Term Abar,b zu speisen"),
        ("la géométrie real des Pfads", "die reale Geometrie des Pfads"),
        ("d'alimenter der Term", "den Term zu speisen"),
        ("Perfil del terreno", "Geländeprofil"),
        ("le profil Quelle–Rezeptor ist extrait du MDT mit einem adaptive Abtastung", "das Quelle-Rezeptor-Profil wird aus dem DGM mit adaptiver Abtastung extrahiert"),
        ("le profil Quelle-Rezeptor ist extrait du MDT mit einem adaptive Abtastung", "das Quelle-Rezeptor-Profil wird aus dem DGM mit adaptiver Abtastung extrahiert"),
        ("Línea de visión", "Sichtlinie"),
        ("la droite zwischen la Höhe efectiva der Quelle und la Rezeptorhöhe ist construite", "die Gerade zwischen der effektiven Quellhöhe und der Rezeptorhöhe wird konstruiert"),
        ("Si le Gelände bleibt toujours en dessous, alors", "Wenn das Gelände stets darunter bleibt, gilt"),
        ("Obstáculo dominante", "Dominantes Hindernis"),
        ("si une colline ou une crête dépasse", "wenn ein Hügel oder Grat die Sichtlinie überschreitet"),
        ("la Höhe au-dessus de la ligne de visée wird berechnet", "wird die Höhe über der Sichtlinie berechnet"),
        ("le relief coupe la vision directe", "das Gelände schneidet die direkte Sichtlinie"),
        ("eine Dämpfung supplémentaire par diffraction kann apparaître", "eine zusätzliche Dämpfung durch Beugung kann auftreten"),
        ("Géométrie real de l'obstacle", "Reale Geometrie des Hindernisses"),
        ("le plugin utilise la position réelle de l'obstacle dominant", "das Plugin verwendet die reale Position des dominanten Hindernisses"),
        ("et calcule", "und berechnet"),
        ("Activation conservative", "Konservative Aktivierung"),
        ("Abar ist nicht aktiviert für de petites irrégularités du MDT", "Abar wird nicht für kleine DGM-Unregelmäßigkeiten aktiviert"),
        ("un seuil minimal lié à la résolution du raster ist exigé", "es wird ein Mindestschwellwert in Bezug auf die Rasterauflösung verlangt"),
        ("Diffraction de tipo Fresnel", "Fresnel-artige Beugung"),
        ("Diffraction de type Fresnel", "Fresnel-artige Beugung"),
        ("mit cette géométrie", "mit dieser Geometrie"),
        ("une différence de chemins und un nombre de Fresnel sind estimés", "werden eine Weglängendifferenz und eine Fresnel-Zahl geschätzt"),
        ("Ce nombre est ensuite transformé en une Dämpfung", "Diese Zahl wird anschließend in eine Dämpfung umgewandelt"),
        ("dépendante de la fréquence au moyen de l’approximation actuelle du plugin", "die mit der aktuellen Plugin-Näherung frequenzabhängig ist"),
        ("En l’implémentation actuelle", "In der aktuellen Implementierung"),
        ("Abar ist également limité à des Werte raisonnables", "Abar wird außerdem auf plausible Werte begrenzt"),
        ("plafonnement supérieur", "obere Begrenzung"),
        ("afin d’éviter des suratténuations parasites", "um unerwünschte Überdämpfungen zu vermeiden"),
        ("En l’absence de MDT ou d’obstacle pertinent", "Ohne DGM oder relevantes Hindernis"),
        ("alors Abar,b = 0", "gilt Abar,b = 0"),
    ])


    repl.extend([
        ("Abar dominanter Pfad", "Abar des dominanten Pfads"),
        ("Maximaler Abar beitragend", "Maximaler Abar-Wert der Beitragenden"),
        ("Abar maximal contrib.", "Maximaler Abar-Wert der Beitragenden"),
        ("Maximaler Abar zwischen todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Máximo Abar zwischen todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Máximo Abar entre toutes les éoliennes qui contribuent au récepteur", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Mittelwert, gewichtet nach dem akustischen Beitrag jeder Turbine", "Mittelwert, gewichtet nach dem akustischen Beitrag jeder Windturbine"),
        ("Anzahl beitragenWindturbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl beitragendWindturbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl beitragen Turbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl de Windturbinen", "Anzahl der Windturbinen"),
        ("Número de Turbinen contribuyentes con Abar &gt; 0 dB", "Anzahl beitragender Windturbinen mit Abar &gt; 0 dB"),
        ("Número de Turbinen contribuyentes con Abar > 0 dB", "Anzahl beitragender Windturbinen mit Abar > 0 dB"),
        ("ERGENISPEGEL", "ERGEBNISPEGEL"),
        ("NIVEAU RÉSULTANT", "ERGEBNISPEGEL"),
        ("NIVEL RESULTANTE", "ERGEBNISPEGEL"),
        ("Nota : le niveau résultant inclut", "Hinweis: Der Ergebnispegel enthält"),
        ("Nota: el nivel resultante incluye", "Hinweis: Der Ergebnispegel enthält"),
        ("la suma energética multi-Quelle y multi-banda", "die energetische Summierung über mehrere Quellen und Frequenzbänder"),
        ("la sommation énergétique multi-Quelle y multi-banda", "die energetische Summierung über mehrere Quellen und Frequenzbänder"),
        ("multi-Quelle y multi-banda", "über mehrere Quellen und Frequenzbänder"),
        ("no es una resta directa de una única Windturbine", "dies ist keine direkte Subtraktion von einer einzelnen Windturbine"),
        ("no es una resta directa de una única Turbine", "dies ist keine direkte Subtraktion von einer einzelnen Windturbine"),
        ("ce n’est pas une resta directa de una única Windturbine", "dies ist keine direkte Subtraktion von einer einzelnen Windturbine"),
        ("Dominantes Band:", "Dominantes Frequenzband:"),
        ("Banda dominante", "Dominantes Frequenzband"),
        ("Origen Spectrum", "Spektrumquelle"),
        ("Origen Spektrum", "Spektrumquelle"),
        ("Spektrumquelle:", "Spektrumquelle:"),
        ("Estadísticos de Dämpfungen", "Dämpfungsstatistik"),
        ("Statistiques de Dämpfungen", "Dämpfungsstatistik"),
        ("(Abgedeckte Rezeptoren)", "(abgedeckte Rezeptoren)"),
        ("Dämpfung due zur Bodeneffekt", "Dämpfung durch Bodeneffekt"),
        ("Dämpfung due zur Bodenefekt", "Dämpfung durch Bodeneffekt"),
        ("Dämpfung due à l’effet de sol", "Dämpfung durch Bodeneffekt"),
        ("DEM auf dem dominanten Pfad", "DGM auf dem dominanten Pfad"),
        ("Abar trayectoria dominante", "Abar des dominanten Pfads"),
        ("Trayectorias apantalladas", "Abgeschirmte Pfade"),
        ("Trajectoires écrantées", "Abgeschirmte Pfade"),
        ("con Abar", "mit Abar"),
        ("contribuyen al receptor", "zum Rezeptor beitragen"),
        ("entre todas las turbinas", "unter allen Windturbinen"),
        ("zwischen todas las turbinas", "unter allen Windturbinen"),
        ("todas las turbinas", "allen Windturbinen"),
        ("éoliennes qui contribuent au récepteur", "Windturbinen, die zum Rezeptor beitragen"),
        # Topographic-screening report section
        ("Écran topographique mit MDT", "Topografische Abschirmung mit DGM"),
        ("Écran topographique avec MDT", "Topografische Abschirmung mit DGM"),
        ("Das DGM ändert nicht die Emission der Windturbine noch die atmosphärische Absorption", "Das DGM ändert weder die Schallemission der Windturbine noch die atmosphärische Absorption"),
        ("Das DGM ändert die Schallemission der Windturbine nicht und nicht die atmosphärische Absorption", "Das DGM ändert weder die Schallemission der Windturbine noch die atmosphärische Absorption"),
        ("Seine Funktion ist es, zu beschreiben la géométrie real des Pfads und d'alimenter der Term Abar,b", "Seine Funktion besteht darin, die reale Geometrie des Quelle-Rezeptor-Pfads zu beschreiben und den Term Abar,b zu speisen"),
        ("zu beschreiben la géométrie real des Pfads", "die reale Geometrie des Quelle-Rezeptor-Pfads zu beschreiben"),
        ("d'alimenter der Term Abar,b", "den Term Abar,b zu speisen"),
        ("Perfil del terreno", "Geländeprofil"),
        ("le profil Quelle–Rezeptor ist extrait du MDT mit einem adaptive Abtastung", "das Quelle-Rezeptor-Profil wird aus dem DGM mit adaptiver Abtastung extrahiert"),
        ("le profil Quelle-Rezeptor ist extrait du MDT mit einem adaptive Abtastung", "das Quelle-Rezeptor-Profil wird aus dem DGM mit adaptiver Abtastung extrahiert"),
        ("Línea de visión", "Sichtlinie"),
        ("la droite zwischen la Höhe efectiva der Quelle und la Rezeptorhöhe ist construite", "die Gerade zwischen der effektiven Quellhöhe und der Rezeptorhöhe wird konstruiert"),
        ("Si le Gelände bleibt toujours en dessous, alors", "Wenn das Gelände stets darunter bleibt, gilt"),
        ("Obstáculo dominante", "Dominantes Hindernis"),
        ("si une colline ou une crête dépasse", "wenn ein Hügel oder Grat die Sichtlinie überschreitet"),
        ("la Höhe au-dessus de la ligne de visée wird berechnet", "wird die Höhe über der Sichtlinie berechnet"),
        ("le relief coupe la vision directe", "das Gelände schneidet die direkte Sichtlinie"),
        ("eine Dämpfung supplémentaire par diffraction kann apparaître", "eine zusätzliche Dämpfung durch Beugung kann auftreten"),
        ("Géométrie real de l'obstacle", "Reale Geometrie des Hindernisses"),
        ("le plugin utilise la position réelle de l'obstacle dominant", "das Plugin verwendet die reale Position des dominanten Hindernisses"),
        ("et calcule", "und berechnet"),
        ("Activation conservative", "Konservative Aktivierung"),
        ("Abar ist nicht activé für de petites irrégularités du MDT", "Abar wird nicht für kleine DGM-Unregelmäßigkeiten aktiviert"),
        ("Abar ist nicht aktiviert für de petites irrégularités du MDT", "Abar wird nicht für kleine DGM-Unregelmäßigkeiten aktiviert"),
        ("un seuil minimal lié à la résolution du raster ist exigé", "es wird ein Mindestschwellwert in Bezug auf die Rasterauflösung verlangt"),
        ("Diffraction de tipo Fresnel", "Fresnel-artige Beugung"),
        ("Diffraction de type Fresnel", "Fresnel-artige Beugung"),
        ("mit cette géométrie", "mit dieser Geometrie"),
        ("une différence de chemins und un nombre de Fresnel sind estimés", "werden eine Weglängendifferenz und eine Fresnel-Zahl geschätzt"),
        ("Ce nombre est ensuite transformé en une Dämpfung", "Diese Zahl wird anschließend in eine Dämpfung umgewandelt"),
        ("dépendante de la fréquence au moyen de l’approximation actuelle du plugin", "die mit der aktuellen Plugin-Näherung frequenzabhängig ist"),
        ("En l’implémentation actuelle", "In der aktuellen Implementierung"),
        ("Abar ist également limité à des Werte raisonnables", "Abar wird außerdem auf plausible Werte begrenzt"),
        ("plafonnement supérieur", "obere Begrenzung"),
        ("afin d’éviter des suratténuations parasites", "um unerwünschte Überdämpfungen zu vermeiden"),
        ("En l’absence de MDT ou d’obstacle pertinent", "Ohne DGM oder relevantes Hindernis"),
        ("alors Abar,b = 0", "gilt Abar,b = 0"),
    ])

    repl.extend([
        ("Dämpfung due zur Bodeneffekt", "Dämpfung durch Bodeneffekt"),
        ("Dämpfung due zur Bodenwirkung", "Dämpfung durch Bodeneffekt"),
        ("Atenuación por MDT en la trayectoria dominante", "Dämpfung durch DGM auf dem dominanten Pfad"),
        ("Atenuación por apantallamiento topográfico", "Dämpfung durch topografische Abschirmung"),
        ("Trayectorias apantalladas", "Abgeschirmte Pfade"),
        ("Trajets écrantés", "Abgeschirmte Pfade"),
        ("NIVEL RESULTANTE", "ERGEBNISPEGEL"),
        ("NIVEAU RÉSULTANT", "ERGEBNISPEGEL"),
        ("Banda dominante", "Dominantes Frequenzband"),
        ("Origen Spectrum", "Spektrumquelle"),
        ("Origen Spektrum", "Spektrumquelle"),
        ("Nota: el nivel resultante incluye la suma energética multi-Quelle y multi-banda; no es una resta directa de una única Windturbine.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; dies ist keine direkte Subtraktion von einer einzelnen Windturbine."),
        ("Nota: el nivel resultante incluye la suma energética multi-fuente y multi-banda; no es una resta directa de una única turbina.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; dies ist keine direkte Subtraktion von einer einzelnen Windturbine."),
        ("Máximo Abar zwischen todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Maximo Abar zwischen todas las turbinas que contribuyen al receptor", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen"),
        ("Número de Turbinen contribuyentes con Abar", "Anzahl beitragender Windturbinen mit Abar"),
        ("Número de Windturbinen contribuyentes con Abar", "Anzahl beitragender Windturbinen mit Abar"),
        ("Anzahl beitragenWindturbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl beitragen Windturbinen", "Anzahl beitragender Windturbinen"),
        ("Estadísticos de Dämpfungen", "Dämpfungsstatistik"),
        ("Estadísticos de Dämpfungen (Abgedeckte Rezeptoren)", "Dämpfungsstatistik (abgedeckte Rezeptoren)"),
        ("Écran topographique mit MDT", "Topografische Abschirmung mit DGM"),
        ("mit MDT", "mit DGM"),
        ("del receptor", "des Rezeptors"),
        ("al receptor", "zum Rezeptor"),
        ("de una única", "einer einzelnen"),
        ("turbina", "Windturbine"),
    ])

    repl.extend([
        # Final grammar smoothing after broad fragment replacements
        ("Anzahl beitragende Windturbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl beitragend Windturbinen", "Anzahl beitragender Windturbinen"),
        ("Anzahl beitragende Turbinen", "Anzahl beitragender Turbinen"),
        ("Anzahl beitragend Turbinen", "Anzahl beitragender Turbinen"),
        ("Dämpfung Dämpfung", "Dämpfung"),
        ("Dämpfungsbeträge Dämpfung", "Dämpfungsbeträge"),
        ("in der Hauptgleichung, diese Terme", "In der Hauptgleichung werden diese Terme"),
        ("In der Hauptgleichung, diese Terme", "In der Hauptgleichung werden diese Terme"),
        ("diese Terme werden abgezogen vom Quellpegel", "diese Terme werden vom Quellpegel abgezogen"),
        ("diese Terme werden vom Quellpegel abgezogen vom Quellpegel", "diese Terme werden vom Quellpegel abgezogen"),
    ])

    for a, b in repl:
        html = html.replace(a, b)
    # Final conservative regex pass for common mixed-language connectors.
    html = re.sub(r"Número de\s+(?:Turbinen|Windturbinen)\s+contribuyentes\s+con\s+Abar\s*(&gt;|>)\s*0\s*dB", r"Anzahl beitragender Windturbinen mit Abar \1 0 dB", html)
    html = re.sub(r"Máximo Abar.*?(?:contribuyen al receptor|contribuent au récepteur)", "Maximaler Abar-Wert unter allen Windturbinen, die zum Rezeptor beitragen", html)
    html = re.sub(r"Nota\s*:\s*el nivel resultante.*?(?:Turbine|Windturbine)\.", "Hinweis: Der Ergebnispegel enthält die energetische Summierung über mehrere Quellen und Frequenzbänder; dies ist keine direkte Subtraktion von einer einzelnen Windturbine.", html)
    html = re.sub(r"Banda dominante\s*:", "Dominantes Frequenzband:", html)
    html = re.sub(r"Origen\s+(?:Spectrum|Spektrum)\s*:", "Spektrumquelle:", html)
    return html


class NoiseResultsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, result: Dict[str, object] | None = None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self._res = result or {}
        self.setWindowTitle("Schall · Technische Übersicht" if str(current_language()).lower().startswith("de") else _tr("Bruit · Résumé technique"))
        self.setModal(True)
        self._resize_to_screen()
        self._build_ui()
        apply_i18n(self)
        self._fill()

    def _resize_to_screen(self):
        fit_to_screen(self, preferred=(1100, 820), minimum=(680, 460), max_ratio=(0.92, 0.90))

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Schall · Berechnungsübersicht" if str(current_language()).lower().startswith("de") else "Bruit · Résumé du calcul")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#103b67;")
        header.addWidget(title, 1)
        header.addStretch(1)
        logo = QtWidgets.QLabel(self)
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "velantiswind_logo.png")
        if os.path.exists(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(180, 180, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                logo.setToolTip("Velantis Wind")
        header.addWidget(logo, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        root.addLayout(header)

        self.tabs = QtWidgets.QTabWidget(self)
        root.addWidget(self.tabs, 1)

        self.page_summary = QtWidgets.QTextBrowser(self)
        self.tabs.addTab(self.page_summary, "Résumé")

        self.tbl_models = QtWidgets.QTableWidget(0, 6, self)
        self.tbl_models.setHorizontalHeaderLabels(["Modèle WT", "Éoliennes", "LwA eff.", "HH", "D", "Notes"])
        configure_table(self.tbl_models, stretch_columns=(0, 5))
        self.tbl_models.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tbl_models, "Modèles")

        self.tbl_top = QtWidgets.QTableWidget(0, len(CONSULTANCY_RECEIVER_HEADERS), self)
        self.tbl_top.setHorizontalHeaderLabels(CONSULTANCY_RECEIVER_HEADERS)
        self.tbl_top.setToolTip(
            "Table synthétique pour la consultation : résultats acoustiques par récepteur, "
            "conformité, source dominante et atténuations principales. "
            "Les diagnostics internes MDT par paire sont conservés en mémoire, mais ne sont pas affichés par défaut."
        )
        configure_table(self.tbl_top, stretch_columns=(0, 1, 9, 10, 11, 22))
        self.tbl_top.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tbl_top, "principaux récepteurs")

        # Internal MDT screening table kept for compatibility with helper methods,
        # but no longer exposed as a default consultancy tab/export.
        self.tbl_mdt = QtWidgets.QTableWidget(0, 27, self)
        self.tbl_mdt.setHorizontalHeaderLabels([
            'ID récepteur', 'niveau total dB(A)', 'nb éoliennes', 'Abar max contrib. dB',
            'Abar pondéré dB', 'éoliennes écrantées', 'état MDT dom.', 'Abar dom. dB',
            'ID source Abar max', 'état Abar max', 'obs. Abar max m',
            'seuil Abar max m', 'd1 Abar max m', 'd2 Abar max m',
            'ID source obstacle max', 'état obstacle max', 'obs. obstacle max m',
            'seuil obstacle max m', 'd1 obstacle max m', 'd2 obstacle max m',
            'z terrain récepteur m', 'h récepteur m', 'z acoustique récepteur m',
            'z terrain éolienne dom. m', 'z acoustique éolienne dom. m',
            'z terrain éolienne Abar max m', 'z acoustique éolienne Abar max m'
        ])

        self.tbl_layers = QtWidgets.QTableWidget(0, 2, self)
        self.tbl_layers.setHorizontalHeaderLabels(["Couche", "État"])
        self.tbl_layers.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tbl_layers, "Couches créées")

        btns = QtWidgets.QHBoxLayout()
        self.btn_export_summary = QtWidgets.QPushButton("Exporter le rapport…")
        self.btn_export_summary.setToolTip("Enregistre le résumé technique en HTML ou TXT.")
        self.btn_export_summary.clicked.connect(self._export_summary)
        self.btn_export_receivers = QtWidgets.QPushButton("Exporter les récepteurs CSV…")
        self.btn_export_receivers.setToolTip("Enregistre un tableau propre avec une ligne par récepteur et les colonnes nécessaires pour la consultation.")
        self.btn_export_receivers.clicked.connect(self._export_receivers_csv)
        self.btn_export_exceed = QtWidgets.QPushButton("Exporter les dépassements CSV…")
        self.btn_export_exceed.setToolTip("Enregistre uniquement les récepteurs qui dépassent leur limite acoustique.")
        self.btn_export_exceed.clicked.connect(self._export_exceedances_csv)
        self.btn_export_xlsx = QtWidgets.QPushButton("Exporter le paquet XLSX…")
        self.btn_export_xlsx.setToolTip("Enregistre le résumé, les modèles, les récepteurs et les dépassements dans un seul classeur Excel.")
        self.btn_export_xlsx.clicked.connect(self._export_package_xlsx)
        btns.addWidget(self.btn_export_summary)
        btns.addWidget(self.btn_export_receivers)
        btns.addWidget(self.btn_export_exceed)
        btns.addWidget(self.btn_export_xlsx)
        btns.addStretch(1)
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.setMinimumHeight(34)
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)

        if str(current_language()).lower().startswith("de"):
            self.tabs.setTabText(0, "Übersicht")
            self.tabs.setTabText(1, "Modelle")
            self.tabs.setTabText(2, "Top-Rezeptoren")
            self.tabs.setTabText(3, "Erzeugte Layer")
            self.tbl_models.setHorizontalHeaderLabels(["WT-Modell", "Windturbinen", "LwA eff.", "NH", "D", "Notizen"])
            self.tbl_top.setHorizontalHeaderLabels([
                "Rezeptor-ID", "Typ", "Gesamtpegel dB(A)", "Grenzwert dB(A)",
                "Abstand zum Grenzwert dB", "Status", "überschreitet Grenzwert",
                "Anz. Windturbinen", "nächste Windturbine (m)", "dominantes Modell",
                "dom. Quellgruppe", "dom. Park", "LwA dom. Quelle dB(A)",
                "Adiv dB", "Aatm dB", "Agr/Aground dB", "Abar max. dB",
                "G Boden", "Bodenmodus", "Rezeptorhöhe m", "z Gelände Rezeptor m",
                "z akustisch Rezeptor m", "dominanter Quell-Layer"
            ])
            self.tbl_layers.setHorizontalHeaderLabels(["Layer", "Status"])
            self.btn_export_summary.setText("Bericht exportieren…")
            self.btn_export_summary.setToolTip("Speichert die technische Übersicht als HTML oder TXT.")
            self.btn_export_receivers.setText("Rezeptoren als CSV exportieren…")
            self.btn_export_receivers.setToolTip("Speichert eine saubere Tabelle mit einer Zeile pro Rezeptor.")
            self.btn_export_exceed.setText("Überschreitungen als CSV exportieren…")
            self.btn_export_exceed.setToolTip("Speichert nur Rezeptoren, die ihren akustischen Grenzwert überschreiten.")
            self.btn_export_xlsx.setText("XLSX-Paket exportieren…")
            self.btn_export_xlsx.setToolTip("Speichert Übersicht, Modelle, Rezeptoren und Überschreitungen in einer Excel-Datei.")
            close_btn.setText("Schließen")
        root.addLayout(btns)

    def _fill(self):
        self._fill_summary()
        self._fill_models()
        self._fill_top_receivers()
        self._fill_mdt_screening()
        self._fill_layers()

    def _payload_top_receivers(self) -> List[Dict[str, object]]:
        rows = self._res.get("top_receivers") or []
        out: List[Dict[str, object]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
        def _noise(d):
            try:
                return float(d.get("noise_dba") or d.get("total_level_dba") or 0.0)
            except Exception:
                return -1.0e99
        out.sort(key=_noise, reverse=True)
        return out


    def _payload_receiver_rows(self) -> List[Dict[str, object]]:
        rows = self._res.get("receiver_rows") or []
        out: List[Dict[str, object]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
        if out:
            return out
        # Fallback to visible top rows if the full receiver payload is absent.
        return self._payload_top_receivers()


    def _attenuation_stats_from_payload_rows(self) -> Dict[str, Dict[str, float]]:
        """Compute attenuation statistics from stable named receiver rows.

        The HTML report historically used the precomputed ``*_stats`` entries
        in ``self._res``.  When the calculation is returned by a background
        QgsTask, those entries can remain zero if the QGIS memory layer cannot
        be read at the exact moment the dialog is built, even though
        ``receiver_rows`` and the Top receivers table contain the correct
        values.  This fallback derives the statistics directly from the named
        payload used by the CSV/XLSX exports.
        """
        rows = self._payload_receiver_rows()

        def _f(d: Dict[str, object], *keys: str):
            for key in keys:
                try:
                    v = d.get(key)
                except Exception:
                    v = None
                if v is None:
                    continue
                txt = str(v).strip()
                if txt == '' or txt.lower() in ('none', 'nan', 'n/a'):
                    continue
                try:
                    x = float(txt.replace(',', '.'))
                except Exception:
                    continue
                if x == x:
                    return x
            return None

        def _covered(d: Dict[str, object]) -> bool:
            nsrc = _f(d, 'n_src', 'turbines_in_radius', 'no. turbines')
            if nsrc is not None:
                return nsrc > 0
            covered = _f(d, 'covered')
            if covered is not None:
                return covered > 0
            noise = _f(d, 'noise_dba', 'total_level_dba', 'total level dB(A)')
            return bool(noise is not None and noise > 0)

        vals = {
            'adiv': [],
            'aatm': [],
            'aground': [],
            'abar': [],
        }
        for d in rows:
            if not isinstance(d, dict) or not _covered(d):
                continue
            for name, keys in {
                'adiv': ('adiv_db', 'divergence_loss_db', 'Adiv loss dB', 'pérdida Adiv dB'),
                'aatm': ('aatm_db', 'atmospheric_loss_db', 'Aatm loss dB', 'pérdida Aatm dB'),
                'aground': ('aground_db', 'ground_loss_db', 'Agr/Aground loss dB', 'pérdida Agr/Aground dB'),
                'abar': ('abar_max_db', 'barrier_loss_max_contributors_db', 'Abar max contrib. dB', 'abar_db', 'Abar dom. dB'),
            }.items():
                x = _f(d, *keys)
                if x is not None:
                    vals[name].append(float(x))

        def _stat(seq: List[float]) -> Dict[str, float]:
            if not seq:
                return {'mean': 0.0, 'max': 0.0}
            return {'mean': sum(seq) / float(len(seq)), 'max': max(seq)}

        return {name: _stat(seq) for name, seq in vals.items()}

    def _prefer_payload_stats_if_needed(self, current: Dict[str, object], fallback: Dict[str, float]) -> Dict[str, float]:
        """Use payload-derived stats when the current report stats are empty/zero."""
        try:
            cur_max = float((current or {}).get('max', 0.0) or 0.0)
        except Exception:
            cur_max = 0.0
        try:
            fb_max = float((fallback or {}).get('max', 0.0) or 0.0)
        except Exception:
            fb_max = 0.0
        if fb_max > 0.0 and cur_max <= 0.0:
            return dict(fallback or {})
        return dict(current or {})

    def _infer_critical_receiver_from_layer(self) -> Dict[str, object]:
        """Return the highest-noise receiver as a dict using current layer fields."""
        layer = self._res.get("result_layer")
        payload_rows = self._payload_top_receivers()
        if not isinstance(layer, QgsVectorLayer):
            return dict(payload_rows[0]) if payload_rows else {}
        best_feat = None
        best_level = -1.0e99
        level_keys = ("noise_dba", "total_level_dba", "nivel_total_dba")
        try:
            iterator = layer.getFeatures()
        except Exception:
            return {}
        for feat in iterator:
            level = None
            for key in level_keys:
                try:
                    level = float(feat[key])
                    break
                except Exception:
                    continue
            if level is None:
                continue
            try:
                if level != level:
                    continue
            except Exception:
                continue
            if best_feat is None or level > best_level:
                best_feat = feat
                best_level = level
        if best_feat is None:
            return dict(payload_rows[0]) if payload_rows else {}
        row: Dict[str, object] = {"fid": best_feat.id(), "rec_id": best_feat.id()}
        try:
            for fld in layer.fields():
                name = fld.name()
                try:
                    row[name] = best_feat[name]
                except Exception:
                    pass
        except Exception:
            pass
        if not row.get("rec_id"):
            row["rec_id"] = best_feat.id()
        return row

    def _fill_summary(self):
        n_sources = int(self._res.get("n_sources", 0))
        n_receivers = int(self._res.get("n_receivers", 0))
        n_with = int(self._res.get("n_receivers_with_sources", 0))
        n_without = int(self._res.get("n_uncovered_receivers", max(0, n_receivers - n_with)))
        n_exceed = int(self._res.get("n_receivers_exceeding_limit", 0))
        max_noise = float(self._res.get("max_noise_dba", 0.0))
        model_diag = self._res.get("model_diag", {}) or {}
        n_models = len(model_diag)
        limit_stats = self._res.get('limit_stats') or self._infer_limit_stats_from_layer()
        acoustic = self._res.get('acoustic_scenario', {}) or {}
        crit_raw = self._res.get('critical_receiver') or {}
        crit_layer = self._infer_critical_receiver_from_layer()

        def _has_value(v):
            if v is None:
                return False
            try:
                if isinstance(v, float) and v != v:
                    return False
            except Exception:
                pass
            return str(v).strip() != ''

        # Merge stored critical-receiver metadata with a robust fallback read directly
        # from the result layer. This avoids visual summaries falling back to 0.00
        # when the engine changes field names.
        crit = dict(crit_layer or {})
        for _k, _v in dict(crit_raw or {}).items():
            if _has_value(_v):
                crit[_k] = _v
        payload_att_stats = self._attenuation_stats_from_payload_rows()
        adiv_stats = self._prefer_payload_stats_if_needed(self._res.get('adiv_stats') or {}, payload_att_stats.get('adiv') or {})
        aatm_stats = self._prefer_payload_stats_if_needed(self._res.get('aatm_stats') or {}, payload_att_stats.get('aatm') or {})
        aground_stats = self._prefer_payload_stats_if_needed(self._res.get('aground_stats') or {}, payload_att_stats.get('aground') or {})
        abar_stats = self._prefer_payload_stats_if_needed(self._res.get('abar_stats') or {}, payload_att_stats.get('abar') or {})
        g_eff_stats = self._res.get('g_eff_stats') or {}
        ground_diag = self._res.get('ground_diag') or {}
        receiver_type_counts = self._res.get('receiver_type_counts') or {}
        grid_diag = self._res.get('grid_diag') or {}
        report = self._res.get('report_meta') or {}
        ground_mode = str(report.get('ground_mode') or self._res.get('ground_mode') or 'global')
        landuse_layer_name = str(report.get('landuse_layer_name') or self._res.get('landuse_layer_name') or '')
        dem_layer_name = str(report.get('dem_layer_name') or self._res.get('dem_layer_name') or '')
        dem_used = bool(report.get('dem_used', self._res.get('dem_used', False)))
        engine = str(report.get('engine') or ('iso_aligned' if str(self._res.get('method') or '').startswith('iso_') else 'fast'))
        engine_label = str(report.get('engine_label') or ('ISO-aligned par bandes' if engine == 'iso_aligned' else 'Rapide LwA global'))
        equation = str(report.get('equation') or ('Lp,b = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b' if engine == 'iso_aligned' else 'Lp = LwA - Adiv - Aatm - Aground'))
        alpha = float(report.get('alpha_db_per_m', self._res.get('alpha_db_per_m', 0.0)))
        g = float(report.get('ground_factor_g', self._res.get('ground_factor_g', 0.0)))
        rec_h = float(report.get('receiver_height_m', self._res.get('receiver_height_m', 0.0)))
        radius = float(report.get('max_radius_m', self._res.get('max_radius_m', 0.0)))
        temp_c = float(report.get('temperature_c', 15.0))
        hum_pct = float(report.get('humidity_percent', 70.0))
        pressure_kpa = float(report.get('pressure_kpa', 101.325))
        terms = report.get('active_terms') or {}
        spectrum_rows = report.get('spectrum_sources') or []

        if str(acoustic.get('mode') or 'fixed') == 'curve':
            if bool(acoustic.get('use_curve_worst_case', False)):
                acoustic_txt = 'Courbes acoustiques LwA(ws) en cas le plus défavorable'
            else:
                try:
                    acoustic_txt = f"Courbes acoustiques LwA(ws) à {float(acoustic.get('eval_ws_m_s')):.1f} m/s"
                except Exception:
                    acoustic_txt = 'Courbes acoustiques LwA(ws)'
        else:
            acoustic_txt = 'LwA fixe par groupe de source acoustique'

        eff_lines = []
        for d in list(acoustic.get('effective_models') or []):
            group_name = str(d.get('name') or 'Groupe')
            park_name = str(d.get('park_name') or '').strip()
            model_name = str(d.get('model_name') or '').strip()
            spec_src = ''
            for sp in spectrum_rows:
                if str(sp.get('group_name') or '') == group_name:
                    spec_src = str(sp.get('spectrum_source') or '')
                    break
            try:
                line = f"<li><b>{group_name}</b>: {float(d.get('lwa_effective')):.2f} dB(A)"
            except Exception:
                line = f"<li><b>{group_name}</b>: sans valeur"
            extra = []
            if model_name:
                extra.append(f"modèle {model_name}")
            if park_name:
                extra.append(f"parc {park_name}")
            if str(d.get('curve_note') or '').strip():
                extra.append(str(d.get('curve_note')))
            if spec_src:
                extra.append(f"spectre {spec_src}")
            if extra:
                line += " · " + " · ".join(extra)
            line += "</li>"
            eff_lines.append(line)

        spectrum_detail_blocks = []
        for sp in spectrum_rows:
            group_name = str(sp.get('group_name') or 'Groupe')
            model_name = str(sp.get('model_name') or group_name)
            spec_src = str(sp.get('spectrum_source') or '')
            lw_oct = {int(k): float(v) for k, v in (sp.get('lw_octave') or {}).items()}
            sref = {int(k): float(v) for k, v in (sp.get('spectrum_template_ref') or {}).items()}
            try:
                delta_db = float(sp.get('spectrum_delta_db'))
                if not (delta_db == delta_db):
                    delta_db = None
            except Exception:
                delta_db = None
            rows = []
            for f in OCTAVE_BANDS:
                sref_txt = '-'
                if f in sref:
                    sref_txt = f"{sref[f]:.2f}"
                lw_txt = '-'
                if f in lw_oct:
                    lw_txt = f"{lw_oct[f]:.2f}"
                a_txt = f"{float(A_WEIGHTING.get(f, 0.0)):.1f}"
                rows.append(f"<tr><td>{f}</td><td style='text-align:right;'>{sref_txt}</td><td style='text-align:right;'>{a_txt}</td><td style='text-align:right;'>{lw_txt}</td></tr>")
            delta_line = ''
            if delta_db is not None:
                delta_line = f"<p><b>Δ appliqué :</b> {delta_db:.2f} dB. Ce décalage augmente ou réduit toute la forme spectrale afin que sa somme pondérée A reproduise le <code>LwA_cible</code> de la courbe acoustique ou du LwA fixe.</p>"
            origin_line = '<p><b>Interprétation :</b> le spectre final <code>Lw,b</code> est celui qui entre réellement dans l’équation par bandes. Si <code>S_b^ref</code> existe, il correspond à la forme de référence avant l’ajustement global <code>Δ</code>.</p>' if sref else '<p><b>Interprétation :</b> pour ce groupe, aucune forme interne visible n’a été utilisée ; le spectre final <code>Lw,b</code> provient directement du spectre chargé/importé ou d’une bibliothèque externe.</p>'
            spectrum_detail_blocks.append(f"""
                <div class='card'>
                    <h4>2.1 Spectre utilisé par le groupe source : {group_name}</h4>
                    <p><b>Modèle :</b> {model_name} · <b>Origine du spectre :</b> {spec_src or '-'}.</p>
                    <p><b>Ce que représente chaque colonne :</b> <code>S_b^ref</code> est la forme spectrale de référence (si elle existe), <code>A_weight,b</code> la pondération A de chaque bande et <code>Lw,b</code> le niveau final en dB réellement utilisé par le calcul.</p>
                    {delta_line}
                    <table>
                        <tr><th>Bande [Hz]</th><th style='text-align:right;'>S_b^ref [dB]</th><th style='text-align:right;'>A_weight,b [dB]</th><th style='text-align:right;'>Lw,b final [dB]</th></tr>
                        {''.join(rows)}
                    </table>
                    {origin_line}
                </div>
            """)
        spectrum_detail_html = ''.join(spectrum_detail_blocks)

        def _fmt_equation_term(value: float) -> str:
            try:
                v = float(value)
            except Exception:
                return '-'
            if v != v:
                return '-'
            if abs(v) < 0.005:
                return '0.00'
            return f"{v:.2f}"

        if crit:
            def _crit_value(*keys, default=None):
                for key in keys:
                    try:
                        val = crit.get(key)
                    except Exception:
                        val = None
                    if val is None:
                        continue
                    try:
                        if isinstance(val, float) and val != val:
                            continue
                    except Exception:
                        pass
                    if str(val).strip() == '':
                        continue
                    return val
                return default

            def _crit_float(*keys, default=0.0):
                val = _crit_value(*keys, default=None)
                if val is None:
                    return float(default)
                try:
                    f = float(val)
                    if f != f:
                        return float(default)
                    return f
                except Exception:
                    return float(default)

            crit_id = _crit_value('rec_id', 'fid', default='-')
            crit_level = _crit_float('nivel_total_dba', 'total_level_dba', 'noise_dba', default=max_noise)
            crit_limit = _crit_float('limite_aplicado_dba', 'limit_dba', default=45.0)
            crit_margin = _crit_float('margen_limite_db', 'limit_margin_db', 'margin_db', default=crit_level - crit_limit)
            crit_model = _crit_value('modelo_dominante', 'dominant_model', 'dom_model', default='-')
            crit_group = _crit_value('grupo_fuente_dominante', 'dominant_source_group', 'dom_group', default='-')
            crit_n_turb = _crit_value('n_turbinas_en_radio', 'turbines_in_radius', 'n_src', default='-')
            crit_lwa = _crit_float('lwa_fuente_dom_dba', 'source_lwa_dba', 'src_lwa', default=0.0)
            crit_dist = _crit_float('dist_fuente_dom_3d_m', 'source_receiver_3d_m', 'dist3d_m', 'near_m', default=0.0)
            crit_adiv = _crit_float('perdida_divergencia_db', 'divergence_loss_db', 'adiv_db', default=0.0)
            crit_aatm = _crit_float('perdida_atmosferica_db', 'atmospheric_loss_db', 'aatm_db', default=0.0)
            crit_agr = _crit_float('perdida_suelo_db', 'ground_loss_db', 'aground_db', default=0.0)
            crit_abar = _crit_float('perdida_barrera_db', 'barrier_loss_db', 'abar_db', default=0.0)
            crit_abar_max = _crit_float('perdida_barrera_max_db', 'barrier_loss_max_contributors_db', 'abar_max_db', default=crit_abar)
            crit_abar_mean = _crit_float('perdida_barrera_media_db', 'barrier_loss_mean_contributors_db', 'abar_mean_db', default=crit_abar)
            crit_abar_ew = _crit_float('perdida_barrera_ponderada_db', 'barrier_loss_energy_weighted_db', 'abar_ew_db', default=crit_abar)
            crit_abar_screen_n = _crit_value('n_fuentes_apantalladas', 'barrier_screened_sources_n', 'abar_screen_n', default=0)
            try:
                crit_abar_screen_n = int(crit_abar_screen_n or 0)
            except Exception:
                crit_abar_screen_n = 0
            crit_g_eff = _crit_float('factor_suelo_g', 'ground_factor_g', 'ground_g', default=float(g_eff_stats.get('critical', g)))
            crit_freq = _crit_value('banda_dominante_hz', 'dominant_band_hz', 'dom_freq', default='-')
            crit_spec_src = _crit_value('origen_espectro', 'spectrum_source', 'spec_src', default='-')
            crit_abar_state = str(_crit_value('mdt_abar_state', 'abar_state', default='') or '').strip()
            crit_obs_h = _crit_float('mdt_obstacle_height_m', 'obs_h_m', default=0.0)
            crit_obs_d1 = _crit_float('mdt_d1_m', 'obs_d1_m', default=0.0)
            crit_obs_d2 = _crit_float('mdt_d2_m', 'obs_d2_m', default=0.0)
            crit_obs_thr = _crit_float('mdt_obstacle_threshold_m', 'obs_thr_m', default=0.0)
            crit_src_z = _crit_float('dominant_source_ground_z_m', 'src_z_m', default=float('nan'))
            crit_hub_h = _crit_float('dominant_source_hub_height_m', 'hub_h_m', default=float('nan'))
            crit_src_ac_z = _crit_float('dominant_source_acoustic_z_m', 'src_ac_z_m', default=float('nan'))
            crit_rec_z = _crit_float('receiver_ground_z_m', 'rec_z_m', default=float('nan'))
            crit_rec_h = _crit_float('receiver_height_agl_m', 'rec_h_m', default=float('nan'))
            crit_rec_ac_z = _crit_float('receiver_acoustic_z_m', 'rec_ac_z_m', default=float('nan'))
            crit_maxab_src = _crit_value('max_abar_source_index', 'maxab_src', default='-')
            crit_maxab_state = str(_crit_value('max_abar_mdt_state', 'maxab_state', default='') or '').strip()
            crit_maxab_obs_h = _crit_float('max_abar_obstacle_height_m', 'maxab_obs_h', default=0.0)
            crit_maxab_d1 = _crit_float('max_abar_source_obstacle_m', 'maxab_d1', default=0.0)
            crit_maxab_d2 = _crit_float('max_abar_obstacle_receiver_m', 'maxab_d2', default=0.0)
            
            status_badge = 'badge-success' if crit_margin <= 0 else 'badge-danger'
            status_text = 'CONFORME' if crit_margin <= 0 else 'DÉPASSE'
            card_class = 'card-success' if crit_margin <= 0 else 'card-danger'

            crit_adiv_txt = _fmt_equation_term(crit_adiv)
            crit_aatm_txt = _fmt_equation_term(crit_aatm)
            crit_agr_txt = _fmt_equation_term(crit_agr)
            crit_abar_txt = _fmt_equation_term(crit_abar)
            crit_agr_desc = f"Atténuation due à l’effet de sol (G_eff={crit_g_eff:.2f})"
            crit_abar_desc = "Atténuation due au MDT sur le trajet dominant"
            crit_abar_max_txt = _fmt_equation_term(crit_abar_max)
            crit_abar_mean_txt = _fmt_equation_term(crit_abar_mean)
            crit_abar_ew_txt = _fmt_equation_term(crit_abar_ew)
            try:
                crit_n_turb_i = int(crit_n_turb)
            except Exception:
                crit_n_turb_i = 0

            def _fmt_m_or_na(v):
                try:
                    f = float(v)
                    if f != f:
                        return 'N/A'
                    return f"{f:.2f}"
                except Exception:
                    return 'N/A'

            dominant_height_html = (
                f"<br><b>Hauteurs du trajet dominant :</b> terrain éolienne={_fmt_m_or_na(crit_src_z)} m · "
                f"hub={_fmt_m_or_na(crit_hub_h)} m AGL · hauteur acoustique éolienne={_fmt_m_or_na(crit_src_ac_z)} m · "
                f"terrain récepteur={_fmt_m_or_na(crit_rec_z)} m · h récepteur={_fmt_m_or_na(crit_rec_h)} m AGL · "
                f"hauteur acoustique récepteur={_fmt_m_or_na(crit_rec_ac_z)} m."
            )
            maxabar_height_html = ''
            if float(crit_abar_max or 0.0) > 0.005:
                maxabar_height_html = (
                    f"<br><b>Trajet avec Abar maximal :</b> source={crit_maxab_src} · état={crit_maxab_state or '-'} · "
                    f"obs={_fmt_m_or_na(crit_maxab_obs_h)} m · d1={_fmt_m_or_na(crit_maxab_d1)} m · d2={_fmt_m_or_na(crit_maxab_d2)} m."
                )
            abar_summary_html = ''
            if dem_used and engine == 'iso_aligned':
                abar_summary_html = f"""
                <div class='note'>
                    <b>Lecture correcte d’Abar :</b> la valeur <b>Abar du trajet dominant</b> correspond uniquement à l’éolienne qui contribue le plus au récepteur et à sa bande dominante. Le niveau total du récepteur est obtenu par sommation énergétique de toutes les éoliennes et bandes.
                    <br><b>Abar maximal parmi les éoliennes contributrices :</b> {crit_abar_max_txt} dB · <b>Abar moyen :</b> {crit_abar_mean_txt} dB · <b>Abar pondéré par contribution énergétique :</b> {crit_abar_ew_txt} dB · <b>trajets écrantés :</b> {crit_abar_screen_n}/{crit_n_turb_i if crit_n_turb_i else crit_n_turb}.
                    {dominant_height_html}
                    {maxabar_height_html}
                </div>
                """

            abar_note_html = ''
            if dem_used and engine == 'iso_aligned':
                if abs(float(crit_abar)) < 0.005:
                    reason_map = {
                        'los_clear': 'la ligne de visée entre l’éolienne dominante et ce récepteur est dégagée selon le MDT',
                        'below_threshold': 'un relief a été détecté, mais sous le seuil conservateur d’activation',
                        'no_profile': 'aucun profil MDT valide n’a pu être extrait pour le trajet dominant',
                        'no_dem': 'aucun MDT n’était disponible sur ce trajet',
                    }
                    reason = reason_map.get(crit_abar_state, 'aucun obstacle topographique pertinent n’a été détecté sur le trajet dominant')
                    extra = ''
                    if float(crit_obs_thr) > 0.0:
                        extra = f" Seuil d’activation: {crit_obs_thr:.2f} m."
                    if float(abar_stats.get('max', 0.0) or 0.0) > 0.005:
                        extra += f" D’autres récepteurs présentent bien un écran (Abar max. {float(abar_stats.get('max',0.0)):.2f} dB)."
                    abar_note_html = f"<p style='margin:8px 0 10px 0;color:#495057;'><i>Lecture MDT : Abar=0 au récepteur critique ne signifie pas que le MDT est désactivé ; cela signifie que {reason}.{extra}</i></p>"
                else:
                    abar_note_html = f"<p style='margin:8px 0 10px 0;color:#495057;'><i>Lecture MDT : obstacle dominant estimé {crit_obs_h:.2f} m; d1={crit_obs_d1:.1f} m, d2={crit_obs_d2:.1f} m; état={crit_abar_state or 'actif'}.</i></p>"

            crit_html = f"""
        <div class='{card_class}'>
            <h3>🎯 Récepteur critique (niveau sonore le plus élevé)</h3>
            
            <table style='margin-bottom: 20px;'>
                <tr>
                    <td style='width: 50%; padding-right: 20px;'>
                        <p><b>ID récepteur :</b> {crit_id}</p>
                        <p><b>Niveau total :</b> <span style='font-size:28px; font-weight:bold; color:{'#dc3545' if crit_margin > 0 else '#28a745'};'>{crit_level:.2f} dB(A)</span></p>
                        <p><b>Limite applicable :</b> {crit_limit:.2f} dB(A)</p>
                        <p><b>Marge :</b> {crit_margin:+.2f} dB <span class='{status_badge}'>{status_text}</span></p>
                    </td>
                    <td style='width: 50%;'>
                        <p><b>Modèle dominant :</b> {crit_model}</p>
                        <p><b>Groupe source :</b> {crit_group}</p>
                        <p><b>Éoliennes contributrices dans le rayon :</b> {crit_n_turb}</p>
                        <p><b>Distance :</b> {crit_dist:.1f} m</p>
                    </td>
                </tr>
            </table>
            
            <h4>📊 Décomposition des atténuations</h4>
            <p style='margin: 6px 0 10px 0; color:#495057;'><i>Les valeurs affichées ci-dessous sont les amplitudes d’atténuation utilisées par le modèle. Dans l’équation principale, ces termes sont soustraits au niveau de source.</i></p>
            <table style='margin: 16px 0;'>
                <tr>
                    <th>Terme</th>
                    <th style='text-align: right;'>Valeur [dB]</th>
                    <th>Description</th>
                </tr>
                <tr style='background: #e3f2fd;'>
                    <td><b>LwA source dominante</b></td>
                    <td style='text-align: right;'><b>{crit_lwa:.2f}</b></td>
                    <td>Puissance acoustique de l’éolienne</td>
                </tr>
                <tr>
                    <td>Adiv (divergence)</td>
                    <td style='text-align: right;'>{crit_adiv_txt}</td>
                    <td>Dispersion géométrique</td>
                </tr>
                <tr>
                    <td>Aatm (atmosphérique)</td>
                    <td style='text-align: right;'>{crit_aatm_txt}</td>
                    <td>Absorption dans l’air</td>
                </tr>
                <tr>
                    <td>Agr (sol)</td>
                    <td style='text-align: right;'>{crit_agr_txt}</td>
                    <td>{crit_agr_desc}</td>
                </tr>
                <tr>
                    <td>Abar trajet dominant</td>
                    <td style='text-align: right;'>{crit_abar_txt}</td>
                    <td>{crit_abar_desc}</td>
                </tr>
                <tr>
                    <td>Abar maximal des contributeurs</td>
                    <td style='text-align: right;'>{crit_abar_max_txt}</td>
                    <td>Abar maximal parmi toutes les éoliennes qui contribuent au récepteur</td>
                </tr>
                <tr>
                    <td>Abar pondéré par énergie</td>
                    <td style='text-align: right;'>{crit_abar_ew_txt}</td>
                    <td>Moyenne pondérée par la contribution acoustique de chaque éolienne</td>
                </tr>
                <tr>
                    <td>Trajets écrantés</td>
                    <td style='text-align: right;'>{crit_abar_screen_n}/{crit_n_turb}</td>
                    <td>Nombre d’éoliennes contributrices avec Abar &gt; 0 dB</td>
                </tr>
                <tr style='background: #1e3a5f; color: white; font-weight: bold;'>
                    <td>NIVEAU RÉSULTANT</td>
                    <td style='text-align: right;'>{crit_level:.2f}</td>
                    <td>dB(A)</td>
                </tr>
            </table>
            {abar_note_html}
            {abar_summary_html}
            <p style='margin: 6px 0 10px 0; color:#495057;'><i>Note : le niveau résultant inclut la sommation énergétique multi-source et multi-bande ; ce n’est pas une soustraction directe depuis une seule éolienne.</i></p>
            
            <p style='margin-top: 16px;'>
                <b>Bande dominante :</b> {crit_freq} Hz &nbsp;&nbsp;&nbsp;
                <b>Origine du spectre :</b> {crit_spec_src}
            </p>
        </div>
            """
        else:
            crit_html = "<div class='card'><p>Récepteur critique non disponible.</p></div>"

        rec_types_html = ''.join([f"<li><b>{k}:</b> {v}</li>" for k, v in sorted(receiver_type_counts.items())])
        compliance = self._res.get('receiver_type_compliance') or {}
        compliance_html = ''.join([f"<li><b>{k}:</b> {int((v or {}).get('exceed',0))}/{int((v or {}).get('total',0))} dépassent la limite" + (f" · couverts {int((v or {}).get('covered',0))}" if (v or {}).get('covered') is not None else '') + "</li>" for k, v in sorted(compliance.items())])
        suelo_txt = 'global' if ground_mode != 'landuse' else f"depuis couche ({landuse_layer_name or 'sans nom'})"
        grid_txt = 'non généré'
        if self._res.get('grid_layer') is not None:
            grid_txt = f"oui · résolution demandée {float(grid_diag.get('requested_resolution_m',0.0)):.1f} m · effective {float(grid_diag.get('effective_resolution_m',0.0)):.1f} m"
            if bool(grid_diag.get('auto_adjusted', False)):
                grid_txt += ' · auto-ajustée'
        limit_mode = str(limit_stats.get('mode') or 'global').lower()
        limit_scn = str(limit_stats.get('scenario') or 'custom').lower()
        if limit_mode == 'by_field':
            scn_txt = {'day': 'diurne', 'night': 'nocturne', 'custom': 'personnalisé'}.get(limit_scn, limit_scn or 'personnalisé')
            if abs(float(limit_stats.get('min',45.0)) - float(limit_stats.get('max',45.0))) < 1e-9:
                limit_html = f"<p><b>Limites appliquées :</b> depuis les champs des récepteurs ({scn_txt}) · valeur unique {float(limit_stats.get('min',45.0)):.1f} dB(A)</p>"
            else:
                limit_html = f"<p><b>Limites appliquées :</b> depuis les champs des récepteurs ({scn_txt}) · plage {float(limit_stats.get('min',45.0)):.1f}–{float(limit_stats.get('max',45.0)):.1f} dB(A)</p>"
        else:
            limit_html = f"<p><b>Limite de référence :</b> {float(limit_stats.get('max',45.0)):.1f} dB(A)</p>"

        equations_html = f"<pre style='background:#f6f8fb;border:1px solid #d9e2ef;padding:10px;border-radius:6px;white-space:pre-wrap;'>{equation}</pre>"

        if not crit:
            crit_adiv_txt = crit_aatm_txt = crit_agr_txt = crit_abar_txt = '-'
            crit_agr_desc = 'Effet du sol'
            crit_abar_desc = 'Diffraction topographique'

        param_lines = [
            f"<li><b>Moteur :</b> {engine_label}</li>",
            f"<li><b>Hauteur du récepteur :</b> {rec_h:.1f} m</li>",
            f"<li><b>Rayon maximal :</b> {radius:.0f} m</li>",
            f"<li><b>Mode sol :</b> {suelo_txt}</li>",
        ]
        if ground_mode == 'landuse':
            param_lines.extend([
                f"<li><b>G global de secours:</b> {g:.2f}</li>",
                f"<li><b>G_eff moyen utilisé:</b> {float(g_eff_stats.get('mean', g)):.2f}</li>",
                f"<li><b>G_eff du récepteur critique utilisé:</b> {float(g_eff_stats.get('critical', g)):.2f}</li>",
            ])
        else:
            param_lines.extend([
                f"<li><b>G utilisé:</b> {g:.2f}</li>",
                f"<li><b>G_eff moyen:</b> {float(g_eff_stats.get('mean', g)):.2f}</li>",
                f"<li><b>G_eff du récepteur critique:</b> {float(g_eff_stats.get('critical', g)):.2f}</li>",
            ])
        param_lines.extend([
            f"<li><b>MDT/DSM:</b> {'oui · ' + (dem_layer_name or 'sans nom') if dem_used else 'non'}</li>",
            f"<li><b>Occupation du sol:</b> {'oui · ' + (landuse_layer_name or 'sans nom') if bool(report.get('landuse_used', False)) else 'non'}</li>",
            f"<li><b>Scénario acoustique :</b> {acoustic_txt}</li>",
        ])
        if engine == 'iso_aligned':
            param_lines.extend([
                f"<li><b>Température :</b> {temp_c:.1f} °C</li>",
                f"<li><b>Humidité relative :</b> {hum_pct:.1f} %</li>",
                f"<li><b>Pression :</b> {pressure_kpa:.3f} kPa</li>",
            ])
        else:
            param_lines.append(f"<li><b>α atmosphérique :</b> {alpha:.4f} dB/m</li>")

        term_lines = [
            f"<li><b>Adiv:</b> {'actif' if terms.get('Adiv', True) else 'non'}</li>",
            f"<li><b>Aatm:</b> {'actif' if terms.get('Aatm', True) else 'non'}" + (' (T, HR, P simplifié)' if engine == 'iso_aligned' else ' (α·distance)') + "</li>",
            f"<li><b>Agr/Aground:</b> {'actif' if terms.get('Agr', True) else 'non'}</li>",
            f"<li><b>Abar:</b> {'actif' if terms.get('Abar', False) else 'inactif'}</li>",
            f"<li><b>G effectif depuis l’occupation du sol:</b> {'oui' if terms.get('landuse_g', False) else 'non'}</li>",
        ]

        pressure_warning_html = ''
        if engine == 'iso_aligned' and (pressure_kpa < 85.0 or pressure_kpa > 105.0):
            pressure_warning_html = (
                "<p class='note'><b>Révision recommandée :</b> la pression atmosphérique saisie "
                f"({pressure_kpa:.3f} kPa) est hors de la plage typique utilisée comme référence dans de nombreuses études "
                "préliminaires. Si ce n’est pas une mesure du site, vérifier si elle devrait être proche de 101,325 kPa "
                "ou ajustée à l’altitude.</p>"
            )

        interpretation = (
            "Adiv représente la divergence géométrique. Aatm est calculé par bande et dépend de T, HR et de la pression, avec une formulation simplifiée. "
            "Agr est appliqué comme terme de sol/terrain et Abar comme écran topographique de base lorsqu’un MDT est disponible."
            if engine == 'iso_aligned' else
            "Adiv représente la divergence géométrique, Aatm l’atténuation atmosphérique simplifiée α·distance et Aground une correction simplifiée de l’effet de sol/terrain."
        )

        if engine == 'iso_aligned':
            methodology_flow_html = f"""
            <div class='card card-info'>
                <h3>🧭 Comment le calcul ISO-aligned a été exécuté</h3>
                <p>Cette section explique le flux réel suivi par le plugin afin que le résultat par récepteur soit traçable. Le niveau final de chaque récepteur <b>ne provient pas d’une simple soustraction unique</b>, mais du calcul de toutes les contributions source–récepteur dans le rayon de calcul, puis de leur sommation énergétique.</p>
                <ol>
                    <li><b>Lecture des entrées SIG:</b> les éoliennes/sources acoustiques, les récepteurs, la hauteur du récepteur et le rayon maximal de calcul sont pris en compte (<b>{radius:.0f} m</b>), la couche d’occupation du sol si elle existe et le MDT/DSM s’il est actif.</li>
                    <li><b>État acoustique de chaque groupe source :</b> pour chaque modèle ou groupe d’éoliennes, un <b>LwA opérationnel</b> est obtenu à partir d’une valeur fixe ou d’une courbe <code>LwA(ws)</code>. Dans ce calcul: <b>{acoustic_txt}</b>.</li>
                    <li><b>Conversion en bandes:</b> le moteur ISO-aligned a besoin d’un spectre <code>Lw,b</code> en 8 bandes d’octave. S’il n’existe pas de spectre spécifique, le plugin en reconstruit un à partir d’un gabarit/fallback et l’ajuste pour reproduire le LwA opérationnel.</li>
                    <li><b>Sélection des contributeurs par récepteur:</b> pour chaque récepteur, les éoliennes situées dans le rayon maximal sont recherchées. Les récepteurs sans sources dans ce rayon sont marqués comme <b>hors rayon</b> et ne produisent pas de niveau acoustique utile.</li>
                    <li><b>Calcul par trajet source–récepteur :</b> pour chaque éolienne contributrice, la distance 3D, les cotes acoustiques, <b>G</b> ou <b>G_eff</b> du sol et, si un MDT/DSM est disponible, l’éventuel écran topographique du trajet sont calculés.</li>
                    <li><b>Propagation par bande:</b> dans chaque bande, on applique <code>Lp,b = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b</code>. Adiv dépend de la distance, Aatm,b de la fréquence/de l’atmosphère, Agr,b du sol et Abar,b du MDT s’il existe un obstacle pertinent.</li>
                    <li><b>Sommation par source :</b> les 8 bandes sont pondérées A puis sommées énergétiquement pour obtenir le niveau pondéré A de cette éolienne au récepteur.</li>
                    <li><b>Sommation du récepteur:</b> toutes les éoliennes contributrices sont sommées énergétiquement pour obtenir le <b>niveau total dB(A)</b> du récepteur.</li>
                    <li><b>Comparaison avec les limites:</b> le niveau total est comparé à la limite attribuée au récepteur ou à la limite de référence. La marge, l’état de conformité et le tableau des dépassements en découlent.</li>
                </ol>
                <div class='formula'>LpA,récepteur = 10·log10(Σ_sources 10^(LpA,source/10))</div>
                <p><b>Lecture pratique :</b> le récepteur critique est celui qui présente le niveau total le plus élevé ou la marge la plus défavorable par rapport à la limite. La colonne « source dominante » identifie l’éolienne/le groupe qui contribue le plus, mais le résultat final du récepteur inclut toutes les sources dans le rayon.</p>
            </div>
            <div class='card'>
                <h3>🔎 Ce qui distingue ce mode du mode Screening</h3>
                <p>Le mode ISO-aligned est plus lourd mais plus traçable : il utilise les bandes d’octave, la pondération A finale, l’absorption atmosphérique dépendante de la fréquence, le sol par régions et l’écran topographique <b>Abar</b> lorsqu’un MDT/DSM est disponible. C’est le mode recommandé pour les rapports techniques préliminaires et la revue des récepteurs sensibles.</p>
            </div>
            """
        else:
            methodology_flow_html = f"""
            <div class='card card-info'>
                <h3>🧭 Comment le calcul Screening a été exécuté</h3>
                <p>Cette section explique le flux réel suivi par le plugin en mode rapide. L’objectif est d’obtenir une estimation agile pour les cartes, la comparaison d’alternatives et la détection initiale des récepteurs sensibles.</p>
                <ol>
                    <li><b>Lecture des entrées SIG:</b> les éoliennes/sources acoustiques, les récepteurs, la hauteur du récepteur et le rayon maximal de calcul sont pris en compte (<b>{radius:.0f} m</b>) et la couche d’occupation du sol si elle existe.</li>
                    <li><b>État acoustique de chaque groupe source :</b> chaque modèle ou groupe d’éoliennes utilise un seul <b>LwA opérationnel</b>, défini par une valeur fixe ou par une courbe <code>LwA(ws)</code>. Dans ce calcul: <b>{acoustic_txt}</b>.</li>
                    <li><b>Sélection des contributeurs par récepteur:</b> pour chaque récepteur, les éoliennes situées dans le rayon maximal sont recherchées. Les récepteurs sans sources dans ce rayon sont marqués comme <b>hors rayon</b>.</li>
                    <li><b>Calcul par trajet source–récepteur :</b> pour chaque éolienne contributrice, la distance 3D, la divergence géométrique, une absorption atmosphérique simplifiée <code>α·d</code> et une correction empirique de sol sont calculées.</li>
                    <li><b>Occupation du sol:</b> si une couche de land-use est disponible, le plugin peut calculer un <b>G_eff</b> par trajet ; sinon, il utilise le <b>G global</b> défini par l’utilisateur.</li>
                    <li><b>Propagation simplifiée:</b> <code>Lp = LwA - Adiv - Aatm - Aground</code> est appliqué. Il n’y a ni bandes d’octave ni écran topographique explicite <code>Abar</code>.</li>
                    <li><b>Sommation du récepteur:</b> toutes les éoliennes contributrices sont sommées énergétiquement pour obtenir le <b>niveau total dB(A)</b> du récepteur.</li>
                    <li><b>Comparaison avec les limites:</b> le niveau total est comparé à la limite attribuée au récepteur ou à la limite de référence. La marge, l’état de conformité et le tableau des dépassements en découlent.</li>
                </ol>
                <div class='formula'>LpA,récepteur = 10·log10(Σ_sources 10^(Lp,source/10))</div>
                <p><b>Lecture pratique :</b> ce mode est utile pour le criblage initial. Si un récepteur apparaît proche de la limite ou en dépassement, il est conseillé de le recalculer en mode ISO-aligned et de revoir les spectres, le terrain, l’occupation du sol et les limites appliquées.</p>
            </div>
            <div class='card'>
                <h3>🔎 Ce qui distingue ce mode du mode ISO-aligned</h3>
                <p>Le mode Screening sacrifie le détail pour gagner en vitesse. Il ne propage pas par bandes, n’utilise pas T/HR/P par fréquence, ne calcule pas <b>Abar</b> depuis le MDT et résume l’atmosphère avec un coefficient unique <b>α</b>. Il doit donc être interprété comme une préévaluation rapide, et non comme un rapport acoustique détaillé.</p>
            </div>
            """

        octave_rows = ''.join([
            f"<tr><td>{freq}</td><td style='text-align:right;'>{float(a_w):.1f}</td></tr>"
            for freq, a_w in [(63, -26.2), (125, -16.1), (250, -8.6), (500, -3.2), (1000, 0.0), (2000, 1.2), (4000, 1.0), (8000, -1.1)]
        ])
        atm_rows = ''.join([
            f"<tr><td>{freq}</td><td style='text-align:right;'>{alpha_ref:.4f}</td></tr>"
            for freq, alpha_ref in [(63, 0.0001), (125, 0.0003), (250, 0.0008), (500, 0.0020), (1000, 0.0040), (2000, 0.0095), (4000, 0.0280), (8000, 0.0900)]
        ])
        ground_rows = ''.join([
            "<tr><td>≤ 500 Hz</td><td style='text-align:right;'>A_ground = 1.5 dB</td></tr>",
            "<tr><td>1000 Hz</td><td style='text-align:right;'>1.5·(1 - e^(-h/10))</td></tr>",
            "<tr><td>2000 Hz</td><td style='text-align:right;'>3.0·(1 - e^(-h/10))</td></tr>",
            "<tr><td>4000 Hz</td><td style='text-align:right;'>6.0·(1 - e^(-h/10))</td></tr>",
            "<tr><td>8000 Hz</td><td style='text-align:right;'>12.0·(1 - e^(-h/10))</td></tr>",
        ])

        if engine == 'iso_aligned':
            if dem_used:
                mdt_expl_html = f"""
                <div class='card'>
                    <h3>🗺️ Physique du MDT et de l’écran topographique</h3>
                    <p>Dans le moteur ISO-aligned, le MDT <b>ne modifie pas l’émission de l’éolienne</b> ni l’absorption atmosphérique. Sa fonction est de décrire la <b>géométrie réelle du trajet source–récepteur</b> et d’alimenter le terme d’écran topographique <b>Abar,b</b>.</p>
                    <div class='formula'>Lp,b = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b</div>
                    <h4>Comment le MDT entre dans le calcul</h4>
                    <ol>
                        <li><b>Profil du terrain :</b> le profil source–récepteur est extrait du MDT avec un <b>échantillonnage adaptatif</b>, ajusté à la distance et à la résolution du raster. Le profil est calculé <b>une seule fois</b> par paire source–récepteur et réutilisé sur les 8 bandes afin de réduire le temps de calcul.</li>
                        <li><b>Ligne de visée directe :</b> le profil est comparé à la droite reliant la source acoustique à sa hauteur effective et le récepteur à sa hauteur d’évaluation. Si le terrain reste toujours sous cette droite, il n’y a pas d’obstacle topographique pertinent et <b>Abar,b = 0</b>.</li>
                        <li><b>Détection de l’obstacle dominant :</b> si une colline ou une crête du MDT dépasse au-dessus de la ligne de visée, le modèle considère qu’il existe un écran topographique. La grandeur clé est la hauteur de l’obstacle au-dessus de la ligne de visée:</li>
                    </ol>
                    <div class='formula'>h_obs = z_terrain - z_LOS</div>
                    <p>lorsque <b>h_obs &gt; 0</b>, le relief coupe la vision directe et une atténuation supplémentaire par diffraction peut apparaître.</p>
                    <ol start='4'>
                        <li><b>Activation conservatrice:</b> Abar n’est pas activé pour de petites irrégularités du relief ; un seuil minimal lié à la résolution du MDT est appliqué.</li>
                        <li><b>Géométrie réelle de l’obstacle :</b> le calcul utilise la <b>position réelle</b> de l’obstacle dominant et obtient <b>d1</b> (source → obstacle) et <b>d2</b> (obstacle → récepteur) réels, au lieu de supposer systématiquement un obstacle au point médian.</li>
                        <li><b>Diffraction de type Fresnel:</b> avec cette géométrie, une différence de chemins approximative est estimée et transformée en atténuation dépendante de la fréquence:</li>
                    </ol>
                    <div class='formula'>δ ≈ 0.5·h_obs²·(1/d1 + 1/d2) &nbsp;&nbsp; ; &nbsp;&nbsp; C = (2·f·δ)/c</div>
                    <p>où <b>δ</b> est la différence de chemins approximative, <b>f</b> la fréquence et <b>c</b> la vitesse du son. Le nombre <b>C</b> est ensuite traduit en une atténuation <b>Abar,b</b>, d’autant plus élevée que le relief bloque le trajet. C’est l’approximation implémentée dans le calcul.</p>
                    <p><b>Interprétation physique:</b> en terrain plat ou en l’absence d’intersection avec la ligne de visée, <b>Abar</b> est généralement négligeable. En terrain complexe, le MDT peut introduire plusieurs dB d’atténuation supplémentaire et modifier le récepteur critique.</p>
                    <p><b>Implémentation actuelle :</b> obstacle dominant unique, profil adaptatif avec limites de coût, géométrie réelle de l’obstacle, activation conservatrice et atténuation plafonnée à des valeurs raisonnables.</p>
                    <p><b>MDT utilisé dans ce calcul:</b> {dem_layer_name or 'sans nom'}.</p>
                </div>
                """
            else:
                mdt_expl_html = """
                <div class='card'>
                    <h3>🗺️ Physique du MDT et de l’écran topographique</h3>
                    <p>Dans ce calcul, <b>aucun MDT/DSM n’a été utilisé</b>, donc le terme d’écran topographique est fixé à:</p>
                    <div class='formula'>Abar,b = 0</div>
                    <p>L’évaluation est réalisée sans introduire d’écrans topographiques. La géométrie du trajet est résolue sans profil de terrain et le calcul dépend de Lw,b, Adiv, Aatm,b et Agr,b.</p>
                </div>
                """

            if ground_mode == 'landuse':
                ground_expl_html = f"""
                <div class='card'>
                    <h3>🌱 Physique de l’occupation du sol et calcul de G_eff</h3>
                    <p>Lorsque le mode sol est <b>depuis une couche</b>, le calcul n’utilise pas une seule valeur manuelle pour tout le parc. Pour chaque trajet source–récepteur, un <b>G_eff</b> est calculé depuis la couche d’occupation du sol:</p>
                    <div class='formula'>G_eff = (Σ G_i · L_i) / (Σ L_i)</div>
                    <p>où <b>G_i</b> est la valeur attribuée à chaque polygone intercepté par le trajet et <b>L_i</b> la longueur du trajet à l’intérieur de ce polygone.</p>
                    <ul>
                        <li><b>G = 0</b>: sol dur (urbano/asfalto/roca).</li>
                        <li><b>G = 0.5</b>: terrain mixte.</li>
                        <li><b>G = 1</b>: sol meuble/poreux (agricole, prairie, forestier, végétalisé).</li>
                    </ul>
                    <p><b>Important:</b> le <b>G global</b> affiché dans le rapport est uniquement une valeur de secours. Lorsqu’une couche d’occupation du sol est disponible, le calcul utilise réellement <b>G_eff</b> par trajet. Dans ce calcul, la valeur effective moyenne était <b>{float(g_eff_stats.get('mean', g)):.2f}</b> et celle du récepteur critique <b>{float(g_eff_stats.get('critical', g)):.2f}</b>.</p>
                    <p><b>Couche utilisée:</b> {landuse_layer_name or 'sans nom'}.</p>
                </div>
                """
            else:
                ground_expl_html = f"""
                <div class='card'>
                    <h3>🌱 Physique de l’occupation du sol et calcul de G</h3>
                    <p>Dans ce calcul, l’effet de sol a été calculé avec un <b>G manuel unique</b> pour tout le trajet:</p>
                    <div class='formula'>G = {g:.2f}</div>
                    <p>Cette valeur est appliquée dans le terme de sol du modèle. Aucun G_eff n’a été dérivé depuis une couche d’occupation du sol.</p>
                </div>
                """

            equations_detail_html = f"""
            <div class='card'>
                <h3>📘 Développement physique détaillé du moteur ISO-aligned</h3>
                <p>Ce moteur travaille en <b>8 bandes d’octave</b> (63–8000 Hz). Les bandes ne sont pas un résultat du calcul, mais la <b>grille fréquentielle de la méthode</b>. Pour appliquer la propagation par bandes, le calcul a besoin d’une <b>entrée acoustique par bande</b> de la source <code>Lw,b</code>. Cette entrée peut provenir d’un spectre mesuré/importé ou d’un gabarit/fallback ajusté au niveau global opérationnel.</p>
                <p><b>Scénario opérationnel de ce calcul:</b> {acoustic_txt}.</p>
                <p><b>Équation générale par bande:</b></p>
                <div class='formula'>Lp,b = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b</div>
                <p><b>Sommation finale pondérée A:</b></p>
                <div class='formula'>LpA,total = 10·log10(Σ 10^((Lp,b + A_weight)/10))</div>
                <h4>0. Entrées réellement utilisées dans ce calcul</h4>
                <ul>
                    <li><b>Source acoustique :</b> <code>Lw,b</code> par bandes d’octave. S’il existe un spectre spécifique du groupe source, c’est l’entrée utilisée. Sinon, le plugin utilise une bibliothèque/un gabarit/un fallback et l’ajuste au niveau global opérationnel.</li>
                    <li><b>Niveau opérationnel global:</b> il provient d’un <b>LwA fixe</b> ou d’une <b>courbe acoustique LwA(ws)</b> selon le scénario sélectionné. Ce niveau global ne remplace pas les bandes : il fixe l’état opérationnel et le spectre fournit la répartition fréquentielle.</li>
                    <li><b>Géométrie :</b> coordonnées de source et de récepteur, hauteur du récepteur, hauteur effective de source et distance 3D.</li>
                    <li><b>Atmosphère:</b> température <b>T</b>, humidité relative <b>HR</b> et pression <b>P</b>.</li>
                    <li><b>Sol:</b> un <b>G global manuel</b> ou un <b>G_eff</b> dérivé depuis la couche d’occupation du sol.</li>
                    <li><b>Topographie:</b> MDT/DSM optionnel. Il n’affecte que le calcul de <b>Abar,b</b>.</li>
                </ul>
                <h4>1. Origine de chaque terme de l’équation</h4>
                <table>
                    <tr><th>Terme</th><th>Comment il est obtenu dans ce plugin</th></tr>
                    <tr><td><b>Lw,b</b></td><td>Entrée acoustique par bandes. Elle provient du spectre du groupe source (CSV, bibliothèque, gabarit ou fallback ajusté au niveau global). La courbe acoustique LwA(ws) ou le LwA fixe définit le niveau global opérationnel de l’éolienne, et le spectre par bandes répartit ce niveau entre les 8 bandes.</td></tr>
                    <tr><td><b>Adiv</b></td><td>Calculé à partir de la distance 3D source–récepteur.</td></tr>
                    <tr><td><b>Aatm,b</b></td><td>Calculé par bande avec une table de base d’absorption <code>α_ref(f)</code> et des corrections simplifiées de température, humidité relative et pression. L’implémentation actuelle utilise la formulation exacte du plugin : <code>α = α_ref(f)·corr_T·corr_HR·corr_P</code>.</td></tr>
                    <tr><td><b>Agr,b</b></td><td>Calculé comme effet de sol par régions. Le paramètre de sol utilisé est un <b>G unique par trajet</b> : manuel/global ou <b>G_eff</b> dérivé de la couche d’occupation du sol.</td></tr>
                    <tr><td><b>Abar,b</b></td><td>N’intervient que s’il existe un MDT/DSM et si un écran topographique est détecté. En l’absence de MDT ou d’obstacle pertinent, <b>Abar,b = 0</b>.</td></tr>
                </table>
                <h4>2. Entrée acoustique de la source et bandes</h4>
                <p>Dans ce moteur, le terme <code>Lw,b</code> est une <b>donnée d’entrée par bande</b>. Les <b>bandes d’octave</b> (63–8000 Hz) ne sont pas un résultat ISO ni un tableau calculé par le plugin : ce sont la <b>grille fréquentielle</b> sur laquelle la propagation est résolue.</p>
                <p>Le plugin combine deux éléments:</p>
                <ul>
                    <li><b>Courbe acoustique globale LwA(ws)</b>: fixe le <b>niveau opérationnel global</b> de l’éolienne pour la vitesse de vent ou le cas le plus défavorable sélectionné.</li>
                    <li><b>Spectre par bandes Lw,b</b>: répartit ce niveau global entre les 8 bandes et constitue l’entrée réelle utilisée dans l’équation par bandes.</li>
                </ul>
                <p>Ce spectre peut provenir d’un fichier spécifique du fabricant/de l’utilisateur ou d’un gabarit de référence. Si seule une courbe globale <code>LwA(ws)</code> est disponible, le plugin fixe d’abord le niveau global opérationnel <code>LwA_cible</code>, puis construit un spectre absolu par bandes à partir d’une forme spectrale de référence <code>S_b^ref</code>.</p>
                <p><b>Reconstruction mathématique des bandes lorsqu’il n’existe que LwA(ws):</b></p>
                <div class='formula'>Lw,b = S_b^ref + Δ</div>
                <div class='formula'>Δ = LwA_cible - 10·log10(Σ 10^((S_b^ref + A_weight,b)/10))</div>
                <p>Autrement dit : la courbe acoustique fournit le <b>niveau global opérationnel</b> et le gabarit/la bibliothèque fournit la <b>forme spectrale</b>. Le décalage <b>Δ</b> est calculé de façon à ce que, après pondération A et sommation énergétique des 8 bandes, le spectre reconstruit reproduise exactement le <code>LwA_cible</code> de la courbe importée.</p>
                {spectrum_detail_html}
                <h4>3. Divergence géométrique</h4>
                <div class='formula'>Adiv = 20·log10(d) + 11</div>
                <p>Représente la dispersion géométrique de l’onde sonore avec la distance 3D source–récepteur. Ici, <b>d</b> provient des coordonnées de l’éolienne et du récepteur avec leurs hauteurs d’évaluation.</p>
                <h4>4. Absorption atmosphérique simplifiée</h4>
                <div class='formula'>Aatm,b = α(f, T, HR, P) · d</div>
                <p>L’absorption atmosphérique est calculée par bande à partir d’un coefficient de référence et de trois facteurs correcteurs. La dépendance physique à la température, l’humidité relative et la pression <b>est bien représentée</b>, mais au moyen d’une <b>approximation simplifiée du plugin</b>, et non de la formulation analytique complète de l’ISO 9613-1.</p>
                <div class='formula'>α(f, T, HR, P) = α_ref(f) · corr_T · corr_HR · corr_P</div>
                <div class='formula'>corr_T = 1 + 0.01·(T - 15) &nbsp;&nbsp; ; &nbsp;&nbsp; corr_HR = 1 + 0.003·|HR - 50| &nbsp;&nbsp; ; &nbsp;&nbsp; corr_P = 101.325 / P</div>
                <p><b>Interprétation des corrections:</b> <b>T</b> est introduit en °C par rapport à une référence de 15 °C ; <b>HR</b> est comparée à une humidité optimale de référence de 50 % et la correction augmente lorsque l’on s’en éloigne ; <b>P</b> est introduite en kPa par rapport à une référence de 101,325 kPa avec une correction inverse. Ces facteurs ne modifient que le bloc atmosphérique <b>Aatm,b</b> : ils ne modifient ni l’émission de l’éolienne, ni l’effet de sol, ni le terme MDT/écran.</p>
                <table>
                    <tr><th>Bande [Hz]</th><th style='text-align:right;'>α_ref [dB/m]</th></tr>
                    {atm_rows}
                </table>
                <h4>5. Effet de sol par régions</h4>
                <div class='formula'>Agr,b = As + Am + Ar</div>
                <p>Le terme de sol se décompose en <b>As</b> (région de source), <b>Am</b> (région intermédiaire) et <b>Ar</b> (région du récepteur). Dans cette implémentation, trois paramètres de sol indépendants <code>Gs/Gm/Gr</code> ne sont pas utilisés ; un <b>G unique par trajet</b> est utilisé. Mathématiquement, le plugin applique :</p>
                <div class='formula'>As = G_eff·A_ground(h_s)</div>
                <div class='formula'>Am = G_eff·(1 - G_m)·A_ground(h_medio)</div>
                <div class='formula'>Ar = G_eff·A_ground(h_r)</div>
                <p>où <b>h_s</b> est la hauteur caractéristique de la source, <b>h_r</b> celle du récepteur, <b>h_moy</b> la hauteur moyenne du trajet et <b>G_m≈0</b> dans l’approximation actuelle pour des conditions favorables de propagation. Cette valeur unique de sol peut être :</p>
                <ul>
                    <li><b>G manuel/global</b>, si l’utilisateur fixe une valeur unique.</li>
                    <li><b>G_eff</b>, si une couche d’occupation du sol existe et si une moyenne pondérée par la longueur du trajet est calculée.</li>
                </ul>
                <div class='formula'>G_eff = (Σ G_i · L_i) / (Σ L_i)</div>
                <p><b>Signification physique de G:</b> représente le caractère acoustique du terrain et contrôle l’influence du sol sur la propagation. <b>G≈0</b> indique un sol dur (urbain, asphalte, roche), <b>G≈1</b> un sol meuble/poreux (agricole, prairie, forestier) et les valeurs intermédiaires représentent un terrain mixte.</p>
                <p><b>Ce que signifie « depuis couche » :</b> le plugin intersecte le trajet source–récepteur avec la couche d’occupation du sol, attribue une valeur <b>G_i</b> à chaque polygone intercepté et calcule un <b>G_eff</b> unique pour ce trajet. C’est cette valeur qui entre réellement dans <b>Agr,b</b> ; le <b>G global</b> affiché dans le rapport reste uniquement une valeur de secours.</p>
                <p><b>Convention du rapport :</b> <b>Agr,b</b> est affiché ici comme une <b>amplitude positive d’atténuation</b>. Dans l’équation principale, il est soustrait au niveau de source comme Adiv, Aatm et Abar.</p>
                <table>
                    <tr><th>Bande [Hz]</th><th style='text-align:right;'>Terme base A_ground(h)</th></tr>
                    {ground_rows}
                </table>
                <h4>6. Écran topographique avec MDT</h4>
                <p>Le MDT <b>ne modifie pas l’émission</b> de l’éolienne ni l’absorption atmosphérique. Sa fonction est de décrire la <b>géométrie réelle du trajet</b> et d’alimenter le terme <b>Abar,b</b>.</p>
                <ol>
                    <li><b>Profil du terrain :</b> le profil source–récepteur est extrait du MDT avec un échantillonnage adaptatif.</li>
                    <li><b>Ligne de visée:</b> la droite entre la hauteur effective de source et la hauteur du récepteur est construite. Si le terrain reste toujours en dessous, alors <b>Abar,b = 0</b>.</li>
                    <li><b>Obstacle dominant:</b> si une colline ou une crête dépasse, la hauteur au-dessus de la ligne de visée est calculée :</li>
                </ol>
                <div class='formula'>h_obs = z_terrain - z_LOS</div>
                <p>Lorsque <b>h_obs &gt; 0</b>, le relief coupe la vision directe et une atténuation supplémentaire par diffraction peut apparaître.</p>
                <ol start='4'>
                    <li><b>Géométrie réelle de l’obstacle :</b> le plugin utilise la position réelle de l’obstacle dominant et calcule <b>d1</b> (source → obstacle) et <b>d2</b> (obstacle → récepteur).</li>
                    <li><b>Activation conservatrice:</b> <b>Abar</b> n’est pas activé pour de petites irrégularités du MDT ; un seuil minimal lié à la résolution du raster est exigé.</li>
                    <li><b>Diffraction de type Fresnel:</b> avec cette géométrie, une différence de chemins et un nombre de Fresnel sont estimés :</li>
                </ol>
                <div class='formula'>δ ≈ 0.5·h_obs²·(1/d1 + 1/d2) &nbsp;&nbsp; ; &nbsp;&nbsp; C = (2·f·δ)/c</div>
                <p>Ce nombre est ensuite transformé en une atténuation <b>Abar,b</b> dépendante de la fréquence au moyen de l’approximation actuelle du plugin :</p>
                <div class='formula'>si C ≤ -2 → Abar = 0 &nbsp;&nbsp; ; &nbsp;&nbsp; -2 &lt; C ≤ 0 → Abar = 10·log10(3 + 20·C)</div>
                <div class='formula'>0 &lt; C ≤ 3.5 → Abar = 10·log10(3 + 80·C) &nbsp;&nbsp; ; &nbsp;&nbsp; C &gt; 3.5 → Abar = 10·log10(3 + 280·C)</div>
                <p>Dans l’implémentation actuelle, <b>Abar</b> est également limité à des valeurs raisonnables (plafonnement supérieur) afin d’éviter des suratténuations parasites. En l’absence de MDT ou d’obstacle pertinent, alors <b>Abar,b = 0</b>.</p>
                <h4>7. Pondération A utilisée à la fin</h4>
                <table>
                    <tr><th>Bande [Hz]</th><th style='text-align:right;'>A_weight [dB]</th></tr>
                    {octave_rows}
                </table>
                <p><b>Lecture du récepteur critique:</b> le tableau de la section du récepteur critique affiche des amplitudes d’atténuation pour la traçabilité. Le <b>niveau résultant</b> ne doit pas être interprété comme une soustraction directe depuis une seule éolienne : il est obtenu par sommation énergétique par bandes et par sommation des sources contributrices dans le rayon de calcul.</p>
            </div>
            {ground_expl_html}
            {mdt_expl_html}
            """
        else:
            if ground_mode == 'landuse':
                fast_ground_html = f"""
                <h4>3. Effet de sol simplifié avec occupation du sol</h4>
                <p>Dans le moteur rapide, le terme <b>Aground</b> reste empirique, mais le paramètre de sol peut provenir de la couche d’occupation du sol sous forme de <b>G_eff</b> par trajet :</p>
                <div class='formula'>G_eff = (Σ G_i · L_i) / (Σ L_i)</div>
                <div class='formula'>Aground = min(6, max(0, G_eff · 3·log10(1 + d_xy/100) · 1/(1 + (h_s + h_r)/80)))</div>
                <p>Ce <b>G_eff</b> est ensuite utilisé dans la correction simplifiée du terrain du moteur rapide. La valeur globale <b>G = {g:.2f}</b> reste uniquement une valeur de secours si la couche ne fournit pas d’information valide.</p>
                <p><b>Couche utilisée:</b> {landuse_layer_name or 'sans nom'} · <b>G_eff moyen:</b> {float(g_eff_stats.get('mean', g)):.2f} · <b>G_eff du récepteur critique:</b> {float(g_eff_stats.get('critical', g)):.2f}</p>
                """
            else:
                fast_ground_html = f"""
                <h4>3. Effet de sol simplifié</h4>
                <p>Le terme <b>Aground</b> est une correction empirique du terrain contrôlée par un seul paramètre manuel :</p>
                <div class='formula'>G = {g:.2f}</div>
                <div class='formula'>Aground = min(6, max(0, G · 3·log10(1 + d_xy/100) · 1/(1 + (h_s + h_r)/80)))</div>
                <p>Dans ce calcul, aucun G_eff n’a été dérivé depuis une couche d’occupation du sol. Ici, <b>d_xy</b> est la distance horizontale, <b>h_s</b> la hauteur de source et <b>h_r</b> la hauteur du récepteur.</p>
                """

            fast_mdt_html = """
                <h4>4. MDT / topographie</h4>
                <p>Dans le moteur rapide, le MDT n’introduit pas de terme explicite d’écran topographique. Même si une couche de relief existe dans le projet, ce mode ne calcule pas <b>Abar</b>, n’extrait pas de ligne de visée et n’applique pas de diffraction ; la physique se base donc uniquement sur <b>LwA</b>, <b>Adiv</b>, <b>Aatm = α·d</b> et la correction empirique de terrain <b>Aground</b>.</p>
            """

            equations_detail_html = f"""
            <div class='card'>
                <h3>📘 Développement physique détaillé du moteur rapide</h3>
                <div class='formula'>Lp = LwA - Adiv - Aatm - Aground</div>
                <p>Le moteur rapide travaille avec un seul niveau global <b>LwA</b> par groupe source. Il est conçu pour le criblage, les cartes rapides et les comparaisons rapides, en sacrifiant le détail spectral au profit de la vitesse. Dans ce mode, il n’y a <b>pas de propagation par bandes</b> ni de terme explicite d’écran topographique.</p>
                <p><b>Scénario opérationnel de ce calcul:</b> {acoustic_txt}.</p>
                <h4>0. Entrées réellement utilisées dans ce calcul</h4>
                <ul>
                    <li><b>Source acoustique :</b> un seul niveau global <b>LwA</b> par groupe source.</li>
                    <li><b>Niveau opérationnel global:</b> provient d’un <b>LwA fixe</b> ou d’une <b>courbe acoustique LwA(ws)</b> pour la vitesse ou le cas le plus défavorable sélectionnés.</li>
                    <li><b>Géométrie :</b> coordonnées de source et de récepteur, hauteur du récepteur, hauteur effective de source et distance 3D.</li>
                    <li><b>Atmosphère:</b> dans ce mode, T/HR/P ne sont pas utilisés ; l’absorption est résumée par un coefficient unique <b>α</b>.</li>
                    <li><b>Sol:</b> un <b>G global manuel</b> ou un <b>G_eff</b> dérivé depuis la couche d’occupation du sol.</li>
                    <li><b>Topographie :</b> le MDT n’entre pas comme écran explicite dans ce mode.</li>
                </ul>
                <h4>1. Origine de chaque terme de l’équation</h4>
                <table>
                    <tr><th>Terme</th><th>Comment il est obtenu dans ce plugin</th></tr>
                    <tr><td><b>LwA</b></td><td>Entrée globale de la source. Elle provient d’une valeur fixe par groupe ou d’une courbe acoustique <code>LwA(ws)</code> pour la vitesse/le pire cas sélectionné.</td></tr>
                    <tr><td><b>Adiv</b></td><td>Calculé à partir de la distance 3D source–récepteur.</td></tr>
                    <tr><td><b>Aatm</b></td><td>Calculé avec un coefficient constant unique <code>α</code> multiplié par la distance.</td></tr>
                    <tr><td><b>Aground</b></td><td>Correction empirique de l’effet de sol. Le paramètre de sol peut être un <b>G global manuel</b> ou un <b>G_eff</b> dérivé de la couche d’occupation du sol.</td></tr>
                </table>
                <h4>2. Divergence géométrique</h4>
                <div class='formula'>Adiv = 20·log10(d) + 11</div>
                <p>Représente la dispersion géométrique de l’onde sonore avec la distance 3D source–récepteur.</p>
                <h4>3. Absorption atmosphérique simplifiée</h4>
                <div class='formula'>Aatm = α · d</div>
                <p>Dans ce calcul, <b>α = {alpha:.4f} dB/m</b> a été utilisé. Dans le moteur rapide, l’absorption atmosphérique est résumée par un seul coefficient constant ; <b>T</b>, <b>HR</b> et <b>P</b> <b>n’entrent donc pas explicitement</b> dans le calcul. C’est l’une des simplifications clés par rapport au mode ISO-aligned.</p>
                {fast_ground_html}
                {fast_mdt_html}
                <h4>5. Ce que ce mode ne fait pas</h4>
                <p>Le moteur rapide ne travaille pas par bandes, ne calcule pas <b>Lw,b</b>, n’introduit pas <b>Abar</b> et n’extrait ni ligne de visée ni diffraction depuis le MDT. Il est donc adapté au criblage et aux comparaisons rapides, mais pas à l’analyse spectrale détaillée.</p>
            </div>
            """

        # === CALCULAR TASAS Y FECHA ===
        coverage_rate = (100.0 * n_with / n_receivers) if n_receivers else 0
        exceed_rate = (100.0 * n_exceed / n_with) if n_with else 0
        comply_rate = 100.0 - exceed_rate
        from datetime import datetime
        now = datetime.now()

        # === BANNER DE ALCANCE (lo primero que se lee, antes de cualquier cifra) ===
        if engine == 'iso_aligned':
            scope_what_is = "une évaluation acoustique préliminaire alignée sur la méthodologie ISO 9613-2, destinée à la conception, à la comparaison d’alternatives et au criblage des récepteurs sensibles."
            scope_what_not = "ce n’est pas un rapport acoustique certifié et ne remplace pas une étude réglementaire définitive réalisée avec un logiciel commercial validé."
            scope_simpl_items = [
                "Absorption atmosphérique Aatm via une table de référence avec corrections simplifiées de température, humidité et pression, et non la formulation analytique complète de l’ISO 9613-1.",
                "Sans correction météorologique de long terme Cmet.",
                "Diffraction topographique d’un obstacle dominant unique : sans diffraction latérale ni écrans multiples.",
                "Résolution spectrale en 8 bandes d’octave de 63 à 8000 Hz, pas en tiers d’octave.",
                "Directivité de source Dc supposée égale à 0 dB.",
            ]
        else:
            scope_what_is = "une estimation rapide de criblage pour des cartes agiles et la comparaison d’alternatives d’implantation."
            scope_what_not = "ce n’est ni un calcul spectral détaillé ni un rapport réglementaire ; pour les récepteurs proches de la limite, il convient de recalculer en mode ISO-aligned."
            scope_simpl_items = [
                "Sans propagation par bandes d’octave.",
                "Absorption atmosphérique résumée par un seul coefficient alpha constant.",
                "Sans écran topographique Abar depuis le MDT.",
                "Effet de sol via une correction empirique simplifiée.",
            ]
        scope_reco = "Pour les décisions réglementaires critiques, validez les résultats avec des mesures de terrain ou un logiciel commercial certifié."
        scope_items_html = ''.join(f"<li>{it}</li>" for it in scope_simpl_items)
        scope_banner_html = f"""
        <div style='background:#fff8e1;border:2px solid #f0ad4e;border-left:8px solid #f0ad4e;border-radius:8px;padding:18px 22px;margin:0 0 26px 0;'>
            <h3 style='margin:0 0 10px 0;color:#7a5b00;'>⚠️ Portée de ce rapport — à lire avant d’utiliser les résultats</h3>
            <p style='margin:6px 0;'><b>Ce que c’est :</b> {scope_what_is}</p>
            <p style='margin:6px 0;'><b>Ce que ce n’est pas :</b> {scope_what_not}</p>
            <p style='margin:10px 0 4px 0;'><b>Simplifications appliquées dans ce mode :</b></p>
            <ul style='margin:4px 0 10px 0;'>{scope_items_html}</ul>
            <p style='margin:6px 0 0 0;'><b>Recommandation :</b> {scope_reco}</p>
        </div>
        """

        # === GLOSARIO DE SÍMBOLOS (decodifica fórmulas y tablas en un solo sitio) ===
        glossary_rows = [
            ("LwA", "Niveau de puissance acoustique pondéré A de la source, en dB(A)."),
            ("Lw,b", "Puissance acoustique de la source par bande d’octave, en dB."),
            ("S_b^ref", "Forme spectrale de référence par bande utilisée comme gabarit, en dB."),
            ("A_weight,b", "Pondération A appliquée à chaque bande d’octave, en dB."),
            ("Δ", "Décalage global appliqué au gabarit spectral pour reproduire le LwA cible, en dB."),
            ("LpA", "Niveau de pression acoustique pondéré A résultant au récepteur, en dB(A)."),
            ("Adiv", "Atténuation par divergence géométrique avec la distance, en dB."),
            ("Aatm", "Atténuation due à l’absorption atmosphérique de l’air, en dB."),
            ("Agr", "Atténuation due à l’effet de sol, en dB."),
            ("Abar", "Atténuation due à l’écran topographique, uniquement en mode ISO avec MDT, en dB."),
            ("d", "Distance tridimensionnelle entre source et récepteur, en mètres."),
            ("G / G_eff", "Facteur de sol de 0 (dur) à 1 (meuble) et sa valeur effective par trajet."),
            ("Cmet", "Correction météorologique de long terme, non appliquée dans ce plugin."),
            ("Dc", "Correction de directivité de la source, supposée égale à 0 dB."),
        ]
        glossary_rows_html = ''.join(f"<tr><td><b>{sym}</b></td><td>{desc}</td></tr>" for sym, desc in glossary_rows)
        glossary_html = f"""
        <div class='card card-info'>
            <h3>📖 Glossaire des symboles</h3>
            <p>Définition compacte des symboles qui apparaissent dans les formules et tableaux de ce rapport.</p>
            <table>
                <tr><th>Symbole</th><th>Signification</th></tr>
                {glossary_rows_html}
            </table>
        </div>
        """

        html = f"""
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #212529;
            }}
            h1, h2, h3 {{
                color: #1e3a5f;
                font-weight: 600;
                margin-top: 24px;
                margin-bottom: 12px;
            }}
            h2 {{
                border-left: 4px solid #4a90d9;
                padding-left: 12px;
            }}
            .card {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
                margin: 16px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            .card-success {{
                border-left: 5px solid #28a745;
            }}
            .card-danger {{
                border-left: 5px solid #dc3545;
            }}
            .card-info {{
                border-left: 5px solid #4a90d9;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin: 20px 0;
            }}
            .metric {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                text-align: center;
                border-top: 4px solid #4a90d9;
            }}
            .metric-value {{
                font-size: 32px;
                font-weight: 700;
                color: #1e3a5f;
                margin: 8px 0;
            }}
            .metric-label {{
                font-size: 14px;
                color: #343a40;
                font-weight: 500;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 16px 0;
                font-size: 13px;
            }}
            th {{
                background: #1e3a5f;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }}
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e9ecef;
            }}
            tr:nth-child(even) {{
                background: #f8f9fa;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
            }}
            .badge-success {{
                background: #28a745;
                color: white;
            }}
            .badge-danger {{
                background: #dc3545;
                color: white;
            }}
            .formula {{
                background: #f1f3f5;
                border: 1px solid #dee2e6;
                padding: 16px;
                margin: 12px 0;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
            }}
            .disclaimer {{
                background: #fff3cd;
                border-left: 5px solid #ffc107;
                padding: 16px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .note {{
                background: #fff8e1;
                border-left: 4px solid #f0ad4e;
                padding: 10px 12px;
                margin: 10px 0;
                border-radius: 4px;
                color: #5f4300;
            }}
            ol {{
                margin: 12px 0;
                padding-left: 26px;
            }}
            ol li {{
                margin: 8px 0;
            }}
            ul {{
                margin: 12px 0;
                padding-left: 24px;
            }}
            li {{
                margin: 6px 0;
            }}
        </style>
        
        <div style='background: linear-gradient(135deg, #1e3a5f 0%, #2c5f8d 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px;'>
            <h1 style='color: white; margin: 0 0 8px 0; font-size: 32px;'>📊 RAPPORT TECHNIQUE D’IMPACT ACOUSTIQUE</h1>
            <p style='font-size: 16px; opacity: 0.9; margin: 0;'>Évaluation du bruit généré par les éoliennes</p>
            <p style='font-size: 14px; opacity: 0.85; margin-top: 12px;'>📅 {now.strftime('%d/%m/%Y - %H:%M:%S')}</p>
        </div>
        
        {scope_banner_html}
        
        <h2>1. RÉSUMÉ EXÉCUTIF</h2>
        
        <div class='metrics-grid'>
            <div class='metric'>
                <div class='metric-value'>{n_sources}</div>
                <div class='metric-label'>Éoliennes</div>
            </div>
            <div class='metric'>
                <div class='metric-value'>{n_receivers}</div>
                <div class='metric-label'>Récepteurs évalués</div>
            </div>
            <div class='metric'>
                <div class='metric-value'>{max_noise:.1f}</div>
                <div class='metric-label'>Niveau maximal (dB(A))</div>
            </div>
        </div>
        
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px;'>
            <div class='card card-{'success' if coverage_rate > 80 else 'info'}'>
                <h3>📍 Couverture de l’analyse</h3>
                <p><strong>{n_with} récepteurs</strong> dans le rayon<br>
                <strong>{coverage_rate:.1f}%</strong> de couverture<br>
                {n_without} récepteurs hors rayon</p>
            </div>
            
            <div class='card card-{'success' if comply_rate > 90 else 'danger' if comply_rate < 50 else 'info'}'>
                <h3>✓ Conformité réglementaire</h3>
                <p><strong>{n_exceed} récepteurs</strong> dépassent les limites<br>
                <strong>{comply_rate:.1f}%</strong> de conformité sur les récepteurs couverts<br>
                Limite : {float(limit_stats.get('min',45)):.1f}–{float(limit_stats.get('max',45)):.1f} dB(A)</p>
            </div>
        </div>
        
        <div class='card card-info'>
            <h3>🎯 Méthodologie de calcul</h3>
            <p><b>Moteur utilisé :</b> {engine_label}</p>
            <p><b>Groupes source acoustiques :</b> {n_models} modèle(s) d’éolienne</p>
            <p><b>Méthode :</b> {'Propagation par bandes d’octave selon la méthodologie ISO-aligned' if engine == 'iso_aligned' else 'Calcul acoustique simplifié pour le criblage'}</p>
            <p><b>Carte raster :</b> {grid_txt}</p>
        </div>

        <h2>2. COMMENT LE RÉSULTAT A ÉTÉ GÉNÉRÉ</h2>
        {methodology_flow_html}
        
        <h2>3. RÉCEPTEUR CRITIQUE</h2>
        {crit_html}
        
        <div class='card'>
            <h3>📊 Statistiques des atténuations (récepteurs couverts)</h3>
        <p style='margin: 6px 0 10px 0; color:#495057;'><i>Les amplitudes brutes d’atténuation sont affichées (et non le signe algébrique dans l’équation). Pour Abar, le maximum parmi les éoliennes contributrices de chaque récepteur est utilisé, pas uniquement le trajet dominant.</i></p>
            <table>
                <tr>
                    <th>Terme</th>
                    <th style='text-align: right;'>Moyenne [dB]</th>
                    <th style='text-align: right;'>Maximum [dB]</th>
                </tr>
                <tr>
                    <td><b>Adiv</b> (divergence géométrique)</td>
                    <td style='text-align: right;'>{float(adiv_stats.get('mean',0.0)):.2f}</td>
                    <td style='text-align: right;'>{float(adiv_stats.get('max',0.0)):.2f}</td>
                </tr>
                <tr>
                    <td><b>Aatm</b> (absorption atmosphérique)</td>
                    <td style='text-align: right;'>{float(aatm_stats.get('mean',0.0)):.2f}</td>
                    <td style='text-align: right;'>{float(aatm_stats.get('max',0.0)):.2f}</td>
                </tr>
                <tr>
                    <td><b>Agr/Aground</b> (effet de sol)</td>
                    <td style='text-align: right;'>{float(aground_stats.get('mean',0.0)):.2f}</td>
                    <td style='text-align: right;'>{float(aground_stats.get('max',0.0)):.2f}</td>
                </tr>
                <tr>
                    <td><b>Abar</b> (maximum parmi les contributeurs)</td>
                    <td style='text-align: right;'>{float(abar_stats.get('mean',0.0)):.2f}</td>
                    <td style='text-align: right;'>{float(abar_stats.get('max',0.0)):.2f}</td>
                </tr>
            </table>
        </div>
        
        <h2>4. CONFIGURATION ET PARAMÈTRES</h2>
        
        <div class='card'>
            <h3>⚙️ Équation utilisée</h3>
            <div class='formula'>{equation}</div>
            <p><em>{interpretation}</em></p>
        </div>
        
        <div class='card'>
            <h3>📋 Paramètres du calcul</h3>
            <ul>{''.join(param_lines)}</ul>
            {pressure_warning_html}
            <p><b>Trajets avec G différent du global :</b> {int(ground_diag.get('from_landuse_count',0))} ({float(ground_diag.get('from_landuse_pct',0.0)):.1f}%)</p>
        </div>
        
        <div class='card'>
            <h3>✓ Termes actifs</h3>
            <ul>{''.join(term_lines)}</ul>
        </div>
        
        <h2>5. PHYSIQUE DÉTAILLÉE ET TRAÇABILITÉ DU CALCUL</h2>
        {glossary_html}
        {equations_detail_html}
        
        <h2>6. GROUPES SOURCE ACOUSTIQUES</h2>
        <div class='card'>
            <h3>⚡ LwA effectif par groupe</h3>
            <ul>{''.join(eff_lines) if eff_lines else '<li>Non disponible</li>'}</ul>
        </div>
        
        <h2>7. DISTRIBUTION PAR TYPE DE RÉCEPTEUR</h2>
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px;'>
            <div class='card'>
                <h3>📍 Récepteurs par catégorie</h3>
                <ul>{rec_types_html if rec_types_html else '<li>Non disponible</li>'}</ul>
            </div>
            <div class='card'>
                <h3>✓ Conformité par catégorie</h3>
                <ul>{compliance_html if compliance_html else '<li>Non disponible</li>'}</ul>
            </div>
        </div>
        
        <div class='disclaimer'>
            <strong>⚠️ Limites et recommandations</strong>
            <p><b>Moteur rapide :</b> Adapté au criblage préliminaire et aux cartes agiles.</p>
            <p><b>Moteur ISO-aligned :</b> Adapté aux études techniques préliminaires, aux comparaisons et à l’itération de conception.</p>
            <p><b>Simplifications connues :</b> Aatm simplifié (tables + corrections) ; Agr et Abar avec approximations de base ; directivité Dc supposée égale à 0 dB ; Cmet/correction météorologique de long terme non appliquée.</p>
            <p><b>Modèles multiples :</b> pris en charge au moyen de couches/groupes source indépendants. Mélanger plusieurs modèles dans une seule couche via attributs n’est pas activé dans cette version expérimentale.</p>
            <p><b>Raster ISO + MDT :</b> utilise la même logique d’écran topographique que les récepteurs ponctuels, mais peut être coûteux sur de grandes cartes.</p>
            <p><b>Recommandation :</b> Pour les études réglementaires critiques, valider avec des mesures ou un logiciel commercial certifié.</p>
        </div>
        """
        if current_language() != "fr":
            html = translate_html(html)
            if str(current_language()).lower().startswith("de"):
                html = _cleanup_german_noise_html(html)
        self.page_summary.document().setHtml(html)

    def _fill_models(self):
        model_diag = self._res.get("model_diag", {}) or {}
        rows: List[tuple] = []
        for name, d in model_diag.items():
            dia = d.get("diameter")
            hh = d.get("hub_height")
            mode = str(d.get('acoustic_mode') or 'fixed').lower()
            if mode == 'curve' and str(d.get('curve_path') or '').strip():
                note = str(d.get('curve_note') or 'Courbe acoustique active')
            else:
                note = 'LwA fixe par groupe de source acoustique'
            rows.append((str(name), int(d.get("count", 0)), float(d.get("lwa", 0.0)), hh, dia, note))
        self.tbl_models.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [
                row[0], str(row[1]), f"{row[2]:.1f}",
                "-" if row[3] is None or (isinstance(row[3], float) and not (row[3] == row[3])) else f"{float(row[3]):.1f}",
                "-" if row[4] is None or (isinstance(row[4], float) and not (row[4] == row[4])) else f"{float(row[4]):.1f}",
                row[5],
            ]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                self.tbl_models.setItem(r, c, it)
        self.tbl_models.resizeColumnsToContents()

    def _feature_value_last(self, feat, field_name, default=""):
        """Return the last field named ``field_name`` from a QgsFeature.

        Receiver input layers can already contain generic names such as
        ``state`` or ``limit_dba``. QGIS name lookup returns the first match,
        which can silently pick the original receiver attribute instead of the
        computed noise output. The computed fields are appended at the end, so
        use the last matching index for UI/export fallbacks.
        """
        try:
            fields = feat.fields()
            idx = -1
            for i in range(fields.count()):
                if fields.at(i).name() == field_name:
                    idx = i
            if idx >= 0:
                return feat.attribute(idx)
        except Exception:
            pass
        try:
            return feat[field_name]
        except Exception:
            return default

    def _fill_top_receivers(self):
        # Prefer named payload rows. They are created by the engine with stable
        # semantic keys and avoid both duplicate input-field names and raw
        # attribute-order shifts in the QGIS memory layer.
        payload_rows = self._payload_top_receivers()[:15]
        feats = []
        if not payload_rows:
            layer = self._res.get("result_layer")
            if isinstance(layer, QgsVectorLayer):
                try:
                    for f in layer.getFeatures():
                        feats.append(f)
                except Exception:
                    feats = []
            def keyf(f):
                try:
                    return float(self._feature_value_last(f, "noise_dba", 0.0) or 0.0)
                except Exception:
                    return -1e9
            feats = sorted(feats, key=keyf, reverse=True)[:15]
        row_count = len(payload_rows) if payload_rows else len(feats)
        self.tbl_top.setRowCount(row_count)
        iterable = payload_rows if payload_rows else feats
        for r, f in enumerate(iterable):
            if isinstance(f, dict):
                clean_row = self._clean_receiver_row(f)
            else:
                raw = {"fid": f.id()}
                for key in CONSULTANCY_RECEIVER_KEYS:
                    raw[key] = self._feature_value_last(f, key, "")
                clean_row = self._clean_receiver_row(raw)
            for c, header in enumerate(CONSULTANCY_RECEIVER_HEADERS):
                v = str(clean_row.get(header, ""))
                it = QtWidgets.QTableWidgetItem(v)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                self.tbl_top.setItem(r, c, it)
        self.tbl_top.resizeColumnsToContents()


    def _fill_mdt_screening(self):
        """Fill a DEM/MDT audit table sorted by criblage, not by noise level."""
        rows = [dict(r) for r in self._payload_receiver_rows() if isinstance(r, dict)]

        def _f(d, key, default=0.0):
            try:
                v = d.get(key, default)
                if v is None or str(v).strip().lower() in ('', 'none', 'nan'):
                    return default
                return float(v)
            except Exception:
                return default

        # Keep covered receivers first.  Sort by active Abar, then by largest
        # detected obstacle, then by acoustic level.  This makes receivers with
        # strong terrain screening visible even if their total sound level is low.
        covered = [r for r in rows if _f(r, 'n_src', 0.0) > 0.0]
        covered.sort(
            key=lambda d: (
                _f(d, 'abar_max_db', 0.0),
                _f(d, 'maxobs_h', 0.0),
                _f(d, 'noise_dba', -1.0e99),
            ),
            reverse=True,
        )
        visible = covered[:30]

        keys = [
            'rec_id', 'noise_dba', 'n_src', 'abar_max_db', 'abar_ew_db',
            'abar_screen_n', 'abar_state', 'abar_db', 'maxab_src',
            'maxab_state', 'maxab_obs_h', 'maxab_thr', 'maxab_d1',
            'maxab_d2', 'maxobs_src', 'maxobs_state', 'maxobs_h',
            'maxobs_thr', 'maxobs_d1', 'maxobs_d2', 'rec_z_m',
            'rec_h_m', 'rec_ac_z_m', 'src_z_m', 'src_ac_z_m',
            'maxab_src_z', 'maxab_src_ac_z',
        ]

        self.tbl_mdt.setRowCount(len(visible))
        for r, row in enumerate(visible):
            for c, k in enumerate(keys):
                val = row.get(k, "")
                if k == "rec_id" and (val is None or str(val).strip() == ""):
                    val = row.get("fid", "")
                if val is None or str(val).strip().lower() in ('none', 'nan'):
                    v = "N/A"
                elif isinstance(val, float):
                    v = f"{val:.2f}"
                else:
                    v = str(val)
                it = QtWidgets.QTableWidgetItem(v)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                self.tbl_mdt.setItem(r, c, it)
        self.tbl_mdt.resizeColumnsToContents()


    def _format_receiver_value(self, key: str, val) -> str:
        if key == "rec_id" and (val is None or str(val).strip() == ""):
            return ""
        if key == "exceeds":
            try:
                return "oui" if int(float(val or 0)) == 1 else "non"
            except Exception:
                txt = str(val or "").strip().lower()
                return "oui" if txt in ("true", "yes", "sí", "si", "oui", "1") else "non"
        if val is None:
            return "N/A"
        txt = str(val).strip()
        if txt.lower() in ("", "none", "nan", "n/a"):
            return "N/A"
        try:
            fval = float(txt.replace(",", "."))
        except Exception:
            return txt
        if not (fval == fval):
            return "N/A"
        if key in ("n_src",):
            return str(int(round(fval)))
        if key in ("noise_dba", "limit_dba", "margin_db", "src_lwa", "adiv_db", "aatm_db", "aground_db", "abar_max_db", "ground_g"):
            return f"{fval:.2f}"
        if key in ("near_m", "rec_h_m", "rec_z_m", "rec_ac_z_m"):
            return f"{fval:.1f}"
        return f"{fval:.2f}"


    def _clean_receiver_row(self, row: Dict[str, object]) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for key, label in CONSULTANCY_RECEIVER_COLUMNS:
            val = row.get(key, "") if isinstance(row, dict) else ""
            if key == "rec_id" and (val is None or str(val).strip() == "") and isinstance(row, dict):
                val = row.get("fid", "")
            out[label] = self._format_receiver_value(key, val)
        return out


    def _receiver_rows_for_export(self) -> List[Dict[str, object]]:
        rows = self._res.get('receiver_rows') or []
        if not rows:
            layer = self._res.get('result_layer')
            if isinstance(layer, QgsVectorLayer):
                rows = list(self._iter_layer_dicts(layer))
        if not rows:
            rows = self._payload_top_receivers()
        return [self._clean_receiver_row(r) for r in rows if isinstance(r, dict)]



    def _write_layer_csv(self, layer: QgsVectorLayer, path: str):
        field_names = [f.name() for f in layer.fields()]
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.writer(fh, delimiter=';')
            writer.writerow(['fid'] + field_names)
            for feat in layer.getFeatures():
                row = [feat.id()]
                for name in field_names:
                    try:
                        val = feat[name]
                    except Exception:
                        val = ''
                    row.append(val)
                writer.writerow(row)

    def _iter_layer_dicts(self, layer: QgsVectorLayer):
        field_names = [f.name() for f in layer.fields()]
        for feat in layer.getFeatures():
            row = {"fid": feat.id()}
            for name in field_names:
                try:
                    row[name] = feat[name]
                except Exception:
                    row[name] = ""
            yield row

    def _collect_exceedance_rows(self):
        rows_source = self._res.get('receiver_rows') or []
        layer = self._res.get('result_layer')
        if not rows_source and isinstance(layer, QgsVectorLayer):
            rows_source = list(self._iter_layer_dicts(layer))
        rows = []
        for row in rows_source or []:
            try:
                exceeds = int(float(row.get('exceeds') or 0))
            except Exception:
                exceeds = 0
            if exceeds == 1:
                rows.append(self._clean_receiver_row(row))
        return rows

    def _write_rows_csv(self, rows, path: str):
        rows = list(rows or [])
        headers = []
        for r in rows:
            for k in r.keys():
                if k not in headers:
                    headers.append(k)
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.writer(fh, delimiter=';')
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(h, '') for h in headers])

    def _table_headers(self, table: QtWidgets.QTableWidget) -> List[str]:
        headers: List[str] = []
        for c in range(table.columnCount()):
            item = table.horizontalHeaderItem(c)
            headers.append(item.text() if item is not None else f"col_{c+1}")
        return headers

    def _collect_table_rows(self, table: QtWidgets.QTableWidget) -> List[Dict[str, object]]:
        headers = self._table_headers(table)
        rows: List[Dict[str, object]] = []
        for r in range(table.rowCount()):
            row: Dict[str, object] = {}
            has_value = False
            for c, h in enumerate(headers):
                item = table.item(r, c)
                text = item.text() if item is not None else ""
                if str(text).strip():
                    has_value = True
                row[h] = text
            if has_value:
                rows.append(row)
        return rows

    def _write_table_csv(self, table: QtWidgets.QTableWidget, path: str):
        headers = self._table_headers(table)
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.writer(fh, delimiter=';')
            writer.writerow(headers)
            for row in self._collect_table_rows(table):
                writer.writerow([row.get(h, '') for h in headers])

    def _append_table_sheet(self, wb, title: str, table: QtWidgets.QTableWidget):
        ws = wb.create_sheet(title=title[:31] or 'Hoja')
        headers = self._table_headers(table)
        ws.append(headers)
        rows = self._collect_table_rows(table)
        if not rows:
            ws.append(['sin_datos'])
        else:
            for row in rows:
                ws.append([row.get(h, '') for h in headers])
        try:
            for idx, h in enumerate(headers, start=1):
                width = max(len(str(h)), max((len(str(r.get(h, ''))) for r in rows), default=0))
                ws.column_dimensions[chr(64 + idx) if idx <= 26 else ws.cell(row=1, column=idx).column_letter].width = min(max(width + 2, 10), 45)
        except Exception:
            pass

    def _append_sheet(self, wb, title: str, rows):
        ws = wb.create_sheet(title=title[:31] or 'Hoja')
        rows = list(rows or [])
        headers = []
        for r in rows:
            for k in r.keys():
                if k not in headers:
                    headers.append(k)
        if not headers:
            ws.append(['sin_datos'])
            ws.append([''])
            return
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, '') for h in headers])
        try:
            for idx, h in enumerate(headers, start=1):
                width = max(len(str(h)), max((len(str(r.get(h, ''))) for r in rows), default=0))
                ws.column_dimensions[chr(64 + idx) if idx <= 26 else ws.cell(row=1, column=idx).column_letter].width = min(max(width + 2, 10), 40)
        except Exception:
            pass

    def _export_summary(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, ('Zusammenfassung exportieren' if str(current_language()).lower().startswith('de') else 'Exporter le résumé'), os.path.expanduser('~/schall_zusammenfassung.html' if str(current_language()).lower().startswith('de') else '~/bruit_resume.html'), ('HTML (*.html);;Text (*.txt)' if str(current_language()).lower().startswith('de') else 'HTML (*.html);;Texte (*.txt)'))
        if not path:
            return
        try:
            if path.lower().endswith('.txt'):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(self.page_summary.toPlainText())
            else:
                if not path.lower().endswith('.html'):
                    path += '.html'
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(self.page_summary.toHtml())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, ('Zusammenfassung exportieren' if str(current_language()).lower().startswith('de') else 'Exporter le résumé'), (f'Die Zusammenfassung konnte nicht exportiert werden:\n{e}' if str(current_language()).lower().startswith('de') else f'Impossible d’exporter le résumé :\n{e}'))

    def _export_receivers_csv(self):
        rows = self._receiver_rows_for_export()
        if not rows:
            QtWidgets.QMessageBox.information(self, 'Exporter les récepteurs', 'Aucune ligne de récepteurs à exporter.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter les récepteurs CSV', os.path.expanduser('~/bruit_recepteurs.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_rows_csv(rows, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter les récepteurs', f'Impossible d’exporter le CSV :\n{e}')

    def _write_dict_rows_csv(self, rows, path: str):
        # Deterministic CSV for dictionaries. Keeps debug exports independent
        # from visible table columns and QGIS field ordering.
        keys = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            for k in row.keys():
                if k not in keys:
                    keys.append(k)
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.writer(fh, delimiter=';')
            writer.writerow(keys)
            for row in rows or []:
                writer.writerow([row.get(k, '') if isinstance(row, dict) else '' for k in keys])


    def _export_path_diagnostics_csv(self):
        rows = self._res.get('path_diagnostics') or []
        if not rows:
            QtWidgets.QMessageBox.information(self, 'Exporter le diagnostic MDT', 'Aucun diagnostic par paires source-récepteur n’est disponible. Recalculez avec le moteur ISO-aligned et des sources dans le rayon. Ce CSV permet d’auditer chaque éolienne par rapport à chaque récepteur.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter le diagnostic MDT par paires CSV', os.path.expanduser('~/bruit_diagnostic_mdt_paires.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_dict_rows_csv(rows, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter le diagnostic MDT', f'Impossible d’exporter le CSV de diagnostic MDT :\n{e}')


    def _export_top_receivers_csv(self):
        if self.tbl_top.rowCount() <= 0:
            QtWidgets.QMessageBox.information(self, 'Exporter le principaux récepteurs', 'Aucune ligne de principaux récepteurs à exporter.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter le principaux récepteurs CSV', os.path.expanduser('~/bruit_top_recepteurs.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_table_csv(self.tbl_top, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter le principaux récepteurs', f'Impossible d’exporter le CSV du principaux récepteurs :\n{e}')

    def _export_mdt_screening_csv(self):
        if self.tbl_mdt.rowCount() <= 0:
            QtWidgets.QMessageBox.information(self, 'Exporter le criblage MDT', 'Aucune ligne de criblage MDT à exporter.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter le criblage MDT CSV', os.path.expanduser('~/bruit_criblage_mdt_recepteurs.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_table_csv(self.tbl_mdt, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter le criblage MDT', f'Impossible d’exporter le CSV de criblage MDT :\n{e}')


    def _export_sources_csv(self):
        layer = self._res.get('sources_layer')
        if not isinstance(layer, QgsVectorLayer):
            QtWidgets.QMessageBox.information(self, 'Exporter les groupes source', 'Aucune couche de sources à exporter.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter les groupes source CSV', os.path.expanduser('~/bruit_sources.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_layer_csv(layer, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter les groupes source', f'Impossible d’exporter le CSV :\n{e}')

    def _export_exceedances_csv(self):
        rows = self._collect_exceedance_rows()
        if not rows:
            QtWidgets.QMessageBox.information(self, 'Exporter les dépassements', 'Aucun récepteur ne dépasse la limite dans ce calcul.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter les dépassements CSV', os.path.expanduser('~/bruit_depassements.csv'), 'CSV (*.csv)')
        if not path:
            return
        try:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self._write_rows_csv(rows, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter les dépassements', f'Impossible d’exporter le CSV :\n{e}')

    def _export_package_xlsx(self):
        if Workbook is None:
            QtWidgets.QMessageBox.information(self, 'Exporter le paquet XLSX', 'openpyxl n’est pas disponible dans cet environnement QGIS. Utilisez les exportations CSV ou installez openpyxl.')
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exporter le paquet XLSX', os.path.expanduser('~/bruit_paquet.xlsx'), 'Excel (*.xlsx)')
        if not path:
            return
        try:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            wb = Workbook()
            ws0 = wb.active
            ws0.title = 'Résumé'
            plain = self.page_summary.toPlainText().splitlines()
            for line in plain:
                ws0.append([line])
            self._append_table_sheet(wb, 'Modèles', self.tbl_models)
            self._append_sheet(wb, 'Récepteurs', self._receiver_rows_for_export())
            self._append_sheet(wb, 'Excedencias', self._collect_exceedance_rows())
            self._append_table_sheet(wb, 'Couches_créées', self.tbl_layers)
            wb.save(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Exporter le paquet XLSX', f'Impossible d’exporter le XLSX :\n{e}')

    def _fill_layers(self):
        entries = [
            ("Bruit · Récepteurs", self._res.get("result_layer") is not None),
            ("Bruit · Sources", self._res.get("sources_layer") is not None),
            ("Bruit · Liaisons dominantes", self._res.get("links_layer") is not None),
            ("Bruit · Récepteurs hors rayon", self._res.get("uncovered_layer") is not None),
            ("Bruit · Carte", self._res.get("grid_layer") is not None),
            ("Bruit · Isophones", self._res.get("iso_layer") is not None),
        ]
        self.tbl_layers.setRowCount(len(entries))
        for r, (name, ok) in enumerate(entries):
            for c, v in enumerate([name, "créée" if ok else "non créée"]):
                it = QtWidgets.QTableWidgetItem(v)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                self.tbl_layers.setItem(r, c, it)
        self.tbl_layers.resizeColumnsToContents()

    def _infer_limit_stats_from_layer(self) -> dict:
        layer = self._res.get("result_layer")
        default = {"min": 45.0, "max": 45.0, "mode": "global", "scenario": "custom", "unique_count": 1}
        if not isinstance(layer, QgsVectorLayer):
            return default
        vals = []
        mode = None
        scenario = None
        try:
            for f in layer.getFeatures():
                try:
                    v = f["limit_dba"]
                    if v is not None:
                        vals.append(float(v))
                except Exception:
                    pass
                if mode is None:
                    try:
                        mode = str(f["limit_src"] or "").strip().lower() or None
                    except Exception:
                        pass
                if scenario is None:
                    try:
                        scenario = str(f["limit_scn"] or "").strip().lower() or None
                    except Exception:
                        pass
        except Exception:
            return default
        if not vals:
            return default
        return {
            "min": min(vals),
            "max": max(vals),
            "mode": mode or "global",
            "scenario": scenario or "custom",
            "unique_count": len({round(v, 6) for v in vals}),
        }
