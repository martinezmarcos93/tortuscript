"""Respaldo completo de los datos de las familias: cuentas (SQLite) + progreso por perfil (JSON).

`respaldo_sqlite` copia solo la base; el progreso de cada ChildProfile vive en archivos
aparte y un respaldo que no los incluya no sirve para recuperar nada. Aquí un respaldo es
una carpeta con todo y un MANIFIESTO con el hash de cada archivo, que permite verificarla
antes de confiar en ella.

Reglas:
- Nunca se invoca solo: lo corre una persona con `herramientas/respaldar_datos.py`.
- Crear y verificar no modifican los datos de origen.
- Restaurar exige confirmación si el destino tiene datos, y lo que había se aparta
  (`<destino>.antes-de-restaurar-<fecha>`): nada se borra.
- Para restaurar hay que detener la aplicación antes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .progreso_contrato import ProgresoContratoError, importar_snapshot
from .respaldo_sqlite import ErrorRespaldo, _validar_sqlite, crear_respaldo

FORMATO = "tortuscript-respaldo"
VERSION = 1
BASE = "cuentas.sqlite3"
PROGRESO = "progreso_perfiles"
MANIFIESTO = "MANIFIESTO.json"

__all__ = ["ErrorRespaldo", "crear", "verificar", "restaurar", "listar"]


def _sha256(archivo: Path) -> str:
    h = hashlib.sha256()
    with open(archivo, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _archivos_de_progreso(carpeta: Path) -> list[Path]:
    """Solo los progresos vigentes: ni los .bak ni los apartados por corrupción ni temporales."""
    if not carpeta.is_dir():
        return []
    return sorted(p for p in carpeta.glob("progreso_child_*.json") if p.is_file())


def _perfiles_de_la_base(base: Path) -> set[str]:
    uri = base.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        try:
            return {fila[0] for fila in con.execute("SELECT id FROM child_profiles")}
        except sqlite3.DatabaseError as exc:
            raise ErrorRespaldo("La base de cuentas no tiene la tabla de perfiles.") from exc


def _version_de_esquema(base: Path):
    uri = base.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        try:
            fila = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
        except sqlite3.DatabaseError:
            return None
    return fila[0] if fila else None


def crear(origen: str | Path, carpeta_de_respaldos: str | Path, ahora: datetime | None = None) -> Path:
    """Crea `carpeta_de_respaldos/respaldo-<fecha>/` con la base, el progreso y el manifiesto.

    `origen` es la carpeta de cuentas (la `instance/` de la carpeta de datos). No se modifica.
    El respaldo se arma en una carpeta temporal y se publica renombrándola: una interrupción
    no deja un respaldo a medias con nombre de respaldo válido.
    """
    origen, raiz = Path(origen), Path(carpeta_de_respaldos)
    base = origen / BASE
    if not base.is_file():
        raise ErrorRespaldo("No hay base de cuentas para respaldar en esa carpeta.")
    progreso = (origen / PROGRESO).resolve()
    if raiz.resolve() == progreso or progreso in raiz.resolve().parents:
        raise ErrorRespaldo("Los respaldos no pueden guardarse dentro de la carpeta de progreso.")
    ahora = ahora or datetime.now(timezone.utc)
    nombre = "respaldo-" + ahora.strftime("%Y%m%d-%H%M%S")
    destino = raiz / nombre
    if destino.exists():
        raise ErrorRespaldo("Ya existe un respaldo con esa fecha y hora; probá de nuevo en un segundo.")
    temporal = raiz / f".{nombre}.incompleto"
    if temporal.exists():
        shutil.rmtree(temporal)
    try:
        (temporal / PROGRESO).mkdir(parents=True)
        crear_respaldo(base, temporal / BASE)                      # copia consistente aunque la app esté escribiendo
        for archivo in _archivos_de_progreso(origen / PROGRESO):
            shutil.copy2(archivo, temporal / PROGRESO / archivo.name)
        archivos = {}
        for archivo in [temporal / BASE] + _archivos_de_progreso(temporal / PROGRESO):
            relativo = archivo.relative_to(temporal).as_posix()
            archivos[relativo] = {"sha256": _sha256(archivo), "bytes": archivo.stat().st_size}
        manifiesto = {
            "formato": FORMATO, "version": VERSION, "creado": ahora.isoformat(timespec="seconds"),
            "esquema_de_cuentas": _version_de_esquema(temporal / BASE), "archivos": archivos,
        }
        (temporal / MANIFIESTO).write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
        verificar(temporal)                                        # no se publica un respaldo que no se puede leer
        os.rename(temporal, destino)
    except OSError as exc:
        shutil.rmtree(temporal, ignore_errors=True)
        raise ErrorRespaldo(f"No se pudo crear el respaldo: {exc}") from exc
    except ErrorRespaldo:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    return destino


def verificar(respaldo: str | Path) -> dict:
    """Comprueba un respaldo sin modificarlo y devuelve un resumen. Lanza ErrorRespaldo si no es confiable.

    Verifica: manifiesto, que no falte ni sobre ningún archivo, hash y tamaño de cada uno, integridad
    de la base, que cada progreso sea un snapshot válido de su propio perfil y que ese perfil exista.
    """
    respaldo = Path(respaldo)
    try:
        manifiesto = json.loads((respaldo / MANIFIESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErrorRespaldo("La carpeta no es un respaldo de TortuScript (falta el manifiesto o está dañado).") from exc
    if not isinstance(manifiesto, dict) or manifiesto.get("formato") != FORMATO:
        raise ErrorRespaldo("La carpeta no es un respaldo de TortuScript.")
    if type(manifiesto.get("version")) is not int or manifiesto["version"] > VERSION:
        raise ErrorRespaldo("El respaldo fue creado por una versión más nueva de TortuScript.")
    declarados = manifiesto.get("archivos")
    if not isinstance(declarados, dict) or BASE not in declarados:
        raise ErrorRespaldo("El manifiesto del respaldo no es válido.")
    presentes = {p.relative_to(respaldo).as_posix() for p in respaldo.rglob("*") if p.is_file()} - {MANIFIESTO}
    if presentes != set(declarados):
        faltan, sobran = sorted(set(declarados) - presentes), sorted(presentes - set(declarados))
        raise ErrorRespaldo(f"El respaldo no coincide con su manifiesto (faltan: {faltan}; sobran: {sobran}).")
    for relativo, dato in declarados.items():
        # El manifiesto es una entrada de afuera: ninguna ruta puede salir de la carpeta del respaldo.
        if relativo != BASE and not (relativo.startswith(PROGRESO + "/") and "/" not in relativo[len(PROGRESO) + 1:]):
            raise ErrorRespaldo(f"El manifiesto nombra un archivo inesperado: {relativo}")
        archivo = respaldo / relativo
        if not isinstance(dato, dict) or archivo.stat().st_size != dato.get("bytes") or _sha256(archivo) != dato.get("sha256"):
            raise ErrorRespaldo(f"El archivo {relativo} cambió desde que se creó el respaldo.")
    _validar_sqlite(respaldo / BASE)
    perfiles = _perfiles_de_la_base(respaldo / BASE)
    con_progreso = set()
    for archivo in _archivos_de_progreso(respaldo / PROGRESO):
        try:
            snapshot = importar_snapshot(json.loads(archivo.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, ProgresoContratoError) as exc:
            raise ErrorRespaldo(f"El progreso {archivo.name} del respaldo no es válido.") from exc
        if archivo.name != f"progreso_{snapshot.profile_id}.json":
            raise ErrorRespaldo(f"El progreso {archivo.name} pertenece a otro perfil.")
        if snapshot.profile_id not in perfiles:
            raise ErrorRespaldo(f"El progreso {archivo.name} no corresponde a ningún perfil de la base.")
        con_progreso.add(snapshot.profile_id)
    return {
        "creado": manifiesto.get("creado"), "esquema_de_cuentas": manifiesto.get("esquema_de_cuentas"),
        "perfiles": len(perfiles), "perfiles_con_progreso": len(con_progreso),
        "archivos": len(declarados), "bytes": sum(d["bytes"] for d in declarados.values()),
    }


def listar(carpeta_de_respaldos: str | Path) -> list[Path]:
    raiz = Path(carpeta_de_respaldos)
    return sorted(p for p in raiz.glob("respaldo-*") if (p / MANIFIESTO).is_file()) if raiz.is_dir() else []


def restaurar(respaldo: str | Path, destino: str | Path, *, confirmar: bool = False,
              ahora: datetime | None = None) -> Path | None:
    """Deja `destino` (la carpeta de cuentas) igual al respaldo. La aplicación debe estar detenida.

    Si `destino` ya tiene datos hace falta `confirmar=True`, y la carpeta anterior se conserva entera
    como `<destino>.antes-de-restaurar-<fecha>`. Devuelve esa carpeta (o None si no había nada).
    El respaldo se verifica antes de tocar el destino y la restauración se verifica antes de publicarla.
    """
    respaldo, destino = Path(respaldo), Path(destino)
    verificar(respaldo)
    if destino.resolve() == respaldo.resolve() or respaldo.resolve() in destino.resolve().parents:
        raise ErrorRespaldo("No se puede restaurar un respaldo sobre sí mismo.")
    hay_datos = destino.exists() and any(destino.iterdir())
    if hay_datos and not confirmar:
        raise ErrorRespaldo("El destino ya tiene datos; confirmá explícitamente la restauración.")
    marca = (ahora or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    nuevo = destino.with_name(f".{destino.name}.restaurando-{marca}")
    anterior = destino.with_name(f"{destino.name}.antes-de-restaurar-{marca}")
    if nuevo.exists() or anterior.exists():
        raise ErrorRespaldo("Ya hay una restauración con esa fecha y hora; probá de nuevo en un segundo.")
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        (nuevo / PROGRESO).mkdir(parents=True)
        shutil.copy2(respaldo / BASE, nuevo / BASE)                # el respaldo está quieto: copia byte a byte
        for archivo in _archivos_de_progreso(respaldo / PROGRESO):
            shutil.copy2(archivo, nuevo / PROGRESO / archivo.name)
        shutil.copy2(respaldo / MANIFIESTO, nuevo / MANIFIESTO)
        verificar(nuevo)                                           # lo copiado es idéntico a lo respaldado
        (nuevo / MANIFIESTO).unlink()
        if destino.exists():
            os.rename(destino, anterior)
        try:
            os.rename(nuevo, destino)
        except OSError:
            if anterior.exists():                                  # no dejar la instalación sin datos
                os.rename(anterior, destino)
            raise
    except OSError as exc:
        shutil.rmtree(nuevo, ignore_errors=True)
        raise ErrorRespaldo(f"No se pudo restaurar el respaldo: {exc}") from exc
    except ErrorRespaldo:
        shutil.rmtree(nuevo, ignore_errors=True)
        raise
    return anterior if anterior.exists() else None
