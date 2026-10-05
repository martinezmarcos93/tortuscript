# 🐢 TortuScript

TortuScript es el núcleo de una futura plataforma progresiva de aprendizaje tecnológico para niños y adolescentes. La V1 actual se concentra en programación con Python y está evolucionando hacia un itinerario que incluye alfabetización tecnológica, Web esencial (HTML/CSS/JS), SQL y proyectos integradores. La edad exacta de cada itinerario sigue siendo una decisión curricular pendiente de validación.

El producto local actual enseña Python usando **TortuScript**, un pseudolenguaje en español que se traduce solo a Python real. Se usa en el navegador, **corre en tu compu** (sin internet y sin anuncios; la cuenta del adulto y los perfiles de los chicos se guardan en la misma máquina) y se parece a las apps de lecciones cortas: explicación, práctica, feedback al instante, racha, logros y una liga de amigos.

```
# TortuScript               →     Python
mostrar "Hola mundo"        →     print("Hola mundo")
nombre es "Juan"            →     nombre = "Juan"
si edad > 10:               →     if edad > 10:
    mostrar "Grande"        →         print("Grande")
repetir 3 veces:            →     for _ in range(3):
    mostrar "Hola"          →         print("Hola")
funcion saludar(n):         →     def saludar(n):
    mostrar n               →         print(n)
```

---


## Cuentas, perfiles y correo

Para entrar hace falta una **cuenta adulta** (correo y contraseña) y, dentro de ella, hasta tres **perfiles** de chicos;
cada perfil tiene su propio progreso. Todo se guarda en la máquina donde corre TortuScript. Hay tres formas de crear
la primera cuenta, según `TORTU_EMAIL_MODO` (se configura en un archivo `.env` junto a `iniciar_web.py`; ver
[`.env.example`](.env.example)):

| Modo | Qué pasa al registrarse | Para qué sirve |
|---|---|---|
| *(vacío, por defecto)* | El registro y la recuperación de contraseña responden «no disponible» | Instalación sin correo: la cuenta se crea con `python herramientas/crear_admin.py` |
| `consola` | El enlace de verificación aparece en la terminal donde corre el servidor | Uso local en una sola compu |
| `smtp` | El enlace llega por correo desde el servidor SMTP configurado | Despliegue con un proveedor de correo |

`crear_admin.py` pide la contraseña por teclado (nunca queda en el código) y deja la cuenta verificada con rol `admin`,
que además saltea los bloqueos comerciales para pruebas. Detalles en [docs/ADMIN_LOCAL.md](docs/ADMIN_LOCAL.md).
«Olvidé mi contraseña» necesita el modo `consola` o `smtp`.

### Lo que está construido pero apagado

Estas piezas existen en el código y se encienden por configuración (`.env.example`); en la compu de una familia no
hacen falta:

| Pieza | Para qué | Cómo se enciende | Documento |
|---|---|---|---|
| Suscripción por transferencia | El adulto paga por transferencia y quien opera confirma el pago a mano | `TORTU_PAGO_ALIAS` y `TORTU_PAGO_IMPORTE`; confirmar con `herramientas/gestionar_pagos.py` | ADR-047 |
| Pagos automáticos | Eventos de un proveedor de tarjetas (todavía no hay ninguno conectado) | secreto de webhook del proveedor; los eventos que no se pudieron aplicar se ven con `herramientas/revisar_pagos.py` | ADR-032, `tortuscript/pagos.py` |
| Sandbox de contenedores | Ejecutar el código de los chicos aislado, sin red | `TORTU_SANDBOX=docker` | `despliegue/sandbox/README.md` |
| Paso a Croco-Script | Entrar al producto avanzado sin otra cuenta: botón «Ir a Croco-Script» para las cuentas con acceso | `TORTU_CROCO_URL` y `TORTU_CROCO_CLAVE`; el plan se ofrece con `TORTU_PAGO_IMPORTE_CROCO` | `docs/contratos/README.md` |
| Tortu-LLM | Pistas con IA que ayudan a pensar | `TORTU_TUTOR=claude` + aceptación del adulto | ADR-035, `tortuscript/tutor.py` |

