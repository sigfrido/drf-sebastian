"""
Home page plugins.

A plugin is a panel of the home page: a template plus a context generator,
optionally guarded by a permission. Apps define plugins in a ``plugins``
module (``<app>/plugins.py``) or package (``<app>/plugins/*.py``, every
submodule is imported) and register them with `register_home_plugin`::

    from sebastian.home import HomePlugin, register_home_plugin

    @register_home_plugin
    class StockPlugin(HomePlugin):
        name     = 'stock'
        title    = 'Stock'
        icon     = 'box'
        slot     = 'right'
        order    = 20
        template = 'shop/plugins/stock.html'

        def get_context(self, request, home):
            return {'low': Item.objects.filter(qty__lt=5).count()}

The plugin modules are imported on the first home page request
(``SEBASTIAN['HOME_AUTODISCOVER']``, default ``True``). The home page renders
the visible plugins grouped by slot and sorted by ``order`` (then registration
order); the default layout of the packs has two columns, slots ``left`` and
``right`` (``SEBASTIAN['HOME_SLOTS']``). A project changes the layout by
overriding ``sebastian/<pack>/home.html`` and drawing the slots with
``{% home_plugins "<slot>" %}``. With no plugin registered the home page shows
the module tiles as before.

`MenuLinksPlugin` is a ready-made plugin that shows the items of a menu group
as buttons, with the same URLs, icons and permissions as the menu.
"""
import importlib
import logging
import pkgutil
from dataclasses import dataclass, field

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.module_loading import module_has_submodule
from django.utils.safestring import mark_safe

from . import app_settings
from .config import Permission, _check_permission

logger = logging.getLogger('sebastian.home')

DIVIDER = '-'


class HomePlugin:
    """Base class of the home page plugins (see the module docstring)."""

    name: str = ''                 # unique id; default: '<module>.<class name>'
    title: str = ''                # panel title
    icon: str = ''                 # icon of the title
    slot: str = 'left'             # slot of the home layout
    order: int = 100               # ascending within the slot, then registration order
    template: str = ''             # template of the panel body; '{pack}' is replaced by the pack
    permission: Permission = None  # like MenuItem.permission, evaluated with obj=None

    def is_visible(self, request) -> bool:
        # read from the class: a function set as class attribute would be bound to self
        perm = self.__dict__.get('permission', getattr(type(self), 'permission', None))
        return _check_permission(perm, request, None)

    def get_context(self, request, home: 'HomeContext') -> dict:
        """Context for the panel template, on top of plugin, home, request."""
        return {}

    def get_template(self, home: 'HomeContext') -> str:
        return self.template.replace('{pack}', home.pack)

    def __repr__(self):
        return f'<{type(self).__name__} {self.name!r} {self.slot}/{self.order}>'


@dataclass
class HomeContext:
    """What the home page passes to the plugins."""
    request: object
    pack: str
    skin_name: str = ''
    menu_source: list = field(default_factory=list)   # GUIRouter._menu_groups

    @cached_property
    def menu_groups(self) -> list:
        """The menu as evaluated for the request (same as the navbar menu)."""
        from .views import _evaluate_menu
        return _evaluate_menu(self.request, self.menu_source)

    def menu_group(self, label):
        for group in self.menu_groups:
            if str(group['label']) == str(label):
                return group
        return None


