from django.db import models


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
