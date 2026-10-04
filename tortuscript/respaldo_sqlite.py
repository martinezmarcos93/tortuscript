"""Backup y restauración segura de una base SQLite.

Estas utilidades son explícitas y no se invocan automáticamente al iniciar la app.
La restauración requiere que el consumidor detenga antes todos los escritores.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path


class ErrorRespaldo(ValueError):
    """El respaldo no se puede crear o restaurar de forma segura."""


def _validar_sqlite(path: Path) -> None:
    """Rechaza archivos ausentes, bases corruptas y archivos que no son SQLite."""
    if not path.is_file():
        raise ErrorRespaldo("El archivo SQLite no existe.")
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as con:
            resultado = con.execute("PRAGMA integrity_check").fetchone()
            if not resultado or resultado[0] != "ok":
                raise ErrorRespaldo("La base SQLite no superó la comprobación de integridad.")
            con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    except ErrorRespaldo:
        raise
    except sqlite3.DatabaseError as exc:
        raise ErrorRespaldo("El archivo no es una base SQLite válida.") from exc


def crear_respaldo(origen: str | Path, destino: str | Path) -> Path:
    """Crea una copia consistente usando la API de backup de SQLite.

    No sobrescribe destinos existentes. La copia temporal y el destino deben
    estar en el mismo directorio para que os.replace sea atómico.
    """
    src, dst = Path(origen), Path(destino)
    if not src.is_file():
        raise ErrorRespaldo("La base de origen no existe.")
    if src.resolve() == dst.resolve():
        raise ErrorRespaldo("El respaldo debe ser un archivo diferente del origen.")
    if dst.exists():
        raise ErrorRespaldo("El destino ya existe; elegí otro nombre para no sobrescribirlo.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal_nombre = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent)
    os.close(fd)
    temporal = Path(temporal_nombre)
    try:
        with sqlite3.connect(src) as origen_con, sqlite3.connect(temporal) as destino_con:
            origen_con.backup(destino_con)
        _validar_sqlite(temporal)
        if dst.exists():
            raise ErrorRespaldo("El destino apareció durante la operación; no se sobrescribió.")
        os.replace(temporal, dst)
        return dst
    except ErrorRespaldo:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ErrorRespaldo("No se pudo completar el respaldo SQLite.") from exc
    finally:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass


def restaurar_respaldo(
    respaldo: str | Path,
    destino: str | Path,
    *,
    permitir_sobrescritura: bool = False,
) -> Path:
    """Restaura un respaldo validado mediante reemplazo atómico.

    El llamador debe detener la aplicación y cualquier proceso que escriba en
    destino. Por defecto, no se permite reemplazar una base existente.
    """
    src, dst = Path(respaldo), Path(destino)
    if src.resolve() == dst.resolve():
        raise ErrorRespaldo("El respaldo y el destino deben ser archivos diferentes.")
    _validar_sqlite(src)
    if dst.exists() and not permitir_sobrescritura:
        raise ErrorRespaldo("El destino ya existe; confirmá explícitamente la sobrescritura.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal_nombre = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".restore", dir=dst.parent)
    os.close(fd)
    temporal = Path(temporal_nombre)
    try:
        with sqlite3.connect(src) as respaldo_con, sqlite3.connect(temporal) as destino_con:
            respaldo_con.backup(destino_con)
        _validar_sqlite(temporal)
        if dst.exists() and not permitir_sobrescritura:
            raise ErrorRespaldo("El destino apareció durante la restauración; no se sobrescribió.")
        os.replace(temporal, dst)
        return dst
    except ErrorRespaldo:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ErrorRespaldo("No se pudo completar la restauración SQLite.") from exc
    finally:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass
