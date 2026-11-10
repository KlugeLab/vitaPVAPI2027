from uuid import uuid4
from django.test import TestCase
from apps.organizacion.models import Sucursal
from apps.sync_sucursal.services.aplicador import _sucursal

class SucursalReplicaV5Tests(TestCase):
    def test_extiende_campos_sin_romper_contrato_v1(self):
        uid=uuid4()
        datos={'uuid':str(uid),'codigo':'SUC-001','nombre':'Laboratorio','activa':True,
               'version':4,'tipo':'SUCURSAL','estado':'Yucatán','municipio':'Mérida',
               'codigo_postal':'97000','colonia':'Centro','calle':'Calle 1','numero_exterior':'100',
               'numero_interior':'','rfc':'ABCD800101AA1','correo':'ejemplo@example.mx',
               'telefono':'9991234567','domicilio_fiscal':'Calle 1 #100'}
        _sucursal(datos,uid)
        self.assertEqual(Sucursal.objects.get(pk=uid).estado,'Yucatán')
        self.assertEqual(Sucursal.objects.get(pk=uid).version,4)
        antiguo={'uuid':str(uid),'codigo':'SUC-001','nombre':'Antiguo','activa':True,'version':2}
        _sucursal(antiguo,uid)
        self.assertEqual(Sucursal.objects.get(pk=uid).nombre,'Laboratorio')
