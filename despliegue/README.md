# Desplegar TortuScript para terceros (modo servidor)

Estado: **preparado y probado en tests, nunca desplegado**. En la compu de una familia nada de esto hace falta:
se usa `python iniciar_web.py`.

## Qué cambia respecto del modo local

| | Local (`iniciar_web.py`) | Servidor (`wsgi.py`) |
|---|---|---|
| Quién entra | Solo la propia máquina (127.0.0.1) | Los hosts de `TORTU_HOSTS`, detrás de un proxy con HTTPS |
| Código de los chicos | Subproceso con límites | **Solo** en contenedores efímeros sin red (`despliegue/sandbox/`) |
| Correo | Opcional (`consola` o `smtp`) | SMTP obligatorio |
| Cookies | Sin `Secure` (es http) | `Secure`, `HttpOnly`, `SameSite=Lax` + HSTS |
| Datos | Junto al programa o carpeta del usuario | `TORTUSCRIPT_DATOS`, fuera del código |
| Límite de intentos | En memoria | SQLite compartido en la carpeta de datos |

`wsgi.py` **no arranca** si falta una de las obligatorias (hosts, URL https, carpeta de datos, sandbox, correo):
ver `web/servidor.py` y `tests/test_servidor.py`.

## Pasos

```bash
docker build -f despliegue/sandbox/Dockerfile -t tortuscript-sandbox:1 .
python -m pip install --require-hashes -r requirements.lock
# un servidor WSGI a elección (no está en requirements.txt: auditarlo antes de instalarlo), por ejemplo:
#   gunicorn --workers 1 --threads 8 --bind 127.0.0.1:8000 wsgi:app
```

Delante, un proxy (Caddy, nginx) que termine HTTPS, pase `X-Forwarded-For/Proto/Host` y **no** deje entrar
esas cabeceras desde afuera.

## Restricciones que hoy son parte del diseño

- **Un solo proceso** (con hilos). Las pistas vistas en cada ejercicio, la sesión de práctica del día y las colas de
  repaso viven en memoria del proceso; con varios procesos se perderían entre pedidos. Para escalar hay que
  llevarlas al progreso guardado o a un almacén compartido.
- **Un solo servidor.** El progreso son archivos JSON y la base es SQLite en disco local.
- **El proceso web habla con Docker.** Quien puede lanzar contenedores es, en la práctica, root en esa máquina.
  Antes de exponerlo a internet conviene separar el worker (ver `despliegue/sandbox/README.md`).
- **Respaldos:** `python herramientas/respaldar_datos.py --datos "$TORTUSCRIPT_DATOS" crear`, programado por fuera
  (cron o un timer de systemd), y copiar la carpeta `respaldos/` a otra máquina.

## Lista antes de abrir al público

- [ ] Dominio, certificado y proxy configurados; `curl -I` muestra HSTS y la CSP.
- [ ] Registro real de punta a punta con el proveedor SMTP (llega el correo, el enlace funciona).
- [ ] `tests/test_sandbox_docker.py` en verde en la máquina de producción.
- [ ] Respaldo creado, copiado afuera y **restaurado** en otra máquina.
- [ ] Decisión sobre ADR-046 (supresión) y revisión jurídica de los textos de privacidad.
- [ ] Pagos: proveedor elegido, adaptador escrito y probado en su sandbox (hasta entonces, sin secreto de webhook).
- [ ] Revisión independiente del aislamiento del sandbox.