En «Configuración de cuenta» el adulto puede cambiar nombres de perfiles, archivarlos, cambiar la contraseña,
descargar todos los datos de la familia, eliminar para siempre un perfil archivado y pedir la eliminación de la
cuenta (queda 14 días pendiente; volver a ingresar la cancela). Desde ahí se llega a «Suscripción», la página de
pagos: muestra el estado del acceso y los medios de pago (hoy transferencia; la tarjeta figura como «próximamente»).

## Cómo se usa

### Para una familia (sin instalar Python)
Bajá el paquete de tu sistema, descomprimilo y seguí `LEEME.txt`:

| Sistema | Paquete | Para instalar |
|---|---|---|
| Linux | `TortuScript-<fecha>-linux-<arq>.tar.gz` | `sh instalar.sh` → aparece en el menú de aplicaciones |
| Windows | `TortuScript-<fecha>-windows-<arq>.zip` (y un `…-instalador.exe` si se armó con Inno Setup) | doble clic en `instalar.bat` → menú Inicio y Escritorio |
| macOS | `TortuScript-<fecha>-macos-<arq>.zip` | doble clic en `instalar.command` → carpeta Aplicaciones |

Cada instalador comprueba que el sistema sea el suyo, no pide permisos de administrador y el desinstalador **nunca borra
el progreso**, que se guarda en la carpeta de datos del usuario. Los paquetes se arman con un solo comando que detecta el
sistema: `python herramientas/construir.py` (ver *Para quien mantiene el proyecto*).

### Desde el código (con Python)

**Requisitos:** Python 3.9 o más nuevo. Nada más: la única dependencia es Flask. `requirements.lock` fija también lo que
Flask trae y verifica cada archivo con su hash (se rearma y se audita con `herramientas/auditar_dependencias.py`).

```bash
python -m venv .venv                          # una sola vez
.venv/bin/python -m pip install --require-hashes -r requirements.lock   # en Windows: .venv\Scripts\python.exe
.venv/bin/python iniciar_web.py               # abre el navegador solo
```

También podés hacer doble clic en `lanzadores/Iniciar TortuScript.bat` (Windows) o correr `lanzadores/iniciar_tortuscript.sh` (Linux/macOS). Para tener un acceso directo: `lanzadores/crear_acceso_windows.ps1` o `sh lanzadores/instalar_acceso_linux.sh`.

Opciones de `iniciar_web.py`: `--sin-navegador` (solo arranca el servidor) y `--puerto N`. Se cierra con Ctrl+C o cerrando la ventana.

Si la red de tu oficina o escuela intercepta certificados SSL y `pip` falla, apuntá `PIP_CERT` al bundle de certificados de tu sistema.

---

## Qué hay adentro

### 🗺️ Aprender: nueve cursos, 108 lecciones + proyectos integradores
Cada lección dura unos 2 minutos y sigue el ciclo **explicar → practicar → escribir**: una tarjeta que explica con un ejemplo que se puede ejecutar, preguntas de elegir, predecir lo que muestra un programa, completar con fichas, ordenar líneas y, al final, escribir el programa. Ante un error hay una pista específica; se puede reintentar y, tras dos errores, ver la respuesta (sin XP en ese paso). **No hay vidas ni castigos.**

| Curso | Lecciones | De qué trata |
|---|---|---|
| 💻 Nivel 0 — El mundo digital por dentro | 16 | conceptos de programas, código, navegador, redes, servidor, datos, API y seguridad |\n| 🐢 Primeros pasos con TortuScript | 30 | mostrar, variables, preguntar, cuentas, si/sino, repetir, mientras, funciones |
| 🎨 Dibujá con la tortuga | 15 | avanzar y girar, figuras con repetir, colores, lápiz, variables y funciones; al final, 3 laberintos donde la tortuga busca la salida (se abre al terminar *Dos variables*) |
| 🛠️ Proyectos guiados | 3 | un adivinador de números, una calculadora y una casa; cada paso sigue desde el código anterior |
| 🐍 De TortuScript a Python real | 9 | print, input, if, for/while, def, datos, listas y resolución de problemas (se abre al terminar *Desafío final*) |
| 🌐 Web esencial | 12 | HTML, CSS y JavaScript para leer, modificar, depurar y construir interfaces pequeñas (se abre al terminar Nivel 0; el recorrido puede elegirse después de alfabetización digital) |
| 🗃️ SQL: datos y consultas | 8 | SELECT, filtros, orden, agregaciones, GROUP BY, JOIN y seguridad básica (se abre al terminar Python o Web) |\n| 🐉 Tortuaria: tu primer juego de rol | 10 | un juego de rol por consola: héroe, golpes, `dado()`, ataques con funciones, combate por turnos con `mientras`, inventario con listas y el jefe final (se abre al terminar *Desafío final*) |
| 🎮 Creá tu juego | 5 | TortuGame: escenas, héroes, enemigos, combates, diálogos, inventario, ganar o perder y decisiones con `preguntar` (se abre al terminar *Tortuaria*) |

