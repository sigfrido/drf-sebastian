import django_filters
from .models import Supplier, Request


class SupplierFilter(django_filters.FilterSet):
    company_name = django_filters.CharFilter(lookup_expr='icontains', label='Company name')

    class Meta:
        model  = Supplier
        fields = ['company_name', 'active']


class RequestFilter(django_filters.FilterSet):
    class Meta:
        model  = Request
        fields = ['status', 'supplier']
