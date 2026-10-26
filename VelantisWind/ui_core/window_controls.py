# -*- coding: utf-8 -*-
"""Non-modal Qt window controls shared by the three VelantisWind modules.

Energy uses its own QDialog; Noise and Shadow are stacked QWidget pages of
VelantisHubDialog. The controls always target the actual top-level QDialog.
No calculation or module state is modified by minimizing or maximizing.
"""
from __future__ import annotations

from qgis.PyQt import QtCore, QtWidgets
from ..i18n import current_language
from .sponsor_button import SponsorButton


_TITLES = {
    "es": ("Minimizar", "Maximizar", "Restaurar", "Cerrar"),
    "en": ("Minimize", "Maximize", "Restore", "Close"),
    "fr": ("Réduire", "Agrandir", "Restaurer", "Fermer"),
    "de": ("Minimieren", "Maximieren", "Wiederherstellen", "Schließen"),
}


def enable_native_window_controls(dialog: QtWidgets.QDialog) -> None:
    """Expose minimize/maximize/close in the OS title bar, including for a parented QDialog.

    Preserve flags unrelated to window type (e.g. tool settings) while making
    this a normal independent, non-modal resizable window. Do not show it here.
    """
    flags = dialog.windowFlags()
    new_flags = ((flags & ~QtCore.Qt.WindowType_Mask) |
                 QtCore.Qt.Window | QtCore.Qt.WindowTitleHint |
                 QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowMinimizeButtonHint |
                 QtCore.Qt.WindowMaximizeButtonHint | QtCore.Qt.WindowCloseButtonHint)
    if new_flags != flags:
        dialog.setWindowFlags(new_flags)


class ModuleWindowControls(QtWidgets.QWidget):
    """Three accessible title-bar-style actions attached to a real top-level window."""

    def __init__(self, parent: QtWidgets.QWidget, target: QtWidgets.QDialog, sponsor: bool = False):
        super().__init__(parent)
        self._target = target
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 2, 0)
        layout.setSpacing(2)

        # Energy is a window of its own: its «♥ Sponsors» goes before its controls. The hub has one for all its pages.
        self.sponsor_button = SponsorButton(self) if sponsor else None
        if self.sponsor_button is not None:
            layout.addWidget(self.sponsor_button)
            layout.addSpacing(4)

        self.btn_minimize = self._button("minimize", QtWidgets.QStyle.SP_TitleBarMinButton)
        self.btn_maximize = self._button("maximize", QtWidgets.QStyle.SP_TitleBarMaxButton)
        self.btn_close = self._button("close", QtWidgets.QStyle.SP_TitleBarCloseButton)
        for button in (self.btn_minimize, self.btn_maximize, self.btn_close):
            layout.addWidget(button)

        self.btn_minimize.clicked.connect(lambda _checked=False: self._target.showMinimized())
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(lambda _checked=False: self._target.close())
        target.installEventFilter(self)
        self.refresh_labels()

    def _button(self, key: str, icon: QtWidgets.QStyle.StandardPixmap) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton(self)
        button.setObjectName("velantisWindow" + key.capitalize())
        button.setAutoRaise(True)
        button.setFocusPolicy(QtCore.Qt.StrongFocus)
        button.setFixedSize(28, 26)
        button.setIcon(self.style().standardIcon(icon))
        return button

    def _toggle_maximize(self, _checked=False) -> None:
        if self._target.isMaximized():
            self._target.showNormal()
        else:
            self._target.showMaximized()
        self.refresh_labels()

    def refresh_labels(self) -> None:
        language = str(current_language() or "es").lower().replace("-", "_").split("_", 1)[0]
        minimize, maximize, restore, close = _TITLES.get(language, _TITLES["es"])
        self.btn_minimize.setToolTip(minimize)
        self.btn_minimize.setAccessibleName(minimize)
        is_maximized = self._target.isMaximized()
        label = restore if is_maximized else maximize
        self.btn_maximize.setToolTip(label)
        self.btn_maximize.setAccessibleName(label)
        icon = (QtWidgets.QStyle.SP_TitleBarNormalButton if is_maximized
                else QtWidgets.QStyle.SP_TitleBarMaxButton)
        self.btn_maximize.setIcon(self.style().standardIcon(icon))
        self.btn_close.setToolTip(close)
        self.btn_close.setAccessibleName(close)
        if self.sponsor_button is not None:
            self.sponsor_button.refresh_labels()

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is self._target and event.type() == QtCore.QEvent.WindowStateChange:
            self.refresh_labels()
        return super().eventFilter(watched, event)


def attach_dialog_window_controls(dialog: QtWidgets.QDialog) -> None:
    """Install native actions and a small inline bar on Energy, without rebuilding its UI.

    The Energy dialog has its own stateful layout; reuse it and never recreate
    it merely to toggle window state. If its root is not a QBoxLayout, the OS
    title-bar actions remain available without moving any existing controls.
    """
    enable_native_window_controls(dialog)
    existing = dialog.findChild(ModuleWindowControls, "velantisEnergyWindowControls")
    if existing is not None:
        # The user may have changed language in the hub while Energy was hidden.
        existing.refresh_labels()
        return
    layout = dialog.layout()
    if isinstance(layout, QtWidgets.QBoxLayout):
        toolbar = ModuleWindowControls(dialog, target=dialog, sponsor=True)
        toolbar.setObjectName("velantisEnergyWindowControls")
        layout.insertWidget(0, toolbar, 0, QtCore.Qt.AlignRight)
