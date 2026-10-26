# Energy / AEP module

The Energy / AEP module estimates preliminary wind-farm production directly inside QGIS. It connects GIS layouts, turbine curves and sectoral wind-resource data to a PyWake-based calculation workflow.

> **Scope:** this is an experimental pre-assessment workflow for screening, layout comparison, validation checks and technical review. It is not a certified bankable energy-assessment package and it does not replace formal project-loss and uncertainty analysis.

---

## What it calculates

Depending on the selected configuration, the module can produce:

- the gross AEP without wakes nor blockage (A_0) and the net AEP of the configuration;
- the signed loss breakdown (wake loss, impacts of the added turbulence and of the blockage, total loss), by turbine, by turbine model and for the farm;
- the ambient and effective TI per turbine;
- the configuration selected and the one executed, read from the PyWake objects, with the persistent warnings and the convergence of the iterative loops;
- directional/sector summaries where available;
- per-turbine result tables;
- QGIS point attributes with calculated results;
- CSV and HTML-style technical reports;
- a resource-extent overlay for visual QA/QC;
- a georeferenced wake raster for one wind direction.

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

Power curves are used as supplied: a high-wind derating or an explicit shutdown before cut-out is preserved. Only negative or non-finite power values are set to zero.

In mixed-model parks, each turbine model is evaluated with its own rotor diameter, hub height and Power/CT curve.

### 3. Wind resource

The Energy module supports two main workflows:

| Resource type | Typical use | Notes |
|---|---|---|
| WAsP / PyWake GridSite folder | Sectoral resource already exported/prepared for the PyWake-compatible loader. | Requires a consistent folder/grid structure. |
| WRG / ZIP | Wind-resource grid in WRG format, optionally packaged in ZIP. | Optional TI rasters can be supplied for turbulence-aware workflows. |

For accurate AEP, the resource should provide sectoral wind information. Omnidirectional mean wind speed alone is not enough for a reliable wake/AEP calculation.

WRG handling in the AEP calculation:

- Each position keeps the local Weibull climate of the WRG (A, k and sector frequencies): no speed-up is derived (Speedup `none`).
- With `nearest` directional interpolation, each calculation direction takes the climate of the sector it falls in, so the native sector frequencies are preserved; `linear` interpolates between the centres of the two neighbouring sectors (see **Resource parameters**).
- With one WRG height, the WRG climate is used for every hub height and the turbine hub height is not modified. With several WRG heights, the climate is interpolated vertically between them.
- Directional AEP summaries are aggregated back to the native WRG sectors.

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
5. The same curve/resource assumptions are used when comparing with external tools.
6. TI rasters are selected when using TI-sensitive wake models and a TI-based comparison is expected.
7. Blockage is only enabled with a compatible PyWake engine.
8. The resource-extent overlay looks spatially aligned with the layout.

---

## Resource parameters

How the wind climate is integrated depends on the resource:

- **WRG.** The AEP is computed on a number of wind directions that is a multiple of the N sectors of the WRG, up to 360 (N alone when N > 360): every sector is divided into equal parts and computed at the centre of each one, so every sector gets the same number of directions and none falls on a border between sectors. The initial choice is 7 per sector (84 for 12 sectors), or 1 per sector when 7N exceeds 360; it is a practical choice, not a guarantee of convergence. The directional interpolation is `nearest` (the initial one) or `linear`; x, y and height stay linear. The Speedup is fixed to `none`. The wind speeds cover the operating band of the turbines (declared by `.wtg` and `.owtg` files, or from the first to the last wind speed of a CSV table or a manual curve; with several models, the union of their bands) with a step of 1, 0.5 or 0.25 m/s, initially the step of their power curves. A request outside these options stops the calculation with an error; nothing is rounded. These rules are shared with Velantis Optimizer.
- **GRD (WAsP grid folder).** The defaults of its PyWake `Site`: 360 directions from 0° to 359°, linear interpolation and 3–25 m/s. With 12 sectors, the breakdown by sector assigns the directions that fall on a border to the sector of lower index, so one sector gets 31 directions and another 29; the totals do not change.
- **Hours per year:** 8766 h (Julian year of 365.25 days), for WRG and GRD.

