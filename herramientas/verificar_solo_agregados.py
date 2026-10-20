#!/usr/bin/env python3
"""Comprueba que un curso solo ganó pasos AL FINAL de sus lecciones respecto de una referencia de git.

Protege el progreso guardado: la clave de cada paso es su posición, así que un cambio de contenido no puede
insertar, reordenar, borrar ni modificar pasos existentes, ni cambiar ids de secciones o lecciones.
Se permite agregar campos nuevos opcionales a un paso existente solo si se nombran con --campos-nuevos
(p. ej. `pistas`), y agregar lecciones o secciones nuevas al final.

Uso:  python3 herramientas/verificar_solo_agregados.py REF CURSO [CURSO ...] [--campos-nuevos pistas]
Sale con 1 si encuentra un cambio no permitido.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _curso_en(ref, curso_id):
    ruta = f"contenido/cursos/{curso_id}.json"
    texto = subprocess.run(["git", "show", f"{ref}:{ruta}"], cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", check=True).stdout
    return json.loads(texto)


def comparar(viejo, nuevo, campos_nuevos=()):
    """Lista de problemas (vacía si solo hay agregados permitidos)."""
    problemas = []
    secciones_n = nuevo.get("secciones", [])
    for i, sec_v in enumerate(viejo.get("secciones", [])):
        if i >= len(secciones_n) or secciones_n[i].get("id") != sec_v.get("id"):
            problemas.append(f"sección {sec_v.get('id')}: falta o cambió de lugar")
            continue
        lecciones_n = secciones_n[i].get("lecciones", [])
        for j, lec_v in enumerate(sec_v.get("lecciones", [])):
            if j >= len(lecciones_n) or lecciones_n[j].get("id") != lec_v.get("id"):
                problemas.append(f"lección {lec_v.get('id')}: falta o cambió de lugar")
                continue
            pasos_n = lecciones_n[j].get("pasos", [])
            for k, paso_v in enumerate(lec_v.get("pasos", [])):
                if k >= len(pasos_n):
                    problemas.append(f"{lec_v['id']} paso {k}: se borró")
                    continue
                paso_n = {c: v for c, v in pasos_n[k].items() if c not in campos_nuevos or c in paso_v}
                if paso_n != paso_v:
                    problemas.append(f"{lec_v['id']} paso {k}: cambió (solo se pueden agregar pasos al final)")
    return problemas


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ref")
    parser.add_argument("cursos", nargs="+")
    parser.add_argument("--campos-nuevos", nargs="*", default=[])
    args = parser.parse_args()
    total = 0
    for curso_id in args.cursos:
        nuevo = json.loads((RAIZ / "contenido" / "cursos" / f"{curso_id}.json").read_text(encoding="utf-8"))
        problemas = comparar(_curso_en(args.ref, curso_id), nuevo, set(args.campos_nuevos))
        for p in problemas:
            print(f"❌ {curso_id}: {p}")
        total += len(problemas)
        if not problemas:
            print(f"✅ {curso_id}: solo agregados")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
