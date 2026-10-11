# ADR-051 — Registro de cuentas y confirmación de pagos en el panel de admin

- **Estado:** Propuesta (planificada, **no implementada**; no autoriza código hasta que Marcos la acepte)
- **Fecha:** 11/10/2026
- **Relacionada con:** [ADR-050](ADR-050-gratuidad-y-puertas-de-pago.md), ADR-032 y ADR-047 (pagos)

## Contexto

Con QR o enlace fijo de Mercado Pago el sistema no sabe qué cuenta pagó. Hoy Marcos confirma con `gestionar_pagos.py`
(línea de comandos). Marcos pidió un flujo propio, **solo dentro de su panel de admin**: ver todas las cuentas
registradas, saber quién subió comprobante, y levantar las restricciones con un solo botón.

## Decisión (plan)

1. **Registro de cuentas** (solo super admin, nada visible para otros roles). Una fila por cuenta:
   alta, correo, producto, concepto de la orden abierta (inscripción/cuota), estado de la orden
   (`pendiente` sin comprobante / `informada` con comprobante / `confirmada` / `rechazada`), hasta cuándo está cubierta
   y cuántos días le quedan para pagar. Filtros: «con comprobante sin confirmar» (la vista de trabajo diario), «vencidas», «todas».
2. **Subida del comprobante** por la familia, desde su pantalla de suscripción, al tocar «ya pagué»: imagen o PDF
   (límite de tamaño y de tipo, validado por contenido, guardado **fuera del repo** y fuera de `static/`, nombre
   aleatorio, servido solo al super admin). La orden pasa a `informada`.
3. **Aviso por correo a Marcos** al llegar un comprobante: dato mínimo (cuenta, concepto, importe, enlace al panel),
   **sin adjuntar el comprobante** ni datos del menor. Requiere un canal SMTP configurado en `.env`; si falla, la orden
   igual queda `informada` y visible en el panel (el correo es un aviso, no el registro).
4. **Confirmar con un botón:** ve el comprobante, pulsa «Confirmar pago» y se ejecuta el mismo `confirmar_orden` que hoy
   (período por calendario, ADR-050). Botón secundario «Rechazar» con motivo. Cada acción queda en un registro de
   auditoría (quién, cuándo, orden). Confirmar es idempotente.
5. **Inscripción:** cubre solo el mes en vigencia; después se paga la cuota del 1 al 10.

## Salvaguardas

- Solo super admin con sesión y CSRF; el resto recibe 404.
- Comprobantes: datos personales de terceros; se borran al confirmar o rechazar tras un plazo corto (a definir) y al
  eliminar la cuenta; entran en la exportación y supresión de datos (ADR-037).
- Un comprobante no es prueba de pago: Marcos lo contrasta con su Mercado Pago antes de confirmar.

## Pendiente de decidir antes de implementar

- Canal de correo (SMTP propio o proveedor) y casilla de destino.
- Plazo de retención de comprobantes.
- Si el panel reemplaza del todo a `gestionar_pagos.py` o convive.
- Reemplazo futuro: con órdenes con preferencia propia de Mercado Pago + webhook firmado, este panel queda como respaldo.
