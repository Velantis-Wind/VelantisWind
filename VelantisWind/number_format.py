"""Numbers for display and reports, never for CSV or stored calculation data."""
from . import i18n


def format_number(value, spec=",.1f") -> str:
    """Keep the caller's precision and grouping, using the plugin's current language.

    The specification uses Python's comma grouping, independent of the system locale.
    French uses a narrow non-breaking space between groups of thousands.
    """
    text = format(value, spec)
    lang = i18n.current_language()
    if lang == "en":
        return text
    thousands = "\u202f" if lang == "fr" else "."
    return text.translate(str.maketrans({",": thousands, ".": ","}))


def format_percent(value, spec=",.1f") -> str:
    """Percent values are already scaled to 100; all four languages use a space."""
    return format_number(value, spec) + " %"
