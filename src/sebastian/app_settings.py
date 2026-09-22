"""
Accessors for the ``SEBASTIAN`` settings dict.

Every setting has a hard-coded default, so the ``SEBASTIAN`` dict in a
consumer's ``settings.py`` only needs to declare the keys it wants to
override, e.g.::

    SEBASTIAN = {
        'TEMPLATE_PACK': 'plain',
        'HIDE_UNAUTHORIZED_ACTIONS': False,
    }
"""
from django.conf import settings
from .i18n import sgettext_lazy as _sl


def _sebastian(key, default):
    return getattr(settings, 'SEBASTIAN', {}).get(key, default)


def hide_unauthorized_actions() -> bool:
    """``HIDE_UNAUTHORIZED_ACTIONS`` — hide buttons the user can't use (default) vs.
    render them disabled. Default: ``True``."""
    return _sebastian('HIDE_UNAUTHORIZED_ACTIONS', True)


def template_pack() -> str:
    """``TEMPLATE_PACK`` — active template pack name. Default: ``'htmx'``."""
    return _sebastian('TEMPLATE_PACK', 'htmx')


def skin() -> str:
    """``SKIN`` — active skin key. Default: ``'bootstrap5-bi'``."""
    return _sebastian('SKIN', 'bootstrap5-bi')


_DEFAULT_SKINS = [
    ('bootstrap5-bi', _sl('Light theme'),      'sebastian/skins/light.css'),
    ('dark',          _sl('Dark theme'),       'sebastian/skins/dark.css'),
    ('accessible',    _sl('Accessible theme'), 'sebastian/skins/accessible.css'),
]


def skins() -> list:
    """``SKINS`` — registry of available skins as ``(key, label, css_paths)`` tuples.
    ``css_paths`` can be a single string or a list of strings (static file paths)."""
    return _sebastian('SKINS', _DEFAULT_SKINS)


def skin_css_files(key: str) -> list[str]:
    """Return the list of static CSS paths for the given skin key.
    Falls back to the first available skin if the key is not found."""
    for sk, _label, paths in skins():
        if sk == key:
            return [paths] if isinstance(paths, str) else list(paths)
    _, _label, paths = skins()[0]
    return [paths] if isinstance(paths, str) else list(paths)


def skin_choices() -> list[tuple[str, str]]:
    """Return ``(key, label)`` pairs for all registered skins — ready for a
    form ``choices`` argument."""
    return [(key, label) for key, label, _paths in skins()]


def available_packs() -> list:
    """``AVAILABLE_PACKS`` — template packs offered on the home page pack switcher.
    Default: ``['htmx', 'plain']``."""
    return _sebastian('AVAILABLE_PACKS', ['htmx', 'plain'])


_DEFAULT_HTMX_PACKS = ['htmx']


def pack_uses_htmx() -> bool:
    """Whether the active `template_pack()` is HTMX-aware, per ``HTMX_PACKS``
    (default ``['htmx']``). Custom packs opt in by listing themselves there."""
    return template_pack() in _sebastian('HTMX_PACKS', _DEFAULT_HTMX_PACKS)


def confirm_actions() -> bool:
    """``CONFIRM_ACTIONS`` — global default requiring confirmation before
    non-destructive actions. Default: ``False``.

    Note: not currently consulted anywhere in the library — actions opt into
    confirmation individually via ``gui_config['confirmation']``. Kept for
    forward compatibility; do not rely on this changing action behaviour yet.
    """
    return _sebastian('CONFIRM_ACTIONS', False)


def confirm_deletions() -> bool:
    """``CONFIRM_DELETIONS`` — require confirmation before deleting a record.
    Default: ``True``."""
    return _sebastian('CONFIRM_DELETIONS', True)


def brand() -> str:
    """``BRAND`` — product name shown in the navbar. Default: ``'Sebastian'``."""
    return _sebastian('BRAND', 'Sebastian')


def login_url() -> str:
    """``LOGIN_URL`` — where to send unauthenticated users. Default: ``''``
    (no redirect)."""
    return _sebastian('LOGIN_URL', '')


_DEFAULT_BUTTON_STYLES = {
    'new':       'btn-primary',
    'edit':      'btn-primary',
    'delete':    'btn-danger',
    'view':      'btn-outline-secondary',
    'info':      'btn-info',
    'warning':   'btn-warning',
    'success':   'btn-success',
    'secondary': 'btn-secondary',
}


def button_styles_for_skin(skin_key: str) -> dict:
    """Resolve semantic button style → Bootstrap CSS class for the given skin.

    The result is built from ``_DEFAULT_BUTTON_STYLES``, then overridden by
    ``SEBASTIAN['BUTTON_STYLES']['*']`` (all skins), then by the skin-specific
    key.  Consumer projects add custom semantic styles the same way::

        SEBASTIAN = {
            'BUTTON_STYLES': {
                '*':    {'edit': 'btn-success', 'anteprima': 'btn-info'},
                'dark': {'edit': 'btn-outline-primary'},
            }
        }
    """
    overrides = _sebastian('BUTTON_STYLES', {})
    return {
        **_DEFAULT_BUTTON_STYLES,
        **overrides.get('*', {}),
        **overrides.get(skin_key, {}),
    }


def bool_display() -> str:
    """How to render boolean fields in GUI mode.

    Values: 'yesno' (Yes/No), 'checkmark' (✓/✗), 'icon' (Bootstrap bi icons),
    'truefalse' (raw True/False, no transform).
    """
    return _sebastian('BOOL_DISPLAY', 'yesno')


def date_format() -> str:
    """strftime format for DateField values in GUI mode. Default: dd/mm/yyyy."""
    return _sebastian('DATE_FORMAT', '%d/%m/%Y')


def datetime_format() -> str:
    """strftime format for DateTimeField values in GUI mode. Default: dd/mm/yyyy HH:MM."""
    return _sebastian('DATETIME_FORMAT', '%d/%m/%Y %H:%M')
