# -*- coding: utf-8 -*-
"""
Timezone utilities for the shadow flicker module.

The shadow engine supports two time bases:
- IANA civil time (recommended): e.g. Europe/Madrid, America/Santiago.
  Python applies daylight-saving time (DST) from an IANA timezone database.
- Fixed UTC offset (fixed-offset): e.g. UTC+1 all year.

This module is designed to avoid the heavy ``timezonefinder`` dependency in
QGIS/OSGeo4W. Instead it ships a bundled IANA timezone catalogue and a bundled
TZif database under ``assets/tzdata/zoneinfo``. Detection from coordinates is
therefore intentionally conservative: common wind-market bounding boxes are
used as a convenience, but the user can always select the correct IANA zone
manually from the full list.

Runtime loading order for DST rules:
1) Python stdlib ``zoneinfo`` using the OS database or the optional ``tzdata``
   package if present.
2) Bundled plugin TZif files from ``assets/tzdata/zoneinfo``.
3) ``python-dateutil`` fallback, if installed.
4) Fixed-offset mode if IANA loading is not possible.
"""

from __future__ import annotations

import os
from datetime import timedelta, timezone
from typing import List, Optional, Tuple

from .i18n_local import tr4 as _ml, timezone_label_local

_DEFAULT_TZ = "UTC"


def _plugin_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def bundled_tzdata_root() -> str:
    return os.path.join(_plugin_root(), "assets", "tzdata")


def bundled_zone_tab_path() -> str:
    return os.path.join(bundled_tzdata_root(), "zone.tab")


def bundled_zone1970_tab_path() -> str:
    return os.path.join(bundled_tzdata_root(), "zone1970.tab")


def bundled_full_catalog_path() -> str:
    return os.path.join(bundled_tzdata_root(), "iana_timezones_full.txt")


def bundled_zoneinfo_dir_path() -> str:
    return os.path.join(bundled_tzdata_root(), "zoneinfo")


