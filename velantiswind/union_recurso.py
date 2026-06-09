# -*- coding: utf-8 -*-
"""
union_recurso.py  (WaspGridSite con DSAA idéntico a WAsP y carpeta estricta para py_wake)

- Mosaica tiles de WAsP y escribe una carpeta con Surfer ASCII Grid (DSAA) “estilo WAsP”.
- De 'Sector All' se procesan **todas** las variables (especialmente 'Elevation').
- Crea una subcarpeta espejo **pywake_compat** con **sólo** lo que necesita py_wake:
    · Weibull-A, Weibull-k, Sector frequency, Orographic speed, Orographic turn, Mean speed (por sector/altura)
    · Elevation (Sector All por altura) y Mean speed (Sector All por altura, si existe)
  y valida los nombres con el patrón interno de py_wake; si algún nombre no casa, lo
  mueve a **pywake_compat\\_bad_for_pywake** para evitar el crash.

CLI:
  python union_recurso.py --waspgridsite OUT_DIR TILE_DIR_A TILE_DIR_B [TILE_DIR_C ...]
"""

from typing import Tuple, List, Dict, Optional, Iterable
import os
import re
import sys
import shutil
import numpy as np
from osgeo import gdal, osr

# ====== QGIS GUI opcional ====== #
try:
    from qgis.PyQt import QtWidgets  # type: ignore
    _HAS_QT = True
except Exception:
    _HAS_QT = False

DEBUG = str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}

# === Comportamiento ===
INCLUIR_TODO_ALL = True           # mosaicear cualquier variable presente en "Sector All"
IGNORAR_SECTOR_360 = True         # descarta 360º si hay 1..359
CREAR_ESPEJO_PYWAKE = True        # crea subcarpeta 'pywake_compat' (estricta)
SUBDIR_PYWAKE = "pywake_compat"

FORZAR_FREQ_A_FRACCION = True     # si detecta Sector frequency en %, pasar a 0..1

_SURFER_NODATA = -1.0e38  # NoData WAsP/Surfer

def _dbg(msg: str) -> None:
    if DEBUG:
        print(f"[pwc] {msg}")

# ======================= CRS (EPSG configurable) ======================= #
_EPSG = 25830  # valor por defecto: ETRS89 / UTM zone 30N

def set_epsg(epsg: int) -> None:
    """Fija el EPSG que se usará como CRS de trabajo para toda la unión."""
    global _EPSG
    _EPSG = int(epsg)
    _dbg(f"CRS de trabajo seleccionado: EPSG:{_EPSG}")

def _wkt_25830() -> str:
    """
    Nombre mantenido por compatibilidad; ahora devuelve el WKT
    del EPSG que haya seleccionado el usuario.
    """
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(_EPSG)
    return srs.ExportToWkt()

def _ask_epsg_cli(default: int = 25830) -> int:
    """
    Pregunta por consola el EPSG a usar para la unión.
    Enter vacío → usa el valor por defecto.
    """
    try:
        txt = input(f"EPSG de trabajo (enter para {default}): ").strip()
    except EOFError:
        return default

    if not txt:
        return default

    try:
        return int(txt)
    except ValueError:
        print("EPSG no válido; se usa el valor por defecto.")
        return default

# ======================= Lectura ráster ======================= #
def _read_grd(path: str) -> Tuple[np.ndarray, tuple]:
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    if ds is None:
        raise IOError(f"No se puede abrir: {path}")
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(float)
    gt = ds.GetGeoTransform()
    return arr, gt

# ======================= Parseo por nombre ======================= #
_RX_SECTOR = re.compile(r"[Ss]ector\D*(\d+)")
_RX_SECTOR_ALL = re.compile(r"[Ss]ector\s*All")
_RX_HEIGHT = re.compile(r"[Hh]eight\D*(\d+)\s*m")

