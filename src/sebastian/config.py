from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Union


# Permission type: None (always allow), a single callable, or a list of callables (AND).
Permission = Optional[Union[Callable, Sequence[Callable]]]


def _check_permission(perm: Permission, request, obj) -> bool:
    """Evaluate a Sebastian permission value against (request, obj).

    None   → always True
    callable → call it
    sequence → AND — all callables must return True
    """
    if perm is None:
        return True
    if callable(perm):
        return bool(perm(request, obj))
    return all(bool(p(request, obj)) for p in perm)


@dataclass
class FieldGroup:
    """
    A named group of serializer fields sharing visibility and edit permissions.
    Declared in ViewSet.Sebastian.groups. Order of declaration is respected in GUI.
    """
    name: str
    fields: Sequence[str]
    label: str = ''
    edit_permission: Permission = None    # callable(request, obj) -> bool, or list (AND)
    visible_permission: Permission = None  # same

    def is_visible(self, request, obj) -> bool:
        return _check_permission(self.visible_permission, request, obj)

    def is_editable(self, request, obj) -> bool:
        return _check_permission(self.edit_permission, request, obj)


@dataclass
class MenuItem:
    """A single entry in a MenuGroup. Use `action` for ViewSet-relative routes
    or `url_name` for explicit Django URL names (custom pages, external links)."""
    label: str
    action: str = ''       # 'list' | 'new' | non-detail @action method name
    url_name: str = ''     # explicit URL name — for non-ViewSet pages
    icon: str = ''
    permission: Permission = None


@dataclass
class MenuDivider:
    """A horizontal rule rendered as a visual separator inside a MenuGroup dropdown."""
    pass


@dataclass
class MenuGroup:
    """A navbar dropdown contributed by a module. Declared in ViewSet.Sebastian.menu."""
    label: str
    icon: str = ''
    items: List[Union[MenuItem, 'MenuDivider']] = field(default_factory=list)
    permission: Permission = None
