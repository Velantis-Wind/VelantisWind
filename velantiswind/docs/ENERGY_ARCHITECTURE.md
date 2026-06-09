# Energy module architecture

This document describes the current Energy / AEP architecture for the public experimental release package.

The refactor objective was conservative: improve readability, isolate UI responsibilities and document the execution boundary without changing the numerical PyWake workflow.

---

## Current flow

```text
aep_setup_dialog.py
  ↓
energy_core/dialog_state.py
  ↓
energy_core/validation.py
  ↓
energy_core/dialog_controller.py
  ↓
energy_core/runner.py
  ↓
ag_core/aep_compute.py
  ↓
ag_core/orchestration/
ag_core/resources/
ag_core/layout/
ag_core/turbines/
ag_core/physics/
ag_core/simulation/
ag_core/results/
ag_core/qgis_io/
```

`ag_core/aep_compute.py` remains the compatibility façade around the historical PyWake execution path. It is smaller than the original implementation, but it deliberately remains the public execution boundary for this experimental release.

---

## Design rules

1. **Do not put PyWake execution in Qt widgets.** The UI collects user input only.
2. **Build a structured config before calculating.** `EnergyRunConfig` is the boundary between UI and engine.
3. **Validate early.** User-facing validation should happen before PyWake fails several layers below.
4. **Keep QGIS objects near the edges.** Pure calculation helpers should avoid direct `QgsProject` or widget dependencies where possible.
5. **Preserve public signatures during experimental testing.** `compute_aep_from_ui()` and `compute_and_update()` remain available for compatibility.
6. **Refactor by extraction, not rewrite.** Numerical changes should be explicit physics fixes, not side effects of cleanup.
7. **Keep public builds quiet.** Developer console diagnostics are gated behind `VELANTISWIND_DEBUG=1` unless the message is a user-facing warning/error.

---

## Package responsibilities

### Plugin entry point

```text
plugin.py
```

Creates the QGIS action, opens the main Velantis Wind hub and keeps the hub non-modal so QGIS map tools can continue working.

### UI layer

```text
aep_setup_dialog.py
```

Owns the visible Energy/AEP dialog: widgets, selectors, help text, resource extent buttons, map interaction hooks and user actions.

It should not own resource loading, turbine parsing, PyWake model construction or result-table generation.

### Application layer

```text
energy_core/
├─ domain.py
├─ dialog_state.py
├─ validation.py
├─ dialog_controller.py
├─ ui_feedback.py
└─ runner.py
```

Responsibilities:

- convert the dialog state into `EnergyRunConfig`;
- validate user inputs;
- manage progress and user-facing messages;
- call the calculation runner;
- update QGIS outputs and open the result dialog.

### Engine / compatibility façade

```text
ag_core/aep_compute.py
```

Still coordinates the main AEP calculation because it contains the sensitive sequencing around PyWake calls and stable result keys consumed by the UI, exporters and QGIS layer writers.

It should become smaller over time, but not immediately before publication unless regression fixtures are available.

### Orchestration helpers

```text
ag_core/orchestration/
├─ resource_loader.py
├─ layout_builder.py
├─ model_config.py
└─ result_builder.py
```

Responsibilities:

- normalize WAsP/WRG inputs;
- load the wind resource and optional TI rasters;
- build layout arrays from live map points or CSV inputs;
- filter turbines outside the resource extent;
- configure PyWake model components and compatibility fallbacks;
- build final per-model summaries, global losses, per-turbine tables and payload dictionaries.

### Lower-level packages

```text
ag_core/resources/    # WAsP/WRG/TI resource helpers
ag_core/layout/       # Coordinate and layout IO helpers
ag_core/turbines/     # Turbine curves, factories and hub-height logic
ag_core/physics/      # Wake, turbulence, blockage, rotor-average helpers
ag_core/simulation/   # PyWake execution helpers
ag_core/results/      # AEP arrays, summary and table helpers
ag_core/qgis_io/      # QGIS layer and export helpers
```

These packages should remain as independent as possible from Qt widgets.

---

## Data boundaries

### UI to Energy config

```text
QGIS widgets / selected layers
  ↓
EnergyRunConfig
```

The config object should contain normalized paths, selected layer IDs, model choices and options, not raw UI-control logic.

### Energy config to calculation

```text
EnergyRunConfig
  ↓
compute_aep_from_ui(...)
```

The public call signature is kept stable for the experimental release. The internal implementation may delegate to smaller helpers, but external callers should not need to change.

### Calculation to results

```text
PyWake outputs / arrays / diagnostics
  ↓
result_builder.py
  ↓
result payload dictionary
  ↓
QGIS layers, result dialog, CSV/HTML export
```

The result payload keeps stable keys used by the existing UI and exporters.

---

## Release boundary

Safe before publication:

- documentation;
- UI help text;
- validation wording;
- metadata/changelog;
- non-numerical report wording;
- developer diagnostics that do not affect data flow.

Avoid immediately before publication:

- PyWake simulation ordering;
- wake/turbulence/blockage fallback logic;
- AEP aggregation formulas;
- turbine-type mapping;
- resource interpolation/loading behaviour;
- output-key changes consumed by result dialogs or exporters.

---

## Regression checks

Every Energy refactor should be checked with at least:

1. WAsP/GridSite case.
2. WRG case without TI raster.
3. WRG case with TI raster.
4. CSV layout case.
5. Interactive-map layout case.
6. One turbulence-enabled model.
7. One incompatible blockage setting to verify warning/fallback.
8. CSV export and result-layer update.
9. Result dialog opening.
10. Total AEP and per-turbine AEP comparison against the previous accepted build.

---

## Future cleanup ideas

- Move the remaining simulation sequencing from `aep_compute.py` into a dedicated service once regression fixtures exist.
- Add small public test fixtures if licensing allows: minimal layout, turbine curve and resource sample.
- Add unit tests for `resource_loader`, `layout_builder`, `model_config` and `result_builder` outside QGIS.
- Move report generation into a dedicated report service.
- Add a stable JSON metadata block to exported reports so testers can compare runs more easily.
