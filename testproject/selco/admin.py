from django.contrib import admin
from .models import Fornitore, Richiesta, Allegato


@admin.register(Fornitore)
class FornitoreAdmin(admin.ModelAdmin):
    list_display = ['ragione_sociale', 'codice_fiscale', 'attivo']
    list_filter  = ['attivo']
    search_fields = ['ragione_sociale', 'codice_fiscale']


@admin.register(Richiesta)
class RichiestaAdmin(admin.ModelAdmin):
    list_display  = ['titolo', 'stato', 'fornitore', 'budget', 'created_at']
    list_filter   = ['stato', 'fornitore']
    search_fields = ['titolo', 'descrizione']
    raw_id_fields = ['fornitore']


@admin.register(Allegato)
class AllegatoAdmin(admin.ModelAdmin):
    list_display = ['descrizione', 'richiesta', 'caricato_il']
