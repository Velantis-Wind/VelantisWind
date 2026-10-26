# Wake raster architecture

## Purpose

The wake-raster workflow creates a georeferenced raster package for one wind direction without blocking the QGIS user interface. It is a preliminary engineering visualization and layout-comparison output, not a certified bankable wake assessment.

## Execution boundary

```text
Energy dialog (main thread)
  ├─ snapshots turbine coordinates, the wake configuration of the AEP (the same group) and its resource inputs
  ├─ validates a projected metric project CRS and turbine-layer CRS matching
  └─ captures CRS WKT/authid and output directory
        ↓
WakeRasterTask (worker thread)
  ├─ holds the PyWake lock shared with the AEP (wake_core/raster.py)
  ├─ loads the WAsP/WRG resource with the functions of the AEP, with its TI
  ├─ selects the dominant sector with a NumPy resource-power proxy when requested
  ├─ builds the wind farm model of the configuration with the factory and checks its classes
  ├─ runs the single-condition simulation and flow_map (the flow map with blockage, as PyWake gives it)
  ├─ writes compressed Float32 GeoTIFFs for WS, WS_eff, deficits and terrain
  └─ writes one JSON traceability sidecar
        ↓
Controller callback (main thread)
  ├─ loads the QgsRasterLayer package
  ├─ applies comparable speed scales and deficit/terrain symbology
  ├─ shows WS_eff over a semi-transparent terrain hillshade by default
  ├─ leaves WS and both deficit rasters available but initially hidden
  ├─ inserts a run subgroup into VelantisWind · Estelas
  └─ reports statistics and warnings
```

## Thread-safety rules

- Never pass `QgsMapLayer`, `QgsProject`, providers, widgets or layer-tree nodes to the worker.
- Coordinates must be copied to primitive `(x, y)` tuples before starting the task.
- The CRS is passed as plain WKT/authid text.
- GDAL file writing is allowed in the worker; `QgsRasterLayer` creation is main-thread only.
- Cancellation is checked between major PyWake/GDAL stages and between flow-map tiles. PyWake calls themselves are not interruptible mid-call.

## Outputs

Each successful run creates a common timestamped package containing:

- local free-flow speed `WS` [m/s];
- effective speed `WS_eff` [m/s];
- wake deficit `WS - WS_eff` [m/s];
- relative wake deficit [%];
- terrain elevation [m], when the resource contains it;
- one common `.json` traceability sidecar.

For WRG inputs, the Site is loaded with the functions of the AEP: the local Weibull climate of each position (Speedup `none`), so the free-flow speed of the map is uniform, the direction count and directional interpolation of the dialog's resource parameters, the same straight distance (`ag_core.wrg_site.TERRAIN_FOLLOWING`) and the TI of the AEP (the fixed TI or the TI rasters). The own TI of a GRD resource keeps the previous treatment (a uniform 0.10 when the dataset has no `TI`, also over its `ti15ms`), and the JSON says which case it was. The air density is read from the dialog's controls and decided as in the AEP; if it cannot be established, the raster stops. The task configuration carries `aep_comparison`, the categories of inputs that differ from the last AEP of the project (`energy_core/aep_inputs.py`), written to the JSON. A standard WRG cannot reproduce wind turning or the separate orographic, roughness and obstacle factors present in complete WAsP GRD exports.

The JSON records the screening setup for audit and reconstruction: plugin version, UTC timestamp, CRS, resource paths, the wake configuration (selected by the user, effective, expected classes and executed, read from the built objects, with the accepted adaptations), the product (the configuration of the dialog when the raster was created, or the explicit scenario recalculated without blockage, which also says so in the layer names), how its inputs compare with the last AEP of the project (`aep_comparison`), the TI, the convergence of the iterative loops, the air density, the numerical precision, the turbines used, the grid and its tiles, per-stage timings, warnings and per-raster statistics. Without the free flow of PyWake, only `WS_eff` is written, with a warning; no uniform speed is put in its place.

Mixed layouts retain one dense turbine-type index per coordinate. QGIS layer entries are first compacted into physical turbine definitions; if an input points to an already-combined turbine object, the correct internal branch is extracted. Each type keeps one flat Power/CT curve, and the turbine set is built with PyWake's `WindTurbines.from_WindTurbine_lst`, whose native `PowerCtFunctionList('type', ...)` selects the curve through the documented public `type` argument without nesting `type` selectors. Diameter, hub height and model-specific curves remain attached to each type, and the exact CT vector is checked before the wake model starts.

## Compatibility

UI code uses `wake_core.controller`; non-UI code calls `wake_core.raster.compute_wake_raster_config` with a validated `WakeConfig`. The previous raster (`wake_core.engine.compute_wake_raster`, its site cache and the `graficar.py` façade) was removed: it did not use the configuration of the AEP.


## Performance and mixed-type path

PyWake deficit models are already highly vectorized. The critical optimization is therefore to avoid requesting unused atmospheric cases. The task does not run the default full `wd × ws` matrix before creating one map. It derives the automatic direction from the resource, calls the wind-farm model with one `wd` and one `ws`, and then calculates the flow map for that same case.

Regular numeric WRG files are parsed in bulk with `numpy.fromstring`; unusual files retain the conservative Python parser. Terrain elevation is resampled with vectorized bilinear NumPy indexing. The output grid uses an adaptive interaction budget based on turbine count × raster cells. The cell limit is a budget of 10 million turbine-cell interactions divided by the number of turbines, kept between 50,000 and 200,000 cells (at most 120,000 for mixed parks), so larger farms are automatically coarsened to keep the PyWake point-interaction workload bounded. `VELANTISWIND_WAKE_MAX_CELLS` overrides the limit within 25,000–2,000,000 cells. The flow map is computed in tiles of at most 4,000 cell-turbine pairs and then joined: `TerrainFollowingDistance` builds a 1000-point terrain profile for every pair, which PyWake's `memory_GB` estimate does not count, and each cell is computed independently, so the joined map is identical to a single call. The raster always calculates in float64, as the AEP: in PyWake's single precision (`Numpy32`) the projected coordinates of the turbines would be rounded (to 0.5 m at northings above 4,194,304 m, a problem already fixed in the AEP), so the turbines would not stand where they stand in the AEP. The raster and the AEP hold the same lock (`ag_core.simulation.pywake_lock.PYWAKE_LOCK`), so they never calculate at the same time. The convergence of the simulation is always recorded; that of the flow map only with `WeightedSum`, the one iterative loop that runs inside it (the recorder's trace function slows every Python call down). With `WeightedSum`, the tiled map may differ from one calculated at once, because PyWake computes its weights with a global maximum of each calculation; the raster warns about it. The audit JSON records the effective grid, the precision (`float64`) and per-stage timings.


### Dense physical turbine types

QGIS layers are spatial containers, not turbine definitions. Before simulation, selected entries are canonicalized by their source model row (or repeated WindTurbines identity), coordinates are merged, and a dense type vector `0..N-1` is generated. Mixed Power/CT curves are selected by PyWake's native `PowerCtFunctionList('type', ...)` over one flat curve per type, which avoids nested `type` selectors; the exact CT vector is validated before starting the wake model.

### Multi-height WRG terrain invariant

When several WRG files are combined by hub height, climate variables are concatenated along `h`, while `Elevation` remains a single two-dimensional `Elevation(x, y)` surface. Expanding elevation to `Elevation(h, x, y)` is invalid for PyWake terrain-following distances and can make a spatial grid index be interpreted as a height index. The loader validates identical terrain surfaces across heights before creating `XRSite`.
