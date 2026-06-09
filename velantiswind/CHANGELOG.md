# Changelog

## 0.1.10 - Experimental release candidate

- Adds a small Qt5/Qt6 compatibility bootstrap as groundwork for future QGIS 4 testing.
- Keeps the public experimental release targeted at QGIS 3.x until full QGIS 4 smoke tests are completed.
- Includes the previous AEP hotfix for quiet diagnostics and error handling.

## 0.1.10 · Experimental QGIS publication package

- Prepared Velantis Wind for publication as an experimental QGIS plugin.
- Target compatibility declared for QGIS 3.x (`qgisMinimumVersion=3.28`, `qgisMaximumVersion=3.99`). QGIS 4 compatibility work remains in progress.
- Includes Energy/AEP, Noise and Shadow Flicker workflows in a single QGIS plugin.
- Added public documentation for installation, quick start, module usage, limitations, troubleshooting and publication checks.
- Documented the external PyWake dependency required by the Energy/AEP module.
- Kept diagnostics quiet by default; optional developer logs can be enabled with `VELANTISWIND_DEBUG=1`.
- No sample projects, private datasets, generated reports, cache files or compiled Python artifacts are bundled.

## 0.1.x · Earlier development

- Internal refactoring and validation work leading to the first experimental publication package.
