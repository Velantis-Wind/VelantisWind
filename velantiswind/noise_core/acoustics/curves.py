# -*- coding: utf-8 -*-
"""Acoustic power-curve IO and evaluation helpers."""
from __future__ import annotations

import csv
import math
import os
from typing import List, Optional, Tuple

import numpy as np

def load_acoustic_curve_csv(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Lee una curva acústica simple ws/LwA desde CSV o TXT."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(path or 'Sin ruta de curva acústica')
    rows: List[Tuple[float, float]] = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;	 ')
            delim = dialect.delimiter
        except Exception:
            delim = ',' if ',' in sample else ';' if ';' in sample else None
        if delim:
            reader = csv.reader(f, delimiter=delim)
        else:
            reader = (line.strip().split() for line in f)
        for row in reader:
            if not row or len(row) < 2:
                continue
            try:
                ws = float(str(row[0]).replace(',', '.'))
                lwa = float(str(row[1]).replace(',', '.'))
            except Exception:
                continue
            rows.append((ws, lwa))
    if not rows:
        raise ValueError(f'No se pudieron leer pares ws/LwA válidos de {path}')
    rows = sorted(rows, key=lambda t: t[0])
    ws = np.array([r[0] for r in rows], dtype=float)
    lwa = np.array([r[1] for r in rows], dtype=float)
    # compactar velocidades duplicadas conservando el máximo LwA
    uniq_ws = []
    uniq_lwa = []
    for w in sorted(set(ws.tolist())):
        mask = ws == w
        uniq_ws.append(float(w))
        uniq_lwa.append(float(np.max(lwa[mask])))
    return np.array(uniq_ws, dtype=float), np.array(uniq_lwa, dtype=float)


def evaluate_acoustic_curve(ws: np.ndarray, lwa: np.ndarray, eval_ws_m_s: Optional[float] = None, use_worst_case: bool = False) -> float:
    if ws.size == 0 or lwa.size == 0:
        raise ValueError('Acoustic curve vacía')
    if use_worst_case:
        return float(np.max(lwa))
    if eval_ws_m_s is None or not math.isfinite(float(eval_ws_m_s)):
        eval_ws_m_s = float(ws[len(ws) // 2])
    eval_ws_m_s = float(eval_ws_m_s)
    if eval_ws_m_s <= float(ws.min()):
        return float(lwa[0])
    if eval_ws_m_s >= float(ws.max()):
        return float(lwa[-1])
    return float(np.interp(eval_ws_m_s, ws, lwa))
