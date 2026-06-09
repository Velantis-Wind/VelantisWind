# Noise Module

**Purpose:** preliminary wind-turbine noise screening directly inside QGIS.

The Noise module estimates wind-turbine sound levels at receptors and can generate GIS outputs such as receiver layers, source-receptor links, raster noise maps and isophones. It is intended for early-stage screening, layout comparison, technical validation and GIS-based QA/QC.

> **Important:** this is an experimental, ISO-aligned screening workflow. It is not certified regulatory noise software and should not be presented as a bankable or permitting-grade acoustic assessment without independent validation.

---

## What the module calculates

Depending on the selected options, the module can calculate:

- A-weighted sound pressure level at each receptor;
- receptor limit and margin to limit;
- critical receiver;
- dominant turbine/source group;
- source-receptor link layers;
- source-group summary;
- noise raster map;
- isophones generated from the raster;
- DEM/DSM-aware receptor/source elevation sampling;
- simplified terrain-screening diagnostics;
- optional effective ground factor (`G_eff`) from land-use polygons.

The module is designed to make assumptions visible in QGIS rather than hide them in an external black-box workflow.

---

## Calculation engines

### Fast engine

The fast engine is intended for quick layout screening and UI checks. It uses a simplified propagation model and is useful for:

- quick comparison between layouts;
- confirming source/receptor layers are read correctly;
- checking limits and margins;
- testing raster/isophone generation on small cases.

Use it for rapid feedback, not for formal acoustic conclusions.

### ISO-aligned octave-band engine

The ISO-aligned engine follows the structure of octave-band outdoor sound propagation and reports the main attenuation components used internally.

It includes practical approximations for:

- geometric divergence;
- atmospheric absorption;
- ground effect;
- simplified terrain/topographic screening;
- source spectra and A-weighting;
- receiver-level aggregation from multiple turbines/source groups.

