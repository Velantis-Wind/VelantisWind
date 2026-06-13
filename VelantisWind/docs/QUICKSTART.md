# Velantis Wind — Quickstart

This guide shows the shortest path to check that Velantis Wind opens correctly and that each module can run a first calculation.

> Recommended first test: use a clean QGIS profile, a small project and simple input layers. Add DEM/DSM, rasters and large layouts only after the basic workflow works.

---

## 1. Install and open the plugin

### From ZIP

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the Velantis Wind ZIP.
4. Enable **Velantis Wind**.
5. Open the Velantis Wind toolbar button or plugin menu entry.

### Manual installation

Copy the plugin folder to:

```text
QGIS3/profiles/default/python/plugins/velantiswind/
```

Then restart QGIS and enable the plugin.

---

## 2. Before running calculations

Check these points in the QGIS project:

- Use a projected CRS in metres when distances matter.
- Check that turbine and receptor layers have valid point geometries.
- Reproject layers before running large calculations if they are in latitude/longitude CRS.
- Use small test layers first.
- Confirm output folders are writable.

---

## 3. First Energy / AEP run

### Required setup

The Energy module needs PyWake installed in the same Python environment used by QGIS.

In **OSGeo4W Shell**:

```bash
python -m pip install --upgrade pip
python -m pip install py_wake
python -c "import py_wake; print('PyWake OK')"
```

### Minimum inputs

```text
- Turbine point layer or coordinate input
- Turbine model / power curve / CT curve
- Wind resource supported by the current workflow
- Wake/model options selected in the UI
```

### Steps

1. Load a small turbine layout.
2. Open **Velantis Wind → Energy / AEP**.
3. Select the turbine/layout input.
4. Select the turbine model or curve.
5. Select the wind resource.
6. Use a simple wake configuration for the first run.
7. Run the calculation.
8. Review:
   - Global AEP summary.
   - Wake/loss summary.
   - Per-turbine table.
   - Sector table/plots if available.
   - HTML/CSV export.

### What to check

- No dependency error appears after PyWake installation.
- Turbines are inside the resource domain.
- AEP values are plausible and non-zero.
- The per-turbine CSV opens in Excel/GIS.
- The HTML report opens in a browser.
- The result layer receives the expected fields.

---

## 4. First Noise run

### Minimum inputs

```text
- Turbine source point layer
- Receptor point layer
- Source sound level or acoustic curve
- Receptor height
- Calculation radius
```

### Steps

1. Load turbine and receptor layers.
2. Open **Velantis Wind → Noise**.
3. Start with the fast engine and no DEM/DSM.
4. Run the calculation.
5. Review receiver levels and the critical receiver.
6. Then try the ISO-aligned engine.
7. Add DEM/DSM and raster only after the basic run works.

### What to check

- Receiver table is created.
- Critical receiver is clear.
- Raster/isophones appear when enabled.
- The report states whether DEM/DSM and spectrum data were used.
- QGIS remains responsive during heavy tasks.

---

## 5. First Shadow Flicker run

### Minimum inputs

```text
- Turbine point layer
- Receptor point layer
- Hub height and rotor diameter information
- Project location/time-zone assumptions
```

### Steps

1. Load turbine and receptor layers.
2. Open **Velantis Wind → Shadow Flicker**.
3. Start without DEM/DSM and without raster.
4. Select year, time step and observer height.
5. Run receptor calculation.
6. Review annual hours, real hours, affected days and monthly matrix.
7. Add DEM/DSM and raster after the first run works.

### What to check

- Results are plausible for the site latitude and layout.
- Time zone is correctly reported.
- Monthly/hourly tables are readable.
- Raster generation can be cancelled without freezing QGIS.

---

## 6. Recommended first test order

```text
1. Open plugin hub.
2. Open each module window.
3. Noise fast engine without DEM/DSM.
4. Shadow receptor calculation without DEM/DSM.
5. Energy/AEP small case after PyWake is installed.
6. Noise ISO-aligned without raster.
7. Noise ISO-aligned with DEM/DSM.
8. Shadow with DEM/DSM.
9. Raster outputs only after basic calculations work.
```

This order helps separate installation problems from heavy calculation problems.

---

## 7. Reporting issues

Include:

```text
- QGIS version.
- Operating system.
- Plugin version.
- Module used.
- Input layer summary.
- Screenshots of settings.
- Full traceback from the QGIS Python console, if available.
```

For Energy/AEP, also include:

```text
- PyWake version.
- Wind resource type.
- Turbine model/curve source.
- Wake model and optional physics settings.
```
