"""
Integration tests for the /gui/ HTML endpoints.
Covers: list, detail, form rendering, form submit (create/update/delete),
HTMX fragment detection, and nested inline behaviour.
"""
import pytest
from django.test import override_settings


GUI = {'HTTP_ACCEPT': 'text/html'}
HTMX = {**GUI, 'HTTP_HX_REQUEST': 'true'}

SEBASTIAN_HTMX = {
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
        assert b'Supplier' in r.content  # label from verbose_name_plural


@pytest.mark.django_db
class TestSupplierGUIList:
    def test_list_returns_html(self, auth_client, supplier):
        r = auth_client.get('/gui/suppliers/', **GUI)
        assert r.status_code == 200
        assert b'Acme Inc' in r.content

    def test_htmx_request_returns_fragment_only(self, auth_client, supplier):
        r = auth_client.get('/gui/suppliers/', **HTMX)
        assert r.status_code == 200
        # Fragment must NOT include the full page shell
        assert b'<!doctype' not in r.content.lower()
        assert b'Acme Inc' in r.content

    def test_full_page_includes_bootstrap(self, auth_client):
        r = auth_client.get('/gui/suppliers/', **GUI)
        assert b'bootstrap' in r.content.lower()

    def test_rows_have_consistent_column_count(self, auth_client, db):
        """Regression: rows with null FK must not have fewer <td> than the header."""
        from demo.models import Supplier, Request
        Request.objects.create(title='No supplier', description='', budget='0',
                                status=Request.Status.DRAFT)
        Request.objects.create(title='With supplier', description='', budget='0',
                                status=Request.Status.DRAFT,
                                supplier=Supplier.objects.create(
                                    company_name='X', tax_code='11111111111'))
        r = auth_client.get('/gui/requests/', **HTMX)
        assert r.status_code == 200
        import re
        rows = re.findall(rb'<tr>(.*?)</tr>', r.content, re.DOTALL)
        td_counts = [len(re.findall(rb'<td', row)) for row in rows if re.search(rb'<td', row)]
        assert len(set(td_counts)) == 1, f'Rows with different <td> counts: {td_counts}'


@pytest.mark.django_db
class TestSupplierGUIForms:
    def test_create_form_returns_html(self, auth_client):
        r = auth_client.get('/gui/suppliers/new/', **HTMX)
        assert r.status_code == 200
        assert b'company_name' in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_create_form_has_absolute_submit_url(self, auth_client):
        r = auth_client.get('/gui/suppliers/new/', **HTMX)
        assert b'hx-post="/gui/suppliers/"' in r.content

    def test_create_redirects_to_detail(self, auth_client):
        r = auth_client.post('/gui/suppliers/', {
            'company_name': 'New Supplier Inc',
            'tax_code': '88888888888',
            'active': True,
        }, **HTMX)
        assert r.status_code == 200
        assert 'HX-Redirect' in r
        assert '/gui/suppliers/' in r['HX-Redirect']

    def test_update_form_prefills_data(self, auth_client, supplier):
        r = auth_client.get(f'/gui/suppliers/{supplier.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'Acme Inc' in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_update_form_has_absolute_submit_url(self, auth_client, supplier):
        r = auth_client.get(f'/gui/suppliers/{supplier.pk}/edit/', **HTMX)
        expected = f'hx-patch="/gui/suppliers/{supplier.pk}/"'.encode()
        assert expected in r.content

    def test_update_redirects_to_detail(self, auth_client, supplier):
        r = auth_client.patch(
            f'/gui/suppliers/{supplier.pk}/',
            {'company_name': 'Acme Corp', 'tax_code': '12345678901', 'active': True},
            **HTMX,
        )
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/suppliers/{supplier.pk}/'

    @override_settings(**SEBASTIAN_HTMX)
    def test_create_form_has_cancel_button(self, auth_client):
        r = auth_client.get('/gui/suppliers/new/', **HTMX)
        assert b'hx-get="/gui/suppliers/"' in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_update_form_has_cancel_button(self, auth_client, supplier):
        r = auth_client.get(f'/gui/suppliers/{supplier.pk}/edit/', **HTMX)
        expected = f'hx-get="/gui/suppliers/{supplier.pk}/"'.encode()
        assert expected in r.content

    def test_create_invalid_rerenders_form_with_errors(self, auth_client):
        r = auth_client.post('/gui/suppliers/', {
            'company_name': '',      # required — triggers error
            'tax_code': 'x',
        }, **HTMX)
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'company_name' in r.content   # form is re-rendered
        assert b'invalid-feedback' in r.content  # field-level error shown

    def test_update_invalid_rerenders_form_with_errors(self, auth_client, supplier):
        r = auth_client.patch(
            f'/gui/suppliers/{supplier.pk}/',
            {'company_name': '', 'tax_code': '12345678901'},
            **HTMX,
        )
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'company_name' in r.content
        assert b'invalid-feedback' in r.content

    def test_inline_create_invalid_rerenders_form(self, auth_client, purchase_request):
        r = auth_client.post(
            f'/gui/requests/{purchase_request.pk}/attachments/',
            {'description': ''},   # file is required — triggers error
            **HTMX,
        )
        assert r.status_code == 400
        assert r.get('X-Sebastian-Form-Error') == 'true'
        assert b'invalid-feedback' in r.content


@pytest.mark.django_db
class TestSupplierGUIDelete:
    def test_delete_returns_updated_list_html(self, auth_client, supplier):
        r = auth_client.delete(f'/gui/suppliers/{supplier.pk}/', **HTMX)
        assert r.status_code == 200
        # Response is the updated list, not a redirect
        assert 'HX-Location' not in r
        assert 'HX-Redirect' not in r

    @override_settings(**SEBASTIAN_HTMX)
    def test_delete_button_links_to_confirm_url(self, auth_client, supplier):
        """Delete button in list uses hx-get to load the confirm modal."""
        r = auth_client.get('/gui/suppliers/', **HTMX)
        expected = f'/gui/suppliers/{supplier.pk}/delete/'.encode()
        assert expected in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_delete_confirm_page_contains_str(self, auth_client, supplier):
        """GET /delete/ shows confirmation modal with the object's __str__ in the prompt."""
        r = auth_client.get(f'/gui/suppliers/{supplier.pk}/delete/', **HTMX)
        assert r.status_code == 200
        assert b'sb-confirm-modal' in r.content
        assert str(supplier).encode() in r.content


@pytest.mark.django_db
class TestSupplierGUIDetail:
    def test_detail_returns_html(self, auth_client, supplier):
        r = auth_client.get(f'/gui/suppliers/{supplier.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Acme Inc' in r.content

    def test_delete_button_visible_next_to_edit_for_manager(self, manager_client, supplier):
        r = manager_client.get(f'/gui/suppliers/{supplier.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{supplier.pk}/delete/'.encode() in r.content
        assert b'Edit' in r.content

    def test_delete_button_hidden_for_regular_user(self, regular_client, supplier):
        r = regular_client.get(f'/gui/suppliers/{supplier.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{supplier.pk}/delete/'.encode() not in r.content


@pytest.mark.django_db
class TestAttachmentInlineGUI:
    def test_inline_list_loads_as_fragment(self, auth_client, purchase_request, attachment):
        r = auth_client.get(
            f'/gui/requests/{purchase_request.pk}/attachments/', **HTMX
        )
        assert r.status_code == 200
        assert b'Test document' in r.content
        assert b'<!doctype' not in r.content.lower()

    @override_settings(**SEBASTIAN_HTMX)
    def test_inline_create_form_targets_inline_div(self, auth_client, purchase_request):
        r = auth_client.get(
            f'/gui/requests/{purchase_request.pk}/attachments/new/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-attachments"' in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_inline_create_uses_absolute_url(self, auth_client, purchase_request):
        r = auth_client.get(
            f'/gui/requests/{purchase_request.pk}/attachments/new/', **HTMX
        )
        expected = f'hx-post="/gui/requests/{purchase_request.pk}/attachments/"'.encode()
        assert expected in r.content

    def test_inline_create_returns_updated_list(self, auth_client, purchase_request):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('d.txt', b'x', content_type='text/plain')
        r = auth_client.post(
            f'/gui/requests/{purchase_request.pk}/attachments/',
            {'description': 'New attachment', 'file': f},
            format='multipart',
            **HTMX,
        )
        assert r.status_code == 200
        assert b'<!doctype' not in r.content.lower()
        assert b'New attachment' in r.content

    def test_inline_delete_returns_updated_list(self, auth_client, purchase_request, attachment):
        r = auth_client.delete(
            f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/', **HTMX
        )
        assert r.status_code == 200
        assert b'Test document' not in r.content
        assert b'<!doctype' not in r.content.lower()

    @override_settings(**SEBASTIAN_HTMX)
    def test_inline_edit_form_targets_inline_div(self, auth_client, purchase_request, attachment):
        r = auth_client.get(
            f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/edit/', **HTMX
        )
        assert r.status_code == 200
        assert b'hx-target="#inline-attachments"' in r.content

    def test_edit_form_shows_existing_filename(self, auth_client, purchase_request, attachment):
        """In edit mode, the form shows the current filename and does not require it."""
        import re
        r = auth_client.get(
            f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/edit/', **HTMX
        )
        assert r.status_code == 200
        filename = attachment.file.name.split('/')[-1].encode()
        assert filename in r.content                # current filename visible
        file_input = re.search(rb'<input[^>]+name="file"[^>]*>', r.content)
        assert file_input and b'required' not in file_input.group(0)
        assert b'Select a file to replace' in r.content  # replacement hint

    def test_edit_without_new_file_keeps_existing_file(self, auth_client, purchase_request, attachment):
        """PATCH without a file field → existing file preserved."""
        r = auth_client.patch(
            f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/',
            {'description': 'Updated description'},
            **HTMX,
        )
        assert r.status_code == 200
        attachment.refresh_from_db()
        assert attachment.file.name  # file still present
        assert attachment.description == 'Updated description'

    def test_download_button_visible_in_inline_list(self, auth_client, purchase_request, attachment):
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/attachments/', **HTMX)
        assert r.status_code == 200
        assert f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/download/'.encode() in r.content

    def test_download_returns_file(self, auth_client, purchase_request, attachment):
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/download/')
        assert r.status_code == 200
        assert 'attachment' in r.get('Content-Disposition', '')

    def test_preview_returns_file_inline(self, auth_client, purchase_request, attachment):
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/preview/')
        assert r.status_code == 200
        assert 'attachment' not in r.get('Content-Disposition', '')

    def test_inline_update_returns_updated_list(self, auth_client, purchase_request, attachment):
        r = auth_client.patch(
            f'/gui/requests/{purchase_request.pk}/attachments/{attachment.pk}/',
            {'description': 'Updated'},
            **HTMX,
        )
        assert r.status_code == 200
        assert b'<!doctype' not in r.content.lower()
        assert b'Updated' in r.content


@pytest.mark.django_db
class TestRequestActionsGUI:

    def test_gui_submit_returns_redirect_to_detail(self, auth_client, purchase_request):
        r = auth_client.post(
            f'/gui/requests/{purchase_request.pk}/submit/',
            {'justification': 'Within the approved budget.', 'confirmed': 'true'},
            **HTMX,
        )
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/requests/{purchase_request.pk}/'
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'submitted'
        assert purchase_request.justification == 'Within the approved budget.'

    @override_settings(**SEBASTIAN_HTMX)
    def test_gui_submit_without_justification_returns_400(self, auth_client, purchase_request):
        """Validation error → 400 with X-Sebastian-Form-Error and re-rendered modal."""
        r = auth_client.post(
            f'/gui/requests/{purchase_request.pk}/submit/',
            {'justification': '', 'confirmed': 'true'},
            **HTMX,
        )
        assert r.status_code == 400
        assert r['X-Sebastian-Form-Error'] == 'true'
        assert b'sb-confirm-form' in r.content

    @override_settings(**SEBASTIAN_HTMX)
    def test_gui_submit_without_confirmation_returns_400(self, auth_client, purchase_request):
        """confirmed checkbox unchecked → validation error."""
        r = auth_client.post(
            f'/gui/requests/{purchase_request.pk}/submit/',
            {'justification': 'ok'},  # confirmed not sent → False
            **HTMX,
        )
        assert r.status_code == 400
        assert r['X-Sebastian-Form-Error'] == 'true'

    @override_settings(**SEBASTIAN_HTMX)
    def test_gui_submit_get_returns_modal(self, auth_client, purchase_request):
        """GET /submit/confirm/ → modal HTML fragment with serializer fields."""
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/submit/confirm/', **HTMX)
        assert r.status_code == 200
        assert b'sb-confirm-modal' in r.content
        assert b'sb-confirm-form' in r.content
        assert b'justification' in r.content
        assert b'confirmed' in r.content
        # Regression: BooleanField in a confirmation serializer must render as a
        # real checkbox, not fall through to <input type="bool-select"> (text box).
        assert b'type="checkbox"' in r.content
        assert b'name="confirmed"' in r.content

    def test_gui_approve_full_flow(self, auth_client, purchase_request):
        """Draft → submit → approve: redirect to detail, final status approved."""
        auth_client.post(
            f'/gui/requests/{purchase_request.pk}/submit/',
            {'justification': 'ok', 'confirmed': 'true'},
            **HTMX,
        )
        r = auth_client.post(f'/gui/requests/{purchase_request.pk}/approve/', **HTMX)
        assert r.status_code == 200
        assert r['HX-Redirect'] == f'/gui/requests/{purchase_request.pk}/'
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'approved'

    def test_gui_approve_on_draft_shows_error_html(self, auth_client, purchase_request):
        """400 on approving a draft → HTML response with an error message."""
        r = auth_client.post(f'/gui/requests/{purchase_request.pk}/approve/', **HTMX)
        assert r.status_code == 400
        assert b'alert' in r.content
        assert 'submitted'.encode() in r.content  # message from the action

    def test_approve_button_hidden_for_non_admin(self, regular_client, purchase_request):
        """Non-staff: perm_is_admin fails → Approve hidden."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' not in r.content

    def test_approve_button_hidden_for_admin_on_draft(self, auth_client, purchase_request):
        """Admin on draft: perm_is_admin passes but status check fails → hidden."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' not in r.content

    def test_approve_button_visible_for_manager_on_submitted(self, manager_client, purchase_request):
        """Manager on submitted: both callables pass → button visible."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = manager_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' in r.content

    def test_approve_button_hidden_for_admin_who_is_not_manager(self, auth_client, purchase_request):
        """Admin (superuser) on submitted: not a manager → button hidden, matching
        the literal rule that only managers approve."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' not in r.content

    def test_submit_button_hidden_after_submission(self, auth_client, purchase_request):
        """Submit has permission=status==DRAFT → hidden once status changes."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        # Check the action URL rather than the label: 'Submitted' (status display value)
        # is a substring of 'Submit' so a plain label check would be a false positive.
        # The button uses data-sb-confirm-url=".../submit/" (no /confirm/ suffix).
        assert b'/submit/"' not in r.content

    def test_submit_button_visible_on_draft(self, auth_client, purchase_request):
        """Submit button visible when status==DRAFT."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'/submit/"' in r.content


@pytest.mark.django_db
class TestFieldGroupPermissions:
    def test_management_fields_readonly_for_non_admin(self, regular_client, purchase_request):
        """Non-admin: edit_permission requires perm_is_admin → read-only regardless of status."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'form-control-plaintext' in r.content
        assert b'name="manager_notes"' not in r.content

    def test_management_fields_readonly_for_admin_on_draft(self, auth_client, purchase_request):
        """Admin, but status is still draft: management fields are not editable yet."""
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="manager_notes"' not in r.content

    def test_management_fields_editable_for_admin_on_submitted(self, auth_client, purchase_request):
        """Admin + status=submitted: both conditions pass → management fields are inputs."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="manager_notes"' in r.content

    def test_general_fields_editable_on_draft(self, auth_client, purchase_request):
        """General fields (title, description, budget, supplier) are editable in draft."""
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="title"' in r.content

    def test_general_fields_editable_by_any_authenticated_user_on_draft(self, regular_client, purchase_request):
        """No role restriction on General — any logged-in user, not just admin/manager."""
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="title"' in r.content

    def test_general_fields_readonly_after_submit(self, auth_client, purchase_request):
        """Once submitted, General fields are no longer editable (requester can't change them)."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="title"' not in r.content

    def test_general_fields_editable_when_creating(self, auth_client):
        """New instance (no object yet): General fields must still be fillable."""
        r = auth_client.get('/gui/requests/new/', **HTMX)
        assert r.status_code == 200
        assert b'name="title"' in r.content

    def test_create_form_title_field_value_is_empty_not_bound_method(self, auth_client):
        """Regression: the create form for a model with a 'title' field used to
        render value="<built-in method title of str object at 0x...>" — see
        get_item()/create_form() fix. Any str-method-named field is affected,
        'title' just happens to be this project's example."""
        r = auth_client.get('/gui/requests/new/', **HTMX)
        assert r.status_code == 200
        assert b'built-in method' not in r.content
        assert b'name="title"\n               value=""' in r.content

    def test_status_field_never_writable_via_api(self, auth_client, purchase_request):
        """status is serializer-level read_only — direct API writes are silently ignored,
        not just hidden/blocked in the GUI."""
        r = auth_client.patch(f'/api/requests/{purchase_request.pk}/', {'status': 'approved'})
        assert r.status_code == 200
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'draft'

    def test_record_locked_when_approved(self, auth_client, purchase_request):
        """Record-level lock: once approved, no field (even ones an admin could
        otherwise edit) can be written any more — a 403, not just a read-only form."""
        from demo.models import Request as R
        purchase_request.status = R.Status.APPROVED
        purchase_request.save()
        r = auth_client.patch(f'/api/requests/{purchase_request.pk}/', {'title': 'Changed'})
        assert r.status_code == 403
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert b'Edit' not in r.content

    def test_record_locked_when_rejected(self, auth_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.REJECTED
        purchase_request.save()
        r = auth_client.patch(f'/api/requests/{purchase_request.pk}/', {'title': 'Changed'})
        assert r.status_code == 403

    def test_record_still_writable_when_submitted(self, auth_client, purchase_request):
        """Sanity check: the record-level lock only fires for approved/rejected, not submitted."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client.patch(f'/api/requests/{purchase_request.pk}/', {'manager_notes': 'ok'})
        assert r.status_code == 200

    def test_delete_blocked_when_approved(self, auth_client, purchase_request):
        """API-level record lock also covers DELETE, not just PATCH/PUT."""
        from demo.models import Request as R
        purchase_request.status = R.Status.APPROVED
        purchase_request.save()
        r = auth_client.delete(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 403

    def test_delete_draft_by_any_authenticated_user(self, regular_client, purchase_request):
        """Draft requests can be deleted by anyone logged in, not just managers/admin."""
        r = regular_client.delete(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 204

    def test_delete_submitted_forbidden_for_regular_user(self, regular_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = regular_client.delete(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 403

    def test_delete_submitted_allowed_for_manager(self, manager_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = manager_client.delete(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 204

    def test_delete_submitted_allowed_for_admin(self, auth_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client.delete(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 204

    def test_delete_button_visible_next_to_edit_on_draft(self, regular_client, purchase_request):
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{purchase_request.pk}/delete/'.encode() in r.content
        assert b'Edit' in r.content

    def test_delete_button_hidden_for_regular_user_on_submitted(self, regular_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{purchase_request.pk}/delete/'.encode() not in r.content

    def test_delete_button_visible_for_manager_on_submitted(self, manager_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = manager_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{purchase_request.pk}/delete/'.encode() in r.content

    def test_delete_button_hidden_when_approved(self, auth_client, purchase_request):
        """Even admin/manager: the record-level lock wins, no exception for delete."""
        from demo.models import Request as R
        purchase_request.status = R.Status.APPROVED
        purchase_request.save()
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert f'{purchase_request.pk}/delete/'.encode() not in r.content

    def test_delete_from_detail_page_redirects_to_list(self, regular_client, purchase_request):
        """The button added to detail.html hx-gets the confirm modal, which then
        POSTs to the same /delete/ URL used from the list — same redirect either
        way, since the detail page for a now-deleted object can't stay open."""
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/delete/', **HTMX)
        assert r.status_code == 200
        assert b'sb-confirm-modal' in r.content
        r = regular_client.post(f'/gui/requests/{purchase_request.pk}/delete/', **HTMX)
        assert r.status_code == 200
        assert r['HX-Redirect'] == '/gui/requests/'


@pytest.mark.django_db
class TestRejectAction:
    def test_reject_from_submitted(self, manager_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = manager_client.post(f'/api/requests/{purchase_request.pk}/reject/')
        assert r.status_code == 200
        purchase_request.refresh_from_db()
        assert purchase_request.status == 'rejected'

    def test_reject_on_draft_returns_400(self, manager_client, purchase_request):
        r = manager_client.post(f'/api/requests/{purchase_request.pk}/reject/')
        assert r.status_code == 400

    def test_reject_requires_manager(self, auth_client_regular, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client_regular.post(f'/api/requests/{purchase_request.pk}/reject/')
        assert r.status_code == 403

    def test_reject_forbidden_for_admin_who_is_not_manager(self, auth_client, purchase_request):
        """Same 'only managers' rule as approve — admin alone isn't enough."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        r = auth_client.post(f'/api/requests/{purchase_request.pk}/reject/')
        assert r.status_code == 403

    def test_reject_button_visible_for_manager_on_submitted(self, manager_client, purchase_request):
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = manager_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Reject' in r.content

    def test_hide_false_renders_disabled_button(self, regular_client, purchase_request):
        """HIDE_UNAUTHORIZED_ACTIONS=False: unauthorized action rendered as disabled button."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' in r.content
        assert b'disabled' in r.content

    def test_permission_list_and_logic(self, auth_client, purchase_request):
        """List of callables uses AND: admin+draft fails the status check → hidden."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' not in r.content


@pytest.mark.django_db
class TestAppMenu:
    def test_menu_endpoint_returns_json(self, auth_client):
        r = auth_client.get('/api/menu/', HTTP_ACCEPT='application/json')
        assert r.status_code == 200
        assert 'menu_groups' in r.data
        labels = [g['label'] for g in r.data['menu_groups']]
        assert 'Suppliers' in labels
        assert 'Requests' in labels

    def test_menu_endpoint_returns_html_fragment(self, auth_client):
        r = auth_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        # Fragment only — no full page shell
        assert b'<!doctype' not in r.content.lower()
        assert b'<ul' in r.content
        assert b'Suppliers' in r.content
        assert b'Requests' in r.content

    def test_menu_items_present_for_admin(self, auth_client):
        r = auth_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'List' in r.content
        assert b'New' in r.content   # admin sees all items

    def test_menu_shows_divider_and_settings_link(self, auth_client):
        r = auth_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'dropdown-divider' in r.content
        assert b'Settings' in r.content

    def test_new_request_visible_for_any_authenticated_user(self, regular_client):
        """Any authenticated user can create a Request (draft) — menu item is unrestricted."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'/gui/requests/new/' in r.content

    def test_new_supplier_hidden_for_non_manager(self, regular_client):
        """Suppliers can only be created/edited by managers or admin."""
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'Suppliers' in r.content   # group still visible
        assert b'/gui/suppliers/new/' not in r.content

    def test_new_supplier_visible_for_manager(self, manager_client):
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = manager_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'/gui/suppliers/new/' in r.content

    def test_new_supplier_disabled_for_non_manager(self, regular_client):
        import re
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        # Disabled items render as a <span class="dropdown-item disabled"> with no
        # href, so "New" is only findable by structure, not by URL.
        assert re.search(rb'<span class="dropdown-item disabled">\s*.*?New\s*</span>', r.content, re.DOTALL)

    @override_settings(**SEBASTIAN_HTMX)
    def test_menu_active_item_via_hx_current_url(self, auth_client):
        r = auth_client.get(
            '/gui/menu/', **GUI,
            HTTP_HX_CURRENT_URL='http://testserver/gui/requests/',
        )
        assert r.status_code == 200
        content = r.content.decode()
        # Parent group toggle must carry the active class
        assert 'nav-link dropdown-toggle active' in content
        # The matching dropdown item must also be active
        assert 'dropdown-item active' in content

    @override_settings(**SEBASTIAN_HTMX)
    def test_base_template_loads_menu_via_htmx(self, auth_client):
        r = auth_client.get('/gui/requests/', **GUI)
        assert r.status_code == 200
        assert b'hx-get' in r.content
        assert b'menu' in r.content   # hx-get points to the menu endpoint


@pytest.mark.django_db
class TestAPIBehaviour:
    """API endpoints always return JSON; detail includes inline data."""

    def test_api_list_returns_json_from_browser(self, auth_client):
        r = auth_client.get('/api/requests/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')

    def test_api_detail_returns_json_from_browser(self, auth_client, purchase_request):
        r = auth_client.get(f'/api/requests/{purchase_request.pk}/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')

    def test_api_menu_returns_json_from_browser(self, auth_client):
        r = auth_client.get('/api/menu/', HTTP_ACCEPT='text/html,*/*;q=0.8')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('application/json')
        assert 'menu_groups' in r.data

    def test_api_detail_includes_inline_data(self, auth_client, purchase_request, attachment):
        r = auth_client.get(f'/api/requests/{purchase_request.pk}/')
        assert r.status_code == 200
        assert 'attachments' in r.data
        assert len(r.data['attachments']) == 1
        assert r.data['attachments'][0]['id'] == attachment.pk

    def test_api_detail_inline_in_api_false_excluded(self, auth_client, purchase_request):
        from demo.views import RequestViewSet
        inline_cls = RequestViewSet.Sebastian.inlines[0]
        original = inline_cls.inline_in_api
        try:
            inline_cls.inline_in_api = False
            r = auth_client.get(f'/api/requests/{purchase_request.pk}/')
            assert r.status_code == 200
            assert 'attachments' not in r.data
        finally:
            inline_cls.inline_in_api = original


@pytest.mark.django_db
class TestOrdering:
    """Ordering widget and queryset filter."""

    def test_ordering_widget_present_when_configured(self, auth_client):
        r = auth_client.get('/gui/suppliers/', **GUI)
        assert r.status_code == 200
        assert b'sb-ordering' in r.content
        assert b'Company Name' in r.content

    def test_ordering_applies_to_queryset(self, auth_client):
        from demo.models import Supplier
        Supplier.objects.create(company_name='Zeta Inc',  tax_code='11111111111', active=True)
        Supplier.objects.create(company_name='Alpha Inc', tax_code='22222222222', active=True)
        r = auth_client.get('/api/suppliers/?ordering=company_name')
        assert r.status_code == 200
        items = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        names = [item['company_name'] for item in items]
        assert names == sorted(names)

    def test_ordering_descending(self, auth_client):
        from demo.models import Supplier
        Supplier.objects.create(company_name='Zeta Inc',  tax_code='11111111111', active=True)
        Supplier.objects.create(company_name='Alpha Inc', tax_code='22222222222', active=True)
        r = auth_client.get('/api/suppliers/?ordering=-company_name')
        assert r.status_code == 200
        items = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        names = [item['company_name'] for item in items]
        assert names == sorted(names, reverse=True)

    def test_ordering_rejects_undeclared_field(self, auth_client):
        from demo.models import Supplier
        Supplier.objects.create(company_name='Zeta Inc', tax_code='11111111111', active=True)
        # 'tax_code' is not in Sebastian.ordering → ignored, default ordering used
        r = auth_client.get('/api/suppliers/?ordering=tax_code')
        assert r.status_code == 200  # no error, just falls back to default

    def test_plain_pack_ordering_slots(self, auth_client):
        with override_settings(SEBASTIAN={'TEMPLATE_PACK': 'plain'}):
            r = auth_client.get('/gui/suppliers/', **GUI)
        assert r.status_code == 200
        assert b'ordering_1' in r.content


@pytest.mark.django_db
class TestTypeahead:
    """@typeahead endpoint and widget rendering."""

    def test_typeahead_endpoint_returns_json_list(self, auth_client, supplier):
        r = auth_client.get('/api/suppliers/suppliers_typeahead/?q=')
        assert r.status_code == 200
        assert isinstance(r.data, list)
        assert r.data[0]['value'] == supplier.pk
        assert 'label' in r.data[0]

    def test_typeahead_endpoint_filters_by_q(self, auth_client):
        from demo.models import Supplier
        Supplier.objects.create(company_name='Acme Corp', tax_code='11111111111', active=True)
        Supplier.objects.create(company_name='Beta Inc',  tax_code='22222222222', active=True)
        r = auth_client.get('/api/suppliers/suppliers_typeahead/?q=acm')
        assert r.status_code == 200
        assert len(r.data) == 1
        assert 'Acme' in r.data[0]['label']

    def test_typeahead_widget_present_in_form(self, auth_client, purchase_request):
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **GUI)
        assert r.status_code == 200
        assert b'sb-typeahead' in r.content
        assert b'suppliers_typeahead' in r.content
