import django_filters
from .models import Fornitore, Richiesta


class FornitoreFilter(django_filters.FilterSet):
    ragione_sociale = django_filters.CharFilter(lookup_expr='icontains', label='Ragione sociale')

    class Meta:
        model  = Fornitore
        fields = ['ragione_sociale', 'attivo']


class RichiestaFilter(django_filters.FilterSet):
    class Meta:
        model  = Richiesta
        fields = ['stato', 'fornitore']
