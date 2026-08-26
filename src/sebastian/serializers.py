"""
GUISerializer mixin — enforces FieldGroup permissions at the serializer layer
and adds GUI display helpers for RelatedField values.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models as django_models
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.relations import RelatedField

from .i18n import sgettext


class NullableFileField(serializers.FileField):
    """FileField that treats an empty string as None.

    When the HTMX clear button (sbFileClear) is activated, the form sends
    an empty string for the field name. Standard DRF FileField rejects it;
    this subclass converts '' to None so nullable file fields can be cleared.
    """

    def to_internal_value(self, data):
        if data == '':
            return None
        return super().to_internal_value(data)


def gui_field(label_or_func=None):
    """Marks a serializer method as a GUI-only display field.

    The method is called during ``to_representation()`` only when
    ``request.sebastian_gui=True`` (never in the JSON API response).
    Its result is injected into the serialized dict so templates can
    reference it by name in ``Sebastian.list_fields`` or ``FieldGroup.fields``.

    Usage::

        @gui_field                      # auto-label from method name
        def my_col(self, obj): ...

        @gui_field('My Label')          # explicit label
        def my_col(self, obj): ...
    """
    if callable(label_or_func):
        label_or_func._is_gui_field = True
        label_or_func._gui_label = label_or_func.__name__.replace('_', ' ').title()
        return label_or_func
    def decorator(func):
        func._is_gui_field = True
        func._gui_label = label_or_func or func.__name__.replace('_', ' ').title()
        return func
    return decorator


class GUISerializerMixin:
    """
    Mixin for DRF Serializers.

    - Enforces FieldGroup visibility/edit permissions via get_fields().
    - In GUI mode (request.sebastian_gui=True), adds {field}__display keys
      to the serialized output for each RelatedField so templates can show
      human-readable values without extra DB queries.

    Override get_sebastian_description() to customize per-field display:

        def get_sebastian_description(self, field_name, related_obj):
            if field_name == 'supplier':
                return related_obj.company_name
            return super().get_sebastian_description(field_name, related_obj)

    @gui_field protocol
    -------------------
    Decorate serializer methods with ``@gui_field`` (or ``@gui_field('Label')``)
    to inject GUI-only computed columns. The method signature must be
    ``(self, instance) -> str | SafeString`` and it is called during
    ``to_representation()`` only when ``request.sebastian_gui=True``
    (never in the JSON API response). Reference the method name in
    ``Sebastian.list_fields`` or ``FieldGroup.fields`` as you would any
    regular field.
    """
    # Configuration
    SKIP_MODEL_VALIDATION = False
    bool_display     = None  # override per-serializer; None → use SEBASTIAN['BOOL_DISPLAY'] setting
    date_format      = None  # override per-serializer; None → use SEBASTIAN['DATE_FORMAT'] setting
    datetime_format  = None  # override per-serializer; None → use SEBASTIAN['DATETIME_FORMAT'] setting

    @classmethod
    def _get_gui_field_names(cls):
        """Return names of all @gui_field methods, ordered MRO base-first."""
        if '_gui_field_names_cache' not in cls.__dict__:
            seen, names = set(), []
            for klass in reversed(cls.__mro__):
                for name, m in klass.__dict__.items():
                    if callable(m) and getattr(m, '_is_gui_field', False) and name not in seen:
                        names.append(name)
                        seen.add(name)
            cls._gui_field_names_cache = names
        return cls._gui_field_names_cache

    # ------------------------------------------------------------------ #
    # Representation                                                       #
    # ------------------------------------------------------------------ #

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = (self.context or {}).get('request')
        if not getattr(request, 'sebastian_gui', False):
            return ret
        ret['sebastian__str'] = str(instance)
        for field_name, field in self.fields.items():
            if field.write_only:
                continue
            if isinstance(field, RelatedField):
                if ret.get(field_name) is None:
                    continue
                related_obj = getattr(instance, field_name, None)
                ret[f'{field_name}__display'] = self.get_sebastian_description(field_name, related_obj)
            elif isinstance(field, serializers.ChoiceField):
                raw = ret.get(field_name)
                if raw is not None:
                    display = field.choices.get(raw, raw)
                    if str(display) != str(raw):
                        ret[f'{field_name}__display'] = str(display)
            elif isinstance(field, serializers.DateTimeField):
                raw = ret.get(field_name)
                rendered = self._render_datetime(raw)
                if rendered is not None:
                    ret[f'{field_name}__display'] = rendered
            elif isinstance(field, serializers.DateField):
                raw = ret.get(field_name)
                rendered = self._render_date(raw)
                if rendered is not None:
                    ret[f'{field_name}__display'] = rendered
            elif isinstance(field, serializers.BooleanField):
                raw = ret.get(field_name)
                rendered = self._render_bool(raw)
                if rendered is not None:
                    ret[f'{field_name}__display'] = rendered
        hidden = getattr(self, '_permission_hidden_fields', set())
        for method_name in self._get_gui_field_names():
            if method_name in hidden:
                continue
            method = getattr(self, method_name, None)
            if callable(method):
                ret[method_name] = method(instance)
        return ret

    def get_sebastian_description(self, field_name, related_obj):
        """Template method: return a display string for a RelatedField value.

        Default: str(related_obj) — delegates to the model's __str__.
        Override per-serializer to customise individual fields.
        """
        if related_obj is None:
            return ''
        return str(related_obj)

    def _render_bool(self, value):
        """Return a display string for a boolean value, or None to skip transform.

        Format is determined by ``self.bool_display`` (per-serializer override)
        or the ``SEBASTIAN['BOOL_DISPLAY']`` setting.  Formats:
        - ``'yesno'``     → "Yes" / "No"
        - ``'checkmark'`` → "✓" / "✗"
        - ``'icon'``      → Bootstrap ``bi-check-circle-fill`` / ``bi-x-circle``
        - ``'truefalse'`` → no transform (returns None; template shows raw True/False)
        NullBooleanField None values always render as "—" unless format is 'truefalse'.
        """
        from . import app_settings
        fmt = self.bool_display or app_settings.bool_display()
        if fmt == 'truefalse':
            return None
        if value is None:
            return '—'
        if fmt == 'checkmark':
            return '✓' if value else '✗'
        if fmt == 'icon':
            from django.utils.html import format_html
            if value:
                return format_html('<i class="bi bi-check-circle-fill text-success"></i>')
            return format_html('<i class="bi bi-x-circle text-danger"></i>')
        # default: 'yesno'
        return sgettext('Yes') if value else sgettext('No')

    def _render_date(self, value):
        """Format a DateField value using SEBASTIAN['DATE_FORMAT'] or self.date_format.

        Returns None when the value is absent (no ``__display`` key added, template
        renders the raw value which Django shows as empty string for None).
        """
        if not value:
            return None
        from . import app_settings
        fmt = self.date_format or app_settings.date_format()
        if not fmt:
            return None
        import datetime
        from django.utils.dateparse import parse_date
        d = value if isinstance(value, datetime.date) else parse_date(str(value))
        return d.strftime(fmt) if d else None

    def _render_datetime(self, value):
        """Format a DateTimeField value using SEBASTIAN['DATETIME_FORMAT'] or self.datetime_format.

        Timezone-aware values are converted to local time before formatting.
        Returns None when the value is absent.
        """
        if not value:
            return None
        from . import app_settings
        fmt = self.datetime_format or app_settings.datetime_format()
        if not fmt:
            return None
        import datetime
        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import localtime, is_aware
        dt = value if isinstance(value, datetime.datetime) else parse_datetime(str(value))
        if dt is None:
            return None
        if is_aware(dt):
            dt = localtime(dt)
        return dt.strftime(fmt)

    # ------------------------------------------------------------------ #
    # Model-level validation                                              #
    # ------------------------------------------------------------------ #

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # DRF silently drops read_only and unknown fields from attrs, so we
        # check initial_data (raw submitted payload) against our permission sets,
        # populated by get_fields() during deserialization.
        hidden   = getattr(self, '_permission_hidden_fields',    set())
        readonly = getattr(self, '_permission_readonly_fields',  set())
        for attr in self.initial_data:
            if attr in hidden:
                raise PermissionDenied(sgettext("Field '$FIELD' is not accessible.").replace('$FIELD', attr))
            if attr in readonly:
                raise PermissionDenied(sgettext("Field '$FIELD' is read-only.").replace('$FIELD', attr))

        if not self.SKIP_MODEL_VALIDATION:
            # We call clean() only — not full_clean() — to avoid re-running
            # field-level DB constraints (blank/null/max_length) and unique
            # checks that the serializer fields already handle.
            instance = self.instance or self.Meta.model()
            # Only proceed if the instance is a Django model that overrides clean().
            if (
                hasattr(type(instance), 'clean')
                and type(instance).clean is not django_models.Model.clean
            ):
                for attr, value in attrs.items():
                    setattr(instance, attr, value)
                try:
                    instance.clean()
                except DjangoValidationError as exc:
                    errors = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
                    raise serializers.ValidationError(errors)
        return attrs

    # ------------------------------------------------------------------ #
    # Field permissions                                                    #
    # ------------------------------------------------------------------ #

    def get_fields(self):
        fields = super().get_fields()
        request, view = self._get_request_and_view()
        if not request or not view:
            return fields

        groups = self._get_field_groups(view)
        if not groups:
            return fields

        self._permission_hidden_fields   = set()
        self._permission_readonly_fields = set()

        # In many=True lists the child serializer's self.instance is the full queryset,
        # not an individual model instance — treat as no-object context.
        raw_obj = getattr(self, 'instance', None)
        obj = raw_obj if isinstance(raw_obj, django_models.Model) else None

        # In a list action without a specific object we cannot evaluate per-object
        # visibility rules — skip them so all fields remain serialized. Edit
        # permissions are still enforced (fields become read-only).
        is_list_without_obj = obj is None and getattr(view, 'action', None) == 'list'

        from sebastian.config import FieldGroup
        gui_names = set(self._get_gui_field_names())
        for group in groups:
            if not isinstance(group, FieldGroup):
                continue
            for field_name in group.fields:
                is_drf = field_name in fields
                is_gui = field_name in gui_names
                if not is_drf and not is_gui:
                    continue
                if not is_list_without_obj and not group.is_visible(request, obj):
                    self._permission_hidden_fields.add(field_name)
                    if is_drf:
                        del fields[field_name]
                elif is_drf and not group.is_editable(request, obj):
                    self._permission_readonly_fields.add(field_name)
                    fields[field_name].read_only = True
        return fields

    def _get_request_and_view(self):
        ctx = getattr(self, 'context', {})
        return ctx.get('request'), ctx.get('view')

    def _get_field_groups(self, view):
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if not sebastian:
            return []
        return getattr(sebastian, 'groups', [])
