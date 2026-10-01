# Changelog

All notable changes to this project are documented here, starting from this release. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0-rc7] - unreleased

### Changed

- **Solid buttons**: the built-in `view` style is now `btn-secondary` (was `btn-outline-secondary`), and the Cancel, Filter, pagination and file-delete buttons of the htmx and plain templates are filled (`btn-secondary`, `btn-danger`) instead of outlined. Bootstrap's solid buttons darken on hover. Restore the old look per skin with `SEBASTIAN['BUTTON_STYLES']`

### Added

- **Action order**: optional `gui_config['order']` (number). Actions with an order are listed first, ascending; the others follow in method-name order as before
- **Page titles**: `get_page_title(action, obj)` on the viewset (`_SebastianBaseMixin`, overridable) builds the browser title — list "Label - List", detail "Label - <obj>", form "Label - <obj> [Edit]" ("Label - New [Edit]" when creating); `SingletonGUIMixin`: "Label" / "Label [Edit]". The renderer passes it as `page_title`; the base templates use it in `<title>` (falling back to `brand_title`)

### Fixed

- **"None" in the detail view**: `display_value` returned the raw `None` of empty nullable fields (dates, decimals…), shown as the literal text "None"; it now returns an empty string
- The download buttons of `link_field` actions (detail and list, both packs) were outlined (`cfg.color` defaulting to `outline-secondary`); they now resolve through `btn_class_cfg` like the other action buttons
- **Title stuck on the first page loaded**: htmx content fragments carried no `<title>`, so navigating list → detail → form kept e.g. "Requests — List". Fragments swapped into `#sebastian-content` now include `<title>{{ page_title }}</title>` (htmx updates `document.title` from it); inline fragments don't. The generic per-template titles ("Detail", "Edit", "New") are gone

## [1.0.0-rc6] - 2026-09-29

### Fixed

- **"None" in the form of nullable fields**: the htmx form rendered a nullable `TextField` whose value is `None` as the literal text "None" inside the `<textarea>` (saved back as a string if the form was submitted); the plain pack did the same for `<input>` values. Both now render an empty value
- `form_input_value` treated every falsy value as empty, so a numeric `0` showed as an empty input; only `None` and `''` are now empty

## [1.0.0-rc5] - 2026-09-29

### Fixed

- **Dropdowns near the bottom of the page were cut off**: single-select and typeahead dropdowns (`position: fixed`, attached to `<body>`) always opened below the control, so near the bottom edge the list ran off the viewport and only the first option was visible. They now open upward when there isn't enough room below and there is more above, and the option list is capped to the available height (it scrolls instead); a `ResizeObserver` re-places the dropdown while open, e.g. when a typeahead loads its results

## [1.0.0-rc4] - 2026-09-29

### Fixed

- **Italian translation missing when installed from git**: `*.mo` was gitignored, so a package installed with `pip install git+https://…@tag` shipped only `django.po` and the whole GUI chrome stayed in English. The compiled `locale/it/LC_MESSAGES/django.mo` is now versioned, and a test fails if it is missing or out of date with the `.po`
- Missing Italian translations for the built-in skin names (Light/Dark/Accessible theme)

## [1.0.0-rc3] - 2026-09-29

### Added

- **Display renderers for detail views** (`Sebastian.field_config[field]['display']`), parallel to the existing `widget` key: built-in `'textbr'` (newlines → `<br>`, XSS-safe) or a callable `(value) -> SafeString`. Rendered by the new `{% render_display data field_name fc %}` tag in both packs. `widget` and `display` are auto-detected from the DRF field style: a model `TextField` gets `widget='textarea'` and `display='textbr'` with no configuration; explicit entries win (spec §4.7)
- **Semantic button styles**: `gui_config['style']` names a semantic style (`new`, `edit`, `delete`, `view`, `info`, `warning`, `success`, `secondary`) resolved per skin via the new `SEBASTIAN['BUTTON_STYLES']` setting; template filters `btn_class` / `btn_class_cfg`. `color` keeps working as a raw Bootstrap suffix fallback (spec §4.11)
- **`{% actions "group" %}` template tag** and `gui_config['group']` (default `'actions'`): action buttons are rendered by `_actions.html` partials (both packs) and can be placed in named groups by extending templates
- **GUI messages view**: `SebastianMessagesView` (override `get_html()` to render e.g. Django session messages), registered by `GUIRouter` at `messages/` (`sebastian-messages`), customizable via `GUIRouter(messages_view=...)`. The htmx pack loads it into `#sebastian-messages` on every page and swapped-in fragment
- **`NestedGUIMixin.parent_is_editable(parent)` hook**: overridable gate for editing nested resources, evaluated before `Sebastian.edit_permission`; and **`GUIMixin.extra_context()`** to merge view-specific values into the renderer's template context
- Form tabs: the first group with an editable field is active when the form opens; the active tab caption is bold

### Changed

- **Breaking — no workflow knowledge in the library**: `NestedGUIMixin` no longer duck-types workflow-managed parents (`wfm_state` / `wfm`: suspended state, owner/admin checks). Parent editability is now the `parent_is_editable()` hook (default: editable); workflow-aware behaviour lives in the workflow library (e.g. workflango's `WFNestedGUIMixin`). The renderer no longer puts `workflow_transitions` in the template context (it used to call the view's `get_workflow_transitions()`): a view that needs it provides it through `extra_context()`
- Top-level create/update/delete in the htmx pack answer with an empty `HttpResponse` + `HX-Redirect` instead of a rendered DRF response
- Detail header action buttons use `d-flex gap-1` instead of `btn-group`, keeping individual border radius
- `__version__` aligned with the package version (it was still `0.1.0`)

