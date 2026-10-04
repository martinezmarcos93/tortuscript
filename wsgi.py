"""Entrada WSGI para el modo servidor (ver web/servidor.py y despliegue/README.md).

    TORTU_HOSTS=… TORTU_URL_BASE=https://… TORTUSCRIPT_DATOS=… TORTU_SANDBOX=docker TORTU_EMAIL_MODO=smtp … \\
        <servidor wsgi> --workers 1 --threads 8 wsgi:app

UN solo proceso (con varios hilos): las pistas vistas y la sesión de práctica viven en memoria del proceso.
El uso local sigue siendo `python iniciar_web.py`.
"""
from web.servidor import crear_aplicacion_servidor

app = crear_aplicacion_servidor()
