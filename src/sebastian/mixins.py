from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework import renderers as drf_renderers
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import CreateModelMixin, UpdateModelMixin
from rest_framework.response import Response as DRFResponse

from .app_settings import hide_unauthorized_actions, pack_uses_htmx, confirm_deletions
from .config import _check_permission
from .renderers import SebastianHTMLRenderer


# ====================================================================== #
# Shared infrastructure                                                    #
# ====================================================================== #

class _SebastianBaseMixin:
    """
    Common infrastructure for all Sebastian GUI mixins.

    Provides: renderer negotiation, request lifecycle hooks,
    sebastian metadata helpers, confirmation flow, and action introspection.
    Subclasses add the specific HTTP verb handlers.
    """

    renderer_classes = [drf_renderers.JSONRenderer, SebastianHTMLRenderer]

    # Per-view template overrides (Django CBV style).
    # Set on the viewset/view class to use a custom template instead of the
    # pack default. The custom template can freely extend the pack template:
    #   class MyViewSet(GUIMixin, ...):
    #       form_template = 'myapp/my_form.html'
    #   {# myapp/my_form.html #}
    #   {% extends "sebastian/htmx/form.html" %}
    form_template:      str | None = None
    detail_template:    str | None = None
    list_template:      str | None = None
    template_namespace: str | None = None

    _STANDARD_ACTIONS = frozenset([
        'list', 'create', 'retrieve', 'update', 'partial_update', 'destroy',
        'create_form', 'update_form', 'confirm',
    ])

    # ------------------------------------------------------------------ #
    # Request lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def get_view_name(self):
        label = ''
        if hasattr(self, 'Sebastian'):
            label = getattr(self.Sebastian, 'label')
        return label or super().get_view_name()

    def get_renderers(self):
        # For API routes (no sebastian_gui flag), never render HTML — always JSON.
        # The flag is set on the Django request by GUIRouter._wrap() before dispatch,
        # transferred to the DRF request in initialize_request() below.
        if not getattr(self.request, 'sebastian_gui', False):
            return [drf_renderers.JSONRenderer()]
        return super().get_renderers()

    def initialize_request(self, request, *args, **kwargs):
        drf_request = super().initialize_request(request, *args, **kwargs)
        # Transfer flag set by GUIRouter's URL kwargs wrapper (django request → drf request)
        if getattr(request, 'sebastian_gui', False):
            drf_request.sebastian_gui = True
        return drf_request

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

    def can_create(self):
        """Returns True if the current user is allowed to create a new instance.

        Looks for a MenuItem with action='new' in Sebastian.menu; if one exists,
        evaluates its permission. Falls back to True when no menu or no 'new' item
        is configured (i.e. creation is unrestricted by default).
        """
        from .config import _check_permission
        sebastian = getattr(self.__class__, 'Sebastian', None)
        menu = getattr(sebastian, 'menu', None)
        if menu is None:
            return True
        for item in getattr(menu, 'items', []):
            if getattr(item, 'action', None) == 'new':
                return bool(_check_permission(item.permission, self.request, None))
        return True

    def can_update(self):
        """Returns True if the current user can update the current instance.

        Default: checks permission_classes via has_object_permission when an instance
        is available (_sebastian_obj set by retrieve). Returns True in list context
        (no object available — ownership is checked at form load time).
        Override for custom logic (e.g. WorkflowViewSetMixin checks wfm ownership).
        """
        obj = getattr(self, '_sebastian_obj', None)
        if obj is None:
            return True
        for perm in self.get_permissions():
            if not perm.has_object_permission(self.request, self, obj):
                return False
        return True

    def can_delete(self):
        """Returns True if the current user can delete the current instance.

        Default: same logic as can_update — checks permission_classes.
        Override for custom logic.
        """
        obj = getattr(self, '_sebastian_obj', None)
        if obj is None:
            return True
        for perm in self.get_permissions():
            if not perm.has_object_permission(self.request, self, obj):
                return False
        return True

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

    # ------------------------------------------------------------------ #
    # Unified confirmation handler                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_confirmation(conf, action_name='', instance=None):
        """
        Resolve a confirmation config dict into normalized fields.

        conf — dict with keys: prompt, serializer, icon, style, confirm (bool shortcut)
        Returns a dict with: prompt, icon, style, serializer_class
        or None if no confirmation is needed (confirm=False or empty config).
        """
        if not conf:
            return None
        confirm_flag = conf.get('confirm')
        if confirm_flag is False:
            return None
        prompt = conf.get('prompt', '')
        if not prompt and confirm_flag is True:
            prompt = 'Eseguire $ACTION su $OBJECT?' if action_name else 'Confermare?'
        # Substitute $OBJECT / $ACTION
        if instance is not None:
            prompt = prompt.replace('$OBJECT', str(instance))
        if action_name:
            prompt = prompt.replace('$ACTION', action_name)
        return {
            'prompt':           prompt,
            'icon':             conf.get('icon', ''),
            'style':            conf.get('style', 'primary'),
            'serializer_class': conf.get('serializer'),
        }

    def confirm(self, request, *args, **kwargs):
        """
        Unified GET/POST handler for all confirmation flows:
        - DELETE (via /{pk}/delete/)
        - @action with confirmation config (via /{pk}/{action}/confirm/ for GET,
          /{pk}/{action}/ for POST)

        URL kwargs:
            _confirm_type  = 'delete' | 'action'
            _confirm_action = action name (for type='action')
        """
        confirm_type   = self.kwargs.get('_confirm_type', 'delete')
        action_name    = self.kwargs.get('_confirm_action', '')
        instance       = self.get_object()
        instance_label = str(instance)

        if confirm_type == 'delete':
            sebastian  = getattr(self.__class__, 'Sebastian', None)
            delete_cfg = getattr(sebastian, 'delete_action', None)
            if delete_cfg is not None:
                raw_conf = delete_cfg.get('confirmation', {})
            elif confirm_deletions():
                raw_conf = {'prompt': 'Eliminare $OBJECT?', 'icon': 'trash', 'style': 'danger'}
            else:
                raw_conf = {}
            resolved = self._resolve_confirmation(raw_conf, '', instance) if raw_conf else None

            if request.method == 'POST':
                with transaction.atomic():
                    self.perform_destroy(instance)
                return self._do_delete_redirect(request)

            # GET: show confirmation page
            serializer = self.get_serializer(instance)
            cancel_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
            return DRFResponse({
                'action':             'confirm',
                'confirm_prompt':     resolved['prompt'] if resolved else '',
                'confirm_icon':       resolved['icon']   if resolved else 'trash',
                'confirm_style':      resolved['style']  if resolved else 'danger',
                'confirm_serializer': None,
                'form_errors':        {},
                'action_url':         request.path,
                'cancel_url':         cancel_url,
                'instance':           serializer.data,
            })

        # confirm_type == 'action'
        method_fn   = getattr(self.__class__, action_name, None)
        gui_config  = getattr(method_fn, 'gui_config', {})
        conf        = gui_config.get('confirmation', {})
        ConfSerializer = conf.get('serializer')
        action_label   = gui_config.get('label', action_name.replace('_', ' ').title())
        resolved       = self._resolve_confirmation(conf, action_label, instance)

        # POST target = strip /confirm/ suffix → action URL
        action_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        cancel_url = action_url.rstrip('/').rsplit('/', 1)[0] + '/'

        def _confirm_response(serializer_instance, status=200):
            resp = DRFResponse({
                'action':             'confirm',
                'confirm_prompt':     resolved['prompt'] if resolved else '',
                'confirm_icon':       resolved['icon']   if resolved else '',
                'confirm_style':      resolved['style']  if resolved else 'primary',
                'confirm_serializer': serializer_instance,
                'form_errors':        {},
                'action_url':         action_url,
                'cancel_url':         cancel_url,
                'instance':           self.get_serializer(instance).data,
                'htmx_target':        '#sebastian-modal',
            }, status=status)
            return resp

        if request.method == 'GET':
            get_fn       = getattr(self, f'{action_name}_get', None)
            initial_data = get_fn(instance) if get_fn else {}
            serializer_instance = ConfSerializer(initial_data) if ConfSerializer else None
            return _confirm_response(serializer_instance)

        # POST — validate confirmation serializer if present
        if ConfSerializer and getattr(request, 'sebastian_gui', False):
            serializer_instance = ConfSerializer(
                data=request.data,
                context={**self.get_serializer_context(), 'confirmation_instance': instance},
            )
            if not serializer_instance.is_valid():
                resp = _confirm_response(serializer_instance, status=400)
                resp['X-Sebastian-Form-Error'] = 'true'
                return resp
        else:
            serializer_instance = None

        valid_fn = getattr(self, f'{action_name}_valid', None)
        if valid_fn is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} must define {action_name}_valid() "
                f"for confirmation actions."
            )
        result = valid_fn(instance, serializer_instance)
        if isinstance(result, DRFResponse):
            return result
        return DRFResponse(self.get_serializer(instance).data)

    def _do_delete_redirect(self, request):
        """Return the appropriate redirect after a successful delete."""
        path = request.path.rstrip('/')
        if getattr(self.__class__, '_sebastian_is_nested', False):
            redirect_url = path.rsplit('/', 3)[0] + '/'
        else:
            redirect_url = path.rsplit('/', 2)[0] + '/'
        if request.META.get('HTTP_HX_REQUEST'):
            resp = DRFResponse({}, status=200)
            resp['HX-Redirect'] = redirect_url
            return resp
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(redirect_url)

    def _post_confirmation_action(self, action_name, instance=None):
        """
        Handle the POST side of a confirmation action.

        Validates the confirmation serializer (if declared in gui_config['confirmation'])
        for GUI requests, then calls {action_name}_valid(instance, serializer).
        On validation failure in GUI context, returns a confirm-style 400 response that
        re-renders the modal/page with field errors.

        Use this from your action method's body (POST path only):
            def my_action(self, request, *args, **kwargs):
                return self._post_confirmation_action('my_action')
        """
        if instance is None:
            instance = self.get_object()
        method_fn   = getattr(self.__class__, action_name, None)
        gui_config  = getattr(method_fn, 'gui_config', {})
        conf        = gui_config.get('confirmation', {})
        ConfSerializer = conf.get('serializer')
        valid_fn    = getattr(self, f'{action_name}_valid', None)
        if valid_fn is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} must define {action_name}_valid() "
                f"for confirmation actions."
            )
        if ConfSerializer and getattr(self.request, 'sebastian_gui', False):
            serializer_instance = ConfSerializer(
                data=self.request.data,
                context={**self.get_serializer_context(), 'confirmation_instance': instance},
            )
            if not serializer_instance.is_valid():
                action_label = gui_config.get('label', action_name.replace('_', ' ').title())
                resolved     = self._resolve_confirmation(conf, action_label, instance)
                cancel_url   = self.request.path.rstrip('/').rsplit('/', 1)[0] + '/'
                resp = DRFResponse({
                    'action':             'confirm',
                    'confirm_prompt':     resolved['prompt'] if resolved else '',
                    'confirm_icon':       resolved['icon']   if resolved else '',
                    'confirm_style':      resolved['style']  if resolved else 'primary',
                    'confirm_serializer': serializer_instance,
                    'form_errors':        {},
                    'action_url':         self.request.path,
                    'cancel_url':         cancel_url,
                    'instance':           self.get_serializer(instance).data,
                    'htmx_target':        '#sebastian-modal',
                }, status=400)
                resp['X-Sebastian-Form-Error'] = 'true'
                return resp
        else:
            serializer_instance = None
        result = valid_fn(instance, serializer_instance)
        if isinstance(result, DRFResponse):
            return result
        return DRFResponse(self.get_serializer(instance).data)

    # ------------------------------------------------------------------ #
    # Helper methods                                                      #
    # ------------------------------------------------------------------ #

    def download_action(self, field_name, request, pk=None, **kwargs):
        """Called by actions which download file fields"""
        instance = self.get_object()
        field = getattr(instance, field_name)
        filename = field.name.split('/')[-1]
        return FileResponse(field.open('rb'), as_attachment=True, filename=filename)

    def preview_action(self, field_name, request, pk=None, **kwargs):
        """Serve a file field inline so the browser opens it in its viewer (e.g. PDF preview)."""
        instance = self.get_object()
        field = getattr(instance, field_name)
        filename = field.name.split('/')[-1]
        return FileResponse(field.open('rb'), as_attachment=False, filename=filename)

    def standard_typeahead(self, filter, order_by=None, get_description=str):
        """Helper for @typeahead actions. Returns Response([{value, label}, ...])."""
        qs = self.get_queryset()
        if isinstance(filter, dict):
            qs = qs.filter(**filter)
        else:
            qs = qs.filter(filter)
        if order_by:
            qs = qs.order_by(*[f.strip() for f in order_by.split(',')])
        action_fn = getattr(self.__class__, getattr(self, 'action', ''), None)
        max_results = getattr(action_fn, 'max_results', 100)
        qs = qs[:max_results]
        items = [{'value': obj.pk, 'label': get_description(obj)} for obj in qs]
        return DRFResponse(items)


