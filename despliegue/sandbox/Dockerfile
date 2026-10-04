# Imagen del sandbox que ejecuta el código del alumno (ADR-033).
# Solo contiene Python y el paquete `tortuscript` (biblioteca estándar, sin Flask): ni datos, ni secretos,
# ni contenido de cursos. Se construye desde la raíz del repositorio:
#     docker build -f despliegue/sandbox/Dockerfile -t tortuscript-sandbox:1 .
# Cada ejecución es un contenedor nuevo que se destruye al terminar (ver tortuscript/sandbox_docker.py).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
COPY tortuscript /app/tortuscript
# Compilado en la imagen: el contenedor corre con el sistema de archivos en solo lectura.
RUN python -m compileall -q /app/tortuscript
WORKDIR /app
USER 65534:65534
ENTRYPOINT ["python", "-m", "tortuscript.worker"]
