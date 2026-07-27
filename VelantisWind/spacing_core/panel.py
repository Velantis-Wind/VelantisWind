# -*- coding: utf-8 -*-
"""spacing_core/panel.py — Controles de envolventes por modelo.

El panel edita siempre una envolvente elíptica. Cada capa/modelo de turbina
puede almacenar su propia separación longitudinal/transversal, orientación y
ángulo de respaldo. El selector de modelo evita que los parámetros de una
familia se apliquen accidentalmente a otra.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from qgis.PyQt import QtCore, QtWidgets

try:
    from ..i18n import apply_i18n, tr_text
except Exception:  # pragma: no cover
    def apply_i18n(_widget):
        return None
    def tr_text(text):
        return text

from .geometry import (
    MODE_AUTO,
    MODE_MANUAL_ANGLE,
    MODE_MANUAL_SCREEN,
    SHAPE_ELLIPTICAL,
    SpacingSpec,
)

VALIDATE_VIEW = "view"
VALIDATE_WARN = "warn"
VALIDATE_BLOCK = "block"

_ORG = "VelantisWind"
_APP = "VelantisWindPlugin"


class SpacingEnvelopePanel(QtWidgets.QGroupBox):
    """Panel de configuración de la envolvente elíptica por modelo."""

    changed = QtCore.pyqtSignal()
    apply_configuration = QtCore.pyqtSignal()
    toggled_envelopes = QtCore.pyqtSignal(bool)
    model_selected = QtCore.pyqtSignal(str)
    models_refresh_requested = QtCore.pyqtSignal()
    define_on_screen = QtCore.pyqtSignal()
    reset_overrides = QtCore.pyqtSignal()
    export_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Envolvente de separación", parent)
        self._settings = QtCore.QSettings(_ORG, _APP)
        self._syncing_model = False
        self._build_ui()
        self._load_settings()
        self._wire()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 6)
        v.setSpacing(5)

        self.chk_enable = QtWidgets.QCheckBox("Activar envolventes de separación")
        self.chk_enable.setToolTip(
            "Dibuja una elipse semitransparente alrededor de cada turbina. "
            "Cada modelo conserva su propia geometría. Rojo = conflicto; "
            "naranja = cerca del límite."
        )
        v.addWidget(self.chk_enable)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        self.cb_model = QtWidgets.QComboBox()
        self.cb_model.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_model.setToolTip(
            "Selecciona la capa/modelo cuyas dimensiones y orientación quieres editar."
        )
        self.btn_refresh_models = QtWidgets.QPushButton("↻")
        self.btn_refresh_models.setMaximumWidth(34)
        self.btn_refresh_models.setToolTip("Actualizar la lista de modelos de turbina del proyecto.")
        model_row = QtWidgets.QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(4)
        model_row.addWidget(self.cb_model, 1)
        model_row.addWidget(self.btn_refresh_models, 0)
        model_wrap = QtWidgets.QWidget()
        model_wrap.setLayout(model_row)
        form.addRow("Modelo de aerogenerador:", model_wrap)

        self.lbl_model_info = QtWidgets.QLabel("No hay modelos cargados.")
        self.lbl_model_info.setWordWrap(True)
        self.lbl_model_info.setStyleSheet("color: #666; font-size: 10px;")
        form.addRow("", self.lbl_model_info)

        self.sp_long = QtWidgets.QDoubleSpinBox()
        self.sp_long.setRange(0.5, 30.0)
        self.sp_long.setSingleStep(0.5)
        self.sp_long.setDecimals(2)
        self.sp_long.setValue(7.0)
        self.sp_long.setSuffix(" · D")
        self.sp_long.setToolTip(
            "Separación longitudinal mínima del modelo seleccionado, en diámetros de rotor."
        )
        form.addRow("Longitudinal:", self.sp_long)

        self.sp_trans = QtWidgets.QDoubleSpinBox()
        self.sp_trans.setRange(0.5, 30.0)
        self.sp_trans.setSingleStep(0.5)
        self.sp_trans.setDecimals(2)
        self.sp_trans.setValue(4.0)
        self.sp_trans.setSuffix(" · D")
        self.sp_trans.setToolTip(
            "Separación transversal mínima del modelo seleccionado, en diámetros de rotor."
        )
        form.addRow("Transversal:", self.sp_trans)

        self.cb_orientation = QtWidgets.QComboBox()
        self.cb_orientation.addItem("Automática · sector más energético", MODE_AUTO)
        self.cb_orientation.addItem("Manual · ángulo", MODE_MANUAL_ANGLE)
        self.cb_orientation.addItem("Manual · definir en pantalla", MODE_MANUAL_SCREEN)
        self.cb_orientation.setToolTip(
            "La orientación se guarda por modelo. En modo automático la elipse se alinea "
            "con el sector más energético del recurso; el ángulo actúa como respaldo."
        )
        form.addRow("Orientación:", self.cb_orientation)

        self.sp_angle = QtWidgets.QDoubleSpinBox()
        self.sp_angle.setRange(0.0, 359.9)
        self.sp_angle.setSingleStep(1.0)
        self.sp_angle.setDecimals(1)
        self.sp_angle.setSuffix(" °")
        self.sp_angle.setToolTip(
            "Azimut del eje mayor desde el Norte, en sentido horario. "
            "Se guarda de forma independiente para el modelo seleccionado."
        )
        form.addRow("Ángulo:", self.sp_angle)

        self.cb_validation = QtWidgets.QComboBox()
        self.cb_validation.addItem("Solo visualización", VALIDATE_VIEW)
        self.cb_validation.addItem("Avisar si hay conflicto", VALIDATE_WARN)
        self.cb_validation.addItem("Bloquear inserción si hay conflicto", VALIDATE_BLOCK)
        self.cb_validation.setToolTip(
            "La validación se aplica conjuntamente entre todos los modelos del proyecto."
        )
        form.addRow("Validación:", self.cb_validation)
        v.addLayout(form)

        self.btn_apply = QtWidgets.QPushButton("Aplicar nueva configuración")
        self.btn_apply.setToolTip(
            "Guarda los valores mostrados en el modelo seleccionado y reconstruye "
            "su capa de elipses. No crea una excepción individual."
        )
        v.addWidget(self.btn_apply)

        h_btn = QtWidgets.QHBoxLayout()
        h_btn.setSpacing(4)
        self.btn_define = QtWidgets.QPushButton("Definir elipse en pantalla")
        self.btn_define.setToolTip(
            "Define una excepción para una turbina del modelo seleccionado mediante tres clics."
        )
        self.btn_reset = QtWidgets.QPushButton("Restablecer")
        self.btn_reset.setToolTip(
            "Elimina las excepciones dibujadas de la capa/modelo seleccionado."
        )
        self.btn_reset.setMaximumWidth(110)
        h_btn.addWidget(self.btn_define, 1)
        h_btn.addWidget(self.btn_reset, 0)
        v.addLayout(h_btn)

        self.btn_export = QtWidgets.QPushButton("Exportar envolventes…")
        self.btn_export.setToolTip(
            "Exporta todas las capas de envolventes a un GeoPackage, una tabla por modelo."
        )
        v.addWidget(self.btn_export)

        self.lbl_status = QtWidgets.QLabel("—")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #555; font-size: 11px;")
        v.addWidget(self.lbl_status)

        apply_i18n(self)
        self._update_enabled_state()

    def _load_settings(self):
        s = self._settings
        try:
            self.chk_enable.setChecked(s.value("spacing/enabled", False, type=bool))
            self.sp_long.setValue(float(s.value("spacing/long_d", 7.0)))
            self.sp_trans.setValue(float(s.value("spacing/trans_d", 4.0)))
            self.sp_angle.setValue(float(s.value("spacing/angle_deg", 0.0)))
            mode = str(s.value("spacing/mode", MODE_AUTO))
            idx = self.cb_orientation.findData(mode)
            if idx >= 0:
                self.cb_orientation.setCurrentIndex(idx)
            val = str(s.value("spacing/validation", VALIDATE_WARN))
            idx = self.cb_validation.findData(val)
            if idx >= 0:
                self.cb_validation.setCurrentIndex(idx)
        except Exception:
            pass
        self._update_enabled_state()

    def _save_settings(self):
        s = self._settings
        try:
            s.setValue("spacing/enabled", self.chk_enable.isChecked())
            # Los campos también actúan como fallback para modelos nuevos/antiguos.
            s.setValue("spacing/long_d", self.sp_long.value())
            s.setValue("spacing/trans_d", self.sp_trans.value())
            s.setValue("spacing/angle_deg", self.sp_angle.value())
            s.setValue("spacing/mode", self.cb_orientation.currentData())
            s.setValue("spacing/shape", SHAPE_ELLIPTICAL)
            s.setValue("spacing/validation", self.cb_validation.currentData())
        except Exception:
            pass

    def _wire(self):
        self.chk_enable.toggled.connect(self._on_toggle)
        for w in (self.sp_long, self.sp_trans, self.sp_angle):
            w.valueChanged.connect(self._on_config_edited)
        self.cb_orientation.currentIndexChanged.connect(self._on_mode_edited)
        self.cb_validation.currentIndexChanged.connect(self._on_validation_changed)
        self.cb_model.currentIndexChanged.connect(self._on_model_changed)
        self.btn_refresh_models.clicked.connect(self.models_refresh_requested.emit)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_define.clicked.connect(self.define_on_screen.emit)
        self.btn_reset.clicked.connect(self.reset_overrides.emit)
        self.btn_export.clicked.connect(self.export_requested.emit)

    def _on_toggle(self, checked: bool):
        self._save_settings()
        self._update_enabled_state()
        # El controlador reconstruye al recibir ``toggled_envelopes``; emitir
        # también ``changed`` duplicaba el trabajo al activar/desactivar.
        self.toggled_envelopes.emit(bool(checked))

    def _on_config_edited(self, *_):
        """Marca la edición como pendiente sin alterar todavía el modelo."""
        if self._syncing_model:
            return
        self._update_enabled_state()
        self.set_status(
            "Cambios pendientes · pulsa «Aplicar nueva configuración» para actualizar el modelo."
        )

    def _on_mode_edited(self, *_):
        if self._syncing_model:
            return
        self._update_enabled_state()
        self.set_status(
            "Cambios pendientes · pulsa «Aplicar nueva configuración» para actualizar el modelo."
        )

    def _on_validation_changed(self, *_):
        if self._syncing_model:
            return
        # La validación es global y no modifica la geometría del modelo.
        self._save_settings()

    def _on_apply_clicked(self):
        if self._syncing_model:
            return
        self._save_settings()
        self.apply_configuration.emit()

    def _on_model_changed(self, *_):
        if self._syncing_model:
            return
        self.model_selected.emit(self.selected_model_id())

    def _update_enabled_state(self):
        on = self.chk_enable.isChecked()
        has_model = bool(self.selected_model_id())
        mode = self.cb_orientation.currentData()

        # La plantilla puede prepararse incluso con la visualización desactivada;
        # al pulsar Aplicar, el controller activa y reconstruye las envolventes.
        self.cb_model.setEnabled(True)
        self.btn_refresh_models.setEnabled(True)
        for w in (self.sp_long, self.sp_trans, self.cb_orientation, self.btn_apply):
            w.setEnabled(has_model)
        self.sp_angle.setEnabled(has_model and mode == MODE_MANUAL_ANGLE)

        # Estas acciones sí necesitan una capa de envolventes activa.
        self.btn_define.setEnabled(on and has_model)
        self.btn_reset.setEnabled(on and has_model)
        self.cb_validation.setEnabled(on)
        self.btn_export.setEnabled(on)

    def fallback_spec(self) -> SpacingSpec:
        return SpacingSpec(
            long_d=float(self.sp_long.value()),
            trans_d=float(self.sp_trans.value()),
            angle_deg=float(self.sp_angle.value()),
            mode=str(self.cb_orientation.currentData() or MODE_AUTO),
            shape=SHAPE_ELLIPTICAL,
        )

    def defaults_spec(self) -> SpacingSpec:
        return self.fallback_spec()

    def validation_mode(self) -> str:
        return str(self.cb_validation.currentData() or VALIDATE_WARN)

    def is_enabled(self) -> bool:
        return bool(self.chk_enable.isChecked())

    def set_enabled(self, enabled: bool, emit: bool = True):
        # Bloquea siempre la señal nativa para evitar dobles refresh; cuando se
        # solicita emisión, se lanzan una sola vez las señales públicas.
        try:
            self.chk_enable.blockSignals(True)
            self.chk_enable.setChecked(bool(enabled))
        finally:
            try:
                self.chk_enable.blockSignals(False)
            except Exception:
                pass
        self._save_settings()
        self._update_enabled_state()
        if emit:
            self.toggled_envelopes.emit(bool(enabled))

    def selected_model_id(self) -> str:
        try:
            return str(self.cb_model.currentData(QtCore.Qt.UserRole) or "")
        except Exception:
            return ""

    def set_models(
        self,
        models: Iterable[Tuple[str, str]],
        selected_id: str = "",
    ) -> None:
        items = list(models or [])
        self._syncing_model = True
        try:
            previous = selected_id or self.selected_model_id()
            self.cb_model.clear()
            if not items:
                self.cb_model.addItem(tr_text("No hay modelos cargados"), "")
                self.cb_model.setCurrentIndex(0)
                self.lbl_model_info.setText(tr_text("No hay modelos cargados."))
            else:
                for label, layer_id in items:
                    self.cb_model.addItem(str(label), str(layer_id))
                idx = self.cb_model.findData(str(previous)) if previous else -1
                self.cb_model.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._syncing_model = False
        self._update_enabled_state()

    def reflect_model_spec(
        self,
        spec: SpacingSpec,
        *,
        model_name: str = "",
        diameter_m: Optional[float] = None,
        turbine_count: Optional[int] = None,
    ) -> None:
        self._syncing_model = True
        widgets = (self.sp_long, self.sp_trans, self.sp_angle, self.cb_orientation)
        try:
            for w in widgets:
                w.blockSignals(True)
            self.sp_long.setValue(float(spec.long_d))
            self.sp_trans.setValue(float(spec.trans_d))
            self.sp_angle.setValue(float(spec.angle_deg))
            idx = self.cb_orientation.findData(str(spec.mode))
            self.cb_orientation.setCurrentIndex(idx if idx >= 0 else 0)
            pieces = []
            if model_name:
                pieces.append(str(model_name))
            if diameter_m is not None:
                pieces.append(f"D={float(diameter_m):g} m")
            if turbine_count is not None:
                pieces.append(tr_text(f"{int(turbine_count)} turbina(s)"))
            self.lbl_model_info.setText(" · ".join(pieces) if pieces else tr_text("Modelo seleccionado."))
        finally:
            for w in widgets:
                try:
                    w.blockSignals(False)
                except Exception:
                    pass
            self._syncing_model = False
        self._update_enabled_state()

    def set_status(self, text: str):
        try:
            self.lbl_status.setText(tr_text(text or "—"))
        except Exception:
            pass

    def reflect_spec(self, spec: SpacingSpec):
        """Compatibilidad: refleja temporalmente una geometría dibujada."""
        self.reflect_model_spec(spec)
