# -*- coding: utf-8 -*-
"""spacing_core/i18n_spacing.py — Traducciones del módulo de envolventes.

El español es el idioma fuente del plugin (ver i18n.py); aquí se registran
los mapas ES->EN/FR/DE de las cadenas visibles del panel, capa, tooltips y
mensajes de estado del módulo de envolventes de separación.
"""

from __future__ import annotations

try:
    from ..i18n import LANG_DE, LANG_EN, LANG_FR, register_language
except Exception:  # ejecución fuera del paquete (tests)
    try:
        from i18n import LANG_DE, LANG_EN, LANG_FR, register_language  # type: ignore
    except Exception:
        register_language = None  # type: ignore

_TO_EN = {
    "Envolventes de separación…": "Spacing envelopes…",
    "Cerrar": "Close",
    "Configura la separación mínima entre turbinas. Las envolventes se "
    "dibujan en una capa independiente por cada modelo de turbina y se "
    "validan también entre modelos al editar en el Mapa interactivo.":
        "Configure the minimum inter-turbine separation. Envelopes are drawn "
        "in a separate layer for each turbine model and are also validated "
        "between models while editing in Interactive Map mode.",
    "No se pudo inicializar el módulo de envolventes (spacing_core).":
        "Could not initialize the spacing envelope module (spacing_core).",
    "Tipo:": "Type:",
    "Elíptica": "Elliptical",
    "Circular": "Circular",
    "Validación:": "Validation:",
    "Solo visualización": "Visualization only",
    "Avisar si hay conflicto": "Warn on conflict",
    "Bloquear inserción si hay conflicto": "Block insertion on conflict",
    "Exportar envolventes…": "Export envelopes…",
    "Exportar envolventes de separación": "Export spacing envelopes",
    "No hay envolventes que exportar.": "No envelopes to export.",
    "Envolventes exportadas:": "Envelopes exported:",
    "No se pudo exportar:": "Could not export:",
    "Capa exportada a": "Layer exported to",
    "La turbina invade la envolvente de otra turbina · inserción bloqueada.":
        "The turbine intrudes into another turbine's envelope · insertion blocked.",
    "Envolvente de separación": "Spacing envelope",
    "Envolventes de separación": "Spacing envelopes",
    "Activar envolventes de separación": "Enable spacing envelopes",
    "Longitudinal:": "Downwind:",
    "Transversal:": "Crosswind:",
    "Orientación:": "Orientation:",
    "Ángulo:": "Angle:",
    "Automática · sector más energético": "Automatic · most energetic sector",
    "Manual · ángulo": "Manual · angle",
    "Manual · definir en pantalla": "Manual · define on screen",
    "Definir elipse en pantalla": "Define ellipse on screen",
    "Restablecer": "Reset",
    "OK": "OK",
    "Cerca del límite": "Near the limit",
    "Conflicto de spacing": "Spacing conflict",
    "No hay capa de turbinas activa.": "No active turbine layer.",
    "No hay capa de turbinas activa para dibujar.": "No active turbine layer to draw on.",
    "No hay turbina cerca del clic · pincha sobre un aerogenerador":
        "No turbine near the click · click on a wind turbine",
    "Clic sobre una turbina para definir su envolvente · Esc cancela":
        "Click a turbine to define its envelope · Esc cancels",
    "Overrides eliminados · usando la plantilla global.":
        "Overrides cleared · using the global template.",
    "sin conflictos": "no conflicts",
    "cerca del límite": "near the limit",
    "sector más energético": "most energetic sector",
    "conflicto(s) de spacing": "spacing conflict(s)",
    "envolvente(s)": "envelope(s)",
    "Eje mayor": "Major axis",
    "Eje menor": "Minor axis",
    "Clic para confirmar": "Click to confirm",
    "usando ángulo manual": "using manual angle",
    "No se pudo determinar automáticamente el sector más energético":
        "Could not automatically determine the most energetic sector",
    "La disposición incumple la separación mínima en":
        "The layout violates the minimum spacing at",
    "No hay capas de turbinas asociadas a los modelos.":
        "No turbine layers are associated with the models.",
    "La disposición multimodelo incumple la separación mínima en":
        "The multi-model layout violates the minimum spacing at",
    "Overrides del modelo": "Overrides for model",
    "eliminados · usando la plantilla global.": "cleared · using the global template.",
    "Exportar envolventes de separación por modelo":
        "Export spacing envelopes by model",
    "capa(s) de modelo exportadas:": "model layer(s) exported:",
    "Se exportaron": "Exported",
    "capas de modelo a": "model layers to",
    "La turbina invade la envolvente de una turbina del modelo":
        "The turbine intrudes into the envelope of a turbine from model",
    "inserción bloqueada.": "insertion blocked.",
    "modelo": "model",
    "modelos": "models",
    "turbina(s).": "turbine(s).",
}

