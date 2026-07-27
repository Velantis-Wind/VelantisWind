# QGIS 4 / Qt6 smoke-test checklist

The plugin package includes a Qt5/Qt6 compatibility bootstrap and declares QGIS 3.28–4.99 support. Static Python checks are not a substitute for launching the plugin in a real QGIS installation.

Run this checklist in a **new QGIS profile** on both QGIS 4.x and QGIS 3.44 LTR before publishing the release.

1. Install the ZIP from **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Restart QGIS and confirm that Velantis Wind loads without a Python traceback.
3. Open the Hub and switch ES → EN → FR → DE → ES. Check titles, buttons, tooltips and summaries.
4. Open Energy → Define turbine → Manual. Search the 42-candidate catalogue, select several models and verify that diameter, hub height, power and CT arrays are populated.
5. Import a small turbine layout and open Noise. In EN/FR/DE, verify that the full **Calculation preparation** block stays in the selected language.
6. Run a receptor-only Noise calculation without DEM, then with DEM. Generate the standard report and the XLSX package.
7. Run a small Noise raster/isophone calculation and verify the output layers.
8. Open Shadow Flicker, run a small receptor calculation and a coarse raster calculation.
9. Install PyWake in the exact Python environment used by that QGIS installation, restart QGIS, and run a small Energy/AEP case.
10. Check **View → Panels → Log Messages** and the Python console for deprecation warnings or tracebacks.

Record QGIS, Qt, Python, GDAL, NumPy and PyWake versions with the result. A successful QGIS 4 test should not be inferred only from `qgisMaximumVersion=4.99`.
