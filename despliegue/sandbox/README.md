# Sandbox de ejecución (ADR-033)

Ejecuta el código de los chicos en un contenedor nuevo por cada trabajo. Es opcional: en la compu de una familia
TortuScript usa un subproceso local con límites; el sandbox es para cuando el servidor atiende a terceros.

## Uso

```bash
docker build -f despliegue/sandbox/Dockerfile -t tortuscript-sandbox:1 .   # desde la raíz del repo
TORTU_SANDBOX=docker python iniciar_web.py                                 # o en el .env
```

Hay que reconstruir la imagen cada vez que cambia el paquete `tortuscript/` (el worker vive adentro).

## Qué garantiza cada trabajo

| Requisito de ADR-033 | Cómo se cumple | Prueba |
|---|---|---|
| Sin red | `--network none` | `test_sin_red` |
| Sin secretos | la imagen solo trae Python y `tortuscript/`; no hereda el entorno ni monta nada del host | `test_no_recibe_el_entorno…`, `test_sistema_de_archivos…` |
| Filesystem efímero | `--read-only` + `/tmp` en memoria de 16 MB, sin ejecución; `--rm` | `test_tmp_es_efimero…` |
| Límite de CPU | `--cpus 1`, 4 s de CPU (`--ulimit cpu`) | `test_los_abusos…` |
| Límite de memoria | 256 MB del contenedor, sin swap; 512 MB de memoria virtual | `test_memoria_acotada…` |
| Timeout | 10 s de trabajo; al vencer se elimina el contenedor por nombre | `test_un_trabajo_que_no_termina…` |
| Límite de salida | el del intérprete (20.000 caracteres) | `test_sandbox_abuso.py` |
| Privilegios mínimos | usuario `nobody`, `--cap-drop ALL`, `no-new-privileges` | `test_sin_privilegios…` |
| Destruido al terminar | `--rm` | `test_no_queda_ningun_contenedor…` |
| Sin acceso al host ni a otros trabajos | namespaces propios; 16 procesos como máximo | `test_no_ve_procesos…`, `test_bomba_de_procesos…` |

Las pruebas están en `tests/test_sandbox_docker.py` y corren código hostil arbitrario (sin el validador del lenguaje).
Se saltean si no hay Docker o falta la imagen; en CI la imagen se construye antes de los tests.

## Lo que falta antes de producción

- **Cola y concurrencia.** Hoy los pedidos se atienden de a uno (un candado en la app web). Con varios procesos web
  hace falta una cola acotada y un tope de contenedores simultáneos.
- **El servidor web tiene acceso a Docker.** Quien puede hablar con el daemon de Docker es, en la práctica, root en
  esa máquina: en producción el web debe pedir trabajos a un servicio aparte (API → cola → worker), no lanzar
  contenedores él mismo. Es el flujo de ADR-033; esta implementación es el «worker» de ese flujo.
- **Refuerzo del runtime.** Docker comparte el kernel con el host. Para código realmente hostil conviene sumar gVisor
  (`--runtime runsc`) o microVMs, y un perfil seccomp más estricto que el de Docker por defecto.
- **Latencia.** ~0,45 s por ejecución en la máquina de desarrollo. Un pool de contenedores precalentados la bajaría.
- **Revisión independiente** del aislamiento, como exige la puerta de aceptación de los contratos de dominio.
