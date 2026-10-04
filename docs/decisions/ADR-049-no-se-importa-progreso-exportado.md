# ADR-049 — El progreso exportado no se vuelve a importar

- Estado: Aceptada
- Fecha: 2026-10-04 (propuesta y aceptada el mismo día)
- Decisor: Marcos
- Relacionadas: ADR-026, ADR-041, ADR-044, ADR-048

## Contexto

El barrido 3 dejó abierta una decisión de producto: el adulto puede descargar todos los datos de la cuenta
(`GET /cuenta/datos/exportar`), pero no existe una importación de ese archivo. La prueba de ciclo completo
(`tests/test_ciclo_alumno.py`) verifica la exportación y documenta la ausencia.

## Decisión

**Mantener el comportamiento actual: la exportación es de solo lectura y no hay importación desde el
navegador.**

- El archivo exportado lo puede editar cualquiera. Aceptarlo de vuelta sería aceptar XP, lecciones
  completadas y logros declarados por el cliente, justo lo que el servidor rechaza en todas las demás rutas
  (`PUT /cuenta/progreso` responde 410).
- La exportación cumple su finalidad: el derecho de acceso de ADR-026.
- Las necesidades reales de mover datos ya tienen su camino:
  - cambiar de máquina o recuperar una instalación: `herramientas/respaldar_datos.py` (lo corre quien opera,
    con verificación de integridad);
  - pasar el progreso de la app local sin cuentas a un perfil: la migración explícita de ADR-044;
  - usar dos dispositivos: la sincronización de ADR-048, que reevalúa en servidor.

## Consecuencias

- El barrido 3 no tiene nada pendiente de implementar.
- Si en el futuro hiciera falta portabilidad entre proveedores, el camino es el de ADR-048 (hechos que el
  servidor vuelve a evaluar), no reabrir la escritura de snapshots.
