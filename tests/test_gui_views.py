"""
Integration tests for the /gui/ HTML endpoints.
Covers: list, detail, form rendering, form submit (create/update/delete),
HTMX fragment detection, and nested inline behaviour.
"""
import pytest
from django.test import override_settings


GUI = {'HTTP_ACCEPT': 'text/html'}
HTMX = {**GUI, 'HTTP_HX_REQUEST': 'true'}

SEBASTAN_HTMX = {
    'SEBASTIAN': {
        'TEMPLATE_PACK': 'htmx',
    }
}


@pytest.mark.django_db
class TestHome:
    def test_home_returns_html(self, auth_client):
        r = auth_client.get('/gui/', **GUI)
        assert r.status_code == 200
        assert b'Sebastian' in r.content

    def test_home_lists_registered_viewsets(self, auth_client):
        r = auth_client.get('/gui/', **GUI)
        assert b'Fornitor' in r.content  # label from verbose_name_plural


@pytest.mark.django_db
class TestFornitoreGUIList:
    def test_list_returns_html(self, auth_client, fornitore):
        r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'Acme Srl' in r.content

    def test_htmx_request_returns_fragment_only(self, auth_client, fornitore):
        r = auth_client.get('/gui/fornitori/', **HTMX)
        assert r.status_code == 200
        # Fragment must NOT include the full page shell
        assert b'<!doctype' not in r.content.lower()
        assert b'Acme Srl' in r.content

    def test_full_page_includes_bootstrap(self, auth_client):
        r = auth_client.get('/gui/fornitori/', **GUI)
        assert b'bootstrap' in r.content.lower()

    def test_rows_have_consistent_column_count(self, auth_client, db):
        """Regression: rows with null FK must not have fewer <td> than the header."""
        from selco.models import Fornitore, Richiesta
        Richiesta.objects.create(titolo='No fornitore', descrizione='', budget='0',
                                  stato=Richiesta.Stato.BOZZA)
        Richiesta.objects.create(titolo='Con fornitore', descrizione='', budget='0',
                                  stato=Richiesta.Stato.BOZZA,
                                  fornitore=Fornitore.objects.create(
                                      ragione_sociale='X', codice_fiscale='11111111111'))
        r = auth_client.get('/gui/richieste/', **HTMX)
        assert r.status_code == 200
        import re
        rows = re.findall(rb'<tr>(.*?)</tr>', r.content, re.DOTALL)
        td_counts = [len(re.findall(rb'<td', row)) for row in rows if re.search(rb'<td', row)]
        assert len(set(td_counts)) == 1, f'Righe con numero <td> diverso: {td_counts}'


@pytest.mark.django_db
class TestFornitoreGUIForms:
    def test_create_form_returns_html(self, auth_client):
        r = auth_client.get('/gui/fornitori/new/', **HTMX)
        assert r.status_code == 200
        assert b'ragione_sociale' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_create_form_has_absolute_submit_url(self, auth_client):
        r = auth_client.get('/gui/fornitori/new/', **HTMX)
        assert b'hx-post="/gui/fornitori/"' in r.content

    def test_create_redirects_to_detail(self, auth_client):
        r = auth_client.post('/gui/fornitori/', {
            'ragione_sociale': 'Nuovo Srl',
            'codice_fiscale': '88888888888',
            'attivo': True,
        }, **HTMX)
        assert r.status_code == 200
        assert 'HX-Redirect' in r
        assert '/gui/fornitori/' in r['HX-Redirect']

    def test_update_form_prefills_data(self, auth_client, fornitore):
        r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'Acme Srl' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_update_form_has_absolute_submit_url(self, auth_client, fornitore):
        r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/edit/', **HTMX)
        expected = f'hx-patch="/gui/fornitori/{fornitore.pk}/"'.encode()
        assert expected in r.content

    def test_update_redirects_to_detail(self, auth_client, fornitore):
        r = auth_client.patch(
            f'/gui/fornitori/{fornitore.pk}/',
            {'ragione_sociale': 'Acme SpA', 'codice_fiscale': '12345678901', 'attivo': True},
            **HTMX,
        )
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/fornitori/{fornitore.pk}/'

    @override_settings(**SEBASTAN_HTMX)
    def test_create_form_has_cancel_button(self, auth_client):
        r = auth_client.get('/gui/fornitori/new/', **HTMX)
        assert b'hx-get="/gui/fornitori/"' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_update_form_has_cancel_button(self, auth_client, fornitore):
        r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/edit/', **HTMX)
        expected = f'hx-get="/gui/fornitori/{fornitore.pk}/"'.encode()
        assert expected in r.content

    def test_create_invalid_rerenders_form_with_errors(self, auth_client):
        r = auth_client.post('/gui/fornitori/', {
            'ragione_sociale': '',      # required — triggers error
            'codice_fiscale': 'x',
        }, **HTMX)
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'ragione_sociale' in r.content   # form is re-rendered
        assert b'invalid-feedback' in r.content  # field-level error shown

    def test_update_invalid_rerenders_form_with_errors(self, auth_client, fornitore):
        r = auth_client.patch(
            f'/gui/fornitori/{fornitore.pk}/',
            {'ragione_sociale': '', 'codice_fiscale': '12345678901'},
            **HTMX,
        )
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'ragione_sociale' in r.content
        assert b'invalid-feedback' in r.content

    def test_inline_create_invalid_rerenders_form(self, auth_client, richiesta):
        r = auth_client.post(
            f'/gui/richieste/{richiesta.pk}/allegati/',
            {'descrizione': ''},   # file is required — triggers error
            **HTMX,
        )
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'invalid-feedback' in r.content


