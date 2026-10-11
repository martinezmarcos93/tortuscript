"""Supresion.v1 del lado que emite (ADR-037): pedirle a Croco-Script que borre o exporte datos de un perfil.

Al eliminar un perfil o una cuenta, Croco-Script guarda el historial de entregas de esos menores y no se entera
solo. Este módulo le avisa de servidor a servidor, con un token firmado de un solo uso (`federacion.emitir_operacion`).

Si Croco-Script no responde, el pedido NO se pierde: queda en una cola en disco (`operaciones_pendientes.json`, solo
identificadores opacos) y se reintenta con un token nuevo. Borrar en TortuScript nunca depende de que el otro esté arriba.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tortuscript import federacion

logger = logging.getLogger(__name__)

PRODUCTO = "croco-script"
RUTA_OPERACION = "/federacion/v1/operacion"
ESPERA_MAXIMA = 3                       # segundos por pedido
RESPUESTA_MAXIMA = 256 * 1024           # respuestas de supresión y errores
RESPUESTA_EXPORTACION_MAXIMA = 16 * 1024 * 1024  # historial educativo completo, con límite defensivo
MAXIMO_POR_PASADA = 20                  # pendientes que se reintentan de una vez, para no demorar un arranque
_CANDADO = threading.Lock()


def _url_de_operacion(url_de_entrada: str) -> str:
    partes = urllib.parse.urlsplit(url_de_entrada)
    return f"{partes.scheme}://{partes.netloc}{RUTA_OPERACION}"


class OperacionesCroco:
    """`config` es la entrada `croco-script` de `app.config["FEDERACION"]`; vacía o None: no hay nada que avisar."""

    def __init__(self, config, carpeta: Path | str, abrir=None):
        self.config = config or None
        self.archivo = Path(carpeta) / "operaciones_pendientes.json"
        self._abrir = abrir or (lambda *a, **k: urllib.request.urlopen(*a, **k))   # se resuelve al usar: se puede reemplazar en pruebas

    @property
    def activa(self) -> bool:
        return bool(self.config)

    # ── pedido HTTP ──
    def _enviar(self, accion: str, cuenta: str, perfil: str | None):
        """Devuelve (estado, cuerpo|None). Lanza OSError ante un fallo de red."""
        token = federacion.emitir_operacion(self.config["clave"], self.config["kid"], PRODUCTO, accion, cuenta, perfil)
        pedido = urllib.request.Request(_url_de_operacion(self.config["url"]), method="POST", data=b"", headers={
            "Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with self._abrir(pedido, timeout=ESPERA_MAXIMA) as respuesta:
                limite = RESPUESTA_EXPORTACION_MAXIMA if accion == "exportar_perfil" else RESPUESTA_MAXIMA
                crudo = respuesta.read(limite + 1)
                estado = respuesta.status
        except urllib.error.HTTPError as exc:
            return exc.code, None
        if len(crudo) > limite:
            raise OSError("La respuesta de Croco-Script es demasiado grande.")
        try:
            return estado, json.loads(crudo.decode("utf-8"))
        except ValueError:
            return estado, None

    # ── cola ──
    def _poner_en_cuarentena(self) -> None:
        """Conserva una cola ilegible antes de permitir que una escritura la reemplace."""
        marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destino = self.archivo.with_name(f"{self.archivo.name}.corrupto-{marca}")
        self.archivo.replace(destino)
        logger.error("La cola de operaciones pendientes está dañada; se conservó en %s", destino.name)

    def _leer(self) -> list:
        try:
            contenido = self.archivo.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        # Otros errores de E/S deben propagarse: asumir una cola vacía podría sobrescribir
        # pedidos de supresión que no pudimos leer.
        try:
            datos = json.loads(contenido)
        except ValueError:
            self._poner_en_cuarentena()
            return []
        if not isinstance(datos, list) or any(not self._entrada_valida(e) for e in datos):
            self._poner_en_cuarentena()
            return []
        return datos

    @staticmethod
    def _entrada_valida(entrada) -> bool:
        """Evita que una cola sintácticamente válida pero mal formada rompa los reintentos."""
        if not isinstance(entrada, dict):
            return False
        accion, cuenta, perfil = entrada.get("accion"), entrada.get("cuenta"), entrada.get("perfil")
        intentos, creada = entrada.get("intentos"), entrada.get("creada")
        if accion not in ("suprimir_perfil", "suprimir_cuenta") or not isinstance(cuenta, str) or not cuenta:
            return False
        if accion == "suprimir_perfil" and (not isinstance(perfil, str) or not perfil):
            return False
        if accion == "suprimir_cuenta" and perfil is not None:
            return False
        if not isinstance(intentos, int) or isinstance(intentos, bool) or intentos < 1:
            return False
        estado = entrada.get("estado", "pendiente")
        return isinstance(creada, str) and bool(creada) and estado in ("pendiente", "conflicto_409")

    def _escribir(self, pendientes: list) -> None:
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".operaciones_", suffix=".tmp", dir=str(self.archivo.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as salida:
                json.dump(pendientes, salida, ensure_ascii=False, indent=1)
                salida.flush()
                os.fsync(salida.fileno())
            os.replace(tmp, self.archivo)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def pendientes(self) -> list:
        with _CANDADO:
            return self._leer()

    def _encolar(self, accion: str, cuenta: str, perfil: str | None) -> None:
        with _CANDADO:
            cola = self._leer()
            entrada = {"accion": accion, "cuenta": cuenta, "perfil": perfil, "intentos": 1,
                       "creada": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if not any(e.get("accion") == accion and e.get("cuenta") == cuenta and e.get("perfil") == perfil for e in cola):
                cola.append(entrada)
            self._escribir(cola)

    def _encolar_conflicto(self, accion: str, cuenta: str, perfil: str | None) -> None:
        """Conserva una operación rechazada por conflicto de propiedad sin reintentarla a ciegas."""
        with _CANDADO:
            cola = self._leer()
            entrada = next((e for e in cola if e.get("accion") == accion and
                            e.get("cuenta") == cuenta and e.get("perfil") == perfil), None)
            if entrada is None:
                entrada = {"accion": accion, "cuenta": cuenta, "perfil": perfil, "intentos": 1,
                           "creada": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                cola.append(entrada)
            entrada["estado"] = "conflicto_409"
            entrada["ultimo_error"] = "perfil_de_otra_cuenta"
            self._escribir(cola)

    # ── interfaz ──
    def solicitar(self, accion: str, cuenta: str, perfil: str | None = None) -> bool:
        """Pide borrar. True si Croco-Script confirmó; False si quedó en cola. Nunca lanza: borrar acá ya ocurrió."""
        if not self.activa:
            return True
        try:
            estado, _ = self._enviar(accion, cuenta, perfil)
        except (OSError, federacion.FederacionError) as exc:
            logger.warning("Croco-Script no confirmó %s (%s); queda en cola", accion, type(exc).__name__)
            estado = None
        if estado == 200:
            logger.info("Croco-Script confirmó %s", accion)
            return True
        if estado == 409:
            logger.error("Croco-Script rechazó %s por conflicto de propiedad; se conserva para revisión manual.", accion)
            try:
                self._encolar_conflicto(accion, cuenta, perfil)
            except OSError:
                logger.error("No se pudo conservar el conflicto de la operación %s", accion, exc_info=True)
            return False
        if estado is not None:
            logger.warning("Croco-Script respondió %s a %s; queda en cola", estado, accion)
        try:
            self._encolar(accion, cuenta, perfil)
        except OSError:
            logger.error("No se pudo guardar la operación %s en la cola de pendientes", accion, exc_info=True)
        return False

    def reintentar_pendientes(self) -> int:
        """Reenvía lo que quedó en cola. Devuelve cuántos se confirmaron."""
        if not self.activa:
            return 0
        with _CANDADO:
            cola = self._leer()
        if not cola:
            return 0
        hechos, restantes = 0, []
        for posicion, entrada in enumerate(cola):
            if entrada.get("estado", "pendiente") == "conflicto_409":
                restantes.append(entrada)
                continue
            if posicion >= MAXIMO_POR_PASADA:
                restantes.append(entrada)
                continue
            try:
                estado, _ = self._enviar(entrada["accion"], entrada["cuenta"], entrada.get("perfil"))
            except (OSError, KeyError, federacion.FederacionError):
                estado = None
            if estado == 200:
                hechos += 1
                continue
            if estado == 409:
                entrada["estado"] = "conflicto_409"
                entrada["ultimo_error"] = "perfil_de_otra_cuenta"
                restantes.append(entrada)
                continue
            entrada["intentos"] = int(entrada.get("intentos", 1)) + 1
            restantes.append(entrada)
        with _CANDADO:
            ahora = self._leer()
            nuevas = [e for e in ahora if e not in cola]      # lo que se encoló mientras se reintentaba
            self._escribir(restantes + nuevas)
        return hechos

    def exportar_perfil(self, cuenta: str, perfil: str) -> dict:
        """Lo que Croco-Script guarda de un perfil (`exportar_perfil`), o {"error": …} si no se pudo obtener."""
        if not self.activa:
            return {"error": "Croco-Script no está conectado."}
        try:
            estado, cuerpo = self._enviar("exportar_perfil", cuenta, perfil)
        except (OSError, federacion.FederacionError):
            return {"error": "Croco-Script no respondió."}
        if estado == 200 and isinstance(cuerpo, dict) and isinstance(cuerpo.get("datos"), dict):
            return cuerpo["datos"]
        if estado == 404:
            return {"vacio": "Este perfil no entró nunca a Croco-Script."}
        return {"error": "Croco-Script no pudo entregar los datos de este perfil."}
