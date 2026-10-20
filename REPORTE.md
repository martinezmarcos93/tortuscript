# Encargo 014 — desafíos de transferencia

## Desafíos

- **TortuScript**: saludo fijo con variable y repetición; total de puntos con suma y condición; clave pedida con entrada y condición; tabla del 3 con contador, repetición y multiplicación.
- **Python**: saludo de equipo con `input` y `for`; doble de entrada numérica con `input`, `int` y multiplicación; filtro de lista con `for`, `if` y `len`; función con `def`, `return` y llamada.
- Los conceptos de transferencia son ids de lecciones previas. El catálogo deriva la unidad de cobro de esas lecciones; los desafíos TortuScript no apuntan a unidades del mapa y quedan gratis.

## Verificación

- `./.venv/bin/python -m unittest tests.test_transferencia tests.test_contenido`: 53 tests OK.
- `./.venv/bin/python herramientas/validar_contenido.py`: todos los cursos pasan sin errores; quedan dos avisos preexistentes de orden ambiguo en `primeros-pasos`.
- `./.venv/bin/python -m unittest discover tests`: repetido dos veces; ambas ejecuciones llegan a 1205 tests y fallan en los mismos cuatro casos de `tests/test_lanzador.py` al crear sockets, con `PermissionError: [Errno 1] Operation not permitted`. El sandbox bloquea esa operación.
- La expectativa de `tests/test_camino.py::TestWebCamino::test_camino_en_el_inicio` pasa a `0/116` para contar las ocho lecciones nuevas.

## Estado de entrega

- El intento de restaurar los cambios tras el segundo fallo fue bloqueado por el sandbox: el índice compartido de Git está fuera del worktree y en solo lectura. No intenté otra vía para modificarlo. Los cambios de implementación quedan presentes en este worktree; no se creó ningún commit.
