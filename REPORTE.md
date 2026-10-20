# Encargo 009 — Planificador adaptativo P3

## Hecho

- Implementé el interruptor apagado por defecto, la selección por nivel/atraso e intercalado, el fallback con log y las recomendaciones en `tortuscript/planificador.py`.
- Conecté el selector a `/practica`, agregué siete pruebas unitarias y una entrada al changelog.

## Verificación

- `.venv/bin/python -m unittest discover -s tests -p 'test_planificador.py'`: 7 pruebas, OK.
- `.venv/bin/python herramientas/validar_contenido.py`: 0 errores, 2 avisos existentes en `primeros-pasos`.
- `.venv/bin/python -m unittest discover -s tests`: 1176 pruebas; 4 errores por `PermissionError: [Errno 1] Operation not permitted` al abrir sockets en `tests/test_lanzador.py`. El sandbox bloqueó esas pruebas.

## Dudas sobre la especificación

- Ninguna.
