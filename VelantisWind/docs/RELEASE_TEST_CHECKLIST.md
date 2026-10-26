# Release test checklist — Velantis Wind 0.1.17

Use this checklist before publishing the ZIP to GitHub or the QGIS plugin portal.

## 1. Install from ZIP

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the release ZIP.
4. Enable **Velantis Wind**.
5. Open the Hub from the toolbar/menu.

## 2. Language switching

Test the Hub in this order: Spanish → English → French → German → Spanish.

Confirm that these areas update without mixed-language leftovers:

- Module cards.
- Project summary.
- Support button.
- Layout-optimization panel.
- Energy, Noise and Shadow Flicker entry labels.

## 3. Module smoke tests

- Open Energy/AEP and return to the Hub.
- Open Noise and return to the Hub.
- Open Shadow Flicker and return to the Hub.
- Change language again after visiting each module.

## 4. Energy dependency

Energy/AEP requires PyWake in the QGIS Python environment. On Windows/OSGeo4W:

```bash
python -m pip install py_wake==2.6.18 "h5netcdf>=1.8"
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Noise and Shadow Flicker can be smoke-tested without PyWake.

Since version 1.8, `h5netcdf` no longer depends on `h5py`, so this command does not install `h5py` through `h5netcdf`. For `GaussianOverlapAvgModel` on Windows, see the untested `python3-h5py` option in the [OSGeo4W guide](INSTALL_OSGEO4W_PYWAKE.md#h5py-in-qgis-from-osgeo4w).

### Mixed-turbine wake raster regression

1. Define two turbine models with visibly different diameter, hub height and CT curves.
2. Load coordinates for both models and create a wake raster.
3. Confirm the task starts without a `PowerCtFunctionList`/`type` error.
4. Confirm the JSON reports both model labels and the expected turbine counts.
5. Repeat with a homogeneous single-model layout (the raster calculates in float64 in both cases).

### Multi-height WRG terrain regression

1. Load two WRG files from the same resource grid at different heights, for example 80 m and 100 m.
2. Confirm climate variables retain an `h` dimension with two values while `Elevation` remains exactly `(x, y)`.
3. Run a mixed-turbine wake raster using two hub heights and confirm no `IndexError ... axis 0 with size 2` occurs.
4. Repeat with two deliberately inconsistent terrain surfaces and confirm Velantis stops before PyWake with a clear validation error.
5. Repeat with a single WRG height to confirm the legacy path remains unchanged.

## 5. Packaging checks

- The ZIP contains one top-level folder named `VelantisWind`.
- `metadata.txt` version is `0.1.17`.
- No `__pycache__`, `.pyc`, local build folders or temporary files are included.

## Hub UI smoke test

Before testing this ZIP in QGIS, remove any previous VelantisWind folder from the QGIS profile or restart QGIS after reinstalling, so an older hub dialog is not kept alive in memory.

Expected hub home screen:
1. Title and subtitle centered.
2. Language selector in a rounded group.
3. Three module cards only: Energy/AEP, Noise, Shadow Flicker.
4. Velantis logo centered below the cards.
5. Layout optimization strip below the logo, with a prominent gradient CTA button and commercial text about layout + wake-steering co-optimization.
6. Project summary below the optimization strip.
7. Support button pinned at the lower-right footer.

Switch ES -> EN -> FR -> DE -> ES. The layout must remain visually identical; only labels should change.


## 6. Noise report smoke test

Run one Noise calculation with the ISO-aligned engine and export the technical report.

Check that:

- Receiver coverage is explicit: compliance is only claimed for receivers inside the calculation radius.
- The report does not show `Spectrum source: -` when an OEM/CSV spectrum was used.
- Absolute/imported spectra do not display an empty `S_b^ref` column.
- Raster resolution is described as map visualization only, not as the point-receiver calculation resolution.
- Unusual meteorological inputs show a review warning.
- The physics section appears as a technical appendix rather than the main executive body.


## 7. Spacing envelope smoke test (Interactive Map)

With two turbine models defined and a WRG loaded:

1. Before loading coordinates, open **Spacing envelopes…**. Confirm there is no circular/type selector and both defined models appear in **Wind turbine model** as *no layer*. Set model A to 7 D × 4 D and press **Apply new configuration**. Set model B to 8 D × 5 D and apply it. Switching back and forth must preserve the independent values.
2. Import a valid CSV for model A. Without reopening the spacing dialog, a memory layer `Envolventes de separación · <model A>` appears automatically with one semi-transparent 7 D × 4 D ellipse per turbine.
3. Import a second CSV for model B, using a different rotor diameter. A second 8 D × 5 D envelope layer appears automatically; the first one remains and conflicts are evaluated across both models.
4. Enter Interactive Map mode and switch the active edit layer between model A and model B. The spacing model selector follows the selected turbine layer and the point layer stays above its ellipse layer.
5. Add a turbine well inside another turbine's ellipse: both envelopes turn red immediately. With **Block insertion on conflict**, the point is not committed and QGIS shows the blocked-insertion warning. With **Visualization only**, it is committed and only the colors change.
6. Clear the WRG path and refresh: automatic orientation falls back to the angle stored for each model with the notice *“Could not automatically determine the most energetic sector”*. The plugin must not error.
7. Change a dimension without pressing **Apply new configuration** and confirm that the model layer is not rebuilt. Then press Apply and confirm that all ellipses for that model update. Press **Define ellipse on screen** afterwards and verify that it changes only the selected turbine. Click a turbine, drag to set the major axis, and drag again to set the minor axis. Ctrl snaps to 5°/sector centers, Shift snaps to 0.5 D, and Esc/right-click steps back. Only that turbine retains the override.
8. Press **Reset** while model A is selected: only model A overrides are cleared and its turbines return to the model template.
9. Close or leave Interactive Map: the generated envelope layers remain in the project and no Python error appears. Disable **Enable spacing envelopes** explicitly: all managed envelope layers are removed.
10. Switch ES → EN → FR → DE. Check the spacing dialog, Interactive Map static labels, dynamic layer labels, TI status, warnings and tooltips. No mixed Spanish strings should remain.
11. Save and reopen the QGIS project. Model association, rotor diameter, 7 D × 4 D / 8 D × 5 D values, orientation mode, fallback angle and per-turbine overrides must persist.
12. Press **Export envelopes…** and save a GeoPackage. It opens in QGIS with one table per turbine model and the spacing/model attributes.
13. Load an old project that stored `shape=circular`. It must open without error and regenerate elliptical envelopes using its saved longitudinal and transversal values.
14. Switch **Enable spacing envelopes** on again. With one model, choose in its row a layer that overlaps another layout alternative used before in that row (or imported from a CSV). Only the chosen layer gets envelopes, without conflicts against the alternative, and **Block insertion on conflict** does not block against it. Choose the alternative in the row instead: the envelopes of the first layer disappear. Switch the envelopes off and choose the first layer again: no envelope is created and the checkbox stays off.
15. Switch the envelopes on again and import a turbine layout from Noise (or Shadow), in a CRS projected in metres, next to a layer of the Energy rows: it gets an envelope layer of its own, checked only against itself, and the Energy envelopes do not change.


## 8. Turbine catalogue and energy symbology

1. Open the turbine selector and confirm that the catalogue contains 42 candidates: 4 public/reference, 8 `spec_based_approximation` and 30 generic `approximate` entries.
2. Confirm that quality, source and caveat text are visible before loading a curve.
3. Edit a packaged curve and confirm that its provenance becomes `user_edited`.
4. Run an AEP calculation with at least two turbine models. Each model layer must receive its own graduated AEP renderer, plus populated `model_perf_pct` and `model_rank` fields.
5. Confirm that `resources/turbines/curve_audit.csv` contains 42 PASS rows and no missing curve file.

## 9. Wake raster QgsTask smoke test

1. Use a saved project with a projected metric CRS, a valid WRG/WAsP resource and at least one turbine layer.
2. Create a wake raster for the most energetic sector. Confirm the Energy button shows progress and QGIS lists **Velantis Wind · Ráster de estelas** in the task manager while the UI remains responsive.
3. Confirm the completed run appears under **VelantisWind · Estelas** with five layers when elevation is available: `WS`, `WS_eff`, deficit in m/s, deficit in %, and elevation. Only `WS_eff` and the elevation hillshade should be visible by default.
4. With a spatially varying WRG, confirm the free-flow `WS` raster is uniform (the WRG keeps its local climate, no speed-up), its JSON reports `free_flow_spatial_method=none`, `distance_method=StraightDistance` and `turning_available=false`. Compare `WS` and `WS_eff` using their shared colour range.
5. Confirm one common `.json` file exists beside the wake-raster package and includes the plugin version from `metadata.txt`, CRS, resource input, exact turbine coordinates/inclusion status, direction, speed, wake model, superposition, turbine counts, grid dimensions and statistics for every raster.
6. Start a second calculation while one is active. Confirm the plugin refuses to launch a duplicate task and explains how to cancel the existing one.
7. Start a sufficiently large calculation and cancel it from the QGIS task manager. Confirm the button is restored, no layer is added and no completed GeoTIFF/JSON pair is left from the cancelled result.
8. Change the project CRS to EPSG:4326 and retry. Confirm the plugin blocks the metre-based raster calculation with a projected-CRS warning.
9. Restore a metric project CRS but leave one selected turbine layer in another CRS. Confirm the plugin blocks the task and names the mismatched layer.
10. Repeat with a manual wind direction and with mixed turbine models. Select several coordinate layers belonging to only two physical turbine models (including more than two layer entries). Confirm the plugin compacts them to dense PyWake types `0` and `1`, the correct diameter/height/CT is assigned to every turbine, and no layer index is passed as a turbine type. The JSON must report the number of input model entries, physical turbine types, type range and dispatcher class.
11. Repeat with an input turbine object that is already a two-type `WindTurbines`. Confirm Velantis extracts the selected physical branch before building the park and does not create a nested `PowerCtFunctionList('type', ...)`.

## 10. Resource parameters and TurbOPark

1. Choose a 12-sector WRG: under it, the metadata line reports `sectores=12` and the folded **Resource parameters** button reads `(nearest, 84 directions, …)` with the band of the defined models and its step. Unfold it: interpolation and `Speedup: None` on the left, directions (12, 24, …, 360) and wind speeds with their step on the right; each one shows its help. Clear the WRG and choose only a WAsP folder: the group disappears.
2. Run one AEP with other values than the initial ones and confirm the result notes and the log line `[RECURSO]` report them (directions, sectors × subdivisions, interpolation, Speedup `none`, the wind speeds of the turbines' band with the chosen step and 8766 h/year). Close and open the dialog: the initial values are back.
3. With a WAsP grid folder (GRD), confirm the notes report the directions and wind speeds of its Site (360 directions, 3–25 m/s) and 8766 h/year.
4. Select the TurbOPark wake model: the rotor-average selector stays active and offers `GaussianOverlapAvgModel`; the advanced panel shows `A`, `ctlim`, `cTI[0]`, `cTI[1]` and `ceps`. Select another wake model and confirm `GaussianOverlapAvgModel` is no longer offered.
