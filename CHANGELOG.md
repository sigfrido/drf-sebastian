# Changelog

All notable changes to this project are documented here, starting from this release. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0rc3] - unreleased

### Fixed

- **Typeahead dropdown hidden behind Bootstrap modal**: `initTypeahead` lacked the `onDropdownOpen` hook already present in `initTsSelect`. Typeaheads rendered inside a Bootstrap modal (z-index 1055) had their dropdown obscured by the backdrop. Added the same `position: fixed` + `getBoundingClientRect` + `zIndex: 9999` override

## [1.0.0rc2] - 2026-09-21

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

## [1.0.0rc1] - 2026-08-26

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