_VAR_PATTERNS = [
    (re.compile(r"Weibull-?A", re.IGNORECASE), "Weibull_A"),
    (re.compile(r"Weibull-?k", re.IGNORECASE), "Weibull_k"),
    (re.compile(r"Sector\s*frequency|wd[_\s-]*freq", re.IGNORECASE), "Sector_frequency"),
    (re.compile(r"(^|[^A-Za-z])WS([^A-Za-z]|$)", re.IGNORECASE), "WS"),
    (re.compile(r"Mean\s*speed", re.IGNORECASE), "WS"),
    (re.compile(r"oro?grap?h?ic\s*speed(?:-?\s*up)?|Speed\s*up|Speedup", re.IGNORECASE), "Speedup"),
    (re.compile(r"Turning|veer|oro?grap?h?ic\s*turn", re.IGNORECASE), "Turning"),
    (re.compile(r"(^|[^A-Za-z])TI([^A-Za-z]|$)", re.IGNORECASE), "TI"),
    (re.compile(r"Turbulence\s*intensity|Turbulen[ct]?\s*intensi\w*", re.IGNORECASE), "TI"),
    (re.compile(r"Elevation", re.IGNORECASE), "Elevation"),
]

# Nombre de exportación exactamente como lo espera py_wake
_EXPORT_NAMES = {
    "Weibull_A": "Weibull-A",
    "Weibull_k": "Weibull-k",
    "Sector_frequency": "Sector frequency",
    "WS": "Mean speed",
    "Speedup": "Orographic speed",
    "Turning": "Orographic turn",
    "TI": "Turbulence intensity",
    "Elevation": "Elevation",
}

# Variables a reflejar en pywake_compat (lo que necesita py_wake + Mean speed a petición)
_PYWAKE_MIN = {"Weibull_A", "Weibull_k", "Sector_frequency", "Speedup", "Turning", "Elevation", "WS"}

def _canonical_var_from_filename(filename: str) -> Optional[str]:
    for pat, name in _VAR_PATTERNS:
        if pat.search(filename):
            return name
    return None

def _parse_meta(filename: str):
    sec = _RX_SECTOR.search(filename)
    sec_all = bool(_RX_SECTOR_ALL.search(filename))
    hei = _RX_HEIGHT.search(filename)
    sector = int(sec.group(1)) if sec else (0 if sec_all else None)  # 0 = All
    height = float(hei.group(1)) if hei else None
    variable = _canonical_var_from_filename(filename)
    return sector, height, variable, sec_all

# ======================= Utilidades ficheros ======================= #
def _listar_archivos(folder: str) -> List[str]:
    files = []
    for f in os.listdir(folder):
        fp = os.path.join(folder, f)
        if os.path.isfile(fp) and f.lower().endswith(".grd"):
            files.append(fp)
    return files

# ======================= Nomenclatura de salida ======================= #
def _out_name(grid_id: int, sector: int, height: float, var: str) -> str:
    r"""
    Nombres compatibles con el patrón de py_wake:
      'Sector (\w+|\d+) \s+ Height (\d+\.?\d*)m \s+ ([a-zA-Z0-9\- ]+)'
    OJO: ese patrón tiene espacios literales alrededor de los \s+, por lo que
    en la práctica exige **3 espacios**:
      • entre "Sector <n>" y "Height ..."
      • entre "...m" y "<Variable>"
    Además, mantenemos 2 espacios entre 'Resource grid <id>' y 'Sector ...'
    para imitar el estilo WAsP.
    """
    label = _EXPORT_NAMES.get(var, var)
    sep2 = "  "   # tras 'Resource grid <id>'
    sep3 = "   "  # antes de 'Height ...' y antes de '<Variable>'

    if sector == 0:  # 'Sector All'
        return f"Resource grid {grid_id}{sep2}Sector All{sep3}Height {int(height)}m{sep3}{label}.grd"
    else:
        # entre 'Sector' y el número va 1 espacio (el regex lo pide así)
        return f"Resource grid {grid_id}{sep2}Sector {sector}{sep3}Height {int(height)}m{sep3}{label}.grd"


# ======================= Escritura DSAA estilo WAsP ======================= #
def _fmt_head_number(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.6f}"

