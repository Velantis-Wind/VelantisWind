# -*- coding: utf-8 -*-
"""Traducciones focalizadas del dock y herramienta de mapa interactivo."""
from __future__ import annotations

from .i18n import LANG_DE, LANG_EN, LANG_FR, register_language

_TO_EN = {
    "Mapa interactivo · Velantis Wind": "Interactive map · Velantis Wind",
    "Capa de turbinas": "Turbine layer",
    "Editar capa:": "Edit layer:",
    "Actualizar lista de capas de turbinas editables.": "Refresh the list of editable turbine layers.",
    "Sin capas editables": "No editable layers",

    "Volver al diálogo": "Back to dialog",
    "Vuelve al diálogo principal sin salir del modo interactivo.": "Return to the main dialog without leaving interactive mode.",
    "Vuelve al diálogo principal de Velantis Wind sin perder la edición.": "Return to the Velantis Wind main dialog without losing edits.",
    "Física PyWake": "PyWake physics",
    "Motor WFM": "WFM engine",
    "Estela": "Wake",
    "Bloqueo": "Blockage",
    "Turbulencia (modelo)": "Turbulence model",


    "Limpiar": "Clear",
    "Alturas [m]:": "Heights [m]:",
    "p.ej. 90;120 (opcional)": "e.g. 90;120 (optional)",
    "Acciones": "Actions",
    "Calcular / Recalcular AEP": "Calculate / recalculate AEP",

    "Crear ráster de estelas": "Create wake raster",
    "Esc. A": "Scenario A",
    "Esc. B": "Scenario B",
    "Comparar escenarios A vs B.": "Compare scenarios A vs B.",
    "Guarda el último cálculo como escenario A.": "Save the latest calculation as scenario A.",
    "Guarda el último cálculo como escenario B.": "Save the latest calculation as scenario B.",
    "Salir": "Exit",
    "Salir del modo interactivo (ESC también funciona).": "Exit interactive mode (ESC also works).",
    "Calcula AEP con la capa de turbinas activa y los modelos seleccionados.": "Calculate AEP with the active turbine layer and selected models.",
    "Exporta los puntos editados de la capa activa a CSV. No sobrescribe el CSV original sin confirmar.": "Export edited points from the active layer to CSV. The original CSV is not overwritten without confirmation.",
    "Crea una capa ráster QGIS de velocidad efectiva con las turbinas y el recurso seleccionados.": "Create a QGIS effective-wind-speed raster layer using the selected turbines and resource.",



    "Sin capa activa": "No active layer",
    "Selecciónala en el panel de capas, o usa «Generar capas de puntos» en el diálogo.": "Select it in the layer panel, or use “Generate point layers” in the dialog.",
    "Hay": "There are",
    "capa(s) con": "layer(s) with",
    "turbina(s) disponibles para calcular.": "turbine(s) available for calculation.",

    "Puedes calcular igualmente con": "You can still calculate with",
    "capa(s) ya cargada(s),": "already loaded layer(s),",
    "turbina(s) en total.": "turbine(s) in total.",
    "editada": "edited",
    "activa": "active",
    "No se pudo activar la capa seleccionada:": "Could not activate the selected layer:",
    "Mapa interactivo": "Interactive map",
    "No hay turbina cerca del clic.": "No turbine was found near the click.",
    "No se pudo añadir turbina:": "Could not add turbine:",
    "No se pudo borrar turbina:": "Could not delete turbine:",
    "La capa activa no es de puntos.": "The active layer is not a point layer.",
    "La capa activa no es vectorial.": "The active layer is not a vector layer.",
    "Ya existe una turbina en ese punto.": "A turbine already exists at that point.",
    "No hay una capa de turbinas válida activa para el mapa interactivo.": "There is no valid active turbine layer for the interactive map.",
    "Click izq = añadir turbina | Click der = borrar turbina cercana": "Left click = add turbine | Right click = delete nearby turbine",
}

