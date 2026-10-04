# ADR-047 — Transferencia como primer medio de pago

- Estado: Aceptada
- Fecha: 2026-10-04
- Decisor: Marcos
- Relacionadas: ADR-032, ADR-040, ADR-046

## Contexto

ADR-032 dejó el circuito interno (evento del proveedor → suscripción → acceso con vencimiento) sin ningún
proveedor real detrás. Elegir un procesador de tarjetas, escribir su adaptador y probarlo en su sandbox es
trabajo que conviene hacer cuando se decida lanzar. Mientras tanto hace falta poder cobrar sin depender de
un tercero ni guardar datos de pago.

## Decisión

1. **El primer medio de pago es la transferencia** al alias de quien opera la instalación. Paga el adulto
   dueño de la cuenta; la suscripción cubre todos sus perfiles (ADR-032).
2. **El alias no vive en el repositorio ni en el código**: se configura con `TORTU_PAGO_ALIAS` en el `.env` de
   la instalación, junto con el importe y la duración (`TORTU_PAGO_IMPORTE`, `TORTU_PAGO_DIAS`). Sin alias o
   sin importe la página de suscripción existe, pero no se puede contratar. El alias se muestra recién cuando
   el adulto armó una orden.
3. **Circuito:** el adulto arma una *orden de pago* (queda `pendiente`, con una referencia corta para el
   concepto de la transferencia) → transfiere por fuera de TortuScript → avisa («ya hice la transferencia»,
   `informada`) → quien opera ve el dinero en su cuenta y confirma con `herramientas/gestionar_pagos.py`
   (`confirmada`). **Avisar no da acceso: solo la confirmación lo da.**
4. **La confirmación es un evento más**: entra a `ServicioPagos.aplicar` como `payment_succeeded` del
   proveedor `transferencia`, con el identificador de la orden. Hereda la idempotencia (confirmar dos veces
   no suma días), el vencimiento y los días de gracia. No hay un camino aparte para conceder acceso.
5. **No se renueva sola.** Cada pago cubre un período; renovar antes del vencimiento extiende desde el fin
   del período vigente, y después, desde la fecha de la confirmación.
6. **El importe y la duración los fija el servidor**, nunca el pedido del navegador. Como mucho hay una orden
   abierta por cuenta y producto.
7. **La ventana queda preparada para otros medios.** `pagos.MEDIOS_DE_PAGO` lista cada medio con su
   disponibilidad; la tarjeta de crédito o débito figura como «próximamente». Sumarla es escribir el adaptador
   del proveedor (`pagos.ADAPTADORES`), configurar el secreto de su webhook y marcarla disponible: la página,
   las órdenes y el acceso no cambian.

## Lo que no se guarda

Ni CBU, ni número de tarjeta, ni comprobantes. De una orden queda: producto, medio, importe, referencia,
fechas y una nota opcional de hasta 120 caracteres (quién transfirió). Las órdenes se borran con la cuenta
(ADR-046) y figuran en la descarga de datos del adulto.

## Consecuencias

- Cobrar exige trabajo manual de quien opera: mirar la cuenta y confirmar. `gestionar_pagos.py` sale con
  código 2 cuando hay órdenes informadas sin resolver, para poder programar un aviso.
- Qué contenido es premium sigue siendo una decisión de producto aparte: hoy ninguna unidad lo es.
- Reembolsos y facturación quedan fuera de esta ADR: se resuelven por fuera, y un reembolso se refleja
  quitando el acceso a mano.
- Antes de cobrar de verdad falta la revisión comercial y legal prevista para el lanzamiento.

## Alternativas descartadas

- *Integrar ya un procesador de tarjetas*: agrega un tercero, credenciales y un sandbox que probar, para un
  producto que todavía no se publica.
- *Conceder el acceso cuando el adulto avisa que pagó*: cualquiera obtendría acceso sin pagar.
- *Publicar el alias en la página antes de armar la orden o dejarlo en el repo*: lo expone sin necesidad.
