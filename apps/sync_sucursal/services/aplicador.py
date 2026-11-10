"""Consumidor con cursores atómicos, UUID global e idempotencia.

Ningún modelo global recibe el permiso de editarse desde sucursal.
Los permisos ausentes del Django local NO se conceden automáticamente.
"""
import uuid
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.identidad.models import Rol, CatalogoPermiso, RolPermiso, AsignacionSucursal
from apps.organizacion.models import Sucursal
from apps.sync_sucursal.models import EstadoSincronizacion, EventoAplicado


class ErrorSincronizacion(Exception):
    pass


def _uuid(valor):
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError, AttributeError):
        raise ErrorSincronizacion('UUID inválido en la respuesta central.')


def _fecha(valor):
    if not valor:
        return None
    d = parse_datetime(valor)
    if d is None:
        raise ErrorSincronizacion('Fecha inválida en una asignación.')
    if timezone.is_naive(d):
        raise ErrorSincronizacion('La fecha debe incluir zona horaria.')
    return d


def _empleado(datos):
    Empleado = get_user_model()
    uid = _uuid(datos['uuid'])
    obj = Empleado.objects.filter(pk=uid).first()
    if obj is None:
        obj = Empleado(pk=uid)
        obj.set_unusable_password()   # Nunca inventar contraseña local
        obj.version_credenciales = 0   # Contraseña pendiente de canal seguro
    if obj.is_staff or obj.is_superuser:
        raise ErrorSincronizacion('No se puede sobrescribir usuario administrativo local.')
    version = int(datos['version'])
    if obj.pk and obj.pk == uid and obj.version > version and obj._state.adding is False:
        return obj
    obj.username = datos['username']
    obj.codigo_empleado = datos['codigo_empleado']
    obj.first_name = datos.get('first_name','')
    obj.last_name = datos.get('last_name','')
    obj.email = datos.get('email','')
    obj.is_active = bool(datos['is_active'])
    obj.is_staff = False
    obj.is_superuser = False
    obj.version = version
    obj.save()
    return obj


def _sucursal(datos, sucursal_id):
    if _uuid(datos['uuid']) != sucursal_id:
        raise ErrorSincronizacion('Intento de aplicar información de otra sucursal.')
    version = int(datos.get('version', 1))
    anterior = Sucursal.objects.filter(pk=sucursal_id).first()
    if anterior and anterior.version > version:
        return anterior  # No degradar snapshot reciente con un evento atrasado.
    campos = ('tipo','estado','municipio','codigo_postal','colonia','calle',
              'numero_exterior','numero_interior','domicilio_fiscal','rfc','correo','telefono')
    defaults = {'codigo': datos['codigo'], 'nombre': datos['nombre'],
                'activa': bool(datos['activa']), 'version': version}
    for campo in campos:
        if campo in datos:
            defaults[campo] = datos[campo] or ''
    obj, _ = Sucursal.objects.update_or_create(pk=sucursal_id, defaults=defaults)
    return obj


def _rol(datos):
    rid = _uuid(datos['uuid'])
    rol = Rol.objects.select_related('group').filter(pk=rid).first()
    if rol is not None and rol.version > int(datos['version']):
        return rol
    if rol is None:
        grupo = Group.objects.create(name=datos['nombre'])
        rol = Rol(uuid=rid, group=grupo)
    else:
        grupo = rol.group
        grupo.name = datos['nombre']
        grupo.save(update_fields=['name'])
    rol.codigo = datos['codigo']
    rol.descripcion = datos.get('descripcion','')
    rol.activo = bool(datos['activo'])
    rol.version = int(datos['version'])
    rol.save()
    permisos_logicos = []
    permisos_locales = []
    faltantes = []
    for d in datos.get('permisos', []):
        if not d.get('activo', True):
            continue
        p, _ = CatalogoPermiso.objects.update_or_create(
            pk=_uuid(d['uuid']),
            defaults={
                'app_label': d['app_label'], 'modelo': d['modelo'],
                'codename': d['codename'], 'descripcion': d['descripcion'],
                'activo': bool(d['activo']), 'version': int(d.get('version',1)),
            }
        )
        permisos_logicos.append(RolPermiso(rol=rol, permiso=p))
        permiso_django = Permission.objects.filter(
            content_type__app_label=d['app_label'],
            content_type__model=d['modelo'],
            codename=d['codename'],
        ).first()
        if permiso_django is None:
            faltantes.append(f"{d['app_label']}.{d['modelo']}.{d['codename']}")
        else:
            permisos_locales.append(permiso_django)
    RolPermiso.objects.filter(rol=rol).delete()
    RolPermiso.objects.bulk_create(permisos_logicos)
    grupo.permissions.set(permisos_locales)
    # Nunca conceder permisos inexistentes. El rol sigue siendo registrable.
    if faltantes:
        import logging
        logging.getLogger(__name__).warning('Permisos sin modelo local: %s', ', '.join(faltantes))
    return rol


