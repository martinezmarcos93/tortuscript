# Roadmap — Ideas de «Inventa tus propios juegos de computadora con Python»

**Estado:** aprobado por Marcos en alcance (19/10/2026). L5 tiene ADR-054 aceptada; L6 (si cambian límites) y L7a necesitan su propia ADR.
**Fuente:** `src/InventarConPython_3a_es.pdf` de la carpeta del proyecto (Al Sweigart, 3ª ed., traducción de A. Carella, A. Pernin y F. Palm; 380 págs.).
**Redactado por:** Claude Code, 19/10/2026.

## 0. Licencia: qué se puede tomar y qué no

- El **texto** del libro es CC BY-NC-SA 3.0: **no comercial**. TortuScript cobra (ADR-050), así que **no se copia ni se adapta texto, ejemplos ni ejercicios del libro**.
- El **código** es BSD-2, pero tampoco se copia: los juegos de TortuScript se escriben desde cero, en TortuScript o en Python real, con historias propias.
- Lo que sí se toma son **ideas didácticas** y **juegos populares de dominio común** (adivinar un número, ahorcado, ta-te-ti, pico-fama, cifrado César, batalla naval/sonar), que no pertenecen al libro.
- Regla para los encargos: ningún worker recibe el PDF ni fragmentos del texto; recibe solo la idea, explicada con nuestras palabras.

## 1. Ideas del libro y qué hace hoy TortuScript

| # | Idea del libro | Capítulos | TortuScript hoy | Brecha |
|---|---|---|---|---|
| I1 | **El juego primero**: cada capítulo arranca con una *muestra de ejecución*, después el programa completo y después la explicación por partes | todos | Las lecciones van de concepto a ejercicio; no hay transcripción de una partida | Falta un formato «mirá cómo se juega → leé el programa → entendé cada parte» |
| I2 | **Tipeá vos el código** en vez de copiar y pegar, y compará tu versión con el original (herramienta *diff* en línea) | 1, 4 | Hay pasos `escribir`; no hay comparación con un modelo | Falta un comparador como último nivel de pista |
| I3 | **Tres tipos de error**: de sintaxis, de ejecución y de semántica (hace otra cosa) | 7 | `error_handler` explica errores de Python; el feedback no los clasifica | Las tres categorías se pueden detectar con certeza y encajan con P4 |
| I4 | **Depurador paso a paso** (entrar, saltar, salir, puntos de quiebre) | 7 | La tortuga ya marca la línea que se ejecuta (`chk-depurador`) | No hay seguimiento de variables para programas de texto |
| I5 | **Diagramas de flujo antes de programar** | 8 | No existe | Pensar el algoritmo antes de escribirlo |
| I6 | **Un juego por capítulo**, construido de a poco: Adivina el número, Chistes, Reino de Dragones, Ahorcado, Ta-te-ti, Panecillos, Sonar, César, Reversi | 4–16 | Proyectos guiados (adivinador, calculadora, casa), Tortuaria (RPG) y «Creá tu juego» | Faltan juegos de texto clásicos que integren varios conceptos |
| I7 | **Extender un juego terminado** (Ahorcado → «Extendiendo Ahorcado»; «Modificando Evasor») | 10, 20 | Los desafíos de P5 recién empiezan | Calza con los desafíos de transferencia (`asistencia: "autonoma"`) |
| I8 | **IA de juego por reglas** (ta-te-ti: ganar, bloquear, esquina, centro) | 10, 15 | Enemigos de TortuGame con azar | Programar la estrategia de la computadora |
| I9 | **Simular cientos de partidas para comparar estrategias** (IA contra IA, porcentajes) | 16 | El azar ya tiene semilla (`tortugame.Azar`, mulberry32) | Experimentar con datos: hipótesis → simulación → conclusión |
| I10 | **Coordenadas cartesianas** como puente matemático (Sonar, distancias, `abs`) | 12–13 | La tortuga usa avanzar/girar | Coordenadas como unidad propia |
| I11 | **Temas tratados al inicio y resumen al final** de cada capítulo | todos | La lección muestra «aprendiste / practicaste» al final | Falta el «vas a aprender» al inicio (cambio chico) |
| I12 | **Gráficos, bucle de juego, eventos y colisiones** (Pygame) | 17–20 | TortuGame (escenas, héroe, enemigo, combate) | Bucle en tiempo real: grande, probablemente para Croco-Script (16+) |

