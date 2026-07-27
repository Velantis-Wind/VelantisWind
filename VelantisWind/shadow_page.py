# -*- coding: utf-8 -*-
"""
Shadow Flicker module page.

Operational experimental UI for receptor-based and raster shadow/flicker assessment.
The calculation logic lives under ``shadow_core/``; this file keeps the Qt page,
widget state and compatibility wrappers.
"""

from __future__ import annotations

from .shadow_core.debug import debug_print

import json
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional

import numpy as np

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsWkbTypes, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem, QgsTask,
)

from .shadow_core import (
    ShadowFlickerCalculator,
    ShadowFlickerResult,
    calculate_shadow_for_receptor,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_MAX_SUN_ELEVATION,
    DEFAULT_OBSERVER_HEIGHT,
    DEFAULT_MAX_SHADOW_DISTANCE_M,
)
from .i18n import apply_i18n, install_runtime_i18n_patches, tr_text as _tr, is_spanish, current_language
from .ui_core.layout_sources import import_turbine_layout_from_csv
from .shadow_core.timezone_utils import (
    detect_timezone_name,
    load_iana_timezones,
    timezone_label,
)

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




def _ml(es: str, en: str = None, fr: str = None, de: str = None) -> str:
    """Return a clean UI string for the active language without mixing languages."""
    lang = str(current_language() or "es").lower()[:2]
    if lang == "en" and en is not None:
        return en
    if lang == "fr" and fr is not None:
        return fr
    if lang == "de" and de is not None:
        return de
    return _tr(es)


def _de_cleanup_shadow_status(text: str) -> str:
    s = str(text or "")
    repl = [
        ("Couche d’éoliennes", "Windturbinen-Layer"),
        ("Couche de récepteurs", "Rezeptor-Layer"),
        ("récepteur(s)", "Rezeptor(en)"),
        ("éolienne(s)", "Windturbine(n)"),
        ("Calculé depuis", "Berechnet aus"),
        ("couche sélectionnée", "ausgewähltem Layer"),
        ("toutes les couches du module Énergie", "allen Layern des Energiemoduls"),
        ("Nombre total d’éoliennes utilisées", "Anzahl verwendeter Windturbinen"),
        ("Fuseau horaire détecté", "Zeitzone erkannt"),
        ("Fuseau horaire : non détecté automatiquement", "Zeitzone: nicht automatisch erkannt"),
        ("Sélectionnez manuellement un fuseau IANA.", "Wählen Sie manuell eine IANA-Zeitzone aus."),
        ("Calculé depuis", "Berechnet aus"),
        ("Nombre total d’éoliennes utilisées", "Anzahl verwendeter Windturbinen"),
        ("Méthode", "Methode"),
        ("Table horaire : heure civile locale avec DST", "Zeittabelle: lokale Uhrzeit mit DST"),
        ("Table horaire : décalage UTC fixe", "Zeittabelle: fester UTC-Offset"),
        ("Zone", "Zone"),
    ]
    for a,b in repl:
        s=s.replace(a,b)
    return s

