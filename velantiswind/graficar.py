# -*- coding: utf-8 -*-
"""
graficar.py — Dibuja mapas de estelas con control de memoria.
Compat WAsP (.grd) + WRG (Vortex .wrg / .zip).

Cambios clave (para que también pinte con WRG):
- Permite cargar Site desde WRG usando el mismo loader que AEP (load_wrg_site).
- Inyecta TI de forma compatible (crea ds['TI'] y alias ds['ti'], ds['ti15ms'] con dims correctas).
- flow_map() con WRG: pasa SIEMPRE wd y ws (PyWake 2.6.x lo agradece para maps).
- Mantiene tu control de memoria (grid anclado + auto-throttle).

Requisitos:
- PyWake 2.6.x
- QGIS + matplotlib Qt backend
"""

from __future__ import annotations
import os, csv, math
from typing import List, Dict, Any, Tuple, Optional


def _is_debug_enabled() -> bool:
    return str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}


def _debug_print(message: str) -> None:
    if _is_debug_enabled():
        print(message)

# Qt opcional (para QMessageBox)
try:
    from qgis.PyQt import QtWidgets
except Exception:  # pragma: no cover
    QtWidgets = None  # type: ignore

import numpy as np

# Forzar backend Qt antes de pyplot (para que abra ventana en QGIS)
import matplotlib
try:
    if not matplotlib.get_backend().lower().startswith(("qt", "module://")):
        try:
            matplotlib.use("Qt5Agg", force=True)
        except Exception:
            matplotlib.use("QtAgg", force=True)
except Exception:
    pass

import matplotlib.pyplot as plt

# ---------------- py_wake imports (robustos) ----------------
try:
    from py_wake.site.wasp_grid_site import WaspGridSite  # PyWake 2.6.x
except Exception:  # pragma: no cover
    from py_wake.site import WaspGridSite  # type: ignore

try:
    from py_wake.wind_farm_models import PropagateDownwind
except Exception:  # pragma: no cover
    from py_wake.wind_farm_models.engineering_models import PropagateDownwind  # type: ignore

try:
    from py_wake.deficit_models import BastankhahGaussianDeficit
except Exception:  # pragma: no cover
    from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit  # type: ignore

try:
    from py_wake.superposition_models import LinearSum
except Exception:  # pragma: no cover
    from py_wake.superposition_models import LinearSum  # type: ignore

try:
    from py_wake.examples.data.hornsrev1 import V80
except Exception:  # pragma: no cover
    V80 = None  # type: ignore

# ---- Superposición coherente con el selector de Energía ----
_make_superposition_model = None
try:
    from .ag_core.physics.wake import make_superposition_model as _make_superposition_model  # type: ignore
except Exception:
    try:
        from ag_core.physics.wake import make_superposition_model as _make_superposition_model  # type: ignore
    except Exception:
        _make_superposition_model = None

try:
    from py_wake import HorizontalGrid
except Exception:  # pragma: no cover
    try:
        from py_wake.flow_map import HorizontalGrid  # type: ignore
    except Exception:
        HorizontalGrid = None  # type: ignore

# ---- WRG loader (el mismo que usas en AEP) ----
load_wrg_site = None
try:
    # si graficar.py está en el paquete raíz del plugin
    from .ag_core.wrg_site import load_wrg_site  # type: ignore
except Exception:
    try:
        from ag_core.wrg_site import load_wrg_site  # type: ignore
    except Exception:
        load_wrg_site = None

# ---- WT combinado (mismo criterio que el cálculo AEP) ----
_combine_wt = None
try:
    from .ag_core.turbines.factory import combine_wt as _combine_wt  # type: ignore
except Exception:
    try:
        from ag_core.turbines.factory import combine_wt as _combine_wt  # type: ignore
    except Exception:
        _combine_wt = None


# ===================== Mensajes =====================
def _msg_info(title: str, text: str, parent=None):
    if QtWidgets is not None and parent is not None:
        QtWidgets.QMessageBox.information(parent, title, text)
    else:
        print(f"[INFO] {title}: {text}")

def _msg_warn(title: str, text: str, parent=None):
    if QtWidgets is not None and parent is not None:
        QtWidgets.QMessageBox.warning(parent, title, text)
    else:
        print(f"[WARN] {title}: {text}")

