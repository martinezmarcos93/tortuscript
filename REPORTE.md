# Encargo 014 — desafíos de transferencia

## Desafíos

- **TortuScript**: saludo en ronda (variables, concatenación y repetir); puntos del juego (variables, cuentas y si/sino); clave secreta (preguntar y si/sino); tabla relámpago (repetir, variable contador y multiplicación).
- **Python**: saludo de equipo (input, variables, concatenación y for); doble o nada (input, int y multiplicación); filtro de nombres (listas, for, if y len); función de puntos (def, return y llamada).

El mapa curricular no contiene unidades de `primeros-pasos`. Para respetar la validación contra unidades existentes sin modificar el mapa, los desafíos de TortuScript referencian las unidades equivalentes disponibles (`python-puente`, `python-control`, `python-datos` y `python-problemas`).

## Verificado

- `./.venv/bin/python -m unittest tests.test_transferencia tests.test_contenido`: 48 tests OK.
- `./.venv/bin/python herramientas/validar_contenido.py`: todos los cursos pasan sin errores; los únicos avisos son dos de orden ambiguo ya presentes en `primeros-pasos`.
- `./.venv/bin/python -m unittest discover tests`: 1177 tests, 1 fallo y 4 errores. `tests/test_camino.py::TestWebCamino::test_camino_en_el_inicio` espera `0/108`; con las 8 lecciones nuevas el camino informa `0/116`. No se modificó ese test. Los 4 errores de `tests/test_lanzador.py` ocurren porque el sandbox deniega crear sockets (`PermissionError: [Errno 1] Operation not permitted`).
- Las pruebas nuevas verifican las soluciones por salida con entradas fijadas y el bloqueo de cada curso hasta completar el requisito. No se probaron sockets del lanzador fuera del sandbox.
