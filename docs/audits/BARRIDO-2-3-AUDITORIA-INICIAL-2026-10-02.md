# Barrido 2 + 3 — auditoría inicial de runtime educativo, cuentas y privacidad

**Fecha:** 2026-10-02  
**Rama:** `sweep/consolidacion-ux-v1`  
**Base de trabajo:** HEAD de la rama tras cerrar los barridos 0 + 1.  
**Estado:** auditoría en curso; no autoriza merge a `main`.

## Objetivo

Auditar en paralelo el recorrido educativo autenticado (B2) y los límites de identidad, perfiles, progreso y acceso comercial (B3). La auditoría distingue defectos actuales, riesgos de diseño para la siguiente etapa y funciones que la documentación declara explícitamente fuera del alcance local-first.

## Hallazgos confirmados

### B3-01 — Identificador de ChildProfile determinista y derivado del nombre visible
**Severidad:** alta para el ciclo de vida futuro; media en el modo actual.

En la versión auditada, `crear_child_profile` derivaba el ID mediante `SHA-256(account_id + display_name.lower())`. El identificador interno dependía del nombre visible, por lo que una futura eliminación y recreación con el mismo correo y alias podía volver a asociar progreso huérfano. La API de borrado aún no está implementada.

**Corrección aplicada en la rama:** los nuevos perfiles reciben IDs opacos aleatorios (`child_<24 hex>`), independientes del alias. Se agregaron pruebas para validar formato y unicidad. CI del commit de código `b5d9a8be48ce5c5f4a55a3b6a0a7128886ee3cec` pasó en Python 3.9 y 3.12 (589 tests, 2 omitidos por versión; 0 fallos/errores). Ejecución: [37046712403](https://github.com/martinezmarcos93/tortuscript/actions/runs/37046712403). Antes de exponer el borrado sigue siendo necesaria una política de eliminación/retención de los archivos de progreso.

### B3-02 — La unicidad de nombres no coincide con la generación de IDs
**Severidad:** media; reproducible por inspección del contrato SQLite.

La tabla original usaba `UNIQUE(account_id, display_name)`, sensible a mayúsculas, mientras el ID se calculaba con el nombre en minúsculas. Esto permitía una colisión de ID para `Ana` y `ANA`.

**Corrección aplicada en la rama:** el esquema sube a versión 3, agrega `display_name_key` con una clave canónica `NFKC + casefold()` y una restricción única por cuenta. La migración revisa duplicados históricos antes de imponer el índice y falla con un mensaje accionable en vez de elegir silenciosamente qué perfil conservar. Se agregó una regresión para el alias duplicado con mayúsculas. CI del commit de código `b5d9a8be48ce5c5f4a55a3b6a0a7128886ee3cec` completó correctamente en Python 3.9 y 3.12 (589 tests, 2 omitidos por versión; 0 fallos/errores). Ejecución: [37046712403](https://github.com/martinezmarcos93/tortuscript/actions/runs/37046712403). Se agregó una prueba automatizada de migración desde una base v2 sintética con conservación del perfil y verificación del índice. Sigue pendiente validar la migración con una copia de una base local real, porque los fixtures automatizados no sustituyen esa comprobación.

### B3-06 — El inicializador podía modificar un esquema de versión futura antes de rechazarlo
**Severidad:** media; riesgo de alterar una base incompatible.

`ensure_schema` comprobaba la versión guardada después de crear tablas e índices y aplicar migraciones. Si una versión más nueva de TortuScript había creado la base, la versión antigua podía modificarla antes de emitir el error de incompatibilidad. Ahora la versión se comprueba antes de ejecutar cambios de esquema; una regresión verifica que una base v4 sea rechazada sin añadir columnas ni tablas. Verificado en CI.

### B3-05 — Entradas inválidas podían inutilizar la recuperación o reservar una cuenta
**Severidad:** media; fallos de consistencia y recuperación ante errores de entrada.

`reset_password` consumía el token antes de validar la longitud de la nueva contraseña; un error de validación dejaba al usuario sin poder reutilizar el enlace. Además, el registro creaba la cuenta antes de validar la política de contraseña, por lo que un intento inválido podía reservar el correo y bloquear un reintento. Ahora la validación ocurre antes de consumir el token o crear la cuenta. Se agregaron pruebas para ambos recorridos; CI confirmó el comportamiento.

### B3-04 — La verificación de correo consumía el token mediante GET
**Severidad:** media; riesgo de activación accidental por escáneres automáticos de enlaces.

La ruta `GET /cuenta/verificar-email` consumía el token de un solo uso. Algunos clientes de correo y filtros de seguridad visitan enlaces automáticamente, por lo que podían verificar la cuenta sin una acción explícita del usuario. La ruta GET ahora solo presenta la confirmación y el consumo se realiza mediante POST; se agregó una regresión que simula el GET y verifica que la cuenta siga sin verificar hasta el POST. Verificado en CI.

### B3-03 — La migración podía dejar una columna nueva tras detectar duplicados
**Severidad:** media; defecto de consistencia del esquema ante una base histórica conflictiva.

La prueba de regresión para alias históricos equivalentes detectó que `ALTER TABLE` podía persistir antes de que la migración arrojara `CuentaError`. Los perfiles no se perdían, pero quedaba un esquema parcialmente alterado. La migración ahora calcula y valida todas las claves históricas antes de añadir la columna; la prueba comprueba que se conservan las dos filas y que la columna no se agrega cuando la migración debe abortar. La corrección quedó verificada en CI.

### B2-01 — Cobertura insuficiente del ciclo de vida completo en un único contrato de integración
**Severidad:** media; brecha de verificación.

Hay pruebas unitarias separadas para cuenta, autenticación, selección de perfil, persistencia por ChildProfile, acceso y runtime. La suite también incluye una prueba de rutas de cuenta. Aun así, los contratos distribuidos entre servicios deben verificarse juntos: sesión válida → selección de perfil → carga de progreso → escritura educativa → cambio de perfil → confirmación de aislamiento → reanudación de sesión. La prueba de rutas ahora cubre el cambio entre dos perfiles de una misma cuenta, la escritura de snapshots distintos y la recuperación de los valores correctos al volver a cada perfil.

**Acción:** inspeccionar la cobertura de rutas y añadir una regresión de recorrido integral solo para los pasos que hoy no estén cubiertos, evitando duplicar pruebas ya existentes.

### B2-02 — Permutaciones de líneas con salida equivalente en tres ejercicios
**Severidad:** baja; aviso editorial no bloqueante, con riesgo de evaluación demasiado estricta si el contrato no se prueba.

El validador detecta permutaciones que producen la misma salida en «Dos variables», «Tabla del 2» y «Solo los pares». La lógica de lecciones ya admite ordenamientos alternativos cuando la ejecución genera la salida esperada; agregué una regresión que comprueba esos tres casos con el motor real. Los tres avisos del validador siguen siendo intencionales: informan al autor de que la consigna puede admitir más de un orden correcto, no indican un fallo de validación del curso.

### B3-08 — El limitador de intentos retenía claves expiradas indefinidamente
**Severidad:** baja en el modo local; riesgo de consumo de memoria bajo tráfico prolongado.

`RateLimiter` guardaba una cola por clave, y las claves con emails únicos podían permanecer en el diccionario incluso después de expirar. Ahora hace limpieza periódica de colas vencidas conservando la ventana configurada para cada clave; agregué pruebas de límite/reintento y limpieza. CI completó correctamente el cambio. El limitador sigue siendo process-local: antes de escalar a varios workers debe reemplazarse por un backend compartido y añadir límites coordinados por IP/cuenta.

### B3-07 — El envío de correo depende de una integración opcional
**Severidad:** bloqueante para un lanzamiento remoto; no bloqueante para pruebas locales.

`_emitir_email` no falla si `ACCOUNT_EMAIL_SENDER` no está configurado: registro y recuperación pueden responder como aceptados sin entregar ningún enlace. La integración de correo no está configurada por defecto en el servidor local y no debe darse por operativa en producción. Antes del despliegue hay que incorporar un proveedor de correo, comprobar fallos de entrega, definir reintentos y verificar que los enlaces lleven a la nueva confirmación explícita por POST. No se simula ni se inventa un proveedor dentro de esta auditoría.

### B3-09 — El registro de cuentas no tenía límite de intentos
**Severidad:** media para cualquier exposición a tráfico no confiable; riesgo de abuso del endpoint y crecimiento de cuentas/tokens.

Las rutas JSON y HTML de registro aceptaban solicitudes sin un límite, a diferencia de login y recuperación. Esto permitía automatizar altas y, cuando existe un remitente configurado, provocar un volumen elevado de correos de verificación.

**Corrección aplicada en la rama:** ambas rutas comparten un límite de cinco intentos por IP por hora y responden HTTP 429 con `Retry-After` al excederlo. El limitador se guarda por instancia Flask para evitar compartir estado accidentalmente entre aplicaciones de prueba dentro del mismo proceso. Se añadió una regresión que comprueba el límite y que la ruta HTML no ofrece una vía alternativa para eludirlo.

**Límite residual:** el limitador sigue siendo en memoria y por proceso; no coordina workers ni instancias distintas. Antes de desplegar con múltiples workers debe migrarse a un backend compartido. El límite por IP también requiere calibración operativa detrás de proxies para no confiar en cabeceras reenviadas sin configuración explícita.

### B4-01 — El runtime autenticado acepta puntuación y XP declarados por el cliente
**Severidad:** alta si se usa como fuente fiable del progreso comercial.

Las rutas `/cuenta/runtime/ejercicio` y `/cuenta/runtime/leccion/paso` reciben del cliente valores como `estrellas`, `xp_ganado`, `xp`, `perfecto` y `total_pasos`. `RuntimeEducativo` pasa esos valores al motor de progreso, que actualiza XP y finalización. La autenticación y CSRF evitan solicitudes anónimas o cross-site, pero no prueban que el alumno haya resuelto el ejercicio ni que la puntuación enviada sea legítima: un usuario autenticado puede modificar su propia petición.

**Estado:** hallazgo confirmado por inspección del contrato entre rutas, runtime y motor. No se aplica una validación superficial de rangos como si resolviera el problema: limitar `xp` o `estrellas` no impide que el cliente solicite repetidamente el máximo permitido.

**Mitigación aplicada en la rama:** los tres endpoints de escritura directa (`/cuenta/runtime/ejercicio`, `/cuenta/runtime/leccion/paso` y `/cuenta/runtime/practica`) ahora responden HTTP 410 y no modifican el progreso. Informan los endpoints canónicos que evalúan código/respuestas y derivan los metadatos del contenido del curso: `/api/ejercicios/<n>/evaluar`, `/api/lecciones/<leccion_id>/pasos/<i>/evaluar` y `/api/practica/comprobar`. Se actualizó la regresión para intentar enviar XP 5000, marcar un paso perfecto y declarar una práctica acertada, y comprobar que el progreso sigue intacto.

**Límite residual:** el flujo canónico debe seguir cubierto por pruebas de integración en modo de cuenta autenticada para confirmar que cada tipo de contenido se evalúa y persiste en el ChildProfile activo. No se debe reactivar ninguno de los endpoints 410 como ruta de escritura confiable.

### B4-02 — Escritura genérica de snapshots permitía falsificar todo el progreso
**Severidad:** alta.

Además de los endpoints de puntuación, `PUT /cuenta/progreso` aceptaba un snapshot completo enviado por el navegador. Aunque verificaba que el `profile_id` coincidiera con el perfil activo, no validaba semánticamente los campos de `data`: un usuario podía enviar directamente `xp_total`, ejercicios, lecciones completadas y otros valores arbitrarios. El control de propiedad impedía escribir en otro perfil, pero no impedía falsificar el progreso propio.

**Mitigación aplicada:** la ruta conserva los controles de sesión y CSRF, pero rechaza escrituras genéricas con HTTP 410 y código `escritura_no_autoritativa`. La persistencia debe ocurrir desde las operaciones de servidor que evalúan onboarding, ejercicios, pasos y práctica. Se actualizaron pruebas para enviar XP falsificado, comprobar que no se guarda nada y comprobar que la configuración de onboarding sigue persistiendo por perfil.

**Implicación funcional:** cualquier cliente que todavía dependiera de `PUT /cuenta/progreso` debe migrar a las operaciones evaluadas del servidor; no reactivar la escritura de snapshots como atajo. La importación de progreso local es un flujo separado y debe continuar verificando su origen y destino.

### B4-04 — Registro y recuperación podían aparentar éxito sin un canal de correo
**Severidad:** alta para un despliegue con cuentas, porque la verificación y recuperación dependen de correo electrónico.

`_emitir_email()` no hacía nada cuando `ACCOUNT_EMAIL_SENDER` no estaba configurado, pero las rutas seguían devolviendo respuestas de éxito. El registro podía crear una cuenta pendiente de verificación sin enviar el enlace; la recuperación podía confirmar recepción sin enviar un enlace de restablecimiento.

**Mitigación aplicada en la rama:** el registro HTML/JSON y la recuperación devuelven HTTP 503 con código `envio_email_no_configurado` si no existe un sender callable. El registro falla antes de crear la cuenta, evitando dejar una cuenta pendiente irrecuperable por este motivo. La respuesta de recuperación no depende de que la cuenta exista; el 503 solo informa que falta el canal global. Se añadieron pruebas de regresión para las tres rutas.

**Límite residual:** un sender configurado que luego falle al entregar el mensaje necesita manejo de fallos/outbox y reintentos; la mera existencia de un callable no garantiza entrega. La instalación no debe considerarse lista para producción hasta verificar envío real y recuperación de extremo a extremo.

### B4-03 — La importación local aceptaba fuentes inexistentes o malformadas
**Severidad:** media; riesgo de respuestas HTTP 500, importaciones vacías inesperadas y estado inconsistente.

La migración llamaba a `cargar_progreso(nombre)`, que devuelve el progreso inicial cuando el archivo no existe. Por ello, una solicitud con un nombre de perfil inexistente podía importar un perfil vacío como si la fuente fuera válida. Además, algunos archivos JSON podían superar la validación superficial y fallar después durante la migración de esquema (por ejemplo, una configuración que no fuera un objeto), propagando una excepción no controlada.

**Mitigación aplicada en la rama:** se valida que el nombre sea texto normalizado y que el perfil figure entre las fuentes locales existentes antes de leerlo. Los errores de estructura durante la carga se convierten en `MigracionProgresoError`, sin guardar el destino. Se añadieron regresiones para valores no textuales, perfiles inexistentes y archivos con configuración malformada.

**Límite residual:** los perfiles locales son archivos compartidos por la instalación local y no tienen un vínculo de propiedad con una cuenta comercial. La migración requiere selección explícita, pero antes de habilitar el servicio en un entorno multiusuario remoto habrá que definir una prueba de consentimiento/propiedad para la fuente; no debe exponerse el listado global de perfiles locales a cuentas remotas.

## Riesgos de arquitectura y límites de alcance

1. **Privacidad/consentimiento:** `docs/FASE12_PRIVACIDAD_MENORES_V1.md` define minimización, consentimiento, retención y derechos, pero declara que es una base de diseño, no una habilitación legal ni una implementación completa. Antes de cualquier despliegue comercial hay que traducir cada requisito a flujos, persistencia, pruebas y revisión jurídica argentina.
2. **Exportación y supresión:** los documentos de arquitectura futura enumeran estas operaciones; no se encontraron implementaciones en los módulos de identidad revisados. Se mantienen como trabajo futuro explícito, no como regresión del modo local actual. No habilitar borrado de perfiles sin resolver progreso huérfano y retención.
3. **Pagos y suscripciones:** el esquema reserva tablas para suscripciones y derechos, pero el producto sigue local-first y la documentación excluye pagos, SaaS y sincronización. No conectar un proveedor ni presentar el estado de entitlement como prueba de pago hasta definir la autoridad que lo modifica y verificar webhooks/autenticidad en la fase comercial.
4. **Concurrencia:** el runtime web serializa las operaciones en el proceso actual. Esto no constituye coordinación entre múltiples procesos o instancias; la sincronización remota requerirá un contrato transaccional y resolución de conflictos explícitos.
5. **Correo transaccional:** la configuración `ACCOUNT_EMAIL_SENDER` es opcional y no existe proveedor por defecto; ver B3-07. Registro y recuperación no están listos para uso remoto hasta configurar y probar entrega real.
6. **Borrado y restauración:** el adaptador de progreso crea una copia `.bak` antes de reemplazar un archivo. Debe documentarse su ciclo de vida y considerar su eliminación/exportación junto con el archivo principal al implementar derechos de datos.

## Secuencia propuesta

1. **CI previo verificado:** el commit `b5d9a8be48ce5c5f4a55a3b6a0a7128886ee3cec` pasó en Python 3.9 y 3.12 (589 tests, 2 omitidos por versión). La cobertura NFKC, migración v2 → v3, cambio de perfil y ordenamientos equivalentes pasó en Python 3.9 y 3.12 en el commit `3fe66f208424bfe9bbaf35f2317455ad482986c0` (593 tests, 2 omitidos por versión). CI del commit `22a3d697fbe28b29cc5190069b2118db058fb8e1` pasó en Python 3.9 y 3.12: 597 tests, 2 omitidos por versión, sin fallos ni errores. La prueba adicional del limitador también pasó en CI. Incluye las regresiones de migración parcial, rechazo de esquema futuro, contraseña inválida y verificación explícita de correo. [Ejecución](https://github.com/martinezmarcos93/tortuscript/actions/runs/37051187720).
2. **CI actual verificado:** Python 3.9 y 3.12 pasan en el commit `f6223be3f61e1281c2a007bf9c1395a350c54d0a` (599 tests, 2 omitidos por versión).
3. Validar la migración v2 → v3 con una copia local real, sin tocar la base original.
4. Mantener consentimiento, exportación/supresión, retención y operación comercial como bloqueadores de un futuro lanzamiento remoto; no simular que están implementados.
5. Actualizar el checklist de pruebas manuales sin pedir al usuario un pull antes de su ventana disponible.

## Seguridad y control de cambios

- No se modifica `main`.
- No se habilitan pagos, despliegue remoto ni sincronización.
- No se relajan autenticación, CSRF, rate limiting ni aislamiento de perfiles.
- Todo cambio de persistencia debe incluir prueba de migración/esquema y regresión.

**Mitigación adicional:** las rutas HTTP para listar e importar perfiles locales quedaron deshabilitadas por defecto mediante `ENABLE_LOCAL_PROGRESS_MIGRATION=False`. Solo una instalación local de un único usuario debe activar la opción explícitamente. Se añadieron pruebas para comprobar el 404 por defecto y que, al habilitarla, sigue siendo obligatoria una sesión válida.
## Continuación — integridad de importación y persistencia (2026-10-03)

### B4-05 — El archivo de progreso podía declarar una identidad distinta de su propietario

**Hallazgo:** el adaptador validaba el formato del profile_id al construir la ruta, pero al leer el JSON no comparaba la identidad declarada dentro del snapshot con el identificador del archivo consultado. Un archivo alterado o intercambiado podía entregar un snapshot que afirmara pertenecer a otro ChildProfile y dejar la detección únicamente a cargo de la capa superior.

**Corrección aplicada en la rama:** ProgresoChildProfile.cargar() ahora rechaza el snapshot cuando snapshot.profile_id no coincide con el ID propietario solicitado. Se agregó una regresión que altera la identidad declarada en el archivo y comprueba que la carga falle.

### B4-06 — El contrato aceptaba metadatos y datos de snapshot insuficientemente validados

**Hallazgo:** el contrato permitía que updated_at estuviera vacío, malformado o sin zona horaria; además, el valor booleano true podía pasar como versión numérica 1 en Python. El contrato tampoco comprobaba que todos los valores de data fueran serializables como JSON estricto.

**Corrección aplicada en la rama:** el contrato exige una fecha ISO 8601 con zona horaria, una versión de tipo entero exacto y datos serializables como JSON (sin valores no finitos). Se añadieron regresiones para fechas inválidas, fechas sin zona horaria, versión booleana y valores no serializables.

**Estado de verificación:** cambios enviados a la rama sweep/consolidacion-ux-v1; las ejecuciones de CI correspondientes están pendientes/en curso al registrar esta actualización. No se declara el barrido cerrado hasta confirmar CI verde en Python 3.9 y 3.12.

**Próximo paso:** verificar el resultado del workflow más reciente; después completar el contrato de integración autenticado del flujo canónico (sesión → ChildProfile → onboarding/evaluación → persistencia → cambio de perfil → recuperación aislada). La comprobación de migración v2→v3 contra una copia local real sigue expresamente aplazada hasta autorización de Marcos; no acceder ni validar la copia local antes de esa autorización.


## Actualización de verificación e integración — 2026-10-03

**CI final verificado:** [37129180624](https://github.com/martinezmarcos93/tortuscript/actions/runs/37129180624), commit b9179881245c6f3046311367416355838d9ef7a1. Python 3.9 y 3.12 terminaron en verde; se completaron pruebas Python/JavaScript y validador de contenido.

### Cierre técnico de B2-01

Se agregó una regresión integrada autenticada que recorre:

1. registro y verificación de una cuenta de prueba;
2. inicio de sesión y creación de dos ChildProfiles;
3. selección del perfil, onboarding y persistencia;
4. evaluación correcta del primer ejercicio por la ruta canónica del servidor;
5. evaluación del paso de lección equivalente;
6. cambio al segundo perfil, confirmación de progreso independiente y vuelta al primero para recuperar sus XP y configuración.

La prueba impide que la integración se considere cubierta únicamente por tests unitarios aislados. Los endpoints heredados que aceptaban puntuación o snapshots del cliente permanecen deshabilitados con HTTP 410.

### Estado consolidado de los barridos 2 + 3

- **B3/B4, integridad y límites de confianza:** correcciones de identidad de ChildProfile, validación de snapshots, rechazo de versiones/timestamps/datos inválidos, controles de registro y autenticación: CI verde.
- **B2, recorrido autenticado:** onboarding, evaluación canónica de ejercicio y paso de lección, persistencia y aislamiento al cambiar de perfil: CI verde.
- **B2/B3, validación manual y operación real:** no se declara verificado lo que requiere entorno externo.

### Riesgos residuales que no se deben confundir con fallos del barrido local

- La matriz de UX móvil debe ejecutarse en navegador real/dispositivo; una auditoría estática no demuestra usabilidad táctil.
- La migración v2→v3 contra una copia real de la base local queda aplazada hasta autorización de Marcos.
- El envío real de correo, los fallos del proveedor y los reintentos/outbox requieren configuración y pruebas de integración con un proveedor; la existencia de un callable no demuestra entrega.
- La operación multi-worker requiere rate limiting compartido; el limitador actual es por proceso.
- Consentimiento, retención, exportación/supresión, revisión jurídica argentina, pagos y sincronización remota siguen siendo puertas de lanzamiento comercial, no funciones que esta rama deba simular como terminadas.

**Estado:** barridos técnicos automatizados 2 + 3 cerrados con las salvedades anteriores documentadas. Esta actualización no autoriza merge a main.


## Cobertura final del flujo educativo canónico — 2026-10-03

CI [37129366763](https://github.com/martinezmarcos93/tortuscript/actions/runs/37129366763), commit 41855a724d7b2960e0221b8eb7b0c44dfa29fcad, terminó en verde en Python 3.9 y 3.12, incluyendo pruebas Python/JavaScript y validador de contenido.

Se añadió una prueba de integración autenticada para la práctica espaciada: crea una cuenta y ChildProfile, completa onboarding y pasos rápidos por las rutas de evaluación, avanza el reloj de la aplicación de prueba sin modificar el reloj del sistema, abre la práctica, comprueba una tarjeta y verifica que los XP y el registro de repaso se persistan en el perfil activo.

Con las regresiones anteriores de evaluación de ejercicio y paso de lección, la suite cubre ahora los tres caminos de evaluación canónicos —ejercicio, paso de lección y práctica— junto con persistencia y aislamiento entre perfiles. Las rutas heredadas de escritura directa continúan rechazando los intentos de asignar puntuación desde el cliente.

La validación de UX móvil en navegador/dispositivo y la migración v2→v3 contra una copia local real siguen siendo tareas manuales bloqueadas por entorno/autorización; no se declaran completadas por el CI.


## Cierre de integración y auditoría de navegador — 2026-10-03

CI final: [37131712662](https://github.com/martinezmarcos93/tortuscript/actions/runs/37131712662), commit `736393a6356aaf727369dbc2472eb2ca1256de39`.

### Resultados comprobados

- 613 tests Python aprobados en Python 3.9 y 3.12; validador de contenido correcto.
- Responsive Chromium: sin desbordes en 320×800, 375×812, 390×844 y 768×1024.
- Contraste normal/alto: sin problemas detectados por el auditor automatizado.
- Recorrido Playwright de los nueve cursos: 108 lecciones, 541 pasos, 4.520 XP de prueba, cero errores de consola.

### Defectos detectados y corregidos por la auditoría

- El mapa curricular tenía etiquetas con relación de contraste 3,67:1; el texto ahora usa el color de alto contraste y conserva la identidad del nivel en el borde.
- Una actividad HTML pedía dos fichas `h1` pero solo ofrecía una. Se añadió la ficha faltante.
- El validador ahora comprueba la multiplicidad de fichas en pasos `completar`, también para HTML/CSS/JavaScript; una prueba de regresión impide reintroducirlo.
- El servidor de prueba crea cuenta, perfil y sesión en SQLite temporal; el bootstrap existe solo en el servidor de prueba. No toca la copia local.
- El recorrido de navegador espera la progresión asíncrona después de pasos de explicación y reconoce los botones de los editores web y SQL.

### Límites pendientes fuera del CI

- Migración v2→v3 contra una copia real de la base local: pendiente de autorización expresa de Marcos.
- Prueba física en móviles/tablets, teclado y tecnologías de asistencia: la matriz automatizada no sustituye estas pruebas.
- Entrega real de correo/outbox, limitación de tasa compartida multi-worker, revisión jurídica argentina de datos de menores, pagos y sincronización remota: puertas de lanzamiento, no se declaran cerradas por esta auditoría.

**Estado:** barridos técnicos 2 + 3 cerrados en su alcance automatizado, con límites manuales y operativos identificados.
