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

        context = {
            'data':             data,
            'items':            items,
            'pagination':       pagination,
            'is_htmx':          is_htmx,
            'view':             view,
            'request':          request,
            'response':         response,
            'sebastian_config': getattr(view.__class__, 'Sebastian', None) if view else None,
            'field_labels':     self._get_field_labels(view),
            'filter_form':      self._get_filter_form(view, request),
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
                    backend  = backend_class()
                    filterset = backend.get_filterset(request, view.get_queryset(), view)
                    return filterset.form if filterset else None
            except Exception:
                pass
        return None