_TO_FR = {
    "Mapa interactivo · Velantis Wind": "Carte interactive · Velantis Wind",
    "Capa de turbinas": "Couche d’éoliennes",
    "Editar capa:": "Modifier la couche :",
    "Actualizar lista de capas de turbinas editables.": "Actualiser la liste des couches d’éoliennes modifiables.",
    "Sin capas editables": "Aucune couche modifiable",

    "Volver al diálogo": "Revenir à la boîte de dialogue",
    "Vuelve al diálogo principal sin salir del modo interactivo.": "Revient à la boîte de dialogue principale sans quitter le mode interactif.",
    "Vuelve al diálogo principal de Velantis Wind sin perder la edición.": "Revient à la boîte de dialogue principale de Velantis Wind sans perdre les modifications.",
    "Física PyWake": "Physique PyWake",
    "Motor WFM": "Moteur WFM",
    "Estela": "Sillage",
    "Bloqueo": "Blocage",
    "Turbulencia (modelo)": "Modèle de turbulence",


    "Limpiar": "Effacer",
    "Alturas [m]:": "Hauteurs [m] :",
    "p.ej. 90;120 (opcional)": "p. ex. 90;120 (facultatif)",
    "Acciones": "Actions",
    "Calcular / Recalcular AEP": "Calculer / recalculer l’AEP",

    "Crear ráster de estelas": "Créer le raster de sillages",
    "Esc. A": "Scénario A",
    "Esc. B": "Scénario B",
    "Comparar escenarios A vs B.": "Comparer les scénarios A et B.",
    "Guarda el último cálculo como escenario A.": "Enregistrer le dernier calcul comme scénario A.",
    "Guarda el último cálculo como escenario B.": "Enregistrer le dernier calcul comme scénario B.",
    "Salir": "Quitter",
    "Salir del modo interactivo (ESC también funciona).": "Quitter le mode interactif (Échap fonctionne aussi).",
    "Calcula AEP con la capa de turbinas activa y los modelos seleccionados.": "Calculer l’AEP avec la couche d’éoliennes active et les modèles sélectionnés.",
    "Exporta los puntos editados de la capa activa a CSV. No sobrescribe el CSV original sin confirmar.": "Exporter les points modifiés de la couche active en CSV. Le CSV original n’est pas remplacé sans confirmation.",
    "Crea una capa ráster QGIS de velocidad efectiva con las turbinas y el recurso seleccionados.": "Créer une couche raster QGIS de vitesse effective avec les éoliennes et la ressource sélectionnées.",



    "Sin capa activa": "Aucune couche active",
    "Selecciónala en el panel de capas, o usa «Generar capas de puntos» en el diálogo.": "Sélectionnez-la dans le panneau des couches ou utilisez « Générer les couches de points ».",
    "Hay": "Il y a",
    "capa(s) con": "couche(s) avec",
    "turbina(s) disponibles para calcular.": "éolienne(s) disponibles pour le calcul.",

    "Puedes calcular igualmente con": "Vous pouvez tout de même calculer avec",
    "capa(s) ya cargada(s),": "couche(s) déjà chargée(s),",
    "turbina(s) en total.": "éolienne(s) au total.",
    "editada": "modifiée",
    "activa": "active",
    "No se pudo activar la capa seleccionada:": "Impossible d’activer la couche sélectionnée :",
    "Mapa interactivo": "Carte interactive",
    "No hay turbina cerca del clic.": "Aucune éolienne près du clic.",
    "No se pudo añadir turbina:": "Impossible d’ajouter l’éolienne :",
    "No se pudo borrar turbina:": "Impossible de supprimer l’éolienne :",
    "La capa activa no es de puntos.": "La couche active n’est pas une couche de points.",
    "La capa activa no es vectorial.": "La couche active n’est pas vectorielle.",
    "Ya existe una turbina en ese punto.": "Une éolienne existe déjà à cet emplacement.",
    "No hay una capa de turbinas válida activa para el mapa interactivo.": "Aucune couche d’éoliennes active valide pour la carte interactive.",
    "Click izq = añadir turbina | Click der = borrar turbina cercana": "Clic gauche = ajouter une éolienne | clic droit = supprimer l’éolienne proche",
}

