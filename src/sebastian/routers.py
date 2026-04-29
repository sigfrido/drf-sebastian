"""
GUIRouter — mirrors a DRF router's registry to generate parallel /gui/ URL patterns.

Usage:

    api_router = DefaultRouter()
    api_router.register('richieste', RichiestaViewSet)

    gui_router = GUIRouter(api_router)

    urlpatterns = [
        path('api/', include(api_router.urls)),
        path('gui/', include(gui_router.urls)),
    ]

The GUI router:
  - mirrors every ViewSet registered in api_router
  - forces format='html' via URL kwargs so DRF content negotiation picks
    SebastianHTMLRenderer without relying on the Accept header
  - sets request.sebastian_gui = True via a lightweight view wrapper
  - adds /new/ and /<pk>/edit/ routes for GUIMixin ViewSets
  - mirrors custom @actions that carry gui_config metadata
"""
from django.urls import path
from rest_framework.routers import BaseRouter

from .mixins import GUIMixin


class GUIRouter:

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

    def _home_view(self):
        from django.shortcuts import render as django_render

        registry = self.api_router.registry

        def home(request):
            entries = []
            for prefix, viewset, basename in registry:
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

    def _routes_for(self, prefix, viewset, basename):
        has_gui = issubclass(viewset, GUIMixin)
        routes  = []
        kw      = {'format': 'html'}  # forces SebastianHTMLRenderer via DRF content negotiation

        # List
        routes.append(path(
            f'{prefix}/',
            self._wrap(viewset.as_view({'get': 'list'})),
            kw,
            name=f'{basename}-gui-list',
        ))

        if has_gui:
            # Create form: no API equivalent
            routes.append(path(
                f'{prefix}/new/',
                self._wrap(viewset.as_view({'get': 'create_form'})),
                kw,
                name=f'{basename}-gui-new',
            ))

        # Detail
        routes.append(path(
            f'{prefix}/<pk>/',
            self._wrap(viewset.as_view({'get': 'retrieve'})),
            kw,
            name=f'{basename}-gui-detail',
        ))

        if has_gui:
            # Edit form: no API equivalent
            routes.append(path(
                f'{prefix}/<pk>/edit/',
                self._wrap(viewset.as_view({'get': 'update_form'})),
                kw,
                name=f'{basename}-gui-edit',
            ))

        # Mirror @actions that carry gui_config
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

        return routes

    @staticmethod
    def _wrap(view):
        """Sets request.sebastian_gui = True before dispatching (debug convenience flag B)."""
        def wrapped(request, *args, **kwargs):
            request.sebastian_gui = True
            return view(request, *args, **kwargs)
        wrapped.__name__ = getattr(getattr(view, 'cls', None), '__name__', 'view')
        wrapped.__module__ = view.__module__
        return wrapped
