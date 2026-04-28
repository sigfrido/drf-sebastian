"""
Internal ViewSet dispatch — call a ViewSet action without an HTTP round-trip.

Usage (always within transaction.atomic in the caller):

    from django.db import transaction
    from sebastian.dispatch import call

    with transaction.atomic():
        instance.approve()
        call(OtherViewSet, 'activate', request, pk=instance.related_id)
"""
from django.http import HttpRequest


def call(viewset_class, action_name: str, request: HttpRequest, **kwargs):
    """
    Instantiate viewset_class and invoke action_name directly.

    Permission checks defined on the target ViewSet still run — enforcement
    is consistent whether the call comes from HTTP or internally.
    Pass format_kwarg=None so the target ViewSet uses its default renderer.
    """
    viewset = viewset_class()
    viewset.request = request
    viewset.kwargs = kwargs
    viewset.format_kwarg = None
    viewset.action = action_name
    viewset.args = ()

    method = getattr(viewset, action_name, None)
    if method is None:
        raise AttributeError(
            f'{viewset_class.__name__} has no action "{action_name}"'
        )

    return method(request, **kwargs)
