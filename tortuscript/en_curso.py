"""Estado «en curso» de un perfil: lo que pasa mientras resuelve, que no es progreso.

Pistas vistas en cada paso, errores del intento actual, la sesión de práctica del día y las colas de
repaso. Antes vivía en memoria del proceso web: se perdía al reiniciar, crecía sin límite y obligaba a
correr un solo proceso. Ahora es un archivo chico por perfil, junto a su progreso.

No es progreso: no entra en los respaldos ni en las exportaciones, y si se pierde solo se reinician las
pistas y los intentos de los ejercicios abiertos.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_PROFILE_ID_RE = re.compile(r"^child_[a-f0-9]{24}$")
ENTRADAS_MAX = 400            # pasos con pistas o intentos recordados por perfil
COLAS_MAX = 6                 # colas de repaso recordadas por perfil


def vacio() -> dict:
    return {"pistas": {}, "intentos": {}, "practica": None, "colas": {}}


def _normalizar(datos) -> dict:
    """Un archivo dañado o de otra versión no rompe nada: lo que no tenga la forma esperada se descarta."""
    limpio = vacio()
    if not isinstance(datos, dict):
        return limpio
    if isinstance(datos.get("pistas"), dict):
        limpio["pistas"] = {str(k): v for k, v in datos["pistas"].items() if type(v) is int and 0 <= v <= 3}
    if isinstance(datos.get("intentos"), dict):
        for clave, valor in datos["intentos"].items():
            if isinstance(valor, dict) and type(valor.get("errores")) is int and valor["errores"] >= 0:
                limpio["intentos"][str(clave)] = {"errores": valor["errores"], "revelado": valor.get("revelado") is True}
    practica = datos.get("practica")
    if isinstance(practica, dict) and isinstance(practica.get("dia"), str) and isinstance(practica.get("pasos"), list):
        pasos = [(p[0], p[1]) for p in practica["pasos"]
                 if isinstance(p, (list, tuple)) and len(p) == 2 and isinstance(p[0], str) and type(p[1]) is int]
        limpio["practica"] = {"dia": practica["dia"], "pasos": pasos}
    if isinstance(datos.get("colas"), dict):
        for clave, cola in datos["colas"].items():
            if isinstance(cola, list) and all(type(n) is int for n in cola):
                limpio["colas"][str(clave)] = cola
    return limpio


class EnCurso:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    def _archivo(self, profile_id: str) -> Path:
        if not isinstance(profile_id, str) or not _PROFILE_ID_RE.fullmatch(profile_id):
            raise ValueError("profile_id no tiene el formato interno esperado.")
        return self.directory / f"en_curso_{profile_id}.json"

    def cargar(self, profile_id: str) -> dict:
        archivo = self._archivo(profile_id)
        try:
            return _normalizar(json.loads(archivo.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return vacio()
        except (OSError, ValueError) as e:
            logger.warning("Estado en curso ilegible del perfil %s (%s): se reinicia", profile_id, type(e).__name__)
            return vacio()

    def guardar(self, profile_id: str, datos: dict) -> None:
        archivo = self._archivo(profile_id)
        datos = _normalizar(datos)
        # Acotado: un perfil no puede hacer crecer su archivo sin límite.
        for clave in ("pistas", "intentos"):
            if len(datos[clave]) > ENTRADAS_MAX:
                datos[clave] = dict(list(datos[clave].items())[-ENTRADAS_MAX:])
        if len(datos["colas"]) > COLAS_MAX:
            datos["colas"] = dict(list(datos["colas"].items())[-COLAS_MAX:])
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".en_curso_", suffix=".tmp", dir=str(self.directory))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as salida:
                json.dump(datos, salida, ensure_ascii=False)
            os.replace(tmp, archivo)
        except OSError as e:
            # Perder este estado no es grave: se registra y se sigue.
            logger.error("No se pudo guardar el estado en curso del perfil %s: %s", profile_id, e, exc_info=True)
            try:
                os.remove(tmp)
            except OSError:
                pass