def _write_dsaa_waspstyle(out_path: str, arr: np.ndarray, gt: tuple, nodata: float = _SURFER_NODATA) -> None:
    nx = int(arr.shape[1]); ny = int(arr.shape[0])
    x0, dx, _, y0, _, dy = gt

    # centros de celda
    x_min_c = x0 + dx*0.5
    x_max_c = x0 + dx*(nx - 0.5)
    y_top_c = y0 + dy*0.5
    y_bot_c = y0 + dy*(ny - 0.5)
    y_min_c, y_max_c = (y_bot_c, y_top_c) if dy < 0 else (y_top_c, y_bot_c)

    data = np.flipud(arr) if dy < 0 else arr

    mask = np.isfinite(data) & (data != nodata)
    zmin = float(np.min(data[mask])) if np.any(mask) else 0.0
    zmax = float(np.max(data[mask])) if np.any(mask) else 0.0

    EOL = "\r\n"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("DSAA" + EOL)
        f.write(f"{nx}  {ny}" + EOL)  # doble espacio como WAsP
        f.write(f" {_fmt_head_number(x_min_c)}   {_fmt_head_number(x_max_c)}" + EOL)
        f.write(f" {_fmt_head_number(y_min_c)}   {_fmt_head_number(y_max_c)}" + EOL)
        f.write(f" {zmin:.6f}   {zmax:.6f}" + EOL)
        for j in range(ny):
            row = data[j, :]
            row = np.where(np.isfinite(row), row, nodata)
            first = f"{row[0]:.6f}"
            rest = "".join(f"{v:15.6f}" for v in row[1:])
            f.write(first + rest + EOL)

# ======================= Mosaico en memoria (GDAL VRT) ======================= #
def _mosaic_to_mem(inputs: List[str]) -> Tuple[np.ndarray, tuple]:
    if not inputs:
        raise ValueError("mosaic: lista de entrada vacía")
    vrt = gdal.BuildVRT("/vsimem/_tmp.vrt", inputs,
                        srcNodata=_SURFER_NODATA, VRTNodata=_SURFER_NODATA)
    if vrt is None:
        raise RuntimeError("BuildVRT devolvió None; revisa los paths")
    band = vrt.GetRasterBand(1)
    arr = band.ReadAsArray().astype(float)
    gt = vrt.GetGeoTransform()
    vrt = None
    return arr, gt

def mosaic_grd_dsaa(inputs: List[str], out_path: str, var: Optional[str] = None) -> None:
    _dbg(f"MOSAIC → {os.path.basename(out_path)}  | inputs={len(inputs)}  driver=GSAG")
    arr, gt = _mosaic_to_mem(inputs)

    # Normalización opcional de Sector frequency (si llega en %)
    if FORZAR_FREQ_A_FRACCION and var == "Sector_frequency":
        vmax = float(np.nanmax(arr))
        if vmax > 1.0 + 1e-6:  # parece % (0..100)
            _dbg("   · 'Sector frequency' detectada en % → convirtiendo a fracción 0–1")
            arr = arr / 100.0

    _write_dsaa_waspstyle(out_path, arr, gt, _SURFER_NODATA)
    _dbg(f"DSAA ✓ {os.path.basename(out_path)}")

# ======================= Escaneo de tiles ======================= #
class _Entry:
    __slots__ = ("path", "var", "sector", "height")
    def __init__(self, path: str, var: str, sector: int, height: float) -> None:
        self.path = path
        self.var = var
        self.sector = sector
        self.height = height

