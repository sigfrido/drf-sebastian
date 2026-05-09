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
- [x] `@action` GET actions render as `<a href>` links in list and detail; POST actions render as `<button hx-post>`
- [x] `NullableFileField` — DRF FileField subclass that converts empty-string → None for nullable file clearing
- [x] File field UX: badge shows current filename; X button disables file input + marks it `data-sb-pending`; `htmx:configRequest` injects `''` for pending-clear fields and drops empty file inputs from params
- [x] `selco` app migrations split: `0001_initial` (pre-existing schema), `0002_fornitore_add_certificazione` (new nullable FileField)

## Phase 3b — Remaining form polish

- [x] Validation errors returned as HTML fragment (form re-render with field-level error messages via `X-Sebastian-Form-Error` header + `htmx:beforeSwap` hook)
- [x] Form cancel on top-level uses `hx-get` HTMX navigation (same mechanism as nested inline forms)
- [x] `GUISerializer.validate()` calls `Model.clean()` automatically — model-level validation fires on every API write without duplicating logic in the serializer; Django `ValidationError` is remapped to DRF `ValidationError`

## Phase 4 — Permission enforcement (done)

- [x] `FieldGroup.edit_permission` / `visible_permission` accept a single callable or list of callables (AND logic); evaluated per-request via `_check_permission()`
- [x] `get_available_actions()` checks DRF `permission_classes` + optional `gui_config['permission']` (callable or list); caches instance via `retrieve()` override for zero extra queries
- [x] `HIDE_UNAUTHORIZED_ACTIONS` setting: `True` (default) hides unauthorised buttons; `False` renders them as `disabled`
- [x] `app_settings.py` — thin settings accessor for `SEBASTIAN` dict in Django settings

## Phase 5 — App menu (done)

- [x] `MenuItem` / `MenuGroup` dataclasses in `config.py` — explicit opt-in via `ViewSet.Sebastian.menu`
- [x] `SebastianMenuView` — DRF `APIView` at `/api/menu/` (JSON for SPAs) and `/gui/menu/` (HTML fragment); auto-registered by `GUIRouter` + `SebastianRouter`
- [x] `GUIRouter._build_menu_groups()` resolves `MenuItem.action` → URL names at startup; `SebastianMenuView._menu_groups` set as class attribute for shared access
- [x] `base.html` loads menu via `hx-get="/gui/menu/" hx-trigger="load, menuRefresh from:body"` — single extra request per page load; reloads on HTMX navigation via `htmx:pushedIntoHistory` → `menuRefresh` event
- [x] Active item: server-side longest-prefix-wins matching via `HX-Current-URL` header; exact match beats prefix (so `/new/` activates "Nuovo", not "Elenco"); group toggle inherits `active` from any active child
- [x] Responsive navbar: hamburger toggler button; dropdowns become inline sub-lists on small screens (Bootstrap 5 built-in)
- [x] `Cancel` button in top-level forms sets `hx-push-url` so URL history is updated and menu refreshes correctly
- [x] Menu items respect `permission` (callable or list) — follows `HIDE_UNAUTHORIZED_ACTIONS`: hidden or `disabled`
- [x] `gui_router.add_page(url_path, view, name)` — register custom pages; view receives `request.sebastian_gui = True`
- [x] `Sebastian.templates` dict — per-ViewSet template overrides (`'list'`, `'detail'`, `'form'`); legacy `Sebastian.{action}_template` still supported

## Phase 6 — Action confirmation forms

- [ ] `@action` can declare a `confirmation_serializer` in `gui_config` — a DRF serializer whose fields are collected in a modal form before the action is dispatched
- [ ] Example use-case: workflow transition that requires a `note` (text) and an optional `destinatario` (FK to user), only shown when the WF phase is configured to accept a receiver
- [ ] GUI flow: action button click → HTMX loads confirmation form into modal → user fills form → submit POSTs action with form data merged into the request body
- [ ] `SebastianHTMLRenderer` detects `confirmation_serializer` in `gui_config` and adds a `confirm_form` template for the modal content
- [ ] Confirmation forms use the same FieldGroup / field rendering pipeline as regular forms

## Phase 7 — Theming and template override framework

- [ ] `SEBASTIAN['TEMPLATE_PACK']` setting selects a subdirectory under `sebastian/templates/` (default: `bootstrap5`)
- [ ] All templates moved into `sebastian/templates/bootstrap5/`; existing imports updated
- [ ] Management command `sebastian_templates` copies the active pack's templates into the project's `templates/sebastian/` directory for per-project customization
- [ ] CSS custom-property hooks (`--sb-primary`, `--sb-font`, etc.) injected in `base.html` and driven by `SEBASTIAN['THEME']` dict
- [ ] Documentation of the override points: which blocks exist in each template, which context variables are always available

## Phase 8 — BPM/SELCO integration

- [ ] Install `drf-sebastian` from local path into BPM project
- [ ] Wire one real SELCO ViewSet, validate real-world friction
- [ ] Add actual SELCO domain models and permissions
- [ ] Workflow phase → FieldGroup permission callables + action confirmation serializers

## Deferred

- Management command `sebastian-templates` for exporting/customizing templates
- SPA/schema mode (`GET /api/...?_schema`)
- Inline editing (double-click in list)
- Breadcrumbs
- Menu auto-generation from router registry
