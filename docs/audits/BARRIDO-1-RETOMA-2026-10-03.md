# Barrido 1 — retomada del barrido transversal
**Fecha:** 2026-10-03  
**Rama:** `plan/barridos-pendientes-2026-10-03`  
**Estado:** auditoría inicial en curso; no declarar cerrado.

## Evidencia actual que sí está confirmada

- El CI asociado al último head integrado terminó en verde en Python 3.9, Python 3.12 y auditoría de navegador. La matriz automatizada cubrió responsive Chromium, contraste automatizado y recorrido de los cursos.
- Las pruebas actuales de cuenta incluyen emisión de las cookies `tortu_session` y `tortu_csrf`, rechazo de mutaciones sin CSRF, selección de perfil y cierre de sesión. El hallazgo histórico de ausencia de cookie CSRF ya no describe el estado actual.
- Los controles de rate limiting, respuestas de login uniformes y mitigación de redirección abierta cuentan con regresiones en el código actual.
- El informe de Barrido 4 fue actualizado en esta rama para dejar constancia de la integración real y conservar por separado los límites que siguen pendientes.

## Pendientes que permanecen abiertos

### B1-01 — Completar el inventario de pruebas manuales
El checklist `PRUEBAS-PENDIENTES-PULL-2026-10-02.md` mantiene pendientes M01–M23: arranque, registro/verificación/login, sesiones, dos perfiles, onboarding, lecciones, persistencia, proyectos, API, migración, responsive y reinicio. No se pueden marcar como realizadas sin evidencia del entorno de prueba; no se accedió a la copia local del usuario.

### B1-02 — Completar la prueba integral del alumno
La prueba `test_cuenta_perfil_activo_abre_onboarding_y_progreso_persiste` cubre registro, verificación simulada, login, perfil, onboarding y persistencia de configuración. **No cubre aún todo el ciclo requerido**: respuesta incorrecta → pista → reintento correcto → XP/logro → cierre de lección → mapa/siguiente lección → abandono/reanudación. Tampoco sustituye el recorrido con dos perfiles dentro del mismo flujo. Se deriva al Barrido 3, pero se registra ahora para evitar que el CI verde se interprete como cobertura completa.

### B1-03 — Revisar avisos editoriales del validador
Persisten avisos no bloqueantes sobre ordenamientos alternativos equivalentes en tres ejercicios. Hay una regresión que acepta los órdenes equivalentes; falta decidir si las consignas deberían aclarar el objetivo pedagógico. No cambiar la evaluación hasta revisar el contenido concreto.

### B1-04 — Revisar protección de formularios de autenticación
Las mutaciones autenticadas de perfil/logout verifican CSRF y las APIs locales requieren token. Queda por revisar específicamente el riesgo de *login CSRF* en `POST /cuenta/login`, que acepta formularios HTML y crea sesión sin exigir un token CSRF previo. Antes de modificarlo, comprobar el flujo local-first, el comportamiento de formularios y el contrato de origen; no introducir un bloqueo que rompa el login legítimo.

### B1-05 — Separar fallos actuales de resultados históricos
Los informes de los primeros pases incluyen conteos de fallos anteriores al estado actual. Deben conservarse como historial, pero nunca presentarse como estado actual de CI. Usar el workflow del commit concreto como fuente para cada declaración de estado.

## Próximas acciones del Barrido 1

1. Verificar el contrato de origen/CSRF del login y definir una regresión reproducible antes de tocar autenticación.
2. Revisar las rutas de formularios y estados de error/loading/vacío con foco en inconsistencias de bajo riesgo.
3. Revisar el validador de contenido y los tres avisos editoriales, sin alterar reglas curriculares por intuición.
4. Cerrar los hallazgos con pruebas automatizadas y enlazar la ejecución de CI correspondiente.
5. Mantener en una lista separada las comprobaciones que requieren dispositivo, correo real o copia local; no declararlas completadas remotamente.

## Criterio de cierre

Barrido 1 se cierra cuando los hallazgos transversales revisables por código estén resueltos o explícitamente diferidos a su etapa arquitectónica, cada cambio tenga regresión y CI verde, y las verificaciones dependientes del entorno estén registradas sin confundirlas con las automatizadas.
