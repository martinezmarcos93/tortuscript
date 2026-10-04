"""Abre TortuScript en el navegador. Es la forma normal de usar la app.

Uso:  python iniciar_web.py                  (abre el navegador solo)
      python iniciar_web.py --sin-navegador  (solo arranca el servidor)
      python iniciar_web.py --puerto 8080    (si no querés el puerto de siempre)

También sirven los lanzadores de la carpeta lanzadores/ (doble clic en Windows, acceso directo en Linux).
Corre solo en tu compu (127.0.0.1), sin internet. Las cuentas y el correo se configuran con .env (ver .env.example).
Se cierra con Ctrl+C o cerrando la ventana.
"""
import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PUERTO_PREFERIDO = 5057
CANTIDAD_DE_PUERTOS = 20
PYTHON_MINIMO = (3, 9)


def configurar_logs(carpeta=None):
    """Errores internos a logs/tortuscript.log (rotación diaria, 7 días). Al chico no se le muestran."""
    carpeta = Path(carpeta) if carpeta else RAIZ / "logs"
    try:
        carpeta.mkdir(exist_ok=True)
        h = TimedRotatingFileHandler(carpeta / "tortuscript.log", when="midnight", backupCount=7, encoding="utf-8")
    except OSError:
        return                                                     # sin permisos de escritura: seguimos sin logs
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    raiz = logging.getLogger("tortuscript")
    raiz.setLevel(logging.INFO)
    raiz.addHandler(h)


def puerto_libre(preferido=PUERTO_PREFERIDO, cantidad=CANTIDAD_DE_PUERTOS):
    """El primer puerto libre desde `preferido` (así se pueden abrir dos perfiles a la vez)."""
    for puerto in range(preferido, preferido + cantidad):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    raise RuntimeError(f"No encontré un puerto libre entre el {preferido} y el {preferido + cantidad - 1}.")


def crear_servidor(puerto, app=None):
    """El servidor listo para `serve_forever()` (en un hilo, para poder probarlo, o en el principal)."""
    from werkzeug.serving import WSGIRequestHandler, make_server
    WSGIRequestHandler.protocol_version = "HTTP/1.1"          # conexiones que se reusan: la página baja fuentes y scripts sin reconectar
    if app is None:
        from web.app import create_app
        app = create_app()
    return make_server("127.0.0.1", puerto, app, threaded=True)


def cargar_env(archivo):
    """Lee un `.env` simple (CLAVE=valor, # comentarios) sin pisar lo que ya esté en el entorno.
    Devuelve las claves que agregó. Sin dependencias: no interpreta comillas anidadas ni variables."""
    agregadas = []
    try:
        lineas = Path(archivo).read_text(encoding="utf-8").splitlines()
    except OSError:
        return agregadas
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave, valor = clave.strip(), valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if clave and clave not in os.environ:
            os.environ[clave] = valor
            agregadas.append(clave)
    return agregadas


def crear_aplicacion(datos, url):
    """La app real: cuentas y progreso en la carpeta de datos, y correo según el entorno (o deshabilitado)."""
    from tortuscript import correo, rutas
    from web.app import create_app
    app = create_app()
    cuentas = rutas.carpeta_de_cuentas(datos)
    app.config["ACCOUNT_DB"] = cuentas / "cuentas.sqlite3"
    app.config["PROGRESS_DIR"] = cuentas / "progreso_perfiles"
    app.config["ACCOUNT_EMAIL_SENDER"] = correo.desde_entorno(url_base=url)
    return app


def verificar_entorno():
    """Mensajes claros en español si falta algo (en vez de un traceback en inglés)."""
    if sys.version_info < PYTHON_MINIMO:
        return f"TortuScript necesita Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} o más nuevo (tenés el {sys.version_info[0]}.{sys.version_info[1]})."
    try:
        import flask  # noqa: F401
    except ImportError:
        return ("Falta Flask, la única pieza que necesita TortuScript.\n"
                "Instalala con:  python -m pip install -r requirements.txt")
    return None


def leer_argumentos(argv=None):
    ap = argparse.ArgumentParser(description="Abre TortuScript en el navegador.")
    ap.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador")
    ap.add_argument("--puerto", type=int, default=None, help=f"puerto (por defecto, el primero libre desde el {PUERTO_PREFERIDO})")
    return ap.parse_args(argv)


def main(argv=None):
    args = leer_argumentos(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")                   # Windows: emojis en la consola
    problema = verificar_entorno()
    if problema:
        print(f"❌ {problema}")
        return 1
    sys.path.insert(0, str(RAIZ))
    from tortuscript import persistencia_local, rutas
    datos = rutas.preparar_carpeta_de_datos()          # junto al programa, o la del usuario si está instalado
    persistencia_local.DIRECTORIO = datos
    configurar_logs(datos / "logs")
    cargar_env(datos / ".env")
    try:
        puerto = args.puerto or puerto_libre()
        url = f"http://127.0.0.1:{puerto}/"
        app = crear_aplicacion(datos, url)
        servidor = crear_servidor(puerto, app)
    except (RuntimeError, OSError, ValueError) as e:
        print(f"❌ No pude arrancar el servidor: {e}")
        return 1
    if app.config["ACCOUNT_EMAIL_SENDER"] is None:
        print("✉️  El correo no está configurado: no se pueden crear cuentas nuevas ni recuperar contraseñas.")
        print("   Ver .env.example (TORTU_EMAIL_MODO) o usar herramientas/crear_admin.py para una cuenta local.")
    if not args.sin_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"🐢 TortuScript está en {url}")
    print("   Se abre solo en tu navegador. Para cerrar, apretá Ctrl+C o cerrá esta ventana.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta la próxima!")
    finally:
        servidor.server_close()
    return 0


def atender_worker():
    """El ejecutable instalado se relanza con --worker para correr el código del chico (ADR-015). Va antes de
    importar Flask: cada ejecución tiene que ser liviana."""
    sys.path.insert(0, str(RAIZ))
    from tortuscript.worker import main as worker
    worker()
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if sys.argv[1:2] == ["--worker"]:
        sys.exit(atender_worker())
    sys.exit(main())
