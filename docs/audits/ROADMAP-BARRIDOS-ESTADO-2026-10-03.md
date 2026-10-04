# TortuScript — Estado y reordenamiento de barridos
**Fecha de corte:** 2026-10-03  
**Rama de trabajo:** `plan/barridos-pendientes-2026-10-03`  
**Base:** `main`, tras integrar PR #4  
**Regla:** una etapa solo se declara cerrada cuando hay evidencia automatizada y funcional suficiente; un CI verde por sí solo no acredita pruebas manuales, entrega de correo, migraciones seguras ni preparación para producción.

## Estado ejecutivo

El PR #4 fue integrado a `main` mediante squash después de que CI del commit `13828250f6f9a9fc1a5b34d0a34191c3d06d2a8d` terminara en verde en los tres trabajos: Python 3.9, Python 3.12 y auditoría de navegador. Commit de merge: `959f977196912fff575cad23c2a6fdc643d00ceb`.

La integración no significa que todos los barridos 0–4 estén completos. La rama reunía cambios de distintas áreas y la propia descripción del PR registra pendientes de operación, privacidad y validación manual. Por ello, los estados de abajo distinguen **hecho**, **parcial** y **pendiente**.

## Clasificación por barrido

| Nº | Barrido | Estado | Criterio de trabajo |
|---:|---|---|---|
| 0 | Consolidación | **Hecho como baseline técnico; revalidación continua** | Cambios consolidados, base ejecutable y CI integrado. No reabrir salvo regresión o deuda identificada. |
| 1 | Bugs simples y transversales | **Parcial; retomar primero** | Existen validaciones, normalización de errores, regresiones y auditorías. Falta una pasada sistemática y trazable de UI, API, navegación, estados vacíos/carga/error, CSRF/sesiones/cookies, consistencia lingüística, contenido huérfano y prerequisitos. |
| 2 | UX, responsive y accesibilidad | **Parcial** | Hay auditoría responsive automatizada en varios tamaños, revisión automatizada de contraste y ajuste de altura/ancho de editor y lienzo en Tortuga/Juegos. Pendientes: verificación manual con teclado, tacto y tecnologías de asistencia; revisar estados/foco en todas las zonas y comprobar el ajuste visual en dispositivos reales. |
| 3 | Integración educativa completa | **Parcial; requiere prueba de ciclo completo** | Hay validador curricular, recorrido automatizado de cursos y pruebas de navegador. Falta acreditar de punta a punta el recorrido de un alumno con registro/perfil/onboarding/diagnóstico, lección, error, pista, reintento, XP, cierre, mapa, siguiente lección, abandono, regreso y continuación; repetir con segundo perfil para comprobar aislamiento y exportación/importación. |
| 4 | Cuenta, perfiles y privacidad | **Parcial; diseño y privacidad no cerrados** | Hay autenticación, perfiles, controles de acceso y pruebas de aislamiento. Falta formalizar y verificar los límites Account / Authentication / Consent / Subscription / Entitlements / ChildProfiles, propiedad de datos, consentimiento, minimización, retención, exportación/eliminación y requisitos aplicables a menores. |
| 5 | Backend persistente | **Parcial** | Hay cambios de esquema/progreso y contratos de snapshots. Falta probar la migración v2→v3 sobre copia desechable con backup y restauración verificados; revisar transacciones, integridad, recuperación y límites entre servicios. El rate limiter actual es por proceso; falta almacén compartido antes de escalar. |
| 6 | Autenticación robusta | **Parcial** | Integrados límites de intentos, respuestas de login uniformes, mitigación de redirección abierta, reenvío de verificación y manejo de fallos del proveedor. Falta validar correo real con proveedor configurado, recuperación completa y expiraciones, controles manuales de sesión/CSRF/cookies, limitación compartida y, si corresponde, patrón transaccional/outbox. |
| 7 | Pagos + entitlements | **Pendiente de implementación integral** | Conservar la separación entre currículo y acceso comercial. Completar checkout, proveedor, webhooks autenticados, idempotencia, renovación, cancelación, período de gracia, reembolsos, recuperación de acceso y reglas para múltiples perfiles. No habilitar cobros reales sin pruebas de sandbox y reconciliación. |
| 8 | Sandbox remoto | **Pendiente** | La ejecución actual/local no debe considerarse sandbox seguro para código hostil. Diseñar API → cola → worker → aislamiento del SO/contenedor → runtime restringido; definir cuotas de CPU/memoria/tiempo, filesystem, red, procesos, syscalls, salida, concurrencia y abuso. |
| 9 | Cloud sync | **Pendiente** | Definir modelo de sincronización, identidad, conflictos, versiones, borrado, cifrado, recuperación, exportación y permisos por perfil antes de implementarlo. |
| 10 | Tutor IA | **Pendiente** | Diseñar el tutor como capa pedagógica sobre perfil/progreso/permisos; definir contexto permitido, datos excluidos, retención, memoria temporal, seguridad infantil, evaluación y límites de generación. |
| 11 | Croco-Script integration | **Pendiente de integración; contratos por definir/verificar** | Mantener Croco-Script como producto avanzado separado. Definir contratos versionados de Identity, Entitlement, Progress, Curriculum y Authorization; evitar acoplar su implementación al núcleo de TortuScript. |
| 12 | Release Candidate | **Pendiente** | Criterios de aceptación, regresión integral, migraciones, accesibilidad manual, seguridad, empaquetado, recuperación, documentación, observabilidad y checklist de publicación. No equivale a desplegar automáticamente. |

