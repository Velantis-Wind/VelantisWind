# -*- coding: utf-8 -*-
"""Shared turbine-layout import helpers for VelantisWind modules.

The Energy, Noise and Shadow modules all need the same first step: obtain a
point layer with turbine coordinates and enough metadata for the calculation
module to interpret it.  Keeping the CSV parsing and memory-layer creation here
prevents Noise/Shadow from depending on the Energy dialog just to load a layout.
"""
from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional, Tuple

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

_LAYOUT_GROUP_NAME = "VelantisWind · Turbine layouts"
_X_NAMES = {"x", "utm_x", "easting", "east", "lon", "longitude"}
_Y_NAMES = {"y", "utm_y", "northing", "north", "lat", "latitude"}


def _safe_float(value) -> Optional[float]:
    try:
        return float(str(value).strip().replace(",", "."))
    except Exception:
        return None


def read_xy_csv(path: str) -> List[Tuple[float, float]]:
    """Read XY turbine coordinates from a CSV/TXT file.

    The parser accepts either explicit X/Y-like headers or a simple two-column
    file without headers.  Empty rows and rows with non-numeric coordinates are
    ignored; at least one valid point is required.
    """
    if not path or not os.path.exists(path):
        raise ValueError("CSV file not found.")

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        except Exception:
            dialect = csv.excel
        rows = list(csv.reader(f, dialect))

    rows = [r for r in rows if r and any(str(c).strip() for c in r)]
    if not rows:
        raise ValueError("The CSV file is empty.")

    header = [str(c).strip().lower() for c in rows[0]]
    x_idx = next((i for i, h in enumerate(header) if h in _X_NAMES), None)
    y_idx = next((i for i, h in enumerate(header) if h in _Y_NAMES), None)

    data_rows = rows[1:] if x_idx is not None and y_idx is not None else rows
    if x_idx is None or y_idx is None:
        x_idx, y_idx = 0, 1

    points: List[Tuple[float, float]] = []
    for row in data_rows:
        if len(row) <= max(x_idx, y_idx):
            continue
        x = _safe_float(row[x_idx])
        y = _safe_float(row[y_idx])
        if x is None or y is None:
            continue
        points.append((float(x), float(y)))

    if not points:
        raise ValueError("No valid XY coordinates were found. Use columns named X/Y or a two-column CSV.")
    return points


def _project_crs_uri() -> str:
    crs = QgsProject.instance().crs()
    authid = crs.authid() if crs and crs.isValid() else "EPSG:25830"
    return authid or "EPSG:25830"


def _ensure_group(name: str = _LAYOUT_GROUP_NAME):
    root = QgsProject.instance().layerTreeRoot()
    try:
        group = root.findGroup(name)
    except Exception:
        group = None
    if group is None:
        group = root.addGroup(name)
    return group


def _unique_layer_name(base_name: str) -> str:
    existing = {lyr.name() for lyr in QgsProject.instance().mapLayers().values()}
    base = (base_name or "Turbine layout").strip() or "Turbine layout"
    if base not in existing:
        return base
    i = 2
    while True:
        candidate = f"{base} {i}"
        if candidate not in existing:
            return candidate
        i += 1


