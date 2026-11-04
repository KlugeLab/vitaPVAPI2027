import uuid
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from apps.identidad.models import AsignacionSucursal, Rol
from apps.sync_sucursal.services.aplicador import aplicar_bootstrap, aplicar_lote, aplicar_credenciales
from apps.sync_sucursal.models import EstadoSincronizacion


class AplicadorSucursalTest(TestCase):
    def setUp(self):
        self.sucursal = uuid.uuid4()
        self.empleado = uuid.uuid4()
        self.rol = uuid.uuid4()
        self.asignacion = uuid.uuid4()
        self.permiso = uuid.uuid4()
        self.override = override_settings(VITA_SUCURSAL_UUID=self.sucursal)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.snapshot = {
            'schema_version': 1, 'cursor': '10',
            'sucursal': {'uuid': str(self.sucursal), 'codigo': 'SUC-001',
                         'nombre': 'Sucursal laboratorio', 'activa': True},
            'asignaciones': [{
                'empleado': {'uuid':str(self.empleado), 'username':'caja01',
                             'codigo_empleado':'EMP-001', 'first_name':'Juan',
                             'last_name':'Perez', 'email':'', 'is_active':True,
                             'version':1, 'version_credenciales':1},
                'rol': {'uuid':str(self.rol), 'codigo':'CAJERO', 'nombre':'Cajero',
                        'descripcion':'', 'activo':True, 'version':2,
                        'permisos':[{'uuid': str(self.permiso),
                          'app_label':'identidad', 'modelo':'empleado',
                          'codename':'view_empleado','descripcion':'Ver empleados',
                          'activo':True, 'version':1}]},
                'sucursal': {'uuid': str(self.sucursal), 'codigo':'SUC-001',
                             'nombre':'Sucursal laboratorio','activa':True},
                'asignacion': {'uuid':str(self.asignacion),
                         'empleado_uuid':str(self.empleado),
                         'rol_uuid':str(self.rol),'sucursal_uuid':str(self.sucursal),
                         'activa':True,'version':1,'vigente_desde':None,
                         'vigente_hasta':None},
            }],
        }

    def test_bootstrap_credencial_autenticacion_y_permiso(self):
        aplicar_bootstrap(self.snapshot, self.sucursal)
        user = get_user_model().objects.get(pk=self.empleado)
        self.assertFalse(user.has_usable_password())
        self.assertIsNone(authenticate(username='caja01', password='ClavePrueba!2026'))
        aplicar_credenciales({'schema_version':1, 'credentials': [{
            'empleado_uuid': str(self.empleado), 'version_credenciales':1,
            'password_hash': make_password('ClavePrueba!2026'),
        }]})
        user = authenticate(username='caja01', password='ClavePrueba!2026')
        self.assertIsNotNone(user)
        self.assertTrue(user.has_perm('identidad.view_empleado'))
        self.assertFalse(user.has_perm('identidad.delete_empleado'))

    def test_revocacion_rol_invalida_permisos(self):
        aplicar_bootstrap(self.snapshot, self.sucursal)
        rol = dict(self.snapshot['asignaciones'][0]['rol'], activo=False, version=3)
        evento = {'event_id': str(uuid.uuid4()),'sequence':11,
                  'entity':'rol', 'operation':'deactivated',
                  'entity_uuid':str(self.rol), 'version':3,
                  'schema_version':1,'payload':rol}
        aplicar_lote({'schema_version':1,'events':[evento],
                      'next_cursor':'11','has_more':False}, self.sucursal)
        u = get_user_model().objects.get(pk=self.empleado)
        self.assertFalse(u.has_perm('identidad.view_empleado'))
        self.assertEqual(EstadoSincronizacion.objects.get(flujo='identidad').ultimo_cursor,'11')

    def test_idempotencia_eventos(self):
        aplicar_bootstrap(self.snapshot, self.sucursal)
        rol = dict(self.snapshot['asignaciones'][0]['rol'], version=3)
        eid = str(uuid.uuid4())
        evento = {'event_id': eid,'sequence':11,'entity':'rol',
                  'operation':'updated','entity_uuid':str(self.rol),
                  'version':3,'schema_version':1,'payload':rol}
        aplicar_lote({'schema_version':1,'events':[evento],
                      'next_cursor':'11','has_more':False},self.sucursal)
        # Nuevo cursor con evento ya visto (mismo event_id): no duplicar.
        evento2 = dict(evento, sequence=12)
        aplicar_lote({'schema_version':1,'events':[evento2],
                      'next_cursor':'12','has_more':False},self.sucursal)
        self.assertEqual(Rol.objects.get(pk=self.rol).version,3)

    def test_asignacion_caducada_no_concede_permiso(self):
        aplicar_bootstrap(self.snapshot, self.sucursal)
        aplicar_credenciales({'schema_version':1,'credentials':[{
            'empleado_uuid':str(self.empleado),'version_credenciales':1,
            'password_hash':make_password('ClavePrueba!2026')}]})
        AsignacionSucursal.objects.filter(pk=self.asignacion).update(activa=False)
        self.assertIsNone(authenticate(username='caja01', password='ClavePrueba!2026'))
