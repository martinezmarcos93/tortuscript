
# ADR-030 — Cuenta familiar y perfiles infantiles

- Estado: Aceptada
- Fecha: 2026-09-30
- Decisor: Marcos
- Relacionadas: ADR-012, ADR-025, ADR-026, ADR-029

## Decisión

El modelo será:

Account
├── Subscription
├── ConsentRecords
├── ChildProfile
├── ChildProfile
└── ChildProfile

La suscripción pertenece a Account, no a ChildProfile.

Una suscripción activa habilita el contenido premium para todos los perfiles infantiles de esa cuenta, sujeto a límites de producto. El límite inicial será de 5 perfiles.

Cada ChildProfile tendrá:
- identificador técnico no semántico;
- alias opcional;
- franja pedagógica;
- configuración educativa;
- progreso;
- logros;
- preferencias;
- estado.

No se usará el nombre real del menor como identificador técnico.

El perfil infantil no podrá modificar email, contraseña, pagos, cuenta familiar, consentimiento adulto ni acceder a otro perfil.

## Roadmap

### 13–19/10
- Esquema de Account, ChildProfile y ConsentRecord.
- Relaciones y claves.
- Autorización por cuenta.
- Límite de 3 perfiles en uso (decisión de Marcos del 04/10/2026; el plan original decía 5).

### 20/10–02/11
- API de creación/selección/edición de perfiles.
- Sesión adulta y sesión educativa.
- Migración del perfil local actual.

### 03–09/11
- Integración con AccessService.
- Entitlement heredado por perfiles.
- Tests de aislamiento entre perfiles.

### 24/11–07/12
- Sincronización de progreso.
- Recuperación de cuenta.
- Eliminación/exportación por cuenta.

### 15–22/12
- Pruebas de abuso y autorización.
- Pruebas de UX con múltiples perfiles.
- Verificación de privacidad.

### 23–28/12 — Fase 15
- Prueba completa de cuenta familiar.

### 29–31/12 — Fase 16
- Congelación del contrato de datos.
