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
    return User.objects.create_user('regular', 'regular@example.com', 'password')


@pytest.fixture
def manager_user(db):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from demo.permissions import MANAGERS
    User = get_user_model()
    user = User.objects.create_user('manager_test', 'manager_test@example.com', 'password')
    group, _ = Group.objects.get_or_create(name=MANAGERS)
    user.groups.add(group)
    return user


@pytest.fixture
def regular_client(api_client, regular_user):
    # force_login() (real session, not just DRF-level auth) is required so that
    # GUIRouter._wrap()'s login-gate — which reads request.user on the raw Django
    # request, before DRF's own auth even runs — also sees the user as logged in.
    api_client.force_login(user=regular_user)
    api_client.force_authenticate(user=regular_user)
    return api_client


@pytest.fixture
def manager_client(api_client, manager_user):
    api_client.force_login(user=manager_user)
    api_client.force_authenticate(user=manager_user)
    return api_client


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_login(user=admin_user)
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def auth_client_regular(api_client, regular_user):
    api_client.force_login(user=regular_user)
    api_client.force_authenticate(user=regular_user)
    return api_client


# ── model fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def supplier(db):
    from demo.models import Supplier
    return Supplier.objects.create(
        company_name='Acme Inc',
        tax_code='AC1234567890',
        active=True,
    )


@pytest.fixture
def purchase_request(db, supplier):
    # Named purchase_request (not `request`) to avoid shadowing pytest's builtin
    # `request` fixture, which every test implicitly has access to.
    from demo.models import Request
    return Request.objects.create(
        title='Server purchase',
        description='Infrastructure renewal',
        budget='5000.00',
        status=Request.Status.DRAFT,
        supplier=supplier,
    )


@pytest.fixture
def attachment(db, purchase_request):
    from demo.models import Attachment
    from django.core.files.base import ContentFile
    a = Attachment(request=purchase_request, description='Test document')
    a.file.save('test.txt', ContentFile(b'test content'))
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
