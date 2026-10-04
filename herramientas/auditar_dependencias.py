#!/usr/bin/env python3
"""Dependencias de la app: lockfile con hashes y auditoría de vulnerabilidades (solo biblioteca estándar).

Uso:
    python herramientas/auditar_dependencias.py                 # consulta OSV por las versiones de requirements.lock
    python herramientas/auditar_dependencias.py --generar-lock  # rearma requirements.lock desde el entorno actual

- requirements.txt dice qué usa la app (Flask). requirements.lock fija TODAS las versiones, también las que Flask
  arrastra, con los hashes que publica PyPI: `pip install --require-hashes -r requirements.lock` rechaza cualquier
  archivo alterado. Se incluyen los hashes de todos los archivos de cada versión (sirve en Linux y en Windows).
- Necesita internet (PyPI y api.osv.dev). Sale con código 1 si hay vulnerabilidades conocidas.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOCK = RAIZ / "requirements.lock"
# Vulnerabilidades conocidas con un tratamiento aceptado y escrito. Cada entrada dice por qué no aplica y cuándo
# deja de valer; una vulnerabilidad nueva del mismo paquete vuelve a fallar. Revisar al cambiar de versión.
ACEPTADAS = {
    ("click", "PYSEC-2026-2132"): (
        "inyección de comandos en click.edit() (CVE-2026-7246, local y con privilegios). TortuScript no llama a "
        "click.edit ni usa la CLI de Flask; click solo está porque Flask lo requiere. Se corrige en click 8.3.3, "
        "que exige Python 3.10: actualizar cuando se deje de soportar Python 3.9."),
}
_LINEA = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")


def leer_lock(texto):
    """[(paquete, versión)] de un requirements.lock (ignora comentarios y líneas de hash)."""
    return [(m.group(1), m.group(2)) for linea in texto.splitlines() if (m := _LINEA.match(linea.strip()))]


def _json(url, datos=None):
    pedido = urllib.request.Request(url, data=json.dumps(datos).encode() if datos else None,
                                    headers={"Content-Type": "application/json"} if datos else {})
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return json.load(r)


def hashes_de_pypi(paquete, version):
    datos = _json(f"https://pypi.org/pypi/{paquete}/{version}/json")
    return sorted({f["digests"]["sha256"] for f in datos["urls"]})


def _nombre_canonico(paquete):
    """Normaliza el nombre según PEP 503 para comparar guiones, puntos y guiones bajos."""
    return re.sub(r"[-_.]+", "-", paquete).lower()


def instalados():
    salida = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True).stdout
    # pip freeze puede escribir importlib_metadata, mientras PyPI/requirements usa
    # importlib-metadata. Conservamos la grafía existente para que el lock sea estable.
    existentes = {}
    if LOCK.exists():
        existentes = {_nombre_canonico(p): p for p, _ in leer_lock(LOCK.read_text(encoding="utf-8"))}
    return [(existentes.get(_nombre_canonico(p), p), v) for p, v in leer_lock(salida)]


def generar_lock():
    lineas = ["# Generado por herramientas/auditar_dependencias.py --generar-lock. No editar a mano.",
              "# Instalar verificando hashes:  python -m pip install --require-hashes -r requirements.lock"]
    for paquete, version in sorted(instalados(), key=lambda x: x[0].lower()):
        hashes = hashes_de_pypi(paquete, version)
        lineas.append(f"{paquete}=={version} \\")
        lineas.extend(f"    --hash=sha256:{h}" + (" \\" if i < len(hashes) - 1 else "") for i, h in enumerate(hashes))
    LOCK.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"escrito {LOCK.name}: {len(instalados())} paquetes")


def auditar():
    paquetes = leer_lock(LOCK.read_text(encoding="utf-8"))
    consultas = [{"package": {"name": p, "ecosystem": "PyPI"}, "version": v} for p, v in paquetes]
    resultados = _json("https://api.osv.dev/v1/querybatch", {"queries": consultas})["results"]
    hallazgos = [(p, v, [x["id"] for x in r.get("vulns", [])]) for (p, v), r in zip(paquetes, resultados) if r.get("vulns")]
    sin_tratar = 0
    for p, v, ids in hallazgos:
        nuevas = [i for i in ids if (p, i) not in ACEPTADAS]
        sin_tratar += bool(nuevas)
        if nuevas:
            print(f"⚠️  {p}=={v}: {', '.join(nuevas)}")
        for i in ids:
            if (p, i) in ACEPTADAS:
                print(f"ℹ️  {p}=={v}: {i} — riesgo aceptado: {ACEPTADAS[(p, i)]}")
    print(f"{len(paquetes)} paquetes revisados en OSV: {sin_tratar} con vulnerabilidades sin tratar, "
          f"{len(hallazgos) - sin_tratar} con riesgo aceptado")
    return 1 if sin_tratar else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generar-lock", action="store_true")
    args = ap.parse_args()
    if args.generar_lock:
        generar_lock()
        return 0
    return auditar()


if __name__ == "__main__":
    sys.exit(main())