_TO_FR = {
    "Envolventes de separación…": "Enveloppes d'espacement…",
    "Cerrar": "Fermer",
    "Configura la separación mínima entre turbinas. Las envolventes se "
    "dibujan en una capa independiente por cada modelo de turbina y se "
    "validan también entre modelos al editar en el Mapa interactivo.":
        "Configurez l'espacement minimal entre éoliennes. Les enveloppes sont "
        "dessinées dans une couche distincte pour chaque modèle et sont aussi "
        "validées entre modèles en mode Carte interactive.",
    "No se pudo inicializar el módulo de envolventes (spacing_core).":
        "Impossible d'initialiser le module d'enveloppes (spacing_core).",
    "Tipo:": "Type :",
    "Elíptica": "Elliptique",
    "Circular": "Circulaire",
    "Validación:": "Validation :",
    "Solo visualización": "Visualisation seule",
    "Avisar si hay conflicto": "Avertir en cas de conflit",
    "Bloquear inserción si hay conflicto": "Bloquer l'insertion en cas de conflit",
    "Exportar envolventes…": "Exporter les enveloppes…",
    "Exportar envolventes de separación": "Exporter les enveloppes d'espacement",
    "No hay envolventes que exportar.": "Aucune enveloppe à exporter.",
    "Envolventes exportadas:": "Enveloppes exportées :",
    "No se pudo exportar:": "Échec de l'export :",
    "Capa exportada a": "Couche exportée vers",
    "La turbina invade la envolvente de otra turbina · inserción bloqueada.":
        "L'éolienne empiète sur l'enveloppe d'une autre éolienne · insertion bloquée.",
    "Envolvente de separación": "Enveloppe d'espacement",
    "Envolventes de separación": "Enveloppes d'espacement",
    "Activar envolventes de separación": "Activer les enveloppes d'espacement",
    "Longitudinal:": "Longitudinal :",
    "Transversal:": "Transversal :",
    "Orientación:": "Orientation :",
    "Ángulo:": "Angle :",
    "Automática · sector más energético": "Automatique · secteur le plus énergétique",
    "Manual · ángulo": "Manuel · angle",
    "Manual · definir en pantalla": "Manuel · définir à l'écran",
    "Definir elipse en pantalla": "Définir l'ellipse à l'écran",
    "Restablecer": "Réinitialiser",
    "Cerca del límite": "Proche de la limite",
    "Conflicto de spacing": "Conflit d'espacement",
    "No hay capa de turbinas activa.": "Aucune couche d'éoliennes active.",
    "No hay capa de turbinas activa para dibujar.":
        "Aucune couche d'éoliennes active pour dessiner.",
    "No hay turbina cerca del clic · pincha sobre un aerogenerador":
        "Aucune éolienne près du clic · cliquez sur une éolienne",
    "Clic sobre una turbina para definir su envolvente · Esc cancela":
        "Cliquez sur une éolienne pour définir son enveloppe · Échap annule",
    "Overrides eliminados · usando la plantilla global.":
        "Personnalisations supprimées · modèle global utilisé.",
    "sin conflictos": "aucun conflit",
    "cerca del límite": "proche de la limite",
    "sector más energético": "secteur le plus énergétique",
    "conflicto(s) de spacing": "conflit(s) d'espacement",
    "envolvente(s)": "enveloppe(s)",
    "Eje mayor": "Grand axe",
    "Eje menor": "Petit axe",
    "Clic para confirmar": "Cliquez pour confirmer",
    "usando ángulo manual": "angle manuel utilisé",
    "No se pudo determinar automáticamente el sector más energético":
        "Impossible de déterminer automatiquement le secteur le plus énergétique",
    "La disposición incumple la separación mínima en":
        "La disposition ne respecte pas l'espacement minimal pour",
    "No hay capas de turbinas asociadas a los modelos.":
        "Aucune couche d'éoliennes n'est associée aux modèles.",
    "La disposición multimodelo incumple la separación mínima en":
        "La disposition multi-modèle ne respecte pas l'espacement minimal pour",
    "Overrides del modelo": "Personnalisations du modèle",
    "eliminados · usando la plantilla global.": "supprimées · modèle global utilisé.",
    "Exportar envolventes de separación por modelo":
        "Exporter les enveloppes d'espacement par modèle",
    "capa(s) de modelo exportadas:": "couche(s) de modèle exportée(s) :",
    "Se exportaron": "Export de",
    "capas de modelo a": "couches de modèle vers",
    "La turbina invade la envolvente de una turbina del modelo":
        "L'éolienne empiète sur l'enveloppe d'une éolienne du modèle",
    "inserción bloqueada.": "insertion bloquée.",
    "modelo": "modèle",
    "modelos": "modèles",
    "turbina(s).": "éolienne(s).",
}

