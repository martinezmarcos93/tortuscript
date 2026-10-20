# Encargo 018 — Pistas graduadas en Python real

## Resultado

Se agregaron o corrigieron las pistas de los pasos rápidos de las nueve lecciones solicitadas en `contenido/cursos/python-real.json`. Cada paso tiene dos pistas. El validador encontró 0 errores en el curso Python real, y una comprobación adicional confirmó las cantidades y que las pistas de `elegir` y `predecir` no incluyan literalmente la respuesta.

## Commits

No se pudieron crear los nueve commits solicitados. El primer intento (`py-print`) fue bloqueado por el sandbox al intentar crear el lock del índice de Git:

```text
fatal: Unable to create '/home/marcos/src/tortuscript/.git/worktrees/tortuscript-pistas-python/index.lock': Read-only file system
```

Los cambios permanecen sin stage en `contenido/cursos/python-real.json`; no se modificó el índice ni se intentó eludir el bloqueo.

## Oráculo

`python3 herramientas/validar_contenido.py` — ejecutado antes del primer commit; 0 errores en `python-real` (y 2 avisos editoriales preexistentes en otros cursos).

## Propuestas

Ninguna.
