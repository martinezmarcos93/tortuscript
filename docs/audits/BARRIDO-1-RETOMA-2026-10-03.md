# Barrido 1 — retomada del barrido transversal
**Fecha:** 2026-10-03  
**Rama:** `plan/barridos-pendientes-2026-10-03`  
**Estado:** revisión automatizada de código avanzada; no declarar cerrado hasta finalizar CI y registrar las verificaciones dependientes del entorno.

## Evidencia actual que sí está confirmada

- En el head `42504c1b4b63ee0aa158f7df1436978b8f092a61`, Python 3.9 y 3.12 terminaron en verde con 629 tests y 2 omitidos por versión. La auditoría de navegador del head anterior (`37162509911`) también terminó en verde: responsive, contraste WCAG AA y recorrido de 108/108 lecciones y 541 pasos, sin errores de consola. La ejecución `37162900126`, que valida además `upload-artifact@v7` en el workflow de verificación, tiene Python en verde y su recorrido de navegador sigue en curso.
- Las pruebas actuales de cuenta incluyen emisión de las cookies `tortu_session` y `tortu_csrf`, rechazo de mutaciones sin CSRF, selección de perfil y cierre de sesión. El hallazgo histórico de ausencia de cookie CSRF ya no describe el estado actual.
- Los controles de rate limiting, respuestas de login uniformes y mitigación de redirección abierta cuentan con regresiones en el código actual.
- El informe de Barrido 4 fue actualizado en esta rama para dejar constancia de la integración real y conservar por separado los límites que siguen pendientes.

## Pendientes que permanecen abiertos

### B1-01 — Completar el inventario de pruebas manuales
El checklist `PRUEBAS-PENDIENTES-PULL-2026-10-02.md` mantiene pendientes M01–M23: arranque, registro/verificación/login, sesiones, dos perfiles, onboarding, lecciones, persistencia, proyectos, API, migración, responsive y reinicio. No se pueden marcar como realizadas sin evidencia del entorno de prueba; no se accedió a la copia local del usuario.

### B1-02 — Completar la prueba integral del alumno
La prueba `test_cuenta_perfil_activo_abre_onboarding_y_progreso_persiste` cubre registro, verificación simulada, login, perfil, onboarding y persistencia de configuración. **No cubre aún todo el ciclo requerido**: respuesta incorrecta → pista → reintento correcto → XP/logro → cierre de lección → mapa/siguiente lección → abandono/reanudación. Tampoco sustituye el recorrido con dos perfiles dentro del mismo flujo. Se deriva al Barrido 2 (integración educativa completa), pero se registra ahora para evitar que el CI verde se interprete como cobertura completa.

### B1-03 — Revisar avisos editoriales del validador
La revisión identificó tres equivalencias reales: las dos asignaciones independientes pueden cambiar de orden en «Dos variables» y en «Tabla del 2»; en «Solo los pares», con cuatro vueltas, incrementar antes de comprobar también mostraba 2 y 4. Se aclararon las dos primeras consignas y «Solo los pares» ahora usa cinco vueltas, con una consigna explícita que exige comprobar antes de incrementar. La suite del head `42504c1b4b63ee0aa158f7df1436978b8f092a61` pasó en Python 3.9 y 3.12; quedan dos avisos editoriales intencionales para las asignaciones independientes.

### B1-04 — Login CSRF: mitigación añadida y validada en CI
La revisión confirmó que `POST /cuenta/login` acepta formularios HTML y crea sesión sin token CSRF previo. Se añadió un control de origen en el blueprint: rechaza `Sec-Fetch-Site: cross-site` y un `Origin`/`Referer` que no coincida con esquema y host de la aplicación. La regresión `test_login_rechaza_post_de_origen_cruzado` comprueba HTTP 403, ausencia de `Set-Cookie` y que no se crea sesión. La suite Python del head `42504c1b4b63ee0aa158f7df1436978b8f092a61` pasó y contiene regresiones separadas para `Sec-Fetch-Site: cross-site` sin `Origin`, `Referer` externo sin `Origin`, origen propio y `Origin` malformado. El recorrido de navegador del head de código anterior pasó en `37162509911`; el run `37162900126` vuelve a verificarlo junto con la actualización del workflow. Las solicitudes de clientes no navegador que no envían Origin/Referer siguen admitidas, mientras que los navegadores modernos se cubren con Fetch Metadata.


