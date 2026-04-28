from django import template
from rest_framework import serializers as drf_serializers

register = template.Library()


@register.filter
def get_item(obj, key):
    """Get a value from a dict or object attribute by key."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, '')


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
