import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models import F, Q

class Empleado(AbstractUser):
    """Usuario global basado en autenticación nativa de Django.

    En sucursales se replica con EL MISMO UUID, distinto a sus grupos locales.
    Las altas y modificaciones operativas estarán a cargo de servicios centrales.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_empleado = models.CharField(max_length=30, unique=True)
    version = models.PositiveBigIntegerField(default=1)
    version_credenciales = models.PositiveBigIntegerField(default=1)
    actualizado_en = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ['email', 'codigo_empleado']

    class Meta:
        ordering = ['username']
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'

    def __str__(self):
        return self.get_full_name() or self.username

class Rol(models.Model):
    """Metadatos replicables de un Group nativo de Django."""
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.OneToOneField(Group, on_delete=models.PROTECT, related_name='vita_rol')
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['codigo']

    def __str__(self):
        return self.group.name

class CatalogoPermiso(models.Model):
    """Definición lógica central, incluso si el módulo solo existe en sucursal.

    El mapeo con auth.Permission se resuelve en cada sucursal usando
    (app_label, modelo, codename) y no IDs numéricos entre bases de datos.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_label = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    codename = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['app_label', 'modelo', 'codename'],
                name='uq_catalogo_permiso_natural',
            ),
        ]
        ordering = ['app_label', 'modelo', 'codename']

    def __str__(self):
        return f'{self.app_label}.{self.modelo}.{self.codename}'

class RolPermiso(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='reglas_permisos')
    permiso = models.ForeignKey(CatalogoPermiso, on_delete=models.PROTECT, related_name='roles')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['rol', 'permiso'], name='uq_rol_permiso'),
        ]

class AsignacionSucursal(models.Model):
    """Rol del empleado CONTEXTUALIZADO a una sucursal.

    Central: verdad maestra. Sucursal: copia de las asignaciones de SU sitio.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empleado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='asignaciones_sucursales')
    sucursal = models.ForeignKey('organizacion.Sucursal', on_delete=models.PROTECT, related_name='asignaciones_usuarios')
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name='asignaciones')
    activa = models.BooleanField(default=True)
    vigente_desde = models.DateTimeField(null=True, blank=True)
    vigente_hasta = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['empleado', 'sucursal', 'rol'],
                name='uq_asignacion_empleado_sucursal_rol',
            ),
            models.CheckConstraint(
                condition=Q(vigente_hasta__isnull=True) | Q(vigente_desde__isnull=True) | Q(vigente_hasta__gte=F('vigente_desde')),
                name='ck_asignacion_vigencia',
            ),
        ]
        indexes = [models.Index(fields=['sucursal', 'activa'])]

    def __str__(self):
        return f'{self.empleado.username} / {self.sucursal.codigo} / {self.rol.codigo}'