def _msg_err(title: str, text: str, parent=None):
    if QtWidgets is not None and parent is not None:
        QtWidgets.QMessageBox.critical(parent, title, text)
    else:
        print(f"[ERROR] {title}: {text}")


# ===================== WAsP helpers =====================
def _resolve_wasp_dir_for_pywake(wasp_dir: str) -> str:
    """
    Si existe wasp_dir/pywake_compat y contiene .grd, se usa ese directorio.
    """
    cand = os.path.join(wasp_dir, "pywake_compat")
    if os.path.isdir(cand):
        try:
            if any(fn.lower().endswith(".grd") for fn in os.listdir(cand)):
                return cand
        except Exception:
            pass
    return wasp_dir

def _load_site_wasp(wasp_dir: str) -> WaspGridSite:
    load_dir = _resolve_wasp_dir_for_pywake(wasp_dir)
    if os.path.normpath(load_dir) != os.path.normpath(wasp_dir):
        _debug_print(f"[AEP-plot] Usando subcarpeta prioritaria: {load_dir}")

    if hasattr(WaspGridSite, "from_wasp_grd"):
        site = WaspGridSite.from_wasp_grd(load_dir)  # type: ignore
    else:
        site = WaspGridSite(load_dir)  # type: ignore
    return site

def _looks_like_wrg_path(p: str) -> bool:
    p = (p or "").strip().lower()
    return p.endswith(".wrg") or p.endswith(".zip")  # zip puede contener wrg

def _load_site_any(wasp_dir: str, wrg_paths: Optional[List[str]] = None):
    """
    Devuelve (site, kind) donde kind ∈ {'WASP','WRG'}.
    - Si wrg_paths no vacío -> carga WRG
    - Si wasp_dir es un fichero .wrg/.zip -> carga WRG
    - Si wasp_dir es carpeta -> carga WAsP
    """
    wrg_paths = [p for p in (wrg_paths or []) if str(p).strip()]
    if wrg_paths or (wasp_dir and os.path.isfile(wasp_dir) and _looks_like_wrg_path(wasp_dir)):
        if load_wrg_site is None:
            raise RuntimeError("No se pudo importar load_wrg_site. Revisa que exista ag_core/wrg_site.py.")
        paths = wrg_paths if wrg_paths else [wasp_dir]
        site, ds, used = load_wrg_site(paths)  # type: ignore
        _debug_print(f"[AEP-plot] [WRG] Site cargado desde: {used}")
        return site, "WRG"
    else:
        if not wasp_dir or not os.path.isdir(wasp_dir):
            raise RuntimeError("Selecciona una carpeta WAsP válida o un WRG (.wrg/.zip).")
        site = _load_site_wasp(wasp_dir)
        _debug_print(f"[AEP-plot] [WASP] Site cargado desde: {wasp_dir}")
        return site, "WASP"