class ShadowPage(QtWidgets.QWidget):
    """Shadow Flicker module page."""
    
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
        """Small clickable information button used across the Shadow module."""
        btn = QtWidgets.QToolButton(self)
        try:
            btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            btn.setText("?")
        btn.setAutoRaise(True)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setToolTip(_tr(tooltip))
        btn.clicked.connect(lambda _checked=False, key=help_key: self._show_shadow_help(key))
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

    def _shadow_help_text(self, key: str):
        """Help texts for the clickable ℹ buttons.

        Spanish is the canonical source for runtime translation.  English is
        returned only when English is explicitly selected; French and future
        languages use the Spanish source so tr_text can translate the full help
        popup instead of producing mixed fragment translations.
        """
        lang = current_language()
        if lang == "de":
            data_de = {
                "site": (
                    "Hilfe · Standortkonfiguration",
                    """
                    <b>Was hier definiert wird</b><br><br>
                    In diesem Block werden Standort und Zeitrahmen der Schattenwurfberechnung konfiguriert.<br><br>
                    <b>Breitengrad und Längengrad</b><br>
                    Sie werden zur Berechnung der Sonnenposition verwendet. Geben Sie sie in Dezimalgrad ein, zum Beispiel 42.465 und -2.445.<br><br>
                    <b>Analysejahr</b><br>
                    Damit kann das Plugin die Jahrestabelle mit dem realen Kalender des ausgewählten Jahres erzeugen.<br><br>
                    <b>Hinweis</b><br>
                    Wenn die genauen Koordinaten nicht bekannt sind, verwenden Sie die automatische Erkennung, um sie aus dem Schwerpunkt des aktiven Layouts abzuleiten.
                    """,
                ),
                "timezone": (
                    "Hilfe · Zeitzone",
                    """
                    <b>Zeitbasis</b><br><br>
                    Sie können mit der realen lokalen Zeit des Standorts oder mit einem festen UTC-Offset arbeiten.<br><br>
                    <b>Lokale Zeit (IANA/DST)</b><br>
                    Verwendet Zonen wie <code>Europe/Madrid</code> und berücksichtigt automatisch Sommer- und Winterzeit.<br><br>
                    <b>Fester UTC-Offset</b><br>
                    Hält die Differenz zu UTC das ganze Jahr konstant. Das ist einfacher, bildet aber saisonale Zeitumstellungen nicht ab.<br><br>
                    <b>Empfehlung</b><br>
                    Für reale Studien ist normalerweise die IANA-Zeitzone des Standorts vorzuziehen.
                    """,
                ),
                "layers": (
                    "Hilfe · Berechnungs-Layer",
                    """
                    <b>Turbinen-Layer</b><br><br>
                    Wählen Sie den in VelantisWind erkannten oder importierten Koordinaten-Layer der Turbinen. Dieser Layer definiert die Positionen der Turbinen, die Schatten werfen.<br><br>
                    <b>Rezeptor-Layer</b><br>
                    Dies sollte ein Punkt-Layer mit den Positionen sein, an denen der Schattenwurf bewertet werden soll, zum Beispiel Wohngebäude oder sensible Rezeptoren.<br><br>
                    <b>Hinweis</b><br>
                    Prüfen Sie vor der Berechnung, dass beide Layer im Projekt geladen sind und das korrekte CRS verwenden.
                    """,
                ),
                "dem": (
                    "Hilfe · Optionales DGM/DEM",
                    """
                    <b>Wofür es verwendet wird</b><br><br>
                    Wenn ein Höhenraster ausgewählt wird, korrigiert das Plugin die Geometrie anhand der Geländehöhe an jeder Turbine und jedem Rezeptor.<br><br>
                    <b>Erwartetes Format</b><br>
                    Verwenden Sie einen in QGIS geladenen Raster-Layer, vorzugsweise im gleichen CRS wie das Projekt und mit Höhenwerten in Metern.<br><br>
                    <b>Wenn nichts ausgewählt ist</b><br>
                    Die Berechnung nimmt ebenes Gelände an (z = 0), was für eine erste Abschätzung ausreichend ist.
                    """,
                ),
                "parameters": (
                    "Hilfe · Berechnungsparameter",
                    """
                    <b>Beobachterhöhe</b><br><br>
                    Höhe, in der der Rezeptor bewertet wird. Ein typischer Wert ist 2 m für ein Fenster oder einen Beobachtungspunkt.<br><br>
                    <b>Zeitschritt</b><br>
                    Steuert die zeitliche Auflösung der Berechnung. 5 Minuten bieten meist einen guten Kompromiss zwischen Genauigkeit und Laufzeit; 1 Minute ist genauer, aber deutlich langsamer.<br><br>
                    <b>Minimale und maximale Sonnenhöhe</b><br>
                    Damit können weniger relevante Sonnenstände ignoriert werden. Das Minimum wird häufig auf etwa 3° gesetzt. Das Maximum kann bei 90° bleiben, wenn hohe Sonnenstände nicht gefiltert werden sollen.<br><br>
                    <b>Verfügbarkeit und maximale Entfernung</b><br>
                    Die Verfügbarkeit reduziert das Ergebnis entsprechend der realen Betriebszeit der Turbine. Die maximale Entfernung begrenzt den betrachteten Einflussradius.
                    """,
                ),
                "models": (
                    "Hilfe · Konfiguration der Turbinenmodelle",
                    """
                    <b>Was jede Zeile darstellt</b><br><br>
                    Jede Zeile fasst ein im Projekt erkanntes Turbinenmodell zusammen.<br><br>
                    <b>Wichtige Felder</b><br>
                    • <b>Nabenhöhe</b>: Höhe der Nabe über Gelände.<br>
                    • <b>Rotordurchmesser</b>: Durchmesser des Rotors.<br>
                    • <b>Notizen</b>: Hinweise oder Rückverfolgbarkeitskommentare zum Modell.<br><br>
                    <b>Warum das wichtig ist</b><br>
                    Diese Parameter werden benötigt, um die Schattengeometrie korrekt zu projizieren. Prüfen Sie, dass sie zum realen Turbinenmodell passen.
                    """,
                ),
                "raster": (
                    "Hilfe · Schattenwurf-Raster",
                    """
                    <b>Was erzeugt wird</b><br><br>
                    Zusätzlich zur Berechnung an Rezeptoren kann das Plugin ein kontinuierliches Raster mit Schattenwurfdauer um den Windpark erzeugen.<br><br>
                    <b>Auflösung</b><br>
                    Eine kleinere Zelle liefert mehr Detail, dauert aber länger. 100 m ist oft für schnelle Tests geeignet; 50 m oder 25 m liefern feinere Ergebnisse.<br><br>
                    <b>Zeitschritt des Rasters</b><br>
                    Er ist unabhängig vom Zeitschritt der Rezeptoren. Zur schnelleren Kartenerzeugung kann ein etwas größerer Schritt verwendet werden.
                    """,
                ),
                "filter": (
                    "Hilfe · Monats-/Stundenfilter",
                    """
                    <b>Wofür diese Funktion gedacht ist</b><br><br>
                    Nachdem das Jahresraster erzeugt wurde, können gefilterte Versionen nach Monat und/oder Stunde erstellt werden, ohne die gesamte Jahresgeometrie neu zu berechnen.<br><br>
                    <b>Beispiele</b><br>
                    • Nur März.<br>
                    • Nur 08:00–09:00.<br>
                    • März um 18:00.<br><br>
                    <b>Hinweis</b><br>
                    Diese Option wird nach Erstellung des Basisrasters aktiviert.
                    """,
                ),
            }
            return data_de.get(key, ("Hilfe", "Für dieses Element ist keine Hilfe verfügbar."))
        data_es = {
            "site": (
                "Ayuda · Configuración del emplazamiento",
                """
                <b>Qué defines aquí</b><br><br>
                En este bloque se configura la localización y el marco temporal del cálculo de sombras y parpadeo.<br><br>
                <b>Latitud y longitud</b><br>
                Se usan para calcular la posición solar. Deben estar en grados decimales, por ejemplo 42.465 y -2.445.<br><br>
                <b>Año de análisis</b><br>
                Permite generar la tabla anual con el calendario real del año seleccionado.<br><br>
                <b>Consejo</b><br>
                Si no conoces las coordenadas exactas, utiliza el botón de autodetección para tomarlas del centroide del layout activo.
                """,
            ),
            "timezone": (
                "Ayuda · Zona horaria",
                """
                <b>Base temporal</b><br><br>
                Puedes trabajar con hora civil real del emplazamiento o con un offset UTC fijo.<br><br>
                <b>Hora civil local (IANA/DST)</b><br>
                Usa zonas como <code>Europe/Madrid</code> y aplica automáticamente los cambios de horario de verano e invierno.<br><br>
                <b>Offset UTC fijo</b><br>
                Mantiene la misma diferencia con UTC durante todo el año. Es más simple, pero no refleja cambios estacionales.<br><br>
                <b>Recomendación</b><br>
                Para estudios reales normalmente conviene usar la zona IANA del emplazamiento.
                """,
            ),
            "layers": (
                "Ayuda · Capas de cálculo",
                """
                <b>Capa de turbinas</b><br><br>
                Selecciona la capa de coordenadas detectada o importada en VelantisWind. Esa capa define la posición de las turbinas que proyectan sombra.<br><br>
                <b>Capa de receptores</b><br>
                Debe ser una capa de puntos con las ubicaciones donde quieres evaluar las sombras y el parpadeo, por ejemplo viviendas o receptores sensibles.<br><br>
                <b>Consejo</b><br>
                Comprueba que ambas capas estén en el proyecto y con el CRS correcto antes de lanzar el cálculo.
                """,
            ),
            "dem": (
                "Ayuda · MDT / DEM opcional",
                """
                <b>Para qué sirve</b><br><br>
                Si seleccionas un raster de elevación, el plugin corrige la geometría usando la cota del terreno en cada turbina y en cada receptor.<br><br>
                <b>Formato esperado</b><br>
                Usa una capa raster cargada en QGIS, preferiblemente en el mismo CRS del proyecto y con valores de elevación en metros.<br><br>
                <b>Si no se selecciona</b><br>
                El cálculo asume terreno plano (z = 0), suficiente para una primera aproximación.
                """,
            ),
            "parameters": (
                "Ayuda · Parámetros del cálculo",
                """
                <b>Altura del observador</b><br><br>
                Altura a la que se evalúa el receptor. Un valor típico es 2 m para una ventana o punto de observación.<br><br>
                <b>Paso temporal</b><br>
                Controla la resolución temporal del cálculo. 5 min suele dar un buen equilibrio entre precisión y tiempo; 1 min es más preciso pero mucho más lento.<br><br>
                <b>Elevación solar mínima y máxima</b><br>
                Permiten ignorar posiciones solares poco relevantes. La mínima suele ponerse alrededor de 3°.
                La máxima puede mantenerse en 90° si no quieres filtrar el sol alto.<br><br>
                <b>Disponibilidad y distancia máxima</b><br>
                La disponibilidad reduce el resultado según el tiempo real de operación de la turbina. La distancia máxima limita el radio de influencia considerado.
                """,
            ),
            "models": (
                "Ayuda · Configuración de modelos de turbina",
                """
                <b>Qué representa cada fila</b><br><br>
                Cada fila resume un modelo de aerogenerador detectado en el proyecto.<br><br>
                <b>Campos clave</b><br>
                • <b>Altura de buje</b>: altura sobre el terreno.<br>
                • <b>Diámetro del rotor</b>: diámetro del rotor.<br>
                • <b>Notas</b>: observaciones o trazabilidad del modelo.<br><br>
                <b>Importancia</b><br>
                Estos parámetros son necesarios para proyectar correctamente la geometría de sombra. Revisa que coincidan con el aerogenerador real.
                """,
            ),
            "raster": (
                "Ayuda · Raster de sombras y parpadeo",
                """
                <b>Qué genera</b><br><br>
                Además del cálculo en receptores, el plugin puede crear un raster continuo con las horas de sombras y parpadeo en el entorno del parque.<br><br>
                <b>Resolución</b><br>
                Una celda más pequeña ofrece más detalle, pero tarda más. 100 m suele ser útil para pruebas rápidas; 50 m o 25 m dan más detalle.<br><br>
                <b>Paso temporal del raster</b><br>
                Es independiente del usado en receptores. Puedes usar un paso algo mayor para acelerar la generación del mapa.
                """,
            ),
            "filter": (
                "Ayuda · Filtro por mes y hora",
                """
                <b>Para qué sirve</b><br><br>
                Una vez generado el raster anual, puedes regenerar versiones filtradas por mes y/o por hora sin recalcular toda la geometría anual.<br><br>
                <b>Ejemplos</b><br>
                • Solo marzo.<br>
                • Solo las 08:00–09:00.<br>
                • Marzo a las 18:00.<br><br>
                <b>Nota</b><br>
                Esta opción se habilita después de crear el raster base.
                """,
            ),
        }
        data_en = {
            "site": (
                "Help · Site configuration",
                """
                <b>What you define here</b><br><br>
                This block configures the site location and the temporal framework of the shadow flicker calculation.<br><br>
                <b>Latitude and longitude</b><br>
                They are used to compute the solar position. Enter them in decimal degrees, for example 42.465 and -2.445.<br><br>
                <b>Analysis year</b><br>
                It lets the plugin generate the annual table using the real calendar of the selected year.<br><br>
                <b>Tip</b><br>
                If you do not know the exact coordinates, use the auto-detect button to estimate them from the active layout centroid.
                """,
            ),
            "timezone": (
                "Help · Time zone",
                """
                <b>Time basis</b><br><br>
                You can work either with the site's real local civil time or with a fixed UTC offset.<br><br>
                <b>Local civil time (IANA/DST)</b><br>
                Uses zones such as <code>Europe/Madrid</code> and automatically applies daylight-saving and winter-time changes.<br><br>
                <b>Fixed UTC offset</b><br>
                Keeps the same UTC difference throughout the year. It is simpler, but it does not reflect seasonal clock changes.<br><br>
                <b>Recommendation</b><br>
                For real studies, it is usually better to use the site IANA time zone.
                """,
            ),
            "layers": (
                "Help · Calculation layers",
                """
                <b>Turbine layer</b><br><br>
                Select the turbine-coordinate layer detected or imported in VelantisWind. This layer defines the turbine positions that cast shadow flicker.<br><br>
                <b>Receiver layer</b><br>
                This should be a point layer with the locations where you want to evaluate shadow flicker, for example houses or sensitive receptors.<br><br>
                <b>Tip</b><br>
                Make sure both layers are loaded in the project and use the correct CRS before running the calculation.
                """,
            ),
            "dem": (
                "Help · Optional DEM",
                """
                <b>What it is for</b><br><br>
                If you select an elevation raster, the plugin corrects the geometry using the ground elevation at each turbine and each receiver.<br><br>
                <b>Expected format</b><br>
                Use a raster layer loaded in QGIS, preferably in the same CRS as the project and with elevation values in metres.<br><br>
                <b>If left empty</b><br>
                The calculation assumes flat terrain (z = 0), which is acceptable for a first-pass assessment.
                """,
            ),
            "parameters": (
                "Help · Calculation parameters",
                """
                <b>Observer height</b><br><br>
                Height at which the receptor is evaluated. A typical value is 2 m for a window or observation point.<br><br>
                <b>Time step</b><br>
                Controls the temporal resolution. 5 min usually gives a good balance between accuracy and runtime; 1 min is more accurate but much slower.<br><br>
                <b>Minimum and maximum solar elevation</b><br>
                They let you ignore less relevant solar positions. The minimum is often set around 3°.
                The maximum can remain at 90° if you do not want to filter out high-sun conditions.<br><br>
                <b>Availability and maximum distance</b><br>
                Availability scales the result according to the real turbine operating time. Maximum distance limits the influence radius considered.
                """,
            ),
            "models": (
                "Help · Turbine model configuration",
                """
                <b>What each row represents</b><br><br>
                Each row summarizes one wind turbine model detected in the project.<br><br>
                <b>Key fields</b><br>
                • <b>Hub Height</b>: hub height above ground.<br>
                • <b>Rotor Diameter</b>: rotor diameter.<br>
                • <b>Notes</b>: notes or traceability comments for the model.<br><br>
                <b>Why it matters</b><br>
                These parameters are required to project the shadow geometry correctly. Check that they match the real turbine model.
                """,
            ),
            "raster": (
                "Help · Shadow flicker raster",
                """
                <b>What it generates</b><br><br>
                In addition to the receptor-based calculation, the plugin can create a continuous raster with shadow flicker hours around the wind farm.<br><br>
                <b>Resolution</b><br>
                A smaller cell gives more detail but takes longer. 100 m is often useful for quick tests; 50 m or 25 m provide finer detail.<br><br>
                <b>Raster time step</b><br>
                It is independent from the receiver time step. You can use a slightly larger step to speed up map generation.
                """,
            ),
            "filter": (
                "Help · Month/hour filter",
                """
                <b>What it is for</b><br><br>
                Once the annual raster has been generated, you can regenerate filtered versions by month and/or hour without recalculating the full annual geometry.<br><br>
                <b>Examples</b><br>
                • March only.<br>
                • Only 08:00–09:00.<br>
                • March at 18:00.<br><br>
                <b>Note</b><br>
                This option becomes available after the base raster has been created.
                """,
            ),
        }

        data_fr = {'site': ('Aide · Configuration du site',
                  '<b>Ce que vous définissez ici</b><br><br>Ce bloc configure la localisation du site et le cadre temporel du '
                  'calcul d’ombres et scintillement.<br><br><b>Latitude et longitude</b><br>Elles servent à calculer la position '
                  'solaire. Elles doivent être saisies en degrés décimaux, par exemple 42.465 et -2.445.<br><br><b>Année '
                  'd’analyse</b><br>Elle permet au plugin de générer le tableau annuel avec le calendrier réel de l’année '
                  'sélectionnée.<br><br><b>Conseil</b><br>Si vous ne connaissez pas les coordonnées exactes, utilisez le '
                  'bouton de détection automatique pour les estimer à partir du centroïde de l’implantation active.'),
         'timezone': ('Aide · Fuseau horaire',
                      '<b>Base temporelle</b><br><br>Vous pouvez travailler avec l’heure civile réelle du site ou avec un '
                      'décalage UTC fixe.<br><br><b>Heure civile locale (IANA/DST)</b><br>Utilise des zones comme '
                      '<code>Europe/Madrid</code> et applique automatiquement les changements d’heure d’été et '
                      'd’hiver.<br><br><b>Décalage UTC fixe</b><br>Conserve la même différence avec UTC pendant toute l’année. '
                      'C’est plus simple, mais cela ne reflète pas les changements saisonniers '
                      'd’heure.<br><br><b>Recommandation</b><br>Pour des études réelles, il est généralement préférable '
                      'd’utiliser le fuseau IANA du site.'),
         'layers': ('Aide · Couches de calcul',
                    '<b>Couche d’éoliennes</b><br><br>Sélectionnez la couche de coordonnées d’éoliennes détectée ou importée '
                    'dans VelantisWind. Cette couche définit les positions des éoliennes qui projettent l’ombre '
                    'intermittente.<br><br><b>Couche de récepteurs</b><br>Il doit s’agir d’une couche de points contenant les '
                    'emplacements où vous voulez évaluer les ombres et scintillement, par exemple des maisons ou des récepteurs '
                    'sensibles.<br><br><b>Conseil</b><br>Vérifiez que les deux couches sont chargées dans le projet et '
                    'utilisent le bon CRS avant de lancer le calcul.'),
         'dem': ('Aide · MDT/DEM optionnel',
                 '<b>À quoi il sert</b><br><br>Si vous sélectionnez un raster d’élévation, le plugin corrige la géométrie en '
                 'utilisant l’altitude du terrain à chaque éolienne et à chaque récepteur.<br><br><b>Format '
                 'attendu</b><br>Utilisez une couche raster chargée dans QGIS, de préférence dans le même CRS que le projet et '
                 'avec des valeurs d’altitude en mètres.<br><br><b>Si rien n’est sélectionné</b><br>Le calcul suppose un '
                 'terrain plat (z = 0), ce qui est acceptable pour une première approximation.'),
         'parameters': ('Aide · Paramètres du calcul',
                        '<b>Hauteur de l’observateur</b><br><br>Hauteur à laquelle le récepteur est évalué. Une valeur typique '
                        'est 2 m pour une fenêtre ou un point d’observation.<br><br><b>Pas temporel</b><br>Contrôle la '
                        'résolution temporelle du calcul. 5 min donne généralement un bon équilibre entre précision et temps '
                        'de calcul ; 1 min est plus précis mais beaucoup plus lent.<br><br><b>Élévation solaire minimale et '
                        'maximale</b><br>Elles permettent d’ignorer des positions solaires peu pertinentes. La minimale est '
                        'souvent fixée autour de 3°. La maximale peut rester à 90° si vous ne voulez pas filtrer le soleil '
                        'haut.<br><br><b>Disponibilité et distance maximale</b><br>La disponibilité réduit le résultat selon '
                        'le temps réel de fonctionnement de l’éolienne. La distance maximale limite le rayon d’influence '
                        'considéré.'),
         'models': ('Aide · Configuration des modèles d’éolienne',
                    '<b>Ce que représente chaque ligne</b><br><br>Chaque ligne résume un modèle d’éolienne détecté dans le '
                    'projet.<br><br><b>Champs clés</b><br>• <b>Hauteur de moyeu</b> : hauteur au-dessus du terrain.<br>• '
                    '<b>Diamètre du rotor</b> : diamètre du rotor.<br>• <b>Notes</b> : observations ou commentaires de '
                    'traçabilité du modèle.<br><br><b>Pourquoi c’est important</b><br>Ces paramètres sont nécessaires pour '
                    'projeter correctement la géométrie d’ombre. Vérifiez qu’ils correspondent au modèle réel d’éolienne.'),
         'raster': ('Aide · Raster d’ombres et scintillement',
                    '<b>Ce qu’il génère</b><br><br>En plus du calcul par récepteurs, le plugin peut créer un raster continu '
                    'avec les heures d’ombres et scintillement autour du parc éolien.<br><br><b>Résolution</b><br>Une cellule plus '
                    'petite offre plus de détail mais prend plus de temps. 100 m est souvent utile pour des tests rapides ; 50 '
                    'm ou 25 m donnent un détail plus fin.<br><br><b>Pas temporel du raster</b><br>Il est indépendant du pas '
                    'utilisé pour les récepteurs. Vous pouvez utiliser un pas un peu plus grand pour accélérer la génération '
                    'de la carte.'),
         'filter': ('Aide · Filtre par mois et heure',
                    '<b>À quoi il sert</b><br><br>Une fois le raster annuel généré, vous pouvez régénérer des versions '
                    'filtrées par mois et/ou par heure sans recalculer toute la géométrie '
                    'annuelle.<br><br><b>Exemples</b><br>• Mars uniquement.<br>• Seulement 08:00–09:00.<br>• Mars à '
                    '18:00.<br><br><b>Note</b><br>Cette option devient disponible après la création du raster de base.')}
        if lang == "fr":
            return data_fr.get(key, ("Aide", "Aucune aide disponible pour cet élément."))
        if lang == "en":
            return data_en.get(key, ("Help", "No help available for this item."))
        return data_es.get(key, ("Ayuda", "No hay ayuda disponible para este elemento."))

    def _show_shadow_help(self, key: str) -> None:
        title, body = self._shadow_help_text(key)
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setText(body.strip())
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        _set_help_ok_text(msg)
        msg.exec_()

    def _build_ui(self):
        """Build the module interface."""
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)
        
        # Scroll area
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(self.scroll)
        
        container = QtWidgets.QWidget(self.scroll)
        self.scroll.setWidget(container)
        
        root = QtWidgets.QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        de = str(current_language()).lower().startswith("de")
        
        # Top bar with buttons
        top = QtWidgets.QHBoxLayout()
        self.btn_back = QtWidgets.QPushButton(_tr("← Inicio"))
        self.btn_back.clicked.connect(self._go_back)
        self.btn_refresh = QtWidgets.QPushButton(_tr("Actualizar"))
        self.btn_refresh.clicked.connect(self.refresh_from_project)
        top.addWidget(self.btn_back)
        top.addWidget(self.btn_refresh)
        top.addStretch(1)
        root.addLayout(top)
        
        # Corporate header
        hero = QtWidgets.QHBoxLayout()
        hero.setSpacing(16)

        hero_text = QtWidgets.QVBoxLayout()
        hero_text.setSpacing(6)
        title = QtWidgets.QLabel(_tr("Sombras y parpadeo"))
        title.setObjectName("shadowTitle")
        hero_text.addWidget(title)
        
        subtitle = QtWidgets.QLabel(_tr(
            "Módulo de sombras y parpadeo para aerogeneradores. "
            "Conectado al layout del proyecto, calcula receptores puntuales "
            "y genera capas QGIS de salida detalladas por receptor."
        ))
        subtitle.setWordWrap(True)
        subtitle.setObjectName("shadowSubtitle")
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
        
        # Group: Project context
        grp_ctx = QtWidgets.QGroupBox(_tr("Contexto del proyecto"))
        form_ctx = QtWidgets.QFormLayout(grp_ctx)
        
        self.lbl_project = QtWidgets.QLabel("-")
        self.lbl_crs = QtWidgets.QLabel("-")
        self.lbl_layout = QtWidgets.QLabel("-")
        self.lbl_models = QtWidgets.QLabel("-")
        self.lbl_receptor_info = QtWidgets.QLabel("-")
        
        for w in [self.lbl_project, self.lbl_crs, self.lbl_layout, self.lbl_models, self.lbl_receptor_info]:
            w.setWordWrap(True)
        
        form_ctx.addRow(_tr("Proyecto:"), self.lbl_project)
        form_ctx.addRow(_tr("CRS:"), self.lbl_crs)
        form_ctx.addRow(_tr("Layout activo:"), self.lbl_layout)
        form_ctx.addRow(_tr("Modelos WT detectados:"), self.lbl_models)
        form_ctx.addRow(_tr("Capa de receptores:"), self.lbl_receptor_info)
        root.addWidget(grp_ctx)
        
        # Group: Site configuration
        grp_site = QtWidgets.QGroupBox(_tr("Configuración del emplazamiento"))
        grid_site = QtWidgets.QGridLayout(grp_site)
        row = 0
        
        # Latitude
        grid_site.addWidget(self._label_with_help("Latitud [°]:", "Latitud/longitud y año de análisis", "site"), row, 0)
        self.sp_latitude = QtWidgets.QDoubleSpinBox()
        self.sp_latitude.setDecimals(6)
        self.sp_latitude.setRange(-90.0, 90.0)
        self.sp_latitude.setValue(float(self._qsettings.value("shadow/latitude", 42.0, type=float)))
        self.sp_latitude.setSuffix(" °")
        self.sp_latitude.setToolTip(_tr("Latitud del emplazamiento (ej. 42.465 para Logroño)"))
        self.sp_latitude.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/latitude", float(v)))
        grid_site.addWidget(self.sp_latitude, row, 1)
        
        # Longitude
        grid_site.addWidget(QtWidgets.QLabel(_tr("Longitud [°]:")), row, 2)
        self.sp_longitude = QtWidgets.QDoubleSpinBox()
        self.sp_longitude.setDecimals(6)
        self.sp_longitude.setRange(-180.0, 180.0)
        self.sp_longitude.setValue(float(self._qsettings.value("shadow/longitude", -2.0, type=float)))
        self.sp_longitude.setSuffix(" °")
        self.sp_longitude.setToolTip(_tr("Longitud del emplazamiento (ej. -2.445 para Logroño)"))
        self.sp_longitude.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/longitude", float(v)))
        grid_site.addWidget(self.sp_longitude, row, 3)
        row += 1
        
        # Year
        grid_site.addWidget(QtWidgets.QLabel(_tr("Año de análisis:")), row, 0)
        self.sp_year = QtWidgets.QSpinBox()
        self.sp_year.setRange(2020, 2050)
        self.sp_year.setValue(int(self._qsettings.value("shadow/year", datetime.now().year, type=int)))
        self.sp_year.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/year", int(v)))
        grid_site.addWidget(self.sp_year, row, 1)
        
        # Time basis: civil IANA/DST or fixed UTC offset
        grid_site.addWidget(self._label_with_help("Base temporal:", "Modo de zona horaria y gestión de la hora civil", "timezone"), row, 2)
        self.cb_timezone_mode = QtWidgets.QComboBox()
        self.cb_timezone_mode.addItem(_tr("Hora civil local (IANA/DST)"), "iana")
        self.cb_timezone_mode.addItem(_tr("Desfase UTC fijo"), "fixed")
        saved_tz_mode = str(self._qsettings.value("shadow/timezone_mode", "fixed"))
        idx_mode = self.cb_timezone_mode.findData(saved_tz_mode)
        self.cb_timezone_mode.setCurrentIndex(idx_mode if idx_mode >= 0 else 0)
        self.cb_timezone_mode.setToolTip(_tr(
            "IANA/DST: la tabla usa la hora civil local real del emplazamiento.\n"
            "Desfase UTC fijo: usa el mismo desfase UTC durante todo el año."
        ))
        self.cb_timezone_mode.currentIndexChanged.connect(self._on_timezone_mode_changed)
        grid_site.addWidget(self.cb_timezone_mode, row, 3)
        row += 1

        grid_site.addWidget(QtWidgets.QLabel(_tr("Zona horaria IANA:")), row, 0)
        self.cb_timezone_name = QtWidgets.QComboBox()
        self.cb_timezone_name.setEditable(True)
        self.cb_timezone_name.addItems(load_iana_timezones())
        saved_tz_name = str(self._qsettings.value("shadow/timezone_name", "Europe/Madrid"))
        self._set_timezone_combo_value(saved_tz_name)
        self.cb_timezone_name.setToolTip(_tr(
            "Zona horaria IANA, por ejemplo Europe/Madrid, America/Santiago o Asia/Tokyo.\n"
            "El plugin incluye un catálogo IANA ampliado y una base TZif local para aplicar el horario de verano sin timezonefinder."
        ))
        self.cb_timezone_name.currentTextChanged.connect(lambda v: self._qsettings.setValue("shadow/timezone_name", str(v).strip()))
        grid_site.addWidget(self.cb_timezone_name, row, 1)

        grid_site.addWidget(QtWidgets.QLabel(_tr("Desfase UTC fijo:")), row, 2)
        self.sp_timezone = QtWidgets.QDoubleSpinBox()
        self.sp_timezone.setDecimals(1)
        self.sp_timezone.setRange(-12.0, 14.0)
        self.sp_timezone.setValue(float(self._qsettings.value("shadow/timezone_offset", 1.0, type=float)))
        self.sp_timezone.setPrefix("UTC ")
        self.sp_timezone.setToolTip(_tr("Desfase fijo para el modo UTC fijo. No se aplica horario de verano."))
        self.sp_timezone.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/timezone_offset", float(v)))
        grid_site.addWidget(self.sp_timezone, row, 3)
        row += 1

        self.lbl_timezone_status = QtWidgets.QLabel("-")
        self.lbl_timezone_status.setWordWrap(True)
        self.lbl_timezone_status.setObjectName("shadowMinor")
        grid_site.addWidget(self.lbl_timezone_status, row, 0, 1, 4)
        row += 1
        self._on_timezone_mode_changed()
        
        # Button to detect coordinates from CRS
        btn_detect = QtWidgets.QPushButton(_tr("Detectar automáticamente coordenadas y zona horaria"))
        btn_detect.clicked.connect(self._auto_detect_coordinates)
        btn_detect.setToolTip(_tr("Calcula latitud/longitud desde el centroide del layout e intenta detectar la zona IANA"))
        grid_site.addLayout(self._wrap_in_hbox(btn_detect), row, 0, 1, 4)
        row += 1
        
        root.addWidget(grp_site)
        
        # Group: Calculation inputs
        grp_inputs = QtWidgets.QGroupBox(_tr("Entradas del cálculo"))
        grid_inputs = QtWidgets.QGridLayout(grp_inputs)
        row = 0
        
        # Sources (turbines) - can be detected from any Velantis turbine layout or imported here
        grid_inputs.addWidget(self._label_with_help("Capa de aerogeneradores:", "Seleccionar o importar la capa de coordenadas de aerogeneradores", "layers"), row, 0)
        self.cb_turbines = QtWidgets.QComboBox()
        self.cb_turbines.currentIndexChanged.connect(self._on_turbine_layer_changed)
        self.cb_turbines.setToolTip(_tr("Selecciona una capa de coordenadas de aerogeneradores de VelantisWind o importa una directamente desde este módulo"))
        grid_inputs.addWidget(self.cb_turbines, row, 1, 1, 3)
        row += 1

        turbine_btns = QtWidgets.QHBoxLayout()
        self.btn_import_layout = QtWidgets.QPushButton(_tr("Importar layout de aerogeneradores desde CSV…"))
        self.btn_import_layout.clicked.connect(self._import_turbine_layout_for_shadow)
        turbine_btns.addWidget(self.btn_import_layout)
        turbine_btns.addStretch(1)
        grid_inputs.addLayout(turbine_btns, row, 1, 1, 3)
        row += 1
        
        # Receiver layer
        grid_inputs.addWidget(self._label_with_help("Capa de receptores:", "Seleccionar la capa de puntos que contiene los receptores", "layers"), row, 0)
        self.cb_receivers = QtWidgets.QComboBox()
        self.cb_receivers.currentIndexChanged.connect(self._on_receiver_changed)
        self.cb_receivers.setToolTip(_tr("Selecciona la capa de puntos que contiene los receptores"))
        grid_inputs.addWidget(self.cb_receivers, row, 1, 1, 3)
        row += 1
        
        # DEM (digital elevation model) - optional, for terrain-aware geometry
        grid_inputs.addWidget(self._label_with_help("Raster MDT/DEM (opcional):", "Raster de elevación opcional para geometría con terreno", "dem"), row, 0)
        self.cb_dem = QtWidgets.QComboBox()
        self.cb_dem.currentIndexChanged.connect(self._on_dem_changed)
        self.cb_dem.setToolTip(_tr(
            "Modelo digital de elevación (MDT/DEM) opcional.\n"
            "Si se proporciona, se muestrea la altitud del terreno bajo cada aerogenerador y cada receptor.\n"
            "Permite calcular elev_diff = (buje + terreno_aerogenerador) - (observador + terreno_receptor).\n"
            "Si queda vacío, se asume terreno plano (z=0)."
        ))
        grid_inputs.addWidget(self.cb_dem, row, 1, 1, 3)
        row += 1
        
        # Observer height
        grid_inputs.addWidget(self._label_with_help("Altura del observador [m]:", "Altura del observador, paso temporal, elevación solar, disponibilidad y distancia", "parameters"), row, 0)
        self.sp_observer_height = QtWidgets.QDoubleSpinBox()
        self.sp_observer_height.setDecimals(1)
        self.sp_observer_height.setRange(0.0, 50.0)
        self.sp_observer_height.setValue(float(self._qsettings.value("shadow/observer_height", 2.0, type=float)))
        self.sp_observer_height.setSuffix(" m")
        self.sp_observer_height.setToolTip(_tr("Altura del punto de observación (ventana típica: 2 m)"))
        self.sp_observer_height.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/observer_height", float(v)))
        grid_inputs.addWidget(self.sp_observer_height, row, 1)
        
        # Time step
        grid_inputs.addWidget(QtWidgets.QLabel(_tr("Paso temporal [min]:")), row, 2)
        self.sp_time_step = QtWidgets.QSpinBox()
        self.sp_time_step.setRange(1, 60)
        self.sp_time_step.setValue(int(self._qsettings.value("shadow/time_step_minutes", 5, type=int)))
        self.sp_time_step.setSuffix(" min")
        self.sp_time_step.setToolTip(_tr("Resolución temporal del cálculo\n5 min = buen equilibrio velocidad/precisión\n1 min = precisión máxima (muy lento)"))
        self.sp_time_step.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/time_step_minutes", int(v)))
        grid_inputs.addWidget(self.sp_time_step, row, 3)
        row += 1
        
        # Minimum/maximum solar elevation
        grid_inputs.addWidget(QtWidgets.QLabel(_tr("Elevación solar mín. [°]:")), row, 0)
        self.sp_min_elevation = QtWidgets.QDoubleSpinBox()
        self.sp_min_elevation.setDecimals(1)
        self.sp_min_elevation.setRange(0.0, 30.0)
        self.sp_min_elevation.setValue(float(self._qsettings.value("shadow/min_sun_elevation", 3.0, type=float)))
        self.sp_min_elevation.setSuffix(" °")
        self.sp_min_elevation.setToolTip(_tr("Sol demasiado bajo → ignorado (típico: 3°)"))
        self.sp_min_elevation.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/min_sun_elevation", float(v)))
        grid_inputs.addWidget(self.sp_min_elevation, row, 1)
        
        grid_inputs.addWidget(QtWidgets.QLabel(_tr("Elevación solar máx. [°]:")), row, 2)
        self.sp_max_elevation = QtWidgets.QDoubleSpinBox()
        self.sp_max_elevation.setDecimals(1)
        self.sp_max_elevation.setRange(30.0, 90.0)
        self.sp_max_elevation.setValue(float(self._qsettings.value("shadow/max_sun_elevation", 90.0, type=float)))
        self.sp_max_elevation.setSuffix(" °")
        self.sp_max_elevation.setToolTip(_tr("Elevación solar máxima a incluir (90° = sin filtrar el sol alto; valores menores son una hipótesis opcional de cribado)"))
        self.sp_max_elevation.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/max_sun_elevation", float(v)))
        grid_inputs.addWidget(self.sp_max_elevation, row, 3)
        row += 1
        
        # Turbine availability
        grid_inputs.addWidget(self._label_with_help("Disponibilidad de los aerogeneradores:", "Disponibilidad y distancia máxima de influencia", "parameters"), row, 0)
        self.sp_availability = QtWidgets.QDoubleSpinBox()
        self.sp_availability.setDecimals(3)
        self.sp_availability.setRange(0.0, 1.0)
        self.sp_availability.setValue(float(self._qsettings.value("shadow/turbine_availability", 0.97, type=float)))
        self.sp_availability.setSingleStep(0.01)
        self.sp_availability.setToolTip(_tr("Fracción del tiempo durante la que el aerogenerador está en funcionamiento (0.97 = 97 %)"))
        self.sp_availability.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/turbine_availability", float(v)))
        grid_inputs.addWidget(self.sp_availability, row, 1)

        grid_inputs.addWidget(QtWidgets.QLabel(_tr("Distancia máxima de sombra [m]:")), row, 2)
        self.sp_max_shadow_distance = QtWidgets.QSpinBox()
        self.sp_max_shadow_distance.setRange(100, 20000)
        self.sp_max_shadow_distance.setSingleStep(100)
        self.sp_max_shadow_distance.setValue(int(self._qsettings.value("shadow/max_shadow_distance", int(DEFAULT_MAX_SHADOW_DISTANCE_M), type=int)))
        self.sp_max_shadow_distance.setSuffix(" m")
        self.sp_max_shadow_distance.setToolTip(_tr(
            "Distancia máxima desde un aerogenerador para considerar sombras y parpadeo.\n"
            "Valor por defecto: 2000 m, coherente con una distancia de cribado conservadora tipo Continuum.\n"
            "Se usa para filtrar receptores y para la extensión/máscara del raster."
        ))
        self.sp_max_shadow_distance.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/max_shadow_distance", int(v)))
        self.sp_max_shadow_distance.valueChanged.connect(lambda _v: self._check_configuration())
        grid_inputs.addWidget(self.sp_max_shadow_distance, row, 3)
        row += 1
        
        
        root.addWidget(grp_inputs)
        
        # Group: turbine model configuration (hub height and rotor diameter)
        grp_models = QtWidgets.QGroupBox(_tr("Configuración de los modelos de aerogenerador"))
        models_lay = QtWidgets.QVBoxLayout(grp_models)
        models_head = QtWidgets.QHBoxLayout()
        models_head.addWidget(QtWidgets.QLabel(_tr("Comprueba la altura de buje y el diámetro del rotor para cada modelo de aerogenerador detectado.")))
        models_head.addWidget(self._make_help_button("Altura de buje, diámetro del rotor y notas del modelo", "models"))
        models_head.addStretch(1)
        models_lay.addLayout(models_head)
        
        self.tbl_models = QtWidgets.QTableWidget(0, 5)
        self.tbl_models.setMinimumHeight(150)
        self.tbl_models.setHorizontalHeaderLabels([
            _tr("Modelo"), _tr("Aerogeneradores"), _tr("Altura de buje [m]"), _tr("Diámetro del rotor [m]"), _tr("Notas")
        ])
        hh_models = self.tbl_models.horizontalHeader()
        hh_models.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        hh_models.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        for c in (1, 2, 3):
            hh_models.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
        self.tbl_models.verticalHeader().setVisible(False)
        self.tbl_models.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_models.setToolTip(_tr(
            "Configura los parámetros geométricos de cada modelo de aerogenerador.\n"
            "Altura de buje: altura sobre el terreno [m]\n"
            "Diámetro del rotor: diámetro del rotor [m]"
        ))
        models_lay.addWidget(self.tbl_models)
        
        help_models = QtWidgets.QLabel(_tr(
            "💡 Configura la altura de buje y el diámetro del rotor para cada modelo detectado. "
            "Estos parámetros son necesarios para el cálculo de sombras y parpadeo."
        ))
        help_models.setWordWrap(True)
        help_models.setObjectName("shadowMinor")
        models_lay.addWidget(help_models)
        
        root.addWidget(grp_models)
        
        # Group: Calculation preparation
        grp_actions = QtWidgets.QGroupBox(_tr("Preparación del cálculo"))
        act_lay = QtWidgets.QVBoxLayout(grp_actions)
        
        self.txt_status = QtWidgets.QTextEdit()
        self.txt_status.setReadOnly(True)
        self.txt_status.setMinimumHeight(120)
        self.txt_status.setMaximumHeight(220)
        act_lay.addWidget(self.txt_status)
        
        # Option to create raster map
        raster_layout = QtWidgets.QHBoxLayout()
        self.chk_create_raster = QtWidgets.QCheckBox(_tr("Crear mapa raster de sombras y parpadeo"))
        self.chk_create_raster.setChecked(bool(self._qsettings.value("shadow/create_raster", False, type=bool)))
        self.chk_create_raster.setToolTip(_tr(
            "Genera un mapa raster continuo de horas de sombra y parpadeo\n"
            "Muestra un gradiente de colores en toda la zona de análisis\n"
            "ATENCIÓN: puede tardar varios minutos según la zona"
        ))
        self.chk_create_raster.stateChanged.connect(lambda s: self._qsettings.setValue("shadow/create_raster", bool(s)))
        raster_layout.addWidget(self.chk_create_raster)
        raster_layout.addWidget(self._make_help_button("Mapa raster, resolución y paso temporal del raster", "raster"))
        
        raster_layout.addWidget(QtWidgets.QLabel(_tr("Resolución [m]:")))
        self.sp_raster_resolution = QtWidgets.QSpinBox()
        self.sp_raster_resolution.setRange(25, 500)
        self.sp_raster_resolution.setValue(int(self._qsettings.value("shadow/raster_resolution", 100, type=int)))
        self.sp_raster_resolution.setSuffix(" m")
        self.sp_raster_resolution.setToolTip(_tr(
            "Tamaño de celda del raster\n"
            "100 m = rápido, menos detalle\n"
            "50 m = intermedio\n"
            "25 m = lento, máximo detalle"
        ))
        self.sp_raster_resolution.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/raster_resolution", int(v)))
        self.sp_raster_resolution.setEnabled(self.chk_create_raster.isChecked())
        self.chk_create_raster.stateChanged.connect(lambda s: self.sp_raster_resolution.setEnabled(bool(s)))
        raster_layout.addWidget(self.sp_raster_resolution)
        
        # Raster timestep (can be larger than the point-receiver timestep)
        raster_layout.addWidget(QtWidgets.QLabel(_tr("Paso temporal [min]:")))
        self.sp_raster_timestep = QtWidgets.QSpinBox()
        self.sp_raster_timestep.setRange(1, 30)
        self.sp_raster_timestep.setValue(int(self._qsettings.value("shadow/raster_timestep", 5, type=int)))
        self.sp_raster_timestep.setSuffix(" min")
        self.sp_raster_timestep.setToolTip(_tr(
            "Paso temporal SOLO para el raster (independiente de los receptores).\n"
            "1 min = precisión máxima, MUY lento\n"
            "5 min = recomendado (precisión >98 %, 5× más rápido)\n"
            "10 min = muy rápido, precisión ~95 %\n"
            "20 min = ultrarrápido para previsualizar"
        ))
        self.sp_raster_timestep.valueChanged.connect(lambda v: self._qsettings.setValue("shadow/raster_timestep", int(v)))
        self.sp_raster_timestep.setEnabled(self.chk_create_raster.isChecked())
        self.chk_create_raster.stateChanged.connect(lambda s: self.sp_raster_timestep.setEnabled(bool(s)))
        raster_layout.addWidget(self.sp_raster_timestep)
        
        raster_layout.addStretch(1)
        act_lay.addLayout(raster_layout)
        
        # ============ NEW: Raster month/hour filter ============
        filter_group = QtWidgets.QGroupBox(_tr("Filtrar raster por mes/hora (después de generarlo)"))
        filter_group.setToolTip(_tr(
            "Una vez generado el raster, puedes regenerar TIF filtrados por mes y/o hora\n"
            "sin recalcular toda la geometría anual."
        ))
        filter_layout = QtWidgets.QHBoxLayout(filter_group)
        filter_layout.addWidget(self._make_help_button("Filtrar el raster generado por mes y/u hora", "filter"))
        
        filter_layout.addWidget(QtWidgets.QLabel(_tr("Mes:")))
        self.cb_filter_month = QtWidgets.QComboBox()
        self.cb_filter_month.addItem(_tr("Todos"), -1)
        months = [_tr(m) for m in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]]
        for i, m in enumerate(months):
            self.cb_filter_month.addItem(m, i)
        filter_layout.addWidget(self.cb_filter_month)
        
        filter_layout.addWidget(QtWidgets.QLabel(_tr("Hora:")))
        self.cb_filter_hour = QtWidgets.QComboBox()
        self.cb_filter_hour.addItem(_tr("Todas"), -1)
        for h in range(24):
            self.cb_filter_hour.addItem(f"{h:02d}:00", h)
        filter_layout.addWidget(self.cb_filter_hour)
        
        self.btn_regenerate = QtWidgets.QPushButton(_tr("📊 Regenerar TIF filtrado"))
        self.btn_regenerate.setToolTip(_tr("Crea un nuevo TIF con el filtro de mes/hora seleccionado"))
        self.btn_regenerate.clicked.connect(self._regenerate_filtered_raster)
        self.btn_regenerate.setEnabled(False)  # Se habilita después de generar el raster
        filter_layout.addWidget(self.btn_regenerate)
        
        filter_layout.addStretch(1)
        act_lay.addWidget(filter_group)
        
        # Guardar referencia al último NPZ para regeneración
        self._last_npz_path = None
        
        btns = QtWidgets.QHBoxLayout()
        self.btn_check = QtWidgets.QPushButton(_tr("Comprobar configuración"))
        self.btn_check.setMinimumHeight(34)
        self.btn_check.clicked.connect(self._check_configuration)
        
        self.btn_calc = QtWidgets.QPushButton(_tr("Calcular sombras y parpadeo"))
        self.btn_calc.setMinimumHeight(34)
        self.btn_calc.clicked.connect(self._run_shadow_calculation)
        
        btns.addStretch(1)
        btns.addWidget(self.btn_check)
        btns.addWidget(self.btn_calc)
        act_lay.addLayout(btns)
        
        root.addWidget(grp_actions)
    
    def _apply_style(self):
        """Apply CSS styles to the module."""
        self.setStyleSheet(
            self.styleSheet()
            + """
            QLabel#shadowTitle { font-size: 22px; font-weight: 700; color: #103b67; }
            QLabel#shadowSubtitle { font-size: 12px; color: #4f5d6b; }
            QLabel#shadowMinor { font-size: 11px; color: #667480; }
            QTextEdit { background: white; }
            QGroupBox { background: white; }
            QTableWidget { background: white; }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton { min-height: 28px; }
            """
        )
    
    def _wrap_in_hbox(self, widget: QtWidgets.QWidget) -> QtWidgets.QHBoxLayout:
        """Wrap a widget in a QHBoxLayout."""
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(widget)
        hbox.addStretch(1)
        return hbox
    
    def _set_timezone_combo_value(self, tz_name: str):
        """Set editable timezone combo without requiring the value to pre-exist."""
        if not hasattr(self, "cb_timezone_name"):
            return
        tz_name = (tz_name or "UTC").strip() or "UTC"
        idx = self.cb_timezone_name.findText(tz_name, QtCore.Qt.MatchFixedString)
        if idx < 0:
            self.cb_timezone_name.insertItem(0, tz_name)
            idx = 0
        self.cb_timezone_name.setCurrentIndex(idx)
        self.cb_timezone_name.setEditText(tz_name)

    def _on_timezone_mode_changed(self, *args):
        """Enable/disable timezone widgets according to selected time basis."""
        if not hasattr(self, "cb_timezone_mode"):
            return
        mode = self.cb_timezone_mode.currentData(QtCore.Qt.UserRole) or "fixed"
        mode = str(mode)
        self._qsettings.setValue("shadow/timezone_mode", mode)

        use_iana = mode == "iana"
        if hasattr(self, "cb_timezone_name"):
            self.cb_timezone_name.setEnabled(use_iana)
        if hasattr(self, "sp_timezone"):
            self.sp_timezone.setEnabled(not use_iana)
        if hasattr(self, "lbl_timezone_status"):
            if use_iana:
                tz_name = self.cb_timezone_name.currentText().strip() if hasattr(self, "cb_timezone_name") else "UTC"
                self.lbl_timezone_status.setText(
                    _ml(
                        f"Tabla horaria: hora civil local con DST · Zona: {tz_name}. El cálculo solar usa UTC internamente y acumula resultados por mes/hora local.",
                        f"Time table: local civil time with DST · Zone: {tz_name}. The solar calculation uses UTC internally and aggregates results by local month/hour.",
                        f"Table horaire : heure civile locale avec DST · Zone : {tz_name}. Le calcul solaire utilise UTC en interne et accumule les résultats par mois/heure locaux.",
                        f"Zeittabelle: lokale Uhrzeit mit DST · Zone: {tz_name}. Die Sonnenberechnung verwendet intern UTC und aggregiert die Ergebnisse nach lokalen Monaten/Stunden.",
                    )
                )
            else:
                offset = self.sp_timezone.value() if hasattr(self, "sp_timezone") else 0.0
                self.lbl_timezone_status.setText(
                    _ml(
                        f"Tabla horaria: desfase UTC fijo UTC{offset:+.1f}. Útil para cálculos reproducibles con desfase fijo; no se aplica horario de verano.",
                        f"Time table: fixed UTC offset UTC{offset:+.1f}. Useful for reproducible fixed-offset calculations; daylight saving time is not applied.",
                        f"Table horaire : décalage UTC fixe UTC{offset:+.1f}. Utile pour une reproductibilité à décalage fixe ; l’heure d’été n’est pas appliquée.",
                        f"Zeittabelle: fester UTC-Offset UTC{offset:+.1f}. Nützlich für reproduzierbare Berechnungen mit festem Offset; Sommerzeit wird nicht angewendet.",
                    )
                )
        if hasattr(self, "txt_status") and hasattr(self, "btn_calc"):
            self._check_configuration()

    def _get_timezone_settings(self):
        """Return (mode, timezone_name, fixed_offset)."""
        mode = self.cb_timezone_mode.currentData(QtCore.Qt.UserRole) if hasattr(self, "cb_timezone_mode") else "fixed"
        mode = str(mode or "fixed")
        tz_name = self.cb_timezone_name.currentText().strip() if hasattr(self, "cb_timezone_name") else "UTC"
        if not tz_name:
            tz_name = "UTC"
        offset = float(self.sp_timezone.value()) if hasattr(self, "sp_timezone") else 0.0
        self._qsettings.setValue("shadow/timezone_mode", mode)
        self._qsettings.setValue("shadow/timezone_name", tz_name)
        self._qsettings.setValue("shadow/timezone_offset", offset)
        return mode, tz_name, offset

    def _go_back(self):
        """Return to the main hub."""
        if self._on_back:
            self._on_back()
    
    # ========== UPDATE METHODS ==========
    
    def _import_turbine_layout_for_shadow(self):
        """Import a turbine-coordinate CSV directly from the Shadow module."""
        try:
            layer = import_turbine_layout_from_csv(self, module="shadow")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                _ml("Sombras · Importar layout", "Shadow · Layout import", "Ombres · Import d’implantation", "Schattenwurf · Layout-Import"),
                _ml(
                    f"No se pudo importar el layout de aerogeneradores:\n{e}",
                    f"Could not import the wind-turbine layout:\n{e}",
                    f"Impossible d’importer l’implantation d’éoliennes :\n{e}",
                    f"Das Windturbinen-Layout konnte nicht importiert werden:\n{e}",
                ),
            )
            return
        if layer is None:
            return
        try:
            self._qsettings.setValue("shadow/turbine_layer_id", layer.id())
        except Exception:
            pass
        self.refresh_from_project()
        try:
            idx = self.cb_turbines.findData(layer.id(), QtCore.Qt.UserRole)
            if idx >= 0:
                self.cb_turbines.setCurrentIndex(idx)
        except Exception:
            pass
        QtWidgets.QMessageBox.information(
            self,
            _ml("Sombras · Importar layout", "Shadow · Layout import", "Ombres · Import d’implantation", "Schattenwurf · Layout-Import"),
            _ml(f"'{layer.name()}' importado con {int(layer.featureCount())} aerogenerador(es).", f"'{layer.name()}' imported with {int(layer.featureCount())} wind turbine(s).", f"'{layer.name()}' importé avec {int(layer.featureCount())} éolienne(s).", f"'{layer.name()}' mit {int(layer.featureCount())} Windturbine(n) importiert.")
        )

    def refresh_from_project(self):
        """Refresh the interface from the QGIS project."""
        prj = QgsProject.instance()
        self._model_rows = self._detect_models(prj)
        self._populate_context(prj)
        self._populate_turbines_combo(prj)
        self._populate_receivers_combo(prj)
        self._populate_dem_combo(prj)
        self._check_configuration()
    
    def _populate_context(self, prj: QgsProject):
        """Populate project context information."""
        base_name = (prj.baseName() or _tr("Proyecto sin nombre")).strip() or _tr("Proyecto sin nombre")
        self.lbl_project.setText(base_name)
        self.lbl_crs.setText(prj.crs().authid() or _tr("CRS no disponible"))
        
        n_models = len(self._model_rows)
        n_turbs = sum(int(r.get("n_turbines", 0)) for r in self._model_rows)
        
        if n_models <= 0:
            self.lbl_layout.setText(_tr("No se ha detectado ningún layout"))
            self.lbl_models.setText("0")
        else:
            self.lbl_layout.setText(_ml(f"{n_models} modelo(s) WT · {n_turbs} aerogenerador(es)", f"{n_models} WT model(s) · {n_turbs} wind turbine(s)", f"{n_models} modèle(s) WT · {n_turbs} éolienne(s)", f"{n_models} WT-Modell(e) · {n_turbs} Windturbine(n)"))
            names = ", ".join(str(r.get("name", "-")) for r in self._model_rows[:5])
            if n_models > 5:
                names += " …"
            self.lbl_models.setText(names)
    
    def _populate_turbines_combo(self, prj: QgsProject):
        """Populate turbine-layer combo."""
        current_id = self._qsettings.value("shadow/turbine_layer_id", "", type=str)
        
        self.cb_turbines.blockSignals(True)
        self.cb_turbines.clear()
        self.cb_turbines.addItem(_tr("— Seleccionar capa de aerogeneradores —"), None)
        
        # Show any VelantisWind turbine/model layer, regardless of which module imported it.
        for model_info in self._model_rows:
            lid = str(model_info.get("layer_id", ""))
            if not lid:
                continue
            name = str(model_info.get("name", _tr("Modelo")))
            n = int(model_info.get("n_turbines", 0))
            self.cb_turbines.addItem(_ml(f"{name} ({n} aerogenerador(es))", f"{name} ({n} wind turbine(s))", f"{name} ({n} éolienne(s))", f"{name} ({n} Windturbine(n))"), lid)
        
        # Restaurar selección previa
        idx = self.cb_turbines.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_turbines.setCurrentIndex(idx)
        
        self.cb_turbines.blockSignals(False)
        self._on_turbine_layer_changed()
    
    def _populate_receivers_combo(self, prj: QgsProject):
        """Populate receiver-layer combo."""
        current_id = self._qsettings.value("shadow/receiver_layer_id", self.cb_receivers.currentData(QtCore.Qt.UserRole), type=str)
        model_layer_ids = {str(r.get("layer_id")) for r in self._model_rows if r.get("layer_id")}
        
        self.cb_receivers.blockSignals(True)
        self.cb_receivers.clear()
        self.cb_receivers.addItem(_tr("— Seleccionar capa de receptores —"), None)
        
        for lyr in prj.mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if bool(lyr.customProperty("velantis/shadow_output", False)):
                continue
            if lyr.id() in model_layer_ids:
                continue
            
            gtype = QgsWkbTypes.geometryType(lyr.wkbType())
            if gtype == QgsWkbTypes.PointGeometry:
                self.cb_receivers.addItem(f"{lyr.name()} [Points]", lyr.id())
        
        idx = self.cb_receivers.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_receivers.setCurrentIndex(idx)
        
        self.cb_receivers.blockSignals(False)
        self._on_receiver_changed()
    
    def _populate_dem_combo(self, prj: QgsProject):
        """Populate DEM raster combo. The DEM is optional - if not selected,
        the calculation falls back to flat-terrain behaviour."""
        current_id = self._qsettings.value("shadow/dem_layer_id", "", type=str)
        
        self.cb_dem.blockSignals(True)
        self.cb_dem.clear()
        self.cb_dem.addItem(_tr("— Sin DEM/MDT (terreno plano) —"), None)
        
        for lyr in prj.mapLayers().values():
            if not isinstance(lyr, QgsRasterLayer):
                continue
            # Filter out non-elevation rasters by heuristic: must have at least 1 band.
            try:
                if lyr.bandCount() < 1:
                    continue
            except Exception:
                continue
            self.cb_dem.addItem(f"{lyr.name()} [{lyr.crs().authid()}]", lyr.id())
        
        idx = self.cb_dem.findData(current_id, QtCore.Qt.UserRole)
        if idx >= 0:
            self.cb_dem.setCurrentIndex(idx)
        
        self.cb_dem.blockSignals(False)
    
    def _on_dem_changed(self):
        """Persist DEM layer selection."""
        lid = self.cb_dem.currentData(QtCore.Qt.UserRole)
        if lid:
            self._qsettings.setValue("shadow/dem_layer_id", lid)
        else:
            self._qsettings.setValue("shadow/dem_layer_id", "")
    
    def _populate_models_table(self):
        """Populate model-configuration table for the selected turbine layer."""
        self.tbl_models.blockSignals(True)
        self.tbl_models.setRowCount(0)
        
        # Get selected turbine layer
        turbine_layer_id = self.cb_turbines.currentData(QtCore.Qt.UserRole)
        if not turbine_layer_id:
            self.tbl_models.blockSignals(False)
            return
        
        # Find corresponding model info
        model_info = None
        for info in self._model_rows:
            if str(info.get("layer_id", "")) == turbine_layer_id:
                model_info = info
                break
        
        if not model_info:
            self.tbl_models.blockSignals(False)
            return
        
        # Add a single row with the selected model
        self.tbl_models.insertRow(0)
        
        # Column 0: model name (read-only)
        item_name = QtWidgets.QTableWidgetItem(str(model_info.get("name", "Model")))
        item_name.setFlags(item_name.flags() & ~QtCore.Qt.ItemIsEditable)
        self.tbl_models.setItem(0, 0, item_name)
        
        # Column 1: number of turbines (read-only)
        item_n = QtWidgets.QTableWidgetItem(str(model_info.get("n_turbines", 0)))
        item_n.setFlags(item_n.flags() & ~QtCore.Qt.ItemIsEditable)
        item_n.setTextAlignment(QtCore.Qt.AlignCenter)
        self.tbl_models.setItem(0, 1, item_n)
        
        # Column 2: Hub Height (editable) - try saved value, imported metadata or default
        default_hh = model_info.get('hub_height')
        default_hh_txt = f"{float(default_hh):.1f}" if default_hh is not None else "100.0"
        saved_hh = self._qsettings.value(f"shadow/model_{model_info.get('name')}_hh", default_hh_txt, type=str)
        item_hh = QtWidgets.QTableWidgetItem(saved_hh)
        item_hh.setTextAlignment(QtCore.Qt.AlignCenter)
        self.tbl_models.setItem(0, 2, item_hh)
        
        # Column 3: Rotor Diameter (editable) - try saved value, imported metadata or default
        default_d = model_info.get('diameter')
        default_d_txt = f"{float(default_d):.1f}" if default_d is not None else "120.0"
        saved_d = self._qsettings.value(f"shadow/model_{model_info.get('name')}_d", default_d_txt, type=str)
        item_d = QtWidgets.QTableWidgetItem(saved_d)
        item_d.setTextAlignment(QtCore.Qt.AlignCenter)
        self.tbl_models.setItem(0, 3, item_d)
        
        # Column 4: Notes (editable)
        saved_notes = self._qsettings.value(f"shadow/model_{model_info.get('name')}_notes", "", type=str)
        item_notes = QtWidgets.QTableWidgetItem(saved_notes)
        self.tbl_models.setItem(0, 4, item_notes)
        
        # Connect signals to save changes
        self.tbl_models.itemChanged.connect(self._on_model_table_changed)
        
        self.tbl_models.blockSignals(False)
    
    def _on_model_table_changed(self, item):
        """Save model-table changes into QSettings."""
        if self.tbl_models.rowCount() == 0:
            return
        
        model_name = self.tbl_models.item(0, 0).text()
        
        try:
            if item.column() == 2:  # Hub Height
                self._qsettings.setValue(f"shadow/model_{model_name}_hh", item.text())
            elif item.column() == 3:  # Rotor Diameter
                self._qsettings.setValue(f"shadow/model_{model_name}_d", item.text())
            elif item.column() == 4:  # Notes
                self._qsettings.setValue(f"shadow/model_{model_name}_notes", item.text())
        except Exception:
            pass
        
        self._check_configuration()
    
    # ========== EVENTS AND CHANGES ==========
    
    def _on_turbine_layer_changed(self):
        """Callback when the selected turbine layer changes."""
        lid = self.cb_turbines.currentData(QtCore.Qt.UserRole)
        if lid:
            self._qsettings.setValue("shadow/turbine_layer_id", lid)
        
        # Refresh tabla de modelos with la selected layer
        self._populate_models_table()
        self._check_configuration()
    
    def _on_receiver_changed(self):
        """Callback when the receiver layer changes."""
        lid = self.cb_receivers.currentData(QtCore.Qt.UserRole)
        if lid:
            self._qsettings.setValue("shadow/receiver_layer_id", lid)
        
        # Refresh info
        if lid:
            prj = QgsProject.instance()
            lyr = prj.mapLayer(lid)
            if lyr:
                self.lbl_receptor_info.setText(_ml(f"{lyr.name()} · {lyr.featureCount()} receptor(es)", f"{lyr.name()} · {lyr.featureCount()} receiver(s)", f"{lyr.name()} · {lyr.featureCount()} récepteur(s)", f"{lyr.name()} · {lyr.featureCount()} Rezeptor(en)"))
            else:
                self.lbl_receptor_info.setText("-")
        else:
            self.lbl_receptor_info.setText("-")
        
        self._check_configuration()
    
    def _auto_detect_coordinates(self):
        """Auto-detect latitude/longitude from the layout centroid."""
        try:
            prj = QgsProject.instance()
            project_crs = prj.crs()
            
            if not project_crs.isValid():
                QtWidgets.QMessageBox.warning(
                    self,
                    _ml("CRS no válido", "Invalid CRS", "CRS non valide", "Ungültiges CRS"),
                    _ml("El proyecto no tiene un CRS válido.", "The project does not have a valid CRS.", "Le projet n’a pas de CRS valide.", "Das Projekt hat kein gültiges CRS."),
                )
                return
            
            # Prefer computing centroid from the SELECTED layer
            all_coords = []
            source_description = ""
            
            # Opción 1: Usar selected layer en el combo
            selected_layer_id = self.cb_turbines.currentData(QtCore.Qt.UserRole)
            if selected_layer_id:
                lyr = prj.mapLayer(str(selected_layer_id))
                if lyr:
                    for feat in lyr.getFeatures():
                        geom = feat.geometry()
                        if geom and not geom.isNull():
                            all_coords.append(geom.asPoint())
                    source_description = _ml(f"la capa seleccionada '{lyr.name()}'", f"selected layer '{lyr.name()}'", f"couche sélectionnée '{lyr.name()}'", f"ausgewähltem Layer '{lyr.name()}'")
                    debug_print(f"[Shadow] Centroid calculated from {source_description}: {len(all_coords)} turbines")
            
            # Opción 2: Si no hay selected layer, usar todas las capas de turbinas detectadas/importadas
            if not all_coords:
                for info in self._model_rows:
                    lyr = prj.mapLayer(str(info.get("layer_id", "")))
                    if not lyr:
                        continue
                    for feat in lyr.getFeatures():
                        geom = feat.geometry()
                        if geom and not geom.isNull():
                            all_coords.append(geom.asPoint())
                source_description = _ml("todas las capas del módulo de Energía", "all Energy module layers", "toutes les couches du module Énergie", "allen Layern des Energiemoduls")
                debug_print(f"[Shadow] Centroid calculated from {source_description}: {len(all_coords)} turbines")
            
            if not all_coords:
                QtWidgets.QMessageBox.warning(self, _ml("Sin coordenadas", "No coordinates", "Aucune coordonnée", "Keine Koordinate"), _ml("No se encontró ningún aerogenerador en el layout.", "No wind turbine was found in the layout.", "Aucune éolienne n’a été trouvée dans le layout.", "Im Layout wurde keine Windturbine gefunden."))
                return
            
            # Centroide
            x_avg = sum(p.x() for p in all_coords) / len(all_coords)
            y_avg = sum(p.y() for p in all_coords) / len(all_coords)
            centroid = QgsPointXY(x_avg, y_avg)
            
            # Transformar a WGS84
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(project_crs, wgs84, prj)
            centroid_wgs84 = transform.transform(centroid)
            
            debug_print(f"  UTM centroid: ({x_avg:.0f}, {y_avg:.0f})")
            debug_print(f"  WGS84 centroid: ({centroid_wgs84.x():.6f}°, {centroid_wgs84.y():.6f}°)")
            
            # Refresh spinboxes
            lat = centroid_wgs84.y()
            lon = centroid_wgs84.x()
            self.sp_latitude.setValue(lat)
            self.sp_longitude.setValue(lon)

            # Detect IANA time zone if possible
            tz_name, tz_method, tz_warning = detect_timezone_name(lat, lon)
            tz_msg = ""
            if tz_name:
                self._set_timezone_combo_value(tz_name)
                idx = self.cb_timezone_mode.findData("iana")
                if idx >= 0:
                    self.cb_timezone_mode.setCurrentIndex(idx)
                self._qsettings.setValue("shadow/timezone_name", tz_name)
                self._qsettings.setValue("shadow/timezone_mode", "iana")
                self._on_timezone_mode_changed()
                tz_msg = _ml(
                    f"\nZona horaria detectada: {tz_name}\nMétodo: {tz_method}",
                    f"\nTime zone detected: {tz_name}\nMethod: {tz_method}",
                    f"\nFuseau horaire détecté : {tz_name}\nMéthode : {tz_method}",
                    f"\nZeitzone erkannt: {tz_name}\nMethode: {tz_method}",
                )
                if tz_warning:
                    tz_msg += _ml(
                        f"\nAviso: {tz_warning}",
                        f"\nWarning: {tz_warning}",
                        f"\nAvertissement : {tz_warning}",
                        f"\nWarnung: {tz_warning}",
                    )
            else:
                tz_msg = _ml(
                    f"\nZona horaria: no detectada automáticamente.\n{tz_warning or 'Selecciona manualmente una zona IANA.'}",
                    f"\nTime zone: not detected automatically.\n{tz_warning or 'Select an IANA time zone manually.'}",
                    f"\nFuseau horaire : non détecté automatiquement.\n{tz_warning or 'Sélectionnez manuellement un fuseau IANA.'}",
                    f"\nZeitzone: nicht automatisch erkannt.\n{tz_warning or 'Wählen Sie manuell eine IANA-Zeitzone aus.'}",
                )
            
            QtWidgets.QMessageBox.information(
                self,
                _ml("Coordenadas detectadas", "Coordinates detected", "Coordonnées détectées", "Koordinaten erkannt"),
                _ml(
                    f"Latitud: {lat:.6f}°\nLongitud: {lon:.6f}°\n\nCalculado desde {source_description}.\nNúmero total de aerogeneradores usados: {len(all_coords)}{tz_msg}",
                    f"Latitude: {lat:.6f}°\nLongitude: {lon:.6f}°\n\nCalculated from {source_description}.\nTotal wind turbines used: {len(all_coords)}{tz_msg}",
                    f"Latitude : {lat:.6f}°\nLongitude : {lon:.6f}°\n\nCalculé depuis {source_description}.\nNombre total d’éoliennes utilisées : {len(all_coords)}{tz_msg}",
                    f"Breitengrad: {lat:.6f}°\nLängengrad: {lon:.6f}°\n\nBerechnet aus {source_description}.\nAnzahl verwendeter Windturbinen: {len(all_coords)}{tz_msg}",
                )
            )
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                _ml("Error", "Error", "Erreur", "Fehler"),
                _ml(
                    f"Error al detectar las coordenadas:\n\n{e}",
                    f"Error while detecting coordinates:\n\n{e}",
                    f"Erreur lors de la détection des coordonnées :\n\n{e}",
                    f"Fehler beim Erkennen der Koordinaten:\n\n{e}",
                ),
            )
    
    def _check_configuration(self):
        """Check configuration and show status."""
        msgs = []
        is_valid = True
        de = str(current_language()).lower().startswith("de")
        
        # Turbine layer
        turbine_layer_id = self.cb_turbines.currentData(QtCore.Qt.UserRole)
        if not turbine_layer_id:
            msgs.append(_ml("⚠️ No se ha seleccionado ninguna capa de aerogeneradores.", "⚠️ No wind-turbine layer selected.", "⚠️ Aucune couche d’éoliennes sélectionnée.", "⚠️ Kein Windturbinen-Layer ausgewählt."))
            is_valid = False
        else:
            prj = QgsProject.instance()
            lyr = prj.mapLayer(turbine_layer_id)
            if lyr:
                n_turb = lyr.featureCount()
                msgs.append(_ml(f"✓ Capa de aerogeneradores: {lyr.name()} con {n_turb} aerogenerador(es).", f"✓ Wind-turbine layer: {lyr.name()} with {n_turb} wind turbine(s).", f"✓ Couche d’éoliennes : {lyr.name()} avec {n_turb} éolienne(s).", f"✓ Windturbinen-Layer: {lyr.name()} mit {n_turb} Windturbine(n)."))
                if n_turb == 0:
                    msgs.append(_ml("⚠️ La capa de aerogeneradores está vacía.", "⚠️ The wind-turbine layer is empty.", "⚠️ La couche d’éoliennes est vide.", "⚠️ Der Windturbinen-Layer ist leer."))
                    is_valid = False
            else:
                msgs.append(_ml("⚠️ No se encontró la capa de aerogeneradores.", "⚠️ Wind-turbine layer not found.", "⚠️ Couche d’éoliennes introuvable.", "⚠️ Windturbinen-Layer nicht gefunden."))
        min_elev = self.sp_min_elevation.value()
        max_elev = self.sp_max_elevation.value()
        msgs.append(_ml(f"✓ Elevación solar: {min_elev}° - {max_elev}°", f"✓ Solar elevation: {min_elev}° - {max_elev}°", f"✓ Élévation solaire : {min_elev}° - {max_elev}°", f"✓ Sonnenhöhe: {min_elev}° - {max_elev}°"))
        msgs.append(_ml(f"✓ Distancia máxima de sombra: {self.sp_max_shadow_distance.value()} m", f"✓ Maximum shadow distance: {self.sp_max_shadow_distance.value()} m", f"✓ Distance maximale d’ombre : {self.sp_max_shadow_distance.value()} m", f"✓ Maximale Schattenentfernung: {self.sp_max_shadow_distance.value()} m"))
        
        # Model configuration
        n_models = self.tbl_models.rowCount()
        if n_models == 0:
            msgs.append(_ml("⚠️ No se ha detectado ningún modelo. Comprueba que existan capas de aerogeneradores.", "⚠️ No model detected. Check that wind-turbine layers exist.", "⚠️ Aucun modèle détecté. Vérifiez que les couches d’éoliennes existent.", "⚠️ Kein Modell erkannt. Prüfen Sie, ob Windturbinen-Layer vorhanden sind."))
            is_valid = False
        else:
            models_ok = 0
            geometry_lines = []
            for i in range(n_models):
                try:
                    model_name_item = self.tbl_models.item(i, 0)
                    model_name = model_name_item.text() if model_name_item is not None else _ml(f"Modelo {i + 1}", f"Model {i + 1}", f"Modèle {i + 1}", f"Modell {i + 1}")
                    hh = float(self.tbl_models.item(i, 2).text())
                    d = float(self.tbl_models.item(i, 3).text())
                    if hh > 0 and d > 0:
                        models_ok += 1
                        geometry_lines.append(_ml(f"   {model_name}: altura de buje={hh:.2f} m · diámetro del rotor={d:.2f} m", f"   {model_name}: hub height={hh:.2f} m · rotor diameter={d:.2f} m", f"   {model_name} : hauteur de moyeu={hh:.2f} m · diamètre du rotor={d:.2f} m", f"   {model_name}: Nabenhöhe={hh:.2f} m · Rotordurchmesser={d:.2f} m"))
                except Exception:
                    pass
            
            if models_ok == n_models:
                msgs.append(_ml(f"✓ {n_models} modelo(s) configurado(s) correctamente.", f"✓ {n_models} model(s) configured correctly.", f"✓ {n_models} modèle(s) configuré(s) correctement.", f"✓ {n_models} Modell(e) korrekt konfiguriert."))
                msgs.append(_ml("✓ Geometría de aerogeneradores usada en el cálculo de sombras:", "✓ Wind-turbine geometry used in the shadow calculation:", "✓ Géométrie d’éolienne utilisée dans le calcul d’ombres :", "✓ Windturbinengeometrie für die Schattenwurfberechnung:"))
                msgs.extend(geometry_lines)
            elif models_ok > 0:
                msgs.append(_ml(f"⚠️ Solo {models_ok}/{n_models} modelos tienen una configuración válida.", f"⚠️ Only {models_ok}/{n_models} models have a valid configuration.", f"⚠️ Seuls {models_ok}/{n_models} modèles ont une configuration valide.", f"⚠️ Nur {models_ok}/{n_models} Modelle haben eine gültige Konfiguration."))
                msgs.append(_ml("   Configura la altura de buje y el diámetro del rotor para todos los modelos.", "   Configure hub height and rotor diameter for all models.", "   Veuillez configurer la hauteur de moyeu et le diamètre du rotor pour tous les modèles.", "   Bitte Nabenhöhe und Rotordurchmesser für alle Modelle konfigurieren."))
                is_valid = False
            else:
                msgs.append(_ml("⚠️ Ningún modelo tiene una configuración válida (altura de buje y diámetro del rotor).", "⚠️ No model has a valid configuration (hub height and rotor diameter).", "⚠️ Aucun modèle n’a une configuration valide (hauteur de moyeu et diamètre du rotor).", "⚠️ Kein Modell hat eine gültige Konfiguration (Nabenhöhe und Rotordurchmesser)."))
                is_valid = False
        
        if is_valid:
            msgs.append("")
            msgs.append(_ml("✅ Configuración válida. Puedes lanzar el cálculo.", "✅ Valid configuration. You can start the calculation.", "✅ Configuration valide. Vous pouvez lancer le calcul.", "✅ Konfiguration gültig. Sie können die Berechnung starten."))
        else:
            msgs.append("")
            msgs.append(_ml("❌ Configuración incompleta. Revisa los puntos marcados.", "❌ Incomplete configuration. Check the highlighted items.", "❌ Configuration incomplète. Vérifiez les éléments signalés.", "❌ Konfiguration unvollständig. Prüfen Sie die markierten Punkte."))
        
        self.txt_status.setText("\n".join(msgs))
        self.btn_calc.setEnabled(is_valid)

    # ========== CALCULATION ==========
    
    def _run_shadow_calculation(self):
        """Run the ombres et scintillement calculation through the controller layer."""
        from .shadow_core.dialog_controller import run_shadow_calculation_from_dialog
        return run_shadow_calculation_from_dialog(self)

    def _run_shadow_point_calculation(self):
        """Run the point-receptor calculation outside the UI class."""
        from .shadow_core.calculation.point_runner import run_shadow_point_calculation_for_page
        return run_shadow_point_calculation_for_page(self)

    def _create_results_layer(self, results: List[ShadowFlickerResult], receiver_layer: QgsVectorLayer,
                              turbines: List[dict], calculator):
        """Create ombres et scintillement output layer."""
        from .shadow_core.qgis_io.layers import create_results_layer_for_page
        return create_results_layer_for_page(self, results, receiver_layer, turbines, calculator)

    def _apply_result_symbology(self, layer: QgsVectorLayer):
        """Apply enhanced symbology to the output layer."""
        from .shadow_core.qgis_io.layers import apply_result_symbology_for_page
        return apply_result_symbology_for_page(self, layer)

    def _apply_labels(self, layer: QgsVectorLayer):
        """Apply labels to the output layer."""
        from .shadow_core.qgis_io.layers import apply_labels_for_page
        return apply_labels_for_page(self, layer)

    def _show_calculation_summary(self, results, turbines, calculator):
        """Show final calculation summary in summary."""
        from .shadow_core.results.summary import show_calculation_summary_for_page
        return show_calculation_summary_for_page(self, results, turbines, calculator)

    def _show_summary_dialog(self, results, turbines, calculator):
        """Show comprehensive summary dialog after calculation."""
        from .shadow_core.results.summary import show_summary_dialog_for_page
        return show_summary_dialog_for_page(self, results, turbines, calculator)

    def _create_shadow_raster(self, turbines, calculator, turbine_layer, dem_layer=None):
        """Create ombres et scintillement raster map using a background QgsTask."""
        from .shadow_core.raster.map import create_shadow_raster_for_page
        return create_shadow_raster_for_page(self, turbines, calculator, turbine_layer, dem_layer)

    def _on_raster_completed(self, task):
        """Callback when raster generation completes successfully."""
        from .shadow_core.raster.map import on_raster_completed_for_page
        return on_raster_completed_for_page(self, task)

    def _regenerate_filtered_raster(self):
        """Regenerate a filtered TIF from the saved NPZ by month/hour."""
        from .shadow_core.raster.map import regenerate_filtered_raster_for_page
        return regenerate_filtered_raster_for_page(self)

    def _on_raster_terminated(self, task=None):
        """Callback when raster generation is cancelled or fails."""
        from .shadow_core.raster.map import on_raster_terminated_for_page
        return on_raster_terminated_for_page(self, task)

    def _apply_raster_symbology(self, layer):
        """Apply heatmap-style symbology to the ombres et scintillement raster."""
        from .shadow_core.raster.map import apply_raster_symbology_for_page
        return apply_raster_symbology_for_page(self, layer)

    # ========== MODEL DETECTION ==========
    
    def _is_model_layer(self, lyr) -> bool:
        """Return True only for Velantis turbine/model source layers.

        Receiver layers may be stored by users inside the same QGIS layer group
        as the Energy/AEP output layers. The shadow module must not classify every
        point layer in that group as a turbine model; otherwise those receiver
        layers disappear from the receiver combo.
        """
        try:
            if not isinstance(lyr, QgsVectorLayer):
                return False
            if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
                return False
            if bool(lyr.customProperty("velantis/shadow_output", False)):
                return False
            if bool(lyr.customProperty("velantis/noise_output", False)):
                return False
            name = (lyr.name() or "").strip()
            if name.startswith("Noise ·") or name.startswith("Shadow ·"):
                return False

            # Velantis turbine layers created/imported by any module carry these properties.
            model_name = (lyr.customProperty("velantis/model_name", "") or "").strip()
            coords_csv = (lyr.customProperty("velantis/coords_csv", "") or "").strip()
            if model_name or coords_csv:
                return True

            # Backward compatibility for older layers generated from CSV.
            if name.endswith(" (CSV)"):
                return True
        except Exception:
            return False
        return False

    def _iter_group_layers_recursive(self, node):
        """Yield QGIS layers below a layer-tree node, including nested groups."""
        try:
            children = node.children()
        except Exception:
            children = []
        for child in children:
            lyr = None
            try:
                lyr = child.layer()
            except Exception:
                lyr = None
            if lyr is not None:
                yield lyr
            else:
                yield from self._iter_group_layers_recursive(child)

    def _iter_model_layers(self, prj: QgsProject) -> List[QgsVectorLayer]:
        """Find turbine/model layers imported by any VelantisWind module."""
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

    def _detect_models(self, prj: QgsProject) -> List[Dict]:
        """Detect turbine model layers in the project.

        Only actual Velantis turbine/model layers are returned. Plain point
        receiver layers remain available in the receiver combo even if the user
        has placed them inside a Velantis layer group.
        """
        models: List[Dict] = []
        for lyr in self._iter_model_layers(prj):
            try:
                model_name = (lyr.customProperty("velantis/model_name", "") or "").strip()
            except Exception:
                model_name = ""
            try:
                hh = lyr.customProperty("velantis/hub_height_m", None)
                hh = float(hh) if hh is not None else None
            except Exception:
                hh = None
            try:
                diam = lyr.customProperty("velantis/diameter_m", None)
                diam = float(diam) if diam is not None else None
            except Exception:
                diam = None
            models.append({
                'layer_id': lyr.id(),
                'name': model_name or lyr.name(),
                'n_turbines': lyr.featureCount(),
                'hub_height': hh,
                'diameter': diam,
            })
        return models
