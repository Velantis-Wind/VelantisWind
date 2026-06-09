# Contributing to Velantis Wind

Thank you for helping improve Velantis Wind.

Velantis Wind is an experimental QGIS plugin for wind-farm pre-assessment. Useful contributions include bug reports, documentation improvements, test cases, validation comparisons, translations and carefully reviewed code changes.

---

## Useful feedback

When reporting a problem, include:

```text
- QGIS version.
- Operating system.
- Plugin version.
- Module used: Energy/AEP, Noise or Shadow Flicker.
- Input layer/resource summary.
- Screenshots of the settings.
- Full traceback from the QGIS Python console, if available.
- Whether DEM/DSM, raster, background task or parallel execution was enabled.
```

For Energy/AEP issues, also include:

```text
- PyWake version.
- Wind-resource type.
- Turbine model/curve source.
- Wake model and optional physics settings.
```

---

## Development principles

- Keep UI code separated from calculation logic where possible.
- Avoid changing numerical behaviour and architecture in the same commit.
- Document physical assumptions and limitations clearly.
- Keep experimental outputs reproducible: record model options, resource type, turbine curve and plugin version.
- Prefer small, reviewable changes.

---

## Before submitting a code change

Run from the plugin folder:

```bash
python -m compileall -q .
```

Recommended:

```bash
bandit -r .
detect-secrets scan .
flake8 .
```

Then run the relevant QGIS smoke tests described in `docs/RELEASE_CHECKLIST.md`.

---

## Documentation changes

Documentation improvements are welcome. Keep public-facing docs clear about:

- Experimental release status.
- External PyWake dependency for Energy/AEP.
- Noise and Shadow screening limitations.
- CRS, units and input-data quality requirements.

---

## License

By contributing, you agree that your contribution can be distributed under the project license: GPL-3.0-or-later.