# ====================================================================== #
# ViewSet mixins                                                           #
# ====================================================================== #

class GUIMixin(_SebastianBaseMixin):
    """
    ViewSet mixin that enables Sebastian GUI generation.

    Adds SebastianHTMLRenderer alongside JSONRenderer so the same ViewSet
    serves JSON (Accept: application/json or /api/ routes) and HTML
    (Accept: text/html or /gui/ routes with format='html' URL kwarg).

    Sets request.sebastian_gui = True when the selected renderer is HTML,
    available for use in custom hooks and debug tooling.

    GUI-specific actions provided:
        create_form(request)         — empty form for a new instance
        update_form(request, pk)     — pre-filled form for an existing instance
    """

    # ------------------------------------------------------------------ #
    # Ordering                                                            #
    # ------------------------------------------------------------------ #

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        sebastian = getattr(self.__class__, 'Sebastian', None)
        ordering_decl = getattr(sebastian, 'ordering', None)
        if not ordering_decl:
            return queryset
        allowed_values = {f for f, _ in ordering_decl}  # includes sign (e.g. '-created_at')
        max_n = getattr(sebastian, 'max_ordering_fields', 3)
        params = self.request.query_params
        # HTMX pack sends ?ordering=f1,-f2; plain pack sends ?ordering_1=f1&ordering_2=-f2
        ordering_param = params.get('ordering', '')
        if ordering_param:
            raw = [f.strip() for f in ordering_param.split(',') if f.strip()]
        else:
            raw = []
            for i in range(1, max_n + 1):
                val = params.get(f'ordering_{i}', '')
                if val:
                    raw.append(val)
        valid = [f for f in raw if f in allowed_values][:max_n]
        if valid:
            queryset = queryset.order_by(*valid)
        elif getattr(self.request, 'sebastian_gui', False):
            # In GUI mode the ordering widget owns all sorting.  When nothing is
            # selected (valid is empty) override the model's Meta.ordering so the
            # list matches the widget's empty state rather than a hidden default.
            queryset = queryset.order_by()
        return queryset

    # ------------------------------------------------------------------ #
    # Create / update — redirect to detail on success                     #
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return super().create(request, *args, **kwargs)
        if not self.can_create():
            raise PermissionDenied()
        data = request.data.copy()
        for key in [k for k, v in list(data.items()) if v == '' and k not in request.FILES]:
            data.pop(key)
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'instance': {k: v for k, v in request.data.items()},
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content',
                 'form_errors': serializer.errors},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except Exception as exc:
            import traceback, logging
            logging.getLogger(__name__).error('perform_create failed: %s', traceback.format_exc())
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(exc, DRFValidationError):
                raise
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'instance': {k: v for k, v in request.data.items()},
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content',
                 'form_errors': {'non_field_errors': [str(exc)]}},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        headers = self.get_success_headers(serializer.data)
        lookup_value = serializer.data.get(self.lookup_field, serializer.data.get('id'))
        resp = DRFResponse(serializer.data, status=200, headers=headers)
        resp['HX-Redirect'] = f'{request.path}{lookup_value}/'
        return resp

    def update(self, request, *args, **kwargs):
        if not getattr(request, 'sebastian_gui', False):
            return super().update(request, *args, **kwargs)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data
        if partial and not pack_uses_htmx():
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
        try:
            with transaction.atomic():
                self.perform_update(serializer)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(exc, DRFValidationError):
                raise
            merged = {**instance_data, **{k: v for k, v in data.items()}}
            resp = DRFResponse(
                {'serializer': serializer, 'instance': merged, 'action': 'update',
                 'submit_url': request.path, 'cancel_url': request.path,
                 'htmx_target': '#sebastian-content',
                 'form_errors': {'non_field_errors': ['Errore durante il salvataggio. Verificare i dati inseriti.']}},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        is_htmx = bool(request.META.get('HTTP_HX_REQUEST'))
        lookup_val = getattr(instance, self.lookup_field, None)
        if lookup_val is not None:
            # HTMX posts to detail URL /{prefix}/{old}/; plain posts to /{prefix}/{old}/edit/
            segments_to_strip = 1 if is_htmx else 2
            list_url = request.path.rstrip('/').rsplit('/', segments_to_strip)[0] + '/'
            detail_url = f'{list_url}{lookup_val}/'
        else:
            detail_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        if is_htmx:
            resp = DRFResponse(serializer.data, status=200)
            resp['HX-Redirect'] = detail_url
            return resp
        from django.http import HttpResponseRedirect
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
        if not self.can_create():
            raise PermissionDenied()
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
        # Non-HTMX packs POST to /edit/ (mapped → partial_update); HTMX packs
        # use hx-patch to the detail URL regardless of how the form was loaded.
        if not pack_uses_htmx():
            submit_url = request.path
        else:
            submit_url = detail_url
        return DRFResponse({
            'serializer': serializer, 'instance': serializer.data, 'action': 'update',
            'submit_url': submit_url, 'cancel_url': detail_url,
            'htmx_target': '#sebastian-content',
        })

    # ------------------------------------------------------------------ #
    # Retrieve                                                            #
    # ------------------------------------------------------------------ #

    def retrieve(self, request, *args, **kwargs):
        self._sebastian_obj = self.get_object()
        serializer = self.get_serializer(self._sebastian_obj)
        if getattr(request, 'sebastian_gui', False):
            return DRFResponse(serializer.data)
        # API path: append inline data for each NestedGUIMixin declared in Sebastian.inlines
        data = dict(serializer.data)
        sebastian = getattr(self.__class__, 'Sebastian', None)
        for inline_cls in getattr(sebastian, 'inlines', []):
            if not getattr(inline_cls, 'inline_in_api', True):
                continue
            mp = getattr(inline_cls, 'mountpoint', '')
            if not mp:
                continue
            child_model = inline_cls.queryset.model
            parent_model = type(self._sebastian_obj)
            for f in child_model._meta.get_fields():
                if hasattr(f, 'related_model') and f.related_model == parent_model:
                    qs = child_model._default_manager.filter(**{f.name: self._sebastian_obj})
                    ctx = self.get_serializer_context()
                    data[mp] = inline_cls.serializer_class(qs, many=True, context=ctx).data
                    break
        return DRFResponse(data)


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
    inline_in_api = True # Rendered inline this viewset in parent serialized data

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
        container = self._inline_container_id()
        list_path = self._inline_list_path()
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'htmx_target': f'#{container}', 'cancel_url': list_path,
                 'submit_url': list_path},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(exc, DRFValidationError):
                raise
            resp = DRFResponse(
                {'serializer': serializer, 'action': 'create',
                 'htmx_target': f'#{container}', 'cancel_url': list_path,
                 'submit_url': list_path,
                 'form_errors': {'non_field_errors': ['Errore durante il salvataggio. Verificare i dati inseriti.']}},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
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
        is_plain     = not pack_uses_htmx()
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
        try:
            with transaction.atomic():
                self.perform_update(serializer)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(exc, DRFValidationError):
                raise
            merged = {**instance_data, **{k: v for k, v in data.items()}}
            resp = DRFResponse(
                {'serializer': serializer, 'instance': merged, 'action': 'update',
                 'htmx_target': f'#{container}', 'cancel_url': cancel_url,
                 'submit_url': submit_url,
                 'form_errors': {'non_field_errors': ['Errore durante il salvataggio. Verificare i dati inseriti.']}},
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp
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
        if not pack_uses_htmx():
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
            model_name = f.related_model._meta.model_name
            kwarg = next(
                (k for k in self.kwargs if k.startswith(f'{model_name}_')),
                None,
            )
            if kwarg is None:
                continue
            field_name = kwarg[len(model_name) + 1:]
            return get_object_or_404(f.related_model, **{field_name: self.kwargs[kwarg]})
        raise ImproperlyConfigured(
            f"{self.__class__.__name__}: cannot find parent object from URL kwargs. "
            f"Expected a kwarg named '{{parent_model_name}}_<lookup_field>'. "
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

    # ------------------------------------------------------------------ #
    # Edit permissions — inherit from parent's workflow state              #
    # ------------------------------------------------------------------ #

    def _parent_is_editable(self) -> bool:
        """Return True if the parent object permits editing this nested resource.

        For workflow-managed parents: requires that the user is the owner (or
        admin) and that the parent is not suspended.

        Additionally, if this nested viewset declares ``Sebastian.edit_permission``
        (a callable ``(request, parent_obj) -> bool``), that permission is checked
        after the ownership check.  This lets per-phase rules be expressed:

            class RequisitoViewSet(NestedGUIMixin, ...):
                class Sebastian:
                    edit_permission = perm_fase('richiesta')

        The result is cached on the viewset instance so that repeated calls
        (one per row in a list) do not issue extra DB queries.
        """
        if hasattr(self, '_parent_is_editable_cache'):
            return self._parent_is_editable_cache

        try:
            parent = self.get_parent_object()
        except Exception:
            self._parent_is_editable_cache = True
            return True

        user = self.request.user

        # Duck-type check for workflow-managed parents.
        if hasattr(parent, 'wfm_state') and hasattr(parent, 'wfm'):
            state = parent.wfm_state
            if state:
                if state.suspended:
                    self._parent_is_editable_cache = False
                    return False
                if not parent.wfm.is_owner(user) and not parent.wfm.can_admin(user):
                    self._parent_is_editable_cache = False
                    return False

        # Optional per-viewset phase/role restriction.
        from .config import _check_permission
        sebastian = getattr(self.__class__, 'Sebastian', None)
        perm = getattr(sebastian, 'edit_permission', None)
        if perm is not None:
            result = bool(_check_permission(perm, self.request, parent))
            self._parent_is_editable_cache = result
            return result

        self._parent_is_editable_cache = True
        return True

    def can_create(self):
        return self._parent_is_editable()

    def can_update(self):
        if not self._parent_is_editable():
            return False
        return super().can_update()

    def can_delete(self):
        if not self._parent_is_editable():
            return False
        return super().can_delete()


# ====================================================================== #
# Singleton view mixin                                                     #
# ====================================================================== #

class SingletonGUIMixin(_SebastianBaseMixin):
    """
    Mixin for GenericAPIView that exposes a singleton resource via the Sebastian GUI.

    Suitable for resources where there is at most one instance per user/context
    (e.g. UserConfig), where the standard list/create/destroy semantics don't apply.

    Register two URL paths in urls.py:
        path('userconfig/',       UserConfigView.as_view(),                  name='userconfig'),
        path('userconfig/edit/',  UserConfigView.as_view(edit_mode=True),    name='userconfig-edit'),

    GET  <url>/       → detail (read-only, with Edit button)
    GET  <url>/edit/  → edit form (Cancel → detail, Save → POST to detail)
    POST/PATCH/PUT <url>/  → partial upsert; redirects to detail on success

    The subclass must implement get_object() using get_or_create (or equivalent).
    Unlike GUIMixin, this mixin sets sebastian_gui = True directly in dispatch()
    since it is not managed by GUIRouter.
    """

    edit_mode: bool = False

    def dispatch(self, request, *args, **kwargs):
        # Set the flag directly — this view is not wrapped by GUIRouter._wrap()
        request.sebastian_gui = True
        # Force HTML content negotiation (GUIRouter does this via URL kwargs;
        # we replicate it here since SingletonGUIMixin is registered manually)
        return super().dispatch(request, *args, **{**kwargs, 'format': 'html'})

    def _detail_url(self, request):
        """Canonical detail URL (strips /edit/ suffix if present)."""
        path = request.path.rstrip('/')
        if path.endswith('/edit'):
            path = path[: -len('/edit')]
        return path + '/'

    def _form_context(self, serializer, instance_data, detail_url):
        return {
            'serializer': serializer,
            'instance': instance_data,
            'action': 'update',
            'submit_url': detail_url,
            'cancel_url': detail_url,
            'htmx_target': '#sebastian-content',
        }

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        instance = self.get_object()
        if self.edit_mode:
            self.action = 'update_form'
            serializer = self.get_serializer(instance)
            return DRFResponse(self._form_context(serializer, serializer.data, self._detail_url(request)))
        self.action = 'retrieve'
        self._sebastian_obj = instance
        return DRFResponse(self.get_serializer(instance).data)

    def _upsert(self, request):
        self.action = 'update_form'
        detail_url = self._detail_url(request)
        instance = self.get_object()
        instance_data = self.get_serializer(instance).data

        data = request.data
        if not pack_uses_htmx():
            data = data.copy()
            for key in [k for k, v in list(data.items())
                        if v == '' and k not in request.FILES
                        and f'_clear_{k}' not in request.POST]:
                data.pop(key)

        serializer = self.get_serializer(instance, data=data, partial=True)
        if not serializer.is_valid():
            resp = DRFResponse(
                self._form_context(serializer, {**instance_data, **dict(data.items())}, detail_url),
                status=400,
            )
            resp['X-Sebastian-Form-Error'] = 'true'
            return resp

        try:
            with transaction.atomic():
                serializer.save()
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(exc, DRFValidationError):
                serializer._errors = exc.detail  # inject back so _form_context renders them
                resp = DRFResponse(
                    self._form_context(serializer, {**instance_data, **dict(data.items())}, detail_url),
                    status=400,
                )
                resp['X-Sebastian-Form-Error'] = 'true'
                return resp
            raise

        if request.META.get('HTTP_HX_REQUEST'):
            resp = DRFResponse(serializer.data, status=200)
            resp['HX-Redirect'] = detail_url
            return resp
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(detail_url)

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        return self._upsert(request)

    def patch(self, request, *args, **kwargs):  # noqa: ARG002
        return self._upsert(request)

    def put(self, request, *args, **kwargs):  # noqa: ARG002
        return self._upsert(request)
