"""Default list filters (sebastian.default_filter) and user-dependent metavalues (sebastian.filters)."""
from types import SimpleNamespace

import django_filters
import pytest
from django.test import RequestFactory, override_settings

from sebastian.filters import MetaModelChoiceFilter

GUI = {'HTTP_ACCEPT': 'text/html'}
HTMX = {**GUI, 'HTTP_HX_REQUEST': 'true'}
REQUESTS = '/gui/requests/'
DECLARED = 'status=draft&ordering=-budget'     # demo RequestViewSet.Sebastian.default_filter


def _menu_items(client):
    r = client.get('/api/menu/', HTTP_ACCEPT='application/json')
    return {str(i['label']) + '@' + str(g['label']): i
            for g in r.data['menu_groups'] for i in g['items'] if not i.get('divider')}


@pytest.mark.django_db
class TestDefaultFilter:
    def test_redirect_to_declared_default(self, auth_client):
        r = auth_client.get(REQUESTS + '?_filter=default', **GUI)
        assert r.status_code == 302
        assert r['Location'] == f'{REQUESTS}?{DECLARED}'

    def test_htmx_also_redirected(self, auth_client):
        # htmx follows the redirect and pushes the final URL
        r = auth_client.get(REQUESTS + '?_filter=default', **HTMX)
        assert r.status_code == 302 and r['Location'] == f'{REQUESTS}?{DECLARED}'

    def test_no_default_declared(self, auth_client):
        r = auth_client.get('/gui/suppliers/?_filter=default', **GUI)
        assert r.status_code == 302 and r['Location'] == '/gui/suppliers/'

    def test_api_ignores_filter_param(self, auth_client):
        r = auth_client.get('/api/requests/?_filter=default', HTTP_ACCEPT='application/json')
        assert r.status_code == 200

    def test_save_includes_ordering_and_drops_page(self, auth_client):
        r = auth_client.post(REQUESTS + 'default-filter/', {
            'op': 'save', 'status': 'approved', 'ordering': 'title', 'page': '3', 'supplier': '',
        })
        assert r.status_code == 302 and r['Location'] == REQUESTS + '?_filter=default'
        r = auth_client.get(REQUESTS + '?_filter=default', **GUI)
        assert r['Location'] == f'{REQUESTS}?status=approved&ordering=title'

    def test_saved_empty_filter_means_all(self, auth_client):
        auth_client.post(REQUESTS + 'default-filter/', {'op': 'save'})
        assert auth_client.get(REQUESTS + '?_filter=default', **GUI)['Location'] == REQUESTS

    def test_reset_restores_declared(self, auth_client):
        auth_client.post(REQUESTS + 'default-filter/', {'op': 'save', 'status': 'approved'})
        auth_client.post(REQUESTS + 'default-filter/', {'op': 'reset'})
        r = auth_client.get(REQUESTS + '?_filter=default', **GUI)
        assert r['Location'] == f'{REQUESTS}?{DECLARED}'

    def test_own_default_on_list_without_declared_default(self, auth_client):
        html = auth_client.get('/gui/suppliers/', **GUI).content.decode()
        assert 'Save as default' in html and '>Default<' not in html.replace('\n', '')
        r = auth_client.post('/gui/suppliers/default-filter/', {'op': 'save', 'active': 'true'})
        assert r['Location'] == '/gui/suppliers/?_filter=default'
        assert auth_client.get('/gui/suppliers/?_filter=default', **GUI)['Location'] == \
            '/gui/suppliers/?active=true'
        html = auth_client.get('/gui/suppliers/', **GUI).content.decode()
        assert 'href="/gui/suppliers/?_filter=default"' in html and 'Restore default' in html
        auth_client.post('/gui/suppliers/default-filter/', {'op': 'reset'})
        assert auth_client.get('/gui/suppliers/?_filter=default', **GUI)['Location'] == '/gui/suppliers/'

    def test_bad_op(self, auth_client):
        r = auth_client.post(REQUESTS + 'default-filter/', {'op': 'nope'})
        assert r.status_code == 400

    @override_settings(SEBASTIAN={'DEFAULT_FILTER_STORE': None})
    def test_no_store(self, auth_client):
        html = auth_client.get(REQUESTS, **GUI).content.decode()
        assert 'Save as default' not in html and '?_filter=default' in html
        assert auth_client.post(REQUESTS + 'default-filter/', {'op': 'save'}).status_code == 404

    def test_filter_menu(self, auth_client):
        html = auth_client.get(REQUESTS, **GUI).content.decode()
        assert f'href="{REQUESTS}?_filter=default"' in html
        assert 'Save as default' in html and 'Restore default' not in html
        auth_client.post(REQUESTS + 'default-filter/', {'op': 'save', 'status': 'approved'})
        assert 'Restore default' in auth_client.get(REQUESTS, **GUI).content.decode()

    @override_settings(SEBASTIAN={'DEFAULT_FILTER_STORE': None})
    def test_filter_menu_without_any_default(self, auth_client):
        html = auth_client.get('/gui/suppliers/', **GUI).content.decode()
        assert 'href="/gui/suppliers/?_filter=default"' not in html and 'Save as default' not in html
        assert 'dropdown-toggle-split' in html          # Filter + Clear still there

    def test_menu_items_open_the_default(self, auth_client):
        items = _menu_items(auth_client)
        assert items['List@Requests']['url'] == REQUESTS + '?_filter=default'
        # any list: the user may have saved an own default filter
        assert items['List@Suppliers']['url'] == '/gui/suppliers/?_filter=default'
        assert items['New@Requests']['url'] == REQUESTS + 'new/'

    def test_menu_active_item_ignores_query(self, auth_client):
        r = auth_client.get('/api/menu/', HTTP_ACCEPT='application/json',
                            HTTP_HX_CURRENT_URL=f'http://testserver{REQUESTS}?status=draft')
        group = next(g for g in r.data['menu_groups'] if g['label'] == 'Requests')
        assert next(i for i in group['items'] if i.get('label') == 'List')['active']