## Deuda transversal ya identificada

- El rate limiter predeterminado sigue siendo por proceso. Se añadió una alternativa SQLite compartida entre workers que acceden al mismo archivo, activable con `ACCOUNT_RATE_LIMIT_DB`; no coordina hosts distintos y no sustituye Redis/servicio compartido para despliegues distribuidos.
- El manejo de correo no sustituye una cola transaccional/outbox; una respuesta HTTP 202 no prueba entrega.
- La entrega real de verificación y recuperación necesita proveedor configurado y pruebas.
- La migración v2→v3 debe ensayarse con una copia y un backup restaurable, nunca sobre datos reales sin autorización específica.
- La app conserva el límite local/localhost; los cambios de cuenta no autorizan exposición pública.
- CI no reemplaza las pruebas manuales de tacto, teclado y tecnologías de asistencia.
- Privacidad de menores, pagos y sincronización requieren revisión específica antes de producción.

## Orden operativo actualizado

1. **Barrido 1 — transversal:** inventariar defectos concretos, clasificarlos por severidad, corregir los de bajo riesgo y añadir regresiones. Evitar cambios de arquitectura dentro de este bloque.
2. **Barrido 2 — UX y accesibilidad:** cerrar la matriz responsive, foco/teclado, tacto y lector de pantalla; confirmar el ajuste reciente de Tortuga/Juegos.
3. **Barrido 3 — integración educativa:** probar el ciclo de alumno completo y el aislamiento entre dos perfiles, documentando cada paso y resultado.
4. **Barrido 4 — cuenta, perfiles y privacidad:** fijar el modelo de dominio y los límites de autorización antes de añadir más endpoints.
5. **Barrido 5 — backend persistente:** validar migraciones, integridad, transacciones, backup/restore y servicios.
6. **Barrido 6 — autenticación:** completar los controles pendientes y verificar entrega real de correo y rate limiting compartido.
7. **Barrido 7 — pagos y entitlements.**
8. **Barrido 8 — sandbox remoto.**
9. **Barrido 9 — cloud sync.**
10. **Barrido 10 — tutor IA.**
11. **Barrido 11 — contratos e integración de Croco-Script.**
12. **Barrido 12 — Release Candidate.**

Esta secuencia operativa conserva la hoja de ruta general acordada (0–12). Los informes históricos pueden usar numeración distinta o agrupar varios bloques; no deben redefinir la secuencia canónica.

## Reglas de ejecución

- Trabajar en ramas distintas de `main`; no tocar la copia local del usuario.
- Cada bloque debe tener alcance, checklist, pruebas de regresión y criterio explícito de cierre.
- Mantener separados los cambios funcionales, las decisiones arquitectónicas y las tareas de despliegue.
- No marcar una tarea como terminada por existir código o documentación: exigir evidencia de pruebas y anotar las limitaciones restantes.
- No desplegar, ejecutar migraciones sobre datos reales ni activar cobros sin autorización explícita.

## Avance remoto posterior al corte