In the dialog, the WRG parameters are in **Resource parameters**, under the WRG row and its metadata line (which gives the number of sectors), shown only with a readable WRG. The group is folded when the dialog opens; its button shows the choice (for example «Resource parameters (nearest, 84 directions, 3–24 m/s every 0,5)»). Inside: the directional interpolation and the fixed Speedup, the calculation directions (the multiples of the sectors) and the wind speeds (the band of the models, shown with «—» until every model row is defined, and the step). Choosing another WRG gives the directions and the interpolation their initial values, and another set of models gives the step its initial value. Nothing is saved between sessions. Every parameter explains itself when the pointer rests on it.

Gross/free-stream and wake-reduced AEP use the same directions, wind speeds and annualisation, and the capacity factor uses the same hours. The log line `[RECURSO]` and the result notes record the settings used, and the result keeps them, with the full grids (`resource_settings`).

---

## Main physical options

The wake physics is a configuration of exact PyWake 2.6.18 classes, each with the values of its signature unless edited (the arguments of its subordinate objects included: rotor average, ground model, superposition, added turbulence, blockage and engine): the engine (`PropagateDownwind`, `All2AllIterative`, `PropagateUpDownIterative`), one of twelve wake-deficit classes with its editable arguments, its rotor average and its ground model, the wake superposition, the added turbulence and, with `All2AllIterative` and `PropagateUpDownIterative`, a blockage model with its own superposition. The default is `PropagateDownwind`, `BastankhahGaussianDeficit` with its signature values, `LinearSum`, no added turbulence and no blockage. The classes, their arguments (and those of the subordinate objects, with the only technical limit, what PyWake does not build, and the warnings of what it calculates with non-finite results) and helps, what PyWake refuses, the persistent warnings, the convergence, what is not offered and why, the loss breakdown and the `wake_physics` contract of the API are described in the [main README, «Wake physics»](../../README.md#wake-physics).

- Nothing is replaced: a combination PyWake cannot calculate is a conflict in the dialog (with its reason and resolution) and an error in the API; the calculation is not started. There is no automatic superposition, no engine switch, no fallback turbulence and no degradation of a calculation PyWake refuses.
- What PyWake refuses is refused exactly where it stops: with the engine, the number of turbines (some combinations fail only where PyWake evaluates a model between turbines, each from the number of turbines measured for it: most with `All2AllIterative` always and with the other engines from the second turbine, checked with the turbines of the calculation; a note in the dialog) and the stage (the AEP or the map of the raster). What PyWake calculates, even without physical sense, is allowed, and warned where its behaviour is known; what fails only with given values is an error of the calculation, with its cause. Each resolution names only options that take its cause away.
- The classes are not the PyWake predefined models (presets): for example `TurboGaussianDeficit` is offered as a class, and the `Nygaard_2022` preset (TurbOPark) is that class with `ct2a_mom1d`, `ctlim = 0.96`, `GaussianOverlapAvgModel`, `Mirror(SquaredSum())`, `SquaredSum` and the free wind speed of the waked turbine (`WS_jlk`), which is not in the class signature and cannot be chosen; on a WRG resource, without speed-up, both give the same AEP, but not on a resource with a spatial speed-up. Choosing the arguments and components of a preset reproduces it as far as the class allows.
- Before simulating, the classes of the built model are checked against the configuration; the result records what was executed, read from the objects.
- `GaussianOverlapAvgModel` needs `h5py` and `h5netcdf`; without them the dialog asks before using `CGIRotorAvg(7)` instead (see [`INSTALL_ENERGY_DEPENDENCIES.md`](INSTALL_ENERGY_DEPENDENCIES.md)).

---

## Outputs

| Output | Description |
|---|---|
| Result dialog | Summary of AEP, losses, turbine counts and model diagnostics. |
| Per-turbine table | Coordinates, model name, gross/free AEP, operational/wake-reduced AEP and loss diagnostics. |
| QGIS result layer | Updated point attributes for visual inspection and downstream GIS work. |
| Summary memory layer | Optional project-level summary layer. |
| CSV export | Per-turbine result export for external review. |
| HTML report | Human-readable technical output where enabled. |
| Resource extent overlay | Visual QA layer showing the loaded resource footprint. |
| Wake raster | Georeferenced GeoTIFF layers for one selected or most energetic direction (free-flow speed, `WS_eff`, deficit in m/s and in %, and terrain when available), loaded under **VelantisWind · Estelas**. |
| Wake-raster JSON | Audit sidecar recording plugin version, CRS, resource, models, grid, warnings and raster statistics. |

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
9. With a WRG, review its **Resource parameters** under it.
10. Run the calculation.
11. Optionally create a wake raster. It runs in the QGIS task manager, can be cancelled and requires a projected metric CRS.
12. Inspect skipped turbines, resource extent, per-turbine values and global losses.
13. Export reports only after confirming the inputs and CRS are correct.

---

## Wake raster

**Create wake raster** computes a georeferenced wake map for one wind direction: the most energetic sector of the resource or a manually entered direction. It runs as a cancellable QGIS task and writes a GeoTIFF package plus a JSON audit file.

- A WRG is loaded as in the AEP: each position keeps its local Weibull climate (no speed-up), so the free-flow speed of the map is uniform, with the directional interpolation chosen in **Resource parameters** and straight wake distances. Standard WRG files do not contain flow turning.
- The flow map is computed in bounded tiles, so memory stays limited on fine grids and cancellation is checked between tiles.
- Mixed parks keep each model's diameter, hub height and Power/CT curve.
- The raster is configured as the AEP, from the dialog when it is created: the same classes, built by the same factory and checked before simulating (with the turbines it simulates; what only the map refuses, also with one turbine), the resource with its TI (the fixed TI or the TI rasters of a WRG; the own TI of a GRD keeps its previous treatment, declared in the JSON) and the air density of the dialog's controls, treated as in the AEP (if it cannot be established, the raster stops). If the turbines and their positions, the resource and its TI, the wake model, the air density or the project CRS differ from the last AEP of the project, the final window says which, and the JSON records it (`aep_comparison`). The flow map with blockage is the one of PyWake for every engine and blockage model offered. The JSON records the configuration selected and executed, the TI, the convergence and the numerical precision (always `float64`, as the AEP: in `float32` the projected coordinates of the turbines would be rounded).
- With `WeightedSum` the map is calculated in tiles and PyWake computes its weights with a global maximum of each calculation, so the map may differ from one calculated at once; the raster says so.

---

## Comparing against external software

When validating the module against external tools, record at least:

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
- AEP memory grows roughly with turbines² × calculation directions × wind speeds. With 80–84 directions × 71 wind speeds, measured peaks were about 0.7–1.1 GB for 86 turbines, 2.7 GB for 300 turbines and more than 6 GB for 600 turbines; the wind speeds of the turbines' band are fewer. If the system runs out of memory, QGIS can be closed by the operating system. For large layouts, reduce the number of directions or choose a coarser wind-speed step. The wake raster does not add its own memory risk.

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
7. A combination PyWake refuses (for example a deficit with `use_effective_ti` and no turbulence) to confirm that it is shown as a conflict and not calculated.
8. CSV export and QGIS attribute update.
9. Resource extent overlay.
10. Result dialog and report export.
11. A WRG and a GRD resource, and the resource parameters of the WRG.
12. `TurboGaussianDeficit` with the components of the `Nygaard_2022` preset, and `GaussianOverlapAvgModel` with and without `h5py`.
13. Wake raster for the most energetic and a manual direction.
14. Comparison of total and per-turbine AEP against the previous accepted build.

---

## Related document

See [`ENERGY_ARCHITECTURE.md`](ENERGY_ARCHITECTURE.md) for the code structure and release boundary.
