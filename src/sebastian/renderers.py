from django.template.loader import render_to_string
from rest_framework.renderers import BaseRenderer
from . import app_settings


def _find_in_mro(view, attr):
    """Return the first value of `attr` defined explicitly in the MRO of view's class.

    Uses __dict__ lookup so that inherited None values (e.g. from _SebastianBaseMixin)
    do not shadow a non-None value defined by a later mixin such as WorkflowViewSetMixin.
    """
    for cls in type(view).__mro__:
        val = cls.__dict__.get(attr)
        if val is not None:
            return val
    return None


class SebastianHTMLRenderer(BaseRenderer):
    media_type = 'text/html'
    format = 'html'
    charset = 'utf-8'

    ACTION_TEMPLATE_SUFFIXES = {
        'list':           'list.html',
        'retrieve':       'detail.html',
        'create_form':    'form.html',
        'update_form':    'form.html',
        'confirm':        'confirm.html',
        'create':         'detail.html',
        'update':         'detail.html',
        'partial_update': 'detail.html',
        'history':        'history.html',
    }
    DEFAULT_TEMPLATE_SUFFIX = 'detail.html'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        view     = renderer_context.get('view')
        request  = renderer_context.get('request')
        response = renderer_context.get('response')

        is_confirm = (
            isinstance(data, dict) and data.get('action') == 'confirm'
            and 'confirm_prompt' in data
        )
        is_form_error = (
            response and response.status_code >= 400
            and isinstance(data, dict) and 'serializer' in data
            and not is_confirm
        )
        if response and response.status_code >= 400 and not is_form_error and not is_confirm:
            return self._render_error(data, response, request)

        pack      = app_settings.template_pack()
        skin_name = app_settings.skin()
        template_name = self._resolve_template(view, pack)
        if is_confirm:
            template_name = self._resolve_confirm_template(view, pack)
        elif is_form_error:
            template_name = (
                getattr(view, 'form_template', None) or f'sebastian/{pack}/form.html'
            )
        is_htmx = bool(request and request.META.get('HTTP_HX_REQUEST'))

        # Unpack DRF paginated response so templates always get a plain list
        if isinstance(data, dict) and 'results' in data:
            items      = data['results']
            pagination = {k: data[k] for k in ('count', 'next', 'previous') if k in data}
        else:
            items      = data
            pagination = None

        is_inline   = bool(view and getattr(view.__class__, '_sebastian_is_nested', False))
        if is_inline:
            mp          = getattr(view.__class__, 'mountpoint', 'inline')
            htmx_target = f'#inline-{mp}'
        else:
            htmx_target = '#sebastian-content'
        # Forms pass htmx_target/cancel_url in response data; pull them into context.
        if isinstance(data, dict) and 'htmx_target' in data:
            htmx_target = data['htmx_target']
        cancel_url = data.get('cancel_url', '') if isinstance(data, dict) else ''
        submit_url = data.get('submit_url', '') if isinstance(data, dict) else ''
        is_serializer_error = is_form_error or (
            is_confirm and response and response.status_code >= 400
            and isinstance(data, dict) and 'confirm_serializer' in data
            and data.get('confirm_serializer') is not None
        )
        if is_serializer_error:
            if 'serializer' in data:
                form_errors = data['serializer'].errors
            elif 'confirm_serializer' in data and data['confirm_serializer'] is not None:
                form_errors = data['confirm_serializer'].errors
            else:
                form_errors = {}
        else:
            form_errors = {}

        from django.urls import reverse, NoReverseMatch
        try:
            menu_url = reverse('sebastian-menu')
        except NoReverseMatch:
            menu_url = ''

        sebastian_config = getattr(view.__class__, 'Sebastian', None) if view else None
        action = getattr(view, 'action', None) if view else None
        context = {
            'data':               data,
            'items':              items,
            'display_fields':     self._get_display_fields(sebastian_config, items),
            'pagination':         pagination,
            'is_htmx':            is_htmx,
            'is_inline':          is_inline,
            'list_level':         2 if is_inline else 1,
            'htmx_target':        htmx_target,
            'cancel_url':         cancel_url,
            'submit_url':         submit_url,
            'object_url':         self._get_object_url(view, request),
            'instance':           getattr(view, '_sebastian_obj', None),
            'view':               view,
            'request':            request,
            'response':           response,
            'sebastian_config':   sebastian_config,
            'visible_groups':     self._get_visible_groups(sebastian_config, data, action),
            'field_labels':       self._get_field_labels(view),
            'filter_form':        self._get_filter_form(view, request),
            'ordering_config':    self._get_ordering_config(view, request),
            'field_config':       self._get_field_config(sebastian_config),
            'cascading_fields':   getattr(sebastian_config, 'cascading_fields', []) or [],
            'inlines':            self._get_inlines(view),
            'workflow_transitions': self._get_workflow_transitions(view),
            'form_errors':        form_errors,
            'pack_name':          pack,
            'pack_base':          f'sebastian/{pack}/base.html',
            'skin_name':          skin_name,
            'menu_url':           menu_url,
            'file_field_template': f'sebastian/{pack}/_file_field.html',
        }

        return render_to_string(template_name, context, request=request)

    def _render_error(self, data, response, request) -> str:
        pack = app_settings.template_pack()
        skin_name = app_settings.skin()
        alert_map = {400: 'warning', 403: 'danger', 404: 'warning'}
        alert_class = alert_map.get(response.status_code, 'danger')
        detail = ''
        if isinstance(data, dict):
            detail = data.get('detail', '') or data.get('message', '')
        if not detail:
            detail = f'Errore {response.status_code}'
        return render_to_string(f'sebastian/{pack}/error.html', {
            'error_detail':    str(detail),
            'alert_class':     alert_class,
            'pack_name':       pack,
            'pack_base':       f'sebastian/{pack}/base.html',
            'skin_name':       skin_name,
        }, request=request)

    def _resolve_template(self, view, pack: str = None) -> str:
        if pack is None:
            pack = app_settings.template_pack()
        if view is None:
            return f'sebastian/{pack}/{self.DEFAULT_TEMPLATE_SUFFIX}'
        # SebastianMenuView always renders with the menu fragment template
        from .views import SebastianMenuView
        if isinstance(view, SebastianMenuView):
            return f'sebastian/{pack}/menu.html'
        action = getattr(view, 'action', None)
        # 1. View-level template attributes (Django CBV style: form_template, detail_template, list_template)
        _VIEW_PROP = {
            'list':        'list_template',
            'retrieve':    'detail_template',
            'create_form': 'form_template',
            'update_form': 'form_template',
            'create':      'form_template',
            'update':      'form_template',
        }
        if view and action:
            prop = _VIEW_PROP.get(action)
            if prop:
                # MRO walk so WorkflowViewSetMixin.list_template is found before
                # the inherited None on _SebastianBaseMixin stops the search.
                override = _find_in_mro(view, prop)
                if override:
                    return override
        # 2. Sebastian.templates dict and legacy per-attribute override
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if sebastian and action:
            templates = getattr(sebastian, 'templates', {})
            _key_map = {'retrieve': 'detail', 'create_form': 'form', 'update_form': 'form'}
            key = _key_map.get(action, action)
            if key in templates:
                return templates[key]
            # Legacy: Sebastian.retrieve_template = '...'
            override = getattr(sebastian, f'{action}_template', None)
            if override:
                return override
        # 3. template_namespace declared on the viewset or a mixin (MRO walk).
        #    Builds the path as {namespace}/sebastian/{pack}/{suffix}, keeping the
        #    pack dynamic so a settings change propagates everywhere automatically.
        #    Falls back to sebastian/{pack}/{suffix} if the namespaced template does
        #    not exist, so a namespace only needs to define templates it customises.
        namespace = _find_in_mro(view, 'template_namespace') if view else None
        suffix = self.ACTION_TEMPLATE_SUFFIXES.get(action, self.DEFAULT_TEMPLATE_SUFFIX)
        if namespace:
            candidate = f'{namespace}/sebastian/{pack}/{suffix}'
            from django.template.loader import get_template
            from django.template.exceptions import TemplateDoesNotExist
            try:
                get_template(candidate)
                return candidate
            except TemplateDoesNotExist:
                pass
        return f'sebastian/{pack}/{suffix}'

    def _get_visible_groups(self, sebastian_config, data, action) -> list:
        """Return groups that should be rendered, filtering out fully-hidden ones.

        A FieldGroup is hidden when GUISerializerMixin removed all its fields
        because visible_permission returned False.  Detection strategy:
        - retrieve: check whether any field appears in the serialized data dict.
        - update_form / create_form: check whether any field is still present in
          serializer.fields (hidden fields are removed by get_fields()).
        Non-FieldGroup entries are always included.
        """
        from sebastian.config import FieldGroup
        all_groups = list(getattr(sebastian_config, 'groups', []) or []) if sebastian_config else []

        if action == 'retrieve' and isinstance(data, dict):
            return [
                g for g in all_groups
                if not isinstance(g, FieldGroup) or any(f in data for f in g.fields)
            ]

        if action in ('update_form', 'create_form') and isinstance(data, dict):
            serializer = data.get('serializer')
            if serializer is not None:
                serializer_fields = getattr(serializer, 'fields', {})
                return [
                    g for g in all_groups
                    if not isinstance(g, FieldGroup) or any(f in serializer_fields for f in g.fields)
                ]

        return all_groups

    def _get_display_fields(self, sebastian_config, items) -> list:
        explicit = getattr(sebastian_config, 'list_fields', None) if sebastian_config else None
        if explicit:
            return list(explicit)
        if not items:
            return []
        first = items[0] if isinstance(items, list) else {}
        return [
            k for k, v in first.items()
            if not k.endswith('__display')
            and not k.startswith('sebastian__')
            and not isinstance(v, (dict, list))
        ]

    def _get_field_labels(self, view) -> dict:
        if not view:
            return {}
        try:
            serializer = view.get_serializer()
            labels = {
                name: str(field.label) if field.label else name.replace('_', ' ').title()
                for name, field in serializer.fields.items()
            }
            for method_name in serializer._get_gui_field_names():
                if method_name not in labels:
                    method = getattr(type(serializer), method_name, None)
                    labels[method_name] = (
                        getattr(method, '_gui_label', None)
                        or method_name.replace('_', ' ').title()
                    )
            return labels
        except Exception:
            return {}

    def _get_filter_form(self, view, request):
        if not view or not request:
            return None
        try:
            from django_filters.rest_framework import DjangoFilterBackend
        except ImportError:
            return None
        for backend_class in getattr(view, 'filter_backends', []):
            try:
                if issubclass(backend_class, DjangoFilterBackend):
                    backend   = backend_class()
                    filterset = backend.get_filterset(request, view.get_queryset(), view)
                    return filterset.form if filterset else None
            except Exception:
                pass
        return None

    def _get_ordering_config(self, view, request):
        if not view or not request:
            return None
        sebastian = getattr(view.__class__, 'Sebastian', None)
        ordering_decl = getattr(sebastian, 'ordering', None)
        if not ordering_decl:
            return None
        max_n = getattr(sebastian, 'max_ordering_fields', 3)
        params = request.query_params
        ordering_param = params.get('ordering', '')
        if ordering_param:
            current = [f.strip() for f in ordering_param.split(',') if f.strip()]
        else:
            current = []
            for i in range(1, max_n + 1):
                val = params.get(f'ordering_{i}', '')
                if val:
                    current.append(val)
        slots = [current[i] if i < len(current) else '' for i in range(max_n)]
        return {
            'fields':         list(ordering_decl),
            'max_n':          max_n,
            'slots':          slots,
            'ordering_param': ','.join(current),
        }

    def _get_field_config(self, sebastian_config) -> dict:
        raw = getattr(sebastian_config, 'field_config', None) or {}
        result = {}
        for field_name, config in raw.items():
            entry = dict(config)
            if 'typeahead_url' in entry and 'typeahead_chars' not in entry:
                entry['typeahead_chars'] = self._resolve_typeahead_chars(entry['typeahead_url'])
            result[field_name] = entry
        return result

    def _resolve_typeahead_chars(self, url: str) -> int:
        if not url:
            return 2
        try:
            from django.urls import resolve
            match = resolve(url.split('?')[0])
            # DRF ViewSet.as_view() stores {'get': 'action_name', ...} in view.actions
            action_name = (getattr(match.func, 'actions', None) or {}).get('get', '')
            cls = getattr(match.func, 'cls', None)
            if cls and action_name:
                method = getattr(cls, action_name, None)
                if method is not None:
                    return getattr(method, 'typeahead_chars', 2)
        except Exception:
            pass
        return 2

    def _get_inlines(self, view) -> list:
        """Return a normalized list of {mountpoint, label} for each inline in Sebastian.inlines."""
        if not view:
            return []
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if not sebastian:
            return []
        result = []
        for spec in getattr(sebastian, 'inlines', []):
            inline_vs = spec[0] if isinstance(spec, (list, tuple)) else spec
            mountpoint = (
                getattr(inline_vs, 'mountpoint', None)
                or getattr(getattr(getattr(inline_vs, 'queryset', None), 'model', None),
                           '_meta', None) and
                   inline_vs.queryset.model._meta.verbose_name_plural.lower()
                or inline_vs.__name__.lower().replace('viewset', '')
            )
            label = getattr(getattr(inline_vs, 'Sebastian', None), 'label', None) or mountpoint.title()
            result.append({'mountpoint': mountpoint, 'label': label})
        return result

    def _resolve_confirm_template(self, view, pack: str) -> str:
        """Return the confirm template path, preferring a namespace-specific override.

        Checks ``{namespace}/sebastian/{pack}/confirm.html`` first; falls back to
        the default ``sebastian/{pack}/confirm.html``.
        """
        default = f'sebastian/{pack}/confirm.html'
        namespace = getattr(view, 'template_namespace', None) if view else None
        if not namespace:
            return default
        candidate = f'{namespace}/sebastian/{pack}/confirm.html'
        from django.template.loader import get_template
        from django.template import TemplateDoesNotExist
        try:
            get_template(candidate)
            return candidate
        except TemplateDoesNotExist:
            return default

    def _get_workflow_transitions(self, view):
        """Return WorkflowTransitions for the current instance, or None.

        Called only when the view exposes get_workflow_transitions() (i.e. when
        WorkflowViewSetMixin is in the MRO) and _sebastian_obj is set (i.e. in
        retrieve/detail context).
        """
        if not view:
            return None
        get_wt = getattr(view, 'get_workflow_transitions', None)
        if not callable(get_wt):
            return None
        obj = getattr(view, '_sebastian_obj', None)
        if obj is None:
            return None
        try:
            return get_wt(obj)
        except Exception:
            return None

    def _get_object_url(self, view, request) -> str:
        """Canonical GUI detail URL for the current object.

        For 'retrieve' this equals request.path. For other detail actions
        (history, change_state_form, …) we reverse basename-gui-detail so that
        templates use the correct base URL for inline loading and sub-resource links,
        regardless of which action URL is currently being served.

        GUIRouter does not pass ``basename`` to ``as_view()``, so ``view.basename``
        is None for GUI action URLs. We fall back to extracting the basename from
        ``request.resolver_match.url_name`` which follows the pattern
        ``{basename}-gui-{action}``.
        """
        if view is None or request is None:
            return getattr(request, 'path', '') if request else ''
        if getattr(view, 'action', None) == 'retrieve':
            return request.path
        basename = getattr(view, 'basename', None)
        if not basename:
            url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
            if url_name and '-gui-' in url_name:
                basename = url_name.split('-gui-')[0]
        pk = (getattr(view, 'kwargs', None) or {}).get('pk')
        if basename and pk:
            from django.urls import reverse, NoReverseMatch
            try:
                return reverse(f'{basename}-gui-detail', kwargs={'pk': pk})
            except NoReverseMatch:
                pass
        return request.path
