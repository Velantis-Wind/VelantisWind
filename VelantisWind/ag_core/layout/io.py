# -*- coding: utf-8 -*-
"""Lectura y geometría ligera de layouts de turbinas para AEP."""
from __future__ import annotations

import csv
from typing import List, Tuple


def read_xy_csv(path: str) -> Tuple[List[float], List[float]]:
    """Lee un CSV con columnas x/y, easting/northing o las dos primeras columnas."""
    return _read_xy_csv(path)


def bbox_from_site(site) -> Tuple[float, float, float, float]:
    """Devuelve xmin, xmax, ymin, ymax a partir del dataset del site PyWake."""
    return _bbox_from_site(site)

def _read_xy_csv(path: str) -> Tuple[List[float], List[float]]:
    xs, ys = [], []
    with open(path, newline="", encoding="utf-8") as f:
        sn = csv.Sniffer()
        sample = f.read(2048); f.seek(0)
        try:
            has_header = sn.has_header(sample)
        except Exception:
            has_header = False
        r = csv.reader(f)
        if has_header:
            header = next(r, None) or []
            norm = [str(h).strip().lower() for h in header]
            ix = norm.index("x") if "x" in norm else (norm.index("easting") if "easting" in norm else 0)
            iy = norm.index("y") if "y" in norm else (norm.index("northing") if "northing" in norm else 1)
        else:
            ix, iy = 0, 1
        for row in r:
            if len(row) < 2:
                continue
            try:
                xs.append(float(row[ix])); ys.append(float(row[iy]))
            except Exception:
                try:
                    xs.append(float(row[0])); ys.append(float(row[1]))
                except Exception:
                    continue
    return xs, ys

def _bbox_from_site(site) -> Tuple[float, float, float, float]:
    for attr in ("ds", "dataset"):
        if hasattr(site, attr):
            ds = getattr(site, attr)
            try:
                xmin = float(ds["x"].min()); xmax = float(ds["x"].max())
                ymin = float(ds["y"].min()); ymax = float(ds["y"].max())
                if xmin > xmax: xmin, xmax = xmax, xmin
                if ymin > ymax: ymin, ymax = ymax, ymin
                return xmin, xmax, ymin, ymax
            except Exception:
                pass
    # Fallback
    return 0.0, 1.0, 0.0, 1.0

__all__ = ["read_xy_csv", "bbox_from_site"]
