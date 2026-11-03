import uuid
from django.db import models

class Sucursal(models.Model):
    """Identidad global de una sucursal (mismo UUID en central y copia local)."""
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'
