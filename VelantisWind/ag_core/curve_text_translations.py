"""Translations for whitespace-delimited turbine-curve import help."""
SPACE_TOOLTIP = "Espacio ( ): admite uno o varios espacios y tabuladores; ignora la sangría."
TRANSLATIONS = {
    "en": {SPACE_TOOLTIP: "Space ( ): accepts one or more spaces and tabs; ignores indentation."},
    "fr": {SPACE_TOOLTIP: "Espace ( ) : accepte un ou plusieurs espaces et tabulations ; ignore l’indentation."},
    "de": {SPACE_TOOLTIP: "Leerzeichen ( ): akzeptiert ein oder mehrere Leerzeichen und Tabulatoren; ignoriert Einrückungen."},
}


def register_curve_text_translations():
    from ..i18n import register_language
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, mapping)
