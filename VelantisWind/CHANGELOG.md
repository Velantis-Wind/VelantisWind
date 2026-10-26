# Changelog

## 0.1.17

### Installation
- Pinned `py_wake==2.6.18`, the version used to check the predefined models and consistency with PyWake. The dialog does not warn if another version is installed. In the Python environment used by QGIS, Linux and macOS install `py_wake==2.6.18`, `h5py` and `h5netcdf>=1.8` with pip; Windows with QGIS from OSGeo4W installs `py_wake==2.6.18` and `h5netcdf>=1.8` with pip. Since version 1.8, `h5netcdf` no longer depends on `h5py`.
- On Windows with QGIS from OSGeo4W, the pip wheel of `h5py` is expected to fail to load because its HDF5 library conflicts with the one QGIS loads. This has not been reproduced on Windows. Do not install `h5py` with pip there; installing `python3-h5py` through the OSGeo4W installer is an option still to be tested. See the [installation guide](docs/INSTALL_OSGEO4W_PYWAKE.md). On Windows, the result notes and the plugin API error no longer suggest installing `h5py` with pip; they refer to the installation instructions.
- `h5py` and `h5netcdf` are needed by `GaussianOverlapAvgModel`, used by the predefined NiayifarGaussian and TurbOPark models. If either library is missing or fails to load where PyWake needs the lookup table (for these predefined models, with two or more turbines or in a wake raster), both predefined and manual modes ask before calculating. **Continue** uses `CGIRotorAvg(7)` for that launch; **Cancel** calculates nothing. The result records the selected and executed configurations and identifies a predefined result as an adaptation from that model. An unchecked box can remember the decision for that predefined model; an applicable saved decision is applied without asking and is stated in the result.

### Energy / AEP
- Wake physics is built from the PyWake classes selected in the dialog: engine first, then deficit, rotor average, ground, superposition, turbulence and blockage where supported. Parameters of these objects and the engine's numerical settings are editable; unchanged values come from their PyWake signatures. Unsupported combinations report a conflict instead of calculating with different physics.
- Added read-only predefined PyWake park models, including TurbOPark and excluding Fuga, with contextual help for each mode, model and selector. A new installation, and an upgrade from 0.1.16, opens in **Predefined models** with **NOJ**. The manual mode starts with `PropagateDownwind`, `BastankhahGaussianDeficit`, `LinearSum`, no rotor average, no added turbulence and no blockage. The physics preferences of 0.1.16 are no longer used and are left untouched; if there are any, a one-time notice says so the first time the manual mode is shown. Between dialog sessions, the manual mode remembers the engine, deficit, superposition, turbulence and blockage selections; edited parameters and subordinate choices restart from their PyWake signature defaults.
- Results record the selection and the executed configuration, convergence and model warnings. The signed wake, turbulence and blockage breakdown is shared by the results window, reports, CSV, layers and scenario comparator; an unavailable term is identified as such, rather than reported as zero. In turbine layers, result fields of the previous version whose meaning changed are kept but no longer written, with a warning; current results use the new fields. A CSV export is accompanied by `<name>.wake_config.json`, with the wake configuration.
- API: a calculation request can give the wake physics as a versioned `wake_physics`; supported fields of the previous schema are translated and the translation is recorded in the result. Rejected, with an error: `AUTO` as a physics selector, `wake_model`, previous-schema values that are neither in the translation table nor a class name, requests mixing the previous fields with `wake_physics`, a position given twice with different values and an `include_*` flag that contradicts its class.
- WRG resource parameters use directions at the centres of equal sector subdivisions: initially seven per sector, or one if seven would exceed 360 directions. Directional interpolation is `nearest` initially, with `linear` also available; Speedup is `none`, preserving the local Weibull climate. Wind speeds cover the turbines' operating bands, with a step of 1, 0.5 or 0.25 m/s. GRD resources use their PyWake site's directions and wind speeds. Both use 8766 h/year.
- A single-height WRG can be used at other hub heights with a warning. With a multi-height WRG, turbine hub heights must lie within the covered vertical range: heights outside it are now rejected instead of being clipped to it; directional summaries use the resource's native sectors. The WRG readers now agree on node records, including X coordinates in scientific notation, with a trailing dot or with a leading `+`. Node identifiers that read as a finite number, such as `001` or `1e3`, are now rejected, because they can shift the columns of a record; some files that earlier versions accepted are affected. Text identifiers remain supported, and a rejected record names its file and line.
- Each Energy model row selects a point layer of the project, which replaces the coordinates-CSV field; **Load new layer** imports a coordinate table into a new layer. AEP and the wake raster use only the selected layers; AEP results are written back to those layers when they accept the result fields, and a failed write is reported. Turbines outside the resource are reported and totals are identified as partial; excluded turbines may keep results of an earlier calculation in their layer, and the warning says that those values do not belong to the current calculation. Coordinates retain double precision.
- Mixed-model parks: each turbine model is evaluated at its own hub height. Version 0.1.16 evaluated every model at the hub height of the first one, so the AEP of mixed parks with different hub heights changes. Multi-height WRG files keep a two-dimensional terrain surface.
- Turbine curves now respect their operating bands and validate supplied Ct instead of clipping it. CSV/TXT readers keep each row whole, reject malformed power or Ct with its location and accept repeated spaces and tabs; missing Ct is explicitly identified as estimated. Invalid or ambiguous hub heights and rotor diameters are rejected instead of using silent geometry defaults.
- Added `.wtg` and `.owtg` density-tabulated curves with strict format validation and optional uniform or per-turbine air density. Density is bounded by each model's actual table, including an irregular density axis. The turbine dialog discards failed builds and asks before accepting a turbine whose inputs have changed.
- Energy calculations use the mean power over each wind-speed bin by default, including gross AEP and the loss variants; Ct is still evaluated at the supplied speed.
- Power curves keep a high-wind derating or a shutdown before cut-out; previously a cumulative maximum removed it. Only negative or non-finite power values are set to zero. For curves without a CT column, the estimated CT is now zero wherever the power is zero (below cut-in or at a shutdown), so the AEP of those curves changes.
- Two turbine models with the same name are rejected before calculating, because their layers and per-model results are matched by name.
- Negative or non-finite effective speeds no longer fail solely because a density-tabulated curve's wind-speed axis is exceeded. Results warn about negative speeds and non-finite values; totals omitting cases that may carry energy are labelled partial. `WeightedSum` handles the 0 m/s node separately where applicable so it can weight the other bins, and records exceptions and convergence warnings.
- The reference air density of the density adjustment, new in this version, is stored in each QGIS project; a project without one starts **undefined**, with the adjustment off. Reference-density values saved globally by development builds before the release are not imported. Changing projects clears the last AEP and comparator scenarios.

