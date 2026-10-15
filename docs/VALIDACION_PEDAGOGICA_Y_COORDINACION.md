# Coordinación y validación — mejoras pedagógicas adaptativas

**Estado:** guía de trabajo y aceptación; no aprueba por sí misma la ADR-052 ni autoriza cambios arquitectónicos.
**Base de trabajo:** `prod`.
**Responsable del producto y de decisiones de alcance:** Marcos.
**Implementación y validación final coordinada:** Claude Code.
**Trabajo documental y revisión independiente:** ChatGPT.
**Integración final:** Claude Code, únicamente después de terminar ambos frentes y completar los controles descritos aquí, según la autorización expresa dada por Marcos para esta tarea. No se integra a `main`.

## 1. Distribución del trabajo

### Claude Code — implementación y validación final
1. Leer `docs/ROADMAP_PEDAGOGIA_ADAPTATIVA.md`, `docs/FLUJO_DE_RAMAS_PROD.md`, `docs/decisions/ADR-052-modelo-de-dominio-pedagogico.md` y este documento.
2. Realizar una auditoría amplia del estado real del código y de las pruebas; no asumir que los documentos describen fielmente el comportamiento actual.
3. Implementar en ramas temporales nacidas de `prod` únicamente mejoras seguras dentro del alcance autorizado. Priorizar contenido y secuenciación usando los seis tipos de ejercicio existentes.
4. No implementar el modelo de dominio ni el planificador adaptativo como cambios arquitectónicos mientras ADR-052 siga en estado `Propuesta`. Puede preparar hallazgos y una propuesta concreta.
5. Ejecutar y documentar pruebas de cada rama, hacer push y dejar un resumen reproducible.
6. Cuando ChatGPT y Claude hayan terminado, revisar ambos conjuntos de cambios como un único lote, resolver conflictos de manera explícita, ejecutar la validación final y realizar la integración autorizada a `prod`. No integrar a `main`.

### ChatGPT — validación documental y revisión independiente
1. Crear una matriz verificable de regresión y criterios de aceptación para las mejoras pedagógicas.
2. Revisar los contratos documentados del contenido, progreso y compatibilidad histórica; identificar riesgos y requisitos que deben probarse.
3. Mantener esta tarea en una rama temporal independiente, sin modificar los mismos archivos funcionales que Claude Code.
4. Publicar la rama y entregar a Claude Code el enlace, el resumen del diff y las comprobaciones realizadas.
5. No fusionar ramas ni escribir directamente en `prod` o `main`.

## 2. Protocolo de autonomía y toma de decisiones

Claude Code y ChatGPT deben resolver por contexto las decisiones ordinarias de implementación sin interrumpir a Marcos con preguntas de bajo impacto. Antes de decidir, consultar el código, pruebas, ADR, roadmaps, historial y convenciones existentes.

Orden de precedencia:
1. Instrucciones explícitas de Marcos en la conversación.
2. ADR aceptadas y contratos documentados vigentes.
3. Comportamiento real y pruebas existentes.
4. Roadmaps y ADR en estado Propuesta, como orientación y no como autorización arquitectónica.
5. Convenciones locales y criterio técnico conservador.

Ante ambigüedades, elegir la solución de menor riesgo, más pequeña, reversible y compatible con el comportamiento actual. Registrar la decisión, alternativas descartadas y razón en el resumen de trabajo. No preguntar por decisiones rutinarias.

Detener solo la acción afectada —sin detener auditorías independientes— cuando exista una decisión irreversible o de producto, una migración de datos riesgosa, un cambio de seguridad/privacidad, una dependencia externa, un cambio contractual incompatible o una decisión reservada expresamente a Marcos. Proponer una alternativa segura y documentar el bloqueo; no inventar autorización.

## 3. Reglas de ramas y colaboración

- Todo trabajo comienza desde el estado actualizado de `prod` y se desarrolla en ramas temporales separadas, por ejemplo `feature/secuencias-variadas`, `fix/regresion-progreso` o `docs/matriz-validacion-pedagogica`.
- Nunca desarrollar directamente en `prod` ni en `main`.
- Hacer commits pequeños y descriptivos; hacer push de cada rama al remoto.
- No sobrescribir el trabajo de la otra parte ni compartir archivos en escritura simultánea sin coordinar.
- No borrar ramas con trabajo pendiente antes de que Claude confirme que fue revisado, integrado o respaldado.
- No hacer force-push ni reescribir historia compartida.
- No fusionar a `prod` antes de que ambos frentes hayan terminado y Claude haya completado la validación final. La instrucción de Marcos para este encargo delega a Claude la integración final a `prod` tras cumplir esas condiciones.
- Ninguna parte puede fusionar a `main`; cualquier promoción posterior requiere una instrucción expresa y separada de Marcos.

## 4. Matriz de regresión obligatoria

