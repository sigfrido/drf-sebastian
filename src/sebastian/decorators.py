"""
Sebastian @action decorator — extends DRF's @action with gui_config metadata.

gui_config keys:
    label    str   Button label in the GUI
    icon     str   Icon name (e.g. 'check-circle')
    color    str   Bootstrap color: 'primary'|'success'|'danger'|'warning'|'secondary'
    confirm  str   Confirmation prompt shown before the action fires
    position str   Where to show the button: 'detail'|'list'|'both'  (default: 'detail')
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
