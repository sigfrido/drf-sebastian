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
        required=False,
        default=False,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        richiesta = self.context.get('confirmation_instance')
        if richiesta is not None and richiesta.stato != Richiesta.Stato.BOZZA:
            raise serializers.ValidationError(
                'Solo le bozze possono essere inviate.'
            )
        if not attrs.get('verifica', False):
            raise serializers.ValidationError(
                {'verifica': 'Devi confermare la verifica prima di inviare.'}
            )
        return attrs


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
    num_allegati = serializers.SerializerMethodField()
    class Meta:
        model  = Richiesta
        fields = [
            'id', 'titolo', 'descrizione', 'budget', 'stato',
            'fornitore', 'fornitore_nome',
            'note_direttore', 'cig', 'motivazione',
            'created_at', 'updated_at', 'num_allegati',
        ]
        read_only_fields = ['created_at', 'updated_at', 'num_allegati']

    def get_sebastian_description(self, field_name, related_obj):
        if field_name == 'fornitore':
            return f'{related_obj.pk} - {related_obj.ragione_sociale} ({related_obj.codice_fiscale})'
        return super().get_sebastian_description(field_name, related_obj)
    
    def get_num_allegati(self, obj):
        return obj.allegati.count()
