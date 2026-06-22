# -*- coding: utf-8 -*-
"""
Página del módulo de Ruido.

Iteración actual:
- Conexión al estado real del proyecto (layout, modelos WT, CRS, recurso).
- Tabla de configuración por grupo fuente acústico.
- Selección de receptores y MDT/DSM.
- Cálculo acústico sobre receptores con motores fast e ISO-aligned.
- Capa de resultados de ruido en QGIS.

La arquitectura se deja preparada para contrastar más adelante con PyWake
ISONoise cuando el plugin disponga de una definición acústica más rica por
modelo/turbina.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Dict, List, Optional

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtGui import QGuiApplication

from .noise_core.noise_compute import compute_noise, load_acoustic_curve_csv, evaluate_acoustic_curve
from qgis.core import QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes
from .noise_results_dialog import NoiseResultsDialog
from .i18n import apply_i18n, install_runtime_i18n_patches, tr_text as _tr, is_spanish, current_language
from .ui_core.responsive import configure_scroll_area, configure_table
from .ui_core.layout_sources import import_turbine_layout_from_csv

_GROUP_NAME = "AEP · Coordenadas por modelo"


# Direct helper for long help popups. It bypasses the generic fragment cache so
# clickable ℹ dialogs do not end up half Spanish / half French.
def _tr_help(text):
    if text is None:
        return text
    s = str(text)
    try:
        if current_language() in {"fr", "de"}:
            lang = current_language()
            if lang == "de":
                try:
                    from . import i18n_de as _vw_i18n_lang  # type: ignore
                except Exception:
                    import i18n_de as _vw_i18n_lang  # type: ignore
                table = getattr(_vw_i18n_lang, "TO_DE", {}) or {}
            else:
                try:
                    from . import i18n_fr as _vw_i18n_lang  # type: ignore
                except Exception:
                    import i18n_fr as _vw_i18n_lang  # type: ignore
                table = getattr(_vw_i18n_lang, "TO_FR", {}) or {}
            if s in table:
                return table[s]
            st = s.strip()
            if st in table:
                return table[st]
            try:
                import re as _re
                norm_s = _re.sub(r"\s+", " ", st.replace("\u00a0", " ")).strip()
                if not hasattr(_tr_help, "_norm_%s" % current_language()):
                    setattr(_tr_help, "_norm_%s" % current_language(), {
                        _re.sub(r"\s+", " ", str(k).replace("\u00a0", " ")).strip(): v
                        for k, v in table.items()
                    })
                hit = getattr(_tr_help, "_norm_%s" % current_language(), {}).get(norm_s)
                if hit is not None:
                    return hit
            except Exception:
                pass
            # For translated help dialogs, prefer a clean source fallback over mixed fragments.
            return st or s
    except Exception:
        pass
    return _tr(s)


def _help_ok_label() -> str:
    lang = current_language()
    if lang == "fr":
        return "Fermer"
    if lang == "de":
        return "Schließen"
    if lang == "en":
        return "OK"
    return "Aceptar"


def _set_help_ok_text(msg) -> None:
    try:
        msg.button(QtWidgets.QMessageBox.Ok).setText(_help_ok_label())
    except Exception:
        pass



def _de_cleanup_noise_status(text: str) -> str:
    """Final DE-only cleanup for visible Noise status/fallback messages."""
    s = str(text or "")
    repl = [
        ("Acoustic sources: will use 1 source layer manually selected from Inputs.", "Akustische Quellen: Es wird 1 manuell in den Eingaben ausgewählter Quell-Layer verwendet."),
        ("Acoustic sources: will use", "Akustische Quellen: Es werden"),
        ("source layers manually selected from Inputs.", "manuell in den Eingaben ausgewählte Quell-Layer verwendet."),
        ("Acoustic sources: will use all WT layers automatically detected/imported in VelantisWind.", "Akustische Quellen: Es werden alle in VelantisWind automatisch erkannten/importierten WT-Layer verwendet."),
        ("Receptores", "Rezeptoren"),
        ("Grupos fuente acústicos", "Akustische Quellgruppen"),
        ("Escenario acústico", "Akustisches Szenario"),
        ("Altura de receptor configurada", "Konfigurierte Rezeptorhöhe"),
        ("Radio máximo configurado", "Konfigurierter Maximalradius"),
        ("Atenuación lineal α", "Lineare Dämpfung α"),
        ("Factor de suelo G", "Bodenfaktor G"),
        ("Límite de receptor", "Rezeptorgrenzwert"),
        ("Configured isophones", "Konfigurierte Isophonen"),
        ("MDT/DSM seleccionado", "Ausgewähltes DGM/DSM"),
        ("Método actual", "Aktuelle Methode"),
        ("Parámetros de consultoría acústica", "Akustische Beratungsparameter"),
        ("cálculo acústico", "Akustikberechnung"),
        ("fuente-receptor", "Quelle-Rezeptor"),
        ("consultoría eólica", "Windenergie-Beratung"),
        ("receptores fuera de radio", "Rezeptoren außerhalb des Radius"),
        ("mapa de ruido ráster", "Schallraster"),
        ("isófonas", "Isophonen"),
        ("límite de receptor", "Rezeptorgrenzwert"),
        ("factor de suelo", "Bodenfaktor"),
        ("revisión rápida de cumplimiento", "schnelle Konformitätsprüfung"),
        ("influencia del terreno", "Geländeeinfluss"),
        ("will use G global", "verwendet den globalen G-Wert"),
        ("0=duro, 1=poroso", "0=hart, 1=porös"),
        ("elemento(s)", "Element(e)"),
        ("modelo(s)", "Modell(e)"),
        ("turbina(s)", "Windturbine(n)"),
        ("grupo(s)", "Gruppe(n)"),
        ("capa(s)", "Layer"),
        ("Curvas disponibles", "Verfügbare Kurven"),
        ("LwA fijo", "fester LwA"),
        ("por grupo fuente acústico", "je akustischer Quellgruppe"),
    ]
    for a,b in repl:
        s=s.replace(a,b)
    return s

class NoisePage(QtWidgets.QWidget):
    def __init__(self, parent=None, on_back: Optional[Callable[[], None]] = None):
        install_runtime_i18n_patches()
        super().__init__(parent)
        self._on_back = on_back
        self._qsettings = QtCore.QSettings("VelantisWind", "VelantisWindPlugin")
        self._model_rows: List[Dict[str, object]] = []
        self._build_ui()
        self._apply_style()
        self.refresh_from_project()
        apply_i18n(self)

    def _make_help_button(self, tooltip: str, help_key: str) -> QtWidgets.QToolButton:
        """Small clickable information button used across the Noise module."""
        btn = QtWidgets.QToolButton(self)
        try:
            btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            btn.setText("?")
        btn.setAutoRaise(True)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setToolTip(_tr(tooltip))
        btn.clicked.connect(lambda _checked=False, key=help_key: self._show_noise_help(key))
        return btn

    def _label_with_help(self, text: str, tooltip: str, help_key: str) -> QtWidgets.QWidget:
        """Label + information button, compact enough for QGridLayout label cells."""
        wrap = QtWidgets.QWidget(self)
        lay = QtWidgets.QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lbl = QtWidgets.QLabel(_tr(text))
        lay.addWidget(lbl, 0)
        lay.addWidget(self._make_help_button(tooltip, help_key), 0)
        lay.addStretch(1)
        return wrap

    def _noise_help_text(self, key: str):
        """Help texts for the clickable ℹ buttons.

        Spanish is the canonical source for runtime translation.  English is
        returned only when English is explicitly selected; French and future
        languages use the Spanish source so tr_text can translate the full help
        popup instead of producing mixed fragment translations.
        """
        lang = current_language()
        if lang == "de":
            data_de = {
                "sources": (
                    "Hilfe · Akustische Quellen",
                    """
                    <b>Was hier ausgewählt wird</b><br><br>
                    Diese Liste enthält die in VelantisWind erkannten oder importierten Turbinen-Layer. Jeder Layer steht normalerweise für ein Turbinenmodell oder ein vorbereitetes akustisches Layout.<br><br>
                    <b>Verwendung</b><br>
                    • Markieren Sie einen oder mehrere Quellen-Layer, wenn der kumulierte Schall des gesamten Windparks berechnet werden soll.<br>
                    • Wenn mehrere Turbinenmodelle vorhanden sind, sollten diese normalerweise alle aktiviert bleiben.<br>
                    • In der darunterliegenden Tabelle der Quellgruppen kann jedem Modell ein fester LwA-Wert oder eine akustische Kennlinie zugewiesen werden.<br><br>
                    <b>Hinweis</b><br>
                    Wenn das Ergebnis zu niedrig erscheint, prüfen Sie, ob versehentlich ein Turbinen-Layer abgewählt wurde.
                    """,
                ),
                "receivers": (
                    "Hilfe · Rezeptoren und Grenzwerte",
                    """
                    <b>Was Rezeptoren sind</b><br><br>
                    Rezeptoren sind Punkte oder Polygone, an denen der Schallpegel bewertet wird, zum Beispiel Wohngebäude, Ortschaften, Höfe oder sensible Grenzen.<br><br>
                    <b>Einfacher Modus</b><br>
                    Wählen Sie einen einzelnen Rezeptor-Layer und verwenden Sie einen globalen dB(A)-Grenzwert. Das reicht für eine erste Prüfung aus.<br><br>
                    <b>Kategorie-Modus</b><br>
                    Aktivieren Sie mehrere Layer, wenn Rezeptoren nach Kategorie getrennt werden sollen, zum Beispiel Wohnen, Industrie oder Umwelt. Jeder Layer kann einen eigenen Tagesgrenzwert, Nachtgrenzwert und eine eigene Höhe haben.<br><br>
                    <b>Grenzwertkriterium</b><br>
                    Manuell/global verwendet den allgemeinen Grenzwert. Tag/Nacht verwendet die je Layer konfigurierten Grenzwerte, wenn mit mehreren Kategorien gearbeitet wird.
                    """,
                ),
                "map": (
                    "Hilfe · Schallkarte und Isophonen",
                    """
                    <b>GIS-Schallkarte</b><br><br>
                    Erzeugt ein Raster mit dem geschätzten Schallpegel um den Windpark. Das ist hilfreich, um akustische Einflussbereiche zu visualisieren, erhöht aber die Rechenzeit.<br><br>
                    <b>Auflösung</b><br>
                    Eine kleinere Zellgröße liefert mehr Detail, dauert aber länger. Für schnelle Tests sind 100–200 m sinnvoll; für feinere Ausgaben kann die Zellgröße reduziert werden, wenn das Gebiet nicht sehr groß ist.<br><br>
                    <b>Isophonen</b><br>
                    Isophonen sind Linien gleichen Schallpegels, zum Beispiel 35, 40, 45 und 50 dB(A). Das Plugin erzeugt sie aus dem Schallraster.
                    """,
                ),
                "terrain": (
                    "Hilfe · DGM/DSM, Abstand und Rezeptorhöhe",
                    """
                    <b>Rezeptorhöhe</b><br><br>
                    Höhe, in der der Schall am Rezeptor bewertet wird. Für Wohnrezeptoren ist 4 m ein üblicher Wert, kann aber an das Kriterium der Studie angepasst werden.<br><br>
                    <b>Maximaler Radius</b><br>
                    Begrenzt, welche Turbinen zu jedem Rezeptor beitragen. Ein zu kleiner Radius kann relevante Quellen ausschließen; ein sehr großer Radius erhöht die Rechenzeit.<br><br>
                    <b>DGM/DSM</b><br>
                    Wenn ein Geländeraster ausgewählt wird, kann die Berechnung 3D-Abstände verwenden und spätere topografische Korrekturen besser vorbereiten. Wenn kein Raster ausgewählt wird, wird ebenes Gelände angenommen.
                    """,
                ),
                "ground": (
                    "Hilfe · Dämpfung, Boden und Landnutzung",
                    """
                    <b>Lineare Dämpfung α</b><br><br>
                    Im schnellen Rechenkern fasst α die atmosphärische Absorption über die Entfernung vereinfacht zusammen. Es ersetzt nicht die frequenzbandweise Berechnung des ISO-orientierten Rechenkerns.<br><br>
                    <b>Bodenfaktor G</b><br>
                    G=0 steht für harten oder reflektierenden Boden; G=1 für porösen oder absorbierenden Boden. Zwischenwerte mischen beide Verhaltensweisen.<br><br>
                    <b>Landnutzung</b><br>
                    Wenn ein Landnutzungs-Layer gewählt wird, kann das Plugin für jeden Pfad einen effektiven G-Wert abschätzen. Andernfalls wird der manuell definierte globale G-Wert verwendet.<br><br>
                    <b>Erwartetes Layer-Format</b><br>
                    • Es muss ein <b>polygonaler Vektor-Layer</b> in QGIS sein, z. B. GeoPackage oder Shapefile. Raster, Linien und Punkte werden nicht als Landnutzung gelesen.<br>
                    • Er sollte im <b>gleichen CRS wie das Projekt</b> liegen. Wenn das nicht der Fall ist, reprojizieren Sie ihn vor der Berechnung.<br>
                    • Jedes Polygon sollte einen Geländebereich mit einem G-Wert oder einer Landnutzungsklasse abdecken.<br><br>
                    <b>Empfohlene Felder</b><br>
                    Bevorzugt wird ein numerisches Feld mit Werten zwischen 0 und 1, z. B. <code>g_factor</code>, <code>g</code>, <code>ground_g</code>, <code>g_value</code> oder <code>G</code>.<br>
                    • <code>0</code> = harter/reflektierender Boden: urban, Asphalt, Fels, Industrie.<br>
                    • <code>0.5</code> = gemischter Boden.<br>
                    • <code>1</code> = poröser/absorbierender Boden: Acker, Wiese, Weide, Wald, Vegetation.<br><br>
                    <b>Text-Alternative</b><br>
                    Wenn kein numerisches Feld vorhanden ist, versucht das Plugin eine Textspalte wie <code>uso_suelo</code>, <code>uso</code>, <code>clase</code>, <code>landuse</code>, <code>cover</code> oder <code>type</code> zu lesen. Wenn die Klasse nicht erkannt wird, dient der globale G-Wert als Fallback.
                    """,
                ),
                "engine": (
                    "Hilfe · Schall-Rechenkern",
                    """
                    <b>Schneller Rechenkern</b><br><br>
                    Verwendet einen vereinfachten Quelle-Rezeptor-Ansatz mit globalem LwA, geometrischer Divergenz, linearer Absorption und Bodenkorrektur. Er ist schnell und für Screening geeignet.<br><br>
                    <b>ISO-orientierter Rechenkern</b><br>
                    Arbeitet mit Oktavbändern und nähert die Struktur der ISO 9613-2 mit Adiv, Aatm und Agr an. Er benötigt mehr Informationen, z. B. atmosphärische Bedingungen und akustische Spektren, sofern verfügbar.<br><br>
                    <b>Empfehlung</b><br>
                    Verwenden Sie den schnellen Rechenkern für Iterationen und den ISO-orientierten Rechenkern für Rezeptoren nahe am Grenzwert oder für belastbarere technische Vergleiche.
                    """,
                ),
                "atmos": (
                    "Hilfe · Atmosphärische Bedingungen",
                    """
                    <b>Wofür diese Werte verwendet werden</b><br><br>
                    Im ISO-orientierten Rechenkern beeinflussen Temperatur, relative Luftfeuchte und Luftdruck die atmosphärische Absorption nach Frequenzband.<br><br>
                    <b>Wahl der Werte</b><br>
                    Verwenden Sie repräsentative Standortbedingungen oder das regulatorische Szenario, das untersucht werden soll. Wenn kein gemessener Druck vorliegt, ist 101,325 kPa ein Referenzwert auf Meereshöhe; in höheren Lagen ist er normalerweise geringer.<br><br>
                    <b>Wichtig</b><br>
                    Diese Parameter ändern nicht die akustische Emission der Turbine; sie ändern, wie sich der Schall bis zu den Rezeptoren ausbreitet.
                    """,
                ),
                "acoustic": (
                    "Hilfe · Akustische Emission LwA und Kennlinien",
                    """
                    <b>Fester LwA</b><br><br>
                    Weist jeder Quellgruppe einen einzigen Schallleistungspegel zu. Das ist einfach und nützlich, wenn nur ein garantierter Wert vorliegt oder ein konservativer Fall gerechnet werden soll.<br><br>
                    <b>Akustische Kennlinie LwA(ws)</b><br>
                    Ermöglicht den Import einer Kennlinie in Abhängigkeit von der Windgeschwindigkeit. Das Plugin kann die Emission bei einer bestimmten Windgeschwindigkeit auswerten oder den ungünstigsten Wert der Kennlinie verwenden.<br><br>
                    <b>Erwartetes CSV</b><br>
                    Verwenden Sie Spalten für Windgeschwindigkeit und LwA. Ein übliches Format ist <code>ws,LwA</code> oder ein entsprechender Spaltenname.
                    """,
                ),
                "groups": (
                    "Hilfe · Akustische Quellgruppen",
                    """
                    <b>Was jede Zeile darstellt</b><br><br>
                    Jede Zeile fasst eine Turbinengruppe zusammen, die als akustische Quelle verwendet wird. Normalerweise stammt sie aus einem in VelantisWind erkannten oder importierten Turbinenmodell.<br><br>
                    <b>Wichtige Spalten</b><br>
                    • Quellgruppe und Windpark: Namen, damit Berichte und Exporte lesbar bleiben.<br>
                    • HH und D: Nabenhöhe und Durchmesser für die Ausbreitungsgeometrie.<br>
                    • Fester LwA: globale akustische Emission, wenn keine Kennlinie verwendet wird.<br>
                    • CSV-Kennlinie: importierte ws/LwA-Datei für diese Gruppe.<br><br>
                    <b>Hinweis</b><br>
                    Wenn mehrere Turbinenmodelle vorhanden sind, prüfen Sie vor der Berechnung, ob jede Gruppe die richtige akustische Emission hat.
                    """,
                ),
            }
            return data_de.get(key, ("Hilfe", "Für dieses Element ist keine Hilfe verfügbar."))
        data_es = {
            "sources": (
                "Ayuda · Fuentes acústicas",
                """
                <b>Qué seleccionas aquí</b><br><br>
                Esta lista contiene las capas de turbinas detectadas o importadas en VelantisWind. Cada capa suele representar un modelo de aerogenerador o un layout acústico preparado.<br><br>
                <b>Cómo usarlo</b><br>
                • Marca una o varias capas fuente si quieres calcular el ruido acumulado de todo el parque.<br>
                • Si tienes varios modelos de turbina, normalmente conviene mantenerlos todos marcados.<br>
                • La tabla inferior de grupos fuente permite asignar a cada grupo su LwA fijo o su curva acústica.<br><br>
                <b>Consejo</b><br>
                Si el resultado parece demasiado bajo, revisa que no hayas dejado sin marcar alguna capa de turbinas.
                """,
            ),
            "receivers": (
                "Ayuda · Receptores y límites",
                """
                <b>Qué son los receptores</b><br><br>
                Son los puntos o polígonos donde se evalúa el nivel sonoro, por ejemplo viviendas, núcleos urbanos, granjas o límites sensibles.<br><br>
                <b>Modo simple</b><br>
                Selecciona una única capa de receptores y usa un límite global en dB(A). Es suficiente para una primera revisión.<br><br>
                <b>Modo por categorías</b><br>
                Activa varias capas si quieres separar receptores por categoría, por ejemplo residencial, industrial o ambiental. Cada capa puede tener límite día, límite noche y altura propia.<br><br>
                <b>Criterio de límite</b><br>
                Manual/global usa el límite general. Diurno/nocturno toma los límites configurados por capa cuando trabajas con varias categorías.
                """,
            ),
            "map": (
                "Ayuda · Mapa de ruido e isófonas",
                """
                <b>Mapa GIS de ruido</b><br><br>
                Genera una malla raster con el nivel sonoro estimado alrededor del parque. Es útil para visualizar zonas de influencia acústica, pero aumenta el tiempo de cálculo.<br><br>
                <b>Resolución</b><br>
                Una resolución pequeña da más detalle pero tarda más. Para pruebas rápidas usa 100–200 m; para salidas más finas puedes bajar la celda si el área no es muy grande.<br><br>
                <b>Isófonas</b><br>
                Las isófonas son líneas de igual nivel sonoro, por ejemplo 35, 40, 45 y 50 dB(A). El plugin las genera a partir del raster de ruido.
                """,
            ),
            "terrain": (
                "Ayuda · MDT/DSM, distancia y altura de receptor",
                """
                <b>Altura de receptor</b><br><br>
                Representa la altura a la que se evalúa el ruido. Un valor habitual para receptores residenciales es 4 m, pero puede ajustarse al criterio del estudio.<br><br>
                <b>Radio máximo</b><br>
                Limita qué turbinas contribuyen a cada receptor. Un radio demasiado pequeño puede excluir fuentes relevantes; uno muy grande aumenta el coste de cálculo.<br><br>
                <b>MDT/DSM</b><br>
                Si seleccionas un raster de terreno, el cálculo puede usar distancias 3D y preparar mejor futuras correcciones topográficas. Si no lo seleccionas, se asume terreno plano.
                """,
            ),
            "ground": (
                "Ayuda · Atenuación, suelo y land-use",
                """
                <b>Atenuación lineal α</b><br><br>
                En el motor rápido, α resume de forma simplificada la absorción atmosférica por distancia. No sustituye al cálculo por bandas del motor ISO.<br><br>
                <b>Factor de suelo G</b><br>
                G=0 representa suelo duro o reflectante; G=1 representa suelo poroso/absorbente. Valores intermedios mezclan ambos comportamientos.<br><br>
                <b>Uso del suelo</b><br>
                Si eliges una capa de land-use, el plugin puede estimar un G efectivo por trayecto. Si no, usa el G global definido manualmente.<br><br>
                <b>Formato de capa esperado</b><br>
                • Debe ser una <b>capa vectorial poligonal</b> cargada en QGIS, por ejemplo GeoPackage o Shapefile. No se leen rasters, líneas ni puntos como uso del suelo.<br>
                • Debe estar en el <b>mismo CRS que el proyecto</b>. Si no coincide, reproyéctala antes de calcular.<br>
                • Cada polígono debe cubrir una zona de terreno con un valor G o una clase de uso del suelo.<br><br>
                <b>Campos recomendados</b><br>
                Opción preferida: un campo numérico con valores entre 0 y 1 llamado <code>g_factor</code>, <code>g</code>, <code>ground_g</code>, <code>g_value</code> o <code>G</code>.<br>
                • <code>0</code> = suelo duro/reflectante: urbano, asfalto, roca, industrial.<br>
                • <code>0.5</code> = suelo mixto.<br>
                • <code>1</code> = suelo poroso/absorbente: cultivo, prado, pasto, forestal, vegetación.<br><br>
                <b>Alternativa por texto</b><br>
                Si no hay campo numérico, el plugin intenta leer una columna textual llamada <code>uso_suelo</code>, <code>uso</code>, <code>clase</code>, <code>landuse</code>, <code>cover</code> o <code>type</code>. Si no reconoce la clase, usa el G global como respaldo.
                """,
            ),
            "engine": (
                "Ayuda · Motor de cálculo de ruido",
                """
                <b>Motor rápido</b><br><br>
                Usa un enfoque fuente–receptor simplificado con LwA global, divergencia geométrica, absorción lineal y corrección de suelo. Es rápido y útil para screening.<br><br>
                <b>Motor ISO-aligned</b><br>
                Trabaja por bandas de octava y aproxima la estructura de ISO 9613-2 con Adiv, Aatm y Agr. Requiere más información, como condiciones atmosféricas y espectros acústicos si están disponibles.<br><br>
                <b>Recomendación</b><br>
                Usa el motor rápido para iterar y el ISO-aligned para revisar receptores cercanos al límite o preparar una comparación técnica más seria.
                """,
            ),
            "atmos": (
                "Ayuda · Condiciones atmosféricas",
                """
                <b>Para qué sirven</b><br><br>
                En el motor ISO-aligned, temperatura, humedad relativa y presión influyen en la absorción atmosférica por bandas de frecuencia.<br><br>
                <b>Cómo elegir valores</b><br>
                Usa condiciones representativas del emplazamiento o del escenario normativo que quieras estudiar. Si no tienes presión medida, 101.325 kPa es una referencia a nivel del mar; en zonas altas suele ser menor.<br><br>
                <b>Importante</b><br>
                Estos parámetros no cambian la emisión acústica de la turbina; cambian cómo se propaga el sonido hasta los receptores.
                """,
            ),
            "acoustic": (
                "Ayuda · Emisión acústica LwA y curvas",
                """
                <b>LwA fijo</b><br><br>
                Asigna un único nivel de potencia acústica por grupo fuente. Es simple y útil cuando solo tienes un valor garantizado o quieres hacer un caso conservador.<br><br>
                <b>Curva acústica LwA(ws)</b><br>
                Permite importar una curva por velocidad de viento. El plugin puede evaluar la emisión a una velocidad concreta o tomar el peor caso de la curva.<br><br>
                <b>CSV esperado</b><br>
                Usa columnas de velocidad de viento y LwA. Lo habitual es una tabla tipo <code>ws,LwA</code> o nombres equivalentes.
                """,
            ),
            "groups": (
                "Ayuda · Grupos fuente acústicos",
                """
                <b>Qué representa cada fila</b><br><br>
                Cada fila resume un grupo de turbinas usado como fuente acústica. Normalmente viene de un modelo de aerogenerador detectado o importado en VelantisWind.<br><br>
                <b>Columnas clave</b><br>
                • Grupo fuente y parque: nombres para que informes y exportaciones sean legibles.<br>
                • HH y D: altura de buje y diámetro usados para la geometría de propagación.<br>
                • LwA fijo: emisión acústica global si no usas curva.<br>
                • Curva CSV: archivo ws/LwA importado para ese grupo.<br><br>
                <b>Consejo</b><br>
                Si tienes varios modelos de turbina, revisa que cada grupo tenga la emisión acústica correcta antes de calcular.
                """,
            ),
        }
        data_en = {
            "sources": (
                "Help · Acoustic sources",
                """
                <b>What you select here</b><br><br>
                This list contains the turbine layers detected or imported in VelantisWind. Each layer usually represents one turbine model or one prepared acoustic layout.<br><br>
                <b>How to use it</b><br>
                • Tick one or several source layers if you want to calculate the accumulated noise from the whole wind farm.<br>
                • If you have several turbine models, it is usually better to keep all of them selected.<br>
                • The source-group table below lets you assign a fixed LwA or an acoustic curve to each group.<br><br>
                <b>Tip</b><br>
                If the result looks too low, check that no turbine layer was accidentally left unticked.
                """,
            ),
            "receivers": (
                "Help · Receivers and limits",
                """
                <b>What receivers are</b><br><br>
                Receivers are the points or polygons where the sound level is evaluated, for example dwellings, villages, farms or sensitive boundaries.<br><br>
                <b>Simple mode</b><br>
                Select a single receiver layer and use one global dB(A) limit. This is enough for a first review.<br><br>
                <b>Category mode</b><br>
                Enable several layers if you want to separate receivers by category, for example residential, industrial or environmental. Each layer can have its own day limit, night limit and height.<br><br>
                <b>Limit criterion</b><br>
                Manual/global uses the general limit. Day/night reads the limits configured per layer when you work with several categories.
                """,
            ),
            "map": (
                "Help · Noise map and isophones",
                """
                <b>GIS noise map</b><br><br>
                Generates a raster grid with the estimated sound level around the wind farm. It is useful for visualizing acoustic influence areas, but increases calculation time.<br><br>
                <b>Resolution</b><br>
                A smaller cell gives more detail but takes longer. For quick tests use 100–200 m; for finer outputs you can reduce the cell size if the area is not too large.<br><br>
                <b>Isophones</b><br>
                Isophones are equal-sound-level contours, for example 35, 40, 45 and 50 dB(A). The plugin generates them from the noise raster.
                """,
            ),
            "terrain": (
                "Help · DEM/DSM, distance and receiver height",
                """
                <b>Receiver height</b><br><br>
                This is the height at which noise is evaluated. A common value for residential receivers is 4 m, but it can be adapted to the study criterion.<br><br>
                <b>Maximum radius</b><br>
                Limits which turbines contribute to each receiver. A radius that is too small may exclude relevant sources; a very large radius increases computation time.<br><br>
                <b>DEM/DSM</b><br>
                If you select a terrain raster, the calculation can use 3D distances and better prepare future topographic corrections. If none is selected, flat terrain is assumed.
                """,
            ),
            "ground": (
                "Help · Attenuation, ground and land use",
                """
                <b>Linear attenuation α</b><br><br>
                In the fast engine, α is a simplified distance-based representation of atmospheric absorption. It does not replace the band-by-band calculation of the ISO engine.<br><br>
                <b>Ground factor G</b><br>
                G=0 represents hard or reflective ground; G=1 represents porous/absorptive ground. Intermediate values mix both behaviours.<br><br>
                <b>Land use</b><br>
                If you choose a land-use layer, the plugin can estimate an effective G for each path. Otherwise, it uses the manually defined global G.<br><br>
                <b>Expected layer format</b><br>
                • It must be a <b>polygon vector layer</b> loaded in QGIS, for example GeoPackage or Shapefile. Rasters, lines and points are not read as land-use layers.<br>
                • It must use the <b>same CRS as the project</b>. If it does not match, reproject it before calculating.<br>
                • Each polygon should cover a ground area with either a G value or a land-use class.<br><br>
                <b>Recommended fields</b><br>
                Preferred option: a numeric field with values between 0 and 1 named <code>g_factor</code>, <code>g</code>, <code>ground_g</code>, <code>g_value</code> or <code>G</code>.<br>
                • <code>0</code> = hard/reflective ground: urban, asphalt, rock, industrial.<br>
                • <code>0.5</code> = mixed ground.<br>
                • <code>1</code> = porous/absorptive ground: crops, meadow, pasture, forest, vegetation.<br><br>
                <b>Text-class alternative</b><br>
                If there is no numeric field, the plugin tries to read a text column named <code>uso_suelo</code>, <code>uso</code>, <code>clase</code>, <code>landuse</code>, <code>cover</code> or <code>type</code>. If the class is not recognised, the global G is used as fallback.
                """,
            ),
            "engine": (
                "Help · Noise calculation engine",
                """
                <b>Fast engine</b><br><br>
                Uses a simplified source-receiver approach with global LwA, geometrical divergence, linear absorption and ground correction. It is fast and useful for screening.<br><br>
                <b>ISO-aligned engine</b><br>
                Works by octave bands and approximates the ISO 9613-2 structure with Adiv, Aatm and Agr. It needs more information, such as atmospheric conditions and acoustic spectra when available.<br><br>
                <b>Recommendation</b><br>
                Use the fast engine to iterate and the ISO-aligned engine to review receivers close to the limit or to prepare a more serious technical comparison.
                """,
            ),
            "atmos": (
                "Help · Atmospheric conditions",
                """
                <b>What they are used for</b><br><br>
                In the ISO-aligned engine, temperature, relative humidity and pressure affect atmospheric absorption by frequency band.<br><br>
                <b>How to choose values</b><br>
                Use representative site conditions or the regulatory scenario you want to study. If you do not have measured pressure, 101.325 kPa is a sea-level reference; at high altitude it is usually lower.<br><br>
                <b>Important</b><br>
                These parameters do not change turbine acoustic emission; they change how sound propagates to the receivers.
                """,
            ),
            "acoustic": (
                "Help · LwA emission and curves",
                """
                <b>Fixed LwA</b><br><br>
                Assigns one acoustic power level to each source group. It is simple and useful when you only have one guaranteed value or want to run a conservative case.<br><br>
                <b>Acoustic curve LwA(ws)</b><br>
                Lets you import a curve by wind speed. The plugin can evaluate emission at one specific wind speed or take the worst case of the curve.<br><br>
                <b>Expected CSV</b><br>
                Use wind-speed and LwA columns. A common format is <code>ws,LwA</code> or equivalent names.
                """,
            ),
            "groups": (
                "Help · Acoustic source groups",
                """
                <b>What each row represents</b><br><br>
                Each row summarizes a turbine group used as an acoustic source. It can come from Energy or from a layout imported directly in this module.<br><br>
                <b>Key columns</b><br>
                • Source group and wind farm: names used to keep reports and exports readable.<br>
                • HH and D: hub height and diameter used for propagation geometry.<br>
                • Fixed LwA: global acoustic emission if no curve is used.<br>
                • CSV curve: imported ws/LwA file for that group.<br><br>
                <b>Tip</b><br>
                If you have several turbine models, check that each group has the correct acoustic emission before running the calculation.
                """,
            ),
        }

        data_fr = {'sources': ('Aide · Sources acoustiques',
                     '<b>Ce que vous sélectionnez ici</b><br><br>Cette liste contient les couches d’éoliennes détectées ou '
                     'importées dans VelantisWind. Chaque couche représente généralement un modèle d’éolienne ou un layout '
                     'acoustique préparé.<br><br><b>Comment l’utiliser</b><br>• Cochez une ou plusieurs couches source si vous '
                     'voulez calculer le bruit cumulé de tout le parc.<br>• Si vous avez plusieurs modèles d’éolienne, il est '
                     'généralement préférable de les garder tous sélectionnés.<br>• Le tableau des groupes source ci-dessous '
                     'permet d’assigner un LwA fixe ou une courbe acoustique à chaque groupe.<br><br><b>Conseil</b><br>Si le '
                     'résultat semble trop bas, vérifiez qu’aucune couche d’éoliennes n’a été laissée décochée par erreur.'),
         'receivers': ('Aide · Récepteurs et limites',
                       '<b>Ce que sont les récepteurs</b><br><br>Ce sont les points ou polygones où le niveau sonore est '
                       'évalué, par exemple des habitations, des noyaux urbains, des fermes ou des limites '
                       'sensibles.<br><br><b>Mode simple</b><br>Sélectionnez une seule couche de récepteurs et utilisez une '
                       'limite globale en dB(A). C’est suffisant pour une première vérification.<br><br><b>Mode par '
                       'catégories</b><br>Activez plusieurs couches si vous voulez séparer les récepteurs par catégorie, par '
                       'exemple résidentiel, industriel ou environnemental. Chaque couche peut avoir sa propre limite de jour, '
                       'limite de nuit et hauteur.<br><br><b>Critère de limite</b><br>Manuel/global utilise la limite '
                       'générale. Jour/nuit utilise les limites configurées par couche lorsque vous travaillez avec plusieurs '
                       'catégories.'),
         'map': ('Aide · Carte de bruit et isophones',
                 '<b>Carte GIS de bruit</b><br><br>Génère une grille raster avec le niveau sonore estimé autour du parc. Elle '
                 'est utile pour visualiser les zones d’influence acoustique, mais augmente le temps de '
                 'calcul.<br><br><b>Résolution</b><br>Une résolution plus fine donne plus de détail mais prend plus de temps. '
                 'Pour des tests rapides, utilisez 100–200 m ; pour des sorties plus fines, vous pouvez réduire la taille de '
                 'cellule si la zone n’est pas trop grande.<br><br><b>Isophones</b><br>Les isophones sont des lignes de niveau '
                 'sonore égal, par exemple 35, 40, 45 et 50 dB(A). Le plugin les génère à partir du raster de bruit.'),
         'terrain': ('Aide · MDT/DSM, distance et hauteur de récepteur',
                     '<b>Hauteur du récepteur</b><br><br>Elle représente la hauteur à laquelle le bruit est évalué. Une valeur '
                     'courante pour des récepteurs résidentiels est 4 m, mais elle peut être ajustée au critère de '
                     'l’étude.<br><br><b>Rayon maximal</b><br>Il limite les éoliennes qui contribuent à chaque récepteur. Un '
                     'rayon trop petit peut exclure des sources importantes ; un rayon très grand augmente le coût de '
                     'calcul.<br><br><b>MDT/DSM</b><br>Si vous sélectionnez un raster de terrain, le calcul peut utiliser des '
                     'distances 3D et préparer de meilleures corrections topographiques futures. S’il n’est pas sélectionné, '
                     'le terrain est supposé plat.'),
         'ground': ('Aide · Atténuation, sol et land-use',
                    '<b>Atténuation linéaire α</b><br><br>Dans le moteur rapide, α résume de façon simplifiée l’absorption '
                    'atmosphérique avec la distance. Il ne remplace pas le calcul par bandes du moteur ISO.<br><br><b>Facteur '
                    'de sol G</b><br>G=0 représente un sol dur ou réfléchissant ; G=1 représente un sol poreux/absorbant. Les '
                    'valeurs intermédiaires mélangent les deux comportements.<br><br><b>Usage du sol</b><br>Si vous choisissez '
                    'une couche de land-use, le plugin peut estimer un G effectif pour chaque trajet. Sinon, il utilise le G '
                    'global défini manuellement.<br><br><b>Format de couche attendu</b><br>• Il doit s’agir d’une <b>couche '
                    'vectorielle polygonale</b> chargée dans QGIS, par exemple GeoPackage ou Shapefile. Les rasters, lignes et '
                    'points ne sont pas lus comme couches d’usage du sol.<br>• Elle doit utiliser le <b>même CRS que le '
                    'projet</b>. Si ce n’est pas le cas, reprojetez-la avant le calcul.<br>• Chaque polygone doit couvrir une '
                    'zone de terrain avec une valeur G ou une classe d’usage du sol.<br><br><b>Champs '
                    'recommandés</b><br>Option préférée : un champ numérique avec des valeurs entre 0 et 1 nommé '
                    '<code>g_factor</code>, <code>g</code>, <code>ground_g</code>, <code>g_value</code> ou '
                    '<code>G</code>.<br>• <code>0</code> = sol dur/réfléchissant : urbain, asphalte, roche, industriel.<br>• '
                    '<code>0.5</code> = sol mixte.<br>• <code>1</code> = sol poreux/absorbant : cultures, prairie, pâturage, '
                    'forêt, végétation.<br><br><b>Alternative par classe texte</b><br>S’il n’y a pas de champ numérique, le '
                    'plugin essaie de lire une colonne texte nommée <code>uso_suelo</code>, <code>uso</code>, '
                    '<code>clase</code>, <code>landuse</code>, <code>cover</code> ou <code>type</code>. Si la classe n’est pas '
                    'reconnue, le G global est utilisé comme secours.'),
         'engine': ('Aide · Moteur de calcul du bruit',
                    '<b>Moteur rapide</b><br><br>Utilise une approche source–récepteur simplifiée avec LwA global, divergence '
                    'géométrique, absorption linéaire et correction de sol. Il est rapide et utile pour le '
                    'screening.<br><br><b>Moteur aligné ISO</b><br>Travaille par bandes d’octave et approxime la structure ISO '
                    '9613-2 avec Adiv, Aatm et Agr. Il nécessite plus d’informations, comme les conditions atmosphériques et '
                    'les spectres acoustiques lorsqu’ils sont disponibles.<br><br><b>Recommandation</b><br>Utilisez le moteur '
                    'rapide pour itérer et le moteur aligné ISO pour vérifier les récepteurs proches de la limite ou préparer '
                    'une comparaison technique plus sérieuse.'),
         'atmos': ('Aide · Conditions atmosphériques',
                   '<b>À quoi elles servent</b><br><br>Dans le moteur aligné ISO, la température, l’humidité relative et la '
                   'pression influencent l’absorption atmosphérique par bande de fréquence.<br><br><b>Comment choisir les '
                   'valeurs</b><br>Utilisez des conditions représentatives du site ou le scénario réglementaire que vous '
                   'voulez étudier. Si vous n’avez pas de pression mesurée, 101.325 kPa est une référence au niveau de la mer '
                   '; en altitude elle est généralement plus faible.<br><br><b>Important</b><br>Ces paramètres ne changent pas '
                   'l’émission acoustique de l’éolienne ; ils changent la façon dont le son se propage jusqu’aux récepteurs.'),
         'acoustic': ('Aide · Émission acoustique LwA et courbes',
                      '<b>LwA fixe</b><br><br>Attribue un seul niveau de puissance acoustique à chaque groupe source. C’est '
                      'simple et utile lorsque vous n’avez qu’une valeur garantie ou que vous voulez créer un cas '
                      'conservateur.<br><br><b>Courbe acoustique LwA(ws)</b><br>Permet d’importer une courbe selon la vitesse '
                      'du vent. Le plugin peut évaluer l’émission à une vitesse précise ou prendre le pire cas de la '
                      'courbe.<br><br><b>CSV attendu</b><br>Utilisez des colonnes de vitesse du vent et de LwA. Le format '
                      'habituel est une table de type <code>ws,LwA</code> ou des noms équivalents.'),
         'groups': ('Aide · Groupes source acoustiques',
                    '<b>Ce que représente chaque ligne</b><br><br>Chaque ligne résume un groupe d’éoliennes utilisé comme '
                    'source acoustique. Il provient généralement d’un modèle d’éolienne détecté ou importé dans '
                    'VelantisWind.<br><br><b>Colonnes clés</b><br>• Groupe source et parc : noms utilisés pour rendre les '
                    'rapports et exportations lisibles.<br>• HH et D : hauteur de moyeu et diamètre utilisés pour la géométrie '
                    'de propagation.<br>• LwA fixe : émission acoustique globale si vous n’utilisez pas de courbe.<br>• CSV de '
                    'courbe : fichier ws/LwA importé pour ce groupe.<br><br><b>Conseil</b><br>Si vous avez plusieurs modèles '
                    'd’éolienne, vérifiez que chaque groupe possède l’émission acoustique correcte avant de calculer.')}
        if lang == "fr":
            return data_fr.get(key, ("Aide", "Aucune aide disponible pour cet élément."))
        if lang == "en":
            return data_en.get(key, ("Help", "No help available for this item."))
        return data_es.get(key, ("Ayuda", "No hay ayuda disponible para este elemento."))

    def _show_noise_help(self, key: str) -> None:
        title, body = self._noise_help_text(key)
        msg = QtWidgets.QMessageBox(self)
        if current_language() in ("fr", "de"):
            msg.setWindowTitle(title)
        else:
            msg.setWindowTitle(_tr_help(title))
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setTextFormat(QtCore.Qt.RichText)
        if current_language() in ("fr", "de"):
            msg.setText(body.strip())
        else:
            msg.setText(_tr_help(body.strip()))
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        _set_help_ok_text(msg)
        msg.exec_()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        self.scroll = QtWidgets.QScrollArea(self)
        configure_scroll_area(self.scroll)
        outer.addWidget(self.scroll)

        container = QtWidgets.QWidget(self.scroll)
        self.scroll.setWidget(container)

        root = QtWidgets.QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        self.btn_back = QtWidgets.QPushButton("← Inicio")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_refresh = QtWidgets.QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self.refresh_from_project)
        top.addWidget(self.btn_back)
        top.addWidget(self.btn_refresh)
        top.addStretch(1)
        root.addLayout(top)

        hero = QtWidgets.QHBoxLayout()
        hero.setSpacing(16)

        hero_text = QtWidgets.QVBoxLayout()
        hero_text.setSpacing(6)
        title = QtWidgets.QLabel("Noise")
        title.setObjectName("noiseTitle")
        hero_text.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Módulo de ruido: conectado al layout y modelos WT del proyecto, con cálculo sobre receptores, "
            "tabla de emisión por modelo, motores fast e ISO-aligned, mapas raster y salidas GIS. "
            "La física actual es un flujo de screening experimental con limitaciones documentadas."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("noiseSubtitle")
        hero_text.addWidget(subtitle)
        hero.addLayout(hero_text, 1)
        hero.addStretch(1)

        logo = QtWidgets.QLabel(self)
        logo.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "velantiswind_logo.png")
        if os.path.exists(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(200, 200, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                logo.setToolTip("Velantis Wind")
        hero.addWidget(logo, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        root.addLayout(hero)

        grp_ctx = QtWidgets.QGroupBox("Contexto del proyecto")
        form_ctx = QtWidgets.QFormLayout(grp_ctx)
        self.lbl_project = QtWidgets.QLabel("-")
        self.lbl_crs = QtWidgets.QLabel("-")
        self.lbl_layout = QtWidgets.QLabel("-")
        self.lbl_models = QtWidgets.QLabel("-")
        self.lbl_resource = QtWidgets.QLabel("-")
        self.lbl_ti = QtWidgets.QLabel("-")
        self.lbl_receptor_info = QtWidgets.QLabel("-")
        for w in [self.lbl_project, self.lbl_crs, self.lbl_layout, self.lbl_models, self.lbl_resource, self.lbl_ti, self.lbl_receptor_info]:
            w.setWordWrap(True)
        form_ctx.addRow("Proyecto:", self.lbl_project)
        form_ctx.addRow("CRS:", self.lbl_crs)
        form_ctx.addRow("Layout activo:", self.lbl_layout)
        form_ctx.addRow("Modelos WT detectados:", self.lbl_models)
        form_ctx.addRow("Recurso:", self.lbl_resource)
        form_ctx.addRow("TI WRG:", self.lbl_ti)
        form_ctx.addRow("Capa de receptores:", self.lbl_receptor_info)
        root.addWidget(grp_ctx)

        grp_inputs = QtWidgets.QGroupBox("Entradas del cálculo")
        grid_inputs = QtWidgets.QGridLayout(grp_inputs)
        row = 0
        grid_inputs.addWidget(self._label_with_help("Fuentes / layout acústico:", "Explain which turbine layers are used as acoustic sources", "sources"), row, 0)
        self.lst_sources = QtWidgets.QListWidget()
        self.lst_sources.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.lst_sources.setMinimumHeight(72)
        self.lst_sources.setMaximumHeight(140)
        self.lst_sources.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.lst_sources.itemChanged.connect(self._on_sources_changed)
        self.lst_sources.setToolTip("Selecciona una o varias capas fuente detectadas/importadas en VelantisWind. Si marcas varias, el cálculo de ruido usará todas ellas a la vez.")
        grid_inputs.addWidget(self.lst_sources, row, 1, 1, 3)
        row += 1

        src_btns = QtWidgets.QHBoxLayout()
        self.btn_sources_all = QtWidgets.QPushButton("Marcar todas")
        self.btn_sources_none = QtWidgets.QPushButton("Desmarcar todas")
        self.btn_import_layout = QtWidgets.QPushButton("Importar layout CSV…")
        self.btn_sources_all.clicked.connect(lambda: self._set_all_sources_checked(True))
        self.btn_sources_none.clicked.connect(lambda: self._set_all_sources_checked(False))
        self.btn_import_layout.clicked.connect(self._import_turbine_layout_for_noise)
        src_btns.addWidget(self.btn_sources_all)
        src_btns.addWidget(self.btn_sources_none)
        src_btns.addWidget(self.btn_import_layout)
        src_btns.addStretch(1)
        grid_inputs.addLayout(src_btns, row, 1, 1, 3)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Capa de receptores:", "Explain receiver layers, categories and day/night limits", "receivers"), row, 0)
        self.cb_receivers = QtWidgets.QComboBox()
        self.cb_receivers.currentIndexChanged.connect(self._on_receiver_changed)
        grid_inputs.addWidget(self.cb_receivers, row, 1, 1, 3)
        row += 1

        self.chk_multi_receivers = QtWidgets.QCheckBox("Usar varias capas de receptores por categoría")
        self.chk_multi_receivers.setChecked(bool(self._qsettings.value("noise/use_multi_receivers", False, type=bool)))
        self.chk_multi_receivers.toggled.connect(self._on_multi_receivers_toggled)
        grid_inputs.addWidget(self.chk_multi_receivers, row, 0, 1, 2)

        self.cb_limit_scenario = QtWidgets.QComboBox()
        self.cb_limit_scenario.addItem("Manual / global", "custom")
        self.cb_limit_scenario.addItem("Diurno", "day")
        self.cb_limit_scenario.addItem("Nocturno", "night")
        idx_scn = self.cb_limit_scenario.findData(self._qsettings.value("noise/receiver_limit_scenario", "day", type=str), QtCore.Qt.UserRole)
        if idx_scn >= 0:
            self.cb_limit_scenario.setCurrentIndex(idx_scn)
        self.cb_limit_scenario.currentIndexChanged.connect(lambda *_: self._qsettings.setValue("noise/receiver_limit_scenario", str(self.cb_limit_scenario.currentData(QtCore.Qt.UserRole) or 'day')))
        self.cb_limit_scenario.setToolTip("Selecciona qué campo de límite se aplica a cada receptor. No cambia la física del ruido, solo el criterio de evaluación.")
        grid_inputs.addWidget(self._label_with_help("Criterio de límite:", "Explain manual, day and night receiver limits", "receivers"), row, 2)
        grid_inputs.addWidget(self.cb_limit_scenario, row, 3)
        row += 1

        self.tbl_receiver_groups = QtWidgets.QTableWidget(0, 6)
        self.tbl_receiver_groups.setHorizontalHeaderLabels(["Usar", "Capa", "Tipo", "Límite día", "Límite noche", "Altura [m]"])
        configure_table(self.tbl_receiver_groups, stretch_columns=(1,), min_height=120)
        hh_rg = self.tbl_receiver_groups.horizontalHeader()
        hh_rg.setStretchLastSection(False)
        hh_rg.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hh_rg.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for c in (2,3,4,5):
            hh_rg.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
        grid_inputs.addWidget(self.tbl_receiver_groups, row, 0, 1, 4)
        row += 1

        btn_rg_row = QtWidgets.QHBoxLayout()
        self.btn_rg_add = QtWidgets.QPushButton("Añadir capa receptores")
        self.btn_rg_del = QtWidgets.QPushButton("Quitar capa seleccionada")
        self.btn_rg_add.clicked.connect(self._add_receiver_group_row)
        self.btn_rg_del.clicked.connect(self._remove_receiver_group_row)
        btn_rg_row.addWidget(self.btn_rg_add)
        btn_rg_row.addWidget(self.btn_rg_del)
        btn_rg_row.addStretch(1)
        grid_inputs.addLayout(btn_rg_row, row, 0, 1, 4)
        row += 1

        self.chk_use_layout = QtWidgets.QCheckBox("Usar layouts de turbinas seleccionados/detectados")
        self.chk_use_layout.setChecked(True)
        self.chk_use_layout.setEnabled(False)
        grid_inputs.addWidget(self.chk_use_layout, row, 0, 1, 2)

        self.chk_generate_grid = QtWidgets.QCheckBox("Generar mapa GIS de ruido (malla de cálculo)")
        self.chk_generate_grid.setChecked(bool(self._qsettings.value("noise/generate_grid", True, type=bool)))
        self.chk_generate_grid.toggled.connect(lambda v: self._qsettings.setValue("noise/generate_grid", bool(v)))
        grid_inputs.addWidget(self.chk_generate_grid, row, 2, 1, 2)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Altura de receptor [m]:", "Explain receiver height, maximum radius and DEM/DSM use", "terrain"), row, 0)
        self.sp_receiver_h = QtWidgets.QDoubleSpinBox()
        self.sp_receiver_h.setDecimals(1)
        self.sp_receiver_h.setRange(0.0, 50.0)
        self.sp_receiver_h.setValue(float(self._qsettings.value("noise/receiver_height_m", 4.0, type=float)))
        self.sp_receiver_h.setSuffix(" m")
        self.sp_receiver_h.valueChanged.connect(lambda v: self._qsettings.setValue("noise/receiver_height_m", float(v)))
        grid_inputs.addWidget(self.sp_receiver_h, row, 1)

        grid_inputs.addWidget(self._label_with_help("Radio máximo [m]:", "Explain receiver height, maximum radius and DEM/DSM use", "terrain"), row, 2)
        self.sp_max_radius = QtWidgets.QDoubleSpinBox()
        self.sp_max_radius.setDecimals(0)
        self.sp_max_radius.setRange(100.0, 50000.0)
        self.sp_max_radius.setSingleStep(100.0)
        self.sp_max_radius.setValue(float(self._qsettings.value("noise/max_radius_m", 5000.0, type=float)))
        self.sp_max_radius.setSuffix(" m")
        self.sp_max_radius.valueChanged.connect(lambda v: self._qsettings.setValue("noise/max_radius_m", float(v)))
        grid_inputs.addWidget(self.sp_max_radius, row, 3)
        row += 1

        grid_inputs.addWidget(self._label_with_help("MDT / DSM (opcional):", "Explain receiver height, maximum radius and DEM/DSM use", "terrain"), row, 0)
        self.cb_dem = QtWidgets.QComboBox()
        grid_inputs.addWidget(self.cb_dem, row, 1, 1, 3)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Resolución del mapa [m]:", "Explain the GIS noise map, raster resolution and isophones", "map"), row, 0)
        self.sp_grid_res = QtWidgets.QSpinBox()
        self.sp_grid_res.setRange(10, 5000)
        self.sp_grid_res.setSingleStep(10)
        self.sp_grid_res.setValue(int(self._qsettings.value("noise/grid_resolution_m", 100, type=int)))
        self.sp_grid_res.setSuffix(" m")
        self.sp_grid_res.valueChanged.connect(lambda v: self._qsettings.setValue("noise/grid_resolution_m", int(v)))
        grid_inputs.addWidget(self.sp_grid_res, row, 1)

        self.chk_iso = QtWidgets.QCheckBox("Generar isófonas")
        self.chk_iso.setChecked(bool(self._qsettings.value("noise/prepare_iso", False, type=bool)))
        self.chk_iso.toggled.connect(lambda v: self._qsettings.setValue("noise/prepare_iso", bool(v)))
        grid_inputs.addWidget(self.chk_iso, row, 2, 1, 2)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Niveles isófonas [dB(A)]:", "Explain the GIS noise map, raster resolution and isophones", "map"), row, 0)
        self.le_iso_levels = QtWidgets.QLineEdit(str(self._qsettings.value("noise/iso_levels", "35,40,45,50", type=str)))
        self.le_iso_levels.editingFinished.connect(lambda: self._qsettings.setValue("noise/iso_levels", self.le_iso_levels.text().strip()))
        grid_inputs.addWidget(self.le_iso_levels, row, 1)

        grid_inputs.addWidget(self._label_with_help("Límite receptor [dB(A)]:", "Explain receiver layers, categories and day/night limits", "receivers"), row, 2)
        self.sp_limit = QtWidgets.QDoubleSpinBox()
        self.sp_limit.setDecimals(1)
        self.sp_limit.setRange(0.0, 120.0)
        self.sp_limit.setValue(float(self._qsettings.value("noise/receiver_limit_dba", 45.0, type=float)))
        self.sp_limit.setSuffix(" dB(A)")
        self.sp_limit.valueChanged.connect(lambda v: self._qsettings.setValue("noise/receiver_limit_dba", float(v)))
        grid_inputs.addWidget(self.sp_limit, row, 3)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Atenuación lineal α [dB/m]:", "Explain simplified atmospheric attenuation, ground factor G and land-use layers", "ground"), row, 0)
        self.sp_alpha = QtWidgets.QDoubleSpinBox()
        self.sp_alpha.setDecimals(4)
        self.sp_alpha.setRange(0.0, 0.0500)
        self.sp_alpha.setSingleStep(0.0005)
        self.sp_alpha.setValue(float(self._qsettings.value("noise/alpha_db_per_m", 0.005, type=float)))
        self.sp_alpha.valueChanged.connect(lambda v: self._qsettings.setValue("noise/alpha_db_per_m", float(v)))
        grid_inputs.addWidget(self.sp_alpha, row, 1)

        grid_inputs.addWidget(self._label_with_help("Factor de suelo G:", "Explain simplified atmospheric attenuation, ground factor G and land-use layers", "ground"), row, 2)
        self.sp_ground_g = QtWidgets.QDoubleSpinBox()
        self.sp_ground_g.setDecimals(2)
        self.sp_ground_g.setRange(0.0, 1.0)
        self.sp_ground_g.setSingleStep(0.05)
        self.sp_ground_g.setValue(float(self._qsettings.value("noise/ground_factor_g", 0.5, type=float)))
        self.sp_ground_g.valueChanged.connect(lambda v: self._qsettings.setValue("noise/ground_factor_g", float(v)))
        self.sp_ground_g.setToolTip("G=0 suelo duro · G=1 suelo poroso")
        grid_inputs.addWidget(self.sp_ground_g, row, 3)
        row += 1

        grid_inputs.addWidget(self._label_with_help("Modo suelo:", "Explain simplified atmospheric attenuation, ground factor G and land-use layers", "ground"), row, 0)
        self.cb_ground_mode = QtWidgets.QComboBox()
        self.cb_ground_mode.addItem("Global (G manual)", "global")
        self.cb_ground_mode.addItem("Desde capa de uso del suelo", "landuse")
        idx_gm = self.cb_ground_mode.findData(self._qsettings.value("noise/ground_mode", "global", type=str), QtCore.Qt.UserRole)
        if idx_gm >= 0:
            self.cb_ground_mode.setCurrentIndex(idx_gm)
        self.cb_ground_mode.currentIndexChanged.connect(lambda *_: self._on_ground_mode_changed())
        grid_inputs.addWidget(self.cb_ground_mode, row, 1)

        grid_inputs.addWidget(self._label_with_help("Capa uso del suelo (opcional):", "Explain simplified atmospheric attenuation, ground factor G and land-use layers", "ground"), row, 2)
        self.cb_landuse = QtWidgets.QComboBox()
        grid_inputs.addWidget(self.cb_landuse, row, 3)
        row += 1

        self.lbl_method = QtWidgets.QLabel("Método fuente-receptor eólico (Adiv + Aatm + Aground)")
        self.lbl_method.setObjectName("noiseMinor")
        grid_inputs.addWidget(self.lbl_method, row, 0, 1, 4)
        row += 1

        # Acoustic engine selector
        grid_inputs.addWidget(self._label_with_help("Motor de cálculo:", "Explain the fast and ISO-aligned noise engines", "engine"), row, 0)
        self.cb_engine = QtWidgets.QComboBox()
        self.cb_engine.addItem("⚡ Rápido - LwA global simplificado", "fast")
        self.cb_engine.addItem("📊 ISO-aligned - ISO 9613-2 por bandas", "iso")
        engine_saved = self._qsettings.value("noise/calculation_engine", "fast", type=str)
        idx_engine = self.cb_engine.findData(engine_saved, QtCore.Qt.UserRole)
        if idx_engine >= 0:
            self.cb_engine.setCurrentIndex(idx_engine)
        self.cb_engine.currentIndexChanged.connect(self._on_engine_changed)
        self.cb_engine.setToolTip(
            "Motor rápido: cálculo simplificado para cribado acústico\n"
            "Motor ISO: cálculo por bandas según ISO 9613-2:2024"
        )
        grid_inputs.addWidget(self.cb_engine, row, 1, 1, 3)
        row += 1

        # Contenedor parámetros atmosféricos (solo Motor ISO)
        self.grp_atmos = QtWidgets.QGroupBox("⛅ Condiciones Atmosféricas (Motor ISO)")
        form_atmos = QtWidgets.QFormLayout(self.grp_atmos)
        atmos_help_wrap = QtWidgets.QWidget(self.grp_atmos)
        atmos_help = QtWidgets.QHBoxLayout(atmos_help_wrap)
        atmos_help.setContentsMargins(0, 0, 0, 0)
        atmos_help.addWidget(QtWidgets.QLabel(_tr("Temperature, humidity and pressure used by the ISO-aligned engine.")))
        atmos_help.addWidget(self._make_help_button("Explain how atmospheric conditions affect ISO-band absorption", "atmos"), 0)
        atmos_help.addStretch(1)
        form_atmos.addRow("", atmos_help_wrap)

        self.sp_temperature = QtWidgets.QDoubleSpinBox()
        self.sp_temperature.setDecimals(1)
        self.sp_temperature.setRange(-20.0, 50.0)
        self.sp_temperature.setValue(float(self._qsettings.value("noise/temperature_c", 15.0, type=float)))
        self.sp_temperature.setSuffix(" °C")
        self.sp_temperature.valueChanged.connect(lambda v: self._qsettings.setValue("noise/temperature_c", float(v)))
        form_atmos.addRow("Temperatura:", self.sp_temperature)

        self.sp_humidity = QtWidgets.QDoubleSpinBox()
        self.sp_humidity.setDecimals(1)
        self.sp_humidity.setRange(0.0, 100.0)
        self.sp_humidity.setValue(float(self._qsettings.value("noise/humidity_percent", 70.0, type=float)))
        self.sp_humidity.setSuffix(" %")
        self.sp_humidity.valueChanged.connect(lambda v: self._qsettings.setValue("noise/humidity_percent", float(v)))
        form_atmos.addRow("Humedad relativa:", self.sp_humidity)

        self.sp_pressure = QtWidgets.QDoubleSpinBox()
        self.sp_pressure.setDecimals(3)
        self.sp_pressure.setRange(80.0, 110.0)
        self.sp_pressure.setValue(float(self._qsettings.value("noise/pressure_kpa", 101.325, type=float)))
        self.sp_pressure.setSuffix(" kPa")
        self.sp_pressure.setToolTip(
            "Presión atmosférica local en kPa. Valor de referencia habitual a nivel del mar: 101.325 kPa. "
            "Usa un dato medido o ajustado por altitud si está disponible."
        )
        self.sp_pressure.valueChanged.connect(lambda v: self._qsettings.setValue("noise/pressure_kpa", float(v)))
        form_atmos.addRow("Presión atmosférica:", self.sp_pressure)

        help_atmos = QtWidgets.QLabel("💡 Usa condiciones típicas del emplazamiento. Si no tienes presión medida, 101.325 kPa es una referencia estándar a nivel del mar; en altitud suele ser menor.")
        help_atmos.setWordWrap(True)
        help_atmos.setObjectName("noiseMinor")
        form_atmos.addRow("", help_atmos)

        grid_inputs.addWidget(self.grp_atmos, row, 0, 1, 4)
        row += 1
        # End acoustic engine selector

        grid_inputs.addWidget(self._label_with_help("Escenario acústico:", "Explain fixed LwA, acoustic curves and worst-case mode", "acoustic"), row, 0)
        self.cb_acoustic_mode = QtWidgets.QComboBox()
        self.cb_acoustic_mode.addItem("LwA fijo por grupo fuente", "fixed")
        self.cb_acoustic_mode.addItem("Acoustic curve LwA(ws)", "curve")
        idx_mode = self.cb_acoustic_mode.findData(self._qsettings.value("noise/acoustic_mode", "fixed", type=str), QtCore.Qt.UserRole)
        if idx_mode >= 0:
            self.cb_acoustic_mode.setCurrentIndex(idx_mode)
        self.cb_acoustic_mode.currentIndexChanged.connect(self._on_acoustic_scenario_changed)
        self.cb_acoustic_mode.currentTextChanged.connect(self._on_acoustic_scenario_changed)
        try:
            self.cb_acoustic_mode.activated.connect(self._on_acoustic_scenario_changed)
        except Exception:
            pass
        grid_inputs.addWidget(self.cb_acoustic_mode, row, 1)

        grid_inputs.addWidget(self._label_with_help("Velocidad eval. [m/s]:", "Explain fixed LwA, acoustic curves and worst-case mode", "acoustic"), row, 2)
        self.sp_eval_ws = QtWidgets.QDoubleSpinBox()
        self.sp_eval_ws.setDecimals(1)
        self.sp_eval_ws.setRange(0.0, 50.0)
        self.sp_eval_ws.setSingleStep(0.5)
        self.sp_eval_ws.setValue(float(self._qsettings.value("noise/eval_ws_m_s", 8.0, type=float)))
        self.sp_eval_ws.valueChanged.connect(self._on_acoustic_scenario_changed)
        grid_inputs.addWidget(self.sp_eval_ws, row, 3)
        row += 1

        self.chk_curve_worst = QtWidgets.QCheckBox("Usar peor caso de la curva")
        self.chk_curve_worst.setChecked(bool(self._qsettings.value("noise/curve_worst_case", False, type=bool)))
        self.chk_curve_worst.toggled.connect(self._on_acoustic_scenario_changed)
        grid_inputs.addWidget(self.chk_curve_worst, row, 0, 1, 2)
        self.lbl_acoustic_minor = QtWidgets.QLabel("En modo curva, cada grupo fuente puede usar un CSV ws/LwA distinto.")
        self.lbl_acoustic_minor.setObjectName("noiseMinor")
        grid_inputs.addWidget(self.lbl_acoustic_minor, row, 2, 1, 2)
        self._acoustic_mode_state = str(self._qsettings.value("noise/acoustic_mode", "fixed", type=str) or "fixed").strip().lower()
        root.addWidget(grp_inputs)

        grp_em = QtWidgets.QGroupBox("Configuración de grupos fuente acústicos")
        em_lay = QtWidgets.QVBoxLayout(grp_em)
        em_help = QtWidgets.QHBoxLayout()
        em_help.setContentsMargins(0, 0, 0, 0)
        em_help.addWidget(QtWidgets.QLabel(_tr("Review the acoustic emission assigned to each source group before running the calculation.")))
        em_help.addWidget(self._make_help_button("Explain the acoustic source-group table", "groups"), 0)
        em_help.addStretch(1)
        em_lay.addLayout(em_help)
        self.tbl_models = QtWidgets.QTableWidget(0, 9)
        self.tbl_models.setMinimumHeight(180)
        self.tbl_models.setHorizontalHeaderLabels([
            "Grupo fuente", "Parque", "Modelo base", "Turbinas", "HH [m]", "D [m]", "LwA fijo [dB(A)]", "Curva CSV", "Notas"
        ])
        configure_table(self.tbl_models, stretch_columns=(0, 7, 8), min_height=180)
        hh = self.tbl_models.horizontalHeader()
        try:
            hh.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            hh.setSectionResizeMode(7, QtWidgets.QHeaderView.Stretch)
            hh.setSectionResizeMode(8, QtWidgets.QHeaderView.Stretch)
        except Exception:
            pass
        self.tbl_models.verticalHeader().setVisible(False)
        self.tbl_models.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_models.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_models.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)
        self.tbl_models.setToolTip(_tr("Each row represents an acoustic source group. You can rename the group/wind farm and edit its fixed LwA directly in the table."))
        em_lay.addWidget(self.tbl_models)

        curve_btns = QtWidgets.QHBoxLayout()
        self.btn_curve_load = QtWidgets.QPushButton("Importar curva acústica para el grupo fuente seleccionado…")
        self.btn_curve_load.clicked.connect(self._import_curve_for_selected_model)
        self.btn_curve_clear = QtWidgets.QPushButton("Limpiar curva del grupo fuente seleccionado")
        self.btn_curve_clear.clicked.connect(self._clear_curve_for_selected_model)
        curve_btns.addWidget(self.btn_curve_load)
        curve_btns.addWidget(self.btn_curve_clear)
        curve_btns.addStretch(1)
        em_lay.addLayout(curve_btns)

        help_lbl = QtWidgets.QLabel(
            "Puedes editar el LwA fijo directamente en la tabla de grupos fuente acústicos o importar una curva acústica ws/LwA por grupo. "
            "Si activas el modo curva, el plugin evaluará la emisión a una velocidad concreta o en peor caso."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setObjectName("noiseMinor")
        em_lay.addWidget(help_lbl)
        root.addWidget(grp_em, 1)

        grp_actions = QtWidgets.QGroupBox("Preparación del cálculo")
        act_lay = QtWidgets.QVBoxLayout(grp_actions)
        self.txt_status = QtWidgets.QTextEdit()
        self.txt_status.setReadOnly(True)
        self.txt_status.setMinimumHeight(120)
        self.txt_status.setMaximumHeight(220)
        act_lay.addWidget(self.txt_status)

        progress_lay = QtWidgets.QHBoxLayout()
        self.lbl_noise_progress = QtWidgets.QLabel("Listo.")
        self.lbl_noise_progress.setObjectName("noiseMinor")
        self.lbl_noise_progress.setMinimumWidth(220)
        self.pb_noise_progress = QtWidgets.QProgressBar()
        self.pb_noise_progress.setRange(0, 100)
        self.pb_noise_progress.setValue(0)
        self.pb_noise_progress.setTextVisible(True)
        self.pb_noise_progress.setVisible(False)
        self.lbl_noise_progress.setVisible(False)
        progress_lay.addWidget(self.lbl_noise_progress)
        progress_lay.addWidget(self.pb_noise_progress, 1)
        act_lay.addLayout(progress_lay)
        self._noise_grid_task = None

        btns = QtWidgets.QHBoxLayout()
        self.btn_check = QtWidgets.QPushButton("Comprobar configuración")
        self.btn_check.setMinimumHeight(34)
        self.btn_check.clicked.connect(self._check_configuration)
        self.btn_calc = QtWidgets.QPushButton("Calcular ruido")
        self.btn_calc.setMinimumHeight(34)
        self.btn_calc.clicked.connect(self._run_noise)
        btns.addStretch(1)
        btns.addWidget(self.btn_check)
        btns.addWidget(self.btn_calc)
        act_lay.addLayout(btns)
        root.addWidget(grp_actions)

        # Initialise acoustic-engine visibility
        QtCore.QTimer.singleShot(0, self._on_engine_changed)
        # End acoustic-engine visibility setup

    def _apply_style(self):
        self.setStyleSheet(
            self.styleSheet()
            + """
            QLabel#noiseTitle { font-size: 22px; font-weight: 700; color: #103b67; }
            QLabel#noiseSubtitle { font-size: 12px; color: #4f5d6b; }
            QLabel#noiseMinor { font-size: 11px; color: #667480; }
            QTextEdit { background: white; }
            QGroupBox { background: white; }
            QTableWidget { background: white; }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton { min-height: 28px; }
            """
        )

    def _on_engine_changed(self):
        """Muestra/oculta parámetros según el motor elegido."""
        try:
            engine = self.cb_engine.currentData(QtCore.Qt.UserRole) or "fast"
        except:
            engine = "fast"
        
        self._qsettings.setValue("noise/calculation_engine", engine)
        
        # Mostrar/ocultar parámetros atmosféricos
        is_iso = (engine == "iso")
        self.grp_atmos.setVisible(is_iso)
        
        # Actualizar label de método
        if is_iso:
            self.lbl_method.setText(
                "Método ISO-aligned: ISO 9613-2 con bandas de octava (Adiv + Aatm(T,RH,P) + Agr(f))"
            )
            # Deshabilitar α porque se calcula automático
            try:
                self.sp_alpha.setEnabled(False)
                self.sp_alpha.setToolTip("α se calcula automáticamente por banda en Motor ISO")
            except:
                pass
        else:
            self.lbl_method.setText(
                "Método fuente-receptor eólico (Adiv + Aatm + Aground)"
            )
            try:
                self.sp_alpha.setEnabled(True)
                self.sp_alpha.setToolTip("")
            except:
                pass
        
        try:
            self._check_configuration()
        except:
            pass

    def _import_turbine_layout_for_noise(self):
        """Import a turbine-coordinate CSV directly from the Noise module."""
        try:
            layer = import_turbine_layout_from_csv(self, module="noise")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Noise · Import layout", f"Could not import the turbine layout:\n{e}")
            return
        if layer is None:
            return
        try:
            default_lwa = layer.customProperty("velantis/default_lwa_dba", None)
            if default_lwa is not None:
                settings = self._load_noise_model_settings()
                settings[str(layer.id())] = float(default_lwa)
                self._qsettings.setValue("noise/source_group_lwa_json", json.dumps(settings, ensure_ascii=False))
        except Exception:
            pass
        self.refresh_from_project()
        QtWidgets.QMessageBox.information(
            self,
            "Noise · Import layout",
            f"Imported '{layer.name()}' with {int(layer.featureCount())} turbine(s)."
        )

    def refresh_from_project(self):
        prj = QgsProject.instance()
        self._model_rows = self._detect_models(prj)
        self._populate_context(prj)
        self._populate_sources_combo(prj)
        self._populate_receivers_combo(prj)
        self._populate_receiver_group_table()
        self._populate_dem_combo(prj)
        self._populate_landuse_combo(prj)
        self._populate_models_table()
        self._on_ground_mode_changed()
        self._check_configuration()

    def _populate_context(self, prj: QgsProject):
        base_name = (prj.baseName() or "Unnamed project").strip() or "Unnamed project"
        self.lbl_project.setText(base_name)
        self.lbl_crs.setText(prj.crs().authid() or "CRS unavailable")

        n_models = len(self._model_rows)
        n_turbs = sum(int(r.get("n_turbines", 0)) for r in self._model_rows)
        if n_models <= 0:
            self.lbl_layout.setText("No layout detected in the coordinate-by-model group")
            self.lbl_models.setText("0")
        else:
            self.lbl_layout.setText(f"{n_models} WT model(s) · {n_turbs} turbine(s)")
            names = ", ".join(str(r.get("name", "-")) for r in self._model_rows[:5])
            if n_models > 5:
                names += " …"
            self.lbl_models.setText(names)

        wrg = (self._qsettings.value("last_wrg_path", "", type=str) or "").strip()
        wasp = (self._qsettings.value("last_wasp_dir", "", type=str) or "").strip()
        if wrg:
            self.lbl_resource.setText(f"WRG: {os.path.basename(wrg)}")
        elif wasp:
            self.lbl_resource.setText(f"WAsP grids: {wasp}")
        else:
            self.lbl_resource.setText("No resource selected yet")

        ti = (self._qsettings.value("last_wrg_ti_path", "", type=str) or "").strip()
        if ti:
            parts = [os.path.basename(p.strip()) for p in ti.split(";") if p.strip()]
            self.lbl_ti.setText(", ".join(parts[:3]) + (" …" if len(parts) > 3 else ""))
        else:
            self.lbl_ti.setText("Not selected")

    def _populate_sources_combo(self, prj: QgsProject):
        raw = self._qsettings.value("noise/source_layer_ids_json", "", type=str) or ""
        selected_ids = set()
        if raw:
            try:
                vals = json.loads(raw)
                if isinstance(vals, list):
                    selected_ids = {str(v) for v in vals if str(v)}
            except Exception:
                selected_ids = set()
        saved_source_layer_id = self._qsettings.value("noise/source_layer_id", "__AUTO_ALL__", type=str) or "__AUTO_ALL__"
        self.lst_sources.blockSignals(True)
        self.lst_sources.clear()
        all_layer_ids = []
        for info in self._model_rows:
            lid = str(info.get("layer_id") or "")
            if not lid:
                continue
            all_layer_ids.append(lid)
            name = str(info.get("name") or "Modelo")
            n = int(info.get("n_turbines") or 0)
            item = QtWidgets.QListWidgetItem(f"{name} · {n} turbine(s)")
            item.setData(QtCore.Qt.UserRole, lid)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            checked = True
            if selected_ids:
                checked = lid in selected_ids
            elif saved_source_layer_id not in ("", "__AUTO_ALL__"):
                checked = (lid == saved_source_layer_id)
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            self.lst_sources.addItem(item)
        if all_layer_ids and not any(self.lst_sources.item(i).checkState() == QtCore.Qt.Checked for i in range(self.lst_sources.count())):
            for i in range(self.lst_sources.count()):
                self.lst_sources.item(i).setCheckState(QtCore.Qt.Checked)
        self.lst_sources.blockSignals(False)
        self._on_sources_changed()

    def _populate_receivers_combo(self, prj: QgsProject):
        current_id = self._qsettings.value("noise/receiver_layer_id", self.cb_receivers.currentData(QtCore.Qt.UserRole), type=str)
        model_layer_ids = {str(r.get("layer_id")) for r in self._model_rows if r.get("layer_id")}
        self.cb_receivers.blockSignals(True)
        self.cb_receivers.clear()
        self.cb_receivers.addItem("— Select receiver layer —", None)
        for lyr in prj.mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if bool(lyr.customProperty("velantis/noise_output", False)):
                continue
            if lyr.id() in model_layer_ids:
                continue
            lname = (lyr.name() or "").lower()
            if "contexto_ruido" in lname or lname.startswith("contexto"):
                continue
            gtype = QgsWkbTypes.geometryType(lyr.wkbType())
            if gtype in (QgsWkbTypes.PointGeometry, QgsWkbTypes.PolygonGeometry):
                self.cb_receivers.addItem(f"{lyr.name()} [{self._geom_label(gtype)}]", lyr.id())
        idx = self.cb_receivers.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_receivers.setCurrentIndex(idx)
        self.cb_receivers.blockSignals(False)
        self._on_receiver_changed()


    def _receiver_candidate_layers(self):
        prj = QgsProject.instance()
        model_layer_ids = {str(r.get("layer_id")) for r in self._model_rows if r.get("layer_id")}
        out = []
        for lyr in prj.mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if bool(lyr.customProperty("velantis/noise_output", False)):
                continue
            if lyr.id() in model_layer_ids:
                continue
            lname = (lyr.name() or "").lower()
            if "contexto_ruido" in lname or lname.startswith("contexto"):
                continue
            gtype = QgsWkbTypes.geometryType(lyr.wkbType())
            if gtype in (QgsWkbTypes.PointGeometry, QgsWkbTypes.PolygonGeometry):
                out.append(lyr)
        return out

    def _populate_receiver_group_table(self):
        self.tbl_receiver_groups.setRowCount(0)
        saved = self._qsettings.value("noise/receiver_groups_json", "", type=str) or ""
        groups = []
        if saved:
            try:
                groups = json.loads(saved)
            except Exception:
                groups = []
        if not groups:
            rid = self.cb_receivers.currentData(QtCore.Qt.UserRole)
            if rid:
                lyr = QgsProject.instance().mapLayer(rid)
                if lyr is not None:
                    groups = [{"layer_id": lyr.id(), "type": "general", "day": float(self.sp_limit.value()), "night": float(self.sp_limit.value()), "height": float(self.sp_receiver_h.value()), "enabled": True}]
        for g in groups:
            self._add_receiver_group_row(g)
        self._on_multi_receivers_toggled(bool(self.chk_multi_receivers.isChecked()))

    def _save_receiver_groups(self):
        groups = []
        for r in range(self.tbl_receiver_groups.rowCount()):
            w_enabled = self.tbl_receiver_groups.cellWidget(r,0)
            w_layer = self.tbl_receiver_groups.cellWidget(r,1)
            w_type = self.tbl_receiver_groups.cellWidget(r,2)
            w_day = self.tbl_receiver_groups.cellWidget(r,3)
            w_night = self.tbl_receiver_groups.cellWidget(r,4)
            w_h = self.tbl_receiver_groups.cellWidget(r,5)
            groups.append({
                "enabled": bool(w_enabled.isChecked()) if w_enabled else True,
                "layer_id": str(w_layer.currentData(QtCore.Qt.UserRole) or "") if w_layer else "",
                "type": str(w_type.text() or "general") if w_type else "general",
                "day": float(w_day.value()) if w_day else float(self.sp_limit.value()),
                "night": float(w_night.value()) if w_night else float(self.sp_limit.value()),
                "height": float(w_h.value()) if w_h else float(self.sp_receiver_h.value()),
            })
        self._qsettings.setValue("noise/receiver_groups_json", json.dumps(groups, ensure_ascii=False))
        self._qsettings.setValue("noise/use_multi_receivers", bool(self.chk_multi_receivers.isChecked()))

    def _add_receiver_group_row(self, group=None):
        group = group or {}
        row = self.tbl_receiver_groups.rowCount()
        self.tbl_receiver_groups.insertRow(row)
        chk = QtWidgets.QCheckBox()
        chk.setChecked(bool(group.get("enabled", True)))
        chk.toggled.connect(lambda *_: self._save_receiver_groups())
        self.tbl_receiver_groups.setCellWidget(row, 0, chk)

        cb = QtWidgets.QComboBox()
        for lyr in self._receiver_candidate_layers():
            cb.addItem(lyr.name(), lyr.id())
        target_id = str(group.get("layer_id") or "")
        idx = cb.findData(target_id, QtCore.Qt.UserRole)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        cb.currentIndexChanged.connect(lambda *_: self._save_receiver_groups())
        self.tbl_receiver_groups.setCellWidget(row, 1, cb)

        le = QtWidgets.QLineEdit(str(group.get("type") or "general"))
        le.editingFinished.connect(self._save_receiver_groups)
        self.tbl_receiver_groups.setCellWidget(row, 2, le)

        for col,key,default in [(3,"day", float(self.sp_limit.value())), (4,"night", float(self.sp_limit.value())), (5,"height", float(self.sp_receiver_h.value()))]:
            sp = QtWidgets.QDoubleSpinBox()
            sp.setDecimals(1)
            sp.setRange(0.0, 120.0 if col in (3,4) else 50.0)
            sp.setValue(float(group.get(key, default)))
            sp.valueChanged.connect(lambda *_: self._save_receiver_groups())
            self.tbl_receiver_groups.setCellWidget(row, col, sp)
        self._save_receiver_groups()

    def _remove_receiver_group_row(self):
        row = self.tbl_receiver_groups.currentRow()
        if row >= 0:
            self.tbl_receiver_groups.removeRow(row)
            self._save_receiver_groups()
            self._check_configuration()

    def _on_multi_receivers_toggled(self, checked):
        for w in [self.tbl_receiver_groups, self.btn_rg_add, self.btn_rg_del, self.cb_limit_scenario]:
            w.setEnabled(bool(checked))
        self.cb_receivers.setEnabled(not bool(checked))
        self.sp_receiver_h.setEnabled(not bool(checked))
        self.sp_limit.setEnabled(not bool(checked))
        self._qsettings.setValue("noise/use_multi_receivers", bool(checked))
        self._save_receiver_groups()
        self._check_configuration()

    def _build_multi_receiver_layer(self):
        fields = QgsFields()
        fields.append(QgsField("grp_type", QtCore.QVariant.String))
        fields.append(QgsField("grp_h_m", QtCore.QVariant.Double))
        fields.append(QgsField("grp_lim_d", QtCore.QVariant.Double))
        fields.append(QgsField("grp_lim_n", QtCore.QVariant.Double))
        fields.append(QgsField("grp_lim_c", QtCore.QVariant.Double))
        fields.append(QgsField("grp_src", QtCore.QVariant.String))
        feats = []
        total = 0
        for r in range(self.tbl_receiver_groups.rowCount()):
            w_enabled = self.tbl_receiver_groups.cellWidget(r,0)
            if w_enabled and not w_enabled.isChecked():
                continue
            w_layer = self.tbl_receiver_groups.cellWidget(r,1)
            lyr = QgsProject.instance().mapLayer(str(w_layer.currentData(QtCore.Qt.UserRole) or "")) if w_layer else None
            if not isinstance(lyr, QgsVectorLayer):
                continue
            gtype = QgsWkbTypes.geometryType(lyr.wkbType())
            w_type = self.tbl_receiver_groups.cellWidget(r,2)
            w_day = self.tbl_receiver_groups.cellWidget(r,3)
            w_night = self.tbl_receiver_groups.cellWidget(r,4)
            w_h = self.tbl_receiver_groups.cellWidget(r,5)
            for f in lyr.getFeatures():
                nf = QgsFeature(fields)
                geom = f.geometry()
                if geom is None or geom.isEmpty():
                    continue
                try:
                    if gtype == QgsWkbTypes.PointGeometry:
                        pt = geom.asPoint()
                    else:
                        pt = geom.centroid().asPoint()
                    nf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(pt.x()), float(pt.y()))))
                except Exception:
                    continue
                nf.setAttributes([
                    str(w_type.text() or "general") if w_type else "general",
                    float(w_h.value()) if w_h else float(self.sp_receiver_h.value()),
                    float(w_day.value()) if w_day else float(self.sp_limit.value()),
                    float(w_night.value()) if w_night else float(self.sp_limit.value()),
                    float(self.sp_limit.value()),
                    lyr.name(),
                ])
                feats.append(nf)
                total += 1
        if not feats:
            return None, 0
        mem = QgsVectorLayer(f"Point?crs={QgsProject.instance().crs().authid() or 'EPSG:25830'}", "__noise_multi_receivers__", "memory")
        pr = mem.dataProvider()
        pr.addAttributes(fields)
        mem.updateFields()
        pr.addFeatures(feats)
        mem.updateExtents()
        return mem, total

    def _populate_dem_combo(self, prj: QgsProject):
        try:
            self.cb_dem.currentIndexChanged.disconnect(self._on_dem_changed)
        except Exception:
            pass
        current_id = self._qsettings.value("noise/dem_layer_id", self.cb_dem.currentData(QtCore.Qt.UserRole), type=str)
        self.cb_dem.clear()
        self.cb_dem.addItem("— Sin MDT/DSM —", None)
        for lyr in prj.mapLayers().values():
            if isinstance(lyr, QgsRasterLayer):
                self.cb_dem.addItem(lyr.name(), lyr.id())
        idx = self.cb_dem.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_dem.setCurrentIndex(idx)
        self.cb_dem.currentIndexChanged.connect(self._on_dem_changed)


    def _populate_landuse_combo(self, prj: QgsProject):
        try:
            self.cb_landuse.currentIndexChanged.disconnect(self._on_landuse_changed)
        except Exception:
            pass
        current_id = self._qsettings.value("noise/landuse_layer_id", self.cb_landuse.currentData(QtCore.Qt.UserRole), type=str)
        self.cb_landuse.clear()
        self.cb_landuse.addItem("— Sin capa de uso del suelo —", None)
        for lyr in prj.mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if bool(lyr.customProperty("velantis/noise_output", False)):
                continue
            if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PolygonGeometry:
                continue
            lname = (lyr.name() or "").lower()
            if lname.startswith("ruido ·"):
                continue
            self.cb_landuse.addItem(lyr.name(), lyr.id())
        idx = self.cb_landuse.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_landuse.setCurrentIndex(idx)
        self.cb_landuse.currentIndexChanged.connect(self._on_landuse_changed)

    def _on_ground_mode_changed(self, *_args):
        mode = str(self.cb_ground_mode.currentData(QtCore.Qt.UserRole) or 'global')
        self._qsettings.setValue('noise/ground_mode', mode)
        use_land = (mode == 'landuse')
        self.cb_landuse.setEnabled(use_land)
        self._check_configuration()

    def _on_landuse_changed(self, *_args):
        self._qsettings.setValue('noise/landuse_layer_id', self.cb_landuse.currentData(QtCore.Qt.UserRole) or "")
        self._check_configuration()

    def _populate_models_table(self):
        try:
            self.tbl_models.itemChanged.disconnect(self._on_model_table_item_changed)
        except Exception:
            pass
        saved = self._load_noise_model_settings()
        saved_curves = self._load_curve_settings()
        acoustic_mode = self._current_acoustic_mode()
        self.tbl_models.setRowCount(len(self._model_rows))
        for row, info in enumerate(self._model_rows):
            name = str(info.get("name", f"Model {row+1}"))
            n_turbs = int(info.get("n_turbines", 0))
            hh = info.get("hub_height")
            diam = info.get("diameter")
            cfg_key = str(info.get("source_group_key") or info.get("layer_id") or name)
            lwa = float(saved.get(cfg_key, saved.get(name, info.get("default_lwa", 105.0))))
            curve_path = str(saved_curves.get(cfg_key, '') or saved_curves.get(name, '') or '')
            note = str(info.get("notes") or "Detected from project source layer")
            if curve_path:
                note = (note + ' · ' + self._curve_preview_text(curve_path)).strip(' ·')
            elif acoustic_mode == 'curve':
                note = (note + ' · no curve -> fixed LwA fallback').strip(' ·')
            park_name = str(info.get("park_name") or "")
            model_name = str(info.get("model_name") or name)
            items = [
                QtWidgets.QTableWidgetItem(name),
                QtWidgets.QTableWidgetItem(park_name),
                QtWidgets.QTableWidgetItem(model_name),
                QtWidgets.QTableWidgetItem(str(n_turbs)),
                QtWidgets.QTableWidgetItem("-" if hh is None else f"{float(hh):.1f}"),
                QtWidgets.QTableWidgetItem("-" if diam is None else f"{float(diam):.1f}"),
                QtWidgets.QTableWidgetItem(f"{lwa:.1f}"),
                QtWidgets.QTableWidgetItem(os.path.basename(curve_path) if curve_path else "—"),
                QtWidgets.QTableWidgetItem(note),
            ]
            for col, item in enumerate(items):
                if col in (2, 3, 4, 5, 6, 7, 8):
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                if col == 6:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    item.setToolTip(_tr("Edit the fixed LwA for this acoustic source group."))
                self.tbl_models.setItem(row, col, item)
            self.tbl_models.setCellWidget(row, 6, self._make_lwa_spinbox(lwa))
        self.tbl_models.itemChanged.connect(self._on_model_table_item_changed)

    def _make_lwa_spinbox(self, value: float) -> QtWidgets.QDoubleSpinBox:
        """Editable fixed LwA control embedded directly in the source-group table."""
        sp = QtWidgets.QDoubleSpinBox(self.tbl_models)
        sp.setDecimals(1)
        sp.setRange(0.0, 200.0)
        sp.setSingleStep(0.5)
        sp.setSuffix(" dB(A)")
        sp.setValue(float(value))
        sp.setKeyboardTracking(False)
        sp.setToolTip(_tr("Fixed acoustic emission level for this source group. Edit it here before running the calculation."))
        sp.valueChanged.connect(self._on_lwa_spinbox_changed)
        return sp

    def _model_lwa_value(self, row: int, default: float = 105.0) -> float:
        """Return the fixed LwA from the table, supporting both the spinbox UI and older text cells."""
        try:
            w = self.tbl_models.cellWidget(row, 6)
            if isinstance(w, QtWidgets.QDoubleSpinBox):
                return float(w.value())
        except Exception:
            pass
        try:
            item = self.tbl_models.item(row, 6)
            if item is not None:
                return float((item.text() or '').replace(',', '.'))
        except Exception:
            pass
        return float(default)

    def _on_lwa_spinbox_changed(self, *_args):
        """Persist direct edits from the LwA spinboxes and refresh validation/status text."""
        self.tbl_models.blockSignals(True)
        try:
            for row in range(self.tbl_models.rowCount()):
                w = self.tbl_models.cellWidget(row, 6)
                item = self.tbl_models.item(row, 6)
                if isinstance(w, QtWidgets.QDoubleSpinBox) and item is not None:
                    item.setText(f"{float(w.value()):.1f}")
        finally:
            self.tbl_models.blockSignals(False)
        self._save_noise_model_settings()
        self._check_configuration()

    def _detect_models(self, prj: QgsProject) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for lyr in self._iter_model_layers(prj):
            lname = lyr.name()
            base_name = (lyr.customProperty("velantis/model_name", "") or "").strip()
            if not base_name:
                base_name = lname[:-6] if lname.endswith(" (CSV)") else lname
            hh = lyr.customProperty("velantis/hub_height_m", None)
            diam = lyr.customProperty("velantis/diameter_m", None)
            notes = []
            if hh is not None:
                notes.append(f"HH={float(hh):.1f} m")
            if diam is not None:
                notes.append(f"D={float(diam):.1f} m")
            if lyr.customProperty("velantis/coords_csv", None):
                source_module = str(lyr.customProperty("velantis/source_module", "") or "").strip()
                notes.append(f"layout imported from {source_module}" if source_module else "layout imported from CSV")
            source_group_name = (lyr.customProperty("velantis/noise_group_name", "") or "").strip() or lname
            park_name = (lyr.customProperty("velantis/park_name", "") or "").strip()
            meta_overrides = self._load_source_group_meta_settings().get(lyr.id(), {})
            if str(meta_overrides.get("group_name") or "").strip():
                source_group_name = str(meta_overrides.get("group_name") or "").strip()
            if str(meta_overrides.get("park_name") or "").strip():
                park_name = str(meta_overrides.get("park_name") or "").strip()
            rows.append(
                {
                    "name": source_group_name,
                    "model_name": base_name,
                    "park_name": park_name,
                    "source_group_key": lyr.id(),
                    "layer_id": lyr.id(),
                    "layer_name": lname,
                    "n_turbines": int(lyr.featureCount()),
                    "hub_height": float(hh) if hh is not None else None,
                    "diameter": float(diam) if diam is not None else None,
                    "default_lwa": float(lyr.customProperty("velantis/default_lwa_dba", 105.0) or 105.0),
                    "notes": (("Wind farm=" + park_name + " · ") if park_name else "") + ("Model=" + base_name + (" · " + " · ".join(notes) if notes else "")),
                }
            )
        rows.sort(key=lambda r: str(r.get("name", "")))
        return rows

    def _is_model_layer(self, lyr) -> bool:
        try:
            if not isinstance(lyr, QgsVectorLayer):
                return False
            if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
                return False
            if bool(lyr.customProperty("velantis/noise_output", False)):
                return False
            name = (lyr.name() or "").strip()
            if name.startswith("Noise ·"):
                return False
            model_name = (lyr.customProperty("velantis/model_name", "") or "").strip()
            coords_csv = (lyr.customProperty("velantis/coords_csv", "") or "").strip()
            if model_name or coords_csv:
                return True
            if name.endswith(" (CSV)"):
                return True
        except Exception:
            return False
        return False

    def _iter_group_layers_recursive(self, node):
        try:
            children = node.children()
        except Exception:
            children = []
        for child in children:
            try:
                lyr = child.layer()
            except Exception:
                lyr = None
            if lyr is not None:
                yield lyr
            else:
                yield from self._iter_group_layers_recursive(child)

    def _iter_model_layers(self, prj: QgsProject) -> List[QgsVectorLayer]:
        """Find all Velantis turbine/model layers, not only Energy-generated ones."""
        out: List[QgsVectorLayer] = []
        seen = set()
        try:
            root = prj.layerTreeRoot()
            for child in root.children():
                try:
                    child_name = child.name()
                except Exception:
                    child_name = None
                if child_name not in (_GROUP_NAME, "VelantisWind · Turbine layouts"):
                    continue
                for lyr in self._iter_group_layers_recursive(child):
                    try:
                        lid = lyr.id()
                    except Exception:
                        lid = None
                    if lid and lid not in seen and self._is_model_layer(lyr):
                        out.append(lyr)
                        seen.add(lid)
        except Exception:
            pass
        for lyr in prj.mapLayers().values():
            try:
                lid = lyr.id()
            except Exception:
                lid = None
            if lid and lid not in seen and self._is_model_layer(lyr):
                out.append(lyr)
                seen.add(lid)
        return out

    def _geom_label(self, gtype: int) -> str:

        if gtype == QgsWkbTypes.PointGeometry:
            return "points"
        if gtype == QgsWkbTypes.PolygonGeometry:
            return "polygons"
        return "vector"

    def _load_source_group_meta_settings(self) -> Dict[str, Dict[str, str]]:
        raw = self._qsettings.value("noise/source_group_meta_json", "", type=str)
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            obj = {}
        out: Dict[str, Dict[str, str]] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    out[str(k)] = {
                        "group_name": str(v.get("group_name") or ""),
                        "park_name": str(v.get("park_name") or ""),
                    }
        return out

    def _save_source_group_meta_settings(self):
        data: Dict[str, Dict[str, str]] = {}
        for row, info in enumerate(self._model_rows):
            group_item = self.tbl_models.item(row, 0)
            park_item = self.tbl_models.item(row, 1)
            cfg_key = str(info.get("source_group_key") or info.get("layer_id") or (group_item.text().strip() if group_item else f"row_{row+1}"))
            data[cfg_key] = {
                "group_name": group_item.text().strip() if group_item else str(info.get("name") or ""),
                "park_name": park_item.text().strip() if park_item else str(info.get("park_name") or ""),
            }
        self._qsettings.setValue("noise/source_group_meta_json", json.dumps(data, ensure_ascii=False))

    def _load_noise_model_settings(self) -> Dict[str, float]:
        raw = self._qsettings.value("noise/source_group_lwa_json", "", type=str)
        if not raw:
            raw = self._qsettings.value("noise/model_lwa_json", "{}", type=str)
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            obj = {}
        out: Dict[str, float] = {}
        for k, v in obj.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out

    def _save_noise_model_settings(self):
        data: Dict[str, float] = {}
        for row in range(self.tbl_models.rowCount()):
            name_item = self.tbl_models.item(row, 0)
            if not name_item:
                continue
            try:
                cfg_key = str((self._model_rows[row].get("source_group_key") or self._model_rows[row].get("layer_id") or name_item.text().strip()))
                data[cfg_key] = float(self._model_lwa_value(row))
            except Exception:
                continue
        self._qsettings.setValue("noise/source_group_lwa_json", json.dumps(data, ensure_ascii=False))

    def _load_curve_settings(self) -> Dict[str, str]:
        raw = self._qsettings.value("noise/source_group_curve_json", "", type=str)
        if not raw:
            raw = self._qsettings.value("noise/model_curve_json", "{}", type=str)
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            obj = {}
        return {str(k): str(v) for k, v in obj.items() if str(v).strip()}

    def _save_curve_settings(self, data: Optional[Dict[str, str]] = None):
        if data is None:
            data = self._load_curve_settings()
        self._qsettings.setValue("noise/source_group_curve_json", json.dumps(data, ensure_ascii=False))

    def _selected_model_row(self) -> int:
        sel = self.tbl_models.selectionModel().selectedRows() if self.tbl_models.selectionModel() else []
        if sel:
            return int(sel[0].row())
        return 0 if self.tbl_models.rowCount() > 0 else -1

    def _curve_preview_text(self, path: str) -> str:
        try:
            ws, lwa = load_acoustic_curve_csv(path)
            if self.chk_curve_worst.isChecked():
                val = evaluate_acoustic_curve(ws, lwa, use_worst_case=True)
                return f"{os.path.basename(path)} · peor caso={val:.1f} dB(A)"
            val = evaluate_acoustic_curve(ws, lwa, eval_ws_m_s=float(self.sp_eval_ws.value()), use_worst_case=False)
            return f"{os.path.basename(path)} · {float(self.sp_eval_ws.value()):.1f} m/s → {val:.1f} dB(A)"
        except Exception as e:
            return f"{os.path.basename(path)} · inválida ({e})"

    def _import_curve_for_selected_model(self):
        row = self._selected_model_row()
        if row < 0:
            return
        name_item = self.tbl_models.item(row, 0)
        if not name_item:
            return
        model_name = name_item.text().strip()
        cfg_key = str((self._model_rows[row].get("source_group_key") or self._model_rows[row].get("layer_id") or model_name))
        start = self._load_curve_settings().get(cfg_key, "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Acoustic curve ws/LwA", start, "CSV/TXT (*.csv *.txt);;Todos (*.*)")
        if not path:
            return
        try:
            ws, lwa = load_acoustic_curve_csv(path)
            _ = evaluate_acoustic_curve(ws, lwa, eval_ws_m_s=float(self.sp_eval_ws.value()), use_worst_case=bool(self.chk_curve_worst.isChecked()))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Noise · Acoustic curve", f"Could not read the acoustic curve:\n{e}")
            return
        data = self._load_curve_settings()
        data[cfg_key] = path
        self._save_curve_settings(data)
        self._populate_models_table()
        self._check_configuration()

    def _clear_curve_for_selected_model(self):
        row = self._selected_model_row()
        if row < 0:
            return
        name_item = self.tbl_models.item(row, 0)
        if not name_item:
            return
        model_name = name_item.text().strip()
        cfg_key = str((self._model_rows[row].get("source_group_key") or self._model_rows[row].get("layer_id") or model_name))
        data = self._load_curve_settings()
        if cfg_key in data:
            del data[cfg_key]
            self._save_curve_settings(data)
        self._populate_models_table()
        self._check_configuration()

    def _current_acoustic_mode(self) -> str:
        """Return the acoustic mode robustly.

        QGIS/PyQt can occasionally report inconsistent combo box state after dynamic
        UI refreshes. Prefer the visible state, but keep an explicit cached state and
        the last saved QSettings value as additional fallbacks.
        """
        try:
            txt = (self.cb_acoustic_mode.currentText() or '').strip().lower()
        except Exception:
            txt = ''
        try:
            idx = int(self.cb_acoustic_mode.currentIndex())
        except Exception:
            idx = -1
        try:
            data = self.cb_acoustic_mode.currentData(QtCore.Qt.UserRole)
            data = str(data).strip().lower() if data is not None else ''
        except Exception:
            data = ''
        try:
            cached = str(getattr(self, '_acoustic_mode_state', '') or '').strip().lower()
        except Exception:
            cached = ''
        try:
            saved = str(self._qsettings.value('noise/acoustic_mode', '', type=str) or '').strip().lower()
        except Exception:
            saved = ''

        if 'curva' in txt or idx == 1 or data == 'curve':
            mode = 'curve'
        elif 'fijo' in txt or idx == 0 or data == 'fixed':
            mode = 'fixed'
        elif cached in ('curve', 'fixed'):
            mode = cached
        elif saved in ('curve', 'fixed'):
            mode = saved
        else:
            mode = 'fixed'

        self._acoustic_mode_state = mode
        return mode

    def _on_acoustic_scenario_changed(self, *_args):
        mode = self._current_acoustic_mode()
        self._acoustic_mode_state = mode
        self._qsettings.setValue("noise/acoustic_mode", mode)
        self._qsettings.setValue("noise/eval_ws_m_s", float(self.sp_eval_ws.value()))
        self._qsettings.setValue("noise/curve_worst_case", bool(self.chk_curve_worst.isChecked()))
        self._populate_models_table()
        self._check_configuration()

    def _collect_model_cfg(self) -> Dict[str, Dict[str, float]]:
        cfg: Dict[str, Dict[str, float]] = {}
        curve_settings = self._load_curve_settings()
        acoustic_mode = self._current_acoustic_mode()
        try:
            txt = (self.cb_acoustic_mode.currentText() or '').strip().lower()
        except Exception:
            txt = ''
        # Extra robustness: if the user visibly selected the curve mode or requested
        # worst-case evaluation while curve CSVs are loaded, force curve mode.
        if curve_settings and ('curva' in txt or bool(self.chk_curve_worst.isChecked()) or str(getattr(self, '_acoustic_mode_state', '')).lower() == 'curve' or str(self._qsettings.value('noise/acoustic_mode', '', type=str) or '').lower() == 'curve'):
            acoustic_mode = 'curve'
        eval_ws = float(self.sp_eval_ws.value())
        use_curve_worst = bool(self.chk_curve_worst.isChecked())
        for row, info in enumerate(self._model_rows):
            name_item = self.tbl_models.item(row, 0)
            park_item = self.tbl_models.item(row, 1)
            if not name_item:
                continue
            name = name_item.text().strip()
            cfg_key = str(info.get("source_group_key") or info.get("layer_id") or name)
            try:
                lwa = float(self._model_lwa_value(row))
            except Exception:
                lwa = 105.0
            item = {
                "lwa": float(lwa),
                "acoustic_mode": acoustic_mode,
                "eval_ws_m_s": float(eval_ws),
                "use_curve_worst_case": bool(use_curve_worst),
            }
            curve_path = str(curve_settings.get(cfg_key, '') or curve_settings.get(name, '') or '')
            if curve_path:
                item['curve_path'] = curve_path
            hh = info.get("hub_height")
            diam = info.get("diameter")
            if hh is not None:
                item["hub_height"] = float(hh)
            if diam is not None:
                item["diameter"] = float(diam)
            item["source_group_name"] = name
            item["model_name"] = str(info.get("model_name") or name)
            item["park_name"] = (park_item.text().strip() if park_item else str(info.get("park_name") or ""))
            cfg[cfg_key] = item
        return cfg

    def _selected_source_layer_ids(self) -> Optional[List[str]]:
        ids: List[str] = []
        for i in range(self.lst_sources.count()):
            item = self.lst_sources.item(i)
            if item and item.checkState() == QtCore.Qt.Checked:
                lid = str(item.data(QtCore.Qt.UserRole) or "")
                if lid:
                    ids.append(lid)
        if ids:
            return ids
        return [str(r.get("layer_id")) for r in self._model_rows if r.get("layer_id")]

    def _set_all_sources_checked(self, checked: bool):
        self.lst_sources.blockSignals(True)
        for i in range(self.lst_sources.count()):
            item = self.lst_sources.item(i)
            if item:
                item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        self.lst_sources.blockSignals(False)
        self._on_sources_changed()

    def _on_sources_changed(self, *_args):
        try:
            ids = self._selected_source_layer_ids()
            self._qsettings.setValue("noise/source_layer_ids_json", json.dumps(ids, ensure_ascii=False))
            if ids and len(ids) == 1:
                self._qsettings.setValue("noise/source_layer_id", ids[0])
            else:
                self._qsettings.setValue("noise/source_layer_id", "__AUTO_ALL__")
        except Exception:
            pass
        self._check_configuration()

    def _on_receiver_changed(self, *_args):
        layer_id = self.cb_receivers.currentData(QtCore.Qt.UserRole)
        try:
            self._qsettings.setValue("noise/receiver_layer_id", layer_id or "")
        except Exception:
            pass
        lyr = QgsProject.instance().mapLayer(layer_id) if layer_id else None
        if isinstance(lyr, QgsVectorLayer):
            try:
                self.lbl_receptor_info.setText(f"{lyr.name()} · {int(lyr.featureCount())} feature(s)")
            except Exception:
                self.lbl_receptor_info.setText(lyr.name())
        else:
            self.lbl_receptor_info.setText("Not selected")
        self._check_configuration()

    def _on_dem_changed(self, *_args):
        try:
            self._qsettings.setValue("noise/dem_layer_id", self.cb_dem.currentData(QtCore.Qt.UserRole) or "")
        except Exception:
            pass
        self._check_configuration()

    def _on_model_table_item_changed(self, item):
        if item.column() in (0, 1):
            self._save_source_group_meta_settings()
        if item.column() == 6:
            txt = (item.text() or "").replace(",", ".").strip()
            try:
                val = float(txt)
                if val < 0 or val > 200:
                    raise ValueError
            except Exception:
                val = 105.0
            w = self.tbl_models.cellWidget(item.row(), 6)
            if isinstance(w, QtWidgets.QDoubleSpinBox):
                w.blockSignals(True)
                w.setValue(float(val))
                w.blockSignals(False)
            item.setText(f"{float(val):.1f}")
            self._save_noise_model_settings()
        self._check_configuration()

    def _check_configuration(self):
        msgs: List[str] = []
        ok = True
        de = str(current_language()).lower().startswith("de")
        fr = current_language() == "fr"

        if not self._model_rows:
            ok = False
            if de:
                msgs.append("• Es wurden keine Koordinaten-Layer nach Modell erkannt. Importieren Sie hier ein CSV-Layout oder verwenden Sie ein aus dem Energiemodul erzeugtes Layout.")
            else:
                msgs.append("• No se han detectado capas de coordenadas por modelo. Importa un layout CSV aquí o reutiliza un layout generado desde Energía.")
        else:
            n_models = len(self._model_rows)
            n_turbs = sum(int(r.get("n_turbines", 0)) for r in self._model_rows)
            if de:
                msgs.append(f"• Layout erkannt: {n_models} WT-Modell(e) und {n_turbs} Windturbine(n).")
            else:
                msgs.append(f"• Layout detectado: {n_models} modelo(s) WT y {n_turbs} turbina(s).")
            src_ids = self._selected_source_layer_ids() or []
            if len(src_ids) == 1:
                msgs.append("• Akustische Quellen: Es wird 1 manuell in den Eingaben ausgewählter Quell-Layer verwendet." if de else "• Acoustic sources: will use 1 source layer manually selected from Inputs.")
            elif len(src_ids) > 1:
                msgs.append(f"• Akustische Quellen: Es werden {len(src_ids)} manuell in den Eingaben ausgewählte Quell-Layer verwendet." if de else f"• Acoustic sources: will use {len(src_ids)} source layers manually selected from Inputs.")
            else:
                msgs.append("• Akustische Quellen: Es werden alle in VelantisWind automatisch erkannten/importierten WT-Layer verwendet." if de else "• Acoustic sources: will use all WT layers automatically detected/imported in VelantisWind.")

        if self.chk_multi_receivers.isChecked():
            n_groups = 0
            n_feats = 0
            for r in range(self.tbl_receiver_groups.rowCount()):
                w_enabled = self.tbl_receiver_groups.cellWidget(r,0)
                if w_enabled and not w_enabled.isChecked():
                    continue
                w_layer = self.tbl_receiver_groups.cellWidget(r,1)
                lyr = QgsProject.instance().mapLayer(str(w_layer.currentData(QtCore.Qt.UserRole) or "")) if w_layer else None
                if isinstance(lyr, QgsVectorLayer):
                    n_groups += 1
                    n_feats += int(lyr.featureCount())
            if n_groups == 0:
                ok = False
                msgs.append("• Es muss mindestens ein Rezeptor-Layer in der Mehrlayer-Tabelle konfiguriert werden." if de else "• Falta configurar al menos una capa de receptores en la tabla multi-capa.")
            else:
                msgs.append(f"• Mehrlayer-Rezeptoren: {n_groups} aktive Layer und {n_feats} Elemente insgesamt." if de else f"• Receptores multi-capa: {n_groups} capa(s) activas y {n_feats} elemento(s) totales.")
                msgs.append(f"• Grenzwertkriterium je Layer: {self.cb_limit_scenario.currentText()}." if de else f"• Criterio de límite por capa: {self.cb_limit_scenario.currentText()}.")
        else:
            receiver_id = self.cb_receivers.currentData(QtCore.Qt.UserRole)
            if not receiver_id:
                ok = False
                msgs.append("• Es fehlt ein Rezeptor-Layer. Für diesen Workflow wird ein Punkt- oder Polygon-Layer mit Wohngebäuden/Rezeptoren empfohlen." if de else "• Falta seleccionar la capa de receptores. Para este flujo se recomienda una capa de puntos o polígonos de viviendas/receptores.")
            else:
                lyr = QgsProject.instance().mapLayer(receiver_id)
                if isinstance(lyr, QgsVectorLayer):
                    msgs.append(f"• Rezeptoren: {lyr.name()} ({int(lyr.featureCount())} Element(e))." if de else f"• Receptores: {lyr.name()} ({int(lyr.featureCount())} elemento(s)).")
                    if lyr.id() in {str(r.get('layer_id')) for r in self._model_rows}:
                        ok = False
                        msgs.append("• Der Rezeptor-Layer entspricht dem Turbinenlayout. Wählen Sie einen anderen Layer für Wohngebäude/Rezeptoren." if de else "• La capa de receptores coincide con el layout de turbinas. Elige una capa distinta de viviendas/receptores.")

        if self.tbl_models.rowCount() > 0:
            ok_rows = 0
            group_names = []
            empty_groups = 0
            for row in range(self.tbl_models.rowCount()):
                try:
                    val = float(self._model_lwa_value(row))
                    if 0 < val < 200:
                        ok_rows += 1
                except Exception:
                    pass
                try:
                    gname = (self.tbl_models.item(row, 0).text() or '').strip()
                except Exception:
                    gname = ''
                if not gname:
                    empty_groups += 1
                else:
                    group_names.append(gname.lower())
            if ok_rows != self.tbl_models.rowCount():
                ok = False
            if empty_groups > 0:
                ok = False
                msgs.append(f"• Akustische Quellgruppen: In der Tabelle fehlen {empty_groups} Gruppenname(n)." if de else f"• Grupos fuente acústicos: faltan {empty_groups} nombre(s) de grupo en la tabla.")
            dups = len(group_names) - len(set(group_names))
            if dups > 0:
                ok = False
                msgs.append(f"• Akustische Quellgruppen: {dups} doppelte Gruppenname(n). Benennen Sie sie für Export und Nachverfolgbarkeit um." if de else f"• Grupos fuente acústicos: hay {dups} nombre(s) duplicados. Conviene renombrarlos para exportación y trazabilidad.")
            msgs.append(f"• Akustische Quellgruppen: {ok_rows}/{self.tbl_models.rowCount()} Gruppe(n) mit gültigem LwA." if de else f"• Grupos fuente acústicos: {ok_rows}/{self.tbl_models.rowCount()} grupo(s) con LwA válido.")

        mode = self._current_acoustic_mode()
        if mode == 'curve':
            curve_settings = self._load_curve_settings()
            n_curves = sum(1 for r in self._model_rows if curve_settings.get(str(r.get('source_group_key') or r.get('layer_id') or r.get('name') or '')) or curve_settings.get(str(r.get('name') or '')))
            if self.chk_curve_worst.isChecked():
                msgs.append(f"• Akustisches Szenario: LwA(ws)-Kurven im Worst Case. Verfügbare Kurven: {n_curves}/{len(self._model_rows)} Modell(e)." if de else f"• Escenario acústico: curvas LwA(ws) en peor caso. Curvas disponibles: {n_curves}/{len(self._model_rows)} modelo(s).")
            else:
                msgs.append(f"• Akustisches Szenario: LwA(ws)-Kurven bei {self.sp_eval_ws.value():.1f} m/s. Verfügbare Kurven: {n_curves}/{len(self._model_rows)} Modell(e)." if de else f"• Escenario acústico: curvas LwA(ws) a {self.sp_eval_ws.value():.1f} m/s. Curvas disponibles: {n_curves}/{len(self._model_rows)} modelo(s).")
        else:
            msgs.append("• Akustisches Szenario: fester LwA je akustischer Quellgruppe." if de else "• Escenario acústico: LwA fijo por grupo fuente acústico.")
        if self.chk_multi_receivers.isChecked():
            msgs.append("• Rezeptorhöhe: wird aus jedem in der Mehrlayer-Tabelle konfigurierten Layer übernommen." if de else "• Altura de receptor: se toma de cada capa configurada en la tabla multi-capa.")
        else:
            msgs.append(f"• Konfigurierte Rezeptorhöhe: {self.sp_receiver_h.value():.1f} m." if de else f"• Altura de receptor configurada: {self.sp_receiver_h.value():.1f} m.")
        msgs.append(f"• Konfigurierter Maximalradius: {self.sp_max_radius.value():.0f} m." if de else f"• Radio máximo configurado: {self.sp_max_radius.value():.0f} m.")
        msgs.append(f"• Lineare Dämpfung α: {self.sp_alpha.value():.4f} dB/m (vereinfachte atmosphärische Absorption)." if de else f"• Atenuación lineal α: {self.sp_alpha.value():.4f} dB/m (absorción atmosférica simplificada).")
        ground_mode = str(self.cb_ground_mode.currentData(QtCore.Qt.UserRole) or 'global')
        if ground_mode == 'landuse':
            lu_id = self.cb_landuse.currentData(QtCore.Qt.UserRole)
            lu = QgsProject.instance().mapLayer(lu_id) if lu_id else None
            if lu is not None:
                msgs.append(f"• Boden/Gelände: aus Landnutzungs-Layer '{lu.name()}'. Globaler G-Fallback = {self.sp_ground_g.value():.2f}." if de else f"• Suelo/terreno: desde capa de uso del suelo '{lu.name()}'. G global de respaldo = {self.sp_ground_g.value():.2f}.")
            else:
                msgs.append(f"• Boden/Gelände: Layer-Modus aktiv, aber kein gültiger Layer; globaler G-Wert = {self.sp_ground_g.value():.2f} wird als Fallback verwendet." if de else f"• Suelo/terreno: modo capa activado pero sin capa válida; will use G global = {self.sp_ground_g.value():.2f}.")
        else:
            msgs.append(f"• Bodenfaktor G: {self.sp_ground_g.value():.2f} (0=hart, 1=porös)." if de else f"• Factor de suelo G: {self.sp_ground_g.value():.2f} (0=duro, 1=poroso).")
        if self.chk_multi_receivers.isChecked():
            msgs.append("• Rezeptorgrenzwert: wird aus jedem in der Mehrlayer-Tabelle konfigurierten Layer übernommen." if de else "• Límite de receptor: se toma de cada capa configurada en la tabla multi-capa.")
        else:
            msgs.append(f"• Rezeptorgrenzwert: {self.sp_limit.value():.1f} dB(A)." if de else f"• Límite de receptor: {self.sp_limit.value():.1f} dB(A).")
        msgs.append(f"• Konfigurierte Isophonen: {self.le_iso_levels.text().strip() or '35,40,45,50'} dB(A)." if de else f"• Configured isophones: {self.le_iso_levels.text().strip() or '35,40,45,50'} dB(A).")
        dem_id = self.cb_dem.currentData(QtCore.Qt.UserRole)
        if dem_id:
            dem = QgsProject.instance().mapLayer(dem_id)
            if dem:
                msgs.append(f"• Ausgewähltes DGM/DSM: {dem.name()} (Gelände an Quelle/Rezeptor wird im akustischen Rechenkern abgetastet)." if de else f"• MDT/DSM seleccionado: {dem.name()} (se muestreará terreno fuente/receptor en el cálculo acústico).")
        else:
            msgs.append("• Kein DGM/DSM ausgewählt. Die Akustikberechnung startet mit planaren Koordinaten und relativen Quell-/Rezeptorhöhen." if de else "• Sin MDT/DSM seleccionado. El cálculo acústico arrancará en coordenadas planas con alturas relativas de fuente/receptor.")

        if de:
            msgs.append("• Aktuelle Methode: akustische Quelle-Rezeptor-Berechnung für Windenergie-Beratung (Lp = LwA - Adiv - Aatm - Aground). Zusätzlich können GIS-Layer für Quellen, dominante Verbindungen, Rezeptoren außerhalb des Radius, Schallraster und Isophonen erzeugt werden.")
            msgs.append("• Beratungsparameter: Rezeptorgrenzwert, Isophonen und Bodenfaktor G für eine schnelle Prüfung von Einhaltung und Geländeeinfluss.")
        else:
            msgs.append("• Método actual: cálculo acústico fuente-receptor para consultoría eólica (Lp = LwA - Adiv - Aatm - Aground). Además puede crear capas GIS de fuentes, enlaces dominantes, receptores fuera de radio, mapa de ruido ráster e isófonas.")
            msgs.append("• Parámetros de consultoría acústica: límite de receptor, isófonas y factor de suelo G para revisión rápida de cumplimiento e influencia del terreno.")
        
        if str(current_language()).lower().startswith("de"):
            msgs = [_de_cleanup_noise_status(m) for m in msgs]
        self.txt_status.setPlainText("\n".join(msgs))
        self.btn_calc.setEnabled(ok)

    def _validate_inputs_for_run(self):
        errors = []
        warnings = []
        if self.chk_multi_receivers.isChecked():
            n_active = 0
            for r in range(self.tbl_receiver_groups.rowCount()):
                w_enabled = self.tbl_receiver_groups.cellWidget(r,0)
                if w_enabled and not w_enabled.isChecked():
                    continue
                w_layer = self.tbl_receiver_groups.cellWidget(r,1)
                lyr = QgsProject.instance().mapLayer(str(w_layer.currentData(QtCore.Qt.UserRole) or "")) if w_layer else None
                if not isinstance(lyr, QgsVectorLayer):
                    errors.append(f"Zeile {r+1}: ungültiger Rezeptor-Layer." if str(current_language()).lower().startswith("de") else f"Fila {r+1}: capa de receptores no válida.")
                    continue
                if int(lyr.featureCount()) <= 0:
                    errors.append(f"Zeile {r+1}: Der Layer '{lyr.name()}' ist leer." if str(current_language()).lower().startswith("de") else f"Fila {r+1}: la capa '{lyr.name()}' está vacía.")
                n_active += 1
            if n_active <= 0:
                errors.append("Es gibt keine aktiven Rezeptor-Layer nach Kategorie." if str(current_language()).lower().startswith("de") else "No hay capas activas de receptores por categoría.")
        else:
            receiver_id = self.cb_receivers.currentData(QtCore.Qt.UserRole)
            lyr = QgsProject.instance().mapLayer(receiver_id) if receiver_id else None
            if not isinstance(lyr, QgsVectorLayer):
                errors.append("Wählen Sie einen gültigen Rezeptor-Layer aus." if str(current_language()).lower().startswith("de") else "Select a valid receiver layer.")
            elif int(lyr.featureCount()) <= 0:
                errors.append(f"Der Rezeptor-Layer '{lyr.name()}' ist leer." if str(current_language()).lower().startswith("de") else f"La capa de receptores '{lyr.name()}' está vacía.")
        for row in range(self.tbl_models.rowCount()):
            name_item = self.tbl_models.item(row, 0)
            name = name_item.text().strip() if name_item else f"fila {row+1}"
            try:
                lwa = float(self._model_lwa_value(row))
                if lwa <= 0:
                    raise ValueError
            except Exception:
                errors.append(f"{name}: ungültiger fester LwA." if str(current_language()).lower().startswith("de") else f"{name}: LwA fijo inválido.")
        if float(self.sp_max_radius.value()) <= 0:
            errors.append("Der maximale Radius muss größer als 0 sein." if str(current_language()).lower().startswith("de") else "El radio máximo debe ser mayor que 0.")
        if float(self.sp_grid_res.value()) <= 0:
            errors.append("Die Rasterauflösung muss größer als 0 sein." if str(current_language()).lower().startswith("de") else "La resolución del raster debe ser mayor que 0.")
        if str(self.cb_ground_mode.currentData(QtCore.Qt.UserRole) or 'global') == 'landuse' and not self.cb_landuse.currentData(QtCore.Qt.UserRole):
            warnings.append("Bodenmodus aus Layer ist aktiv, aber ohne gültigen Layer: Der globale G-Wert wird als Fallback verwendet." if str(current_language()).lower().startswith("de") else "Modo suelo desde capa activo sin capa válida: will use G global como respaldo.")
        return errors, warnings

    def _run_noise(self):
        from .noise_core.dialog_controller import run_noise_from_dialog
        return run_noise_from_dialog(self)

    def _go_back(self):
        if callable(self._on_back):
            self._on_back()
