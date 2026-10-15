# Matriz de cobertura y regresión — pedagogía adaptativa

**Base analizada:** rama `prod`, inspección estática del 14/10/2026.  
**Estado:** matriz de revisión; no afirma que los tests hayan sido ejecutados.  
**Responsable de validación final:** Claude Code.  
**Objetivo:** convertir los riesgos pedagógicos y de compatibilidad en controles verificables antes de integrar cambios.

## 1. Cobertura ya identificada en el repositorio

Esta tabla se basa en nombres y contenido inspeccionado de los tests existentes. Que exista un test relacionado no demuestra que cubra todos los casos de una fila: revisar el cuerpo del test al usarlo como evidencia de aceptación.

| Contrato | Cobertura existente identificada | Uso durante esta iniciativa |
|---|---|---|
| Estructura, prerrequisitos y calidad de cursos | `tests/test_contenido.py`, `tests/test_leccion.py`, `tests/test_camino.py` | Ejecutar tras cualquier cambio de contenido; agregar pruebas de regresión para nuevos invariantes |
| Seis tipos de paso y validez de ejercicios | `tests/test_contenido.py`, `tests/test_leccion.py` | Mantener el formato y el comportamiento de los ejercicios existentes |
| IDs únicos y orden de ejercicios históricos | `tests/test_contenido.py` | Exigir explícitamente que los 30 ejercicios históricos `escribir` de `primeros-pasos` permanezcan en orden |
| Respuestas, equivalencias y pistas | `tests/test_leccion.py`, `tests/test_evaluacion.py` | Evitar que la secuenciación o feedback cambien el criterio de corrección |
| XP, intentos y revelación de respuesta | `tests/test_leccion.py`, `tests/test_camino.py`, `tests/test_gamificacion.py` | Verificar que las mejoras no alteren XP, perfección o recompensas por efecto colateral |
| Progreso y perfiles antiguos | `tests/test_progreso.py`, `tests/test_migracion_progreso.py`, `tests/test_progreso_contrato.py`, `tests/test_progreso_childprofile.py` | Probar compatibilidad, aislamiento por perfil y persistencia de datos históricos |
| Estado del camino y desbloqueos | `tests/test_camino.py`, `tests/test_leccion.py`, `tests/test_ciclo_alumno.py` | Comprobar prerrequisitos, lecciones salteadas y recorrido completo |
| Repaso espaciado e intercalado | `tests/test_practica.py`, `tests/test_referencia_repaso.py`, parte de `tests/test_camino.py` | Preservar intervalos, elegibilidad, límites por sesión y respuesta ante error |
| Integración del recorrido real | `tests/test_ciclo_alumno.py`, `tests/test_web.py`, `tests/test_web_v1.py` | Validar el flujo entre API, lección, progreso y UI |
| JavaScript | `tests/test_js.py` y `tests/js/*.test.mjs` | Ejecutar cuando Node esté disponible; registrar si se omite |
| Coherencia documental y archivos huérfanos | `tests/test_coherencia_repo.py` | Ejecutar después de agregar o mover documentación, tests o herramientas |


## 1.1. Evidencia concreta por nombre de test

Se contrastaron los nombres de los métodos de prueba en los siete archivos principales de la matriz. Esta comprobación es estática: confirma que existen esos casos nombrados, no que hayan pasado en la revisión actual.

