from django.conf import settings


def _sebastian(key, default):
    return getattr(settings, 'SEBASTIAN', {}).get(key, default)


def hide_unauthorized_actions() -> bool:
    return _sebastian('HIDE_UNAUTHORIZED_ACTIONS', True)
