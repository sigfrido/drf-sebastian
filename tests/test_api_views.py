"""
Integration tests for the JSON API endpoints.
Covers CRUD for top-level and nested resources.
"""
import pytest


@pytest.mark.django_db
class TestSupplierAPI:
    def test_list(self, auth_client, supplier):
        r = auth_client.get('/api/suppliers/')
        assert r.status_code == 200
        pks = [item['id'] for item in r.data]
        assert supplier.pk in pks

    def test_create(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'New Supplier Inc',
            'tax_code': 'XX9999999999',
            'active': True,
        })
        assert r.status_code == 201
        assert r.data['company_name'] == 'New Supplier Inc'

    def test_retrieve(self, auth_client, supplier):
        r = auth_client.get(f'/api/suppliers/{supplier.pk}/')
        assert r.status_code == 200
        assert r.data['company_name'] == supplier.company_name

    def test_partial_update(self, auth_client, supplier):
        r = auth_client.patch(f'/api/suppliers/{supplier.pk}/', {'company_name': 'Acme Corp'})
        assert r.status_code == 200
        assert r.data['company_name'] == 'Acme Corp'

    def test_delete(self, auth_client, supplier):
        r = auth_client.delete(f'/api/suppliers/{supplier.pk}/')
        assert r.status_code == 204


@pytest.mark.django_db
class TestSupplierPermissions:
    """Only managers or admin can write; reads stay open to anyone."""

    def test_anonymous_can_read(self, api_client, supplier):
        r = api_client.get('/api/suppliers/')
        assert r.status_code == 200

    def test_regular_user_cannot_create(self, auth_client_regular):
        r = auth_client_regular.post('/api/suppliers/', {
            'company_name': 'Blocked Inc', 'tax_code': 'XX1111111111', 'active': True,
        })
        assert r.status_code == 403

    def test_regular_user_cannot_update(self, auth_client_regular, supplier):
        r = auth_client_regular.patch(f'/api/suppliers/{supplier.pk}/', {'company_name': 'Blocked'})
        assert r.status_code == 403

    def test_regular_user_cannot_delete(self, auth_client_regular, supplier):
        r = auth_client_regular.delete(f'/api/suppliers/{supplier.pk}/')
        assert r.status_code == 403

    def test_manager_can_create(self, manager_client):
        r = manager_client.post('/api/suppliers/', {
            'company_name': 'Manager Created Inc', 'tax_code': 'XX2222222222', 'active': True,
        })
        assert r.status_code == 201

    def test_manager_can_update(self, manager_client, supplier):
        r = manager_client.patch(f'/api/suppliers/{supplier.pk}/', {'company_name': 'Updated by manager'})
        assert r.status_code == 200

    def test_manager_can_delete(self, manager_client, supplier):
        r = manager_client.delete(f'/api/suppliers/{supplier.pk}/')
        assert r.status_code == 204


@pytest.mark.django_db
class TestAttachmentNestedAPI:
    def test_list_filters_by_parent(self, auth_client, attachment, purchase_request):
        r = auth_client.get(f'/api/requests/{purchase_request.pk}/attachments/')
        assert r.status_code == 200
        pks = [item['id'] for item in r.data]
        assert attachment.pk in pks

    def test_list_excludes_other_parent(self, auth_client, attachment):
        from demo.models import Request
        other = Request.objects.create(
            title='Other', description='', budget='0', status=Request.Status.DRAFT,
        )
        r = auth_client.get(f'/api/requests/{other.pk}/attachments/')
        assert r.status_code == 200
        assert r.data == []

    def test_create_sets_parent_fk(self, auth_client, purchase_request):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('doc.txt', b'content', content_type='text/plain')
        r = auth_client.post(
            f'/api/requests/{purchase_request.pk}/attachments/',
            {'description': 'New document', 'file': f},
            format='multipart',
        )
        assert r.status_code == 201
        from demo.models import Attachment
        a = Attachment.objects.get(pk=r.data['id'])
        assert a.request_id == purchase_request.pk


