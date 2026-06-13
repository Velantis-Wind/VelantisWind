# Velantis Wind — Troubleshooting

This document lists common issues during experimental release testing and suggested checks.

---

## 1. Plugin does not appear in QGIS

Check:

- The plugin folder is named `VelantisWind` or matches the single plugin folder bundled in the ZIP.
- The folder contains `metadata.txt` and `__init__.py` directly inside it.
- The folder is located inside the active QGIS profile, for example:

```text
QGIS3/profiles/default/python/plugins/velantiswind/
```

Try:

1. Restart QGIS.
2. Open **Plugins → Manage and Install Plugins**.
3. Search for **Velantis Wind**.
4. Enable the plugin.

---

## 2. PyWake not found

Typical message:

```text
ModuleNotFoundError: No module named 'py_wake'
```

Cause:

PyWake is not installed in the same Python environment used by QGIS.

Fix using OSGeo4W Shell:

```bash
python -m pip install --upgrade pip
python -m pip install py_wake
python -c "import py_wake; print('PyWake OK')"
```

Important:

- Do not install PyWake only in Anaconda unless QGIS is using that same Python.
- The Energy module needs PyWake; the Noise and Shadow modules can usually open without it.

See:

- [`INSTALL_OSGEO4W_PYWAKE.md`](INSTALL_OSGEO4W_PYWAKE.md)
- [`INSTALL_ENERGY_DEPENDENCIES.md`](INSTALL_ENERGY_DEPENDENCIES.md)

---

## 3. QGIS freezes during a calculation

Possible causes:

- A large raster calculation is running.
- DEM/DSM-aware calculations are expensive.
- A configuration has fallen back to a synchronous route.
- Very small raster resolution was selected over a large extent.

Try:

- Increase raster resolution.
- Reduce calculation radius.
- Test without raster first.
- Test without DEM/DSM first.
- Use fewer receptors for the first run.
- Check whether a QGIS task/progress dialog is active.

For Noise ISO + DEM/DSM:

- This is one of the heaviest workflows.
- Raster generation may take significantly longer than receiver-only calculation.

For Shadow Flicker:

- Use a coarser time step for first tests.
- Enable parallel calculation only after confirming the sequential run works.

---

## 4. No raster generated

Check:

- Raster output is enabled in the module settings.
- Output folder is writable.
- Raster resolution is not too small for the selected extent.
- Input layers have valid extents.
- CRS is projected and uses metric units where possible.
- The background task completed successfully.

Try:

1. Run without DEM/DSM.
2. Increase raster cell size.
3. Reduce maximum radius.
4. Use a small test area.
5. Check QGIS message bar for warnings.

Common causes:

- Output path not writable.
- Processing temporary layer source not materialized.
- DEM/DSM source cannot be read by GDAL.
- The task was cancelled before completion.

---

## 5. CRS mismatch or strange distances

Symptoms:

- Distances are extremely large or small.
- Results look unrealistic.
- Raster extent is very large.
- Noise levels or shadow hours look unreasonable.

Check:

- Project CRS.
- Turbine layer CRS.
- Receptor layer CRS.
- DEM/DSM CRS.

Recommended:

- Use a projected CRS with metre units.
- Reproject layers before running large calculations.
- Avoid running calculations directly in latitude/longitude CRS when distances are important.

---

## 6. DEM/DSM not sampled or ignored

Symptoms:

- Report says DEM/DSM is not active.
- Elevation effects are not visible.
- Terrain-related terms remain zero everywhere.

Check:

- The DEM/DSM layer is selected.
- The DEM/DSM overlaps the turbine and receptor area.
- The DEM/DSM CRS is compatible with the project or can be transformed.
- The DEM/DSM source is a real raster file or can be materialized.
- NoData values are not covering the area of interest.

For Noise:

- `Abar = 0` for a critical receiver can be valid if the line of sight is clear.
- Check attenuation statistics across all receivers, not only the critical receiver.

For Shadow Flicker:

- DEM/DSM currently adjusts absolute elevations.
- Full intermediate terrain obstruction is not yet implemented.

---

## 7. Missing noise spectrum

Symptoms:

- The report says a generic template was used.
- Source spectrum comes from `generic_modern`, `generic_large` or `generic_small`.

Explanation:

The Noise module can use octave-band spectrum files when available. If no manufacturer or user spectrum is found, it uses editable generic templates from:

```text
noise_core/spectrum_library/
```

This does not break the calculation, but it means the spectral shape is generic rather than manufacturer-specific.

Recommended for better tests:

