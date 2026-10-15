# Roadmap — Evolución pedagógica adaptativa de TortuScript

**Estado:** propuesta de trabajo; no autoriza por sí sola cambios de arquitectura.  
**Rama de integración de estas mejoras:** `prod`.  
**Rama estable de referencia:** `main`.  
**Principio rector:** cambios incrementales, aditivos, reversibles y respaldados por pruebas.

## 1. Objetivo

Incorporar a TortuScript prácticas pedagógicas inspiradas en los principios públicos de Duolingo —no copiar su contenido, marca ni implementación propietaria— adaptadas al aprendizaje de programación: práctica de un concepto desde varios ángulos, recuperación activa, intercalado, repaso espaciado sensible al desempeño, pistas graduadas, evaluación de dominio y transferencia a problemas nuevos.

TortuScript ya dispone de lecciones breves, seis tipos de paso, evaluador, pistas, progreso por perfil, práctica espaciada, proyectos, tortuga gráfica, juegos y validación automática del contenido. El objetivo es coordinar y aprovechar esos mecanismos antes de crear otros nuevos.

## 2. Restricciones no negociables

1. No reemplazar ni reescribir el motor de lecciones, el evaluador, el traductor, el ejecutor ni el sistema de progreso para implementar mejoras pedagógicas.
2. No perder progreso existente, logros, XP, rachas, perfiles, proyectos ni compatibilidad con los archivos de progreso.
3. No alterar el orden ni los identificadores de los pasos `escribir` del curso `primeros-pasos`: su posición es clave del progreso histórico.
4. No renombrar identificadores de cursos o lecciones usados por progreso, logros o prerrequisitos.
5. Mantener el comportamiento actual como fallback si el planificador adaptativo no tiene información suficiente o falla.
6. No introducir vidas, castigos por equivocarse, presión competitiva adicional ni bloqueos pedagógicos arbitrarios.
7. No incorporar IA como requisito para el primer modelo adaptativo. Cualquier tutor con IA seguirá siendo opcional y sujeto a los controles de privacidad y consentimiento ya establecidos.
8. Ninguna implementación se integra directamente a `main`. El trabajo se realiza en ramas paralelas y se integra primero en `prod`, conforme a `docs/FLUJO_DE_RAMAS_PROD.md`.
9. No implementar propuestas que requieran una decisión arquitectónica hasta que Marcos acepte la ADR correspondiente.

## 3. Fases

### P0 — Línea de base y auditoría

**Objetivo:** conocer el comportamiento real antes de tocarlo.

- Auditar `tortuscript/leccion.py`, `tortuscript/evaluacion.py`, `tortuscript/progreso.py`, `tortuscript/practica.py`, `tortuscript/contenido.py`, la lógica de interfaz de lecciones y los esquemas de `contenido/cursos/*.json`.
- Identificar los eventos que ya se registran: primer intento, errores, pistas, respuesta revelada, tiempo y resultado final. No asumir que una métrica existe hasta verificarlo.
- Ejecutar la suite completa, el validador de contenido y las comprobaciones de interfaz disponibles; registrar resultados y fallos preexistentes.
- Documentar contratos, dependencias, claves históricas de progreso y rutas críticas.
- Crear una matriz de regresión para cuentas/perfiles, continuidad de lecciones, XP, logros, repaso, tortuga, proyectos y juegos.

**Salida:** informe de línea de base, mapa de módulos y pruebas de regresión identificadas.

**Puerta de salida:** ninguna modificación funcional comienza hasta comprender los contratos que debe preservar.

### P1 — Secuenciación pedagógica con ejercicios existentes

**Objetivo:** practicar cada concepto en formatos distintos sin ampliar todavía el modelo de datos del progreso.

- Mapear conceptos y prerrequisitos a los ejercicios existentes.
- Diseñar secuencias graduadas: explicación, reconocimiento, predicción, completar, ordenar, escritura autónoma y aplicación en proyecto cuando corresponda.
- Intercalar selectivamente conceptos anteriores, sin romper el orden curricular, los prerrequisitos ni la navegación.
- Mantener los seis tipos de paso y el formato JSON actual.
- Revisar que los ejercicios no se limiten a reformular la misma pregunta con otras palabras.
- Validar cada cambio con `herramientas/validar_contenido.py`, pruebas unitarias y recorrido real de las lecciones afectadas.

**Salida:** mapa de cobertura pedagógica y primeras secuencias mejoradas.

**Puerta de salida:** todo el contenido afectado pasa la validación; el progreso previo permanece intacto.

### P2 — Modelo de dominio por concepto

**Objetivo:** estimar qué conceptos requieren práctica adicional y cuáles parecen consolidados.

- Definir un identificador estable para cada concepto pedagógico; no reutilizar IDs de lecciones como sustituto si no representan el mismo concepto.
- Diseñar un modelo mínimo que distinga, cuando los datos lo permitan: reconocimiento, predicción, producción autónoma, uso de pistas y retención diferida.
- Definir reglas transparentes y deterministas antes de considerar modelos estadísticos o IA.
- Separar el modelo de dominio del evaluador y del motor de lecciones.
- Guardar los datos de forma aditiva y versionada, con valores por defecto para perfiles antiguos.
- Evitar inferir dominio a partir de una única respuesta o de ejercicios con ayuda.
- Si faltan datos, utilizar el recorrido estándar sin bloquear al alumno.

**Salida:** especificación del modelo, reglas documentadas, esquema versionado y pruebas unitarias.

**Puerta de salida:** compatibilidad con perfiles antiguos demostrada en pruebas; ningún dato histórico se sobrescribe ni se interpreta silenciosamente de forma incompatible.

