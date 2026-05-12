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
        'create_form', 'update_form', 'delete_confirm', 'action_confirm_page',
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
        # Plain pack: convert HX-Redirect into a real HTTP redirect (no HTMX to follow the header).
        if (
            isinstance(response, DRFResponse)
            and getattr(request, 'sebastian_gui', False)
            and not request.META.get('HTTP_HX_REQUEST')
            and 'HX-Redirect' in response
        ):
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(response['HX-Redirect'])
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
                 'instance': dict(request.data),
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
        from . import app_settings
        data = request.data
        if partial and app_settings.template_pack() == 'plain':
            # Plain form: browser sends '' for unselected file inputs; strip them so
            # partial=True can ignore unchanged file fields instead of failing validation.
            # Exception: if a _clear_{field} checkbox was checked, keep the empty string
            # so NullableFileField can convert it to None (explicit clear).
            data = data.copy()
            for key in [k for k, v in list(data.items())
                        if v == '' and k not in request.FILES
                        and f'_clear_{k}' not in request.POST]:
                data.pop(key)
        instance_data = self.get_serializer(instance).data
        serializer = self.get_serializer(instance, data=data, partial=partial)
        if not serializer.is_valid():
            merged = {**instance_data, **{k: v for k, v in data.items()}}
            resp = DRFResponse(
                {'serializer': serializer, 'instance': merged, 'action': 'update',
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content'},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        if request.META.get('HTTP_HX_REQUEST'):
            resp = DRFResponse(serializer.data, status=200)
            resp['HX-Redirect'] = request.path
            return resp
        # Plain pack (no HTMX): POST to /edit/ — redirect to detail page
        from django.http import HttpResponseRedirect
        detail_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        return HttpResponseRedirect(detail_url)

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
        detail_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        # Plain pack POSTs to /edit/ (mapped → partial_update); all other packs
        # use hx-patch to the detail URL regardless of how the form was loaded.
        from . import app_settings
        if app_settings.template_pack() == 'plain':
            submit_url = request.path
        else:
            submit_url = detail_url
        return DRFResponse({
            'serializer': serializer, 'instance': serializer.data, 'action': 'update',
            'submit_url': submit_url, 'cancel_url': detail_url,
            'htmx_target': '#sebastian-content',
        })

    def delete_confirm(self, request, *args, **kwargs):
        """GET: confirmation page.  POST: perform delete, redirect to parent list."""
        instance = self.get_object()
        if request.method == 'POST':
            self.perform_destroy(instance)
            from django.http import HttpResponseRedirect
            path = request.path.rstrip('/')
            if getattr(self.__class__, '_sebastian_is_nested', False):
                # Nested: strip /delete/, /{pk}/, /{mountpoint}/ → parent detail URL
                redirect_url = path.rsplit('/', 3)[0] + '/'
            else:
                # Top-level: strip /delete/, /{pk}/ → list URL
                redirect_url = path.rsplit('/', 2)[0] + '/'
            return HttpResponseRedirect(redirect_url)
        # GET: render confirm page
        serializer = self.get_serializer(instance)
        cancel_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        return DRFResponse({
            'action': 'delete_confirm',
            'instance': serializer.data,
            'cancel_url': cancel_url,
        })

    def action_confirm_page(self, request, *args, **kwargs):
        """GET: server-side confirmation page for POST actions with a confirm text."""
        action_name = self.kwargs.get('_confirm_action', '')
        method      = getattr(self.__class__, action_name, None)
        confirm_text = getattr(method, 'gui_config', {}).get('confirm', '')
        instance    = self.get_object()
        serializer  = self.get_serializer(instance)
        # action_url = strip /confirm/ → the POST target
        action_url  = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        cancel_url  = action_url.rstrip('/').rsplit('/', 1)[0] + '/'
        return DRFResponse({
            'action':        'action_confirm_page',
            'confirm_text':  confirm_text,
            'action_url':    action_url,
            'cancel_url':    cancel_url,
            'instance':      serializer.data,
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

    def confirmation_action(self, action_name, *args, **kwargs):
        """
        Generic GET/POST handler for @actions with gui_config['confirmation_serializer'].

        GET  → {action_name}_get(instance) returns initial data dict → modal response.
        POST GUI → validates ConfirmSerializer → {action_name}_valid(instance, serializer).
        POST API → {action_name}_valid(instance, None).

        {action_name}_valid() may return a DRFResponse to signal an error, or None/omit
        a return to use the default (re-serialized instance detail response).
        """
        from django.core.exceptions import ImproperlyConfigured

        method_fn  = getattr(self.__class__, action_name, None)
        gui_config = getattr(method_fn, 'gui_config', {})
        ConfirmSerializer = gui_config.get('confirmation_serializer')
        if not ConfirmSerializer:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__}.{action_name}: "
                f"gui_config['confirmation_serializer'] is required for confirmation_action()."
            )

        valid_fn = getattr(self, f'{action_name}_valid', None)
        if valid_fn is None or not callable(valid_fn):
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} must define {action_name}_valid() "
                f"to use confirmation_action()."
            )

        action_label = gui_config.get('action_label', action_name.replace('_', ' ').title())
        instance   = self.get_object()
        parent_url = self.request.path.rstrip('/').rsplit('/', 1)[0] + '/'

        def _modal_response(serializer, instance_data, status=200):
            resp = DRFResponse({
                'serializer':   serializer,
                'instance':     instance_data,
                'action':       'confirm_action',
                'action_label': action_label,
                'submit_url':   self.request.path,
                'cancel_url':   parent_url,
                'htmx_target':  '#sebastian-modal',
            }, status=status)
            return resp

        if self.request.method == 'GET':
            get_fn       = getattr(self, f'{action_name}_get', None)
            initial_data = get_fn(instance) if get_fn else {}
            return _modal_response(ConfirmSerializer(initial_data), initial_data)

        # POST ─ GUI path: full serializer validation
        if getattr(self.request, 'sebastian_gui', False):
            serializer = ConfirmSerializer(
                data=self.request.data,
                context={**self.get_serializer_context(), 'confirmation_instance': instance},
            )
            if not serializer.is_valid():
                resp = _modal_response(serializer, self.request.data, status=400)
                resp['X-Sebastian-Form-Error'] = 'true'
                return resp
        else:
            serializer = None   # API callers skip GUI-only validation

        result = valid_fn(instance, serializer)
        if isinstance(result, DRFResponse):
            return result
        return DRFResponse(self.get_serializer(instance).data)

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
        if not request.META.get('HTTP_HX_REQUEST'):
            from django.http import HttpResponseRedirect
            list_path  = self._inline_list_path()
            parent_url = list_path.rstrip('/').rsplit('/', 1)[0] + '/'
            return HttpResponseRedirect(parent_url)
        self.action = 'list'
        request._request.path = self._inline_list_path()
        return self.list(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return UpdateModelMixin.update(self, request, *args, **kwargs)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        from . import app_settings
        is_plain     = app_settings.template_pack() == 'plain'
        data = request.data
        if partial and is_plain:
            data = data.copy()
            for key in [k for k, v in list(data.items())
                        if v == '' and k not in request.FILES
                        and f'_clear_{k}' not in request.POST]:
                data.pop(key)
        container    = self._inline_container_id()
        list_path    = self._inline_list_path()
        parent_url   = list_path.rstrip('/').rsplit('/', 1)[0] + '/'
        instance_data = self.get_serializer(instance).data
        detail_url   = f'{list_path}{instance.pk}/'
        submit_url   = request.path if is_plain else detail_url
        cancel_url   = parent_url if is_plain else list_path
        serializer = self.get_serializer(instance, data=data, partial=partial)
        if not serializer.is_valid():
            merged = {**instance_data, **{k: v for k, v in data.items()}}
            resp = DRFResponse(
                {'serializer': serializer, 'instance': merged, 'action': 'update',
                 'htmx_target': f'#{container}', 'cancel_url': cancel_url,
                 'submit_url': submit_url},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        if not request.META.get('HTTP_HX_REQUEST'):
            from django.http import HttpResponseRedirect
            list_path  = self._inline_list_path()
            parent_url = list_path.rstrip('/').rsplit('/', 1)[0] + '/'
            return HttpResponseRedirect(parent_url)
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
        parent_url = list_path.rstrip('/').rsplit('/', 1)[0] + '/'
        detail_url = f'{list_path}{instance.pk}/'
        from . import app_settings
        if app_settings.template_pack() == 'plain':
            submit_url = request.path  # /edit/ URL → POST maps to partial_update
            cancel_url = parent_url
        else:
            submit_url = detail_url
            cancel_url = list_path
        return DRFResponse({
            'serializer':  serializer,
            'instance':    serializer.data,
            'action':      'update',
            'htmx_target': f'#{container}',
            'cancel_url':  cancel_url,
            'submit_url':  submit_url,
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
