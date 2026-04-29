from rest_framework import viewsets, permissions
from rest_framework.response import Response
from sebastian.mixins import GUIMixin
from sebastian.config import FieldGroup, EntityGroup
from sebastian.decorators import action
from .models import Fornitore, Richiesta
from .serializers import FornitoreSerializer, RichiestaSerializer, AllegatoSerializer


class FornitoreViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Fornitore.objects.all()
    serializer_class = FornitoreSerializer
    filterset_fields = ['ragione_sociale', 'attivo']

    class Sebastian:
        groups = [
            FieldGroup('anagrafica', ['ragione_sociale', 'codice_fiscale', 'attivo'],
                       label='Anagrafica'),
        ]


class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Richiesta.objects.select_related('fornitore').all()
    serializer_class = RichiestaSerializer
    filterset_fields = ['stato', 'fornitore']

    class Sebastian:
        groups = [
            FieldGroup(
                'generale',
                ['titolo', 'descrizione', 'budget', 'stato', 'fornitore'],
                label='Generale',
            ),
            FieldGroup(
                'direzione',
                ['note_direttore', 'cig'],
                label='Direzione',
                # example: restrict editing to directors
                # edit_permission=lambda req, obj: req.user.groups.filter(name='direttori').exists(),
            ),
            EntityGroup(
                'allegati',
                model=None,           # set below to avoid circular import at class-body time
                serializer_class=AllegatoSerializer,
                label='Allegati',
                related_field='richiesta',
            ),
        ]

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':    'Invia',
            'icon':     'send',
            'color':    'primary',
            'confirm':  'Confermi invio della richiesta?',
            'position': 'detail',
        },
    )
    def invia(self, request, pk=None):
        instance = self.get_object()
        if instance.stato != Richiesta.Stato.BOZZA:
            return Response({'detail': 'Solo le bozze possono essere inviate.'}, status=400)
        instance.stato = Richiesta.Stato.INVIATA
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        gui_config={
            'label':    'Approva',
            'icon':     'check-circle',
            'color':    'success',
            'confirm':  'Confermi approvazione?',
            'position': 'detail',
        },
    )
    def approva(self, request, pk=None):
        instance = self.get_object()
        if instance.stato != Richiesta.Stato.INVIATA:
            return Response({'detail': 'Solo le richieste inviate possono essere approvate.'}, status=400)
        instance.stato = Richiesta.Stato.APPROVATA
        instance.save()
        return Response(self.get_serializer(instance).data)


# Patch EntityGroup model reference (avoids circular import at class-body time)
from .models import Allegato  # noqa: E402
RichiestaViewSet.Sebastian.groups[2].model = Allegato