| Invariante | Test existente identificado | Qué demuestra si pasa |
|---|---|---|
| Los 30 ejercicios históricos mantienen el orden | `tests/test_contenido.py::test_el_curso_principal_conserva_sus_30_ejercicios_en_orden` | Protege explícitamente la secuencia histórica del curso principal |
| Los seis tipos de paso siguen presentes | `tests/test_contenido.py::test_el_curso_usa_los_6_tipos_de_paso` | Evita perder cobertura de un tipo de ejercicio |
| IDs de lección únicos | `tests/test_contenido.py::test_ids_de_leccion_unicos_entre_cursos` y `test_ids_repetidos_y_seccion_vacia` | Detecta colisiones y estructuras vacías/duplicadas contempladas por el validador |
| Una palabra no se usa antes de enseñarse | `tests/test_contenido.py::test_usar_una_palabra_antes_de_ensenarla` | Comprueba una regla de secuenciación léxica |
| El evaluador acepta soluciones semánticamente equivalentes | `tests/test_leccion.py::test_completar_acepta_otra_solucion_con_la_misma_salida`, `test_ordenar_acepta_otro_orden_que_muestra_lo_mismo` | Evita restringir indebidamente respuestas equivalentes |
| XP no se duplica al repetir | `tests/test_leccion.py::test_repetir_no_da_xp_doble_pero_si_mejora` | Protege la regla de XP en repetición |
| El progreso antiguo sigue siendo legible | `tests/test_leccion.py::test_esta_completada_compatibilidad_con_progreso_viejo`, `test_progreso_viejo_sin_lecciones_se_migra`, `test_un_progreso_v8_gana_el_campo_nuevo` | Cubre compatibilidad con formas históricas específicas |
| Recuperación de progreso corrupto | `tests/test_progreso.py::test_json_corrupto_no_se_pierde_y_se_recupera_del_bak`, `test_json_corrupto_sin_bak_arranca_de_cero_sin_borrar_el_danado` | Comprueba recuperación sin destruir el archivo dañado |
| Aislamiento de perfiles en persistencia | `tests/test_progreso.py::test_ventana_abierta_no_mezcla_perfiles` | Protege contra mezcla de progreso entre perfiles |
| Intervalos, error y límite de sesión del repaso | `tests/test_practica.py::test_cajas_e_intervalos`, `test_un_error_vuelve_a_la_caja_1_y_toca_mañana`, `test_a_lo_sumo_dos_por_leccion_si_hay_variedad` | Protege reglas existentes de repaso espaciado |
| Recorrido completo de dos perfiles | `tests/test_ciclo_alumno.py::test_recorrido_completo_con_dos_perfiles` | Cubre un flujo de integración de extremo a extremo con aislamiento |

**Brecha concreta detectada al leer las aserciones:** `test_el_curso_principal_conserva_sus_30_ejercicios_en_orden` comprueba la cantidad total, la secuencia de niveles, la solución de los índices 0 y 3 y la lección del índice 29; no compara la identidad de los 30 ejercicios uno por uno. Por eso, el test actual puede detectar ciertos desplazamientos, pero no demuestra por sí solo que cada ejercicio conserve exactamente su posición histórica. Se recomienda reforzarlo con una huella/fixture explícito de los 30 pares `(leccion_id, paso_id)` o con una lista de IDs estable, después de confirmar cuál es la identidad persistida real.

**Cobertura que sigue pendiente de confirmar:** que los tests existentes cubran todos los casos límite de la iniciativa, y que la suite completa pase sobre la combinación final. La existencia de un test con nombre pertinente no reemplaza la lectura de sus aserciones ni su ejecución.

## 2. Casos de regresión adicionales recomendados

Estos casos son objetivos de prueba; no se afirma que todos estén ausentes. Antes de agregar uno, buscar cobertura equivalente para evitar duplicaciones.

### P0 — baseline y compatibilidad

- [ ] Ejecutar `python -m unittest discover tests` y registrar la salida completa y el resultado.
- [ ] Ejecutar `python herramientas/validar_contenido.py` y clasificar cada error/aviso.
- [ ] Ejecutar `python -m unittest tests.test_contenido tests.test_leccion tests.test_progreso tests.test_practica tests.test_camino tests.test_ciclo_alumno`.
- [ ] Ejecutar pruebas JS y UI disponibles; anotar explícitamente qué herramientas faltan.
- [ ] Capturar una instantánea de los IDs de cursos/lecciones y de las posiciones 0–29 de los pasos `escribir` en `primeros-pasos`.
- [ ] Confirmar que los fallos observados antes de cambiar código quedan identificados como baseline, no atribuidos a cambios posteriores.

### P1 — contenido y secuenciación

- [ ] Cada concepto que se declara introducido tiene una explicación previa o una introducción inequívoca.
- [ ] Los ejercicios de práctica no exigen una palabra o construcción todavía no enseñada, salvo que la propia consigna la presente.
- [ ] Los prerrequisitos de lección/curso se cumplen en el recorrido nuevo y no hay bucles o bloqueos accidentales.
- [ ] La variedad de ejercicio cambia la operación cognitiva (por ejemplo, reconocer frente a predecir o producir), no solo los nombres o el texto superficial.
- [ ] Las nuevas secuencias no duplican IDs ni alteran claves usadas por el progreso.
- [ ] El orden y la cantidad de los ejercicios históricos `escribir` de `primeros-pasos` siguen intactos.
- [ ] Los ejercicios añadidos son deterministas donde corresponda y sus respuestas correctas son verificables.
- [ ] Un perfil con progreso previo puede continuar la lección y abrir el mismo contenido que antes, salvo una corrección deliberada y documentada de un bug.
- [ ] Una lección repetida no duplica XP ni cambia el estado de perfección de manera inesperada.
- [ ] Los cursos afectados se recorren con el mecanismo de UI real disponible, no solo con el validador JSON.

