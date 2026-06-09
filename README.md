# VelantisWind

> Open-source wind energy workflows, directly inside QGIS.

VelantisWind is a free and open-source QGIS plugin designed to support early-stage wind farm analysis, validation workflows and geospatial pre-assessment tasks.

The plugin brings wind energy calculations into a GIS environment, helping users work with layouts, wind resource data, wake effects, noise assessment and shadow flicker analysis directly inside QGIS.

---

## Project status

VelantisWind is currently under active development and is being released as an experimental open-source QGIS plugin.

The project is open for wider testing, validation with real wind farm cases and future community contributions.

VelantisWind is designed to support **QGIS 3.x** and **QGIS 4.0**. The plugin has been developed and tested mainly on QGIS 3.x, while QGIS 4.0 / Qt6 compatibility is being actively tested and improved.

For production or validation workflows, QGIS 3.x LTR is currently recommended. QGIS 4.0 users are welcome to test the plugin and report any compatibility issues.

---

## What VelantisWind does

| Module                | Purpose                                                                       |
| --------------------- | ----------------------------------------------------------------------------- |
| Energy assessment     | Estimate Annual Energy Production from wind resource data and turbine layouts |
| Wake-aware evaluation | Analyse layout performance considering wake effects                           |
| Noise assessment      | Support early-stage acoustic impact analysis                                  |
| Shadow flicker        | Estimate potential shadow flicker impact around wind turbines                 |
| GIS workflows         | Work directly inside QGIS with layers, rasters, layouts and project data      |
| Reporting             | Generate practical outputs for technical review and validation                |

---

## Why VelantisWind?

Wind farm pre-assessment often requires combining wind resource data, turbine layouts, GIS layers, environmental constraints and technical calculations.

VelantisWind aims to provide an open-source foundation for these workflows inside QGIS.

The goal is to make wind energy analysis more:

* Transparent
* Accessible
* Adaptable
* GIS-native
* Useful for early-stage project evaluation
* Suitable for validation, research and technical collaboration

VelantisWind is designed to complement existing technical workflows, not replace the expertise, validation processes or engineering judgement required in professional wind energy studies.

---

## Main features

Current and planned capabilities include:

* QGIS-based wind farm layout analysis
* Annual Energy Production estimation
* Wake-aware layout evaluation
* Wind resource data handling
* Noise assessment workflows
* Shadow flicker assessment workflows
* GIS layer integration
* Raster and vector-based project analysis
* Exportable results for technical review
* Support for validation with real project data

---

## Who is it for?

VelantisWind is designed for:

* Wind energy engineers
* Renewable energy consultants
* Developers working on early-stage wind projects
* GIS users in renewable energy
* Universities and research groups
* Students working on wind energy, GIS or environmental assessment
* Open-source contributors interested in renewable energy tools

---

## Installation

VelantisWind is a QGIS plugin. Some parts of the plugin may run with the standard QGIS Python environment, but the **Energy / AEP module requires PyWake** for wake-aware energy calculations.

PyWake is **not a QGIS plugin**, so it will not appear in the QGIS Plugin Manager. It is an external Python library that must be installed in the same Python environment used by QGIS.

---

## Recommended environment

| Component          | Recommended                       |
| ------------------ | --------------------------------- |
| QGIS               | QGIS 3.x LTR or QGIS 4.0          |
| Operating system   | Windows 10 / Windows 11           |
| Python environment | QGIS / OSGeo4W Python environment |
| PyWake version     | `py_wake==2.6.18`                 |

For production or validation workflows, QGIS 3.x LTR is currently recommended. QGIS 4.0 compatibility is supported and under active testing.

---

## Installing PyWake on Windows

### Step 1 — Open OSGeo4W Shell

On Windows, QGIS usually installs a tool called **OSGeo4W Shell**.

To open it:

1. Open the Windows Start menu.
2. Search for `OSGeo4W Shell`.
3. Open it.

This shell is important because it uses the same Python environment as QGIS.

Do not install PyWake from a normal Windows terminal unless you are sure it points to the same Python environment used by QGIS.

---

### Step 2 — Install PyWake

Inside OSGeo4W Shell, run:

```bash
python -m pip install py_wake==2.6.18
```

Wait until the installation finishes.

If the installation completes successfully, restart QGIS before using VelantisWind.

---

### Step 3 — Verify the installation

To check that PyWake was installed correctly, run this command in OSGeo4W Shell:

```bash
python -c "import py_wake; print('PyWake installed successfully')"
```

If no error appears, PyWake is available in the QGIS Python environment.

You can also check the installed package with:

```bash
python -m pip show py_wake
```

---

## Installing VelantisWind from ZIP

After installing PyWake, open QGIS and install VelantisWind from the plugin ZIP file:

1. Open QGIS.
2. Go to:

```text
Plugins → Manage and Install Plugins
```

3. Open the tab:

```text
Install from ZIP
```

4. Select the VelantisWind ZIP file.
5. Click:

```text
Install Plugin
```

6. Restart QGIS if needed.

After installation, VelantisWind should appear in the QGIS plugin menu or toolbar.