Current simplifications are documented in [Known limitations](#known-limitations). Keep these limitations visible when sharing results with testers or technical partners.

---

## Required inputs

### 1. Turbine source layer(s)

Recommended geometry:

```text
Point layer
```

Recommended CRS:

```text
Projected CRS in metres
```

Each turbine source should be represented as a point. Multiple turbine models are best handled as separate source layers during the experimental release:

```text
Layer A → acoustic settings for model A
Layer B → acoustic settings for model B
Layer C → acoustic settings for model C
```

A single mixed layer with per-feature acoustic model attributes is not the preferred public workflow yet.

### 2. Receiver layer

Supported geometry:

```text
Point receptor layer
Polygon receptor layer
```

For polygon layers, the module uses representative geometry/centroid-style handling for screening. For formal work, verify the receptor definition manually.

Recommended fields:

```text
name / id / receptor_id / building / type / limit
```

The exact field names can vary, but a stable identifier and a receptor limit are recommended for clear QA/QC.

### 3. Acoustic source level

The module supports two public workflows:

```text
Fixed LwA per source group
```

or:

```text
Acoustic curve / spectrum per source group
```

For technical validation, record the manufacturer/source of each acoustic assumption and the wind speed used when evaluating source levels.

### 4. Optional DEM/DSM

A DEM/DSM can be used to sample source and receptor elevations and to support simplified terrain-screening diagnostics.

Recommended input:

```text
Single-band raster
Projected CRS compatible with the project
Elevation units in metres
```

DEM/DSM use improves spatial consistency but does not make the workflow a full terrain-diffraction model.

### 5. Optional land-use layer

The land-use layer is used to estimate effective ground factor (`G_eff`) along source-receptor paths.

Recommended geometry:

```text
Polygon layer
```

Recommended CRS:

```text
Same projected CRS as the QGIS project
```

Preferred numeric fields:

```text
g_factor
g
ground_g
g_value
G
```

Expected numeric range:

```text
0.0 = acoustically hard ground
1.0 = porous/soft ground
```

Intermediate values are accepted.

If a numeric ground-factor field is not available, the module may infer approximate values from text fields such as:

```text
landuse
cover
type
uso_suelo
uso
clase
```

This fallback is useful for screening but should be reviewed manually. For technical validation, a numeric `g_factor` field is strongly preferred.

---

## Source spectra and acoustic curves

The module can use:

- fixed A-weighted source level (`LwA`);
- octave-band reference spectra;
- acoustic curves by wind speed;
- custom CSV inputs where supported by the UI.

Recommended CSV style for acoustic curves:

```text
wind_speed,lwa
6,101.5
7,103.0
8,104.2
9,105.0
```

Recommended CSV style for octave-band spectra:

```text
frequency_hz,lw
63,92.0
125,96.0
250,99.0
500,101.0
1000,102.0
2000,101.0
4000,98.0
8000,93.0
```

The built-in spectra are reference templates. They are not certified manufacturer data.

---

## Main options

Typical options include:

- engine: fast or ISO-aligned;
- receptor height;
- calculation radius;
- receptor limit;
- fixed `LwA` or acoustic curve mode;
- optional DEM/DSM;
- optional land-use `G_eff`;
- raster resolution and extent;
- isophone generation;
- source-receptor links.

For publication examples, keep test extents small and use coarse raster resolution first. Fine rasters over large domains can be slow.

---

## Outputs

The module can create or update:

```text
Receiver result layer
Source summary layer
Dominant source-receptor link layer
Noise raster
Isophone contours
Noise results dialog
```

Typical receiver fields include:

```text
noise level
limit
margin
critical flag
dominant source/source group
terrain-screening diagnostics where available
```

For ISO + DEM/DSM workflows, the result payload may include diagnostics such as mean terrain screening or dominant-screening counters. Treat these as QA/QC indicators, not as certified diffraction evidence.

---

## DEM/DSM behavior

DEM/DSM sampling is used for:

- turbine/source elevation;
- receptor elevation;
- path/profile information for simplified screening;
- raster cell elevation where raster generation is enabled.

Important boundaries:

- DEM/DSM does not replace a full terrain-noise model.
- Intermediate terrain obstruction is simplified.
- Raster and receiver paths should be checked separately in technical validation.
- Large rasters with DEM/DSM may take time.

---

## Background task behavior

The module can run task-safe calculations with `QgsTask` to keep QGIS responsive.

Task-friendly cases include:

- fast engine with or without DEM/DSM;
- ISO-aligned engine with or without DEM/DSM when inputs can be represented with primitive snapshots/file paths;
- raster generation from task-safe source/receptor snapshots.

Synchronous fallback is still expected for:

- land-use `G_eff`, because it relies on vector polygon intersections;
- configurations that cannot be safely serialized;
- unexpected task-preparation failures.

A synchronous fallback is not automatically an error. It means the module selected the safer route for that input combination.

---

## Multiple turbine models

Recommended public experimental release workflow:

```text
One source layer per acoustic group / turbine model
```

Example:

```text
Vestas V112 layer → V112 acoustic curve
Vestas V150 layer → V150 acoustic curve
```

This is easier to audit than mixing multiple models in one layer before per-feature acoustic model selection is fully hardened.

---

## Known limitations

The Noise module is an ISO-aligned screening tool, not certified regulatory software.

Current simplifications include:

- atmospheric absorption uses reference assumptions and simplified corrections;
- ground effect follows the ISO-style regional structure but uses simplified coefficients;
- terrain screening is simplified and does not model advanced multiple-edge diffraction;
- source directivity is currently simplified;
- long-term meteorological correction is not applied as a full regulatory workflow;
- built-in spectra are reference templates, not certified manufacturer spectra;
- land-use text fallback can misclassify ground type if the attribute table is inconsistent;
- large ISO + DEM/DSM rasters may be computationally heavy;
- results should be independently checked before formal use.

---

## Recommended smoke tests before publication

Run these tests in a clean QGIS profile when possible:

1. Open the Noise page and confirm all help text appears correctly.
2. Fast engine without DEM/DSM.
3. ISO-aligned engine without DEM/DSM.
4. ISO-aligned engine with DEM/DSM and no raster.
5. ISO-aligned engine with DEM/DSM and raster.
6. Raster + isophones on a small extent.
7. Land-use `G_eff` with numeric `g_factor` polygons.
8. Two source layers with different acoustic settings.
9. Custom acoustic curve CSV.
10. Cancel a heavy background task and run again.
11. Confirm no public UI text still uses development-version labels.

---

## Related documents

- [`NOISE_ARCHITECTURE.md`](NOISE_ARCHITECTURE.md)
- [`SMOKE_TESTS.md`](SMOKE_TESTS.md)
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- [`LIMITATIONS.md`](LIMITATIONS.md)
