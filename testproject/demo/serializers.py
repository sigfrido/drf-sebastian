from django.utils import timezone
from rest_framework import serializers
from sebastian.serializers import GUISerializerMixin, NullableFileField, gui_field
from .models import Supplier, Request, Attachment, Settings


class SubmitSerializer(serializers.Serializer):
    justification = serializers.CharField(
        label='Justification',
        required=True,
    )
    confirmed = serializers.BooleanField(
        label='I confirm this request is within my department\'s available budget',
        required=False,
        default=False,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request_obj = self.context.get('confirmation_instance')
        if request_obj is not None and request_obj.status != Request.Status.DRAFT:
            raise serializers.ValidationError(
                'Only draft requests can be submitted.'
            )
        if not attrs.get('confirmed', False):
            raise serializers.ValidationError(
                {'confirmed': 'You must confirm the budget check before submitting.'}
            )
        return attrs


class SupplierSerializer(GUISerializerMixin, serializers.ModelSerializer):
    certification = NullableFileField(allow_null=True, required=False)

    class Meta:
        model  = Supplier
        fields = ['id', 'company_name', 'tax_code', 'active', 'certification']


class AttachmentSerializer(GUISerializerMixin, serializers.ModelSerializer):
    class Meta:
        model  = Attachment
        fields = ['id', 'description', 'file', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class RequestSerializer(GUISerializerMixin, serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    num_attachments = serializers.SerializerMethodField()

    class Meta:
        model  = Request
        fields = [
            'id', 'title', 'description', 'budget', 'status',
            'supplier', 'supplier_name',
            'manager_notes', 'reference_code', 'justification',
            'created_at', 'updated_at', 'num_attachments',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at', 'num_attachments']

    def get_sebastian_description(self, field_name, related_obj):
        if field_name == 'supplier':
            return f'{related_obj.pk} - {related_obj.company_name} ({related_obj.tax_code})'
        return super().get_sebastian_description(field_name, related_obj)

    def get_num_attachments(self, obj):
        return obj.attachments.count()

    @gui_field('Days open')
    def days_open(self, obj):
        return (timezone.now() - obj.created_at).days


class SettingsSerializer(GUISerializerMixin, serializers.ModelSerializer):
    class Meta:
        model  = Settings
        fields = ['auto_approval_threshold', 'notification_email']
