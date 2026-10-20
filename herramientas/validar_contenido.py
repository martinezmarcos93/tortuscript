#!/usr/bin/env python3
"""Valida todos los cursos de contenido/cursos/ sin abrir la app.

Uso:  python3 herramientas/validar_contenido.py          (todos los cursos)
      python3 herramientas/validar_contenido.py primeros-pasos

Sale con código 1 si hay errores (❌). Los avisos (⚠️) son para revisar a mano.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tortuscript.contenido import CARPETA, cargar_curso, pasos, todos_los_cursos  # noqa: E402
from tortuscript.validacion import ERROR, validar_curso, validar_transferencias  # noqa: E402
from tortuscript import proyectos_integradores  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")     # Windows: consola/pipe en cp1252
    ids = sys.argv[1:] or sorted(p.stem for p in CARPETA.glob("*.json"))
    total_errores = 0
    errores_transferencia = [h for h in validar_transferencias(todos_los_cursos()) if h.nivel == ERROR]
    if errores_transferencia:
        print("\n🔗 Transferencias")
        for h in errores_transferencia:
            print("   ", h)
        total_errores += len(errores_transferencia)
    for curso_id in ids:
        curso = cargar_curso(curso_id)
        hallazgos = validar_curso(curso)
        errores = [h for h in hallazgos if h.nivel == ERROR]
        avisos = [h for h in hallazgos if h.nivel != ERROR]
        total_errores += len(errores)
        n_pasos = len(pasos(curso))
        print(f"\n📚 {curso['titulo']} ({curso_id}) — {n_pasos} pasos revisados")
        for h in errores + avisos:
            print("   ", h)
        estado = "✅ sin errores" if not errores else f"❌ {len(errores)} error(es)"
        print(f"   {estado}, {len(avisos)} aviso(s)")
    errores_proyectos = proyectos_integradores.validar_catalogo()
    print(f"\n🧩 Proyectos integradores — {len(proyectos_integradores.cargar_catalogo())} proyectos revisados")
    for error in errores_proyectos:
        print("   ❌", error)
    total_errores += len(errores_proyectos)
    print("  ", "✅ sin errores" if not errores_proyectos else f"❌ {len(errores_proyectos)} error(es)")
    sys.exit(1 if total_errores else 0)


if __name__ == "__main__":
    main()
