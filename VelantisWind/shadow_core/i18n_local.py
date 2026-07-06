# -*- coding: utf-8 -*-
"""Small four-language helpers for the Shadow/Flicker module.

The rest of the plugin uses the global runtime i18n table.  The shadow module
also builds many dynamic strings (progress dialogs, result summaries, layer
names), so this helper keeps those strings deterministic in ES/EN/FR/DE and
prevents the previous FR/DE-only fallbacks from leaking into other languages.
"""
from __future__ import annotations


def lang_code() -> str:
    try:
        from ..i18n import current_language  # type: ignore
    except Exception:
        try:
            from VelantisWind.i18n import current_language  # type: ignore
        except Exception:
            current_language = None  # type: ignore
    try:
        lang = str(current_language() if current_language else "es").lower().replace("-", "_").split("_", 1)[0]
    except Exception:
        lang = "es"
    return lang if lang in {"es", "en", "fr", "de"} else "es"


def is_de() -> bool:
    return lang_code() == "de"


def tr4(es: str, en: str | None = None, fr: str | None = None, de: str | None = None) -> str:
    lang = lang_code()
    if lang == "en" and en is not None:
        return en
    if lang == "fr" and fr is not None:
        return fr
    if lang == "de" and de is not None:
        return de
    return es


def yes_no(value: bool) -> str:
    return tr4("Sí" if value else "No", "Yes" if value else "No", "Oui" if value else "Non", "Ja" if value else "Nein")


def hours_per_year_unit() -> str:
    return tr4("h/año", "h/year", "h/an", "h/Jahr")


def close_label() -> str:
    return tr4("Cerrar", "Close", "Fermer", "Schließen")


def cancel_label() -> str:
    return tr4("Cancelar", "Cancel", "Annuler", "Abbrechen")


def month_names(short: bool = False):
    if short:
        return {
            "es": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
            "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            "fr": ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"],
            "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        }[lang_code()]
    return {
        "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "fr": ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
        "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
    }[lang_code()]


def timezone_label_local(timezone_mode: str, timezone_name: str | None, utc_offset: float) -> str:
    mode = (timezone_mode or "fixed").lower()
    if mode == "iana":
        return tr4(
            f"{timezone_name or 'UTC'} · hora civil local con DST",
            f"{timezone_name or 'UTC'} · local civil time with DST",
            f"{timezone_name or 'UTC'} · heure civile locale avec DST",
            f"{timezone_name or 'UTC'} · lokale Uhrzeit mit DST",
        )
    return tr4(
        f"UTC{utc_offset:+.1f} · desfase fijo",
        f"UTC{utc_offset:+.1f} · fixed offset",
        f"UTC{utc_offset:+.1f} · décalage fixe",
        f"UTC{utc_offset:+.1f} · fester Offset",
    )
