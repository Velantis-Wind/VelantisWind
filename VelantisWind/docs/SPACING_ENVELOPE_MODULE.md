# Spacing Envelope Module

**Purpose:** visual, real-time validation of minimum inter-turbine spacing while designing a layout in Interactive Map mode.

The Spacing Envelope draws a semi-transparent ellipse (the *spacing envelope*) around every wind turbine in every turbine-model layer associated with the project. The ellipse represents the **minimum center-to-center separation**: if two envelopes overlap, the two turbines are closer than the configured threshold and the envelopes turn red instantly.

> **Important:** this is a geometric screening aid for manual layout design. It does not replace wake modelling, micrositing constraints or any regulatory setback analysis.

---

### Model-specific ellipse dimensions

Each turbine model stores its own longitudinal and crosswind spacing, orientation mode and fallback angle in the Energy model definition and, once created, on the associated turbine layer (`velantis/spacing_long_d`, `velantis/spacing_trans_d`, `velantis/spacing_mode` and `velantis/spacing_angle_deg`). The panel contains an explicit **wind turbine model selector**. Edit the values and press **Apply new configuration** to persist and rebuild only the selected model. A defined model appears in that selector even before it has a point layer, labelled as *no layer*, so its ellipse can be configured before loading the coordinate CSV. Older layers without these properties are initialized from the application defaults. Per-turbine ellipses drawn on screen still take priority over the model template.

## What it does

- Draws one semi-transparent ellipse per turbine, centered on the exact turbine position (the turbine point stays visible on top).
- Orients the ellipse along the **most energetic wind sector**, computed from the loaded WRG, or along a direction the user defines — including drawing the whole ellipse **directly on the map**.
- Validates spacing continuously while turbines are added, moved or deleted in Interactive Map mode, with three statuses:

  | Status | Meaning | Style |
  |---|---|---|
  | OK | No conflict | Turquoise fill, ~28 % opacity |
  | Near the limit | Free distance below 10 % of the threshold | Orange fill |
  | Spacing conflict | Envelopes overlap → separation violated | Red fill, strong outline |

- Applies the selected **validation level**: *Visualization only* (colors), *Warn on conflict* (adds a message-bar warning), or *Block insertion on conflict* (a turbine whose envelope would overlap an existing one cannot be inserted).
- Exports all envelope layers to **GeoPackage**, using one table per turbine model.

---

## Where to find it

There are two entry points to the **same shared configuration**:

1. **Main Energy/AEP dialog** — the **Spacing envelopes…** button in the *Turbine models* group, directly below the CSV coordinate import rows. It opens a non-modal configuration dialog, so envelopes can be set up and previewed on the map before entering Interactive Map mode. Pressing *Define ellipse on screen* from here hides the dialogs, lets you draw on the canvas, and restores them when the drawing tool exits.
2. **Interactive Map dock** — the **Spacing envelope** group between the ambient-TI group and the Actions group, for live validation while editing the layout.

Both embed the same panel and drive a single shared controller. There is one envelope layer and one parameter set per turbine model; the model selector determines which set is being edited. Changes made in one place are immediately reflected in the other. The UI, including Interactive Map labels and runtime messages, is available in ES/EN/FR/DE.

When a turbine CSV is converted into a point layer, the plugin transfers the spacing values already stored in the selected model definition, assigns the model metadata and **creates/rebuilds its ellipse layer automatically**. Opening the spacing dialog first is not required, but doing so allows the user to configure that model before importing its coordinates.

---

## Concepts and conventions

- **Separations are center-to-center distances**, expressed in rotor diameters (`X · D` downwind, `Y · D` crosswind). Each individual envelope therefore uses **semi-axes = separation / 2**, so two turbines exactly at the threshold have envelopes that just touch, and closer than that they overlap.
- **Defaults:** 7 D downwind (longitudinal), 4 D crosswind (transversal).
- **Angle convention:** azimuth in degrees from North, clockwise (standard GIS/meteorological convention). The major axis is bidirectional, so `α` and `α + 180°` are equivalent.
- **Rotor diameter `D`** is read from the turbine layer custom property `velantis/diameter_m` (written when point layers are generated). If several turbine models coexist as separate layers, each layer uses its own `D`.

---

## Orientation modes

### 1. Automatic — most energetic sector (default)

The ellipse is aligned with the sector that contributes most energy, **not** merely the most frequent one. For each WRG sector `s` with frequency `f_s` and Weibull parameters `(A_s, k_s)`, the relative energy is approximated with the third Weibull moment:

```
E_s ∝ f_s · A_s³ · Γ(1 + 3/k_s)
```

averaged over the WRG grid nodes. The envelope is rotated to the center azimuth of `argmax(E_s)`.

If the most energetic sector cannot be determined (no WRG loaded, unreadable file), the module falls back to the manual angle of the panel and shows a discreet notice:

> *Could not automatically determine the most energetic sector · using manual angle.*

### 2. Manual — numeric angle

Type an azimuth in the panel; every envelope without a per-turbine override uses it.

### 3. Manual — define on screen

**Apply new configuration** and **Define ellipse on screen** are intentionally separate. The first saves the longitudinal/crosswind spacing and orientation as the selected model template and rebuilds its full ellipse layer. The second creates a per-turbine override only.

