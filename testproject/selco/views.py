from django.http import FileResponse
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from sebastian.mixins import GUIMixin, NestedGUIMixin
from sebastian.config import FieldGroup, MenuGroup, MenuItem
from sebastian.decorators import action
from .models import Fornitore, Richiesta, Allegato
from .serializers import FornitoreSerializer, RichiestaSerializer, AllegatoSerializer, InviaSerializer
from .filters import FornitoreFilter, RichiestaFilter


def perm_fail(request, _obj):
    return False

def perm_is_admin(request, _obj):
    return request.user.is_staff


def perm_richiesta_stato(stato):
    def has_perm(request, _obj):
        return _obj.stato == stato
    return has_perm


def perm_stato_inviata_o_approvata(request, obj):
    if obj is None:
        return False
    return obj.stato in (Richiesta.Stato.INVIATA, Richiesta.Stato.APPROVATA)


def perm_is_invia_action(request, obj):
    view = request.parser_context.get('view')
    return getattr(view, 'action', None) == 'invia'
    

class FornitoreViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Fornitore.objects.all()
    serializer_class = FornitoreSerializer
    filterset_class  = FornitoreFilter

    class Sebastian:
        menu = MenuGroup('Fornitori', icon='building', items=[
            MenuItem('Elenco', action='list', icon='list-ul'),
            MenuItem('Nuovo',  action='new',  icon='plus-circle'),
        ])
        groups = [
            FieldGroup('anagrafica', ['ragione_sociale', 'codice_fiscale', 'attivo'],
                       label='Anagrafica'),
            FieldGroup('documenti', ['certificazione'], label='Documenti'),
        ]

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':    'Scarica',
            'icon':     'download',
            'color':    'outline-secondary',
            'position': 'both',
        },
    )
    def download(self, request, pk=None, **kwargs):
        instance = self.get_object()
        filename = instance.certificazione.name.split('/')[-1]
        return FileResponse(instance.certificazione.open('rb'), as_attachment=True, filename=filename)



class AllegatoViewSet(NestedGUIMixin, viewsets.ModelViewSet):
    queryset         = Allegato.objects.all()
    serializer_class = AllegatoSerializer
    mountpoint       = 'allegati'

    class Sebastian:
        label  = 'Allegati'
        groups = [
            FieldGroup('dati', ['descrizione', 'file', 'caricato_il'], label='Dati'),
        ]

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':    'Scarica',
            'icon':     'download',
            'color':    'outline-secondary',
            'position': 'list',
        },
    )
    def download(self, request, pk=None, **kwargs):
        instance = self.get_object()
        filename = instance.file.name.split('/')[-1]
        return FileResponse(instance.file.open('rb'), as_attachment=True, filename=filename)


class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Richiesta.objects.select_related('fornitore').all()
    serializer_class = RichiestaSerializer
    filterset_class  = RichiestaFilter

    class Sebastian:
        menu = MenuGroup('Richieste', icon='clipboard-check', items=[
            MenuItem('Elenco', action='list', icon='list-ul'),
            MenuItem('Nuova',  action='new',  icon='plus-circle', permission=(perm_is_admin,)),
        ])
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
                edit_permission=(perm_is_admin, ),
            ),
            FieldGroup(
                'invia',
                ['motivazione'],
                label='Motivazione Invio',
                visible_permission=perm_stato_inviata_o_approvata,
                edit_permission=perm_is_invia_action,
            ),
        ]
        inlines = [AllegatoViewSet]

    @action(
        detail=True,
        methods=['get', 'post'],
        permission_classes=[permissions.IsAuthenticated],
        gui_config={
            'label':                  'Invia',
            'icon':                   'send',
            'color':                  'primary',
            'position':               'detail',
            'permission':             [perm_richiesta_stato(Richiesta.Stato.BOZZA)],
            'confirmation_serializer': InviaSerializer,
            'action_label':           'Invia Richiesta',
        },
    )
    def invia(self, request, pk=None, **kwargs):
        instance = self.get_object()
        parent_url = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
        if request.method == 'GET':
            serializer = InviaSerializer(
                {'motivazione': instance.motivazione or '', 'verifica': False}
            )
            return Response({
                'serializer':   serializer,
                'instance':     {'motivazione': instance.motivazione or '', 'verifica': False},
                'action':       'confirm_action',
                'action_label': 'Invia Richiesta',
                'submit_url':   request.path,
                'cancel_url':   parent_url,
                'htmx_target':  '#sebastian-modal',
            })
        # POST
        if getattr(request, 'sebastian_gui', False):
            # GUI: validate full confirmation form (motivazione + verifica checkbox)
            serializer = InviaSerializer(data=request.data)
            if not serializer.is_valid():
                resp = Response({
                    'serializer':   serializer,
                    'instance':     request.data,
                    'action':       'confirm_action',
                    'action_label': 'Invia Richiesta',
                    'submit_url':   request.path,
                    'cancel_url':   parent_url,
                    'htmx_target':  '#sebastian-modal',
                }, status=400)
                resp['X-Sebastian-Form-Error'] = 'true'
                return resp
            motivazione = serializer.validated_data['motivazione']
        else:
            # API: verifica is a GUI-only policy checkbox; accept motivazione directly
            motivazione = request.data.get('motivazione', '')
        if instance.stato != Richiesta.Stato.BOZZA:
            return Response({'detail': 'Solo le bozze possono essere inviate.'}, status=400)
        instance.motivazione = motivazione
        instance.stato = Richiesta.Stato.INVIATA
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        gui_config={
            'label':      'Approva',
            'icon':       'check-circle',
            'color':      'success',
            'confirm':    'Confermi approvazione?',
            'position':   'detail',
            'permission': [
                perm_is_admin,
                perm_richiesta_stato(Richiesta.Stato.INVIATA),
            ],
        },
    )
    def approva(self, request, pk=None, **kwargs):
        instance = self.get_object()
        if instance.stato != Richiesta.Stato.INVIATA:
            return Response({'detail': 'Solo le richieste inviate possono essere approvate.'}, status=400)
        instance.stato = Richiesta.Stato.APPROVATA
        instance.save()
        return Response(self.get_serializer(instance).data)
