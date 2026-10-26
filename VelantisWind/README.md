# Velantis Wind — QGIS Plugin

**Open-source wind-farm pre-assessment workflows directly inside QGIS.**

Velantis Wind is an open-source QGIS 3.x plugin for early-stage wind-farm analysis. It brings together **Energy / AEP**, **Noise** and **Shadow Flicker** workflows in one GIS-based environment.

> **Status:** stable QGIS repository release (version 0.1.17). Velantis Wind is intended for screening, layout comparison, validation workflows and technical feedback. It is **not** certified regulatory, permitting or bankable assessment software.
>
> **Compatibility:** this stable package declares QGIS 3.28–3.99 support. QGIS 4 has not been validated and is outside the declared compatibility of this build.

## What is new in 0.1.17

- Predefined PyWake models, including TurbOPark, and manual class selection with editable parameters, rotor averaging, ground, turbulence and blockage. A new installation opens with predefined NOJ; manual defaults use Bastankhah with `LinearSum` and PyWake signature values. Results report the executed configuration and signed losses.
- WRG resource parameters: sector-subdivision centres (seven per sector initially, or one if seven would exceed 360 directions), `nearest` or `linear` directional interpolation, Speedup `none` and wind speeds covering the turbines' operating bands. GRD uses its PyWake site's directions and wind speeds; both use 8766 h/year.
- Density-tabulated `.wtg`/`.owtg` curves, optional per-turbine density, validated CSV/TXT curves, preserved derating, per-model hub heights and bin-mean power in energy calculations.
- A turbine layer per Energy model row, reported resource exclusions, double-precision coordinates and fixes to spacing-envelope persistence and comparisons.
- Negative effective speeds no longer fail at the density-table axis boundary; results report negative and non-finite values and partial totals. `WeightedSum` handles the 0 m/s node separately where applicable.
- Georeferenced wake rasters with cancellation and a JSON audit file, using all current dialog inputs and reporting differences from the last AEP. Custom and derived CRS are retained; a raster is not loaded into another project after a project change.
- XLSX and any-valid-CRS layout imports in Noise and Shadow Flicker; Noise isophones retain derived CRS. Exactly 30 h/year does not exceed the shadow-flicker annual limit, consistently in the summary, result fields and map.
- Minimize, maximize/restore and close controls; a shared Sponsors button and clearer support links. Corrected ES/EN/FR/DE translations, faster translation and live language changes that preserve user data and edits. MW and MWh in the text and tables of the Energy results and report follow the plugin language; other numbers, such as the chart axes, may still use a decimal point, and CSV numeric formats are unchanged.

**Default AEP results change compared with 0.1.16**, through wake defaults, resource grids, 8766 h/year, bin-mean power and turbine-curve corrections. The reference air density, new in this version, is stored in each project; a project without one starts undefined, with the density adjustment off.

**Installation:** use `py_wake==2.6.18`, `h5netcdf>=1.8` and, on Linux/macOS, `h5py` with pip. On Windows with QGIS from OSGeo4W, do not install `h5py` with pip: an HDF5 conflict is expected but has not been reproduced there; `python3-h5py` through the OSGeo4W installer is an untested option. When GaussianOverlap's libraries are unavailable, the dialog asks before using `CGIRotorAvg(7)` where its table is needed and records the adaptation, or applies an applicable saved decision for the predefined model without asking. See [Energy dependency](#energy-dependency).

**Known problem:** **Merge resource** ("Unir recurso") can write grids PyWake cannot read and discards turbulence intensity and speed factors; these problems remain for the next version. See the [full changelog](CHANGELOG.md).

## What is new in 0.1.16

- Per-model elliptical spacing envelopes with WRG-based orientation, conflict validation, automatic CSV-layer refresh and screen-defined overrides.
- A curated 42-candidate turbine screening catalogue with explicit quality and source labels.
- More robust Noise/Shadow raster processing and a dependency-free Noise XLSX writer for affected Windows/QGIS installations.
- Independent per-model AEP symbology and relative turbine performance fields after calculation.

See [`CHANGELOG.md`](CHANGELOG.md) for the full release notes.

---

## What Velantis Wind does

