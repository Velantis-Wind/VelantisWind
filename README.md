# VelantisWind

> Open-source wind-farm pre-assessment workflows directly inside QGIS.

VelantisWind is an experimental QGIS plugin for early-stage wind-farm analysis, GIS-based validation and technical screening. It brings together Energy/AEP, wake-aware evaluation, Noise and Shadow Flicker workflows, plus interactive turbine-layout tools.

## Release 0.1.16

- Per-model elliptical spacing envelopes with WRG-based orientation, automatic creation after CSV imports, cross-model conflict validation and optional insertion blocking.
- Searchable catalogue of 42 turbine screening candidates with explicit quality, provenance and limitations.
- More robust Noise and Shadow Flicker raster processing on affected QGIS/Windows installations.
- Dependency-free, atomic Noise XLSX export.
- Independent AEP symbology and within-model performance/rank fields on turbine layers.
- Interactive Map and spacing workflow localization in Spanish, English, French and German.

Read the complete [0.1.16 changelog](VelantisWind/CHANGELOG.md).

## Main workflows

| Workflow | Purpose |
|---|---|
| Energy / AEP | Estimate gross/free and wake-reduced production using PyWake-compatible workflows and GIS inputs. |
| Turbine catalogue | Load public/reference curves or clearly labelled screening approximations, then edit or replace them with project data. |
| Interactive Map | Create and manage turbine layouts directly in QGIS. |
| Spacing envelopes | Visualize model-specific separation ellipses, identify conflicts and export the validation layers. |
| Noise | Run preliminary receiver and raster screening with fast and ISO-aligned octave-band engines. |
| Shadow Flicker | Estimate preliminary receptor and raster impacts using solar geometry, turbine geometry and optional terrain inputs. |

VelantisWind is intended to complement professional engineering workflows, not replace project-specific validation, OEM data or specialist judgement.

## Installation

### 1. Install the Energy dependency

The Energy/AEP module requires PyWake in the same Python environment used by QGIS. On Windows, close QGIS, open **OSGeo4W Shell** and run:

```bash
python -m pip install py_wake==2.6.18
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Noise and Shadow Flicker can be tested without PyWake.

### 2. Install the plugin ZIP

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select `VelantisWind-0.1.16.zip`.
4. Enable **Velantis Wind**.

The ZIP must contain one top-level folder named `VelantisWind`.

## Documentation

- [Quick start](VelantisWind/docs/QUICKSTART.md)
- [Energy/AEP guide](VelantisWind/docs/ENERGY_MODULE.md)
- [Noise guide](VelantisWind/docs/NOISE_MODULE.md)
- [Shadow Flicker guide](VelantisWind/docs/SHADOW_FLICKER_MODULE.md)
- [Spacing Envelope guide](VelantisWind/docs/SPACING_ENVELOPE_MODULE.md)
- [Known limitations](VelantisWind/docs/LIMITATIONS.md)
- [Troubleshooting](VelantisWind/docs/TROUBLESHOOTING.md)
- [Release test checklist](VelantisWind/docs/RELEASE_TEST_CHECKLIST.md)
- [QGIS 4 smoke test](VelantisWind/docs/QGIS4_SMOKE_TEST.md)

The complete plugin documentation is also available inside [`VelantisWind/README.md`](VelantisWind/README.md).

## Repository structure

```text
VelantisWind/
├─ .github/                 # GitHub workflows and templates
├─ VelantisWind/            # Installable QGIS plugin folder
│  ├─ metadata.txt
│  ├─ plugin.py
│  ├─ ag_core/
│  ├─ energy_core/
│  ├─ spacing_core/
│  ├─ noise_core/
│  ├─ shadow_core/
│  ├─ resources/
│  └─ docs/
├─ README.md
├─ CONTRIBUTING.md
├─ SUPPORT.md
└─ LICENSE
```

## Important limitations

- Experimental screening software; not certified regulatory, permitting or bankable assessment software.
- QGIS 4 / Qt6 compatibility remains experimental and requires validation on real installations.
- Spec-based and generic turbine curves are Velantis approximations, not OEM-certified power or CT curves.
- Energy results depend on resource quality, turbine data and selected wake/turbulence/blockage assumptions.
- Noise and Shadow Flicker workflows include documented simplifications and require independent review before formal use.

## Contributing and support

Bug reports, validation cases, documentation improvements, translations and technical contributions are welcome. Please avoid sharing confidential project data in public issues.

For collaboration, validation cases, sponsorship or project-specific workflow discussions, contact **info@velantiswind.com**.

VelantisWind is released under **GPL-3.0-or-later**.
