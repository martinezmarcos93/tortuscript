# ADR-046 — Supresión de cuenta y de perfiles

- Estado: Aceptada
- Fecha: 2026-10-04 (propuesta y aceptada el mismo día)
- Decisor: Marcos
- Relacionadas: ADR-026, ADR-030, ADR-032, `docs/architecture/CONTRATOS-DOMINIO-PRIVACIDAD-Y-ROADMAP.md`

## Contexto

ADR-026 exige operaciones de acceso, rectificación, supresión y exportación. Desde el 04/10/2026 existen acceso
(descarga de datos), rectificación (renombrar perfil, cambiar contraseña) y **archivo** reversible de perfiles.
Falta la supresión definitiva. El documento de contratos pide no implementar un borrado en cascada hasta definir
retención, exportación, recuperación y qué pasa con una suscripción activa. Esta ADR fija esas definiciones.

## Decisión

1. **Perfil.** El adulto puede eliminar un perfil *archivado*. Se borran su fila, su progreso, su `.bak` y sus
   archivos `.corrupto-*`. Pide escribir el nombre del perfil para confirmar. No hay período de gracia: el paso
   previo obligatorio de archivar ya es la red de seguridad, y antes de confirmar se ofrece descargar los datos.
2. **Cuenta.** El adulto pide la eliminación con su contraseña. La cuenta queda *pendiente de eliminación* durante
   **14 días**: no se puede usar, y volver a ingresar dentro del plazo la reactiva. Vencido el plazo se borran cuenta,
   perfiles, progreso, sesiones, tokens y consentimientos.
3. **Suscripción activa.** No se puede eliminar una cuenta con una suscripción que se renueva: primero se cancela.
   Así no quedan cobros sin cuenta. El período ya pagado no se reembolsa por eliminar la cuenta.
4. **Lo que se conserva.** Solo lo que una obligación legal exija (comprobantes de cobro, que viven en el proveedor
   de pagos y no en TortuScript) y un registro mínimo sin datos personales: fecha y un hash irreversible del
   identificador de cuenta, para poder demostrar que la eliminación se hizo.
5. **Respaldos.** Los respaldos locales (`respaldar_datos.py`) son del operador de la instalación: la eliminación no
   los reescribe. En un despliegue hospedado deben rotar en un plazo no mayor al de gracia (14 días) para que un dato
   eliminado no sobreviva en copias.
6. **Logs.** Ya no contienen correo ni nombres (solo identificadores opacos); rotan a los 7 días.

## Implementación

- `accounts.deletion_requested_at` y la tabla `account_deletions` (constancia: fecha y hash). `CuentaRepository`:
  `eliminar_child_profile`, `solicitar_eliminacion`, `cancelar_eliminacion`, `purgar_account`.
- `ProgresoChildProfile.eliminar` borra progreso, `.bak`, `.corrupto-*` y el estado en curso del perfil.
- Rutas `POST /cuenta/perfiles/<id>/eliminar` y `POST /cuenta/eliminar`; el ingreso dentro del plazo reactiva.
- La purga corre al arrancar (`iniciar_web.py`, `wsgi.py`) y al intentar ingresar a una cuenta con el plazo vencido.
- Punto 3: una suscripción por transferencia (ADR-047) no se renueva sola y no bloquea la eliminación; las de
  un proveedor automático, sí. Los eventos de pago se conservan sin la cuenta ni la referencia de suscripción.
- Pruebas: `tests/test_supresion.py`.

## Consecuencias

- La purga es parte del arranque y del ingreso: no hace falta un servicio aparte.
- Los plazos (14 días) y lo que deba conservarse por ley necesitan revisión jurídica antes de operar comercialmente.

## Alternativas descartadas

- *Borrado inmediato de la cuenta*: un adulto que se equivoca, o alguien con la sesión abierta, destruye el progreso
  de todos los chicos sin vuelta atrás.
- *Solo archivar, nunca borrar*: no cumple el derecho de supresión de ADR-026.