## 2. Fases

Orden de menor a mayor riesgo. Cada fase cumple los criterios globales del roadmap pedagógico: tests en verde, validador en 0, sin pérdida de progreso, CHANGELOG, integración solo en `prod`.

### L1 — Juegos de texto en TortuScript (solo contenido, riesgo bajo)

Curso nuevo `juegos-de-texto` (fuera del mapa curricular, como Juegos o Tortuaria; `requiere` la última lección de `primeros-pasos`). Cada juego es una sección y cada lección suma una parte del programa:

1. **Adiviná el número**: azar con semilla, `mientras`, comparaciones, contar intentos.
2. **La cueva de los dos caminos** (idea de Reino de Dragones con historia propia): funciones, azar, `si/sino`.
3. **Ahorcado**: listas, recorrer un texto, ir armando la palabra oculta.

- **Formato I1**: cada sección arranca con una muestra de partida (paso `explicacion` con la transcripción), sigue con `predecir` sobre partes del programa y termina con `escribir` del programa completo, evaluado por comportamiento con `entradas_prueba` y semilla fija.
- **I11**: el primer paso de cada lección dice «vas a aprender: …» (texto; no cambia el motor).
- **I7**: al final de cada juego hay 2 desafíos `autonoma` con el formato de P5 («que avise si el número está cerca», «que muestre las letras ya usadas»).
- **Ya existe lo necesario**: el ejecutor de lecciones ofrece `dado()` con semilla (`executor._hacer_globals`) y el evaluador corre la solución con la misma semilla (`evaluacion.SEMILLA_EVALUACION`), así que un juego con azar se puede evaluar sin tocar el motor.
- **Encargos**: un worker por juego (contenido), con el validador como oráculo; Codex revisa la pedagogía.

### L2 — Feedback que enseña a depurar (motor, riesgo medio)

1. **Clasificar el error en tres tipos (I3)**: los datos ya están, aunque hoy no se etiquetan: la traducción o `ast.parse` falla (escritura), `ejecutar_codigo` informa un error al correr (ejecución), o `evaluacion.evaluar` da `incorrecto` (hace otra cosa). Se agrega `tipo_error: "escritura" | "ejecucion" | "resultado"` a la respuesta y la interfaz lo muestra con un ícono y una frase. Sin cambio de esquema ni de XP. Respeta P4: solo etiqueta lo que se detecta con certeza.
2. **Comparador con el modelo (I2)**: como **último** nivel de pista de un `escribir` guiado (no en los `autonoma`), después de 2 errores, marca las líneas del alumno que difieren de la solución (diff por líneas con `difflib`, stdlib). Nunca reemplaza la evaluación por comportamiento.
3. **Muestra de ejecución verificada (I1)**: campo opcional `muestra` en `explicacion` (`[{"sale": "…"} | {"entra": "…"}]`). El validador **corre el código del paso con esas entradas y exige que la salida coincida**: así la transcripción nunca miente.
4. **Unidad «Cazadores de bugs»** en `primeros-pasos` o en el curso nuevo: programas con un error de cada tipo para encontrar y arreglar (contenido).

### L3 — Juegos de Python real para 13–15 (contenido, riesgo bajo-medio)

Sección o curso nuevo dentro del recorrido de Python, con juegos de dominio común:

1. **Pico-fama** (la idea de Panecillos): listas, `join`, comparar posiciones; es un juego cuyo propio feedback hay que diseñar.
2. **Ta-te-ti con estrategia (I8)**: tablero como lista, funciones, reglas en orden de prioridad.
3. **Sonar en una grilla (I10)**: coordenadas, distancia, `abs`.
4. **Cifrado César**: `ord`/`chr`, módulo; enlaza con Alfabetización digital (privacidad).