_TO_DE = {
    "Mapa interactivo · Velantis Wind": "Interaktive Karte · Velantis Wind",
    "Capa de turbinas": "Windturbinen-Layer",
    "Editar capa:": "Layer bearbeiten:",
    "Actualizar lista de capas de turbinas editables.": "Liste bearbeitbarer Windturbinen-Layer aktualisieren.",
    "Sin capas editables": "Keine bearbeitbaren Layer",

    "Volver al diálogo": "Zurück zum Dialog",
    "Vuelve al diálogo principal sin salir del modo interactivo.": "Zum Hauptdialog zurückkehren, ohne den interaktiven Modus zu verlassen.",
    "Vuelve al diálogo principal de Velantis Wind sin perder la edición.": "Zum Velantis-Wind-Hauptdialog zurückkehren, ohne Änderungen zu verlieren.",
    "Física PyWake": "PyWake-Physik",
    "Motor WFM": "WFM-Rechenkern",
    "Estela": "Nachlauf",
    "Bloqueo": "Blockade",
    "Turbulencia (modelo)": "Turbulenzmodell",


    "Limpiar": "Leeren",
    "Alturas [m]:": "Höhen [m]:",
    "p.ej. 90;120 (opcional)": "z. B. 90;120 (optional)",
    "Acciones": "Aktionen",
    "Calcular / Recalcular AEP": "AEP berechnen / neu berechnen",

    "Crear ráster de estelas": "Nachlauf-Raster erstellen",
    "Esc. A": "Szenario A",
    "Esc. B": "Szenario B",
    "Comparar escenarios A vs B.": "Szenarien A und B vergleichen.",
    "Guarda el último cálculo como escenario A.": "Letzte Berechnung als Szenario A speichern.",
    "Guarda el último cálculo como escenario B.": "Letzte Berechnung als Szenario B speichern.",
    "Salir": "Beenden",
    "Salir del modo interactivo (ESC también funciona).": "Interaktiven Modus beenden (ESC funktioniert ebenfalls).",
    "Calcula AEP con la capa de turbinas activa y los modelos seleccionados.": "AEP mit aktivem Windturbinen-Layer und ausgewählten Modellen berechnen.",
    "Exporta los puntos editados de la capa activa a CSV. No sobrescribe el CSV original sin confirmar.": "Bearbeitete Punkte des aktiven Layers als CSV exportieren. Die ursprüngliche CSV wird nicht ohne Bestätigung überschrieben.",
    "Crea una capa ráster QGIS de velocidad efectiva con las turbinas y el recurso seleccionados.": "Erstellt einen QGIS-Rasterlayer der effektiven Windgeschwindigkeit mit den ausgewählten Windturbinen und der Ressource.",



    "Sin capa activa": "Kein aktiver Layer",
    "Selecciónala en el panel de capas, o usa «Generar capas de puntos» en el diálogo.": "Wählen Sie ihn im Layer-Panel oder verwenden Sie „Punkt-Layer erzeugen“ im Dialog.",
    "Hay": "Es gibt",
    "capa(s) con": "Layer mit",
    "turbina(s) disponibles para calcular.": "Windturbine(n) für die Berechnung.",

    "Puedes calcular igualmente con": "Sie können trotzdem berechnen mit",
    "capa(s) ya cargada(s),": "bereits geladene Layer,",
    "turbina(s) en total.": "Windturbine(n) insgesamt.",
    "editada": "bearbeitet",
    "activa": "aktiv",
    "No se pudo activar la capa seleccionada:": "Der ausgewählte Layer konnte nicht aktiviert werden:",
    "Mapa interactivo": "Interaktive Karte",
    "No hay turbina cerca del clic.": "Keine Windturbine in der Nähe des Klicks.",
    "No se pudo añadir turbina:": "Windturbine konnte nicht hinzugefügt werden:",
    "No se pudo borrar turbina:": "Windturbine konnte nicht gelöscht werden:",
    "La capa activa no es de puntos.": "Der aktive Layer ist kein Punkt-Layer.",
    "La capa activa no es vectorial.": "Der aktive Layer ist kein Vektor-Layer.",
    "Ya existe una turbina en ese punto.": "An diesem Punkt existiert bereits eine Windturbine.",
    "No hay una capa de turbinas válida activa para el mapa interactivo.": "Kein gültiger aktiver Windturbinen-Layer für die interaktive Karte.",
    "Click izq = añadir turbina | Click der = borrar turbina cercana": "Linksklick = Windturbine hinzufügen | Rechtsklick = nahe Windturbine löschen",
}


