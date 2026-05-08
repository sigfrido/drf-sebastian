"""
Integration tests for the /gui/ HTML endpoints.
Covers: list, detail, form rendering, form submit (create/update/delete),
HTMX fragment detection, and nested inline behaviour.
"""
import pytest
from django.test import override_settings


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

    def test_create_form_has_cancel_button(self, auth_client):
        r = auth_client.get('/gui/fornitori/new/', **HTMX)
        assert b'hx-get="/gui/fornitori/"' in r.content

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
        assert b'Scarica' in r.content
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
        """Non-staff never sees Approva, regardless of stato."""
        r = regular_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content

    def test_approva_button_nascosto_per_admin_su_bozza(self, auth_client, richiesta):
        """Admin on bozza: is_admin passes but stato check fails → button hidden."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' not in r.content

    def test_approva_button_visibile_per_admin_su_inviata(self, auth_client, richiesta):
        """Admin on inviata: both callables pass → button visible."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' in r.content


@pytest.mark.django_db
class TestFieldGroupPermissions:
    def test_direzione_fields_readonly_for_non_admin(self, regular_client, richiesta):
        """Non-admin: direzione group has edit_permission=is_admin → fields read-only in form."""
        r = regular_client.get(f'/gui/richieste/{richiesta.pk}/edit/', **HTMX)
        assert r.status_code == 200
        # note_direttore should appear as plain text, not as an <input>
        assert b'note_direttore' not in r.content or b'form-control-plaintext' in r.content

    def test_direzione_fields_editable_for_admin(self, auth_client, richiesta):
        """Admin: direzione group is fully editable."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="note_direttore"' in r.content

    def test_hide_unauthorized_actions_false_renders_disabled(self, regular_client, richiesta):
        """HIDE_UNAUTHORIZED_ACTIONS=False: Approva rendered as disabled button for non-admin."""
        from selco.models import Richiesta as R
        richiesta.stato = R.Stato.INVIATA
        richiesta.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approva' in r.content
        assert b'disabled' in r.content

    def test_permission_list_and_logic(self, auth_client, richiesta):
        """List of callables: both must pass — admin on bozza still can't approve."""
        r = auth_client.get(f'/gui/richieste/{richiesta.pk}/', **HTMX)
        assert r.status_code == 200
        # is_admin passes, stato check fails → hidden
        assert b'Approva' not in r.content
