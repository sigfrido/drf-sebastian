from rest_framework import viewsets, permissions, generics
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from sebastian.mixins import GUIMixin, NestedGUIMixin, SingletonGUIMixin
from sebastian.config import FieldGroup, MenuGroup, MenuItem, MenuDivider
from sebastian.decorators import action, typeahead
from sebastian.permissions import perm_is_admin, perm_is_staff, perm_is_action, perm_or, perm_and
from .models import Supplier, Request, Attachment, Settings
from .serializers import (
    SupplierSerializer, RequestSerializer, AttachmentSerializer,
    SubmitSerializer, SettingsSerializer,
)
from .filters import SupplierFilter, RequestFilter


# Permissions

def perm_request_status(*statuses):
    def _has_perm(request, _obj):
        if not _obj:
            return False
        return _obj.status in statuses
    return _has_perm


def perm_editable_or_new(*statuses):
    """Editable while creating a new instance (no object yet), or once saved,
    only when the object's status is one of *statuses."""
    def _has_perm(request, obj):
        if obj is None:
            return True
        return obj.status in statuses
    return _has_perm


class RequestNotFinalized(BasePermission):
    """Record-level lock: once a Request is approved or rejected, it is read-only —
    no field group, action, or direct API write can change it any more."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.status not in (Request.Status.APPROVED, Request.Status.REJECTED)


class SupplierViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filterset_class  = SupplierFilter

    class Sebastian:
        label = 'Suppliers'
        menu = MenuGroup('Suppliers', icon='building', items=[
            MenuItem('List', action='list', icon='list-ul'),
            MenuItem('New',  action='new',  icon='plus-circle'),
        ])
        groups = [
            FieldGroup('info', ['company_name', 'tax_code', 'active'],
                       label='Info'),
            FieldGroup('documents', ['certification'], label='Documents'),
        ]
        ordering = (
            ('company_name',  'Company Name ↑'),
            ('-company_name', 'Company Name ↓'),
            ('active',        'Active ↑'),
            ('-active',       'Active ↓'),
        )
        max_ordering_fields = 2

    @typeahead(typeahead_chars=1, max_results=40)
    def suppliers_typeahead(self, request):
        q = request.query_params.get('q', '')
        return self.standard_typeahead(
            filter={'company_name__icontains': q},
            order_by='company_name',
        )

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':      '', # icon-only
            'icon':       'download',
            'color':      'outline-secondary',
            'position':   'both',
            'hint':       'Download certification',
            'link_field': 'certification',
            'permission': perm_or(perm_is_admin, perm_is_staff),
        },
    )
    def download(self, request, pk=None, **kwargs):
        return self.download_action('certification', request, pk, **kwargs)


class AttachmentViewSet(NestedGUIMixin, viewsets.ModelViewSet):
    queryset         = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    mountpoint       = 'attachments'

    class Sebastian:
        label  = 'Attachments'
        groups = [
            FieldGroup('data', ['description', 'file', 'uploaded_at'], label='Data'),
        ]

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':      '', # icon only
            'icon':       'download',
            'color':      'outline-secondary',
            'position':   'list',
            'link_field': 'file',
        },
    )
    def download(self, request, pk=None, **kwargs):
        return self.download_action('file', request, pk, **kwargs)

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':      '', # icon only
            'icon':       'eye',
            'color':      'outline-secondary',
            'position':   'list',
            'link_field': 'file',
        },
    )
    def preview(self, request, pk=None, **kwargs):
        return self.preview_action('file', request, pk, **kwargs)


class RequestViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset           = Request.objects.select_related('supplier').all()
    serializer_class   = RequestSerializer
    filterset_class    = RequestFilter
    permission_classes = [RequestNotFinalized]

    def can_update(self):
        # RequestNotFinalized.has_object_permission() only rejects unsafe methods;
        # the default can_update() evaluates it against *this* (GET) request, which
        # is always safe, so it would never hide the Edit button on its own.
        obj = getattr(self, '_sebastian_obj', None)
        if obj is not None and obj.status in (Request.Status.APPROVED, Request.Status.REJECTED):
            return False
        return super().can_update()

    def can_delete(self):
        obj = getattr(self, '_sebastian_obj', None)
        if obj is not None and obj.status in (Request.Status.APPROVED, Request.Status.REJECTED):
            return False
        return super().can_delete()

    class Sebastian:
        label = 'Requests'
        ordering = (
            ('title',    'Title ↑'),
            ('-title',   'Title ↓'),
            ('budget',   'Budget ↑'),
            ('-budget',  'Budget ↓'),
            ('supplier', 'Supplier ↑'),
            ('-supplier','Supplier ↓'),
        )
        max_ordering_fields = 2
        field_config = {
            'supplier': {'typeahead_url': '/api/suppliers/suppliers_typeahead/'},
        }
        menu = MenuGroup('Requests', icon='clipboard-check', items=[
            MenuItem('List', action='list', icon='list-ul'),
            MenuItem('New',  action='new',  icon='plus-circle', permission=(perm_is_admin,)),
            MenuDivider(),
            MenuItem('Settings', url_name='settings', icon='gear'),
        ])
        groups = [
            FieldGroup(
                'general',
                ['title', 'description', 'budget', 'status', 'supplier'],
                label='General',
                edit_permission=perm_editable_or_new(Request.Status.DRAFT),
            ),
            FieldGroup(
                'management',
                ['manager_notes', 'reference_code'],
                label='Management',
                edit_permission=perm_and(
                    perm_is_admin,
                    perm_request_status(Request.Status.SUBMITTED),
                ),
            ),
            FieldGroup(
                'submit',
                ['justification'],
                label='Submission Notes',
                visible_permission=perm_request_status(Request.Status.SUBMITTED, Request.Status.APPROVED),
                edit_permission=perm_is_action('submit'),
            ),
        ]
        inlines = [AttachmentViewSet]

    @action(
        detail=True,
        methods=['get', 'post'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':      'Submit',
            'icon':       'send',
            'color':      'primary',
            'position':   'detail',
            'permission': [perm_request_status(Request.Status.DRAFT)],
            'confirmation': {
                'prompt':     'Submit $OBJECT?',
                'serializer': SubmitSerializer,
                'icon':       'send',
                'style':      'primary',
            },
        },
    )
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.method == 'GET':
            return Response(self.get_serializer(instance).data)
        return self._post_confirmation_action('submit', instance)

    def submit_get(self, instance):
        return {'justification': instance.justification or '', 'confirmed': False}

    def submit_valid(self, instance, serializer):
        if serializer is None:
            # API path: status check (GUI path handled by SubmitSerializer.validate())
            if instance.status != Request.Status.DRAFT:
                return Response({'detail': 'Only draft requests can be submitted.'}, status=400)
        instance.justification = (
            serializer.validated_data['justification'] if serializer
            else self.request.data.get('justification', '')
        )
        instance.status = Request.Status.SUBMITTED
        instance.save()

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        gui_config={
            'label':    'Approve',
            'icon':     'check-circle',
            'color':    'success',
            'position': 'detail',
            'permission': perm_and(
                perm_is_admin,
                perm_request_status(Request.Status.SUBMITTED),
            ),
            'confirmation': {
                'prompt': 'Confirm approval of $OBJECT?',
                'icon':   'check-circle',
                'style':  'success',
            },
        },
    )
    def approve(self, request, pk=None, **kwargs):
        instance = self.get_object()
        if instance.status != Request.Status.SUBMITTED:
            return Response({'detail': 'Only submitted requests can be approved.'}, status=400)
        instance.status = Request.Status.APPROVED
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        gui_config={
            'label':    'Reject',
            'icon':     'x-circle',
            'color':    'danger',
            'position': 'detail',
            'permission': perm_and(
                perm_is_admin,
                perm_request_status(Request.Status.SUBMITTED),
            ),
            'confirmation': {
                'prompt': 'Confirm rejection of $OBJECT?',
                'icon':   'x-circle',
                'style':  'danger',
            },
        },
    )
    def reject(self, request, pk=None, **kwargs):
        instance = self.get_object()
        if instance.status != Request.Status.SUBMITTED:
            return Response({'detail': 'Only submitted requests can be rejected.'}, status=400)
        instance.status = Request.Status.REJECTED
        instance.save()
        return Response(self.get_serializer(instance).data)


class SettingsView(SingletonGUIMixin, generics.GenericAPIView):
    serializer_class   = SettingsSerializer
    permission_classes = [permissions.IsAdminUser]

    class Sebastian:
        label = 'Settings'
        groups = [
            FieldGroup('general', ['auto_approval_threshold', 'notification_email'], label='General'),
        ]

    def get_object(self):
        return Settings.get_solo()
