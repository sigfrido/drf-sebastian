"""
Extraction-only registry for strings used via `{% strans %}` or `sgettext()`.

`django-admin makemessages` recognizes a fixed set of literal function/tag
names when scanning source: the built-in `{% trans %}`/`{% blocktrans %}`
template tags, and `gettext`/`pgettext`/... calls in Python files. It has no
idea `{% strans %}` (templatetags/sebastian_tags.py) or `sgettext()`
(i18n.py) exist — both are thin wrappers, invisible to extraction — so a
template using only `{% strans "X" %}`, or Python code calling only
`sgettext("X")`, would silently vanish from the .po file with no warning.
This module exists purely so makemessages' ordinary Python-file extraction
(which *does* understand real `pgettext()` calls) picks these strings up.
`_strings()` below is never called anywhere — makemessages only scans the
source text, it doesn't execute this module — so the calls are wrapped in a
function specifically to keep `pgettext()` from ever running at import time
(pdoc and any other bare `import sebastian...` would otherwise crash with
`AppRegistryNotReady`, since translation needs `django.setup()` to have run
first).

Whenever you add or change a `{% strans "..." %}` or `sgettext("...")` call
anywhere in the library, add or update the matching line here, then re-run:

    django-admin makemessages -l it --no-location   # (from src/sebastian/)
    django-admin compilemessages

The two `{% blocktrans context "sebastian" %}` pagination-count strings in
list.html do NOT need an entry here — blocktrans IS understood natively by
makemessages, unlike strans.

Any `# Translators:` comment explaining a placeholder (e.g. `$OBJECT`) must
live on the line directly above the `pgettext()` call *here*, not at the
`sgettext()` call site — makemessages only reads comments adjacent to the
literal extraction point it recognizes, which is always this file.
"""
# NOTE: this must call the real `pgettext` directly, NOT the `sgettext()`
# wrapper from .i18n -- xgettext's Python extraction only recognizes a fixed
# set of literal function names (gettext, pgettext, ngettext, ...); a custom
# wrapper name is just as invisible to it as the {% strans %} tag is.
from django.utils.translation import pgettext


def _strings():  # pragma: no cover - never called, see module docstring
    return (
        # Used only from Python (mixins.py / renderers.py / serializers.py), never from a template:
        # Translators: $<VAR> tokens are placeholders substituted after 
        # translation — keep them verbatim.
        pgettext('sebastian', 'Perform $ACTION on $OBJECT?'),
        pgettext('sebastian', 'Delete $OBJECT?'),
        pgettext('sebastian', 'An error occurred while saving. Please check the entered data.'),
        pgettext('sebastian', 'Error'),
        pgettext('sebastian', "Field '$FIELD' is not accessible."),
        pgettext('sebastian', "Field '$FIELD' is read-only."),
        # Used via {% strans %} in templates (and some also from Python):
        pgettext('sebastian', 'Available modules'),
        pgettext('sebastian', 'Cancel'),
        pgettext('sebastian', 'Clear'),
        pgettext('sebastian', 'Close'),
        pgettext('sebastian', 'Confirm'),
        pgettext('sebastian', 'Confirm?'),
        pgettext('sebastian', 'Delete'),
        pgettext('sebastian', 'Detail'),
        pgettext('sebastian', 'Edit'),
        pgettext('sebastian', 'File will be removed'),
        pgettext('sebastian', 'Filter'),
        pgettext('sebastian', 'Home'),
        pgettext('sebastian', 'Invalid username or password.'),
        pgettext('sebastian', 'List'),
        pgettext('sebastian', 'Loading…'),
        pgettext('sebastian', 'New'),
        pgettext('sebastian', 'No'),
        pgettext('sebastian', 'No modules registered.'),
        pgettext('sebastian', 'No records found.'),
        pgettext('sebastian', 'Password'),
        pgettext('sebastian', 'Remove file'),
        pgettext('sebastian', 'Save'),
        pgettext('sebastian', 'Select a file to replace the current one.'),
        pgettext('sebastian', 'Sign in'),
        pgettext('sebastian', 'Sort by'),
        pgettext('sebastian', 'Sort by…'),
        pgettext('sebastian', 'Then by'),
        pgettext('sebastian', 'Username'),
        pgettext('sebastian', 'Yes'),
    )
