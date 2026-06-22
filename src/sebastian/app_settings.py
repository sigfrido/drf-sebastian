from django.conf import settings


def _sebastian(key, default):
    return getattr(settings, 'SEBASTIAN', {}).get(key, default)


def hide_unauthorized_actions() -> bool:
    return _sebastian('HIDE_UNAUTHORIZED_ACTIONS', True)


def template_pack() -> str:
    return _sebastian('TEMPLATE_PACK', 'htmx')


def skin() -> str:
    return _sebastian('SKIN', 'bootstrap5-bi')


def available_packs() -> list:
    return _sebastian('AVAILABLE_PACKS', ['htmx', 'plain'])


_DEFAULT_HTMX_PACKS = ['htmx']


def pack_uses_htmx() -> bool:
    return template_pack() in _sebastian('HTMX_PACKS', _DEFAULT_HTMX_PACKS)


def confirm_actions() -> bool:
    return _sebastian('CONFIRM_ACTIONS', False)


def confirm_deletions() -> bool:
    return _sebastian('CONFIRM_DELETIONS', True)


def brand() -> str:
    return _sebastian('BRAND', 'Sebastian')


def login_url() -> str:
    return _sebastian('LOGIN_URL', '')


def bool_display() -> str:
    """How to render boolean fields in GUI mode.

    Values: 'yesno' (Sì/No), 'checkmark' (✓/✗), 'icon' (Bootstrap bi icons),
    'truefalse' (raw True/False, no transform).
    """
    return _sebastian('BOOL_DISPLAY', 'yesno')


def date_format() -> str:
    """strftime format for DateField values in GUI mode. Default: gg/mm/aaaa."""
    return _sebastian('DATE_FORMAT', '%d/%m/%Y')


def datetime_format() -> str:
    """strftime format for DateTimeField values in GUI mode. Default: gg/mm/aaaa hh:mm."""
    return _sebastian('DATETIME_FORMAT', '%d/%m/%Y %H:%M')