@pytest.mark.django_db
class TestFornitoreGUIDelete:
    def test_delete_returns_updated_list_html(self, auth_client, fornitore):
        r = auth_client.delete(f'/gui/fornitori/{fornitore.pk}/', **HTMX)
        assert r.status_code == 200
        # Response is the updated list, not a redirect
        assert 'HX-Location' not in r
        assert 'HX-Redirect' not in r

    @override_settings(**SEBASTAN_HTMX)
    def test_delete_button_links_to_confirm_url(self, auth_client, fornitore):
        """Delete button in list uses hx-get to load the confirm modal."""
        r = auth_client.get('/gui/fornitori/', **HTMX)
        expected = f'/gui/fornitori/{fornitore.pk}/delete/'.encode()
        assert expected in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_delete_confirm_page_contains_str(self, auth_client, fornitore):
        """GET /delete/ shows confirmation modal with the object's __str__ in the prompt."""
        r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/delete/', **HTMX)
        assert r.status_code == 200
        assert b'sb-confirm-modal' in r.content
        assert str(fornitore).encode() in r.content


@pytest.mark.django_db
class TestFornitoreGUIDetail:
    def test_detail_returns_html(self, auth_client, fornitore):
        r = auth_client.get(f'/gui/fornitori/{fornitore.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Acme Srl' in r.content


@pytest.mark.django_db
class TestAllegatoInlineGUI:
    def test_inline_list_loads_as_fragment(self, auth_client, richiesta, allegato):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/', **HTMX
        )
        assert r.status_code == 200
        assert b'Documento test' in r.content
        assert b'<!doctype' not in r.content.lower()

    @override_settings(**SEBASTAN_HTMX)
    def test_inline_create_form_targets_inline_div(self, auth_client, richiesta):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/new/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-allegati"' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_inline_create_uses_absolute_url(self, auth_client, richiesta):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/new/', **HTMX
        )
        expected = f'hx-post="/gui/richieste/{richiesta.pk}/allegati/"'.encode()
        assert expected in r.content

    def test_inline_create_returns_updated_list(self, auth_client, richiesta):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('d.txt', b'x', content_type='text/plain')
        r = auth_client.post(
            f'/gui/richieste/{richiesta.pk}/allegati/',
            {'descrizione': 'Nuovo', 'file': f},
            format='multipart',
            **HTMX,
        )
        assert r.status_code == 200
        assert b'<!doctype' not in r.content.lower()
        assert b'Nuovo' in r.content

    def test_inline_delete_returns_updated_list(self, auth_client, richiesta, allegato):
        r = auth_client.delete(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/', **HTMX
        )
        assert r.status_code == 200
        assert b'Documento test' not in r.content
        assert b'<!doctype' not in r.content.lower()

    @override_settings(**SEBASTAN_HTMX)
    def test_inline_edit_form_targets_inline_div(self, auth_client, richiesta, allegato):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/edit/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-allegati"' in r.content

    def test_edit_form_mostra_filename_esistente(self, auth_client, richiesta, allegato):
        """In edit mode, il form mostra il nome del file attuale e non lo richiede."""
        import re
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/edit/', **HTMX
        )
        assert r.status_code == 200
        filename = allegato.file.name.split('/')[-1].encode()
        assert filename in r.content                # filename attuale visibile
        file_input = re.search(rb'<input[^>]+name="file"[^>]*>', r.content)
        assert file_input and b'required' not in file_input.group(0)
        assert b'Seleziona un file per' in r.content  # hint sostituzione

    def test_edit_senza_nuovo_file_mantiene_file_esistente(self, auth_client, richiesta, allegato):
        """PATCH senza file field → file esistente preservato."""
        r = auth_client.patch(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/',
            {'descrizione': 'Descrizione aggiornata'},
            **HTMX,
        )
        assert r.status_code == 200
        allegato.refresh_from_db()
        assert allegato.file.name  # file ancora presente
        assert allegato.descrizione == 'Descrizione aggiornata'

    def test_download_button_visible_in_inline_list(self, auth_client, richiesta, allegato):
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/allegati/', **HTMX)
        assert r.status_code == 200
        assert f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/download/'.encode() in r.content

    def test_download_returns_file(self, auth_client, richiesta, allegato):
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/download/')
        assert r.status_code == 200
        assert 'attachment' in r.get('Content-Disposition', '')

    def test_inline_update_returns_updated_list(self, auth_client, richiesta, allegato):
        r = auth_client.patch(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/',
            {'descrizione': 'Aggiornato'},
            **HTMX,
        )
        assert r.status_code == 200
        assert b'<!doctype' not in r.content.lower()
        assert b'Aggiornato' in r.content


