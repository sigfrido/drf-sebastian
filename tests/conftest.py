import pytest


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def admin_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_superuser('admin', 'admin@example.com', 'password')


@pytest.fixture
def regular_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user('utente', 'utente@example.com', 'password')


@pytest.fixture
def regular_client(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    return api_client


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def auth_client_regular(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    return api_client


# ── model fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def fornitore(db):
    from selco.models import Fornitore
    return Fornitore.objects.create(
        ragione_sociale='Acme Srl',
        codice_fiscale='12345678901',
        attivo=True,
    )


@pytest.fixture
def richiesta(db, fornitore):
    from selco.models import Richiesta
    return Richiesta.objects.create(
        titolo='Acquisto server',
        descrizione='Rinnovo infrastruttura',
        budget='5000.00',
        stato=Richiesta.Stato.BOZZA,
        fornitore=fornitore,
    )


@pytest.fixture
def allegato(db, richiesta):
    from selco.models import Allegato
    from django.core.files.base import ContentFile
    a = Allegato(richiesta=richiesta, descrizione='Documento test')
    a.file.save('test.txt', ContentFile(b'contenuto test'))
    return a


# ── DRF request helpers ───────────────────────────────────────────────────────

@pytest.fixture
def rf():
    from rest_framework.test import APIRequestFactory
    return APIRequestFactory()


def make_gui_request(rf, user=None):
    """Return a DRF Request with sebastian_gui=True."""
    from rest_framework.request import Request
    django_request = rf.get('/')
    if user:
        django_request.user = user
    req = Request(django_request)
    req.sebastian_gui = True
    return req
