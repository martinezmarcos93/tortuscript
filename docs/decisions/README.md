# Decisiones de arquitectura (ADR)

## Regla de gobernanza

> **Propuesta ≠ decisión aprobada.** Una ADR en estado *Propuesta* puede orientar el diseño, pero **no autoriza implementación**. Solo una ADR *Aceptada* puede usarse como fundamento para modificar la arquitectura o el comportamiento. Si una implementación contradice una ADR Aceptada, primero se modifica la ADR y después el código.
>
> Solo Marcos cambia el estado de una ADR. Los documentos de `docs/experimental/` son ideas, no decisiones: nada de lo que dicen se implementa sin una ADR Aceptada que lo cubra.

Las medidas de endurecimiento que no condicionan el modelo de producto, por ejemplo security headers/CSP, no necesitan ADR.

## Tablero

| ADR | Tema | Estado |
|-----|------|--------|
| [ADR-001](ADR-001-migracion-a-web.md) | Migración a web (Flask local) | Aceptada |
| [ADR-002](ADR-002-cursos-como-datos-y-progreso-aditivo.md) | Cursos como datos / progreso aditivo | Aceptada |
| [ADR-003](ADR-003-producto-local-y-validacion.md) | Producto local y validación antes de crecer | Aceptada |
| [ADR-004](ADR-004-diagnostico-y-continuidad.md) | Diagnóstico y continuidad del camino | Aceptada |
| [ADR-005](ADR-005-intereses-locales.md) | Intereses y feedback locales | Aceptada |
| [ADR-006](ADR-006-runtime-educativo-y-de-juegos.md) | Runtime educativo / runtime de juegos | Aceptada |
| [ADR-007](ADR-007-seguridad-runtime-de-juegos.md) | Seguridad del runtime de juegos | Aceptada |
| [ADR-008](ADR-008-alcance-tortugame-v1.md) | Alcance de TortuGame v1 | Aceptada |
| [ADR-009](ADR-009-determinismo.md) | Determinismo y azar controlado | Aceptada |
| [ADR-010](ADR-010-sin-comunidad-v1.md) | Sin comunidad en la V1 | Aceptada |
| [ADR-011](ADR-011-proyectos-privados.md) | Proyectos privados por defecto | Aceptada |
| [ADR-012](ADR-012-cuenta-adulto-perfiles-hijo.md) | Cuenta adulta → perfiles hijo | Aceptada |
| [ADR-013](ADR-013-desktop-y-cloud.md) | TortuScript Desktop / Cloud | Aceptada |
| [ADR-014](ADR-014-ejecucion-de-codigo-del-alumno.md) | Ejecución del código del alumno | Aceptada |
| [ADR-015](ADR-015-distribucion-a-familias.md) | Instaladores para familias | Aceptada |
| [ADR-016](ADR-016-vision-plataforma.md) | TortuScript como plataforma curricular progresiva | Propuesta |
| [ADR-017](ADR-017-modelo-curricular-por-edades.md) | Edad y nivel como dimensiones curriculares | Propuesta |
| [ADR-018](ADR-018-fuentes-curriculares-externas.md) | Repositorios avanzados como fuentes curriculares | Propuesta |
| [ADR-019](ADR-019-estados-de-acceso.md) | Estados de acceso independientes del motor | Propuesta |
| [ADR-020](ADR-020-nivel-web-esencial.md) | HTML/CSS/JS como alfabetización web | Aceptada |
| [ADR-021](ADR-021-nivel-sql.md) | SQL como segundo bloque de datos | Aceptada |
| [ADR-022](ADR-022-preparacion-saas-sin-implementacion.md) | Preparación comercial sin SaaS en V1 | Propuesta |
| [ADR-023](ADR-023-recorridos-iniciales.md) | Recorridos iniciales después de Nivel 0 | Aceptada |
| [ADR-024](ADR-024-proyecto-integrador-adaptativo.md) | Proyecto integrador adaptativo y exportable | Aceptada |
| ADR-025 | Arquitectura web/comercial futura | Aceptada |
| ADR-026 | Privacidad y menores | Aceptada |
| ADR-027 | UX diferenciada por edad | Aceptada |
| ADR-028 | Fuentes curriculares avanzadas externas | Aceptada |
| [ADR-029](ADR-029-transicion-a-producto-web-comercial.md) | Transición a producto web comercial | **Aceptada** |
| [ADR-030](ADR-030-cuenta-familiar-y-perfiles-infantiles.md) | Cuenta familiar y perfiles infantiles | **Aceptada** |
| [ADR-031](ADR-031-autenticacion-sesiones-y-seguridad-web.md) | Autenticación, sesiones y seguridad web | **Aceptada** |
| [ADR-032](ADR-032-pagos-y-entitlements-familiares.md) | Pagos y entitlements familiares | **Aceptada** |
| [ADR-033](ADR-033-sandbox-remoto-para-ejecucion-de-codigo.md) | Sandbox remoto para ejecución de código | **Aceptada** |
| [ADR-034](ADR-034-mobile-ux-y-sistema-visual-comercial.md) | Mobile-first, UX y sistema visual | **Aceptada** |
| [ADR-035](ADR-035-tortu-llm-como-asistente-pedagogico.md) | Tortu-LLM como asistente pedagógico | **Aceptada** |
| [ADR-036](ADR-036-croco-script-como-producto-avanzado.md) | Croco-Script como producto avanzado separado | **Aceptada** |
| [ADR-037](ADR-037-integracion-tortuscript-croco-script.md) | Integración entre TortuScript y Croco-Script | **Aceptada** |
| [ADR-038](ADR-038-persistencia-cuenta-familiar.md) | Persistencia de cuenta familiar y perfiles | **Aceptada** |

## Documentos de producto

- [PRODUCTO_V1](../PRODUCTO_V1.md)
- [ROADMAP V1 educativo](../ROADMAP_V1_2026-12-31.md)
- [ROADMAP V1 comercial](../ROADMAP_COMERCIAL_V1_2026-12-31.md)
- [Catálogo curricular V1](../catalogo_curricular_v1.json)

## Regla de transición comercial

ADR-025 a ADR-037 forman ahora el bloque de arquitectura comercial y de evolución de producto. Las ADR anteriores siguen vigentes salvo contradicción explícita. La implementación comercial debe respetar las separaciones entre núcleo educativo, identidad adulta, perfiles infantiles, acceso comercial, ejecución remota y producto avanzado Croco-Script.

| [ADR-041](ADR-041-progreso-por-childprofile.md) | Contrato de progreso asociado a ChildProfile | **Aceptada** |
| [ADR-042](ADR-042-adaptador-progreso-childprofile.md) | Adaptador de progreso por ChildProfile | **Aceptada** |
| [ADR-043](ADR-043-contexto-educativo-autenticado.md) | Contexto educativo autenticado por ChildProfile | **Aceptada** |
| [ADR-044](ADR-044-migracion-progreso-local.md) | Migración explícita de progreso local | **Aceptada** |
| [ADR-045](ADR-045-runtime-educativo-childprofile.md) | Adaptador del runtime educativo para ChildProfile | **Aceptada** |
| [ADR-046](ADR-046-supresion-de-cuenta-y-perfiles.md) | Supresión de cuenta y de perfiles | Propuesta |
