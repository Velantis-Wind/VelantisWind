# Velantis Wind — QGIS Plugin

**Open-source wind-farm pre-assessment workflows directly inside QGIS.**

Velantis Wind is an experimental QGIS 3.x plugin for early-stage wind-farm analysis. It brings together **Energy / AEP**, **Noise** and **Shadow Flicker** workflows in one GIS-based environment.

> **Status:** experimental release. Velantis Wind is intended for screening, layout comparison, validation workflows and technical feedback. It is **not** certified regulatory, permitting or bankable assessment software.
>
> **Compatibility:** this public package targets QGIS 3.x. QGIS 4 compatibility work is in progress and should be tested separately before declaring the plugin QGIS 4-ready.

---

## What Velantis Wind does

| Module | Purpose | Main outputs |
|---|---|---|
| **Energy / AEP** | Estimate wind-farm production with PyWake-compatible workflows and GIS inputs. | Gross/free AEP, wake-reduced AEP, wake/TI/blockage diagnostics, per-turbine table, sector summaries, HTML/CSV reports and QGIS layers. |
| **Noise** | Run preliminary wind-turbine noise screening with fast and ISO-aligned octave-band engines. | Receiver levels, margins, compliance tables, critical receiver, noise raster, isophones and source-receptor links. |
| **Shadow Flicker** | Estimate preliminary shadow/flicker impact using turbine, receptor, terrain and solar-geometry inputs. | Annual hours, real/adjusted hours, affected days, monthly/hourly matrices, receptor layer and raster map. |

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

On Windows / OSGeo4W, close QGIS, open **OSGeo4W Shell** and run:

```bash
python -m pip install py_wake==2.6.18
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Then restart QGIS and install or enable VelantisWind.

Detailed installation guide:

- [`docs/INSTALL_OSGEO4W_PYWAKE.md`](docs/INSTALL_OSGEO4W_PYWAKE.md)
- [`docs/INSTALL_ENERGY_DEPENDENCIES.md`](docs/INSTALL_ENERGY_DEPENDENCIES.md)

---

## Quick start

### Energy / AEP

1. Load or create a turbine point layer, or prepare a layout CSV.
2. Open **Velantis Wind → Energy / AEP**.
3. Select turbine model/curve, layout input and wind-resource input.
4. Select wake model and optional physics settings.
5. Run the calculation.
6. Review AEP, losses, sector summaries and per-turbine outputs.
7. Export HTML/CSV reports if needed.

### Noise

1. Load turbine source layer(s).
2. Load a receptor layer.
3. Open **Velantis Wind → Noise**.
4. Select fast or ISO-aligned engine.
5. Set source level/curve, receptor height, radius and optional DEM/DSM or land-use layer.
6. Run the calculation.
7. Review compliance, critical receiver, raster and isophones.

### Shadow Flicker

1. Load turbine and receptor layers.
2. Optionally load a DEM/DSM.
3. Open **Velantis Wind → Shadow Flicker**.
4. Set observer height, time step, year/time assumptions and raster options.
5. Run the calculation.
6. Review annual hours, real/adjusted hours, monthly tables and raster outputs.

---

## Repository layout

```text
VelantisWind/
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

### Architecture

- [`docs/ENERGY_ARCHITECTURE.md`](docs/ENERGY_ARCHITECTURE.md)
- [`docs/NOISE_ARCHITECTURE.md`](docs/NOISE_ARCHITECTURE.md)
- [`docs/SHADOW_ARCHITECTURE.md`](docs/SHADOW_ARCHITECTURE.md)

### Testing and publication

- [`docs/EXPERIMENTAL_TESTING_GUIDE.md`](docs/EXPERIMENTAL_TESTING_GUIDE.md)
- [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md)
- [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)
- [`docs/PUBLISHING_QGIS.md`](docs/PUBLISHING_QGIS.md)
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

See [`docs/PUBLISHING_QGIS.md`](docs/PUBLISHING_QGIS.md) and [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

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
