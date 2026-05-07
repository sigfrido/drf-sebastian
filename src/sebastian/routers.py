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
        return super().urls + self._nested_patterns


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
        self.api_router = api_router

    @property
    def urls(self):
        return self._build_urls()

    def _build_urls(self):
        urls = [path('', self._home_view(), name='sebastian-home')]
        for prefix, viewset, basename in self.api_router.registry:
            urls += self._routes_for(prefix, viewset, basename)
        return urls

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
                self._wrap(viewset.as_view({'get': 'update_form'})),
                kw,
                name=f'{basename}-gui-edit',
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
                    self._wrap(inline_vs.as_view({'get': 'update_form'})),
                    kw,
                    name=f'{nested_base}-edit',
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

        registry = self.api_router.registry

        def home(request):
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
            return django_render(request, 'sebastian/home.html', {'entries': entries})

        home.__name__ = 'sebastian_home'
        return home

    @staticmethod
    def _wrap(view):
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