### Fixed

- **Typeahead dropdown hidden behind a Bootstrap modal**: `initTypeahead` lacked the `onDropdownOpen` hook already present in `initTsSelect`; added the same `position: fixed` + `getBoundingClientRect` + `zIndex: 9999` override
- **Errors raised by `perform_create` / `perform_update` in nested forms**: a DRF `ValidationError` was re-raised (breaking the inline form) and any other exception showed a generic message; both are now mapped to the form's errors (field errors by name, otherwise `non_field_errors`) and the form is re-rendered
- **Tab after a failed save**: the re-rendered form (update / partial_update / create) now activates the first group holding a field with errors (or the first editable group for `non_field_errors`) instead of always the first tab, which could hide the error messages
- Clearer error messages in the renderer for form errors

## [1.0.0-rc2] - 2026-09-21

### Added

- **Configurable skin system** (`SKINS` setting): skins are a list of `(key, label, css_paths)` tuples where `css_paths` can be a string or a list of strings. `app_settings.skin_css_files(key)` resolves the CSS paths for injection; `app_settings.skin_choices()` returns `(key, label)` pairs for form fields. Three built-in skins ship with the library: `bootstrap5-bi` (default light), `dark`, `accessible`. Per-request skin override via `request.sebastian_skin` (set by the consuming app, e.g. from a user preference)
- `sgettext_lazy()` in `i18n.py`: lazy variant of `sgettext()` using `pgettext_lazy('sebastian', ...)`, required for module-level string constants in `app_settings.py`. Strings registered in `_translatable_strings.py` for `makemessages` extraction

### Changed

- `_base.html`: injects skin CSS files via `{% for css_file in skin_css_files %}` loop after the fixed vendor links; `{% block extra_css %}` follows immediately after
- `renderers.py` and `routers.py` home view: resolve skin key from `request.sebastian_skin` (if set) before falling back to `app_settings.skin()`; pass `skin_css_files` list in every template context
- `form.html`: static-choice `<select>` fields always get `class="form-select ts-select"` (previously conditional on `fc.widget == 'ts-select'`), ensuring consistent TomSelect initialisation and dropdown positioning

### Fixed

- **TomSelect dropdown displacement** (single-select): `dropdownParent` was passed as `document.body` (DOM element) but TomSelect v2.3.1 checks `"body" === settings.dropdownParent` (string literal) to trigger its `positionDropdown()` calculation — the check silently failed. Fixed by passing the string `'body'`. Added an `onDropdownOpen` callback that additionally overrides to `position: fixed` with `getBoundingClientRect()` for maximum robustness against scroll-container and containing-block edge cases
- **Multi-select Bootstrap arrow bleed-through**: Bootstrap `.form-select` applies a `background-image` chevron to any element carrying that class, including TomSelect multi-select wrappers (`.ts-wrapper.multi`). TomSelect's own CSS suppresses the arrow only for `.single`. Added `.ts-wrapper.multi.form-select { background-image: none !important }` to `sebastian.css`
- **Multi-select empty-value option used as placeholder**: when a `<select multiple>` contains an `<option value="">…text…</option>` (e.g. a visual separator), TomSelect reads its text as the input's `placeholder`. Fixed by setting `placeholder: ''` explicitly in the multi-select TomSelect options
- **Multi-select items overflow without wrapping** in filter forms: added `max-width: 14rem` on `#sb-filter-form .ts-wrapper.multi` so selected tags wrap inside the control instead of stretching the filter row

## [1.0.0-rc1] - 2026-08-26

First release candidate. Feature-complete and used in production by another project; this candidate exists to get more real-world mileage before committing to the API-stability guarantee of a full `1.0.0`.

### Added

- Full Django i18n support for the library's own GUI chrome, with a bundled Italian translation catalog. `{% strans %}` (template) and `sgettext()` (Python) wrap the required `msgctxt "sebastian"` so call sites don't need to write it by hand — see `docs/sebastian-spec.md` §7.3 for the maintainer workflow, including the `_translatable_strings.py` extraction registry `makemessages` needs
- Login screen: unauthenticated requests redirect to it, the current username shows in the navbar, logout is a proper POST form. The template lives in the library itself (`registration/login.html`) so every consuming project gets it for free, overridable via Django's normal template-shadowing
- Delete button next to Edit in detail view, gated by `view.can_delete`
- Frontend libraries (Bootstrap, Bootstrap Icons, Tom Select, htmx) are now vendored under `static/sebastian/vendor/` instead of loaded from a CDN — no internet access required at runtime, and consuming projects can override any of them by shadowing the same path in their own `STATICFILES_DIRS`
- Demo project (`testproject/demo`): phase-based `FieldGroup` permissions (general fields editable only in draft, management fields only by managers while submitted, fully locked once approved/rejected), a `reject` action alongside the existing `approve`, and role-based demo accounts (`manager`/`user` groups)

### Changed

- `testproject` translated from Italian to English (models, fields, fixtures) and renamed its app from `selco` to `demo`
- README rewritten with a quickstart, a demo-accounts table, and a frontend-dependencies table listing vendored library versions
- Full API reference regenerated with `pdoc` (`docs/api/`)

### Fixed

- `create_form()` omitted `instance` from its template context entirely, which could render a bound `str.title` method literally in a blank text field instead of an empty value
- Sebastian's own translations could be silently shadowed by `django.contrib.admin`'s bundled Italian catalog for common words (e.g. "Delete" → "Cancella"); every library string now carries `msgctxt "sebastian"` to prevent collisions regardless of `INSTALLED_APPS` order
- Two `PermissionDenied` messages in `serializers.py` (inaccessible/read-only field) were hardcoded in English and never reached the translation catalog
