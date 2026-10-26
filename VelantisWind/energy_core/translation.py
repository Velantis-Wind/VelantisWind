# -*- coding: utf-8 -*-
"""Traducción de los textos visibles de ``energy_core``.

El import de ``i18n`` (Qt) es diferido para que el paquete se siga importando
sin QGIS; fuera de QGIS los textos quedan en español. Los textos con datos se
traducen como plantilla y se rellenan después (``tr("… {path}").format(...)``),
para que rutas, nombres y errores no pasen por el traductor.
"""

from __future__ import annotations


def tr(text: str) -> str:
    try:
        from ..i18n import tr_text
    except Exception:
        return text
    return tr_text(text)