### P3 — Planificador adaptativo y repaso

**Objetivo:** decidir qué practicar y cuándo, usando el modelo de dominio.

- Mantener el repaso existente de 1, 2, 4, 8 y 16 días como referencia inicial.
- Evaluar reglas que adelanten una práctica tras un olvido o amplíen el intervalo tras recuperaciones correctas y autónomas.
- Distinguir los errores conceptuales, de predicción, sintácticos, de secuencia y de aplicación solo cuando puedan identificarse de forma fiable.
- Recomendar actividades adecuadas al tipo de dificultad.
- Intercalar contenidos antiguos con los nuevos de forma limitada y comprensible.
- No modificar la fecha de los repasos históricos ni borrar la cola existente durante la migración.
- Introducir un fallback y un interruptor de configuración para volver al planificador anterior.

**Salida:** planificador independiente, política de selección documentada y pruebas de determinismo, fallback y fechas.

**Puerta de salida:** el sistema anterior sigue disponible y el nuevo puede desactivarse sin pérdida de progreso.

### P4 — Pistas graduadas y feedback orientado al error

**Objetivo:** que la retroalimentación ayude a comprender y no solo revele la respuesta.

- Auditar las pistas actuales y su relación con los errores frecuentes.
- Diseñar pistas graduadas: orientar la atención, explicar el concepto relevante y, solo al final, mostrar una solución.
- Mantener el comportamiento existente de reintento y revelación de respuesta mientras se prueba la mejora.
- No penalizar al alumno por pedir ayuda; las pistas pueden informar el nivel de autonomía, pero no deben convertir la experiencia en castigo.
- Usar errores reales del evaluador; no etiquetar automáticamente un fallo como conceptual si solo se conoce que la salida no coincidió.

**Salida:** guía de diseño de pistas, ejemplos por tipo de ejercicio y tests de regresión.

### P5 — Transferencia y proyectos integradores

**Objetivo:** comprobar si el conocimiento puede aplicarse fuera del ejercicio original.

- Crear desafíos de transferencia que combinen conceptos ya enseñados.
- Reutilizar la tortuga, los proyectos guiados, Tortuaria, TortuGame, Python real, Web y SQL cuando el itinerario lo permita.
- Distinguir proyectos guiados de tareas que el alumno resuelve con menor asistencia.
- Evaluar comportamiento correcto, no una única forma textual de escribir el programa.
- No exigir técnicas o conceptos que todavía no hayan sido enseñados, salvo que la consigna los presente explícitamente.

**Salida:** matriz concepto → ejercicios de práctica → desafío de transferencia.

### P6 — Métricas, validación pedagógica y ajuste

**Objetivo:** comprobar que las mejoras aportan aprendizaje y no solo más actividad.

Medir, según disponibilidad y privacidad:
- acierto al primer intento;
- número y nivel de pistas utilizadas;
- éxito en producción autónoma;
- retención en repasos diferidos;
- desempeño en ejercicios nuevos;
- finalización de proyectos y necesidad de asistencia;
- fallos de evaluación o de contenido.

- Definir una línea de base antes de comparar.
- Separar pruebas técnicas automatizadas de evidencia pedagógica obtenida con alumnos.
- No recoger telemetría remota por defecto ni ampliar la recopilación de datos infantiles sin revisión explícita de privacidad.
- Si no hay evidencia suficiente, describir el resultado como hipótesis y no como mejora demostrada.

**Salida:** informe de validación con resultados, limitaciones y decisiones recomendadas.

## 4. Orden de trabajo y dependencias

`P0 → P1 → P2 → P3`, con `P4` en paralelo solo después de auditar el feedback existente. `P5` puede diseñarse durante P1, pero sus implementaciones dependen de los contratos y conceptos ya validados. `P6` acompaña todas las fases y cierra la evaluación.

La documentación y las pruebas forman parte de cada fase, no una tarea final separada.

## 5. Criterios globales de aceptación

- Suite de tests existente y nueva en verde, o diferencias preexistentes documentadas sin atribuirlas al cambio.
- Validador de contenido aprobado.
- Flujos de interfaz afectados probados en navegador cuando exista herramienta de prueba disponible.
- Perfiles antiguos y nuevos compatibles.
- Sin regresiones en progreso, XP, rachas, logros, prerrequisitos, proyectos, tortuga ni juegos.
- Fallback al comportamiento anterior comprobado.
- Documentación y changelog actualizados.
- Revisión de seguridad y privacidad si se toca ejecución de código, autenticación, perfiles o datos de menores.
- Integración únicamente en `prod`; `main` permanece fuera de este ciclo.

## 6. Fuera de alcance inicial

- Reescribir el motor de lecciones.
- Sustituir el evaluador actual.
- Cambiar el formato de los cursos sin necesidad demostrada.
- Introducir un modelo de IA como dependencia obligatoria.
- Copiar contenido, ilustraciones, textos, marca o algoritmos propietarios de Duolingo.
- Añadir presión competitiva, vidas o castigos por errores.
- Rediseñar la gamificación sin evidencia de que sea necesario.

## 7. Documentos relacionados

- [Cómo escribir un curso](CONTENIDO.md)
- [Roadmap educativo V1](ROADMAP_V1_2026-12-31.md)
- [Roadmap comercial V1](ROADMAP_COMERCIAL_V1_2026-12-31.md)
- [Flujo de ramas e integración en prod](FLUJO_DE_RAMAS_PROD.md)
- [Índice de decisiones de arquitectura](decisions/README.md)
