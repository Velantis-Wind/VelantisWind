# -*- coding: utf-8 -*-
"""The «♥ Sponsors» button shared by the hub (home, Noise and Shadow) and Energy: it opens the support dialog."""
from __future__ import annotations

from qgis.PyQt import QtCore, QtWidgets

from .. import support_dialog
from ..i18n import tr_text as _tr


_STYLE = """
QPushButton#velantisSponsorButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #145da0, stop:1 #2583c9);
    color: #ffffff;
    border: 1px solid #14568d;
    border-radius: 9px;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 13px;
}
QPushButton#velantisSponsorButton:hover { background: #0e5594; border-color: #0a447d; }
QPushButton#velantisSponsorButton:pressed { background: #093e6f; }
QPushButton#velantisSponsorButton:focus { border: 2px solid #f0b34b; }
"""


class SponsorButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("velantisSponsorButton")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAutoDefault(False)  # Enter in a field of its window does not open the support dialog
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setStyleSheet(_STYLE)
        self.clicked.connect(self._open_support_dialog)
        self.refresh_labels()

    def keyPressEvent(self, event) -> None:
        if self.hasFocus() and event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            event.accept()
            self.click()
            return
        super().keyPressEvent(event)

    def refresh_labels(self) -> None:
        self.setText(_tr("♥ Sponsors"))
        self.setToolTip(_tr("Apoya voluntariamente el desarrollo, el mantenimiento y la validación de VelantisWind."))
        self.setAccessibleName(self.text().replace("♥", "").strip())
        self.setAccessibleDescription(self.toolTip())

    def _open_support_dialog(self, _checked=False) -> None:
        try:
            support_dialog.show_support_dialog(self.window())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.window(), _tr("Apoyar VelantisWind"), str(e))
