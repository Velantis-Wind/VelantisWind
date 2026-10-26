# -*- coding: utf-8 -*-
"""
Diálogo minimal para crear turbinas:
- Manual (listas ws/power_kW/ct)
- Desde TXT/CSV (usa TxtSpec + load_curves_from_txt)
- Desde .wtg (curvas tabuladas por densidad, load_wtg + build_wt_from_curve_table)
- Desde .owtg (curvas tabuladas por densidad, load_owtg + build_wt_from_curve_table)
Devuelve un WindTurbines (plural) compatible con PyWake 2.6.7 y expone result_data()
para que AG_dialog pueda reconstruir si lo desea.
"""

from qgis.PyQt import QtWidgets, QtCore
from typing import Optional, List, Tuple, Dict, Any
import os
import math

# Utilidades del módulo turbine.py
from .turbine import CT_ESTIMATED_WARNING, TxtSpec, _error, build_wt_from_curve_table, build_wt_from_manual, load_curves_from_txt
from .turbines.owtg import load_owtg
from .turbines.wtg import WtgFormatError, load_wtg
from .log_text import shown

try:
    from .turbines.library import load_builtin_candidates, load_candidate_curve
except Exception:  # pragma: no cover - package data fallback
    def load_builtin_candidates():
        return tuple()
    def load_candidate_curve(_candidate):
        raise FileNotFoundError("Built-in turbine catalogue is not available")

try:
    from ..i18n import apply_i18n, install_runtime_i18n_patches, mark_translated, tr_text
    from .curve_text_translations import register_curve_text_translations
    register_curve_text_translations()
except Exception:  # pragma: no cover - allows standalone imports during tests
    def apply_i18n(widget):
        return None
    def install_runtime_i18n_patches():
        return None
    def tr_text(text):
        return text
    def mark_translated(widget):
        return None

__all__ = ["CustomTurbineDialog"]


