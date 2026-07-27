# VelantisWind — QGIS Plugin

**Open-source wind-farm pre-assessment, layout validation and technical screening directly inside QGIS.**

VelantisWind is an experimental QGIS plugin for early-stage wind-farm analysis. It brings together **Energy / AEP**, wake-aware evaluation, interactive turbine-layout tools, model-specific spacing validation, **Noise** and **Shadow Flicker** workflows in one GIS-based environment.

> **Status:** experimental release. VelantisWind is intended for screening, layout comparison, GIS-based QA/QC, workflow validation and technical feedback. It is **not** certified regulatory, permitting or bankable assessment software.
>
> **Compatibility:** the public package targets QGIS 3.x and QGIS 4.x. QGIS 4 / Qt6 support remains experimental and should be validated on real installations.

---

## What VelantisWind does

| Module | Purpose | Main outputs |
|---|---|---|
| **Energy / AEP** | Estimate wind-farm production with PyWake-compatible workflows and GIS inputs. | Gross/free AEP, wake-reduced AEP, wake/TI/blockage diagnostics, per-turbine results, sector summaries, HTML/CSV reports and QGIS layers. |
| **Interactive Map** | Create, import, edit and compare turbine layouts directly in QGIS. | Editable turbine layers, model-aware attributes, layout management and energy-based symbology. |
| **Spacing Envelopes** | Visualize and validate model-specific minimum turbine separation. | Elliptical envelopes, WRG-based orientation, cross-model conflict detection, warnings or insertion blocking, and exportable validation layers. |
| **Turbine Catalogue** | Load traceable public/reference curves or clearly labelled screening candidates. | Searchable turbine library, editable power/CT curves, quality and provenance labels, and project-layer metadata. |
| **Noise** | Run preliminary wind-turbine noise screening with fast and ISO-aligned octave-band engines. | Receiver levels, margins, compliance tables, critical receiver, raster maps, isophones, source-receptor links and XLSX/HTML/TXT outputs. |
| **Shadow Flicker** | Estimate preliminary shadow/flicker impact using turbine, receptor, terrain and solar-geometry inputs. | Annual and adjusted hours, affected days, monthly/hourly matrices, receptor layers and raster maps. |

VelantisWind is designed for transparent pre-assessment, layout iteration and technical validation against established workflows. Users should document all assumptions and independently verify outputs before using them in formal studies.

---

## Why use VelantisWind?

- **GIS-native workflow:** keep layouts, receptors, terrain, resource data and results in the same QGIS project.
- **Open and inspectable:** review the workflow, assumptions and outputs instead of relying on a closed black box.
- **Modular:** use Energy/AEP, Noise or Shadow Flicker independently.
- **Layout-aware:** create and compare turbine configurations directly on the map.
- **Model-aware spacing:** validate elliptical separation envelopes for mixed turbine models.
- **Editable turbine data:** replace screening curves with project-specific or OEM data when available.
- **Designed for validation:** export tables, reports and QGIS layers for comparison with professional tools.

---

## Release 0.1.16

Version 0.1.16 consolidates the latest public improvements into a single release.

### Main additions

- Added one independent **elliptical spacing-envelope layer per turbine model/source layer**.
- Added automatic envelope creation or refresh after turbine CSV imports.
- Added WRG-based orientation using the most energetic wind sector, with manual fallback.
- Added cross-model conflict validation and optional insertion blocking.
- Added an explicit **Apply new configuration** workflow for spacing parameters.
- Added a searchable catalogue of **42 turbine screening candidates**:
  - 4 public/reference curves.
  - 8 specification-based approximations.
  - 30 manufacturer-neutral generic classes.
- Added visible turbine-curve quality, source and provenance information.
- Added within-model AEP, performance and rank fields for turbine-layer symbology.
- Reworked Noise and Shadow Flicker raster I/O to avoid dependence on GDAL's optional NumPy bridge.
- Replaced the Noise XLSX export path with a lightweight standard-library OOXML writer.
- Expanded Spanish, English, French and German localization across the Interactive Map and spacing workflows.

See the complete [0.1.16 changelog](VelantisWind/CHANGELOG.md).

---

## Installation

### Option A — Install from ZIP in QGIS

1. Download `VelantisWind-0.1.16.zip`.
2. Open QGIS.
3. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
4. Select the downloaded ZIP.
5. Enable **Velantis Wind**.
6. Open the plugin from the toolbar or the Plugins menu.

The ZIP must contain one top-level folder named `VelantisWind`.

### Option B — Manual installation

Copy the `VelantisWind` plugin folder into your QGIS profile plugin directory:

