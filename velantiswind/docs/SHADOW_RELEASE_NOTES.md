# Shadow Flicker module — experimental release checklist

This document records the experimental release-readiness state of the Shadow Flicker module.

## Current architecture

The module is split into clear responsibilities:

```text
shadow_page.py                      # UI surface and thin QGIS callback wrappers
shadow_core/dialog_state.py          # reads widgets/capas into ShadowRunConfig
shadow_core/domain.py                # pure ShadowRunConfig dataclass
shadow_core/validation.py            # input validation
shadow_core/ui_feedback.py           # validation/status/button feedback
shadow_core/dialog_controller.py     # validated entry point from the UI
shadow_core/runner.py                # module runner façade
shadow_core/calculation/point_runner.py
shadow_core/calculation/executor.py
shadow_core/terrain/dem.py
shadow_core/turbines/collector.py
shadow_core/receptors/collector.py
shadow_core/results/summary.py
shadow_core/qgis_io/layers.py
shadow_core/raster/task.py
shadow_core/raster/map.py
shadow_core/solar_geometry.py
shadow_core/shadow_calculator.py
shadow_core/timezone_utils.py
```

## Physics status

The refactor is architecture-only. It does not intentionally change:

- solar geometry;
- turbine/receptor geometry;
- DEM-aware elevation handling;
- sequential receptor calculation;
- raster task calculation;
- monthly / hourly result aggregation;
- result-layer field schema.

## Debug policy

Detailed Shadow diagnostics are gated behind:

```bash
VELANTISWIND_DEBUG=1
```

Normal public use should not fill the QGIS Python console with geometry, DEM or raster progress logs.

## Known limitations to communicate to testers

- The module is intended for preliminary GIS-based shadow/flicker screening.
- Building heights, vegetation and detailed local obstructions are not fully modelled unless represented in the selected DEM/DSM.
- Time-zone handling is explicit, but results should be checked carefully near daylight-saving transitions and for projects close to time-zone borders.
- DEM/DSM no-data samples fall back to `0.0 m`, matching the current flat-terrain fallback policy.
- Raster maps may take time on large extents or fine resolutions, although the raster path runs as a task-style workflow where supported.

## Smoke tests before sharing

1. Run a small case without DEM/DSM.
2. Run the same case with DEM/DSM.
3. Run with raster enabled and confirm the raster task completes.
4. Run the sequential receptor workflow and confirm results are created.
5. Cancel a long raster task and confirm QGIS remains stable.
6. Export / inspect the receptor result layer and monthly/hourly summaries.

## Experimental release recommendation

The Shadow Flicker module is suitable for experimental release testing once the tests above pass in a clean QGIS profile. It should still be labelled preliminary screening, not a regulatory-grade certified shadow/flicker package.