@pytest.mark.django_db
class TestSupplierCertification:
    def test_patch_uploads_certification(self, auth_client, supplier):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('cert.pdf', b'%PDF-1.4', content_type='application/pdf')
        r = auth_client.patch(
            f'/api/suppliers/{supplier.pk}/',
            {'certification': f},
            format='multipart',
        )
        assert r.status_code == 200
        supplier.refresh_from_db()
        assert supplier.certification  # file present

    def test_patch_clears_certification(self, auth_client, supplier):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('cert.pdf', b'%PDF-1.4', content_type='application/pdf')
        auth_client.patch(
            f'/api/suppliers/{supplier.pk}/',
            {'certification': f},
            format='multipart',
        )
        r = auth_client.patch(
            f'/api/suppliers/{supplier.pk}/',
            {'certification': ''},
            format='multipart',
        )
        assert r.status_code == 200
        supplier.refresh_from_db()
        assert not supplier.certification  # file cleared


@pytest.mark.django_db
class TestSupplierTaxCodeValidation:
    """Validation of tax_code at model and serializer level."""

    # --- valid formats ---

    def test_valid_tax_code_accepted(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'Valid Tax Code Inc', 'tax_code': '12345678901',
        })
        assert r.status_code == 201

    def test_valid_tax_code_with_dashes_accepted(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'Dashes Inc',
            'tax_code': 'AB-123-CD-456',
        })
        assert r.status_code == 201

    def test_valid_tax_code_lowercase_accepted(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'Lowercase Inc', 'tax_code': 'ab123cd456',
        })
        assert r.status_code == 201

    def test_blank_tax_code_allowed(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'No Tax Code Inc', 'tax_code': '',
        })
        assert r.status_code == 201

    # --- invalid formats (API → 400) ---

    def test_invalid_too_short_rejected(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'X', 'tax_code': '123',
        })
        assert r.status_code == 400
        assert 'tax_code' in r.data

    def test_invalid_too_long_rejected(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'X', 'tax_code': '1' * 25,
        })
        assert r.status_code == 400

    def test_invalid_non_alphanumeric_rejected(self, auth_client):
        r = auth_client.post('/api/suppliers/', {
            'company_name': 'X', 'tax_code': '1234$6789',
        })
        assert r.status_code == 400

    # --- model clean() ---

    def test_model_clean_raises_for_invalid(self):
        from django.core.exceptions import ValidationError
        from demo.models import Supplier
        s = Supplier(company_name='X', tax_code='!!')
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'tax_code' in exc_info.value.message_dict

    def test_model_clean_passes_for_valid(self):
        from demo.models import Supplier
        Supplier(company_name='X', tax_code='12345678901').clean()

    def test_model_clean_passes_for_blank(self):
        from demo.models import Supplier
        Supplier(company_name='X', tax_code='').clean()


@pytest.mark.django_db
class TestRequestActions:
    def test_submit_changes_status(self, auth_client, purchase_request):
        r = auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        assert r.status_code == 200
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'submitted'

    def test_approve_after_submit(self, auth_client, manager_client, purchase_request):
        """Draft → submit → approve: final status is approved. Approve requires a
        manager specifically — submit can be done by any authenticated user."""
        auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        r = manager_client.post(f'/api/requests/{purchase_request.pk}/approve/')
        assert r.status_code == 200
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'approved'

    def test_approve_on_draft_returns_400(self, manager_client, purchase_request):
        r = manager_client.post(f'/api/requests/{purchase_request.pk}/approve/')
        assert r.status_code == 400

    def test_approve_requires_manager_not_just_admin(self, auth_client, purchase_request):
        """'Only managers' means admin (superuser, not in MANAGERS) is also rejected."""
        auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        r = auth_client.post(f'/api/requests/{purchase_request.pk}/approve/')
        assert r.status_code == 403

    def test_approve_forbidden_for_regular_user(self, auth_client, auth_client_regular, purchase_request):
        auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        r = auth_client_regular.post(f'/api/requests/{purchase_request.pk}/approve/')
        assert r.status_code == 403

    def test_submit_already_submitted_returns_400(self, auth_client, purchase_request):
        auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        r = auth_client.post(f'/api/requests/{purchase_request.pk}/submit/')
        assert r.status_code == 400

    def test_regular_user_edit_readonly_fields(self, auth_client_regular, purchase_request):
        r = auth_client_regular.patch(f'/api/requests/{purchase_request.pk}/',
            {'description': 'New description'})
        assert r.status_code == 200
        assert r.data['description'] == 'New description'
        # Now try with admin-only field
        r = auth_client_regular.patch(f'/api/requests/{purchase_request.pk}/',
            {'description': 'New description', 'manager_notes': 'This will not work'}
        )
        assert r.status_code == 403
        assert 'manager_notes' in r.data['detail']