# Dynamic labels and status fragments used after the dock is built.
_TO_EN.update({
    "Rotor-avg": "Rotor averaging",
    "de turbinas": "of turbines",
    "turbina(s)": "turbine(s)",
    "turb.": "turb.",
    "gen.": "gen.",

    "respaldo TI=10%": "TI=10% fallback",
    "más": "more",
    "falló:": "failed:",
    "Calcular AEP": "Calculate AEP",
    "A/B": "A/B",
})
_TO_FR.update({
    "Rotor-avg": "Moyenne sur le rotor",
    "de turbinas": "d’éoliennes",
    "turbina(s)": "éolienne(s)",
    "turb.": "éol.",
    "gen.": "gén.",

    "respaldo TI=10%": "TI=10 % par défaut",
    "más": "de plus",
    "falló:": "a échoué :",
    "Calcular AEP": "Calculer l’AEP",
    "A/B": "A/B",
})
_TO_DE.update({
    "Rotor-avg": "Rotormittelung",
    "de turbinas": "von Windturbinen",
    "turbina(s)": "Windturbine(n)",
    "turb.": "WT",
    "gen.": "Gen.",

    "respaldo TI=10%": "Fallback TI=10 %",
    "más": "weitere",
    "falló:": "fehlgeschlagen:",
    "Calcular AEP": "AEP berechnen",
    "A/B": "A/B",
})

