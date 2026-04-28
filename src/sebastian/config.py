from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Type


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


@dataclass
class EntityGroup:
    """
    A named inline relation rendered as an HTMX-powered section with per-row
    add/edit/delete modal actions. Declared in ViewSet.Sebastian.groups alongside
    FieldGroups; declaration order is respected in GUI.

    The parent ViewSet handles all nested CRUD via @action methods.
    Sebastian auto-generates modal routes for add/edit/delete.
    """
    name: str
    model: Type
    serializer_class: Type
    label: str = ''
    related_field: str = ''        # FK on child pointing to parent; auto-detected if blank
    display: str = 'tabular'       # 'tabular' | 'stacked'
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

    def resolve_related_field(self) -> str:
        """Auto-detect the FK field on the child model pointing to the parent."""
        if self.related_field:
            return self.related_field
        from django.db import models as django_models
        parent_model = None  # resolved at runtime by GUIMixin using the view's queryset model
        for f in self.model._meta.get_fields():
            if isinstance(f, django_models.ForeignKey):
                return f.name
        raise ValueError(
            f"EntityGroup '{self.name}': cannot auto-detect related_field on "
            f"{self.model.__name__}. Set it explicitly."
        )