class MenuLinksPlugin(HomePlugin):
    """Shows the items of the menu group labelled ``menu_label`` as a column of
    small buttons, with the URLs, icons and permissions of the menu.

    ``items``: labels to show, in this order (``'-'`` = spacing); empty = the
    whole group in menu order (dividers become spacing). ``primary_items``:
    labels drawn with the ``primary`` button style instead of ``view``.
    """

    menu_label: str = ''
    items: tuple = ()
    primary_items: tuple = ()
    template = 'sebastian/{pack}/home_links.html'

    def get_links(self, home: HomeContext) -> list:
        group = home.menu_group(self.menu_label or self.title)
        if group is None:
            return []
        primary = {str(label) for label in self.primary_items}
        if self.items:
            by_label = {str(i['label']): i for i in group['items'] if not i.get('divider')}
            selected = []
            for label in self.items:
                if label == DIVIDER:
                    selected.append({'divider': True})
                elif str(label) in by_label:
                    selected.append(by_label[str(label)])
        else:
            selected = list(group['items'])
        links = []
        for item in selected:
            if item.get('divider'):
                # no spacing at the top or twice in a row (hidden items)
                if links and not links[-1].get('divider'):
                    links.append({'divider': True})
                continue
            links.append({**item, 'style': 'primary' if str(item['label']) in primary else 'view'})
        while links and links[-1].get('divider'):
            links.pop()
        return links

    def get_context(self, request, home):
        return {'links': self.get_links(home)}


# ---------------------------------------------------------------------------
# Registry

_registry: list = []
_discovered = False


def register_home_plugin(plugin_class=None, *, slot=None, order=None):
    """Register a `HomePlugin` subclass (an instance is created once).
    Usable as ``@register_home_plugin`` or ``@register_home_plugin(slot=..., order=...)``;
    ``slot``/``order`` override the class attributes."""
    def _register(cls):
        plugin = cls()
        if not plugin.name:
            plugin.name = f'{cls.__module__}.{cls.__qualname__}'
        if slot is not None:
            plugin.slot = slot
        if order is not None:
            plugin.order = order
        if any(p.name == plugin.name for p in _registry):
            raise ImproperlyConfigured(f'Home plugin {plugin.name!r} registered twice')
        _registry.append(plugin)
        return cls

    if plugin_class is None:
        return _register
    return _register(plugin_class)


def unregister_home_plugin(name):
    _registry[:] = [p for p in _registry if p.name != name]


def autodiscover():
    """Import the ``plugins`` module (or every module of the ``plugins`` package)
    of each installed app. Runs once."""
    global _discovered
    if _discovered:
        return
    _discovered = True
    for app_config in apps.get_app_configs():
        if not module_has_submodule(app_config.module, 'plugins'):
            continue
        module = importlib.import_module(f'{app_config.name}.plugins')
        for info in pkgutil.iter_modules(getattr(module, '__path__', [])):
            importlib.import_module(f'{module.__name__}.{info.name}')


def get_home_plugins() -> list:
    """The registered plugins sorted by order (stable: same order = registration order)."""
    if app_settings.home_autodiscover():
        autodiscover()
    return sorted(_registry, key=lambda p: p.order)


def render_home_plugins(home: HomeContext) -> dict:
    """Render the plugins visible to the request: ``{slot: [html, ...]}`` with every
    slot of ``SEBASTIAN['HOME_SLOTS']``. A plugin whose slot is not among them goes
    to the first slot; a plugin that raises is shown as an error panel (and logged)."""
    request = home.request
    slots = list(app_settings.home_slots())
    rendered = {slot: [] for slot in slots}
    card_template = f'sebastian/{home.pack}/home_plugin.html'
    for plugin in get_home_plugins():
        slot = plugin.slot
        if slot not in rendered:
            logger.warning('Home plugin %r: unknown slot %r, shown in %r', plugin.name, slot, slots[0])
            slot = slots[0]
        error = False
        body = ''
        try:
            if not plugin.is_visible(request):
                continue
            context = {
                **plugin.get_context(request, home),
                'plugin': plugin, 'home': home, 'skin_name': home.skin_name,
            }
            template = plugin.get_template(home)
            if template:
                body = render_to_string(template, context, request=request)
        except Exception:
            logger.exception('Home plugin %r failed (%s)', plugin.name, request.path)
            error = True
        html = render_to_string(card_template, {
            'plugin': plugin, 'body': mark_safe(body), 'error': error, 'skin_name': home.skin_name,
        }, request=request)
        rendered[slot].append(mark_safe(html))
    return rendered
