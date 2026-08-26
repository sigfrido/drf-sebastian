# Development Roadmap

## Phase 1 — Core scaffold (done)

- [x] Package structure: `src/sebastian/`, `testproject/demo/`, `tests/`
- [x] `pyproject.toml` — `drf-sebastian` distribution, `sebastian` import name
- [x] `GUIMixin` — adds `SebastianHTMLRenderer`, sets `request.sebastian_gui`, provides `create_form`/`update_form`
- [x] `GUIRouter` — mirrors DRF router registry, forces `format=html` via URL kwargs
- [x] `SebastianHTMLRenderer` — renders action-appropriate template from `renderer_context`
- [x] `GUISerializerMixin` — enforces FieldGroup permissions at serializer layer
- [x] `FieldGroup` — declared in `ViewSet.Sebastian.groups`
- [x] `sebastian.dispatch.call()` — internal ViewSet dispatch for cascading actions
- [x] `@action` decorator — DRF `@action` extended with `gui_config`
- [x] Template tags — `get_item`, `input_type`, `field_value`, `display_value`, `data_keys`
- [x] Base templates — `base.html`, `list.html`, `detail.html`, `form.html`
- [x] Demo test models — `Supplier`, `Request` (with workflow states), `Attachment`
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
- [x] `demo/admin.py` — Supplier, Request, Attachment registered for data entry
- [x] FK display via `{field}__display` keys added by `GUISerializerMixin.to_representation()` in GUI mode

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
- [x] `GUISerializerMixin` adds `sebastian__str` key (filtered from columns, used for delete confirmation)
- [x] `list.html` uses `items.0|data_keys` for all row cells (fixes missing cell when DRF raises `SkipField` for null FK traversal)
- [x] `@action` buttons rendered in detail view header with `hx-confirm`
- [x] Bootstrap 5.3.3 JS SRI hash corrected (wrong hash was silently blocking JS, breaking tabs)
- [x] `list_level` context variable (`1` top-level, `2` inline) → CSS class `list-level1/2` on table wrapper
- [x] Single `list.html` template shared by top-level and inline lists; `is_inline` / `htmx_target` distinguish behavior
- [x] `@action` GET actions render as `<a href>` links in list and detail; POST actions render as `<button hx-post>`
- [x] `NullableFileField` — DRF FileField subclass that converts empty-string → None for nullable file clearing
- [x] File field UX: badge shows current filename; X button disables file input + marks it `data-sb-pending`; `htmx:configRequest` injects `''` for pending-clear fields and drops empty file inputs from params
- [x] `demo` app migration: single `0001_initial` covering Supplier, Request, Attachment, Settings (rebuilt from scratch when the testproject was translated to English — see Phase 9)

## Phase 3b — Remaining form polish

- [x] Validation errors returned as HTML fragment (form re-render with field-level error messages via `X-Sebastian-Form-Error` header + `htmx:beforeSwap` hook)
- [x] Form cancel on top-level uses `hx-get` HTMX navigation (same mechanism as nested inline forms)
- [x] `GUISerializerMixin.validate()` calls `Model.clean()` automatically — model-level validation fires on every API write without duplicating logic in the serializer; Django `ValidationError` is remapped to DRF `ValidationError`

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
- [x] Active item: server-side longest-prefix-wins matching via `HX-Current-URL` header; exact match beats prefix (so `/new/` activates "New", not "List"); group toggle inherits `active` from any active child
- [x] Responsive navbar: hamburger toggler button; dropdowns become inline sub-lists on small screens (Bootstrap 5 built-in)
- [x] `Cancel` button in top-level forms sets `hx-push-url` so URL history is updated and menu refreshes correctly
- [x] Menu items respect `permission` (callable or list) — follows `HIDE_UNAUTHORIZED_ACTIONS`: hidden or `disabled`
- [x] `gui_router.add_page(url_path, view, name)` — register custom pages; view receives `request.sebastian_gui = True`
- [x] `Sebastian.templates` dict — per-ViewSet template overrides (`'list'`, `'detail'`, `'form'`); legacy `Sebastian.{action}_template` still supported