| Module | Purpose | Main outputs |
|---|---|---|
| **Energy / AEP** | Estimate wind-farm production with PyWake-compatible workflows and GIS inputs. | Gross/free AEP, wake-reduced AEP, wake/TI/blockage diagnostics, per-turbine table, sector summaries, HTML/CSV reports, QGIS layers and georeferenced wake rasters. |
| **Noise** | Run preliminary wind-turbine noise screening with fast and ISO-aligned octave-band engines. | Receiver levels, margins, compliance tables, critical receiver, noise raster, isophones and source-receptor links. |
| **Shadow Flicker** | Estimate preliminary shadow/flicker impact using turbine, receptor, terrain and solar-geometry inputs. | Annual hours, real/adjusted hours, affected days, monthly/hourly matrices, receptor layer and raster map. |
| **Spacing envelopes** | Visualize and validate model-specific minimum turbine separation in the Interactive Map. | Per-model elliptical layers, conflict status, optional insertion blocking and GeoPackage export. |

The plugin is designed for transparent pre-assessment, GIS-based QA/QC, technical validation against existing workflows and layout iteration. Users should document all input assumptions and independently verify outputs before using them in formal studies.

---

## Installation summary

### Option A — Install from ZIP in QGIS

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the Velantis Wind ZIP.
4. Enable **Velantis Wind**.
5. Open the plugin from the toolbar or the plugin menu.

### Option B — Manual installation

Copy the plugin folder into your QGIS profile plugin directory:

```text
QGIS3/profiles/default/python/plugins/VelantisWind/
```

Then restart QGIS and enable **Velantis Wind** from the Plugin Manager.

### Energy dependency

The Energy / AEP module requires **PyWake** in the same Python environment used by QGIS. PyWake is not bundled inside the plugin and it is not installed from the QGIS Plugin Manager.

Install `py_wake==2.6.18`, `h5py` and `h5netcdf>=1.8` in the Python environment used by QGIS. PyWake 2.6.18 requires `h5netcdf`. Since version 1.8, `h5netcdf` no longer depends on `h5py`, so the Windows command below does not install `h5py` through `h5netcdf`. On Linux and macOS, install all three with pip. On Windows with QGIS from OSGeo4W, do not install `h5py` with pip; see the OSGeo4W option below. The predefined models and the plugin's consistency with PyWake were checked with version 2.6.18; the dialog does not warn if a different version is installed. `h5py` and `h5netcdf` are needed by `GaussianOverlapAvgModel`, the rotor average used by the predefined models NiayifarGaussian and TurbOPark.

On Linux and macOS, in the Python environment used by QGIS:

```bash
python -m pip install py_wake==2.6.18 h5py "h5netcdf>=1.8"
python -c "import py_wake, h5py, h5netcdf; print('PyWake OK:', py_wake.__file__)"
```

On Windows, with QGIS from OSGeo4W, close QGIS, open **OSGeo4W Shell** and run:

