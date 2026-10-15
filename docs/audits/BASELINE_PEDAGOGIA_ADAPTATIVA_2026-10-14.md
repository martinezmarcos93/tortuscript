# Auditoría P0 — contratos pedagógicos observados en `prod`

**Fecha de inspección:** 14/10/2026  
**Rama inspeccionada:** `prod`  
**Naturaleza:** inspección estática de código y documentación remota. No equivale a ejecutar tests ni a una auditoría completa.  
**Objetivo:** dejar una línea de base independiente para orientar las implementaciones y la validación final.

## 1. Hallazgos confirmados por inspección

### 1.1 El motor de lecciones ya cubre seis tipos de paso

`tortuscript/contenido.py` define `TIPOS = ("explicacion", "elegir", "completar", "ordenar", "predecir", "escribir")`. El contrato de contenido se documenta en `docs/CONTENIDO.md` y el motor sin interfaz está en `tortuscript/leccion.py`.

**Implicación:** las primeras mejoras pedagógicas deberían hacerse principalmente mediante secuenciación y calidad/cobertura de contenido JSON. No se justifica añadir tipos nuevos antes de demostrar una limitación real de los existentes.

### 1.2 La evaluación se basa en resultados ejecutados

`tortuscript/evaluacion.py` compara la salida del programa del alumno con la salida de la solución ejecutada con entradas equivalentes. La documentación también contempla equivalencia de dibujos y juegos en sus modos respectivos.

**Implicación:** no modificar criterios de evaluación ni duplicar lógica de corrección en un planificador pedagógico. Las recomendaciones deben consumir señales ya producidas o proponer un contrato explícito, sin convertirse en otro evaluador.

### 1.3 El progreso es un contrato histórico, no un objeto descartable

En `tortuscript/progreso.py` se declara `VERSION_ESQUEMA = 11`, `PROGRESO_INICIAL` y una función `_migrar(data)` que completa campos ausentes o de tipo incorrecto y establece la versión vigente. El progreso contiene, entre otros campos, `xp_total`, `ejercicios`, `lecciones`, `logros`, `repaso`, proyectos, racha y configuración del perfil.

La migración actual es permisiva: completa estructura y valores por defecto, pero no constituye por sí misma una prueba de que cualquier campo nuevo se haya preservado semánticamente.

**Implicación:** no aumentar la versión del esquema ni guardar una nueva representación de dominio como parte de P1. Si P2 se autoriza más adelante, el nuevo dato debe ser aditivo, versionado, con fixtures de perfiles históricos y pruebas de ida/carga sin pérdida.

### 1.4 El repaso espaciado ya existe como módulo puro

`tortuscript/practica.py` define:
- intervalos `(1, 2, 4, 8, 16)`;
- tarjetas para los tipos rápidos `elegir`, `predecir`, `completar` y `ordenar`;
- un máximo ordinario de seis tarjetas por sesión;
- intercalado con un límite por lección;
- una función `registrar` que sube de caja con acierto y devuelve a la caja 1 ante un error.

El módulo recibe fecha y cursos; su contrato indica que no accede al disco.

**Implicación:** no describir el repaso espaciado como una funcionalidad por construir. P3 debe partir de este baseline y demostrar qué problema real no resuelve, preservando calendario, límites y fallback.

### 1.5 Las reglas de XP forman parte de la experiencia actual

El encabezado de `tortuscript/leccion.py` documenta 5 XP al primer intento, 2 con reintentos y 0 si se revela la respuesta; los pasos `escribir` conservan su esquema de premios según las pistas. El módulo también documenta el umbral de dos errores antes de mostrar «Ver respuesta».

**Implicación:** la adaptación no debe penalizar por pedir pistas ni alterar recompensas como efecto colateral. Separar métricas pedagógicas de las reglas de XP y logros.

### 1.6 El contenido tiene contratos que protegen el avance existente

`docs/CONTENIDO.md` advierte explícitamente que el orden de los pasos `escribir` del curso `primeros-pasos` (posiciones 0–29) está ligado al progreso histórico guardado en `ejercicios`. También advierte que los IDs de lecciones son usados por progreso, logros y prerrequisitos.

**Implicación:** cualquier cambio en ese curso requiere comparar el orden e IDs antes/después. No reordenar, eliminar ni renombrar los pasos históricos. Para ampliar práctica, preferir añadir contenido no disruptivo y probar el camino completo.

## 2. Riesgos que la auditoría de código debe resolver

1. **Observabilidad real:** confirmar qué señales existen de primer intento, reintentos, pistas, respuesta revelada y fecha; no inferirlas solo de XP o estrellas.
2. **Cobertura pedagógica:** mapear conceptos, prerrequisitos y tipos de ejercicio por curso antes de editar secuencias.
3. **Interacción UI/API:** comprobar cómo `web/static/js/leccion.js` solicita pasos, envía respuestas y recibe resultados; no suponer que la UI puede reordenar pasos sin soporte del servidor.
4. **Persistencia y compatibilidad:** identificar qué rutas escriben el progreso y cómo se cargan perfiles antiguos; diseñar pruebas de fixtures, no solo de progreso recién creado.
5. **Pruebas de interfaz:** confirmar disponibilidad real de Playwright y el comando `python herramientas/jugar_cursos.py <curso>`; registrar las limitaciones del entorno.
6. **Repaso:** revisar pruebas existentes de `practica` y del progreso que lo integra antes de proponer cambios en selección o calendario.
7. **Estado base de tests:** ejecutar `python -m unittest discover tests` y `python herramientas/validar_contenido.py` en un checkout de `prod`; registrar salidas, dependencias y cualquier fallo previo.

## 3. Recomendación por fase

### P0 — antes de implementar
- Completar auditoría de contratos, rutas de persistencia, JS, tests y contenido.
- Guardar salida real de tests y validador como baseline.
- Obtener snapshot de IDs de cursos/lecciones y posiciones de `escribir` de `primeros-pasos`.

### P1 — secuenciación y contenido
- Priorizar archivos JSON de cursos, con cambios acotados.
- Mapear concepto → formatos existentes → prerrequisitos → producción autónoma.
- Mantener formato de datos, motor, evaluación y progreso sin cambios salvo necesidad demostrada.
- Validar contenido, tests y recorrido UI de cada curso afectado.

### P2/P3 — no iniciar como cambio funcional en esta etapa
El modelo de dominio y el planificador adaptativo dependen de decisiones de arquitectura de ADR-052, que sigue en estado `Propuesta`. La inspección actual no autoriza implementarlos ni actualizar el esquema. Primero se debe cerrar P0, medir lo que realmente existe y obtener la decisión de Marcos.

## 4. Alcance y límites de este informe

Este informe recoge contratos visibles en archivos de `prod` consultados el 14/10/2026. No declara que la suite pase, no verifica el estado de CI y no demuestra el comportamiento de la interfaz en ejecución. Claude Code debe completar la auditoría dinámica y corregir este informe si las pruebas o el código adicional contradicen alguno de los hallazgos.
