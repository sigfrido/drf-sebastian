"""
Verifies the Italian translation catalog bundled with the library is wired
correctly: locale discovery via INSTALLED_APPS, package-data inclusion, and
that the compiled .mo actually gets used when the active language is 'it'.
"""
import pytest
from django.test import override_settings
from django.utils import translation


GUI = {'HTTP_ACCEPT': 'text/html'}


@pytest.mark.django_db
def test_default_language_renders_english(auth_client, supplier):
    r = auth_client.get('/gui/suppliers/', **GUI)
    assert r.status_code == 200
    assert b'Filter' in r.content
    assert b'plus-lg"></i> New' in r.content


@pytest.mark.django_db
def test_italian_locale_translates_library_chrome(auth_client, supplier):
    with translation.override('it'):
        r = auth_client.get('/gui/suppliers/', **GUI)
    assert r.status_code == 200
    assert b'Filtra' in r.content
    assert b'plus-lg"></i> Nuovo' in r.content
    # English defaults must be gone, not just the Italian strings present
    assert b'plus-lg"></i> New' not in r.content


@pytest.mark.django_db
def test_italian_locale_translates_bool_yesno(supplier):
    from demo.serializers import SupplierSerializer
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    with translation.override('it'):
        req = Request(factory.get('/'))
        req.sebastian_gui = True
        s = SupplierSerializer(supplier, context={'request': req})
        assert s.data['active__display'] == 'Sì'