### P2 — futuro modelo de dominio, solo tras aceptar ADR-052

- [ ] El estado por concepto se distingue del progreso histórico por lección/paso.
- [ ] Un perfil antiguo sin datos de dominio sigue funcionando mediante valores por defecto.
- [ ] Datos parciales, desconocidos o corruptos no bloquean la lección.
- [ ] Las señales se derivan de hechos comprobables; no se infiere dominio solo del XP, tiempo empleado o finalización.
- [ ] Se prueba exportación/importación y aislamiento por perfil si el nuevo estado entra en el contrato persistido.
- [ ] Una nueva versión de esquema tiene migración, fixture previo y prueba de preservación semántica.
- [ ] El planificador no duplica el evaluador ni altera las reglas de XP.
- [ ] La ausencia de señales provoca un recorrido estándar y reproducible.
- [ ] El estado del modelo no se comparte entre perfiles infantiles.

### P3 — futuro planificador adaptativo, solo tras aceptación y línea de base

- [ ] El planificador conserva el calendario de repaso existente como baseline.
- [ ] La elección de ejercicios es determinista para una misma entrada, salvo aleatoriedad explícita con semilla controlada.
- [ ] No se rompe el límite diario de práctica ni se concentra la sesión en una sola lección cuando hay variedad elegible.
- [ ] Una respuesta correcta asistida se distingue de una respuesta autónoma.
- [ ] Un error reprograma práctica sin castigar al alumno ni borrar avance histórico.
- [ ] La falta de historial, un concepto desconocido o un estado inválido activa el fallback estándar.
- [ ] Ninguna regla adaptativa hace imposible completar el camino curricular.
- [ ] Las pruebas cubren fechas de borde, cambios de mes/año y estados de repaso incompletos.
- [ ] Se documenta cómo desactivar el planificador y volver al comportamiento anterior.

## 3. Qué evidencia permite declarar cada resultado

| Declaración | Evidencia necesaria |
|---|---|
| «El contenido valida» | Salida real del validador sobre el commit examinado |
| «Los tests pasan» | Código de salida real de la suite indicada y resumen reproducible |
| «No hay regresiones de progreso» | Tests de migración/compatibilidad, fixtures históricos y comparación de IDs/posiciones |
| «La UI funciona» | Prueba de integración o recorrido de interfaz ejecutado; no alcanza con tests de funciones puras |
| «La adaptación es segura» | Fallback probado, ausencia de cambios no autorizados al esquema y pruebas de perfiles antiguos |
| «Mejora el aprendizaje» | Evaluación pedagógica con alumnos o evidencia empírica pertinente; los tests técnicos no demuestran eficacia educativa |

## 4. Puerta mínima de integración

Claude Code debe revisar la matriz completa al finalizar ambas ramas. Los controles críticos son:

1. Sin errores del validador de contenido.
2. Suite completa ejecutada y resultados documentados; toda prueba no ejecutada queda explícita.
3. Sin cambios involuntarios en IDs, prerrequisitos o posiciones históricas.
4. Compatibilidad con perfiles existentes y sin pérdida de progreso.
5. Sin cambios arquitectónicos dependientes de una ADR todavía no aceptada.
6. Sin regresiones de XP, feedback, accesibilidad o repaso.
7. Diff final inspeccionado y documentación coherente con el comportamiento real.
8. Validación repetida sobre la combinación final de cambios, no solo sobre cada rama por separado.

Un fallo crítico impide integrar el lote completo. Solo se puede separar una unidad independiente si su aislamiento es real y sus propias pruebas pasan. Cualquier excepción debe quedar documentada en el informe final.

## 5. Límites de esta matriz

La matriz se elaboró mediante inspección estática de archivos de `prod`. No representa una ejecución de tests ni una inspección completa del comportamiento en navegador. Claude Code debe confirmar cada caso contra el cuerpo real de las pruebas y actualizar el documento si encuentra cobertura adicional, contradicciones o cambios de arquitectura ya aceptados.