## Phase 6 — Action confirmation forms (done, superseded by Phase 7b)

- [x] `@action` declares `confirmation_serializer` in `gui_config` — a plain DRF Serializer whose fields are collected in a Bootstrap modal before the action is dispatched
- [x] Example use-case: `submit` action on `Request` requires `justification` (TextField, saved to model) and `confirmed` (BooleanField checkbox, GUI-only policy acceptance, not saved)
- [x] GUI flow: action button `hx-get` → HTMX loads `confirm_action.html` into `#sebastian-modal` → JS shows Bootstrap modal → user fills form → `hx-post` to action URL → success `HX-Redirect` / error re-renders modal
- [x] `SebastianHTMLRenderer` detects `data['action'] == 'confirm_action'` → renders `sebastian/confirm_action.html` (standalone, no `{% extends %}`  — always renders modal structure regardless of HTMX partial mode)
- [x] `detail.html` checks `cfg.confirmation_serializer` first (before `action.method == 'get'`) → modal-trigger button
- [x] `base.html` JS: `htmx:afterSwap` on `#sebastian-modal` → `new bootstrap.Modal(el).show()`
- [x] `finalize_response` in `GUIMixin` guards `request.method != 'get'` — GET actions never get `HX-Redirect` appended
- [x] `GUISerializerMixin.get_fields()` guards `isinstance(raw_obj, Model)` — queryset (many=True child) and None both treated as no-object context
- [x] API path: `confirmed` is GUI-only; API callers can POST `submit` without it (backward-compatible)
- [x] Permission callables for `visible_permission` / `edit_permission` must guard `obj is None` for list/label context
- [x] `GUIMixin.confirmation_action()` — reusable dispatcher; actions declare `{action}_get()` (initial data) and `{action}_valid()` (post-validation logic); passes `confirmation_instance` in serializer context
- [x] `base.html` JS tracks `_sbModal` instance and calls `.dispose()` before re-creating — prevents duplicate backdrops on validation-error re-renders

## Phase 7 — Template packs, skins, and non-HTMX pack (done)

- [x] Template pack system: all templates live under `sebastian/{pack_name}/`; active pack set via `SEBASTIAN['TEMPLATE_PACK']` (default `htmx`); users can add packs in their own project's `templates/` directory
- [x] Non-HTMX `plain` pack: `{% include_resource url %}` template tag calls a Django URL server-side (synchronous) and returns the rendered HTML fragment — replaces `hx-get` inline loads
- [x] Skin system: skin = CSS/icon library combination defined as a `sebastian/skins/{skin_name}/_skin.html` fragment injected via `{% include skin_head %}`; configured via `SEBASTIAN['SKIN']`; decoupled from pack structure
- [x] `{% icon name %}` template tag: renders the correct icon HTML based on the active skin (e.g. Bootstrap Icons, FontAwesome), keeping templates skin-agnostic
- [x] Plain pack plain-form correctness: `/edit/` URL mapped `POST → partial_update`; empty file inputs stripped before validation so partial updates don't fail on unchanged file fields; error re-render shows existing instance data (not submitted data)
- [x] Plain pack navigation: after nested create/update/delete, redirect to parent detail page (not inline list); cancel on nested edit forms goes to parent detail
- [x] Plain pack field groups: `<details>`/`<summary>` accordion replaces Bootstrap tab JS in both `form.html` and `detail.html`; zero JavaScript required; first group open by default

## Phase 7b — Architecture review (done)

