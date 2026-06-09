# Energy / AEP module

The Energy / AEP module estimates preliminary wind-farm production directly inside QGIS. It connects GIS layouts, turbine curves and sectoral wind-resource data to a PyWake-based calculation workflow.

> **Scope:** this is an experimental pre-assessment workflow for screening, layout comparison, validation checks and technical review. It is not a certified bankable energy-assessment package and it does not replace formal project-loss and uncertainty analysis.

---

## What it calculates

Depending on the selected configuration, the module can produce:

- gross/free-stream AEP;
- wake-reduced operational AEP;
- wake loss by turbine and by turbine model;
- optional turbulence and blockage diagnostic variants;
- rotor-average diagnostics where supported by the selected model;
- directional/sector summaries where available;
- per-turbine result tables;
- QGIS point attributes with calculated results;
- CSV and HTML-style technical reports;
- a resource-extent overlay for visual QA/QC.

The exact meaning of the result depends on the wind resource, turbine curve, wake deficit model, engine, turbulence model, blockage model, rotor-average option and PyWake version used for the run.

---

## Required inputs

### 1. Turbine layout

A layout can be provided through:

- the interactive Energy map workflow;
- an existing QGIS point layer;
- a single CSV file with coordinates;
- one CSV/layout source per turbine model for mixed-model projects.

Recommended coordinate fields:

```text
x,y
```

or:

```text
easting,northing
```

Use a projected CRS in metres. Do not use longitude/latitude degrees for wake-distance calculations.

### 2. Turbine model and curve

Each turbine model should define:

- turbine name;
- rotor diameter;
- hub height;
- rated power;
- power curve;
- Ct/thrust curve when available.

Generic curves included in the UI are only screening placeholders. For validation or comparison against external tools, use the same manufacturer or project-specific curve in all tools.

### 3. Wind resource

The Energy module supports two main workflows:

| Resource type | Typical use | Notes |
|---|---|---|
| WAsP / PyWake GridSite folder | Sectoral resource already exported/prepared for the PyWake-compatible loader. | Requires a consistent folder/grid structure. |
| WRG / ZIP | Vortex/WRG-style resource input. | Optional TI rasters can be supplied for turbulence-aware workflows. |

For accurate AEP, the resource should provide sectoral wind information. Omnidirectional mean wind speed alone is not enough for a reliable wake/AEP calculation.

### 4. Optional turbulence intensity input

For WRG workflows, the module can use:

- one or more TI rasters;
- TI raster height metadata when available;
- a fixed/fallback TI if the selected PyWake model requires a TI variable and no raster is supplied.

If a turbulence-aware model is selected without a TI raster, the plugin warns the user and records the fallback assumption in the output.

---

## Input checklist before running

Before pressing calculate, check:

1. The QGIS project CRS is projected and uses metres.
2. The turbine coordinates are inside the wind-resource domain.
3. The turbine curve uses the expected units.
4. Hub height and rotor diameter match the intended model.
5. The same curve/resource assumptions are used when comparing with WAsP, WindPRO, OpenWind or other tools.
6. TI rasters are selected when using TI-sensitive wake models and a TI-based comparison is expected.
7. Blockage is only enabled with a compatible PyWake engine.
8. The resource-extent overlay looks spatially aligned with the layout.

---

## Main physical options

### Wake deficit model

The UI exposes PyWake-compatible wake deficit choices such as NOJ/Jensen, Bastankhah Gaussian, Niayifar Gaussian, TurboNOJ, TurboGaussian, Zong Gaussian and other options available in the installed PyWake version.

### Wind-farm model engine

| Engine | PyWake family | Practical note |
|---|---|---|
| `PDW` | PropagateDownwind | Fast and stable for many wake-only workflows. |
| `A2A` | All2AllIterative | Useful for iterative interaction effects. |
| `PUD` | PropagateUpDownIterative | Used for selected induction/blockage workflows where supported. |

Some PyWake combinations are version-dependent. The plugin applies conservative fallbacks or warnings when a selected combination cannot be executed safely.

### Turbulence

