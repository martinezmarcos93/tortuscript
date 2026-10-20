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

## Actualización 20/10 (madrugada)
Completado: P6 (métricas, revisado y corregido), Alfabetización entera (16 lecciones), casos de prueba ocultos (Codex),
CHANGELOG. Suite completa: 1238 tests OK (antes del merge de casos ocultos); validador sin errores.

## Pendiente
1. OK de Marcos para push de `pedagogia/p1-p6` y PR hacia `prod` (después de #27, o apilado sobre él).
2. Proxy LiteLLM: el fallback a Groq/Cerebras rechaza `reasoning_content` y corta las sesiones de OpenCode; arreglo pendiente del OK de Marcos.
3. Roadmap del libro (`docs/ROADMAP_INVENTAR_CON_PYTHON.md`): L1 a L7 sin empezar; L5 tiene ADR-054 aceptada.
4. Limpiar worktrees `~/src/tortuscript-*` ya integrados.
