#!/usr/bin/env python3
"""Informe de métricas pedagógicas locales (P6).

Uso: python3 herramientas/informe_pedagogico.py RUTA_PROGRESO.json
"""
import json
import sys
import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tortuscript import metricas_pedagogicas, contenido, dominio

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("progreso", type=Path, help="Ruta al archivo de progreso JSON")
    args = parser.parse_args()

    if not args.progreso.exists():
        print(f"Error: No existe {args.progreso}")
        return 1

    with open(args.progreso, "r", encoding="utf-8") as f:
        progreso_data = json.load(f)

    metricas = metricas_pedagogicas.metricas(
        progreso_data, 
        contenido.todos_los_cursos(), 
        dominio.cargar_mapa()
    )

    print(f"--- Informe Pedagógico para {args.progreso.name} ---\n")
    
    pr = metricas["pasos_rapidos"]
    print("## Pasos rápidos")
    print(f"- Total: {pr['total']}")
    print(f"- Primer intento: {pr['primer_intento']}")
    print(f"- Con reintentos: {pr['con_reintentos']}")
    print(f"- Ayudados: {pr['ayudados']}")
    print()

    es = metricas["escribir"]
    print("## Producción (Escribir)")
    print(f"- Total: {es['total']}")
    print(f"- Autónomos: {es['autonomos']}")
    print(f"- Con ayuda: {es['con_ayuda']}")
    print()

    re = metricas["repaso"]
    print("## Repaso")
    print(f"- Tarjetas: {re['tarjetas']}")
    print(f"- Aciertos: {re['aciertos']}")
    print(f"- Fallos: {re['fallos']}")
    print(f"- Tasa de acierto: {re['tasa_acierto']}")
    print(f"- Retenidas: {re['retenidas']}")
    print()

    co = metricas["conceptos"]
    print("## Estado de conceptos")
    for estado, cant in co.items():
        print(f"- {estado.replace('_', ' ').capitalize()}: {cant}")
    print()

    reco = metricas["recomendaciones"]
    print("## Recomendaciones")
    if not reco:
        print("- Ninguna")
    for uid, r in reco.items():
        print(f"- `{uid}`: {r}")
    
    if metricas["datos_danados"] > 0:
        print(f"\n[!] Registros de datos dañados detectados: {metricas['datos_danados']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
