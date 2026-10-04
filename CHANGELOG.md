# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Todavía no hay una
versión publicada de la app web: los cambios de versión se consultan antes de fijarlos.

## Sin publicar — barridos de consolidación (desde 03/10/2026)

Rama `plan/barridos-pendientes-2026-10-03` (PR #5). Sigue `docs/audits/ROADMAP-BARRIDOS-ESTADO-2026-10-03.md`.

### Corregido
- **Migración de progreso local (ADR-044):** la importación lee el archivo de origen de forma estricta. Un archivo
  ilegible (JSON roto, raíz que no es objeto, `ejercicios` mal tipado) se rechaza sin apartarlo ni reescribirlo; antes
  se convertía en un progreso vacío que, con reemplazo explícito, podía pisar el progreso comercial. Los campos
  anidados mal tipados de un JSON válido se normalizan y se conserva lo válido.
- **Navegación de cuenta:** el destino pedido (`next`) se conserva al ingresar, al elegir perfil y al crear el
  primer perfil; antes se perdía y siempre se caía en el inicio. Los formularios HTML de login y perfiles responden
  con una página y un mensaje (límite de intentos, perfil inválido) en vez de JSON crudo o un 403 en blanco.
- **Selector de perfiles:** se quitó un `<script>` en línea que la CSP bloqueaba (código muerto y error de consola)
  y el límite de perfiles sale de `MAX_CHILD_PROFILES` en vez de estar repetido a mano en plantillas y rutas.
- **Validación HTTP:** `perfil_id` y el token de verificación que no son texto se rechazan con 4xx.
- **Datos de cuentas en la app instalada:** la base de cuentas y el progreso por perfil se guardan en la carpeta de
  datos del usuario (`<datos>/instance`), no dentro de la carpeta del programa, que el desinstalador borra. Desde el
  código fuente la ubicación no cambia.
- **Errores 500 por tipos inesperados:** un barrido de 18.442 pedidos con cuerpos mal tipados encontró errores
  internos en `/api/onboarding`, `/api/traducir`, `/cuenta/perfil`, `/cuenta/perfiles` y `/cuenta/verificar-email`;
  ahora responden 4xx. `tests/test_robustez_http.py` repite el barrido (reducido) sobre todas las rutas registradas,
  incluidas las futuras.
- **Progreso de perfil dañado (Barrido 5):** un archivo de progreso ilegible dejaba al perfil con error 500 en todas
  las páginas aunque existiera el `.bak`. Ahora se aparta como `.corrupto-<fecha>` (nunca se borra), se restaura el
  respaldo si es válido y del mismo perfil, y si no lo hay el perfil vuelve a la bienvenida. Un archivo escrito por
  una versión más nueva se rechaza sin tocarlo.
- **Respaldo SQLite en discos sin enlaces duros:** en un pendrive FAT/exFAT `link()` falla y el respaldo no se podía
  publicar; ahora se reserva el nombre con creación exclusiva, que tampoco sobrescribe.
- **Accesibilidad de los editores de código (Barrido 2):** el campo de CodeMirror no tenía nombre accesible (un
  lector de pantalla solo anunciaba «cuadro de edición»); ahora cada editor se anuncia con su función y sus atajos.

### Agregado
- **Recuperación de contraseña con pantallas (Barrido 6):** «Olvidé mi contraseña» en el ingreso, formulario para
  pedir el enlace y formulario para elegir la clave nueva. Abrir el enlace no consume el token; una clave corta o
  mal repetida se corrige sin pedir otro enlace; al cambiarla se cierran las sesiones abiertas. La respuesta es la
  misma exista o no la cuenta.
- **Correo transaccional real (Barrido 6):** `tortuscript/correo.py` arma y envía los correos de verificación y
  recuperación por SMTP (biblioteca estándar, sin dependencias nuevas) o los muestra en la terminal para uso local.
  Se configura por entorno o `.env` (`TORTU_EMAIL_MODO`, ver `.env.example`); sin configuración el registro sigue
  fallando cerrado, y una configuración a medias impide arrancar con un mensaje claro. Antes ningún enviador estaba
  conectado al arranque: no se podía crear una cuenta fuera de `crear_admin.py`.
- **Prueba de ciclo completo del alumno (Barrido 3):** `tests/test_ciclo_alumno.py` recorre por HTTP, sin sembrar
  datos por fuera de la API, el registro con enlace de correo, la verificación, el ingreso, el perfil, la
  bienvenida, una lección con error → pista → reintento, XP y cierre, mapa, abandono, reinicio del servidor y
  regreso, un segundo perfil aislado, proyectos y exportación; y que otra familia no puede elegir un perfil ajeno.
- **Respaldo completo de los datos (Barrido 5):** `herramientas/respaldar_datos.py` (`crear`, `listar`, `verificar`,
  `restaurar --confirmar`) respalda la base de cuentas **y** el progreso de cada perfil en una carpeta con
  manifiesto y hash por archivo. Verificar detecta archivos alterados, faltantes o sobrantes, progreso de otro
  perfil o de un perfil inexistente; restaurar exige confirmación y conserva lo anterior en `instance.antes-de-
  restaurar-<fecha>`. Ensayado sobre una copia de datos reales en el disco del proyecto: restauración idéntica y
  originales intactos.
- **Auditoría de teclado ampliada:** `herramientas/revisar_teclado.py` recorre cada página con Tab (trampas de foco,
  salida del editor con Escape, indicador de foco visible), incluye las páginas de cuenta con y sin sesión y mide
  los objetivos táctiles en 360 px. `--estricto` la convierte en puerta de CI.

### Seguridad
- Las respuestas de `/cuenta/*` llevan `Cache-Control: no-store` (contienen tokens, correos y nombres de perfiles).

### Cambiado
- **Costo por pedido (Barrido 5):** el esquema de cuentas se asegura una vez por archivo y proceso, y cada pedido
  valida la sesión y lee el progreso una sola vez. Una página pasaba por ~12 migraciones de esquema, 7 lecturas del
  progreso y ~80 transacciones SQLite: el inicio bajó de 118 ms a 9 ms y el mapa de 366 ms a 7 ms (medido con el
  cliente de pruebas).

## Sin publicar — TortuGame: crear juegos de rol (26/09/2026)

Rama `feat/tortugame`. Fase 3 del roadmap; implementa ADR-006, 007 y 008 (aceptadas).

### Agregado
- **🎮 Juegos** (`/juego`): se escribe un juego de rol por turnos con la API TortuGame (escena, héroe, enemigos, atacar,
  curar, decir, dar/tiene, mover, misión, ganar/perder, dado, preguntar) y se ve en una escena animada, con lo que pasa
  escrito debajo (también para lectores de pantalla). Se guarda en Mis proyectos.
- **Seguridad (ADR-007):** el servidor solo analiza el código y manda un árbol con lista blanca; el navegador lo corre en
  un Web Worker con su propio intérprete (sin `eval`) y con una CSP sin red, con topes de pasos, profundidad,
  personajes, eventos, listas y textos. La página corta el Worker a los 3 segundos.
- **Curso "🎮 Creá tu juego"** (5 lecciones, se abre al terminar Tortuaria). Las lecciones se evalúan en el servidor
  comparando lo que pasa en el juego (misma semilla): vale cualquier forma de escribirlo, y si algo difiere, la pista
  dice en qué momento.
- Implementación de referencia en Python y **tests de conformidad**: 33 programas dan el mismo registro de eventos,
  error y pregunta en Python y en JS. Tests de seguridad del intérprete con JSON armado a mano.
- Referencia: sección 🎮 Juegos. Especificación: `docs/TORTUGAME.md`.

### Cambiado
- Menú: "Juegos" junto a "Tortuga". Seis cursos, 69 lecciones.

## Sin publicar — instaladores para familias, en cualquier sistema (26/09/2026)

Rama `feat/instalador-agnostico`. Implementa ADR-015 (aceptada).

### Agregado
- `herramientas/construir.py`: **un solo comando** arma TortuScript instalable, sin Python para la familia. Detecta el
  sistema (o se elige con `--sistema`) y usa una única configuración; por sistema solo cambia el paquete y su
  instalador: Linux `.tar.gz` + `instalar.sh` (menú de aplicaciones), Windows `.zip` + `instalar.bat` (menú Inicio y
  Escritorio; además un `.exe` si está Inno Setup), macOS `.zip` + `instalar.command`. Cada instalador comprueba que el
  sistema sea el suyo y el desinstalador nunca borra el progreso.
- `tortuscript/rutas.py`: instalado, el progreso y los logs van a la carpeta de datos del usuario de cada sistema
  (desde el código fuente, todo sigue igual). Si había progreso junto al programa, se copia.
- El ejecutable instalado corre el código de los chicos relanzándose con `--worker` (mismos límites de tiempo y memoria).
- Workflow de GitHub para armar los tres sistemas, **solo a mano**.
- **Probado en Linux** de punta a punta. **Windows y macOS: sin probar todavía.**

### Cambiado
- `requirements-dev.txt` suma `pyinstaller==6.22.3` (auditado: licencia con excepción para distribuir, sin CVE).
- README: instalación para familias, dónde se guardan los datos, versión del esquema (10) y enlace al índice de ADR.

## Sin publicar — tests que ejecutan el JavaScript de la tortuga (26/09/2026)

### Agregado
- `tests/js/tortuga.test.mjs` ejecuta de verdad `web/static/js/tortuga.js` (con `node:test` y un canvas falso, sin
  dependencias): el cuerpo usa el color del nivel, el lápiz arranca verde y `color` cambia solo el lápiz, el estado del
  lápiz, y el laberinto. Una prueba de mutación (volver a pintar el cuerpo con el color del lápiz) los hace fallar.
- `tests/test_js.py` los corre dentro de la suite (se saltean si no hay Node).

## Sin publicar — privacidad explicada en la Ayuda (26/09/2026)

### Agregado
- Pregunta 🔒 "¿Qué guarda TortuScript y quién lo ve?": el apodo, el progreso, los proyectos, los ajustes y los
  intereses; todo en un archivo por perfil en esta compu, sin envíos a internet; cómo lo borra un adulto.

## Sin publicar — lockfile con hashes y auditoría de dependencias (26/09/2026)

Rama `chore/lockfile-dependencias`.

### Agregado
- `requirements.lock`: las 7 dependencias (Flask y lo que trae) con versión exacta y los hashes de PyPI. Instalar con
  `pip install --require-hashes -r requirements.lock` rechaza cualquier archivo alterado (probado).
- `herramientas/auditar_dependencias.py`: rearma el lock (`--generar-lock`) y consulta OSV por vulnerabilidades
  conocidas (hoy: 0). Solo biblioteca estándar.

### Cambiado
- El paquete instalable incluye el lock y sus instaladores lo usan con `--require-hashes`, también en el modo sin
  internet (`--con-ruedas`, probado de punta a punta).
- Se quitó del `.venv` del proyecto un paquete (`typing_extensions`) que había quedado de un intento de instalar
  Playwright ahí.

## Sin publicar — prueba de nivel en la bienvenida (26/09/2026)

Rama `feat/prueba-de-nivel`. Segunda versión de ADR-004 (aceptada).

### Agregado
- Quien elige "Bastante" puede hacer una **prueba corta** (6 preguntas, una por sección del curso 1). El servidor la
  corrige (el navegador no recibe las respuestas) y recomienda empezar en la primera sección con un error, o en
  *Desafíos* si acertó todo. Es opcional: "Desde el principio" sigue elegido.
- Las preguntas son datos (`contenido/diagnostico.json`) y los tests comprueban que la opción correcta sea lo que
  muestra el código, que ninguna otra lo sea y que los textos cumplan las reglas de estilo.

## Sin publicar — textos más cortos (26/09/2026)

### Cambiado
- Consigna del jefe final de Tortuaria (188 → 140 caracteres; el detalle de contar turnos pasa a la nota) y
  explicación del techo en *Proyecto casa* (166 → 150). La auditoría ya no marca textos de más de 160 caracteres.

## Sin publicar — verificación de las páginas nuevas (26/09/2026)

### Cambiado
- `revisar_responsive.py` y `revisar_contraste.py` también revisan Ayuda, la bienvenida (contraste), un laberinto,
  Tortuaria y la página 404. Resultado: sin desbordes y contraste AA en modo normal y alto.

## Sin publicar — pistas propias en todos los pasos (26/09/2026)

Rama `content/pistas-propias`.

### Agregado
- **142 pistas nuevas**, una por cada paso de elegir, predecir, completar u ordenar que usaba la pista genérica
  (primeros pasos, tortuga y Python real). Explican el razonamiento sin dar la respuesta. Ahora es cierto lo que dice
  el README: ante un error hay una pista específica.
- El validador revisa el estilo de las pistas (frases cortas, sin jerga, tildes) y **avisa si un paso nuevo queda sin
  pista propia**. Un test exige que no falte ninguna.

### Corregido
- Consigna de *Texto o cuenta* con tuteo y sin tildes ("Utiliza… renglon… veras") → voseo y ortografía correctos.
- Informe de la prueba simulada actualizado: 0 pasos sin pista propia.

## Sin publicar — Tortuaria, el curso piloto de juego de rol (26/09/2026)

Rama `feat/tortuaria`. Fase 2 del roadmap maestro.

### Agregado
- **🐉 Tortuaria: tu primer juego de rol** — 10 lecciones (42 pasos) en 4 zonas: la aldea (tu héroe, el primer golpe,
  ¿sigue en pie?), el bosque (los dados, el ataque, una acción que se repite), la cueva (combate por turnos, el
  inventario, pociones) y la mazmorra (**jefe final: la Mazmorra del Bug**). Cada concepto aparece porque el juego lo
  necesita. Presenta `dado()`, las listas con `para … en` y `y`. Todos los pasos con opciones tienen pista propia.
  Se abre al terminar *Desafío final*. En total: 5 cursos, 64 lecciones.
- Segunda encuesta local: "¿Qué tipo de juego te gustaría crear?".

### Cambiado
- Las encuestas aparecen **como mucho una por curso terminado**: nunca dos seguidas.
- El test del paquete toma la lista de cursos de `ORDEN_CURSOS` en vez de tenerla escrita a mano.

## Sin publicar — prueba simulada con chicos (26/09/2026)

Rama `feat/simulacion-chicos`.

### Agregado
- `herramientas/simular_chicos.py`: **8 perfiles sintéticos** (10 a 14 años; celular, tablet y compu; letra enorme,
  alto contraste, solo teclado; quien usa pistas y quien se rinde rápido; con y sin diagnóstico) juegan por la interfaz
  real y se equivocan de forma reproducible. Escribe un informe en Markdown.
- Primer informe: [`docs/validacion/simulacion-2026-09-26.md`](docs/validacion/simulacion-2026-09-26.md).
  **Robustez: pasa** (62 lecciones, 363 pasos, 0 errores de consola, 0 trabas, 0 desbordes). **Retención y gusto: sin
  respuesta** (una simulación no los mide). Hallazgo real de la auditoría de contenido: 137 pasos usan la pista
  genérica en vez de una propia.

## Sin publicar — intereses locales (26/09/2026)

Rama `feat/intereses`. Implementa ADR-005 (aceptada). Esquema del progreso **v10** (aditivo: campo `intereses`).

### Agregado
- Al terminar un curso, el inicio pregunta **"¿Qué te gustaría crear ahora?"** (videojuegos, aventura y rol, estrategia,
  dibujos, web, robots e IA, historias, "no sé todavía"). Se pueden elegir varias o tocar **"Ahora no"**, y no se
  vuelve a preguntar.
- Todo queda en el progreso local: nada se manda a ningún lado. Solo opciones cerradas, sin texto libre. Viaja en la
  exportación del progreso (y al importar se descarta lo que no corresponda).
- Las encuestas son datos (`contenido/encuestas/*.json`) y un test les aplica las reglas de estilo de los cursos.

## Sin publicar — diagnóstico: elegir dónde empezar (26/09/2026)

Rama `feat/diagnostico`. Implementa ADR-004 (aceptada). Esquema del progreso **v9** (aditivo: campo `salteadas`).

### Agregado
- En la bienvenida, quien ya programó ("un poquito" o "bastante") puede elegir **dónde empezar**: desde el principio
  (viene elegido) o en *Variables* / *Condicionales*.
- Las lecciones anteriores quedan **salteadas** (⏭ en el camino, "la salteaste: hacela cuando quieras"): no dan XP,
  logros, liga ni certificado, se pueden hacer cuando se quiera y, al hacerlas, pasan a hechas normalmente.
- El servidor solo acepta el punto de entrada que corresponde a la experiencia elegida.

## Sin publicar — azar con dado() (26/09/2026)

Rama `feat/dado`. Implementa ADR-009 (aceptada).

### Agregado
- **`dado(caras)`**: un número al azar de 1 a `caras` (6 si no se dice), igual en TortuScript y en Python. Sin `import`:
  el ejecutor sigue igual de cerrado. Si se usa mal (`dado("seis")`, `dado(1)`), lo explica en lenguaje simple.
- **Azar reproducible**: al evaluar y al validar se usa siempre la misma semilla, así que un ejercicio con dados se
  puede comprobar ("mismo código + misma semilla = mismo resultado"). Al jugar libremente, cada ejecución tira distinto
  y, si el programa pregunta algo, la página repite la semilla para que las tiradas no cambien entre vueltas.
- `dado` en la Referencia (Operaciones matemáticas) y resaltado en el editor.

## Sin publicar — herramientas de verificación con Playwright (26/09/2026)

Rama `chore/playwright-dev`.

### Agregado
- `requirements-dev.txt` con `playwright==1.63.0` (auditado: Apache-2.0, sin CVE en OSV; solo para desarrollo).
  En discos sin permiso de ejecución va en un venv aparte (ver README).
- Primera corrida de las tres herramientas: el jugador de cursos resolvió **54/54 lecciones (301 pasos) sin errores
  de consola** (tampoco violaciones de CSP); contraste WCAG AA sin problemas.

### Corregido
- Pantallas de 320–360 px: las tres casillas de estadísticas del inicio y los botones de certificado de *Logros* se
  salían de la pantalla (las detectó `revisar_responsive.py`).

## Sin publicar — cierre de lección reforzado (26/09/2026)

Rama `feat/cierre-de-leccion`.

### Agregado
- Al terminar una lección, la pantalla final cuenta **qué aprendí → qué gané → qué sigue**: las palabras que la lección
  presentó por primera vez (📚 *Aprendiste*), las que se usaron para practicar (🔁 *Practicaste*), el XP y los aciertos, y
  el botón **▶ Sigue: <próxima lección>**.
- Las palabras salen del propio contenido, con la misma regla del validador (una palabra se "aprende" donde aparece por
  primera vez en una *Forma* o un ejemplo, recorriendo los cursos en orden). En *Python real* se usan sus
  `palabras_pista`. Ningún campo nuevo en los JSON.

### Cambiado
- `translator.palabras_usadas()` concentra el cálculo de palabras que antes estaba solo en el validador.
- README: coma mal puesta en la lista de herramientas.

## Sin publicar — página de ayuda (26/09/2026)

Rama `feat/ayuda`.

### Agregado
- **❓ Ayuda** (menú *Más*): 10 preguntas frecuentes con respuestas cortas, distinta de la Referencia del lenguaje.
  Cómo empezar, si hay que guardar, varios chicos en la misma compu, cómo pasar el progreso a otra compu, qué pasa si
  te equivocás, la racha, la accesibilidad, dónde ver cómo se escribe algo, qué hacer si algo no anda (el código de
  referencia y el log) y si hace falta internet.
- La ayuda es dato (`contenido/ayuda.json`) y un test le aplica las mismas reglas de estilo que a los cursos.
- No guarda reportes ni opiniones: eso es feedback local y depende de ADR-005, que sigue en Propuesta.

## Sin publicar — pantalla de retorno (26/09/2026)

Rama `feat/pantalla-de-retorno`.

### Agregado
- **Al volver un día nuevo**, el inicio saluda "¡Hola de nuevo!" y cuenta qué pasó la última vez y qué sigue:
  "Ayer ganaste 40 XP. Hoy te espera «Dos líneas». Y tenés 3 tarjetas para repasar", con el botón **▶ Continuar**.
  Solo cuenta lo bueno: si faltó varios días, no lo reta. Usa datos que el progreso ya guardaba (sin cambio de esquema).

## Sin publicar — exportar e importar el progreso (26/09/2026)

Rama `feat/exportar-importar`.

### Agregado
- **Guardar el progreso en un archivo y traerlo en otra compu**, desde el modal de perfiles (👤). El archivo
  (`tortuscript-<perfil>-<fecha>.json`) lleva el progreso completo: lecciones, XP, logros, ajustes y proyectos.
- **Importar nunca pisa nada**: crea un perfil nuevo (`lua`, o `lua_2` si ya existe) y cambia a ese perfil.
- El archivo importado se valida como entrada de afuera (`tortuscript/respaldo.py`): formato y versión, tipo de cada
  campo, sin números negativos, meta/experiencia/ajustes válidos, proyectos con las mismas reglas que al guardarlos,
  tope de 1 MB y nombre de perfil saneado. Los campos desconocidos se descartan.

## Sin publicar — páginas de error humanas (26/09/2026)

Rama `feat/pagina-de-error`.

### Agregado
- **Páginas de error propias** para 400, 403, 404 y 500, en lenguaje para chicos y con un botón para volver al inicio,
  en vez de las páginas genéricas en inglés de Flask. En la API, el mismo mensaje en JSON (`error`, `mensaje`).
- Un error interno muestra "Algo se rompió de nuestro lado... Tu progreso sigue guardado" y un **código de referencia**
  (p. ej. `8F72A1`) que queda en `logs/tortuscript.log` junto con la traza. Nunca se muestran trazas ni rutas.
- La página de error no depende del progreso: se muestra aunque lo que falló sea cargarlo.

## Sin publicar — cabeceras de seguridad y CSP (26/09/2026)

Rama `feat/security-headers`. Era el único punto en FAIL de la auditoría de seguridad
(`docs/experimental/SEGURIDAD_SITIO_PROFESIONAL.md` §22).

### Agregado
- **Cabeceras de seguridad en toda respuesta** (páginas, API, estáticos y errores): Content-Security-Policy,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy`,
  `Cross-Origin-Opener-Policy` y `Cross-Origin-Resource-Policy`.
- La CSP solo permite scripts propios (`script-src 'self'`: nada inline, nada de `eval`, nada de afuera) y ninguna
  página se puede meter en un marco. Los estilos inline siguen permitidos porque las plantillas usan `style=`.
- Un test recorre todas las plantillas y páginas y falla si vuelve a aparecer un script inline.

### Cambiado
- El token de la sesión y los avisos viajan como dato JSON (`#tortu-config`), no como script inline. El botón de
  imprimir del certificado y la lista de *Mis proyectos* se inician desde sus `.js`.
- El confeti se dibuja sin Worker (antes lo creaba desde `blob:`), así la CSP no necesita abrir `blob:`.

## Sin publicar — color de la tortuga por nivel (26/09/2026)

Rama `feat/color-por-nivel`.

### Agregado
- **La tortuga cambia de color al subir de nivel** (niveles de XP 1–10: verde, turquesa, azul, violeta, fucsia, rojo,
  naranja, dorado, marrón y negro). Todos contrastan al menos 3:1 con el fondo blanco del lienzo, y el nivel 1 es el
  verde de siempre. El color se actualiza en el momento en que se sube de nivel.

### Cambiado
- El **cuerpo** de la tortuga ya no toma el color del lápiz: muestra el progreso del chico. El **lápiz** arranca siempre
  en verde y solo cambia con `color`, así que los dibujos que se comparan en los ejercicios no se ven afectados.

## Sin publicar — laberintos de la tortuga (26/09/2026)

Rama `feat/laberinto`.

### Agregado
- **Tres laberintos** al final de *Dibujá con la tortuga* (lecciones 13–15): recto y con giros, más giros, y una
  escalera que exige `repetir`. El curso pasa a 15 lecciones (54 en total).
- **Nueva forma de comprobar** los pasos `escribir` con `laberinto`: no se compara con un dibujo, se revisan las reglas
  del mundo (no tocar paredes y terminar en la 🏁). Vale cualquier ruta. Si la tortuga choca, se frena contra la pared
  y el chico ve la línea que la hizo chocar, marcada en el editor. `usar` exige palabras (p. ej. `repetir`).
- El validador revisa el dato del laberinto y que la solución oficial llegue sin chocar y use lo que pide `usar`.

### Cambiado
- El paso final de *12. Reto: la espiral* ya no dice "¡Terminaste!": anuncia los laberintos. El cierre del curso pasó
  al final de *15. Laberinto III*. No se borró ni se movió ningún paso, así que el progreso guardado no cambia.

## Sin publicar — migración a aplicación web (25/09/2026)

Rama `feature/migracion-web-paridad`. Fases F0 a F9 del roadmap (`docs/ROADMAP_MIMO_KIDS.md`).

### Agregado
- **App web local** (Flask + HTML/CSS/JS, sin build, todo offline) con paridad completa con la app
  de escritorio: ejercicios, Experimentar, Zona Tortuga con canvas y depurador paso a paso, Mapa,
  Resumen, Repaso (4 modos), Referencia, perfiles, sonidos y confeti.
- **Motor de lecciones** con 6 tipos de paso (explicación, elegir, predecir, completar con fichas,
  ordenar y escribir), feedback por paso, pista específica, "ver respuesta" tras 2 errores y
  progreso por lección.
- **Cuatro cursos, 51 lecciones, 291 pasos**: Primeros pasos (30), Dibujá con la tortuga (12),
  Proyectos guiados (3) y De TortuScript a Python real (6). Los cursos se abren al terminar una
  lección de otro curso; las lecciones pueden pedir otra.
- **Camino** como pantalla de inicio, **onboarding** de 3 pasos y **meta diaria** con anillo.
- **Gamificación amable**: racha con congeladores que se ganan, reto de 7 días, 25 logros, liga
  semanal local con rivales simulados, práctica del día (repaso espaciado e intercalado).
- **Mis proyectos** (guardar, abrir, duplicar, borrar) y **certificado imprimible** por curso.
- **Accesibilidad**: tamaño de letra, alto contraste, letra fácil de leer, menos movimiento,
  teclado completo, lectores de pantalla y lectura en voz alta de las consignas.
- Validador automático de contenido (`herramientas/validar_contenido.py`) integrado a los tests.
- Herramientas opcionales con Playwright: jugador de cursos, revisor de contraste y servidor de
  prueba. `herramientas/crear_paquete.py` arma un `.zip` instalable.
- Lanzador `iniciar_web.py` y accesos directos para Windows y Linux; ícono.
- Documentación: `docs/CONTENIDO.md`, ADR-001 (migración) y ADR-002 (cursos como datos).

### Cambiado
- Pantallas chicas: el encabezado se compacta con un botón **Menú** y ninguna página se desborda en 320–768 px
  (`herramientas/revisar_responsive.py`). El servidor usa conexiones HTTP/1.1 que se reusan.
- **Límite de memoria** del subproceso también en Windows (Job Object vía `ctypes`, sin dependencias): una bomba de
  memoria termina con un mensaje claro en vez de congelar la compu. Los pedidos web van de a uno para que el
  progreso no se pise entre pestañas.
- El código del chico corre en un **subproceso** con límites (antes, dentro de la app).
- Los niveles se recalibraron (80/180/300/440/600/780/980/1200/1350 XP) porque el XP máximo pasó
  de 900 a 1460. El XP guardado no cambia.
- El progreso pasó del esquema 2 al 8, **siempre agregando campos**: los archivos anteriores
  siguen abriéndose y se completan solos.
- El límite de tiempo del subproceso es de 10 s (un antivirus puede demorar el arranque de Python).

### Corregido
- El worker escribía su JSON en cp1252 en Windows y fallaba con emojis en cualquier mensaje de error.
- Dos diferencias de Python 3.9 (comillas sin cerrar en el traductor y `:` faltante en el mensaje
  de error).
- Chips y botones con texto oscuro sobre fondo oscuro y botones violetas con poco contraste.

### Eliminado
- La app de escritorio Tkinter: `ui/`, `main.py`, `highlighter.py`, `celebracion.py`,
  `dialogo_preguntar.py`, `sounds.py` y `utils.py`, además del parámetro `pedir_entrada` del ejecutor.
