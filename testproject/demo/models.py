from django.core.exceptions import ValidationError
from django.db import models

_TAX_CODE_ERROR = 'Tax code must be 5 to 20 alphanumeric characters (letters, digits, dashes).'


def _is_valid_tax_code(value: str) -> bool:
    stripped = value.replace('-', '')
    return 5 <= len(value) <= 20 and stripped.isalnum()


class Supplier(models.Model):
    company_name = models.CharField(max_length=200)
    tax_code      = models.CharField(max_length=20, blank=True)
    active        = models.BooleanField(default=True)
    certification = models.FileField(upload_to='suppliers/certifications/', null=True, blank=True)

    class Meta:
        verbose_name        = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering            = ['company_name']

    def __str__(self):
        return f"{self.pk} - {self.company_name}"

    def clean(self):
        if self.tax_code and not _is_valid_tax_code(self.tax_code):
            raise ValidationError({'tax_code': _TAX_CODE_ERROR})


class Request(models.Model):

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED  = 'approved',  'Approved'
        REJECTED  = 'rejected',  'Rejected'

    title          = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    budget         = models.DecimalField(max_digits=12, decimal_places=2)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    supplier       = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests'
    )
    manager_notes  = models.TextField(blank=True)
    reference_code = models.CharField(max_length=20, blank=True)
    justification  = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Request'
        verbose_name_plural = 'Requests'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.pk} - {self.title}"


class Attachment(models.Model):
    request     = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name='attachments'
    )
    description = models.CharField(max_length=255)
    file        = models.FileField(upload_to='attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Attachment'
        verbose_name_plural = 'Attachments'
        ordering            = ['uploaded_at']

    def __str__(self):
        return f"{self.pk} - {self.description}"


class Settings(models.Model):
    """Singleton settings row — see demo/views.py:SettingsView (SingletonGUIMixin)."""

    auto_approval_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Requests with a budget below this amount could be auto-approved.',
    )
    notification_email = models.EmailField(blank=True)

    class Meta:
        verbose_name = 'Settings'

    def __str__(self):
        return 'Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