### B1-06 — Fallos de UX silenciados en acciones cotidianas
La revisión de JavaScript encontró fallos de bajo riesgo, pero visibles para el alumno:
- En el resumen, cambiar la meta diaria solo recargaba si la API devolvía `ok`; una respuesta válida negativa quedaba silenciosa y las excepciones solo se escribían en consola.
- En la página de ejercicio y en tres variantes de lección (SQL, Web y código general), el botón de pista no capturaba errores de red/servidor. La promesa podía rechazarse sin mensaje y el alumno no recibía una vía clara para reintentar.
- En el onboarding, la respuesta JSON `ok: false` con HTTP 200 no mostraba error ni reactivaba el botón de envío. El backend actual devuelve HTTP 400 en sus validaciones conocidas, pero el frontend no manejaba el contrato negativo de forma defensiva.
- En el editor compartido, si fallaba la petición de traducción en vivo, se conservaba el Python traducido anteriormente y podía parecer que correspondía al código recién editado.

**Correcciones aplicadas en esta rama:** el resumen muestra un aviso de error cuando no se confirma el cambio y evita clics duplicados durante la petición; el botón de pista de ejercicios se deshabilita mientras carga, muestra un error comprensible si falla y vuelve a habilitarse para reintentar, salvo que ya se hayan agotado las tres pistas. La revisión de `leccion.js` detectó el mismo defecto en los tres tipos de ejercicio con editor (SQL, Web y código general); sus manejadores de pista ahora capturan el fallo, informan al alumno y permiten reintentar sin duplicar solicitudes simultáneas. El onboarding ahora muestra el mensaje de una respuesta negativa y reactiva el botón para corregir los datos. La vista Python ya no conserva una traducción anterior si falla la traducción en vivo, sino que muestra una nota explícita. La nueva suite Python pasó con el head actual; la ejecución de navegador está en curso.

### B1-07 — Los ejemplos ejecutables de las lecciones no mostraban errores de red

En las explicaciones con ejemplo ejecutable, los botones de juego, dibujo con tortuga y salida de consola siempre reactivaban el botón en `finally`, pero no capturaban fallos de la API. El rechazo podía quedar como promesa no manejada y la pantalla no explicaba qué pasó.

**Corrección aplicada:** los tres caminos ahora capturan el error, muestran un mensaje visible y permiten volver a probar. Además, las páginas de ejercicio, lección, laboratorio y tortuga dejan de mostrar la representación técnica cruda de excepciones de red y ofrecen un mensaje comprensible, usando el detalle validado por el servidor cuando existe. No se modifica la lógica curricular. La suite Python del head `42504c1b4b63ee0aa158f7df1436978b8f092a61` pasó; la auditoría de navegador `37162509911` terminó en verde con 108/108 lecciones, 541 pasos y cero errores de consola.

### B1-11 — Excepciones crudas aún visibles en proyectos y lecciones

La búsqueda transversal encontró usos residuales de `String(e)` en proyectos guiados, integradores, la lección con editor y el juego. Esos valores pueden exponer detalles técnicos de red o implementación y no ayudan al alumno a recuperarse.

**Corrección aplicada:** los manejadores ahora priorizan el mensaje validado del servidor y, si no existe, muestran una instrucción comprensible para revisar la conexión e intentar nuevamente. Se añadió `tests/test_frontend_error_contract.py`, que recorre los scripts propios bajo `web/static/js` y falla si reaparece `String(e)`. La suite Python actual pasó y ejecutó 629 tests, con 2 omitidos por versión.

### B1-12 — Cabecera Origin malformada podía producir un error interno

