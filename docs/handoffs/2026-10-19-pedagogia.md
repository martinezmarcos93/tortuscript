# Handoff — 2026-10-19 (noche): roadmap pedagógico P1–P6

Pausado por Marcos (límite de tokens). Rama `pedagogia/p1-p6` (local, sin push), sale de `integracion/2026-10-19` (PR #27 abierto hacia `prod`).

## Integrado en `pedagogia/p1-p6`
- Especificación `docs/ESPECIFICACION_P1_P6.md`; ADR-053 (cobro por lecciones requeridas) y ADR-054 (depurador), aceptadas por Marcos.
- P1: `tortuscript/cobertura.py`, `herramientas/cobertura_pedagogica.py`, informe `docs/audits/COBERTURA_PEDAGOGICA.md`; `herramientas/verificar_solo_agregados.py`.
- P3: `tortuscript/planificador.py` (apagado por defecto, `TORTU_PLANIFICADOR=adaptativo`).
- P4: pistas graduadas (motor, validador, `docs/GUIA_PISTAS.md`); contenido en Alfabetización (11 de 16 lecciones) y Python real.
- P5: cursos `desafios-tortuscript` y `desafios-python`, `unidad_de_cobro`, matriz de transferencia.
- P6: `docs/audits/VALIDACION_PEDAGOGICA_P6.md`. Roadmap del libro: `docs/ROADMAP_INVENTAR_CON_PYTHON.md`.
- Tests afectados en verde y validador sin errores al momento del último merge (suite completa sin correr).

## Pendiente (worktrees en `~/src/`)
1. `tortuscript-alfabetizacion-b` (encargo 016): commits de seguridad, integracion, json; falta revisar el archivo sin commitear y hacer `git`, `github`. Revisar pistas que regalan la respuesta antes de integrar.
2. `tortuscript-metricas-impl` (encargo 017): P6 implementado por el worker (`53ecff5`), **sin revisar**: correr `test_metricas_pedagogicas` y mutación.
3. Encargo 019 (casos de prueba ocultos, Codex): cortado antes de empezar; relanzar.
4. Correr la suite completa, regenerar el informe de cobertura y abrir PR de `pedagogia/p1-p6` hacia `prod` con OK de Marcos.
5. Proxy LiteLLM: el fallback a Groq/Cerebras rechaza `reasoning_content` y corta las sesiones de OpenCode; arreglo propuesto, pendiente del OK de Marcos.
