"""
Sebastian built-in views.

SebastianMenuView — serves the application menu at /api/menu/ (JSON) and
/gui/menu/ (HTML fragment). Auto-registered by GUIRouter and SebastianRouter.
"""
from django.urls import reverse, NoReverseMatch
from rest_framework import renderers as drf_renderers
from rest_framework.response import Response
from rest_framework.views import APIView

from .app_settings import hide_unauthorized_actions
from .config import _check_permission
from .renderers import SebastianHTMLRenderer


def _evaluate_menu(request, groups: list, current_url: str = '') -> list:
    """
    Evaluate a list of resolved menu groups against the current request.

    groups — list of dicts built by GUIRouter._build_menu_groups():
        [{'label', 'icon', 'permission', 'items': [{'label', 'url_name', 'icon', 'permission'}]}]

    Returns a template/JSON-ready list:
        [{'label', 'icon', 'disabled', 'items': [{'label', 'url', 'icon', 'disabled', 'active'}]}]
    """
    hide = hide_unauthorized_actions()
    result = []
    for group in groups:
        group_permitted = _check_permission(group.get('permission'), request, None)
        if not group_permitted and hide:
            continue

        evaluated_items = []
        for item in group.get('items', []):
            item_permitted = _check_permission(item.get('permission'), request, None)
            if not item_permitted and hide:
                continue
            try:
                url = reverse(item['url_name'])
            except (NoReverseMatch, KeyError):
                url = '#'
            # Prefix match: /gui/richieste/3/ is active when current_url starts with /gui/richieste/
            active = bool(current_url and url != '#' and current_url.startswith(url))
            evaluated_items.append({
                'label':    item['label'],
                'url':      url,
                'icon':     item.get('icon', ''),
                'disabled': not item_permitted,
                'active':   active,
            })

        if not evaluated_items and hide:
            continue

        result.append({
            'label':    group['label'],
            'icon':     group.get('icon', ''),
            'disabled': not group_permitted,
            'items':    evaluated_items,
        })
    return result


class SebastianMenuView(APIView):
    """
    Serves the application menu.
    GET /api/menu/  → JSON   {'menu_groups': [...]}
    GET /gui/menu/  → HTML fragment (navbar <ul>, no full page)

    _menu_groups is injected by GUIRouter._build_menu_view() at URL-conf time.
    """
    renderer_classes  = [drf_renderers.JSONRenderer, SebastianHTMLRenderer]
    permission_classes = []   # authentication enforced per-project; menu may be public
    _menu_groups: list = []

    def get(self, request, *args, **kwargs):
        current_url = request.META.get('HTTP_HX_CURRENT_URL', '')
        # Strip scheme+host from absolute HTMX URL so we can match against reverse() paths
        if current_url.startswith('http'):
            from urllib.parse import urlparse
            current_url = urlparse(current_url).path
        menu = _evaluate_menu(request, self._menu_groups, current_url)
        return Response({'menu_groups': menu})
