# Release test checklist — Velantis Wind 0.1.15

Use this checklist before publishing the ZIP to GitHub or the QGIS plugin portal.

## 1. Install from ZIP

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the release ZIP.
4. Enable **Velantis Wind**.
5. Open the Hub from the toolbar/menu.

## 2. Language switching

Test the Hub in this order: Spanish → English → French → German → Spanish.

Confirm that these areas update without mixed-language leftovers:

- Module cards.
- Project summary.
- Support button.
- Layout-optimization panel.
- Energy, Noise and Shadow Flicker entry labels.

## 3. Module smoke tests

- Open Energy/AEP and return to the Hub.
- Open Noise and return to the Hub.
- Open Shadow Flicker and return to the Hub.
- Change language again after visiting each module.

## 4. Energy dependency

Energy/AEP requires PyWake in the QGIS Python environment. On Windows/OSGeo4W:

```bash
python -m pip install py_wake==2.6.18
python -c "import py_wake; print('PyWake OK:', py_wake.__file__)"
```

Noise and Shadow Flicker can be smoke-tested without PyWake.

## 5. Packaging checks

- The ZIP contains one top-level folder named `VelantisWind`.
- `metadata.txt` version is `0.1.15`.
- No `__pycache__`, `.pyc`, local build folders or temporary files are included.

## Hub UI smoke test

Before testing this ZIP in QGIS, remove any previous VelantisWind folder from the QGIS profile or restart QGIS after reinstalling, so an older hub dialog is not kept alive in memory.

Expected hub home screen:
1. Title and subtitle centered.
2. Language selector in a rounded group.
3. Three module cards only: Energy/AEP, Noise, Shadow Flicker.
4. Velantis logo centered below the cards.
5. Layout optimization strip below the logo, with a prominent gradient CTA button and commercial text about layout + wake-steering co-optimization.
6. Project summary below the optimization strip.
7. Support button pinned at the lower-right footer.

Switch ES -> EN -> FR -> DE -> ES. The layout must remain visually identical; only labels should change.


## 6. Noise report smoke test

Run one Noise calculation with the ISO-aligned engine and export the technical report.

Check that:

- Receiver coverage is explicit: compliance is only claimed for receivers inside the calculation radius.
- The report does not show `Spectrum source: -` when an OEM/CSV spectrum was used.
- Absolute/imported spectra do not display an empty `S_b^ref` column.
- Raster resolution is described as map visualization only, not as the point-receiver calculation resolution.
- Unusual meteorological inputs show a review warning.
- The physics section appears as a technical appendix rather than the main executive body.
