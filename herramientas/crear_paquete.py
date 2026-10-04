#!/usr/bin/env python3
"""Arma un .zip instalable de TortuScript para llevar a otra compu (sin git ni el entorno de desarrollo).

Uso:  python herramientas/crear_paquete.py [--salida dist] [--con-ruedas]

- Incluye la app (tortuscript/, web/, contenido/), el lanzador, los accesos directos, la
  documentación y las herramientas. NO incluye tests, git, entornos virtuales, logs ni ningún
  progreso de los chicos (progreso_*.json, config_tortuscript.json).
- Agrega INSTALAR.txt, instalar.bat e instalar.sh: crean el entorno e instalan Flask.
- Con --con-ruedas también trae las ruedas (wheels) de Flask y sus dependencias en wheels/, para
  instalar sin internet (sirven para el mismo sistema y la misma versión de Python que esta compu).
- Deja al lado un .sha256 para comprobar que el archivo llegó entero.
"""
import argparse
import hashlib
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAIZ_DEL_ZIP = "TortuScript"

# Lo que va en el paquete (carpetas completas y archivos sueltos)
INCLUIR_CARPETAS = ("tortuscript", "web", "contenido", "lanzadores", "docs", "herramientas")
INCLUIR_ARCHIVOS = ("iniciar_web.py", "requirements.txt", "requirements.lock", "README.md", "CHANGELOG.md", ".env.example")
# Lo que NUNCA va (datos privados, basura de desarrollo)
EXCLUIR_PARTES = {"__pycache__", ".git", ".venv", "venv", "logs", "dist", ".claude", "tests", ".pytest_cache"}
EXCLUIR_PATRONES = ("*.pyc", "*.pyo", "progreso_*.json", "progreso_*.json.*", "config_tortuscript.json", "*.bak", "*.tmp")

INSTALAR_TXT = """TortuScript — instalación
=========================

Necesitás Python 3.9 o más nuevo (https://www.python.org/downloads/).

Windows:  doble clic en instalar.bat   (una sola vez)
Linux/macOS:  sh instalar.sh           (una sola vez)

Después, para usar la app:
  Windows:  doble clic en "lanzadores\\Iniciar TortuScript.bat"
  Linux/macOS:  sh lanzadores/iniciar_tortuscript.sh

Se abre en tu navegador. Funciona sin internet: solo se necesita la primera vez, para instalar Flask
{nota_ruedas}
El progreso de cada chico se guarda en esta carpeta, en archivos progreso_<nombre>.json.
Para llevar el progreso a otra compu, copiá esos archivos.
"""

