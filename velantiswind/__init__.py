# -*- coding: utf-8 -*-
"""QGIS entry point for the Velantis Wind plugin."""

from . import qt_compat  # noqa: F401 - apply Qt5/Qt6 aliases before plugin imports


def classFactory(iface):  # pylint: disable=invalid-name
    """Return the main QGIS plugin instance."""
    from .plugin import VelantisWindPlugin

    return VelantisWindPlugin(iface)
