import uuid
from django.db import models

class EstadoSincronizacion(models.Model):
    flujo = models.CharField(max_length=40, unique=True)
    ultimo_cursor = models.CharField(max_length=100, blank=True)
    ultimo_intento = models.DateTimeField(null=True, blank=True)
    ultima_sincronizacion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='pendiente')
    mensaje_error = models.TextField(blank=True)

class EventoAplicado(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_entidad = models.CharField(max_length=50)
    version_entidad = models.PositiveBigIntegerField()
    aplicado_en = models.DateTimeField(auto_now_add=True)