- [x] Pack HTMX awareness: `app_settings.pack_uses_htmx()` checks `HTMX_PACKS` setting (default `['htmx']`); replaces scattered `template_pack() == 'plain'` checks in `mixins.py`; custom packs opt in via `HTMX_PACKS`
- [x] Global confirmation settings: `app_settings.confirm_actions()` (default `False`, **still unwired — see Open Issues**) + `confirm_deletions()` (default `True`, consulted by `GUIMixin`)
- [x] Skin simplification: Bootstrap + Icons CDN links moved directly into `htmx/base.html` and `plain/base.html`; the old per-skin `skins/` directory was removed; `sebastian.css` added with CSS custom properties for the few remaining skin-driven values
- [x] Unified confirmation: `GUIMixin.confirm()` handles both delete confirmation and action confirmation through one code path
  - Routing: `GET`/`POST /{pk}/delete/` → `confirm()` (`_confirm_type='delete'`); `GET /{pk}/{action}/confirm/` → `confirm()` (`_confirm_type='action'`); `POST /{pk}/{action}/` → the action method directly
  - htmx pack renders confirmations as a Bootstrap modal; plain pack renders a full confirmation page
  - `gui_config['confirmation']` replaced the earlier flat `'confirm'` / `'confirmation_serializer'` keys from Phase 6 — now a dict: `{'prompt', 'serializer', 'icon', 'style'}`, with `$OBJECT`/`$ACTION` substitution in `prompt`
  - `_post_confirmation_action(action_name, instance)` — validates the confirmation serializer (GUI POST path) and calls `{action_name}_valid(instance, serializer)`; returns a confirm-style 400 on validation error

## Phase 8 — Advanced widgets (done)

- [x] `Sebastian.ordering` — tuple of `(value, label)` pairs driving a multi-select ordering widget in list views; `Sebastian.max_ordering_fields` caps how many can be active at once; `GUIMixin.filter_queryset()` reads `?ordering=f1,f2` and ignores undeclared fields
- [x] `@typeahead` decorator (`sebastian.decorators`) + `GUIMixin.standard_typeahead()` helper — turns any list `@action` into a `[{value, label}]` search endpoint for a `ForeignKey`
- [x] `Sebastian.field_config = {'field': {'typeahead_url': '...', 'typeahead_chars': N}}` wires a field to a typeahead endpoint; rendered as a TomSelect widget (htmx pack) with async search
- [x] `Sebastian.cascading_fields = [(...)]` — dependent typeahead fields that clear/reload when an upstream field changes; all fields in a cascade group must already be typeahead-enabled
- [x] Filter form cleanup: empty and sentinel (`"unknown"` for `NullBooleanSelect`) values stripped from HTMX-submitted filter requests so they read as "no selection" instead of literal filter values
- [x] Plain pack equivalents: sequential `<select name="ordering_N">` dropdowns for ordering (no JS); plain `<select>` chain for cascading fields

## Phase 9 — Real-world integration (in progress, via `opus`)

The originally-planned "BPM/SELCO" integration project is now called **opus**; `drf-sebastian` is installed there as an editable local package (`pip install -e`), so library changes are picked up immediately without a release cycle.

