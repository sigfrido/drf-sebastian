"""
GUISerializer mixin — enforces FieldGroup permissions at the serializer layer
and adds GUI display helpers for RelatedField values.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models as django_models
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.relations import RelatedField


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


class GUISerializerMixin:
    """
    Mixin for DRF Serializers.

    - Enforces FieldGroup visibility/edit permissions via get_fields().
    - In GUI mode (request.sebastian_gui=True), adds {field}__display keys
      to the serialized output for each RelatedField so templates can show
      human-readable values without extra DB queries.

    Override get_sebastian_description() to customize per-field display:

        def get_sebastian_description(self, field_name, related_obj):
            if field_name == 'fornitore':
                return related_obj.ragione_sociale
            return super().get_sebastian_description(field_name, related_obj)
    """
    # Configuration
    SKIP_MODEL_VALIDATION = False
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
            if not isinstance(field, RelatedField) or field.write_only:
                continue
            if ret.get(field_name) is None:
                continue
            related_obj = getattr(instance, field_name, None)
            ret[f'{field_name}__display'] = self.get_sebastian_description(field_name, related_obj)
        return ret

    def get_sebastian_description(self, field_name, related_obj):
        """Template method: return a display string for a RelatedField value.

        Default: str(related_obj) — delegates to the model's __str__.
        Override per-serializer to customise individual fields.
        """
        if related_obj is None:
            return ''
        return str(related_obj)

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
                raise PermissionDenied(f"Field '{attr}' is not accessible.")
            if attr in readonly:
                raise PermissionDenied(f"Field '{attr}' is read-only.")

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
        for group in groups:
            from sebastian.config import FieldGroup
            if not isinstance(group, FieldGroup):
                continue
            for field_name in group.fields:
                if field_name not in fields:
                    continue
                if not group.is_visible(request, obj):
                    self._permission_hidden_fields.add(field_name)
                    del fields[field_name]
                elif not group.is_editable(request, obj):
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
