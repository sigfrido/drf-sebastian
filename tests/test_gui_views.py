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

    def test_approve_button_visible_for_admin_on_submitted(self, auth_client, purchase_request):
        """Admin on submitted: both callables pass → button visible."""
        from demo.models import Request as R
        purchase_request.status = R.Status.SUBMITTED
        purchase_request.save()
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', **HTMX)
        assert r.status_code == 200
        assert b'Approve' in r.content

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
        """Non-admin: edit_permission=perm_is_admin → management fields read-only in form."""
        r = regular_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'form-control-plaintext' in r.content
        assert b'name="manager_notes"' not in r.content

    def test_management_fields_editable_for_admin(self, auth_client, purchase_request):
        """Admin: edit_permission passes → management fields rendered as inputs."""
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/edit/', **HTMX)
        assert r.status_code == 200
        assert b'name="manager_notes"' in r.content

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

    def test_menu_item_permission_hidden_for_non_admin(self, regular_client):
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': True}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        assert b'Requests' in r.content   # group still visible
        # "New request" is admin-only (perm_is_admin); "New supplier" has no such
        # restriction, so check the specific URL rather than the shared "New" label.
        assert b'/gui/requests/new/' not in r.content

    def test_menu_item_permission_disabled_for_non_admin(self, regular_client):
        import re
        with override_settings(SEBASTIAN={'HIDE_UNAUTHORIZED_ACTIONS': False}):
            r = regular_client.get('/gui/menu/', **GUI)
        assert r.status_code == 200
        # Disabled items render as a <span class="dropdown-item disabled"> with no
        # href, so "New request" is only findable by structure, not by URL.
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
