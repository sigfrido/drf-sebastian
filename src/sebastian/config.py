from dataclasses import dataclass
from typing import Callable, Optional, Sequence


@dataclass
class FieldGroup:
    """
    A named group of serializer fields sharing visibility and edit permissions.
    Declared in ViewSet.Sebastian.groups. Order of declaration is respected in GUI.
    """
    name: str
    fields: Sequence[str]
    label: str = ''
    edit_permission: Optional[Callable] = None    # callable(request, obj) -> bool
    visible_permission: Optional[Callable] = None  # callable(request, obj) -> bool

    def is_visible(self, request, obj) -> bool:
        if self.visible_permission is None:
            return True
        return bool(self.visible_permission(request, obj))

    def is_editable(self, request, obj) -> bool:
        if self.edit_permission is None:
            return True
        return bool(self.edit_permission(request, obj))