| Área | Verificación mínima | Criterio de aceptación |
|---|---|---|
| Contenido | `python herramientas/validar_contenido.py` | Sin errores; cada aviso nuevo se revisa y justifica |
| Tests de contenido | `python -m unittest tests.test_contenido` | Pasa |
| Suite existente | Ejecutar el comando completo documentado por el repositorio; si no existe uno, identificar y ejecutar los tests disponibles | Sin regresiones nuevas; separar fallos preexistentes |
| Cursos y prerrequisitos | Recorrer los cursos afectados y comprobar el orden y desbloqueo | No se saltean prerrequisitos ni se rompe el camino curricular |
| Progreso histórico | Comparar fixtures/perfiles anteriores con los nuevos y completar una lección ya iniciada | Se conservan progreso, completitud, racha, XP, logros y repasos |
| Identificadores | Comparar IDs de cursos/lecciones y los pasos `escribir` de `primeros-pasos` | Ningún ID histórico renombrado; orden y posiciones 0–29 intactos |
| Perfiles antiguos | Cargar datos sin campos nuevos o con versiones previas | Carga sin excepción; se aplican valores por defecto/fallback |
| Evaluación | Probar respuestas correctas, incorrectas, equivalentes y con pistas en cada tipo afectado | El criterio de corrección existente no cambia accidentalmente |
| Interfaz | Recorrer en navegador los flujos tocados y revisar consola | Sin bloqueos, controles rotos ni errores nuevos |
| Repaso espaciado | Comprobar calendario base de 1, 2, 4, 8 y 16 días | El comportamiento actual se conserva salvo cambio aprobado y probado |
| Ejercicios adaptados | Resolver casos sin datos de desempeño y casos con datos parciales | Fallback al recorrido estándar; no se bloquea al alumno |
| Seguridad y privacidad | Revisar cambios de almacenamiento, telemetría, tutor IA y datos infantiles | Sin envío remoto nuevo ni ampliación de datos sin revisión/decisión |
| Reversión | Identificar cómo desactivar o revertir cada mejora | Reversión documentada; sin pérdida de datos |

## 5. Reglas pedagógicas de aceptación

- Cada concepto relevante se practica desde más de un ángulo cuando el contenido disponible lo permite: reconocer, predecir, completar/ordenar, producir y aplicar.
- No se considera que una pregunta sea una práctica distinta solo por cambiar nombres o texto superficial.
- No se introducen conceptos antes de explicarlos ni se exige una construcción que no haya sido enseñada o habilitada por una pista.
- La dificultad aumenta de manera gradual y respeta prerrequisitos.
- El error produce feedback útil, no castigo; pedir una pista no debe penalizar el dominio como si fuera un error.
- Un acierto aislado o asistido no basta para declarar dominio consolidado.
- La retención real y la transferencia deben distinguirse de la finalización de una lección.
- No afirmar mejora pedagógica demostrada a partir de tests técnicos únicamente; la eficacia con alumnos requiere evaluación posterior.

## 6. Informe requerido por rama

Cada entrega debe incluir:
- nombre de rama y SHA del último commit;
- objetivo, alcance y archivos cambiados;
- decisiones tomadas autónomamente y su fundamento;
- comandos ejecutados y resultados reales (no declarar pruebas no ejecutadas);
- fallos preexistentes diferenciados de regresiones;
- riesgos, limitaciones y pasos de reversión;
- estado de la ADR si el cambio depende de una decisión arquitectónica;
- enlace a la rama o PR, sin integrarlo a `prod`.

## 7. Puerta de integración final

Claude Code no integra hasta comprobar todos estos puntos:

1. Ambas partes entregaron sus ramas y resúmenes.
2. Los cambios se revisaron como un lote y no hay archivos inesperados ni duplicación de responsabilidades.
3. Los conflictos se resolvieron con revisión semántica, no eligiendo automáticamente una versión.
4. La matriz de regresión aplicable se ejecutó sobre la combinación final.
5. El validador de contenido pasa y se documentan los avisos.
6. No hay cambios arquitectónicos que dependan de una ADR todavía propuesta.
7. La compatibilidad de progreso y los identificadores históricos está verificada.
8. La documentación y el roadmap reflejan lo realmente implementado, no lo meramente planificado.
9. Claude deja un informe final con los SHA de origen, commit integrado a `prod`, pruebas, limitaciones y estado de `main`.

Si algún control crítico falla, no se integra el lote completo. Se puede integrar una unidad independiente solo si su separación es clara, pasa sus propios controles y no depende de los cambios fallidos; la decisión debe quedar documentada.

## 8. Alcance inmediato

El primer ciclo se concentra en la auditoría P0 y en mejoras de secuenciación/contenido P1 que puedan hacerse sin alterar la arquitectura. P2 (modelo de dominio) y P3 (planificador adaptativo) quedan en diseño hasta que exista línea de base suficiente y Marcos acepte ADR-052. El trabajo no cambia la rama estable `main`.
