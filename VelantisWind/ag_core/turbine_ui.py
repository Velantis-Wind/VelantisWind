# -*- coding: utf-8 -*-
"""
Diálogo minimal para crear turbinas:
- Manual (listas ws/power_kW/ct)
- Desde TXT/CSV (usa TxtSpec + load_curves_from_txt)
Devuelve un WindTurbines (plural) compatible con PyWake 2.6.7 y expone result_data()
para que AG_dialog pueda reconstruir si lo desea.
"""

from qgis.PyQt import QtWidgets, QtCore
from typing import Optional, List, Tuple, Dict, Any
import os

# Utilidades del módulo turbine.py
from .turbine import TxtSpec, load_curves_from_txt, build_wt_from_manual

try:
    from ..i18n import apply_i18n, install_runtime_i18n_patches
except Exception:  # pragma: no cover - allows standalone imports during tests
    def apply_i18n(widget):
        return None
    def install_runtime_i18n_patches():
        return None

__all__ = ["CustomTurbineDialog"]


def _debug_print(message: str) -> None:
    """Optional console diagnostics enabled with VELANTISWIND_DEBUG=1."""
    try:
        if os.environ.get("VELANTISWIND_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(message)
    except Exception:
        pass


def _parse_num_list(txt: str) -> List[float]:
    """Convierte un bloque de texto en lista de floats.
    Soporta separadores: coma, punto y coma, espacios, tabs y saltos de línea."""
    raw = (
        txt.replace(";", " ")
           .replace(",", " ")
           .replace("\t", " ")
           .replace("\r", " ")
           .strip()
    )
    if not raw:
        return []
    out: List[float] = []
    for token in raw.split():
        out.append(float(token))
    return out


# Plantillas rápidas para pre-assessment. No son curvas oficiales de fabricante:
# generan una curva genérica editable a partir de geometría + potencia nominal típica.
_GENERIC_PRESETS: Dict[str, Dict[str, float]] = {
    "Vestas V80-2.0 · genérico": {"diam": 80.0, "hub": 80.0, "rated_kw": 2000.0},
    "Vestas V90-2.0 · genérico": {"diam": 90.0, "hub": 80.0, "rated_kw": 2000.0},
    "Vestas V100-2.0 · genérico": {"diam": 100.0, "hub": 95.0, "rated_kw": 2000.0},
    "Vestas V112-3.0 · genérico": {"diam": 112.0, "hub": 94.0, "rated_kw": 3000.0},
    "Siemens SWT-2.3-93 · genérico": {"diam": 93.0, "hub": 80.0, "rated_kw": 2300.0},
    "Enercon E-82 · genérico": {"diam": 82.0, "hub": 85.0, "rated_kw": 2000.0},
    "GE 1.5sle · genérico": {"diam": 77.0, "hub": 80.0, "rated_kw": 1500.0},
}


def _generic_curve_from_rated(rated_kw: float, cut_in: float = 3.0, rated_ws: float = 12.0, cut_out: float = 25.0) -> Tuple[List[float], List[float], List[float]]:
    """Curva screening simple, editable y no certificada por fabricante."""
    ws = [float(v) for v in range(0, 26)]
    power: List[float] = []
    ct: List[float] = []
    for w in ws:
        if w < cut_in or w > cut_out:
            p = 0.0
            c = 0.0
        elif w < rated_ws:
            frac = max(0.0, min(1.0, (w - cut_in) / max(rated_ws - cut_in, 1e-9)))
            p = float(rated_kw) * (frac ** 3)
            c = 0.82
        else:
            p = float(rated_kw)
            c = max(0.18, 0.82 - 0.045 * (w - rated_ws))
        power.append(round(p, 3))
        ct.append(round(max(0.0, min(1.0, c)), 3))
    return ws, power, ct


def _fmt_list(vals: List[float]) -> str:
    return " ".join((f"{v:.3f}".rstrip("0").rstrip(".") for v in vals))


class _HLine(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


class CustomTurbineDialog(QtWidgets.QDialog):
    """Diálogo sin .ui que permite definir una turbina y recuperar sus datos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        install_runtime_i18n_patches()
        self.setWindowTitle("Definir turbina")
        self.setMinimumSize(520, 420)
        self.resize(720, 560)
        self.setSizeGripEnabled(True)

        self._wt = None  # type: Optional[object]
        self._last_curves = None  # type: Optional[Tuple[List[float], List[float], List[float]]]
        self._result_data = None  # type: Optional[Dict[str, Any]]

        tabs = QtWidgets.QTabWidget(self)

        def _make_scroll(content: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
            area = QtWidgets.QScrollArea(self)
            area.setWidgetResizable(True)
            area.setFrameShape(QtWidgets.QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            area.setWidget(content)
            return area

        def _tune_plain_edit(w: QtWidgets.QPlainTextEdit) -> None:
            w.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
            w.setMinimumHeight(70)
            w.setMaximumHeight(115)
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # ---------- TAB: MANUAL ----------
        w_manual = QtWidgets.QWidget()
        f_man = QtWidgets.QFormLayout(w_manual)
        f_man.setContentsMargins(10, 10, 10, 10)
        f_man.setSpacing(8)
        try:
            f_man.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            f_man.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            f_man.setFormAlignment(QtCore.Qt.AlignTop)
        except Exception:
            pass

        self.ed_name_m = QtWidgets.QLineEdit("Custom WT")
        self.ed_name_m.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.sp_diam_m = QtWidgets.QDoubleSpinBox()
        self.sp_diam_m.setRange(1.0, 500.0)
        self.sp_diam_m.setValue(120.0)
        self.sp_diam_m.setSuffix(" m")

        self.sp_hub_m = QtWidgets.QDoubleSpinBox()
        self.sp_hub_m.setRange(1.0, 300.0)
        self.sp_hub_m.setValue(90.0)
        self.sp_hub_m.setSuffix(" m")

        self.te_ws = QtWidgets.QPlainTextEdit()
        self.te_power = QtWidgets.QPlainTextEdit()
        self.te_ct = QtWidgets.QPlainTextEdit()
        self.te_ct.setPlaceholderText("(opcional)")
        for _te in (self.te_ws, self.te_power, self.te_ct):
            _tune_plain_edit(_te)

        # Placeholders rápidos
        self.te_ws.setPlaceholderText("Ej.: 3 4 5 6 7 8 9 10 11 12 13 14")
        self.te_power.setPlaceholderText("Potencia en kW, misma longitud que ws")

        self.cb_generic_preset = QtWidgets.QComboBox()
        self.cb_generic_preset.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_generic_preset.setMinimumContentsLength(22)
        self.cb_generic_preset.addItem("Sin plantilla", None)
        for label, data in _GENERIC_PRESETS.items():
            self.cb_generic_preset.addItem(label, data)
        self.cb_generic_preset.setToolTip(
            "Plantillas de screening: rellenan D, hub, potencia nominal y una curva genérica editable. "
            "No sustituyen la curva oficial del fabricante."
        )
        self.cb_generic_preset.currentIndexChanged.connect(self._apply_generic_preset)

        note_preset = QtWidgets.QLabel(
            "Las plantillas son genéricas para pre-screening. Para entrega final usa la curva oficial del fabricante/cliente."
        )
        note_preset.setWordWrap(True)
        note_preset.setStyleSheet("color: #666; font-size: 11px;")

        f_man.addRow("Plantilla rápida:", self.cb_generic_preset)
        f_man.addRow("", note_preset)
        f_man.addRow("Nombre:", self.ed_name_m)
        f_man.addRow("Diámetro rotor:", self.sp_diam_m)
        f_man.addRow("Altura buje:", self.sp_hub_m)
        f_man.addRow(_HLine())
        f_man.addRow("Velocidad viento (m/s):", self.te_ws)
        f_man.addRow("Potencia (kW):", self.te_power)
        f_man.addRow("CT (0–1):", self.te_ct)

        btn_build_m = QtWidgets.QPushButton("Crear turbina (Manual)")
        btn_build_m.clicked.connect(self._on_build_manual)
        f_man.addRow(btn_build_m)

        # ---------- TAB: TXT/CSV ----------
        w_csv = QtWidgets.QWidget()
        f_csv = QtWidgets.QFormLayout(w_csv)
        f_csv.setContentsMargins(10, 10, 10, 10)
        f_csv.setSpacing(8)
        try:
            f_csv.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            f_csv.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            f_csv.setFormAlignment(QtCore.Qt.AlignTop)
        except Exception:
            pass

        self.ed_name_c = QtWidgets.QLineEdit("Custom WT (CSV)")
        self.sp_diam_c = QtWidgets.QDoubleSpinBox()
        self.sp_diam_c.setRange(1.0, 500.0)
        self.sp_diam_c.setValue(120.0)
        self.sp_diam_c.setSuffix(" m")

        self.sp_hub_c = QtWidgets.QDoubleSpinBox()
        self.sp_hub_c.setRange(1.0, 300.0)
        self.sp_hub_c.setValue(90.0)
        self.sp_hub_c.setSuffix(" m")

        h_path = QtWidgets.QHBoxLayout()
        h_path.setContentsMargins(0, 0, 0, 0)
        self.ed_path = QtWidgets.QLineEdit()
        self.ed_path.setPlaceholderText("Selecciona TXT/CSV…")
        btn_browse = QtWidgets.QPushButton("Examinar…")
        btn_browse.clicked.connect(self._browse_file)
        h_path.addWidget(self.ed_path, 1)
        h_path.addWidget(btn_browse, 0)
        path_wrap = QtWidgets.QWidget()
        path_wrap.setLayout(h_path)

        self.cb_delim = QtWidgets.QComboBox()
        self.cb_delim.addItems(["Tabulación (\\t)", "Coma (,)", "Punto y coma (;)", "Espacio ( )"])
        self.cb_delim.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.sp_ws_col = QtWidgets.QSpinBox(); self.sp_ws_col.setRange(0, 99); self.sp_ws_col.setValue(0)
        self.sp_pw_col = QtWidgets.QSpinBox(); self.sp_pw_col.setRange(0, 99); self.sp_pw_col.setValue(1)
        self.chk_ct_col = QtWidgets.QCheckBox("Incluir columna CT")
        self.sp_ct_col = QtWidgets.QSpinBox(); self.sp_ct_col.setRange(0, 99); self.sp_ct_col.setEnabled(False)
        self.chk_ct_col.toggled.connect(self.sp_ct_col.setEnabled)

        self.sp_skip = QtWidgets.QSpinBox(); self.sp_skip.setRange(0, 100); self.sp_skip.setValue(1)

        f_csv.addRow("Nombre:", self.ed_name_c)
        f_csv.addRow("Diámetro rotor:", self.sp_diam_c)
        f_csv.addRow("Altura buje:", self.sp_hub_c)
        f_csv.addRow(_HLine())
        f_csv.addRow("Fichero TXT/CSV:", path_wrap)
        f_csv.addRow("Delimitador:", self.cb_delim)
        f_csv.addRow("Columna ws (0-based):", self.sp_ws_col)
        f_csv.addRow("Columna potencia kW (0-based):", self.sp_pw_col)
        f_csv.addRow(self.chk_ct_col, self.sp_ct_col)
        f_csv.addRow("Filas de cabecera a saltar:", self.sp_skip)

        btn_build_c = QtWidgets.QPushButton("Crear turbina (TXT/CSV)")
        btn_build_c.clicked.connect(self._on_build_csv)
        f_csv.addRow(btn_build_c)

        tabs.addTab(_make_scroll(w_manual), "Manual")
        tabs.addTab(_make_scroll(w_csv), "TXT/CSV")

        # ---------- BOTONES INFERIORES ----------
        btn_ok = QtWidgets.QPushButton("Aceptar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_back = QtWidgets.QPushButton("Volver al diálogo")
        btn_back.setToolTip("Cerrar esta ventana y volver al diálogo principal sin crear la capa.")
        btn_back.clicked.connect(self.reject)

        bb = QtWidgets.QHBoxLayout()
        bb.addWidget(btn_back)
        bb.addStretch(1)
        bb.addWidget(btn_cancel)
        bb.addWidget(btn_ok)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(tabs, 1)
        lay.addLayout(bb)

        apply_i18n(self)
        QtCore.QTimer.singleShot(0, self._fit_to_screen)

    def _fit_to_screen(self) -> None:
        """Evita que el diálogo se salga de pantallas pequeñas dentro de QGIS."""
        try:
            screen = self.screen() or QtWidgets.QApplication.primaryScreen()
            if screen is None:
                return
            available = screen.availableGeometry()
            max_w = max(520, int(available.width() * 0.86))
            max_h = max(420, int(available.height() * 0.86))
            self.setMaximumSize(max_w, max_h)
            self.resize(min(max(self.width(), 640), max_w), min(max(self.height(), 520), max_h))
        except Exception:
            pass

    def _apply_generic_preset(self) -> None:
        """Rellena la pestaña Manual con una plantilla genérica editable."""
        try:
            data = self.cb_generic_preset.currentData()
        except Exception:
            data = None
        if not isinstance(data, dict):
            return
        try:
            label = self.cb_generic_preset.currentText().replace(" · genérico", "")
            rated_kw = float(data.get("rated_kw", 0.0) or 0.0)
            ws, power_kw, ct = _generic_curve_from_rated(rated_kw)
            self.ed_name_m.setText(label + " (generic curve)")
            self.sp_diam_m.setValue(float(data.get("diam", 120.0)))
            self.sp_hub_m.setValue(float(data.get("hub", 90.0)))
            self.te_ws.setPlainText(_fmt_list(ws))
            self.te_power.setPlainText(_fmt_list(power_kw))
            self.te_ct.setPlainText(_fmt_list(ct))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Plantilla de turbina", f"No se pudo aplicar la plantilla:\n{e}")


    # -------------------- Handlers --------------------
    def _browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Abrir TXT/CSV", os.path.expanduser("~"),
            "TXT/CSV (*.txt *.csv);;Todos (*.*)"
        )
        if path:
            self.ed_path.setText(path)
            _debug_print(f"[Energy turbine UI] Selected file: {path}")

    def _delimiter(self) -> str:
        idx = self.cb_delim.currentIndex()
        return {0: "\t", 1: ",", 2: ";", 3: " "}.get(idx, "\t")

    def _on_build_manual(self):
        try:
            name = self.ed_name_m.text().strip() or "Custom WT"
            d = float(self.sp_diam_m.value())
            h = float(self.sp_hub_m.value())
            ws = _parse_num_list(self.te_ws.toPlainText())
            pw_kw = _parse_num_list(self.te_power.toPlainText())
            ct_txt = self.te_ct.toPlainText().strip()
            ct = _parse_num_list(ct_txt) if ct_txt else None

            _debug_print(f"[Energy turbine UI] Manual curve: name={name} D={d} HH={h} npts={len(ws)} has_ct={ct is not None}")

            wt = build_wt_from_manual(name, d, h, ws, pw_kw, ct)
            self._wt = wt
            self._last_curves = (ws, [p for p in pw_kw], ct if ct else [])

            self._result_data = {
                "mode": "manual",
                "name": name,
                "diam": d,
                "hh": h,
                "ws": ws,
                "power_kw": pw_kw,
                "ct": ct,
                # Potencia nominal pre-calculada para que aep_compute no tenga que
                # inferirla desde wt.power() (camino frágil entre versiones de PyWake).
                "p_rated_kw": float(max(pw_kw)) if pw_kw else 0.0,
            }

            QtWidgets.QMessageBox.information(self, "Listo",
                                              "Turbina creada (manual). Pulsa Aceptar para usarla.")
            _debug_print("[Energy turbine UI] Manual turbine created and stored.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error creando turbina", str(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_manual: {e}")

    def _on_build_csv(self):
        try:
            path = self.ed_path.text().strip()
            if not path or not os.path.exists(path):
                raise FileNotFoundError("Selecciona un archivo TXT/CSV válido.")

            spec = TxtSpec(
                ws_col=int(self.sp_ws_col.value()),
                power_col=int(self.sp_pw_col.value()),
                delimiter=self._delimiter(),
                skip_header=int(self.sp_skip.value()),
                ct_col=int(self.sp_ct_col.value()) if self.chk_ct_col.isChecked() else None,
            )
            _debug_print(f"[Energy turbine UI] CSV spec: {spec}")

            ws, power_W, ct = load_curves_from_txt(path, spec)
            power_kW = [p / 1000.0 for p in power_W]  # W -> kW para nuestro builder

            name = self.ed_name_c.text().strip() or "Custom WT (CSV)"
            d = float(self.sp_diam_c.value())
            h = float(self.sp_hub_c.value())

            _debug_print(f"[Energy turbine UI] CSV curve: name={name} D={d} HH={h} npts={len(ws)}")

            wt = build_wt_from_manual(name, d, h, ws, power_kW, ct)
            self._wt = wt
            self._last_curves = (ws, power_kW, ct)

            self._result_data = {
                "mode": "csv",
                "name": name,
                "diam": d,
                "hh": h,
                "path": path,
                "ws_col": int(self.sp_ws_col.value()),
                "power_col": int(self.sp_pw_col.value()),
                "delimiter": self._delimiter(),
                "skip_header": int(self.sp_skip.value()),
                "ct_col": int(self.sp_ct_col.value()) if self.chk_ct_col.isChecked() else None,
                # Curvas ya parseadas + potencia nominal — útiles para preview, persistencia
                # y para que aep_compute no tenga que inferirlas.
                "ws": list(ws),
                "power_kw": list(power_kW),
                "ct": list(ct) if ct else None,
                "p_rated_kw": float(max(power_kW)) if power_kW else 0.0,
            }

            QtWidgets.QMessageBox.information(self, "Listo",
                                              "Turbina creada desde TXT/CSV. Pulsa Aceptar para usarla.")
            _debug_print("[Energy turbine UI] CSV turbine created and stored.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error leyendo TXT/CSV", str(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_csv: {e}")

    # -------------------- API pública --------------------
    def get_wind_turbine(self):
        """Devuelve la instancia WindTurbines creada o None si no se construyó."""
        _debug_print(f"[Energy turbine UI] get_wind_turbine() -> {type(self._wt)}")
        return self._wt

    def get_last_curves(self) -> Optional[Tuple[List[float], List[float], List[float]]]:
        """Devuelve las últimas curvas (ws, power_kW, ct) usadas para construir, si existen."""
        return self._last_curves

    def result_data(self) -> Optional[Dict[str, Any]]:
        """
        Diccionario con la info necesaria para construir la turbina desde fuera (AG_dialog).
          - mode: "manual" | "csv"
          - name, diam, hh
          - si mode == "manual": ws, power_kw, (ct opcional)
          - si mode == "csv": path, ws_col, power_col, delimiter, skip_header, (ct_col opcional)
        """
        _debug_print(f"[Energy turbine UI] result_data() -> keys={list(self._result_data.keys()) if self._result_data else None}")
        return self._result_data

    # Evitar cerrar si no se ha creado la WT todavía
    def accept(self):
        if self._wt is None:
            QtWidgets.QMessageBox.warning(
                self, "Sin turbina",
                "Primero pulsa «Crear turbina» en la pestaña correspondiente."
            )
            _debug_print("[Energy turbine UI] accept blocked: turbine not created yet.")
            return
        _debug_print("[Energy turbine UI] accept -> OK.")
        super().accept()
