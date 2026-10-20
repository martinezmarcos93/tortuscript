# Encargo 019 — Casos ocultos en `escribir`

## Cambios

- `proceso.normalizar_pedido` valida y normaliza hasta cinco casos y las respuestas de cada uno con los límites de `entradas`.
- El worker, cuando la primera evaluación resulta correcta, compara la salida normalizada del alumno y la solución en cada caso, con la semilla de evaluación. Si difieren o el alumno falla, devuelve `incorrecto` e incluye `caso`.
- El endpoint de pasos `escribir` reenvía los `casos_prueba` del contenido. La lección muestra qué entrada oculta encontró otra salida, junto con lo esperado y lo obtenido.
- El validador revisa formato, tipo de paso y ejecución de la solución con cada caso. Se agregaron casos a Clave secreta, Saludo de equipo y Doble o nada.
- Se agregó `tests/test_casos_ocultos.py` con pruebas de normalización, evaluación, validador y desafíos reales.

## Verificado

- `python3 -m unittest tests.test_casos_ocultos -v` — 7 pruebas, OK.
- `python3 -m unittest tests.test_contenido tests.test_evaluacion -v` — 49 pruebas, OK.
- `python3 herramientas/validar_contenido.py` — sin errores; los cursos modificados no tienen avisos.
- `git diff --check` — OK.

## No verificado

- No se ejecutó la suite completa ni pruebas de interfaz en navegador.
- El comando `python` no está disponible en el entorno; las verificaciones se ejecutaron con `python3`.
