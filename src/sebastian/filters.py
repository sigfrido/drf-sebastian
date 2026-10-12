"""
User-dependent filter values ("metavalues") for django-filter (optional dependency).

A metavalue is an extra choice of a filter whose value is computed for the
current user, like workflango's ``owner=me``::

    from sebastian.filters import MetaModelChoiceFilter

    class RequestFilter(django_filters.FilterSet):
        supplier = MetaModelChoiceFilter(
            queryset=Supplier.objects.all(),
            metavalues={'my_supplier': ('My supplier', lambda request: request.user.supplier)},
        )

``?supplier=my_supplier`` filters by the user's supplier; the metavalues are
listed first among the choices. A function returning ``None`` (e.g. a user
with no supplier) means no filtering. Metavalues fit default filters
(`sebastian.default_filter`): ``default_filter = 'supplier=my_supplier'``.
"""
import django_filters
from django import forms
from django.forms.models import ModelChoiceIterator


class _MetaModelChoiceIterator(ModelChoiceIterator):
    """Empty label, then the metavalues, then the queryset."""

    def __iter__(self):
        choices = super().__iter__()
        if self.field.empty_label is not None:
            yield next(choices)
        for key, (label, _fn) in self.field.metavalues.items():
            yield (key, label)
        yield from choices

    def __len__(self):
        return super().__len__() + len(self.field.metavalues)


class MetaModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that also accepts the keys of ``metavalues`` (returned as they are)."""
    iterator = _MetaModelChoiceIterator

    def __init__(self, *args, metavalues=None, **kwargs):
        self.metavalues = dict(metavalues or {})
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.metavalues:
            return value
        return super().to_python(value)


class MetaModelChoiceFilter(django_filters.ModelChoiceFilter):
    """ModelChoiceFilter with user-dependent values:
    ``metavalues={key: (label, fn(request) -> instance | None)}``."""
    field_class = MetaModelChoiceField

    def __init__(self, *args, metavalues=None, **kwargs):
        self.metavalues = dict(metavalues or {})
        super().__init__(*args, metavalues=self.metavalues, **kwargs)

    def filter(self, qs, value):
        if isinstance(value, str) and value in self.metavalues:
            _label, fn = self.metavalues[value]
            value = fn(getattr(self.parent, 'request', None))
            if value is None:
                return qs
        return super().filter(qs, value)
