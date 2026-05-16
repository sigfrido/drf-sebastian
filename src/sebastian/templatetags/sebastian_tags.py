from django import template
from django.utils.safestring import mark_safe
from rest_framework import serializers as drf_serializers

register = template.Library()

_ICON_RENDERERS = {
    'bi': lambda n, cls: f'<i class="bi bi-{n}{" " + cls if cls else ""}"></i>',
    'fa': lambda n, cls: f'<i class="fa-solid fa-{n}{" " + cls if cls else ""}"></i>',
}


@register.simple_tag(takes_context=True)
def icon(context, name, extra_class=''):
    """Render an icon for the active skin. Usage: {% icon "name" %} or {% icon name "extra-class" %}"""
    skin = context.get('skin_name', 'bootstrap5-bi')
    key = 'fa' if 'fa' in skin else 'bi'
    return mark_safe(_ICON_RENDERERS[key](name, extra_class))


@register.filter
def get_item(obj, key):
    """Get a value from a mapping (dict, BindingDict…) or object attribute by key."""
    try:
        return obj[key]
    except (KeyError, IndexError, TypeError):
        return getattr(obj, key, '')


@register.filter
def display_value(data, field_name):
    """Return the display value for field_name: uses {field}__display if present, else raw value."""
    try:
        display = data[f'{field_name}__display']
        if display != '' and display is not None:
            return display
    except (KeyError, TypeError):
        pass
    try:
        return data[field_name]
    except (KeyError, TypeError):
        return getattr(data, field_name, '')


@register.filter
def data_items(data):
    """Iterate data items skipping internal __display keys added by GUISerializer."""
    try:
        return [(k, v) for k, v in data.items() if not k.endswith('__display')]
    except AttributeError:
        return []


@register.filter
def data_keys(data):
    """Return data keys skipping internal keys added by GUISerializer."""
    try:
        return [k for k in data.keys()
                if not k.endswith('__display') and not k.startswith('sebastian__')]
    except AttributeError:
        return []


@register.filter
def filename(value) -> str:
    """Extract just the filename from a URL or file path."""
    from pathlib import PurePosixPath
    return PurePosixPath(str(value)).name if value else ''


@register.filter
def input_type(field) -> str:
    """Map a DRF field instance to an appropriate HTML input type."""
    mapping = {
        drf_serializers.IntegerField:  'number',
        drf_serializers.FloatField:    'number',
        drf_serializers.DecimalField:  'number',
        drf_serializers.DateField:     'date',
        drf_serializers.DateTimeField: 'datetime-local',
        drf_serializers.TimeField:     'time',
        drf_serializers.EmailField:    'email',
        drf_serializers.URLField:      'url',
        drf_serializers.BooleanField:  'checkbox',
        drf_serializers.FileField:     'file',
        drf_serializers.ImageField:    'file',
    }
    for field_class, html_type in mapping.items():
        if isinstance(field, field_class):
            return html_type
    return 'text'


@register.filter
def field_value(instance, field_name: str):
    """Get the display value of a field from a serializer's data dict or model instance."""
    if instance is None:
        return ''
    if isinstance(instance, dict):
        return instance.get(field_name, '')
    return getattr(instance, field_name, '')


@register.simple_tag(takes_context=True)
def get_link_action(context, field_name):
    """
    Return the first available action whose gui_config['link_field'] matches field_name,
    or None if no such action exists. Used by detail/list templates to render inline
    file-download links directly on the field value instead of in the action button group.
    """
    view = context.get('view')
    if not view:
        return None
    for action_dict in view.get_available_actions():
        if action_dict.get('gui_config', {}).get('link_field') == field_name:
            return action_dict
    return None


@register.filter
def json(value) -> str:
    """Serialize a Python value to a JSON string safe for use in HTML data attributes."""
    import json as _json
    return mark_safe(_json.dumps(value, ensure_ascii=False))


@register.simple_tag
def sebastian_version():
    from sebastian import __version__
    return __version__


@register.simple_tag(takes_context=True)
def include_resource(context, url):
    """
    Server-side GET to a Django GUI URL. Returns the rendered HTML fragment.
    Used by the 'plain' pack to replace hx-get inline loads with synchronous includes.
    Sets HTTP_HX_REQUEST so the inner render returns just the content block.
    """
    from django.test import RequestFactory as DjangoRF
    from django.urls import resolve, Resolver404

    if not url:
        return ''
    request = context.get('request')
    try:
        match = resolve(url)
    except Resolver404:
        return mark_safe(f'<!-- include_resource: no route for {url} -->')

    current_url = request.build_absolute_uri() if request else ''
    sub = DjangoRF().get(url, HTTP_HX_REQUEST='1', HTTP_HX_CURRENT_URL=current_url)
    sub.user    = getattr(request, 'user', None)
    sub.session = getattr(request, 'session', {})
    sub.sebastian_gui = True

    try:
        resp = match.func(sub, *match.args, **match.kwargs)
        if hasattr(resp, 'render'):
            resp.render()
        return mark_safe(resp.content.decode('utf-8'))
    except Exception as exc:
        return mark_safe(f'<!-- include_resource error: {exc} -->')
