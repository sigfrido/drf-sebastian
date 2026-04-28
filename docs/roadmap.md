# Development Roadmap

## Phase 1 — Core scaffold (done)

- [x] Package structure: `src/sebastian/`, `testproject/selco/`, `tests/`
- [x] `pyproject.toml` — `drf-sebastian` distribution, `sebastian` import name
- [x] `GUIMixin` — adds `SebastianHTMLRenderer`, sets `request.sebastian_gui`, provides `create_form`/`update_form`
- [x] `GUIRouter` — mirrors DRF router registry, forces `format=html` via URL kwargs
- [x] `SebastianHTMLRenderer` — renders action-appropriate template from `renderer_context`
- [x] `GUISerializer` — enforces FieldGroup permissions at serializer layer
- [x] `FieldGroup` / `EntityGroup` — declared in `ViewSet.Sebastian.groups`
- [x] `sebastian.dispatch.call()` — internal ViewSet dispatch for cascading actions
- [x] `@action` decorator — DRF `@action` extended with `gui_config`
- [x] Template tags — `get_item`, `input_type`, `field_value`
- [x] Base templates — `base.html`, `list.html`, `detail.html`, `form.html`, `modal.html`
- [x] SELCO test models — `Fornitore`, `Richiesta` (with workflow states), `Allegato`
- [x] Django system check passes, DB tables created

## Phase 2 — Working list + detail views

- [ ] `list.html` renders real data from API response
- [ ] `detail.html` renders FieldGroups as Bootstrap tabs
- [ ] EntityGroup section loads inline list via HTMX (`hx-trigger="load"`)
- [ ] HTMX partial detection in renderer (full page vs fragment)
- [ ] `GUIRouter` mirrors `@action` routes correctly (url_path, detail flag)
- [ ] Filter form wired to `django-filter` filterset

## Phase 3 — Forms and actions

- [ ] `create_form` / `update_form` render functional HTML forms
- [ ] Form POST → API PUT/PATCH → redirect or HTMX swap
- [ ] EntityGroup modal: add/edit/delete buttons, HTMX modal load, save closes modal + refreshes section
- [ ] `@action` buttons rendered in detail view, confirmation dialog via `hx-confirm`
- [ ] Validation errors returned as HTML fragments (form re-render with error messages)

## Phase 4 — Permission enforcement

- [ ] `FieldGroup.edit_permission` / `visible_permission` callables evaluated in `GUISerializer.get_fields()`
- [ ] `EntityGroup` visibility/editability checked in renderer context
- [ ] `get_available_actions()` correctly filters by per-action `permission_classes`
- [ ] `HIDE_UNAUTHORIZED_ACTIONS` setting respected

## Phase 5 — BPM/SELCO integration

- [ ] Install `drf-sebastian` from local path into BPM project
- [ ] Wire one real SELCO ViewSet, validate real-world friction
- [ ] Add actual SELCO domain models and permissions
- [ ] Workflow phase → FieldGroup permission callables

## Deferred

- Management command `sebastian-templates` for exporting/customizing templates
- SPA/schema mode (`GET /api/...?_schema`)
- Theme system
- Inline editing (double-click in list)
- Breadcrumbs
- Menu auto-generation from router registry
