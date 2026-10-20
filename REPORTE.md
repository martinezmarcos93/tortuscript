# Encargo 012 — Pistas graduadas

## Resultado

Implementadas las pistas graduadas del motor, su paso de errores previos desde las dos rutas web y las reglas de validación para el campo `pistas`. Cada texto de `pistas` también pasa por la revisión textual; cualquier hallazgo que genere lleva nivel ERROR y menciona `pistas`.

## Verificación

- `python3 -m unittest tests.test_pistas_graduadas tests.test_leccion tests.test_validacion_repetida tests.test_web tests.test_contenido`: 174 pruebas OK, 58 saltadas.
- `python3 herramientas/validar_contenido.py`: sin errores; dos avisos existentes en `primeros-pasos` sobre órdenes equivalentes.
- La primera invocación con `python` no pudo ejecutarse porque ese comando no existe en PATH.
- Un intento de invocar `tests.test_validacion` falló porque no existe ese módulo; se identificó y ejecutó `tests.test_validacion_repetida.py`.
- No se pudo crear el commit: Git intentó escribir `.../tortuscript/.git/worktrees/tortuscript-pistas-impl/index.lock`, que está fuera del worktree y bloqueado como solo lectura por el sandbox. Los cambios quedan sin commit.

## Propuestas

Ninguna.