def _scan_tiles(dirs: Iterable[str]):
    """
    Devuelve:
      entries: lista de _Entry para sectores numéricos (1..360)
      all_by_hv: dict[(altura, var)] -> [lista de paths (Sector All)]
    """
    entries: List[_Entry] = []
    all_by_hv: Dict[Tuple[float, str], List[str]] = {}

    for d in dirs:
        files = _listar_archivos(d)
        _dbg(f"Leyendo {len(files)} ficheros en: {d}")
        for p in files:
            fname = os.path.basename(p)
            sector, height, var, is_all = _parse_meta(fname)

            if is_all:
                if INCLUIR_TODO_ALL and var is not None and height is not None:
                    all_by_hv.setdefault((height, var), []).append(p)
                    _dbg(f"  · (ALL) añadido h={int(height)}m, var={var}: {fname}")
                else:
                    _dbg(f"  · Skip (ALL): {fname}")
                continue

            # Resto: sectores numéricos válidos
            if sector is None or height is None or var is None:
                _dbg(f"  · Skip (sin meta reconocible): {fname}")
                continue

            entries.append(_Entry(p, var, int(sector), float(height)))

    if not entries and not all_by_hv:
        raise RuntimeError("No se encontraron GRD válidos en los directorios dados")
    return entries, all_by_hv

# ======================= Validación “anti-crash” para py_wake ======================= #
# Patrón que usa py_wake 2.6.12 dentro de wasp_grid_site.py
_PYW_RE = re.compile(r"Sector (\w+|\d+)\s+ Height (\d+\.?\d*)m\s+ ([a-zA-Z0-9\- ]+)")

def _validate_dir_for_pywake(dirpath: str) -> Dict[str, int]:
    """
    Revisa todos los .grd; si alguno NO casa con _PYW_RE en su **ruta completa**,
    lo mueve a dirpath\\_bad_for_pywake para que no provoque IndexError en py_wake.
    """
    bad_dir = os.path.join(dirpath, "_bad_for_pywake")
    os.makedirs(bad_dir, exist_ok=True)
    total = 0
    moved = 0
    for f in os.listdir(dirpath):
        if not f.lower().endswith(".grd"):
            continue
        total += 1
        full = os.path.join(dirpath, f)
        if not _PYW_RE.search(full):
            _dbg(f"[VALIDATE] NO MATCH para py_wake → {f}  (se mueve a _bad_for_pywake)")
            shutil.move(full, os.path.join(bad_dir, f))
            moved += 1
    _dbg(f"[VALIDATE] pywake_compat: {total} archivos | movidos a _bad_for_pywake: {moved}")
    return {"total": total, "moved": moved}

