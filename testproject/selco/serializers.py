from rest_framework import serializers
from sebastian.serializers import GUISerializer
from .models import Fornitore, Richiesta, Allegato


class FornitoreSerializer(GUISerializer, serializers.ModelSerializer):
    class Meta:
        model  = Fornitore
        fields = ['id', 'ragione_sociale', 'codice_fiscale', 'attivo']


class AllegatoSerializer(GUISerializer, serializers.ModelSerializer):
    class Meta:
        model  = Allegato
        fields = ['id', 'descrizione', 'file', 'caricato_il']
        read_only_fields = ['caricato_il']


class RichiestaSerializer(GUISerializer, serializers.ModelSerializer):
    fornitore_nome = serializers.CharField(source='fornitore.ragione_sociale', read_only=True)

    class Meta:
        model  = Richiesta
        fields = [
            'id', 'titolo', 'descrizione', 'budget', 'stato',
            'fornitore', 'fornitore_nome',
            'note_direttore', 'cig',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_sebastian_description(self, field_name, related_obj):
        if field_name == 'fornitore':
            return f'{related_obj.pk} - {related_obj.ragione_sociale} ({related_obj.codice_fiscale})'
        return super().get_sebastian_description(field_name, related_obj)
