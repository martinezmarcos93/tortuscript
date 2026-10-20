# Especificación — fases P1, P3, P4, P5 y P6 del roadmap pedagógico

**Fundamento:** `docs/ROADMAP_PEDAGOGIA_ADAPTATIVA.md` · ADR-052 (Aceptada: modelo de dominio y planificador adaptativo) ·
`docs/MODELO_DOMINIO_V1.md` (P2, ya implementado en `tortuscript/dominio.py`).
**Emitida por:** Claude Code (director), 19/10/2026, por pedido de Marcos de terminar el roadmap.
**Rama:** `pedagogia/p1-p6` (sale de `integracion/2026-10-19`).

Reglas comunes a todas las fases (además de las 9 restricciones del roadmap):

- Todo módulo nuevo es **puro**: recibe `progreso`, `cursos`, `mapa`, `hoy`; no toca disco ni lee el reloj (salvo las herramientas de línea de comandos).
- **No cambia el esquema del progreso** (`VERSION_ESQUEMA` sigue en 11) ni recopila datos nuevos de menores. Nada sale de la máquina.
- **No muta** el `progreso` recibido (probar con `copy.deepcopy`).
- Datos dañados: se ignoran sin lanzar, igual que en `practica.py` y `dominio.py`.
- Sin dependencias nuevas. Tests con `unittest` (stdlib). Comentarios cortos, en español.

---

## P1 — Mapa de cobertura pedagógica

### P1.a `tortuscript/cobertura.py` (puro)

```python
def cobertura(cursos: list, mapa: dict) -> dict:
    """{unidad_id: {"curso": str, "lecciones": [ids], "pasos": int,
                    "tipos": {tipo: n},            # los 6 tipos, con 0 si no aparecen
                    "categorias": [ordenadas según dominio.CATEGORIAS],
                    "faltan": [categorías de dominio.CATEGORIAS ausentes, en ese orden]}}
    Solo unidades de tipo "lecciones", en el orden del mapa. Lecciones o cursos inexistentes aportan 0."""

def resumen(cob: dict) -> dict:
    """{"unidades": n, "con_una_categoria": [ids], "sin_produccion": [ids], "completas": [ids con las 4 categorías]}"""

def tabla_markdown(cob: dict) -> str:
    """Tabla Markdown: | Unidad | Curso | Pasos | Reconocimiento | Predicción | Construcción | Producción | Faltan |"""
```

La categoría de cada tipo es la de `dominio._CATEGORIA_POR_TIPO` (`explicacion` no es categoría). Reutilizá esa tabla: no la copies.

### P1.b `herramientas/cobertura_pedagogica.py`

CLI: sin argumentos imprime la tabla y el resumen; con `--escribir` regenera `docs/audits/COBERTURA_PEDAGOGICA.md`
(encabezado fijo, fecha que se pasa con `--fecha AAAA-MM-DD` o la de hoy, tabla y resumen). Sale con 0.

### P1.c Secuencias y huecos de contenido (después de ver el informe)

- Solo se **agregan pasos al final** de una lección existente. Nunca se insertan en el medio, se reordenan, se borran ni se
  cambian ids. En `primeros-pasos` no se agregan pasos `escribir` (su posición es clave del progreso histórico).
- Prioridad: unidades con una sola categoría; después, las que no tienen `prediccion` o `construccion`.
- Cada paso nuevo debe ser **otro ángulo** del concepto (no la misma pregunta con otras palabras) y pasar el validador.
- El intercalado entre conceptos lo hace el planificador (P3), no el contenido.

---

## P3 — Planificador adaptativo (`tortuscript/planificador.py`)

### Interruptor y fallback

- `VARIABLE = "TORTU_PLANIFICADOR"`. `activo(entorno=None) -> bool`: `True` solo si `entorno` (por defecto `os.environ`)
  tiene `TORTU_PLANIFICADOR == "adaptativo"` (sin distinguir mayúsculas ni espacios alrededor). **Apagado por defecto.**
- `elegir_sesion(progreso, cursos, hoy, mapa=None, entorno=None, cantidad=practica.POR_SESION) -> [(leccion_id, paso)]`:
  - apagado → devuelve exactamente `practica.elegir(progreso, cursos, hoy, cantidad)`;
  - encendido → `elegir(...)`; si lanza cualquier excepción, `logger.error(..., exc_info=True)` y devuelve `practica.elegir(...)`.
- `web/app.py`, ruta `/practica`: la única línea que cambia es la que elige las tarjetas, que pasa a `planificador.elegir_sesion(p, _cursos(), date.today())`.

### Selección (`elegir`)

```python
def elegir(progreso, cursos, hoy, mapa=None, cantidad=practica.POR_SESION) -> list[tuple[str, int]]:
```

