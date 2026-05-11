from rest_framework import serializers
from sebastian.serializers import GUISerializerMixin, NullableFileField
from .models import Fornitore, Richiesta, Allegato


class InviaSerializer(serializers.Serializer):
    motivazione = serializers.CharField(
        label='Motivazione',
        required=True,
    )
    verifica = serializers.BooleanField(
        label=(
            'Ho verificato che la richiesta sia nel budget '
            'disponibile per la mia Direzione'
        ),
        required=True,
    )

    def validate_verifica(self, value):
        if not value:
            raise serializers.ValidationError(
                'Devi confermare la verifica prima di inviare.'
            )
        return value


class FornitoreSerializer(GUISerializerMixin, serializers.ModelSerializer):
    certificazione = NullableFileField(allow_null=True, required=False)

    class Meta:
        model  = Fornitore
        fields = ['id', 'ragione_sociale', 'codice_fiscale', 'attivo', 'certificazione']


class AllegatoSerializer(GUISerializerMixin, serializers.ModelSerializer):
    class Meta:
        model  = Allegato
        fields = ['id', 'descrizione', 'file', 'caricato_il']
        read_only_fields = ['caricato_il']


class RichiestaSerializer(GUISerializerMixin, serializers.ModelSerializer):
    fornitore_nome = serializers.CharField(source='fornitore.ragione_sociale', read_only=True)

    class Meta:
        model  = Richiesta
        fields = [
            'id', 'titolo', 'descrizione', 'budget', 'stato',
            'fornitore', 'fornitore_nome',
            'note_direttore', 'cig', 'motivazione',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_sebastian_description(self, field_name, related_obj):
        if field_name == 'fornitore':
            return f'{related_obj.pk} - {related_obj.ragione_sociale} ({related_obj.codice_fiscale})'
        return super().get_sebastian_description(field_name, related_obj)
