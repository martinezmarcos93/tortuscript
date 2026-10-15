# Auditoría dinámica P0 — línea de base ejecutada (segunda pasada)

**Fecha:** 14–15/10/2026
**Base:** `prod` en `2ac6b2a` (código idéntico a `main` en `717d621`; `prod` solo suma documentación).
**Naturaleza:** ejecución real de tests, validador y recorrido HTTP, más lectura del cuerpo de los tests.
Complementa `BASELINE_PEDAGOGIA_ADAPTATIVA_2026-10-14.md` y se contrasta con
`MATRIZ_COBERTURA_REGRESION_PEDAGOGICA.md` y `REVISION_CONTRATOS_CONTENIDO_PROGRESO.md` (rama
`docs/validacion-pedagogica-chatgpt`, PR #18, ambas **estáticas**).

> Convención de este documento: **[EJECUTADO]** = lo corrí y está su salida; **[ESTÁTICO]** = lo concluí leyendo
> código o tests sin ejecutarlo; **[NO VERIFICADO]** = no se pudo comprobar.

## 1. Resultados de ejecución sobre `prod` (sin cambios míos)

| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests` | **[EJECUTADO]** 1015 tests, 1 fallo, 2 omitidos (≈290 s) |
| `python herramientas/validar_contenido.py` | **[EJECUTADO]** 0 errores, 2 avisos (§4.2) |
| `python -m unittest discover -s tests -p "test_contenido.py"` | **[EJECUTADO]** OK |
| `docs/contratos/curriculum-v1.json` | **[EJECUTADO]** la suite informa «está al día» |
| Tests de JavaScript (`tests/test_js.py`, Node v24.20.0) | **[EJECUTADO]** OK; corren dentro de la suite |
| Recorrido en navegador (`herramientas/jugar_cursos.py`) | **[NO VERIFICADO]** Playwright no está instalado |

**Nota sobre comandos.** La matriz sugiere `python -m unittest tests.test_contenido tests.test_leccion …`. Con ese
formato, `tests.test_camino` falla con `ModuleNotFoundError: fixtures_cuenta` (54 errores) **tanto con mis cambios como
sin ellos**: ese módulo auxiliar solo se resuelve con `discover -s tests`. El comando válido es el documentado en el
`CLAUDE.md`: `python -m unittest discover -s tests` (o `-p "test_x.py"` para un archivo).

### Fallo preexistente (reproducido en `prod` limpio)
`test_federacion_respuestas.TestOperaciones.test_un_perfil_de_otra_cuenta_no_se_reintenta`. El PR #15 (`main`) cambió el
contrato del 409 de supresión —se conserva en cola como `conflicto_409` para revisión manual y `solicitar` devuelve
`False`— y quedó este test del PR #12 afirmando el comportamiento anterior. Falla igual en `main`. El PR #19 corrige
**solo el test**; el código de producción (`federacion_operaciones.py`) no cambia (verificado con `git diff`).

## 2. Señales de desempeño que el progreso guarda realmente [ESTÁTICO, leído en `progreso.py`/`practica.py`]

- Paso de lección: `{xp, perfecto, fecha, estrellas?}`. Primer intento / reintentos / respuesta revelada solo se
  distinguen **indirectamente** por el XP (5 / 2 / 0). No se guarda cantidad de reintentos, pistas por paso (salvo
  `estrellas` en los `escribir`) ni hora del intento.
- `repaso`: `{caja, proximo, aciertos, fallos}`; «acierto» = bien al primer intento, sin distinguir ayuda.
  Intervalos 1-2-4-8-16 y regreso a la caja 1 ante error: **[EJECUTADO]** por `test_practica` (§5).
- `ejercicios` (`escribir`): `{estrellas, xp, completado}`, con clave = índice 0..29.
- **Consecuencia para P2:** con estos datos no se distingue reconocimiento / predicción / producción ni el uso de
  pistas por concepto. Un modelo de dominio exige señales nuevas (esquema > 11) y depende de la ADR-052 (Propuesta).
  No se tocó el esquema.
- Descartado como defecto: `correcta: 0` en casi todos los `elegir` **no** es sesgo de posición; `leccion._mezclar`
  baraja las opciones con semilla estable por lección y paso [ESTÁTICO].

## 3. Migración del progreso y perfiles antiguos

- **[ESTÁTICO]** Existen fixtures de progreso v2, v3, v4, v5, v7 y v8 repartidos en `test_leccion`, `test_camino`,
  `test_gamificacion`, `test_practica` y `test_accesibilidad`, cada uno centrado en su propia función. **No hay un test
  sistemático que recorra todas las versiones hasta la 11 y compare qué se conserva.**
- **[EJECUTADO, ad hoc, fuera de la suite]** `progreso._migrar` sobre un perfil sintético con XP, ejercicios, racha,
  logros, repaso y lecciones, declarado como v1, v2, v3, v5, v8 y v10: en todos los casos devuelve `version = 11`, no
  falta ninguna clave de `PROGRESO_INICIAL` y los campos conservados son idénticos. Es evidencia puntual, no una
  garantía versionada.
- `tests/test_migracion_progreso.py` **no** cubre esto: prueba la importación de progreso local a una cuenta
  (ChildProfile), no la migración de esquema. La matriz de ChatGPT lo lista bajo «Progreso y perfiles antiguos»; esa
  fila es válida para aislamiento y recuperación, no para migración de versiones.

## 4. Hallazgos de contenido

### 4.1 `alfabetizacion-digital` (curso gratuito) — corregido en el PR #20
Recuento verificado comparando el JSON de `prod` con el de la rama, paso por paso:

- **61 pasos**, mismos IDs de lección, mismos tipos, mismas posiciones y misma `version` del curso (3) [EJECUTADO].
- **19 pasos modificados** en 13 lecciones; el resto del curso queda byte a byte igual en datos.
- **5 pasos `elegir` repetían como respuesta correcta la del paso anterior bajo otra pregunta** (`programa` 3,
  `navegador` 3, `servidor` 3, `base-datos` 3, `integracion` 2): la pregunta no correspondía a su respuesta. Además
  `integracion` 3 tenía una respuesta que enumeraba todo el curso y no respondía la pregunta.
  *(Una versión previa de este informe decía «7 lecciones»: era un error de recuento.)*
- **6 preguntas con solo dos opciones** (`json` 1 y 2, `git` 1 y 2, `github` 1 y 2). *(Una versión previa decía
  «cuatro»: era un error.)* Ahora tienen tres; no queda ninguna con menos de tres.
- Pistas que pertenecían a otra pregunta (p. ej. en `programa` 2) y pistas que nombraban la respuesta correcta.

Segunda pasada pedagógica sobre mi propio PR: se encontraron y corrigieron pistas que regalaban la opción correcta
(`codigo` 2, `base-datos` 2, `integracion` 3, `lenguaje` 3, `internet` 3), un distractor técnicamente defendible
(«las ignora hasta que alguien las traduzca», por la compilación) y varios distractores poco plausibles.

Verificado por HTTP **[EJECUTADO, script descartable fuera del repo]** con el cliente Flask de `test_camino`: las 16
lecciones se renderizan (200); las 45 respuestas correctas se aceptan; las 90 incorrectas se rechazan devolviendo la
pista propia del paso.

### 4.2 Pendiente (no se hace en esta fase)
- `alfabetizacion-digital` practica solo con `elegir`. Variar tipos exige confirmar que el evaluador acepta texto no
  ejecutable en `ordenar`/`completar`; hasta entonces no se cambian tipos (riesgo en §6 del informe de integración).
- Redundancia semántica que persiste: en `navegador` 2–3, `servidor` 2–3 y `lenguaje` 1–3 se pregunta
  lo mismo con otras palabras; solo se cambió lo incoherente.
- `proyectos` solo usa `escribir`; sin recuperación previa a cada etapa.
- Dos avisos del validador en `primeros-pasos` (pasos `ordenar` de «6. Dos variables» paso 5 y «24. Tabla del 2»
  paso 4: otro orden muestra lo mismo; hay que aceptar ambos). No se tocó `primeros-pasos` por la restricción de
  posiciones 0–29.
- P2/P3: sin cambios funcionales (ADR-052 en Propuesta).

## 5. Qué protege realmente cada invariante (cuerpo de los tests leído)

| Invariante | Estado | Evidencia |
|---|---|---|
| 30 `escribir` históricos de `primeros-pasos` | **Parcial** en `prod`; **protegido** con el PR #23 | `test_el_curso_principal_conserva_sus_30_ejercicios_en_orden` solo comprueba cantidad (30), la secuencia de niveles, la solución de los índices 0 y 3 y la lección del 29. No compara los otros 26 uno por uno. El PR #23 fija los 30 pares `(leccion_id, paso)` (§5.1) |
| IDs de lección únicos entre cursos | Protegido | `test_ids_de_leccion_unicos_entre_cursos` recorre todos los JSON reales |
| El contenido real valida | Protegido | `test_todos_los_cursos_validan_sin_errores` |
| Pista propia en pasos con opciones | Protegido | `test_todos_los_pasos_con_opciones_tienen_pista_propia` |
| Palabra usada antes de enseñarse | Parcial | `test_usar_una_palabra_antes_de_ensenarla` prueba la regla del validador con datos sintéticos; que el contenido real la cumple lo da `test_todos_los_cursos_validan_sin_errores` |
| Pregunta incoherente con su respuesta (defecto de §4.1) | **Sin test** | Nada detecta que una pregunta no corresponda a la opción correcta; solo `test_nivel_0_no_repite_preguntas_dentro_de_una_leccion` (texto idéntico). Propuesta en §6 del informe de integración |
| XP no se duplica al repetir | Parcial | `test_repetir_no_da_xp_doble_pero_si_mejora` cubre `registrar_paso_leccion` con IDs sintéticos y XP 2→5; no recorre una lección real |
| Progreso viejo legible | Parcial | Fixtures v2/v8 en `test_leccion` y otros sueltos (§3); sin matriz de versiones |
| Recuperación de JSON corrupto | Protegido | `.bak` y archivo `corrupto-*` apartado, con aserciones sobre contenido |
| Aislamiento de perfiles al guardar | Protegido (un caso) | `test_ventana_abierta_no_mezcla_perfiles` |
| Repaso: intervalos y retorno a caja 1 | Protegido | `test_cajas_e_intervalos`, `test_un_error_vuelve_a_la_caja_1_y_toca_mañana` |
| Repaso: «máximo seis por sesión» | Parcial | `test_a_lo_sumo_dos_por_leccion_si_hay_variedad` comprueba que `elegir(..., cantidad=6)` devuelve 6 con ≤2 por lección; el valor por defecto `POR_SESION = 6` **no lo referencia ningún test** (`grep` en `tests/`), de modo que cambiarlo no rompería nada. (La matriz lo presenta como protección de «límite de sesión»: es más débil) |
| Recorrido completo con dos perfiles | Protegido | `test_recorrido_completo_con_dos_perfiles` (flujo cuenta → perfiles → progreso aislado) |
| JavaScript | Protegido | `tests/js/*.test.mjs` vía `test_js.py`; Node disponible |
| Recorrido en navegador | **No verificado** | Playwright ausente (ver §1 y §4.1 para el sustituto HTTP) |

### 5.1 Identidad de los ejercicios históricos (base del PR #23)
- **[ESTÁTICO]** La identidad **persistida** es solo el índice 0..29 de `contenido.ejercicios()` (clave
  `progreso["ejercicios"]["N"]`). Lo que ata ese índice a un contenido es el par `(leccion_id, paso)`; `paso` es además la
  clave de `progreso["lecciones"][id]["pasos"]`. No existe un ID de ejercicio propio, y no se inventó ninguno.
- **[EJECUTADO]** La lista de los 30 pares es idéntica en `prod`, en la etiqueta `v1.0.0` y en
  `backup/main-2026-10-03`.
- **[EJECUTADO]** Mutación de control: insertar un paso antes de un `escribir` histórico hace fallar el test nuevo;
  sobre el contenido real pasa. No se usa una huella opaca: la fotografía es una lista legible de pares.

## 6. Limitaciones
- Sin recorrido en navegador real (Playwright ausente); el sustituto es HTTP contra el motor, que no valida DOM ni JS
  de página, aunque los tests JS de la suite sí corren.
- No se midió eficacia pedagógica con alumnos: los cambios corrigen defectos objetivos de coherencia, no demuestran
  mejora de aprendizaje.
- La matriz de ChatGPT es estática; sus afirmaciones se contrastaron aquí con el cuerpo de los tests (§5), no se
  reescribió su documento.