_TO_DE = {
    "Envolventes de separación…": "Abstandshüllen…",
    "Cerrar": "Schließen",
    "Configura la separación mínima entre turbinas. Las envolventes se "
    "dibujan en una capa independiente por cada modelo de turbina y se "
    "validan también entre modelos al editar en el Mapa interactivo.":
        "Konfigurieren Sie den Mindestabstand zwischen Turbinen. Für jedes "
        "Turbinenmodell wird eine eigene Hüllen-Ebene erzeugt; die Validierung "
        "erfolgt auch modellübergreifend im interaktiven Kartenmodus.",
    "No se pudo inicializar el módulo de envolventes (spacing_core).":
        "Das Abstandshüllen-Modul (spacing_core) konnte nicht initialisiert werden.",
    "Tipo:": "Typ:",
    "Elíptica": "Elliptisch",
    "Circular": "Kreisförmig",
    "Validación:": "Validierung:",
    "Solo visualización": "Nur Visualisierung",
    "Avisar si hay conflicto": "Bei Konflikt warnen",
    "Bloquear inserción si hay conflicto": "Einfügen bei Konflikt blockieren",
    "Exportar envolventes…": "Hüllen exportieren…",
    "Exportar envolventes de separación": "Abstandshüllen exportieren",
    "No hay envolventes que exportar.": "Keine Hüllen zum Exportieren.",
    "Envolventes exportadas:": "Hüllen exportiert:",
    "No se pudo exportar:": "Export fehlgeschlagen:",
    "Capa exportada a": "Ebene exportiert nach",
    "La turbina invade la envolvente de otra turbina · inserción bloqueada.":
        "Die Turbine ragt in die Hülle einer anderen Turbine · Einfügen blockiert.",
    "Envolvente de separación": "Abstandshülle",
    "Envolventes de separación": "Abstandshüllen",
    "Activar envolventes de separación": "Abstandshüllen aktivieren",
    "Longitudinal:": "Längsrichtung:",
    "Transversal:": "Querrichtung:",
    "Orientación:": "Ausrichtung:",
    "Ángulo:": "Winkel:",
    "Automática · sector más energético": "Automatisch · energiereichster Sektor",
    "Manual · ángulo": "Manuell · Winkel",
    "Manual · definir en pantalla": "Manuell · am Bildschirm definieren",
    "Definir elipse en pantalla": "Ellipse am Bildschirm definieren",
    "Restablecer": "Zurücksetzen",
    "Cerca del límite": "Nahe am Grenzwert",
    "Conflicto de spacing": "Abstandskonflikt",
    "No hay capa de turbinas activa.": "Keine aktive Turbinen-Ebene.",
    "No hay capa de turbinas activa para dibujar.":
        "Keine aktive Turbinen-Ebene zum Zeichnen.",
    "No hay turbina cerca del clic · pincha sobre un aerogenerador":
        "Keine Turbine in Klicknähe · auf eine Windenergieanlage klicken",
    "Clic sobre una turbina para definir su envolvente · Esc cancela":
        "Turbine anklicken, um ihre Hülle zu definieren · Esc bricht ab",
    "Overrides eliminados · usando la plantilla global.":
        "Überschreibungen gelöscht · globale Vorlage wird verwendet.",
    "sin conflictos": "keine Konflikte",
    "cerca del límite": "nahe am Grenzwert",
    "sector más energético": "energiereichster Sektor",
    "conflicto(s) de spacing": "Abstandskonflikt(e)",
    "envolvente(s)": "Hülle(n)",
    "Eje mayor": "Hauptachse",
    "Eje menor": "Nebenachse",
    "Clic para confirmar": "Klicken zum Bestätigen",
    "usando ángulo manual": "manueller Winkel wird verwendet",
    "No se pudo determinar automáticamente el sector más energético":
        "Der energiereichste Sektor konnte nicht automatisch bestimmt werden",
    "La disposición incumple la separación mínima en":
        "Das Layout verletzt den Mindestabstand bei",
    "No hay capas de turbinas asociadas a los modelos.":
        "Den Modellen sind keine Turbinen-Ebenen zugeordnet.",
    "La disposición multimodelo incumple la separación mínima en":
        "Das Mehrmodell-Layout verletzt den Mindestabstand bei",
    "Overrides del modelo": "Überschreibungen des Modells",
    "eliminados · usando la plantilla global.": "gelöscht · globale Vorlage wird verwendet.",
    "Exportar envolventes de separación por modelo":
        "Abstandshüllen nach Modell exportieren",
    "capa(s) de modelo exportadas:": "Modell-Ebene(n) exportiert:",
    "Se exportaron": "Exportiert wurden",
    "capas de modelo a": "Modell-Ebenen nach",
    "La turbina invade la envolvente de una turbina del modelo":
        "Die Turbine ragt in die Hülle einer Turbine des Modells",
    "inserción bloqueada.": "Einfügen blockiert.",
    "modelo": "Modell",
    "modelos": "Modelle",
    "turbina(s).": "Turbine(n).",
}


