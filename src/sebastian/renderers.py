from django.template.loader import render_to_string
from rest_framework.renderers import BaseRenderer


class SebastianHTMLRenderer(BaseRenderer):
    media_type = 'text/html'
    format = 'html'
    charset = 'utf-8'

    # Maps ViewSet action names to default templates
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

        context = {
            'data':             data,
            'view':             view,
            'request':          request,
            'response':         response,
            'sebastian_config': getattr(view.__class__, 'Sebastian', None) if view else None,
        }

        return render_to_string(template_name, context, request=request)

    def _resolve_template(self, view) -> str:
        if view is None:
            return self.DEFAULT_TEMPLATE

        action = getattr(view, 'action', None)

        # Allow per-action template override in ViewSet.Sebastian
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if sebastian and action:
            override = getattr(sebastian, f'{action}_template', None)
            if override:
                return override

        return self.ACTION_TEMPLATES.get(action, self.DEFAULT_TEMPLATE)
