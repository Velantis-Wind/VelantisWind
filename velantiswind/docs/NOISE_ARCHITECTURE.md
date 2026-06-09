# Noise module architecture

The Noise module now follows the same public architecture style used by the Energy module: the Qt page owns widgets, `noise_core` owns workflow/configuration, and the acoustic engines own numerical calculation.

```text
noise_page.py / noise_results_dialog.py
  ↓
noise_core.dialog_state        # widgets/layers → NoiseRunConfig
noise_core.validation          # pre-flight checks
noise_core.dialog_controller   # small workflow coordinator
noise_core.task_controller     # QgsTask / raster task / fallback routing
noise_core.runner              # stable runner façade
  ↓
noise_core.noise_compute       # compatibility façade / high-level orchestrator
  ↓
collectors / engines / raster / results / qgis_io
```

The design goal is to keep QGIS layer/widget access on the main thread, pass only safe primitive snapshots to background workers, and apply results back to QGIS through controlled output helpers.

---

## Main calculation flow

```text
NoisePage
  ↓
dialog_state.build_config_from_dialog
  ↓
validation.validate_run_config
  ↓
dialog_controller workflow entry
  ↓
if task-safe:
    task_controller.run_full_noise_task_from_dialog
else:
    NoiseRunner.run
  ↓
noise_compute façade / task pure engine
  ↓
collect sources + receivers
  ↓
evaluate receiver noise
  ↓
create QGIS layers / raster / isophones
  ↓
result_status.append_result_status
  ↓
NoiseResultsDialog
```

Some internal compatibility function names are preserved for release stability. They should not appear as product/version wording in the public UI.

---

## Package layout

```text
noise_core/
├─ domain.py                  # NoiseRunConfig and NoiseRunResult
├─ validation.py              # pre-flight validation
├─ runner.py                  # stable runner façade
├─ dialog_state.py            # read NoisePage widgets/layers into NoiseRunConfig
├─ dialog_controller.py       # small workflow coordinator
├─ ui_feedback.py             # progress bars, message bar and status-box helpers
├─ task_controller.py         # full QgsTask routing, raster task and fallback raster
├─ result_status.py           # completed-run status summary builder
├─ noise_compute.py           # compatibility façade / high-level orchestrator
├─ noise_engine_fast.py       # simplified fast propagation
├─ noise_engine_iso.py        # ISO-aligned octave-band propagation
├─ noise_common.py            # dataclasses, constants and debug logging
├─ noise_spectrum.py          # spectrum library helpers
├─ acoustics/
│  └─ curves.py               # acoustic curve loading/interpolation
├─ sources/
│  └─ collector.py            # turbine layers → NoiseSource objects
├─ receivers/
│  └─ collector.py            # receptor layers → NoiseReceiver objects
├─ propagation/
│  └─ ground.py               # fast ground/effective-G helpers
├─ raster/
│  ├─ grid.py                 # noise-map raster generation
│  └─ task.py                 # raster task helpers
├─ snapshot/
│  └─ builder.py              # primitive snapshots for background tasks
├─ tasks/
│  ├─ noise_task.py           # full background calculation task
│  └─ pure_engine.py          # QGIS-free worker-side evaluator
├─ results/
│  ├─ evaluator.py            # receiver evaluation and dominant links
│  ├─ payload.py              # final result payload
│  └─ summary.py              # result statistics/report helpers
└─ qgis_io/
   ├─ apply_results.py        # apply task result back to QGIS
   ├─ common.py               # QGIS/raster helper functions
   └─ layers.py               # result/source/link/isophone layer builders
```

---

## Responsibility split

### `noise_page.py`

Owns visible widgets, selectors, help buttons, saved UI preferences and project-layer refresh logic. It should not contain heavy acoustic calculation logic.

### `noise_core/dialog_state.py`

Reads the current UI state and QGIS layer selections, normalises receiver modes, DEM/DSM, land-use, acoustic source settings, raster options and atmospheric parameters, then returns a `NoiseRunConfig`.

### `noise_core/validation.py`

