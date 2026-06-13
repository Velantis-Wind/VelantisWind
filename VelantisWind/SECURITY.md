# Security Policy

Velantis Wind is an experimental QGIS plugin for wind-farm pre-assessment. The project is released under GPL-3.0-or-later and is intended to be transparent, inspectable and community-testable.

---

## Supported versions

Security and critical bug reports should target the latest experimental release unless otherwise agreed.

| Version | Status |
|---|---|
| `0.1.13` | Supported for experimental feedback |
| Older ZIPs | Superseded |

---

## Reporting a vulnerability

Please do not publish suspected security issues publicly before they have been reviewed.

Report security concerns through the contact channel listed in `metadata.txt` / the Velantis Wind website, including:

```text
- Plugin version.
- QGIS version.
- Operating system.
- Clear reproduction steps.
- Screenshots/logs if relevant.
- Whether the issue requires a specific project, layer or external file.
```

---

## Dependency note

The Energy/AEP module depends on external scientific Python packages, especially PyWake. These packages must be installed by the user in the QGIS Python environment. Velantis Wind does not automatically install external dependencies from inside QGIS.

---

## Data handling note

The plugin is designed to run locally inside QGIS. Users should still avoid sharing confidential project data in public bug reports. When possible, reproduce issues with simplified or anonymized layers.
