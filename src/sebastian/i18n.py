"""
Shared i18n helper for sebastian's own GUI chrome.

Every translatable string owned by the library (not the consumer's domain
content) uses the translation context ``"sebastian"``, so it can never be
silently shadowed by another installed app's plain-context catalog defining
the same English word (``django.contrib.admin`` ships its own "Delete",
"Save", "Home", ... — see docs/sebastian-spec.md §7.3 for the full story).

Use `sgettext()` from Python and the `{% strans %}` template tag
(`templatetags/sebastian_tags.py`) instead of calling `pgettext()` /
`{% trans ... context "sebastian" %}` directly — both are thin wrappers
around this same context, so the literal string "sebastian" only needs to be
typed once, here.
"""
from django.utils.translation import pgettext

CONTEXT = 'sebastian'


def sgettext(message: str) -> str:
    """`pgettext(CONTEXT, message)` — Python-side shorthand; mirrors the
    `{% strans %}` template tag."""
    return pgettext(CONTEXT, message)
