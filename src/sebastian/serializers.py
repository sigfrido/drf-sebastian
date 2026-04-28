"""
GUISerializer mixin — enforces FieldGroup permissions at the serializer layer
so that field-level access control applies to both API and GUI calls.
"""


class GUISerializer:
    """
    Mixin for DRF Serializers. Reads FieldGroup configuration from the view
    (available via self.context['view']) and marks fields as read_only or
    removes them from the representation according to per-group permissions.

    Works with any serializer that has self.context['view'] set — this is
    standard DRF behaviour for serializers instantiated by GenericAPIView/ViewSet.
    For plain APIView, pass context={'view': self, 'request': request} explicitly.
    """

    def get_fields(self):
        fields = super().get_fields()
        request, view = self._get_request_and_view()
        if not request or not view:
            return fields

        groups = self._get_field_groups(view)
        if not groups:
            return fields

        obj = getattr(self, 'instance', None)
        grouped_fields = {}
        for group in groups:
            from sebastian.config import FieldGroup
            if not isinstance(group, FieldGroup):
                continue
            for field_name in group.fields:
                if field_name not in fields:
                    continue
                visible  = group.is_visible(request, obj)
                editable = group.is_editable(request, obj)

                if not visible:
                    del fields[field_name]
                elif not editable:
                    fields[field_name].read_only = True

                grouped_fields[field_name] = True

        return fields

    def _get_request_and_view(self):
        ctx = getattr(self, 'context', {})
        return ctx.get('request'), ctx.get('view')

    def _get_field_groups(self, view):
        sebastian = getattr(view.__class__, 'Sebastian', None)
        if not sebastian:
            return []
        return getattr(sebastian, 'groups', [])
