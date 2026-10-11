# Fase 2 — verificación de integración con Croco-Script

Fecha: 11/10/2026. Rama: `work/integration-verification-phase-2`.

## Objetivo

Reproducir los contratos desde los checkouts actuales de `main` sin importar código entre repositorios ni usar datos reales. Esta guía es un procedimiento de prueba, no evidencia de que ya se haya ejecutado.

## Preparación

1. Crear dos checkouts limpios de `main` y registrar los SHA de ambos.
2. Instalar dependencias de desarrollo indicadas por cada proyecto y ejecutar primero sus suites locales.
3. Crear una base de datos temporal y un perfil/cuenta sintéticos; no usar correos, menores ni progreso real.
4. Configurar en TortuScript `FEDERACION["croco-script"]` con URL de entrada de Croco, `kid` y un secreto aleatorio de prueba de al menos 32 caracteres.
5. Configurar en Croco la misma clave como `CROCO_CLAVES`, además de `CROCO_URL_TORTUSCRIPT`, `CROCO_ACCESO_URL` y `CROCO_PROGRESO_URL`. Nunca guardar valores reales en los logs ni en el repositorio.

## Matriz obligatoria

| Caso | Acción | Resultado esperado |
|---|---|---|
| AUTH-01 | Abrir Croco desde un perfil con acceso | Redirección con token breve; Croco crea su propia sesión |
| AUTH-02 | Repetir el mismo token | Rechazo por uso único |
| ENT-01 | Consultar cuenta sintética con acceso | `200`, `activo=true`, `Cache-Control: no-store` |
| ENT-02 | Revocar el acceso y consultar de nuevo | `200`, `activo=false`; Croco cierra la sesión cuando confirma la revocación |
| ENT-03 | Firma inválida o fuera de ventana | `401` con error genérico; sin identificadores en logs |
| PROG-01 | Consultar progreso de perfil activo autorizado | `200`, `Progress.v1` por itinerario; sin nombre/correo/XP |
| PROG-02 | Perfil inexistente, inactivo o sin acceso | `404 perfil_inexistente`; no revelar cuál condición se dio |
| SUP-01 | Eliminar perfil archivado | Croco elimina los datos del perfil y no los de su hermano |
| SUP-02 | Purgar cuenta vencida | Croco elimina datos de todos los perfiles de esa cuenta |
| SUP-03 | Exportar perfil | Se devuelven solo los datos de Croco de ese perfil |
| SUP-04 | Croco apagado durante una supresión | TortuScript termina la operación local, persiste la cola y reporta el pendiente sin exponer IDs |
| SUP-05 | Reiniciar TortuScript y recuperar Croco | El reintento emite un token nuevo, la operación se confirma y sale de la cola |
| SUP-06 | Token de otra cuenta o acción inválida | Rechazo; no se leen, exportan ni borran datos de otro perfil |
| PRIV-01 | Inspeccionar respuestas y logs | Sin email, nombres de menores, tokens completos ni claves |
| PRIV-02 | Inspeccionar cola persistida | Solo IDs opacos, acción, contador y fecha; permisos del archivo adecuados |

## Ejecución

En cada repositorio ejecutar la suite oficial según su README. En Croco, ejecutar `python -m unittest discover -s tests -v` dentro del entorno documentado y con Docker disponible para las pruebas del sandbox. En TortuScript, ejecutar el comando oficial documentado en su README y las pruebas de cuenta/federación.

Después, iniciar ambos servidores en puertos de loopback separados, configurar claves efímeras y ejecutar la matriz de arriba. No exponerlos a interfaces públicas. Guardar en el informe los SHA de ambos checkouts, comandos exactos, salida de cada caso y resultado; no guardar secretos ni payloads con datos de alumnos.

## Criterio de aceptación

- Todas las pruebas locales pasan antes de la integración.
- Todos los casos de la matriz pasan desde los `main` coordinados.
- Los fallos de red no se confunden con revocación confirmada.
- La cola sobrevive al reinicio y el reintento es idempotente.
- No se observan fugas entre cuentas ni datos personales en la federación.
- Una revisión de restauración y retención de copias queda documentada por separado.

Si un caso falla, se abre una corrección en una rama específica y se agrega una prueba de regresión antes del commit. No se marca la fase como cerrada hasta adjuntar evidencia reproducible.