- Provide manufacturer octave-band spectrum data where available.
- Keep one source layer/group per turbine model.
- Check the report section that lists the spectrum source.

---

## 8. Matplotlib or font errors

Symptoms:

- A chart cannot be drawn.
- Error mentions `matplotlib.font_manager` or font properties.

Try:

- Restart QGIS.
- Avoid unusual system fonts in labels.
- Use the default QGIS/Matplotlib font settings.
- Report the full traceback.

If the calculation itself completes, this is usually a plotting/reporting issue rather than a physics issue.

---

## 9. Energy calculation gives NaN or zero AEP

Check:

- Wind resource is valid.
- Turbine power curve is valid.
- Turbine coordinates fall inside the resource domain.
- Hub height is compatible with the resource.
- Wake model selected is compatible with the chosen options.
- Turbine layer has valid point geometries.

Try:

- Run a very small layout first.
- Use default turbine settings first.
- Disable optional turbulence/blockage/rotor-average options.
- Check the QGIS Python console for warnings.

---

## 10. Noise levels look too high or too low

Check:

- Source LwA value.
- Acoustic curve / scenario selected.
- Receptor height.
- Maximum radius.
- Ground factor `G`.
- DEM/DSM setting.
- Spectrum source.

Important:

- The ISO-aligned engine is a screening workflow, not certified regulatory software.
- Atmospheric absorption, ground effect and topographic screening are simplified.
- Directivity is currently assumed as `Dc = 0 dB`.
- `Cmet` is not currently applied.

---

## 11. Shadow Flicker results look unexpected

Check:

- Time zone.
- Latitude/longitude or project location settings.
- Turbine hub height and rotor diameter.
- Receptor height.
- Time step.
- DEM/DSM selected or not selected.
- Whether raster and receptor calculations use the same settings.

Important:

- DEM/DSM adjusts absolute elevations.
- Full intermediate terrain obstruction / line-of-sight blocking is not yet implemented.
- Smaller time steps increase precision but also increase runtime.

---

## 12. Background task appears stuck

Try:

- Wait for a small period if running a heavy raster.
- Check the QGIS task manager/progress area.
- Cancel the task if possible.
- Re-run with coarser raster resolution.
- Re-run without DEM/DSM.
- Re-run with fewer receptors or smaller radius.

Report:

- Whether the progress bar moved.
- Whether the cancel button worked.
- Approximate number of turbines/receptors.
- Raster resolution and maximum radius.
- Whether DEM/DSM was enabled.

---

## 13. When in doubt

Run the smallest possible test:

```text
2–3 turbines
2–3 receptors
no raster
no DEM/DSM
basic/default settings
```

Then add complexity step by step:

```text
DEM/DSM → raster → ISO engine → multiple source groups → exports
```

This makes it much easier to identify the source of the issue.

### Shadow receiver layer not visible

If a receiver point layer does not appear in the Shadow Flicker receiver combo:

- click refresh/reopen the Shadow module after loading the layer;
- check that the layer is a point vector layer;
- receiver layers can be stored inside the Energy/AEP group, but they should not carry Velantis turbine metadata such as `velantis/model_name` or `velantis/coords_csv`;
- Energy-generated turbine layers are detected separately from ordinary receiver point layers.



---

## Noise troubleshooting

### The Noise page opens, but calculation does not start

Check:

- at least one turbine/source layer is selected;
- a receptor layer is selected;
- the project CRS and layer CRS are compatible;
- receptor limit and source level values are numeric;
- raster resolution/extent are not excessively large.

### Land-use `G_eff` does not seem to affect results

Check the land-use layer:

- it should be a polygon layer;
- it should use the same projected CRS as the project;
- it should include a numeric field such as `g_factor`, `g`, `ground_g`, `g_value` or `G`;
- values should normally be between `0.0` and `1.0`.

Text-field fallback is available for screening, but numeric `g_factor` is preferred for validation.

### The calculation falls back to a synchronous route

This is expected for some configurations, especially land-use `G_eff`, because live vector polygon intersections are safer on the main QGIS thread. Reduce the raster extent/resolution if the run feels heavy.

### Raster or isophones are slow

Try:

- coarser raster resolution;
- smaller extent;
- fewer receptors/source layers;
- run receiver-only first, then enable raster once the setup is confirmed.

### DEM/DSM results look unexpected

Check:

- raster CRS and units;
- elevation values are metres;
- source/receptor coordinates overlap the DEM/DSM extent;
- nodata areas are not being sampled near receptors or turbines.

DEM/DSM support improves elevation consistency, but the terrain-screening model remains simplified.
