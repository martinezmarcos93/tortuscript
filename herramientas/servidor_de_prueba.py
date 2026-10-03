#!/usr/bin/env python3
"""Servidor de PRUEBA: la app web con datos temporales y sesión educativa efímera.

Lo usan jugar_cursos.py y las auditorías Playwright. Nunca toca los datos reales del usuario.
Uso: python herramientas/servidor_de_prueba.py [puerto] [--todo-desbloqueado] [--abrir]
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

from flask import make_response, request

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "herramientas"))

from tortuscript import persistencia_local, progreso  # noqa: E402
from tortuscript.auth import AuthRepository  # noqa: E402
from tortuscript.cuentas import CuentaRepository  # noqa: E402

TOKEN = "prueba"


def desbloquear_todo():
    """Prepara progreso legacy temporal; la cuenta de prueba también evita bloqueos curriculares."""
    from tortuscript import contenido
    p = persistencia_local.cargar_progreso()
    progreso.guardar_config(p, onboarding=True, nombre="Prueba")
    for curso in contenido.todos_los_cursos():
        for _, lec in contenido.lecciones(curso):
            p.setdefault("lecciones", {})[lec["id"]] = {"pasos": {}, "completada": True, "perfecta": False}
    for i in range(len(contenido.ejercicios())):
        p["ejercicios"][str(i)] = {"completado": True, "estrellas": 1, "xp": 0}
    persistencia_local.guardar_progreso(p)


def preparar_sesion_de_prueba(app, directorio):
    """Crea cuenta, perfil y sesión en SQLite temporal; el bootstrap solo existe en este servidor."""
    db = directorio / "cuentas.sqlite3"
    progreso_dir = directorio / "progreso_perfiles"
    app.config.update(
        ACCOUNT_DB=db,
        PROGRESS_DIR=progreso_dir,
        ACCOUNT_COOKIE_SECURE=False,
        ACCOUNT_COOKIE_SAMESITE="Lax",
    )
    cuentas = CuentaRepository(db)
    auth = AuthRepository(db)
    cuentas.ensure_schema()
    auth.ensure_schema()
    cuenta = cuentas.crear_account("prueba@example.invalid")
    # El rol admin solo existe en esta base efímera para poder abrir rutas curriculares
    # de cualquier nivel durante las auditorías visuales; nunca se crea en una DB real.
    with sqlite3.connect(db) as con:
        con.execute("UPDATE accounts SET role='admin' WHERE id=?", (cuenta.id,))
    auth.marcar_verificada(cuenta.id)
    auth.set_password(cuenta.id, "clave-temporal-solo-pruebas-123")
    perfil = cuentas.crear_child_profile(cuenta.id, "Prueba")
    raw_session, csrf, _ = auth.create_session(cuenta.id)
    auth.select_profile(raw_session, perfil.id)

    @app.get("/cuenta/__test__/bootstrap")
    def bootstrap():
        nombre = (request.args.get("perfil") or "Prueba").strip()[:60] or "Prueba"
        perfil_actual = next(
            (p for p in cuentas.listar_child_profiles(cuenta.id) if p.display_name == nombre),
            None,
        )
        if perfil_actual is None:
            perfil_actual = cuentas.crear_child_profile(cuenta.id, nombre)
        auth.select_profile(raw_session, perfil_actual.id)
        respuesta = make_response("Sesión de prueba inicializada")
        respuesta.set_cookie(
            "tortu_session", raw_session, httponly=True, secure=False,
            samesite="Lax", path="/", max_age=12 * 60 * 60,
        )
        respuesta.set_cookie(
            "tortu_csrf", csrf, httponly=False, secure=False,
            samesite="Lax", path="/", max_age=12 * 60 * 60,
        )
        return respuesta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    puerto = int(args[0]) if args else 5077
    directorio = Path(tempfile.mkdtemp(prefix="tortu_prueba_"))
    persistencia_local.DIRECTORIO = directorio / "legacy"
    persistencia_local.DIRECTORIO.mkdir(parents=True, exist_ok=True)
    if "--todo-desbloqueado" in sys.argv:
        desbloquear_todo()
    from iniciar_web import crear_servidor
    from web.app import create_app
    app = create_app(token=TOKEN)
    preparar_sesion_de_prueba(app, directorio)
    print(f"Servidor de prueba en http://127.0.0.1:{puerto} (datos temporales en {directorio})")
    if "--abrir" in sys.argv:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{puerto}/__test__/bootstrap")).start()
    crear_servidor(puerto, app).serve_forever()


if __name__ == "__main__":
    main()
