# Noise spectrum library

This folder contains optional octave-band spectral templates used by the ISO-aligned noise engine when no manufacturer/measured spectrum is supplied.

## Important

These files are **reference template shapes**, not manufacturer-certified acoustic data. For project-grade studies, replace them with measured or manufacturer-provided octave-band sound power spectra.

CSV format:

```csv
freq_hz,Lw_dB_rel
63,-3.0
125,-1.5
...
```

The values are relative spectral shapes. The plugin shifts the whole spectrum so that the A-weighted energetic sum matches the selected global LwA value.

Priority used by the plugin:

1. Custom spectrum CSV selected by the user.
2. Matching CSV in this library.
3. Built-in model template.
4. Generic template.
