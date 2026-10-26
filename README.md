# VelantisWind

**Open-source wind-farm pre-assessment, layout validation and technical screening directly inside QGIS.**

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632?logo=qgis&logoColor=white)](https://qgis.org/)
[![QGIS 4](https://img.shields.io/badge/QGIS%204-experimental-orange)](VelantisWind/docs/QGIS4_SMOKE_TEST.md)
[![PyWake](https://img.shields.io/badge/PyWake-2.6.18-blue)](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md)
[![Version](https://img.shields.io/badge/version-0.1.17-blue)](https://github.com/Velantis-Wind/VelantisWind/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)
[![Languages](https://img.shields.io/badge/UI-ES%20%7C%20EN%20%7C%20FR%20%7C%20DE-lightgrey)](VelantisWind/docs/QUICKSTART.md)

VelantisWind is an open-source QGIS plugin for early-stage wind-farm analysis. It combines:

- **Energy / AEP assessment with PyWake**
- **Wake, turbulence and blockage model comparison**
- **Interactive turbine-layout creation and editing**
- **Model-specific turbine-spacing validation**
- **Preliminary Noise assessment**
- **Preliminary Shadow Flicker assessment**

The objective is to keep project inputs, engineering assumptions, calculations and outputs connected to the same QGIS project, making wind-farm screening more transparent, reproducible and easier to review.

> [!IMPORTANT]
> VelantisWind is pre-assessment software intended for technical screening, layout comparison, GIS-based QA/QC, workflow validation, research and technical feedback.
>
> It is **not** certified regulatory, permitting or bankable assessment software. Results must be independently reviewed before being used in formal engineering studies.

> [!NOTE]
> The stable build targets QGIS 3.28–3.99. Qt5/Qt6 compatibility work is included, but QGIS 4 support remains unvalidated and is not declared for this build.

---

## Main workflows

| Module | Purpose | Main outputs |
|---|---|---|
| **Energy / AEP** | Estimate and compare wind-farm production using sectoral wind-resource data, turbine power/CT curves and configurable PyWake engineering models. | Gross/free AEP, wake-reduced AEP, wake losses, per-turbine production, sector summaries, model diagnostics, reports, styled QGIS layers and georeferenced wake rasters. |
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

## Release 0.1.17

Version 0.1.17 extends Energy / AEP, corrects result handling and improves the interface in all four languages.

### Main additions

- **Predefined PyWake models**, including TurbOPark, and a manual mode with engine-first class selection, editable parameters, rotor averaging, ground, turbulence and blockage. A new installation opens with predefined **NOJ**; manual defaults are Bastankhah with `LinearSum` and PyWake signature values. Results record the executed configuration and a signed loss breakdown.
- **WRG resource parameters**: directions at sector-subdivision centres (seven per sector initially, or one if seven would exceed 360 directions), `nearest` or `linear` directional interpolation, Speedup `none` and wind speeds covering the turbines' operating bands. GRD uses its PyWake site's directions and wind speeds; both use 8766 h/year.
- **Turbine curves and energy integration**: `.wtg` and `.owtg` density tables, optional per-turbine density, stricter CSV/TXT validation, preserved power-curve derating and mean power over each wind-speed bin. Mixed parks use each model's hub height.
- **Turbine layers and spacing**: a layer per Energy model row, explicit warnings for turbines outside the resource, double-precision coordinates, preserved file-backed envelopes and spacing comparisons limited to the rows' layers.
- **Numerical results**: density-tabulated curves handle negative effective speeds; results report negative and non-finite values and partial totals. `WeightedSum` handles the 0 m/s node separately where applicable.
- **Wake rasters**: georeferenced, tiled and cancellable, with a JSON audit file. All inputs come from the dialog, differences from the last AEP are reported, custom and derived CRS are retained, and a finished raster is not loaded into a different project.
- **Noise and Shadow Flicker**: XLSX and any-valid-CRS layout imports; Noise isophones retain derived CRS. Exactly **30 h/year does not exceed** the shadow-flicker annual limit; the summary, result fields and map agree.
- **Interface and support**: minimize, maximize/restore and close controls; a shared Sponsors button and clearer support links; corrected ES/EN/FR/DE translations, faster translation and live language changes that preserve user data and unfinished edits. MW and MWh in the text and tables of the Energy results, report and comparison follow the plugin language; other numbers, such as the chart axes and those of the Noise and Shadow results, may still use a decimal point, and CSV numeric formats are unchanged.

Default AEP results change compared with 0.1.16 through the wake defaults, resource grids, 8766 h/year, bin-mean power and turbine-curve corrections. **The reference air density, new in this version, is stored per project**: a project without one starts undefined, with the density adjustment off.

**Installation:** use `py_wake==2.6.18` and `h5netcdf>=1.8`, plus `h5py` with pip on Linux/macOS. On Windows with QGIS from OSGeo4W, do not install `h5py` with pip: an HDF5 conflict is expected but has not been reproduced there; `python3-h5py` from the OSGeo4W installer remains an untested option. If the GaussianOverlap table cannot be read because its libraries are unavailable, the dialog asks before using `CGIRotorAvg(7)` and records the adaptation; an applicable saved decision for a predefined model is applied without asking. See the [dependency guide](VelantisWind/docs/INSTALL_ENERGY_DEPENDENCIES.md).

**Known problem:** **Merge resource** ("Unir recurso") can write grids PyWake cannot read and discards turbulence intensity and speed factors. These problems remain for the next version. See the complete [0.1.17 changelog](VelantisWind/CHANGELOG.md) for details.

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

## Wake physics

The wake physics of the AEP and of the wake raster is a configuration of exact PyWake 2.6.18 classes: an engine, a wake deficit with its arguments, rotor average and ground model, a wake superposition, an optional added-turbulence model and, with `All2AllIterative` and `PropagateUpDownIterative`, an optional blockage model with its own superposition. Every value the user does not change is the one of the PyWake class signature. The plugin builds exactly what was selected: it never replaces a class, an argument or a component, never switches the engine and never degrades a calculation that PyWake refuses. Before simulating, the classes of the built objects are checked against the configuration, and what was executed is read from those objects and shown in the result.

By default (the signatures of PyWake): `PropagateDownwind`, `BastankhahGaussianDeficit` with its signature values, `LinearSum`, no added turbulence and no blockage. With some dense parks and density-dependent curves this default stops with a negative effective wind speed (an error of PyWake, shown as such, never replaced by another calculation).

### The «Wake model» group

The engine, the wake deficit, the wake superposition, the blockage (with `All2AllIterative` and `PropagateUpDownIterative`) and the added turbulence are always visible, one line each. Everything subordinate is in folded sections: the deficit parameters with its rotor average and ground model, the parameters of the superposition and of the added turbulence, and the blockage parameters (its superposition, `use_effective_ws` and its parameters). The numerical settings of the engine open from a small button at the end of its line, in a window like the one of the ground (with what the engine has and the plugin does not offer); a warning or a conflict of them goes to the note of the engine and marks the button. Below a section there are no more folds: the arguments of each subordinate object are edited there, starting from the values of its PyWake signature (see «Arguments of the subordinate objects»). The `n` of a rotor average goes in the line of its selector; the arguments of a ground model, in a small window opened with **Parameters of the ground model…** (**OK** keeps them, **Cancel** changes nothing, **Reset** shows the signature values); under «Inherit», the window says which sum the ground inherits (the wake superposition for the ground of the deficit, the blockage superposition for the ground of the blockage). The arguments PyWake has and the plugin does not offer are listed with their reason.

- A combination PyWake (or the plugin) cannot calculate is shown as a conflict next to the visible selector it belongs to, with the reason and, when known, the resolution; the AEP and the raster are not calculated until it is resolved. A conflict inside a folded section unfolds it; one whose cause is inside the window of a ground model (for example the sum it inherits) also names the window and marks its button, and the window shows it when it is opened, without opening by itself. Nothing is changed automatically.
- An option that no other choice can make calculable is disabled with its reason (for example `NOJDeficit` with `PropagateUpDownIterative`).
- Each deficit class and each blockage model keeps its draft while the dialog is open, and so do the arguments of each engine, superposition, added turbulence, rotor average and ground model; changing the engine does not change them. A small **Reset** at the bottom right of each section (deficit, superposition, blockage, added turbulence) returns what the section shows to its signature: the class and the components it has chosen (its rotor and ground, the nested options), and the selectors inside it; the selector above the section, the other sections, the other classes and the drafts of the options not chosen are kept. The numerical settings of the engine and the windows have their own **Reset**. The dialog shows no summary of the differences with the signatures: what was executed, with its differences, is in the result.
- Between sessions the engine, the class, the superposition, the turbulence and the blockage are remembered and open with their signature values (edited values are not kept between sessions); a remembered choice that is no longer an option is reported. The physics preferences of earlier versions (including the advanced wake parameters) are no longer used; the dialog says so once.
- Every engine, class, option and parameter has a short help text with what PyWake says about it, in the four languages of the interface.
- The interactive map shows the same selectors, with the same enabled options and messages.

### Engines

| Option | Help |
|---|---|
| `PropagateDownwind` | Propagates the wakes downstream, turbine by turbine. Does not support blockage. |
| `All2AllIterative` | Computes the wakes and the blockage of every turbine on every other one and iterates until it converges. Supports blockage. |
| `PropagateUpDownIterative` | Propagates the wakes downstream and the blockage upstream, and iterates. Supports blockage and requires the deficit and the blockage to use the effective wind speed (use_effective_ws). |

### Wake deficits

| Class | Editable arguments (signature values, PyWake 2.6.18) | Notes |
|---|---|---|
| `BastankhahGaussianDeficit` | `ct2a = ct2a_madsen`, `k = 0.0324555`, `ceps = 0.2`, `ctlim = 0.899`, `use_effective_ws = False` | Gaussian deficit of Bastankhah and Porté-Agel (2014), with a constant expansion k. PyWake predefined model: Bastankhah_PorteAgel_2014, which requires k and uses ct2a_mom1d and the effective wind speed. |
| `NiayifarGaussianDeficit` | `ct2a = ct2a_madsen`, `a = [0.38, 0.004]`, `ceps = 0.2`, `ctlim = 0.899`, `use_effective_ws = False`, `use_effective_ti = True` | Gaussian deficit whose expansion depends on the local TI, k = a₁·TI + a₂ (Niayifar and Porté-Agel, 2016). PyWake predefined model: Niayifar_PorteAgel_2016, with a = [0.3837; 0.003678], ct2a_mom1d, effective wind speed, GaussianOverlapAvgModel and CrespoHernandez. |
| `ZongGaussianDeficit` | `ct2a = ct2a_madsen`, `a = [0.38, 0.004]`, `ctlim = 0.899`, `deltawD = 0.7071067811865475`, `eps_coeff = 0.35355339059327373`, `lam = 7.5`, `B = 3`, `use_effective_ws = False`, `use_effective_ti = True` | Extension of Niayifar with the gradual growth of the thrust and the wake width of Shapiro (Zong and Porté-Agel, 2020). PyWake predefined model: Zong_PorteAgel_2020, with eps_coeff = 0.35, effective wind speed, WeightedSum and its own CrespoHernandez (ct2a_mom1d, c = [0.73; 0.83; 0.03; −0.32]). |
| `CarbajofuertesGaussianDeficit` | `ct2a = ct2a_madsen`, `a = [0.35, 0.0]`, `ceps = [-1.91, 0.34]`, `use_effective_ws = False`, `use_effective_ti = True` | Version with constants measured with lidar: empirical ε and new expansion constants (Carbajo Fuertes et al., 2018). PyWake predefined model: CarbajoFuertes_etal_2018, with ct2a_mom1d, effective wind speed, GaussianOverlapAvgModel and CrespoHernandez. |
| `TurboGaussianDeficit` | `ct2a = ct2a_madsen`, `A = 0.04`, `cTI = [1.5, 0.8]`, `ceps = 0.25`, `ctlim = 0.999`, `use_effective_ws = False`, `use_effective_ti = False` | Gaussian deficit similar to Ørsted's TurbOPark: the expansion combines the ambient TI and the one generated by the wake itself. PyWake predefined model: Nygaard_2022 (TurbOPark), with ct2a_mom1d, ctlim = 0.96, GaussianOverlapAvgModel, Mirror(SquaredSum()), SquaredSum and the free wind speed of the affected turbine (WS_jlk), which is not in the class signature and cannot be chosen. ground model of its signature: `Mirror()`. |
| `BlondelSuperGaussianDeficit2020` | `a_s = 0.17`, `b_s = 0.005`, `c_s = 0.2`, `b_f = -0.68`, `c_f = 2.41`, `ctlim = 0.999`, `use_effective_ws = False`, `use_effective_ti = True` | Super-Gaussian: top-hat profile near the rotor and Gaussian far from it (Blondel and Cathelain, 2020). PyWake predefined model: Blondel_Cathelain_2020, with effective wind speed; in PyWake 2.6.18 it has no turbulence model and PyWake rejects it for that reason; its own example uses CrespoHernandez. |
| `BlondelSuperGaussianDeficit2023` | `a_s = 0.28`, `b_s = 0.01`, `c_s = [0.1, 0.1]`, `b_f = [-25.98, -1.06]`, `c_f = 2`, `ctlim = 0.999`, `use_effective_ws = False`, `use_effective_ti = True` | Super-Gaussian with the calibrated parameters of Blondel (2023). |
| `IEA37SimpleBastankhahGaussianDeficit` | — | Simplified Bastankhah of the IEA37 case study (equivalent to Bastankhah with β = 1/√8). PyWake predefined model: IEA37CaseStudy1, with All2All (without convergence check) and SquaredSum, on the site and turbines of that case. |
| `GCLDeficit` | `use_effective_ws = False`, `use_effective_ti = False` | Semi-analytical model of G. C. Larsen (2009), with a rotationally symmetric wake. PyWake predefined models: GCL (LinearSum, no rotor average nor turbulence) and GCLLocal (effective wind speed and TI). |
| `NOJDeficit` | `ct2a = ct2a_madsen`, `k = 0.1` | Jensen (NOJ): top-hat deficit with a linear expansion k. PyWake predefined model: Jensen_1983, with SquaredSum. Rotor average of its signature: `AreaOverlapAvgModel()`. |
| `NOJLocalDeficit` | `ct2a = ct2a_madsen`, `a = [0.38, 0.004]`, `use_effective_ws = True`, `use_effective_ti = True` | Like NOJ, but with the local wind speed and TI; k depends on the TI as in Niayifar. PyWake predefined model: NOJLocal, with LinearSum and STF2017TurbulenceModel. Rotor average of its signature: `AreaOverlapAvgModel()`. |
| `TurboNOJDeficit` | `ct2a = ct2a_madsen`, `A = 0.6`, `cTI = [1.5, 0.8]`, `use_effective_ws = False`, `use_effective_ti = False` | NOJ with the expansion of Nygaard (2020), proportional to the local TI in the wake. Rotor average of its signature: `AreaOverlapAvgModel()`. |

The classes are not the PyWake predefined models (presets) of the same authors: a predefined model is a class with chosen arguments and components (see the notes), and some also set things the class signature does not offer. Choosing its arguments and components reproduces a predefined model as far as the class allows: `Nygaard_2022` (TurbOPark) scales the deficit with the free wind speed of the waked turbine (`WS_key = 'WS_jlk'`), which cannot be chosen; on a WRG resource, without speed-up, it gives the same AEP as `TurboGaussianDeficit` with its components, but not on a resource with a spatial speed-up.

### Rotor average, ground model, superposition and added turbulence

«None» is offered for the rotor average (the wind speed at the rotor centre, not averaged), the ground model and the added turbulence. The initial value of the rotor average and of the ground model is the one of the deficit signature.

| Option | Help |
|---|---|
| `RotorCenter` | A single point at the rotor centre, as an explicit model. |
| `CGIRotorAvg` | Circular Gauss integration with n points (4, 7, 9 or 21; 7 in its signature). |
| `EqGridRotorAvg` | Regular grid of n × n points inside the rotor (n = 4 in its signature). |
| `GaussianOverlapAvgModel` | Exact overlap of the Gaussian wake with the rotor, read from a PyWake table (requires h5py and h5netcdf). |
| `AreaOverlapAvgModel` | Fraction of the rotor area inside a top-hat wake. |

| Option | Help |
|---|---|
| `Mirror` | The ground as a mirror: adds image turbines below the terrain. |
| `MultiMirror` | The ground and a mirror aloft (at 1000 m by default); the number of image turbines grows as 2^(2 + max(0, n_reps)). |

| Option | Help |
|---|---|
| `LinearSum` | Sum of the deficits. |
| `SquaredSum` | Square root of the sum of the squares (Katic et al., 1986). |
| `MaxSum` | The largest of the deficits. |
| `WeightedSum` | Weighted sum that conserves momentum (Zong and Porté-Agel, 2020); iterative. |
| `CumulativeWakeSum` | Cumulative wake (Bastankhah et al., 2021). With CumulativeWakeSum, PyWake 2.6.18 gives results that depend on the order of the turbines (checked with three identical turbines); it is not verified. |

| Option | Help |
|---|---|
| `STF2005TurbulenceModel` | Frandsen, according to IEC 61400-1 of 2005. |
| `STF2017TurbulenceModel` | Frandsen, according to IEC 61400-1 of 2017. |
| `GCLTurbulence` | G. C. Larsen, according to Pierik et al. |
| `CrespoHernandez` | Crespo and Hernández (1996). |

### Blockage

Available with `All2AllIterative` and `PropagateUpDownIterative`; «None» by default. Its superposition is chosen in **Blockage options** (`LinearSum` by default); the wake superposition does not change with the blockage. `use_effective_ws` of the blockage model is editable; `PropagateUpDownIterative` requires it.

| Option | Help |
|---|---|
| `SelfSimilarityDeficit2020` | Self-similarity of Troldborg and Meyer Forsting, revised version (2020). |
| `SelfSimilarityDeficit` | Self-similarity of Troldborg and Meyer Forsting (2016). |
| `VortexCylinder` | Semi-infinite cylinder of tangential vorticity (Branlard). With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |
| `VortexDipole` | Vortex dipole; induces almost the same as the cylinder and is faster. With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |
| `HybridInduction` | Combines a near-rotor approximation and a far-field one, with a switch radius. With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |
| `RankineHalfBody` | Rankine half body with the source set by 1-D momentum. With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |
| `Rathmann` | Rathmann's approximation (DTU, 2020) to the vortex cylinder. With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |
| `RathmannScaled` | Rathmann scaled with Ct to compensate for the wake expansion. With PropagateUpDownIterative, this PyWake 2.6.18 blockage model computes with the free wind speed even when use_effective_ws is set: it does not scale with the effective wind speed PropagateUpDownIterative requires; it is not verified. |

| Option | Help |
|---|---|
| `LinearSum` | Sum of the blockages. |
| `MaxSum` | The largest of the blockages. |
| `SquaredSum` | Square root of the sum of the squares; PyWake does not accept it with speed-ups (negative values). |
| `WeightedSum` | Cannot be used for the blockage: the PyWake engines call the blockage superposition with a single array and WeightedSum needs more data. |
| `CumulativeWakeSum` | Cannot be used for the blockage: the PyWake engines call the blockage superposition with a single array and CumulativeWakeSum needs more data. |

### Arguments of the subordinate objects

Every argument of a subordinate object that changes the calculation in its position (in some valid combination) is offered, with the value of its PyWake 2.6.18 signature to start with; what a given path leaves without effect is warned. Each control follows the kind of the argument: a field per number (read as typed, never rounded nor clipped), one field per coefficient of a list of fixed length, True/False, `ct2a`, the values of a closed set (`CGIRotorAvg.n`), an integer with arrows (`EqGridRotorAvg.n`, minimum −2: a smaller value typed is shown as −2 when leaving the field; from −2 to 0 there are no nodes, which is warned; through the API, −3 or less is refused, as PyWake does not build it), a selector «Check convergence / One iteration (None)» with its field (`All2AllIterative.convergence_tolerance`), and another PyWake class with its own arguments. The plugin always works with copies: no default value of PyWake is modified. The edited values are part of the draft of the class, reach the built objects and are recorded as differences with the signature, with their route (for example `blockage · groundModel · n_reps`).

| Class | Argument | Signature value | What PyWake says, and its source |
|---|---|---|---|
| `All2AllIterative` | `convergence_tolerance` | `1e-06` | PyWake (engineering_models.py:926-929): «if float: maximum accepted change in WS_eff_ilk [m/s]; if None: return after first iteration». At most max(number of turbines, 20) iterations. PyWake gives no range. |
| `PropagateUpDownIterative` | `convergence_tolerance` | `1e-06` | PyWake does not document it (engineering_models.py:515-535); it stops when the largest change is below it. PyWake gives no range. |
| `PropagateUpDownIterative` | `max_iter` | `10` | PyWake does not document it; it is compared with an integer counter (engineering_models.py:589) and the loop has at most as many passes as turbines (line 559); ≤ 0 makes one pass. PyWake gives no range. |
| `CGIRotorAvg` | `n` | `7` | PyWake (rotor_avg_model.py:127-133): «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points». Values: 4, 7, 9, 21. |
| `EqGridRotorAvg` | `n` | `4` | PyWake does not document it: a grid of n × n points, those that fall inside the rotor (rotor_avg_model.py:83-88); from −2 to 0 there are no nodes, and with −3 or less it is not built. PyWake gives no range. |
| `Mirror` | `superpositionModel` | `None` | PyWake (ground_models.py:24-30): «Superposition model used to sum wakes from the above and below-ground turbine. If None, default, the superposition model used for the deficit model is applied». Options: None, LinearSum, SquaredSum, MaxSum, WeightedSum, CumulativeWakeSum, SqrMaxSum. |
| `MultiMirror` | `mirror_height` | `1000.0` | PyWake (ground_models.py:64-75): «Considers the ground and a mirror aloft as a mirror by default … mirror_heigth : int or float, optional». PyWake gives no range. |
| `MultiMirror` | `n_reps` | `0` | PyWake (ground_models.py:64-76): «the user can set how many mirrors should be enforced (n_mirrors = 2 + n_reps). Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors)». PyWake gives no range: a negative adds no repetitions, as 0 (ground_models.py:89-94); the control reaches −2147483647, the minimum of its field. |
| `MultiMirror` | `superpositionModel` | `None` | PyWake (ground_models.py:77-81): the same text as in Mirror. Options: None, LinearSum, SquaredSum, MaxSum, WeightedSum, CumulativeWakeSum, SqrMaxSum. |
| `WeightedSum` | `delta` | `0.01` | PyWake (superposition_models.py:83): «minimum deficit (as fraction of free-stream) to invoke weighted summation»; Zong and Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake gives no range. |
| `WeightedSum` | `max_err` | `0.001` | PyWake (superposition_models.py:85): «convergence limit for computing global convection velocity». PyWake gives no range. |
| `WeightedSum` | `max_iter` | `5` | PyWake (superposition_models.py:87): «maximum number of iterations used in computing weights». PyWake gives no range. |
| `WeightedSum` | `weight_limit` | `10000000000` | PyWake (superposition_models.py:89): «Limit weights to this value. A limit of 1.0 means not exceeding linear superposition». PyWake gives no range. |
| `CumulativeWakeSum` | `alpha` | `2.0` | PyWake (superposition_models.py:216-217): «somewhat empirical factor to scale results to fit LES predictions … alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)»; Bastankhah et al., J. Fluid Mech. (2021) 911 A53. PyWake gives no range. |
| `STF2017TurbulenceModel` | `c` | `[1.5, 0.8]` | PyWake (stf.py:72-73): «the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct))», after IEC 61400-1 of 2017. PyWake gives no range. |
| `STF2017TurbulenceModel` | `addedTurbulenceSuperpositionModel` | `LinearSum()` | How the added turbulence is summed with the ambient one (turbulence_model.py:47). PyWake does not document it. Options: LinearSum, SquaredSum, MaxSum, SqrMaxSum. |
| `STF2017TurbulenceModel` | `weight_function` | `FrandsenWeight()` | PyWake (stf.py:12-17, 43-51): FrandsenWeight, the weight of Frandsen’s thesis (Eq. 3.16); IECWeight, the 21.6° sector of IEC 61400-1 (annexes D of 2005 and E of 2017). Options: FrandsenWeight, IECWeight. |
| `STF2017TurbulenceModel` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `STF2005TurbulenceModel` | `addedTurbulenceSuperpositionModel` | `LinearSum()` | How the added turbulence is summed with the ambient one (turbulence_model.py:47). PyWake does not document it. Options: LinearSum, SquaredSum, MaxSum, SqrMaxSum. |
| `STF2005TurbulenceModel` | `weight_function` | `FrandsenWeight()` | As in STF2017TurbulenceModel. Options: FrandsenWeight, IECWeight. |
| `STF2005TurbulenceModel` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `GCLTurbulence` | `addedTurbulenceSuperpositionModel` | `SqrMaxSum()` | How the added turbulence is summed with the ambient one (turbulence_model.py:47). PyWake does not document it. Options: LinearSum, SquaredSum, MaxSum, SqrMaxSum. |
| `GCLTurbulence` | `rotorAvgModel` | `AreaOverlapAvgModel()` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `CrespoHernandez` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction: ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) or ct2a_mom1d (1-D momentum, Ct = 4a(1 − a), with Ct below 1) (deficit_models/utils.py:6-18). |
| `CrespoHernandez` | `c` | `[0.73, 0.8325, -0.0325, -0.32]` | PyWake (crespo.py:42-44): «added turbulence (Eq. 21)», c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3]; Crespo and Hernández, J. Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake gives no range. |
| `CrespoHernandez` | `addedTurbulenceSuperpositionModel` | `SqrMaxSum()` | How the added turbulence is summed with the ambient one (turbulence_model.py:47). PyWake does not document it. Options: LinearSum, SquaredSum, MaxSum, SqrMaxSum. |
| `CrespoHernandez` | `rotorAvgModel` | `AreaOverlapAvgModel()` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `IECWeight` | `distance_limit` | `10` | PyWake does not document it: the distance, in diameters, up to which the weight applies (stf.py:56). PyWake gives no range. |
| `SelfSimilarityDeficit` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `SelfSimilarityDeficit` | `limiter` | `1e-10` | PyWake: «limiter for singularities»; it cancels the blockage closer than limiter·R to the rotor plane, upstream and downstream (the distance is taken in absolute value, selfsimilarity.py:52, 84) and, with exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range. |
| `SelfSimilarityDeficit` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `SelfSimilarityDeficit` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `SelfSimilarityDeficit` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `SelfSimilarityDeficit` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `SelfSimilarityDeficit2020` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `SelfSimilarityDeficit2020` | `limiter` | `1e-10` | PyWake: «limiter for singularities»; it cancels the blockage closer than limiter·R to the rotor plane, upstream and downstream (the distance is taken in absolute value, selfsimilarity.py:52, 84) and, with exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range. |
| `SelfSimilarityDeficit2020` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `SelfSimilarityDeficit2020` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `SelfSimilarityDeficit2020` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `SelfSimilarityDeficit2020` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `VortexCylinder` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `VortexCylinder` | `limiter` | `0.001` | PyWake: «limiter to avoid singularities»; it regularises the edge of the cylinder (\|ρ − 1\| < limiter, vortexcylinder.py:47) and the rotor plane (line 56), also far from the rotor, and bounds the excluded region (line 88). PyWake gives no range. |
| `VortexCylinder` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `VortexCylinder` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `VortexCylinder` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `VortexCylinder` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `VortexDipole` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `VortexDipole` | `limiter` | `1e-10` | PyWake: «limiter to avoid singularities»; it acts with r/R < limiter (vortexdipole.py:53, 57) and, with exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range. |
| `VortexDipole` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `VortexDipole` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `VortexDipole` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `VortexDipole` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `RankineHalfBody` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `RankineHalfBody` | `limiter` | `1e-10` | PyWake: «limiter to avoid singularities»; it cancels the blockage with 2r/D < limiter (rankinehalfbody.py:70) and, with exclude_wake, it bounds the wake region (deficit_model.py:115). PyWake gives no range. |
| `RankineHalfBody` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `RankineHalfBody` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `RankineHalfBody` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `RankineHalfBody` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `Rathmann` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `Rathmann` | `limiter` | `1e-10` | PyWake: «limiter to avoid singularities»; it is used only with exclude_wake, to bound the wake region (deficit_model.py:115). PyWake gives no range. |
| `Rathmann` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `Rathmann` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `Rathmann` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `Rathmann` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `RathmannScaled` | `ct2a` | `ct2a_madsen` | Relation between Ct and the axial induction (deficit_models/utils.py:6-18). |
| `RathmannScaled` | `limiter` | `1e-10` | PyWake: «limiter to avoid singularities»; it is used only with exclude_wake, to bound the wake region (deficit_model.py:115). PyWake gives no range. |
| `RathmannScaled` | `exclude_wake` | `True` | PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake model is active» (VortexCylinder excludes by the radius of the rotor, vortexcylinder.py:85-90). |
| `RathmannScaled` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `RathmannScaled` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `RathmannScaled` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `HybridInduction` | `switch_radius` | `6.0` | PyWake (hybridinduction.py:15-20): «Location at which to switch from near-rotor to far-field can be altered though by setting switch_radius»; far field if r > R·switch_radius or downstream. PyWake gives no range. |
| `HybridInduction` | `upstream_only` | `False` | PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero». |
| `HybridInduction` | `rotorAvgModel` | `None` | The rotor average of this model, apart from that of the deficit; none: the wind speed at the rotor centre. Options: None, CGIRotorAvg, EqGridRotorAvg, AreaOverlapAvgModel, GaussianOverlapAvgModel. |
| `HybridInduction` | `groundModel` | `None` | The ground model of this blockage, apart from that of the deficit; none: no ground. Options: None, Mirror, MultiMirror. |
| `SelfSimilarityDeficit` | `ss_gamma` | `1.1` | PyWake (selfsimilarity.py:21, 64-65): the effective Ct is gamma·Ct, Eq. (8) of Troldborg and Meyer Forsting (2016). PyWake gives no range. |
| `SelfSimilarityDeficit` | `ss_lambda` | `0.587` | PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) of [1]. PyWake gives no range. |
| `SelfSimilarityDeficit` | `ss_eta` | `1.32` | PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) of [1]. PyWake gives no range. |
| `SelfSimilarityDeficit` | `ss_alpha` | `0.8888888888888888` | PyWake (selfsimilarity.py:43-45, 132): radial shape, Eq. (6) of [1]. |
| `SelfSimilarityDeficit` | `ss_beta` | `1.4142135623730951` | PyWake (selfsimilarity.py:43-45, 132): radial shape, Eq. (6) of [1]. |
| `SelfSimilarityDeficit2020` | `ss_alpha` | `0.8888888888888888` | PyWake (selfsimilarity.py:43-45, 132): radial shape, Eq. (6) of [1]. |
| `SelfSimilarityDeficit2020` | `ss_beta` | `1.4142135623730951` | PyWake (selfsimilarity.py:43-45, 132): radial shape, Eq. (6) of [1]. |
| `SelfSimilarityDeficit2020` | `r12p` | `[-0.672, 0.4897]` | PyWake (selfsimilarity.py:135, 147-151): «coefficients for the half width approximation», Eq. (13) of Meyer Forsting et al. (2023). PyWake gives no range. |
| `SelfSimilarityDeficit2020` | `ngp` | `[-1.381, 2.627, -1.524, 1.336]` | PyWake (selfsimilarity.py:137, 162-166): γ(Ct) at x/R = −1, Eq. (16) of [2]. PyWake gives no range. |
| `SelfSimilarityDeficit2020` | `fgp` | `[-0.06489, 0.4911, 1.116, -0.1577]` | PyWake (selfsimilarity.py:155-158): γ(Ct) at x/R = −6, Eq. (17) of [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) + fgp[2]. PyWake gives no range. |
| `VortexDipole` | `sct` | `1.0` | PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake gives no range. |
| `Rathmann` | `sct` | `1.0` | PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake gives no range. |
| `RathmannScaled` | `sct` | `1.0` | PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the effective forcing». PyWake gives no range. |
| `RankineHalfBody` | `high_ct_mod` | `False` | PyWake does not document it: it changes the strength and the position of the source with a (rankinehalfbody.py:54-62); Gribben and Hawkes (2019). |

Not offered, with their reason:

| Class | Argument | Why it is not offered |
|---|---|---|
| `STF2005TurbulenceModel` | `c` | PyWake 2.6.18 does not read it: STF2005 uses the constants of the standard (stf.py:107-110). |
| `STF2017TurbulenceModel` | `groundModel` | The engine does not call it: the turbulence is only wrapped with its rotor average (turbulence_model.py:26-30). |
| `STF2005TurbulenceModel` | `groundModel` | The engine does not call it: the turbulence is only wrapped with its rotor average (turbulence_model.py:26-30). |
| `GCLTurbulence` | `groundModel` | The engine does not call it: the turbulence is only wrapped with its rotor average (turbulence_model.py:26-30). |
| `CrespoHernandez` | `groundModel` | The engine does not call it: the turbulence is only wrapped with its rotor average (turbulence_model.py:26-30). |
| `GaussianOverlapAvgModel` | `filename` | It is the table of PyWake; the plugin provides no others. |
| `HybridInduction` | `near_rotor` | Not offered yet: PyWake calculates with it, although it calls it without some of its wrappers (hybridinduction.py:49-54); its class and its coefficients change the calculation. |
| `HybridInduction` | `far_field` | Not offered yet: as near_rotor. |
| `PropagateDownwind` | `externalWindFarms` | It asks for another wind farm with its model, which the plugin does not provide. |
| `All2AllIterative` | `externalWindFarms` | It asks for another wind farm with its model, which the plugin does not provide. |
| `PropagateDownwind`, `All2AllIterative`, `PropagateUpDownIterative` | `deflectionModel` | Wake deflection is not offered: the plugin does not compute the AEP with yaw. |
| `PropagateDownwind`, `All2AllIterative`, `PropagateUpDownIterative` | `rotorAvgModel` | Deprecated in PyWake (engineering_models.py:100-107); the rotor average goes in the wake deficit. |
| `PropagateDownwind`, `All2AllIterative`, `PropagateUpDownIterative` | `inputModifierModels` | It only takes multi-rotor turbines, which the plugin does not have. |

`RotorCenter` is not among the options of the rotor averages of the added turbulence and of the blockage: there it is the same as none (rotor_avg_model.py:18-19).

**Technical limits**, refused before calculating with the route of the argument: only what PyWake does not build, `EqGridRotorAvg.n` of −3 or less (`np.linspace` with n + 2 < 0); the control of the dialog goes down to −2. With the values with which PyWake calculates, even with non-finite results, the plugin calculates and warns: `EqGridRotorAvg.n` from −2 to 0 (no nodes: NumPy averages an empty list and PyWake can give NaN in what that rotor averages), `STF2017TurbulenceModel` with `c[0] = 0` (the added turbulence is infinite at distance 0, and with `c = [0, 0]` at any distance), `SelfSimilarityDeficit2020.fgp[3] = 0` (a division by zero), and the centre of the rotor of the turbine itself with `All2AllIterative` in `VortexDipole` and `SelfSimilarityDeficit` (below). The contract checks only the form of a value (a number, a bool, a list of numbers, a function `ct2a`, an option of its family): whether PyWake takes it, PyWake decides. An error of PyWake when building is refused before calculating, at its position (the validation builds the deficit, the blockage and the added turbulence); an error when calculating with a given value is an error of the calculation, with its cause. So `1` for `True`, `True` as a number, the `n` of `CGIRotorAvg` as `7.0`, an integer of any size, and a list longer than what PyWake reads (kept, with a warning; `cTI` of `TurboGaussianDeficit` and `TurboNOJDeficit`, which PyWake unpacks, needs its two elements) are taken; through the API, an array of NumPy is its list. Any other value is kept as it is typed (the fields of the dialog read a number and do not read `nan` or `inf`; through the API, NaN and infinities reach PyWake as given, and the configuration, its JSON (with Python's `NaN` and `Infinity`, not strict JSON), what was executed and the report keep them); what PyWake documents as a recommendation, or what behaves badly with some values, gives a warning, never a refusal. A non-finite result is not refused either: the result flags non-finite values, and totals that omit cases that may carry energy are labelled partial.

### What is refused before calculating

Only what PyWake rejects (when building the model or in its calculation path) and what the plugin cannot support, each with its reason, and **exactly where PyWake stops**: with the engine, the number of turbines and the stage (the AEP or the map of the raster).

- **With any layout** (a conflict in the dialog, refused by the API): blockage with `PropagateDownwind` (through the API: in the dialog, with `PropagateDownwind` the blockage is not shown and the configuration has none, its choice kept for the other engines); a deficit that uses the effective TI (`use_effective_ti = True`) without an added-turbulence model; with `PropagateUpDownIterative`, a deficit or a blockage that does not use the effective wind speed, and `SquaredSum` in a blockage with upstream and downstream effects; `WeightedSum` or `CumulativeWakeSum` with a deficit that is not a convection model or with a rotor average that is not node-based; `CumulativeWakeSum` with `All2AllIterative` and a ground model that inherits it; `None` as the tolerance of `PropagateUpDownIterative`; an error of PyWake when building (the validation builds the deficit, the blockage and the added turbulence); an unknown key or a class the installed PyWake does not have.
- **The failures of interaction**: PyWake stops only where it evaluates a model between turbines or at the points of the map, and each rule is refused from the number of turbines measured for it. Most: with `All2AllIterative`, which evaluates every turbine, itself too, with any layout; with `PropagateDownwind` and `PropagateUpDownIterative`, from the second turbine (checked with the turbines of the AEP and of the raster before simulating; a note in the dialog under the selector of its cause, never a barrier); and the raster refuses them also with one turbine where the map fails. They are: `WeightedSum` with the NOJ family or with a ground model; `CumulativeWakeSum` with the NOJ family; `AreaOverlapAvgModel` with a non-top-hat deficit; `GaussianOverlapAvgModel` with a non-Gaussian deficit, or without `h5py`/`h5netcdf` (its table is read where the rotor of the deficit is evaluated: the dialog asks only there, counting the selected turbines); `MultiMirror` without a sum of its own with a rotor average, in the deficit and in the blockage; `WeightedSum` or `CumulativeWakeSum` as the blockage superposition; `AreaOverlapAvgModel` and `GaussianOverlapAvgModel` as the rotor average of a blockage, and of an added turbulence (`AreaOverlapAvgModel` only in `STF2005TurbulenceModel` and `STF2017TurbulenceModel`; there the map with one turbine calculates); `WeightedSum`, `CumulativeWakeSum` or `SqrMaxSum` as the own sum of a ground model (with `CumulativeWakeSum` as the wake superposition, `PropagateDownwind` and `PropagateUpDownIterative` never evaluate the ground of the deficit in the AEP, nor any of its arguments: only the map, `R9e`); `None` where PyWake uses the argument (with `CumulativeWakeSum` and those two engines, `ct2a` and `deltawD` of the deficit are not evaluated in the AEP; the `limiter` of `Rathmann` and `RathmannScaled` is used only with `exclude_wake`; the `alpha` of `CumulativeWakeSum` weighs the second contribution, so `All2AllIterative` and the map stop from the second turbine and the other two engines from the third); a list shorter than what PyWake reads, or a `cTI` of `TurboGaussianDeficit` and `TurboNOJDeficit` of another length than two. With `PropagateUpDownIterative`, `WeightedSum` or `CumulativeWakeSum` and `MaxSum` as the blockage superposition, from the second turbine (the map calculates). Each frontier is measured, and the tests compare the refusal with PyWake written by hand, by engine, with one, two and three turbines and in the map with one and two.
- **Only the map**: `CumulativeWakeSum` with a ground model of the deficit.

The reasons of a refusal are those of the first stage that stops (building and what fails with any layout, then the simulation with the turbines, then the map): every cause that stops PyWake there on its own, never one PyWake cannot reach (the arguments of a sum it cannot call, the table of `GaussianOverlapAvgModel` where it is never read). The internal order of PyWake's exceptions is not reproduced: a cause is given even if another one of the same stage hides it in that run.

What fails only with given values (for example `SquaredSum` in the blockage or in the ground of the blockage with speed-ups, the usual in a blockage: it has a persistent warning and no resolution proposes it, an integer PyWake cannot operate, `None` as the `max_iter` of `PropagateUpDownIterative`, compared only when its first pass does not converge, or as the `max_err`, `max_iter` and `weight_limit` of `WeightedSum`, read only when a contribution passes its `delta`) is reported as an error of the calculation, with its cause, without a substitute AEP.

### Persistent warnings and convergence

Two demonstrated behaviours of PyWake 2.6.18 are offered with a warning in the dialog, the result and its report: `CumulativeWakeSum` depends on the order of the turbines, and with `PropagateUpDownIterative` the blockage models `VortexCylinder`, `VortexDipole`, `HybridInduction`, `RankineHalfBody`, `Rathmann` and `RathmannScaled` compute with the free wind speed even when `use_effective_ws` is set. With `CumulativeWakeSum`, PyWake takes from the deficit only its width and the rotor average of its crosswind distance, and computes the strength of the deficit in the superposition: a warning names the arguments of the deficit that therefore do not affect the numerical result along this path (`ct2a`, `use_effective_ws` with `PropagateDownwind` and `All2AllIterative`, `deltawD` of `ZongGaussianDeficit`, and the ground of the deficit with `PropagateDownwind` and `PropagateUpDownIterative`, including the `Mirror()` of the signature of `TurboGaussianDeficit`). They are still recorded in the executed configuration, as they were passed; the warning describes the main configuration, not the variants of the breakdown. The edited arguments add their own persistent warnings when their value calls for one: `All2AllIterative` with `convergence_tolerance = None` (one iteration; the result says «convergence not checked», never «converged») or ≤ 0 (never met: it uses up max(number of turbines, 20) iterations); `PropagateUpDownIterative` with a tolerance ≤ 0; `MultiMirror`, always with its cost (2^(2 + max(0, n_reps)) representations of each turbine), and with `n_reps` ≥ 2 (repeated images), ≥ 3 (another copy of the real turbine: the images PyWake places within 1 µm of its height, counted with its own geometry) or negative (kept; it adds no repetitions, as 0), `mirror_height = 0`, and a mirror at the height of a hub or below (checked with the turbines of the calculation; a general note in the dialog), none of them for a ground PyWake never calls (`CumulativeWakeSum` with `PropagateDownwind` or `PropagateUpDownIterative`; with `All2AllIterative` and a sum of its own the ground has no effect but is evaluated, and costs); `WeightedSum` with `max_iter`, `delta` or `weight_limit` ≤ 0 (PyWake leaves out the iteration, bounds the threshold internally, or, when it iterates, takes `weight_limit` as the maximum of the weight of each weighted contribution, the smaller of its ratio of convection velocities and `weight_limit`: with 0, those with a positive ratio are cancelled; with a negative limit, those with a larger ratio take it, inverted); `SelfSimilarityDeficit` with `ss_lambda·(ss_eta + x²)` negative or zero in part of its domain, also with a product `ss_lambda·ss_eta` that rounds to zero (NaN in the wind speeds and the AEP, or an error, depending on the inputs; with `All2AllIterative`, also at the turbine itself); `VortexDipole` with a limiter that leaves the centre of the rotor unregularised (NaN at any point on the centre of a turbine, such as a cell of the raster; with `All2AllIterative` and a rotor average of the blockage with a node at the centre, at the turbine itself: NaN in the wind speeds and the AEP); `EqGridRotorAvg` without nodes; `STF2017TurbulenceModel` with `c[0] = 0`; `SelfSimilarityDeficit2020.fgp[3] = 0`; `RankineHalfBody.high_ct_mod = True` (it modifies `dw_ijlk` in place with a single wind speed and cancels the blockage without an error with a ≥ 0.5). `ctlim` of `ZongGaussianDeficit` is kept by PyWake but never used in its calculation, with any superposition; its help says so. With `PropagateUpDownIterative` and `WeightedSum` or `CumulativeWakeSum`, PyWake keeps no blockage of its downwind pass: the simulation of the turbines leaves out the downstream blockage (the upstream pass keeps the upstream one; the field of the raster does calculate the blockage at its points); a warning says so, and `MaxSum` as the blockage superposition is refused with two turbines or more. `SquaredSum` as the blockage superposition, or as the sum of the ground of the blockage, stops PyWake if a contribution of the blockage is a speed-up, the usual in a blockage: it depends on the values, so it is warned and, if it happens, an error of the calculation. An added turbulence with a deficit that does not use the effective TI (`use_effective_ti` read as PyWake picks its key, `['TI_ilk', 'TI_eff_ilk'][use_effective_ti]`, or a class without it) is calculated but does not change the deficit: a persistent warning says so, also when the breakdown is not calculated.

The iterative loops of `WeightedSum`, `All2AllIterative` and `PropagateUpDownIterative` are observed during the calculation, without changing it. A calculation whose loops did not converge (`max_iter` reached, tolerance not met, or flow cases left out of the convergence check of `PropagateUpDownIterative`) is kept and marked as not converged in the result. If the state of a loop cannot be read, the result says «not available» with its cause, never «not converged»; the largest residual is the largest finite one, and the residuals that were not finite are counted and said.

### GaussianOverlapAvgModel without h5py

`GaussianOverlapAvgModel` reads a PyWake table and needs `h5py` and `h5netcdf`. If either library is missing or fails to load, **Calculate AEP** and the wake raster ask before calculating in both predefined and manual modes, only where PyWake would read the table (with `All2AllIterative`, with two or more selected turbines, or in the raster). **Continue** uses `CGIRotorAvg(7)` instead, recorded in the result with the installation instructions; **Cancel** calculates nothing. If a predefined model has an applicable saved decision, the dialog adapts without asking, and the result states that the saved decision was applied.

On Linux and macOS, install missing libraries with `python -m pip install h5py "h5netcdf>=1.8"` in the Python environment used by QGIS, then restart QGIS. PyWake 2.6.18 requires `h5netcdf` on all platforms. Since version 1.8, `h5netcdf` no longer depends on `h5py`; the Windows command below explicitly requires this version so pip does not install `h5py` through `h5netcdf`. On Windows with QGIS from OSGeo4W, do not install `h5py` with pip: see the untested `python3-h5py` option in the [OSGeo4W guide](VelantisWind/docs/INSTALL_OSGEO4W_PYWAKE.md#h5py-in-qgis-from-osgeo4w).

### Not offered, and why

the classes that need tables the plugin does not provide (FugaDeficit, FugaMultiLUTDeficit, FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel); NoWakeDeficit, because the gross AEP already gives the case without wakes and blockage (the blockage-only scenario is out of scope); and wake deflection, because the plugin does not compute the AEP with yaw.

### Loss breakdown

The result gives, per turbine, per model and for the farm, the AEP without wakes nor blockage (A_0), the net AEP of the configuration (A_WTB) and, with the variants, the AEP with wakes only (A_W), with wakes and added turbulence (A_WT) and with wakes and blockage (A_WB), all with the same engine and inputs. From them, with their sign: the wake loss L_W = A_0 − A_W, the impact of the added turbulence Δ_T = A_WT − A_W, the impact of the blockage Δ_B = A_WTB − A_WT (A_WTB − A_W when no added turbulence is modelled), the total loss L_total = A_0 − A_WTB = L_W − Δ_T − Δ_B and, as a diagnostic outside the balance, the turbulence-blockage interaction. A positive loss takes production away and a positive impact adds it; percentages are over A_0. A term that was not modelled, not requested or that failed is «not available», never zero. Results of earlier versions are read with their own fields.

### The physics in the API

`EnergyRunConfig` and `compute_aep_from_ui()`/`compute_and_update()` take the physics in `wake_physics`:

```python
wake_physics = {
    "version": 1,
    "engine": "All2AllIterative",
    "deficit": "NiayifarGaussianDeficit",
    "deficit_params": {"ceps": 0.25},          # the rest: the signature values
    "rotor": {"class": "CGIRotorAvg", "n": 9},  # None: no rotor average; left out: the signature's
    "superposition": "LinearSum",
    "turbulence": "CrespoHernandez",
    "blockage": "SelfSimilarityDeficit2020",
    "blockage_params": {"use_effective_ws": False},
    "blockage_superposition": "LinearSum",
}
```

The arguments of the other objects go with them, as `{"class": …, <argument>: <value>}`, and an argument whose value is another PyWake class takes it the same way, recursively (for example `"ground": {"class": "MultiMirror", "n_reps": 1, "superpositionModel": {"class": "SquaredSum"}}`, `"engine": {"class": "All2AllIterative", "convergence_tolerance": None}`, or `"rotorAvgModel": {"class": "EqGridRotorAvg", "n": 3}` in `blockage_params`); `CGIRotorAvg` takes `n` in {4, 7, 9, 21} (its name alone, the 7 of its signature). A key left out, or `""`, takes the signature value; `None` or `"NONE"` asks for the absence. Inside a component, an argument left out takes the signature value and `None` is passed as such (where PyWake takes it: no model, inherit, or one iteration); `""` and `"NONE"` are not read there as an omission or an absence. The fields of the previous schema (`wfm_engine`, `wake_deficit_model`, `superposition_model`, `rotor_avg_model`, `turbulence_model`, `blockage_deficit_model`, `wake_deficit_kwargs`, `include_turbulence`, `include_blockage`, `include_rotor_avg`) are still accepted and translated once, with a closed table of the keys the earlier dialog used (`PDW`, `A2A`, `PUD`, `BG`, `NIA`, `TG`, `ZG`, `NOJ`, `TNOJ`, `CGI7`/`CGI9`/`CGI21`, `RC`, `EQ`, `GO`, `LIN`, `SQR`, `MAX`, `WGT`, `STF2005`, `STF2017`, `GCL`, `CH`, `SS2020`, `SS`, `VC`, `VD`, `HI`, `NONE`) or the exact class names; the result says how the request was translated. `AUTO`, `TURBOPARK` and any other key are refused, as is a request that mixes both schemas.

---

## Main Energy outputs

The Energy workflow can produce:

- Gross AEP without wakes nor blockage (A_0).
- Net AEP of the configuration.
- The signed loss breakdown: wake loss, impacts of the added turbulence and of the blockage, total loss and their interaction (see [Loss breakdown](#loss-breakdown)), in MWh and in % of the gross AEP.
- The same per turbine and per turbine model, with the state of each term.
- Ambient and effective TI per turbine.
- Results grouped by turbine model.
- Directional and sector summaries where available.
- The configuration selected and the configuration executed, read from the PyWake objects, with their differences.
- Persistent warnings of PyWake behaviours and the convergence of the iterative loops.
- Resource-domain extent overlay.
- Per-turbine CSV exports.
- Human-readable HTML-style reports.
- Updated QGIS turbine layers.
- Project-level summary layers.
- Individual AEP symbology.
- `model_perf_pct` fields.
- `model_rank` fields.
- Georeferenced wake rasters with a JSON audit file.

The model-relative performance fields allow turbines with different rated powers to be compared within their own turbine-model group.

Energy-based graduated symbology makes it possible to identify higher- and lower-performing turbines directly on the map.

---

## Resource parameters

With a WRG, the AEP is computed on a multiple of its sectors as calculation directions (7 per sector initially: 12 sectors → 84), at the centres of the subdivisions of each sector, with `nearest` or `linear` directional interpolation, Speedup `none` (the local Weibull climate of each position) and the wind speeds that cover the operating band of the turbines, with a step of 1, 0.5 or 0.25 m/s. A GRD resource uses the directions and wind speeds of its PyWake site. Both are annualised with 8766 h/year. In the Energy dialog the WRG parameters are chosen in **Resource parameters**, under the WRG.

Memory grows roughly with turbines² × directions × wind speeds; a layout of several hundred turbines can exhaust the available memory. Reduce the number of directions or choose a coarser wind-speed step. See the [Energy module guide](VelantisWind/docs/ENERGY_MODULE.md).

---

## Wake raster

The wake raster computes a georeferenced flow map for the most energetic or a selected wind direction, with the configuration and the physical inputs of the AEP (the same classes, the resource with its TI, the air density). It runs as a cancellable QGIS task and adds free-flow speed, effective speed, deficit in m/s and in %, and terrain elevation when available, together with a JSON audit file that records the selected and executed configuration, the TI, the convergence and the numerical precision.

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

In the Energy dialog, the envelopes are those of the layers chosen in its rows, the same park that the AEP calculates: alternative layouts in other layers are not compared with each other. A layout imported from Noise or Shadow in a CRS projected in metres gets its own envelope layer at import.

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
3. Creates or refreshes the linked envelope layer (in Energy, unless the spacing envelopes are switched off).
4. Recalculates conflicts: in Energy, against the other layers of its rows; for a layout imported from Noise or Shadow in a CRS projected in metres, only within that layer, at import.

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

1. Download `VelantisWind-0.1.17.zip` from the [GitHub releases page](https://github.com/Velantis-Wind/VelantisWind/releases).
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

Install `py_wake==2.6.18`, `h5py` and `h5netcdf>=1.8` in the Python environment used by QGIS. PyWake 2.6.18 requires `h5netcdf`. Since version 1.8, `h5netcdf` no longer depends on `h5py`, so the Windows command below does not install `h5py` through `h5netcdf`. On Linux and macOS, install all three with pip. On Windows with QGIS from OSGeo4W, do not install `h5py` with pip; see the OSGeo4W option below. The predefined models and the plugin's consistency with PyWake were checked with version 2.6.18; the dialog does not warn if a different version is installed. `h5py` and `h5netcdf` are needed by `GaussianOverlapAvgModel`, the rotor average used by the predefined models NiayifarGaussian and TurbOPark.

On Linux and macOS, in the Python environment used by QGIS:

```bash
python -m pip install py_wake==2.6.18 h5py "h5netcdf>=1.8"
python -c "import py_wake, h5py, h5netcdf; print('PyWake OK:', py_wake.__file__)"
```

On Windows, with QGIS from OSGeo4W:

1. Close QGIS.
2. Open **OSGeo4W Shell**.
3. Run:

```bash
python -m pip install py_wake==2.6.18 "h5netcdf>=1.8"
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

4. Restart QGIS.

Expected problem on Windows (not reproduced there): the `h5py` pip wheel is expected to fail to load inside QGIS from OSGeo4W (`ImportError: DLL load failed while importing defs`). The wheel bundles an HDF5 library named `hdf5.dll`, the same name as the library QGIS loads from OSGeo4W. Windows reuses a DLL already loaded under that name. Inspection of the binaries found that OSGeo4W HDF5 1.14.6 lacks 19 of the 522 symbols required by the `h5py` 3.16.0 wheel (HDF5 2.0.0). For this reason, `pip install h5py` is not offered as a solution on Windows.

An option to try is installing `python3-h5py` through the OSGeo4W installer. This package is built against OSGeo4W's HDF5 and is not included in `qgis-full`. This option has not been tested. The command above ensures `h5netcdf>=1.8` is installed by pip; it does not need to be installed through OSGeo4W.

If `h5py` or `h5netcdf` is missing or fails to load when PyWake would read the `GaussianOverlapAvgModel` table (for the predefined models NiayifarGaussian and TurbOPark, with two or more turbines or in a wake raster), the dialog asks before calculating in both predefined and manual modes. **Continue** uses `CGIRotorAvg(7)` and records the adaptation in the results; **Cancel** calculates nothing. If a predefined model has an applicable saved decision, the dialog adapts without asking, and the result states that the saved decision was applied.

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
- A model combination PyWake cannot calculate is refused with its reason; nothing is replaced automatically.
- Wind-resource quality and turbine curves strongly influence AEP.
- WRG calculations without TI rasters may use a uniform fallback TI.
- AEP memory grows roughly with turbines² × directions × wind speeds (with 84 directions × 71 wind speeds, about 2.7 GB for 300 turbines and more than 6 GB for 600).
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
