"""Publica los documentos de contrato que consume Croco-Script (ADR-037) en `docs/contratos/`.

Uso:
    python herramientas/publicar_contratos.py              # reescribe curriculum-v1.json
    python herramientas/publicar_contratos.py --comprobar  # sale con 1 si lo publicado está desactualizado

`curriculum-v1.json` sale del catálogo curricular: no se edita a mano. Croco-Script lo copia y valida contra él
los prerrequisitos de sus cursos (`federacion.prerrequisitos_desconocidos_v1`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript import catalogo_producto  # noqa: E402

DESTINO = RAIZ / "docs" / "contratos" / "curriculum-v1.json"


def texto_publicable() -> str:
    return json.dumps(catalogo_producto.curriculo_publicado(), ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publica los contratos para otros productos del ecosistema.")
    ap.add_argument("--comprobar", action="store_true", help="no escribe: falla si lo publicado está desactualizado")
    args = ap.parse_args(argv)
    nuevo = texto_publicable()
    actual = DESTINO.read_text(encoding="utf-8") if DESTINO.is_file() else None
    if args.comprobar:
        if actual != nuevo:
            print(f"❌ {DESTINO.relative_to(RAIZ)} está desactualizado: corré herramientas/publicar_contratos.py", file=sys.stderr)
            return 1
        print(f"✅ {DESTINO.relative_to(RAIZ)} está al día.")
        return 0
    DESTINO.write_text(nuevo, encoding="utf-8")
    print(f"Publicado {DESTINO.relative_to(RAIZ)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
