"""Home page plugins (sebastian.home): registry, autodiscovery, rendering, MenuLinksPlugin."""
import logging

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from sebastian import home
from sebastian.home import HomePlugin, MenuLinksPlugin, register_home_plugin

GUI = {'HTTP_ACCEPT': 'text/html'}


@pytest.fixture
def registry():
    """Empty registry, autodiscovery off; the previous state is restored afterwards."""
    saved, saved_discovered = list(home._registry), home._discovered
    home._registry.clear()
    home._discovered = True
    yield home._registry
    home._registry[:] = saved
    home._discovered = saved_discovered


def _plugin(name, slot='left', order=100, **attrs):
    return type(name, (HomePlugin,), {'name': name, 'slot': slot, 'order': order, **attrs})


class TestRegistry:
    def test_order_within_slot_then_registration(self, registry):
        for name, order in (('b', 20), ('a', 10), ('c', 20)):
            register_home_plugin(_plugin(name, order=order))
        assert [p.name for p in home.get_home_plugins()] == ['a', 'b', 'c']

    def test_duplicate_name(self, registry):
        register_home_plugin(_plugin('x'))
        with pytest.raises(ImproperlyConfigured):
            register_home_plugin(_plugin('x'))

    def test_decorator_with_arguments(self, registry):
        @register_home_plugin(slot='right', order=5)
        class P(HomePlugin):
            pass
        plugin, = registry
        assert (plugin.slot, plugin.order) == ('right', 5)
        assert plugin.name.endswith('.P')       # default name: module + class

    def test_autodiscover_imports_app_plugins(self, registry, monkeypatch):
        import sys
        import demo
        # import demo.plugins afresh, so that its classes register again
        monkeypatch.delitem(sys.modules, 'demo.plugins', raising=False)
        monkeypatch.delattr(demo, 'plugins', raising=False)
        home._discovered = False
        home.get_home_plugins()
        assert {p.name for p in registry} == {'demo.suppliers', 'demo.requests'}
        home.get_home_plugins()                 # once only: no duplicate registration

    @override_settings(SEBASTIAN={'HOME_AUTODISCOVER': False})
    def test_autodiscover_off(self, registry):
        home._discovered = False
        assert home.get_home_plugins() == []


@pytest.mark.django_db
class TestHomePage:
    def test_two_slots(self, registry, auth_client):
        register_home_plugin(_plugin('one', 'left', title='Left panel'))
        register_home_plugin(_plugin('two', 'right', title='Right panel'))
        html = auth_client.get('/gui/', **GUI).content.decode()
        assert 'Left panel' in html and 'Right panel' in html
        assert html.index('data-plugin="one"') < html.index('data-plugin="two"')

    def test_no_plugins_shows_entries(self, registry, auth_client):
        html = auth_client.get('/gui/', **GUI).content.decode()
        assert 'sb-home-plugin' not in html
        assert 'Supplier' in html

    def test_permission_hides_plugin(self, registry, auth_client_regular):
        register_home_plugin(_plugin('admins', title='Admins only',
                                     permission=lambda request, obj: request.user.is_superuser))
        html = auth_client_regular.get('/gui/', **GUI).content.decode()
        assert 'Admins only' not in html
        assert 'Nothing available for your profile.' in html

    def test_unknown_slot_goes_to_first(self, registry, auth_client, caplog):
        register_home_plugin(_plugin('odd', 'sidebar', title='Odd panel'))
        with caplog.at_level(logging.WARNING, logger='sebastian.home'):
            html = auth_client.get('/gui/', **GUI).content.decode()
        assert 'Odd panel' in html
        assert 'unknown slot' in caplog.text

    def test_failing_plugin_shows_error_panel(self, registry, auth_client, caplog):
        def boom(self, request, home):
            raise RuntimeError('boom')
        register_home_plugin(_plugin('bad', title='Bad panel', get_context=boom))
        register_home_plugin(_plugin('good', title='Good panel'))
        with caplog.at_level(logging.ERROR, logger='sebastian.home'):
            r = auth_client.get('/gui/', **GUI)
        html = r.content.decode()
        assert r.status_code == 200
        assert 'This panel could not be loaded.' in html and 'Good panel' in html
        assert 'boom' in caplog.text

    def test_template_and_context(self, registry, auth_client, tmp_path, settings):
        (tmp_path / 'p.html').write_text('<b>{{ answer }} in {{ home.pack }}</b>')
        settings.TEMPLATES = [{**settings.TEMPLATES[0],
                               'DIRS': [tmp_path, *settings.TEMPLATES[0]['DIRS']]}]
        register_home_plugin(_plugin('ctx', template='p.html',
                                     get_context=lambda self, request, home: {'answer': 42}))
        html = auth_client.get('/gui/', **GUI).content.decode()
        assert '<b>42 in htmx</b>' in html


@pytest.mark.django_db
class TestMenuLinksPlugin:
    @staticmethod
    def _suppliers():
        register_home_plugin(type('S', (MenuLinksPlugin,), {
            'name': 's', 'title': 'Suppliers', 'menu_label': 'Suppliers'}))

    def test_links_of_the_menu(self, registry, auth_client):
        self._suppliers()
        html = auth_client.get('/gui/', **GUI).content.decode()
        assert 'href="/gui/suppliers/"' in html
        assert 'href="/gui/suppliers/new/"' in html

    def test_links_follow_menu_permissions(self, registry, auth_client_regular):
        # New requires manager or admin (as in the menu)
        self._suppliers()
        html = auth_client_regular.get('/gui/', **GUI).content.decode()
        assert 'href="/gui/suppliers/"' in html
        assert 'href="/gui/suppliers/new/"' not in html

    def test_items_order_spacing_and_primary(self, registry, auth_client):
        register_home_plugin(type('R', (MenuLinksPlugin,), {
            'name': 'r', 'title': 'Requests', 'menu_label': 'Requests',
            'items': ('-', 'Settings', '-', '-', 'Missing', 'New', '-'),
            'primary_items': ('New',)}))
        html = auth_client.get('/gui/', **GUI).content.decode()
        links = html[html.index('sb-home-links'):]
        assert links.index('Settings') < links.index('New')
        assert 'href="/gui/requests/"' not in links          # List not selected
        assert links.count('<div class="mt-2"></div>') == 1  # no leading/trailing/double spacing
        new_link = links[links.index('href="/gui/requests/new/"'):][:120]
        assert 'btn-primary' in new_link

    def test_unknown_menu_renders_nothing(self, registry, auth_client):
        register_home_plugin(type('U', (MenuLinksPlugin,), {
            'name': 'u', 'title': 'Unknown', 'menu_label': 'Nope'}))
        html = auth_client.get('/gui/', **GUI).content.decode()
        assert 'Unknown' in html and '<a href' not in html[html.index('sb-home-links'):][:200]
