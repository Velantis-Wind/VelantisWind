# Spacing Envelope — Architecture

Developer notes for the `spacing_core/` package. User-facing behaviour is described in [`SPACING_ENVELOPE_MODULE.md`](SPACING_ENVELOPE_MODULE.md).

---

## Design goals

1. **Self-contained.** All logic lives in `spacing_core/`; the rest of the plugin only gains two tiny, optional touchpoints. If the package fails to import, Interactive Map mode works exactly as before.
2. **Defensive by convention.** Same style as the rest of the repo: QGIS/Qt calls wrapped so a UI hiccup never breaks turbine editing.
3. **Pure logic separated from QGIS.** Geometry math and the WRG sector-energy analysis are testable without a running QGIS (the WRG parser is stdlib-only).
4. **One source of truth per model.** The selected turbine layer stores its own spacing dimensions, orientation mode and fallback angle. Per-turbine overrides also live on that layer. The panel is an editor for the selected model, while the manager owns one envelope layer per turbine model/source layer and persists the bidirectional association with custom properties.

---

## Package layout

```text
spacing_core/
├─ __init__.py          # public API: SpacingSpec, SpacingController, ...
├─ geometry.py          # SpacingSpec, ellipse_polygon, evaluate_conflicts, snapping
├─ orientation.py       # WRG → energy per sector → most energetic azimuth (stdlib only)
├─ envelope_manager.py  # one memory layer per model, symbology, persistence
├─ auto_envelope.py     # CSV import helper; builds ellipses before the panel opens
├─ map_tool.py          # EllipseDefineTool: 3-click on-screen definition (QgsMapTool)
├─ panel.py             # SpacingEnvelopePanel: dock group box + QSettings persistence
├─ controller.py        # SpacingController: glue between all of the above
└─ i18n_spacing.py      # ES→EN/FR/DE maps registered through i18n.register_language
```

### Dependency direction

```text
panel.py ──┐
map_tool ──┤
manager ───┼──> geometry.py      (pure-ish: only QgsGeometry/QgsPointXY/QgsSpatialIndex)
controller ┘        │
     │              └──> orientation.py   (stdlib only, cached by (path, mtime))
     └──> envelope_manager, map_tool, panel, orientation
```

`controller.py` is the only module that knows about the main dialog (`AEPSetupDialog`).

---

## Integration points (the only edits outside the package)

### `aep_setup_dialog.py`

- Defensive import of `SpacingController` / `SpacingConfigDialog`.
- A **Spacing envelopes…** button at the bottom of the *Turbine models* group (right below the per-model CSV coordinate rows) calls `_open_spacing_config()`.
- `_ensure_spacing_controller()` lazily creates and returns THE shared `SpacingController` for the dialog session; `_teardown_spacing_controller()` is called from `closeEvent` on a real close (not when hiding for Interactive Map mode). Teardown releases Python references but deliberately keeps generated envelope layers in the QGIS project.
- `SpacingConfigDialog` (in `spacing_core/config_dialog.py`) is non-modal and *borrows* the controller's panel widget while open, returning it (`setParent(None)`) on close. The panel exposes an explicit model/layer selector. When *Define ellipse on screen* is pressed, the config dialog and the main dialog hide via the existing `_hide_dialog_for_interactive_map()` machinery and are restored on the controller's `tool_finished` signal.
- After a valid coordinate CSV is converted to a point layer, `spacing_core.auto_envelope.ensure_spacing_envelope_for_layer()` creates or refreshes its envelope layer immediately and rebuilds all known turbine-model layers together.

### `mapa_interactivo_dock.py`

- Imports `SpacingController` behind `try/except` (falls back to `None`).
- In `_build_ui()`, **reuses** the dialog's shared controller via `ctl._ensure_spacing_controller()` and inserts `controller.panel` between the TI group and the Actions group; only if the shared helper is unavailable does it create (and own) a private controller.
- In `_teardown()`, tears the controller down only when the dock owns it; the shared one just gets its panel detached so envelopes stay alive back in the dialog.

Because the panel is a single widget shared between the config dialog and the dock — and those two are never visible simultaneously (the main dialog hides during Interactive Map mode) — reparenting on open/close is safe and keeps one source of truth for settings, hooks and the model-specific envelope layers.

### `mapa_interactivo.py`

- `_TurbineInteractiveTool` gains `_notify_spacing(layer)`, called at the end of `_handle_add` / `_handle_remove`, and a pre-insert consultation of the optional `ctl._spacing_check_candidate(layer, x, y)` hook: when the validation level is *Block insertion*, the controller tests the candidate envelope against the current envelope layer and returns `False` to veto the insert. Both hooks are looked up the same way:

```python
cb = getattr(self.ctl, "_spacing_notify_layout_changed", None)
if callable(cb):
    cb(layer)
```

The attribute is published by `SpacingController.__init__` and removed in `teardown()`. This keeps the turbine-editing tool fully decoupled: no import of `spacing_core`, no behaviour change when the module is absent.

---

## Key decisions

### Center-to-center semantics

`long_d` / `trans_d` are **minimum distances between centers**. Each envelope uses semi-axes = separation/2 so that "two envelopes overlap ⇔ the pair violates the threshold". This is documented in `geometry.py` and in the tooltips, because it is the most common source of confusion in spacing tools.

### Angle convention