INSTALAR_BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Creando el entorno...
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% -m venv .venv || goto :error
{instalacion_bat}
if errorlevel 1 goto :error
echo.
echo Listo. Ahora abri "lanzadores\\Iniciar TortuScript.bat".
pause
exit /b 0
:error
echo.
echo Algo salio mal. Revisa que tengas Python 3.9 o mas nuevo instalado.
pause
exit /b 1
"""

INSTALAR_SH = """#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
echo "Creando el entorno..."
python3 -m venv .venv || {{ echo "Revisá que tengas Python 3.9 o más nuevo y python3-venv."; exit 1; }}
{instalacion_sh} || {{ echo "No se pudo instalar Flask."; exit 1; }}
echo "Listo. Ahora corré: sh lanzadores/iniciar_tortuscript.sh"
"""


def _excluido(ruta):
    partes = set(ruta.parts)
    return bool(partes & EXCLUIR_PARTES) or any(ruta.match(p) for p in EXCLUIR_PATRONES)


def archivos_del_paquete(raiz=RAIZ):
    """Rutas (relativas a `raiz`) de lo que entra en el paquete, ordenadas."""
    raiz = Path(raiz)
    hallados = set()
    for carpeta in INCLUIR_CARPETAS:
        base = raiz / carpeta
        if base.is_dir():
            hallados.update(p.relative_to(raiz) for p in base.rglob("*") if p.is_file())
    for nombre in INCLUIR_ARCHIVOS:
        if (raiz / nombre).is_file():
            hallados.add(Path(nombre))
    return sorted(p for p in hallados if not _excluido(p))


def _commit_actual(raiz):
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(raiz), capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _requisitos(raiz):
    """(archivo, opción extra) para instalar: el lock con hashes si existe (versiones exactas y archivos verificados);
    si no, requirements.txt como antes."""
    if (Path(raiz) / "requirements.lock").is_file():
        return "requirements.lock", " --require-hashes"
    return "requirements.txt", ""


def _descargar_ruedas(destino, raiz):
    archivo, _ = _requisitos(raiz)
    subprocess.run([sys.executable, "-m", "pip", "download", "-r", str(Path(raiz) / archivo), "-d", str(destino),
                    "--only-binary=:all:"], check=True)


def crear_paquete(raiz=RAIZ, salida=None, con_ruedas=False, hoy=None):
    """Crea el .zip y su .sha256. Devuelve la ruta del .zip."""
    raiz = Path(raiz)
    salida = Path(salida) if salida else raiz / "dist"
    salida.mkdir(parents=True, exist_ok=True)
    hoy = hoy or date.today()
    zip_ruta = salida / f"TortuScript-{hoy:%Y%m%d}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        ruedas = []
        if con_ruedas:
            carpeta = Path(tmp) / "wheels"
            carpeta.mkdir()
            _descargar_ruedas(carpeta, raiz)
            ruedas = sorted(carpeta.glob("*"))
        nota = ("Este paquete trae las ruedas de Flask en wheels/: se instala sin internet."
                if ruedas else "(si no hay internet, generá el paquete con --con-ruedas).")
        archivo, verificar = _requisitos(raiz)
        bat = (f"%PY% -m pip install --no-index --find-links wheels{verificar} -r {archivo}" if ruedas
               else f".venv\\Scripts\\python.exe -m pip install{verificar} -r {archivo}")
        sh = (f'.venv/bin/python -m pip install --no-index --find-links wheels{verificar} -r {archivo}' if ruedas
              else f'.venv/bin/python -m pip install{verificar} -r {archivo}')
        if ruedas:
            bat = bat.replace("%PY%", ".venv\\Scripts\\python.exe")
        extras = {
            "INSTALAR.txt": INSTALAR_TXT.format(nota_ruedas=nota),
            "instalar.bat": INSTALAR_BAT.format(instalacion_bat=bat).replace("\n", "\r\n"),
            "instalar.sh": INSTALAR_SH.format(instalacion_sh=sh),
            "VERSION.txt": f"TortuScript, armado el {hoy:%d/%m/%Y}" + (f", commit {_commit_actual(raiz)}" if _commit_actual(raiz) else "") + "\n",
        }
        with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in archivos_del_paquete(raiz):
                z.write(raiz / rel, f"{CARPETA_RAIZ_DEL_ZIP}/{rel.as_posix()}")
            for nombre, contenido in extras.items():
                z.writestr(f"{CARPETA_RAIZ_DEL_ZIP}/{nombre}", contenido)
            for rueda in ruedas:
                z.write(rueda, f"{CARPETA_RAIZ_DEL_ZIP}/wheels/{rueda.name}")

    huella = hashlib.sha256(zip_ruta.read_bytes()).hexdigest()
    (salida / (zip_ruta.name + ".sha256")).write_text(f"{huella}  {zip_ruta.name}\n", encoding="utf-8")
    return zip_ruta


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Arma el paquete instalable de TortuScript.")
    ap.add_argument("--salida", default=None, help="carpeta de salida (por defecto dist/)")
    ap.add_argument("--con-ruedas", action="store_true", help="incluir Flask y sus dependencias para instalar sin internet")
    args = ap.parse_args()
    ruta = crear_paquete(RAIZ, args.salida, args.con_ruedas)
    with zipfile.ZipFile(ruta) as z:
        n = len(z.namelist())
    print(f"📦 {ruta}  ({n} archivos, {ruta.stat().st_size // 1024} KB)")
    print(f"   sha256 en {ruta.name}.sha256")


if __name__ == "__main__":
    main()