```bash
python -m pip install py_wake==2.6.18 "h5netcdf>=1.8"
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Then restart QGIS and install or enable VelantisWind.

Expected problem on Windows (not reproduced there): the `h5py` pip wheel is expected to fail to load inside QGIS from OSGeo4W (`ImportError: DLL load failed while importing defs`). The wheel bundles an HDF5 library named `hdf5.dll`, the same name as the library QGIS loads from OSGeo4W. Windows reuses a DLL already loaded under that name. Inspection of the binaries found that OSGeo4W HDF5 1.14.6 lacks 19 of the 522 symbols required by the `h5py` 3.16.0 wheel (HDF5 2.0.0). For this reason, `pip install h5py` is not offered as a solution on Windows.

An option to try is installing `python3-h5py` through the OSGeo4W installer. This package is built against OSGeo4W's HDF5 and is not included in `qgis-full`. This option has not been tested. The command above ensures `h5netcdf>=1.8` is installed by pip; it does not need to be installed through OSGeo4W.

If `h5py` or `h5netcdf` is missing or fails to load when PyWake would read the `GaussianOverlapAvgModel` table (for the predefined models NiayifarGaussian and TurbOPark, with two or more turbines or in a wake raster), the dialog asks before calculating in both predefined and manual modes. **Continue** uses `CGIRotorAvg(7)` and records the adaptation in the results; **Cancel** calculates nothing. If a predefined model has an applicable saved decision, the dialog adapts without asking, and the result states that the saved decision was applied.

Detailed installation guide:

- [`docs/INSTALL_OSGEO4W_PYWAKE.md`](docs/INSTALL_OSGEO4W_PYWAKE.md)
- [`docs/INSTALL_ENERGY_DEPENDENCIES.md`](docs/INSTALL_ENERGY_DEPENDENCIES.md)

---

## Quick start

### Energy / AEP

1. Load or create a turbine point layer, or prepare a layout CSV.
2. Open **Velantis Wind → Energy / AEP**.
3. Select turbine model/curve, layout input and wind-resource input.
   - Version 0.1.16 includes 4 traceable public/reference curves, 8 commercial-model approximations anchored to public technical specifications, and 30 manufacturer-neutral onshore/offshore classes. The dialog separates all three quality levels. Spec-based and generic curves are not OEM-certified and must be replaced with project data for technical deliverables.
4. Select wake model and optional physics settings; with a WRG, review its resource parameters.
5. Run the calculation.
6. Optionally create a georeferenced wake raster; it runs in the QGIS task manager and writes a matching JSON audit file.
7. Review AEP, losses, sector summaries and per-turbine outputs.
8. Export HTML/CSV reports if needed.

### Noise

1. Open **Velantis Wind → Noise**.
2. Load an existing turbine source layer or import a turbine layout CSV directly from the Noise module.
3. Define the turbine/noise attributes required by the module.
4. Load a receptor layer.
5. Select fast or ISO-aligned engine.
6. Set source level/curve, receptor height, radius and optional DEM/DSM or land-use layer.
7. Run the calculation.
8. Review compliance, critical receiver, raster and isophones.

### Shadow Flicker

1. Open **Velantis Wind → Shadow Flicker**.
2. Load an existing turbine layer or import a turbine layout CSV directly from the Shadow Flicker module.
3. Define the turbine geometry required by the module.
4. Load receptor layers and optionally a DEM/DSM.
5. Set observer height, time step, year/time assumptions and raster options.
6. Run the calculation.
7. Review annual hours, real/adjusted hours, monthly tables and raster outputs.

---

## Repository layout

```text
velantiswind/
├─ __init__.py              # QGIS plugin factory
├─ metadata.txt             # QGIS plugin metadata
├─ plugin.py                # QGIS plugin entry point
├─ hub_dialog.py            # Main Velantis Wind hub
├─ aep_setup_dialog.py      # Energy / AEP UI
├─ noise_page.py            # Noise UI
├─ shadow_page.py           # Shadow Flicker UI
│
├─ energy_core/             # Energy UI state, validation, controller and runner
├─ ag_core/                 # Energy engine, resources, PyWake helpers and QGIS outputs
├─ spacing_core/            # Spacing envelopes: separation ellipses in Interactive Map mode
├─ noise_core/              # Noise engines, propagation, receivers, raster and outputs
├─ shadow_core/             # Shadow calculation, solar geometry, terrain, raster and outputs
├─ ui_core/                 # Shared Qt/QGIS UI helpers
├─ assets/                  # Icons, logos and bundled fallback data
├─ docs/                    # User docs, architecture notes and release checklists
├─ requirements-energy.txt  # Optional Energy/AEP dependency list
└─ LICENSE
```

---

## Architecture at a glance

The three modules follow the same broad pattern:

```text
UI → controller → config / validation → runner / engine → results → QGIS outputs
```

Energy, Noise and Shadow Flicker now have a clearer UI/controller/config/runner separation:

```text
Energy:
aep_setup_dialog.py
    ↓
energy_core/dialog_state.py
energy_core/validation.py
energy_core/dialog_controller.py
energy_core/runner.py
    ↓
ag_core/aep_compute.py compatibility façade
    ↓
ag_core/orchestration/ + resources/ + physics/ + simulation/ + results/ + qgis_io/

Noise:
noise_page.py
    ↓
noise_core/dialog_state.py
noise_core/validation.py
noise_core/dialog_controller.py
noise_core/task_controller.py
noise_core/runner.py
    ↓
noise_core/noise_compute.py compatibility façade
    ↓
sources/ + receivers/ + engines/ + raster/ + results/ + qgis_io/

Shadow Flicker:
shadow_page.py
    ↓
shadow_core/dialog_state.py
shadow_core/validation.py
shadow_core/dialog_controller.py
shadow_core/runner.py
    ↓
shadow_core/calculation/point_runner.py
shadow_core/calculation/executor.py
    ↓
