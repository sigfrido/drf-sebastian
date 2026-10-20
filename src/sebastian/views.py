"""
Sebastian built-in views.

SebastianMenuView — serves the application menu at /api/menu/ (JSON) and
/gui/menu/ (HTML fragment). Auto-registered by GUIRouter and SebastianRouter.

SebastianMessagesView — returns the messages HTML fragment. The default
implementation returns an empty container. Subclass and override get_html()
to provide project-specific message rendering.  Pass the subclass to
GUIRouter(messages_view=...) so it is registered at /gui/messages/.
"""
from django.http import HttpResponse
from django.urls import reverse, NoReverseMatch
from django.views import View
from rest_framework import renderers as drf_renderers
from rest_framework.response import Response
from rest_framework.views import APIView

from .app_settings import hide_unauthorized_actions
from .config import _check_permission
from .renderers import SebastianHTMLRenderer


def gui_page_context(request) -> dict:
    """Context of a custom GUI page extending ``pack_base`` (layout, skin, menu, messages):
    the same keys the ViewSet pages get from the renderer."""
    from . import app_settings
    from .renderers import is_htmx_partial
    pack = app_settings.template_pack()
    skin_name = getattr(request, 'sebastian_skin', None) or app_settings.skin()

    def url(name):
        try:
            return reverse(name)
        except NoReverseMatch:
            return ''
    return {
        'is_htmx':        is_htmx_partial(request),
        'pack_name':      pack,
        'pack_base':      f'sebastian/{pack}/base.html',
        'skin_name':      skin_name,
        'skin_css_files': app_settings.skin_css_files(skin_name),
        'menu_url':       url('sebastian-menu'),
        'messages_url':   url('sebastian-messages'),
        'file_field_template': f'sebastian/{pack}/_file_field.html',
    }


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
            if item.get('divider'):
                evaluated_items.append({'divider': True})
                continue
            item_permitted = _check_permission(item.get('permission'), request, None)
            if not item_permitted and hide:
                continue
            try:
                url = reverse(item['url_name'])
            except (NoReverseMatch, KeyError):
                url = '#'
            href = f"{url}?{item['query']}" if item.get('query') and url != '#' else url
            evaluated_items.append({
                'label':    item['label'],
                'url':      href,
                'path':     url,   # without query string: active item matching
                'icon':     item.get('icon', ''),
                'disabled': not item_permitted,
                'active':   False,   # resolved below
            })

        if not evaluated_items and hide:
            continue

        # Active item: exact match wins; fall back to longest prefix match.
        # This ensures /gui/requests/new/ activates "New", not "List".
        if current_url:
            candidate_urls = [i['path'] for i in evaluated_items if not i.get('divider') and i['path'] != '#']
            exact = current_url if current_url in candidate_urls else None
            if exact:
                best = exact
            else:
                prefixes = [u for u in candidate_urls if current_url.startswith(u)]
                best = max(prefixes, key=len) if prefixes else None
            for item in evaluated_items:
                if not item.get('divider'):
                    item['active'] = (item['path'] == best)

        result.append({
            'label':    group['label'],
            'icon':     group.get('icon', ''),
            'disabled': not group_permitted,
            'active':   any(i['active'] for i in evaluated_items if not i.get('divider')),
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

    def get_renderers(self):
        if not getattr(self.request, 'sebastian_gui', False):
            return [drf_renderers.JSONRenderer()]
        return super().get_renderers()

    def get(self, request, *args, **kwargs):
        current_url = request.META.get('HTTP_HX_CURRENT_URL', '')
        # Strip scheme+host from absolute HTMX URL so we can match against reverse() paths
        if current_url.startswith('http'):
            from urllib.parse import urlparse
            current_url = urlparse(current_url).path
        menu = _evaluate_menu(request, self._menu_groups, current_url)
        return Response({'menu_groups': menu})


class SebastianMessagesView(View):
    """Messages fragment endpoint — returns the #sebastian-messages div.

    Default returns an empty container.  Subclass and override ``get_html()``
    to render project-specific messages (e.g. Django session messages).
    Pass the subclass to ``GUIRouter(messages_view=MyMessagesView.as_view())``.
    """

    def get_html(self, request) -> str:
        return '<div id="sebastian-messages" class="mb-2"></div>'

    def get(self, request, *args, **kwargs):
        return HttpResponse(self.get_html(request), content_type='text/html')
