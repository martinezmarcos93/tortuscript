"""Respaldo, verificación y restauración de los datos de las familias (cuentas + progreso).

Uso:
    python herramientas/respaldar_datos.py crear                 # nuevo respaldo en <datos>/respaldos/
    python herramientas/respaldar_datos.py listar
    python herramientas/respaldar_datos.py verificar <carpeta>
    python herramientas/respaldar_datos.py restaurar <carpeta> --confirmar

Crear y verificar no modifican los datos. Para restaurar hay que cerrar TortuScript antes; lo
que había se conserva en una carpeta `instance.antes-de-restaurar-<fecha>` (nada se borra).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript import respaldo_datos, rutas  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Respaldo de los datos de TortuScript.")
    ap.add_argument("--datos", type=Path, default=None, help="carpeta de datos (por defecto, la de la instalación)")
    ap.add_argument("--respaldos", type=Path, default=None, help="dónde guardar los respaldos (por defecto, <datos>/respaldos)")
    sub = ap.add_subparsers(dest="accion", required=True)
    sub.add_parser("crear")
    sub.add_parser("listar")
    sub.add_parser("verificar").add_argument("carpeta", type=Path)
    restaurar = sub.add_parser("restaurar")
    restaurar.add_argument("carpeta", type=Path)
    restaurar.add_argument("--confirmar", action="store_true", help="reemplazar los datos actuales (se conservan aparte)")
    args = ap.parse_args(argv)

    datos = args.datos or rutas.carpeta_de_datos()
    cuentas = rutas.carpeta_de_cuentas(datos)
    respaldos = args.respaldos or datos / "respaldos"
    try:
        if args.accion == "crear":
            carpeta = respaldo_datos.crear(cuentas, respaldos)
            r = respaldo_datos.verificar(carpeta)
            print(f"✅ Respaldo creado y verificado: {carpeta}")
            print(f"   {r['perfiles']} perfil(es), {r['perfiles_con_progreso']} con progreso, {r['bytes']} bytes.")
        elif args.accion == "listar":
            encontrados = respaldo_datos.listar(respaldos)
            for carpeta in encontrados:
                print(carpeta)
            if not encontrados:
                print(f"No hay respaldos en {respaldos}")
        elif args.accion == "verificar":
            r = respaldo_datos.verificar(args.carpeta)
            print(f"✅ Respaldo íntegro (creado {r['creado']}): {r['perfiles']} perfil(es), "
                  f"{r['perfiles_con_progreso']} con progreso, esquema v{r['esquema_de_cuentas']}.")
        else:
            anterior = respaldo_datos.restaurar(args.carpeta, cuentas, confirmar=args.confirmar)
            print(f"✅ Datos restaurados en {cuentas}")
            if anterior:
                print(f"   Lo que había quedó en {anterior}")
    except respaldo_datos.ErrorRespaldo as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
