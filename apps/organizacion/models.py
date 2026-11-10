import uuid
from django.db import models

class Sucursal(models.Model):
    """Identidad global de una sucursal (mismo UUID en central y copia local)."""
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    # Copia de sólo lectura del snapshot central (no requiere catálogos SEPOMEX locales).
    tipo = models.CharField(max_length=10, default='SUCURSAL')
    version = models.PositiveBigIntegerField(default=1)
    estado = models.CharField(max_length=100, blank=True)
    municipio = models.CharField(max_length=110, blank=True)
    codigo_postal = models.CharField(max_length=5, blank=True)
    colonia = models.CharField(max_length=150, blank=True)
    calle = models.CharField(max_length=150, blank=True)
    numero_exterior = models.CharField(max_length=20, blank=True)
    numero_interior = models.CharField(max_length=20, blank=True)
    domicilio_fiscal = models.TextField(blank=True)
    rfc = models.CharField(max_length=13, blank=True)
    correo = models.EmailField(max_length=254, blank=True)
    telefono = models.CharField(max_length=25, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'
