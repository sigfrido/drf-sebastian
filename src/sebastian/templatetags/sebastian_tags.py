import datetime
import re
from django import template
from django.utils import formats, timezone
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe
from rest_framework import serializers as drf_serializers

from ..i18n import sgettext

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


@register.simple_tag
def strans(text):
    """Shorthand for ``{% trans text context "sebastian" %}``.

    NOTE for makemessages: this custom tag is invisible to Django's template
    string extractor (it only recognizes the built-in trans/blocktrans tags),
    so every string passed to {% strans %} must also appear as a real
    ``pgettext('sebastian', ...)`` call somewhere makemessages *does* scan —
    see ``sebastian/_translatable_strings.py``, kept in sync by hand.
    """
    return sgettext(text)


@register.filter
def get_item(obj, key):
    """Get a value from a mapping (dict, BindingDict…) or object attribute by key.

    Strings are deliberately excluded from the attribute-lookup fallback: a str
    has real methods named after common field names (``title``, ``upper``,
    ``strip``, ``format``, ...), so ``getattr('', 'title')`` returns the bound
    method instead of a missing-value default. A bare string is never a valid
    "object with fields" here, so it should just fall through to ''.
    """
    try:
        return obj[key]
    except (KeyError, IndexError, TypeError):
        if isinstance(obj, str):
            return ''
        return getattr(obj, key, '')


@register.filter
def row_can_update(item, view):
    """Per-row edit permission check for list templates.

    If the serialized item contains a ``__can_update`` key (injected by
    WorkflowSerializerMixin) that value is used; otherwise falls back to
    ``view.can_update()``.  Safe to use on any item regardless of whether the
    viewset is workflow-aware.
    """
    if isinstance(item, dict) and '__can_update' in item:
        return bool(item['__can_update'])
    can_update = getattr(view, 'can_update', None)
    if callable(can_update):
        return bool(can_update())
    return bool(can_update) if can_update is not None else True


@register.filter
def row_can_delete(item, view):
    """Per-row delete permission check for list templates.

    Same fallback logic as ``row_can_update`` but checks ``__can_delete``.
    """
    if isinstance(item, dict) and '__can_delete' in item:
        return bool(item['__can_delete'])
    can_delete = getattr(view, 'can_delete', None)
    if callable(can_delete):
        return bool(can_delete())
    return bool(can_delete) if can_delete is not None else True


@register.filter
def isodt(value, fmt='d/m/Y H:i'):
    """Parse an ISO 8601 datetime string from a DRF serializer and format it.

    Usage: {{ state.state_date|isodt }} or {{ state.state_date|isodt:"d/m/Y" }}
    Falls back to str(value) if parsing fails.
    """
    if not value:
        return ''
    if isinstance(value, (datetime.date, datetime.datetime)):
        dt = value
    else:
        dt = parse_datetime(str(value))
        if dt is None:
            return str(value)
    if isinstance(dt, datetime.datetime) and timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return formats.date_format(dt, fmt)


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
        if isinstance(data, str):
            return ''
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
    """Map a DRF field instance to an appropriate HTML input type.

    Returns 'textarea' for CharField fields generated from models.TextField
    (DRF sets style={'base_template': 'textarea.html'} for these automatically).
    """
    # Check for textarea style (DRF sets this for models.TextField)
    style = getattr(field, 'style', {})
    if style.get('base_template') == 'textarea.html':
        return 'textarea'
    mapping = {
        drf_serializers.IntegerField:  'number',
        drf_serializers.FloatField:    'number',
        drf_serializers.DecimalField:  'number',
        drf_serializers.DateField:     'date',
        drf_serializers.DateTimeField: 'datetime-local',
        drf_serializers.TimeField:     'time',
        drf_serializers.EmailField:    'email',
        drf_serializers.URLField:      'url',
        drf_serializers.BooleanField:  'bool-select',
        drf_serializers.FileField:     'file',
        drf_serializers.ImageField:    'file',
    }
    for field_class, html_type in mapping.items():
        if isinstance(field, field_class):
            return html_type
    return 'text'


