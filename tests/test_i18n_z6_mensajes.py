# -*- coding: utf-8 -*-
"""The errors and notes of the calculation (resource, WRG, layout, wake raster, raster I/O) carry their Spanish template
with the data apart: each language shows the whole template translated and the data as they came, the Spanish text
stays as written, and an error shown later in another language is translated again from its template."""
import ast
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from qgis.PyQt import QtCore, QtWidgets

_SETTINGS = tempfile.TemporaryDirectory()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _SETTINGS.name
QtCore.QSettings.setPath(QtCore.QSettings.NativeFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, _SETTINGS.name)
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from VelantisWind import i18n  # noqa: E402
# The tables the plugin registers when it starts and when its windows open.
from VelantisWind import plugin  # noqa: E402,F401
from VelantisWind import raster_io  # noqa: E402
from VelantisWind.ag_core import aep_compute, resource_grid, wrg_reader, wrg_site  # noqa: E402
from VelantisWind.ag_core.log_text import log_error, log_text, shown  # noqa: E402
from VelantisWind.ag_core.orchestration import layout_builder, resource_loader  # noqa: E402
from VelantisWind.ag_core.qgis_io import wake_raster  # noqa: E402

_CWD = os.getcwd()
_LANGS = ("en", "fr", "de")
_PLUGIN = Path(i18n.__file__).parent
_FILES = [
    "ag_core/aep_compute.py", "ag_core/edge_cases.py", "ag_core/wrg_nodes.py", "ag_core/wrg_reader.py",
    "ag_core/wrg_site.py", "ag_core/resource_grid.py", "ag_core/resources/turbulence_grid.py", "ag_core/resources/wasp.py",
    "ag_core/orchestration/layout_builder.py", "ag_core/orchestration/resource_loader.py",
    "ag_core/orchestration/resource_settings.py", "ag_core/qgis_io/wake_raster.py", "raster_io.py",
]


