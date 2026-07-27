# VelantisWind

**Open-source wind-farm pre-assessment, layout validation and technical screening directly inside QGIS.**

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632?logo=qgis&logoColor=white)](https://qgis.org/)
[![QGIS 4](https://img.shields.io/badge/QGIS%204-experimental-orange)](VelantisWind/docs/QGIS4_SMOKE_TEST.md)
[![PyWake](https://img.shields.io/badge/PyWake-2.6.18-blue)](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
[![Version](https://img.shields.io/badge/version-0.1.16-blue)](https://github.com/Velantis-Wind/VelantisWind/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)
[![Languages](https://img.shields.io/badge/UI-ES%20%7C%20EN%20%7C%20FR%20%7C%20DE-lightgrey)](VelantisWind/docs/QUICKSTART.md)

VelantisWind is an experimental QGIS plugin for early-stage wind-farm analysis. It combines:

- **Energy / AEP assessment with PyWake**
- **Wake, turbulence and blockage model comparison**
- **Interactive turbine-layout creation and editing**
- **Model-specific turbine-spacing validation**
- **Preliminary Noise assessment**
- **Preliminary Shadow Flicker assessment**

The objective is to keep project inputs, engineering assumptions, calculations and outputs connected to the same QGIS project, making wind-farm screening more transparent, reproducible and easier to review.

> [!IMPORTANT]
> VelantisWind is experimental software intended for technical screening, layout comparison, GIS-based QA/QC, workflow validation, research and technical feedback.
>
> It is **not** certified regulatory, permitting or bankable assessment software. Results must be independently reviewed before being used in formal engineering studies.

> [!NOTE]
> The plugin supports QGIS 3.28 and later. Qt5/Qt6 compatibility work is included, but QGIS 4 support remains experimental and should be tested on real installations and project workflows.

---

## Main workflows

| Module | Purpose | Main outputs |
|---|---|---|
| **Energy / AEP** | Estimate and compare wind-farm production using sectoral wind-resource data, turbine power/CT curves and configurable PyWake engineering models. | Gross/free AEP, wake-reduced AEP, wake losses, per-turbine production, sector summaries, model diagnostics, reports and styled QGIS layers. |
| **Interactive Map** | Create, import, edit and compare turbine layouts directly inside QGIS. | Editable turbine layers, model-aware attributes, layout management, project-linked coordinate layers and energy-based symbology. |
| **Spacing Envelopes** | Visualize and validate turbine separation using model-specific elliptical envelopes. | WRG-oriented ellipses, cross-model conflict validation, insertion warnings or blocking, per-turbine overrides and GeoPackage export. |
| **Turbine Catalogue** | Load traceable public/reference curves or clearly labelled screening candidates. | Searchable turbine library, editable power/CT curves, provenance information and model metadata. |
| **Noise** | Perform preliminary wind-turbine noise screening with fast and ISO-aligned octave-band workflows. | Receiver levels, compliance margins, critical receptors, raster maps, isophones, source-receptor links and XLSX/HTML/TXT outputs. |
| **Shadow Flicker** | Estimate potential flicker using solar geometry, turbine geometry, receptors, time assumptions and optional terrain elevations. | Annual and adjusted hours, affected days, monthly/hourly matrices, receptor layers and raster maps. |

---

## Why VelantisWind?

- **GIS-native workflow:** layouts, receptors, wind-resource grids, terrain data and results remain inside QGIS.
- **Open and inspectable:** model assumptions and calculation paths can be reviewed instead of being hidden behind a closed workflow.
- **Configurable Energy model chain:** wake deficit, superposition, rotor averaging, turbulence, blockage and propagation assumptions can be compared.
- **Per-turbine diagnostics:** identify strongly waked or lower-performing turbines through calculated attributes and map symbology.
- **Interactive layout editing:** add, move, remove and compare turbines directly on the map.
- **Mixed-model support:** manage separate turbine models, rotor diameters, curves, layouts and spacing criteria.
- **Model-aware spacing:** validate longitudinal and crosswind separation using elliptical envelopes.
- **Editable turbine data:** replace packaged screening curves with project-specific or OEM information.
- **Modular use:** Energy/AEP, Noise and Shadow Flicker can be used independently.
- **Designed for validation:** export tables, reports and GIS layers for comparison with established engineering tools.
- **Multilingual interface:** Spanish, English, French and German.

VelantisWind is intended to complement professional wind-energy workflows, not replace specialist judgement, project-specific validation or certified software.

---

## Release 0.1.16

Version 0.1.16 consolidates the latest public developments into one release.

### Main additions

- Added one independent **elliptical spacing-envelope layer per turbine model or source layer**.
- Added automatic envelope creation and refresh after turbine CSV imports.
- Added automatic envelope orientation towards the most energetic sector of the loaded WRG.
- Added manual orientation fallback when no suitable resource is available.
- Added cross-model spacing-conflict validation.
- Added optional insertion blocking when a new turbine violates the selected spacing criteria.
- Added an explicit **Apply new configuration** action for model-wide spacing parameters.
- Added a searchable catalogue of **42 turbine screening candidates**:
  - 4 public/reference curves.
  - 8 specification-based approximations.
  - 30 manufacturer-neutral generic classes.
- Added visible curve-quality, source and provenance information.
- Added individual AEP, within-model performance and ranking fields to turbine layers.
- Added energy-based graduated symbology for each turbine-model layer.
- Reworked Noise and Shadow Flicker raster I/O to avoid reliance on GDAL's optional NumPy bridge.
- Replaced the previous Noise XLSX dependency path with a lightweight standard-library OOXML writer.
- Expanded Spanish, English, French and German localization across the Interactive Map and spacing workflows.
- Added documentation for turbine curves, spacing envelopes and QGIS compatibility testing.

See the complete [0.1.16 changelog](VelantisWind/CHANGELOG.md).

---

# Energy / AEP assessment

The Energy module provides a GIS-based interface for estimating wind-farm production and studying turbine interactions with configurable PyWake engineering models.

It is intended for:

- Early-stage energy screening.
- Comparison of alternative turbine layouts.
- Wake-loss assessment.
- Per-turbine performance analysis.
- Mixed-model wind-farm studies.
- Sensitivity analysis between engineering models.
- Comparison with other wind-energy software.
- Reproducible benchmarks.
- Research and teaching workflows.
- Preparation of inputs and outputs for more detailed engineering studies.

## Energy calculation chain

A typical calculation combines:

```text
Wind-resource input
        ↓
Turbine positions and model assignment
        ↓
Rotor diameter and hub height
        ↓
Power and thrust-coefficient curves
        ↓
Wind-farm model engine
        ↓
Wake-deficit model
        ↓
Wake-superposition model
        ↓
Rotor-averaging model
        ↓
Optional added-turbulence model
        ↓
Optional blockage / induction model
        ↓
Per-turbine and wind-farm AEP results
```

VelantisWind keeps these components visible and configurable so that alternative model chains can be compared within the same QGIS project.

---

## Wind-resource inputs

The Energy module supports two principal resource workflows.

### WAsP / GridSite-style resource

A folder containing the sectoral grid information required by the PyWake-compatible resource loader.

This workflow is intended for wind-resource data already exported or prepared as compatible sectoral grids.

### WRG / ZIP resource

A `.wrg` file or ZIP package containing spatially distributed sectoral wind-resource information.

Depending on the source, the resource can contain:

- Wind-direction sectors.
- Sector frequencies.
- Weibull `A` parameters.
- Weibull `k` parameters.
- Mean wind speed.
- Multiple resource heights.
- Projected coordinates.
- CRS information.
- Spatially varying resource values.

### Turbulence-intensity rasters

WRG workflows can optionally include:

- One TI raster.
- Several TI rasters at different heights.
- Explicit TI-height values.
- Heights inferred from file names where possible.
- Interpolation of ambient TI by turbine hub height.
- A manually defined uniform TI fallback when no raster is supplied.

Ambient turbulence and wake-added turbulence are different quantities:

```text
Ambient TI
    Wind variability arriving at the wind farm.
    Obtained from the resource, TI rasters or a manual fallback.

Wake-added TI
    Additional turbulence generated behind operating turbines.
    Estimated by the selected PyWake turbulence model.
```

Loading a TI raster does not automatically guarantee a large change in AEP. The selected wake model must also use turbulence intensity in its wake-expansion or recovery formulation.

The quality and representativeness of the wind resource remain major factors controlling result reliability. VelantisWind does not remove uncertainty associated with measurement campaigns, long-term correction, vertical extrapolation, spatial modelling or climate variability.

---

## Turbine layouts

A layout can be supplied through:

- The Interactive Map.
- An existing QGIS point layer.
- A CSV coordinate file.
- One coordinate source per turbine model.
- Several separate turbine-model layers in the same project.

Recommended coordinate fields include:

```text
x,y
```

or:

```text
easting,northing
```

Use a projected CRS in metres. Geographic longitude/latitude coordinates should be reprojected before wake-distance calculations.

---

## Turbine data

Each model can include:

- Turbine name.
- Rated power.
- Rotor diameter.
- Hub height.
- Power curve.
- Thrust-coefficient curve.
- Longitudinal spacing.
- Crosswind spacing.
- Curve quality.
- Curve source.
- Curve source URL.
- User-edit status.

Users can:

- Select a packaged turbine candidate.
- Load a public/reference curve.
- Use a specification-based approximation.
- Select a manufacturer-neutral generic class.
- Import custom power and CT curves.
- Edit packaged curves.
- Define a custom turbine manually.
- Use different turbine models in the same project.
- Persist turbine and curve provenance on generated QGIS layers.

Packaged generic and specification-based curves are intended for screening and workflow testing. Replace them with project-specific or OEM-approved data whenever formal accuracy is required.

---

## PyWake model configuration

The public Energy interface exposes the following model options.

| Component | Options exposed in VelantisWind 0.1.16 |
|---|---|
| **Wind-farm model engine** | `All2AllIterative`, `PropagateDownwind`, `PropagateUpDownIterative` |
| **Wake-deficit model** | `NOJDeficit`, `TurboNOJDeficit`, `BastankhahGaussianDeficit`, `NiayifarGaussianDeficit`, `TurboGaussianDeficit`, `ZongGaussianDeficit` |
| **Wake superposition** | Automatic, `LinearSum`, `SquaredSum`, `MaxSum`, `WeightedSum` |
| **Rotor averaging** | None, `RotorCenter`, `CGIRotorAvg(7)`, `CGIRotorAvg(9)`, `CGIRotorAvg(21)`, `EqGridRotorAvg` |
| **Added turbulence** | None, `STF2005TurbulenceModel`, `STF2017TurbulenceModel`, `GCLTurbulence`, `CrespoHernandez` |
| **Blockage / induction** | None, `SelfSimilarityDeficit2020`, `SelfSimilarityDeficit`, `VortexCylinder`, `VortexDipole`, `HybridInduction` |

Exact class availability can depend on the installed PyWake version. When a selected class or model combination is unavailable, VelantisWind attempts a conservative fallback and records warnings or configuration notes.

Internal compatibility classes and legacy fallbacks that are not selectable in the normal interface are not presented here as public model options.

---

## Wind-farm model engines

### All2AllIterative

`All2AllIterative` resolves turbine interactions iteratively across the wind farm.

It is useful for model chains where turbine effects cannot be evaluated only through a simple downstream sequence.

Typical uses include:

- Iterative turbine-interaction calculations.
- Selected blockage configurations.
- Model combinations that require effective wind speed to be updated repeatedly.

### PropagateDownwind

`PropagateDownwind` evaluates turbine interactions following the downstream flow direction.

It is generally:

- Fast.
- Suitable for conventional wake-only calculations.
- Useful for screening and repeated layout comparisons.
- Appropriate for many large-layout calculations.

`PropagateDownwind` does not apply upstream blockage in the VelantisWind workflow. If blockage is enabled with this engine, the plugin disables it automatically and reports the change.

### PropagateUpDownIterative

`PropagateUpDownIterative` supports model chains containing both downstream wakes and upstream induction or blockage.

When this engine is selected, VelantisWind attempts to enable:

```text
use_effective_ws=True
```

for wake and blockage models that support the parameter.

Availability and convergence depend on the selected models and the installed PyWake version.

---

## Wake-deficit models

### NOJDeficit

A classical Jensen/NOJ top-hat wake model.

Main characteristics:

- Simple and computationally efficient.
- Uses a linearly expanding wake.
- Suitable for rapid screening and repeated layout comparison.
- Uses a configurable wake-expansion coefficient `k`.
- Ambient TI has limited direct influence on the default formulation.

It is useful when calculation speed and transparency are more important than detailed cross-wake representation.

### TurboNOJDeficit

A turbulence-sensitive extension of the NOJ family.

Main characteristics:

- Retains a relatively lightweight NOJ-style formulation.
- Allows effective turbulence to influence wake expansion.
- More sensitive to ambient and wake-added TI than standard NOJ.
- Exposes compatible `A` and `cTI` coefficients as advanced settings.

### BastankhahGaussianDeficit

A classical Gaussian engineering wake model.

Main characteristics:

- Represents a velocity deficit that varies across the wake section.
- Produces smoother full-wake and partial-wake transitions than a top-hat model.
- Useful as a general reference for layout comparison.
- Exposes wake-expansion and initial-width parameters.

Bastankhah is the principal configuration for which `WeightedSum` is retained when the complete model chain is considered safe.

### NiayifarGaussianDeficit

A turbulence-dependent Gaussian formulation based on the Bastankhah family.

Main characteristics:

- Uses turbulence intensity in wake-expansion behaviour.
- More sensitive to ambient TI and effective TI.
- Particularly relevant when TI rasters or several TI heights are available.
- Can be combined with an added-turbulence model when appropriate.

### TurboGaussianDeficit

A TI-driven Gaussian wake model.

Main characteristics:

- Uses effective turbulence to influence wake expansion.
- Exposes compatible `A`, `cTI` and initial-width coefficients.
- Useful for sensitivity studies where ambient and added turbulence should influence wake recovery.

### ZongGaussianDeficit

An advanced turbulence-sensitive Gaussian formulation.

Main characteristics:

- Includes additional near-wake and wake-development parameters.
- Uses effective turbulence in its formulation.
- Requires a wake-added turbulence model in the VelantisWind workflow.

If Zong is selected while turbulence is set to None, VelantisWind automatically enables `STF2017TurbulenceModel` and records the compatibility adjustment.

---

## Advanced wake parameters

VelantisWind exposes configurable parameters for each public wake model.

| Wake model | Advanced parameters |
|---|---|
| `NOJDeficit` | `k` |
| `BastankhahGaussianDeficit` | `k`, `cεps` |
| `NiayifarGaussianDeficit` | `a₁`, `a₂`, `cεps` |
| `TurboNOJDeficit` | `A`, `cTI[0]`, `cTI[1]` |
| `TurboGaussianDeficit` | `A`, `cTI[0]`, `cTI[1]`, `cεps` |
| `ZongGaussianDeficit` | `a₁`, `a₂`, `δw/D`, `ε coefficient`, `λ`, number of blades `B` |

Grouped parameters are passed to PyWake in the form expected by the selected class, for example:

```text
a = [a₁, a₂]
cTI = [cTI[0], cTI[1]]
```

Advanced values are only passed when the installed PyWake class accepts the corresponding argument.

Changing advanced coefficients can materially alter wake losses. Values should be modified only when there is a documented technical basis, calibration case or sensitivity objective.

---

## Wake superposition

When several upstream wakes affect the same turbine, their deficits must be combined.

VelantisWind exposes:

### Automatic

The plugin selects a conservative superposition model based on:

- Wake-deficit family.
- Rotor-averaging configuration.
- Blockage status.
- PyWake compatibility.

### LinearSum

Adds wake deficits directly.

It can produce stronger accumulated losses in dense multi-wake situations.

It is also the only public superposition method used by VelantisWind when blockage is active, because blockage models can produce signed upstream speedups.

### SquaredSum

Combines wake deficits using a quadratic sum.

It is used as a robust automatic choice for many compatible wake-only calculations.

### MaxSum

Uses the strongest individual wake contribution.

It can be useful for diagnostic comparison but may underrepresent accumulated multi-wake effects.

### WeightedSum

A weighted Gaussian superposition formulation.

Although the selector is presented for Gaussian workflows, VelantisWind retains it only when the runtime configuration is considered numerically safe, primarily with classical `BastankhahGaussianDeficit`.

TI-driven Gaussian variants such as Niayifar, TurboGaussian and Zong are redirected to a safer automatic alternative when necessary.

---

## Rotor averaging

Rotor averaging controls how the effective wind speed is evaluated over the turbine rotor.

### None

No explicit rotor-average model is supplied.

### RotorCenter

Evaluates the wake at the centre of the rotor.

It is fast but can simplify partial-wake conditions.

### CGIRotorAvg

VelantisWind exposes:

- `CGIRotorAvg(7)`
- `CGIRotorAvg(9)`
- `CGIRotorAvg(21)`

Increasing the number of evaluation points can provide a more detailed representation of rotor-disc exposure, with a corresponding increase in calculation time.

### EqGridRotorAvg

Evaluates the rotor using a uniform grid-based approach.

Rotor averaging can be relevant for:

- Partial wakes.
- Wake-edge interactions.
- Large rotors.
- Closely spaced rows.
- Mixed rotor diameters.

Legacy Gaussian-overlap settings are not exposed in this release and are redirected to `CGIRotorAvg(7)` for compatibility.

---

## Added-turbulence models

The turbulence selector estimates wake-added turbulence. It does not replace ambient TI from the resource.

### STF2005TurbulenceModel

A classical Frandsen-based engineering turbulence formulation.

It can be useful for comparison with older or more conservative configurations.

### STF2017TurbulenceModel

The principal general-purpose added-turbulence option in the current workflow.

It is also used as the first fallback when a turbulence-sensitive wake model requires added turbulence.

### GCLTurbulence

An alternative engineering formulation available for comparison and compatibility studies.

### CrespoHernandez

A classical empirical wake-added turbulence formulation.

The effect of selecting an added-turbulence model depends on the selected wake model.

TI-sensitive wake models include:

- `TurboNOJDeficit`
- `NiayifarGaussianDeficit`
- `TurboGaussianDeficit`
- `ZongGaussianDeficit`

With models such as standard NOJ or classical Bastankhah, added turbulence may be useful as a diagnostic but may have less influence on the base AEP calculation.

Added-turbulence outputs are engineering estimates. They are not substitutes for detailed load simulations, fatigue assessment, site-suitability analysis or OEM review.

---

## Blockage and induction models

The public selector includes:

### SelfSimilarityDeficit2020

The principal self-similarity blockage option offered by the interface.

### SelfSimilarityDeficit

A legacy/classical self-similarity selection.

### VortexCylinder

An induction model based on a vortex-cylinder representation.

### VortexDipole

An alternative vortex-based induction approximation.

### HybridInduction

A hybrid induction formulation available in compatible PyWake installations.

Exact model availability and class resolution can vary across PyWake versions. If the selected model cannot be imported or instantiated, VelantisWind attempts a compatible self-similarity fallback or disables blockage with a recorded warning.

Blockage effects are generally smaller and more model-sensitive than conventional downstream wake losses. They should be interpreted carefully and compared across different assumptions.

---

## Automatic compatibility rules

VelantisWind applies compatibility rules to reduce invalid PyWake configurations.

### PropagateDownwind and blockage

```text
PropagateDownwind + blockage
    → blockage disabled automatically
```

### Blockage and superposition

```text
Any active blockage model
    → LinearSum forced
```

This is required because upstream induction can produce signed speedups that are not accepted by `SquaredSum`, `MaxSum` or the Gaussian-only `WeightedSum`.

### PropagateUpDownIterative

```text
PropagateUpDownIterative
    → use_effective_ws=True where supported
```

### Zong and turbulence

```text
ZongGaussianDeficit + no turbulence model
    → STF2017TurbulenceModel enabled automatically
```

### WeightedSum

```text
WeightedSum + incompatible wake model
    → safe automatic superposition fallback
```

### Missing PyWake classes

```text
Selected class unavailable
    → compatible fallback attempted
    → warning/configuration note recorded
```

The executed model chain should always be reviewed in the result summary, particularly when comparing against another tool.

---

## Main Energy outputs

The Energy workflow can produce:

- Gross or free-stream AEP.
- Wake-reduced operational AEP.
- Absolute wake losses.
- Percentage wake losses.
- Per-turbine gross AEP.
- Per-turbine wake-reduced AEP.
- Per-turbine wake losses.
- Results grouped by turbine model.
- Directional and sector summaries where available.
- Effective wind-speed diagnostics.
- Turbulence diagnostics when enabled.
- Blockage diagnostics when enabled.
- Rotor-average diagnostics where supported.
- Model-chain and fallback notes.
- Resource-domain extent overlay.
- Per-turbine CSV exports.
- Human-readable HTML-style reports.
- Updated QGIS turbine layers.
- Project-level summary layers.
- Individual AEP symbology.
- `model_perf_pct` fields.
- `model_rank` fields.

The model-relative performance fields allow turbines with different rated powers to be compared within their own turbine-model group.

Energy-based graduated symbology makes it possible to identify higher- and lower-performing turbines directly on the map.

---

## Scenario comparison

The Energy interface includes an A/B scenario comparator.

A typical workflow is:

```text
Run base case
    ↓
Save as Scenario A
    ↓
Modify layout, turbine model or physical configuration
    ↓
Run alternative case
    ↓
Save as Scenario B
    ↓
Compare A/B
```

The comparison reports global and model-level differences between the stored results.

This is intended for practical layout and model comparison, not formal uncertainty analysis.

---

## Interpreting Energy results

Wake-reduced AEP is not automatically equivalent to a complete project net-energy assessment.

Unless introduced separately, VelantisWind does not automatically include every project loss, such as:

- Turbine availability.
- Electrical losses.
- Grid losses.
- Curtailment.
- Icing.
- Blade degradation.
- Environmental shutdowns.
- Noise-related operating modes.
- Bat or bird curtailment.
- Grid restrictions.
- Long-term wind-resource uncertainty.
- Measurement uncertainty.
- Model uncertainty.
- Other contractual or operational losses.

The Energy module should be understood as a transparent GIS and engineering workflow for resource-based production and turbine-interaction assessment, rather than a complete bankable energy-yield assessment.

---

# Interactive Map

The Interactive Map provides tools for creating and reviewing turbine layouts directly inside QGIS.

Users can:

- Import coordinates from CSV.
- Generate turbine point layers.
- Add turbines directly on the map.
- Move existing turbines.
- Remove turbines.
- Work with several turbine models.
- Select models from the packaged catalogue.
- Use custom turbine curves.
- Edit turbine and spacing parameters.
- Review model metadata.
- Display AEP-based symbology.
- Keep layouts connected to the QGIS project.
- Select which turbine layers participate in the next AEP calculation.

The map workflow supports rapid layout iteration without repeatedly switching between QGIS and external coordinate-editing tools.

---

# Spacing Envelopes

The Spacing Envelope module provides geometric validation of turbine separation.

It uses semi-transparent ellipses representing:

- Longitudinal spacing.
- Crosswind spacing.
- Orientation.
- Turbine rotor diameter.

Default values are:

```text
7 D longitudinal
4 D crosswind
```

The values are editable and stored independently for each turbine model.

## Envelope geometry

Spacing distances are interpreted as centre-to-centre thresholds.

Each ellipse therefore uses:

```text
semi-major axis = longitudinal spacing / 2
semi-minor axis = crosswind spacing / 2
```

Two turbines exactly at the selected threshold have envelopes that touch. Turbines closer than the threshold produce overlapping envelopes.

## Automatic WRG orientation

The envelope can be aligned with the sector contributing the highest relative wind energy.

For each sector:

```text
Eₛ ∝ fₛ · Aₛ³ · Γ(1 + 3/kₛ)
```

where:

- `fₛ` is sector frequency.
- `Aₛ` is the Weibull scale parameter.
- `kₛ` is the Weibull shape parameter.

The ellipse is oriented towards the sector with the maximum relative third-moment contribution.

If no suitable WRG is available, the plugin uses the manually defined fallback angle.

## Per-model configuration

Each turbine model or source layer can have its own:

- Rotor diameter.
- Longitudinal spacing.
- Crosswind spacing.
- Orientation mode.
- Fallback angle.
- Linked envelope layer.
- Per-turbine overrides.

This allows mixed-model projects to be checked using physically different spacing dimensions.

## Automatic CSV synchronization

When a turbine coordinate CSV is converted into a point layer, VelantisWind:

1. Transfers the spacing configuration stored for that model.
2. Adds model and rotor metadata.
3. Creates or refreshes the linked envelope layer.
4. Recalculates conflicts against compatible turbine-model layers.

The Spacing Envelope panel does not need to be opened before importing the CSV.

## Conflict states

| Status | Meaning |
|---|---|
| **OK** | No spacing conflict. |
| **Near the limit** | Free distance is close to the selected threshold. |
| **Conflict** | Elliptical envelopes overlap. |

The validation level can be configured as:

- Visualization only.
- Warn on conflict.
- Block insertion on conflict.

## Define ellipse on screen

A three-click map tool allows a per-turbine ellipse to be defined directly on the QGIS canvas:

1. Select the turbine centre.
2. Define the major axis and orientation.
3. Define the minor axis.

During drawing:

- **Ctrl** enables angular snapping.
- **Shift** enables spacing increments in rotor-diameter units.
- **Esc** or right-click steps back or exits.

Screen-defined ellipses are stored as per-turbine overrides. They do not overwrite the model-wide template.

## GeoPackage export

Envelope layers can be exported to GeoPackage.

One output table is created per turbine model, preserving fields such as:

- Turbine feature ID.
- Source-layer ID.
- Model index.
- Model name.
- Longitudinal spacing.
- Crosswind spacing.
- Resolved angle.
- Orientation mode.
- Spacing status.

Spacing envelopes are geometric screening tools. They do not replace complete analysis of civil, geotechnical, electrical, construction, load, access, permitting or OEM-specific constraints.

---

# Turbine catalogue

VelantisWind 0.1.16 includes a searchable catalogue of **42 turbine screening candidates**.

## Public/reference curves

Four entries are based on traceable public or benchmark sources:

- V80 Horns Rev 1 / PyWake.
- IEA Task 37 3.35 MW benchmark turbine.
- IEA 10 MW reference turbine.
- IEA 15 MW reference turbine.

These entries support reproducible testing and benchmark comparison.

## Specification-based approximations

Eight candidates are anchored to publicly available technical specifications.

Public geometry, rated power and operating points are used where available, but the packaged power and CT curves remain **Velantis parametric approximations**.

They are not OEM-certified curves.

## Manufacturer-neutral generic classes

Thirty generic onshore and offshore classes cover a range of:

- Rated powers.
- Rotor diameters.
- Hub heights.
- Operating ranges.
- Onshore and offshore sizes.

They are intended for:

- Early-stage screening.
- Workflow testing.
- Layout comparison.
- Demonstration cases.
- Projects where the final turbine has not yet been selected.

They are not intended to impersonate a specific commercial turbine.

## Curve provenance

The plugin displays and stores:

- Curve-quality category.
- Source description.
- Source URL where available.
- Screening caveats.
- User-edit state.

When a packaged curve is modified, it is persisted as `user_edited` rather than continuing to appear as an unchanged reference curve.

The packaged catalogue has been audited for:

- Wind-speed ordering.
- Rated power.
- Monotonicity.
- CT range.
- Cut-out behaviour.
- Implied peak power coefficient.

Users should replace screening curves with project-specific or OEM-approved data whenever formal accuracy is required.

---

# Noise assessment

The Noise module provides a preliminary GIS-based workflow for evaluating wind-turbine sound propagation.

It supports:

- Existing QGIS turbine layers.
- Imported turbine CSV files.
- Separate source groups for different turbine models.
- Point or polygon receptor layers.
- Fixed A-weighted source levels.
- Acoustic curves by wind speed.
- Octave-band spectra.
- OEM spectrum CSV import.
- Manual octave-band editing.
- Optional conversion of A-weighted input spectra.
- Optional DEM/DSM inputs.
- Optional land-use ground-factor inputs.
- Receiver calculations.
- Raster calculations.
- Isophone generation.
- Source-receptor links.
- HTML, TXT and XLSX reporting.

## Calculation engines

### Fast engine

The fast engine is intended for:

- Rapid layout screening.
- Checking source and receptor inputs.
- Initial comparison of layouts.
- Fast receiver calculations.
- Basic raster and isophone testing.

It uses a simplified propagation workflow and should not be used alone for formal acoustic conclusions.

### ISO-aligned octave-band engine

The ISO-aligned workflow follows the structure of octave-band outdoor sound propagation.

It includes practical treatments of:

- Geometric divergence.
- Atmospheric absorption.
- Ground effect.
- Simplified topographic or barrier attenuation.
- Source spectra.
- A-weighting.
- Aggregation of multiple turbine sources.

The implementation contains documented simplifications and is not certified regulatory noise software.

## Noise inputs

Typical inputs include:

- Turbine source layer.
- Receptor layer.
- Acoustic source level or spectrum.
- Receptor height.
- Calculation radius.
- Receptor limits.
- Optional DEM/DSM.
- Optional land-use layer.
- Global or spatial ground factor.
- Raster extent and resolution.

Multiple turbine models are best represented as separate source layers or source groups.

## Noise outputs

The module can generate:

- Sound level at each receptor.
- Applicable receptor limit.
- Compliance margin.
- Screening pass/fail status.
- Critical receptor.
- Dominant source or source group.
- Per-turbine contribution.
- Source summary layer.
- Source-receptor link layer.
- Noise raster.
- Isophone contours.
- Technical HTML report.
- Plain-text report.
- XLSX workbook.

The 0.1.16 XLSX writer uses a lightweight standard-library OOXML implementation and atomic file creation, reducing compatibility problems observed with `openpyxl`/`lxml` in some Windows and QGIS installations.

## Noise limitations

Formal acoustic assessment may require additional treatment of:

- Project-specific regulatory methodology.
- Long-term meteorological correction.
- Tonality.
- Amplitude modulation.
- Impulsivity.
- Directivity.
- Detailed diffraction.
- Reflections.
- Detailed ground conditions.
- Turbine operating modes.
- Measurement and modelling uncertainty.

Results should be independently reviewed before use in permitting or compliance studies.

---

# Shadow Flicker assessment

The Shadow Flicker module estimates potential interaction between turbine rotors, receptors and the Sun.

The calculation uses:

- Turbine coordinates.
- Rotor diameter.
- Hub height.
- Receptor coordinates.
- Observer height.
- Solar position.
- Assessment year.
- Time step.
- Time-zone assumptions.
- Minimum and maximum solar elevation.
- Maximum shadow distance.
- Turbine availability factor.
- Optional DEM/DSM.
- Optional raster settings.

## Time-zone support

The module supports:

- Automatic/project-based time handling where available.
- IANA time zones.
- Fixed UTC offsets.
- Bundled time-zone fallback data.

Time-zone assumptions should be reviewed carefully because they affect hourly and daily reporting.

## Shadow Flicker outputs

The module can generate:

- Annual astronomical flicker hours.
- Adjusted or real hours after availability correction.
- Number of affected days.
- Maximum minutes per day.
- Worst day.
- Monthly distribution.
- Hour-by-month matrix.
- Dominant turbine contribution.
- Receptor severity class.
- QGIS receptor result layer.
- Shadow Flicker raster.
- Filtered monthly or hourly raster outputs where supported.
- Exportable result reports.

## DEM/DSM behaviour

The terrain-aware workflow adjusts absolute elevations:

```text
Turbine source elevation = DEM at turbine + hub height
Receptor elevation       = DEM at receptor + observer height
Raster-cell elevation    = DEM at cell + observer height
```

This improves the vertical geometry used in the calculation.

The current version does **not** implement complete intermediate terrain obstruction or full line-of-sight blocking along every turbine-receptor path.

Use the description:

```text
DEM-aware Shadow Flicker geometry
```

Do not describe the current implementation as a full 3D topographic shadow-occlusion model.

## Shadow Flicker limitations

Formal assessment may require additional treatment of:

- Sunshine probability.
- Turbine operating availability.
- Wind-direction-dependent rotor orientation.
- Operational shutdown.
- Vegetation.
- Buildings.
- Window orientation.
- Receptor dimensions.
- Full terrain obstruction.
- Local regulatory limits.

Fine raster resolutions and small time steps can significantly increase runtime.

---

# Installation

## Option A — Install from ZIP

1. Download `VelantisWind-0.1.16.zip` from the [GitHub releases page](https://github.com/Velantis-Wind/VelantisWind/releases).
2. Open QGIS.
3. Go to **Plugins → Manage and Install Plugins**.
4. Open **Install from ZIP**.
5. Select the downloaded ZIP.
6. Confirm the installation.
7. Enable **Velantis Wind**.
8. Open the plugin from the toolbar or Plugins menu.

The ZIP must contain one top-level folder named:

```text
VelantisWind/
```

## Option B — Manual installation

Copy the `VelantisWind` plugin folder into the active QGIS profile:

```text
QGIS3/profiles/default/python/plugins/VelantisWind/
```

Restart QGIS and enable **Velantis Wind** in the Plugin Manager.

## Install PyWake

The Energy/AEP module requires PyWake in the same Python environment used by QGIS.

PyWake is not bundled with VelantisWind and does not appear in the QGIS Plugin Manager.

On Windows:

1. Close QGIS.
2. Open **OSGeo4W Shell**.
3. Run:

```bash
python -m pip install py_wake==2.6.18
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

4. Restart QGIS.

Noise and Shadow Flicker can be tested without PyWake.

Detailed instructions:

- [OSGeo4W / PyWake installation](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
- [Energy dependencies](VelantisWind/docs/INSTALL_ENERGY_DEPENDENCIES.md)
- [Troubleshooting](VelantisWind/docs/TROUBLESHOOTING.md)

---

# Quick start

## Energy / AEP

1. Create or load a turbine point layer, or prepare a turbine CSV.
2. Use a projected CRS in metres.
3. Open **Velantis Wind → Energy / AEP**.
4. Define one or more turbine models.
5. Select packaged or custom power/CT curves.
6. Load a WAsP/GridSite resource or a WRG/ZIP resource.
7. Add TI rasters when required.
8. Select the wind-farm model engine.
9. Select the wake-deficit model.
10. Configure superposition and rotor averaging.
11. Optionally enable turbulence and blockage.
12. Review compatibility notes.
13. Run the calculation.
14. Inspect total and per-turbine results.
15. Review resource extent and AEP symbology.
16. Export reports and result layers.

## Interactive Map and spacing

1. Open the **Interactive Map**.
2. Import a coordinate CSV or add turbines on the canvas.
3. Select the turbine model.
4. Open the Spacing Envelope configuration.
5. Define longitudinal and crosswind spacing.
6. Select automatic WRG orientation or a manual angle.
7. Press **Apply new configuration**.
8. Review the generated envelopes.
9. Inspect near-limit and conflict states.
10. Move, add or remove turbines.
11. Use the on-screen ellipse tool for per-turbine overrides.
12. Export validation layers when required.

## Noise

1. Open **Velantis Wind → Noise**.
2. Select or import turbine source layers.
3. Load receptor points or polygons.
4. Define fixed `LwA`, an acoustic curve or an octave-band spectrum.
5. Select the fast or ISO-aligned engine.
6. Configure receptor height, limits and radius.
7. Optionally load DEM/DSM and land-use data.
8. Start with receiver-only calculation.
9. Add raster and isophones after validating the basic case.
10. Export HTML, TXT or XLSX results.

## Shadow Flicker

1. Open **Velantis Wind → Shadow Flicker**.
2. Select or import the turbine layer.
3. Define rotor diameter and hub height.
4. Load receptor points.
5. Configure location, time zone, assessment year and time step.
6. Optionally select a DEM/DSM.
7. Start with receptor-only calculation.
8. Add a coarse raster after validating the basic case.
9. Review annual, daily, monthly and hourly outputs.
10. Export the result layers and reports.

---

# Documentation

## Start here

- [Quick start](VelantisWind/docs/QUICKSTART.md)
- [Known limitations](VelantisWind/docs/LIMITATIONS.md)
- [Troubleshooting](VelantisWind/docs/TROUBLESHOOTING.md)
- [OSGeo4W / PyWake installation](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
- [Energy dependencies](VelantisWind/docs/INSTALL_ENERGY_DEPENDENCIES.md)

## User guides

- [Energy / AEP](VelantisWind/docs/ENERGY_MODULE.md)
- [Noise](VelantisWind/docs/NOISE_MODULE.md)
- [Shadow Flicker](VelantisWind/docs/SHADOW_FLICKER_MODULE.md)
- [Shadow Flicker time-zone support](VelantisWind/docs/SHADOW_TIMEZONE_SUPPORT.md)
- [Spacing Envelopes](VelantisWind/docs/SPACING_ENVELOPE_MODULE.md)
- [Turbine Library](VelantisWind/docs/TURBINE_LIBRARY.md)

## Architecture

- [Energy architecture](VelantisWind/docs/ENERGY_ARCHITECTURE.md)
- [Noise architecture](VelantisWind/docs/NOISE_ARCHITECTURE.md)
- [Shadow Flicker architecture](VelantisWind/docs/SHADOW_ARCHITECTURE.md)
- [Spacing Envelope architecture](VelantisWind/docs/SPACING_ENVELOPE_ARCHITECTURE.md)

## Testing and publication

- [Release test checklist](VelantisWind/docs/RELEASE_TEST_CHECKLIST.md)
- [QGIS 4 smoke test](VelantisWind/docs/QGIS4_SMOKE_TEST.md)
- [Turbine curve QA](VelantisWind/docs/TURBINE_CURVE_QA_0_1_16.md)
- [Complete changelog](VelantisWind/CHANGELOG.md)

The plugin folder also contains a separate [`VelantisWind/README.md`](VelantisWind/README.md) with package-level information.

---

# Architecture

The main modules follow a shared high-level pattern:

```text
User interface
      ↓
Configuration and validation
      ↓
Workflow controller
      ↓
Calculation engine
      ↓
Result processing
      ↓
Reports and QGIS layers
```

Main package areas:

```text
VelantisWind/
├─ plugin.py
├─ hub_dialog.py
├─ aep_setup_dialog.py
├─ mapa_interactivo.py
├─ mapa_interactivo_dock.py
├─ noise_page.py
├─ shadow_page.py
│
├─ energy_core/              # Energy state, validation and workflow control
├─ ag_core/                  # PyWake integration, physics and QGIS outputs
├─ spacing_core/             # Ellipse geometry, validation and map tools
├─ noise_core/               # Noise engines, raster and reporting
├─ shadow_core/              # Solar geometry, calculation and raster outputs
├─ ui_core/                  # Shared QGIS and Qt utilities
├─ resources/                # Turbine catalogue and power/CT curves
├─ assets/                   # Icons and bundled fallback data
└─ docs/                     # User and developer documentation
```

Optional developer diagnostics are quiet by default.

On Windows:

```bash
set VELANTISWIND_DEBUG=1
```

On Linux or macOS:

```bash
export VELANTISWIND_DEBUG=1
```

The debug setting adds console information but does not intentionally change numerical results.

---

# Validation and reproducibility

VelantisWind is being developed as an open and reproducible environment for wind-farm pre-assessment.

Useful validation contributions include:

- Comparisons with established commercial software.
- Published benchmark cases.
- Reproducible turbine layouts.
- Reproducible wind-resource inputs.
- Anonymized receiver and raster cases.
- Comparisons with field measurements.
- Testing across QGIS versions.
- Testing across operating systems.
- Review of translations and documentation.
- Technical review of model assumptions.

Validation of one module, model or case does not imply certification of the complete plugin.

For Energy comparisons, record at least:

- VelantisWind version.
- QGIS version.
- PyWake version.
- Wind-resource source and height.
- Layout CRS and turbine coordinates.
- Turbine model and curve source.
- Hub height and rotor diameter.
- Wind-farm model engine.
- Wake-deficit model.
- Wake-model parameters.
- Superposition model.
- Rotor-average model.
- Ambient TI source or fallback.
- Added-turbulence model.
- Blockage model.
- Whether neighbouring wind farms were included.
- Whether results are gross, wake-reduced or full net values.

For Noise and Shadow Flicker comparisons, also record all source, receptor, terrain, time and regulatory assumptions.

---

# Important limitations

## General

- VelantisWind is experimental software.
- Interfaces, reports and internal APIs may evolve.
- QGIS 4 / Qt6 compatibility remains experimental.
- Results depend strongly on GIS validity, CRS, units and input quality.
- Large raster calculations can require significant time and memory.
- Optional scientific dependencies must be installed in the QGIS Python environment.

## Energy / AEP

- PyWake must be installed separately.
- Model availability can vary between PyWake versions.
- Some requested model combinations require automatic compatibility fallbacks.
- Wind-resource quality and turbine curves strongly influence AEP.
- WRG calculations without TI rasters may use a uniform fallback TI.
- Wake-reduced AEP is not a complete bankable net-energy assessment.
- The A/B comparator is not a formal uncertainty-analysis tool.

## Turbine catalogue

- Generic and specification-based curves are screening approximations.
- They are not OEM-certified power or thrust-coefficient curves.
- Public/reference status does not make a curve suitable for every project.

## Spacing

- Elliptical envelopes are geometric validation tools.
- They do not include every civil, load, construction, permitting or OEM constraint.
- Automatic orientation depends on the quality of the loaded WRG.

## Noise

- The workflow is ISO-aligned, not certified regulatory software.
- Atmospheric, ground and terrain attenuation include documented simplifications.
- Long-term meteorological and full permitting post-processing are not implemented.
- Generic source spectra should be replaced with project or manufacturer data.

## Shadow Flicker

- DEM/DSM adjusts absolute elevations.
- Full intermediate terrain occlusion is not yet implemented.
- Fine temporal and raster resolutions can be computationally demanding.
- Formal assessment may require additional operational and receptor corrections.

See [Known limitations](VelantisWind/docs/LIMITATIONS.md) for further information.

---

# Repository structure

```text
VelantisWind/
├─ .github/
├─ VelantisWind/
│  ├─ metadata.txt
│  ├─ plugin.py
│  ├─ energy_core/
│  ├─ ag_core/
│  ├─ spacing_core/
│  ├─ noise_core/
│  ├─ shadow_core/
│  ├─ ui_core/
│  ├─ resources/
│  ├─ assets/
│  └─ docs/
├─ README.md
├─ CONTRIBUTING.md
├─ SUPPORT.md
├─ SECURITY.md
└─ LICENSE
```

---

# Contributing

Technical contributions are welcome, including:

- Bug reports.
- Reproducible test cases.
- Code improvements.
- Documentation.
- Translations.
- Turbine-curve review.
- QGIS compatibility testing.
- Benchmark comparison.
- Validation against other engineering tools.

When reporting an issue, include:

- QGIS version.
- Operating system.
- VelantisWind version.
- PyWake version when relevant.
- Module used.
- Input summary.
- Steps to reproduce.
- Screenshots.
- Complete Python traceback when available.

Do not share confidential project information in public issues.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.

---

# Collaboration and support

VelantisWind is free and open source.

Collaboration and optional sponsorship can support:

- Maintenance.
- Documentation.
- Validation.
- Translation.
- QGIS compatibility.
- Reproducible benchmarks.
- New public modules.
- Improvements to Energy, Noise and Shadow Flicker.
- Integration with existing GIS workflows.

Possible forms of collaboration include:

- Technical feedback and beta testing.
- Reproducible validation cases.
- Academic and research collaboration.
- Project-specific workflow adaptation.
- Sponsorship.
- Layout-optimization studies.
- Joint layout and wake-steering optimization studies.

The proprietary VelantisWind optimization workflow is developed separately from the open-source QGIS plugin and is not included in this repository.

For collaboration, validation cases, sponsorship or project-specific workflows:

**info@velantiswind.com**

Website:

**https://www.velantiswind.com/**

---

# License

VelantisWind is released under **GPL-3.0-or-later**.

See [LICENSE](LICENSE) and [`VelantisWind/LICENSE`](VelantisWind/LICENSE).
