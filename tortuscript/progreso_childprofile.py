"""Adaptador de progreso para ChildProfile.

Los perfiles comerciales usan un identificador interno estable como propietario
del archivo de progreso. Los perfiles locales existentes siguen utilizando
progreso_<perfil>.json y no se migran automáticamente.

Este adaptador todavía no forma parte del flujo HTTP; es la pieza de persistencia
que permite incorporarlo sin hacer que la identidad comercial conozca los detalles
del formato educativo.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .progreso_contrato import PROGRESS_CONTRACT_VERSION, ProgresoSnapshot, importar_snapshot, nuevo_snapshot

logger = logging.getLogger(__name__)


_PROFILE_ID_RE = re.compile(r"^child_[a-f0-9]{24}$")


class ProgresoPerfilError(ValueError):
    """Error de almacenamiento de progreso asociado a un ChildProfile."""


class ProgresoChildProfile:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    def _validar(self, profile_id: str) -> str:
        if not isinstance(profile_id, str) or not _PROFILE_ID_RE.fullmatch(profile_id):
            raise ProgresoPerfilError("profile_id no tiene el formato interno esperado.")
        return profile_id

    def _archivo(self, profile_id: str) -> Path:
        profile_id = self._validar(profile_id)
        return self.directory / f"progreso_{profile_id}.json"

    def cargar(self, profile_id: str) -> ProgresoSnapshot | None:
        archivo = self._archivo(profile_id)
        if not archivo.exists():
            return None
        try:
            return self._leer(archivo, profile_id)
        except ProgresoPerfilError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise ProgresoPerfilError("El progreso asociado al perfil no es válido.") from exc

    def _leer(self, archivo: Path, profile_id: str) -> ProgresoSnapshot:
        snapshot = importar_snapshot(json.loads(archivo.read_text(encoding="utf-8")))
        if snapshot.profile_id != profile_id:
            raise ProgresoPerfilError("El identificador del progreso no coincide con el archivo propietario.")
        return snapshot

    def _es_de_version_futura(self, archivo: Path) -> bool:
        try:
            version = json.loads(archivo.read_text(encoding="utf-8")).get("contract_version")
        except (OSError, ValueError, AttributeError):
            return False
        return type(version) is int and version > PROGRESS_CONTRACT_VERSION

    def cargar_o_recuperar(self, profile_id: str) -> ProgresoSnapshot | None:
        """Como `cargar`, pero un archivo dañado no deja al perfil inutilizable.

        El archivo ilegible se aparta como `.corrupto-<fecha>` (nunca se borra) y se
        restaura el `.bak` si es válido y del mismo perfil; si no hay respaldo válido
        devuelve None y el perfil empieza de cero. Un archivo escrito por una versión
        más nueva del programa NO se considera dañado: se rechaza sin tocarlo.
        """
        archivo = self._archivo(profile_id)
        try:
            return self.cargar(profile_id)
        except ProgresoPerfilError as exc:
            if self._es_de_version_futura(archivo):
                raise
            marca = datetime.now().strftime("%Y%m%d-%H%M%S")
            apartado = archivo.with_name(f"{archivo.name}.corrupto-{marca}")
            # Sin datos del alumno en el log: solo el identificador opaco y la causa.
            logger.error("Progreso dañado del perfil %s (%s): se aparta como %s", profile_id, exc.__cause__ or exc,
                         apartado.name)
            try:
                os.replace(archivo, apartado)
            except OSError as e:
                logger.error("No se pudo apartar el progreso dañado: %s", e, exc_info=True)
                raise ProgresoPerfilError("El progreso asociado al perfil no es válido.") from e
        respaldo = archivo.with_name(archivo.name + ".bak")
        if not respaldo.exists():
            return None
        try:
            snapshot = self._leer(respaldo, profile_id)
        except (OSError, ValueError, TypeError) as e:
            logger.error("El respaldo del perfil %s también está dañado: %s", profile_id, e)
            return None
        shutil.copy2(respaldo, archivo)
        logger.warning("Progreso del perfil %s recuperado desde %s", profile_id, respaldo.name)
        return snapshot

    def guardar(self, snapshot: ProgresoSnapshot) -> None:
        snapshot.validar()
        archivo = self._archivo(snapshot.profile_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(
                prefix=".progreso_child_",
                suffix=".tmp",
                dir=str(self.directory),
            )
            documento = {
                "contract_version": snapshot.schema_version,
                "profile_id": snapshot.profile_id,
                "updated_at": snapshot.updated_at,
                "data": copy.deepcopy(snapshot.data),
            }
            with os.fdopen(fd, "w", encoding="utf-8") as salida:
                json.dump(documento, salida, ensure_ascii=False, indent=2)
                salida.flush()
                os.fsync(salida.fileno())
            if archivo.exists():
                shutil.copy2(archivo, archivo.with_name(archivo.name + ".bak"))
            os.replace(tmp, archivo)
        except OSError as exc:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
            raise ProgresoPerfilError("No se pudo guardar el progreso del perfil.") from exc

    def crear_si_no_existe(self, profile_id: str, data: dict) -> ProgresoSnapshot:
        actual = self.cargar(profile_id)
        if actual is not None:
            return actual
        snapshot = nuevo_snapshot(profile_id, data)
        self.guardar(snapshot)
        return snapshot