# Reviewed translations: only source text, language and expected value.
_REVIEWED_TRANSLATIONS = {
    "WRG: se ha usado un único ráster de TI ambiente; si mezclas varias alturas de buje, esa TI se replica/interpola como aproximación vertical.": {
        "en": "WRG: a single ambient TI raster was used; if you mix several hub heights, that TI is replicated/interpolated as a vertical approximation.",
        "fr": "WRG : un seul raster de TI ambiante a été utilisé ; si vous mélangez plusieurs hauteurs de moyeu, cette TI est répliquée/interpolée comme approximation verticale.",
        "de": "WRG: Es wurde ein einziges Raster der Umgebungs-TI verwendet; wenn Sie mehrere Nabenhöhen mischen, wird diese TI als vertikale Näherung repliziert/interpoliert."
    },
    "WRG: se han usado {n} rásteres de TI ambiente para reconstruir TI por altura cuando es posible.": {
        "en": "WRG: {n} ambient TI rasters were used to reconstruct the TI by height where possible.",
        "fr": "WRG : {n} rasters de TI ambiante ont été utilisés pour reconstruire la TI par hauteur lorsque c’est possible.",
        "de": "WRG: Es wurden {n} Raster der Umgebungs-TI verwendet, um die TI nach Höhe zu rekonstruieren, wo dies möglich ist."
    },
    "WRG: no se ha proporcionado ráster TI, así que la TI ambiente se ha fijado al valor de respaldo definido por el usuario como campo uniforme.": {
        "en": "WRG: no TI raster was provided, so the ambient TI was set to the user-defined fallback value as a uniform field.",
        "fr": "WRG : aucun raster TI n’a été fourni ; la TI ambiante a donc été fixée à la valeur de repli définie par l’utilisateur, comme champ uniforme.",
        "de": "WRG: Es wurde kein TI-Raster angegeben, daher wurde die Umgebungs-TI auf den vom Benutzer festgelegten Rückfallwert als einheitliches Feld gesetzt."
    },
    "Hay varias alturas de buje pero solo una TI ambiente verticalmente uniforme; el cálculo sigue siendo válido, aunque es una aproximación en altura.": {
        "en": "There are several hub heights but only one vertically uniform ambient TI; the calculation is still valid, although it is an approximation in height.",
        "fr": "Il y a plusieurs hauteurs de moyeu mais une seule TI ambiante verticalement uniforme ; le calcul reste valide, bien qu’il s’agisse d’une approximation en hauteur.",
        "de": "Es gibt mehrere Nabenhöhen, aber nur eine vertikal einheitliche Umgebungs-TI; die Berechnung bleibt gültig, ist aber eine Näherung in der Höhe."
    },
    "WRG: solo hay una altura climática ({heights}); se usa como referencia vertical sin modificar la altura de buje ni inferir shear.": {
        "en": "WRG: there is only one climate height ({heights}); it is used as the vertical reference without changing the hub height or inferring shear.",
        "fr": "WRG : une seule hauteur climatique est disponible ({heights}) ; elle sert de référence verticale sans modifier la hauteur de moyeu ni déduire de cisaillement.",
        "de": "WRG: Es gibt nur eine Klimahöhe ({heights}); sie dient als vertikale Referenz, ohne die Nabenhöhe zu ändern oder eine Scherung abzuleiten."
    },
    "WRG: alturas climáticas disponibles {heights}; PyWake interpola linealmente en altura cuando la HH está dentro del rango.": {
        "en": "WRG: available climate heights {heights}; PyWake interpolates linearly in height when the HH is within the range.",
        "fr": "WRG : hauteurs climatiques disponibles {heights} ; PyWake interpole linéairement en hauteur lorsque la HH est dans la plage.",
        "de": "WRG: verfügbare Klimahöhen {heights}; PyWake interpoliert linear in der Höhe, wenn die HH innerhalb des Bereichs liegt."
    },
    "No se proporcionaron rutas WRG": {
        "en": "No WRG paths were provided",
        "fr": "Aucun chemin WRG n’a été fourni",
        "de": "Es wurden keine WRG-Pfade angegeben"
    },
    "Extensión WRG no soportada (use .wrg o .zip): {path}": {
        "en": "Unsupported WRG extension (use .wrg or .zip): {path}",
        "fr": "Extension WRG non prise en charge (utilisez .wrg ou .zip) : {path}",
        "de": "Nicht unterstützte WRG-Dateiendung (verwenden Sie .wrg oder .zip): {path}"
    },
    "No se han definido modelos de aerogeneradores": {
        "en": "No wind turbine models have been defined",
        "fr": "Aucun modèle d’éolienne n’a été défini",
        "de": "Es wurden keine Windturbinenmodelle definiert"
    },
    "No se ha podido encontrar una subcarpeta válida para PyWake en '{folder}'. Revisa la estructura exportada de WAsP.": {
        "en": "Could not find a valid PyWake subfolder in '{folder}'. Check the exported WAsP structure.",
        "fr": "Impossible de trouver un sous-dossier valide pour PyWake dans '{folder}'. Vérifiez la structure exportée de WAsP.",
        "de": "In '{folder}' wurde kein gültiger Unterordner für PyWake gefunden. Prüfen Sie die exportierte WAsP-Struktur."
    },
    "El 'site' cargado no expone 'ds'/'dataset'.": {
        "en": "The loaded 'site' does not expose 'ds'/'dataset'.",
        "fr": "Le 'site' chargé n’expose pas 'ds'/'dataset'.",
        "de": "Der geladene 'site' stellt 'ds'/'dataset' nicht bereit."
    },
    "coords_xy inválido para «{name}»: {error}": {
        "en": "Invalid coords_xy for “{name}”: {error}",
        "fr": "coords_xy non valide pour « {name} » : {error}",
        "de": "Ungültige coords_xy für „{name}“: {error}"
    },
    "coords_xy corrupto para «{name}» (longitudes distintas)": {
        "en": "Corrupt coords_xy for “{name}” (different lengths)",
        "fr": "coords_xy corrompu pour « {name} » (longueurs différentes)",
        "de": "Beschädigte coords_xy für „{name}“ (unterschiedliche Längen)"
    },
    "CSV de coordenadas no válido para «{name}»: {path}": {
        "en": "Invalid coordinates CSV for “{name}”: {path}",
        "fr": "CSV de coordonnées non valide pour « {name} » : {path}",
        "de": "Ungültige Koordinaten-CSV für „{name}“: {path}"
    },
    "CSV de coordenadas corrupto para «{name}»: {path}": {
        "en": "Corrupt coordinates CSV for “{name}”: {path}",
        "fr": "CSV de coordonnées corrompu pour « {name} » : {path}",
        "de": "Beschädigte Koordinaten-CSV für „{name}“: {path}"
    },
    "No se pudieron resolver las coordenadas del layout: faltan los CSV por modelo y no existe una carpeta base válida para buscar turbines.csv.": {
        "de": "Die Koordinaten des Layouts konnten nicht ermittelt werden: Die CSV-Dateien je Modell fehlen, und es gibt keinen gültigen Basisordner, um turbines.csv zu suchen."
    },
    "No se encuentra '{path}'. Selecciona los CSV de coordenadas por modelo en el diálogo o crea un turbines.csv con columnas x,y[,model_id].": {
        "en": "'{path}' was not found. Select the per-model coordinate CSVs in the dialog or create a turbines.csv with x,y[,model_id] columns.",
        "fr": "'{path}' est introuvable. Sélectionnez les CSV de coordonnées par modèle dans la boîte de dialogue ou créez un turbines.csv avec les colonnes x,y[,model_id].",
        "de": "'{path}' wurde nicht gefunden. Wählen Sie im Dialog die Koordinaten-CSV-Dateien je Modell aus oder erstellen Sie eine turbines.csv mit den Spalten x,y[,model_id]."
    },
    "Todas las turbinas del CSV están fuera del área del grid WAsP. Revisa unidades (m vs km) y reproyección.": {
        "fr": "Toutes les éoliennes du CSV sont hors de la zone de la grille WAsP. Vérifiez les unités (m ou km) et la reprojection.",
        "de": "Alle Windturbinen der CSV-Datei liegen außerhalb des WAsP-Gitters. Prüfen Sie die Einheiten (m oder km) und die Reprojektion."
    },
    "Speedup no válido: {method}. Con un WRG solo se admite none: se conservan en cada punto las Weibull y frecuencias locales del WRG.": {
        "en": "Invalid Speedup: {method}. With a WRG only none is accepted: the local Weibull distributions and frequencies of the WRG are kept at each point.",
        "fr": "Speedup non valide : {method}. Avec un WRG, seul none est admis : les Weibull et les fréquences locales du WRG sont conservées en chaque point.",
        "de": "Ungültiger Speedup: {method}. Bei einem WRG ist nur none zulässig: An jedem Punkt bleiben die lokalen Weibull-Verteilungen und Häufigkeiten des WRG erhalten."
    },
    "El WRG «{source}» necesita la turbina de cada modelo para sus velocidades de cálculo: define los modelos.": {
        "en": "The WRG “{source}” needs the turbine of each model for its calculation wind speeds: define the models.",
        "fr": "Le WRG « {source} » a besoin de l’éolienne de chaque modèle pour ses vitesses de calcul : définissez les modèles.",
        "de": "Das WRG „{source}“ benötigt die Windturbine jedes Modells für seine Berechnungsgeschwindigkeiten: Definieren Sie die Modelle."
    },
    "La curva de la turbina no da su banda de velocidades de cálculo: {kind}.": {
        "en": "The turbine curve does not give its band of calculation wind speeds: {kind}.",
        "fr": "La courbe de l’éolienne ne donne pas sa bande de vitesses de calcul : {kind}.",
        "de": "Die Kurve der Windturbine liefert kein Band der Berechnungsgeschwindigkeiten: {kind}."
    },
    "La curva de la turbina no sirve para las velocidades de cálculo: {error}": {
        "en": "The turbine curve cannot be used for the calculation wind speeds: {error}",
        "fr": "La courbe de l’éolienne ne convient pas aux vitesses de calcul : {error}",
        "de": "Die Kurve der Windturbine eignet sich nicht für die Berechnungsgeschwindigkeiten: {error}"
    },
    "Número de sectores no válido: {n_sectors} en el WRG «{source}» (direcciones pedidas: {count}). Debe ser un entero positivo.": {
        "en": "Invalid number of sectors: {n_sectors} in the WRG “{source}” (requested directions: {count}). It must be a positive integer.",
        "fr": "Nombre de secteurs non valide : {n_sectors} dans le WRG « {source} » (directions demandées : {count}). Il doit être un entier positif.",
        "de": "Ungültige Sektoranzahl: {n_sectors} im WRG „{source}“ (angeforderte Richtungen: {count}). Sie muss eine positive ganze Zahl sein."
    },
    "Número de direcciones no válido: {count}. El WRG «{source}» contiene {n} sectores; al superar el límite de {max}, la única opción admitida es conservar sus {n} direcciones.": {
        "en": "Invalid number of directions: {count}. The WRG “{source}” contains {n} sectors; as it exceeds the limit of {max}, the only accepted option is to keep its {n} directions.",
        "fr": "Nombre de directions non valide : {count}. Le WRG « {source} » contient {n} secteurs ; comme il dépasse la limite de {max}, la seule option admise est de conserver ses {n} directions.",
        "de": "Ungültige Richtungsanzahl: {count}. Das WRG „{source}“ enthält {n} Sektoren; da es die Grenze von {max} überschreitet, ist die einzige zulässige Option, seine {n} Richtungen beizubehalten."
    },
    "Número de direcciones no válido: {count}. Debe ser un múltiplo entero positivo de {n}, el número de sectores del WRG «{source}», sin superar {max}.": {
        "en": "Invalid number of directions: {count}. It must be a positive integer multiple of {n}, the number of sectors of the WRG “{source}”, not exceeding {max}.",
        "fr": "Nombre de directions non valide : {count}. Il doit être un multiple entier positif de {n}, le nombre de secteurs du WRG « {source} », sans dépasser {max}.",
        "de": "Ungültige Richtungsanzahl: {count}. Sie muss ein positives ganzzahliges Vielfaches von {n} sein, der Sektoranzahl des WRG „{source}“, und darf {max} nicht überschreiten."
    },
    "Interpolación direccional no válida: {method} para el WRG «{source}» ({n} sectores, {count} direcciones). Se admiten {first} y {second}.": {
        "en": "Invalid directional interpolation: {method} for the WRG “{source}” ({n} sectors, {count} directions). {first} and {second} are accepted.",
        "fr": "Interpolation directionnelle non valide : {method} pour le WRG « {source} » ({n} secteurs, {count} directions). {first} et {second} sont admises.",
        "de": "Ungültige Richtungsinterpolation: {method} für das WRG „{source}“ ({n} Sektoren, {count} Richtungen). Zulässig sind {first} und {second}."
    },
    "Malla de direcciones imposible: {count} direcciones con {n} sectores.": {
        "en": "Impossible direction grid: {count} directions with {n} sectors.",
        "fr": "Grille de directions impossible : {count} directions avec {n} secteurs.",
        "de": "Unmögliches Richtungsgitter: {count} Richtungen mit {n} Sektoren."
    },
    "Paso de velocidad no válido: {step} para «{source}». Se admiten {steps} m/s.": {
        "en": "Invalid wind-speed step: {step} for “{source}”. {steps} m/s are accepted.",
        "fr": "Pas de vitesse non valide : {step} pour « {source} ». Les pas admis sont {steps} m/s.",
        "de": "Ungültige Geschwindigkeitsschrittweite: {step} für „{source}“. Zulässig sind {steps} m/s."
    },
    "La curva de la turbina no tiene velocidades tabuladas válidas.": {
        "en": "The turbine curve has no valid tabulated wind speeds.",
        "fr": "La courbe de l’éolienne n’a pas de vitesses tabulées valides.",
        "de": "Die Kurve der Windturbine hat keine gültigen tabellierten Geschwindigkeiten."
    },
    "La curva de la turbina tiene potencia cero en todos sus nodos: no hay banda que cubrir.": {
        "en": "The turbine curve has zero power at all its nodes: there is no band to cover.",
        "fr": "La courbe de l’éolienne a une puissance nulle à tous ses nœuds : il n’y a pas de bande à couvrir.",
        "de": "Die Kurve der Windturbine hat an allen Stützstellen die Leistung null: Es gibt kein Band abzudecken."
    },
    "Banda de operación no válida: {low}–{high} m/s.": {
        "en": "Invalid operating band: {low}–{high} m/s.",
        "fr": "Bande de fonctionnement non valide : {low}–{high} m/s.",
        "de": "Ungültiges Betriebsband: {low}–{high} m/s."
    },
    "Recurso GRD, direcciones y velocidades del Site de PyWake: {count} direcciones ({wd_low}–{wd_high}°), {low}–{high} m/s, interpolación {interp}; {hours} h/año.": {
        "fr": "Ressource GRD, directions et vitesses du Site PyWake : {count} directions ({wd_low}–{wd_high}°), {low}–{high} m/s, interpolation {interp} ; {hours} h/an."
    },
    "'ti' debe ser unitario (0,10 ≡ 10%).": {
        "en": "'ti' must be a fraction (0.10 ≡ 10%).",
        "fr": "'ti' doit être une fraction (0,10 ≡ 10 %).",
        "de": "'ti' muss ein Anteil sein (0,10 ≡ 10 %)."
    },
    "El 'site' no expone 'ds'/'dataset'.": {
        "en": "The 'site' does not expose 'ds'/'dataset'.",
        "fr": "Le 'site' n’expose pas 'ds'/'dataset'.",
        "de": "Der 'site' stellt 'ds'/'dataset' nicht bereit."
    },
    "GDAL/OSR no disponible para leer el ráster de turbulencia": {
        "en": "GDAL/OSR not available to read the turbulence raster",
        "fr": "GDAL/OSR non disponible pour lire le raster de turbulence",
        "de": "GDAL/OSR ist zum Lesen des Turbulenz-Rasters nicht verfügbar"
    },
    "Dataset WRG no disponible para inyectar TI": {
        "en": "WRG dataset not available to inject the TI",
        "fr": "Jeu de données WRG non disponible pour injecter la TI",
        "de": "WRG-Datensatz zum Einsetzen der TI nicht verfügbar"
    },
    "Ráster TI no válido: {path}": {
        "en": "Invalid TI raster: {path}",
        "fr": "Raster TI non valide : {path}",
        "de": "Ungültiges TI-Raster: {path}"
    },
    "El dataset WRG no contiene coordenadas x/y válidas": {
        "fr": "Le jeu de données WRG ne contient pas de coordonnées x/y valides",
        "de": "Der WRG-Datensatz enthält keine gültigen x/y-Koordinaten"
    },
    "No se pudo abrir el ráster TI: {path}": {
        "en": "Could not open the TI raster: {path}",
        "fr": "Impossible d’ouvrir le raster TI : {path}",
        "de": "Das TI-Raster konnte nicht geöffnet werden: {path}"
    },
    "GDAL.Warp devolvió None al alinear el ráster TI al grid WRG": {
        "en": "GDAL.Warp returned None while aligning the TI raster to the WRG grid",
        "fr": "GDAL.Warp a renvoyé None lors de l’alignement du raster TI sur la grille WRG",
        "de": "GDAL.Warp hat beim Ausrichten des TI-Rasters am WRG-Gitter None zurückgegeben"
    },
    "xarray no disponible para construir TI por altura: {error}": {
        "en": "xarray not available to build the TI by height: {error}",
        "fr": "xarray non disponible pour construire la TI par hauteur : {error}",
        "de": "xarray ist zum Aufbau der TI nach Höhe nicht verfügbar: {error}"
    },
    "No se han podido leer ráster(es) TI": {
        "en": "No TI raster could be read",
        "fr": "Aucun raster TI n’a pu être lu",
        "de": "Es konnte kein TI-Raster gelesen werden"
    },
    "No se han indicado ráster(es) TI válidos": {
        "en": "No valid TI raster(s) were provided",
        "fr": "Aucun raster TI valide n’a été indiqué",
        "de": "Es wurden keine gültigen TI-Raster angegeben"
    },
    "No se pudo resolver el CRS destino del WRG/proyecto para el ráster TI": {
        "en": "Could not resolve the target WRG/project CRS for the TI raster",
        "fr": "Impossible de déterminer le SCR de destination du WRG/projet pour le raster TI",
        "de": "Das Ziel-KBS des WRG/Projekts für das TI-Raster konnte nicht ermittelt werden"
    },
    "Hay {n} nombres que no casan con py_wake en: {folder}": {
        "en": "There are {n} names that do not match py_wake in: {folder}",
        "fr": "{n} noms ne correspondent pas à py_wake dans : {folder}",
        "de": "{n} Namen entsprechen nicht dem py_wake-Muster in: {folder}"
    },
    "El ZIP no contiene ningún .wrg: {path}": {
        "en": "The ZIP does not contain any .wrg: {path}",
        "fr": "Le ZIP ne contient aucun .wrg : {path}",
        "de": "Die ZIP-Datei enthält keine .wrg-Datei: {path}"
    },
    "WRG vacío": {
        "fr": "WRG vide",
        "de": "Leeres WRG"
    },
    "Cabecera WRG inválida: {header}": {
        "en": "Invalid WRG header: {header}",
        "fr": "En-tête WRG non valide : {header}",
        "de": "Ungültige WRG-Kopfzeile: {header}"
    },
    "WRG sin puntos (sólo cabecera)": {
        "fr": "WRG sans points (en-tête uniquement)"
    },
    "No se pudo leer ningún WRG desde: {path}": {
        "en": "No WRG could be read from: {path}",
        "fr": "Aucun WRG n’a pu être lu depuis : {path}",
        "de": "Aus folgender Quelle konnte kein WRG gelesen werden: {path}"
    },
    "No se encontró ningún WRG legible en: {path}": {
        "en": "No readable WRG was found in: {path}",
        "fr": "Aucun WRG lisible n’a été trouvé dans : {path}",
        "de": "Keine lesbare WRG-Datei gefunden in: {path}"
    },
    "ZIP no contiene .wrg: {path}": {
        "en": "The ZIP does not contain a .wrg: {path}",
        "fr": "Le ZIP ne contient pas de .wrg : {path}",
        "de": "Die ZIP-Datei enthält keine .wrg-Datei: {path}"
    },
    "Extensión no soportada: {path} (use .wrg o .zip)": {
        "en": "Unsupported extension: {path} (use .wrg or .zip)",
        "fr": "Extension non prise en charge : {path} (utilisez .wrg ou .zip)",
        "de": "Nicht unterstützte Dateiendung: {path} (verwenden Sie .wrg oder .zip)"
    },
    "Cabecera WRG inválida: '{line}'": {
        "en": "Invalid WRG header: '{line}'",
        "fr": "En-tête WRG non valide : '{line}'",
        "de": "Ungültige WRG-Kopfzeile: '{line}'"
    },
    "Cabecera WRG inválida (nx,ny,dx): nx={nx} ny={ny} dx={dx}": {
        "en": "Invalid WRG header (nx,ny,dx): nx={nx} ny={ny} dx={dx}",
        "fr": "En-tête WRG non valide (nx,ny,dx) : nx={nx} ny={ny} dx={dx}",
        "de": "Ungültige WRG-Kopfzeile (nx,ny,dx): nx={nx} ny={ny} dx={dx}"
    },
    "WRG incompleto: cabecera + {expected} líneas esperadas; hay {lines}": {
        "en": "Incomplete WRG: header + {expected} lines expected; there are {lines}",
        "fr": "WRG incomplet : en-tête + {expected} lignes attendues ; il y en a {lines}",
        "de": "Unvollständiges WRG: Kopfzeile + {expected} Zeilen erwartet; vorhanden sind {lines}"
    },
    "Lista WRG vacía": {
        "fr": "Liste WRG vide",
        "de": "Leere WRG-Liste"
    },
    "WRG con distinta resolución/extensión: no se pueden combinar por altura": {
        "en": "WRG files with different resolution/extent: they cannot be combined by height",
        "fr": "WRG avec des résolutions/emprises différentes : combinaison par hauteur impossible",
        "de": "WRG-Dateien mit unterschiedlicher Auflösung/Ausdehnung: Sie können nicht nach Höhe kombiniert werden"
    },
    "WRG con distinto origen x0/y0: no se pueden combinar por altura": {
        "fr": "WRG avec des origines x0/y0 différentes : combinaison par hauteur impossible",
        "de": "WRG-Dateien mit unterschiedlichem Ursprung x0/y0: Sie können nicht nach Höhe kombiniert werden"
    },
    "WRG con distinto dx: no se pueden combinar por altura": {
        "fr": "WRG avec des dx différents : combinaison par hauteur impossible",
        "de": "WRG-Dateien mit unterschiedlichem dx: Sie können nicht nach Höhe kombiniert werden"
    },
    "Los WRG no tienen los mismos sectores: {n_first} en «{first}» y {n} en «{source}». No se pueden combinar por altura.": {
        "en": "The WRG files do not have the same sectors: {n_first} in “{first}” and {n} in “{source}”. They cannot be combined by height.",
        "fr": "Les WRG n’ont pas les mêmes secteurs : {n_first} dans « {first} » et {n} dans « {source} ». Combinaison par hauteur impossible.",
        "de": "Die WRG-Dateien haben nicht dieselben Sektoren: {n_first} in „{first}“ und {n} in „{source}“. Sie können nicht nach Höhe kombiniert werden."
    },
    "No se pudo leer ningún WRG válido": {
        "de": "Es konnte kein gültiges WRG gelesen werden"
    },
    "Hay WRG duplicados para la altura {height} m con contenido distinto: '{first}' y '{second}'": {
        "en": "There are duplicate WRG files for the height {height} m with different content: '{first}' and '{second}'",
        "fr": "Il y a des WRG en double pour la hauteur {height} m avec un contenu différent : '{first}' et '{second}'",
        "de": "Es gibt doppelte WRG-Dateien für die Höhe {height} m mit unterschiedlichem Inhalt: '{first}' und '{second}'"
    },
    "Los WRG contienen superficies de elevación distintas entre alturas; no se puede construir un terreno único y coherente.": {
        "en": "The WRG files contain different elevation surfaces between heights; a single, consistent terrain cannot be built.",
        "fr": "Les WRG contiennent des surfaces d’élévation différentes selon les hauteurs ; impossible de construire un terrain unique et cohérent.",
        "de": "Die WRG-Dateien enthalten zwischen den Höhen unterschiedliche Geländeoberflächen; es kann kein einheitliches, konsistentes Gelände aufgebaut werden."
    },
    "Dimensiones de Elevation no compatibles: {dims}; se esperaba (x, y).": {
        "en": "Incompatible Elevation dimensions: {dims}; (x, y) was expected.",
        "fr": "Dimensions de Elevation incompatibles : {dims} ; (x, y) était attendu.",
        "de": "Inkompatible Dimensionen von Elevation: {dims}; erwartet wurde (x, y)."
    },
    "El mapa de flujo no contiene la coordenada '{name}'.": {
        "en": "The flow map does not contain the coordinate '{name}'.",
        "fr": "La carte d’écoulement ne contient pas la coordonnée '{name}'.",
        "de": "Die Strömungskarte enthält die Koordinate '{name}' nicht."
    },
    "No se pudo leer la coordenada '{name}': {error}": {
        "en": "The coordinate '{name}' could not be read: {error}",
        "fr": "Impossible de lire la coordonnée '{name}' : {error}",
        "de": "Die Koordinate '{name}' konnte nicht gelesen werden: {error}"
    },
    "La coordenada '{name}' no contiene una malla ráster válida.": {
        "en": "The coordinate '{name}' does not contain a valid raster grid.",
        "fr": "La coordonnée '{name}' ne contient pas de grille raster valide.",
        "de": "Die Koordinate '{name}' enthält kein gültiges Rastergitter."
    },
    "PyWake no devolvió el campo {field}. Variables disponibles: {names}.": {
        "en": "PyWake did not return the field {field}. Available variables: {names}.",
        "fr": "PyWake n’a pas renvoyé le champ {field}. Variables disponibles : {names}.",
        "de": "PyWake hat das Feld {field} nicht zurückgegeben. Verfügbare Variablen: {names}."
    },
    "desconocidas": {
        "en": "unknown",
        "fr": "inconnues",
        "de": "unbekannt"
    },
    "No se pudo convertir {field} a una matriz 2-D: {error}": {
        "en": "{field} could not be converted to a 2-D array: {error}",
        "fr": "Impossible de convertir {field} en matrice 2D : {error}",
        "de": "{field} konnte nicht in eine 2D-Matrix umgewandelt werden: {error}"
    },
    "{field} tiene una forma no compatible con ráster: {shape}.": {
        "en": "{field} has a shape that is not compatible with a raster: {shape}.",
        "fr": "{field} a une forme incompatible avec un raster : {shape}.",
        "de": "{field} hat eine mit einem Raster nicht kompatible Form: {shape}."
    },
    "La forma de {field} no coincide con las coordenadas del grid: array={shape}, y={ny}, x={nx}.": {
        "en": "The shape of {field} does not match the grid coordinates: array={shape}, y={ny}, x={nx}.",
        "fr": "La forme de {field} ne correspond pas aux coordonnées de la grille : array={shape}, y={ny}, x={nx}.",
        "de": "Die Form von {field} stimmt nicht mit den Gitterkoordinaten überein: array={shape}, y={ny}, x={nx}."
    },
    "No se pudo determinar la resolución del eje {axis}.": {
        "en": "The resolution of the {axis} axis could not be determined.",
        "fr": "Impossible de déterminer la résolution de l’axe {axis}.",
        "de": "Die Auflösung der {axis}-Achse konnte nicht bestimmt werden."
    },
    "El eje {axis} del mapa de flujo no es regular.": {
        "en": "The {axis} axis of the flow map is not regular.",
        "fr": "L’axe {axis} de la carte d’écoulement n’est pas régulier.",
        "de": "Die {axis}-Achse der Strömungskarte ist nicht regelmäßig."
    },
    "GDAL no está disponible en el Python de QGIS: {error}": {
        "en": "GDAL is not available in the QGIS Python: {error}",
        "fr": "GDAL n’est pas disponible dans le Python de QGIS : {error}",
        "de": "GDAL ist im Python von QGIS nicht verfügbar: {error}"
    },
    "No se pudo importar el escritor ráster seguro: {error}": {
        "en": "The safe raster writer could not be imported: {error}",
        "fr": "Impossible d’importer le module d’écriture raster sécurisé : {error}",
        "de": "Der sichere Raster-Writer konnte nicht importiert werden: {error}"
    },
    "GDAL no dispone del driver GTiff.": {
        "en": "GDAL does not have the GTiff driver.",
        "fr": "GDAL ne dispose pas du pilote GTiff.",
        "de": "GDAL verfügt nicht über den GTiff-Treiber."
    },
    "GDAL no pudo crear el GeoTIFF: {path}": {
        "en": "GDAL could not create the GeoTIFF: {path}",
        "fr": "GDAL n’a pas pu créer le GeoTIFF : {path}",
        "de": "GDAL konnte das GeoTIFF nicht erstellen: {path}"
    },
    "No se pudo importar la API ráster de QGIS: {error}": {
        "en": "The QGIS raster API could not be imported: {error}",
        "fr": "Impossible d’importer l’API raster de QGIS : {error}",
        "de": "Die Raster-API von QGIS konnte nicht importiert werden: {error}"
    },
    "QGIS no pudo abrir el GeoTIFF generado: {path}": {
        "en": "QGIS could not open the generated GeoTIFF: {path}",
        "fr": "QGIS n’a pas pu ouvrir le GeoTIFF généré : {path}",
        "de": "QGIS konnte das erzeugte GeoTIFF nicht öffnen: {path}"
    },
    "Las coordenadas de WS y WS_eff no coinciden.": {
        "en": "The coordinates of WS and WS_eff do not match.",
        "fr": "Les coordonnées de WS et WS_eff ne correspondent pas.",
        "de": "Die Koordinaten von WS und WS_eff stimmen nicht überein."
    },
    "La elevación interpolada no coincide con el grid y no se exportó: {terrain} != {field}.": {
        "en": "The interpolated elevation does not match the grid and was not exported: {terrain} != {field}.",
        "fr": "L’élévation interpolée ne correspond pas à la grille et n’a pas été exportée : {terrain} != {field}.",
        "de": "Die interpolierte Geländehöhe stimmt nicht mit dem Gitter überein und wurde nicht exportiert: {terrain} != {field}."
    },
    "No se pudo importar la API de QGIS: {error}": {
        "en": "The QGIS API could not be imported: {error}",
        "fr": "Impossible d’importer l’API de QGIS : {error}",
        "de": "Die QGIS-API konnte nicht importiert werden: {error}"
    },
    "GDAL no devolvió datos al leer una celda del ráster.": {
        "en": "GDAL returned no data while reading a raster cell.",
        "fr": "GDAL n’a renvoyé aucune donnée lors de la lecture d’une cellule du raster.",
        "de": "GDAL hat beim Lesen einer Rasterzelle keine Daten zurückgegeben."
    },
    "GDAL devolvió un búfer incompleto al leer una celda del ráster.": {
        "en": "GDAL returned an incomplete raster-cell buffer.",
        "fr": "GDAL a renvoyé un tampon incomplet lors de la lecture d’une cellule du raster.",
        "de": "GDAL hat beim Lesen einer Rasterzelle einen unvollständigen Puffer zurückgegeben."
    },
    "La banda del ráster debe tener al menos una celda.": {
        "en": "The raster band must contain at least one cell.",
        "fr": "La bande du raster doit contenir au moins une cellule.",
        "de": "Das Rasterband muss mindestens eine Zelle enthalten."
    },
    "GDAL no devolvió datos al leer la banda del ráster.": {
        "en": "GDAL returned no data while reading the raster band.",
        "fr": "GDAL n’a renvoyé aucune donnée lors de la lecture de la bande du raster.",
        "de": "GDAL hat beim Lesen des Rasterbands keine Daten zurückgegeben."
    },
    "GDAL devolvió un búfer incompleto al leer la banda del ráster.": {
        "en": "GDAL returned an incomplete raster-band buffer.",
        "fr": "GDAL a renvoyé un tampon incomplet lors de la lecture de la bande du raster.",
        "de": "GDAL hat beim Lesen des Rasterbands einen unvollständigen Puffer zurückgegeben."
    },
    "Se necesita una matriz ráster 2-D; se ha recibido la forma {shape}.": {
        "en": "A 2-D raster array is required; received shape {shape}.",
        "fr": "Une matrice raster 2D est nécessaire ; forme reçue : {shape}.",
        "de": "Eine 2D-Rastermatrix ist erforderlich; erhalten wurde die Form {shape}."
    },
    "La matriz ráster debe tener al menos una celda.": {
        "en": "The raster array must contain at least one cell.",
        "fr": "La matrice raster doit contenir au moins une cellule.",
        "de": "Die Rastermatrix muss mindestens eine Zelle enthalten."
    },
    "GDAL WriteRaster falló con el código de error {code}.": {
        "en": "GDAL WriteRaster failed with error code {code}.",
        "fr": "GDAL WriteRaster a échoué avec le code d’erreur {code}.",
        "de": "GDAL WriteRaster ist mit dem Fehlercode {code} fehlgeschlagen."
    },
    "Extensión no válida: {extent}": {
        "en": "Invalid extent: {extent}",
        "fr": "Emprise non valide : {extent}",
        "de": "Ungültige Ausdehnung: {extent}"
    },
    "CRS del recurso/proyecto no válido; no se dibuja un perímetro con CRS supuesto.": {
        "de": "Das KBS der Ressource oder des Projekts ist ungültig; es wird keine Ressourcengrenze mit einem angenommenen KBS gezeichnet."
    },
    "Perímetro WAsP/Surfer dibujado: dominio común de {n} grid(s).": {
        "de": "Ressourcengrenze WAsP/Surfer gezeichnet: gemeinsamer Bereich von {n} Gitter(n)."
    },
    "Perímetro WAsP/Surfer dibujado: envolvente de {n} grid(s) sin intersección común.": {
        "de": "Ressourcengrenze WAsP/Surfer gezeichnet: Hülle von {n} Gitter(n) ohne gemeinsame Schnittfläche."
    },
    "Perímetro WRG dibujado: {n} archivo(s).": {
        "de": "Ressourcengrenze WRG gezeichnet: {n} Datei(en)."
    },
    "No se han encontrado grids .grd/.asc/.tif en la carpeta seleccionada.": {
        "de": "Im ausgewählten Ordner wurden keine .grd/.asc/.tif-Gitter gefunden."
    },
    "No se pudo leer la extensión espacial de los grids seleccionados.": {
        "de": "Die räumliche Ausdehnung der ausgewählten Gitter konnte nicht gelesen werden."
    },
    "Las extensiones de los grids no tienen intersección válida.": {
        "de": "Die Ausdehnungen der Gitter haben keine gültige Schnittfläche."
    },
    "Proporciona una capa de puntos válida.": {
        "fr": "Indiquez une couche de points valide."
    },
    "[Layer] La capa '{layer}' conserva campos de resultados del esquema anterior ({fields}), que ya no se actualizan: los resultados nuevos están en sus propios campos.": {
        "de": "[Layer] Der Layer '{layer}' behält Ergebnisfelder des früheren Schemas ({fields}), die nicht mehr aktualisiert werden: Die neuen Ergebnisse stehen in eigenen Feldern."
    },
    "Ráster: la capa {layer} no tiene celdas finitas: se escribe entera como NoData y sin estilo.": {
        "de": "Raster: Der Layer {layer} hat keine endlichen Zellen: Er wird vollständig als NoData und ohne Stil geschrieben."
    },
    "Ráster: la capa {layer} tiene {count} celdas no finitas por desbordamiento al escribirla en float32: son NoData.": {
        "de": "Raster: Der Layer {layer} hat {count} nicht endliche Zellen durch Überlauf beim Schreiben in float32: Sie sind NoData."
    },
    "{label}: {count} casos sin energía (P = 0, o P no finita en un sector de frecuencia nula) con AEP no finito: no aportan energía y las sumas los omiten.": {
        "de": "{label}: {count} Fälle ohne Energie (P = 0 oder nicht endliches P in einem Sektor mit Häufigkeit null) mit nicht endlicher AEP: Sie tragen keine Energie bei, und die Summen lassen sie aus."
    },
    "{label}: AEP no finito en {count} casos que pueden tener energía (NaN {nan}, +inf {pinf}, −inf {ninf}).": {
        "de": "{label}: nicht endliche AEP in {count} Fällen, die Energie haben können (NaN {nan}, +inf {pinf}, −inf {ninf})."
    },
    "{label}: AEP parcial (omite casos no finitos con energía) en las turbinas {turbines}, y en el total del parque.": {
        "de": "{label}: unvollständige AEP (sie lässt nicht endliche Fälle mit Energie aus) bei den Windturbinen {turbines} und in der Summe des Parks."
    },
    "{label}: AEP no finito en las turbinas {turbines}, y en el total del parque.": {
        "de": "{label}: nicht endliche AEP bei den Windturbinen {turbines} und in der Summe des Parks."
    },
    "{label}: AEP total del parque no finito.": {
        "de": "{label}: nicht endliche AEP in der Summe des Parks."
    },
    "{label}: una suma del AEP desborda: da un infinito sin ningún caso infinito.": {
        "de": "{label}: Eine Summe der AEP läuft über: Sie ergibt einen unendlichen Wert ohne einen unendlichen Fall."
    },
    "{label}: AEP por sector no finito en los sectores {sectors}° (su suma desborda).": {
        "de": "{label}: nicht endliche AEP je Sektor in den Sektoren {sectors}° (ihre Summe läuft über)."
    },
    "{label}: AEP por sector parcial en los sectores {sectors}°: omite los casos no finitos con energía y toda la energía de las direcciones cuya suma no es finita ({directions}°).": {
        "de": "{label}: unvollständige AEP je Sektor in den Sektoren {sectors}°: Sie lässt die nicht endlichen Fälle mit Energie und die gesamte Energie der Richtungen aus, deren Summe nicht endlich ist ({directions}°)."
    },
    "{label}: AEP por sector parcial (omite casos no finitos con energía) en los sectores {sectors}°.": {
        "de": "{label}: unvollständige AEP je Sektor (sie lässt nicht endliche Fälle mit Energie aus) in den Sektoren {sectors}°."
    },
    "TI efectiva {reason} en las turbinas {turbines}: no se guarda ningún valor.": {
        "fr": "TI effective {reason} aux éoliennes {turbines} : aucune valeur n’est conservée."
    },
    "El ráster se ha calculado con las entradas actuales del diálogo, que difieren del último AEP en: {categories}. Vuelve a calcular el AEP para que el informe corresponda al mapa.": {
        "fr": "Le raster a été calculé avec les entrées actuelles de la boîte de dialogue, qui diffèrent du dernier AEP sur : {categories}. Recalculez l’AEP pour que le rapport corresponde à la carte.",
        "de": "Das Raster wurde mit den aktuellen Eingaben des Dialogs berechnet, die sich von der letzten AEP unterscheiden in: {categories}. Berechnen Sie die AEP erneut, damit der Bericht der Karte entspricht."
    },
    "No se pudo identificar el sector dominante del recurso: indica una dirección.": {
        "fr": "Le secteur dominant de la ressource n’a pas pu être identifié : indiquez une direction.",
        "de": "Der dominante Sektor der Ressource konnte nicht bestimmt werden: Geben Sie eine Richtung an."
    },
    "[REPORT] Modelo predefinido {preset}, revisión {revision}: {reference} de PyWake {reference_version}, calculado con PyWake {executed_version}.": {
        "en": "[REPORT] Predefined model {preset}, revision {revision}: {reference} of PyWake {reference_version}, calculated with PyWake {executed_version}.",
        "fr": "[REPORT] Modèle prédéfini {preset}, révision {revision} : {reference} de PyWake {reference_version}, calculé avec PyWake {executed_version}.",
        "de": "[REPORT] Vordefiniertes Modell {preset}, Revision {revision}: {reference} von PyWake {reference_version}, berechnet mit PyWake {executed_version}."
    },
    "[WRG][TI] No se ha seleccionado ráster de turbulencia. Se usará TI fija={ti}.": {
        "en": "[WRG][TI] No turbulence raster has been selected. A fixed TI={ti} will be used.",
        "fr": "[WRG][TI] Aucun raster de turbulence n’a été sélectionné. Une TI fixe={ti} sera utilisée.",
        "de": "[WRG][TI] Es wurde kein Turbulenz-Raster ausgewählt. Es wird eine feste TI={ti} verwendet."
    },
    "[WRG][TI] No se pudieron aplicar los ráster(es) TI '{paths}': {error}. Se usará fallback fijo.": {
        "en": "[WRG][TI] The TI raster(s) '{paths}' could not be applied: {error}. A fixed fallback will be used.",
        "fr": "[WRG][TI] Impossible d’appliquer le(s) raster(s) TI '{paths}' : {error}. Un repli fixe sera utilisé.",
        "de": "[WRG][TI] Die TI-Raster '{paths}' konnten nicht angewendet werden: {error}. Es wird ein fester Rückfallwert verwendet."
    },
    "[WRG][TI] No se han identificado al menos dos alturas TI distintas; se usará el primer ráster para todas las alturas.": {
        "en": "[WRG][TI] At least two different TI heights could not be identified; the first raster will be used for all heights.",
        "fr": "[WRG][TI] Au moins deux hauteurs TI différentes n’ont pas pu être identifiées ; le premier raster sera utilisé pour toutes les hauteurs.",
        "de": "[WRG][TI] Es konnten nicht mindestens zwei verschiedene TI-Höhen erkannt werden; das erste Raster wird für alle Höhen verwendet."
    },
    "[WRG][TI] Ráster sin CRS explícito; por su cabecera parece lon/lat y se asume EPSG:4326.": {
        "en": "[WRG][TI] Raster without an explicit CRS; its header looks like lon/lat, so EPSG:4326 is assumed.",
        "fr": "[WRG][TI] Raster sans SCR explicite ; son en-tête semble en lon/lat, EPSG:4326 est supposé.",
        "de": "[WRG][TI] Raster ohne explizites KBS; der Header sieht nach Lon/Lat aus, daher wird EPSG:4326 angenommen."
    },
    "[WRG][TI] Ráster sin CRS explícito; se asume el CRS del WRG/proyecto.": {
        "en": "[WRG][TI] Raster without an explicit CRS; the WRG/project CRS is assumed.",
        "fr": "[WRG][TI] Raster sans SCR explicite ; le SCR du WRG/projet est supposé.",
        "de": "[WRG][TI] Raster ohne explizites KBS; das KBS des WRG/Projekts wird angenommen."
    },
    "[WRG][TI] El ráster TI ha quedado completamente fuera de cobertura tras reproyección/alineado; se usará TI uniforme={ti} en toda la malla.": {
        "en": "[WRG][TI] The TI raster is completely out of coverage after reprojection/alignment; a uniform TI={ti} will be used over the whole grid.",
        "fr": "[WRG][TI] Le raster TI est entièrement hors couverture après reprojection/alignement ; une TI uniforme={ti} sera utilisée sur toute la grille.",
        "de": "[WRG][TI] Das TI-Raster liegt nach Reprojektion/Ausrichtung vollständig außerhalb der Abdeckung; im gesamten Gitter wird eine einheitliche TI={ti} verwendet."
    },
    "[WRG][TI] Ráster TI con {n} celdas fuera de cobertura tras reproyección/alineado; se rellenan con {ti}.": {
        "en": "[WRG][TI] TI raster with {n} cells out of coverage after reprojection/alignment; they are filled with {ti}.",
        "fr": "[WRG][TI] Raster TI avec {n} cellules hors couverture après reprojection/alignement ; elles sont remplies avec {ti}.",
        "de": "[WRG][TI] TI-Raster mit {n} Zellen außerhalb der Abdeckung nach Reprojektion/Ausrichtung; sie werden mit {ti} gefüllt."
    },
    "[WRG][TI] Altura TI duplicada {height} m en '{file}'; se conserva el primer ráster para esa altura.": {
        "en": "[WRG][TI] Duplicate TI height {height} m in '{file}'; the first raster for that height is kept.",
        "fr": "[WRG][TI] Hauteur TI en double {height} m dans '{file}' ; le premier raster pour cette hauteur est conservé.",
        "de": "[WRG][TI] Doppelte TI-Höhe {height} m in '{file}'; das erste Raster für diese Höhe wird beibehalten."
    },
    "[WRG][TI] Solo hay un ráster TI ({file}) a {height} m; se aplicará a todas las alturas del WRG como aproximación.": {
        "en": "[WRG][TI] There is only one TI raster ({file}) at {height} m; it will be applied to all WRG heights as an approximation.",
        "fr": "[WRG][TI] Il n’y a qu’un seul raster TI ({file}) à {height} m ; il sera appliqué à toutes les hauteurs du WRG à titre d’approximation.",
        "de": "[WRG][TI] Es gibt nur ein TI-Raster ({file}) auf {height} m; es wird näherungsweise auf alle WRG-Höhen angewendet."
    },
    "[WRG][TI] Solo hay un ráster TI ({file}) sin altura identificable; se aplicará a todas las alturas del WRG como aproximación.": {
        "en": "[WRG][TI] There is only one TI raster ({file}) with no identifiable height; it will be applied to all WRG heights as an approximation.",
        "fr": "[WRG][TI] Il n’y a qu’un seul raster TI ({file}) sans hauteur identifiable ; il sera appliqué à toutes les hauteurs du WRG à titre d’approximation.",
        "de": "[WRG][TI] Es gibt nur ein TI-Raster ({file}) ohne erkennbare Höhe; es wird näherungsweise auf alle WRG-Höhen angewendet."
    },
    "Las capas de flujo libre, velocidad efectiva y déficit, junto con el terreno cuando está disponible, se han añadido al grupo ‘{group}’.": {
        "en": "The free-stream, effective wind speed and deficit layers, together with the terrain when available, have been added to the group ‘{group}’.",
        "fr": "Les couches d’écoulement libre, de vitesse effective et de déficit, ainsi que le terrain lorsqu’il est disponible, ont été ajoutées au groupe ‘{group}’.",
        "de": "Die Layer für freie Anströmung, effektive Windgeschwindigkeit und Defizit sowie das Gelände, sofern verfügbar, wurden der Gruppe ‘{group}’ hinzugefügt."
    }
}


