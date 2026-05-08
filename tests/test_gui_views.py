"""
Integration tests for the /gui/ HTML endpoints.
Covers: list, detail, form rendering, form submit (create/update/delete),
HTMX fragment detection, and nested inline behaviour.
"""
import pytest


GUI = {'HTTP_ACCEPT': 'text/html'}
HTMX = {**GUI, 'HTTP_HX_REQUEST': 'true'}


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


@pytest.mark.django_db
class TestFornitoreGUIDelete:
    def test_delete_returns_updated_list_html(self, auth_client, fornitore):
        r = auth_client.delete(f'/gui/fornitori/{fornitore.pk}/', **HTMX)
        assert r.status_code == 200
        # Response is the updated list, not a redirect
        assert 'HX-Location' not in r
        assert 'HX-Redirect' not in r

    def test_delete_confirm_includes_str(self, auth_client, fornitore):
        """hx-confirm must contain the record's __str__."""
        r = auth_client.get('/gui/fornitori/', **HTMX)
        expected = f'Eliminare Fornitore: {fornitore}'.encode()
        assert expected in r.content


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

    def test_inline_create_form_targets_inline_div(self, auth_client, richiesta):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/new/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-allegati"' in r.content

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

    def test_inline_edit_form_targets_inline_div(self, auth_client, richiesta, allegato):
        r = auth_client.get(
            f'/gui/richieste/{richiesta.pk}/allegati/{allegato.pk}/edit/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-allegati"' in r.content

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
    def test_gui_invia_restituisce_redirect_al_detail(self, auth_client, richiesta):
        r = auth_client.post(f'/gui/richieste/{richiesta.pk}/invia/', **HTMX)
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/richieste/{richiesta.pk}/'
        richiesta.refresh_from_db()
        assert richiesta.stato == 'inviata'

    def test_gui_approva_flow_completo(self, auth_client, richiesta):
        """Bozza → invia → approva: redirect al detail, stato finale approvata."""
        auth_client.post(f'/gui/richieste/{richiesta.pk}/invia/', **HTMX)
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
        """Utente non-staff non vede il pulsante Approva nel detail."""
        r = regular_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content

    def test_approva_button_visibile_per_admin(self, auth_client, richiesta):
        """Utente admin vede il pulsante Approva nel detail."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' in r.content