- [x] `drf-sebastian` installed from local path into a real consuming project
- [x] Multiple real ViewSets wired (top-level `GUIMixin`, nested `NestedGUIMixin`, and `SingletonGUIMixin` for settings/impersonation pages) — validated real-world friction and shaped several library features (`SingletonGUIMixin`, `gui_field`, `MenuDivider`, `add_page()`, `perm_or`/`perm_and`) before they had any coverage in `testproject/demo/`
- [x] Workflow-phase → `FieldGroup` permission callables + action confirmation serializers, composed with `perm_and`/`perm_or` and project-specific permission factories
- [ ] Fold any remaining opus-only patterns worth generalizing back into the library (the dynamic "settings registry → Sebastian serializer/view" framework built in opus is a candidate, but is currently too tied to opus's own settings-registry abstraction to lift as-is)

## Phase 10 — First-release polish (done)

- [x] `testproject/` translated to English end-to-end and its Django app renamed `selco` → `demo` (model/field names, menu labels, template strings); migrations rebuilt from scratch as a single `0001_initial`
- [x] `testproject/demo/management/commands/seed_demo_data.py` — idempotent management command seeding sample suppliers/requests/attachments/settings and an `admin`/`admin` superuser, including real sample files for the download/preview actions
- [x] Closed the gap between `testproject/demo/` and real-world (opus) usage: added a `Settings` singleton (`SingletonGUIMixin` + `add_page()`), a `MenuDivider`, a `@gui_field` computed column, a `preview_action`, and explicit `perm_or`/`perm_and` usage — every public library feature now has at least one runnable example
- [x] Found and translated hardcoded Italian strings baked into the library's own default templates and fallback messages (confirmation/cancel buttons, file-field hints, boolean Yes/No rendering, error messages) — these shipped to every consumer regardless of project language, not just a testproject-only issue
- [x] `MEDIA_ROOT`/`MEDIA_URL` configured explicitly for `testproject/` (previously unset, so test runs scattered upload artifacts into the repo root); `testproject/media/` gitignored
- [x] API reference generated with [pdoc](https://pdoc.dev/) at `docs/api/` (`tools/gen-docs.sh`); docstring gaps filled in `app_settings.py`, `renderers.py`
- [x] README Quick Start section — copy-pasteable minimal integration example (verified against a real scratch Django project) plus instructions for running the bundled demo
- [x] `docs/sebastian-spec.md` reconciled against the real codebase (was significantly aspirational — undocumented features added, fictional settings/config removed, superseded `EntityGroup` design replaced with the real `NestedGUIMixin`/`inlines` model)

## Phase 11 — i18n for the library chrome (done)

Triggered by a question about configuring the "Yes"/"No" boolean display via a setting — rejected in favor of real i18n, since there were already ~15 other hardcoded UI strings that would need the same one-setting-per-string treatment.

- [x] All hardcoded UI text in `src/sebastian/templates/` (both packs) wrapped with `{% trans %}`/`{% blocktrans %}` — buttons, modal titles, confirmation prompts, empty-state messages, the ordering widget labels, pluralized record count
- [x] Default fallback strings in `mixins.py` (confirmation/delete prompts, generic save-error message), `serializers.py` (Yes/No boolean rendering), `renderers.py` (generic error label) wrapped with `gettext`/`gettext_lazy`
- [x] `src/sebastian/locale/it/LC_MESSAGES/django.po` — a complete, hand-translated Italian catalog for every string above, compiled to `.mo` and included in package data (`pyproject.toml`)
- [x] `tests/test_i18n.py` — end-to-end proof that `translation.override('it')` actually renders the Italian catalog (not just that the `.po` file exists)
- [x] Documented in `docs/sebastian-spec.md` §7.3: how a consumer gets the Italian chrome automatically (`LANGUAGE_CODE = 'it'`, standard Django app-locale discovery, zero extra config) and how to regenerate/extend the catalog
- [x] Found and fixed one more round of leftover hardcoded Italian strings that the previous "translate testproject" pass had missed (a file-remove tooltip, list heading, ordering label, empty-state messages) — this pass was more thorough (systematic accented-character + stopword sweep across every template file, not a sampled grep)
- [ ] Discovered `src/sebastian/templates/sebastian/{htmx,plain}/modal.html` is dead code (pre-`NestedGUIMixin` leftover) — left untranslated and unremoved, flagged in spec §13 Open Issues, not part of this phase's scope

**Explicit scope decision**: this phase covers `drf-sebastian` (this repo) only.
- `workflango` needs the same treatment but lives in its own repo — not started, do in a session scoped to that repo.
- `opus` gets **no changes** — it's a direct-Italian application with no translation plans of its own; its own hardcoded Italian strings stay as they are. It benefits from this phase only as a side effect: since `sebastian`'s chrome now ships an `it` catalog, opus's `LANGUAGE_CODE` (if set to `'it'`, as expected for an Italian app) picks it up automatically with zero work on opus's side.

## Phase 12 — Login + group-based demo permissions (done)

Prompted by manual testing surfacing an old gap (see Phase 10 note on field-group permissions): the `testproject/demo/` `Request`/`Supplier` permission model is now fleshed out into a real, testable multi-role example instead of a single-admin one.

- [x] `SEBASTIAN['LOGIN_URL']` wired up in `testproject/` (Django's built-in `LoginView`/`LogoutView`, custom Bootstrap template) — every `/gui/` page now requires login, using a mechanism (`GUIRouter._wrap()`) that already existed in the library but had no consumer exercising it
- [x] Username + Logout shown in the navbar via `{% block navbar_right %}` — project-level override of `sebastian/htmx/base.html`; added the same block to `sebastian/plain/base.html` for pack parity (no project-level override built for `plain`, since it isn't the demo's active pack and isn't split into a thin `base.html`/`_base.html` pair the way `htmx` is)
- [x] `testproject/demo/permissions.py` — `MANAGERS`/`USERS` Django groups, Sebastian-callable and DRF-`BasePermission` versions of the same group checks side by side
- [x] `seed_demo_data` now also creates `manager`/`manager` (`MANAGERS`) and `user`/`user` (`USERS`) accounts
- [x] `Request` field-group permissions became phase-aware: "General" editable only in `draft` (any authenticated user, including while creating); "Management" editable only in `submitted`, by a manager or admin
- [x] `approve`/`reject` now require `MANAGERS` group membership specifically — a superuser that isn't in the group is correctly refused; this is a deliberate example of "admin" and "elevated permission" *not* being the same thing
- [x] New `reject` action's authorization mirrors `approve`'s
- [x] Deleting a `Request`: anyone (authenticated) can delete a draft; only a manager or admin can delete a submitted one; the existing approved/rejected record-level lock still wins over everything, including for managers/admin (no delete-override for finalized records)
- [x] `Supplier` writes (create/update/delete) restricted to managers or admin; reads stay open
- [x] Documented a real gotcha found while wiring the Edit/Delete-button visibility to these new rules: `can_update()`/`can_delete()` evaluate object permissions against the *current* (always-safe, `GET`) request, so a permission class that only restricts unsafe methods never hides the button on its own — see spec §4.10
- [x] README "Try the bundled demo" section rewritten with the three account roles and what each can/can't do

## Phase 13 — Two library bugs found via manual testing (done)

- [x] **`create_form()` context bug**: neither `GUIMixin.create_form()` nor `NestedGUIMixin.create_form()` passed an `'instance'` key in their response — Django silently resolves a missing template variable to `''` rather than `None`, and `get_item('', field_name)` then returns the *bound str method* for any field whose name matches one (`title`, `upper`, `strip`, ...) instead of an empty default, since every string genuinely has those methods. Symptom: a brand-new `Request`'s "title" input showed `<built-in method title of str object at 0x...>` as its value. Fixed by passing `'instance': None` explicitly; hardened `get_item()`/`display_value()` in `sebastian_tags.py` to short-circuit on `isinstance(obj, str)` so the same class of bug can't resurface elsewhere.
- [x] **Translation collision with `django.contrib.admin`**: added a Delete button to `detail.html` (both packs, next to Edit — previously detail views had no delete action at all, only list rows did), which surfaced a deeper issue — Django merges every installed app's translation catalog in *reversed* `INSTALLED_APPS` order, so `django.contrib.admin` (listed first, thus merged last) silently overrides a plain-context `{% trans %}` in `sebastian` for any msgid they both define ("Delete" → "Cancella", "Home" → "Pagina iniziale", and others that *happened* to already match so were invisible). Fixed by giving every sebastian string the `msgctxt "sebastian"` context (`{% trans ... context "sebastian" %}` / `pgettext('sebastian', ...)`), which keys the catalog lookup on `(context, msgid)` and makes collision with any other app's catalog structurally impossible. See spec §7.3.
- [x] Both fixes have regression tests that were confirmed to fail without the fix (`tests/test_template_tags.py`, `tests/test_i18n.py::test_translations_not_shadowed_by_django_contrib_admin`, `tests/test_gui_views.py::...test_create_form_title_field_value_is_empty_not_bound_method`)

## Phase 14 — Ergonomic i18n wrappers (done)

Prompted directly by pushback on Phase 13's fix: typing `context "sebastian"` / `pgettext('sebastian', ...)` on every single translatable string was judged (correctly) as too heavy a tax for something call sites will keep doing indefinitely.

- [x] `sebastian/i18n.py` — `sgettext(msg)` (Python) and `{% strans "msg" %}` (`templatetags/sebastian_tags.py`, template) both wrap the same `CONTEXT = 'sebastian'` constant; converted every existing call site in templates and in `mixins.py`/`serializers.py`/`renderers.py` to use them instead of the verbose form
- [x] Discovered mid-implementation that this reintroduces a *different* silent-failure mode: `django-admin makemessages` only recognizes the literal built-in `{% trans %}`/`{% blocktrans %}` tags and a fixed list of real Python function names (`gettext`, `pgettext`, ...) when scanning source — it has no idea `{% strans %}` or `sgettext()` exist, so a string used *only* through either one would silently stop appearing in the `.po` file with no warning (confirmed by breaking it first: previously-translated strings got marked `#~` obsolete the moment their only reference switched to `sgettext()`)
- [x] `sebastian/_translatable_strings.py` — a dead-code registry calling the real `pgettext('sebastian', ...)` for every string used via `{% strans %}`/`sgettext()` elsewhere, purely so makemessages' Python-file extraction (which *does* understand real `pgettext()`) picks them up. Never imported at runtime
- [x] `tests/test_strans_and_sgettext_usages_are_all_in_the_extraction_registry` — statically scans every template and `.py` file for `{% strans %}`/`sgettext()` calls and fails if any string is missing from the registry, so forgetting to update it (as happened twice while building this) fails a test instead of silently breaking translation the next time someone runs `makemessages`
- [x] Documented the two-tier system (ergonomic wrapper for call sites + registry for extraction) in spec §7.3, including why the registry exists and the discipline it requires

## Phase 15 — Login template moved into the library; vendored frontend assets (done)

- [x] `registration/login.html` moved from `testproject/` into `src/sebastian/templates/registration/` — it's generic username/password chrome with zero domain content, so every consumer needed it, not just the demo. Works via Django's normal template-shadow override (project `TEMPLATES[0]['DIRS']` beats app `APP_DIRS`), no urls.py changes needed since `LoginView`'s `template_name` already defaulted to this same path. Its strings now use `{% strans %}`/context `"sebastian"` like the rest of the library chrome (previously drafted with plain `{% trans %}` while it still lived in `testproject`, then corrected after the move)
- [x] Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Tom Select 2.3.1, and htmx 2.0.4 — previously loaded from jsdelivr/unpkg CDNs — are now vendored under `src/sebastian/static/sebastian/vendor/` and served via `{% static %}`. Downloaded files were verified byte-identical to the SRI hashes that were already pinned in the CDN `<link>`/`<script>` tags. Motivation: no runtime dependency on internet access or third-party hosts (relevant for intranet/air-gapped deployments), consistent with the library already vendoring its own `sebastian.css`/`widgets.js`
- [x] Override works "for free" via the same shadow mechanism as templates: a consuming project can replace any vendored file by placing one at the identical relative path under its own `STATICFILES_DIRS`. No settings key or template tag needed for this — considered and rejected a `{% lib "bootstrap" %}`-style indirection as unnecessary complexity for what Django's finder precedence already gives
- [x] Documented the vendored libraries and their pinned versions in the README

Release-checklist note for future maintainers: at each release, check whether any vendored library has a newer version worth pulling in (security fixes especially) — there is currently no automated tracking of this, and no tested compatibility *range* per library, only the single pinned version in use.

## Deferred

- Management command `sebastian-templates` for exporting/customizing templates
- SPA/schema mode (`GET /api/...?_schema`) — no `FRONTEND_MODE` setting or schema endpoint exists; would be a genuinely new feature, not a settings flip
- Inline editing (double-click in list)
- Breadcrumbs
- Browser-level test suite (Playwright) for live HTMX/TomSelect interactions
- `CONFIRM_ACTIONS` setting: declared and defaulted in `app_settings.py`, never consulted anywhere — either wire it up or remove it
- `dispatch.call()`: solid primitive, but has no consuming example yet in `testproject/demo/` or in opus
- Menu auto-generation from router registry — superseded by design: menu entries are explicit opt-in via `Sebastian.menu`, not auto-derived, so every ViewSet controls its own navbar presence
- Remove dead `modal.html` templates (both packs) once confirmed nothing external references them (see spec §13)
- i18n for `workflango` (separate repo, out of scope here)