# ======================= Construcción WaspGridSite ======================= #
def construir_waspgridsite(dirs_tiles: List[str], out_dir: str, grid_id: int = 1) -> Dict[str, int]:
    """
    Genera una única carpeta con GRD DSAA por (Variable, Sector, Altura),
    y mosaica también las variables de 'Sector All' por altura.
    Además, si CREAR_ESPEJO_PYWAKE=True, crea 'pywake_compat' con **sólo**:
      A, k, Sector frequency, Orographic speed, Orographic turn, Mean speed (por-sector)
      y Elevation (Sector All por altura) (+ Mean speed All si existe),
    y valida los nombres con el patrón interno de py_wake para evitar el parche.
    """
    os.makedirs(out_dir, exist_ok=True)
    entries, all_by_hv = _scan_tiles(dirs_tiles)

    # Conjuntos detectados (solo de sectores numéricos)
    sectors = sorted({e.sector for e in entries if 1 <= e.sector <= 360})
    if IGNORAR_SECTOR_360 and 360 in sectors and any(s < 360 for s in sectors):
        sectors.remove(360)
        _dbg("Heurística: eliminado sector 360 (posible omni/duplicado de 0°)")
    heights = sorted({e.height for e in entries})
    vars_present = sorted({e.var for e in entries})
    vars_all_present = sorted({v for (_, v) in all_by_hv.keys()})
    vars_total = sorted(set(vars_present) | set(vars_all_present))

    # Agrupar por (var, sector, altura)
    buckets: Dict[Tuple[str, int, float], List[str]] = {}
    for e in entries:
        buckets.setdefault((e.var, e.sector, e.height), []).append(e.path)

    # Info de Sector_frequency
    sf_any = next((p for (v, *_), files in buckets.items() if v == "Sector_frequency" for p in files), None)
    if sf_any:
        arr, _ = _read_grd(sf_any)
        if float(np.nanmax(arr)) > 1.0 + 1e-6:
            _dbg("AVISO: 'Sector frequency' parece estar en % (>1.0). Se convertirá a fracción si FORZAR_FREQ_A_FRACCION=True.")

    _dbg(f"Resumen detectado → sectores={len(sectors)}  alturas={heights}  vars={sorted(vars_total)}")

    # Carpetas de salida
    out_pywake = os.path.join(out_dir, SUBDIR_PYWAKE) if CREAR_ESPEJO_PYWAKE else None
    if out_pywake:
        if os.path.exists(out_pywake):
            # limpia por si había restos de ejecuciones anteriores
            for f in os.listdir(out_pywake):
                fp = os.path.join(out_pywake, f)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                except Exception:
                    pass
        os.makedirs(out_pywake, exist_ok=True)

    # Mosaico de (var,sector,altura) en carpeta principal
    n_out = 0
    n_skipped = 0

    for v in sorted(vars_present):
        for h in heights:
            for s in sectors:
                inputs = buckets.get((v, s, h), [])
                if not inputs:
                    n_skipped += 1
                    continue

                # 1) Fichero principal estilo WAsP (dos espacios)
                out_name_wasp = _out_name(grid_id, s, h, v)
                out_path_wasp = os.path.join(out_dir, out_name_wasp)
                mosaic_grd_dsaa(inputs, out_path_wasp, var=v)
                n_out += 1

                # 2) Si es una de las mínimas → duplicamos en pywake_compat
                if out_pywake and v in _PYWAKE_MIN:
                    out_name_py = _out_name(grid_id, s, h, v)
                    shutil.copy2(out_path_wasp, os.path.join(out_pywake, out_name_py))

    # Mosaico de TODAS las variables de Sector All por altura (solo carpeta principal)
    for (h, v), inputs in sorted(all_by_hv.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if not inputs:
            continue
        dst = os.path.join(out_dir, _out_name(grid_id, 0, h, v))
        mosaic_grd_dsaa(inputs, dst, var=v)
        n_out += 1

        # Elevation y Mean speed (All) también al espejo para py_wake (si existen)
        if out_pywake and v in {"Elevation", "WS"}:
            shutil.copy2(dst, os.path.join(out_pywake, os.path.basename(dst)))

    _dbg(f"CREACIÓN COMPLETADA → escritos {n_out} GRD  | omitidos {n_skipped}")
    _dbg("Driver usado: GSAG (DSAA)")

    # ===== Validación final para evitar el parche en py_wake =====
    moved = 0
    if out_pywake:
        stats = _validate_dir_for_pywake(out_pywake)
        moved = stats["moved"]

    return {
        "n_out": n_out,
        "n_skipped": n_skipped,
        "n_sectors": len(sectors),
        "n_heights": len(heights),
        "vars": len(vars_total),
        "driver": "GSAG",
        "pywake_dir": out_pywake or "",
        "pywake_bad_moved": moved,
        "epsg": _EPSG,
    }

# ======================= GUI específica WaspGridSite =================== #
def ejecutar_waspgridsite(parent=None):
    if not _HAS_QT:
        raise RuntimeError("La GUI de QGIS/Qt no está disponible en este entorno.")
    try:
        QtWidgets.QMessageBox.information(
            parent,
            "WaspGridSite",
            "Se generará UNA carpeta con GRD mosaico (Sector/Altura/Variable).\n"
            "Selecciona 2 o más carpetas de tiles exportadas desde WAsP.\n"
            "• 'Sector All': se tomarán TODAS las variables presentes (mosaico por altura).\n"
            "• Además, se crea subcarpeta 'pywake_compat' estricta (sin necesidad de parches).\n"
            "• Salida en Surfer ASCII (DSAA) con formato WAsP.",
        )
        dlg = QtWidgets.QFileDialog(parent, "Selecciona carpetas de tiles (WAsP)")
        dlg.setFileMode(QtWidgets.QFileDialog.Directory)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        dlg.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        for view in dlg.findChildren((QtWidgets.QListView, QtWidgets.QTreeView)):
            view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            QtWidgets.QMessageBox.information(parent, "WaspGridSite", "No se seleccionaron carpetas.")
            return None
        in_dirs = [u.toLocalFile() for u in dlg.selectedUrls()]

        out_dir = QtWidgets.QFileDialog.getExistingDirectory(parent, "Selecciona carpeta de salida", os.path.dirname(in_dirs[0]))
        if not out_dir:
            QtWidgets.QMessageBox.information(parent, "WaspGridSite", "No se seleccionó carpeta de salida.")
            return None

        # Preguntar EPSG antes de hacer la unión
        epsg_default = _EPSG
        txt, ok = QtWidgets.QInputDialog.getText(
            parent,
            "CRS de trabajo (EPSG)",
            "Introduce el EPSG en el que están las coordenadas de los tiles.\n"
            "Por ejemplo:\n"
            "  • 25829 → ETRS89 / UTM 29N (Galicia oeste)\n"
            "  • 25830 → ETRS89 / UTM 30N (gran parte de España)\n\n"
            f"Deja vacío para usar {epsg_default}.",
        )
        if ok:
            txt = txt.strip()
            if txt:
                try:
                    set_epsg(int(txt))
                except ValueError:
                    QtWidgets.QMessageBox.warning(
                        parent,
                        "WaspGridSite",
                        f"EPSG no válido. Se seguirá usando EPSG:{epsg_default}."
                    )
                    set_epsg(epsg_default)
            else:
                set_epsg(epsg_default)

        res = construir_waspgridsite(in_dirs, out_dir, grid_id=1)
        msg = (
            f"Escritura completada en: {out_dir}\n"
            f"Ficheros escritos: {res['n_out']}  | omitidos: {res['n_skipped']}\n"
            f"Sectores: {res['n_sectors']}  Alturas: {res['n_heights']}  Variables: {res['vars']}\n"
            f"CRS de trabajo (EPSG): {res.get('epsg', '?')}\n"
            f"Driver: {res['driver']}\n"
            f"py_wake dir: {res['pywake_dir'] or '(no creado)'}\n"
            f"Movidos a _bad_for_pywake (para evitar crash): {res.get('pywake_bad_moved', 0)}\n"
        )
        QtWidgets.QMessageBox.information(parent, "WaspGridSite", msg)
        return res
    except Exception as e:
        QtWidgets.QMessageBox.critical(parent, "WaspGridSite", f"Ocurrió un error:\n{e}")
        return None

# ======================= Compat nombre antiguo ======================= #
def ejecutar_union_recurso(parent=None, *_args, **_kwargs):
    return ejecutar_waspgridsite(parent=parent)

__all__ = [
    "construir_waspgridsite",
    "ejecutar_waspgridsite",
    "ejecutar_union_recurso",
]

# ======================= CLI ======================= #
if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--waspgridsite":
        if len(sys.argv) < 4:
            print("Uso: python union_recurso.py --waspgridsite OUT_DIR TILE_DIR_A [TILE_DIR_B ...]")
            sys.exit(1)
        out_dir = sys.argv[2]
        tile_dirs = sys.argv[3:]

        # Preguntar EPSG en modo consola
        epsg = _ask_epsg_cli(default=_EPSG)
        set_epsg(epsg)

        summary = construir_waspgridsite(tile_dirs, out_dir, grid_id=1)
        print(
            f"OK WaspGridSite. Escritos={summary['n_out']} omitidos={summary['n_skipped']} "
            f"sectores={summary['n_sectors']} alturas={summary['n_heights']} epsg={summary.get('epsg','?')} "
            f"driver={summary['driver']} pywake_dir={summary['pywake_dir']} "
            f"moved_bad={summary.get('pywake_bad_moved',0)}"
        )
        sys.exit(0)

    print("Uso: python union_recurso.py --waspgridsite OUT_DIR tileA tileB [...]")
    sys.exit(1)