### Spacing envelopes
- Regenerating envelopes no longer empties an envelope layer saved to a file. **Apply** and **Reset** mark the project as modified.
- Energy creates and compares spacing envelopes only for the turbine layers selected in its model rows.

### Wake raster
- Added a georeferenced wake raster for the most energetic sector or a selected wind direction, computed as a cancellable QGIS task. It adds free-flow speed, effective speed, deficit in m/s and in %, and terrain elevation when available, and writes a JSON audit file.
- The WRG raster uses Speedup `none`, the selected directional interpolation and the same straight distances as AEP. Mixed-model parks keep each model's diameter, hub height and Power/CT curve.
- The flow map is computed in bounded tiles, keeping memory limited on fine grids and allowing cancellation between tiles.
- Every input, including density, comes from the current dialog; the final window identifies differences from the last AEP in the project. A raster finishing after a project change is not loaded into the new project.
- Custom and derived CRS are retained in the raster files, including CRS without WKT1. Negative and non-finite cells are reported; an undefined relative deficit is written as NoData.

### Noise and Shadow Flicker
- The turbine layout import accepts XLSX files and coordinates in any CRS, transformed to the project CRS. A CRS typed as text that is not valid is rejected. Layout imports now stop at rows with invalid or non-finite coordinates instead of silently omitting those turbines; when other rows can be read, the error names the unreadable ones. XLSX import needs `openpyxl` in the Python environment of QGIS; without it, save the file as CSV.
- Custom and derived CRS are preserved in layout imports and TI-raster sampling. Noise isophones use FlatGeobuf to retain such CRS; failure to create them is reported without discarding the rest of the Noise result.
- Exactly 30 h/year of shadow flicker does not exceed the annual limit in the summary, result fields or map classification; exceeding means **more than 30 h/year**. The daily criterion remains more than 30 min/day. The receiver symbology covers values up to 8784 h/year, and the raster legend uses red only above 30 h, with distinct labels just above the limit.

### Interface, translations and support
- Added minimize, maximize/restore and close controls to Energy, Noise and Shadow Flicker. Reopening a minimized window restores it and preserves its maximized state; Energy retains a single set of controls when reused.
- Corrected Spanish, English, French and German texts across the modules, help, reports and exports. Translation no longer depends on module import order, opening Energy in another language is faster, and live language changes preserve selections, results and unfinished edits. User names, paths and template fields are protected from translation.
- MW and MWh in the text and tables of the Energy results window, its HTML report and the comparison tables use the decimal and thousands separators of the plugin language. Other numbers may still use a decimal point in every language, among them the chart axes and those of the Noise and Shadow results and of the QGIS log. CSV numeric formats are unchanged.
- Added a shared **Sponsors** button in the hub and Energy, linked to the support dialog. Sponsorship opens the GitHub Sponsors profile; support levels can be expanded, documentation has separate links, and a failed link launch shows a copyable address. The button and fallback address support keyboard access; funding links are aligned with the public repository.

### Stability and maintenance
- Fixed a QGIS crash when a calculation running in a background task wrote to the message bar.
- The plugin version is read from `metadata.txt` in one place and recorded in the wake-raster JSON and the Noise XLSX export.
- Annotated reviewed security-scanner false positives.

