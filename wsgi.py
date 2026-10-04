"""Entrada WSGI para el modo servidor (ver web/servidor.py y despliegue/README.md).

    TORTU_HOSTS=… TORTU_URL_BASE=https://… TORTUSCRIPT_DATOS=… TORTU_SANDBOX=docker TORTU_EMAIL_MODO=smtp … \\
        <servidor wsgi> --workers 2 --threads 8 wsgi:app

Con más de un proceso, TORTU_TOKEN tiene que estar definido (si no, cada proceso generaría un token distinto
para la API). El uso local sigue siendo `python iniciar_web.py`.
"""
from web.servidor import crear_aplicacion_servidor

app = crear_aplicacion_servidor()
