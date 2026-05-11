import re

from django.core.exceptions import ValidationError
from django.db import models

_CF_PARTITA_IVA = re.compile(r'^\d{11}$')
_CF_PERSONA_FIS = re.compile(r'^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$')

_CF_ERROR = (
    'Inserire una Partita IVA (11 cifre) oppure un Codice Fiscale '
    'nel formato LLLLLLNNLNNLNNNL.'
)


def _is_valid_codice_fiscale(value: str) -> bool:
    v = value.upper()
    return bool(_CF_PARTITA_IVA.match(v) or _CF_PERSONA_FIS.match(v))


class Fornitore(models.Model):
    ragione_sociale = models.CharField(max_length=200)
    codice_fiscale  = models.CharField(max_length=16, blank=True)
    attivo          = models.BooleanField(default=True)
    certificazione  = models.FileField(upload_to='fornitori/', null=True, blank=True)

    class Meta:
        verbose_name        = 'Fornitore'
        verbose_name_plural = 'Fornitori'
        ordering            = ['ragione_sociale']

    def __str__(self):
        return f"{self.pk} - {self.ragione_sociale}"

    def clean(self):
        if self.codice_fiscale and not _is_valid_codice_fiscale(self.codice_fiscale):
            raise ValidationError({'codice_fiscale': _CF_ERROR})



class Richiesta(models.Model):

    class Stato(models.TextChoices):
        BOZZA     = 'bozza',     'Bozza'
        INVIATA   = 'inviata',   'Inviata'
        APPROVATA = 'approvata', 'Approvata'
        RIFIUTATA = 'rifiutata', 'Rifiutata'

    titolo          = models.CharField(max_length=200)
    descrizione     = models.TextField(blank=True)
    budget          = models.DecimalField(max_digits=12, decimal_places=2)
    stato           = models.CharField(max_length=20, choices=Stato.choices, default=Stato.BOZZA)
    fornitore       = models.ForeignKey(
        Fornitore, on_delete=models.SET_NULL, null=True, blank=True, related_name='richieste'
    )
    note_direttore  = models.TextField(blank=True)
    cig             = models.CharField(max_length=10, blank=True)
    motivazione     = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Richiesta'
        verbose_name_plural = 'Richieste'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.pk} - {self.titolo}"


class Allegato(models.Model):
    richiesta   = models.ForeignKey(
        Richiesta, on_delete=models.CASCADE, related_name='allegati'
    )
    descrizione = models.CharField(max_length=255)
    file        = models.FileField(upload_to='allegati/')
    caricato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Allegato'
        verbose_name_plural = 'Allegati'
        ordering            = ['caricato_il']

    def __str__(self):
        return f"{self.pk} - {self.descrizione}"