# Per-model spacing dimensions
_TO_EN.update({
    "Separación": "Spacing",
    "Dibuja una elipse semitransparente alrededor de cada turbina representando la separación mínima entre centros. Rojo = solape (conflicto de spacing); naranja = cerca del límite.":
        "Draws a semi-transparent ellipse around each turbine representing the minimum centre-to-centre spacing. Red = overlap (spacing conflict); orange = near the limit.",
    "Elíptica: separación longitudinal/transversal distintas, orientada al viento. Circular: modo básico, misma separación (la longitudinal) en todas las direcciones; la orientación no aplica.":
        "Elliptical: different downwind/crosswind spacing, aligned with the wind. Circular: basic mode, using the same spacing (the downwind value) in every direction; orientation does not apply.",
    "Separación longitudinal mínima entre centros, en diámetros de rotor. Define el eje mayor de la elipse (semieje = valor/2).":
        "Minimum downwind centre-to-centre spacing, in rotor diameters. Defines the ellipse major axis (semi-axis = value/2).",
    "Separación transversal mínima entre centros, en diámetros de rotor. Define el eje menor de la elipse (semieje = valor/2).":
        "Minimum crosswind centre-to-centre spacing, in rotor diameters. Defines the ellipse minor axis (semi-axis = value/2).",
    "Automática: la elipse se alinea con el sector más energético del WRG (argmax de f·A³·Γ(1+3/k) por sector). Manual · ángulo: azimut fijo desde el Norte, horario. Manual · definir en pantalla: dibuja centro, eje mayor y eje menor sobre el mapa turbina a turbina.":
        "Automatic: aligns the ellipse with the most energetic WRG sector (sector-wise argmax of f·A³·Γ(1+3/k)). Manual · angle: fixed clockwise azimuth from North. Manual · define on screen: draw the centre, major axis and minor axis on the map for each turbine.",
    "Azimut del eje mayor: grados desde el Norte, en sentido horario. El eje es bidireccional (α y α+180° son equivalentes). También es el fallback si no se puede calcular el sector más energético.":
        "Major-axis azimuth: clockwise degrees from North. The axis is bidirectional (α and α+180° are equivalent). It is also used as the fallback when the most energetic sector cannot be calculated.",
    "Solo visualización: los conflictos solo cambian el color. Avisar: además, aviso en la barra de mensajes de QGIS. Bloquear: además, no se permite insertar una turbina cuya envolvente solaparía con otra.":
        "Visualization only: conflicts only change colour. Warn: also show a QGIS message-bar warning. Block: also prevent insertion of a turbine whose envelope would overlap another one.",
    "Flujo de 3 clics: (1) clic sobre una turbina; (2) arrastra para orientar y fijar el eje mayor; (3) arrastra para fijar el eje menor. Ctrl = snap angular a 5°/sectores · Shift = snap a 0.5·D · Esc/clic derecho = paso atrás.":
        "Three-click workflow: (1) click a turbine; (2) drag to orient and set the major axis; (3) drag to set the minor axis. Ctrl = snap to 5°/sectors · Shift = snap to 0.5·D · Esc/right-click = step back.",
    "Borra las elipses definidas en pantalla (overrides por turbina) y vuelve a la plantilla global del panel.":
        "Clears the ellipses defined on screen (per-turbine overrides) and returns to the panel's global template.",
    "Guarda todas las capas de envolventes, una por modelo de turbina, en un GeoPackage con una tabla independiente por modelo.":
        "Saves all envelope layers, one per turbine model, to a GeoPackage with a separate table for each model.",
    "Estos valores son la plantilla global. Cada modelo puede guardar sus propias dimensiones longitudinal y transversal al definir la turbina.":
        "These values are the global template. Each turbine model can store its own downwind and crosswind dimensions when the turbine is defined.",
    "dimensiones:": "dimensions:",
    "Separación longitudinal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje mayor de sus envolventes.":
        "Initial downwind spacing for this model, expressed in rotor diameters. It is stored with the model and controls the major axis of its envelopes.",
    "Separación transversal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje menor de sus envolventes.":
        "Initial crosswind spacing for this model, expressed in rotor diameters. It is stored with the model and controls the minor axis of its envelopes.",
})
_TO_FR.update({
    "Separación": "Espacement",
    "Dibuja una elipse semitransparente alrededor de cada turbina representando la separación mínima entre centros. Rojo = solape (conflicto de spacing); naranja = cerca del límite.":
        "Dessine une ellipse semi-transparente autour de chaque éolienne représentant l’espacement minimal entre centres. Rouge = chevauchement (conflit d’espacement) ; orange = proche de la limite.",
    "Elíptica: separación longitudinal/transversal distintas, orientada al viento. Circular: modo básico, misma separación (la longitudinal) en todas las direcciones; la orientación no aplica.":
        "Elliptique : espacements longitudinal et transversal différents, orientés selon le vent. Circulaire : mode de base, même espacement (la valeur longitudinale) dans toutes les directions ; l’orientation ne s’applique pas.",
    "Separación longitudinal mínima entre centros, en diámetros de rotor. Define el eje mayor de la elipse (semieje = valor/2).":
        "Espacement longitudinal minimal entre centres, en diamètres de rotor. Définit le grand axe de l’ellipse (demi-axe = valeur/2).",
    "Separación transversal mínima entre centros, en diámetros de rotor. Define el eje menor de la elipse (semieje = valor/2).":
        "Espacement transversal minimal entre centres, en diamètres de rotor. Définit le petit axe de l’ellipse (demi-axe = valeur/2).",
    "Automática: la elipse se alinea con el sector más energético del WRG (argmax de f·A³·Γ(1+3/k) por sector). Manual · ángulo: azimut fijo desde el Norte, horario. Manual · definir en pantalla: dibuja centro, eje mayor y eje menor sobre el mapa turbina a turbina.":
        "Automatique : aligne l’ellipse sur le secteur WRG le plus énergétique (argmax par secteur de f·A³·Γ(1+3/k)). Manuel · angle : azimut fixe depuis le Nord, dans le sens horaire. Manuel · définir à l’écran : dessinez le centre, le grand axe et le petit axe sur la carte pour chaque éolienne.",
    "Azimut del eje mayor: grados desde el Norte, en sentido horario. El eje es bidireccional (α y α+180° son equivalentes). También es el fallback si no se puede calcular el sector más energético.":
        "Azimut du grand axe : degrés depuis le Nord, dans le sens horaire. L’axe est bidirectionnel (α et α+180° sont équivalents). Il sert aussi de valeur de repli si le secteur le plus énergétique ne peut pas être calculé.",
    "Solo visualización: los conflictos solo cambian el color. Avisar: además, aviso en la barra de mensajes de QGIS. Bloquear: además, no se permite insertar una turbina cuya envolvente solaparía con otra.":
        "Visualisation seule : les conflits changent uniquement la couleur. Avertir : affiche aussi un avertissement dans la barre de messages de QGIS. Bloquer : empêche aussi l’insertion d’une éolienne dont l’enveloppe chevaucherait une autre.",
    "Flujo de 3 clics: (1) clic sobre una turbina; (2) arrastra para orientar y fijar el eje mayor; (3) arrastra para fijar el eje menor. Ctrl = snap angular a 5°/sectores · Shift = snap a 0.5·D · Esc/clic derecho = paso atrás.":
        "Procédure en 3 clics : (1) cliquez sur une éolienne ; (2) faites glisser pour orienter et fixer le grand axe ; (3) faites glisser pour fixer le petit axe. Ctrl = accrochage à 5°/aux secteurs · Maj = accrochage à 0,5·D · Échap/clic droit = étape précédente.",
    "Borra las elipses definidas en pantalla (overrides por turbina) y vuelve a la plantilla global del panel.":
        "Efface les ellipses définies à l’écran (personnalisations par éolienne) et revient au gabarit global du panneau.",
    "Guarda todas las capas de envolventes, una por modelo de turbina, en un GeoPackage con una tabla independiente por modelo.":
        "Enregistre toutes les couches d’enveloppes, une par modèle d’éolienne, dans un GeoPackage avec une table distincte par modèle.",
    "Estos valores son la plantilla global. Cada modelo puede guardar sus propias dimensiones longitudinal y transversal al definir la turbina.":
        "Ces valeurs constituent le gabarit global. Chaque modèle peut enregistrer ses propres dimensions longitudinale et transversale lors de la définition de l’éolienne.",
    "dimensiones:": "dimensions :",
    "Separación longitudinal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje mayor de sus envolventes.":
        "Espacement longitudinal initial de ce modèle, exprimé en diamètres de rotor. Il est enregistré avec le modèle et contrôle le grand axe de ses enveloppes.",
    "Separación transversal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje menor de sus envolventes.":
        "Espacement transversal initial de ce modèle, exprimé en diamètres de rotor. Il est enregistré avec le modèle et contrôle le petit axe de ses enveloppes.",
})
_TO_DE.update({
    "Separación": "Abstand",
    "Dibuja una elipse semitransparente alrededor de cada turbina representando la separación mínima entre centros. Rojo = solape (conflicto de spacing); naranja = cerca del límite.":
        "Zeichnet um jede Turbine eine halbtransparente Ellipse, die den Mindestabstand zwischen den Mittelpunkten darstellt. Rot = Überlappung (Abstandskonflikt); Orange = nahe am Grenzwert.",
    "Elíptica: separación longitudinal/transversal distintas, orientada al viento. Circular: modo básico, misma separación (la longitudinal) en todas las direcciones; la orientación no aplica.":
        "Elliptisch: unterschiedliche Längs- und Querabstände, am Wind ausgerichtet. Kreisförmig: Basismodus mit demselben Abstand (Längswert) in alle Richtungen; die Ausrichtung ist nicht relevant.",
    "Separación longitudinal mínima entre centros, en diámetros de rotor. Define el eje mayor de la elipse (semieje = valor/2).":
        "Minimaler Längsabstand zwischen den Mittelpunkten in Rotordurchmessern. Definiert die Hauptachse der Ellipse (Halbachse = Wert/2).",
    "Separación transversal mínima entre centros, en diámetros de rotor. Define el eje menor de la elipse (semieje = valor/2).":
        "Minimaler Querabstand zwischen den Mittelpunkten in Rotordurchmessern. Definiert die Nebenachse der Ellipse (Halbachse = Wert/2).",
    "Automática: la elipse se alinea con el sector más energético del WRG (argmax de f·A³·Γ(1+3/k) por sector). Manual · ángulo: azimut fijo desde el Norte, horario. Manual · definir en pantalla: dibuja centro, eje mayor y eje menor sobre el mapa turbina a turbina.":
        "Automatisch: richtet die Ellipse am energiereichsten WRG-Sektor aus (sektorweises Argmax von f·A³·Γ(1+3/k)). Manuell · Winkel: fester Azimut ab Norden im Uhrzeigersinn. Manuell · am Bildschirm definieren: Mittelpunkt, Haupt- und Nebenachse für jede Turbine auf der Karte zeichnen.",
    "Azimut del eje mayor: grados desde el Norte, en sentido horario. El eje es bidireccional (α y α+180° son equivalentes). También es el fallback si no se puede calcular el sector más energético.":
        "Azimut der Hauptachse: Grad ab Norden im Uhrzeigersinn. Die Achse ist bidirektional (α und α+180° sind gleichwertig). Der Wert dient außerdem als Fallback, wenn der energiereichste Sektor nicht berechnet werden kann.",
    "Solo visualización: los conflictos solo cambian el color. Avisar: además, aviso en la barra de mensajes de QGIS. Bloquear: además, no se permite insertar una turbina cuya envolvente solaparía con otra.":
        "Nur Visualisierung: Konflikte ändern lediglich die Farbe. Warnen: zeigt zusätzlich eine Warnung in der QGIS-Meldungsleiste. Blockieren: verhindert zusätzlich das Einfügen einer Turbine, deren Hülle eine andere überlappen würde.",
    "Flujo de 3 clics: (1) clic sobre una turbina; (2) arrastra para orientar y fijar el eje mayor; (3) arrastra para fijar el eje menor. Ctrl = snap angular a 5°/sectores · Shift = snap a 0.5·D · Esc/clic derecho = paso atrás.":
        "Drei-Klick-Ablauf: (1) Turbine anklicken; (2) ziehen, um die Hauptachse auszurichten und festzulegen; (3) ziehen, um die Nebenachse festzulegen. Strg = Einrasten auf 5°/Sektoren · Umschalt = Einrasten auf 0,5·D · Esc/Rechtsklick = einen Schritt zurück.",
    "Borra las elipses definidas en pantalla (overrides por turbina) y vuelve a la plantilla global del panel.":
        "Löscht die am Bildschirm definierten Ellipsen (turbinenbezogene Überschreibungen) und kehrt zur globalen Vorlage des Panels zurück.",
    "Guarda todas las capas de envolventes, una por modelo de turbina, en un GeoPackage con una tabla independiente por modelo.":
        "Speichert alle Hüllen-Ebenen, jeweils eine pro Turbinenmodell, in einem GeoPackage mit einer separaten Tabelle pro Modell.",
    "Estos valores son la plantilla global. Cada modelo puede guardar sus propias dimensiones longitudinal y transversal al definir la turbina.":
        "Diese Werte bilden die globale Vorlage. Jedes Turbinenmodell kann beim Definieren eigene Längs- und Querabstände speichern.",
    "dimensiones:": "Abmessungen:",
    "Separación longitudinal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje mayor de sus envolventes.":
        "Anfänglicher Längsabstand dieses Modells in Rotordurchmessern. Er wird mit dem Modell gespeichert und steuert die Hauptachse seiner Hüllen.",
    "Separación transversal inicial de este modelo, expresada en diámetros de rotor. Se guarda con el modelo y controla el eje menor de sus envolventes.":
        "Anfänglicher Querabstand dieses Modells in Rotordurchmessern. Er wird mit dem Modell gespeichert und steuert die Nebenachse seiner Hüllen.",
})


