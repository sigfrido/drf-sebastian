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
    """``SKIN`` — active CSS/icon skin. Default: ``'bootstrap5-bi'``."""
    return _sebastian('SKIN', 'bootstrap5-bi')


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