---

## Full installation summary

The recommended installation process is:

1. Open **OSGeo4W Shell**.
2. Install PyWake:

```bash
python -m pip install py_wake==2.6.18
```

3. Restart QGIS.
4. Install VelantisWind from ZIP:

```text
Plugins → Manage and Install Plugins → Install from ZIP
```

5. Select the VelantisWind ZIP package.
6. Enable and open the plugin.

---

## Troubleshooting

### QGIS says that PyWake is missing

Make sure PyWake was installed from **OSGeo4W Shell**, not from a normal system terminal.

Run:

```bash
python -m pip show py_wake
```

inside OSGeo4W Shell.

If PyWake is not found, install it again:

```bash
python -m pip install py_wake==2.6.18
```

Then restart QGIS.

---

### The plugin was installed, but the Energy / AEP module does not run

Please check:

* PyWake is installed in the QGIS Python environment.
* QGIS was restarted after installing PyWake.
* The selected wind resource files are valid.
* The turbine and layout input files are correctly selected.
* The full error message has been copied for debugging.

If the issue continues, please report the full traceback.

---

### Multiple QGIS versions are installed

If you have more than one QGIS installation, make sure you open the **OSGeo4W Shell** corresponding to the same QGIS version where VelantisWind is installed.

Installing PyWake into one QGIS environment will not automatically make it available in another QGIS installation.

---

### Permission or installation errors

If the installation fails due to permissions, try opening OSGeo4W Shell as administrator.

Right-click:

```text
OSGeo4W Shell → Run as administrator
```

Then run:

```bash
python -m pip install py_wake==2.6.18
```

---

## Documentation

Documentation is currently being prepared and expanded.

Planned documentation sections include:

| Section               | Content                                                       |
| --------------------- | ------------------------------------------------------------- |
| Getting started       | Basic installation and first project setup                    |
| Energy module         | Inputs, turbine data, wind resource data and AEP outputs      |
| Noise module          | Receptors, input data, calculation workflow and outputs       |
| Shadow flicker module | Required layers, time configuration and output interpretation |
| Validation            | Comparison workflows using real or reference cases            |
| Troubleshooting       | Common installation and execution issues                      |
| Developer notes       | Structure of the plugin and contribution guidelines           |

---

## Validation

VelantisWind is being tested and validated with real and representative wind farm cases.

Validation work may include comparison against reference calculations, internal workflows, real project outputs or technical feedback from beta testers and collaborators.

If you are interested in testing VelantisWind with real project data or helping validate the plugin, please contact the project team.

Please avoid sharing confidential project data in public GitHub issues.

---

## Known limitations

VelantisWind is intended for early-stage analysis, validation workflows and geospatial pre-assessment tasks.

The results should be reviewed by qualified professionals before being used in engineering, permitting, investment or construction decisions.

Current limitations may include:

* Ongoing validation against commercial and internal reference workflows
* Dependency on correct wind resource, turbine and layout input data
* Possible installation issues depending on the QGIS Python environment
* Module-specific assumptions that should be reviewed for each project
* Ongoing testing across QGIS 3.x and QGIS 4.0 environments

---

## Reporting issues

When reporting installation or execution issues, please include:

* QGIS version
* Windows version
* VelantisWind version
* Full error message or traceback
* Whether PyWake was installed from OSGeo4W Shell
* Output of:

```bash
python -m pip show py_wake
```

Please avoid sharing confidential project data in public GitHub issues.

---

## Support the project

VelantisWind is free and open source.

If the tool is useful for your work, you can support the project through one-time contributions, monthly sponsorship or technical collaboration.

Support helps fund:

* Plugin maintenance
* Documentation
* Tutorials and examples
* Validation with real wind farm cases
* Translations
* QGIS compatibility improvements
* New features requested by users
* Adaptation to practical workflows

More information is available here:

[Support VelantisWind](SUPPORT.md)

---

## Academic collaboration

VelantisWind is open to collaboration with universities and research groups.

One possible collaboration model is to connect the project with future Bachelor’s and Master’s thesis projects, so that student work with real technical value can contribute to the evolution of the plugin.

Potential academic collaboration areas include:

* Wind energy analysis
* GIS-based renewable energy workflows
* Environmental assessment
* QGIS plugin development
* Validation studies
* Documentation and educational material
* New modules that may be integrated into the project

Academic contributions can be reviewed case by case and, when technically aligned with the project, may be integrated into the open-source repository.

---

## Contributing

Community contributions are welcome as the project evolves.

Future contribution paths may include:

* Bug reports
* Feature requests
* Documentation improvements
* Translation support
* Validation cases
* New QGIS workflow ideas
* Code contributions through pull requests

Contribution guidelines will be expanded as the project matures.

---

## License

VelantisWind is free and open source.

This project is distributed under the GNU General Public License v3.0.

See the `LICENSE` file for details.

---

## Contact

For collaboration, validation cases, academic partnerships, sponsorship or technical workflow discussions, please contact:

[info@velantiswind.com](mailto:info@velantiswind.com)