1. **Pool:** exactamente `practica.candidatos(progreso, cursos, hoy)`. El planificador **nunca** ofrece una tarjeta fuera del pool
   y **no cambia fechas, cajas ni intervalos** (los sigue reprogramando `practica.registrar`, igual que hoy).
2. **Concepto de una lección:** la primera unidad de tipo `lecciones` del mapa (orden del mapa) que la nombra. Sin unidad → concepto `None`.
3. **Nivel del concepto:** `dominio.dominio(progreso, cursos, mapa)[unidad]["nivel"]`. Concepto `None` → nivel `NIVEL_SIN_CONCEPTO = 3`.
4. **Prioridad de una tarjeta** (menor = antes): `(nivel, -vencido, caja, leccion_id, paso)`.
5. **Intercalado:** se agrupan las tarjetas por concepto (las de concepto `None` forman un grupo por lección). Los grupos se ordenan por
   la prioridad de su mejor tarjeta; se toman en rondas (una tarjeta por grupo y ronda), con a lo sumo
   `MAX_POR_CONCEPTO = 2` por grupo y `practica.MAX_POR_LECCION = 2` por lección, hasta `cantidad`. Si con esos topes no se llega
   a `cantidad` y quedan tarjetas, el tope por grupo pasa a `max(MAX_POR_CONCEPTO, ceil(cantidad / grupos))` (igual que `practica.elegir`).
6. Determinista (mismo progreso y `hoy` → misma lista), sin repetidos, `len <= cantidad`, `cantidad <= 0` → `[]`.

### Recomendación de actividad

```python
ORDEN_ACTIVIDADES = ("reconocimiento", "prediccion", "construccion", "produccion")
def recomendar(estado: dict) -> str | None:
    """Recibe un dict de dominio.estado_concepto. Devuelve la primera categoría de ORDEN_ACTIVIDADES que esté en
    `disponibles` y no en `fuertes`; si todas están fuertes y no hay `retencion`, "repaso"; si está consolidado, None.
    Sin disponibles → None."""
```

Sobre «adelantar tras un olvido»: ya lo hace `practica.registrar` (un error manda la tarjeta a la caja 1, mañana). V1 no agrega otra regla de fechas.

---

## P4 — Pistas graduadas

### Contenido (campo nuevo, opcional y aditivo)

En pasos `elegir`, `predecir`, `completar` y `ordenar`: `"pistas": ["…", "…"]`, de 1 a 3 textos no vacíos y distintos, de menos a más ayuda:

1. orientar la atención («Fijate qué pasa con la variable en la segunda línea»);
2. recordar el concepto que hace falta;
3. (opcional) casi la solución, sin decirla.

`pista` sigue siendo **obligatoria** (compatibilidad y respaldo). La solución completa la sigue dando «Ver respuesta», sin cambios.

### Motor (`tortuscript/leccion.py`)

`comprobar(paso, respuesta, ejecutar=None, errores_previos=0)`: cuando la respuesta es incorrecta y la pista vendría de
`paso.get("pista") or PISTAS_GENERICAS[...]`, si el paso tiene `pistas` válidas (lista no vacía de textos no vacíos) se devuelve
`pistas[min(errores_previos, len(pistas) - 1)]`. `errores_previos` = errores **antes** de este intento (0 en el primero).
Un `errores_previos` que no sea un entero `>= 0` (o sea `bool`) se trata como 0. Las pistas fijas de forma
(«Todavía quedan huecos sin completar.», «Todavía faltan líneas por ubicar.») no cambian. La forma del dict devuelto no cambia.
XP, reintentos y «Ver respuesta» no cambian: pedir ayuda no se castiga más que hoy.

`web/app.py`: los dos llamados a `motor.comprobar` (lección y práctica) pasan `errores_previos=estado_paso["errores"]`.

### Validador (`tortuscript/validacion.py`)

Si un paso tiene `pistas`: ERROR si no es una lista de 1 a 3 textos no vacíos y distintos, si está en un tipo que no las usa, o si una
pista contiene literalmente la opción correcta de un `elegir`/`predecir` (cuando esa opción tiene 3 caracteres o más).
Cada pista pasa por la misma revisión de texto que `pista`.

### Contenido inicial

`pistas` en los pasos rápidos de `alfabetizacion-digital` y de las dos primeras secciones de `python-real`. Guía de redacción:
`docs/GUIA_PISTAS.md`.

---

## P5 — Transferencia

### Cursos nuevos (aditivos)

- `contenido/cursos/desafios-tortuscript.json` (`"requiere": {"curso": "primeros-pasos"}`) y
  `contenido/cursos/desafios-python.json` (`"requiere": {"curso": "python-real"}`), agregados al final de `ORDEN_CURSOS`.
