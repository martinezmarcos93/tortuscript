# ADR-038 — Persistencia de cuenta familiar y perfiles

- Estado: Aceptada
- Fecha: 2026-09-30
- Contexto: transición de TortuScript desde aplicación local hacia producto web comercial.

## Decisión

Se incorpora una frontera de persistencia independiente del progreso educativo local:

`Account → ChildProfile`

y, a nivel comercial:

`Account → Subscription → Entitlement → ChildProfile`

El primer adaptador persistente será SQLite mediante el repositorio `tortuscript.cuentas.CuentaRepository`.

La capa de cuentas no implementa todavía:
- autenticación;
- contraseñas;
- sesiones HTTP;
- verificación de correo;
- pagos;
- webhooks;
- ejecución remota;
- integración con Croco-Script.

Esas responsabilidades se incorporarán en sus bloques correspondientes.

## Reglas de dominio

1. Una cuenta representa al adulto titular.
2. Los perfiles infantiles pertenecen a una cuenta y no poseen credenciales de acceso propias en esta etapa.
3. Una cuenta admite como máximo 3 perfiles activos (`MAX_CHILD_PROFILES`; decisión de Marcos del 04/10/2026, antes 5).
4. La suscripción y el entitlement pertenecen a la cuenta, no al perfil.
5. Un entitlement activo de producto se consulta por cuenta o por perfil mediante su pertenencia a la cuenta.
6. La capa no almacena tarjetas, contraseñas ni tokens.
7. El progreso educativo actual no se migra todavía: el modo local sigue usando `progreso_*.json`.
8. La futura integración de progreso debe usar una identidad de perfil estable y contratos explícitos, sin acoplar la base de datos comercial al formato JSON local.

## Consecuencia

La arquitectura ya tiene un punto de apoyo persistente para identidad familiar y acceso comercial sin convertir prematuramente el progreso local en una dependencia de base de datos. Esto permite implementar autenticación y sesiones después sin reescribir el motor educativo.

## No decidido

- proveedor de base de datos de producción;
- proveedor de autenticación/correo;
- proveedor de pagos;
- estrategia de migración del progreso local;
- despliegue y alta disponibilidad.
