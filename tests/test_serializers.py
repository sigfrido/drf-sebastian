"""
Unit tests for GUISerializer behaviour.
Tests cover GUI mode vs API mode, __display keys, sebastian__str,
and FieldGroup permission enforcement.
"""
import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from sebastian.config import FieldGroup

factory = APIRequestFactory()


def _gui_request(user=None):
    req = Request(factory.get('/'))
    if user:
        req._request.user = user
    req.sebastian_gui = True
    return req


def _api_request():
    return Request(factory.get('/'))


# ── to_representation: GUI vs API mode ───────────────────────────────────────

@pytest.mark.django_db
def test_gui_mode_adds_sebastian_str(supplier):
    from demo.serializers import SupplierSerializer
    s = SupplierSerializer(supplier, context={'request': _gui_request()})
    assert 'sebastian__str' in s.data
    assert s.data['sebastian__str'] == str(supplier)


@pytest.mark.django_db
def test_api_mode_omits_sebastian_str(supplier):
    from demo.serializers import SupplierSerializer
    s = SupplierSerializer(supplier, context={'request': _api_request()})
    assert 'sebastian__str' not in s.data


@pytest.mark.django_db
def test_gui_mode_adds_display_for_related_field(purchase_request):
    from demo.serializers import RequestSerializer
    s = RequestSerializer(purchase_request, context={'request': _gui_request()})
    assert 'supplier__display' in s.data
    assert purchase_request.supplier.company_name in s.data['supplier__display']


@pytest.mark.django_db
def test_api_mode_omits_display_keys(purchase_request):
    from demo.serializers import RequestSerializer
    s = RequestSerializer(purchase_request, context={'request': _api_request()})
    assert not any(k.endswith('__display') for k in s.data)


@pytest.mark.django_db
def test_gui_mode_null_fk_omits_display(db):
    from demo.models import Request
    from demo.serializers import RequestSerializer
    r = Request.objects.create(
        title='No supplier', description='', budget='0', status=Request.Status.DRAFT,
    )
    s = RequestSerializer(r, context={'request': _gui_request()})
    assert 'supplier__display' not in s.data


# ── FieldGroup permission enforcement ────────────────────────────────────────

@pytest.mark.django_db
def test_fieldgroup_hidden_field_removed(supplier, admin_user):
    """A field whose group has visible_permission=False is absent from output."""
    from demo.serializers import SupplierSerializer

    class RestrictedView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['company_name', 'tax_code'],
                           visible_permission=lambda req, obj: False),
            ]

    req = _gui_request(admin_user)
    s = SupplierSerializer(
        supplier,
        context={'request': req, 'view': RestrictedView()},
    )
    fields = s.fields
    assert 'company_name' not in fields
    assert 'tax_code' not in fields


@pytest.mark.django_db
def test_fieldgroup_readonly_when_not_editable(supplier, admin_user):
    """A field whose group has edit_permission=False is marked read_only."""
    from demo.serializers import SupplierSerializer

    class ReadonlyView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['company_name'],
                           edit_permission=lambda req, obj: False),
            ]

    req = _gui_request(admin_user)
    s = SupplierSerializer(
        supplier,
        context={'request': req, 'view': ReadonlyView()},
    )
    assert s.fields['company_name'].read_only is True


@pytest.mark.django_db
def test_fieldgroup_visible_permission_true_keeps_field(supplier, admin_user):
    from demo.serializers import SupplierSerializer

    class VisibleView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['company_name'],
                           visible_permission=lambda req, obj: True),
            ]

    req = _gui_request(admin_user)
    s = SupplierSerializer(
        supplier,
        context={'request': req, 'view': VisibleView()},
    )
    assert 'company_name' in s.fields
