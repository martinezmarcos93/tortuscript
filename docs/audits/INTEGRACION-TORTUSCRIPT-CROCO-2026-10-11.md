# Auditoría de integración TortuScript ↔ Croco-Script — 11/10/2026

## Alcance y regla de seguridad

Barrido documental y estático de ambos repositorios, sus ramas, contratos publicados, handoffs, roadmaps y pruebas declaradas. Se preserva `main`: este documento vive en `work/ecosystem-audit-2026-10-11`. No se hace merge ni se modifica ninguna rama preexistente.

## Arquitectura confirmada

- **TortuScript** es la experiencia de iniciación y el dueño de la cuenta familiar, perfiles, acceso comercial y progreso curricular propio.
- **Croco-Script** es el producto técnico avanzado, con su propia sesión, catálogo y progreso. No importa módulos de TortuScript.
- La integración es mediante contratos versionados y claves compartidas solo en servidor: `Authorization.v1`, `Identity.v1`, `Entitlement.v1`, `Progress.v1`, `ProgressQuery.v1`, `Supresion.v1` y `Curriculum.v1`.

## Hallazgos por severidad

### P0 — Estado de integración confuso entre ramas
El handoff de Croco del 11/10 informa que la rama `feat/federacion-respuestas-croco` de TortuScript ya implementa los endpoints de entitlement/progreso y la emisión de `Supresion.v1`, incluso con una prueba HTTP entre los dos productos. Esa rama está **fuera de main**. El `main` actual de TortuScript sí contiene `web/federacion_routes.py` con endpoints de entitlement/progreso, pero el flujo emisor de supresión y el cableado de purga/exportación deben tratarse como un conjunto a validar en una máquina con ambos repositorios y ejecución real. No integrar la rama automáticamente: existen otras ramas vivas que no deben perderse ni mezclarse.

### P1 — Documentación de Croco obsoleta
`docs/contratos/README.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md` y `docs/handoffs/2026-10-11.md` mantienen afirmaciones incompatibles entre sí: la nota más reciente dice que TortuScript responde y emite, mientras las tablas/next steps siguen diciendo que falta. La documentación debe separar el estado de implementación en Croco, el estado del código de TortuScript en main y el estado verificado del despliegue conjunto.

### P1 — Quality gate real
Croco declara que la suite oficial es `unittest discover`; `tests/test_service.py` ya fue corregido para ejecutarse con ese runner. La ejecución local de Croco completa dependencias específicas (entorno `datos` y sandbox Docker) y no puede sustituirse por una simple compilación. El repositorio privado informa que GitHub Actions no corre por una restricción de facturación; esto no debe presentarse como CI verde.

### P1 — Supresión y exportación
El endpoint receptor `POST /federacion/v1/operacion` y los validadores de `Supresion.v1` están implementados en Croco, con pruebas para separación de tokens, uso único, aislamiento por cuenta, idempotencia y rechazo cross-site. TortuScript posee `federacion_operaciones.py`; el pendiente operativo es validar que eliminar/perfilar/purgar/exportar llame al emisor, que los fallos queden en cola y que el reintento sea observable sin filtrar datos personales.

### P1 — Retención de backups y revisión de hosting
Las decisiones actuales no autorizan contratar ni abrir el hosting. Sigue pendiente una política explícita de retención de copias ante solicitudes de borrado, respaldo programado probado en despliegue real, revisión técnica independiente del aislamiento y revisión jurídica de privacidad de menores. No se deben cerrar como hechos por tener código local.

### P2 — Roadmap curricular
Croco mantiene huecos explícitos: CSS/JavaScript/TypeScript y partes de proyectos integradores; tutor con IA aplazado por decisión registrada; lectura humana de las unidades antes de publicarlas como contenido pedagógicamente validado. No son bloqueantes para corregir la integración contractual.

## Orden de trabajo recomendado

1. Mantener la rama de integración de TortuScript separada; hacer revisión de diff contra `main` y preparar una PR revisable, sin merge.
2. Corregir documentación de Croco para reflejar con precisión qué existe en su `main`, qué está en ramas de Tortu y qué se verificó entre procesos reales.
3. Añadir una verificación de contratos que no dependa de rutas de workspace personales: permitir origen explícito en herramienta y describir cómo validar con checkouts vecinos. No descargar/copiar código fuente cruzando repositorios.
4. En una ejecución conjunta reproducible, probar: autorización, consulta de entitlement activa/inactiva, progress query autorizado/no autorizado, eliminación de perfil, eliminación de cuenta, exportación, fallo remoto con reintento y ausencia de datos personales en los payloads/logs.
5. Solo después, actualizar de nuevo la documentación de ambos repositorios con resultados reales y tratar la revisión externa/legal como un gate obligatorio antes de desplegar.

## Limitación de esta auditoría

El conector permite inspeccionar y modificar texto en GitHub, pero no ejecutar el proyecto con Python, Docker, navegador ni dos servidores locales. Por eso no declaro una suite ejecutada, un test de integración repetido ni una auditoría de seguridad independiente. Los resultados numéricos de tests citados son los consignados en handoffs/PRs del propio repositorio, no una nueva ejecución de esta sesión.


## Progreso de implementación documental en esta pasada

- Croco-Script: se corrigió `docs/HANDOFF.md` para separar estado de código y evidencia real, actualizar el estado de contratos y enumerar los gates que impiden hosting.
- Croco-Script: se rehízo `docs/ROADMAP.md` con estados actuales de las fases, dependencias y criterios de cierre; se removieron estados incompatibles con el handoff reciente.
- Croco-Script: se actualizó `docs/contratos/README.md` para distinguir cliente/receptor implementado de la necesidad de reproducir integración desde ambos `main`.
- Cada cambio documental quedó como un commit independiente; los commits y pruebas de ejecución se informan al cierre.