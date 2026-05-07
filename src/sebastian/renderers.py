from django.template.loader import render_to_string
from rest_framework.renderers import BaseRenderer


class SebastianHTMLRenderer(BaseRenderer):
    media_type = 'text/html'
    format = 'html'
    charset = 'utf-8'

    ACTION_TEMPLATES = {
        'list':        'sebastian/list.html',
        'retrieve':    'sebastian/detail.html',
        'create_form': 'sebastian/form.html',
        'update_form': 'sebastian/form.html',
    }
    DEFAULT_TEMPLATE = 'sebastian/detail.html'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        view     = renderer_context.get('view')
        request  = renderer_context.get('request')
        response = renderer_context.get('response')

        template_name = self._resolve_template(view)
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

        context = {
            'data':             data,
            'items':            items,
            'pagination':       pagination,
            'is_htmx':          is_htmx,
            'is_inline':        is_inline,
            'list_level':       2 if is_inline else 1,
            'htmx_target':      htmx_target,
            'cancel_url':       cancel_url,
            'submit_url':       submit_url,
            'view':             view,
            'request':          request,
            'response':         response,
            'sebastian_config': getattr(view.__class__, 'Sebastian', None) if view else None,
            'field_labels':     self._get_field_labels(view),
            'filter_form':      self._get_filter_form(view, request),
            'inlines':          self._get_inlines(view),
        }

        return render_to_string(template_name, context, request=request)

    def _resolve_template(self, view) -> str:
        if view is None:
            return self.DEFAULT_TEMPLATE
        action = getattr(view, 'action', None)
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if sebastian and action:
            override = getattr(sebastian, f'{action}_template', None)
            if override:
                return override
        return self.ACTION_TEMPLATES.get(action, self.DEFAULT_TEMPLATE)

    def _get_field_labels(self, view) -> dict:
        if not view:
            return {}
        try:
            serializer = view.get_serializer()
            return {
                name: str(field.label) if field.label else name.replace('_', ' ').title()
                for name, field in serializer.fields.items()
            }
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