Press **Define ellipse on screen** and draw the full envelope of a turbine in three clicks with a continuous live preview:

1. **Click a turbine** — the center snaps to the nearest turbine (within tolerance) and is marked.
2. **Drag and click** — the cursor drives the **major axis**: orientation *and* downwind separation at once. The dashed axis line and the ellipse rotate/stretch in real time.
3. **Drag and click** — the cursor now drives the **minor axis** (perpendicular distance). Click to confirm.

While drawing, the panel status line shows live values:

```
Major axis · Angle: 247.3° · Downwind: 6.8 D (816 m)
```

Modifier keys:

- **Ctrl** — angular snapping to 5° steps *and* to the WRG sector centers (magnet within ±3°), so manual drawing can lock onto the wind rose.
- **Shift** — dimensional snapping to multiples of 0.5 · D.
- **Esc / right-click** — one step back; from step 1 it exits the drawing tool.

The tool stays active after confirming, so several turbines can be chained; press Esc from step 1 to leave it.

**Panel ↔ screen synchronization:** the selector identifies the active turbine model. A drawn ellipse writes its angle and separations back into the panel fields and is stored as a **per-turbine override**; all other turbines keep the selected model template.

**Reset** clears the per-turbine overrides of the selected model and returns those turbines to that model template.

---

## Validation logic

For every rebuild (turbine added/removed, parameter changed, ellipse drawn):

1. Each turbine gets its resolved spec: per-turbine override if present, otherwise the template of its source turbine model; automatic orientation is resolved to the WRG angle.
2. Ellipses are generated as 64-vertex polygons in the turbine layer CRS.
3. Conflicts are evaluated with a `QgsSpatialIndex` (no all-pairs comparison):
   - **conflict** — polygon intersection with non-zero area;
   - **near** — no overlap, but free distance below 10 % of the envelope's characteristic radius;
   - **ok** — otherwise.
4. Results are written to the corresponding model envelope layer (`spacing_status`) and summarized in the panel; conflicts additionally raise a message-bar warning.

The validation level is user-selectable:

- **Visualization only** — conflicts only change colors; no message-bar noise.
- **Warn on conflict** (default) — conflicts additionally raise a message-bar warning.
- **Block insertion on conflict** — before a new turbine is committed in Interactive Map mode, its would-be envelope is tested against the existing ones; on overlap the insertion is rejected with the message *"The turbine intrudes into another turbine's envelope · insertion blocked."* The check is fail-open: any internal error never prevents editing.

---

## The envelope layer

Envelopes live in one **memory layer per turbine model/source layer**, named `Envolventes de separación · <model>`. They are regenerable at any time. Closing or leaving Interactive Map releases the controller but keeps the generated layers in the QGIS project; explicitly disabling spacing envelopes removes them. Attributes per envelope:

| Field | Meaning |
|---|---|
| `turbine_fid` | Feature id of the turbine in its source turbine layer |
| `turbine_layer_id` | QGIS layer id of the associated turbine layer |
| `model_index` | Turbine-model row/index in the Energy dialog |
| `model_name` | Turbine-model name |
| `spacing_long_d` | Downwind separation used (·D) |
| `spacing_trans_d` | Crosswind separation used (·D) |
| `spacing_angle_deg` | Resolved azimuth of the major axis |
| `spacing_mode` | `auto_energy` · `manual_angle` · `manual_screen` |
| `spacing_status` | `ok` · `near` · `conflict` |

Per-turbine overrides persist as JSON in the turbine layer custom property `velantis/spacing_overrides`, so they survive project save/load and are pruned automatically when their turbine is deleted.

---

## Special cases

- **Multiple rotor diameters:** each turbine layer carries its own `velantis/diameter_m`; each model has its own envelope layer and always uses the real `D` of that source layer. Conflicts are also checked between different models.
- **No wind resource loaded:** automatic mode falls back to the panel's manual angle (0° by default) with a visible notice.
- **Turbine model change:** regenerating point layers rewrites `velantis/diameter_m` and the model-specific spacing properties; envelopes pick them up immediately.
- **CSV import:** every valid turbine CSV point layer inherits the spacing values configured for its model and creates or refreshes its associated ellipse layer automatically. If several model layers are present, conflicts are recalculated across all of them.
- **Legacy circular projects:** old `circular` values are accepted when loading the project but migrated to elliptical envelopes.
- **Large layouts:** conflict checks are spatial-index based; the ellipse rebuild itself is O(n) with 64-vertex polygons and is comfortable for screening-size layouts.

---

## Roadmap

Planned for later phases (matching the functional specification):

- Center-to-center distance checks projected on the principal/transverse axes.
- Optimizer integration: envelopes as soft penalties or hard constraints.

Already delivered from the phase-2 list: model-specific elliptical envelopes, automatic CSV synchronization, validation levels with optional insertion blocking, and GeoPackage export.

---

## Related documents

- [`SPACING_ENVELOPE_ARCHITECTURE.md`](SPACING_ENVELOPE_ARCHITECTURE.md) — code structure, integration points and design decisions.
- [`ENERGY_MODULE.md`](ENERGY_MODULE.md) — the Energy/AEP workflow the Interactive Map belongs to.
