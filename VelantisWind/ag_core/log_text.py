# -*- coding: utf-8 -*-
"""Mensajes de log que se pueden traducir al mostrarlos.

El log de QGIS guarda el texto en español; la barra de mensajes traduce la
plantilla y la rellena con los datos, que no pasan por el traductor salvo que
sean a su vez textos con plantilla (p. ej. la etiqueta de un intento).
"""

from __future__ import annotations

from typing import Any, Callable


class LogText(str):
    """Texto en español con su plantilla y sus datos."""

    template_item = None


def log_text(template: str, **data: Any) -> LogText:
    # A nested exception may already display another language; the QGIS log keeps its Spanish source.
    text = LogText(template.format(**{key: shown(value, lambda source: source) for key, value in data.items()}))
    text.template_item = (template, data)
    return text


def shown(text: Any, tr: Callable[[str], str]) -> Any:
    """Texto para mostrar: la plantilla traducida con ``tr`` y sus datos, traducidos también si llevan plantilla."""
    item = getattr(text, "template_item", None)
    if not item:
        return text
    template, data = item
    return tr(template).format(**{key: shown(value, tr) for key, value in data.items()})


def log_error(cls: Callable[[str], Exception], template: str, **data: Any) -> Exception:
    """Excepción ``cls`` con el mensaje en el idioma activo y su plantilla con sus datos (``template_item``).

    Quien la muestra con ``template_item`` la traduce en el idioma de ese momento; quien muestra ``str(exc)``, en el
    del error. Sin el traductor (los lectores sin Qt), el mensaje queda en español.
    """
    text = log_text(template, **data)
    try:
        from ..i18n import tr_text
    except Exception:
        message = str(text)
    else:
        message = shown(text, tr_text)
    exc = cls(message)
    exc.template_item = text.template_item
    return exc
