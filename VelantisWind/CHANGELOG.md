# Changelog

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
