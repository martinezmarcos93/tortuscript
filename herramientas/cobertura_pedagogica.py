#!/usr/bin/env python3
"""Mapa de cobertura pedagógica: qué categorías de práctica tiene cada unidad del mapa curricular (P1).

Uso:  python3 herramientas/cobertura_pedagogica.py                       (imprime tabla y resumen)
      python3 herramientas/cobertura_pedagogica.py --escribir [--fecha AAAA-MM-DD]
            (regenera docs/audits/COBERTURA_PEDAGOGICA.md)
"""
import argparse
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tortuscript import cobertura, contenido, dominio  # noqa: E402

INFORME = RAIZ / "docs" / "audits" / "COBERTURA_PEDAGOGICA.md"


def _texto_resumen(res):
    def lista(ids):
        return ", ".join(f"`{u}`" for u in ids) or "ninguna"
    return (f"- Unidades de lecciones: **{res['unidades']}**\n"
            f"- Con las cuatro categorías: **{len(res['completas'])}**\n"
            f"- Con una sola categoría ({len(res['con_una_categoria'])}): {lista(res['con_una_categoria'])}\n"
            f"- Sin producción autónoma ({len(res['sin_produccion'])}): {lista(res['sin_produccion'])}\n")


def informe(fecha):
    cob = cobertura.cobertura(contenido.todos_los_cursos(), dominio.cargar_mapa())
    return (f"# Cobertura pedagógica por unidad (P1)\n\n"
            f"Generado con `herramientas/cobertura_pedagogica.py --escribir` el {fecha}. No editar a mano.\n\n"
            "Categorías según el tipo de paso (`docs/MODELO_DOMINIO_V1.md`): `elegir` → reconocimiento, "
            "`predecir` → predicción, `completar`/`ordenar` → construcción, `escribir` → producción.\n\n"
            "## Resumen\n\n" + _texto_resumen(cobertura.resumen(cob)) +
            "\n## Por unidad\n\n" + cobertura.tabla_markdown(cob))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--escribir", action="store_true", help="regenera docs/audits/COBERTURA_PEDAGOGICA.md")
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today(), help="fecha del informe (AAAA-MM-DD)")
    args = parser.parse_args()
    texto = informe(args.fecha.isoformat())
    if args.escribir:
        INFORME.write_text(texto, encoding="utf-8")
        print(f"Escrito {INFORME.relative_to(RAIZ)}")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
