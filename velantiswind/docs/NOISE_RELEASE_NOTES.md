# Noise module release notes

## Scope

The noise module is intended for preliminary wind-farm noise screening and GIS-based
layout iteration. The ISO mode is **ISO-aligned**: it follows an octave-band
outdoor propagation structure, but it is not a certified regulatory replacement.

## Physics implemented

- Multi-source energetic summation by receiver.
- Octave-band source spectra from imported/measured spectra or template-based
  reconstruction from global LwA.
- A-weighted energetic summation at receiver level.
- Adiv geometric divergence.
- Aatm atmospheric absorption using the plugin's simplified tabular/correction
  implementation.
- Agr ground effect using one G value per path: global/manual or G_eff from a
  land-use layer.
- Abar topographic screening from MDT/DSM using the compatibility dominant-obstacle and
  Fresnel-style logic.


## Source spectra and spectrum library

The folder `noise_core/spectrum_library/` contains optional reference spectral
templates. These templates are used only when the user has not supplied a
custom octave-band spectrum for the acoustic source group.

The library is not mandatory for the engine to run, because the code also has
built-in fallback templates. However, keeping CSV templates in the repository is
useful for transparency: testers can see and replace the reference spectral
shape that is shifted to match the selected global LwA.

For technical/commercial studies, users should prefer manufacturer or measured
octave-band sound power spectra over the bundled generic templates.

## Known limitations

- Aatm is simplified and does not implement the full analytical ISO 9613-1 model.
- Agr is a practical approximation, not a full certification-grade ground model.
- Abar uses one dominant terrain obstacle per path and capped attenuation.
- Directivity correction Dc is assumed to be 0 dB.
- Long-term meteorological correction Cmet is not applied.
- Wind-direction/downwind occurrence weighting is not yet modelled.
- Multiple turbine/acoustic types are supported through separate source groups or
  separate turbine layers. Per-feature turbine-type mixing inside one layer is a
  future improvement.

## MDT/Abar interpretation

If the report shows `Abar = 0` for the critical receiver while the attenuation
statistics show non-zero Abar elsewhere, this usually means the noisiest receptor
has direct line of sight to its dominant turbine. The MDT is still active; it is
just not producing screening on that specific dominant path.

## Recommended experimental release smoke tests

1. Fast engine, no MDT, no raster.
2. ISO-aligned engine, no MDT, no raster.
3. ISO-aligned engine with MDT, no raster.
4. ISO-aligned engine with MDT and raster.
5. Two turbine/acoustic source groups in two separate layers.
