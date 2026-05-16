"""
Sebastian decorators — extend DRF's @action with GUI metadata.

action()     Drop-in for DRF @action, attaches gui_config dict.
typeahead()  Registers a GET list action as a typeahead endpoint.
             Endpoint must call self.standard_typeahead() and return a
             Response([{value, label}, ...]).
"""
from rest_framework.decorators import action as drf_action


def action(*args, gui_config: dict | None = None, **kwargs):
    """
    Drop-in replacement for DRF's @action that attaches GUI metadata.
    All DRF @action arguments are passed through unchanged.
    """
    def decorator(func):
        func.gui_config = gui_config or {}
        return drf_action(*args, **kwargs)(func)
    return decorator


def typeahead(typeahead_chars: int = 2, max_results: int = 100):
    """
    Register a ViewSet method as a typeahead endpoint.

    Wraps the method as a DRF list @action (GET, detail=False) whose
    url_path is the method name. The method should call
    self.standard_typeahead(...) and return its result.

    Usage:
        @typeahead(typeahead_chars=2, max_results=50)
        def my_typeahead(self, request, **kwargs):
            return self.standard_typeahead(
                filter={'name__istartswith': request.query_params.get('q', '')},
            )
    """
    def decorator(func):
        func.typeahead_chars = typeahead_chars
        func.max_results     = max_results
        return drf_action(
            methods=['get'],
            detail=False,
            url_path=func.__name__,
        )(func)
    return decorator
