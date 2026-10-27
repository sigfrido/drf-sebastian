"""
Default filter of a GUI list.

A list may declare its default filter (GUI only) as a query string, or a
callable ``(request) -> str``, in ``Sebastian.default_filter``::

    class Sebastian:
        default_filter = 'status=draft&ordering=-created'

Every GUI list can also have the user's own default filter (*Save as
default* in the filter button: the current filters and ordering; *Restore
default* forgets it). The URL ``<list>/?_filter=default`` redirects to the
list filtered by the user's own default filter, if saved, otherwise by the
declared one (none declared: the unfiltered list); menu items pointing to a
list (``MenuItem(action='list')``, or any item with ``default_filter=True``)
use that URL.

The user's own default filters are kept by the store named by
``SEBASTIAN['DEFAULT_FILTER_STORE']`` (dotted path of a `DefaultFilterStore`
subclass; default `SessionDefaultFilterStore`; ``None`` = no saving).
``Sebastian.own_default_filter = False`` turns them off for one list (e.g. a
list with a single trivial filter).
"""
from urllib.parse import urlencode

from django.utils.module_loading import import_string

from . import app_settings

FILTER_PARAM = '_filter'
DEFAULT = 'default'
# Not part of a saved filter
_EXCLUDED_PARAMS = {FILTER_PARAM, 'page', 'op', 'csrfmiddlewaretoken'}


class DefaultFilterStore:
    """Where the users' own default filters are kept; ``key`` is the viewset basename."""

    def get(self, request, key):
        """The saved query string, or None if the user has none."""
        raise NotImplementedError

    def set(self, request, key, querystring):
        raise NotImplementedError

    def delete(self, request, key):
        raise NotImplementedError


class SessionDefaultFilterStore(DefaultFilterStore):
    """Default filters kept in the session: they last until logout."""
    _session_key = 'sebastian_default_filters'

    def get(self, request, key):
        return request.session.get(self._session_key, {}).get(key)

    def set(self, request, key, querystring):
        filters = dict(request.session.get(self._session_key, {}))
        filters[key] = querystring
        request.session[self._session_key] = filters

    def delete(self, request, key):
        filters = dict(request.session.get(self._session_key, {}))
        if filters.pop(key, None) is not None:
            request.session[self._session_key] = filters


def get_store():
    path = app_settings.default_filter_store()
    return import_string(path)() if path else None


def declared_default(viewset_class, request=None):
    """The default filter declared by the viewset (``Sebastian.default_filter``), or None."""
    value = getattr(getattr(viewset_class, 'Sebastian', None), 'default_filter', None)
    if callable(value):
        if request is None:
            return ''           # declared, value known only per request
        value = value(request)
    return value


def has_default(viewset_class):
    return declared_default(viewset_class) is not None


def _user_store(request, view):
    """The store of the users' own default filters, None when the list has none."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    if not getattr(getattr(type(view), 'Sebastian', None), 'own_default_filter', True):
        return None
    return get_store()


def store_key(view):
    """Key of the list in the store: the router basename of the viewset."""
    return getattr(view, 'basename', None) or f'{type(view).__module__}.{type(view).__qualname__}'


def personal_default(view, request):
    store = _user_store(request, view)
    return store.get(request, store_key(view)) if store else None


def effective_default(view, request):
    """The user's own default filter if saved, otherwise the declared one ('' = no filter)."""
    personal = personal_default(view, request)
    if personal is not None:
        return personal
    return declared_default(type(view), request) or ''


def querystring_of(params):
    """Query string of a filter (QueryDict or dict of lists), without paging and control
    parameters; empty values are dropped."""
    items = []
    for key in params:
        if key in _EXCLUDED_PARAMS:
            continue
        values = params.getlist(key) if hasattr(params, 'getlist') else params[key]
        items += [(key, v) for v in values if v not in ('', None)]
    return urlencode(items)


def list_context(view, request):
    """Context of the list template's filter button: every GUI list can have the user's own
    default filter (with a store); *Default* is offered when one applies (declared or own)."""
    store = _user_store(request, view)
    personal = store.get(request, store_key(view)) if store else None
    return {
        'url':          f'{request.path}?{FILTER_PARAM}={DEFAULT}',
        'has_default':  personal is not None or has_default(type(view)),
        'save_url':     f'{request.path}default-filter/' if store else '',
        'has_personal': personal is not None,
    }


def list_link(view, request, base='..'):
    """Link from a detail page back to its list: `base` with ``?_filter=default`` only when a
    default filter applies (declared on the viewset, or the user's own), so a list with none is
    reached without the extra redirect."""
    if has_default(type(view)) or personal_default(view, request) is not None:
        return f'{base}/?{FILTER_PARAM}={DEFAULT}'
    return base
