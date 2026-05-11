"""
Sebastian routers.

SebastianRouter — drop-in replacement for DRF DefaultRouter.
    Inspects ViewSet.Sebastian.inlines and auto-registers nested API URL patterns.

GUIRouter — mirrors a SebastianRouter (or DefaultRouter) to generate /gui/ URL patterns.
    Also mirrors nested inlines with their GUI-specific routes (list fragment, modal forms).
"""
from django.urls import path
from rest_framework.routers import BaseRouter, DefaultRouter

from .mixins import GUIMixin


# ---------------------------------------------------------------------------
# SebastianRouter — API router with auto-nested registration
# ---------------------------------------------------------------------------

class SebastianRouter(DefaultRouter):
    """
    Extends DefaultRouter to auto-register nested ViewSets declared in
    ViewSet.Sebastian.inlines.  Drop-in replacement for DefaultRouter in urls.py.

    Nested URL kwargs are named {parent_model_name}_pk to allow unlimited depth
    without kwarg name collisions.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nested_patterns = []

    def register(self, prefix, viewset, basename=None):
        super().register(prefix, viewset, basename)
        if basename is None:
            basename = self.get_default_basename(viewset)
        sebastian = getattr(viewset, 'Sebastian', None)
        specs = getattr(sebastian, 'inlines', [])
        if specs:
            parent_model = viewset.queryset.model
            self._register_inline_specs(prefix, parent_model, basename, specs)

    def _register_inline_specs(self, prefix, parent_model, basename, specs):
        parent_kwarg = f'{parent_model._meta.model_name}_pk'
        for spec in specs:
            if isinstance(spec, (list, tuple)):
                inline_vs, sub_specs = spec[0], list(spec[1:])
            else:
                inline_vs, sub_specs = spec, []

            mountpoint    = _get_mountpoint(inline_vs)
            nested_prefix = f'{prefix}/<{parent_kwarg}>/{mountpoint}'
            nested_base   = f'{basename}-{mountpoint}'

            self._add_nested_api_patterns(nested_prefix, inline_vs, nested_base)

            if sub_specs:
                child_model = inline_vs.queryset.model
                self._register_inline_specs(nested_prefix, child_model, nested_base, sub_specs)

    def _add_nested_api_patterns(self, prefix, viewset, basename):
        list_view   = viewset.as_view({'get': 'list', 'post': 'create'})
        detail_view = viewset.as_view({
            'get': 'retrieve', 'put': 'update',
            'patch': 'partial_update', 'delete': 'destroy',
        })
        self._nested_patterns += [
            path(f'{prefix}/',      list_view,   name=f'{basename}-list'),
            path(f'{prefix}/<pk>/', detail_view, name=f'{basename}-detail'),
        ]
        # Mirror @actions on the nested viewset
        for attr_name in dir(viewset):
            method = getattr(viewset, attr_name, None)
            if not callable(method) or not hasattr(method, 'mapping'):
                continue
            url_path = getattr(method, 'url_path', attr_name)
            detail   = getattr(method, 'detail', True)
            mapping  = dict(method.mapping)
            action_view = viewset.as_view(mapping)
            if detail:
                self._nested_patterns.append(
                    path(f'{prefix}/<pk>/{url_path}/', action_view,
                         name=f'{basename}-{attr_name}')
                )
            else:
                self._nested_patterns.append(
                    path(f'{prefix}/{url_path}/', action_view,
                         name=f'{basename}-{attr_name}')
                )

    @property
    def urls(self):
        return super().urls + self._nested_patterns + self._api_menu_patterns()

    def _api_menu_patterns(self):
        from .views import SebastianMenuView
        return [path('menu/', SebastianMenuView.as_view(), name='sebastian-api-menu')]


# ---------------------------------------------------------------------------
# GUIRouter — GUI URL mirror of an API router
# ---------------------------------------------------------------------------

class GUIRouter:
    """
    Generates /gui/ URL patterns mirroring every ViewSet in an api_router.
    Also mirrors nested ViewSets declared in ViewSet.Sebastian.inlines.

    Usage:
        api_router = SebastianRouter()
        api_router.register('richieste', RichiestaViewSet, basename='richiesta')

        gui_router = GUIRouter(api_router)

        urlpatterns = [
            path('api/', include(api_router.urls)),
            path('gui/', include(gui_router.urls)),
        ]
    """

    def __init__(self, api_router: BaseRouter):
        self.api_router   = api_router
        self._menu_groups = []   # resolved menu structure, built in _build_urls()
        self._extra_urls  = []   # custom pages registered via add_page()

    @property
    def urls(self):
        return self._build_urls()

    def _build_urls(self):
        self._menu_groups = self._build_menu_groups()
        menu_view = self._build_menu_view()
        urls = [
            path('', self._home_view(), name='sebastian-home'),
            path('menu/', self._wrap(menu_view), {'format': 'html'}, name='sebastian-menu'),
        ]
        for prefix, viewset, basename in self.api_router.registry:
            urls += self._routes_for(prefix, viewset, basename)
        urls += self._extra_urls
        return urls

    def add_page(self, url_path: str, view, name: str):
        """Register a custom GUI page (plain Django view or DRF APIView).
        The view receives request.sebastian_gui=True. Call before urls is accessed."""
        self._extra_urls.append(path(url_path, self._wrap(view), name=name))

    def _build_menu_groups(self) -> list:
        """Build a resolved list of menu group dicts from Sebastian.menu declarations."""
        groups = []
        for _, viewset, basename in self.api_router.registry:
            if not issubclass(viewset, GUIMixin):
                continue
            sebastian = getattr(viewset, 'Sebastian', None)
            menu = getattr(sebastian, 'menu', None)
            if menu is None:
                continue
            from .config import MenuGroup
            if not isinstance(menu, MenuGroup):
                continue
            items = []
            for item in menu.items:
                if item.url_name:
                    url_name = item.url_name
                elif item.action == 'list':
                    url_name = f'{basename}-gui-list'
                elif item.action == 'new':
                    url_name = f'{basename}-gui-new'
                else:
                    url_name = f'{basename}-gui-{item.action}'
                items.append({
                    'label':      item.label,
                    'url_name':   url_name,
                    'icon':       item.icon,
                    'permission': item.permission,
                })
            groups.append({
                'label':      menu.label,
                'icon':       menu.icon,
                'permission': menu.permission,
                'items':      items,
            })
        return groups

    def _build_menu_view(self):
        """Set SebastianMenuView._menu_groups (class attr) and return as_view().
        Both /gui/menu/ and /api/menu/ read from the same class attribute."""
        from .views import SebastianMenuView
        SebastianMenuView._menu_groups = self._menu_groups
        return SebastianMenuView.as_view()

    def _routes_for(self, prefix, viewset, basename):
        has_gui = issubclass(viewset, GUIMixin)
        routes  = []
        kw      = {'format': 'html'}

        routes.append(path(
            f'{prefix}/',
            self._wrap(viewset.as_view({'get': 'list', 'post': 'create'})),
            kw,
            name=f'{basename}-gui-list',
        ))

        if has_gui:
            routes.append(path(
                f'{prefix}/new/',
                self._wrap(viewset.as_view({'get': 'create_form'})),
                kw,
                name=f'{basename}-gui-new',
            ))

        routes.append(path(
            f'{prefix}/<pk>/',
            self._wrap(viewset.as_view({
                'get': 'retrieve',
                'put': 'update', 'patch': 'partial_update',
                'delete': 'destroy',
            })),
            kw,
            name=f'{basename}-gui-detail',
        ))

        if has_gui:
            routes.append(path(
                f'{prefix}/<pk>/edit/',
                self._wrap(viewset.as_view({'get': 'update_form', 'post': 'partial_update'})),
                kw,
                name=f'{basename}-gui-edit',
            ))
            routes.append(path(
                f'{prefix}/<pk>/delete/',
                self._wrap(viewset.as_view({'get': 'delete_confirm', 'post': 'delete_confirm'})),
                kw,
                name=f'{basename}-gui-delete',
            ))

        # Mirror @actions with gui_config
        for attr_name in dir(viewset):
            method = getattr(viewset, attr_name, None)
            if not callable(method) or not hasattr(method, 'mapping'):
                continue
            if not getattr(method, 'gui_config', {}):
                continue
            url_path = getattr(method, 'url_path', attr_name)
            detail   = getattr(method, 'detail', True)
            mapping  = dict(method.mapping)
            if detail:
                routes.append(path(
                    f'{prefix}/<pk>/{url_path}/',
                    self._wrap(viewset.as_view(mapping)),
                    kw,
                    name=f'{basename}-gui-{attr_name}',
                ))
            else:
                routes.append(path(
                    f'{prefix}/{url_path}/',
                    self._wrap(viewset.as_view(mapping)),
                    kw,
                    name=f'{basename}-gui-{attr_name}',
                ))

        # Nested GUI routes from Sebastian.inlines
        sebastian = getattr(viewset, 'Sebastian', None)
        specs = getattr(sebastian, 'inlines', [])
        if specs:
            parent_model = viewset.queryset.model
            routes += self._nested_gui_routes(prefix, parent_model, basename, specs)

        return routes

    def _nested_gui_routes(self, prefix, parent_model, basename, specs):
        routes = []
        parent_kwarg = f'{parent_model._meta.model_name}_pk'
        kw = {'format': 'html'}

        for spec in specs:
            if isinstance(spec, (list, tuple)):
                inline_vs, sub_specs = spec[0], list(spec[1:])
            else:
                inline_vs, sub_specs = spec, []

            mountpoint    = _get_mountpoint(inline_vs)
            nested_prefix = f'{prefix}/<{parent_kwarg}>/{mountpoint}'
            nested_base   = f'{basename}-gui-{mountpoint}'
            has_gui       = issubclass(inline_vs, GUIMixin)

            # Inline list (HTMX fragment — loaded into detail page)
            routes.append(path(
                f'{nested_prefix}/',
                self._wrap(inline_vs.as_view({'get': 'list', 'post': 'create'})),
                kw,
                name=f'{nested_base}-list',
            ))

            if has_gui:
                # Create form for modal
                routes.append(path(
                    f'{nested_prefix}/new/',
                    self._wrap(inline_vs.as_view({'get': 'create_form'})),
                    kw,
                    name=f'{nested_base}-new',
                ))

            # Inline detail — accepts PATCH/PUT/DELETE from the inline edit form
            routes.append(path(
                f'{nested_prefix}/<pk>/',
                self._wrap(inline_vs.as_view({
                    'get': 'retrieve',
                    'put': 'update', 'patch': 'partial_update',
                    'delete': 'destroy',
                })),
                kw,
                name=f'{nested_base}-detail',
            ))

            # Edit form for inline section
            if has_gui:
                routes.append(path(
                    f'{nested_prefix}/<pk>/edit/',
                    self._wrap(inline_vs.as_view({'get': 'update_form', 'post': 'partial_update'})),
                    kw,
                    name=f'{nested_base}-edit',
                ))
                routes.append(path(
                    f'{nested_prefix}/<pk>/delete/',
                    self._wrap(inline_vs.as_view({'get': 'delete_confirm', 'post': 'delete_confirm'})),
                    kw,
                    name=f'{nested_base}-delete',
                ))

            # Mirror @actions with gui_config on the nested viewset
            for attr_name in dir(inline_vs):
                action_method = getattr(inline_vs, attr_name, None)
                if not callable(action_method) or not hasattr(action_method, 'mapping'):
                    continue
                if not getattr(action_method, 'gui_config', {}):
                    continue
                url_path = getattr(action_method, 'url_path', attr_name)
                detail   = getattr(action_method, 'detail', True)
                mapping  = dict(action_method.mapping)
                if detail:
                    routes.append(path(
                        f'{nested_prefix}/<pk>/{url_path}/',
                        self._wrap(inline_vs.as_view(mapping)),
                        kw,
                        name=f'{nested_base}-{attr_name}',
                    ))
                else:
                    routes.append(path(
                        f'{nested_prefix}/{url_path}/',
                        self._wrap(inline_vs.as_view(mapping)),
                        kw,
                        name=f'{nested_base}-{attr_name}',
                    ))

            # Recurse for sub-inlines
            if sub_specs:
                child_model = inline_vs.queryset.model
                routes += self._nested_gui_routes(
                    nested_prefix, child_model, f'{basename}-{mountpoint}', sub_specs
                )

        return routes

    def _home_view(self):
        from django.shortcuts import render as django_render
        from django.urls import reverse, NoReverseMatch
        from . import app_settings

        registry = self.api_router.registry

        def home(request):
            request.sebastian_gui = True
            pack      = app_settings.template_pack()
            skin_name = app_settings.skin()
            try:
                menu_url = reverse('sebastian-menu')
            except NoReverseMatch:
                menu_url = ''
            entries = []
            for prefix, viewset, _ in registry:
                if not issubclass(viewset, GUIMixin):
                    continue
                model = getattr(getattr(viewset, 'queryset', None), 'model', None)
                if model:
                    label = model._meta.verbose_name_plural.title()
                    icon  = getattr(getattr(viewset, 'Sebastian', None), 'icon', None) or 'table'
                else:
                    label = prefix.replace('-', ' ').title()
                    icon  = 'table'
                entries.append({'prefix': prefix, 'label': label, 'icon': icon, 'url': f'{prefix}/'})
            return django_render(request, f'sebastian/{pack}/home.html', {
                'entries':           entries,
                'pack_name':         pack,
                'pack_base':         f'sebastian/{pack}/base.html',
                'skin_name':         skin_name,
                'skin_head':         f'sebastian/skins/{skin_name}/_skin.html',
                'menu_url':          menu_url,
                'file_field_template': f'sebastian/{pack}/_file_field.html',
            })

        home.__name__ = 'sebastian_home'
        return home

    def _wrap(self, view):
        def wrapped(request, *args, **kwargs):
            request.sebastian_gui = True
            return view(request, *args, **kwargs)
        wrapped.__name__ = getattr(getattr(view, 'cls', None), '__name__', 'view')
        wrapped.__module__ = view.__module__
        return wrapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_mountpoint(viewset) -> str:
    if getattr(viewset, 'mountpoint', ''):
        return viewset.mountpoint
    model = getattr(getattr(viewset, 'queryset', None), 'model', None)
    if model:
        return model._meta.verbose_name_plural.replace(' ', '-').lower()
    return viewset.__name__.lower().replace('viewset', '')
