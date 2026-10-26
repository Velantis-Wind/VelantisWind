# -*- coding: utf-8 -*-
"""Exact translations for CRS validation errors shared by the QGIS modules, and for the warnings of their outputs."""

TRANSLATIONS = {
    "en": {
        "No se puede crear una capa georreferenciada sin un CRS válido: {name}": "Cannot create a georeferenced layer without a valid CRS: {name}",
        "No se pudo crear la capa en memoria de QGIS: {name}": "Could not create QGIS memory layer: {name}",
        "CRS del recurso/proyecto no válido; no se dibuja un perímetro con CRS supuesto.": "The resource/project CRS is invalid; no boundary will be drawn with an assumed CRS.",
        "El CRS del resultado acústico no es válido; no se asignará uno supuesto.": "The CRS of the acoustic result is invalid; no CRS will be assumed.",
        "El CRS de las fuentes acústicas no es válido.": "The CRS of the acoustic sources is invalid.",
        "sin identificador": "no identifier",
    },
    "fr": {
        "No se puede crear una capa georreferenciada sin un CRS válido: {name}": "Impossible de créer une couche géoréférencée sans SCR valide : {name}",
        "No se pudo crear la capa en memoria de QGIS: {name}": "Impossible de créer la couche en mémoire de QGIS : {name}",
        "CRS del recurso/proyecto no válido; no se dibuja un perímetro con CRS supuesto.": "Le SCR de la ressource ou du projet n’est pas valide ; aucun périmètre ne sera tracé avec un SCR supposé.",
        "El CRS del resultado acústico no es válido; no se asignará uno supuesto.": "Le SCR du résultat acoustique n’est pas valide ; aucun SCR ne sera supposé.",
        "El CRS de las fuentes acústicas no es válido.": "Le SCR des sources acoustiques n’est pas valide.",
        "sin identificador": "sans identifiant",
    },
    "de": {
        "No se puede crear una capa georreferenciada sin un CRS válido: {name}": "Ohne gültiges KBS kann kein georeferenzierter Layer erstellt werden: {name}",
        "No se pudo crear la capa en memoria de QGIS: {name}": "Der QGIS-Layer im Arbeitsspeicher konnte nicht erstellt werden: {name}",
        "CRS del recurso/proyecto no válido; no se dibuja un perímetro con CRS supuesto.": "Das KBS der Ressource oder des Projekts ist ungültig; es wird keine Ressourcengrenze mit einem angenommenen KBS gezeichnet.",
        "El CRS del resultado acústico no es válido; no se asignará uno supuesto.": "Das KBS des Schallergebnisses ist ungültig; es wird kein KBS angenommen.",
        "El CRS de las fuentes acústicas no es válido.": "Das KBS der Schallquellen ist ungültig.",
        "sin identificador": "ohne Kennung",
    },
}

# Lines of the Noise status text, which is translated as a whole: they are also fragments.
STATUS_LINES = {
    "en": {
        "• AVISO: se solicitaron las isófonas pero no se pudieron generar.": "• WARNING: the isophones were requested but could not be generated.",
    },
    "fr": {
        "• AVISO: se solicitaron las isófonas pero no se pudieron generar.": "• AVERTISSEMENT : les isophones ont été demandées mais n’ont pas pu être générées.",
    },
    "de": {
        "• AVISO: se solicitaron las isófonas pero no se pudieron generar.": "• HINWEIS: Isophonen wurden angefordert, konnten aber nicht erstellt werden.",
    },
}


def register_crs_translations():
    from .i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        # Translate templates before inserting user-provided layer names.
        register_language(language, mapping, {})
    for language, mapping in STATUS_LINES.items():
        register_language(language, mapping, mapping)
