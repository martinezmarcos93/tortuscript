# Reporte de Encargo 005 — Implementar la regla «respuesta correcta repetida»

## Objetivo
Se implementó la regla "respuesta correcta repetida" en `tortuscript/validacion.py` para hacer pasar los tests de `tests/test_validacion_repetida.py`.

## Cambios Realizados
1. Se creó la función auxiliar `_revisar_respuestas_repetidas(leccion, hallazgos)` dentro de `tortuscript/validacion.py`.
2. Esta función itera sobre los pasos de una lección, identificando pasos de tipo "elegir" y extrayendo la respuesta correcta (aplicando `strip()`).
3. Si una respuesta correcta ya fue vista en la misma lección, se añade un `Hallazgo` de nivel `AVISO`.
4. Se añadió una llamada a `_revisar_respuestas_repetidas` dentro de `validar_curso` para cada lección.
5. Se modificó la clase `Hallazgo` para que pueda ser accedida como un diccionario (e.g., `h["nivel"]`), añadiendo el método `__getitem__`, para que los tests existentes que esperan esta funcionalidad puedan ejecutarse correctamente sin modificar los tests.

## Oráculo
Los tests y el validador de contenido fueron ejecutados con éxito:

- `python3 -m unittest tests.test_validacion_repetida tests.test_contenido` pasó todos los tests.
- `python3 herramientas/validar_contenido.py` no reportó errores (0 errores).

## Archivos Afectados
- `tortuscript/validacion.py`

## Prohibiciones propias
- No se tocó `tests/**`.
- No se tocaron `contenido/**` ni `progreso.py` ni nada del motor.
- No se agregaron dependencias nuevas.
- No se encontraron tests que parecieran incorrectos.