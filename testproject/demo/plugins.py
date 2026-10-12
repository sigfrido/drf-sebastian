"""Home page plugins of the demo app (sebastian.home), found by autodiscovery."""
from django.db.models import Count, Q

from sebastian.home import MenuLinksPlugin, register_home_plugin

from .models import Request


@register_home_plugin
class SuppliersPlugin(MenuLinksPlugin):
    name       = 'demo.suppliers'
    title      = 'Suppliers'
    icon       = 'building'
    slot       = 'left'
    order      = 10
    menu_label = 'Suppliers'


@register_home_plugin
class RequestsPlugin(MenuLinksPlugin):
    """Links of the Requests menu (New last, as the primary button) and a count."""
    name          = 'demo.requests'
    title         = 'Requests'
    icon          = 'clipboard-check'
    slot          = 'right'
    order         = 10
    menu_label    = 'Requests'
    items         = ('List', 'Settings', '-', 'New')
    primary_items = ('New',)
    template      = 'demo/plugins/requests.html'

    def get_context(self, request, home):
        counts = Request.objects.aggregate(
            total=Count('pk'), draft=Count('pk', filter=Q(status=Request.Status.DRAFT)))
        return {**super().get_context(request, home), **counts}
