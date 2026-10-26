# -*- coding: utf-8 -*-
"""Whether the QGIS project changed while a background Noise task was running (#51, for Noise as for the wake raster).

``QgsProject`` is a singleton: comparing ``instance()`` before and after a task cannot tell that QGIS cleared the
project or opened another one in the meantime; its signals can. A result calculated for one project is never added
to another."""
from __future__ import annotations

from qgis.core import QgsProject

from ..i18n import register_language

PROJECT_CHANGED = ("El proyecto cambió durante el cálculo de ruido. No se han añadido capas al proyecto actual. "
                   "Los archivos generados se conservan en:\n{path}")
PROJECT_CHANGED_NO_FILES = ("El proyecto cambió durante el cálculo de ruido. No se han añadido capas al proyecto "
                            "actual; vuelve a calcular en el proyecto que quieras.")

TRANSLATIONS = {
    "en": {
        PROJECT_CHANGED: "The project changed during the noise calculation. No layers have been added to the current "
                         "project. The generated files are kept in:\n{path}",
        PROJECT_CHANGED_NO_FILES: "The project changed during the noise calculation. No layers have been added to "
                                  "the current project; calculate again in the project you want.",
    },
    "fr": {
        PROJECT_CHANGED: "Le projet a changé pendant le calcul du bruit. Aucune couche n’a été ajoutée au projet "
                         "actuel. Les fichiers générés sont conservés dans :\n{path}",
        PROJECT_CHANGED_NO_FILES: "Le projet a changé pendant le calcul du bruit. Aucune couche n’a été ajoutée au "
                                  "projet actuel ; relancez le calcul dans le projet souhaité.",
    },
    "de": {
        PROJECT_CHANGED: "Das Projekt hat sich während der Schallberechnung geändert. Dem aktuellen Projekt wurden "
                         "keine Layer hinzugefügt. Die erzeugten Dateien bleiben erhalten in:\n{path}",
        PROJECT_CHANGED_NO_FILES: "Das Projekt hat sich während der Schallberechnung geändert. Dem aktuellen "
                                  "Projekt wurden keine Layer hinzugefügt; bitte im gewünschten Projekt neu berechnen.",
    },
}


def register_project_watch_translations() -> None:
    for language, mapping in TRANSLATIONS.items():
        register_language(language, mapping, {})


register_project_watch_translations()


class ProjectWatch:
    """Created when a task is launched, in the main thread; ``changed()`` when it finishes says whether the project
    was cleared or replaced since, and stops watching."""

    def __init__(self) -> None:
        self._project = QgsProject.instance()
        self._changed = False
        self._signals = []
        for name in ("cleared", "readProject"):
            signal = getattr(self._project, name, None)
            if signal is not None:
                signal.connect(self._invalidate)
                self._signals.append(signal)

    def _invalidate(self, *_args) -> None:
        self._changed = True

    def release(self) -> None:
        for signal in self._signals:
            try:
                signal.disconnect(self._invalidate)
            except (RuntimeError, TypeError):
                pass
        self._signals = []

    def changed(self) -> bool:
        self.release()
        return self._changed or QgsProject.instance() is not self._project