**Rama de trabajo de la PR:** `plan/barridos-pendientes-2026-10-03` (también existe la rama de respaldo `work/barridos-maximo-2026-10-03`).  
**PR activa:** [#5 — Barrido 1 y trabajo de seguimiento](https://github.com/martinezmarcos93/tortuscript/pull/5), en borrador; no fusionada a `main`.

- **Barrido 4 — diseño:** creado `docs/architecture/CONTRATOS-DOMINIO-PRIVACIDAD-Y-ROADMAP.md` con límites Account / Authentication / Consent / Subscription / Entitlement / ChildProfile, propiedad de datos, consentimiento de menores, contratos de pagos, sandbox, sync, tutor IA y Croco-Script. Es una decisión de diseño, no una declaración de implementación terminada.
- **Barrido 5 — respaldo/restauración:** agregado `tortuscript/respaldo_sqlite.py` con backup de SQLite, comprobación `integrity_check`, publicación atómica, rechazo de destino existente y restauración con confirmación explícita para sobrescribir. Las utilidades no se invocan automáticamente ni se ejecutaron contra bases reales.
- **Barrido 6 — limitación compartida:** agregado `SQLiteRateLimiter` con transacción `BEGIN IMMEDIATE`, clave SHA-256 para no persistir IP/correo en claro y tests que comparten el límite entre dos instancias. Es opt-in mediante `ACCOUNT_RATE_LIMIT_DB`; el modo por proceso sigue siendo el predeterminado y la solución SQLite solo coordina procesos que comparten archivo.
- **Barrido 5 — migración:** el repositorio ahora valida alias históricos equivalentes antes de crear tablas comerciales; los cambios de columnas, índice y versión se ejecutan dentro de una transacción. Se amplió la regresión para exigir que una migración rechazada no deje tablas `subscriptions` o `entitlements`.
- **Regresiones añadidas:** `tests/test_respaldo_sqlite.py` cubre copia consistente, destino existente, origen ausente, archivo corrupto, confirmación de sobrescritura, restauración y rutas iguales. `tests/test_rate_limit.py` ahora cubre el límite compartido y la no persistencia de la clave original en claro.
- **CI:** se amplió el filtro de `pull_request` del workflow para aceptar ramas `plan/**` y `work/**`, permitiendo que las PR de trabajo intermedias reciban verificación automatizada. La evidencia de CI para esta tanda debe confirmarse desde la ejecución asociada al head actual antes de declarar estos cambios validados.
- **Barrido 2 — diagnóstico de accesibilidad:** añadido `herramientas/revisar_teclado.py` y conectado al workflow de navegador. Inspecciona controles visibles sin nombre accesible aproximado, controles no tabulables y el destino del primer `Tab` en las rutas principales. Por ahora es diagnóstico no bloqueante: sus heurísticas requieren revisar falsos positivos y controles personalizados antes de convertirlo en puerta de aceptación.
- **Barrido 5/6 — regresiones adicionales:** se añadió una prueba HTTP de que `ACCOUNT_RATE_LIMIT_DB` comparte el límite entre dos instancias Flask que usan el mismo archivo SQLite. Además, las rutas de cuenta normalizan los cuerpos JSON y rechazan listas/valores no objeto con respuestas 4xx en lugar de provocar errores 500 por llamadas a `.get()` sobre tipos inesperados. La nueva regresión cubre login, registro y restablecimiento de contraseña; pendiente CI del head más reciente.
- **Barrido 1 — formularios y validación HTTP:** corregida la creación de perfil desde el formulario HTML. Ahora se acepta el campo `nombre` del formulario, se activa el perfil recién creado y se redirige al inicio; antes la ruta solo leía JSON y el botón no completaba el flujo anunciado. Se normalizaron también los cuerpos JSON de las rutas de cuenta para que valores que no son objetos no provoquen errores 500. Hay regresiones para creación por formulario, perfil activo y cuerpos JSON con listas.
- **Estabilidad de pruebas:** CI detectó que el test de perfiles asumía un orden fijo del listado. Las aserciones ahora comparan nombres/IDs sin depender del orden de presentación; el fallo era del test, no de la autorización ni del guardado. La validación del head actual está en cola; no se declara el lote verde hasta que termine.
- **CI de navegador:** una ejecución anterior falló al relanzar Chromium con `spawn ETXTBSY` y errores de arranque de Chromium después de la auditoría responsive. Se trata como fallo de infraestructura/ejecución del navegador, no como prueba de un defecto de la app; queda pendiente confirmar el recorrido completo y la nueva auditoría de teclado en una ejecución estable.
- **Documentación de despliegue:** corregido el docstring de `tortuscript/rate_limit.py` para distinguir el limitador local, SQLite compartido en una máquina y la necesidad de un almacén distribuido entre hosts.
- **Estado:** los cambios están comprometidos en la rama remota. No se marca cerrado el Barrido 5 hasta que CI confirme las nuevas pruebas; backup/restore de datos reales, migración sobre copia local y cualquier validación dependiente de la PC siguen expresamente diferidos por instrucción del usuario.

