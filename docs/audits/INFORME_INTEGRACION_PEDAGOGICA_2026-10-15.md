# Informe de integración — primer ciclo pedagógico (preparado, **no ejecutado**)

**Fecha:** 15/10/2026
**Estado:** la integración a `prod` **no se hizo** y espera la autorización expresa de Marcos. `main` no se tocó.
**Base:** `origin/prod` en `2ac6b2a`.
**Combinación candidata:** rama `candidata/pedagogia-2026-10-15` (fusiona los cinco cambios de §1 sobre `prod` con
`--no-ff`, sin conflictos). Existe solo para validar; no es una rama de integración.

> Convención: **[EJECUTADO]** salida real obtenida; **[ESTÁTICO]** lectura sin ejecutar; **[NO VERIFICADO]** no
> comprobable en este entorno.

## 1. Estado y alcance de cada PR

| PR | Rama | Último commit | Alcance | Archivos |
|---|---|---|---|---|
| #19 | `fix/test-409-contrato-obsoleto` | `acea87a` | Alinea un test obsoleto con el contrato del #15 (el 409 se conserva en cola y no se da por borrado ni se reintenta). Solo test. | `tests/test_federacion_respuestas.py` |
| #20 | `feature/alfabetizacion-preguntas-coherentes` | `8c0bca1` | Corrige 19 pasos `elegir` de `alfabetizacion-digital` (preguntas incoherentes, pistas, distractores, 6 preguntas de 2 opciones). | `contenido/cursos/alfabetizacion-digital.json` |
| #23 | `test/identidad-ejercicios-historicos` | `e6b3b7a` | Fija los 30 pares `(leccion_id, paso)` de los `escribir` históricos de `primeros-pasos` (2 tests nuevos). | `tests/test_contenido.py` |
| #21 | `docs/auditoria-dinamica-pedagogica` | `deac677` (+ ajuste de referencia) | Auditoría P0 (segunda pasada), este informe y entradas del CHANGELOG. | `docs/audits/…`, `CHANGELOG.md` |
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

### Combinación candidata (`4e131d8` + este informe, solo documentación)
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

## 9. Condiciones que todavía impiden dar el visto bueno
1. **Autorización expresa de Marcos** para fusionar a `prod`.
2. **PR #18 en borrador:** hasta que ChatGPT lo marque listo, la puerta del documento de coordinación no se cumple.
3. **Recorrido en navegador sin verificar** (Playwright ausente): decidir si se acepta el sustituto HTTP o se instala
   Playwright (dependencia opcional, no está en `requirements.txt`) para correr `jugar_cursos.py alfabetizacion-digital`.
4. **Revisión humana del texto del #20:** la revisión pedagógica fue mía; conviene que Marcos o quien enseñe valide
   el vocabulario y los distractores antes de publicar.
5. **Índice de documentación:** `docs/ROADMAPS.md` aún no enlaza la auditoría P0 ni este informe; añadirlo tras
   integrar #18 para no generar conflicto.

## 10. Trazabilidad
- Ramas y PR: #19, #20, #21, #23 (míos), #18 (ChatGPT, borrador). Ninguno fusionado.
- `prod` sigue en `2ac6b2a`; `main` sigue en `717d621`. Ninguna rama fue borrada.
- Candidata validada: `4e131d8` (suite completa). Las ediciones posteriores de la candidata son solo este informe y
  la corrección de §4.2 del informe P0; se revalidaron los tests rápidos relacionados (§3).
