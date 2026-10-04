"""
Dónde vive cada cosa, en cualquier sistema (ADR-015: construcción agnóstica).

- Desde el código fuente (desarrollo o el .zip con Python): los datos siguen junto al programa, como siempre.
- Instalado (ejecutable armado con PyInstaller, "congelado"): el programa puede estar en una carpeta de solo lectura,
  así que el progreso, la configuración y los logs van a la carpeta de datos del usuario de cada sistema.
- TORTUSCRIPT_DATOS (variable de entorno) fuerza otra carpeta: sirve para pruebas y para una instalación portátil.

Lo único que cambia entre sistemas está en `carpeta_de_usuario()`: el resto del programa no pregunta el sistema.
"""
import logging
import os
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("tortuscript.rutas")

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "TortuScript"
# Lo que es del chico y hay que llevar si el programa cambia de lugar (nunca se mueve: se copia)
DATOS_DEL_CHICO = ("progreso_*.json", "progreso_*.json.bak", "config_tortuscript.json")


def sistema():
    """"linux", "windows" o "macos" (otro Unix cuenta como linux)."""
    nombre = platform.system().lower()
    return {"darwin": "macos"}.get(nombre, nombre if nombre in ("windows", "linux") else "linux")


def congelado():
    """True si corre como ejecutable armado (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def carpeta_del_programa():
    """La carpeta donde está el ejecutable (congelado) o el proyecto (código fuente)."""
    return Path(sys.executable).resolve().parent if congelado() else RAIZ


def carpeta_de_usuario(nombre_sistema=None, entorno=None, casa=None):
    """La carpeta de datos del usuario según el sistema."""
    nombre_sistema = nombre_sistema or sistema()
    entorno = os.environ if entorno is None else entorno
    casa = Path(casa) if casa else Path.home()
    if nombre_sistema == "windows":
        return Path(entorno.get("APPDATA") or casa / "AppData" / "Roaming") / NOMBRE
    if nombre_sistema == "macos":
        return casa / "Library" / "Application Support" / NOMBRE
    return Path(entorno.get("XDG_DATA_HOME") or casa / ".local" / "share") / NOMBRE.lower()


def carpeta_de_datos(entorno=None):
    entorno = os.environ if entorno is None else entorno
    if entorno.get("TORTUSCRIPT_DATOS"):
        return Path(entorno["TORTUSCRIPT_DATOS"])
    return carpeta_de_usuario(entorno=entorno) if congelado() else RAIZ


def carpeta_de_cuentas(datos=None):
    """Donde viven la base de cuentas y el progreso por ChildProfile: `instance/` dentro de la carpeta de datos.
    Desde el código fuente coincide con la carpeta `instance/` de Flask; instalado, queda en la carpeta del usuario
    (la del programa puede ser de solo lectura y el desinstalador la borra)."""
    return Path(datos if datos is not None else carpeta_de_datos()) / "instance"


def copiar_datos_viejos(origen, destino):
    """Si `destino` todavía no tiene progreso y `origen` sí, copia lo del chico (nunca pisa ni borra nada).
    Devuelve los nombres copiados."""
    origen, destino = Path(origen), Path(destino)
    if origen.resolve() == destino.resolve() or any(destino.glob("progreso_*.json")):
        return []
    copiados = []
    for patron in DATOS_DEL_CHICO:
        for archivo in origen.glob(patron):
            if archivo.is_file() and not (destino / archivo.name).exists():
                shutil.copy2(archivo, destino / archivo.name)
                copiados.append(archivo.name)
    return sorted(copiados)


def preparar_carpeta_de_datos(entorno=None):
    """Crea la carpeta de datos y trae el progreso que hubiera junto al programa. Devuelve la carpeta."""
    datos = carpeta_de_datos(entorno)
    datos.mkdir(parents=True, exist_ok=True)
    try:
        copiados = copiar_datos_viejos(carpeta_del_programa(), datos)
        if copiados:
            logger.warning("Progreso copiado a %s: %s", datos, ", ".join(copiados))
    except OSError as e:
        logger.error("No se pudo copiar el progreso viejo a %s: %s", datos, e, exc_info=True)
    return datos
