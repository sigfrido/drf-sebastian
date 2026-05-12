"""
Tests for Phase 7: template packs, skins, icon tag, and include_resource tag.
"""
import pytest
from django.test import override_settings
from django.template import Context, Template


GUI  = {'HTTP_ACCEPT': 'text/html'}
HTMX = {**GUI, 'HTTP_HX_REQUEST': 'true'}

PLAIN_SETTINGS = override_settings(SEBASTIAN={
    'TEMPLATE_PACK': 'plain',
    'SKIN': 'bootstrap5-bi',
    'HIDE_UNAUTHORIZED_ACTIONS': False,
})


# ---------------------------------------------------------------------------
# Pack context variables
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPackContext:
    def test_pack_name_in_response(self, auth_client):
        r = auth_client.get('/gui/fornitori/', **HTMX)
        assert r.status_code == 200
        # The response is rendered HTML; pack_name drives template selection
        # — if we got here without TemplateDoesNotExist, the pack resolved correctly
        assert b'Fornitor' in r.content or b'fornitor' in r.content.lower()

    def test_htmx_is_default_pack(self, auth_client):
        """Default pack renders HTMX HTML."""
        r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'hx-target' in r.content.lower()

    def test_bootstrap5_skin_fragment_included(self, auth_client):
        """Skin fragment CDN links appear in the full-page response."""
        r = auth_client.get('/gui/fornitori/', **GUI)
        assert b'bootstrap@5.3.3' in r.content
        assert b'bootstrap-icons' in r.content


# ---------------------------------------------------------------------------
# {% icon %} template tag
# ---------------------------------------------------------------------------

class TestIconTag:
    def _render(self, template_str, skin='bootstrap5-bi'):
        t = Template('{% load sebastian_tags %}' + template_str)
        c = Context({'skin_name': skin})
        return t.render(c)

    def test_icon_renders_bootstrap_icon(self):
        html = self._render('{% icon "plus" %}')
        assert html == '<i class="bi bi-plus"></i>'

    def test_icon_with_extra_class(self):
        html = self._render('{% icon "table" "me-1" %}')
        assert html == '<i class="bi bi-table me-1"></i>'

    def test_icon_with_variable_name(self):
        t = Template('{% load sebastian_tags %}{% icon icon_name %}')
        c = Context({'skin_name': 'bootstrap5-bi', 'icon_name': 'trash'})
        assert t.render(c) == '<i class="bi bi-trash"></i>'

    def test_icon_fontawesome_skin(self):
        html = self._render('{% icon "trash" %}', skin='tailwind-fa')
        assert html == '<i class="fa-solid fa-trash"></i>'

    def test_icon_unknown_skin_defaults_to_bi(self):
        html = self._render('{% icon "star" %}', skin='someotherskin')
        assert html == '<i class="bi bi-star"></i>'


# ---------------------------------------------------------------------------
# {% include_resource %} template tag
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIncludeResourceTag:
    def test_include_resource_renders_menu(self, auth_client):
        """include_resource can call the menu endpoint and return HTML."""
        t = Template('{% load sebastian_tags %}{% include_resource url %}')
        # Simulate a request context by calling through the test client
        r = auth_client.get('/gui/', **GUI)
        assert r.status_code == 200
        # The plain pack base.html uses include_resource for the menu —
        # smoke-test it by switching to plain pack
        with PLAIN_SETTINGS:
            r2 = auth_client.get('/gui/', **GUI)
            assert r2.status_code == 200
            assert b'Sebastian' in r2.content

    def test_include_resource_empty_url_returns_empty(self):
        t = Template('{% load sebastian_tags %}{% include_resource url %}')
        c = Context({'url': '', 'request': None})
        assert t.render(c) == ''

    def test_include_resource_bad_url_returns_comment(self):
        from django.test import RequestFactory
        t = Template('{% load sebastian_tags %}{% include_resource url %}')
        req = RequestFactory().get('/')
        c = Context({'url': '/gui/nonexistent-url-xyz/', 'request': req})
        result = t.render(c)
        assert result.startswith('<!-- include_resource')


# ---------------------------------------------------------------------------
# Plain pack — no HTMX attributes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlainPack:
    def test_plain_list_has_no_hx_get(self, auth_client, fornitore):
        with PLAIN_SETTINGS:
            r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'hx-get' not in r.content
        assert b'hx-post' not in r.content
        assert b'Acme Srl' in r.content

    def test_plain_list_filter_uses_plain_form(self, auth_client):
        with PLAIN_SETTINGS:
            r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'method="get"' in r.content

    def test_plain_detail_renders_inline_directly(self, auth_client, richiesta):
        """Inline section is embedded server-side (no hx-trigger=load)."""
        with PLAIN_SETTINGS:
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **GUI)
        assert r.status_code == 200
        assert b'hx-trigger' not in r.content
        # inline section header still present
        assert b'Allegati' in r.content

    def test_plain_form_uses_method_post(self, auth_client, fornitore):
        with PLAIN_SETTINGS:
            r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/edit/', **GUI)
        assert r.status_code == 200
        assert b'method="post"' in r.content
        # Form posts to /edit/ URL (mapped to partial_update) — no _method override needed
        assert b'/edit/' in r.content

    def test_plain_home_renders(self, auth_client):
        with PLAIN_SETTINGS:
            r = auth_client.get('/gui/', **GUI)
        assert r.status_code == 200
        assert b'Moduli disponibili' in r.content
        assert b'hx-' not in r.content


# ---------------------------------------------------------------------------
# Sebastian.templates override still beats pack
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestViewsetTemplateOverride:
    def test_override_beats_pack(self, auth_client, fornitore, settings, tmp_path):
        """Sebastian.templates = {'list': '...'} takes precedence over the active pack."""
        from selco.views import FornitoreViewSet
        original = getattr(getattr(FornitoreViewSet, 'Sebastian', None), 'templates', {})
        # Use the existing flat legacy template as the override target
        try:
            # Ensure active pack is 'plain'
            with PLAIN_SETTINGS:
                r = auth_client.get('/gui/fornitori/', **HTMX)
                assert r.status_code == 200
                assert b'Acme Srl' in r.content
                # plain does not use HTMX
                assert b'hx-target' not in r.content
                FornitoreViewSet.Sebastian.templates = {'list': 'sebastian/htmx/list.html'}
                r = auth_client.get('/gui/fornitori/', **HTMX)
                assert r.status_code == 200
                assert b'Acme Srl' in r.content
                assert b'hx-target' in r.content
        finally:
            FornitoreViewSet.Sebastian.templates = original
