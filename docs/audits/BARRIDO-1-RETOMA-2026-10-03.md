# Barrido 1 — retomada del barrido transversal
**Fecha:** 2026-10-03  
**Rama:** `plan/barridos-pendientes-2026-10-03`  
**Estado:** auditoría inicial en curso; no declarar cerrado.

## Evidencia actual que sí está confirmada

- El CI del commit `e5376a67ed1dc037c82a18250c10b57d65833b98` terminó en verde: 623 tests Python/JavaScript (2 omitidos), contrato de cuenta y auditoría de navegador con responsive Chromium, contraste automatizado y recorrido de los cursos. Después se modificó contenido curricular para precisar consignas; la nueva ejecución `37159152619` debe terminar antes de validar esos cambios.
- Las pruebas actuales de cuenta incluyen emisión de las cookies `tortu_session` y `tortu_csrf`, rechazo de mutaciones sin CSRF, selección de perfil y cierre de sesión. El hallazgo histórico de ausencia de cookie CSRF ya no describe el estado actual.
- Los controles de rate limiting, respuestas de login uniformes y mitigación de redirección abierta cuentan con regresiones en el código actual.
- El informe de Barrido 4 fue actualizado en esta rama para dejar constancia de la integración real y conservar por separado los límites que siguen pendientes.

## Pendientes que permanecen abiertos

### B1-01 — Completar el inventario de pruebas manuales
El checklist `PRUEBAS-PENDIENTES-PULL-2026-10-02.md` mantiene pendientes M01–M23: arranque, registro/verificación/login, sesiones, dos perfiles, onboarding, lecciones, persistencia, proyectos, API, migración, responsive y reinicio. No se pueden marcar como realizadas sin evidencia del entorno de prueba; no se accedió a la copia local del usuario.

### B1-02 — Completar la prueba integral del alumno
La prueba `test_cuenta_perfil_activo_abre_onboarding_y_progreso_persiste` cubre registro, verificación simulada, login, perfil, onboarding y persistencia de configuración. **No cubre aún todo el ciclo requerido**: respuesta incorrecta → pista → reintento correcto → XP/logro → cierre de lección → mapa/siguiente lección → abandono/reanudación. Tampoco sustituye el recorrido con dos perfiles dentro del mismo flujo. Se deriva al Barrido 2 (integración educativa completa), pero se registra ahora para evitar que el CI verde se interprete como cobertura completa.

### B1-03 — Revisar avisos editoriales del validador
La revisión identificó tres equivalencias reales: las dos asignaciones independientes pueden cambiar de orden en «Dos variables» y en «Tabla del 2»; en «Solo los pares», con cuatro vueltas, incrementar antes de comprobar también mostraba 2 y 4, aunque no seguía el orden pedagógico buscado. Se aclararon las dos primeras consignas para indicar expresamente qué líneas pueden permutarse y cuáles no; en «Solo los pares» se cambió el ejercicio de ordenamiento a cinco vueltas, para que incrementar antes de comprobar ya no sea una respuesta equivalente, y se precisó la consigna. El evaluador conserva la aceptación de programas que realmente producen el mismo resultado. CI pendiente para la nueva versión del contenido.

### B1-04 — Login CSRF: mitigación añadida y validada en CI
La revisión confirmó que `POST /cuenta/login` acepta formularios HTML y crea sesión sin token CSRF previo. Se añadió un control de origen en el blueprint: rechaza `Sec-Fetch-Site: cross-site` y un `Origin`/`Referer` que no coincida con esquema y host de la aplicación. La regresión `test_login_rechaza_post_de_origen_cruzado` comprueba HTTP 403, ausencia de `Set-Cookie` y que no se crea sesión. Los tres trabajos del CI (Python 3.9, Python 3.12 y auditoría de navegador) terminaron en verde para el commit `79b24706c5be7c07a88621f4e66e75b5611489c4`. Las solicitudes de clientes no navegador que no envían Origin/Referer siguen admitidas, mientras que los navegadores modernos se cubren con Fetch Metadata.


