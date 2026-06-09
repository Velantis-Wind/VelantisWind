# Installing PyWake for VelantisWind

VelantisWind uses PyWake for wake-aware Energy / AEP calculations.

PyWake is **not a QGIS plugin**. It will not appear in the QGIS Plugin Manager. It is an external Python library and must be installed in the **same Python environment used by QGIS**.

This guide explains the recommended installation process on Windows using **OSGeo4W Shell**.

---

## Quick installation

1. Close QGIS.
2. Open **OSGeo4W Shell** from the Windows Start menu.
3. Run:

```bat
python -m pip install py_wake==2.6.18
```

4. Verify the installation:

```bat
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

5. Restart QGIS.
6. Install or enable VelantisWind.

---

## When is PyWake required?

PyWake is required for the **Energy / AEP module**.

If PyWake is missing, the plugin may still open, but wake-aware energy calculations will not run correctly.

Other parts of VelantisWind, such as the interface, documentation, Noise module or Shadow Flicker module, may be tested independently depending on the selected workflow.

---

## Recommended environment

| Component | Recommended |
|---|---|
| QGIS | QGIS 3.x LTR or recent stable version |
| QGIS 4 / Qt6 | Experimental support, pending wider real-world testing |
| Operating system | Windows 10 / Windows 11 |
| Python environment | QGIS / OSGeo4W Python |
| PyWake version | `py_wake==2.6.18` |

VelantisWind should be installed in QGIS, but PyWake must be installed separately in the QGIS Python environment.

---

## Step 1 — Open OSGeo4W Shell

On Windows, QGIS normally installs **OSGeo4W Shell**.

Open it from:

```text
Windows Start Menu → OSGeo4W Shell
```

Use OSGeo4W Shell instead of:

- normal Windows Command Prompt,
- PowerShell,
- Anaconda Prompt,
- a standalone Python installation.

This is important because QGIS uses its own Python environment.

---

## Step 2 — Check the Python environment

Inside OSGeo4W Shell, run:

```bat
python -c "import sys; print(sys.executable); print(sys.version)"
```

You should see a Python executable belonging to your QGIS / OSGeo4W installation.

Example paths may look like:

```text
C:\OSGeo4W\apps\Python312\python.exe
```

or:

```text
C:\Users\<USER>\AppData\Local\Programs\OSGeo4W\apps\Python312\python.exe
```

The exact path depends on how QGIS was installed.

---

## Step 3 — Check pip

Run:

```bat
python -m pip --version
```

If pip works, continue.

If pip is missing, try:

```bat
python -m ensurepip --upgrade
python -m pip --version
```

If this does not work, your QGIS / OSGeo4W installation may need to be repaired or managed through the OSGeo4W setup tool.

---

## Step 4 — Install PyWake

Recommended command:

```bat
python -m pip install py_wake==2.6.18
```

This installs the PyWake version used for the current VelantisWind experimental release.

If your package index normalizes the name differently, this equivalent command may also work:

```bat
python -m pip install py-wake==2.6.18
```

After installation, restart QGIS.

---

## Step 5 — Verify PyWake

Run this in OSGeo4W Shell:

```bat
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

You can also check the installed package information with:

```bat
python -m pip show py_wake
```

If no error appears, PyWake is installed in the OSGeo4W Python environment.

---

## Step 6 — Verify from inside QGIS

Open QGIS and go to:

```text
Plugins → Python Console
```

Run:

```python
import sys
print(sys.executable)

import py_wake
print("PyWake OK:", py_wake.__file__)
```

The Python executable should correspond to the same QGIS / OSGeo4W environment where PyWake was installed.

---

## Step 7 — Install VelantisWind from ZIP

After installing PyWake:

1. Open QGIS.
2. Go to:

```text
Plugins → Manage and Install Plugins
```

3. Open:

```text
Install from ZIP
```

4. Select the VelantisWind ZIP file.
5. Click:

```text
Install Plugin
```

6. Restart QGIS if needed.

---

## Common problems

### QGIS says `No module named py_wake`

PyWake was probably installed into the wrong Python environment.

Check from OSGeo4W Shell:

```bat
where python
python -c "import sys; print(sys.executable)"
python -m pip show py_wake
```

Then reinstall from OSGeo4W Shell:

```bat
python -m pip install py_wake==2.6.18
```

Restart QGIS afterwards.

---

### The Energy module still fails after installing PyWake

Check PyWake from inside the QGIS Python Console:

```python
import py_wake
print(py_wake.__file__)
```

If this fails inside QGIS, PyWake is not installed in the environment QGIS is actually using.

---

### Multiple QGIS versions are installed

If you have more than one QGIS version installed, each one may use a different Python environment.

Install PyWake from the **OSGeo4W Shell that belongs to the same QGIS installation** where VelantisWind is installed.

---

### Permission denied

Try opening OSGeo4W Shell as administrator:

```text
Right click → Run as administrator
```

Then run:

```bat
python -m pip install py_wake==2.6.18
```

If you work in a managed company environment, ask your IT administrator before modifying the QGIS Python environment.

---

### pip tries to build packages from source

If installation fails because pip tries to compile scientific packages, first update the pip tools:

```bat
python -m pip install --upgrade pip setuptools wheel
```

Then retry:

```bat
python -m pip install py_wake==2.6.18
```

Avoid replacing QGIS / OSGeo4W GDAL packages with unrelated GDAL wheels unless you know exactly what you are doing.

---

### Corporate proxy or SSL issues

If your company uses a proxy, configure pip using your organization’s recommended settings.

A typical command looks like:

```bat
python -m pip install py_wake==2.6.18 --proxy http://proxy.company.com:PORT
```

Do not share proxy credentials in screenshots, logs or GitHub issues.

---

## Recommended smoke test

Before running a large Energy / AEP case, run:

```bat
python -c "import py_wake, numpy, scipy, xarray; print('VelantisWind Energy dependencies OK')"
```

Then open QGIS and run a small test case before using large layouts or high-resolution wind resource files.

---

## Why VelantisWind does not install PyWake automatically

VelantisWind does not automatically modify the user’s QGIS Python environment.

Installing scientific Python packages from inside a QGIS plugin can be risky, especially in company-managed environments. For this reason, PyWake installation is documented and left under the user’s control.

---

## Contact

For installation support, beta testing or technical questions, please contact:

**info@velantiswind.com**
