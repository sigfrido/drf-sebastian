# Changelog

All notable changes to this project are documented here, starting from this release. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
