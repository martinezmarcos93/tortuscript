# Revisión independiente de regresiones de contratos — 15/10/2026

- **Base revisada:** `prod`, SHA `2ac6b2adeefff71465379bae4111cdce5e2a4dd4`.
- **Método:** inspección estática de `tortuscript/leccion.py`, `evaluacion.py`, `progreso.py`, `practica.py` y sus pruebas.
- **Estado:** hallazgos y pruebas propuestas; **no se ejecutó código ni la suite** en esta revisión.
- **Alcance:** revisión complementaria a la matriz pedagógica; no modifica lógica de producción ni el esquema.

## Hallazgos priorizados

### P1 — La migración tolera tipos incorrectos en campos superiores, pero no sanea registros internos

**Evidencia estática.** `progreso._migrar` asegura que algunos campos de primer nivel sean diccionarios/listas y completa claves de configuración faltantes. No valida de forma recursiva la estructura ni los tipos de cada registro. Por su parte, `practica.candidatos` convierte cada clave de paso con `int(indice_s)` sin capturar `ValueError`.

**Riesgo.** Un JSON sintácticamente válido con `lecciones[id].pasos` conteniendo una clave que no sea un índice entero puede pasar la normalización superior y provocar una excepción al construir la sesión de repaso. De forma similar, registros internos de `repaso` con tipos inesperados pueden llegar a operaciones aritméticas o de fecha sin validación previa. Esto es distinto de un archivo JSON sintácticamente corrupto, cuya recuperación ya tiene pruebas.

**Pruebas propuestas.**
- Crear un perfil sintéticamente válido con `lecciones: {"l": {"pasos": {"no-es-indice": {...}}}}`; llamar a `practica.candidatos` y fijar el comportamiento esperado: descartar el registro inválido con seguridad o normalizarlo durante la migración, sin perder los registros válidos del mismo perfil.
- Añadir casos para `repaso` con `caja` no entera/fuera de rango y `proximo` inválido. Definir explícitamente si se descarta solo la tarjeta dañada o se normaliza a caja 0/1.
- Verificar que un registro válido hermano siga apareciendo en la sesión tras aislar el dañado.

**Criterio de aceptación.** Un dato interno inválido no debe bloquear toda la sesión ni eliminar progreso válido; el comportamiento de recuperación debe ser determinista y estar documentado.

### P1 — La actualización de un ejercicio puede reducir el XP guardado cuando mejora la puntuación

**Evidencia estática.** En `progreso.registrar_ejercicio`, cuando `estrellas > estrellas_previas`, se calcula la diferencia `xp_ganado - xp_previo` y se guarda el nuevo `xp_ganado`. `sumar_xp` ignora cantidades no positivas, pero el registro se reemplaza igualmente. El contrato esperado es que repetir un ejercicio no quite XP y que una mejora solo agregue la diferencia.

**Riesgo.** Si una futura modificación de premios, una migración o una llamada inconsistente produce más estrellas con menos XP, el total no baja en ese momento, pero el valor almacenado sí. Una mejora posterior podría entonces volver a conceder XP que ya se había ganado. La tabla actual de premios hace poco probable el caso en el flujo normal, pero el invariante no está protegido por el registro.

**Pruebas propuestas.**
- Registrar un ejercicio con `(estrellas=2, xp=20)` y luego un resultado sintético `(estrellas=3, xp=10)`; comprobar que el XP persistido y el total no retrocedan y que una mejora posterior no duplique XP.
- Definir si el contrato exige rechazar combinaciones incoherentes de estrellas/XP o conservar por separado el máximo de cada campo. No elegir una política silenciosamente: documentarla junto al modelo de premios.
- Mantener pruebas de los casos normales de mejora y repetición para asegurar que el cambio no altera los premios vigentes.

**Criterio de aceptación.** Ninguna actualización puede reducir el XP histórico registrado ni crear XP duplicado en mejoras posteriores.

### P2 — Las pruebas de migración no cubren sistemáticamente todas las versiones y los invariantes semánticos