### Changes to default AEP results
Compared with 0.1.16, default AEP results change with the wake-model selection (predefined NOJ on a new installation; PyWake signature defaults, including Bastankhah with `LinearSum`, in manual mode), the WRG directions and operating-band wind speeds and 8766 h/year for WRG and GRD; as in 0.1.16, WRG calculations keep the local Weibull climates without a speed-up. Bin-mean power, corrected operating bands and Ct handling, preserved derating and per-model hub heights also affect AEP. Density-tabulated curves use the selected density treatment; `WeightedSum` calculations including 0 m/s can change because weighting now applies to the other bins. Review the executed configuration and warnings when comparing results from different versions.

### Known resource-union problems
The **Merge resource** tool ("Unir recurso") can write grids that PyWake cannot read, and discards the turbulence intensity and speed factors of the merged resource. These problems remain for the next version.

## 0.1.16

### Compatibility and stability
- Reworked Noise and Shadow Flicker raster reads/writes to avoid GDAL's optional NumPy bridge and use buffer-based `ReadRaster`/`WriteRaster` helpers.
- Made the Shadow Flicker raster worker use primitive snapshots, CRS text and a GDAL-readable DEM path instead of live QGIS project objects, while preserving terrain-aware sampling and reporting the real raster error when a task fails.
- Replaced the Noise XLSX export path based on `openpyxl`/`lxml` with a small standard-library OOXML writer, added atomic workbook creation and localized workbook content and completion messages in ES/EN/FR/DE.
- Expanded Qt5/Qt6 compatibility aliases used by the turbine catalogue and Interactive Map workflows.

### Turbine catalogue and energy layers
- Added a searchable catalogue of 42 turbine screening candidates: 4 traceable public/reference curves, 8 clearly labelled approximations anchored to public technical specifications and 30 manufacturer-neutral generic onshore/offshore classes.
- Added visible curve quality, source and caveat information; edited packaged curves are persisted as `user_edited`, and provenance is stored on generated QGIS turbine layers.
- Re-audited all 42 packaged curves for ordering, rated power, monotonicity, CT range, shutdown behaviour and implied peak power coefficient.
- Added model-specific longitudinal and crosswind spacing defaults to manual and CSV/TXT turbine definitions.
- After an AEP calculation, each turbine-model layer receives independent graduated symbology by individual AEP plus `model_perf_pct` and `model_rank` fields for within-model comparison.

### Spacing envelopes and Interactive Map
- Added semi-transparent elliptical spacing envelopes for turbines, with configurable longitudinal/crosswind distances, automatic orientation towards the most energetic WRG sector and a manual fallback angle.
- Added one persistent envelope layer per turbine model/source layer, using each model's rotor diameter and validating conflicts across compatible model layers.
- CSV turbine-layout imports now create or refresh their linked envelope layers automatically, including configurations saved before coordinates are loaded.
- Added instant `OK / near the limit / conflict` highlighting, selectable validation up to insertion blocking and one-table-per-model GeoPackage export.
- Added a three-click on-screen ellipse tool with live preview, rotor-diameter/metre readout and keyboard snapping; on-screen ellipses remain per-turbine overrides and do not overwrite the model template.
- Added an explicit **Apply new configuration** action so model-wide dimensions and orientation are only persisted and rebuilt when confirmed.
- Completed static and dynamic Interactive Map and spacing-envelope labels, tooltips and status messages in Spanish, English, French and German.

### Hub and reporting
- Kept the refreshed Hub as the canonical home screen, with stable geometry when switching languages and the public modules limited to Energy/AEP, Noise and Shadow Flicker.
- Strengthened the layout-optimization call to action around layout and wake-steering co-optimization.
- Refined the Noise technical report for consultancy screening, including clearer receiver coverage/compliance wording, safer meteorological warnings and cleaner spectrum traceability.

## 0.1.15
- Refined multilingual coverage for Spanish, English, French and German across the Hub, Energy/AEP, Noise and Shadow Flicker entry points.
- Stabilized Hub language switching so labels, buttons, project summary and layout-optimization panel update in place without changing the interface layout.
- Kept the language selector stable in native labels: Español, English, Français and Deutsch.
- Improved Noise report wording and traceability for OEM octave-band spectra, including spectrum origin, normalization mode and A-weighted consistency checks.
- Added direct OEM spectrum input workflow for Noise source groups, including CSV import, manual octave-band editing and optional A-weighted input conversion.
- Improved Energy/AEP and Shadow Flicker wording for public testing.
- Removed the prototype fourth-module entry from the public Hub for this release.
- Removed temporary/cache artifacts from the release package.

## 0.1.14
- Added multilingual interface coverage, including French and German.
- Improved Energy/AEP, Noise and Shadow Flicker localization.
- Removed global Qt/PyQt runtime translation patches so VelantisWind does not modify methods used by other QGIS plugins.

## 0.1.13
- Added independent turbine-layout import from the Noise and Shadow Flicker modules.
- Improved cross-module detection of VelantisWind turbine layers.
- Kept QGIS 3.x/QGIS 4.x experimental metadata and PyWake installation guidance.