Azimuth from North, clockwise (matches WRG sector centers `0°, 22.5°, …` produced by `ag_core/wrg_site.py`). Map-coordinate conversion happens only inside `ellipse_polygon` (`u = (sin θ, cos θ)`), so every module above geometry speaks azimuth.

### Most energetic sector

`orientation.py` re-implements a minimal WRG node parser instead of importing `ag_core.wrg_site` on purpose: that module requires `numpy`/`xarray` (PyWake stack), while envelopes must work even when Energy dependencies are missing. Scalings match `wrg_site.py` (`A = raw/10`, `k = raw/100`). Energy proxy per sector:

```
E_s ∝ Σ_nodes f_s · A_s³ · Γ(1 + 3/k_s)
```

Results are cached by `(abspath, mtime)`; large grids are subsampled (stride) above 5 000 nodes.

### Conflict evaluation

`EnvelopeManager.rebuild_many` groups source layers by CRS and passes all model envelopes in each CRS to `evaluate_conflicts`, which builds a `QgsSpatialIndex` over envelope bounding boxes and only tests candidate pairs. Statuses:

- `conflict`: `intersection.area() > ε`;
- `near`: `distance < 0.10 · characteristic_radius` (bbox half-diagonal max side);
- `ok`: otherwise.

Touching boundaries (exactly at threshold) have zero intersection area → not a conflict, which matches the center-to-center definition.

### On-screen definition (`EllipseDefineTool`)

A three-state machine (`CENTER → MAJOR → MINOR`) on a single `QgsMapTool`:

- Preview uses two `QgsRubberBand`s (polygon ellipse + dashed major-axis line) and a `QgsVertexMarker` for the center; the ellipse polygon is regenerated on every `canvasMoveEvent` (64 vertices — cheap).
- Step MAJOR drives angle **and** semi-major axis simultaneously (`azimuth_between` + euclidean distance); the semi-minor axis previews at the default `trans/long` ratio until step MINOR fixes it as the perpendicular distance to the axis.
- Ctrl → `snap_angle(5°, magnets=WRG sector centers, ±3°)`; Shift → `snap_length(0.5·D)`.
- The tool **never writes to layers**. It emits `(fid, SpacingSpec)` through `on_defined`, and status text (live angle/D/m) through `on_status`. This makes it reusable and keeps all persistence in the controller.
- Esc / right-click steps back one state; from CENTER it cancels (controller restores the previous map tool — normally the turbine add/remove tool).

### Persistence

- **Application defaults:** `QSettings("VelantisWind", "VelantisWindPlugin")`, keys `spacing/*`. They initialize new/legacy layers and store global enable/validation preferences; they are not the authoritative values once a model layer has its own properties.
- **Per-model template:** each turbine layer stores `velantis/spacing_long_d`, `velantis/spacing_trans_d`, `velantis/spacing_mode` and `velantis/spacing_angle_deg`. The panel edits these properties for the currently selected model.
- **Per-turbine overrides:** JSON in each turbine layer custom property `velantis/spacing_overrides`, keyed by fid — saved with the project, like the existing `velantis/diameter_m`. `controller._on_layout_changed` prunes fids that no longer exist. Legacy `shape=circular` overrides are read but normalized to elliptical geometry.
- **Model-layer association:** the turbine layer stores `velantis/spacing_envelope_layer_id`; the envelope layer stores `velantis/source_turbine_layer_id`, source model name/index and its role. This prevents a model switch from replacing another model's envelope layer.

Caveat: memory-layer fids can be reassigned across sessions; overrides are therefore best-effort session/project state, which is acceptable for a screening tool (documented limitation).

### Symbology

Categorized renderer on `spacing_status` built in code (`QgsFillSymbol.createSimple` + alpha fills), so the layer needs no bundled `.qml`. The layer is flagged non-identifiable to keep map clicks flowing to the turbine tool.

### i18n

Spanish is the plugin's source language; `i18n_spacing.register()` registers ES→EN/FR/DE maps through the existing `i18n.register_language` mechanism at controller import. Dynamic status strings are composed from translated fragments so the fragment maps cover them.

---

## Testing without QGIS

- `orientation.py` is stdlib-only: build a synthetic WRG (header + node lines with `8 + 3·nsec` tokens, raw scalings `f`, `A·10`, `k·100`) and assert `best_sector` / `best_angle_deg`.
- `geometry.py` math (azimuth convention, ellipse orientation, snapping, `SpacingSpec` round-trip) can be exercised by stubbing `qgis.core` with minimal `QgsPointXY`/`QgsGeometry` fakes; register the module in `sys.modules` before `exec_module` so `@dataclass` resolves.

Manual QGIS smoke test: see the new items in [`RELEASE_TEST_CHECKLIST.md`](RELEASE_TEST_CHECKLIST.md).

---

## Extension hooks (roadmap)

- **Optimizer:** the resolved per-turbine `SpacingSpec` + status map is the natural payload for a penalty/constraint term.
- Insertion blocking is fail-open and checks all model envelope layers. GeoPackage export writes one table per model through `EnvelopeManager.export_all_to_gpkg`, with a V3/V2 writer fallback.


## Per-model dimensions

Turbine layers define `velantis/spacing_long_d`, `velantis/spacing_trans_d`, `velantis/spacing_mode` and `velantis/spacing_angle_deg`. `layer_spacing_spec()` resolves this complete model template and always returns an elliptical shape. Resolution priority is: per-turbine override → per-model template → application defaults used only to initialize missing properties.
