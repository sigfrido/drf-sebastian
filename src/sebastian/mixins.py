from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from rest_framework import renderers as drf_renderers
from rest_framework.mixins import CreateModelMixin, UpdateModelMixin
from rest_framework.response import Response as DRFResponse

from .app_settings import hide_unauthorized_actions
from .config import _check_permission
from .renderers import SebastianHTMLRenderer


class GUIMixin:
    """
    ViewSet/GenericAPIView mixin that enables Sebastian GUI generation.

    Adds SebastianHTMLRenderer alongside JSONRenderer so the same ViewSet
    serves JSON (Accept: application/json or /api/ routes) and HTML
    (Accept: text/html or /gui/ routes with format='html' URL kwarg).

    Sets request.sebastian_gui = True when the selected renderer is HTML,
    available for use in custom hooks and debug tooling.

    GUI-specific actions provided:
        create_form(request)         — empty form for a new instance
        update_form(request, pk)     — pre-filled form for an existing instance
    """

    renderer_classes = [drf_renderers.JSONRenderer, SebastianHTMLRenderer]

    _STANDARD_ACTIONS = frozenset([
        'list', 'create', 'retrieve', 'update', 'partial_update', 'destroy',
        'create_form', 'update_form',
    ])

    # ------------------------------------------------------------------ #
    # Request lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def initialize_request(self, request, *args, **kwargs):
        drf_request = super().initialize_request(request, *args, **kwargs)
        # Transfer flag set by GUIRouter's URL kwargs wrapper (django request → drf request)
        if getattr(request, 'sebastian_gui', False):
            drf_request.sebastian_gui = True
        return drf_request

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # After content negotiation, flag HTML responses (A + B from design)
        if getattr(request, 'accepted_renderer', None):
            if request.accepted_renderer.format == 'html':
                request.sebastian_gui = True

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # After a successful custom action in GUI mode, redirect to the parent URL
        # so the detail page reloads from the correct path (avoids broken inline URLs).
        action = getattr(self, 'action', None)
        if (
            isinstance(response, DRFResponse)  # skip FileResponse / StreamingHttpResponse
            and getattr(request, 'sebastian_gui', False)
            and response.status_code == 200
            and action not in self._STANDARD_ACTIONS
            and request.method.lower() != 'get'
            and 'HX-Redirect' not in response
        ):
            response['HX-Redirect'] = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        return response

    # ------------------------------------------------------------------ #
    # Create / update — redirect to detail on success                     #
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return super().create(request, *args, **kwargs)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content'},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        pk = serializer.data.get('id')
        resp = DRFResponse(serializer.data, status=200, headers=headers)
        resp['HX-Redirect'] = f'{request.path}{pk}/'
        return resp

    def update(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return super().update(request, *args, **kwargs)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            resp = DRFResponse(
                {'serializer': serializer, 'instance': serializer.data, 'action': 'update',
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content'},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        resp = DRFResponse(serializer.data, status=200)
        resp['HX-Redirect'] = request.path
        return resp

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        if getattr(request, 'sebastian_gui', False) and response.status_code == 204:
            self.action = 'list'
            request._request.path = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
            return self.list(request, *args, **kwargs)
        return response

    # ------------------------------------------------------------------ #
    # GUI-only actions (registered by GUIRouter)                          #
    # ------------------------------------------------------------------ #

    def create_form(self, request, *args, **kwargs):
        """Return an empty HTML form for creating a new instance."""
        serializer = self.get_serializer()
        # Absolute URL so the form submits correctly when loaded as an HTMX fragment
        # (relative ../  would resolve against the browser URL, not the form fetch URL)
        submit_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        return DRFResponse({
            'serializer': serializer, 'action': 'create',
            'submit_url': submit_url, 'cancel_url': submit_url,
            'htmx_target': '#sebastian-content',
        })

    def update_form(self, request, *args, **kwargs):
        """Return an HTML form pre-filled with an existing instance's data."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        submit_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        return DRFResponse({
            'serializer': serializer, 'instance': serializer.data, 'action': 'update',
            'submit_url': submit_url, 'cancel_url': submit_url,
            'htmx_target': '#sebastian-content',
        })

    # ------------------------------------------------------------------ #
    # Sebastian metadata helpers                                          #
    # ------------------------------------------------------------------ #

    def get_sebastian_config(self):
        """Returns the ViewSet.Sebastian inner class, or None."""
        return getattr(self.__class__, 'Sebastian', None)

    def get_groups(self):
        """Returns the declared groups list (FieldGroup + EntityGroup), or []."""
        sebastian = self.get_sebastian_config()
        if not sebastian:
            return []
        return getattr(sebastian, 'groups', [])

    def retrieve(self, request, *args, **kwargs):
        self._sebastian_obj = self.get_object()
        serializer = self.get_serializer(self._sebastian_obj)
        return DRFResponse(serializer.data)

    def get_available_actions(self):
        """
        Returns gui_config metadata for @actions the current user has permission for.
        Used by templates to render action buttons.
        """
        obj = getattr(self, '_sebastian_obj', None)
        hide = hide_unauthorized_actions()
        available = []
        for name in dir(self.__class__):
            method = getattr(self.__class__, name, None)
            if not callable(method) or not hasattr(method, 'mapping'):
                continue
            gui_config = getattr(method, 'gui_config', {})
            if not gui_config:
                continue

            # Check DRF permission_classes declared on the action
            permitted = True
            permission_classes = getattr(method, 'kwargs', {}).get('permission_classes', [])
            for perm_class in permission_classes:
                if not perm_class().has_permission(self.request, self):
                    permitted = False
                    break

            # Check Sebastian-style permission (callable or list) from gui_config.
            # Only evaluated when obj is available (detail context); in list context
            # obj is None and object-aware callables would fail — DRF permission_classes
            # already handle user-level gating for list actions.
            if permitted and obj is not None:
                permitted = _check_permission(gui_config.get('permission'), self.request, obj)

            if not permitted and hide:
                continue

            primary_method = next(iter(method.mapping), 'post')
            available.append({
                'name': name,
                'gui_config': gui_config,
                'method': primary_method,
                'disabled': not permitted,
            })
        return available


class NestedGUIMixin(GUIMixin):
    """
    ViewSet mixin for nested resources (child of another ViewSet).

    Auto-detects the parent from URL kwargs named `{parent_model_name}_pk`.
    Filters the queryset and injects the parent FK on create.

    Usage:
        class AllegatoViewSet(NestedGUIMixin, viewsets.ModelViewSet):
            queryset         = Allegato.objects.all()
            serializer_class = AllegatoSerializer
            mountpoint       = 'allegati'   # URL segment after parent pk

    The parent is declared in the parent ViewSet:
        class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
            class Sebastian:
                inlines = [AllegatoViewSet]
    """

    _sebastian_is_nested = True
    parent_field = ''  # FK on this model to parent; auto-detected if blank

    # ------------------------------------------------------------------ #
    # Inline helpers                                                       #
    # ------------------------------------------------------------------ #

    def _inline_list_path(self):
        """Return the GUI URL of the inline list (e.g. /gui/richieste/3/allegati/)."""
        mp = getattr(self.__class__, 'mountpoint', '')
        if mp:
            p = self.request.path
            marker = f'/{mp}/'
            idx = p.find(marker)
            if idx != -1:
                return p[:idx + len(marker)]
        return self.request.path

    def _inline_container_id(self):
        mp = getattr(self.__class__, 'mountpoint', '')
        return f'inline-{mp}' if mp else 'inline-section'

    # ------------------------------------------------------------------ #
    # Create / update — reload inline section instead of page redirect    #
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return CreateModelMixin.create(self, request, *args, **kwargs)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            container = self._inline_container_id()
            list_path = self._inline_list_path()
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'htmx_target': f'#{container}', 'cancel_url': list_path,
                 'submit_url': list_path},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_create(serializer)
        self.action = 'list'
        request._request.path = self._inline_list_path()
        return self.list(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return UpdateModelMixin.update(self, request, *args, **kwargs)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            container = self._inline_container_id()
            list_path = self._inline_list_path()
            resp = DRFResponse(
                {'serializer': serializer, 'instance': serializer.data, 'action': 'update',
                 'htmx_target': f'#{container}', 'cancel_url': list_path,
                 'submit_url': f'{list_path}{instance.pk}/'},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        self.action = 'list'
        request._request.path = self._inline_list_path()
        return self.list(request, *args, **kwargs)

    # ------------------------------------------------------------------ #
    # GUI-only actions — carry htmx_target + cancel_url for the template  #
    # ------------------------------------------------------------------ #

    def create_form(self, request, *args, **kwargs):
        serializer = self.get_serializer()
        container  = self._inline_container_id()
        list_path  = self._inline_list_path()
        return DRFResponse({
            'serializer':  serializer,
            'action':      'create',
            'htmx_target': f'#{container}',
            'cancel_url':  list_path,
            'submit_url':  list_path,
        })

    def update_form(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = self.get_serializer(instance)
        container  = self._inline_container_id()
        list_path  = self._inline_list_path()
        return DRFResponse({
            'serializer':  serializer,
            'instance':    serializer.data,
            'action':      'update',
            'htmx_target': f'#{container}',
            'cancel_url':  list_path,
            'submit_url':  f'{list_path}{instance.pk}/',
        })

    def _child_model(self):
        return self.queryset.model

    def get_parent_object(self):
        model = self._child_model()
        for f in model._meta.get_fields():
            if not hasattr(f, 'related_model') or not f.related_model:
                continue
            kwarg = f'{f.related_model._meta.model_name}_pk'
            if kwarg in self.kwargs:
                return get_object_or_404(f.related_model, pk=self.kwargs[kwarg])
        raise ImproperlyConfigured(
            f"{self.__class__.__name__}: cannot find parent object from URL kwargs. "
            f"Expected a kwarg named '{{parent_model_name}}_pk'. "
            f"Set parent_field explicitly if needed."
        )

    def _resolve_parent_field(self, parent_obj):
        if self.parent_field:
            return self.parent_field
        model = self._child_model()
        parent_model = type(parent_obj)
        for f in model._meta.get_fields():
            if hasattr(f, 'related_model') and f.related_model == parent_model:
                return f.name
        raise ImproperlyConfigured(
            f"{self.__class__.__name__}: cannot auto-detect FK from "
            f"{model.__name__} to {parent_model.__name__}. Set parent_field explicitly."
        )

    def get_queryset(self):
        parent = self.get_parent_object()
        field = self._resolve_parent_field(parent)
        return super().get_queryset().filter(**{field: parent})

    def perform_create(self, serializer):
        parent = self.get_parent_object()
        field = self._resolve_parent_field(parent)
        serializer.save(**{field: parent})