def create_turbine_layout_layer(
    *,
    coords: List[Tuple[float, float]],
    layer_name: str,
    module: str,
    model_name: str,
    hub_height_m: Optional[float] = None,
    rotor_diameter_m: Optional[float] = None,
    coords_csv: str = "",
    park_name: str = "",
    source_group_name: str = "",
    extra_properties: Optional[Dict[str, object]] = None,
) -> QgsVectorLayer:
    """Create a memory point layer and tag it as a Velantis turbine layout."""
    if not coords:
        raise ValueError("No turbine coordinates were provided.")

    layer_name = _unique_layer_name(layer_name)
    lyr = QgsVectorLayer(f"Point?crs={_project_crs_uri()}", layer_name, "memory")
    if not lyr.isValid():
        raise RuntimeError("Could not create the turbine layout memory layer.")

    provider = lyr.dataProvider()
    fields = [
        QgsField("model", QtCore.QVariant.String),
        QgsField("park", QtCore.QVariant.String),
        QgsField("module", QtCore.QVariant.String),
        QgsField("hh_m", QtCore.QVariant.Double),
        QgsField("diam_m", QtCore.QVariant.Double),
        QgsField("source_csv", QtCore.QVariant.String),
    ]
    if module == "noise":
        fields.append(QgsField("lwa_dba", QtCore.QVariant.Double))
    provider.addAttributes(fields)
    lyr.updateFields()

    default_lwa = None
    if extra_properties and extra_properties.get("velantis/default_lwa_dba") is not None:
        default_lwa = _safe_float(extra_properties.get("velantis/default_lwa_dba"))

    feats: List[QgsFeature] = []
    for x, y in coords:
        feat = QgsFeature(lyr.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(x), float(y))))
        attrs = [
            model_name,
            park_name,
            module,
            float(hub_height_m) if hub_height_m is not None else None,
            float(rotor_diameter_m) if rotor_diameter_m is not None else None,
            coords_csv,
        ]
        if module == "noise":
            attrs.append(float(default_lwa) if default_lwa is not None else None)
        feat.setAttributes(attrs)
        feats.append(feat)
    provider.addFeatures(feats)
    lyr.updateExtents()

    # Generic metadata used by all module detectors.
    lyr.setCustomProperty("velantis/layer_role", "turbine_layout")
    lyr.setCustomProperty("velantis/source_module", module)
    lyr.setCustomProperty("velantis/model_name", model_name)
    lyr.setCustomProperty("velantis/coords_csv", coords_csv)
    if park_name:
        lyr.setCustomProperty("velantis/park_name", park_name)
    if source_group_name:
        lyr.setCustomProperty("velantis/noise_group_name", source_group_name)
    if hub_height_m is not None:
        lyr.setCustomProperty("velantis/hub_height_m", float(hub_height_m))
    if rotor_diameter_m is not None:
        lyr.setCustomProperty("velantis/diameter_m", float(rotor_diameter_m))
    for key, value in (extra_properties or {}).items():
        try:
            lyr.setCustomProperty(str(key), value)
        except Exception:
            pass

    QgsProject.instance().addMapLayer(lyr, False)
    _ensure_group().addLayer(lyr)
    return lyr


