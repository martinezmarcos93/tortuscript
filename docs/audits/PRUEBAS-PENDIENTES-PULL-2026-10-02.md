# Pruebas pendientes tras el pull — TortuScript

**Fecha de preparación:** 2026-10-02  
**Rama:** `sweep/consolidacion-ux-v1`  
**Objetivo:** ejecutar estas comprobaciones en el entorno local de Marcos después de hacer pull. No hacer merge a `main` hasta revisar resultados.

## Antes de probar

- [ ] Confirmar rama: `git branch --show-current` → `sweep/consolidacion-ux-v1`.
- [ ] Confirmar último commit: `git log -1 --oneline`.
- [ ] Guardar copia de la carpeta de datos/progreso antes de probar.
- [ ] Usar una cuenta de prueba y perfiles infantiles ficticios; no borrar datos reales.
- [ ] Arrancar siguiendo las instrucciones actuales del README y guardar el log de arranque.
- [ ] Para cualquier prueba de cuenta fuera de fixtures, confirmar que `ACCOUNT_EMAIL_SENDER` está configurado y que verificación/recuperación entregan enlaces reales; no considerar respuestas HTTP 202 como prueba de entrega.

## Pruebas funcionales manuales

| ID | Área | Acción | Resultado esperado | Estado/evidencia |
|---|---|---|---|---|
| M01 | Arranque | Iniciar el servidor desde cero | Arranca sin traceback ni error de configuración | Pendiente |
| M02 | Cuenta | Abrir la app sin sesión | Muestra login; no muestra datos educativos | Pendiente |
| M03 | Registro | Registrar cuenta de prueba | Queda pendiente de verificación, sin permitir acceso educativo prematuro | Pendiente |
| M04 | Login | Iniciar sesión con cuenta verificada | Cookie de sesión emitida y acceso a selección/creación de perfil | Pendiente |
| M05 | Sesión | Recargar y navegar entre páginas | Sesión se mantiene de forma consistente | Pendiente |
| M06 | Perfiles | Crear dos perfiles infantiles | Ambos aparecen y pueden seleccionarse | Pendiente |
| M07 | Aislamiento | Cambiar de perfil A a B | Nombre, onboarding, XP, lecciones y proyectos no se mezclan | Pendiente |
| M08 | Onboarding | Entrar con perfil nuevo | Redirige a bienvenida antes del contenido educativo | Pendiente |
| M09 | Onboarding | Completar bienvenida y volver a entrar | No repite bienvenida para ese perfil | Pendiente |
| M10 | Lecciones | Completar un paso correctamente | Se refleja feedback, XP/estrellas y avance esperados | Pendiente |
| M11 | Persistencia | Recargar la lección y reiniciar el servidor | El progreso completado persiste | Pendiente |
| M12 | Sesión | Cerrar sesión y volver a una URL educativa | Se solicita login; no se filtran datos previos | Pendiente |
| M13 | API | Solicitar endpoint API sin token local | Rechazo 403 antes de resolver identidad educativa | Pendiente |
| M14 | API | Enviar token local válido sin sesión educativa | Rechazo 401 por ausencia de sesión | Pendiente |
| M15 | API | Enviar token, sesión y perfil activo | Endpoint permitido y funcional | Pendiente |
| M16 | Proyectos | Crear/editar/guardar un proyecto de prueba | Cambios persisten al recargar | Pendiente |
| M17 | Integrador | Abrir un proyecto integrador, editar y guardar | Estado y archivos se guardan en el perfil correcto | Pendiente |
| M18 | Migración | Revisar flujo de importación de progreso local | Solo ocurre por acción explícita; no reemplaza progreso comercial sin confirmación | Pendiente |
| M19 | Responsive | Probar login, mapa, lección y proyectos en ventana angosta/móvil | Sin scroll horizontal ni botones inaccesibles | Pendiente |
| M20 | Cierre | Cerrar la app normalmente y volver a abrir | No se pierde progreso; el comportamiento de sesión es coherente | Pendiente |
| M21 | Alias de perfil | Intentar crear `Ana` y luego `ANA` en la misma cuenta | El segundo alias se rechaza como duplicado sin error 500 ni colisión de ID | Pendiente |
| M22 | Migración de esquema | Con copia de seguridad previa, arrancar usando una base creada por la versión anterior | El esquema migra a v3 o informa claramente de duplicados históricos; no desaparecen perfiles ni progreso | Pendiente |
| M23 | Aislamiento persistente | Guardar progreso en perfil A, cambiar a B, guardar otro avance, volver a A y reiniciar el servidor | Cada perfil recupera exactamente su propio progreso | Pendiente |