- 4 desafíos por curso como mínimo, en una o dos secciones; al menos 1 `guiada` y 2 `autonoma` por curso.
- Cada lección es un desafío: un paso `explicacion` con el problema (sin solución) y uno o más pasos `escribir` evaluados
  **por comportamiento** (`entradas_prueba` y salida/dibujo esperados), nunca por el texto exacto del programa.
- Cada lección lleva `"transferencia": {"conceptos": [ids de lecciones], "asistencia": "guiada" | "autonoma"}`:
  las **lecciones ya existentes** que enseñan lo que hace falta (ADR-053). Un desafío combina **al menos 2**, de cursos
  anteriores en `ORDEN_CURSOS` (no de cursos de desafíos). Las pistas de un desafío `autonoma` orientan, no dan código.
- No exige nada que no se haya enseñado antes: el validador de presentación ya lo comprueba para TortuScript.
- Los cursos nuevos no entran al mapa curricular (como Tortuga, Juegos o Proyectos): no cambian `Curriculum.v1` ni la puerta de pago.

### Validador

Si una lección tiene `transferencia`: ERROR si `conceptos` tiene menos de 2 ids distintos, si alguno no es una lección de
otro curso anterior en `ORDEN_CURSOS`, o si `asistencia` no es `guiada`/`autonoma`. Como necesita ver todos los cursos,
esta regla corre en `herramientas/validar_contenido.py` (y en un test), no dentro de `validar_curso`.

### Matriz

`tortuscript/cobertura.py` suma `matriz_transferencia(cursos, mapa) -> {unidad_id: [ids de lecciones de desafío que la usan]}`
(todas las unidades `lecciones`, lista vacía si ninguna; una lección declarada cuenta para su unidad del mapa) y el informe
de P1 agrega la sección «Desafíos por unidad».

### Consignas evaluables

La consigna dice **exactamente** qué tiene que mostrar el programa (los textos y valores fijos están en la consigna).
Si el problema depende de un dato, el programa lo pide con `preguntar`/`input` y el paso trae `entradas_prueba`.

---

## P6 — Métricas locales y validación

### `tortuscript/metricas_pedagogicas.py` (puro, solo lee lo que ya se guarda)

```python
def metricas(progreso, cursos, mapa=None) -> dict:
    """{"pasos_rapidos":      {"total": n, "primer_intento": n, "con_reintentos": n, "ayudados": n},
        "escribir":           {"total": n, "autonomos": n, "con_ayuda": n},
        "repaso":             {"tarjetas": n, "aciertos": n, "fallos": n, "tasa_acierto": float | None, "retenidas": n},
        "conceptos":          {estado: cantidad, para los 6 ESTADOS, con 0},
        "recomendaciones":    {unidad_id: planificador.recomendar(estado)}   # solo las que no dan None
        "datos_danados":      n}"""
```

- Paso rápido (`elegir`/`predecir`/`completar`/`ordenar`) según su `xp` guardado: `>= 5` primer intento, `1..4` con reintentos,
  `<= 0` ayudado (misma regla que `dominio._fuerza`). `escribir`: autónomo con 3 estrellas o, sin estrellas, `perfecto` True; si no, con ayuda.
- Repaso: suma `aciertos`/`fallos` enteros válidos de `progreso["repaso"]`; `tasa_acierto = aciertos / (aciertos + fallos)`
  redondeada a 3 decimales, `None` si la suma es 0; `retenidas` = tarjetas con `caja >= 3` y `aciertos >= 2`.
- `datos_danados` cuenta registros de paso/tarjeta ignorados por no ser válidos.

### `herramientas/informe_pedagogico.py RUTA_PROGRESO.json`

Imprime las métricas de un archivo de progreso local en texto legible. Solo lectura; no manda nada a ningún lado.

### Informe de validación

`docs/audits/VALIDACION_PEDAGOGICA_P6.md`: línea de base, qué se puede y qué no se puede medir con los datos actuales,
qué es hipótesis y qué está demostrado, y decisiones recomendadas. Lo escribe el director.

---

## Acceso de las lecciones fuera del mapa (ADR-053, aceptada el 19/10/2026)

- `catalogo_producto.unidad_de_cobro(leccion_id) -> str | None`: la unidad del mapa si la lección está en él; si no, de las
  lecciones declaradas en `transferencia.conceptos` o `conceptos`, la unidad premium que aparece primero en el mapa; si no hay, `None`.
- `web/app.py`: `_unidad_del_pedido` y la marca `de_pago` del camino usan `unidad_de_cobro`.
- Validador: en `desafios-*` y en los cursos de juegos nuevos, toda lección declara conceptos.
