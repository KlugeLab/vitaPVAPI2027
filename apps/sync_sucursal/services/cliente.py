"""Cliente HTTPS de la sucursal hacia SCentralAPI.

Es un proceso offline-safe: sólo consulta si la red está disponible.
"""
from urllib.parse import urljoin
import requests
from django.conf import settings
from django.utils import timezone
from apps.sync_sucursal.models import EstadoSincronizacion
from apps.sync_sucursal.services.aplicador import aplicar_bootstrap, aplicar_lote, aplicar_credenciales
from django.contrib.auth import get_user_model
from apps.identidad.models import AsignacionSucursal


class ClienteCentral:
    def __init__(self):
        self.base = settings.VITA_CENTRAL_SYNC_URL.rstrip('/') + '/'
        if not self.base.startswith('https://'):
            if not (settings.DEBUG and settings.VITA_SYNC_ALLOW_HTTP_DEV):
                raise RuntimeError('Se requiere URL HTTPS hacia SCentralAPI.')
        self.headers = {
            'X-Vita-Installation': str(settings.VITA_INSTALACION_UUID),
            'Authorization': f'Bearer {settings.VITA_SYNC_TOKEN}',
        }
        self.timeout = (5, 25)
        self.verify = settings.VITA_SYNC_CA_BUNDLE or True

    def _request(self, metodo, ruta, **kwargs):
        response = requests.request(
            metodo, urljoin(self.base,ruta), headers=self.headers,
            timeout=self.timeout, verify=self.verify, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def sincronizar(self, forzar_bootstrap=False):
        sucursal_uuid = settings.VITA_SUCURSAL_UUID
        estado, _ = EstadoSincronizacion.objects.get_or_create(flujo='identidad')
        estado.ultimo_intento = timezone.now()
        estado.save(update_fields=['ultimo_intento'])
        total = 0
        try:
            if forzar_bootstrap or not estado.ultimo_cursor:
                data = self._request('GET', 'bootstrap/')
                aplicar_bootstrap(data, sucursal_uuid)
            for _ in range(200):
                estado.refresh_from_db()
                data = self._request('GET', 'cambios/', params={
                    'cursor': estado.ultimo_cursor, 'limit': 100
                })
                total += aplicar_lote(data, sucursal_uuid)
                if not data['has_more']:
                    break
            else:
                raise RuntimeError('Límite de lotes; ejecútalo de nuevo para continuar.')
            estado.refresh_from_db()
            self._request('POST','ack/', json={'cursor': estado.ultimo_cursor})
            # Entrega segregada: sólo pedir las claves autorizadas y necesarias.
            empleados_locales = get_user_model().objects.filter(
                pk__in=AsignacionSucursal.objects.filter(
                    sucursal_id=sucursal_uuid, activa=True
                ).values('empleado_id'),
                is_active=True, is_staff=False, is_superuser=False,
            )
            versiones = {str(u.pk): u.version_credenciales if u.has_usable_password() else 0
                         for u in empleados_locales}
            credenciales = self._request('POST','credenciales/', json={'versions': versiones})
            claves = aplicar_credenciales(credenciales)
            return {'eventos': total, 'credenciales': claves, 'cursor': estado.ultimo_cursor}
        except Exception as exc:
            EstadoSincronizacion.objects.filter(flujo='identidad').update(
                estado='error', mensaje_error=str(exc)[:1500], ultimo_intento=timezone.now()
            )
            raise
