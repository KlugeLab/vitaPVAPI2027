"""Backend local Django: autenticación y permisos por asignaciones VIGENTES.

Se mantiene Group y Permission nativos; NO concede la unión de roles de otras
sucursales ni permisos de asignaciones caducadas.
"""
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils import timezone
from apps.identidad.models import AsignacionSucursal


def asignaciones_vigentes(usuario):
    now = timezone.now()
    return AsignacionSucursal.objects.filter(
        empleado=usuario, sucursal_id=settings.VITA_SUCURSAL_UUID,
        sucursal__activa=True, activa=True, rol__activo=True,
    ).filter(
        Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=now),
        Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=now),
    )


class SucursalAuthBackend(ModelBackend):
    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        if user.is_staff or user.is_superuser:
            return True   # Únicamente administradores locales preautorizados
        return asignaciones_vigentes(user).exists()

    def _get_group_permissions(self, user_obj):
        if user_obj.is_staff or user_obj.is_superuser:
            return super()._get_group_permissions(user_obj)
        grupos = asignaciones_vigentes(user_obj).values_list('rol__group_id', flat=True)
        return Permission.objects.filter(group__id__in=grupos)

    def _get_user_permissions(self, user_obj):
        if user_obj.is_staff or user_obj.is_superuser:
            return super()._get_user_permissions(user_obj)
        # Ningún permiso directo a los empleados, solo por asignación/rol.
        return Permission.objects.none()