### B1-06 — Fallos de UX silenciados en acciones cotidianas
La revisión de JavaScript encontró fallos de bajo riesgo, pero visibles para el alumno:
- En el resumen, cambiar la meta diaria solo recargaba si la API devolvía `ok`; una respuesta válida negativa quedaba silenciosa y las excepciones solo se escribían en consola.
- En la página de ejercicio y en tres variantes de lección (SQL, Web y código general), el botón de pista no capturaba errores de red/servidor. La promesa podía rechazarse sin mensaje y el alumno no recibía una vía clara para reintentar.
- En el onboarding, la respuesta JSON `ok: false` con HTTP 200 no mostraba error ni reactivaba el botón de envío. El backend actual devuelve HTTP 400 en sus validaciones conocidas, pero el frontend no manejaba el contrato negativo de forma defensiva.
- En el editor compartido, si fallaba la petición de traducción en vivo, se conservaba el Python traducido anteriormente y podía parecer que correspondía al código recién editado.

**Correcciones aplicadas en esta rama:** el resumen muestra un aviso de error cuando no se confirma el cambio y evita clics duplicados durante la petición; el botón de pista de ejercicios se deshabilita mientras carga, muestra un error comprensible si falla y vuelve a habilitarse para reintentar, salvo que ya se hayan agotado las tres pistas. La revisión de `leccion.js` detectó el mismo defecto en los tres tipos de ejercicio con editor (SQL, Web y código general); sus manejadores de pista ahora capturan el fallo, informan al alumno y permiten reintentar sin duplicar solicitudes simultáneas. El onboarding ahora muestra el mensaje de una respuesta negativa y reactiva el botón para corregir los datos. La vista Python ya no conserva una traducción anterior si falla la traducción en vivo, sino que muestra una nota explícita. El CI de la revisión previa terminó en verde; la versión actual del contenido y su nueva ejecución quedan pendientes.

### B1-07 — Los ejemplos ejecutables de las lecciones no mostraban errores de red

En las explicaciones con ejemplo ejecutable, los botones de juego, dibujo con tortuga y salida de consola siempre reactivaban el botón en `finally`, pero no capturaban fallos de la API. El rechazo podía quedar como promesa no manejada y la pantalla no explicaba qué pasó.

**Corrección aplicada:** los tres caminos ahora capturan el error, muestran un mensaje visible y permiten volver a probar. Además, las páginas de ejercicio, lección, laboratorio y tortuga dejan de mostrar la representación técnica cruda de excepciones de red y ofrecen un mensaje comprensible, usando el detalle validado por el servidor cuando existe. No se modifica la lógica curricular. La verificación de CI del código terminó en verde en el commit `e5376a67ed1dc037c82a18250c10b57d65833b98`; la ejecución del nuevo head con ajustes de contenido está en curso.

### B1-08 — Respuesta de CSS estático sin cerrar en una prueba

El CI anterior emitía un `ResourceWarning` por una respuesta de Flask de `/static/css/tortu.css` que el test de certificado no cerraba. No era un fallo de producción, pero ensuciaba la salida y podía ocultar advertencias nuevas. La prueba ahora cierra la respuesta en un bloque `finally`, incluso si falla la aserción. La regresión queda pendiente de la ejecución CI del nuevo head.

### B1-05 — Separar fallos actuales de resultados históricos
Los informes de los primeros pases incluyen conteos de fallos anteriores al estado actual. Deben conservarse como historial, pero nunca presentarse como estado actual de CI. Usar el workflow del commit concreto como fuente para cada declaración de estado.

## Próximas acciones del Barrido 1

1. Verificar el contrato de origen/CSRF del login y definir una regresión reproducible antes de tocar autenticación.
2. Revisar más rutas de formularios y estados de error/loading/vacío; ya se corrigieron los dos fallos de UX descritos en B1-06.
3. Revisar el validador de contenido y los tres avisos editoriales, sin alterar reglas curriculares por intuición.
4. Cerrar los hallazgos con pruebas automatizadas y enlazar la ejecución de CI correspondiente.
5. Mantener en una lista separada las comprobaciones que requieren dispositivo, correo real o copia local; no declararlas completadas remotamente.

## Criterio de cierre

Barrido 1 se cierra cuando los hallazgos transversales revisables por código estén resueltos o explícitamente diferidos a su etapa arquitectónica, cada cambio tenga regresión y CI verde, y las verificaciones dependientes del entorno estén registradas sin confundirlas con las automatizadas.
