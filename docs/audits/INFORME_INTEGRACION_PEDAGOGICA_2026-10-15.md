# Informe de integración — primer ciclo pedagógico (**integrado a `prod`** el 15/10/2026)

**Fecha:** 15/10/2026
**Estado:** integrado a `prod` con autorización expresa de Marcos (15/10/2026). `main` no se tocó. Este informe se
escribió como preparación y se actualizó con lo ocurrido; las secciones 1 a 8 conservan el análisis previo a la
integración, la §11 registra la integración real.
**Base:** `origin/prod` en `2ac6b2a`.
**Combinación candidata:** rama `candidata/pedagogia-2026-10-15` (cinco cambios fusionados con `--no-ff`, sin conflictos),
usada solo para validar.

> Convención: **[EJECUTADO]** salida real obtenida; **[ESTÁTICO]** lectura sin ejecutar; **[NO VERIFICADO]** no
> comprobable en este entorno.

## 1. Estado y alcance de cada PR

| PR | Rama | Último commit | Alcance | Archivos |
|---|---|---|---|---|
| #19 | `fix/test-409-contrato-obsoleto` | `acea87a` | Alinea un test obsoleto con el contrato del #15 (el 409 se conserva en cola y no se da por borrado ni se reintenta). Solo test. | `tests/test_federacion_respuestas.py` |
| #20 | `feature/alfabetizacion-preguntas-coherentes` | `8c0bca1` | Corrige 19 pasos `elegir` de `alfabetizacion-digital` (preguntas incoherentes, pistas, distractores, 6 preguntas de 2 opciones). | `contenido/cursos/alfabetizacion-digital.json` |
| #23 | `test/identidad-ejercicios-historicos` | `e6b3b7a` | Fija los 30 pares `(leccion_id, paso)` de los `escribir` históricos de `primeros-pasos` (2 tests nuevos). | `tests/test_contenido.py` |
| #21 | `docs/auditoria-dinamica-pedagogica` | `deac677` (+ ajuste de referencia) | Auditoría P0 (segunda pasada), este informe y entradas del CHANGELOG. | `docs/audits/…`, `CHANGELOG.md` |
| #24 | `docs/revision-regresiones-contratos` (borrador, de ChatGPT) | `076580d` | Revisión estática de brechas de regresión (progreso, XP, migración, repaso). **Fuera de la candidata por decisión de Marcos**; se mantiene abierto y sus hallazgos pasan al backlog (§5-bis). | `docs/audits/REVISION_REGRESIONES_CONTRATOS_2026-10-15.md` |
| #18 | `docs/validacion-pedagogica-chatgpt` (borrador, de ChatGPT) | `8803c50` | Matriz de cobertura y revisión de contratos (estáticas). **No lo marqué como listo ni lo modifiqué.** | `docs/audits/MATRIZ_…`, `REVISION_…`, `docs/ROADMAPS.md` |

## 2. Diff y conflictos semánticos

- **Sin solapamiento de archivos** entre las cinco ramas [EJECUTADO: `git diff --name-only` por rama]. La fusión de las
  cinco sobre `prod` no produjo conflictos.
- **#19 no toca producción** [EJECUTADO]: `git diff --name-only origin/prod origin/fix/test-409-contrato-obsoleto` solo lista
  `tests/test_federacion_respuestas.py`. El test ahora afirma `solicitar(...) is False`, un único pendiente con
  `estado = conflicto_409` y `reintentar_pendientes() == 0`, es decir, el contrato del #15 que ya cubre
  `test_federacion_conflictos.py`.
