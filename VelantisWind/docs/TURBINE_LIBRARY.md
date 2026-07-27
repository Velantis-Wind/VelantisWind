# Turbine curve library

VelantisWind 0.1.16 uses explicit provenance and does not present a parametric curve as an official manufacturer curve.

## Quality levels

- `public_reference`: traceable public/reference data packaged with a source name and URL.
- `spec_based_approximation`: commercial model geometry and available operating points anchored to an official public specification; VelantisWind-generated power/CT shape. Not OEM or certified.
- `approximate`: manufacturer-neutral parametric curve for early screening only.
- `user_edited`: a packaged curve that the user changed before creating the turbine.
- `user_defined`: manually entered or imported by the user.

The QGIS turbine dialog shows the quality and source before a curve is loaded. The same metadata is stored with the model and on generated turbine layers (`velantis/curve_quality`, `velantis/curve_source`, `velantis/curve_source_url`).

The spec-based and generic curves use nominal power, rotor diameter, air density 1.225 kg/m³, a bounded power coefficient and an above-rated CT decay. They are useful for preliminary comparison and interface testing, but they must not be presented as OEM data or used as a contractual power-performance basis.
