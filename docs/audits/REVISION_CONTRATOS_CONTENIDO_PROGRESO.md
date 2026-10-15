# Revisión independiente de contratos de contenido y progreso

**Base examinada:** `prod`, commit `2ac6b2adeefff71465379bae4111cdce5e2a4dd4`.  
**Tipo de revisión:** inspección estática de código y documentación.  
**Estado:** hallazgos para revisión; no se ejecutaron pruebas en esta rama.  
**Alcance:** identificar invariantes que cualquier cambio pedagógico debe preservar y controles concretos para la revisión final.

## 1. Contratos confirmados

### Contenido e identidad curricular

- `tortuscript/contenido.py` declara seis tipos de paso: `explicacion`, `elegir`, `completar`, `ordenar`, `predecir` y `escribir`.
- Los cursos son datos JSON. La secuenciación puede cambiar la experiencia del alumno sin que eso justifique reescribir el motor o crear un segundo evaluador.
- `ejercicios(curso_id)` proyecta únicamente los pasos `escribir` a una lista ordenada. En `primeros-pasos`, la posición 0–29 de esa proyección es una clave histórica del progreso.
- Los IDs de lección son referencias persistidas en progreso, logros y prerrequisitos. Renombrarlos puede hacer que el avance previo deje de asociarse a la lección.
- El validador tiene reglas semánticas: por ejemplo, comprueba que palabras de TortuScript se presenten antes de usarse y que la respuesta de ejercicios `predecir` coincida con la ejecución del código. Añadir contenido no consiste solo en producir JSON sintácticamente válido.

### Evaluación

- `tortuscript/evaluacion.py` compara la salida normalizada del alumno con la salida de la solución ejecutada con las mismas entradas y semilla.
- La evaluación incluye contratos específicos para dibujos y laberintos; una mejora de secuenciación no debe sustituirlos por comparación textual genérica.
- La regla de equivalencia debe seguir perteneciendo al evaluador actual. Un planificador puede seleccionar o recomendar práctica, pero no redefinir qué respuesta es correcta.

### Progreso persistido

- `tortuscript/progreso.py` declara `VERSION_ESQUEMA = 11` y usa `PROGRESO_INICIAL` y `_migrar(data)` para completar campos y normalizar partes de estructuras antiguas.
- El estado persistido abarca, entre otros, XP, ejercicios, lecciones, configuración, rachas, logros, práctica, proyectos, lecciones salteadas, intereses y recorrido inicial.
- La migración actual no constituye por sí sola una migración de un modelo de dominio nuevo. Si una futura fase introduce datos por concepto, deberá decidir explícitamente si son aditivos o requieren una nueva versión y cómo se preservan perfiles antiguos.
- No aumentar la versión de esquema ni alterar la estructura persistida para P1 sin una decisión arquitectónica aceptada y pruebas de compatibilidad.

### Repaso existente

- `tortuscript/practica.py` ya implementa práctica espaciada e intercalada; la política existente usa intervalos `(1, 2, 4, 8, 16)`, un máximo de seis tarjetas por sesión y retorno a la primera caja tras fallos.
- Estos comportamientos forman parte del baseline y no deben presentarse como funciones por implementar ni reemplazarse de manera incidental.

### XP y ayudas

- La documentación de contenido y el motor de lecciones definen reglas de XP diferenciadas por tipo de paso, intentos y uso de pistas/solución.
- Los ejercicios `escribir` tienen su propia escala por pistas. No asumir que todas las familias de ejercicios comparten la misma función de recompensa.
- Los cambios de variedad o secuenciación no deben otorgar XP duplicado por repetir una lección ni cambiar implícitamente el estado de perfección.

## 2. Riesgos que debe comprobar la revisión del cambio

1. **Índices posicionales:** cualquier inserción de pasos `escribir` antes o entre ejercicios históricos puede desplazar las claves del progreso aunque los IDs de lección permanezcan intactos.
2. **Identidad de lecciones:** renombrar, fusionar o dividir lecciones puede romper prerrequisitos, logros o asociaciones de progreso.
3. **Introducción frente a práctica:** el validador detecta ciertos usos prematuros, pero una revisión pedagógica debe comprobar además que las consignas no exijan implícitamente conceptos no enseñados.
4. **Equivalencia de respuestas:** cambios de contenido deben preservar las equivalencias intencionales del evaluador para salida, dibujos, entradas y juegos.
5. **Perfiles antiguos:** completar claves ausentes no demuestra por sí solo que el nuevo flujo funcione con fixtures históricos ni que se mantenga el aislamiento entre perfiles.
6. **Repaso paralelo:** una nueva selección de ejercicios no debe duplicar el calendario ni alterar las cajas/fechas del sistema de práctica existente.
7. **Recompensas:** repetir una lección, recibir ayuda o revelar una solución debe conservar las reglas actuales de XP y perfección.
8. **Alcance arquitectónico:** el modelo de dominio y el planificador siguen sujetos a ADR-052, cuyo estado examinado es `Propuesta`. La documentación de esa ADR indica expresamente que no autoriza implementación arquitectónica.

## 3. Controles verificables recomendados

Antes de aprobar cambios funcionales, adjuntar evidencia para:

- [ ] Comparación de la lista ordenada de IDs de curso y lección antes/después.
- [ ] Comparación de los 30 pasos `escribir` de `primeros-pasos` por posición, solución y lección asociada.
- [ ] Validador de contenido ejecutado sobre el commit candidato, con avisos clasificados.
- [ ] Suite de tests completa ejecutada y código de salida registrado.
- [ ] Tests de evaluación para salidas equivalentes, entradas, dibujos/laberintos y casos de ayuda pertinentes.
- [ ] Fixtures de progreso antiguo antes/después de migración, sin pérdida de datos y con aislamiento entre perfiles.
- [ ] Regresiones de XP, repetición de lecciones, desbloqueos y perfección.
- [ ] Regresiones de práctica espaciada: intervalos, límites por sesión, intercalado y fallo.
- [ ] Recorrido de integración de la interfaz para los cursos modificados.
- [ ] Confirmación de que el cambio no depende de ADR-052 mientras siga en Propuesta.

Los controles anteriores son requisitos de revisión sugeridos; esta inspección estática no afirma que hayan sido ejecutados.

## 4. Decisión de alcance

La línea independiente de ChatGPT se limita a documentación y auditoría. No modifica el motor, los datos de cursos, el esquema de progreso ni el evaluador. Los cambios de implementación pertenecen a la rama funcional de Claude y deben revisarse contra este informe y la matriz de regresión antes de cualquier integración.

No fusionar esta rama a `prod` automáticamente. No modificar `main`.
