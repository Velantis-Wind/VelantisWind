# Velantis Wind — Known Limitations

This document summarizes the main known limitations of the experimental release version.

> The plugin is intended for wind-farm screening, pre-assessment, design iteration and GIS-based comparison. It should not be treated as certified regulatory or bankable assessment software.

---

## 1. General limitations

- The plugin is in experimental release and is still evolving.
- User interface text, report structure and internal APIs may change.
- Results depend strongly on the quality of input data.
- GIS CRS, units, layer validity and geometry validity are the responsibility of the user.
- Large raster calculations may take time, especially with DEM/DSM enabled.
- Some workflows rely on optional scientific dependencies installed in the QGIS Python environment.
- Error handling is being improved during testing.

---

## 2. Energy / AEP limitations

### Dependency

- PyWake is required for the Energy / AEP module.
- PyWake is not bundled with the plugin and must be installed separately in the same Python environment used by QGIS.

### Scope

- The Energy module is intended for preliminary AEP comparison and layout screening.
- It is not a replacement for full bankable wind-resource assessment or certified design tools.

### Model dependence

Energy results depend on:

- Wind-resource quality.
- Turbine power and CT curves.
- Hub-height assumptions.
- Selected wake model.
- Turbulence model and input data.
- Blockage option.
- Rotor-average option.
- Grid resolution and layout constraints.

### Current practical limitations

- Some PyWake model combinations may not be supported in every environment.
- Unsupported physics combinations should show warnings, but some edge cases may still need technical feedback.
- Advanced yaw/layout co-optimization workflows are not part of the public experimental release scope unless explicitly enabled.
- Scenario comparison is intended for practical comparison, not formal uncertainty analysis.

---

## 3. Noise limitations

### Positioning

The Noise module is an **ISO-aligned screening workflow**, not certified regulatory noise software.

It is useful for:

- Early-stage site screening.
- Comparing layouts.
- Identifying potentially critical receptors.
- Producing preliminary GIS noise maps.
- Understanding sensitivity to terrain, ground factor and source levels.

It should not be used alone for final regulatory compliance studies.

### ISO-aligned engine limitations

The current ISO-aligned octave-band engine includes simplifications:

- Atmospheric absorption `Aatm` is simplified.
- Ground effect `Agr` is simplified.
- Topographic screening `Abar` is simplified.
- Directivity correction `Dc` is assumed as `0 dB`.
- Long-term meteorological correction `Cmet` is not currently applied.
- Other miscellaneous attenuation terms are not fully implemented.

### Source data limitations

- Manufacturer-specific octave-band spectra should be used when available.
- If no source spectrum is provided, the plugin uses editable generic templates.
- Generic templates are useful for screening but are not a substitute for verified acoustic data.
- Acoustic curves and spectra must be checked by the user.

### Multiple turbine models

- Multiple turbine models are supported as separate source groups/layers.
- Mixed turbine models inside a single source layer by feature-level attributes are not yet fully supported.
- Recommended experimental workflow: one source layer/group per turbine model.

### DEM/DSM and Abar limitations

- DEM/DSM can be used for basic topographic screening in the ISO-aligned workflow.
- `Abar = 0` for a specific receiver or source path can be valid when line of sight is clear.
- The critical receiver may have `Abar = 0` even if other receivers are terrain-screened.
- Raster with ISO + DEM/DSM may be computationally expensive.

### Land-use / ground factor limitations

- Global `G` is supported.
- Land-use based `G_eff` workflows are more sensitive to vector topology and CRS.
- `G_eff` is a practical screening approximation and should be checked carefully.

---

## 4. Shadow Flicker limitations

### Positioning

The Shadow Flicker module is intended for preliminary screening and GIS-based assessment of potential flicker impact.

It is useful for:

- Early receptor screening.
- Comparing layouts.
- Producing annual/monthly/hourly summaries.
- Creating preliminary shadow flicker rasters.

### DEM/DSM limitations

- DEM/DSM is used to adjust absolute turbine, receptor and raster-cell elevations.
- This affects the vertical geometry of the flicker calculation.
- The current experimental release does **not** implement complete intermediate terrain obstruction / line-of-sight blocking between turbine and receptor.

In other words:

```text
Implemented: DEM-aware elevation geometry.
Not yet implemented: full terrain occlusion along the shadow path.
```

### Time and solar geometry limitations

Results depend on:

- Time zone.
- Date/time grid.
- Time step.
- Receptor height.
- Turbine hub height and rotor diameter.
- Project location and coordinate assumptions.

Smaller time steps improve temporal resolution but increase runtime.

### Raster limitations

- Raster outputs may be slower than receptor-only calculations.
- Raster resolution strongly affects runtime and memory use.
- Coarse rasters are recommended for first experimental tests.

---

## 5. Performance limitations

Heavy workflows include:

- Noise ISO + DEM/DSM + raster.
- Shadow Flicker with small time step + raster.
- Large receptor sets.
- Large turbine layouts.
- Very fine raster resolutions.

Recommended first-test settings:

```text
Small number of turbines
Small number of receptors
No raster
No DEM/DSM
Default/basic settings
```

Then add complexity gradually.

---

## 6. Experimental interpretation guidance

During testing, focus on:

- Does the workflow run?
- Does QGIS remain usable?
- Are outputs created?
- Are results plausible?
- Are warnings understandable?
- Are reports clear about assumptions and limitations?

Avoid treating experimental outputs as final engineering conclusions without independent validation.


---

## Additional Noise experimental limitations

- The Noise module is an ISO-aligned screening workflow, not certified regulatory software.
- Built-in source spectra are reference templates and should be replaced by manufacturer/project data where possible.
- Land-use text fallback may misclassify ground type; numeric `g_factor` polygons are preferred.
- Terrain screening is simplified and should not be treated as a full multiple-edge diffraction model.
- Long-term meteorological correction and detailed regulatory post-processing are not implemented as a full permitting workflow.
- Large ISO + DEM/DSM raster runs may be slow; validate with receiver-only runs first.


## QGIS 4 compatibility

This experimental public package targets QGIS 3.x. QGIS 4 compatibility work is in progress and should be tested separately before declaring the plugin QGIS 4-ready.
