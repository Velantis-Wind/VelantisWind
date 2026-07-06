# Changelog

### Hub UI final polish
- Restores the new hub interface style as the canonical home screen.
- Keeps the same hub geometry when switching ES/EN/FR/DE; only labels are refreshed.
- Removes Visual Impact/Wireline from the visible hub and release package, leaving Energy, Noise and Shadow Flicker.
- Strengthened the layout-optimization CTA in the Hub with clearer commercial wording around layout + wake-steering co-optimization, higher net production and asset-return improvement.
- Cleaned the Noise technical report for consultancy use: clearer receiver coverage/compliance wording, safer meteorological warnings, cleaner OEM spectrum tables, no placeholder spectrum source, and technical physics moved into an appendix-style section.


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