from rest_framework import renderers as drf_renderers
from rest_framework.response import Response

from .renderers import SebastianHTMLRenderer


class GUIMixin:
    """
    ViewSet/GenericAPIView mixin that enables Sebastian GUI generation.

    Adds SebastianHTMLRenderer alongside JSONRenderer so the same ViewSet
    serves JSON (Accept: application/json or /api/ routes) and HTML
    (Accept: text/html or /gui/ routes with format='html' URL kwarg).

    Sets request.sebastian_gui = True when the selected renderer is HTML,
    available for use in custom hooks and debug tooling.

    GUI-specific actions provided:
        create_form(request)         — empty form for a new instance
        update_form(request, pk)     — pre-filled form for an existing instance
    """

    renderer_classes = [drf_renderers.JSONRenderer, SebastianHTMLRenderer]

    # ------------------------------------------------------------------ #
    # Request lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def initialize_request(self, request, *args, **kwargs):
        drf_request = super().initialize_request(request, *args, **kwargs)
        # Transfer flag set by GUIRouter's URL kwargs wrapper (django request → drf request)
        if getattr(request, 'sebastian_gui', False):
            drf_request.sebastian_gui = True
        return drf_request

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # After content negotiation, flag HTML responses (A + B from design)
        if getattr(request, 'accepted_renderer', None):
            if request.accepted_renderer.format == 'html':
                request.sebastian_gui = True

    # ------------------------------------------------------------------ #
    # GUI-only actions (registered by GUIRouter)                          #
    # ------------------------------------------------------------------ #

    def create_form(self, request, *args, **kwargs):
        """Return an empty HTML form for creating a new instance."""
        serializer = self.get_serializer()
        return Response({'serializer': serializer, 'action': 'create'})

    def update_form(self, request, *args, **kwargs):
        """Return an HTML form pre-filled with an existing instance's data."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'serializer': serializer, 'instance': instance, 'action': 'update'})

    # ------------------------------------------------------------------ #
    # Sebastian metadata helpers                                          #
    # ------------------------------------------------------------------ #

    def get_sebastian_config(self):
        """Returns the ViewSet.Sebastian inner class, or None."""
        return getattr(self.__class__, 'Sebastian', None)

    def get_groups(self):
        """Returns the declared groups list (FieldGroup + EntityGroup), or []."""
        sebastian = self.get_sebastian_config()
        if not sebastian:
            return []
        return getattr(sebastian, 'groups', [])

    def get_available_actions(self):
        """
        Returns gui_config metadata for @actions the current user has permission for.
        Used by templates to render action buttons.
        """
        available = []
        for name in dir(self.__class__):
            method = getattr(self.__class__, name, None)
            if not callable(method) or not hasattr(method, 'mapping'):
                continue
            gui_config = getattr(method, 'gui_config', {})
            if not gui_config:
                continue
            permission_classes = getattr(method, 'kwargs', {}).get('permission_classes', [])
            try:
                for perm_class in permission_classes:
                    perm = perm_class()
                    if not perm.has_permission(self.request, self):
                        raise PermissionError
                available.append({'name': name, 'gui_config': gui_config})
            except (PermissionError, Exception):
                pass
        return available