def _debug_print(message: str) -> None:
    """Optional console diagnostics enabled with VELANTISWIND_DEBUG=1."""
    try:
        if os.environ.get("VELANTISWIND_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(message)
    except Exception:  # nosec B110
        pass


def _error_text(exc: Exception) -> str:
    """Texto de un error para mostrarlo: si trae plantilla y datos, se traduce la plantilla y se rellena después."""
    return shown(exc, tr_text) if getattr(exc, "template_item", None) else str(exc)


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
        try:
            out.append(float(token))
        except ValueError:
            raise _error(ValueError, "«{valor}» no es un número.", valor=token) from None
    return out


# Plantillas rápidas para pre-assessment. No son curvas oficiales de fabricante:
# generan una curva genérica editable a partir de geometría + potencia nominal típica.
_FALLBACK_GENERIC_PRESETS: Dict[str, Dict[str, float]] = {
    "Genérica terrestre 2 MW · D90 m": {"diam": 90.0, "hub": 80.0, "rated_kw": 2000.0, "curve_quality": "approximate", "category": "generic_onshore"},
    "Genérica terrestre 3 MW · D120 m": {"diam": 120.0, "hub": 100.0, "rated_kw": 3000.0, "curve_quality": "approximate", "category": "generic_onshore"},
    "Genérica terrestre 5 MW · D165 m": {"diam": 165.0, "hub": 130.0, "rated_kw": 5000.0, "curve_quality": "approximate", "category": "generic_onshore"},
    "Genérica marina 12 MW · D220 m": {"diam": 220.0, "hub": 140.0, "rated_kw": 12000.0, "curve_quality": "approximate", "category": "generic_offshore"},
}


def _catalogue_presets() -> List[Dict[str, Any]]:
    """Load the packaged catalogue, with the legacy seven presets as fallback."""
    try:
        candidates = [dict(item) for item in load_builtin_candidates()]
    except Exception:
        candidates = []
    if candidates:
        return candidates
    return [{"name": label, **data} for label, data in _FALLBACK_GENERIC_PRESETS.items()]


def _generic_curve_from_rated(
    rated_kw: float,
    diameter_m: float = 120.0,
    cut_in: float = 3.0,
    rated_ws: float = 0.0,
    cut_out: float = 25.0,
) -> Tuple[List[float], List[float], List[float]]:
    """Physically plausible fallback for screening; never an OEM curve."""
    rho = 1.225
    area = math.pi * (max(float(diameter_m), 1.0) / 2.0) ** 2
    if rated_ws <= cut_in:
        rated_ws = (max(float(rated_kw), 1.0) * 1000.0 / (0.5 * rho * area * 0.43)) ** (1.0 / 3.0)
        rated_ws = max(8.0, min(13.5, rated_ws))
    cp_target = max(0.25, min(0.47, float(rated_kw) * 1000.0 / (0.5 * rho * area * rated_ws ** 3)))
    ct_base = max(0.72, min(0.84, 0.78 + (cp_target - 0.40) * 0.45))
    ws = [round(i * 0.5, 1) for i in range(61)]
    power: List[float] = []
    ct: List[float] = []
    for w in ws:
        if w < cut_in or w > cut_out:
            p = 0.0
            c = 0.0
        else:
            ramp = max(0.0, min(1.0, (w - cut_in) / 2.0))
            smooth = ramp * ramp * (3.0 - 2.0 * ramp)
            cp = cp_target * smooth
            p = min(float(rated_kw), 0.5 * rho * area * cp * w ** 3 / 1000.0)
            if w >= rated_ws:
                p = float(rated_kw)
            ct_ramp = max(0.0, min(1.0, (w - cut_in)))
            ct_smooth = ct_ramp * ct_ramp * (3.0 - 2.0 * ct_ramp)
            c = ct_base * ct_smooth
            if w > rated_ws:
                c = max(0.04, ct_base * (rated_ws / w) ** 2.5)
        power.append(round(p, 3))
        ct.append(round(max(0.0, min(1.0, c)), 4))
    return ws, power, ct


def _fmt_list(vals: List[float]) -> str:
    return " ".join((f"{float(v):.8f}".rstrip("0").rstrip(".") for v in vals))


_GENERIC_CATEGORIES = {"generic_onshore", "generic_offshore"}
# Frases en español de los textos del catálogo que van junto a nombres propios (fabricantes, modelos, fuentes): se
# traducen solas, para que los nombres no pasen por el traductor.
_CATALOGUE_PHRASES = (
    "aproximación por ficha pública", "ficha técnica pública", "aerogenerador de referencia", "caso de referencia",
)


def _catalogue_text(data: Dict[str, Any], text: str) -> str:
    """Un texto del catálogo en el idioma activo: entero si es de una clase genérica, que no lleva nombres propios; si
    no, solo sus frases en español."""
    if str(data.get("category") or "") in _GENERIC_CATEGORIES:
        return tr_text(text)
    for phrase in _CATALOGUE_PHRASES:
        text = text.replace(phrase, tr_text(phrase))
    return text


def _candidate_display_label(data: Dict[str, Any]) -> str:
    quality = str(data.get("curve_quality") or "approximate")
    category = str(data.get("category") or "")
    if quality == "approximate" and category in _GENERIC_CATEGORIES:
        prefix = tr_text("Genérica terrestre") if category == "generic_onshore" else tr_text("Genérica marina")
        mw = float(data.get("rated_kw", 0.0) or 0.0) / 1000.0
        diam = float(data.get("diam", data.get("diameter_m", 0.0)) or 0.0)
        return f"{prefix} {mw:g} MW · D{diam:g} m"
    return _catalogue_text(data, str(data.get("name") or data.get("display_name") or "")) or tr_text("Turbina")


def _same_curve(a: Tuple[List[float], List[float], List[float]], b: Tuple[List[float], List[float], List[float]], tol: float = 1e-7) -> bool:
    try:
        return all(len(x) == len(y) and all(abs(float(i) - float(j)) <= tol for i, j in zip(x, y)) for x, y in zip(a, b))
    except Exception:
        return False


class _HLine(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


class CustomTurbineDialog(QtWidgets.QDialog):
    """Diálogo sin .ui que permite definir una turbina y recuperar sus datos."""

    # Lo que define la turbina de cada pestaña, con su rótulo: (modo, pestaña, ((control, rótulo), ...)).
    _TAB_INPUTS = (
        ("manual", "Manual", (
            ("ed_name_m", "Nombre:"), ("sp_diam_m", "Diámetro rotor:"), ("sp_hub_m", "Altura buje:"),
            ("sp_spacing_long_m", "Separación longitudinal del modelo:"), ("sp_spacing_trans_m", "Separación transversal del modelo:"),
            ("te_ws", "Velocidad del viento (m/s):"), ("te_power", "Potencia (kW):"), ("te_ct", "CT (0–1,2):"),
        )),
        ("csv", "TXT/CSV", (
            ("ed_name_c", "Nombre:"), ("sp_diam_c", "Diámetro rotor:"), ("sp_hub_c", "Altura buje:"),
            ("sp_spacing_long_c", "Separación longitudinal del modelo:"), ("sp_spacing_trans_c", "Separación transversal del modelo:"),
            ("ed_path", "Fichero TXT/CSV:"), ("cb_delim", "Delimitador:"), ("sp_ws_col", "Columna ws (contando desde 0):"),
            ("sp_pw_col", "Columna potencia kW (contando desde 0):"), ("chk_ct_col", "Incluir columna CT"),
            ("sp_ct_col", "Incluir columna CT"), ("sp_skip", "Filas de cabecera a saltar:"),
        )),
        ("wtg", ".wtg", (
            ("ed_path_w", "Fichero .wtg:"), ("ed_name_w", "Nombre:"), ("sp_diam_w", "Diámetro rotor:"),
            ("sp_hub_w", "Altura buje:"),
            ("sp_spacing_long_w", "Separación longitudinal del modelo:"), ("sp_spacing_trans_w", "Separación transversal del modelo:"),
        )),
        ("owtg", ".owtg", (
            ("ed_path_o", "Fichero .owtg:"), ("ed_name_o", "Nombre:"), ("sp_diam_o", "Diámetro rotor:"),
            ("sp_hub_o", "Altura buje:"),
            ("sp_spacing_long_o", "Separación longitudinal del modelo:"), ("sp_spacing_trans_o", "Separación transversal del modelo:"),
        )),
    )

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
        self._built_inputs = None  # type: Optional[Dict[str, Dict[str, Any]]]
        self._active_catalogue_candidate = None  # type: Optional[Dict[str, Any]]
        self._active_catalogue_curve = None  # type: Optional[Tuple[List[float], List[float], List[float]]]

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
        except Exception:  # nosec B110
            pass

        self.ed_name_m = QtWidgets.QLineEdit(tr_text("Turbina personalizada"))
        self.ed_name_m.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.sp_diam_m = QtWidgets.QDoubleSpinBox()
        self.sp_diam_m.setRange(1.0, 500.0)
        self.sp_diam_m.setValue(120.0)
        self.sp_diam_m.setSuffix(" m")

        self.sp_hub_m = QtWidgets.QDoubleSpinBox()
        self.sp_hub_m.setRange(1.0, 300.0)
        self.sp_hub_m.setValue(90.0)
        self.sp_hub_m.setSuffix(" m")

        self.sp_spacing_long_m = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_long_m.setRange(0.5, 30.0)
        self.sp_spacing_long_m.setDecimals(2)
        self.sp_spacing_long_m.setSingleStep(0.5)
        self.sp_spacing_long_m.setValue(7.0)
        self.sp_spacing_long_m.setSuffix(" · D")
        self.sp_spacing_long_m.setToolTip(
            "Separación longitudinal inicial de este modelo, expresada en diámetros de rotor. "
            "Se guarda con el modelo y controla el eje mayor de sus envolventes."
        )

        self.sp_spacing_trans_m = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_trans_m.setRange(0.5, 30.0)
        self.sp_spacing_trans_m.setDecimals(2)
        self.sp_spacing_trans_m.setSingleStep(0.5)
        self.sp_spacing_trans_m.setValue(4.0)
        self.sp_spacing_trans_m.setSuffix(" · D")
        self.sp_spacing_trans_m.setToolTip(
            "Separación transversal inicial de este modelo, expresada en diámetros de rotor. "
            "Se guarda con el modelo y controla el eje menor de sus envolventes."
        )

        self.te_ws = QtWidgets.QPlainTextEdit()
        self.te_power = QtWidgets.QPlainTextEdit()
        self.te_ct = QtWidgets.QPlainTextEdit()
        self.te_ct.setPlaceholderText(tr_text("(opcional)"))
        for _te in (self.te_ws, self.te_power, self.te_ct):
            _tune_plain_edit(_te)

        # Placeholders rápidos (apply_i18n no traduce los de QPlainTextEdit)
        self.te_ws.setPlaceholderText(tr_text("Ej.: 3 4 5 6 7 8 9 10 11 12 13 14"))
        self.te_power.setPlaceholderText(tr_text("Potencia en kW, misma longitud que ws"))

        self.cb_generic_preset = QtWidgets.QComboBox()
        self.cb_generic_preset.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_generic_preset.setMinimumContentsLength(30)
        self.cb_generic_preset.setEditable(True)
        try:
            self.cb_generic_preset.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        except Exception:  # nosec B110
            pass
        self.cb_generic_preset.addItem(tr_text("Sin plantilla"), None)
        catalogue = _catalogue_presets()
        public_items = [d for d in catalogue if str(d.get("curve_quality") or "") == "public_reference"]
        spec_items = [d for d in catalogue if str(d.get("curve_quality") or "") == "spec_based_approximation"]
        approximate_items = [
            d for d in catalogue
            if str(d.get("curve_quality") or "") not in {"public_reference", "spec_based_approximation"}
        ]
        for data in public_items:
            self.cb_generic_preset.addItem(f"{tr_text('[Referencia pública]')} {_candidate_display_label(data)}", data)
        if public_items and (spec_items or approximate_items):
            self.cb_generic_preset.insertSeparator(self.cb_generic_preset.count())
        for data in spec_items:
            self.cb_generic_preset.addItem(f"{tr_text('[Aprox. basada en ficha]')} {_candidate_display_label(data)}", data)
        if spec_items and approximate_items:
            self.cb_generic_preset.insertSeparator(self.cb_generic_preset.count())
        for data in approximate_items:
            self.cb_generic_preset.addItem(f"{tr_text('[Aproximada genérica]')} {_candidate_display_label(data)}", data)
        try:
            completer = self.cb_generic_preset.completer()
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            self.cb_generic_preset.lineEdit().setPlaceholderText(tr_text("Buscar referencia o clase de turbina…"))
        except Exception:  # nosec B110
            pass
        self.cb_generic_preset.setToolTip(tr_text(
            "El catálogo distingue referencias públicas, aproximaciones ancladas a fichas "
            "técnicas y clases genéricas. Ninguna aproximación es una curva OEM o certificada."
        ))
        self.cb_generic_preset.currentIndexChanged.connect(self._apply_generic_preset)

        note_preset = QtWidgets.QLabel(tr_text(
            "El catálogo incluye referencias abiertas, aproximaciones basadas en especificaciones "
            "públicas y clases genéricas. Comprueba la procedencia antes de una entrega técnica."
        ))
        note_preset.setWordWrap(True)
        note_preset.setStyleSheet("color: #666; font-size: 11px;")

        self.lbl_curve_provenance = QtWidgets.QLabel(tr_text(
            "Selecciona una turbina para ver la calidad y la fuente de la curva."
        ))
        self.lbl_curve_provenance.setWordWrap(True)
        self.lbl_curve_provenance.setTextFormat(QtCore.Qt.RichText)
        self.lbl_curve_provenance.setStyleSheet("padding: 5px; border: 1px solid #bbb; border-radius: 3px;")

        f_man.addRow("Catálogo de turbinas:", self.cb_generic_preset)
        f_man.addRow("", note_preset)
        f_man.addRow(tr_text("Calidad y procedencia:"), self.lbl_curve_provenance)
        f_man.addRow("Nombre:", self.ed_name_m)
        f_man.addRow("Diámetro rotor:", self.sp_diam_m)
        f_man.addRow("Altura buje:", self.sp_hub_m)
        f_man.addRow("Separación longitudinal del modelo:", self.sp_spacing_long_m)
        f_man.addRow("Separación transversal del modelo:", self.sp_spacing_trans_m)
        f_man.addRow(_HLine())
        f_man.addRow("Velocidad del viento (m/s):", self.te_ws)
        f_man.addRow("Potencia (kW):", self.te_power)
        f_man.addRow("CT (0–1,2):", self.te_ct)

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
        except Exception:  # nosec B110
            pass

        self.ed_name_c = QtWidgets.QLineEdit(tr_text("Turbina personalizada (CSV)"))
        self.sp_diam_c = QtWidgets.QDoubleSpinBox()
        self.sp_diam_c.setRange(1.0, 500.0)
        self.sp_diam_c.setValue(120.0)
        self.sp_diam_c.setSuffix(" m")

        self.sp_hub_c = QtWidgets.QDoubleSpinBox()
        self.sp_hub_c.setRange(1.0, 300.0)
        self.sp_hub_c.setValue(90.0)
        self.sp_hub_c.setSuffix(" m")

        self.sp_spacing_long_c = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_long_c.setRange(0.5, 30.0)
        self.sp_spacing_long_c.setDecimals(2)
        self.sp_spacing_long_c.setSingleStep(0.5)
        self.sp_spacing_long_c.setValue(7.0)
        self.sp_spacing_long_c.setSuffix(" · D")
        self.sp_spacing_long_c.setToolTip(
            "Separación longitudinal inicial de este modelo, expresada en diámetros de rotor."
        )

        self.sp_spacing_trans_c = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_trans_c.setRange(0.5, 30.0)
        self.sp_spacing_trans_c.setDecimals(2)
        self.sp_spacing_trans_c.setSingleStep(0.5)
        self.sp_spacing_trans_c.setValue(4.0)
        self.sp_spacing_trans_c.setSuffix(" · D")
        self.sp_spacing_trans_c.setToolTip(
            "Separación transversal inicial de este modelo, expresada en diámetros de rotor."
        )

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
        self.cb_delim.setToolTip(tr_text("Espacio ( ): admite uno o varios espacios y tabuladores; ignora la sangría."))
        self.sp_ws_col = QtWidgets.QSpinBox(); self.sp_ws_col.setRange(0, 99); self.sp_ws_col.setValue(0)
        self.sp_pw_col = QtWidgets.QSpinBox(); self.sp_pw_col.setRange(0, 99); self.sp_pw_col.setValue(1)
        self.chk_ct_col = QtWidgets.QCheckBox("Incluir columna CT")
        self.sp_ct_col = QtWidgets.QSpinBox(); self.sp_ct_col.setRange(0, 99); self.sp_ct_col.setEnabled(False)
        self.chk_ct_col.toggled.connect(self.sp_ct_col.setEnabled)

        self.sp_skip = QtWidgets.QSpinBox(); self.sp_skip.setRange(0, 100); self.sp_skip.setValue(1)

        f_csv.addRow("Nombre:", self.ed_name_c)
        f_csv.addRow("Diámetro rotor:", self.sp_diam_c)
        f_csv.addRow("Altura buje:", self.sp_hub_c)
        f_csv.addRow("Separación longitudinal del modelo:", self.sp_spacing_long_c)
        f_csv.addRow("Separación transversal del modelo:", self.sp_spacing_trans_c)
        f_csv.addRow(_HLine())
        f_csv.addRow("Fichero TXT/CSV:", path_wrap)
        f_csv.addRow("Delimitador:", self.cb_delim)
        f_csv.addRow("Columna ws (contando desde 0):", self.sp_ws_col)
        f_csv.addRow("Columna potencia kW (contando desde 0):", self.sp_pw_col)
        f_csv.addRow(self.chk_ct_col, self.sp_ct_col)
        f_csv.addRow("Filas de cabecera a saltar:", self.sp_skip)

        btn_build_c = QtWidgets.QPushButton("Crear turbina (TXT/CSV)")
        btn_build_c.clicked.connect(self._on_build_csv)
        f_csv.addRow(btn_build_c)

        # ---------- TAB: .wtg ----------
        # Curvas tabuladas por densidad: cada aerogenerador usará después la curva
        # de la densidad del aire en la cota de su buje. La geometría sale del fichero.
        w_wtg = QtWidgets.QWidget()
        f_wtg = QtWidgets.QFormLayout(w_wtg)
        f_wtg.setContentsMargins(10, 10, 10, 10)
        f_wtg.setSpacing(8)
        try:
            f_wtg.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            f_wtg.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            f_wtg.setFormAlignment(QtCore.Qt.AlignTop)
        except Exception:  # nosec B110
            pass

        self._wtg_table = None
        self._wtg_geometry_edited = False
        self._wtg_syncing = False

        h_path_w = QtWidgets.QHBoxLayout()
        h_path_w.setContentsMargins(0, 0, 0, 0)
        self.ed_path_w = QtWidgets.QLineEdit()
        self.ed_path_w.setPlaceholderText("Selecciona un fichero .wtg…")
        self.ed_path_w.editingFinished.connect(self._on_wtg_path_edited)
        # Mientras se escribe otra ruta, Aceptar no puede entregar la turbina del fichero anterior.
        self.ed_path_w.textChanged.connect(lambda *_: self._discard_wtg_turbine())
        btn_browse_w = QtWidgets.QPushButton("Examinar…")
        btn_browse_w.clicked.connect(self._browse_wtg)
        h_path_w.addWidget(self.ed_path_w, 1)
        h_path_w.addWidget(btn_browse_w, 0)
        path_wrap_w = QtWidgets.QWidget()
        path_wrap_w.setLayout(h_path_w)

        self.lbl_wtg_info = QtWidgets.QLabel("El diámetro, la altura de buje y las curvas se leen del propio fichero.")
        self.lbl_wtg_info.setWordWrap(True)
        self.lbl_wtg_info.setStyleSheet("color: #666;")

        self.ed_name_w = QtWidgets.QLineEdit("")
        self.sp_diam_w = QtWidgets.QDoubleSpinBox()
        self.sp_diam_w.setRange(1.0, 500.0)
        self.sp_diam_w.setValue(120.0)
        self.sp_diam_w.setSuffix(" m")
        self.sp_hub_w = QtWidgets.QDoubleSpinBox()
        self.sp_hub_w.setRange(1.0, 300.0)
        self.sp_hub_w.setValue(90.0)
        self.sp_hub_w.setSuffix(" m")
        self.sp_hub_w.setToolTip(
            "Se rellena con la altura del fichero. Cámbiala solo si el proyecto usa otra torre: la curva no "
            "cambia, pero sí la cota a la que se evalúan el viento y la densidad del aire."
        )
        self.sp_diam_w.valueChanged.connect(self._on_wtg_geometry_edited)
        self.sp_hub_w.valueChanged.connect(self._on_wtg_geometry_edited)

        self.sp_spacing_long_w = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_long_w.setRange(0.5, 30.0)
        self.sp_spacing_long_w.setDecimals(2)
        self.sp_spacing_long_w.setSingleStep(0.5)
        self.sp_spacing_long_w.setValue(7.0)
        self.sp_spacing_long_w.setSuffix(" · D")
        self.sp_spacing_trans_w = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_trans_w.setRange(0.5, 30.0)
        self.sp_spacing_trans_w.setDecimals(2)
        self.sp_spacing_trans_w.setSingleStep(0.5)
        self.sp_spacing_trans_w.setValue(4.0)
        self.sp_spacing_trans_w.setSuffix(" · D")

        f_wtg.addRow("Fichero .wtg:", path_wrap_w)
        f_wtg.addRow("", self.lbl_wtg_info)
        f_wtg.addRow(_HLine())
        f_wtg.addRow("Nombre:", self.ed_name_w)
        f_wtg.addRow("Diámetro rotor:", self.sp_diam_w)
        f_wtg.addRow("Altura buje:", self.sp_hub_w)
        f_wtg.addRow("Separación longitudinal del modelo:", self.sp_spacing_long_w)
        f_wtg.addRow("Separación transversal del modelo:", self.sp_spacing_trans_w)

        btn_build_w = QtWidgets.QPushButton("Crear turbina (.wtg)")
        btn_build_w.clicked.connect(self._on_build_wtg)
        f_wtg.addRow(btn_build_w)

        # ---------- TAB: .owtg ----------
        # La misma forma y las mismas garantías que la pestaña .wtg.
        w_owtg = QtWidgets.QWidget()
        f_owtg = QtWidgets.QFormLayout(w_owtg)
        f_owtg.setContentsMargins(10, 10, 10, 10)
        f_owtg.setSpacing(8)
        try:
            f_owtg.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            f_owtg.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            f_owtg.setFormAlignment(QtCore.Qt.AlignTop)
        except Exception:  # nosec B110
            pass

        self._owtg_table = None
        self._owtg_geometry_edited = False
        self._owtg_syncing = False

        h_path_o = QtWidgets.QHBoxLayout()
        h_path_o.setContentsMargins(0, 0, 0, 0)
        self.ed_path_o = QtWidgets.QLineEdit()
        self.ed_path_o.setPlaceholderText("Selecciona un fichero .owtg…")
        self.ed_path_o.editingFinished.connect(self._on_owtg_path_edited)
        # Mientras se escribe otra ruta, Aceptar no puede entregar la turbina del fichero anterior.
        self.ed_path_o.textChanged.connect(lambda *_: self._discard_owtg_turbine())
        btn_browse_o = QtWidgets.QPushButton("Examinar…")
        btn_browse_o.clicked.connect(self._browse_owtg)
        h_path_o.addWidget(self.ed_path_o, 1)
        h_path_o.addWidget(btn_browse_o, 0)
        path_wrap_o = QtWidgets.QWidget()
        path_wrap_o.setLayout(h_path_o)

        self.lbl_owtg_info = QtWidgets.QLabel("El diámetro, la altura de buje y las curvas se leen del propio fichero.")
        self.lbl_owtg_info.setWordWrap(True)
        self.lbl_owtg_info.setStyleSheet("color: #666;")

        self.ed_name_o = QtWidgets.QLineEdit("")
        self.sp_diam_o = QtWidgets.QDoubleSpinBox()
        self.sp_diam_o.setRange(1.0, 500.0)
        self.sp_diam_o.setValue(120.0)
        self.sp_diam_o.setSuffix(" m")
        self.sp_hub_o = QtWidgets.QDoubleSpinBox()
        self.sp_hub_o.setRange(1.0, 300.0)
        self.sp_hub_o.setValue(90.0)
        self.sp_hub_o.setSuffix(" m")
        self.sp_hub_o.setToolTip(
            "Se rellena con la altura del fichero. Cámbiala solo si el proyecto usa otra torre: la curva no "
            "cambia, pero sí la cota a la que se evalúan el viento y la densidad del aire."
        )
        self.sp_diam_o.valueChanged.connect(self._on_owtg_geometry_edited)
        self.sp_hub_o.valueChanged.connect(self._on_owtg_geometry_edited)

        self.sp_spacing_long_o = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_long_o.setRange(0.5, 30.0)
        self.sp_spacing_long_o.setDecimals(2)
        self.sp_spacing_long_o.setSingleStep(0.5)
        self.sp_spacing_long_o.setValue(7.0)
        self.sp_spacing_long_o.setSuffix(" · D")
        self.sp_spacing_trans_o = QtWidgets.QDoubleSpinBox()
        self.sp_spacing_trans_o.setRange(0.5, 30.0)
        self.sp_spacing_trans_o.setDecimals(2)
        self.sp_spacing_trans_o.setSingleStep(0.5)
        self.sp_spacing_trans_o.setValue(4.0)
        self.sp_spacing_trans_o.setSuffix(" · D")

        f_owtg.addRow("Fichero .owtg:", path_wrap_o)
        f_owtg.addRow("", self.lbl_owtg_info)
        f_owtg.addRow(_HLine())
        f_owtg.addRow("Nombre:", self.ed_name_o)
        f_owtg.addRow("Diámetro rotor:", self.sp_diam_o)
        f_owtg.addRow("Altura buje:", self.sp_hub_o)
        f_owtg.addRow("Separación longitudinal del modelo:", self.sp_spacing_long_o)
        f_owtg.addRow("Separación transversal del modelo:", self.sp_spacing_trans_o)

        btn_build_o = QtWidgets.QPushButton("Crear turbina (.owtg)")
        btn_build_o.clicked.connect(self._on_build_owtg)
        f_owtg.addRow(btn_build_o)

        tabs.addTab(_make_scroll(w_manual), "Manual")
        tabs.addTab(_make_scroll(w_csv), "TXT/CSV")
        tabs.addTab(_make_scroll(w_wtg), ".wtg")
        tabs.addTab(_make_scroll(w_owtg), ".owtg")

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

        # Las etiquetas del catálogo ya están traducidas y contienen nombres propios.
        mark_translated(self.cb_generic_preset)
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
        except Exception:  # nosec B110
            pass

    def _apply_generic_preset(self) -> None:
        """Load a packaged curve and expose its quality/provenance clearly."""
        try:
            data = self.cb_generic_preset.currentData()
        except Exception:
            data = None
        if not isinstance(data, dict):
            self._active_catalogue_candidate = None
            self._active_catalogue_curve = None
            try:
                self.lbl_curve_provenance.setText(tr_text("Selecciona una turbina para ver la calidad y la fuente de la curva."))
                self.lbl_curve_provenance.setToolTip("")
            except Exception:  # nosec B110
                pass
            return
        try:
            # El nombre guardado no depende del idioma ni incluye las descripciones de calidad.
            label = " · ".join(
                part for part in str(data.get("name") or data.get("display_name") or data.get("candidate_id"))
                .split(" · ") if part not in _CATALOGUE_PHRASES
            )
            rated_kw = float(data.get("rated_kw", 0.0) or 0.0)
            try:
                ws, power_kw, ct = load_candidate_curve(data)
            except Exception:
                ws, power_kw, ct = _generic_curve_from_rated(
                    rated_kw,
                    diameter_m=float(data.get("diam", 120.0) or 120.0),
                    cut_in=float(data.get("cut_in", 3.0) or 3.0),
                    rated_ws=float(data.get("rated_ws", 0.0) or 0.0),
                    cut_out=float(data.get("cut_out", 25.0) or 25.0),
                )
            quality = str(data.get("curve_quality") or "approximate")
            # El nombre es el del catálogo; la calidad se muestra aparte y se guarda en curve_quality.
            self.ed_name_m.setText(label)
            self.sp_diam_m.setValue(float(data.get("diam", 120.0)))
            self.sp_hub_m.setValue(float(data.get("hub", 90.0)))
            self.sp_spacing_long_m.setValue(float(data.get("spacing_long_d", 7.0)))
            self.sp_spacing_trans_m.setValue(float(data.get("spacing_trans_d", 4.0)))
            self.te_ws.setPlainText(_fmt_list(ws))
            self.te_power.setPlainText(_fmt_list(power_kw))
            self.te_ct.setPlainText(_fmt_list(ct))
            self._active_catalogue_candidate = dict(data)
            self._active_catalogue_curve = (list(ws), list(power_kw), list(ct))

            source = _catalogue_text(data, str(data.get("source_name") or "")) or tr_text("Sin fuente externa")
            if quality == "public_reference":
                title = tr_text("Referencia pública")
                warning = tr_text("Referencia pública/abierta. Revisa la fuente y sus condiciones antes de una entrega técnica.")
            elif quality == "spec_based_approximation":
                title = tr_text("Aproximación basada en ficha pública")
                warning = tr_text(
                    "La geometría y los puntos técnicos indicados proceden de la fuente pública; "
                    "la curva de potencia y CT entre esos puntos es paramétrica. No es OEM ni certificada."
                )
            else:
                title = tr_text("Curva aproximada genérica")
                warning = tr_text("Aproximación paramétrica de Velantis. No es una curva OEM ni certificada.")
            self.lbl_curve_provenance.setText(f"<b>{title}</b><br>{tr_text('Fuente:')} {source}<br>{warning}")
            self.lbl_curve_provenance.setToolTip(
                str(data.get("source_url") or "") or _catalogue_text(data, str(data.get("source_note") or ""))
            )
            mark_translated(self.lbl_curve_provenance)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, tr_text("Catálogo de turbinas"), f"{tr_text('No se pudo aplicar el candidato seleccionado:')}\n{_error_text(e)}"
            )


    # -------------------- Handlers --------------------
    def _browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr_text("Abrir TXT/CSV"), os.path.expanduser("~"),
            tr_text("TXT/CSV (*.txt *.csv);;Todos (*.*)")
        )
        if path:
            self.ed_path.setText(path)
            _debug_print(f"[Energy turbine UI] Selected file: {path}")

    def _delimiter(self) -> str:
        idx = self.cb_delim.currentIndex()
        return {0: "\t", 1: ",", 2: ";", 3: " "}.get(idx, "\t")

    def _discard_turbine(self) -> None:
        """Cada intento de crear una turbina empieza sin la anterior y, si falla en cualquier punto,
        acaba sin turbina: Aceptar no puede entregar una que no es la que se pidió."""
        self._wt = None
        self._result_data = None
        self._last_curves = None
        self._built_inputs = None

    @staticmethod
    def _input_value(widget):
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentIndex()
        if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            return widget.value()
        if isinstance(widget, QtWidgets.QPlainTextEdit):
            # Una lista de números vale por sus números, no por cómo se separan; si no se puede leer o
            # lleva nan (que no es igual a sí mismo), por su texto.
            try:
                values = tuple(_parse_num_list(widget.toPlainText()))
            except ValueError:
                values = None
            if values is not None and all(v == v for v in values):
                return values
            return widget.toPlainText().strip()
        return widget.text().strip()

    def _input_values(self) -> Dict[str, Dict[str, Any]]:
        """Los datos de todas las pestañas, para compararlos con los de la turbina creada."""
        return {mode: {attr: self._input_value(getattr(self, attr)) for attr, _ in inputs}
                for mode, _, inputs in self._TAB_INPUTS}

    def _changed_inputs(self) -> List[Tuple[str, str, List[str]]]:
        """(modo, pestaña, rótulos) de lo que ha cambiado desde que se creó la turbina; primero su pestaña."""
        if not self._built_inputs or not isinstance(self._result_data, dict):
            return []
        now = self._input_values()
        built = self._result_data.get("mode")
        changed = []
        for mode, tab, inputs in sorted(self._TAB_INPUTS, key=lambda item: item[0] != built):
            labels: List[str] = []
            for attr, label in inputs:
                if now[mode][attr] != self._built_inputs[mode][attr] and label not in labels:
                    labels.append(label)
            if labels:
                changed.append((mode, tab, labels))
        return changed

    def _changed_inputs_text(self, changed) -> str:
        """El aviso de Aceptar con datos cambiados desde que se creó la turbina."""
        built = self._result_data.get("mode")
        tabs = {mode: tab for mode, tab, _ in self._TAB_INPUTS}
        parts = []
        for mode, tab, labels in changed:
            data = ", ".join(tr_text("«{dato}»").format(dato=tr_text(label).rstrip(" :")) for label in labels)
            if mode == built:
                parts.append(tr_text("Has cambiado {datos} desde que creaste la turbina.").format(datos=data))
            else:
                parts.append(tr_text(
                    "En la pestaña {pestana} has cambiado {datos}, pero la turbina creada es la de la pestaña {creada}."
                ).format(pestana=tr_text(tab), datos=data, creada=tr_text(tabs[built])))
        parts.append(tr_text(
            "Si continúas, se usará la última turbina que creaste, sin esos cambios. "
            "Para aplicarlos, vuelve y pulsa «Crear turbina»."
        ))
        return " ".join(parts)

    def _ask_continue(self, title: str, text: str) -> bool:
        """Pregunta con Continuar y Volver (por defecto); True si se elige Continuar."""
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, title, text, parent=self)
        go_on = box.addButton(tr_text("Continuar"), QtWidgets.QMessageBox.AcceptRole)
        back = box.addButton(tr_text("Volver"), QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(back)
        box.setEscapeButton(back)
        box.exec_()
        return box.clickedButton() is go_on

    def _on_build_manual(self):
        self._discard_turbine()
        try:
            name = self.ed_name_m.text().strip() or tr_text("Turbina personalizada")
            d = float(self.sp_diam_m.value())
            h = float(self.sp_hub_m.value())
            spacing_long_d = float(self.sp_spacing_long_m.value())
            spacing_trans_d = float(self.sp_spacing_trans_m.value())
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
                "spacing_long_d": spacing_long_d,
                "spacing_trans_d": spacing_trans_d,
                "ws": ws,
                "power_kw": pw_kw,
                "ct": ct,
                "ct_estimated": ct is None,
                # Potencia nominal pre-calculada para que aep_compute no tenga que
                # inferirla desde wt.power() (camino frágil entre versiones de PyWake).
                "p_rated_kw": float(max(pw_kw)) if pw_kw else 0.0,
            }
            candidate = self._active_catalogue_candidate if isinstance(self._active_catalogue_candidate, dict) else None
            current_curve = (list(ws), list(pw_kw), list(ct) if ct else [])
            geometry_unchanged = bool(
                candidate
                and abs(d - float(candidate.get("diam", d) or d)) <= 1e-6
                and abs(h - float(candidate.get("hub", h) or h)) <= 1e-6
            )
            unchanged = bool(
                candidate
                and geometry_unchanged
                and self._active_catalogue_curve
                and _same_curve(current_curve, self._active_catalogue_curve)
            )
            if candidate:
                self._result_data.update({
                    "candidate_id": str(candidate.get("candidate_id") or ""),
                    "curve_kind": str(candidate.get("curve_kind") or ""),
                    "curve_quality": str(candidate.get("curve_quality") or "approximate") if unchanged else "user_edited",
                    "curve_source": str(candidate.get("source_name") or ""),
                    "curve_source_url": str(candidate.get("source_url") or ""),
                    "curve_source_note": str(candidate.get("source_note") or ""),
                })
            else:
                self._result_data.update({"curve_kind": "user_defined", "curve_quality": "user_defined"})

            message = [tr_text("Turbina creada (manual). Pulsa Aceptar para usarla.")]
            if ct is None:
                message.append(tr_text(CT_ESTIMATED_WARNING))
            self._built_inputs = self._input_values()
            QtWidgets.QMessageBox.information(self, tr_text("Listo"), "\n\n".join(message))
            _debug_print("[Energy turbine UI] Manual turbine created and stored.")
        except Exception as e:
            self._discard_turbine()
            QtWidgets.QMessageBox.critical(self, tr_text("Error creando turbina"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_manual: {e}")

    def _on_build_csv(self):
        self._discard_turbine()
        try:
            path = self.ed_path.text().strip()
            if not path or not os.path.exists(path):
                raise FileNotFoundError(tr_text("Selecciona un archivo TXT/CSV válido."))

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

            name = self.ed_name_c.text().strip() or tr_text("Turbina personalizada (CSV)")
            d = float(self.sp_diam_c.value())
            h = float(self.sp_hub_c.value())
            spacing_long_d = float(self.sp_spacing_long_c.value())
            spacing_trans_d = float(self.sp_spacing_trans_c.value())

            _debug_print(f"[Energy turbine UI] CSV curve: name={name} D={d} HH={h} npts={len(ws)}")

            wt = build_wt_from_manual(name, d, h, ws, power_kW, ct)
            self._wt = wt
            self._last_curves = (ws, power_kW, ct)

            self._result_data = {
                "mode": "csv",
                "name": name,
                "diam": d,
                "hh": h,
                "spacing_long_d": spacing_long_d,
                "spacing_trans_d": spacing_trans_d,
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
                "ct_estimated": spec.ct_col is None,
                "p_rated_kw": float(max(power_kW)) if power_kW else 0.0,
                "curve_kind": "user_imported",
                "curve_quality": "user_defined",
                "curve_source": str(path),
                "curve_source_url": "",
            }

            message = [tr_text("Turbina creada desde TXT/CSV. Pulsa Aceptar para usarla.")]
            if spec.ct_col is None:
                message.append(tr_text(CT_ESTIMATED_WARNING))
            self._built_inputs = self._input_values()
            QtWidgets.QMessageBox.information(self, tr_text("Listo"), "\n\n".join(message))
            _debug_print("[Energy turbine UI] CSV turbine created and stored.")
        except Exception as e:
            self._discard_turbine()
            QtWidgets.QMessageBox.critical(self, tr_text("Error leyendo TXT/CSV"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_csv: {e}")

    def _browse_wtg(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr_text("Abrir fichero .wtg"), os.path.expanduser("~"),
            tr_text("Turbina .wtg (*.wtg);;Todos (*.*)")
        )
        if path:
            self.ed_path_w.setText(path)
            self._load_wtg(path)

    def _wtg_is_loaded(self, path: str) -> bool:
        table = self._wtg_table
        return table is not None and str(table.source_path) == os.path.abspath(path)

    def _on_wtg_path_edited(self) -> None:
        """Una ruta escrita o pegada se lee igual que la del selector, con su geometría."""
        path = self.ed_path_w.text().strip()
        if self._wtg_is_loaded(path):
            return
        self._discard_wtg_turbine()
        if path and os.path.isfile(path):
            self._load_wtg(path)

    def _discard_wtg_turbine(self) -> None:
        """Otro fichero (o ninguno) descarta la turbina construida desde la pestaña .wtg:
        Aceptar no puede entregar una turbina distinta de la que muestra la pestaña."""
        if isinstance(self._result_data, dict) and self._result_data.get("mode") == "wtg":
            self._wt = None
            self._result_data = None
            self._last_curves = None

    def _on_wtg_geometry_edited(self, *_args) -> None:
        if not self._wtg_syncing:
            self._wtg_geometry_edited = True

    def _read_wtg(self, path: str):
        """Lee el fichero; si sugiere varias alturas de buje, pide elegir una."""
        try:
            return load_wtg(path)
        except WtgFormatError as exc:
            heights = getattr(exc, "suggested_heights", None)
            if not heights:
                raise
            labels = [f"{h:g} m" for h in heights]
            choice, ok = QtWidgets.QInputDialog.getItem(
                self, tr_text("Altura de buje"),
                tr_text("El fichero sugiere varias alturas de buje. Elige la del proyecto:"), labels, 0, False,
            )
            if not ok:
                raise
            return load_wtg(path, hub_height_m=heights[labels.index(choice)])

    def _load_wtg(self, path: str):
        """Lee el fichero, muestra lo que contiene y toma de él nombre, diámetro y altura."""
        self._discard_wtg_turbine()
        try:
            table = self._read_wtg(path)
            # Un control no admite un valor fuera de su rango: lo recortaría en silencio.
            if not (self.sp_diam_w.minimum() <= table.diameter_m <= self.sp_diam_w.maximum()
                    and self.sp_hub_w.minimum() <= table.hub_height_m <= self.sp_hub_w.maximum()):
                raise ValueError(tr_text(
                    "La geometría del fichero (D={diam} m, HH={hub} m) no cabe en los controles del diálogo "
                    "(D hasta {diam_max} m, HH hasta {hub_max} m)."
                ).format(
                    diam=f"{table.diameter_m:g}", hub=f"{table.hub_height_m:g}",
                    diam_max=f"{self.sp_diam_w.maximum():g}", hub_max=f"{self.sp_hub_w.maximum():g}",
                ))
        except Exception as e:
            self._wtg_table = None
            self.lbl_wtg_info.setText(tr_text("No se pudo leer el fichero .wtg."))
            QtWidgets.QMessageBox.critical(self, tr_text("Fichero .wtg"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _load_wtg: {e}")
            return None

        self._wtg_table = table
        self._wtg_syncing = True
        try:
            self.ed_name_w.setText(table.name)
            self.sp_diam_w.setValue(float(table.diameter_m))
            self.sp_hub_w.setValue(float(table.hub_height_m))
        finally:
            self._wtg_syncing = False
        self._wtg_geometry_edited = False

        lines = [shown(table.describe(), tr_text)]
        if table.is_density_dependent:
            low, high = table.density_range
            lines.append(tr_text(
                "Cada aerogenerador podrá usar la curva de su densidad entre {low} y {high} kg/m³, activando el ajuste "
                "por densidad en la pantalla de energía."
            ).format(low=f"{low:.3f}", high=f"{high:.3f}"))
        else:
            lines.append(tr_text("El fichero solo trae una densidad: la curva será la misma para todo el parque."))
        lines.extend(shown(note, tr_text) for note in table.notes)
        self.lbl_wtg_info.setText("\n".join(lines))
        mark_translated(self.lbl_wtg_info)
        _debug_print(f"[Energy turbine UI] WTG loaded: {table.describe()}")
        return table

    def _on_build_wtg(self):
        self._discard_turbine()
        try:
            path = self.ed_path_w.text().strip()
            if not path or not os.path.isfile(path):
                raise FileNotFoundError(tr_text("Selecciona un fichero .wtg válido."))
            table = self._wtg_table if self._wtg_is_loaded(path) else self._load_wtg(path)
            if table is None:
                return

            name = self.ed_name_w.text().strip() or table.name
            d = float(self.sp_diam_w.value())
            h = float(self.sp_hub_w.value())
            wt = build_wt_from_curve_table(table, name=name, diameter_m=d, hub_height_m=h)
            # Curva 1-D de apoyo para la vista previa y la potencia nominal; la
            # simulación usa la familia completa, interpolada para cada turbina.
            ws, power_kw, ct = table.curve_at_density(table.default_air_density)

            self._wt = wt
            self._last_curves = (ws, power_kw, ct)
            self._result_data = {
                "mode": "wtg",
                "name": name,
                "diam": d,
                "hh": h,
                "spacing_long_d": float(self.sp_spacing_long_w.value()),
                "spacing_trans_d": float(self.sp_spacing_trans_w.value()),
                "path": path,
                "ws": list(ws),
                "power_kw": list(power_kw),
                "ct": list(ct),
                "p_rated_kw": float(table.max_power_kw),
                "curve_kind": "density_table",
                "curve_quality": "user_defined",
                "curve_source": str(path),
                "curve_source_url": "",
                "air_densities": [float(v) for v in table.air_densities],
                "default_air_density": float(table.default_air_density),
            }

            message = [tr_text("Turbina creada desde el fichero .wtg.")]
            if table.is_density_dependent:
                low, high = table.density_range
                message.append(tr_text(
                    "Trae {n} curvas entre {low} y {high} kg/m³; la vista previa se muestra a {preview} kg/m³."
                ).format(n=table.n_densities, low=f"{low:.3f}", high=f"{high:.3f}", preview=f"{table.default_air_density:.3f}"))
            if self._wtg_geometry_edited and (
                abs(d - float(table.diameter_m)) > 1e-6 or abs(h - float(table.hub_height_m)) > 1e-6
            ):
                message.append(tr_text(
                    "Atención: has cambiado la geometría respecto al fichero (D={diam} m, HH={hub} m)."
                ).format(diam=f"{float(table.diameter_m):g}", hub=f"{float(table.hub_height_m):g}"))
            message.append(tr_text("Pulsa Aceptar para usarla."))
            self._built_inputs = self._input_values()
            QtWidgets.QMessageBox.information(self, tr_text("Listo"), "\n\n".join(message))
            _debug_print("[Energy turbine UI] WTG turbine created and stored.")
        except Exception as e:
            self._discard_turbine()
            QtWidgets.QMessageBox.critical(self, tr_text("Error creando turbina"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_wtg: {e}")

    def _browse_owtg(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr_text("Abrir fichero .owtg"), os.path.expanduser("~"),
            tr_text("Turbina .owtg (*.owtg);;Todos (*.*)")
        )
        if path:
            self.ed_path_o.setText(path)
            self._load_owtg(path)

    def _owtg_is_loaded(self, path: str) -> bool:
        table = self._owtg_table
        return table is not None and str(table.source_path) == os.path.abspath(path)

    def _on_owtg_path_edited(self) -> None:
        """Una ruta escrita o pegada se lee igual que la del selector, con su geometría."""
        path = self.ed_path_o.text().strip()
        if self._owtg_is_loaded(path):
            return
        self._discard_owtg_turbine()
        if path and os.path.isfile(path):
            self._load_owtg(path)

    def _discard_owtg_turbine(self) -> None:
        """Otro fichero (o ninguno) descarta la turbina construida desde la pestaña .owtg:
        Aceptar no puede entregar una turbina distinta de la que muestra la pestaña."""
        if isinstance(self._result_data, dict) and self._result_data.get("mode") == "owtg":
            self._wt = None
            self._result_data = None
            self._last_curves = None

    def _on_owtg_geometry_edited(self, *_args) -> None:
        if not self._owtg_syncing:
            self._owtg_geometry_edited = True

    def _load_owtg(self, path: str):
        """Lee el fichero, muestra lo que contiene y toma de él nombre, diámetro y altura."""
        self._discard_owtg_turbine()
        try:
            table = load_owtg(path)
            # Un control no admite un valor fuera de su rango: lo recortaría en silencio.
            if not (self.sp_diam_o.minimum() <= table.diameter_m <= self.sp_diam_o.maximum()
                    and self.sp_hub_o.minimum() <= table.hub_height_m <= self.sp_hub_o.maximum()):
                raise ValueError(tr_text(
                    "La geometría del fichero (D={diam} m, HH={hub} m) no cabe en los controles del diálogo "
                    "(D hasta {diam_max} m, HH hasta {hub_max} m)."
                ).format(
                    diam=f"{table.diameter_m:g}", hub=f"{table.hub_height_m:g}",
                    diam_max=f"{self.sp_diam_o.maximum():g}", hub_max=f"{self.sp_hub_o.maximum():g}",
                ))
        except Exception as e:
            self._owtg_table = None
            self.lbl_owtg_info.setText(tr_text("No se pudo leer el fichero .owtg."))
            QtWidgets.QMessageBox.critical(self, tr_text("Fichero .owtg"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _load_owtg: {e}")
            return None

        self._owtg_table = table
        self._owtg_syncing = True
        try:
            self.ed_name_o.setText(table.name)
            self.sp_diam_o.setValue(float(table.diameter_m))
            self.sp_hub_o.setValue(float(table.hub_height_m))
        finally:
            self._owtg_syncing = False
        self._owtg_geometry_edited = False

        lines = [shown(table.describe(), tr_text)]
        if table.is_density_dependent:
            low, high = table.density_range
            lines.append(tr_text(
                "Cada aerogenerador podrá usar la curva de su densidad entre {low} y {high} kg/m³, activando el ajuste "
                "por densidad en la pantalla de energía."
            ).format(low=f"{low:.3f}", high=f"{high:.3f}"))
        else:
            lines.append(tr_text("El fichero solo trae una densidad: la curva será la misma para todo el parque."))
        lines.extend(shown(note, tr_text) for note in table.notes)
        self.lbl_owtg_info.setText("\n".join(lines))
        mark_translated(self.lbl_owtg_info)
        _debug_print(f"[Energy turbine UI] OWTG loaded: {table.describe()}")
        return table

    def _on_build_owtg(self):
        self._discard_turbine()
        try:
            path = self.ed_path_o.text().strip()
            if not path or not os.path.isfile(path):
                raise FileNotFoundError(tr_text("Selecciona un fichero .owtg válido."))
            table = self._owtg_table if self._owtg_is_loaded(path) else self._load_owtg(path)
            if table is None:
                return

            name = self.ed_name_o.text().strip() or table.name
            d = float(self.sp_diam_o.value())
            h = float(self.sp_hub_o.value())
            wt = build_wt_from_curve_table(table, name=name, diameter_m=d, hub_height_m=h)
            # Curva 1-D de apoyo para la vista previa; la simulación usa la familia
            # completa, interpolada para cada turbina.
            ws, power_kw, ct = table.curve_at_density(table.default_air_density)

            self._wt = wt
            self._last_curves = (ws, power_kw, ct)
            self._result_data = {
                "mode": "owtg",
                "name": name,
                "diam": d,
                "hh": h,
                "spacing_long_d": float(self.sp_spacing_long_o.value()),
                "spacing_trans_d": float(self.sp_spacing_trans_o.value()),
                "path": path,
                "ws": list(ws),
                "power_kw": list(power_kw),
                "ct": list(ct),
                # La nominal que declara el fichero; sin ella, el máximo de la tabla.
                "p_rated_kw": float(table.rated_power_kw or table.max_power_kw),
                "curve_kind": "density_table",
                "curve_quality": "user_defined",
                "curve_source": str(path),
                "curve_source_url": "",
                "air_densities": [float(v) for v in table.air_densities],
                "default_air_density": float(table.default_air_density),
            }

            message = [tr_text("Turbina creada desde el fichero .owtg.")]
            if table.is_density_dependent:
                low, high = table.density_range
                message.append(tr_text(
                    "Trae {n} curvas entre {low} y {high} kg/m³; la vista previa se muestra a {preview} kg/m³."
                ).format(n=table.n_densities, low=f"{low:.3f}", high=f"{high:.3f}", preview=f"{table.default_air_density:.3f}"))
            if self._owtg_geometry_edited and (
                abs(d - float(table.diameter_m)) > 1e-6 or abs(h - float(table.hub_height_m)) > 1e-6
            ):
                message.append(tr_text(
                    "Atención: has cambiado la geometría respecto al fichero (D={diam} m, HH={hub} m)."
                ).format(diam=f"{float(table.diameter_m):g}", hub=f"{float(table.hub_height_m):g}"))
            message.append(tr_text("Pulsa Aceptar para usarla."))
            self._built_inputs = self._input_values()
            QtWidgets.QMessageBox.information(self, tr_text("Listo"), "\n\n".join(message))
            _debug_print("[Energy turbine UI] OWTG turbine created and stored.")
        except Exception as e:
            self._discard_turbine()
            QtWidgets.QMessageBox.critical(self, tr_text("Error creando turbina"), _error_text(e))
            _debug_print(f"[Energy turbine UI][ERROR] _on_build_owtg: {e}")

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
          - mode: "manual" | "csv" | "wtg" | "owtg"
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
                self, tr_text("Sin turbina"),
                tr_text("Primero pulsa «Crear turbina» en la pestaña correspondiente.")
            )
            _debug_print("[Energy turbine UI] accept blocked: turbine not created yet.")
            return
        changed = self._changed_inputs()
        if changed and not self._ask_continue(tr_text("Datos cambiados"), self._changed_inputs_text(changed)):
            _debug_print("[Energy turbine UI] accept cancelled: inputs changed since the turbine was created.")
            return
        _debug_print("[Energy turbine UI] accept -> OK.")
        super().accept()