# ── metavalues ────────────────────────────────────────────────────────────────

def _filterset(user):
    from demo.models import Request, Supplier

    class F(django_filters.FilterSet):
        supplier = MetaModelChoiceFilter(
            queryset=Supplier.objects.all(),
            metavalues={'my_supplier': ('My supplier', lambda request: request.user.supplier)},
        )

        class Meta:
            model = Request
            fields = ['supplier']

    def build(value):
        request = RequestFactory().get('/', {'supplier': value})
        request.user = user
        return F(data=request.GET, queryset=Request.objects.all(), request=request)
    return build


@pytest.mark.django_db
class TestMetaModelChoiceFilter:
    def _data(self):
        from demo.models import Request, Supplier
        a = Supplier.objects.create(company_name='A', tax_code='A1')
        b = Supplier.objects.create(company_name='B', tax_code='B1')
        ra = Request.objects.create(title='ra', budget=1, supplier=a)
        rb = Request.objects.create(title='rb', budget=1, supplier=b)
        return a, b, ra, rb

    def test_metavalue_resolved_for_the_user(self):
        a, _b, ra, _rb = self._data()
        fs = _filterset(SimpleNamespace(supplier=a))('my_supplier')
        assert fs.is_valid(), fs.errors
        assert list(fs.qs) == [ra]

    def test_none_means_no_filter(self):
        self._data()
        fs = _filterset(SimpleNamespace(supplier=None))('my_supplier')
        assert fs.is_valid() and fs.qs.count() == 2

    def test_plain_values_still_work(self):
        _a, b, _ra, rb = self._data()
        fs = _filterset(SimpleNamespace(supplier=None))(str(b.pk))
        assert list(fs.qs) == [rb]

    def test_metavalues_listed_first(self):
        self._data()
        choices = list(_filterset(SimpleNamespace(supplier=None))('').form.fields['supplier'].choices)
        assert [str(label) for _v, label in choices[:2]] == ['---------', 'My supplier']
        assert len(choices) == 4