# ===================== Lectura / helpers =====================
def _read_coords_csv(path: str) -> List[Tuple[float, float]]:
    rows: List[Tuple[float, float]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        header = next(reader, None)
        if header is None:
            raise ValueError("CSV vacío.")

        h = [c.strip().lower() for c in header]
        def _find(*keys):
            for k in keys:
                if k in h:
                    return h.index(k)
            return None

        ix = _find("x", "easting", "east")
        iy = _find("y", "northing", "north")
        if ix is None or iy is None:
            raise ValueError("El CSV debe tener cabeceras 'X' y 'Y' (o easting/northing).")

        for r in reader:
            if not r or all(not (c or "").strip() for c in r):
                continue
            try:
                x = float(str(r[ix]).replace(",", "."))
                y = float(str(r[iy]).replace(",", "."))
                rows.append((x, y))
            except Exception:
                continue

    if not rows:
        raise ValueError("No se encontraron coordenadas válidas en el CSV.")
    return rows

def _collect_coordinates_types_and_labels(models: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, List[str], List[int]]:
    """Recoge coordenadas, vector ``type_i`` y etiquetas por modelo/capa.

    El orden de ``type_i`` coincide exactamente con el orden de ``models`` que
    se pasa a ``combine_wt(models)``. Así PyWake aplica la curva/diámetro/altura
    correcta a cada coordenada cuando hay varios modelos de aerogenerador.
    """
    coords: List[Tuple[float, float]] = []
    type_i: List[int] = []
    labels: List[str] = []
    counts: List[int] = []

    for i, m in enumerate(models or []):
        local: List[Tuple[float, float]] = []
        # Preferir puntos vivos suministrados por la UI (capa en memoria editada)
        cxy = m.get("coords_xy")
        if cxy:
            try:
                local = [(float(p[0]), float(p[1])) for p in cxy]
            except Exception:
                local = []
        if not local:
            p = (m.get("coords_csv") or "").strip()
            if p and os.path.isfile(p):
                local = _read_coords_csv(p)

        name = str(m.get("name") or (m.get("meta") or {}).get("name") or f"Modelo {i+1}")
        layer_name = str(m.get("source_layer_name") or "").strip()
        if layer_name and layer_name not in name:
            label = f"{name} · {layer_name}"
        else:
            label = name
        labels.append(label)
        counts.append(len(local))

        if local:
            coords.extend(local)
            type_i.extend([int(i)] * len(local))

    if not coords:
        raise ValueError("No hay coordenadas válidas en las capas/CSV proporcionados.")
    return np.asarray(coords, dtype=float), np.asarray(type_i, dtype=int), labels, counts


def _collect_coordinates_and_types(models: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    coords, type_i, _labels, _counts = _collect_coordinates_types_and_labels(models)
    return coords, type_i

def _collect_coordinates(models: List[Dict[str, Any]]) -> np.ndarray:
    coords, _type_i = _collect_coordinates_and_types(models)
    return coords

def _pick_wt(models: List[Dict[str, Any]]):
    """
    Para el plot usamos el primer WT disponible.
    Si no hay, usa V80 (si existe).
    """
    for m in models or []:
        wt = m.get("wt")
        if wt is not None:
            return wt
    if V80 is not None:
        return V80()
    raise RuntimeError("No se encontró un WindTurbines en 'models' y V80 no está disponible.")

def _pad_to_step(vmin: float, vmax: float, step: float) -> Tuple[float, float]:
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    if hi <= lo:
        hi = lo + step
    return lo, hi

def _to_1d_float(arr, name: str) -> np.ndarray:
    """
    Convierte arr a 1D float de forma robusta.
    """
    if arr is None:
        raise RuntimeError(f"No se pudo leer '{name}' del dataset.")

    try:
        if hasattr(arr, "values"):
            arr = arr.values
    except Exception:
        pass

    if isinstance(arr, (bytes, bytearray)):
        raise RuntimeError(f"'{name}' es bytes (lectura errónea).")
    if isinstance(arr, str):
        raise RuntimeError(f"'{name}' es str (lectura errónea).")

    a = np.asarray(arr)

    if a.dtype == object:
        try:
            cleaned = []
            for v in a.ravel():
                if isinstance(v, (bytes, bytearray)):
                    vv = v.decode("utf-8", errors="ignore").strip()
                    cleaned.append(float(vv))
                else:
                    cleaned.append(float(v))
            a = np.asarray(cleaned, dtype=float)
        except Exception as e:
            raise RuntimeError(f"No se pudo convertir '{name}' a float: {e}")

    a = np.asarray(a, dtype=float).ravel()
    if a.size < 2:
        raise RuntimeError(f"'{name}' no tiene suficientes valores para definir bounds.")
    a = a[np.isfinite(a)]
    if a.size < 2:
        raise RuntimeError(f"'{name}' contiene NaNs/no finitos.")
    return a

def _get_site_bounds(site) -> Tuple[float, float, float, float]:
    """
    Lee bounds desde coords x/y del Dataset (xarray).
    Funciona tanto para WAsPGridSite como para XRSite (WRG).
    """
    ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
    if ds is None:
        raise RuntimeError("El site no expone 'ds'/'dataset'.")

    x_src = None
    y_src = None

    try:
        if hasattr(ds, "coords"):
            if "x" in ds.coords:
                x_src = ds.coords["x"]
            if "y" in ds.coords:
                y_src = ds.coords["y"]
    except Exception:
        pass

    try:
        if x_src is None and "x" in ds:
            x_src = ds["x"]
        if y_src is None and "y" in ds:
            y_src = ds["y"]
    except Exception:
        pass

    x_vals = _to_1d_float(x_src, "x")
    y_vals = _to_1d_float(y_src, "y")

    return float(np.nanmin(x_vals)), float(np.nanmax(x_vals)), float(np.nanmin(y_vals)), float(np.nanmax(y_vals))


def _ensure_dataset_has_ti(site, ti_value: float = 0.10) -> None:
    """
    Para BastankhahGaussianDeficit en varios flujos, es más seguro que exista ds['TI'].
    Creamos ds['TI'] y además alias ds['ti15ms'], ds['ti'] con dims correctas:
      ('x','y') y si existen también 'h' y 'wd' -> ('x','y','h','wd').

    (Esto vale para WAsP y para WRG/XRSite)
    """
    ti_value = float(ti_value)
    ti_value = min(max(ti_value, 0.0), 0.10)

    ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
    if ds is None:
        return

    # Si ya existe TI o ti/ti15ms, aún así garantizamos 'TI'
    try:
        has_TI = ("TI" in ds)
    except Exception:
        has_TI = False

    if has_TI:
        # asegurar aliases
        try:
            if "ti" not in ds:
                ds["ti"] = ds["TI"]
            if "ti15ms" not in ds:
                ds["ti15ms"] = ds["TI"]
        except Exception:
            pass
        return

    # dims objetivo
    try:
        sizes = getattr(ds, "sizes", {}) or {}
        dims = []
        for d in ("x", "y", "h", "wd"):
            if d in sizes:
                dims.append(d)
        if "x" not in dims or "y" not in dims:
            # fallback mínimo
            dims = ["x", "y"]
        shape = tuple(int(sizes.get(d, 1)) for d in dims)
        arr = np.full(shape, ti_value, dtype=np.float32)
        ds["TI"] = (tuple(dims), arr)
        ds["ti"] = ds["TI"]
        ds["ti15ms"] = ds["TI"]
        _debug_print(f"[AEP-plot] Inyectado ds['TI']=ds['ti']=ds['ti15ms'] con TI fija={ti_value:.2f} dims={dims}")
    except Exception as e:
        _debug_print(f"[AEP-plot] No se pudo inyectar TI fija en dataset: {e}")


# ============ Construcción de grid (anclado + control memoria) ============
def _build_domain_anchored_grid(
    sx_min: float, sx_max: float, sy_min: float, sy_max: float,
    gx_min_req: float, gx_max_req: float, gy_min_req: float, gy_max_req: float,
    res_x: float, res_y: float,
    max_cells: int = 2_000_000,
    max_span_m: float = 60_000.0
) -> Tuple[np.ndarray, np.ndarray, float, float, float, float, float, float]:

    gx_min = max(gx_min_req, sx_min); gx_max = min(gx_max_req, sx_max)
    gy_min = max(gy_min_req, sy_min); gy_max = min(gy_max_req, sy_max)
    if gx_min >= gx_max: gx_min, gx_max = sx_min, sx_max
    if gy_min >= gy_max: gy_min, gy_max = sy_min, sy_max

    cx = 0.5 * (gx_min + gx_max)
    cy = 0.5 * (gy_min + gy_max)
    half = max_span_m * 0.5
    gx_min = max(sx_min, max(gx_min, cx - half)); gx_max = min(sx_max, min(gx_max, cx + half))
    gy_min = max(sy_min, max(gy_min, cy - half)); gy_max = min(sy_max, min(gy_max, cy + half))

    def _grid_with_res(rx: float, ry: float):
        kx_start = int(math.ceil((gx_min - sx_min) / rx))
        kx_end   = int(math.floor((gx_max - sx_min) / rx))
        ky_start = int(math.ceil((gy_min - sy_min) / ry))
        ky_end   = int(math.floor((gy_max - sy_min) / ry))

        grid_x = sx_min + np.arange(kx_start, kx_end + 1, dtype=float) * rx
        grid_y = sy_min + np.arange(ky_start, ky_end + 1, dtype=float) * ry

        grid_x = grid_x[(grid_x >= sx_min) & (grid_x <= sx_max)]
        grid_y = grid_y[(grid_y >= sy_min) & (grid_y <= sy_max)]

        if grid_x.size == 0:
            grid_x = np.array([sx_min, min(sx_max, sx_min + rx)], float)
        if grid_y.size == 0:
            grid_y = np.array([sy_min, min(sy_max, sy_min + ry)], float)

        return grid_x, grid_y

    grid_x, grid_y = _grid_with_res(res_x, res_y)

    nx, ny = int(grid_x.size), int(grid_y.size)
    cells = nx * ny
    if cells > max_cells:
        ratio = math.sqrt(cells / max_cells) * 1.05
        res_x_eff = res_x * ratio
        res_y_eff = res_y * ratio
        grid_x, grid_y = _grid_with_res(res_x_eff, res_y_eff)
    else:
        res_x_eff, res_y_eff = res_x, res_y

    gx_min_eff = float(grid_x.min()); gx_max_eff = float(grid_x.max())
    gy_min_eff = float(grid_y.min()); gy_max_eff = float(grid_y.max())

    return grid_x, grid_y, gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff, res_x_eff, res_y_eff


def _pick_ws_for_plot(sim_res, ws_target: float = 10.0) -> float:
    """
    Para WRG es MUY recomendable pasar ws al flow_map.
    - Si sim_res.ws existe -> usa el más cercano a ws_target
    - Si no -> usa ws_target
    """
    try:
        ws = np.array(sim_res.ws.values, dtype=float).ravel()
        ws = ws[np.isfinite(ws)]
        if ws.size:
            return float(ws[int(np.argmin(np.abs(ws - ws_target)))])
    except Exception:
        pass
    return float(ws_target)


def _pick_wd_targets_12() -> List[Tuple[str, float]]:
    """12 sectores equivalentes (centros cada 30°)."""
    return [(f"Sector {i+1:02d}", float(i * 30.0)) for i in range(12)]


def _energy_by_wd(sim_res) -> Optional[np.ndarray]:
    """
    Intenta obtener la contribución energética por dirección de viento
    sumando turbinas y ws. Devuelve array 1D alineado con sim_res.wd.
    """
    try:
        aep = sim_res.aep(normalize_probabilities=False)
    except Exception:
        try:
            aep = sim_res.aep()
        except Exception:
            return None

    try:
        vals = np.asarray(aep.values, dtype=float)
        dims = list(getattr(aep, "dims", ()))
    except Exception:
        return None

    if vals.ndim == 0:
        return None

    if "wd" not in dims:
        return None

    axes_to_sum = [i for i, d in enumerate(dims) if d != "wd"]
    if axes_to_sum:
        vals = np.sum(vals, axis=tuple(axes_to_sum))

    vals = np.asarray(vals, dtype=float).ravel()
    if vals.size == 0:
        return None
    return vals


def _pick_most_energetic_wd(sim_res, wd_disponible: np.ndarray) -> Optional[Tuple[float, float]]:
    """Devuelve (wd_real, energia_sector) del sector con mayor AEP."""
    ewd = _energy_by_wd(sim_res)
    if ewd is None:
        return None

    n = min(len(ewd), len(wd_disponible))
    if n <= 0:
        return None
    ewd = ewd[:n]
    wd = np.asarray(wd_disponible[:n], dtype=float)
    finite = np.isfinite(ewd) & np.isfinite(wd)
    if not np.any(finite):
        return None
    ewd = ewd[finite]
    wd = wd[finite]
    i = int(np.argmax(ewd))
    return float(wd[i]), float(ewd[i])


def _plot_single_wake_map(sim_res, x_t, y_t, grid, wd_real: float, ws_real: float, kind: str,
                          gx_min_eff: float, gx_max_eff: float, gy_min_eff: float, gy_max_eff: float,
                          n_out: int, res_x_eff: float, res_y_eff: float, title: str, subtitle: str = "",
                          type_i_t=None, type_labels: Optional[List[str]] = None):
    flow_map = sim_res.flow_map(wd=wd_real, ws=ws_real, grid=grid)

    fig, ax = plt.subplots(figsize=(8, 7))
    flow_map.plot_wake_map(ax=ax)

    # Mostrar los modelos de aerogenerador por separado. La simulación ya usa
    # ``type_i``; esta separación visual evita que parezca que todo el parque
    # se ha interpretado como un único WT.
    try:
        ti = np.asarray(type_i_t, dtype=int).ravel() if type_i_t is not None else None
    except Exception:
        ti = None
    labels = list(type_labels or [])
    if ti is not None and ti.size == len(x_t) and len(set(ti.tolist())) > 1:
        for t in sorted(set(int(v) for v in ti.tolist())):
            mask = ti == t
            label = labels[t] if 0 <= t < len(labels) else f"Modelo {t+1}"
            ax.scatter(x_t[mask], y_t[mask], marker="X", s=80, label=f"{label} ({int(mask.sum())})")
    else:
        lbl = labels[0] if labels else "Turbinas"
        ax.scatter(x_t, y_t, marker="X", s=80, label=f"{lbl} (en dominio)")
    ax.set_xlim(gx_min_eff, gx_max_eff)
    ax.set_ylim(gy_min_eff, gy_max_eff)
    t = f"{title}: wd={wd_real:.1f}° | ws={ws_real:.1f} m/s"
    if subtitle:
        t += f" | {subtitle}"
    ax.set_title(t, fontsize=11)
    ax.legend(loc="upper right")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_aspect("equal", adjustable="box")

    fig.suptitle(
        f"Mapa de Estelas ({kind}) — Grid: {int(res_x_eff)}m × {int(res_y_eff)}m "
        f"| Turbinas: {len(x_t)}" + (f" / descartadas: {n_out}" if n_out else ""),
        fontsize=12, y=0.98
    )
    plt.tight_layout()

    try:
        fig.canvas.draw_idle()
        mng = plt.get_current_fig_manager()
        if hasattr(mng, "window"):
            try: mng.window.showNormal()
            except Exception: pass
            try: mng.window.raise_()
            except Exception: pass
            try: mng.window.activateWindow()
            except Exception: pass
    except Exception:
        pass

    plt.show(block=False)
    plt.pause(0.1)


# ===================== Función principal =====================
def graficar(
    models: List[Dict[str, Any]],
    wasp_dir: str,
    parent=None,
    resolution_m: float = 300.0,
    wrg_paths: Optional[List[str]] = None,
    ws_plot: float = 10.0,
    superposition_model: Optional[str] = "AUTO"
) -> None:
    """
    4 gráficas (N/E/S/O) con grid configurable (resolución en metros).
    - wasp_dir: carpeta WAsP o (opcional) path a .wrg/.zip
    - wrg_paths: lista de wrg/zip (si se usa WRG desde UI)
    - ws_plot: velocidad de referencia para flow_map (recomendado para WRG)
    - superposition_model: selector UI (AUTO/LIN/SQR/MAX/WGT)
    """
    try:
        if HorizontalGrid is None:
            _msg_err("Crear Graficas", "No se pudo importar HorizontalGrid desde py_wake.", parent)
            return

        # 1) Turbinas: coordenadas + tipo por modelo/capa
        coords, type_i_all, type_labels_all, type_counts_all = _collect_coordinates_types_and_labels(models)
        x_all = coords[:, 0].astype(float)
        y_all = coords[:, 1].astype(float)
        try:
            resumen_tipos = "; ".join(
                f"{lab}: {cnt}" for lab, cnt in zip(type_labels_all, type_counts_all) if int(cnt or 0) > 0
            )
            if resumen_tipos:
                _debug_print(f"[AEP-plot] Modelos/tipos seleccionados: {resumen_tipos}")
        except Exception:
            pass

        # 2) Site (WAsP o WRG)
        site, kind = _load_site_any(wasp_dir, wrg_paths=wrg_paths)

        # 3) TI fija si no viene (para Bastankhah/plot)
        _ensure_dataset_has_ti(site, ti_value=0.10)

        # Bounds del dominio del site
        sx_min, sx_max, sy_min, sy_max = _get_site_bounds(site)

        inside = (x_all >= sx_min) & (x_all <= sx_max) & (y_all >= sy_min) & (y_all <= sy_max)
        n_total = len(x_all)
        n_inside = int(inside.sum())
        n_out = n_total - n_inside

        if n_inside == 0:
            _msg_err(
                "Crear Graficas",
                f"Todas las turbinas están fuera del dominio del site ({kind}).\n"
                f"Dominio X[{sx_min:.3f},{sx_max:.3f}]  Y[{sy_min:.3f},{sy_max:.3f}]",
                parent
            )
            return

        if n_out > 0:
            idx_out = np.where(~inside)[0]
            ejemplo = ", ".join(map(str, idx_out[:10])) + ("…" if len(idx_out) > 10 else "")
            _msg_warn(
                "Crear Graficas",
                f"{n_out} de {n_total} turbinas están fuera del dominio y se omitirán (ej.: {ejemplo}).\n"
                f"Dominio X[{sx_min:.3f},{sx_max:.3f}]  Y[{sy_min:.3f},{sy_max:.3f}]",
                parent
            )

        x_t = x_all[inside]
        y_t = y_all[inside]
        type_i_t = type_i_all[inside]

        # Etiquetas/counts después de descartar turbinas fuera del dominio.
        type_labels_t = list(type_labels_all)
        try:
            inside_counts = [int(np.sum(type_i_t == i)) for i in range(len(type_labels_t))]
            resumen_inside = "; ".join(
                f"{lab}: {cnt}" for lab, cnt in zip(type_labels_t, inside_counts) if cnt > 0
            )
            if resumen_inside:
                _debug_print(f"[AEP-plot] Tipos dentro del dominio: {resumen_inside}")
        except Exception:
            pass

        use_types = False
        try:
            if _combine_wt is not None:
                wt, use_types = _combine_wt(models)
            else:
                wt = _pick_wt(models)
                use_types = False
        except Exception as e:
            _msg_warn(
                "Crear Graficas",
                "No se pudo construir el WindTurbines combinado para varios modelos. "
                f"Se usará el primer modelo como fallback.\n{e}",
                parent,
            )
            wt = _pick_wt(models)
            use_types = False

        if len([c for c in (type_counts_all or []) if int(c or 0) > 0]) > 1 and not use_types:
            _msg_warn(
                "Crear Graficas",
                "Hay varias capas/modelos seleccionados, pero PyWake no ha podido activar type_i. "
                "Las estelas se dibujarán con el primer modelo como fallback.",
                parent,
            )

        # Modelo de estelas (simple y compatible), usando la superposición elegida en la UI.
        wake_deficit_obj = BastankhahGaussianDeficit()
        try:
            if _make_superposition_model is not None:
                superpos_obj = _make_superposition_model(superposition_model or "AUTO", None, BastankhahGaussianDeficit, "PDW", log=print)
            else:
                superpos_obj = LinearSum()
        except Exception:
            superpos_obj = LinearSum()
        wf_model = PropagateDownwind(
            site=site,
            windTurbines=wt,
            wake_deficitModel=wake_deficit_obj,
            superpositionModel=superpos_obj,
            turbulenceModel=None
        )

        # 4) Caja alrededor de turbinas + grid base
        try:
            res_m = float(resolution_m)
        except Exception:
            res_m = 300.0
        if res_m <= 0:
            res_m = 300.0

        RES_X = res_m
        RES_Y = res_m

        xmin, xmax = float(x_t.min()), float(x_t.max())
        ymin, ymax = float(y_t.min()), float(y_t.max())
        dx = max((xmax - xmin) * 0.10, 1000.0)
        dy = max((ymax - ymin) * 0.10, 1000.0)

        gx_min_req, gx_max_req = _pad_to_step(xmin - dx, xmax + dx, RES_X)
        gy_min_req, gy_max_req = _pad_to_step(ymin - dy, ymax + dy, RES_Y)

        grid_x, grid_y, gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff, res_x_eff, res_y_eff = \
            _build_domain_anchored_grid(
                sx_min, sx_max, sy_min, sy_max,
                gx_min_req, gx_max_req, gy_min_req, gy_max_req,
                RES_X, RES_Y,
                max_cells=2_000_000,
                max_span_m=60_000.0
            )

        nx, ny = int(grid_x.size), int(grid_y.size)
        cells = int(nx * ny)
        if cells >= 2_000_000:
            _msg_info(
                "Crear Graficas",
                f"Grid grande: {nx}×{ny} = {cells:,} celdas. "
                f"Resolución efectiva {int(res_x_eff)}×{int(res_y_eff)} m.",
                parent
            )

        grid = HorizontalGrid(x=grid_x, y=grid_y)

        # 5) Simulación. Si hay varios modelos de turbina, PyWake necesita
        # type_i para aplicar curva/diámetro/altura por tipo.
        if use_types:
            sim_res = wf_model(x=x_t, y=y_t, type_i=type_i_t)
        else:
            sim_res = wf_model(x=x_t, y=y_t)

        # WD disponibles
        try:
            wd_disponible = np.array(sim_res.wd.values, dtype=float).ravel()
        except Exception:
            try:
                wd_disponible = np.array(getattr(site, "default_wd", np.linspace(0, 360, 72, endpoint=False)), dtype=float)
            except Exception:
                wd_disponible = np.linspace(0, 360, 72, endpoint=False)

        wd_disponible = wd_disponible[np.isfinite(wd_disponible)]
        if wd_disponible.size == 0:
            wd_disponible = np.linspace(0, 360, 72, endpoint=False)

        # WS para mapa (IMPORTANTÍSIMO para WRG)
        ws_real = _pick_ws_for_plot(sim_res, ws_target=ws_plot)

        # 6) Figuras: 4 cardinales + 12 sectores + sector más energético
        dirs_cardinales = [("Norte", 0.0), ("Este", 90.0), ("Sur", 180.0), ("Oeste", 270.0)]
        dirs_12 = _pick_wd_targets_12()

        for etiqueta, wd_target in dirs_cardinales:
            wd_idx = int(np.argmin(np.abs(wd_disponible - wd_target)))
            wd_real = float(wd_disponible[wd_idx])
            _plot_single_wake_map(
                sim_res, x_t, y_t, grid, wd_real, ws_real, kind,
                gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff,
                n_out, res_x_eff, res_y_eff,
                title=etiqueta,
                subtitle=f"obj {wd_target:.1f}°",
                type_i_t=type_i_t,
                type_labels=type_labels_t
            )
            _debug_print(
                f"[INFO] {etiqueta}: wd {wd_real:.2f}° | ws {ws_real:.2f} m/s | grid {nx}×{ny} ({cells:,} celdas) "
                f"res {int(res_x_eff)}×{int(res_y_eff)} m"
            )

        for etiqueta, wd_target in dirs_12:
            wd_idx = int(np.argmin(np.abs(wd_disponible - wd_target)))
            wd_real = float(wd_disponible[wd_idx])
            _plot_single_wake_map(
                sim_res, x_t, y_t, grid, wd_real, ws_real, kind,
                gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff,
                n_out, res_x_eff, res_y_eff,
                title=f"12 sectores · {etiqueta}",
                subtitle=f"obj {wd_target:.1f}°",
                type_i_t=type_i_t,
                type_labels=type_labels_t
            )
            _debug_print(
                f"[INFO] 12 sectores · {etiqueta}: wd {wd_real:.2f}° | ws {ws_real:.2f} m/s | grid {nx}×{ny} ({cells:,} celdas) "
                f"res {int(res_x_eff)}×{int(res_y_eff)} m"
            )

        energetic = _pick_most_energetic_wd(sim_res, wd_disponible)
        if energetic is not None:
            wd_best, e_best = energetic
            _plot_single_wake_map(
                sim_res, x_t, y_t, grid, wd_best, ws_real, kind,
                gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff,
                n_out, res_x_eff, res_y_eff,
                title="Sector más energético",
                subtitle=f"AEP dir={e_best:,.2f}",
                type_i_t=type_i_t,
                type_labels=type_labels_t
            )
            _debug_print(
                f"[INFO] Sector más energético: wd {wd_best:.2f}° | AEP_dir {e_best:,.2f} | ws {ws_real:.2f} m/s"
            )
        else:
            _debug_print("[WARN] No se pudo identificar automáticamente el sector más energético; solo se generaron las figuras direccionales.")

        if n_out:
            _debug_print(f"[INFO] Turbinas descartadas: {n_out} de {n_total}")
        _debug_print(f"[INFO] Dominio ({kind}): X[{sx_min:.3f},{sx_max:.3f}]  Y[{sy_min:.3f},{sy_max:.3f}]")

    except Exception as e:
        _msg_err("Crear Graficas", f"Error al generar las gráficas:\n{e}", parent)
        import traceback
        if _is_debug_enabled():
            traceback.print_exc()