def _asignacion(datos, sucursal_id):
    if _uuid(datos['sucursal_uuid']) != sucursal_id:
        raise ErrorSincronizacion('Asignación dirigida a una sucursal incorrecta.')
    empleado = get_user_model().objects.get(pk=_uuid(datos['empleado_uuid']))
    rol = Rol.objects.get(pk=_uuid(datos['rol_uuid']))
    sucursal = Sucursal.objects.get(pk=sucursal_id)
    aid = _uuid(datos['uuid'])
    obj = AsignacionSucursal.objects.filter(pk=aid).first()
    if obj and obj.version > int(datos['version']):
        return obj
    obj, _ = AsignacionSucursal.objects.update_or_create(
        pk=aid,
        defaults={
            'empleado': empleado, 'rol': rol, 'sucursal': sucursal,
            'activa': bool(datos['activa']), 'version': int(datos['version']),
            'vigente_desde': _fecha(datos.get('vigente_desde')),
            'vigente_hasta': _fecha(datos.get('vigente_hasta')),
        },
    )
    return obj


def actualizar_grupos_locales(sucursal_uuid):
    """Usa Group nativo de Django, limitado a los roles de esta sucursal."""
    Empleado = get_user_model()
    now = timezone.now()
    qs = (AsignacionSucursal.objects.filter(sucursal_id=sucursal_uuid, activa=True,
                                           empleado__is_active=True, rol__activo=True)
          .select_related('rol__group'))
    grupos = {}
    for asignacion in qs:
        if asignacion.vigente_desde and asignacion.vigente_desde > now:
            continue
        if asignacion.vigente_hasta and asignacion.vigente_hasta <= now:
            continue
        grupos.setdefault(asignacion.empleado_id, set()).add(asignacion.rol.group_id)
    for empleado in Empleado.objects.filter(is_staff=False, is_superuser=False):
        empleado.groups.set(grupos.get(empleado.pk, set()))
    # La existencia de contraseña no concede acceso: SucursalAuthBackend
    # valida asignación activa y vigente en cada autenticación y permiso.



def aplicar_evento(evento, sucursal_uuid):
    """Se llama dentro de una transacción de lote."""
    if int(evento['schema_version']) != 1:
        raise ErrorSincronizacion('Versión de contrato no compatible.')
    event_id = _uuid(evento['event_id'])
    if EventoAplicado.objects.filter(pk=event_id).exists():
        return False
    entidad = evento['entity']
    datos = evento['payload']
    if entidad == 'asignacion':
        if 'empleado' in datos:
            _sucursal(datos['sucursal'], sucursal_uuid)
            _empleado(datos['empleado'])
            _rol(datos['rol'])
            _asignacion(datos['asignacion'], sucursal_uuid)
        else:
            # Evento de baja de asignación: debe existir previamente.
            _asignacion(datos, sucursal_uuid)
    elif entidad == 'empleado':
        # Altas sin asignación no se dirigen a sucursales.
        _empleado(datos)
    elif entidad == 'rol':
        _rol(datos)
    elif entidad == 'sucursal':
        _sucursal(datos, sucursal_uuid)
    elif entidad == 'credencial':
        pass  # Sólo dispara descarga por canal de credenciales separado
    elif entidad == 'catalogo_permiso':
        pass  # La definición se incluye en cada snapshot completo de rol
    else:
        raise ErrorSincronizacion('Tipo de evento no reconocido: '+str(entidad))
    EventoAplicado.objects.create(
        event_id=event_id, tipo_entidad=entidad, version_entidad=int(evento['version'])
    )
    return True