@pytest.mark.django_db
class TestRichiestaActionsGUI:

    def setUp(self):
        pass

    def test_gui_invia_restituisce_redirect_al_detail(self, auth_client, richiesta):
        r = auth_client.post(
            f'/gui/richieste/{richiesta.pk}/invia/',
            {'motivazione': 'Nel budget approvato.', 'verifica': 'true'},
            **HTMX,
        )
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/richieste/{richiesta.pk}/'
        richiesta.refresh_from_db()
        assert richiesta.stato == 'inviata'
        assert richiesta.motivazione == 'Nel budget approvato.'

    @override_settings(**SEBASTAN_HTMX)
    def test_gui_invia_senza_motivazione_restituisce_400(self, auth_client, richiesta):
        """Validation error → 400 with X-Sebastian-Form-Error and re-rendered modal."""
        r = auth_client.post(
            f'/gui/richieste/{richiesta.pk}/invia/',
            {'motivazione': '', 'verifica': 'true'},
            **HTMX,
        )
        assert r.status_code == 400
        assert r['X-Sebastian-Form-Error'] == 'true'
        assert b'sb-confirm-form' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_gui_invia_senza_verifica_restituisce_400(self, auth_client, richiesta):
        """verifica checkbox unchecked → validation error."""
        r = auth_client.post(
            f'/gui/richieste/{richiesta.pk}/invia/',
            {'motivazione': 'ok'},  # verifica not sent → False
            **HTMX,
        )
        assert r.status_code == 400
        assert r['X-Sebastian-Form-Error'] == 'true'

    @override_settings(**SEBASTAN_HTMX)
    def test_gui_invia_get_restituisce_modal(self, auth_client, richiesta):
        """GET /invia/confirm/ → modal HTML fragment with serializer fields."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/invia/confirm/', **HTMX)
        assert r.status_code == 200
        assert b'sb-confirm-modal' in r.content
        assert b'sb-confirm-form' in r.content
        assert b'motivazione' in r.content
        assert b'verifica' in r.content

    def test_gui_approva_flow_completo(self, auth_client, richiesta):
        """Bozza → invia → approva: redirect al detail, stato finale approvata."""
        auth_client.post(
            f'/gui/richieste/{richiesta.pk}/invia/',
            {'motivazione': 'ok', 'verifica': 'true'},
            **HTMX,
        )
        r = auth_client.post(f'/gui/richieste/{richiesta.pk}/approva/', **HTMX)
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/richieste/{richiesta.pk}/'
        richiesta.refresh_from_db()
        assert richiesta.stato == 'approvata'

    def test_gui_approva_su_bozza_mostra_errore_html(self, auth_client, richiesta):
        """400 su approva di bozza → risposta HTML con messaggio di errore."""
        r = auth_client.post(f'/gui/richieste/{richiesta.pk}/approva/', **HTMX)
        assert r.status_code == 400
        assert b'alert' in r.content
        assert 'inviate'.encode() in r.content  # messaggio dall'action

    def test_approva_button_nascosto_per_non_admin(self, regular_client, richiesta):
        """Non-staff: perm_is_admin fails → Approva hidden."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content

    def test_approva_button_nascosto_per_admin_su_bozza(self, auth_client, richiesta):
        """Admin on bozza: perm_is_admin passes but stato check fails → hidden."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content

    def test_approva_button_visibile_per_admin_su_inviata(self, auth_client, richiesta):
        """Admin on inviata: both callables pass → button visible."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' in r.content

    def test_invia_button_nascosto_dopo_invio(self, auth_client, richiesta):
        """Invia has permission=stato==BOZZA → hidden once stato changes."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Invia' not in r.content

    def test_invia_button_visibile_su_bozza(self, auth_client, richiesta):
        """Invia button visible when stato==BOZZA."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Invia' in r.content


