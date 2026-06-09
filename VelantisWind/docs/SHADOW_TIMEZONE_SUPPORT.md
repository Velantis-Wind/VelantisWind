# Shadow Flicker · hora civil local mundial sin `timezonefinder`

Esta versión deja `timezonefinder` fuera del flujo normal para no forzar `numpy >= 2` ni romper entornos QGIS/OSGeo4W con SciPy/PyWake.

## Modos disponibles

- **Hora civil local IANA/DST**: por ejemplo `Europe/Madrid`, `America/Santiago`, `Asia/Tokyo`. Es el modo recomendado para informes y tablas por hora/mes.
- **UTC offset fijo / fixed-offset**: mantiene un offset fijo todo el año, útil para reproducir comparaciones reproducibles o flujos antiguos.

## Base IANA incluida en el plugin

El plugin incluye ahora una base local más amplia:

- `assets/tzdata/iana_timezones_full.txt`: catálogo amplio de zonas IANA y aliases de compatibilidad.
- `assets/tzdata/zone.tab` y `zone1970.tab`: tablas oficiales/canónicas.
- `assets/tzdata/zoneinfo/`: ficheros TZif incluidos para cargar reglas DST aunque el sistema no tenga base horaria disponible.
- `assets/tzdata/tzdata_version.txt`: versión de la base incluida.

La interfaz muestra primero zonas comunes de mercado eólico y después el catálogo completo.

## Dependencias recomendadas

No instales `timezonefinder` en OSGeo4W para este flujo. Las versiones recientes pueden actualizar `numpy` a 2.x y entrar en conflicto con SciPy/PyWake.

Con esta versión, el plugin funciona con:

```bash
python -m pip install tzdata
```

`tzdata` es ligero y seguro para `zoneinfo`, pero incluso si faltase, el plugin intenta cargar la base TZif incluida en la propia repo.

## Autodetección de zona horaria

Sin `timezonefinder`, una detección mundial exacta desde latitud/longitud requeriría polígonos globales de zonas horarias. Para evitar esa dependencia pesada, el plugin hace lo siguiente:

1. Usa detección aproximada por cajas geográficas para mercados comunes.
2. Muestra una advertencia cuando la detección es aproximada.
3. Permite seleccionar manualmente cualquier zona IANA desde el desplegable completo.

Para proyectos cerca de fronteras horarias, offshore, islas o países con varias zonas, selecciona manualmente la zona correcta.

## Flujo implementado

1. El usuario selecciona o autodetecta latitud/longitud del proyecto.
2. El plugin propone una zona IANA si puede hacerlo con seguridad razonable.
3. El cálculo solar se evalúa internamente sobre una línea temporal UTC.
4. Cada instante se convierte a hora civil local para rellenar la matriz mes × hora.
5. En modo fixed offset se conserva el comportamiento anterior: un offset UTC constante todo el año.

Ejemplo para Valladolid:

- Zona: `Europe/Madrid`
- Enero: UTC+1
- Agosto: UTC+2
- Una sombra física a `05:30 UTC` en agosto se acumula como `07:30` hora civil local.

## Licencia de la base horaria incluida

Los ficheros TZif incluidos proceden del paquete Python `tzdata` y se acompañan con `assets/tzdata/LICENSE-tzdata-package.txt`.

## Default for experimental release

For reproducible fixed-offset screening, the default mode is **Fixed UTC offset**.
Use **Local civil time (IANA/DST)** when the objective is to present results by the real legal clock time of the site, including daylight saving time.