# Turbine layer of each energy row: the map only edits layers it can write, in a projected CRS in metres.
_TO_EN.update({
    "El mapa interactivo solo edita capas en un sistema de coordenadas proyectado y en metros.":
        "The interactive map only edits layers in a projected coordinate reference system in metres.",
    "No se pudo pasar el clic al sistema de coordenadas de la capa: {error}":
        "The click could not be transformed to the layer's coordinate reference system: {error}",
    "La capa «{layer}» no admite añadir turbinas.": "Layer “{layer}” does not allow adding turbines.",
    "La capa «{layer}» no admite borrar turbinas.": "Layer “{layer}” does not allow deleting turbines.",
    "La capa «{layer}» es de solo lectura.": "Layer “{layer}” is read-only.",
    "La capa «{layer}» está en modo edición: guarda o descarta sus cambios para editarla desde el mapa.": "Layer “{layer}” is in edit mode: save or discard its changes to edit it from the map.",
    "la capa no ha guardado el cambio.": "the layer has not saved the change.",
    "el mapa o la capa no tienen un sistema de coordenadas válido": "the map or the layer has no valid coordinate reference system",
    "Ninguna fila tiene capa de turbinas.": "No row has a turbine layer.",
    "Elige una capa en el selector «Capa de turbinas» de una fila, o usa «Generar capas de puntos» en el diálogo.": "Choose a layer in the “Turbine layer” selector of a row, or use “Generate point layers” in the dialog.",
    "Calcula el AEP con las capas de turbinas elegidas en las filas y sus modelos.": "Calculates the AEP with the turbine layers chosen in the rows and their models.",
    "Para calcular, todas las filas deben tener una capa con turbinas.": "To calculate, every row must have a layer with turbines.",
    "Modelos sin capa con turbinas: {rows}.": "Models without a layer with turbines: {rows}.",
})
_TO_FR.update({
    "El mapa interactivo solo edita capas en un sistema de coordenadas proyectado y en metros.":
        "La carte interactive ne modifie que des couches dans un système de coordonnées projeté et en mètres.",
    "No se pudo pasar el clic al sistema de coordenadas de la capa: {error}":
        "Le clic n’a pas pu être transformé dans le système de coordonnées de la couche : {error}",
    "La capa «{layer}» no admite añadir turbinas.": "La couche « {layer} » ne permet pas d’ajouter des éoliennes.",
    "La capa «{layer}» no admite borrar turbinas.": "La couche « {layer} » ne permet pas de supprimer des éoliennes.",
    "La capa «{layer}» es de solo lectura.": "La couche « {layer} » est en lecture seule.",
    "La capa «{layer}» está en modo edición: guarda o descarta sus cambios para editarla desde el mapa.": "La couche « {layer} » est en mode édition : enregistrez ou annulez ses modifications pour la modifier depuis la carte.",
    "la capa no ha guardado el cambio.": "la couche n’a pas enregistré la modification.",
    "el mapa o la capa no tienen un sistema de coordenadas válido": "la carte ou la couche n’a pas de système de coordonnées valide",
    "Ninguna fila tiene capa de turbinas.": "Aucune ligne n’a de couche d’éoliennes.",
    "Elige una capa en el selector «Capa de turbinas» de una fila, o usa «Generar capas de puntos» en el diálogo.": "Choisissez une couche dans le sélecteur « Couche d’éoliennes » d’une ligne, ou utilisez « Générer les couches de points » dans la boîte de dialogue.",
    "Calcula el AEP con las capas de turbinas elegidas en las filas y sus modelos.": "Calcule l’AEP avec les couches d’éoliennes choisies sur les lignes et leurs modèles.",
    "Para calcular, todas las filas deben tener una capa con turbinas.": "Pour calculer, chaque ligne doit avoir une couche avec des éoliennes.",
    "Modelos sin capa con turbinas: {rows}.": "Modèles sans couche avec des éoliennes : {rows}.",
})
_TO_DE.update({
    "El mapa interactivo solo edita capas en un sistema de coordenadas proyectado y en metros.":
        "Die interaktive Karte bearbeitet nur Layer in einem projizierten Koordinatenbezugssystem in Metern.",
    "No se pudo pasar el clic al sistema de coordenadas de la capa: {error}":
        "Der Klick konnte nicht in das Koordinatenbezugssystem des Layers transformiert werden: {error}",
    "La capa «{layer}» no admite añadir turbinas.": "Der Layer „{layer}“ erlaubt nicht, Windturbinen hinzuzufügen.",
    "La capa «{layer}» no admite borrar turbinas.": "Der Layer „{layer}“ erlaubt nicht, Windturbinen zu löschen.",
    "La capa «{layer}» es de solo lectura.": "Der Layer „{layer}“ ist schreibgeschützt.",
    "La capa «{layer}» está en modo edición: guarda o descarta sus cambios para editarla desde el mapa.": "Der Layer „{layer}“ ist im Bearbeitungsmodus: Speichern oder verwerfen Sie seine Änderungen, um ihn in der Karte zu bearbeiten.",
    "la capa no ha guardado el cambio.": "Der Layer hat die Änderung nicht gespeichert.",
    "el mapa o la capa no tienen un sistema de coordenadas válido": "die Karte oder der Layer hat kein gültiges Koordinatenbezugssystem",
    "Ninguna fila tiene capa de turbinas.": "Keine Zeile hat einen Windturbinen-Layer.",
    "Elige una capa en el selector «Capa de turbinas» de una fila, o usa «Generar capas de puntos» en el diálogo.": "Wählen Sie einen Layer in der Auswahl „Windturbinen-Layer“ einer Zeile oder verwenden Sie „Punkt-Layer erzeugen“ im Dialog.",
    "Calcula el AEP con las capas de turbinas elegidas en las filas y sus modelos.": "Berechnet die AEP mit den in den Zeilen gewählten Windturbinen-Layern und ihren Modellen.",
    "Para calcular, todas las filas deben tener una capa con turbinas.": "Für die Berechnung muss jede Zeile einen Layer mit Windturbinen haben.",
    "Modelos sin capa con turbinas: {rows}.": "Modelle ohne Layer mit Windturbinen: {rows}.",
})


def register() -> None:
    register_language(LANG_EN, _TO_EN, _TO_EN, label="English")
    register_language(LANG_FR, _TO_FR, _TO_FR, label="Français")
    register_language(LANG_DE, _TO_DE, _TO_DE, label="Deutsch")


__all__ = ["register"]
