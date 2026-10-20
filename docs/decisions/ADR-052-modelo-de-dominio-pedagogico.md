# ADR-052 — Modelo de dominio pedagógico y planificación adaptativa

- **Estado:** Aceptada (Marcos, 18/10/2026)
- **Fecha:** 14/10/2026
- **Responsable de decisión:** Marcos
- **Relacionado:** ADR-002, ADR-003, ADR-004, ADR-024; `docs/ROADMAP_PEDAGOGIA_ADAPTATIVA.md`; `docs/FLUJO_DE_RAMAS_PROD.md`

## Contexto

TortuScript ya cuenta con un motor de lecciones, seis tipos de paso, evaluación de respuestas y resultados ejecutables, progreso por perfil y repaso espaciado. Se propone mejorar la coordinación de estas funciones para que la práctica responda al desempeño demostrado por el alumno.

La inspiración procede de principios pedagógicos públicos empleados por plataformas como Duolingo —práctica variada, recuperación activa, repetición espaciada, dificultad progresiva y feedback inmediato— adaptados a la programación. No se copiarán contenido, identidad visual ni algoritmos propietarios.

## Propuesta

1. Mantener el motor de lecciones, el evaluador, el traductor y el ejecutor como componentes estables.
2. Introducir un modelo de dominio por concepto, separado del progreso histórico de lecciones.
3. Introducir un planificador independiente que recomiende ejercicios y repasos, con fallback al recorrido actual.
4. Mantener la compatibilidad con perfiles existentes mediante datos aditivos, versionados y migraciones explícitas cuando sean necesarias.
5. Priorizar reglas deterministas, explicables y probables mediante tests; la IA no será requisito del sistema adaptativo inicial.
6. Evaluar dominio con evidencia de distintos formatos y niveles de ayuda; un único acierto no será suficiente.
7. No bloquear el avance curricular ni penalizar al alumno por errores o por solicitar pistas.
8. No añadir telemetría remota ni ampliar la recopilación de datos infantiles sin una revisión de privacidad y una decisión explícita.

## Límites y garantías

- No cambiar el orden ni los identificadores de los pasos `escribir` del curso `primeros-pasos`.
- No renombrar IDs de cursos o lecciones que tengan referencias en progreso, logros o prerrequisitos.
- No alterar silenciosamente el significado de datos históricos.
- El planificador debe poder desactivarse sin pérdida de progreso.
- La ausencia de datos suficientes debe activar el comportamiento estándar.
- Los cambios se integran primero en `prod`; no se permite merge a `main` sin autorización explícita de Marcos.
- La aceptación de esta ADR no sustituye los tests de regresión, las validaciones de contenido ni la evaluación pedagógica.

## Alternativas consideradas

### A. Reescribir el motor de lecciones

**Descartada:** eleva el riesgo de regresiones sin ser necesaria para el objetivo pedagógico.

### B. Añadir solamente más ejercicios

**Insuficiente:** aumenta el catálogo, pero no coordina la práctica ni determina qué conviene repasar.

### C. Usar IA como planificador desde el principio

**Aplazada:** añade variabilidad, complejidad y consideraciones de privacidad antes de disponer de una línea de base y métricas fiables.

### D. Extender el sistema de forma aditiva

**Preferida en esta propuesta:** permite comparar, probar, desactivar y revertir componentes sin sustituir el funcionamiento estable.

## Consecuencias

### Positivas esperadas

- Mayor variedad de práctica por concepto.
- Mejor detección de diferencias entre reconocimiento y producción autónoma.
- Repasos seleccionados según evidencia de desempeño.
- Mejor trazabilidad de las decisiones pedagógicas.

### Costes y riesgos

- Se necesita una taxonomía de conceptos estable.
- Las señales disponibles pueden no permitir clasificar con certeza todos los errores.
- El modelo de dominio podría sobreestimar o subestimar el conocimiento.
- Las migraciones y reglas de selección requieren pruebas de compatibilidad.
- La mejora pedagógica no se puede afirmar sin validación con usuarios y ejercicios nuevos.

## Plan de validación

1. Auditar módulos, contratos, métricas y formato de progreso.
2. Establecer pruebas de regresión y una línea de base.
3. Probar secuencias variadas con los ejercicios actuales.
4. Evaluar el modelo de dominio de manera aislada.
5. Comparar el planificador nuevo con el existente y probar el fallback.
6. Medir producción autónoma, retención diferida y transferencia a problemas nuevos.
7. Documentar limitaciones y resultados antes de solicitar la aceptación de esta ADR.

## Decisión

**Aceptada por Marcos el 18/10/2026.** Las decisiones de esta ADR pasan a ser fundamento arquitectónico para las fases P2 (modelo de dominio) y P3 (planificador adaptativo) de `docs/ROADMAP_PEDAGOGIA_ADAPTATIVA.md`, siempre dentro de los límites y garantías de arriba y del flujo de ramas de `docs/FLUJO_DE_RAMAS_PROD.md` (ramas de trabajo → `prod`; nada a `main` sin orden expresa).

Precisiones de la primera implementación (18/10/2026):

1. **El dominio se deriva, no se guarda.** `tortuscript/dominio.py` calcula el estado por concepto leyendo el progreso que ya existe (`lecciones`, `ejercicios`, `repaso`). No agrega claves al progreso, no cambia `VERSION_ESQUEMA` y no recopila datos nuevos de menores. Si más adelante hiciera falta persistir, será otra decisión con migración propia.
2. **El concepto es la unidad de `contenido/mapa_curricular.json`** (37 unidades). No se crea una taxonomía paralela.
3. **El planificador es un módulo independiente con interruptor** y fallback al repaso actual de `practica.py`.
4. Ver `docs/MODELO_DOMINIO_V1.md` para las reglas exactas.