def bundled_tzdata_version() -> str:
    path = os.path.join(bundled_tzdata_root(), "tzdata_version.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "unknown"


# Curated front-list used to keep common wind-market zones near the top.
COMMON_TIMEZONES = [
    "UTC",
    "Europe/Madrid", "Atlantic/Canary", "Europe/Lisbon", "Europe/London",
    "Europe/Dublin", "Europe/Paris", "Europe/Berlin", "Europe/Rome",
    "Europe/Brussels", "Europe/Amsterdam", "Europe/Zurich", "Europe/Vienna",
    "Europe/Warsaw", "Europe/Athens", "Europe/Istanbul", "Europe/Moscow",
    "Africa/Casablanca", "Africa/Algiers", "Africa/Tunis", "Africa/Cairo",
    "Africa/Johannesburg", "Africa/Nairobi",
    "America/Santiago", "America/Punta_Arenas", "Pacific/Easter",
    "America/Argentina/Buenos_Aires", "America/Montevideo", "America/Sao_Paulo",
    "America/Bogota", "America/Lima", "America/Caracas", "America/Mexico_City",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Anchorage", "Pacific/Honolulu", "America/Toronto",
    "America/Vancouver",
    "Asia/Dubai", "Asia/Riyadh", "Asia/Kolkata", "Asia/Bangkok", "Asia/Singapore",
    "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul",
    "Australia/Perth", "Australia/Adelaide", "Australia/Brisbane", "Australia/Sydney",
    "Australia/Melbourne", "Pacific/Auckland",
]


def _read_simple_zone_list(path: str, zones: set) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                z = line.strip()
                if z and not z.startswith("#"):
                    zones.add(z)
    except Exception:
        pass


def _read_zone_tab(path: str, zones: set) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    zones.add(parts[2].strip())
    except Exception:
        pass


def _scan_bundled_zoneinfo(zones: set) -> None:
    """Add all bundled TZif file names as potential IANA zones/aliases."""
    root = bundled_zoneinfo_dir_path()
    if not os.path.isdir(root):
        return
    excluded_files = {"iso3166.tab", "zone.tab", "zone1970.tab", "zonenow.tab", "tzdata.zi", "leapseconds"}
    excluded_zones = {"Factory", "localtime", "posixrules"}
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if filename in excluded_files:
                continue
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel.startswith(("posix/", "right/")) or rel in excluded_zones:
                continue
            zones.add(rel)


def load_iana_timezones() -> List[str]:
    """
    Return a broad IANA timezone name list for UI use.

    The list is intentionally larger than ``zone.tab``: it includes canonical
    geographic zones plus backward-compatible aliases such as
    ``US/Eastern``, ``CET`` or ``Etc/GMT-1`` when they exist in the bundled DB.
    """
    zones = set(COMMON_TIMEZONES)

    # Full bundled catalogue generated from tzdata. This keeps the UI complete
    # even on Windows environments where zoneinfo.available_timezones() is empty.
    _read_simple_zone_list(bundled_full_catalog_path(), zones)

    # Canonical geographic catalogues.
    _read_zone_tab(bundled_zone_tab_path(), zones)
    _read_zone_tab(bundled_zone1970_tab_path(), zones)

    # Safety net: scan bundled TZif files directly.
    _scan_bundled_zoneinfo(zones)

    # Runtime DB, if available, can add aliases provided by the OS/tzdata wheel.
    try:
        from zoneinfo import available_timezones  # type: ignore
        for z in available_timezones():
            if z and not z.startswith(("posix/", "right/")) and z not in {"localtime", "posixrules", "Factory"}:
                zones.add(z)
    except Exception:
        pass

    common = [z for z in COMMON_TIMEZONES if z in zones]
    rest = sorted(z for z in zones if z not in set(common))
    return common + rest


def _get_bundled_zoneinfo(tz_name: str):
    """Load tzinfo from bundled TZif files using zoneinfo.ZoneInfo.from_file."""
    try:
        from zoneinfo import ZoneInfo  # type: ignore
    except Exception as e:
        raise ValueError(_ml(
            "Python zoneinfo no está disponible en este entorno: {}",
            "Python zoneinfo is not available in this environment: {}",
            "Python zoneinfo n’est pas disponible dans cet environnement : {}",
            "Python zoneinfo ist in dieser Umgebung nicht verfügbar: {}",
        ).format(e))

    safe_name = (tz_name or _DEFAULT_TZ).strip().replace("\\", "/")
    if safe_name.startswith("/") or ".." in safe_name.split("/"):
        raise ValueError(_ml(
            "Nombre de zona horaria no válido: '{}'",
            "Invalid timezone name: '{}'",
            "Nom de fuseau horaire invalide : '{}'",
            "Ungültiger Zeitzonenname: '{}'",
        ).format(tz_name))

    path = os.path.join(bundled_zoneinfo_dir_path(), *safe_name.split("/"))
    if not os.path.isfile(path):
        raise ValueError(_ml(
            "La zona '{}' no existe en la base IANA incluida.",
            "Zone '{}' does not exist in the bundled IANA database.",
            "La zone '{}' n’existe pas dans la base IANA incluse.",
            "Die Zone '{}' ist in der mitgelieferten IANA-Datenbank nicht vorhanden.",
        ).format(tz_name))

    with open(path, "rb") as f:
        return ZoneInfo.from_file(f, key=safe_name)


def get_tzinfo(tz_name: Optional[str]):
    """
    Return a tzinfo object for an IANA timezone name.

    Raises ValueError if the timezone cannot be loaded from system/tzdata,
    bundled plugin tzdata, or dateutil fallback.
    """
    name = (tz_name or _DEFAULT_TZ).strip() or _DEFAULT_TZ

    if name.upper() in ("UTC", "Z"):
        return timezone.utc

    zoneinfo_error = None

    # Python 3.9+: uses system tzdb on Linux/macOS or the optional tzdata wheel.
    try:
        from zoneinfo import ZoneInfo  # type: ignore
        return ZoneInfo(name)
    except Exception as e:
        zoneinfo_error = e

    # Plugin-bundled IANA TZif database. This avoids needing timezonefinder and
    # also avoids relying on OS-level timezone files on Windows.
    try:
        return _get_bundled_zoneinfo(name)
    except Exception as e_bundled:
        bundled_error = e_bundled

    # Fallback often available in scientific/QGIS Python environments.
    try:
        from dateutil import tz  # type: ignore
        tzinfo = tz.gettz(name)
        if tzinfo is not None:
            return tzinfo
    except Exception:
        pass

    raise ValueError(_ml(
        "No se pudo cargar la zona horaria IANA '{}'. La repo incluye una base IANA local, pero esa zona no se encontró o no pudo abrirse. Prueba con una zona como 'Europe/Madrid' o usa el modo UTC offset fijo. Error zoneinfo: {}; error de la base incluida: {}",
        "Could not load IANA timezone '{}'. The plugin includes a local IANA database, but this zone was not found or could not be opened. Try a zone such as 'Europe/Madrid' or use fixed UTC-offset mode. zoneinfo error: {}; bundled database error: {}",
        "Impossible de charger le fuseau horaire IANA '{}'. Le plugin inclut une base IANA locale, mais cette zone est introuvable ou n’a pas pu être ouverte. Essayez une zone comme 'Europe/Madrid' ou utilisez le mode décalage UTC fixe. Erreur zoneinfo : {}; erreur de la base incluse : {}",
        "Die IANA-Zeitzone '{}' konnte nicht geladen werden. Das Plugin enthält eine lokale IANA-Datenbank, aber diese Zone wurde nicht gefunden oder konnte nicht geöffnet werden. Versuchen Sie eine Zone wie 'Europe/Madrid' oder verwenden Sie den festen UTC-Offset-Modus. zoneinfo-Fehler: {}; Fehler der mitgelieferten Datenbank: {}",
    ).format(name, zoneinfo_error, bundled_error))


def fixed_offset_tz(offset_hours: float):
    minutes = int(round(float(offset_hours) * 60.0))
    return timezone(timedelta(minutes=minutes))


def timezone_label(timezone_mode: str, timezone_name: Optional[str], utc_offset: float) -> str:
    return timezone_label_local(timezone_mode, timezone_name, utc_offset)


def offset_to_etc_timezone(offset_hours: float) -> str:
    """
    Convert UTC offset to an Etc/GMT zone name.

    Note: Etc/GMT sign is intentionally reversed by IANA convention.
    UTC+1 -> Etc/GMT-1, UTC-5 -> Etc/GMT+5.
    """
    rounded = int(round(offset_hours))
    if rounded == 0:
        return "Etc/GMT"
    sign = "-" if rounded > 0 else "+"
    return f"Etc/GMT{sign}{abs(rounded)}"


def _in(lat: float, lon: float, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _approx_warning(extra: str = "") -> str:
    msg = _ml(
        "Autodetección aproximada sin polígonos mundiales; verifica la zona horaria en el desplegable IANA.",
        "Approximate autodetection without worldwide polygons; verify the timezone in the IANA dropdown.",
        "Autodétection approximative sans polygones mondiaux ; vérifiez le fuseau horaire dans la liste IANA.",
        "Ungefähre automatische Erkennung ohne weltweite Polygone; prüfen Sie die Zeitzone in der IANA-Auswahlliste.",
    )
    if extra:
        msg += " " + extra
    return msg


def detect_timezone_name(latitude: float, longitude: float) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Detect a best-effort IANA timezone from WGS84 coordinates without heavy deps.

    Returns: (timezone_name, method, warning)

    Without a polygon engine such as timezonefinder, fully reliable worldwide
    detection is not possible. This function therefore only provides a curated
    approximation for common wind markets and otherwise asks the user to select
    the correct IANA zone manually from the bundled full database.
    """
    lat = float(latitude)
    lon = float(longitude)

    # Europe / Atlantic
    if _in(lat, lon, 27.0, 30.7, -18.7, -13.0):
        return "Atlantic/Canary", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 35.0, 44.5, -9.8, 4.8):
        return "Europe/Madrid", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 36.5, 42.5, -9.8, -6.0):
        return "Europe/Lisbon", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 49.0, 61.5, -11.0, 2.5):
        return "Europe/London", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 41.0, 51.5, -5.5, 10.5):
        return "Europe/Paris", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 45.0, 56.0, 5.0, 16.0):
        return "Europe/Berlin", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 35.0, 48.5, 6.0, 19.0):
        return "Europe/Rome", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 35.0, 43.0, 19.0, 30.5):
        return "Europe/Athens", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 35.0, 42.5, 25.0, 45.0):
        return "Europe/Istanbul", "bundled approximate bbox", _approx_warning()

    # North Africa / Middle East
    if _in(lat, lon, 27.0, 36.5, -13.5, -0.5):
        return "Africa/Casablanca", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 18.0, 37.5, -9.5, 12.5):
        return "Africa/Algiers", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 19.0, 38.0, 24.0, 37.0):
        return "Africa/Cairo", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 12.0, 33.5, 34.0, 56.0):
        return "Asia/Riyadh", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 22.0, 27.5, 51.0, 57.0):
        return "Asia/Dubai", "bundled approximate bbox", _approx_warning()

    # Africa, coarse regional defaults used by many project reports.
    if _in(lat, lon, -35.0, -20.0, 16.0, 33.5):
        return "Africa/Johannesburg", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, -6.0, 12.5, 32.0, 52.0):
        return "Africa/Nairobi", "bundled approximate bbox", _approx_warning()

    # South America
    if _in(lat, lon, -56.5, -17.0, -76.0, -66.0):
        return "America/Santiago", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, -55.5, -21.0, -73.5, -53.5):
        return "America/Argentina/Buenos_Aires", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, -35.5, 5.5, -74.0, -34.0):
        return "America/Sao_Paulo", "bundled approximate bbox", _approx_warning(_ml("Brasil tiene varias zonas; selecciona manualmente si aplica.", "Brazil has multiple timezones; select manually if applicable.", "Le Brésil a plusieurs fuseaux horaires ; sélectionnez manuellement si nécessaire.", "Brasilien hat mehrere Zeitzonen; wählen Sie bei Bedarf manuell aus."))
    if _in(lat, lon, -19.0, 13.0, -82.0, -66.0):
        return "America/Lima", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, -5.0, 13.5, -79.5, -59.0):
        return "America/Bogota", "bundled approximate bbox", _approx_warning()

    # North America, coarse longitude split.
    if _in(lat, lon, 24.0, 50.0, -125.0, -66.0):
        if lon < -115:
            return "America/Los_Angeles", "bundled approximate longitude", _approx_warning()
        if lon < -100:
            return "America/Denver", "bundled approximate longitude", _approx_warning()
        if lon < -85:
            return "America/Chicago", "bundled approximate longitude", _approx_warning()
        return "America/New_York", "bundled approximate longitude", _approx_warning()
    if _in(lat, lon, 14.0, 33.5, -118.0, -86.0):
        return "America/Mexico_City", "bundled approximate bbox", _approx_warning(_ml("México tiene varias zonas; verifica manualmente.", "Mexico has multiple timezones; verify manually.", "Le Mexique a plusieurs fuseaux horaires ; vérifiez manuellement.", "Mexiko hat mehrere Zeitzonen; bitte manuell prüfen."))
    if _in(lat, lon, 42.0, 71.5, -141.5, -52.0):
        # Canada: approximate by longitude. Manual verification recommended.
        if lon < -123:
            return "America/Vancouver", "bundled approximate longitude", _approx_warning(_ml("Canadá tiene varias zonas; verifica manualmente.", "Canada has multiple timezones; verify manually.", "Le Canada a plusieurs fuseaux horaires ; vérifiez manuellement.", "Kanada hat mehrere Zeitzonen; bitte manuell prüfen."))
        if lon < -102:
            return "America/Edmonton", "bundled approximate longitude", _approx_warning(_ml("Canadá tiene varias zonas; verifica manualmente.", "Canada has multiple timezones; verify manually.", "Le Canada a plusieurs fuseaux horaires ; vérifiez manuellement.", "Kanada hat mehrere Zeitzonen; bitte manuell prüfen."))
        if lon < -88:
            return "America/Winnipeg", "bundled approximate longitude", _approx_warning(_ml("Canadá tiene varias zonas; verifica manualmente.", "Canada has multiple timezones; verify manually.", "Le Canada a plusieurs fuseaux horaires ; vérifiez manuellement.", "Kanada hat mehrere Zeitzonen; bitte manuell prüfen."))
        return "America/Toronto", "bundled approximate longitude", _approx_warning(_ml("Canadá tiene varias zonas; verifica manualmente.", "Canada has multiple timezones; verify manually.", "Le Canada a plusieurs fuseaux horaires ; vérifiez manuellement.", "Kanada hat mehrere Zeitzonen; bitte manuell prüfen."))

    # Asia-Pacific
    if _in(lat, lon, 6.0, 38.0, 68.0, 98.0):
        return "Asia/Kolkata", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 18.0, 54.0, 73.0, 135.0):
        return "Asia/Shanghai", "bundled approximate bbox", _approx_warning(_ml("China usa una zona oficial; verifica si el proyecto usa otra referencia.", "China uses one official timezone; verify whether the project uses another reference.", "La Chine utilise un fuseau officiel unique ; vérifiez si le projet utilise une autre référence.", "China verwendet eine offizielle Zeitzone; prüfen Sie, ob das Projekt eine andere Referenz nutzt."))
    if _in(lat, lon, 30.0, 46.0, 129.0, 146.0):
        return "Asia/Tokyo", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 33.0, 39.5, 124.0, 132.0):
        return "Asia/Seoul", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, 5.0, 21.0, 97.0, 106.5):
        return "Asia/Bangkok", "bundled approximate bbox", _approx_warning()
    if _in(lat, lon, -11.0, 6.5, 95.0, 142.0):
        return "Asia/Jakarta", "bundled approximate bbox", _approx_warning(_ml("Indonesia tiene varias zonas; verifica manualmente.", "Indonesia has multiple timezones; verify manually.", "L’Indonésie a plusieurs fuseaux horaires ; vérifiez manuellement.", "Indonesien hat mehrere Zeitzonen; bitte manuell prüfen."))
    if _in(lat, lon, -44.0, -10.0, 112.0, 154.0):
        if lon < 129:
            return "Australia/Perth", "bundled approximate longitude", _approx_warning(_ml("Australia tiene varias zonas; verifica manualmente.", "Australia has multiple timezones; verify manually.", "L’Australie a plusieurs fuseaux horaires ; vérifiez manuellement.", "Australien hat mehrere Zeitzonen; bitte manuell prüfen."))
        if lon < 141:
            return "Australia/Adelaide", "bundled approximate longitude", _approx_warning(_ml("Australia tiene varias zonas; verifica manualmente.", "Australia has multiple timezones; verify manually.", "L’Australie a plusieurs fuseaux horaires ; vérifiez manuellement.", "Australien hat mehrere Zeitzonen; bitte manuell prüfen."))
        return "Australia/Sydney", "bundled approximate longitude", _approx_warning(_ml("Australia tiene varias zonas; verifica manualmente.", "Australia has multiple timezones; verify manually.", "L’Australie a plusieurs fuseaux horaires ; vérifiez manuellement.", "Australien hat mehrere Zeitzonen; bitte manuell prüfen."))
    if _in(lat, lon, -48.0, -33.0, 165.0, 179.9):
        return "Pacific/Auckland", "bundled approximate bbox", _approx_warning()

    return None, "manual required", _ml(
        "No se pudo detectar una zona horaria fiable sin una base mundial de polígonos. Selecciona manualmente la zona IANA en el desplegable; la repo incluye un catálogo amplio y una base TZif con reglas DST.",
        "A reliable timezone could not be detected without a worldwide polygon database. Select the IANA zone manually in the dropdown; the plugin includes a broad catalogue and a TZif database with DST rules.",
        "Impossible de détecter un fuseau horaire fiable sans base mondiale de polygones. Sélectionnez manuellement la zone IANA dans la liste ; le plugin inclut un vaste catalogue et une base TZif avec règles DST.",
        "Ohne weltweite Polygondatenbank konnte keine zuverlässige Zeitzone erkannt werden. Wählen Sie die IANA-Zone manuell in der Auswahlliste; das Plugin enthält einen breiten Katalog und eine TZif-Datenbank mit DST-Regeln.",
    )
