# Development Roadmap

## Phase 1 — Core scaffold (done)

- [x] Package structure: `src/sebastian/`, `testproject/selco/`, `tests/`
- [x] `pyproject.toml` — `drf-sebastian` distribution, `sebastian` import name
- [x] `GUIMixin` — adds `SebastianHTMLRenderer`, sets `request.sebastian_gui`, provides `create_form`/`update_form`
- [x] `GUIRouter` — mirrors DRF router registry, forces `format=html` via URL kwargs
- [x] `SebastianHTMLRenderer` — renders action-appropriate template from `renderer_context`
- [x] `GUISerializer` — enforces FieldGroup permissions at serializer layer
- [x] `FieldGroup` — declared in `ViewSet.Sebastian.groups`
- [x] `sebastian.dispatch.call()` — internal ViewSet dispatch for cascading actions
- [x] `@action` decorator — DRF `@action` extended with `gui_config`
- [x] Template tags — `get_item`, `input_type`, `field_value`, `display_value`, `data_keys`
- [x] Base templates — `base.html`, `list.html`, `detail.html`, `form.html`
- [x] SELCO test models — `Fornitore`, `Richiesta` (with workflow states), `Allegato`
- [x] Django system check passes, DB tables created

## Phase 2 — Working list + detail views (done)

- [x] `list.html` renders real data from API response (pagination unpacked in renderer)
- [x] `detail.html` renders FieldGroups as Bootstrap tabs with serializer labels
- [x] HTMX partial detection in renderer (`HX-Request` → content block only, no full page)
- [x] `GUIRouter` mirrors `@action` routes correctly (url_path, detail flag)
- [x] Filter form wired to `django-filter` filterset (FilterSet class, `icontains` on text fields)
- [x] Filter field labels shown above each field
- [x] `GUIRouter` auto-generates home at `/gui/` with card grid of registered ViewSets
- [x] `django_filters` in INSTALLED_APPS + DEFAULT_FILTER_BACKENDS in REST_FRAMEWORK
- [x] `selco/admin.py` — Fornitore, Richiesta, Allegato registered for data entry
- [x] FK display via `{field}__display` keys added by `GUISerializer.to_representation()` in GUI mode

## Phase 3 — Forms, nested resources, and actions (done)

- [x] `EntityGroup` removed; replaced by `NestedGUIMixin` + `Sebastian.inlines`
- [x] `SebastianRouter` — drop-in for DefaultRouter, auto-registers nested API URL patterns from `Sebastian.inlines`
- [x] `NestedGUIMixin` — auto-detects parent from `{model_name}_pk` URL kwargs, filters queryset, injects FK on create
- [x] `GUIRouter` extended with nested GUI routes: list, new/, `<pk>/`, `<pk>/edit/`
- [x] Inline list loaded via HTMX `hx-trigger="load"` in detail page
- [x] `create_form` / `update_form` render functional HTML forms (Bootstrap tabs per FieldGroup, checkbox support, select for FK)
- [x] Forms use absolute `submit_url` to avoid HTMX resolving relative `../` against browser URL
- [x] Form POST → 201 → `HX-Redirect` to new item detail (top-level); or inline list reload (nested)
- [x] Form PATCH → 200 → `HX-Redirect` to item detail (top-level); or inline list reload (nested)
- [x] CSRF handled via `hx-headers='{"X-CSRFToken": "..."}'` on `<body>`
- [x] Delete button in list (top-level and inline), with `hx-confirm` showing table name + `__str__` of record
- [x] After nested create/update/delete: return updated inline list HTML directly (no browser navigation)
- [x] After top-level delete: reset `request.path` to list URL, return updated list HTML directly
- [x] `GUISerializer` adds `sebastian__str` key (filtered from columns, used for delete confirmation)
- [x] `list.html` uses `items.0|data_keys` for all row cells (fixes missing cell when DRF raises `SkipField` for null FK traversal)
- [x] `@action` buttons rendered in detail view header with `hx-confirm`
- [x] Bootstrap 5.3.3 JS SRI hash corrected (wrong hash was silently blocking JS, breaking tabs)
- [x] `list_level` context variable (`1` top-level, `2` inline) → CSS class `list-level1/2` on table wrapper
- [x] Single `list.html` template shared by top-level and inline lists; `is_inline` / `htmx_target` distinguish behavior

## Phase 3b — Remaining form polish

- [ ] Validation errors returned as HTML fragment (form re-render with field-level error messages)
- [ ] Form cancel on top-level navigates correctly when loaded via HTMX (currently uses `href="../"`)

## Phase 4 — Permission enforcement

- [ ] `FieldGroup.edit_permission` / `visible_permission` callables evaluated per-request
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
