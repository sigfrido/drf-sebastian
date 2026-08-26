"""
Login gate, login/logout flow, and the username shown in the navbar.
"""
import pytest


@pytest.mark.django_db
def test_anonymous_gui_request_redirects_to_login(api_client):
    r = api_client.get('/gui/', HTTP_ACCEPT='text/html')
    assert r.status_code == 302
    assert r['Location'] == '/gui/login/?next=/gui/'


@pytest.mark.django_db
def test_anonymous_gui_subpage_redirects_to_login_with_next(api_client):
    r = api_client.get('/gui/requests/', HTTP_ACCEPT='text/html')
    assert r.status_code == 302
    assert r['Location'] == '/gui/login/?next=/gui/requests/'


@pytest.mark.django_db
def test_login_page_renders(api_client):
    r = api_client.get('/gui/login/')
    assert r.status_code == 200
    assert b'<form method="post">' in r.content
    assert b'name="username"' in r.content
    assert b'name="password"' in r.content


@pytest.mark.django_db
def test_login_with_valid_credentials_redirects(api_client, regular_user):
    r = api_client.post('/gui/login/', {'username': 'regular', 'password': 'password'})
    assert r.status_code == 302
    assert r['Location'] == '/gui/'


@pytest.mark.django_db
def test_login_with_invalid_credentials_shows_error(api_client, regular_user):
    r = api_client.post('/gui/login/', {'username': 'regular', 'password': 'wrong'})
    assert r.status_code == 200
    assert b'Invalid username or password.' in r.content


@pytest.mark.django_db
def test_login_then_next_param_reaches_original_page(api_client, regular_user):
    api_client.post('/gui/login/', {
        'username': 'regular', 'password': 'password', 'next': '/gui/requests/',
    })
    r = api_client.get('/gui/requests/', HTTP_ACCEPT='text/html')
    assert r.status_code == 200


@pytest.mark.django_db
def test_username_shown_in_navbar_when_authenticated(auth_client):
    r = auth_client.get('/gui/', HTTP_ACCEPT='text/html')
    assert r.status_code == 200
    assert b'admin' in r.content
    assert b'Logout' in r.content


@pytest.mark.django_db
def test_logout_control_is_a_post_form_not_a_get_link(auth_client):
    """Regression: Django's LogoutView only accepts POST (since Django 5.0) —
    a plain <a href> would 405 the moment someone actually clicks it."""
    r = auth_client.get('/gui/', HTTP_ACCEPT='text/html')
    assert r.status_code == 200
    assert b'<form method="post" action="/gui/logout/"' in r.content
    assert b'csrfmiddlewaretoken' in r.content
    assert b'<a href="/gui/logout/"' not in r.content


@pytest.mark.django_db
def test_username_not_shown_on_login_page(api_client):
    r = api_client.get('/gui/login/')
    assert b'Logout' not in r.content


@pytest.mark.django_db
def test_logout_redirects_to_login(auth_client):
    r = auth_client.post('/gui/logout/')
    assert r.status_code == 302
    r2 = auth_client.get('/gui/', HTTP_ACCEPT='text/html')
    assert r2.status_code == 302
    assert r2['Location'].startswith('/gui/login/')
