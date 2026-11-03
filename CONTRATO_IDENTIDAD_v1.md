# Contrato de identidad — versión 1

SCentralAPI es la autoridad de escritura. SSucursalAPI conserva copias locales.
Estos documentos se COPIAN en cada repositorio; NO se importa código del otro.

- `Empleado.id`: UUID global estable (mismo valor al replicar).
- `Sucursal.uuid`: UUID global estable.
- `Rol.uuid` y `CatalogoPermiso.uuid`: UUID global estable.
- `AsignacionSucursal.uuid`: UUID global estable.
- `auth.Group.id` y `auth.Permission.id`: claves LOCALES, nunca transportarlas.
- Permisos: identificar por `(app_label, modelo, codename)`.
- Rol: enlazar por UUID y reproducir `Group` localmente.
- Asignación: empleado/rol/sucursal por UUID, no por ID autoincremental.
- Versión de contrato de eventos: `schema_version=1`.
- Central administra altas, bajas y roles; sucursal no altera esa autoridad.
- Solo aplicarán eventos con versión superior; procesar eventos de manera idempotente.
- Hashes de contraseñas: sincronización separada, autenticada y cifrada (pendiente).
- El backend de sucursal debe materializar `User.groups` SOLAMENTE con roles vigentes de su sucursal.
- Bloquear `is_superuser` al replicar; no clonar privilegios de administradores centrales.
- Si los esquemas divergen, bloquear la aplicación del evento y registrar incidencia.
- CONTRATO únicamente; endpoints, distribución, outbox publisher y workers AÚN NO IMPLEMENTADOS.

## Política de versiones de repositorios separados

Cada cambio contractual requerirá actualizar ambos repositorios en una entrega
coordinada, con pruebas de compatibilidad antes del despliegue.
Las migraciones comunes de `organizacion` e `identidad` han de ser equivalentes
en ambos repositorios. Una vez creadas, versionarlas sin regenerarlas arbitrariamente.
