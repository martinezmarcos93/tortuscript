# TortuScript — reglas para asistentes (Claude/Codex)

## Ramas de backup: PROHIBIDO tocarlas
- `backup/main-2026-10-03` es un clon exacto de `main` en `1312dc0` (03/10/2026), local y publicado en `origin`.
  Reemplaza a `backup/main-2026-09-26` (`7c9c04c`, que sigue en la historia de `main`); el cambio lo decidió Marcos
  el 04/10/2026. Se queda así hasta que Marcos decida otra actualización.
- `backup/*` es una referencia de recuperación protegida. No se modifica, no se mueve, no se borra (ni local ni en
  `origin`) y no se usa como rama de trabajo: no hay commit, rebase, reset, cherry-pick ni push forzado sobre ella.
- **Nunca participa en un merge**, ni hacia `backup/*` ni desde `backup/*` hacia `main` u otra rama. Los cambios se
  desarrollan en ramas de trabajo y se integran solo en `main` según el flujo autorizado.
- Cualquier excepción la decide y la ejecuta Marcos.
- Protección técnica: hook `reference-transaction` en `~/.config/git-hooks/tortuth/` (activado con
  `git config core.hooksPath ~/.config/git-hooks/tortuth`; fuera del repo porque el disco NTFS no permite hooks
  ejecutables). Rechaza crear, mover o borrar `refs/heads/backup/*`; excepción deliberada: `TORTU_PERMITIR_BACKUP=1`.
  No está versionado: en otro clon hay que volver a activarlo.

## Decisiones de arquitectura
- Antes de implementar algo de `docs/experimental/`, leer [`docs/decisions/README.md`](docs/decisions/README.md).
- **Una ADR en estado Propuesta no autoriza implementación.** Solo una ADR Aceptada puede fundamentar cambios de
  arquitectura o comportamiento; si el código contradice una ADR Aceptada, primero se cambia la ADR.

## Cómo trabajar
- Correr: `.venv/bin/python iniciar_web.py` · Tests: `.venv/bin/python -m unittest discover -s tests` ·
  Contenido: `.venv/bin/python herramientas/validar_contenido.py`.
- Cada cambio va en su propia rama, con tests en verde, validador en 0 errores y entrada en el `CHANGELOG.md`;
  se fusiona a `main` solo con aprobación de Marcos.