- **#20 y #23** actúan sobre cursos distintos (`alfabetizacion-digital` y `primeros-pasos`): no pueden pisarse.
- **Interacción #21 ↔ #18:** el informe P0 cita y corrige afirmaciones de la matriz de #18 (§7) sin editar sus
  archivos. `docs/ROADMAPS.md` (editado por #18) **no enlaza** la auditoría P0 ni este informe: se evitó editarlo para no
  generar conflicto con #18; ver §9.
- Combinaciones que podrían fallar aunque cada PR esté bien: se validó la combinación completa (§3); no se halló ninguna.

## 3. Resultados de pruebas

### Combinación candidata (suite completa sobre `4e131d8`; ediciones posteriores solo documentación, ver §8-bis)
| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests -v` | **[EJECUTADO]** 1017 tests, **OK**, 0 fallos, 0 errores, 2 omitidos (≈273 s) |
| omitidos | `test_limites.TestJobObjectWindows` ×2: «el Job Object es de Windows» (no aplica a Linux) |
| `python herramientas/validar_contenido.py` | **[EJECUTADO]** exit 0, 0 errores; 2 avisos, ambos en `primeros-pasos` (§5) |
| Tests de JavaScript (Node v24.20.0, vía `test_js.py`) | **[EJECUTADO]** incluidos en la suite, OK |
| Contrato `curriculum-v1.json` | **[EJECUTADO]** la suite informa «está al día» |
| Recorrido HTTP de `alfabetizacion-digital` (cliente Flask) | **[EJECUTADO]** 16 lecciones → 200; 45 respuestas correctas aceptadas; 90 incorrectas rechazadas con la pista propia del paso |
| Recorrido en navegador real | **[NO VERIFICADO]** Playwright no instalado |

### Comparación contra `prod` sin cambios
`prod` limpio: 1015 tests, 1 fallo (el del 409), 2 omitidos. Candidata: 1017 tests (+2 de #23), 0 fallos. Es decir:
**fallo preexistente: 1, corregido por #19; regresiones introducidas: 0.**

### Pruebas individuales
- #19: `test_federacion_respuestas` + `test_federacion_conflictos`, 37 tests OK **[EJECUTADO]**.
- #20: validador (0 errores, 0 avisos en el curso), `test_contenido` y `test_camino` OK **[EJECUTADO]**; suite completa
  con #20 aplicado sobre `prod`: 1015 tests con el único fallo preexistente del 409.
- #23: `test_contenido` 41 tests OK; prueba de mutación (insertar un paso antes de un `escribir` histórico) hace fallar el
  test nuevo **[EJECUTADO]**.
- #21 y #18 son documentación: sin suite propia. **La suite completa no se corrió rama por rama** (disjuntas, 5 min cada
  una); se corrió sobre la combinación.

## 4. Contenido y garantías de compatibilidad

**[EJECUTADO]** comparando los nueve cursos entre `prod` y la candidata:

- Metadatos de curso idénticos (incluida la `version` de `alfabetizacion-digital`, 3).
- Estructura idéntica en los nueve cursos: IDs de sección y lección, títulos, `requiere` y **tipo de cada paso en cada
  posición**. Por lo tanto no cambian IDs, prerrequisitos, desbloqueos ni claves del progreso guardado.
- Texto distinto solo en **19 pasos de `alfabetizacion-digital`** (13 lecciones); 0 pasos distintos en los otros ocho
  cursos, incluido `primeros-pasos` (posiciones 0–29 de los `escribir` intactas).
- Sin cambios en `tortuscript/`, `web/`, `herramientas/` ni `docs/contratos/` [EJECUTADO: `git diff --stat` vacío].
- El campo `correcta` no cambió en ningún paso (el motor mezcla las opciones, así que el orden de lectura no revela la
  respuesta).
- Revisión pedagógica paso a paso del #20 (§4.1 del informe P0): coherencia pregunta–respuesta–distractores–pista,
  vocabulario contrastado manualmente con las explicaciones del curso, sin contenido ajeno al alcance. En esta pasada se
  corrigieron 5 pistas que regalaban la respuesta y varios distractores poco plausibles o defendibles.
- Sin migración, sin cambio de esquema (sigue en 11), sin telemetría, sin dependencias nuevas.

## 5. Hallazgos pendientes, riesgos y tareas diferidas

Cada una es una tarea **separada**, no mezclada con los PR actuales.

### T1 — Regla de calidad: respuesta correcta repetida dentro de una lección (recomendada)
- **Hallazgo:** nada detecta una pregunta que no corresponde a su respuesta; así se coló el defecto de §4.1.
- **Propuesta:** en el validador, `AVISO` (o `ERROR`) si dos `elegir` de una misma lección tienen idéntico texto de
  opción correcta.
- **Evidencia [EJECUTADO, script descartable]:** sobre `prod` marca exactamente 5 pasos (los defectos corregidos), en los
  otros ocho cursos 0 falsos positivos, y sobre la candidata 0.
- **Riesgo:** bajo (es una regla de herramienta, no del motor). Toca `tortuscript/validacion.py`.
- **Tests propuestos:** un caso sintético con repetición (debe avisar), uno sin repetición (no avisa) y el curso real
  (0 hallazgos).

### T2 — Variedad de tipos de paso en `alfabetizacion-digital` (bloqueada)
- **Hallazgo:** el curso practica solo con `elegir` (45 pasos).
- **Bloqueo verificado [EJECUTADO]:** `validar_curso` rechaza prosa en `ordenar` («en el orden correcto no corre»),
  `completar` («completado con la respuesta, no corre») y `predecir` («el código no corre»); esos tipos exigen código
  ejecutable. El curso no contiene código.
- **Opciones:** (a) un tipo o modo nuevo de ordenar/predecir sin ejecución, lo que cambia validador y motor y
  probablemente necesita una ADR; (b) introducir fragmentos reales de TortuScript, lo que adelanta contenido al nivel 0
  y choca con la regla «no exigir lo no enseñado». No se implementa ninguna sin decisión.
- **Riesgo:** alto si se toca el evaluador (el contrato lo prohíbe como atajo pedagógico).

### T3 — Avisos del validador en `primeros-pasos` (reclasificados: no son defecto)
Los dos `ordenar` (`dos-variables` y `tabla-del-2`) avisan que otro orden da la misma salida; sus consignas ya lo
declaran y el motor acepta órdenes equivalentes. **No requieren cambio.** Riesgo de tocarlos: innecesario sobre un curso
con claves históricas.

### T4 — Matriz de migración de versiones de progreso (recomendada)
- **Hallazgo:** hay fixtures v2–v8 dispersos, sin un test que recorra v1 a v11 y compare qué se conserva.
- **Evidencia ad hoc [EJECUTADO, fuera de la suite]:** `_migrar` sobre perfiles sintéticos v1, v2, v3, v5, v8 y v10
  devuelve versión 11, completa todas las claves y conserva XP, ejercicios, racha, logros, repaso y lecciones.
- **Propuesta:** test parametrizado por versión con ese mismo contrato. Riesgo bajo; solo test.

### T5 — Cobertura débil del repaso
`POR_SESION = 6` no lo referencia ningún test. Propuesta: un test que fije el valor por defecto de `practica.elegir`.

### T6 — Redundancia semántica residual
`navegador` 2–3, `servidor` 2–3 y `lenguaje` 1–3 preguntan lo mismo con otras palabras. Requiere diseño pedagógico
(un ángulo distinto con el mismo tipo `elegir`, p. ej. escenarios), no es corrección de errores.

### 5-bis. Backlog de segunda tanda (origen: PR #24, fuera de esta candidata)

El #24 es **inspección estática**. Contrasté sus cuatro hallazgos ejecutando casos mínimos sobre `prod` (solo lectura;
scripts descartables, sin tocar el repo). Es evidencia puntual, no una suite:

| Hallazgo del #24 | Prioridad | Resultado de mi comprobación [EJECUTADO] | Acción |
|---|---|---|---|
| Registros internos dañados (`lecciones[id].pasos` con clave no entera) | Alta | **Reproducido**: `practica.candidatos` lanza `ValueError: invalid literal for int()` sobre un perfil que pasa `_migrar`. | Primero tests que fijen la política (descartar el registro o normalizar en la migración), luego el cambio |
| Registros internos dañados (`repaso`) | Alta | **Reproducido en dos de cuatro casos**: `proximo` inválido → `ValueError: Invalid isoformat string`; tarjeta que no es dict → `AttributeError`. Con `caja` no entera o fuera de rango **no** hay excepción (`candidatos` y `elegir` devuelven resultado) | Igual que arriba; definir qué hace con `caja` fuera de rango |
| XP guardado de un ejercicio puede retroceder | Media (invariante) | **Reproducido solo con entrada artificial**: `(2★, 20 XP)` y luego `(3★, 10 XP)` deja el `xp` almacenado en 10 y el total en 20 (no baja). La secuencia siguiente `(3★, 30 XP)` no concede XP extra (no hay mejora de estrellas). No se demostró duplicación de XP. La tabla de premios actual hace improbable el caso | Test del invariante «el XP histórico no retrocede»; decidir y documentar la política antes de cambiar código |
| Matriz de migración por versión | Media | Ya propuesta como **T4** (mi evidencia ad hoc coincide) | Trabajo separado con fixtures |
| Límite por defecto de 6 tarjetas | Baja | Ya propuesto como **T5**: ningún test referencia `POR_SESION` | Test directo llamando a `practica.elegir(...)` sin `cantidad` |

**Alcance de la segunda tanda:** ninguna de estas correcciones toca contenido ni depende de la ADR-052, pero sí cambia
`progreso.py`/`practica.py`; por eso van con tests primero, en ramas propias desde `prod`, y con su propia validación.
Las dos primeras son robustez ante archivos de progreso editados a mano o dañados que siguen siendo JSON válido, un
caso distinto del JSON corrupto que ya está cubierto.

### Riesgos residuales del lote actual
1. Sin recorrido en navegador real: el sustituto HTTP no valida DOM ni JS de página (los tests JS de la suite sí corren).
2. No hay medición con alumnos: se corrigieron defectos objetivos, no se demuestra mejora de aprendizaje.
3. El lote toca contenido **gratuito** (Alfabetización completa es parte de las 19 unidades gratuitas, ADR-050): es el
   curso que primero ven las familias, de ahí el cuidado en la revisión.
4. P2/P3 siguen sin implementarse: la ADR-052 continúa en `Propuesta`.

## 6. Limitaciones de la validación
- Playwright ausente → [NO VERIFICADO] el recorrido de navegador.
- La suite completa se corrió una vez sobre la combinación, no por rama.
- La matriz y la revisión de ChatGPT son estáticas; se contrastaron con el cuerpo de los tests (§7) pero no se editaron.

## 7. Contradicciones entre documentos y su resolución

| Afirmación (fuente) | Hallazgo | Resolución |
|---|---|---|
| Informe P0 inicial: «cuatro preguntas con dos opciones» | Eran **seis** (`json` 1–2, `git` 1–2, `github` 1–2) | Corregido en el informe P0 |
| Informe P0 inicial: «7 lecciones» con paso 3 incoherente | Eran **5 pasos en 5 lecciones** con respuesta repetida, más `integracion` 3 | Corregido |
| Informe P0 inicial: los 30 históricos «protegidos por los tests existentes» | El test solo comprueba cantidad, niveles, 2 soluciones y la lección del 29 | Reformulado «parcial» y cerrado con #23 |
| Matriz #18 §1.1: la brecha de los 30 ejercicios (sin tests) | Confirmada por lectura del cuerpo del test | Cubierta por #23 |
| Matriz #18: `test_a_lo_sumo_dos_por_leccion…` «protege el límite de sesión del repaso» | Comprueba 6 elegidas con ≤2 por lección; `POR_SESION` no aparece en ningún test | Anotado como parcial (T5) |
| Matriz #18, fila «Progreso y perfiles antiguos» cita `test_migracion_progreso.py` | Ese archivo prueba importación de progreso local a una cuenta, no migración de esquema | Anotado; propuesta T4 |
| Matriz #18: ejecutar `python -m unittest tests.test_contenido tests.test_leccion … tests.test_camino` | `tests.test_camino` da `ModuleNotFoundError: fixtures_cuenta` con ese formato (también en `prod` limpio) | Documentado: usar `discover -s tests [-p test_x.py]` |
| Matriz #18 y revisión: «inspección estática, no ejecutada» | Coherente con mi informe; sus nombres de tests existen todos | Sin contradicción |
| ADR-052 en `Propuesta` | Confirmada; ninguna parte del lote depende de ella | Sin cambios |

Sugerencia para ChatGPT (no aplicada para no pisar su rama): ajustar en la matriz el comando de ejecución, la fila de
migración y la de límite de sesión, y marcar la brecha de los 30 ejercicios como cubierta por #23 una vez integrado.

## 8. Orden recomendado de integración y justificación

1. **#19** (test del 409): independiente, devuelve la suite a verde; sin él la validación posterior mostraría un fallo
   ajeno.
2. **#23** (identidad de ejercicios): solo tests; protege el contrato antes de integrar cambios de contenido.
3. **#20** (contenido): el único cambio con efecto visible para el alumno; entra con la protección ya activa.
4. **#18** (matriz de ChatGPT), **cuando ChatGPT lo marque como listo**: documentación; conviene antes que #21 para
   que el informe lo cite ya integrado.
5. **#21** (auditoría e informe): al final, para que describa lo que realmente quedó integrado.

Integrar uno por uno con `merge` revisable y repetir `discover -s tests` + validador tras el último. Reversión: cada PR
es revertible por separado (`git revert -m 1 <merge>`) porque no se solapan.

## 8-bis. Qué se validó y cuándo

| Estado de la candidata | Qué se ejecutó |
|---|---|
| `4e131d8` (cinco merges, sin este informe) | **Suite completa** (1017 tests, OK), validador, recorrido HTTP, comparación estructural de cursos |
| `15f80c5` (+ informe y corrección de §4.2, solo `docs/audits/`) | `test_coherencia_repo` (8, OK), `test_contenido` OK, validador exit 0. **La suite completa no se repitió**: la diferencia con `4e131d8` es únicamente documentación |
| Candidata tras las últimas ediciones de esta sección | Se repite la misma validación rápida que en `15f80c5` (ver §10) |

Cualquier cambio posterior que toque código, contenido o tests obliga a repetir la suite completa.

## 9. Condiciones que todavía impiden dar el visto bueno
1. **Autorización expresa de Marcos** para fusionar a `prod`.
2. **PR #18 en borrador:** hasta que ChatGPT lo marque listo, la puerta del documento de coordinación no se cumple.
3. **Recorrido en navegador sin verificar** (Playwright ausente): decidir si se acepta el sustituto HTTP o se instala
   Playwright (dependencia opcional, no está en `requirements.txt`) para correr `jugar_cursos.py alfabetizacion-digital`.
4. **Revisión humana del texto del #20:** la revisión pedagógica fue mía; conviene que Marcos o quien enseñe valide
   el vocabulario y los distractores antes de publicar.
5. **Decisión sobre el #24:** queda fuera; mantenerlo abierto como auditoría complementaria (§5-bis).
6. **Índice de documentación:** `docs/ROADMAPS.md` aún no enlaza la auditoría P0 ni este informe; añadirlo tras
   integrar #18 para no generar conflicto.

## 10. Trazabilidad
- Ramas y PR: #19, #20, #21, #23 (míos), #18 (ChatGPT, borrador). Ninguno fusionado.
- `prod` sigue en `2ac6b2a`; `main` sigue en `717d621`. Ninguna rama fue borrada.
- Candidata: `4e131d8` con suite completa; ramas posteriores solo suman documentación (§8-bis). El #24 no está en la candidata.

## 11. Integración realizada (15/10/2026)

Con autorización expresa de Marcos, en este orden y con `merge` revisable (`gh pr merge --merge`):

| Orden | PR | Merge en `prod` |
|---|---|---|
| 1 | #19 test del 409 | `b8fc40c` |
| 2 | #23 identidad de los 30 ejercicios | `9fb0ecc` |
| 3 | #20 contenido de alfabetización digital | `f692900` |
| 4 | #18 matriz y revisión de ChatGPT (sacado de borrador tras revisarlo) | `91b5732` |
| 5 | #21 esta auditoría e informes | ver `git log --first-parent prod` |

El #24 **no** se integró (decisión de Marcos): sigue abierto como auditoría complementaria; su backlog está en §5-bis.

### Condiciones de §9 resueltas antes de integrar
- **Autorización de Marcos:** otorgada.
- **Recorrido en navegador real [EJECUTADO]:** Playwright se instaló en un entorno aparte, fuera del proyecto (el repo no
  cambió). Con `servidor_de_prueba.py --todo-desbloqueado` y `jugar_cursos.py`:
  `alfabetizacion-digital`: 16 lecciones, 61 pasos, **sin errores de consola**; los nueve cursos: **108/108 lecciones, 541
  pasos, XP 4520, sin errores de consola**. Se corrió sobre la candidata `b4d75cf`, cuyo contenido es el integrado.
- **Revisión humana del texto del #20:** Marcos autorizó la integración conociendo el contenido; la revisión pedagógica
  paso a paso fue la descrita en §4.
- **Índice de documentación:** `docs/ROADMAPS.md` ahora enlaza la auditoría P0 y este informe.

### Hallazgo durante la integración
Existe la rama `test/proteger-identidad-ejercicios-historicos` (commit `6cf738c`, 14/10, sin PR), anterior al #23. Contiene
**un solo test con los mismos 30 pares** (comparados uno por uno: idénticos) y confirma de forma independiente la
fotografía. Está **redundante** con el #23 ya integrado y entraría en conflicto en `tests/test_contenido.py`. No se
fusionó ni se borró (no es una rama integrada); queda a decisión de Marcos.

### Verificación posterior a la integración
Ver §12.

## 12. Verificación de `prod` tras la integración

Se ejecutó sobre el árbol de la rama `docs/auditoria-dinamica-pedagogica` en `d9960b6`, que contiene `prod` con los PR #19,
#23, #20 y #18 ya integrados y suma solo documentación (`CHANGELOG.md`, `docs/ROADMAPS.md`, `docs/audits/`). Al fusionar
el #21 el árbol de `prod` es ese mismo, salvo esta sección y la corrección de referencias, también solo documentación.

| Comando | Resultado **[EJECUTADO]** |
|---|---|
| `python -m unittest discover -s tests` | 1017 tests, **OK**, 0 fallos, 2 omitidos (Job Object de Windows), ≈270 s |
| `python herramientas/validar_contenido.py` | exit 0, 0 errores, 2 avisos informativos en `primeros-pasos` (T3) |
| Contrato `curriculum-v1.json` | «está al día» |
| Recorrido HTTP de `alfabetizacion-digital` | 16 lecciones, 45 correctas aceptadas, 90 incorrectas rechazadas con su pista |
| Navegador real (Playwright, sobre la candidata `b4d75cf`, mismo contenido) | 108/108 lecciones, 541 pasos, sin errores de consola |

Fallos preexistentes: el único conocido (test del 409) quedó corregido por el #19. Regresiones introducidas: ninguna.

## 13. Preparación de la segunda tanda

Ramas por crear desde `prod` (una por unidad, tests primero, sin tocar contenido ni depender de la ADR-052). Ver §5-bis
para la evidencia de cada hallazgo.

| Rama | Contenido | Tipo de cambio |
|---|---|---|
| `test/robustez-registros-progreso` | Tests de `practica.candidatos` con `pasos` de clave no entera y tarjetas de `repaso` con `proximo` inválido o no-dict; fijan la política antes de cambiar código | Solo tests (algunos fallarán hasta el fix) |
| `fix/saneamiento-registros-progreso` | Saneamiento determinista: descartar solo el registro dañado y conservar los válidos hermanos | Código (`progreso.py`/`practica.py`) |
| `test/xp-ejercicio-no-retrocede` | Invariante: el XP almacenado de un ejercicio no baja; documentar la política (máximo por campo o rechazo de combinaciones incoherentes) | Test; el fix solo si se decide la política |
| `test/limite-repaso-por-defecto` | `practica.elegir(...)` sin `cantidad` devuelve como máximo `POR_SESION` | Solo test |
| `test/migracion-por-version` | Fixture por versión de esquema (v1 a v10) + idempotencia de `_migrar` | Solo test |
| `feature/regla-respuesta-repetida` (T1) | Aviso del validador si dos `elegir` de una lección comparten respuesta correcta | Código de herramienta + tests |

Orden sugerido: limite-repaso (trivial) → robustez (tests) → saneamiento (fix) → xp → migracion-por-version → T1. El #24 queda
abierto como referencia de ese trabajo. No se crearon estas ramas todavía: esperan la orden de Marcos.