```text
QGIS3/profiles/default/python/plugins/VelantisWind/
```

Restart QGIS and enable **Velantis Wind** from the Plugin Manager.

### Energy / AEP dependency

The Energy/AEP module requires **PyWake** in the same Python environment used by QGIS. PyWake is not bundled with the plugin.

On Windows, close QGIS, open **OSGeo4W Shell** and run:

```bash
python -m pip install py_wake==2.6.18
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Restart QGIS after installation.

Noise and Shadow Flicker can be tested without PyWake.

Detailed installation guides:

- [OSGeo4W / PyWake installation](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
- [Energy dependencies](VelantisWind/docs/INSTALL_ENERGY_DEPENDENCIES.md)
- [Troubleshooting](VelantisWind/docs/TROUBLESHOOTING.md)

---

## Quick start

### Energy / AEP

1. Load or create a turbine point layer, or prepare a turbine-layout CSV.
2. Open **Velantis Wind → Energy / AEP**.
3. Select the turbine model or load a custom power/CT curve.
4. Select the layout and wind-resource input.
5. Configure the wake model and optional turbulence, blockage and rotor-averaging settings.
6. Run the calculation.
7. Review AEP, wake losses, sector summaries and per-turbine results.
8. Export the reports and QGIS result layers.

### Interactive Map and spacing validation

1. Open the **Interactive Map**.
2. Import a layout CSV or add turbines directly on the map.
3. Select the turbine model and spacing configuration.
4. Apply the longitudinal spacing, crosswind spacing and orientation settings.
5. Review the generated semi-transparent ellipses.
6. Inspect near-limit and conflict states across all compatible turbine layers.
7. Move, add or remove turbines and refresh the validation.
8. Export the envelope layers to GeoPackage when needed.

### Noise

1. Open **Velantis Wind → Noise**.
2. Select an existing turbine layer or import a turbine-layout CSV.
3. Define the acoustic source data.
4. Load receptor points.
5. Select the fast or ISO-aligned octave-band engine.
6. Configure source level, receptor height, radius and optional DEM/DSM or land-use inputs.
7. Run the calculation.
8. Review receiver levels, margins, critical receiver, raster and isophones.
9. Export HTML, TXT or XLSX results.

### Shadow Flicker

1. Open **Velantis Wind → Shadow Flicker**.
2. Select an existing turbine layer or import a turbine-layout CSV.
3. Define turbine geometry.
4. Load receptor layers and optionally a DEM/DSM.
5. Set observer height, time step, year/time assumptions and raster options.
6. Run the calculation.
7. Review annual hours, adjusted hours, affected days, monthly tables and raster outputs.

---

## Turbine catalogue and curve provenance

The packaged catalogue contains 42 candidates intended for screening and workflow testing.

### Public/reference curves

These entries are based on traceable public or benchmark sources:

- V80 Horns Rev 1 / PyWake.
- IEA Task 37 3.35 MW benchmark turbine.
- IEA 10 MW reference turbine.
- IEA 15 MW reference turbine.

### Specification-based approximations

These entries use public geometry, rating and operating points where available, but their packaged power and CT curves are **Velantis parametric approximations**, not OEM-certified curves.

### Manufacturer-neutral generic classes

These entries represent generic onshore and offshore size classes for early-stage screening. They are not intended to represent a specific commercial turbine.

Users should replace packaged screening data with project-specific or OEM-approved data whenever formal accuracy is required.

---

## Architecture at a glance

The modules follow the same broad pattern:

```text
UI → controller → configuration / validation → engine → results → QGIS outputs
```

Main package areas:

```text
VelantisWind/
├─ plugin.py                 # QGIS plugin entry point
├─ hub_dialog.py             # Main VelantisWind hub
├─ aep_setup_dialog.py       # Energy / AEP interface
├─ mapa_interactivo*.py      # Interactive layout tools
├─ noise_page.py             # Noise interface
├─ shadow_page.py            # Shadow Flicker interface
│
├─ energy_core/              # Energy state, validation, controller and runner
├─ ag_core/                  # Energy engine, PyWake helpers and QGIS outputs
├─ spacing_core/             # Spacing envelopes, geometry and map tools
├─ noise_core/               # Noise engines, raster and reporting
├─ shadow_core/              # Solar geometry, calculation, raster and outputs
├─ ui_core/                  # Shared Qt/QGIS helpers
├─ resources/                # Turbine catalogue and packaged curves
├─ assets/                   # Icons and bundled fallback data
└─ docs/                     # User guides, architecture and release checks
```

Optional developer diagnostics are quiet by default. To print additional diagnostics to the QGIS/Python console, start QGIS with:

```bash
set VELANTISWIND_DEBUG=1
```

On Linux/macOS:

```bash
export VELANTISWIND_DEBUG=1
```

---

## Documentation

### Start here

- [Quick start](VelantisWind/docs/QUICKSTART.md)
- [OSGeo4W / PyWake installation](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
- [Troubleshooting](VelantisWind/docs/TROUBLESHOOTING.md)
- [Known limitations](VelantisWind/docs/LIMITATIONS.md)

### Module guides

- [Energy / AEP](VelantisWind/docs/ENERGY_MODULE.md)
- [Noise](VelantisWind/docs/NOISE_MODULE.md)
- [Shadow Flicker](VelantisWind/docs/SHADOW_FLICKER_MODULE.md)
- [Spacing Envelopes](VelantisWind/docs/SPACING_ENVELOPE_MODULE.md)
- [Turbine Library](VelantisWind/docs/TURBINE_LIBRARY.md)

### Architecture and development

- [Energy architecture](VelantisWind/docs/ENERGY_ARCHITECTURE.md)
- [Noise architecture](VelantisWind/docs/NOISE_ARCHITECTURE.md)
- [Shadow Flicker architecture](VelantisWind/docs/SHADOW_ARCHITECTURE.md)
- [Spacing Envelope architecture](VelantisWind/docs/SPACING_ENVELOPE_ARCHITECTURE.md)

### Testing and publication

- [Release test checklist](VelantisWind/docs/RELEASE_TEST_CHECKLIST.md)
- [QGIS 4 smoke test](VelantisWind/docs/QGIS4_SMOKE_TEST.md)
- [Turbine curve QA](VelantisWind/docs/TURBINE_CURVE_QA_0_1_16.md)

The full plugin-level documentation is also available in [`VelantisWind/README.md`](VelantisWind/README.md).

---

## Important limitations

### General

- VelantisWind is experimental software.
- APIs, interfaces and reports may continue to evolve.
- Results depend strongly on GIS layers, CRS, wind-resource data, terrain data and turbine/acoustic inputs.
- Users should independently verify assumptions and outputs before using them in formal studies.

### Energy / AEP

- Requires PyWake in the QGIS Python environment.
- Results depend on resource quality, turbine curves, wake model, turbulence assumptions, blockage options and rotor-averaging settings.
- Wake-reduced AEP is not a complete bankable net-energy assessment unless availability, electrical losses, curtailment, icing, environmental losses and other project losses are handled separately.

### Turbine curves

- Specification-based and generic curves are screening approximations.
- They are not OEM-certified power or CT curves.
- Curve provenance is shown in the plugin and persisted on generated turbine layers.

### Spacing envelopes

- Spacing envelopes are geometric validation tools, not a substitute for the complete civil, geotechnical, electrical, constructability, load or permitting constraints of a real project.
- Automatic WRG orientation depends on the quality and availability of the loaded wind resource.

### Noise

- The Noise workflow is intended for preliminary screening.
- It is not certified regulatory noise software.
- Atmospheric absorption, ground effect, topographic screening, directivity and long-term meteorological correction include documented simplifications.

### Shadow Flicker

- DEM/DSM inputs adjust absolute elevations for turbines, receptors and raster cells.
- Full intermediate terrain-obstruction or line-of-sight blocking is not yet implemented.
- Fine-resolution raster calculations may be computationally demanding.

See [Known limitations](VelantisWind/docs/LIMITATIONS.md) for the complete list.

---

## Contributing, validation and support

Bug reports, validation cases, documentation improvements, translations and technical contributions are welcome.

When reporting a bug, include:

- QGIS version.
- Operating system.
- VelantisWind version.
- Module used.
- Input summary.
- Screenshots.
- Full Python traceback when available.

Please do not share confidential project data in public issues.

VelantisWind is free and open source. Optional support helps fund maintenance, validation, documentation, translations, QGIS compatibility and improvements across the Energy/AEP, Noise and Shadow Flicker modules.

Possible forms of collaboration include:

- Technical feedback and beta testing.
- Reproducible validation cases.
- Academic or research collaboration.
- Workflow adaptation.
- Sponsorship.
- Project-specific layout and wake-steering optimization studies.

For collaboration, validation cases, sponsorship or project-specific workflows, contact **info@velantiswind.com**.

---

## License

VelantisWind is released under **GPL-3.0-or-later**. See [`VelantisWind/LICENSE`](VelantisWind/LICENSE).
