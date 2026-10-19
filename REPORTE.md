# REPORTE.md

## Encargo 004 — Tests (en rojo) de la regla «respuesta correcta repetida» (T1, parte tester)

**Estado:** Bloqueada

### Tareas realizadas:
1.  Creación de `tests/test_validacion_repetida.py` con cursos sintéticos y mocks para asegurar que los tests fallen con `AssertionError`.
2.  Implementación de los casos de prueba (a) a (h) según lo especificado en el encargo.

### Propuestas:
No se detectaron propuestas, el encargo fue seguido al pie de la letra.

### Hallazgos:
Como se esperaba, los tests (a)-(g) fallan con `AssertionError` debido a que la implementación de `validar_curso` (mocked o inexistente) no produce los `Hallazgos` de `AVISO` esperados con la frase "respuesta correcta repetida".

El oráculo espera que el archivo `tests/test_validacion_repetida` falle con `AssertionError`.

### Comando de verificación:
`.venv/bin/python -m unittest discover -s tests`
