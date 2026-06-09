# Shadow Flicker Module

**Purpose:** preliminary shadow/flicker screening directly inside QGIS.

The Shadow Flicker module estimates potential flicker impact at receptors and across raster maps using turbine geometry, receptor positions, solar geometry, terrain elevation and user-defined time assumptions. It is intended for screening and layout iteration, not final permitting certification.

> **Important:** the current experimental release is DEM/DSM-aware for absolute elevations, but it does **not** yet implement full intermediate terrain line-of-sight obstruction between each turbine and receptor.

---

## What the module calculates

Depending on selected options, the module can calculate:

- annual astronomical flicker hours per receptor;
- real/adjusted flicker hours after availability factor;
- number of affected days;
- maximum minutes per day;
- worst day per receptor;
- monthly distribution;
- hour-by-month matrix;
- dominant turbine contribution;
- receptor severity class;
- shadow flicker raster;
- filtered raster outputs by month/hour where supported.

---

## Required inputs

### 1. Turbine layer

A QGIS point layer containing wind-turbine positions.

Recommended attributes or UI settings:

- hub height;
- rotor diameter;
- turbine name or ID.

If these are not available as attributes, the module may use values configured in the UI.

### 2. Receptor layer

A QGIS point layer containing receptor locations.

Recommended attributes:

- receptor name or ID;
- optional receptor category.

### 3. Location and time settings

The module needs consistent geographic and temporal assumptions:

- latitude and longitude;
- time zone mode;
- IANA time zone or fixed UTC offset;
- assessment year;
- time step;
- minimum and maximum solar elevation thresholds.

### 4. Optional DEM/DSM

A DEM/DSM raster can be used to adjust the absolute elevation of turbines, receptors and raster cells.

---

## Main options

| Option | Meaning |
|---|---|
| Time step | Temporal resolution of receptor calculation. Smaller values are more precise but slower. |
| Raster time step | Temporal resolution for raster calculation. |
| Observer height | Height of receptor point above ground. |
| Minimum sun elevation | Filters very low solar elevations. |
| Maximum sun elevation | Optional upper screening limit; default is normally 90°. |
| Maximum shadow distance | Maximum turbine-receptor distance considered. |
| Turbine availability | Linear correction factor applied to astronomical hours. |
| DEM/DSM | Terrain/surface raster used to adjust absolute elevations. |
| Raster output | Generates spatial flicker map. |
| Raster resolution | Cell size for the output raster. |

Current experimental release execution is sequential for receptor calculations to prioritise stability. Raster generation can run through a QGIS task-style workflow where supported.

---

## DEM/DSM behavior

The current experimental release implementation is **DEM/DSM-aware**.

The DEM/DSM is used to adjust absolute elevations:

```text
source elevation   = DEM at turbine + hub height
receiver elevation = DEM at receptor + observer height
raster elevation   = DEM at cell + observer height
```

This affects the vertical geometry of the turbine-receptor-sun alignment.

Important limitation:

```text
The current version does not yet implement full intermediate terrain obstruction / line-of-sight blocking between turbine and receptor.
```

In other words, terrain adjusts relative elevations, but the module does not yet fully test whether a hill between a turbine and a receptor physically blocks the shadow path.

Recommended wording for experimental use:

```text
DEM-aware shadow flicker geometry
```

Avoid claiming:

```text
full 3D topographic shadow obstruction model
```

---

## Calculation concept

At a high level, the module evaluates whether the solar position, turbine rotor and receptor geometry align in a way that can produce flicker.

The calculation uses:

- NOAA-style solar position over the assessment year;
- turbine coordinates and rotor geometry;
- receptor coordinates and observer height;
- terrain-adjusted elevations if DEM/DSM is enabled;
- time-step sampling;
- maximum shadow distance filtering;
- optional operational availability correction.

The geometric engine follows an angular shadow-screening approach: solar position is compared against the turbine-to-receptor azimuth/altitude target, with a rotor-size angular tolerance and a configurable maximum shadow distance.

The rotor is treated as a worst-case disc for screening. The plugin does not currently query wind direction to orient the rotor plane for each timestep.

---

---

## Architecture and diagnostics

The public workflow now follows the same pattern as Energy and Noise:

```text
Shadow page → dialog state → validation → controller → runner → point-receptor/raster calculation → QGIS outputs
```

Console diagnostics are quiet by default. Start QGIS with `VELANTISWIND_DEBUG=1` only when you need detailed geometry, DEM/DSM or raster troubleshooting logs.

## Outputs

| Output | Description |
|---|---|
| Receptor result layer | Annual hours, real/adjusted hours, affected days, severity class and dominant turbine information. |
| Summary dialog | Overview of turbines, receptors, maximum impact, monthly tables and receptor table. |
| Monthly table | Flicker distribution by month. |
| Hour × month matrix | Temporal distribution of flicker occurrence. |
| Raster map | Spatial map of calculated flicker impact. |
| Filtered raster | Optional raster filtered by selected month/hour where available. |
| CSV export | Optional tabular export of matrices and results. |

---

## Recommended workflow

1. Load turbine and receptor layers.
2. Check that the project CRS and layer units are appropriate.
3. Open **Velantis Wind → Shadow Flicker**.
4. Select turbine and receptor layers.
5. Set hub height, rotor diameter and observer height.
6. Select DEM/DSM if available.
7. Select year, time zone and time step.
8. Set maximum shadow distance and availability factor.
9. Run receptor calculation first.
10. Enable raster output only after the receptor workflow is confirmed.
11. Review receptor results, monthly table and raster output.

---

## Performance notes

Shadow flicker calculations can be computationally heavy because they combine:

```text
number of turbines × number of receptors × number of time steps
```

Raster output adds an additional spatial dimension. For large projects, start with:

- larger time step;
- coarser raster resolution;
- smaller test area;
- receptor-only calculation before raster.

Then refine settings once the workflow is confirmed.

---

## Known limitations

- Intended for screening and early-stage assessment.
- Rotor is treated as a worst-case disc; the actual wind-direction-dependent rotor plane is not modelled.
- DEM/DSM adjusts absolute elevations but does not yet perform full intermediate terrain line-of-sight blocking.
- Solar angular semi-diameter is fixed at `0.27°`.
- Turbine availability is applied as a linear multiplicative factor: `real hours = astronomical hours × availability`.
- Results depend on time-zone assumptions, receptor height, turbine geometry and time step.
- Raster outputs can be computationally expensive at fine resolution.
- Execution is sequential in the current experimental release for stability.
- Final regulatory submissions should be validated with specialist tools or project-specific methods.

---

## Recommended smoke tests before publication

1. Shadow calculation without DEM/DSM.
2. Shadow calculation with DEM/DSM.
3. Receptor-only calculation.
4. Raster calculation.
5. IANA time zone mode.
6. Fixed UTC-offset mode.
7. Cancel/close behavior during a long raster calculation.
8. Export monthly and hour-by-month tables.

When reporting issues, include QGIS version, number of turbines, number of receptors, DEM/DSM status, year, time zone mode, time step, raster resolution and maximum shadow distance.

---

## Related architecture document

See [`SHADOW_ARCHITECTURE.md`](SHADOW_ARCHITECTURE.md) for the current code structure and refactor boundary.
