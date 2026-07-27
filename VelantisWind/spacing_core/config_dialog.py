# -*- coding: utf-8 -*-
"""spacing_core/config_dialog.py — Configuración desde el diálogo principal.

Diálogo no modal que incrusta el panel del SpacingController compartido para
poder configurar las envolventes de separación desde el diálogo principal
(botón bajo la importación de coordenadas CSV), sin necesidad de entrar en el
modo Mapa interactivo.

El panel es un widget único compartido con el dock del mapa interactivo, así
que este diálogo lo "toma prestado" al abrirse y lo devuelve (setParent(None))
al cerrarse. Dock y diálogo nunca están visibles a la vez (el diálogo
principal se oculta en modo interactivo), por lo que no compiten por él.

Al pulsar «Definir elipse en pantalla», este diálogo se oculta junto con el
diálogo principal para dejar el mapa libre, y ambos se restauran cuando la
herramienta de dibujo termina (señal ``tool_finished`` del controller).
"""

from __future__ import annotations

from qgis.PyQt import QtCore, QtWidgets

try:
    from ..i18n import apply_i18n
except Exception:  # pragma: no cover
    def apply_i18n(_widget):
        return None


class SpacingConfigDialog(QtWidgets.QDialog):
    """Envuelve el panel de envolventes para su uso desde el diálogo principal."""

    def __init__(self, controller, main_dialog=None, parent=None):
        super().__init__(parent or main_dialog)
        self.controller = controller
        self.main_dialog = main_dialog
        self._hidden_for_tool = False

        self.setWindowTitle("Envolvente de separación")
        self.setWindowModality(QtCore.Qt.NonModal)
        self.setMinimumWidth(340)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 8)
        v.setSpacing(8)

        note = QtWidgets.QLabel(
            "Configura la separación mínima entre turbinas. Las envolventes se "
            "dibujan en una capa independiente por cada modelo de turbina y se "
            "validan también entre modelos al editar en el Mapa interactivo. "
            "Edita los valores y pulsa «Aplicar nueva configuración» para "
            "actualizar el modelo; «Definir elipse en pantalla» crea solo una "
            "excepción para una turbina concreta."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666;")
        v.addWidget(note)

        # Tomar prestado el panel compartido
        self._panel = controller.panel
        try:
            self._panel.setParent(self)
        except Exception:
            pass
        v.addWidget(self._panel)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.close)
        btns.button(QtWidgets.QDialogButtonBox.Close).setText("Cerrar")
        v.addWidget(btns)
        apply_i18n(self)

        # Dibujo en pantalla: ocultar ventanas y restaurar al terminar
        try:
            self._panel.define_on_screen.connect(self._hide_for_tool)
        except Exception:
            pass
        try:
            controller.tool_finished.connect(self._restore_after_tool)
        except Exception:
            pass

    # ---------------------------------------------------------------- tool
    def _hide_for_tool(self):
        self._hidden_for_tool = True
        try:
            self.hide()
        except Exception:
            pass
        md = self.main_dialog
        if md is not None:
            try:
                md._hide_dialog_for_interactive_map()
            except Exception:
                try:
                    md.hide()
                except Exception:
                    pass

    def _restore_after_tool(self):
        if not self._hidden_for_tool:
            return
        self._hidden_for_tool = False
        md = self.main_dialog
        if md is not None:
            try:
                md._show_dialog_after_interactive_map()
            except Exception:
                try:
                    md.show()
                except Exception:
                    pass
        try:
            self.show()
            self.raise_()
        except Exception:
            pass

    # ------------------------------------------------------------- cierre
    def closeEvent(self, event):
        # Devolver el panel al controller (queda huérfano/oculto hasta que el
        # dock del mapa interactivo o un nuevo diálogo lo reclamen).
        try:
            self._panel.define_on_screen.disconnect(self._hide_for_tool)
        except Exception:
            pass
        try:
            self.controller.tool_finished.disconnect(self._restore_after_tool)
        except Exception:
            pass
        try:
            self.layout().removeWidget(self._panel)
            self._panel.setParent(None)
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()