shadow_calculator.py + solar_geometry.py + raster/ + qgis_io/ + results/
```

The goal is to keep user interface code separated from calculation logic, make assumptions easier to document and reduce the risk of breaking numerical results during experimental development.

Optional developer diagnostics are quiet by default. To print extra Energy/AEP, Noise and Shadow diagnostics to the QGIS/Python console, start QGIS with:

```bash
set VELANTISWIND_DEBUG=1
```

On Linux/macOS, use `export VELANTISWIND_DEBUG=1` before launching QGIS.

---

## Documentation map

### Start here

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- [`docs/INSTALL_OSGEO4W_PYWAKE.md`](docs/INSTALL_OSGEO4W_PYWAKE.md)
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)

### Module guides

- [`docs/ENERGY_MODULE.md`](docs/ENERGY_MODULE.md)
- [`docs/NOISE_MODULE.md`](docs/NOISE_MODULE.md)
- [`docs/SHADOW_FLICKER_MODULE.md`](docs/SHADOW_FLICKER_MODULE.md)
- [`docs/SPACING_ENVELOPE_MODULE.md`](docs/SPACING_ENVELOPE_MODULE.md)

### Architecture

- [`docs/ENERGY_ARCHITECTURE.md`](docs/ENERGY_ARCHITECTURE.md)
- [`docs/NOISE_ARCHITECTURE.md`](docs/NOISE_ARCHITECTURE.md)
- [`docs/SHADOW_ARCHITECTURE.md`](docs/SHADOW_ARCHITECTURE.md)
- [`docs/SPACING_ENVELOPE_ARCHITECTURE.md`](docs/SPACING_ENVELOPE_ARCHITECTURE.md)

### Testing and publication

- [`docs/RELEASE_TEST_CHECKLIST.md`](docs/RELEASE_TEST_CHECKLIST.md)
- [`docs/QGIS4_SMOKE_TEST.md`](docs/QGIS4_SMOKE_TEST.md)
- [`SUPPORT.md`](SUPPORT.md)

---

## Known limitations

### General

- Experimental software.
- APIs, UI text and reports may still evolve.
- Results depend strongly on GIS layers, CRS, wind-resource data, terrain data and turbine/acoustic inputs.
- Users should independently verify assumptions before using outputs in formal studies.

### Energy / AEP

- Requires PyWake installed in the QGIS Python environment.
- Results depend on resource quality, turbine curves, wake model, turbulence assumptions, blockage options and rotor-average settings.
- The reported wake-reduced AEP is not a full bankable net-energy assessment unless the user separately accounts for availability, electrical losses, curtailment, icing, environmental losses and other project losses.

### Noise

- ISO-aligned screening workflow, not certified regulatory noise software.
- Atmospheric absorption, ground effect, topographic screening, directivity and long-term meteorological correction are simplified.

### Shadow Flicker

- DEM/DSM adjusts absolute elevations for turbines, receptors and raster cells.
- Full intermediate terrain obstruction / line-of-sight blocking is not yet implemented.
- Current execution is sequential for stability; raster calculations may be heavy at fine resolution.

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the complete limitation list.

---

## Public QGIS repository notes

This package is prepared as an experimental release targeting both QGIS 3.x and QGIS 4.x. The metadata declares `qgisMinimumVersion=3.28` and `qgisMaximumVersion=4.99` so the same package can be tested across the current QGIS 3/Qt5 and QGIS 4/Qt6 lines.

Before submitting to the official QGIS plugin repository, check:

- `metadata.txt` version and changelog.
- `repository=`, `homepage=` and `tracker=` links.
- No temporary files, cache folders or generated reports are bundled.
- The plugin opens from a clean QGIS profile.
- Energy, Noise and Shadow smoke tests pass.

See [`docs/RELEASE_TEST_CHECKLIST.md`](docs/RELEASE_TEST_CHECKLIST.md) and [`docs/QGIS4_SMOKE_TEST.md`](docs/QGIS4_SMOKE_TEST.md).

The QGIS Plugin Repository also runs automated security and quality checks after upload. Keep the public ZIP free from hidden files, cache folders, bundled binaries, secrets, generated reports and temporary-only documents.

---

## License

Velantis Wind is released under **GPL-3.0-or-later**. See [`LICENSE`](LICENSE).

---

## Support, sponsorship and partnerships

VelantisWind is free and open source. Optional support helps fund maintenance, documentation, validation with real wind farm cases, translations, QGIS compatibility work and improvements in the Energy/AEP, Noise and Shadow Flicker modules.

Support can take different forms: one-time support, monthly sponsorship, technical partnership, beta testing, validation cases, workflow adaptation or academic/research collaboration.

Sponsorship does not imply ownership, exclusivity or control over the open-source roadmap. Custom adaptations and project-specific developments can be discussed separately when they are aligned with the project.

See [`SUPPORT.md`](SUPPORT.md) for support levels, recognition options, workflow adaptation possibilities and academic collaboration models.

Public recognition is optional and is managed through [`SUPPORTERS.md`](SUPPORTERS.md) when explicitly agreed.

For sponsorship, collaboration, validation cases, custom workflow adaptations, academic collaboration or technical partnerships, contact **info@velantiswind.com**.

## Feedback and bug reports

For bugs and technical feedback, use the GitHub issue templates. When reporting a bug, include QGIS version, operating system, plugin version, module used, input summary, screenshots and the full Python traceback when available.
