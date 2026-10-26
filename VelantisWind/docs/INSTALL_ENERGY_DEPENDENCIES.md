# Installing Energy / AEP dependencies

The VelantisWind plugin can be loaded without PyWake, but the **Energy / AEP** module requires PyWake and scientific Python packages installed in the same Python environment used by QGIS.

For the detailed Windows / OSGeo4W guide, see:

[`INSTALL_OSGEO4W_PYWAKE.md`](INSTALL_OSGEO4W_PYWAKE.md)

---

## Which versions, and why

Install `py_wake==2.6.18`, `h5py` and `h5netcdf>=1.8` with pip on Linux and macOS. On Windows with QGIS from OSGeo4W, run `python -m pip install py_wake==2.6.18 "h5netcdf>=1.8"`: PyWake requires `h5netcdf`, and since version 1.8, `h5netcdf` no longer depends on `h5py`. With this minimum version, the command does not install `h5py` through `h5netcdf`. Use the untested OSGeo4W option below for `h5py`. `requirements-energy.txt` pins PyWake, requires `h5netcdf>=1.8` on all platforms and excludes `h5py` on Windows.

The package metadata checked with pip in the QGIS environment lists only `numpy` and `packaging` as requirements of `h5netcdf` 1.8.1; it does not declare `h5py` as a dependency.

- `py_wake==2.6.18`: the predefined models and the plugin's consistency with PyWake were checked with this version; the dialog does not warn if a different version is installed.
- `h5py` and `h5netcdf`: needed by `GaussianOverlapAvgModel`, the rotor average of the predefined models NiayifarGaussian and TurbOPark.

---

## Linux and macOS

In the Python environment used by QGIS:

```bash
python -m pip install py_wake==2.6.18 h5py "h5netcdf>=1.8"
python -c "import py_wake, h5py, h5netcdf; print('PyWake OK:', py_wake.__file__)"
```

Restart QGIS afterwards.

---

## Windows / OSGeo4W

Close QGIS, open **OSGeo4W Shell**, and run:

```bat
python -m pip install py_wake==2.6.18 "h5netcdf>=1.8"
```

Then verify:

```bat
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Restart QGIS afterwards. This command ensures `h5netcdf>=1.8` is installed, so `h5netcdf` does not pull in `h5py`. Do not add `h5py`; read the next section.

### `h5py` in QGIS from OSGeo4W

Expected problem on Windows (not reproduced there): the `h5py` pip wheel is expected to fail to load inside QGIS from OSGeo4W (`ImportError: DLL load failed while importing defs`). Its wheel bundles an HDF5 library named `hdf5.dll`, the same name as the library QGIS loads from OSGeo4W. Windows reuses a DLL already loaded under that name. Inspection of the binaries found that `gdal313.dll` imports `netcdf.dll`, which imports OSGeo4W's `hdf5.dll` 1.14.6. The `h5py` 3.16.0 wheel for Windows bundles HDF5 2.0.0 under the same name, and version 1.14.6 lacks 19 of the 522 symbols required by `h5py`. The same type of error is documented in qgis/QGIS#54643 and qgis/QGIS#29439; h5py/h5py#1979 describes the conflict between two `hdf5.dll` libraries in one process. The outcome depends on the HDF5 versions bundled with QGIS and the pip wheel. For this reason, `pip install h5py` is not offered as a solution on Windows.

An option to try is installing `python3-h5py` through the OSGeo4W installer. This package is built against OSGeo4W's HDF5 and is not included in `qgis-full`. This option has not been tested. The command above ensures `h5netcdf>=1.8` is installed by pip; it does not need to be installed through OSGeo4W.

If `h5py` is missing, the result note and the plugin API error suggest `python -m pip install h5py` on Linux and macOS. On Windows they say that `h5py` is not installed with pip and refer to the installation instructions, where the untested OSGeo4W installer option above applies.

If `h5py` or `h5netcdf` is missing or fails to load when PyWake would read the `GaussianOverlapAvgModel` table (for the predefined models NiayifarGaussian and TurbOPark, with two or more turbines or in a wake raster), the dialog asks before calculating in both predefined and manual modes. **Continue** uses `CGIRotorAvg(7)` and records the adaptation in the results; **Cancel** calculates nothing. If a predefined model has an applicable saved decision, the dialog adapts without asking, and the result states that the saved decision was applied.

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
| `h5py` and `h5netcdf` | The table of the `GaussianOverlapAvgModel` rotor average (see the sections above for Windows) |

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


## GaussianOverlapAvgModel and h5py

The `GaussianOverlapAvgModel` rotor average reads a PyWake NetCDF table and needs both `h5py` and `h5netcdf`. The commands above install `h5netcdf>=1.8`; since that version no longer depends on `h5py`, the Windows command does not install `h5py` through `h5netcdf`.

If `h5py` or `h5netcdf` is missing or fails to load when PyWake would read the `GaussianOverlapAvgModel` table (for the predefined models NiayifarGaussian and TurbOPark, with two or more turbines or in a wake raster), the dialog asks before calculating in both predefined and manual modes. **Continue** uses `CGIRotorAvg(7)` and records the adaptation in the results; **Cancel** calculates nothing. If a predefined model has an applicable saved decision, the dialog adapts without asking, and the result states that the saved decision was applied.

The API refuses a request that would read the table when either library is unavailable, with installation instructions. The plugin never installs anything.