Ambient TI is an input assumption in the resource/site. Added wake turbulence is optional and depends on the selected PyWake model. The module can report diagnostic variants when this separation is meaningful.

### Blockage / induction

Blockage depends on the PyWake engine and blockage model. `PDW` does not apply blockage; the plugin warns and disables incompatible blockage selections rather than silently reporting a misleading result.

### Rotor average

Rotor averaging can better represent rotor-disc effects for some wake models. Older Gaussian-overlap choices are redirected to compatible PyWake rotor-average options when needed.

### Superposition

The module supports compatible wake-superposition options and applies fallback rules for combinations rejected by the installed PyWake version.

---

## Outputs

| Output | Description |
|---|---|
| Result dialog | WAsP-style summary of AEP, losses, turbine counts and model diagnostics. |
| Per-turbine table | Coordinates, model name, gross/free AEP, operational/wake-reduced AEP and loss diagnostics. |
| QGIS result layer | Updated point attributes for visual inspection and downstream GIS work. |
| Summary memory layer | Optional project-level summary layer. |
| CSV export | Per-turbine result export for external review. |
| HTML report | Human-readable technical output where enabled. |
| Resource extent overlay | Visual QA layer showing the loaded resource footprint. |

The wake-reduced output is not a full project net AEP unless external losses such as availability, electrical losses, curtailment, icing, environmental losses, degradation and uncertainty are added separately.

---

## Recommended workflow

1. Install PyWake in the QGIS Python environment.
2. Load the turbine layout or prepare a layout CSV.
3. Confirm the project CRS uses metric units.
4. Open **Velantis Wind → Energy / AEP**.
5. Define turbine model(s) and power/Ct curve(s).
6. Select the WAsP/GridSite folder or WRG/ZIP resource.
7. Add TI rasters if the comparison requires turbulence intensity.
8. Select wake model, engine and optional physical effects.
9. Run the calculation.
10. Inspect skipped turbines, resource extent, per-turbine values and global losses.
11. Export reports only after confirming the inputs and CRS are correct.

---

## Comparing against external software

When validating the module against WAsP, WindPRO, OpenWind or similar tools, record at least:

- resource source and height;
- layout CRS and turbine coordinates;
- turbine model, hub height, rotor diameter and curve source;
- wake model and wake-superposition assumption;
- TI source or fallback TI;
- gross AEP, wake-reduced AEP and wake-loss percentage;
- whether neighbouring wind farms or external wakes were included in the reference tool;
- whether reported values are gross, wake-reduced, or full net including project losses.

A good gross-AEP match but a larger net discrepancy often indicates different wake, TI, blockage, neighbouring-park or external-loss assumptions rather than a coordinate/resource parsing error.

---

## Known limitations

- PyWake must be installed separately in the QGIS Python environment.
- Results depend strongly on the wind-resource grid, sectoral data quality and turbine curves.
- Some PyWake model combinations are version-dependent.
- WRG workflows without TI rasters rely on fixed/fallback TI for models that need turbulence intensity.
- The module does not currently perform complete bankable project-loss accounting.
- Large layouts and high-resolution resources may take time inside QGIS.

---

## Optional diagnostics

Normal public builds keep Energy console diagnostics quiet by default. For developer testing, launch QGIS with:

```bash
VELANTISWIND_DEBUG=1
```

This enables extra console messages for turbine-curve parsing and selected Energy UI actions. It does not change numerical results.

---

## Smoke tests before publication

1. WAsP/GridSite resource with one turbine model.
2. WRG/ZIP resource without TI raster.
3. WRG/ZIP resource with TI raster.
4. Layout from CSV.
5. Layout from interactive map / QGIS layer.
6. A turbulence-enabled model.
7. An intentionally incompatible blockage setting to confirm warning/fallback behaviour.
8. CSV export and QGIS attribute update.
9. Resource extent overlay.
10. Result dialog and report export.
11. Comparison of total and per-turbine AEP against the previous accepted build.

---

## Related document

See [`ENERGY_ARCHITECTURE.md`](ENERGY_ARCHITECTURE.md) for the code structure and release boundary.
