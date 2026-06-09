# -*- coding: utf-8 -*-
"""Responsive Qt helpers for QGIS plugin dialogs.

The plugin is often used on laptops, external monitors and high-DPI screens.
These helpers keep dialogs bounded to the visible screen and avoid hard fixed
sizes that make the UI unusable on smaller displays.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from qgis.PyQt import QtCore, QtWidgets


def _available_geometry(widget: Optional[QtWidgets.QWidget] = None):
    """Return the available screen geometry for *widget* or the primary screen."""
    try:
        screen = None
        if widget is not None:
            try:
                screen = widget.screen()
            except Exception:
                screen = None
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
    except Exception:
        pass
    return QtCore.QRect(0, 0, 1280, 800)


def fit_to_screen(
    widget: QtWidgets.QWidget,
    *,
    preferred: Tuple[int, int] = (1100, 760),
    minimum: Tuple[int, int] = (720, 480),
    max_ratio: Tuple[float, float] = (0.92, 0.90),
    set_maximum: bool = False,
) -> None:
    """Resize a dialog/window to fit the current screen.

    ``minimum`` is clipped to the actual screen, so the window never asks for a
    minimum size larger than the visible display. This is the main fix for small
    laptops or split-screen use.
    """
    try:
        geo = _available_geometry(widget)
        max_w = max(360, int(geo.width() * float(max_ratio[0])))
        max_h = max(320, int(geo.height() * float(max_ratio[1])))

        min_w = min(int(minimum[0]), max_w)
        min_h = min(int(minimum[1]), max_h)
        pref_w = min(max(int(preferred[0]), min_w), max_w)
        pref_h = min(max(int(preferred[1]), min_h), max_h)

        widget.setMinimumSize(min_w, min_h)
        if set_maximum:
            widget.setMaximumSize(max_w, max_h)
        widget.resize(pref_w, pref_h)
    except Exception:
        try:
            widget.resize(*preferred)
        except Exception:
            pass


def configure_scroll_area(scroll: QtWidgets.QScrollArea) -> None:
    """Make a scroll area behave well when the available size changes."""
    try:
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    except Exception:
        pass


def configure_table(
    table: QtWidgets.QTableWidget,
    *,
    stretch_columns: Sequence[int] = (),
    interactive: bool = True,
    min_height: Optional[int] = None,
) -> None:
    """Apply safe defaults for tables embedded in scrollable dialogs."""
    try:
        table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        table.setWordWrap(False)
        table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        if min_height is not None:
            table.setMinimumHeight(int(min_height))
        header = table.horizontalHeader()
        for c in range(table.columnCount()):
            if c in set(stretch_columns):
                header.setSectionResizeMode(c, QtWidgets.QHeaderView.Stretch)
            elif interactive:
                header.setSectionResizeMode(c, QtWidgets.QHeaderView.Interactive)
            else:
                header.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
    except Exception:
        pass


def relax_fixed_buttons(buttons: Iterable[QtWidgets.QAbstractButton], *, min_size: Tuple[int, int] = (132, 72)) -> None:
    """Replace hard fixed button sizes with scalable minimum sizes."""
    for btn in buttons:
        try:
            btn.setMinimumSize(int(min_size[0]), int(min_size[1]))
            btn.setMaximumSize(16777215, 16777215)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        except Exception:
            continue
