"""Contexto educativo autenticado: une sesión, ChildProfile, progreso y acceso comercial.

Esta capa es la frontera entre la identidad comercial y el núcleo educativo.
El progreso siempre se resuelve por ChildProfile.id y nunca por email o nombre.
"""
from __future__ import annotations

from dataclasses import dataclass

from tortuscript.acceso import AccesoError, AccesoProducto
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import Account, ChildProfile, CuentaRepository
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import ProgresoSnapshot


class ContextoEducativoError(ValueError):
    """La sesión no puede operar sobre un contexto educativo válido."""


@dataclass(frozen=True)
class ContextoEducativo:
    cuenta: Account
    perfil: ChildProfile


class PerfilEducativoService:
    """Orquesta autorización de sesión sin modificar el runtime educativo local."""

    def __init__(self, cuentas: CuentaRepository, auth: AuthRepository, progreso: ProgresoChildProfile, acceso: AccesoProducto):
        self.cuentas = cuentas
        self.auth = auth
        self.progreso = progreso
        self.acceso = acceso

    def contexto(self, raw_session: str | None) -> ContextoEducativo:
        if not raw_session:
            raise ContextoEducativoError("Sesión requerida.")
        session = self.auth.get_session(raw_session)
        if not session:
            raise ContextoEducativoError("La sesión no es válida.")
        account = self.cuentas.obtener_account(session["account_id"])
        if not account:
            raise ContextoEducativoError("La cuenta de la sesión no existe.")
        profile_id = session["active_profile_id"]
        if not profile_id:
            raise ContextoEducativoError("Primero debe seleccionarse un perfil educativo.")
        perfiles = self.cuentas.listar_child_profiles(account.id)
        perfil = next((p for p in perfiles if p.id == profile_id and p.active), None)
        if not perfil:
            raise ContextoEducativoError("El perfil activo no pertenece a la cuenta o no está activo.")
        return ContextoEducativo(cuenta=account, perfil=perfil)

    def cargar_progreso(self, raw_session: str | None) -> ProgresoSnapshot | None:
        contexto = self.contexto(raw_session)
        snapshot = self.progreso.cargar_o_recuperar(contexto.perfil.id)
        if snapshot is not None and snapshot.profile_id != contexto.perfil.id:
            raise ContextoEducativoError("El progreso no pertenece al perfil activo.")
        return snapshot

    def guardar_progreso(self, raw_session: str | None, snapshot: ProgresoSnapshot) -> None:
        contexto = self.contexto(raw_session)
        if snapshot.profile_id != contexto.perfil.id:
            raise ContextoEducativoError("No se puede guardar progreso de otro perfil.")
        self.progreso.guardar(snapshot)

    def exigir_acceso(self, raw_session: str | None, product: str) -> ContextoEducativo:
        contexto = self.contexto(raw_session)
        try:
            self.acceso.exigir_acceso(contexto.perfil.id, product)
        except AccesoError as exc:
            raise ContextoEducativoError("El perfil no tiene acceso al producto solicitado.") from exc
        return contexto

    def resumen_acceso(self, raw_session: str | None, products: list[str]) -> dict[str, bool]:
        contexto = self.contexto(raw_session)
        return self.acceso.resumen_acceso(contexto.perfil.id, products)
