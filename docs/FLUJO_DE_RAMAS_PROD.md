# Flujo de ramas e integración — TortuScript

**Estado:** regla de trabajo vigente por instrucción de Marcos.  
**Rama estable de referencia:** `main`.  
**Rama de integración de las nuevas implementaciones:** `prod`.

## 1. Regla principal

Todo trabajo nuevo de las mejoras pedagógicas y de los roadmaps asociados se realiza en ramas paralelas de trabajo y se integra en `prod`. **No se fusiona directamente ninguna rama de trabajo a `main`.** La rama `main` queda fuera de este ciclo de integración hasta que Marcos dé una autorización explícita posterior.

La creación de `prod` no implica que el producto esté listo para usuarios ni que sea una release. Es una rama de integración para probar y consolidar estas implementaciones.

## 2. Topología de ramas

- `main`: referencia estable previa al programa de mejoras. No recibe merges de este trabajo.
- `prod`: rama de integración donde se combinan las implementaciones revisadas y probadas.
- `feature/<tema-corto>`: implementación funcional acotada.
- `docs/<tema-corto>`: documentación, roadmaps y decisiones.
- `fix/<tema-corto>`: correcciones específicas detectadas durante pruebas.

Las ramas de trabajo nacen de `prod` para el programa pedagógico. Si una tarea necesita cambios de `main` que todavía no estén en `prod`, se debe documentar y resolver esa diferencia de forma explícita; no se mezclan bases silenciosamente.

## 3. Flujo obligatorio

1. **Inspeccionar:** revisar estado de `prod`, archivos afectados, tests y ADRs.
2. **Definir alcance:** una rama debe resolver una unidad coherente, con criterios de aceptación verificables.
3. **Crear rama paralela:** no trabajar directamente en `prod` ni en `main` para implementar funcionalidades.
4. **Implementar de forma incremental:** cambios acotados, preferentemente aditivos; no reescribir componentes estables por conveniencia.
5. **Validar:** ejecutar tests pertinentes, suite completa, validador de contenido y pruebas de interfaz que correspondan.
6. **Documentar:** actualizar roadmap, ADR, guía de contenido o changelog cuando el cambio lo requiera.
7. **Revisar diferencias:** comprobar el diff completo, archivos inesperados, compatibilidad de datos y riesgos de seguridad.
8. **Integrar a `prod`:** mediante PR o mecanismo equivalente revisable; no integrar si fallan criterios de aceptación.
9. **Verificar `prod`:** repetir las pruebas de integración tras cada merge y registrar commit, resultado y limitaciones.
10. **Informar:** comunicar rama, PR/commit, pruebas ejecutadas, resultados y cualquier trabajo pendiente.

## 4. Autorización y límites

- El asistente puede crear ramas, modificar archivos y preparar PRs dentro del alcance autorizado.
- Los merges a `prod` se realizan solo después de revisar el diff y las pruebas de la unidad correspondiente.
- **Está prohibido hacer merge a `main` sin una instrucción explícita de Marcos en ese momento.** Una autorización para trabajar, documentar o integrar a `prod` no autoriza el merge a `main`.
- No borrar ramas de trabajo que contengan cambios sin integrar o que sirvan como evidencia de una implementación.
- No hacer force-push ni reescribir historia compartida como operación rutinaria.
- Si una integración necesita una migración de datos, cambio de contrato o ADR, debe resolverse y probarse antes del merge.
- Si los tests no pueden ejecutarse por limitaciones del entorno, informar la limitación y no afirmar que el cambio está validado.

## 5. Convención de commits y PRs

- Un commit debe representar un cambio coherente y describir su propósito.
- Una PR debe explicar problema, solución, archivos afectados, pruebas, riesgos y plan de reversión.
- Evitar PRs gigantes que mezclen secuenciación de ejercicios, modelo de dominio, planificador, interfaz y cambios comerciales.
- Mantener cada fase del roadmap rastreable a una rama, PR o conjunto de commits.
- No introducir dependencias nuevas sin justificar necesidad, mantenimiento, seguridad y efecto sobre el funcionamiento offline.

## 6. Protección de `prod`

Antes de cada integración:
- suite de tests pertinente;
- `python herramientas/validar_contenido.py`;
- revisión de regresiones sobre progreso y perfiles;
- prueba de interfaz real para cambios de experiencia;
- inspección de `git diff` y estado de la rama;
- documentación actualizada.

Después de cada integración:
- confirmar el commit de `prod`;
- repetir validaciones de integración;
- dejar constancia de cualquier fallo preexistente o limitación;
- mantener un camino de reversión identificable.

Si el repositorio permite configurar protección de ramas, se recomienda exigir PR y checks para `prod`. La configuración remota debe verificarse por separado; este documento no afirma que las reglas estén activadas en GitHub.

## 7. Release y retorno a main

`prod` no se fusiona automáticamente a `main`. Cuando Marcos considere finalizado el programa:
1. se congela el alcance;
2. se revisan todos los commits y PRs integrados;
3. se ejecuta la matriz completa de pruebas;
4. se prepara un informe de diferencias, riesgos, migraciones y reversión;
5. Marcos decide expresamente si autoriza promover `prod` a `main`.

Hasta esa autorización, `main` no recibe estos cambios.

## 8. Alcance de esta política

Esta política regula el ciclo de nuevas mejoras pedagógicas de TortuScript y sus documentos relacionados. No modifica retroactivamente releases ya publicadas ni autoriza cambios en otros repositorios. Cualquier extensión del flujo a otros proyectos debe indicarse expresamente.


## 9. Excepción de bootstrap documental

La creación inicial de `prod` y la incorporación de este documento, el roadmap pedagógico, el índice de roadmaps y la ADR-052 se realizaron directamente en `prod` como bootstrap documental explícitamente solicitado por Marcos. Esta excepción queda limitada a la preparación inicial de las reglas y documentos de gobierno; **no es precedente para implementar funcionalidades directamente en `prod`**. Desde este punto, todo cambio nuevo debe seguir el flujo de ramas paralelas y revisión establecido arriba.