# --- Selector y edición de envolventes por modelo ---
_TO_EN.update({
    "Modelo de aerogenerador:": "Wind turbine model:",
    "No hay modelos cargados": "No models loaded",
    "No hay modelos cargados.": "No models loaded.",
    "Actualizar la lista de modelos de turbina del proyecto.": "Refresh the list of turbine models in the project.",
    "Selecciona la capa/modelo cuyas dimensiones y orientación quieres editar.": "Select the layer/model whose dimensions and orientation you want to edit.",
    "Modelo seleccionado.": "Selected model.",
    "Dibuja una elipse semitransparente alrededor de cada turbina. Cada modelo conserva su propia geometría. Rojo = conflicto; naranja = cerca del límite.": "Draws a semi-transparent ellipse around each turbine. Each model keeps its own geometry. Red = conflict; orange = near the limit.",
    "Separación longitudinal mínima del modelo seleccionado, en diámetros de rotor.": "Minimum downwind spacing for the selected model, in rotor diameters.",
    "Separación transversal mínima del modelo seleccionado, en diámetros de rotor.": "Minimum crosswind spacing for the selected model, in rotor diameters.",
    "La orientación se guarda por modelo. En modo automático la elipse se alinea con el sector más energético del recurso; el ángulo actúa como respaldo.": "Orientation is stored per model. In automatic mode the ellipse aligns with the resource's most energetic sector; the angle is used as a fallback.",
    "Azimut del eje mayor desde el Norte, en sentido horario. Se guarda de forma independiente para el modelo seleccionado.": "Major-axis azimuth clockwise from North. It is stored independently for the selected model.",
    "La validación se aplica conjuntamente entre todos los modelos del proyecto.": "Validation is applied jointly across all models in the project.",
    "Define una excepción para una turbina del modelo seleccionado mediante tres clics.": "Defines an exception for a turbine of the selected model using three clicks.",
    "Elimina las excepciones dibujadas de la capa/modelo seleccionado.": "Removes the drawn exceptions from the selected layer/model.",
    "Exporta todas las capas de envolventes a un GeoPackage, una tabla por modelo.": "Exports all envelope layers to a GeoPackage, one table per model.",
    "se utilizará el ángulo de respaldo guardado en cada modelo.": "the fallback angle stored in each model will be used.",
    "Excepción guardada para la turbina": "Exception saved for turbine",
    "del modelo": "of model",
    "Excepción de envolvente guardada.": "Envelope exception saved.",
    "Excepciones del modelo": "Model exceptions",
    "eliminadas · usando su plantilla de modelo.": "cleared · using its model template.",
    "dimensiones:": "dimensions:",
    "sin capa": "no layer",
    "Modelo definido sin capa de turbinas. Carga un CSV o genera la capa de puntos para crear sus elipses.":
        "Model defined without a turbine layer. Load a CSV or generate the point layer to create its ellipses.",
    "El modelo seleccionado todavía no tiene una capa de turbinas para dibujar.":
        "The selected model does not yet have a turbine layer to draw on.",
    "No hay modelos de aerogenerador definidos.": "No wind turbine models are defined.",
})
_TO_FR.update({
    "Modelo de aerogenerador:": "Modèle d’éolienne :",
    "No hay modelos cargados": "Aucun modèle chargé",
    "No hay modelos cargados.": "Aucun modèle chargé.",
    "Actualizar la lista de modelos de turbina del proyecto.": "Actualiser la liste des modèles d’éoliennes du projet.",
    "Selecciona la capa/modelo cuyas dimensiones y orientación quieres editar.": "Sélectionnez la couche/le modèle dont vous souhaitez modifier les dimensions et l’orientation.",
    "Modelo seleccionado.": "Modèle sélectionné.",
    "Dibuja una elipse semitransparente alrededor de cada turbina. Cada modelo conserva su propia geometría. Rojo = conflicto; naranja = cerca del límite.": "Dessine une ellipse semi-transparente autour de chaque éolienne. Chaque modèle conserve sa propre géométrie. Rouge = conflit ; orange = proche de la limite.",
    "Separación longitudinal mínima del modelo seleccionado, en diámetros de rotor.": "Espacement longitudinal minimal du modèle sélectionné, en diamètres de rotor.",
    "Separación transversal mínima del modelo seleccionado, en diámetros de rotor.": "Espacement transversal minimal du modèle sélectionné, en diamètres de rotor.",
    "La orientación se guarda por modelo. En modo automático la elipse se alinea con el sector más energético del recurso; el ángulo actúa como respaldo.": "L’orientation est enregistrée par modèle. En mode automatique, l’ellipse s’aligne sur le secteur le plus énergétique de la ressource ; l’angle sert de valeur de repli.",
    "Azimut del eje mayor desde el Norte, en sentido horario. Se guarda de forma independiente para el modelo seleccionado.": "Azimut du grand axe depuis le Nord, dans le sens horaire. Il est enregistré séparément pour le modèle sélectionné.",
    "La validación se aplica conjuntamente entre todos los modelos del proyecto.": "La validation est appliquée conjointement à tous les modèles du projet.",
    "Define una excepción para una turbina del modelo seleccionado mediante tres clics.": "Définit une exception pour une éolienne du modèle sélectionné en trois clics.",
    "Elimina las excepciones dibujadas de la capa/modelo seleccionado.": "Supprime les exceptions dessinées de la couche/du modèle sélectionné.",
    "Exporta todas las capas de envolventes a un GeoPackage, una tabla por modelo.": "Exporte toutes les couches d’enveloppes vers un GeoPackage, une table par modèle.",
    "se utilizará el ángulo de respaldo guardado en cada modelo.": "l’angle de repli enregistré dans chaque modèle sera utilisé.",
    "Excepción guardada para la turbina": "Exception enregistrée pour l’éolienne",
    "del modelo": "du modèle",
    "Excepción de envolvente guardada.": "Exception d’enveloppe enregistrée.",
    "Excepciones del modelo": "Exceptions du modèle",
    "eliminadas · usando su plantilla de modelo.": "supprimées · utilisation de son gabarit de modèle.",
    "dimensiones:": "dimensions :",
    "sin capa": "sans couche",
    "Modelo definido sin capa de turbinas. Carga un CSV o genera la capa de puntos para crear sus elipses.":
        "Modèle défini sans couche d’éoliennes. Chargez un CSV ou générez la couche de points pour créer ses ellipses.",
    "El modelo seleccionado todavía no tiene una capa de turbinas para dibujar.":
        "Le modèle sélectionné ne possède pas encore de couche d’éoliennes sur laquelle dessiner.",
    "No hay modelos de aerogenerador definidos.": "Aucun modèle d’éolienne n’est défini.",
})
_TO_DE.update({
    "Modelo de aerogenerador:": "Windturbinenmodell:",
    "No hay modelos cargados": "Keine Modelle geladen",
    "No hay modelos cargados.": "Keine Modelle geladen.",
    "Actualizar la lista de modelos de turbina del proyecto.": "Liste der Turbinenmodelle im Projekt aktualisieren.",
    "Selecciona la capa/modelo cuyas dimensiones y orientación quieres editar.": "Wählen Sie die Ebene/das Modell aus, dessen Abmessungen und Ausrichtung Sie bearbeiten möchten.",
    "Modelo seleccionado.": "Ausgewähltes Modell.",
    "Dibuja una elipse semitransparente alrededor de cada turbina. Cada modelo conserva su propia geometría. Rojo = conflicto; naranja = cerca del límite.": "Zeichnet eine halbtransparente Ellipse um jede Turbine. Jedes Modell behält seine eigene Geometrie. Rot = Konflikt; Orange = nahe am Grenzwert.",
    "Separación longitudinal mínima del modelo seleccionado, en diámetros de rotor.": "Minimaler Längsabstand des ausgewählten Modells in Rotordurchmessern.",
    "Separación transversal mínima del modelo seleccionado, en diámetros de rotor.": "Minimaler Querabstand des ausgewählten Modells in Rotordurchmessern.",
    "La orientación se guarda por modelo. En modo automático la elipse se alinea con el sector más energético del recurso; el ángulo actúa como respaldo.": "Die Ausrichtung wird je Modell gespeichert. Im Automatikmodus richtet sich die Ellipse am energiereichsten Ressourcensektor aus; der Winkel dient als Fallback.",
    "Azimut del eje mayor desde el Norte, en sentido horario. Se guarda de forma independiente para el modelo seleccionado.": "Azimut der Hauptachse ab Norden im Uhrzeigersinn. Er wird separat für das ausgewählte Modell gespeichert.",
    "La validación se aplica conjuntamente entre todos los modelos del proyecto.": "Die Validierung wird gemeinsam für alle Modelle im Projekt angewendet.",
    "Define una excepción para una turbina del modelo seleccionado mediante tres clics.": "Definiert mit drei Klicks eine Ausnahme für eine Turbine des ausgewählten Modells.",
    "Elimina las excepciones dibujadas de la capa/modelo seleccionado.": "Entfernt die gezeichneten Ausnahmen aus der ausgewählten Ebene/dem ausgewählten Modell.",
    "Exporta todas las capas de envolventes a un GeoPackage, una tabla por modelo.": "Exportiert alle Hüllen-Ebenen in ein GeoPackage, eine Tabelle pro Modell.",
    "se utilizará el ángulo de respaldo guardado en cada modelo.": "der in jedem Modell gespeicherte Fallback-Winkel wird verwendet.",
    "Excepción guardada para la turbina": "Ausnahme für Turbine gespeichert",
    "del modelo": "des Modells",
    "Excepción de envolvente guardada.": "Hüllenausnahme gespeichert.",
    "Excepciones del modelo": "Modellausnahmen",
    "eliminadas · usando su plantilla de modelo.": "gelöscht · die Modellvorlage wird verwendet.",
    "dimensiones:": "Abmessungen:",
    "sin capa": "ohne Ebene",
    "Modelo definido sin capa de turbinas. Carga un CSV o genera la capa de puntos para crear sus elipses.":
        "Modell ohne Turbinen-Ebene definiert. Laden Sie eine CSV-Datei oder erzeugen Sie die Punktebene, um die Ellipsen zu erstellen.",
    "El modelo seleccionado todavía no tiene una capa de turbinas para dibujar.":
        "Das ausgewählte Modell besitzt noch keine Turbinen-Ebene zum Zeichnen.",
    "No hay modelos de aerogenerador definidos.": "Es sind keine Windturbinenmodelle definiert.",
})


