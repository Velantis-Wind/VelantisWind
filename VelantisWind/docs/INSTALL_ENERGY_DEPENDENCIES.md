# Installing Energy / AEP dependencies

The VelantisWind plugin can be loaded without PyWake, but the **Energy / AEP** module requires PyWake and scientific Python packages installed in the same Python environment used by QGIS.

For the detailed Windows / OSGeo4W guide, see:

[`INSTALL_OSGEO4W_PYWAKE.md`](INSTALL_OSGEO4W_PYWAKE.md)

---

## Recommended command for Windows / OSGeo4W

Close QGIS, open **OSGeo4W Shell**, and run:

```bat
python -m pip install py_wake==2.6.18
```

Then verify:

```bat
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Restart QGIS afterwards.

---

## Required for the Energy module

The Energy / AEP module uses:

| Package | Purpose |
|---|---|
| `py_wake` | Wake-aware AEP calculations |
| `numpy` | Numerical arrays |
| `scipy` | Scientific calculations |
| `xarray` | PyWake datasets and multidimensional data |
| `matplotlib` | Figures and plots |
| `pandas` / `openpyxl` | Some tabular/report workflows |

PyWake normally installs or requires most of its scientific dependencies. If a specific dependency is missing, install it inside the same QGIS / OSGeo4W Python environment.

---

## Important notes

- PyWake is not bundled with VelantisWind.
- PyWake is not installed from the QGIS Plugin Manager.
- PyWake must be installed in the same Python environment used by QGIS.
- Do not install dependencies into Anaconda or a standalone Python environment unless QGIS is configured to use that same environment.
- Avoid replacing QGIS / OSGeo4W GDAL packages with unrelated GDAL wheels.

---

## Experimental release limitation

For the first experimental release, dependency installation is intentionally documented rather than automated.

This avoids modifying the user’s QGIS Python environment from inside the plugin and keeps the installation process safer for different QGIS setups.

---

## Contact

For installation support, beta testing or technical questions, please contact:

**info@velantiswind.com**