El **camino** es la pantalla de inicio: muestra dónde estás y qué sigue. Nivel 0 es la entrada conceptual; al completarlo se puede elegir comenzar por Web o Python. SQL se habilita al completar uno de esos dos recorridos. Las demás rutas históricas mantienen sus prerrequisitos.
Quien ya programó puede elegir en la bienvenida **dónde empezar** (*Variables*, *Condicionales* o lo que recomiende una
**prueba corta de 6 preguntas**): las lecciones
anteriores quedan ⏭ salteadas, sin XP ni logros, para hacerlas cuando quiera. Al volver otro día, el inicio saluda con
lo que pasó la última vez y un botón **▶ Continuar**; al terminar cada lección se ve qué aprendiste, qué practicaste y
qué sigue. Ante un error hay siempre una pista propia de ese paso.

### 🎮 Motivación, sin presión
- **XP y niveles** (10 títulos: 🐣 Aprendiz … 🏆 Maestro). Solo suma cuando mejorás tu mejor resultado.
- **Meta diaria** con anillo: 5, 10 o 15 minutos (20, 40 o 60 XP).
- **Racha** con **congeladores que se ganan** (uno cada 7 días seguidos, hasta 2): si faltás un día, la racha se salva sola. Reto de 7 días.
- **25 logros** que nunca se pierden y una **liga local semanal** (Bronce → Diamante) entre los perfiles de la compu y rivales simulados; suben los 3 primeros y nadie baja.
- **Práctica del día**: repaso espaciado e intercalado (1, 2, 4, 8 y 16 días) con los pasos de lecciones viejas.
- **Certificado imprimible** (o PDF) al terminar cada curso.
- **La tortuga cambia de color** con cada nivel (el lápiz sigue arrancando en verde).
- Al terminar un curso, una pregunta opcional: **¿qué te gustaría crear?** (se puede decir "Ahora no" y no insiste).
  Las respuestas quedan solo en la compu.

### 🧰 Herramientas
- **🧪 Experimentar**: escribís lo que quieras, con la traducción a Python en vivo. Acepta TortuScript o Python, y
  `dado(6)` tira un dado (al evaluar ejercicios el azar es siempre el mismo, así se puede corregir).
- **🎨 Zona Tortuga**: dibujo con `avanzar`, `retroceder`, `girar_der`, `girar_izq`, `color`, `subir_lapiz` y `bajar_lapiz`; con *paso a paso* se resalta cada línea mientras la tortuga la ejecuta. Colores en español (`"rojo"`, `"celeste"`...) o `#rrggbb`. La tortuga cambia de color con cada nivel de XP; el lápiz arranca siempre en verde.
- **🎮 Juegos**: creás un juego de rol por turnos con TortuGame (`docs/TORTUGAME.md`) y lo ves en una escena animada, con todo lo que pasa escrito abajo. Corre en el navegador, aislado de la página y de la red.
- **📂 Mis proyectos**: guardar, abrir, duplicar y borrar lo hecho en Experimentar, la Zona Tortuga y Juegos (hasta 30 por perfil).
- **📖 Referencia** del lenguaje, **🗺️ Mapa** de los 30 ejercicios clásicos, **🔁 Repaso** de ejercicios (4 modos), **📊 Resumen** de hoy y **❓ Ayuda** con las preguntas más comunes.
- **👤 Perfiles**: cada chico tiene su progreso, sus ajustes y su meta en la misma compu. Desde el botón del perfil se puede **guardar el progreso en un archivo** y **traerlo en otra compu** (crea un perfil nuevo, no pisa nada).

