from django.contrib import admin
from .models import Supplier, Request, Attachment


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'tax_code', 'active']
    list_filter  = ['active']
    search_fields = ['company_name', 'tax_code']


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display  = ['title', 'status', 'supplier', 'budget', 'created_at']
    list_filter   = ['status', 'supplier']
    search_fields = ['title', 'description']
    raw_id_fields = ['supplier']


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['description', 'request', 'uploaded_at']
