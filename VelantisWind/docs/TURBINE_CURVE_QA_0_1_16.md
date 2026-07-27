# Turbine curve QA — 0.1.16

Automated integrity checks were run for every packaged curve:

- unique candidate identifier and existing curve file;
- wind speed strictly increasing;
- power non-negative;
- CT within `[0, 1]`;
- rated power reached within numerical tolerance;
- an explicit post-cut-out zero-power/zero-CT region where applicable.

Additional checks for all Velantis-generated `approximate` and `spec_based_approximation` curves:

- power growth without negative steps before rated operation;
- maximum implied Cp below the Betz limit at `rho = 1.225 kg/m³`;
- CT decay above rated speed and zero CT outside operation.

The eight new spec-based approximations use a uniform 0.5 m/s grid from 0 to 30 m/s. The 30 existing generic classes retain their packaged 0–26 m/s tabulation, including an explicit point immediately after cut-out to represent shutdown without interpolating a false power tail.

Result: **42/42 packaged candidates PASS integrity checks**. The eight new spec-based curves also pass the parametric physical-plausibility checks; their highest implied Cp is below 0.46.

Catalogue composition:

- 4 public/reference curves;
- 8 approximations anchored to public manufacturer specifications;
- 30 manufacturer-neutral generic approximations.

This QA confirms file integrity and internal plausibility. It does not certify a curve for a commercial turbine, site density, controller mode, degradation state, turbine variant or contractual power-performance assessment.