class TurbineLayoutImportDialog(QtWidgets.QDialog):
    """Small module-aware CSV import dialog."""

    def __init__(self, parent=None, module: str = "noise"):
        super().__init__(parent)
        self.module = (module or "noise").strip().lower()
        self.setWindowTitle("Import turbine layout")
        self.setMinimumWidth(520)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.ed_layer_name = QtWidgets.QLineEdit()
        self.ed_layer_name.setPlaceholderText("Example: Project A · WT layout")
        form.addRow("Layer name:", self.ed_layer_name)

        self.ed_model = QtWidgets.QLineEdit("WT model")
        form.addRow("WT model / family:", self.ed_model)

        self.ed_park = QtWidgets.QLineEdit()
        self.ed_park.setPlaceholderText("Optional")
        form.addRow("Wind farm / park:", self.ed_park)

        self.ed_csv = QtWidgets.QLineEdit()
        self.ed_csv.setPlaceholderText("CSV with X,Y or easting,northing columns")
        btn_csv = QtWidgets.QPushButton("Browse…")
        btn_csv.clicked.connect(self._browse_csv)
        csv_row = QtWidgets.QHBoxLayout()
        csv_row.addWidget(self.ed_csv, 1)
        csv_row.addWidget(btn_csv)
        form.addRow("Coordinates CSV:", csv_row)

        self.sp_hh = QtWidgets.QDoubleSpinBox()
        self.sp_hh.setDecimals(1)
        self.sp_hh.setRange(0.0, 400.0)
        self.sp_hh.setValue(100.0)
        self.sp_hh.setSuffix(" m")
        form.addRow("Hub height:", self.sp_hh)

        self.sp_diam = QtWidgets.QDoubleSpinBox()
        self.sp_diam.setDecimals(1)
        self.sp_diam.setRange(0.0, 400.0)
        self.sp_diam.setValue(120.0)
        self.sp_diam.setSuffix(" m")
        form.addRow("Rotor diameter:", self.sp_diam)

        self.ed_source_group = QtWidgets.QLineEdit("Acoustic source group" if self.module == "noise" else "")
        if self.module == "noise":
            form.addRow("Noise source group:", self.ed_source_group)

            self.sp_lwa = QtWidgets.QDoubleSpinBox()
            self.sp_lwa.setDecimals(1)
            self.sp_lwa.setRange(0.0, 200.0)
            self.sp_lwa.setValue(105.0)
            self.sp_lwa.setSuffix(" dB(A)")
            form.addRow("Default fixed LwA:", self.sp_lwa)
        else:
            self.sp_lwa = None

        lay.addLayout(form)

        note = QtWidgets.QLabel(
            "The layer will be added to QGIS as a VelantisWind turbine layout. "
            "You can still edit module-specific values in the module table before calculating."
        )
        note.setWordWrap(True)
        lay.addWidget(note)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _browse_csv(self):
        start_dir = os.path.dirname(self.ed_csv.text().strip()) if self.ed_csv.text().strip() else os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select turbine coordinates CSV", start_dir, "CSV/TXT (*.csv *.txt);;All files (*.*)")
        if path:
            self.ed_csv.setText(path)
            if not self.ed_layer_name.text().strip():
                base = os.path.splitext(os.path.basename(path))[0]
                suffix = "noise layout" if self.module == "noise" else "shadow layout"
                self.ed_layer_name.setText(f"{base} · {suffix}")

    def values(self) -> Dict[str, object]:
        model = self.ed_model.text().strip() or "WT model"
        layer_name = self.ed_layer_name.text().strip() or f"{model} · {self.module} layout"
        out = {
            "layer_name": layer_name,
            "model_name": model,
            "park_name": self.ed_park.text().strip(),
            "coords_csv": self.ed_csv.text().strip(),
            "hub_height_m": float(self.sp_hh.value()) if self.sp_hh.value() > 0 else None,
            "rotor_diameter_m": float(self.sp_diam.value()) if self.sp_diam.value() > 0 else None,
            "source_group_name": self.ed_source_group.text().strip() if self.module == "noise" else "",
        }
        if self.module == "noise" and self.sp_lwa is not None:
            out["default_lwa_dba"] = float(self.sp_lwa.value())
        return out


def exec_dialog(dialog: QtWidgets.QDialog) -> int:
    """Qt5/Qt6 compatible dialog execution."""
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


def import_turbine_layout_from_csv(parent=None, module: str = "noise") -> Optional[QgsVectorLayer]:
    """Prompt the user for a CSV layout and create a tagged QGIS layer."""
    dlg = TurbineLayoutImportDialog(parent, module=module)
    if exec_dialog(dlg) != QtWidgets.QDialog.Accepted:
        return None
    values = dlg.values()
    coords_csv = str(values.get("coords_csv") or "").strip()
    coords = read_xy_csv(coords_csv)
    extra: Dict[str, object] = {}
    if module == "noise" and values.get("default_lwa_dba") is not None:
        extra["velantis/default_lwa_dba"] = float(values.get("default_lwa_dba"))
    return create_turbine_layout_layer(
        coords=coords,
        layer_name=str(values.get("layer_name") or "Turbine layout"),
        module=module,
        model_name=str(values.get("model_name") or "WT model"),
        hub_height_m=values.get("hub_height_m"),
        rotor_diameter_m=values.get("rotor_diameter_m"),
        coords_csv=coords_csv,
        park_name=str(values.get("park_name") or ""),
        source_group_name=str(values.get("source_group_name") or ""),
        extra_properties=extra,
    )


__all__ = [
    "read_xy_csv",
    "create_turbine_layout_layer",
    "import_turbine_layout_from_csv",
]
