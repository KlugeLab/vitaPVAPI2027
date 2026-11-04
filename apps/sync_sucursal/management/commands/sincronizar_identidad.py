from django.core.management.base import BaseCommand, CommandError
from apps.sync_sucursal.services.cliente import ClienteCentral

class Command(BaseCommand):
    help = 'Sincroniza usuarios, roles, permisos y hashes de contraseña con la central.'

    def add_arguments(self, parser):
        parser.add_argument('--bootstrap', action='store_true', help='Reconcilia todo el estado local.')

    def handle(self, *args, **options):
        try:
            resultado = ClienteCentral().sincronizar(forzar_bootstrap=options['bootstrap'])
        except Exception as exc:
            raise CommandError('Sincronización fallida (datos locales conservados): '+str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(str(resultado)))