def setUpModule():
    # Without an initialised QGIS profile, QGIS writes its style database (symbology-style.db) in the working folder.
    os.chdir(_SETTINGS.name)


def tearDownModule():
    os.chdir(_CWD)


def _error_templates():
    """The templates of the errors raised with ``log_error`` in these files."""
    found = set()
    for name in _FILES:
        for node in ast.walk(ast.parse((_PLUGIN / name).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "log_error" and len(node.args) > 1:
                if isinstance(node.args[1], ast.Constant):
                    found.add(node.args[1].value)
    return sorted(found)


def _raised(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # the error under test
        return exc
    raise AssertionError("no error")


class Z6MessagesTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("es")

    def tearDown(self):
        i18n.set_language("es")

    def test_every_error_template_has_an_exact_translation(self):
        templates = _error_templates()
        self.assertGreater(len(templates), 60)
        i18n._ensure()
        for text in templates:
            with self.subTest(lang="es", text=text[:60]):
                self.assertEqual(i18n.tr_text(text), text)
        for lang in _LANGS:
            i18n.set_language(lang)
            table = i18n._STATE["full"][lang]
            for text in templates:
                with self.subTest(lang=lang, text=text[:60]):
                    self.assertTrue(text in table, "sin entrada")
                    self.assertEqual(i18n.tr_text(text), table[text])

    def test_delivered_translations_match_the_reviewed_values(self):
        for lang in _LANGS:
            i18n.set_language(lang)
            for text, translations in _REVIEWED_TRANSLATIONS.items():
                if lang in translations:
                    with self.subTest(lang=lang, text=text):
                        self.assertEqual(i18n.tr_text(text), translations[lang])

    def test_nested_errors_keep_user_data_when_the_language_changes(self):
        path = "/tmp/Modelo Parque/Turbinas {name}.zip"
        inner = log_error(ValueError, "El ZIP no contiene ningún .wrg: {path}", path=path)
        outer = log_error(RuntimeError, "CSV de coordenadas no válido para «{name}»: {path}",
                          name="Plantilla: Norte", path=inner)
        expected = {
            "es": "CSV de coordenadas no válido para «Plantilla: Norte»: El ZIP no contiene ningún .wrg: " + path,
            "en": "Invalid coordinates CSV for “Plantilla: Norte”: The ZIP does not contain any .wrg: " + path,
            "fr": "CSV de coordonnées non valide pour « Plantilla: Norte » : Le ZIP ne contient aucun .wrg : " + path,
            "de": "Ungültige Koordinaten-CSV für „Plantilla: Norte“: Die ZIP-Datei enthält keine .wrg-Datei: " + path,
        }
        for lang in ("es", "fr", "de", "en", "es"):
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                self.assertEqual(shown(outer, i18n.tr_text), expected[lang])

    def test_the_qgis_log_keeps_nested_errors_in_spanish(self):
        i18n.set_language("fr")
        error = log_error(ValueError, "El ZIP no contiene ningún .wrg: {path}", path="Modelo/Turbinas.zip")
        message = log_text("CSV de coordenadas no válido para «{name}»: {path}",
                           name="Parque", path=error)
        self.assertEqual(str(message), "CSV de coordenadas no válido para «Parque»: "
                         "El ZIP no contiene ningún .wrg: Modelo/Turbinas.zip")
        self.assertEqual(shown(message, i18n.tr_text), "CSV de coordonnées non valide pour « Parque » : "
                         "Le ZIP ne contient aucun .wrg : Modelo/Turbinas.zip")

    def test_wake_completion_quotes_the_actual_group_name(self):
        from qgis.core import QgsCoordinateReferenceSystem, QgsProject
        from VelantisWind.wake_core import controller

        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        self.addCleanup(project.clear)
        expected = {
            "es": "Las capas de flujo libre, velocidad efectiva y déficit, junto con el terreno cuando está disponible, "
                  "se han añadido al grupo ‘VelantisWind · Estelas’.",
            "en": "The free-stream, effective wind speed and deficit layers, together with the terrain when available, "
                  "have been added to the group ‘VelantisWind · Estelas’.",
            "fr": "Les couches d’écoulement libre, de vitesse effective et de déficit, ainsi que le terrain lorsqu’il "
                  "est disponible, ont été ajoutées au groupe ‘VelantisWind · Estelas’.",
            "de": "Die Layer für freie Anströmung, effektive Windgeschwindigkeit und Defizit sowie das Gelände, sofern "
                  "verfügbar, wurden der Gruppe ‘VelantisWind · Estelas’ hinzugefügt.",
        }
        for lang, text in expected.items():
            i18n.set_language(lang)
            with self.subTest(lang=lang), \
                    mock.patch.object(controller, "start_wake_raster_task") as start, \
                    mock.patch.object(controller, "add_wake_raster_result_to_qgis", return_value=[]), \
                    mock.patch.object(controller.QtWidgets.QMessageBox, "information") as info:
                controller.start_wake_raster_from_dialog(
                    mock.Mock(_wake_raster_task=None), models=[], wasp_dir="", resolution_m=300.0,
                    wrg_paths=[], wake_config=None, wd_target=270.0)
                start.call_args.kwargs["on_finished"](True, {"path": "/tmp/Modelo/Parque.tif"}, None)
                message = info.call_args.args[2]
                self.assertEqual(message.split("\n\n", 1)[0], text)
                self.assertIn("/tmp/Modelo/Parque.json", message)

    def test_ti_notes_of_the_wrg(self):
        """S3-5, S3-6: the notes are templates, so the report translates them whole; «interpola», in Spanish."""
        one, hubs = aep_compute._resource_ti_notes(use_wrg=True, wrg_ti_paths=["ti.tif"], unique_hubs=[100.0, 120.0])
        (none,) = aep_compute._resource_ti_notes(use_wrg=True, wrg_ti_paths=[], unique_hubs=[100.0])
        (several,) = aep_compute._resource_ti_notes(use_wrg=True, wrg_ti_paths=["a.tif", "b.tif"], unique_hubs=[100.0])
        expected = {
            "es": ("WRG: se ha usado un único ráster de TI ambiente; si mezclas varias alturas de buje, esa TI se "
                   "replica/interpola como aproximación vertical.",
                   "Hay varias alturas de buje pero solo una TI ambiente verticalmente uniforme; el cálculo sigue siendo "
                   "válido, aunque es una aproximación en altura.",
                   "WRG: no se ha proporcionado ráster TI, así que la TI ambiente se ha fijado al valor de respaldo definido "
                   "por el usuario como campo uniforme.",
                   "WRG: se han usado 2 rásteres de TI ambiente para reconstruir TI por altura cuando es posible."),
            "en": ("WRG: a single ambient TI raster was used; if you mix several hub heights, that TI is "
                   "replicated/interpolated as a vertical approximation.",
                   "There are several hub heights but only one vertically uniform ambient TI; the calculation is still "
                   "valid, although it is an approximation in height.",
                   "WRG: no TI raster was provided, so the ambient TI was set to the user-defined fallback value as a "
                   "uniform field.",
                   "WRG: 2 ambient TI rasters were used to reconstruct the TI by height where possible."),
            "fr": ("WRG : un seul raster de TI ambiante a été utilisé ; si vous mélangez plusieurs hauteurs de moyeu, "
                   "cette TI est répliquée/interpolée comme approximation verticale.",
                   "Il y a plusieurs hauteurs de moyeu mais une seule TI ambiante verticalement uniforme ; le calcul "
                   "reste valide, bien qu’il s’agisse d’une approximation en hauteur.",
                   "WRG : aucun raster TI n’a été fourni ; la TI ambiante a donc été fixée à la valeur de repli définie "
                   "par l’utilisateur, comme champ uniforme.",
                   "WRG : 2 rasters de TI ambiante ont été utilisés pour reconstruire la TI par hauteur lorsque c’est "
                   "possible."),
            "de": ("WRG: Es wurde ein einziges Raster der Umgebungs-TI verwendet; wenn Sie mehrere Nabenhöhen mischen, "
                   "wird diese TI als vertikale Näherung repliziert/interpoliert.",
                   "Es gibt mehrere Nabenhöhen, aber nur eine vertikal einheitliche Umgebungs-TI; die Berechnung bleibt "
                   "gültig, ist aber eine Näherung in der Höhe.",
                   "WRG: Es wurde kein TI-Raster angegeben, daher wurde die Umgebungs-TI auf den vom Benutzer "
                   "festgelegten Rückfallwert als einheitliches Feld gesetzt.",
                   "WRG: Es wurden 2 Raster der Umgebungs-TI verwendet, um die TI nach Höhe zu rekonstruieren, wo dies "
                   "möglich ist."),
        }
        for lang, texts in expected.items():
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                self.assertEqual(tuple(shown(n, i18n.tr_text) for n in (one, hubs, none, several)), texts)

    def test_wrg_error_is_translated_and_keeps_the_path(self):
        """S1-9: the reason of an unreadable WRG, in the language of the error and again in the one it is shown in."""
        folder = os.path.join(_SETTINGS.name, "Modelo Parque Norte")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Turbinas.zip")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("leeme.txt", "sin WRG")
        expected = {
            "es": "El ZIP no contiene ningún .wrg: {path}",
            "en": "The ZIP does not contain any .wrg: {path}",
            "fr": "Le ZIP ne contient aucun .wrg : {path}",
            "de": "Die ZIP-Datei enthält keine .wrg-Datei: {path}",
        }
        for lang, text in expected.items():
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                exc = _raised(wrg_reader.read_wrg_meta, path)
                self.assertIsInstance(exc, ValueError)
                self.assertEqual(str(exc), text.format(path=path))
        i18n.set_language("fr")
        exc = _raised(wrg_reader.read_wrg_meta, path)
        i18n.set_language("de")
        self.assertEqual(shown(exc, i18n.tr_text), expected["de"].format(path=path))

    def test_invalid_numeric_header_uses_the_wrg_template(self):
        header = "Modelo Parque Norte 0 50"
        expected = {
            "es": "Cabecera WRG inválida: ", "en": "Invalid WRG header: ",
            "fr": "En-tête WRG non valide : ", "de": "Ungültige WRG-Kopfzeile: ",
        }
        for lang, prefix in expected.items():
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                exc = _raised(wrg_reader._read_wrg_meta_from_handle, io.BytesIO(header.encode()))
                self.assertEqual(str(exc), prefix + header)
                self.assertTrue(exc.template_item)
                exc = _raised(wrg_site._parse_header, header)
                self.assertEqual(str(exc), prefix + "'" + header + "'")
                self.assertTrue(exc.template_item)

    def test_resource_and_grid_errors(self):
        """S10-4, S2-7: the errors of the resource and of the directions, translated whole, with their data."""
        no_models = {
            "es": "No se han definido modelos de aerogeneradores",
            "en": "No wind turbine models have been defined",
            "fr": "Aucun modèle d’éolienne n’a été défini",
            "de": "Es wurden keine Windturbinenmodelle definiert",
        }
        directions = {
            "es": "Número de direcciones no válido: 5. Debe ser un múltiplo entero positivo de 12, el número de sectores "
                  "del WRG «Parque Norte.wrg», sin superar 360.",
            "en": "Invalid number of directions: 5. It must be a positive integer multiple of 12, the number of sectors "
                  "of the WRG “Parque Norte.wrg”, not exceeding 360.",
            "fr": "Nombre de directions non valide : 5. Il doit être un multiple entier positif de 12, le nombre de "
                  "secteurs du WRG « Parque Norte.wrg », sans dépasser 360.",
            "de": "Ungültige Richtungsanzahl: 5. Sie muss ein positives ganzzahliges Vielfaches von 12 sein, der "
                  "Sektoranzahl des WRG „Parque Norte.wrg“, und darf 360 nicht überschreiten.",
        }
        for lang in ("es",) + _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                exc = _raised(resource_loader.normalize_resource_inputs, wasp_dir=_SETTINGS.name, models=[],
                              wrg_paths=None, wrg_ti_paths=None, wrg_ti_path=None)
                self.assertEqual(str(exc), no_models[lang])
                exc = _raised(resource_grid.validate_request, 12, 5, "nearest", "Parque Norte.wrg")
                self.assertIsInstance(exc, resource_grid.WrgContractError)
                self.assertEqual(str(exc), directions[lang])

    def test_layout_error_names_the_unnamed_model_in_the_language(self):
        """S2-7: «Modelo {n}», the name of a model without one, is a text; the error of the data comes as it is."""
        try:
            float("x")
        except ValueError as exc:
            reason = str(exc)
        expected = {
            "es": "coords_xy inválido para «Modelo 1»: " + reason,
            "en": "Invalid coords_xy for “Model 1”: " + reason,
            "fr": "coords_xy non valide pour « Modèle 1 » : " + reason,
            "de": "Ungültige coords_xy für „Modell 1“: " + reason,
        }
        for lang, text in expected.items():
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                exc = _raised(layout_builder.build_layout_arrays, models=[{"coords_xy": [(0.0, "x")]}], site=None,
                              wasp_dir="", use_wrg=False, wrg_paths=[], dtype=float, read_xy_csv=None,
                              bbox_from_site=None)
                self.assertEqual(str(exc), text)

    def test_raster_errors_are_written_in_spanish(self):
        """S7-12: the raster I/O errors, in Spanish at the source; English is a translation."""
        band = mock.Mock()
        band.ReadRaster.return_value = None
        gdal = mock.Mock(GDT_Float64=7)
        reading = {
            "es": "GDAL no devolvió datos al leer una celda del ráster.",
            "en": "GDAL returned no data while reading a raster cell.",
            "fr": "GDAL n’a renvoyé aucune donnée lors de la lecture d’une cellule du raster.",
            "de": "GDAL hat beim Lesen einer Rasterzelle keine Daten zurückgegeben.",
        }
        flow_map = {
            "es": "El mapa de flujo no contiene la coordenada 'x'.",
            "en": "The flow map does not contain the coordinate 'x'.",
            "fr": "La carte d’écoulement ne contient pas la coordonnée 'x'.",
            "de": "Die Strömungskarte enthält die Koordinate 'x' nicht.",
        }
        for lang in ("es",) + _LANGS:
            i18n.set_language(lang)
            with self.subTest(lang=lang):
                exc = _raised(raster_io.read_float64_pixel, band, 0, 0, gdal_module=gdal)
                self.assertIsInstance(exc, RuntimeError)
                self.assertEqual(str(exc), reading[lang])
                exc = _raised(wake_raster._extract_coord, object(), "x")
                self.assertEqual(str(exc), flow_map[lang])


if __name__ == "__main__":
    unittest.main()