Evaluación por comportamiento con `entradas_prueba`; las partes con azar usan semilla. Cada juego cierra con desafíos de transferencia (P5).

### L4 — Pensar antes de programar: diagramas de flujo (I5) (contenido + render, riesgo bajo)

- Lecciones donde se **ordena** un diagrama (pasos `ordenar` con frases en castellano, no código) y se **predice** qué camino toma una entrada.
- Si hace falta dibujar el diagrama: SVG estático en `web/static/img/` referenciado desde la explicación. Sin editor de diagramas en V1.

### L5 — Depurador paso a paso para programas de texto (I4) (motor, riesgo alto, **ADR-054 aceptada**)

- Entra en V1 (Marcos, 19/10). Diseño en ADR-054: el programa corre entero una sola vez en el worker de siempre y deja un
  **registro** de pasos (línea, variables, salida); la página lo reproduce con «siguiente», «anterior» y «hasta el final».
- Antes de integrar: revisión de seguridad de lo que se serializa desde el worker y tests de los topes.

### L6 — Simular para decidir (I9) (contenido + límites de ejecución, riesgo medio, **ADR** si cambian los límites)

- Para 14–15: «¿qué estrategia de ta-te-ti gana más?». Simular N partidas con semilla, contar resultados, sacar conclusiones. Enseña a experimentar y conecta con SQL/datos.
- Puede chocar con los límites de tiempo del ejecutor: medir primero; si hay que subir límites, ADR.

### L7 — Juegos gráficos (I12): evaluación de complejidad

Criterio de Marcos (19/10): todo lo de Croco-Script es de alto nivel. Evaluación:

- **Cómo funciona hoy TortuGame:** el programa del chico corre entero y deja un registro de eventos que la página anima
  después; el mismo intérprete existe en Python (referencia y evaluación) y en JS (`web/static/js/tortugame/interprete.js`),
  y los tests de conformidad exigen que den el mismo registro. Es un modelo **por turnos**.
- **Un juego en tiempo real** (bucle de cuadros, teclado continuo, colisiones, sprites, sonido) rompe ese modelo: el código
  del chico tiene que correr en cada cuadro reaccionando a entradas que no se conocen de antemano. Exige un runtime nuevo
  en el navegador, conformidad Python↔JS de un modelo continuo, otra forma de evaluar (no hay una salida fija que comparar)
  y otra revisión de seguridad. **Complejidad alta → Croco-Script.**
- **Lo que sí cabe en TortuScript (L7a, complejidad media):** juegos **por turnos con teclado** en la grilla de 8×5 que ya
  usa TortuGame. Cada tecla es un turno: el chico escribe la función que reacciona a `arriba/abajo/izquierda/derecha` y
  el juego avanza un paso (esquivar, juntar objetos, llegar a la salida). Se evalúa con una secuencia de teclas fija y su
  registro esperado, sin salir del modelo actual. Necesita una extensión de TortuGame (ADR nueva, porque cambia ADR-006/007).
- **L7b (Croco-Script):** bucle en tiempo real, colisiones y animación continua (las ideas de los capítulos 17–20 del libro).
  Se propone en el roadmap de Croco-Script, no en este.

## 3. Dependencias con el roadmap pedagógico

- L1 y L3 usan el formato de desafíos de **P5** y las pistas graduadas de **P4**.
- L2.1 y L2.2 son la continuación natural de **P4** (feedback orientado al error).
- El planificador (**P3**) y las métricas (**P6**) toman los juegos nuevos solo si entran al mapa curricular; en V1 quedan fuera, como Juegos y Tortuaria.

## 4. Decisiones de Marcos (19/10/2026)

1. **Gratis o premium según lo que hace falta saber** (ADR-053): si un juego o desafío se resuelve con lo que se aprende
   gratis, es gratis; si necesita alguna lección premium, queda bloqueado. Cada lección declara sus conceptos.
2. **L5 entra** (ADR-054).
3. **L7 según su complejidad:** el tiempo real va a Croco-Script (L7b); los juegos por turnos con teclado (L7a) quedan en TortuScript.