@register.filter
def form_input_value(data, field_name) -> str:
    """Like get_item, but formats datetime → YYYY-MM-DDTHH:MM for a datetime-local input.

    Browsers ignore datetime values with a timezone offset (e.g. +02:00); this
    filter returns the string truncated to the minute, with no offset.
    """
    val = get_item(data, field_name)
    if not val:
        return ''
    s = str(val)
    m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})', s)
    return m.group(1) if m else s


_WIDTH_MAP = {
    'xs':   'col-sm-3 col-md-2',
    'sm':   'col-sm-4 col-md-3',
    'md':   'col-sm-6 col-md-5',
    'lg':   'col-sm-9 col-md-7',
    'full': 'col-12',
}


@register.simple_tag
def field_col(field, fc=None) -> str:
    """Return a Bootstrap column class for a form field, used to size input width.

    Checks field_config[field]['width'] first (logical size: xs/sm/md/lg/full),
    then auto-maps from the field's HTML input type and max_length.
    """
    if fc and isinstance(fc, dict):
        override = fc.get('width')
        if override and override in _WIDTH_MAP:
            return _WIDTH_MAP[override]

    itype = input_type(field)
    # manual widget override in field_config counts as textarea for width purposes
    if fc and isinstance(fc, dict) and fc.get('widget') == 'textarea':
        return _WIDTH_MAP['full']

    if itype in ('date', 'time', 'number', 'bool-select'):
        return _WIDTH_MAP['sm']
    if itype == 'datetime-local':
        return _WIDTH_MAP['md']
    if itype in ('email', 'select'):
        return _WIDTH_MAP['md']
    if itype == 'url':
        return _WIDTH_MAP['lg']
    if itype == 'text':
        max_len = getattr(field, 'max_length', None)
        if max_len and max_len <= 50:
            return _WIDTH_MAP['sm']
        if max_len and max_len <= 200:
            return _WIDTH_MAP['md']
        return _WIDTH_MAP['full']
    # textarea, file, unknown
    return _WIDTH_MAP['full']


@register.filter
def bool_select_value(instance, field) -> str:
    """Return 'true', 'false', or '' for a boolean field, suitable for <select> value comparison.
    Accepts a DRF field object or a plain field name string.
    When the value is None and the field does not allow null, defaults to 'false'.
    """
    if isinstance(field, str):
        field_name, allow_null = field, False
    else:
        field_name = field.field_name
        allow_null = getattr(field, 'allow_null', False)
    val = instance.get(field_name) if isinstance(instance, dict) else getattr(instance, field_name, None)
    if val is True:
        return 'true'
    if val is False:
        return 'false'
    return '' if allow_null else 'false'


@register.filter
def resolve_confirm(prompt, obj) -> str:
    """Substitute $OBJECT in a confirmation prompt with str(obj)."""
    return (prompt or '').replace('$OBJECT', str(obj) if obj is not None else '')


@register.filter
def any_has_label(groups) -> bool:
    """True if at least one group in the list has a non-empty label."""
    return any(getattr(g, 'label', '') for g in groups)


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

@register.filter
def bootstrapfield(field):
    if field.widget_type in ('select', 'selectmultiple'):
        return add_class(field, 'form-select form-select-sm')
    return add_class(field, 'form-control form-control-sm')

@register.filter
def add_class(field, classes):
    widget = getattr(getattr(field, 'field', None), 'widget', None)
    widget_class = getattr(widget, 'attrs', {}).get('class', '') if widget else ''
    field_classes = field.css_classes().split(' ')
    for cls in (classes + ' ' + widget_class).split(' '):
        if cls and cls not in field_classes:
            field_classes.append(cls)
    return field.as_widget(attrs={
        "class": " ".join(c for c in field_classes if c)
    })

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

