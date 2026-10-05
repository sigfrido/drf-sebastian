"""
Pagination driven by the viewset's ``Sebastian.pagination`` metadata.

    class Sebastian:
        pagination = {'on': True, 'page_size': 10, 'show_first_last': True, 'show_page_num': True}

``on`` defaults to False (list not paginated); the other keys default to
``SEBASTIAN['PAGE_SIZE']`` / ``['PAGE_FIRST_LAST']`` / ``['PAGE_SHOW_NUM']``.
When on, it applies to the GUI and the API alike (standard DRF pagination).
"""
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from . import app_settings


def pagination_config(view) -> dict:
    """The view's ``Sebastian.pagination`` merged over the global defaults; {} when off."""
    sebastian = getattr(view.__class__, 'Sebastian', None) if view is not None else None
    cfg = getattr(sebastian, 'pagination', None) or {}
    if not cfg.get('on'):
        return {}
    return {
        'page_size':       cfg.get('page_size') or app_settings.page_size(),
        'show_first_last': cfg.get('show_first_last', app_settings.page_first_last()),
        'show_page_num':   cfg.get('show_page_num', app_settings.page_show_num()),
    }


class SebastianPagination(PageNumberPagination):
    """Page-number pagination, active only for viewsets with ``Sebastian.pagination['on']``."""

    def paginate_queryset(self, queryset, request, view=None):
        self._config = pagination_config(view)
        self._first_page = False
        if not self._config:
            return None
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound as exc:
            # GUI: a page out of range (or not a number) shows the first page of the same list,
            # with the error as a message; the API keeps DRF's 404.
            if not getattr(request, 'sebastian_gui', False):
                raise
            from django.contrib import messages
            messages.warning(getattr(request, '_request', request), str(exc.detail),
                             fail_silently=True)
            self._first_page = True
            return super().paginate_queryset(queryset, request, view)

    def get_page_number(self, request, paginator):
        if getattr(self, '_first_page', False):
            return 1
        return super().get_page_number(request, paginator)

    def get_page_size(self, request):
        return getattr(self, '_config', {}).get('page_size') or app_settings.page_size()

    def get_paginated_response(self, data):
        return Response({
            'count':     self.page.paginator.count,
            'next':      self.get_next_link(),
            'previous':  self.get_previous_link(),
            'page':      self.page.number,
            'num_pages': self.page.paginator.num_pages,
            'results':   data,
        })

    def get_paginated_response_schema(self, schema):
        response = super().get_paginated_response_schema(schema)
        response['properties']['page'] = {'type': 'integer', 'example': 1}
        response['properties']['num_pages'] = {'type': 'integer', 'example': 3}
        return response
