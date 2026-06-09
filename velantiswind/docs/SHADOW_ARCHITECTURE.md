# Shadow Flicker module architecture

The Shadow Flicker module follows the same public structure used by Energy and Noise: UI, dialog-state reader, validation, controller, runner, calculation workflows, QGIS outputs and result reporting.

The current experimental release prioritises stability. The previous multiprocessing receptor path is not active; point-receptor calculations are sequential, while raster generation is launched through a QGIS task-style workflow where supported.

---

## Main flow

```text
shadow_page.py
  ↓
shadow_core.dialog_state
  ↓
shadow_core.validation
  ↓
shadow_core.dialog_controller
  ↓
shadow_core.runner
  ↓
shadow_core.calculation.point_runner
  ↓
shadow_core.calculation.executor
  ↓
ShadowFlickerCalculator / raster task / QGIS outputs
```

---

## Package layout

```text
shadow_core/
├─ domain.py                  # pure ShadowRunConfig dataclass
├─ dialog_state.py            # reads Qt/QGIS widgets into ShadowRunConfig
├─ validation.py              # pre-flight validation
├─ ui_feedback.py             # status text, buttons and validation messages
├─ runner.py                  # runner façade used by the UI/controller
├─ dialog_controller.py       # small validated UI workflow entry point
├─ debug.py                   # VELANTISWIND_DEBUG-gated diagnostics
├─ shadow_calculator.py       # core point-receptor shadow/flicker physics
├─ solar_geometry.py          # solar position and vectorized helpers
├─ timezone_utils.py          # IANA/fixed-offset timezone support
├─ calculation/
│  ├─ point_runner.py         # point-receptor orchestration
│  └─ executor.py             # sequential receptor execution strategy
├─ terrain/
│  └─ dem.py                  # DEM/DSM sampling helpers
├─ turbines/
│  └─ collector.py            # turbine layer → calculation dictionaries
├─ receptors/
│  └─ collector.py            # receiver layer → calculation dictionaries
├─ raster/
│  ├─ task.py                 # raster task calculation
│  └─ map.py                  # raster launch, callbacks and symbology
├─ results/
│  └─ summary.py              # summary dialog, CSV export and report tables
└─ qgis_io/
   └─ layers.py               # receptor result layer creation/styling
```

---

## Responsibility split

### `shadow_page.py`

Owns widgets, selectors, help text and the visible Shadow Flicker page. It now delegates calculation startup to `shadow_core.dialog_controller` and keeps only thin compatibility wrappers for QGIS output callbacks.

### `shadow_core/domain.py`

Defines `ShadowRunConfig`. It is intentionally free from Qt widget access.

### `shadow_core/dialog_state.py`

Reads the current Shadow page widgets and builds `ShadowRunConfig`. This keeps UI-state extraction separate from validation and calculation.

### `shadow_core/validation.py`

Checks selected layers, DEM/DSM validity, numeric ranges, time settings and raster parameters.

### `shadow_core/dialog_controller.py`

Small entry point: prevent duplicate runs, read state, validate, update UI state, and call the runner.

### `shadow_core/ui_feedback.py`

Centralises user-facing validation messages, button state and status updates.

### `shadow_core/runner.py`

Stable runner façade used by the controller.

### `calculation/point_runner.py`

Main point-receptor orchestration layer. It keeps compatibility with the current UI while delegating work to collectors, executor, calculator and output helpers.

### `calculation/executor.py`

Sequential receptor execution strategy. This is intentionally conservative for the experimental release.

### `shadow_calculator.py`

Core geometric/solar calculation for receptor-level flicker.

### `solar_geometry.py`

Solar-position calculations and vectorized yearly solar arrays.

### `timezone_utils.py`

Time-zone handling through IANA or fixed-offset modes.

### `terrain/dem.py`

DEM/DSM sampling helpers used for turbine, receptor and raster-cell elevations.

### `raster/`

Raster-map generation, task execution, filtered raster creation and symbology.

### `results/summary.py`

Summary dialog, receptor table, monthly/hourly matrices and CSV/export helpers.

---

## DEM/DSM handling

DEM/DSM is used to adjust absolute elevations of turbines, receptors and raster cells. This affects the vertical angular geometry of shadow/flicker detection.

The experimental release version does not yet implement complete intermediate terrain obstruction checks along every turbine-receptor path. That limitation must remain visible in user-facing documentation.

---

## Execution policy

Current experimental release policy:

```text
Receptor calculation: sequential for stability
Raster calculation: task-style execution where supported
```

This avoids Windows/QGIS multiprocessing edge cases and makes testing more predictable.

---

## Debug policy

Shadow diagnostics are quiet by default. To enable detailed geometry, DEM and raster logs, start QGIS with:

```bash
set VELANTISWIND_DEBUG=1
```

On Linux/macOS:

```bash
export VELANTISWIND_DEBUG=1
```

---

## Current refactor boundary

The Shadow module is acceptable for experimental release publication if smoke tests pass. Do not reintroduce multiprocessing or change solar geometry immediately before release.

Recommended boundary for publication:

```text
Safe to change before release:
- documentation
- UI help text
- validation messages
- report wording
- debug/logging behaviour

Avoid changing before release:
- solar-position formulas
- angular screening tolerance
- raster algorithm
- time-zone conversion logic
- result-layer field schema
```

---

## Recommended tests

1. Point receptors without DEM/DSM.
2. Point receptors with DEM/DSM.
3. IANA time-zone mode.
4. Fixed-offset time-zone mode.
5. Raster output at coarse resolution.
6. Smaller time-step sensitivity check.
7. CSV/monthly matrix export.
8. Large layout performance sanity check.