**Evidencia estática.** Los tests existentes prueban casos puntuales (por ejemplo, progreso v2 y v8 en el motor de lecciones, v5 en repaso y JSON válido con algunos tipos superiores dañados). No hay una matriz versionada que pruebe cada versión soportada hasta `VERSION_ESQUEMA` contra los mismos invariantes de conservación.

**Riesgo.** Que un perfil termine con la versión de esquema actual no demuestra por sí solo que conserve XP, ejercicios históricos, lecciones, racha, logros, repaso, ajustes y aislamiento por perfil. Una migración puede rellenar campos y cambiar la versión, pero alterar silenciosamente un dato anidado.

**Pruebas propuestas.**
- Mantener fixtures representativos por cada versión histórica realmente soportada, no solo por unas pocas versiones.
- Ejecutar cada fixture a través de la migración real y comprobar: versión final; XP total y diario; índices de ejercicios; pasos por lección; racha/logros; repaso; configuración; ausencia de mezcla entre perfiles.
- Comprobar idempotencia: migrar dos veces el mismo perfil no debe cambiar el resultado de la primera migración.
- Documentar explícitamente las versiones no soportadas y el fallback aplicado.

**Criterio de aceptación.** Cada versión soportada tiene un fixture y aserciones de preservación de datos; no basta con comprobar que existen claves predeterminadas.

### P2 — El límite por defecto de seis tarjetas de repaso no está fijado directamente por una prueba

**Evidencia estática.** `practica.POR_SESION = 6` es el argumento por defecto de `practica.elegir`, pero las pruebas de variedad llaman a `elegir(..., cantidad=6)`. Ese test comprueba el resultado con seis solicitado explícitamente; no fallaría necesariamente si cambiara el valor por defecto.

**Riesgo.** Una modificación accidental del tamaño de sesión puede pasar la suite, aunque sea parte del contrato de producto.

**Prueba propuesta.** Con más de seis tarjetas vencidas, invocar `practica.elegir(progreso, cursos, hoy)` sin argumento `cantidad` y comprobar que devuelve como máximo seis; mantener separado el test que permite completar una sesión cuando hay pocas lecciones elegibles.

**Criterio de aceptación.** El límite por defecto se verifica sin repetir el valor como argumento en la llamada bajo prueba.

## Contratos revisados que sí tienen evidencia parcial

- **No filtrar respuestas correctas al cliente:** existe una prueba de proyección pública del paso que comprueba que campos sensibles como `correcta`, `respuesta` y `solucion` no aparecen. Conviene mantenerla al modificar los tipos de paso.
- **Equivalencia de respuestas en `completar` y `ordenar`:** hay pruebas de alternativas que producen el mismo resultado/dibujo. No sustituirlas por una comparación textual más estricta.
- **XP al repetir pasos de lección:** existe una prueba de no duplicación y mejora. El hallazgo P1 anterior corresponde al registro separado de ejercicios, no invalida esa cobertura.
- **Repaso espaciado:** hay pruebas de intervalos, error que vuelve a caja 1, independencia de tarjetas y tope de XP diario. La prueba del límite por defecto de sesión sigue siendo una brecha distinta.
- **Normalización de salida:** hay pruebas para espacios, puntuación, mayúsculas, tildes y separación de líneas. Cualquier cambio debe preservar esos casos y añadir casos nuevos según el lenguaje de salida.

## Orden recomendado

1. Agregar pruebas de robustez de registros anidados y decidir la política de saneamiento antes de cambiar el comportamiento.
2. Fijar el invariante de no regresión del XP persistido para ejercicios.
3. Añadir el test directo del límite por defecto de repaso.
4. Diseñar la matriz de migración por versión como trabajo separado, con fixtures verificables.
5. Ejecutar las pruebas focalizadas y luego la suite completa en la rama de integración; registrar resultados reales y distinguir fallos preexistentes.

## Límites de esta revisión

Este documento no afirma que los casos propuestos fallen hoy en ejecución: las observaciones derivan de lectura estática del código. Tampoco propone implementar P2/P3 del modelo pedagógico adaptativo; ADR-052 continúa en estado **Propuesta** y debe aceptarse antes de implementar arquitectura dependiente de ella.