## Estado de verificación automática

- [x] CI completo del commit `f6223be3f61e1281c2a007bf9c1395a350c54d0a`: Python 3.9 y 3.12, 599 tests, 2 omitidos por versión, sin fallos. [Ejecución](https://github.com/martinezmarcos93/tortuscript/actions/runs/37051639743). [Ejecución](https://github.com/martinezmarcos93/tortuscript/actions/runs/37051187720).
- [x] Regresión automatizada: abrir el enlace (GET) no consume el token; la verificación solo se completa tras confirmar por POST.
- [x] Regresiones automatizadas: registro con contraseña inválida permite reintentar con el mismo correo; contraseña inválida no consume el token de recuperación.
- [x] CI confirma las regresiones de `tests/test_cuentas.py`: ID opaco, alias equivalentes por mayúsculas/Unicode NFKC, migración v2 → v3, aborto sin mutación parcial y rechazo de versión futura. ID opaco, alias equivalentes por mayúsculas/Unicode NFKC y migración de esquema v2 → v3.
- [x] CI confirma que una base con versión de esquema futura se rechaza sin crear tablas ni alterar columnas existentes.
- [ ] Revisar los logs de migración del esquema v2 → v3; comprobar que los duplicados históricos abortan antes de alterar el esquema y no eliminan ni modifican perfiles.
- [x] CI confirma la prueba HTTP de cambio entre dos perfiles de una misma cuenta: cada perfil recupera su propio XP tras alternar varias veces.
- [x] CI confirma `tests/test_rate_limit.py`: límites por clave, `Retry-After` y limpieza de claves expiradas.
- [x] CI confirma que el validador de contenido no tiene errores bloqueantes. Los tres avisos de ordenamientos equivalentes están explicados y cubiertos por `test_tres_ordenamientos_equivalentes_del_curso_se_aceptan`; revisar si las consignas deberían precisar mejor el objetivo pedagógico.
- [ ] No fusionar a `main` hasta que CI esté verde, se revise el diff completo y Marcos complete las pruebas manuales relevantes.


## Registro de resultados

Anotar por prueba: **OK / FALLA / BLOQUEADA**, commit probado, pasos exactos, resultado observado y captura/log si corresponde. No poner solo “anda/no anda”: especificar URL, código HTTP, perfil usado y si el resultado persistió tras recarga.

## Regla de seguridad

No desactivar autenticación, token local, aislamiento por perfil ni protección CSRF para conseguir que pasen tests antiguos. Si una expectativa de test contradice el contrato vigente, actualizar el fixture o documentar la incompatibilidad después de verificar el comportamiento esperado.


## Actualización de CI — 2026-10-03

La ejecución más reciente [37129180624](https://github.com/martinezmarcos93/tortuscript/actions/runs/37129180624), commit b9179881245c6f3046311367416355838d9ef7a1, terminó correctamente en Python 3.9 y 3.12. Pasaron las pruebas Python/JavaScript y el validador de contenido, incluida la nueva regresión autenticada de evaluación y aislamiento de progreso entre perfiles.

Esto **no marca como realizadas** las pruebas que requieren tu entorno: arranque de tu copia, comprobación visual responsive en navegador/dispositivo y migración v2→v3 contra una copia de una base local real. Esas comprobaciones siguen en esta lista para ejecutarlas después del pull y con datos de prueba; no accedí a tu copia local.


## Estado actualizado de pruebas — 2026-10-03

CI final: [37131712662](https://github.com/martinezmarcos93/tortuscript/actions/runs/37131712662), commit `736393a6356aaf727369dbc2472eb2ca1256de39`.

**Comprobado en CI:** 613 tests Python en cada versión (3.9 y 3.12), validador de contenido, responsive Chromium sin desbordes en la matriz definida, contraste automatizado sin problemas y recorrido de 108 lecciones/541 pasos sin errores de consola.

**Sigue pendiente de entorno/autorización:** probar una copia local real con migración v2→v3; validar interacción táctil, teclado y tecnologías de asistencia en dispositivos físicos; integrar envío real de correo y confirmar las puertas operativas/comerciales enumeradas en el barrido. No accedí a la copia local de Marcos.

La suite de contrato comercial/educativo es ahora bloqueante en CI. Los jobs de navegador se omiten en commits cuyo mensaje comienza con `docs:`, para que las actualizaciones documentales no vuelvan a ejecutar el recorrido de 108 lecciones.