### ♿ Accesibilidad y voz
Ajustes por perfil (⚙️): tamaño de letra grande y enorme, alto contraste, tipo de letra fácil de leer, menos movimiento y **lectura en voz alta** de las consignas (usa las voces del sistema, sin internet). Se maneja todo con el teclado (enlace *Saltar al contenido*, foco visible, `Esc` sale del editor, teclas `1`–`9` eligen opciones) y funciona con lectores de pantalla. El contraste de las páginas principales cumple WCAG AA (`herramientas/revisar_contraste.py`).

---

## El lenguaje TortuScript

| TortuScript | Python | Descripción |
|-------------|--------|-------------|
| `mostrar X` | `print(X)` | Mostrar en pantalla (`mostrar "a", 3` junta varias cosas) |
| `X es Y` | `X = Y` | Asignar variable (dentro de una condición, `es` compara) |
| `preguntar("msg")` | `input("msg")` | Pedir un dato |
| `si` / `sino si` / `sino` | `if` / `elif` / `else` | Condicionales |
| `repetir N veces:` | `for _ in range(N):` | Repetir |
| `para x en lista:` | `for x in lista:` | Recorrer una lista |
| `mientras cond:` | `while cond:` | Repetir mientras se cumpla |
| `funcion n(p):` / `devolver X` | `def n(p):` / `return X` | Funciones |
| `y` / `o` / `no` | `and` / `or` / `not` | Lógica |
| `Verdadero` / `Falso` | `True` / `False` | Booleanos |

Las palabras aceptan **tildes y mayúsculas** (`función`, `Mostrar`). `y`, `o`, `no` y `color` solo se traducen cuando funcionan como operador o comando: se pueden usar como nombres de variable. La indentación puede ser con espacios o con Tab.

---

## Cómo está hecho

```
proyecto/
├── iniciar_web.py            ← lanzador (abre el navegador)
├── lanzadores/               ← .bat / .sh / accesos directos
├── requirements.txt          ← Flask
├── tortuscript/              ← NÚCLEO sin interfaz
│   ├── translator.py         ← TortuScript → Python (con tokenize)
│   ├── executor.py           ← ejecuta el código del chico con protecciones
│   ├── worker.py, proceso.py ← el código corre en un subproceso con límites
│   ├── error_handler.py      ← errores explicados en lenguaje simple
│   ├── evaluacion.py         ← compara salidas y dibujos con la solución
│   ├── tortuga.py            ← la tortuga como registro de órdenes + comparación de dibujos
│   ├── leccion.py            ← motor de lecciones (pasos, comprobación, camino, cursos)
│   ├── practica.py           ← repaso espaciado
│   ├── logros.py, liga.py    ← gamificación
│   ├── proyectos.py          ← Mis proyectos
│   ├── progreso.py           ← XP, racha, perfiles, ajustes (guardado seguro)
│   ├── contenido.py, referencia.py, validacion.py
├── contenido/                ← los cursos y la referencia, como DATOS (JSON)
├── web/                      ← Flask: app.py, templates/, static/{css,js,vendor,fonts,img}
├── herramientas/             ← validador de contenido, jugador de cursos, contraste, paquete
├── tests/                    ← unittest
└── docs/                     ← ADR, roadmap, guía para escribir cursos
```

- **El contenido es dato, no código.** Los cursos están en `contenido/cursos/*.json` y los revisa un **validador automático** que corre cada respuesta, cada fragmento y cada salida esperada: nunca llega a la pantalla un ejercicio roto. Guía completa en [`docs/CONTENIDO.md`](docs/CONTENIDO.md).
- **Un solo servidor local.** Flask escucha solo en `127.0.0.1`; toda la API exige un token secreto de la sesión (una página ajena abierta en el navegador no puede usarla) y se rechazan `Host` que no sean locales.
- **El código del alumno nunca se ejecuta dentro del proceso Flask.** En el modo local educativo se ejecuta en un proceso hijo controlado con límite de tiempo y de memoria (512 MB: `resource` en Linux/macOS, un Job Object en Windows; el de CPU es solo Linux/macOS), validación previa con AST (sin `import` ni nombres que empiecen con `_`), builtins limitados, tope de 50.000 pasos y de 20.000 caracteres de salida. **No es un sandbox para código hostil**: protege al chico de errores y de copiar/pegar cosas peligrosas.
- **`preguntar()`** se resuelve re-ejecutando el programa con las respuestas acumuladas; la tortuga es un registro de órdenes que el navegador anima en un `<canvas>`.
- **Todo offline**: CodeMirror, confeti y las fuentes están en `web/static/`; no se pide nada a internet.
- **Cabeceras de seguridad en toda respuesta**: una CSP que solo deja correr scripts propios (nada inline ni de afuera) y no deja enmarcar la app, más `nosniff`, `no-referrer` y `Permissions-Policy` (`web/app.py`, `CABECERAS_SEGURIDAD`).