@pytest.mark.django_db
class TestFieldGroupPermissions:
    def test_direzione_fields_readonly_for_non_admin(self, regular_client, richiesta):
        """Non-admin: edit_permission=perm_is_admin → direzione fields read-only in form."""
        r = regular_client.get(f'/gui/richieste/{richiesta.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'form-control-plaintext' in r.content
        assert b'name="note_direttore"' not in r.content

    def test_direzione_fields_editable_for_admin(self, auth_client, richiesta):
        """Admin: edit_permission passes → direzione fields rendered as inputs."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="note_direttore"' in r.content

    def test_hide_false_renders_disabled_button(self, regular_client, richiesta):
        """HIDE_UNAUTHORIZED_ACTIONS=False: unauthorized action rendered as disabled button."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' in r.content
        assert b'disabled' in r.content

    def test_permission_list_and_logic(self, auth_client, richiesta):
        """List of callables uses AND: admin+bozza fails the stato check → hidden."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content


@pytest.mark.django_db
class TestAppMenu:
    def test_menu_endpoint_returns_json(self, auth_client):
        r = auth_client.get('/api/menu/', HTTP_ACCEPT='application/json')
        assert r.status_code == 200
        assert 'menu_groups' in r.data
        labels = [g['label'] for g in r.data['menu_groups']]
        assert 'Fornitori' in labels
        assert 'Richieste' in labels

    def test_menu_endpoint_returns_html_fragment(self, auth_client):
        r = auth_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        # Fragment only — no full page shell
        assert b'<!doctype' not in r.content.lower()
        assert b'<ul' in r.content
        assert b'Fornitori' in r.content
        assert b'Richieste' in r.content

    def test_menu_items_present_for_admin(self, auth_client):
        r = auth_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'Elenco' in r.content
        assert b'Nuova' in r.content   # admin sees all items

    def test_menu_item_permission_hidden_for_non_admin(self, regular_client):
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'Richieste' in r.content   # group still visible
        assert b'Nuova' not in r.content   # item hidden (perm_is_admin fails)

    def test_menu_item_permission_disabled_for_non_admin(self, regular_client):
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'Nuova' in r.content
        assert b'disabled' in r.content

    @override_settings(**SEBASTAN_HTMX)
    def test_menu_active_item_via_hx_current_url(self, auth_client):
        r = auth_client.get(
            '/gui/menu/', **GUI,
            HTTP_HX_CURRENT_URL='http://testserver/gui/richieste/',
        )
        assert r.status_code == 200
        content = r.content.decode()
        # Parent group toggle must carry the active class
        assert 'nav-link dropdown-toggle active' in content
        # The matching dropdown item must also be active
        assert 'dropdown-item active' in content

    @override_settings(**SEBASTAN_HTMX)
    def test_base_template_loads_menu_via_htmx(self, auth_client):
        r = auth_client.get('/gui/richieste/', **GUI)
        assert r.status_code == 200
        assert b'hx-get' in r.content
        assert b'menu' in r.content   # hx-get points to the menu endpoint


@pytest.mark.django_db
class TestAPIBehaviour:
    """API endpoints always return JSON; detail includes inline data."""

    def test_api_list_returns_json_from_browser(self, auth_client):
        r = auth_client.get('/api/richieste/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')

    def test_api_detail_returns_json_from_browser(self, auth_client, richiesta):
        r = auth_client.get(f'/api/richieste/{richiesta.pk}/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')

    def test_api_menu_returns_json_from_browser(self, auth_client):
        r = auth_client.get('/api/menu/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')
        assert 'menu_groups' in r.data

    def test_api_detail_includes_inline_data(self, auth_client, richiesta, allegato):
        r = auth_client.get(f'/api/richieste/{richiesta.pk}/')
        assert r.status_code == 200
        assert 'allegati' in r.data
        assert len(r.data['allegati']) == 1
        assert r.data['allegati'][0]['id'] == allegato.pk

    def test_api_detail_inline_in_api_false_excluded(self, auth_client, richiesta):
        from selco.views import RichiestaViewSet
        inline_cls = RichiestaViewSet.Sebastian.inlines[0]
        original = inline_cls.inline_in_api
        try:
            inline_cls.inline_in_api = False
            r = auth_client.get(f'/api/richieste/{richiesta.pk}/')
            assert r.status_code == 200
            assert 'allegati' not in r.data
        finally:
            inline_cls.inline_in_api = original


@pytest.mark.django_db
class TestOrdering:
    """Ordering widget and queryset filter."""

    def test_ordering_widget_present_when_configured(self, auth_client):
        r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'sb-ordering' in r.content
        assert b'Ragione Sociale' in r.content

    def test_ordering_applies_to_queryset(self, auth_client):
        from selco.models import Fornitore
        Fornitore.objects.create(ragione_sociale='Zeta Srl',  codice_fiscale='11111111111', attivo=True)
        Fornitore.objects.create(ragione_sociale='Alpha Srl', codice_fiscale='22222222222', attivo=True)
        r = auth_client.get('/api/fornitori/?ordering=ragione_sociale')
        assert r.status_code == 200
        items = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        names = [item['ragione_sociale'] for item in items]
        assert names == sorted(names)

    def test_ordering_descending(self, auth_client):
        from selco.models import Fornitore
        Fornitore.objects.create(ragione_sociale='Zeta Srl',  codice_fiscale='11111111111', attivo=True)
        Fornitore.objects.create(ragione_sociale='Alpha Srl', codice_fiscale='22222222222', attivo=True)
        r = auth_client.get('/api/fornitori/?ordering=-ragione_sociale')
        assert r.status_code == 200
        items = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        names = [item['ragione_sociale'] for item in items]
        assert names == sorted(names, reverse=True)

    def test_ordering_rejects_undeclared_field(self, auth_client):
        from selco.models import Fornitore
        Fornitore.objects.create(ragione_sociale='Zeta Srl',  codice_fiscale='11111111111', attivo=True)
        # 'codice_fiscale' is not in Sebastian.ordering → ignored, default ordering used
        r = auth_client.get('/api/fornitori/?ordering=codice_fiscale')
        assert r.status_code == 200  # no error, just falls back to default

    def test_plain_pack_ordering_slots(self, auth_client):
        with override_settings(SEBASTIAN={'TEMPLATE_PACK': 'plain'}):
            r = auth_client.get('/gui/fornitori/', **GUI)
        assert r.status_code == 200
        assert b'ordering_1' in r.content


@pytest.mark.django_db
class TestTypeahead:
    """@typeahead endpoint and widget rendering."""

    def test_typeahead_endpoint_returns_json_list(self, auth_client, fornitore):
        r = auth_client.get('/api/fornitori/fornitori_typeahead/?q=')
        assert r.status_code == 200
        assert isinstance(r.data, list)
        assert r.data[0]['value'] == fornitore.pk
        assert 'label' in r.data[0]

    def test_typeahead_endpoint_filters_by_q(self, auth_client):
        from selco.models import Fornitore
        Fornitore.objects.create(ragione_sociale='Acme Corp', codice_fiscale='11111111111', attivo=True)
        Fornitore.objects.create(ragione_sociale='Beta Inc',  codice_fiscale='22222222222', attivo=True)
        r = auth_client.get('/api/fornitori/fornitori_typeahead/?q=acm')
        assert r.status_code == 200
        assert len(r.data) == 1
        assert 'Acme' in r.data[0]['label']

    def test_typeahead_widget_present_in_form(self, auth_client, richiesta):
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/edit/', **GUI)
        assert r.status_code == 200
        assert b'sb-typeahead' in r.content
        assert b'fornitori_typeahead' in r.content