Performs pre-flight validation before a calculation starts. It should catch missing layers, invalid receptor settings, invalid raster options and unsafe combinations early enough to give the user a clear message.

### `noise_core/dialog_controller.py`

Owns only the high-level workflow:

- build config;
- validate config;
- decide task vs synchronous route;
- call the runner or task controller;
- open the results dialog;
- restore UI state after success/error/cancel.

It intentionally does not own detailed widget parsing, progress-dialog internals or task implementation.

### `noise_core/ui_feedback.py`

Centralises:

- inline progress bar updates;
- floating task progress dialogs;
- QGIS message-bar notifications;
- status-box append helpers;
- calculate-button enable/disable helpers.

### `noise_core/task_controller.py`

Owns background execution boundaries:

- full receiver/raster `QgsTask` for task-safe configurations;
- asynchronous raster generation after synchronous receiver results;
- raster fallback when a synchronous grid result cannot be materialised as a visible layer;
- task cancellation hooks and finished callbacks.

### `noise_core/result_status.py`

Builds the human-readable run summary shown in the Noise page status box. This keeps presentation wording away from the calculation engine.

### `noise_core/noise_compute.py`

Stable compatibility façade and high-level orchestrator. It coordinates source/receiver collection, result-layer creation and optional raster/isophone generation. For the experimental release, keep this façade stable.

### Acoustic engines

```text
noise_engine_fast.py
noise_engine_iso.py
```

Own the propagation equations. They should not import UI widgets and should remain conservative before public releases.

### Collectors

```text
sources/collector.py
receivers/collector.py
```

Translate QGIS layers into calculation objects and sample DEM/DSM where needed.

### QGIS output helpers

```text
qgis_io/layers.py
qgis_io/apply_results.py
qgis_io/common.py
```

Own result-layer creation, layer replacement, field schemas and task-result application on the main QGIS thread.

---

## Background execution policy

Use a background worker only when the calculation can be represented without live QGIS layer objects.

Task-friendly:

- fast engine with or without DEM/DSM;
- ISO-aligned engine with or without DEM/DSM when the terrain can be sampled from a GDAL-readable path;
- raster creation from primitive source/receptor snapshots.

Synchronous fallback:

- land-use based `G_eff`, because it still requires polygon intersections with a live vector layer;
- any configuration that cannot be safely serialized;
- unexpected task-preparation failures.

The UI should explain the fallback reason to the user rather than failing silently.

---

## Debug policy

Noise console diagnostics are silent by default for public use. To enable diagnostic logs during development or diagnostic debugging:

```bash
VELANTISWIND_DEBUG=1
```

On Windows, set it before launching QGIS from the same shell:

```bat
set VELANTISWIND_DEBUG=1
qgis
```

This matches the Energy module policy and avoids noisy QGIS Python consoles for normal users.

---

## Public wording policy

Public labels, help text and documentation should use neutral module wording:

```text
Noise
Noise module
Noise calculation
ISO-aligned engine
Fast engine
```

Avoid user-facing development labels, implementation notes or temporary maintenance wording.

---

## Current release boundary

The Noise module is ready for experimental publication after the controller split and documentation refresh. Avoid large rewrites of `noise_compute.py`, `noise_engine_iso.py`, raster generation or task snapshot schemas immediately before release.

Safe to change before release:

- documentation;
- UI help text;
- validation messages;
- progress labels;
- report/status wording.

Avoid changing before release:

- propagation formulas;
- DEM/DSM profile logic;
- land-use intersection logic;
- task snapshot schema;
- result-layer field schema.

---

## Recommended tests

1. Fast engine, no DEM/DSM.
2. Fast engine, DEM/DSM.
3. ISO engine, no DEM/DSM.
4. ISO engine, DEM/DSM.
5. Land-use `G_eff` layer with numeric `g_factor`.
6. Raster generation.
7. Isophone generation.
8. Two source groups / turbine models.
9. Full background-task run.
10. Task cancellation.
11. Re-run after cancellation to confirm the UI state resets.
12. Confirm public UI/help text does not show development-version labels.
