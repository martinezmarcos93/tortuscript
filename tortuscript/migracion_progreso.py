"""Puente explícito entre progreso local legado y progreso por ChildProfile.

No se ejecuta automáticamente. Una cuenta autenticada debe solicitar la importación
de un perfil local concreto y el servicio copia sus datos al ChildProfile activo.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tortuscript.perfil_educativo import PerfilEducativoService, ContextoEducativoError
from tortuscript import persistencia_local
from tortuscript.persistencia_local import obtener_perfiles, sanitizar_perfil
from tortuscript.progreso_contrato import nuevo_snapshot


class MigracionProgresoError(ValueError):
    """La migración explícita de progreso no puede realizarse."""


class MigracionProgresoLocal:
    def __init__(self, educativo: PerfilEducativoService):
        self.educativo = educativo

    def importar_local(self, raw_session: str | None, perfil_local: str, reemplazar: bool = False):
        if not isinstance(perfil_local, str):
            raise MigracionProgresoError("El nombre del perfil local no es válido.")
        nombre = sanitizar_perfil(perfil_local)
        normalizado = perfil_local.strip().lower().replace(" ", "_")
        if not nombre or nombre != normalizado:
            raise MigracionProgresoError("El nombre del perfil local no es válido.")

        # No permitir que un nombre inexistente se convierta silenciosamente en
        # un perfil vacío: cargar_progreso() crea el progreso inicial si falta.
        if nombre not in obtener_perfiles():
            raise MigracionProgresoError("El perfil local solicitado no existe.")

        contexto = self.educativo.contexto(raw_session)
        actual = self.educativo.cargar_progreso(raw_session)
        if actual is not None and not reemplazar:
            raise MigracionProgresoError("El perfil comercial ya tiene progreso; se requiere reemplazo explícito.")
        # Lectura estricta: cargar_progreso() aparta el archivo dañado y devuelve un
        # progreso vacío, lo que aquí reemplazaría datos comerciales por nada. Un
        # archivo ilegible se rechaza sin tocarlo; los campos anidados mal tipados
        # de un JSON válido sí se normalizan, igual que en la carga local.
        try:
            datos = persistencia_local._migrar(
                persistencia_local._leer(persistencia_local.get_archivo_progreso(nombre))
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise MigracionProgresoError("El progreso local no tiene un formato válido.") from exc
        datos.pop("_perfil", None)
        snapshot = nuevo_snapshot(contexto.perfil.id, deepcopy(datos))
        self.educativo.guardar_progreso(raw_session, snapshot)
        return snapshot

    def listar_locales(self, raw_session: str | None) -> list[str]:
        self.educativo.contexto(raw_session)
        return obtener_perfiles()