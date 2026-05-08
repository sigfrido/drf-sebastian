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
def test_gui_mode_adds_sebastian_str(fornitore):
    from selco.serializers import FornitoreSerializer
    s = FornitoreSerializer(fornitore, context={'request': _gui_request()})
    assert 'sebastian__str' in s.data
    assert s.data['sebastian__str'] == str(fornitore)


@pytest.mark.django_db
def test_api_mode_omits_sebastian_str(fornitore):
    from selco.serializers import FornitoreSerializer
    s = FornitoreSerializer(fornitore, context={'request': _api_request()})
    assert 'sebastian__str' not in s.data


@pytest.mark.django_db
def test_gui_mode_adds_display_for_related_field(richiesta):
    from selco.serializers import RichiestaSerializer
    s = RichiestaSerializer(richiesta, context={'request': _gui_request()})
    assert 'fornitore__display' in s.data
    assert richiesta.fornitore.ragione_sociale in s.data['fornitore__display']


@pytest.mark.django_db
def test_api_mode_omits_display_keys(richiesta):
    from selco.serializers import RichiestaSerializer
    s = RichiestaSerializer(richiesta, context={'request': _api_request()})
    assert not any(k.endswith('__display') for k in s.data)


@pytest.mark.django_db
def test_gui_mode_null_fk_omits_display(db):
    from selco.models import Richiesta
    from selco.serializers import RichiestaSerializer
    r = Richiesta.objects.create(
        titolo='No fornitore', descrizione='', budget='0', stato=Richiesta.Stato.BOZZA,
    )
    s = RichiestaSerializer(r, context={'request': _gui_request()})
    assert 'fornitore__display' not in s.data


# ── FieldGroup permission enforcement ────────────────────────────────────────

@pytest.mark.django_db
def test_fieldgroup_hidden_field_removed(fornitore, admin_user):
    """A field whose group has visible_permission=False is absent from output."""
    from selco.serializers import FornitoreSerializer

    class RestrictedView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['ragione_sociale', 'codice_fiscale'],
                           visible_permission=lambda req, obj: False),
            ]

    req = _gui_request(admin_user)
    s = FornitoreSerializer(
        fornitore,
        context={'request': req, 'view': RestrictedView()},
    )
    fields = s.fields
    assert 'ragione_sociale' not in fields
    assert 'codice_fiscale' not in fields


@pytest.mark.django_db
def test_fieldgroup_readonly_when_not_editable(fornitore, admin_user):
    """A field whose group has edit_permission=False is marked read_only."""
    from selco.serializers import FornitoreSerializer

    class ReadonlyView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['ragione_sociale'],
                           edit_permission=lambda req, obj: False),
            ]

    req = _gui_request(admin_user)
    s = FornitoreSerializer(
        fornitore,
        context={'request': req, 'view': ReadonlyView()},
    )
    assert s.fields['ragione_sociale'].read_only is True


@pytest.mark.django_db
def test_fieldgroup_visible_permission_true_keeps_field(fornitore, admin_user):
    from selco.serializers import FornitoreSerializer

    class VisibleView:
        class Sebastian:
            groups = [
                FieldGroup('base', ['ragione_sociale'],
                           visible_permission=lambda req, obj: True),
            ]

    req = _gui_request(admin_user)
    s = FornitoreSerializer(
        fornitore,
        context={'request': req, 'view': VisibleView()},
    )
    assert 'ragione_sociale' in s.fields