# --- Aplicación explícita de la configuración del modelo ---
_TO_EN.update({
    "Aplicar nueva configuración": "Apply new configuration",
    "Guarda los valores mostrados en el modelo seleccionado y reconstruye su capa de elipses. No crea una excepción individual.":
        "Saves the displayed values to the selected model and rebuilds its ellipse layer. It does not create an individual exception.",
    "Cambios pendientes · pulsa «Aplicar nueva configuración» para actualizar el modelo.":
        "Pending changes · press ‘Apply new configuration’ to update the model.",
    "No hay un modelo seleccionado al que aplicar la configuración.":
        "There is no selected model to apply the configuration to.",
    "Configuración aplicada al modelo": "Configuration applied to model",
    "capa de elipses actualizada.": "ellipse layer updated.",
    "Configuración guardada para el modelo": "Configuration saved for model",
    "se utilizará automáticamente al cargar su CSV.":
        "it will be used automatically when its CSV is loaded.",
})
_TO_FR.update({
    "Aplicar nueva configuración": "Appliquer la nouvelle configuration",
    "Guarda los valores mostrados en el modelo seleccionado y reconstruye su capa de elipses. No crea una excepción individual.":
        "Enregistre les valeurs affichées dans le modèle sélectionné et reconstruit sa couche d’ellipses. Ne crée pas d’exception individuelle.",
    "Cambios pendientes · pulsa «Aplicar nueva configuración» para actualizar el modelo.":
        "Modifications en attente · cliquez sur « Appliquer la nouvelle configuration » pour mettre à jour le modèle.",
    "No hay un modelo seleccionado al que aplicar la configuración.":
        "Aucun modèle n’est sélectionné pour appliquer la configuration.",
    "Configuración aplicada al modelo": "Configuration appliquée au modèle",
    "capa de elipses actualizada.": "couche d’ellipses mise à jour.",
    "Configuración guardada para el modelo": "Configuration enregistrée pour le modèle",
    "se utilizará automáticamente al cargar su CSV.":
        "elle sera utilisée automatiquement lors du chargement de son CSV.",
})
_TO_DE.update({
    "Aplicar nueva configuración": "Neue Konfiguration anwenden",
    "Guarda los valores mostrados en el modelo seleccionado y reconstruye su capa de elipses. No crea una excepción individual.":
        "Speichert die angezeigten Werte im ausgewählten Modell und baut dessen Ellipsen-Ebene neu auf. Es wird keine individuelle Ausnahme erzeugt.",
    "Cambios pendientes · pulsa «Aplicar nueva configuración» para actualizar el modelo.":
        "Ausstehende Änderungen · klicken Sie auf „Neue Konfiguration anwenden“, um das Modell zu aktualisieren.",
    "No hay un modelo seleccionado al que aplicar la configuración.":
        "Es ist kein Modell ausgewählt, auf das die Konfiguration angewendet werden kann.",
    "Configuración aplicada al modelo": "Konfiguration auf Modell angewendet",
    "capa de elipses actualizada.": "Ellipsen-Ebene aktualisiert.",
    "Configuración guardada para el modelo": "Konfiguration für Modell gespeichert",
    "se utilizará automáticamente al cargar su CSV.":
        "sie wird beim Laden der zugehörigen CSV-Datei automatisch verwendet.",
})