Decisiones de diseño: [`docs/decisions/`](docs/decisions/README.md) (ADR-001 a ADR-015, con su estado en el índice).

---

## Dónde se guarda el progreso

Instalado con el paquete de tu sistema, en la carpeta de datos del usuario: `~/.local/share/tortuscript` (Linux),
`%APPDATA%\TortuScript` (Windows) o `~/Library/Application Support/TortuScript` (macOS). Desde el código, como siempre:

En `progreso_<perfil>.json`, junto al programa (el perfil inicial es `default`). Cada guardado es atómico y deja una copia `.bak`; si el archivo se daña se aparta como `.corrupto-<fecha>` y se recupera desde la copia: nunca se pisa en silencio. El esquema es **aditivo**: los archivos de versiones anteriores se abren y se completan solos (hoy es la versión 10). Para empezar de cero un perfil, borrá su `progreso_<perfil>.json` (y el `.bak`).

Con cuentas, la base (`cuentas.sqlite3`) y el progreso de cada perfil (`progreso_perfiles/progreso_child_<id>.json`,
con el mismo guardado atómico, `.bak` y recuperación) viven en `instance/` dentro de esa misma carpeta de datos. El
nombre del chico no aparece en el nombre del archivo.

**Respaldo.** `python herramientas/respaldar_datos.py crear` copia la base y el progreso de todos los perfiles a
`respaldos/respaldo-<fecha>/` con un manifiesto de hashes; `verificar <carpeta>` comprueba que esté íntegro y
`restaurar <carpeta> --confirmar` lo vuelve a poner (con TortuScript cerrado), dejando lo que había en
`instance.antes-de-restaurar-<fecha>`. Nada se borra nunca.

Los logs de errores internos van a `logs/tortuscript.log` y nunca se muestran al chico.

---

## Para quien mantiene el proyecto

```bash
python -m unittest discover tests            # tests Python; los de JavaScript se saltean si no hay Node
python herramientas/validar_contenido.py     # valida todos los cursos
python herramientas/crear_paquete.py         # arma dist/TortuScript-<fecha>.zip para instalar en otra compu
```

Con **Playwright** (opcional, fijado en `requirements-dev.txt`, no en `requirements.txt`) se puede verificar la interfaz real.
Si el proyecto está en un disco que no permite ejecutar programas (NTFS montado sin `exec`), Playwright tiene que ir en
un venv fuera de ese disco:

```bash
python3 -m venv ~/.venvs/tortuscript-dev
~/.venvs/tortuscript-dev/bin/python -m pip install -r requirements-dev.txt
~/.venvs/tortuscript-dev/bin/python -m playwright install chromium
# y después, las herramientas con ~/.venvs/tortuscript-dev/bin/python en lugar de python
```

```bash
python herramientas/servidor_de_prueba.py    # servidor con progreso temporal (otra terminal)
python herramientas/servidor_de_prueba.py 5077 --todo-desbloqueado --abrir   # revisar todo el contenido sin jugar lo anterior
python herramientas/jugar_cursos.py          # juega TODAS las lecciones por el navegador
python herramientas/revisar_contraste.py     # contraste WCAG AA en modo normal y alto contraste
python herramientas/revisar_responsive.py    # que nada se desborde en pantallas de 320 a 768 px
python herramientas/simular_chicos.py --informe docs/validacion/simulacion-<fecha>.md
                                             # prueba SIMULADA: 8 perfiles juegan y se equivocan (servidor sin --todo-desbloqueado)
```

La rama principal es `main`. El roadmap de finalización V1 hasta el 31/12/2026 está en `docs/ROADMAP_V1_2026-12-31.md`; la definición de producto está en `docs/PRODUCTO_V1.md`. Cambios recientes: [`CHANGELOG.md`](CHANGELOG.md). Roadmap: [`docs/ROADMAP_MIMO_KIDS.md`](docs/ROADMAP_MIMO_KIDS.md).

*Hecho con 🐢 y mucho amor para aprender a programar de a poco.*