@transaction.atomic
def aplicar_bootstrap(datos, sucursal_uuid):
    if datos.get('schema_version') != 1:
        raise ErrorSincronizacion('Versión de contrato no soportada.')
    _sucursal(datos['sucursal'], sucursal_uuid)
    ids = set()
    for conjunto in datos['asignaciones']:
        _empleado(conjunto['empleado'])
        _rol(conjunto['rol'])
        _asignacion(conjunto['asignacion'], sucursal_uuid)
        ids.add(_uuid(conjunto['asignacion']['uuid']))
    # Desactivar lo que no aparece en el snapshot maestro actual.
    AsignacionSucursal.objects.filter(sucursal_id=sucursal_uuid).exclude(pk__in=ids).update(activa=False)
    empleados_vigentes = set(AsignacionSucursal.objects.filter(
        sucursal_id=sucursal_uuid, activa=True
    ).values_list('empleado_id', flat=True))
    get_user_model().objects.filter(is_staff=False, is_superuser=False).exclude(
        pk__in=empleados_vigentes
    ).update(is_active=False)
    actualizar_grupos_locales(sucursal_uuid)
    estado, _ = EstadoSincronizacion.objects.select_for_update().get_or_create(flujo='identidad')
    estado.ultimo_cursor = str(datos['cursor'])
    estado.ultima_sincronizacion = timezone.now()
    estado.estado = 'correcto'
    estado.mensaje_error = ''
    estado.save()


@transaction.atomic
def aplicar_lote(datos, sucursal_uuid):
    if datos.get('schema_version') != 1:
        raise ErrorSincronizacion('Versión de contrato no soportada.')
    estado = EstadoSincronizacion.objects.select_for_update().get(flujo='identidad')
    cursor_actual = int(estado.ultimo_cursor)
    eventos = datos['events']
    sec_anterior = cursor_actual
    for evento in eventos:
        seq = int(evento['sequence'])
        if seq <= sec_anterior:
            raise ErrorSincronizacion('Secuencia de evento no creciente.')
        sec_anterior = seq
        aplicar_evento(evento, sucursal_uuid)
    cursor_nuevo = int(datos['next_cursor'])
    if cursor_nuevo < sec_anterior or cursor_nuevo < cursor_actual:
        raise ErrorSincronizacion('Cursor regresivo o inconsistente.')
    actualizar_grupos_locales(sucursal_uuid)
    estado.ultimo_cursor = str(cursor_nuevo)
    estado.ultima_sincronizacion = timezone.now()
    estado.estado = 'correcto'
    estado.mensaje_error = ''
    estado.save()
    return len(eventos)


@transaction.atomic
def aplicar_credenciales(datos):
    if datos.get('schema_version') != 1:
        raise ErrorSincronizacion('Versión de credenciales no soportada.')
    Empleado = get_user_model()
    total = 0
    for item in datos['credentials']:
        empleado = Empleado.objects.select_for_update().filter(pk=_uuid(item['empleado_uuid'])).first()
        if empleado is None or not empleado.is_active or empleado.is_staff or empleado.is_superuser:
            continue
        version = int(item['version_credenciales'])
        if version > empleado.version_credenciales or not empleado.has_usable_password():
            encoded = item['password_hash']
            if not isinstance(encoded, str) or len(encoded) > 512 or len(encoded) < 20:
                raise ErrorSincronizacion('Hash de contraseña con formato inválido.')
            from django.contrib.auth.hashers import identify_hasher
            try:
                identify_hasher(encoded)
            except ValueError as exc:
                raise ErrorSincronizacion('Algoritmo de hash no reconocido en sucursal.') from exc
            empleado.password = encoded
            empleado.version_credenciales = version
            empleado.save(update_fields=['password', 'version_credenciales', 'actualizado_en'])
            total += 1
    return total
