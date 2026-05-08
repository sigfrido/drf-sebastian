"""
Integration tests for the JSON API endpoints.
Covers CRUD for top-level and nested resources.
"""
import pytest


@pytest.mark.django_db
class TestFornitoreAPI:
    def test_list(self, auth_client, fornitore):
        r = auth_client.get('/api/fornitori/')
        assert r.status_code == 200
        pks = [item['id'] for item in r.data]
        assert fornitore.pk in pks

    def test_create(self, auth_client):
        r = auth_client.post('/api/fornitori/', {
            'ragione_sociale': 'Nuovo Srl',
            'codice_fiscale': '99999999999',
            'attivo': True,
        })
        assert r.status_code == 201
        assert r.data['ragione_sociale'] == 'Nuovo Srl'

    def test_retrieve(self, auth_client, fornitore):
        r = auth_client.get(f'/api/fornitori/{fornitore.pk}/')
        assert r.status_code == 200
        assert r.data['ragione_sociale'] == fornitore.ragione_sociale

    def test_partial_update(self, auth_client, fornitore):
        r = auth_client.patch(f'/api/fornitori/{fornitore.pk}/', {'ragione_sociale': 'Acme SpA'})
        assert r.status_code == 200
        assert r.data['ragione_sociale'] == 'Acme SpA'

    def test_delete(self, auth_client, fornitore):
        r = auth_client.delete(f'/api/fornitori/{fornitore.pk}/')
        assert r.status_code == 204


@pytest.mark.django_db
class TestAllegatoNestedAPI:
    def test_list_filters_by_parent(self, auth_client, allegato, richiesta):
        r = auth_client.get(f'/api/richieste/{richiesta.pk}/allegati/')
        assert r.status_code == 200
        pks = [item['id'] for item in r.data]
        assert allegato.pk in pks

    def test_list_excludes_other_parent(self, auth_client, allegato):
        from selco.models import Richiesta
        other = Richiesta.objects.create(
            titolo='Altra', descrizione='', budget='0', stato=Richiesta.Stato.BOZZA,
        )
        r = auth_client.get(f'/api/richieste/{other.pk}/allegati/')
        assert r.status_code == 200
        assert r.data == []

    def test_create_sets_parent_fk(self, auth_client, richiesta):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('doc.txt', b'contenuto', content_type='text/plain')
        r = auth_client.post(
            f'/api/richieste/{richiesta.pk}/allegati/',
            {'descrizione': 'Nuovo doc', 'file': f},
            format='multipart',
        )
        assert r.status_code == 201
        from selco.models import Allegato
        a = Allegato.objects.get(pk=r.data['id'])
        assert a.richiesta_id == richiesta.pk


@pytest.mark.django_db
class TestRichiestaActions:
    def test_invia_cambia_stato(self, auth_client, richiesta):
        r = auth_client.post(f'/api/richieste/{richiesta.pk}/invia/')
        assert r.status_code == 200
        richiesta.refresh_from_db()
        assert richiesta.stato == 'inviata'

    def test_approva_da_inviata(self, auth_client, richiesta):
        """Bozza → invia → approva: verifica stato finale approvata."""
        auth_client.post(f'/api/richieste/{richiesta.pk}/invia/')
        r = auth_client.post(f'/api/richieste/{richiesta.pk}/approva/')
        assert r.status_code == 200
        richiesta.refresh_from_db()
        assert richiesta.stato == 'approvata'

    def test_approva_su_bozza_restituisce_400(self, auth_client, richiesta):
        r = auth_client.post(f'/api/richieste/{richiesta.pk}/approva/')
        assert r.status_code == 400

    def test_invia_gia_inviata_restituisce_400(self, auth_client, richiesta):
        auth_client.post(f'/api/richieste/{richiesta.pk}/invia/')
        r = auth_client.post(f'/api/richieste/{richiesta.pk}/invia/')
        assert r.status_code == 400
