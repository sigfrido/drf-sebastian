from django import template
from rest_framework import serializers as drf_serializers

register = template.Library()


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


@register.simple_tag
def sebastian_version():
    from sebastian import __version__
    return __version__