El control de origen del login analizaba `Origin`/ `Referer` con `urlsplit`; ciertos valores malformados pueden lanzar `ValueError`. **Corrección aplicada:** la ruta ahora rechaza esas cabeceras con HTTP 403. Se agregaron pruebas independientes para origen cruzado por Fetch Metadata, Referer externo, origen propio y Origin malformado. La suite Python actual pasó; el recorrido de navegador del mismo head aún está en curso.

### B1-10 — Actions de CI apuntaban a versiones con runtime Node.js obsoleto

La ejecución verde anterior avisaba que `actions/checkout@v4`, `setup-node@v4` y `setup-python@v5` estaban siendo forzadas al runtime Node 24 pese a declarar Node 20. Se actualizaron las acciones a sus versiones mayores actuales (`checkout@v7`, `setup-node@v7`, `setup-python@v7` y `upload-artifact@v7` en los workflows de verificación e instaladores). El workflow de instaladores es manual y no se ejecuta con cada push; su matriz de construcción Windows/macOS/Linux sigue pendiente de una ejecución manual. La CI habitual sí pasó con las nuevas versiones de acciones.

### B1-09 — Regresión de equivalencias quedó desactualizada al corregir el ejercicio

La primera ejecución posterior al cambio de «Solo los pares» falló en `test_tres_ordenamientos_equivalentes_del_curso_se_aceptan`: el test seguía exigiendo aceptar la permutación antigua, precisamente la que el ajuste curricular buscaba dejar de aceptar. Se actualizó el test para conservar las dos equivalencias legítimas (asignaciones independientes) y añadir una regresión que exige rechazar incrementar antes de comprobar. La ejecución `37162509911` pasó en Python 3.9 y 3.12 (629 tests, 2 omitidos); la auditoría de navegador aún debe terminar. El fallo previo queda documentado y no se oculta.

### B1-08 — Respuesta de CSS estático sin cerrar en una prueba

El CI anterior emitía un `ResourceWarning` por una respuesta de Flask de `/static/css/tortu.css` que el test de certificado no cerraba. No era un fallo de producción, pero ensuciaba la salida y podía ocultar advertencias nuevas. La prueba ahora cierra la respuesta en un bloque `finally`, incluso si falla la aserción. La prueba pasó en el head `97486d115dc9707778b1596984c6a7e579ff13b5` junto con la suite Python.

### B1-05 — Separar fallos actuales de resultados históricos
Los informes de los primeros pases incluyen conteos de fallos anteriores al estado actual. Deben conservarse como historial, pero nunca presentarse como estado actual de CI. Usar el workflow del commit concreto como fuente para cada declaración de estado.

### B1-13 — Acción de artefactos obsoleta en el workflow de verificación

La revisión posterior de ambos workflows detectó que `verificar-fase0.yml` todavía usaba `actions/upload-artifact@v4` en la auditoría de navegador, aunque el workflow de construcción ya había migrado a v7. Se actualizó también esa referencia a `@v7`. La ejecución `37162900126` está verificando la nueva versión de la acción; los dos jobs Python ya terminaron en verde y el recorrido de navegador continúa en curso. La matriz manual de construcción de instaladores para Windows/macOS/Linux sigue sin ejecutarse.

## Próximas acciones del Barrido 1

1. Confirmar el final de `37162900126` tras actualizar `upload-artifact@v7` y conservar la evidencia de CI.
2. Completar la revisión transversal de errores visibles; se normalizaron los últimos `String(e)` hallados en lecciones, proyectos, integradores y juego, y se añadió una prueba de contrato que evita regresiones.
3. Revisar el validador de contenido y los tres avisos editoriales, sin alterar reglas curriculares por intuición.
4. Cerrar los hallazgos con pruebas automatizadas y enlazar la ejecución de CI correspondiente.
5. Mantener en una lista separada las comprobaciones que requieren dispositivo, correo real o copia local; no declararlas completadas remotamente.

## Criterio de cierre

Barrido 1 se cierra cuando los hallazgos transversales revisables por código estén resueltos o explícitamente diferidos a su etapa arquitectónica, cada cambio tenga regresión y CI verde, y las verificaciones dependientes del entorno estén registradas sin confundirlas con las automatizadas.
