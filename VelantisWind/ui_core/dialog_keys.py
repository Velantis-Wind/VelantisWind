# -*- coding: utf-8 -*-
"""The Enter key in the dialog of Energy and in the windows of the wake group (piece E1 of #64).

A push button that has the focus presses itself, an open list chooses its option and a field confirms its value, each
its own way, before the key reaches the dialog. What reaches it goes on to the default action of the dialog («Calcular
AEP», «Aceptar») only with no control with the focus, or the dialog itself; otherwise it does nothing, but open a
combo box of the dialog."""
from __future__ import annotations

from qgis.PyQt import QtCore, QtWidgets

__all__ = ["enter_reaches_default"]


def enter_reaches_default(dialog: QtWidgets.QDialog, event) -> bool:
    """Whether a key press that reached ``dialog`` goes on to its default action (``QDialog.keyPressEvent``). Return
    and Enter do only with no control with the focus, or the dialog itself; on a combo box of the dialog (or its
    editor), enabled and closed, they open it; from any other control, or one of another window, they are taken here
    and do nothing."""
    if event.key() not in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):  # scoped: Qt5 and Qt6
        return True
    focus = QtWidgets.QApplication.focusWidget()
    if focus is None or focus is dialog:
        return True
    combo = focus if isinstance(focus, QtWidgets.QComboBox) else focus.parent()
    if (isinstance(combo, QtWidgets.QComboBox) and combo.window() is dialog and combo.isEnabled()
            and not combo.view().isVisible()):
        combo.showPopup()
    event.accept()
    return False
