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