_TO_EN.update({
    "Configura la separación mínima entre turbinas. Las envolventes se dibujan en una capa independiente por cada modelo de turbina y se validan también entre modelos al editar en el Mapa interactivo. Edita los valores y pulsa «Aplicar nueva configuración» para actualizar el modelo; «Definir elipse en pantalla» crea solo una excepción para una turbina concreta.":
        "Configure the minimum inter-turbine separation. Envelopes are drawn in a separate layer for each turbine model and are also validated between models while editing in Interactive Map mode. Edit the values and press ‘Apply new configuration’ to update the model; ‘Define ellipse on screen’ creates an exception only for one specific turbine.",
})
_TO_FR.update({
    "Configura la separación mínima entre turbinas. Las envolventes se dibujan en una capa independiente por cada modelo de turbina y se validan también entre modelos al editar en el Mapa interactivo. Edita los valores y pulsa «Aplicar nueva configuración» para actualizar el modelo; «Definir elipse en pantalla» crea solo una excepción para una turbina concreta.":
        "Configurez l’espacement minimal entre éoliennes. Les enveloppes sont dessinées dans une couche distincte pour chaque modèle et sont aussi validées entre modèles en mode Carte interactive. Modifiez les valeurs puis cliquez sur « Appliquer la nouvelle configuration » pour mettre à jour le modèle ; « Définir l’ellipse à l’écran » crée uniquement une exception pour une éolienne précise.",
})
_TO_DE.update({
    "Configura la separación mínima entre turbinas. Las envolventes se dibujan en una capa independiente por cada modelo de turbina y se validan también entre modelos al editar en el Mapa interactivo. Edita los valores y pulsa «Aplicar nueva configuración» para actualizar el modelo; «Definir elipse en pantalla» crea solo una excepción para una turbina concreta.":
        "Konfigurieren Sie den Mindestabstand zwischen Turbinen. Für jedes Turbinenmodell wird eine eigene Hüllen-Ebene erzeugt; die Validierung erfolgt auch modellübergreifend im interaktiven Kartenmodus. Bearbeiten Sie die Werte und klicken Sie auf „Neue Konfiguration anwenden“, um das Modell zu aktualisieren; „Ellipse am Bildschirm definieren“ erzeugt nur eine Ausnahme für eine bestimmte Turbine.",
})

def register() -> None:
    """Registra las traducciones del módulo (idempotente)."""
    if register_language is None:
        return
    try:
        register_language(LANG_EN, _TO_EN, _TO_EN, label="English")
        register_language(LANG_FR, _TO_FR, _TO_FR, label="Français")
        register_language(LANG_DE, _TO_DE, _TO_DE, label="Deutsch")
    except Exception:
        pass
