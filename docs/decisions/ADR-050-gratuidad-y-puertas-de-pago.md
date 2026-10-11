# ADR-050 — Qué es gratis y cuándo se pide pagar

- **Estado:** Aceptada por Marcos el 11/10/2026 (con las decisiones de la sección «Decisiones de Marcos»)
- **Fecha:** 2026-10-11
- **Decide:** Marcos. Las secciones «Propuesta» son el razonamiento original; lo que rige está en «Decisiones de Marcos».
- **Relacionadas:** ADR-019 (estados de acceso), ADR-032 (pagos y entitlements), ADR-036/037 (Croco-Script), ADR-040, ADR-047 (transferencia)

## Contexto

ADR-019 y `PRODUCTO_V1.md` dejaron abierta la política: «ofrecer un recorrido inicial suficientemente útil de forma gratuita y
usar contenido posterior, proyectos o niveles avanzados como superficie premium». Hoy **ninguna unidad es premium**: el
catálogo ya sabe declarar `estado_acceso` por unidad (`gratuito`, `premium`, `prueba`…) y `catalogo_producto.estado_acceso`
lo interpreta, pero **nada lo hace cumplir**: las rutas de lección no consultan el acceso. Lo que sí existe es el cobro: un
pago por transferencia concede un **período de 30 días** (`TORTU_PAGO_DIAS`), no se renueva solo, tiene 7 días de gracia y
cada pago lo confirma una persona a mano (ADR-047).

## Los números (medidos en el catálogo del 11/10/2026)

| Itinerario | Unidades | Lecciones |
|---|---|---|
| Alfabetización tecnológica | 16 | 16 |
| Python fundamentos | 7 | 9 |
| Web esencial | 4 | 9 |
| SQL fundamentos | 8 | 8 |
| Proyecto integrador | 2 | (proyectos) |
| **TortuScript** | **37** | **42 + 2 proyectos** |

Croco-Script (nivel avanzado, 16–20 años): cursos `python-datos` (57 tareas), `orquestacion-streaming-llm` (33),
`desarrollo-aplicaciones` y `cybersecurity-lab` (68), cada uno con su unidad inicial.

## Decisiones de Marcos (11/10/2026) — lo que rige

1. **Gratis: 19 unidades / 20 lecciones** (Alfabetización completa + primera unidad de Python, Web y SQL). Tienen que alcanzar para
   enganchar al chico y convencer al adulto de que es un producto de calidad.
2. **Una sola puerta con renovación mensual.** Modelo: **inscripción** (primer pago) y **mantenimiento mensual** de la **mitad**
   de la inscripción: más atractivo para la familia y ingreso constante para el negocio. Importes (ARS):

   | Producto | Inscripción (primer pago) | Mantenimiento mensual |
   |---|---|---|
   | TortuScript Premium | 30.000 | 15.000 |
   | Croco-Script | 60.000 | 30.000 |

3. **Promociones y referidos:** habrá promociones con enlaces de referido; el usuario obtiene descuentos cuando un referido paga
   la inscripción (en TortuScript y en Croco-Script). **Diseño pendiente de análisis**, incluido el rol de la inteligencia
   artificial; no se implementa hasta una ADR propia.
4. **Croco-Script: sin prueba de 7 días** (demasiado). En su lugar, **prueba gratuita de los primeros 3 niveles del primer curso**.
   Esto exige ampliar el contrato de entrada (hoy `Authorization.v1` exige `ent.activo: true`): ver «Consecuencias para Croco-Script».

5. **Ciclo mensual por calendario (11/10/2026, tarde).** La cuota de cada mes se paga **del 1 al 10**; si el día 11 no está
   paga, **se pausa el acceso premium** (lo gratis y el progreso se conservan). El cobro se hace con **dos enlaces/QR de Mercado
   Pago por producto**: uno de **inscripción** y otro de **cuota mensual**.

## Cómo funciona el ciclo (implementado)
- **Cuota del mes M:** se paga del 1 al 10 de M y cubre hasta el 10 del mes M+1 inclusive. El 11 a las 00:00 **hora de Argentina**
  se corta (`entitlements.expires_at`); Croco-Script se entera por `Entitlement.v1` en menos de 5 minutos.
- **Inscripción:** cubre **dos meses** (el actual y el siguiente), igual que dos cuotas (30.000 = 2 × 15.000; 60.000 = 2 × 30.000).
  La primera cuota se paga del 1 al 10 del mes que sigue a esos dos. *(Supuesto de implementación: confirmar con Marcos.)*
- **Pagar tarde** está permitido: quien paga el día 15 cubre el mes en curso (no se cobran meses sin acceso). **Pagar por adelantado
  más allá del mes en curso no**: si la cuota de este mes ya está paga, la orden siguiente se abre el día 1.
- **Quién ya se inscribió** se deduce de sus órdenes confirmadas; si deja vencer meses y vuelve, paga la **cuota**, no una inscripción
  nueva. *(Supuesto: confirmar con Marcos.)*
- **Pausar ≠ borrar:** al pasar el 10 sin pago, `tiene_entitlement` da `false`; la puerta dice «el acceso Premium está pausado» y no
  se pierde nada.
- **Aviso:** del 1 al 10, mientras la cuota del mes no esté paga, el inicio muestra «Quedan N días para pagar la cuota».

## Cobro automático: lo que se sabe y lo que no
Un enlace de pago estático de Mercado Pago **no lleva la cuenta de quien paga**, así que no alcanza para habilitar solo: hoy
confirma una persona viendo el pago en Mercado Pago (`gestionar_pagos.py`). Para habilitar **automáticamente** hace falta que cada
orden genere su **propia preferencia de pago por API** con `external_reference` = la orden y una `notification_url`: Mercado Pago
avisa por webhook firmado (HMAC, `x-signature`) y el adaptador confirma la orden sin intervención. Requiere las credenciales de la
cuenta de Mercado Pago de Marcos (access token y clave del webhook) y probarlo contra su entorno de pruebas. Qué hace Mercado Pago
con una transferencia bancaria común (no con su dinero en cuenta, tarjeta o QR) **no está verificado**: se verifica al integrarlo.

## Propuesta

### 1. Un «nivel» es una unidad
Para el chico, un nivel es una **unidad** del catálogo (la que hoy se completa y desbloquea la siguiente). Se mide en
unidades, no en lecciones, porque las unidades son lo que ven en el camino.

### 2. TortuScript: 20 lecciones gratis (≈ la mitad), el resto con Premium
**Gratis para siempre:** Alfabetización completa (16 unidades) **más la primera unidad de cada itinerario** (`python-puente`,
`web-html-estructura`, `sql-tablas`): **19 unidades, 20 de 42 lecciones**. Con eso el chico llega a escribir su primer
Python, su primera página y su primera consulta —el «ya puedo»— y elige por dónde seguir con una muestra real de cada camino.

**Premium:** el resto de Python, Web y SQL y los proyectos integradores (**18 unidades, 22 lecciones y 2 proyectos**).

### 3. Una sola puerta, no una cada N niveles
Se propone **una puerta de pago** (al terminar el tramo gratis), no repetirla cada cierto número de niveles:

- El acceso ya es **por período** (30 días) y una suscripción activa desbloquea **todo** Premium para todos los perfiles
  (ADR-032). Pedir de nuevo «cada N niveles» obligaría a cobrar por tramos, y con transferencia manual cada cobro es trabajo
  tuyo y fricción para la familia: tres o cuatro puertas multiplican ambas.
- **«Volver a pedir dinero» = renovar el período.** Se avisa con un cartel 7 días antes de vencer y hay 7 días de gracia
  (ya implementados). Quien deja vencer conserva todo lo gratis y **todo su progreso** (ADR-032: cancelar no borra nada);
  lo premium vuelve a mostrarse bloqueado, con su avance intacto.
- Alternativa B (si preferís pagar por tramos): cada itinerario premium se desbloquea por separado (3 puertas: Python,
  Web, SQL). Funciona con el modelo actual de entitlements ampliado a un entitlement por itinerario, pero triplica los
  cobros manuales. **No se recomienda mientras la confirmación sea manual.**

### 4. Cómo se ve la puerta (reglas)
1. Aparece **al intentar abrir** la primera lección premium, nunca a mitad de una lección ni de un ejercicio.
2. Dice qué logró el chico («terminaste 19 unidades»), qué sigue y que **lo decide un adulto**; el botón lleva a
   `/cuenta/suscripcion`. Sin cuenta de adulto con sesión no hay forma de pagar desde el perfil del chico.
3. Lo premium **se ve en el camino** con candado (el chico sabe qué hay), pero no se abre.
4. La decisión se toma **en servidor** por unidad y perfil (ADR-032: el navegador nunca decide). Un acceso dado a mano o un
   administrador entran igual que hoy.
5. Los umbrales viven en el **catálogo** (`estado_acceso` por unidad), no en el código: se pueden mover sin tocar el
   motor, tras ver cómo se comporta la primera cohorte.

### 5. Croco-Script (reemplazado por la decisión 4: 3 niveles gratis en vez de 7 días)
- **Sin nivel gratis en v1.** `Authorization.v1` exige `ent.activo: true`; un nivel gratis obligaría a un contrato nuevo.
- **Prueba de 7 días** concedida como entitlement con vencimiento (ya soportado: `expires_at`), una vez por cuenta y a
  pedido del adulto. La puerta de pago de Croco-Script es su plan propio (ya existe, `TORTU_PAGO_IMPORTE_CROCO`).
- El nivel gratis de TortuScript hace de «muestra» para quien llega; la tarjeta «Siguiente paso» y una página de
  presentación hacen el resto.

## Cómo se implementa (fases; ninguna empieza sin aceptar esta ADR)
1. **Catálogo:** marcar `estado_acceso` en `catalogo_curricular_v1.json` (19 `gratuito`, 18 `premium`, proyectos `premium`).
2. **Servicio de acceso por unidad:** `AccesoProducto.puede_ver_unidad(perfil, unidad)` = unidad gratuita **o** acceso
   comercial vigente **o** admin. Se aplica en las rutas de lección, ejercicios y proyectos (no solo en la interfaz).
3. **Pantalla de puerta** y candados en el camino/mapa; cartel de renovación a 7 días del vencimiento.
4. **Tests:** perfil sin acceso no abre una lección premium ni por URL directa; con acceso sí; al vencer vuelve a bloquearse
   sin perder progreso; admin y acceso manual pasan; el catálogo no deja unidades sin estado.
5. **Medición** (eventos estructurados, sin datos personales): `puerta_vista`, `puerta_clic_plan`, `pago_informado`,
   `pago_confirmado`, para validar los umbrales antes de cobrar a escala.

## Consecuencias para Croco-Script
- Un nivel gratis significa que un perfil **sin** plan puede entrar. Hay que definir en el contrato (una versión nueva, sin romper
  `Authorization.v1`) un acceso `gratuito` distinto de `activo`, y que Croco-Script solo abra las 3 primeras unidades del primer
  curso y pida el plan para el resto. Hasta entonces, TortuScript no ofrece el paso a Croco-Script a cuentas sin plan salvo
  admin.
- Con inscripción distinta de mantenimiento, el cobro necesita saber si una cuenta **ya pagó la inscripción** (primer pago por
  producto) para ofrecer el importe correcto; hoy `TORTU_PAGO_IMPORTE*` es un único importe por producto.

## Preguntas que quedaron abiertas
- Descuentos exactos de los referidos y su mecánica antifraude (ADR propia, después).
- Período anual, política de reembolsos y revisión comercial/legal antes de cobrar de verdad.
- Si la inscripción se paga de nuevo tras un tiempo largo sin renovar (hoy se asume que no: se reactiva con el mantenimiento).

## Lo que se pidió decidir originalmente (histórico)
1. ¿Confirmás **19 unidades / 20 lecciones gratis** (Alfabetización + primera unidad de cada camino)? Opciones: más cerca de
   un tercio (Alfabetización + `python-puente` solamente) o más generosa (+ el itinerario Python completo).
2. ¿**Una puerta con renovación mensual** (recomendado) o **tres por itinerario** (alternativa B)?
3. **Importe y período:** el precio de TortuScript Premium y del plan de Croco-Script (en ARS) y si el período sigue en 30 días
   o se ofrece también uno anual. No se fijan acá: hoy se configuran por entorno.
4. ¿**Prueba de 7 días** de Croco-Script, o prefieren un nivel gratis (requiere cambiar el contrato)?
5. Antes de cobrar de verdad: revisión comercial y legal ya prevista (ADR-047) y la política de reembolsos.

## Consecuencias
- Cambiar qué es gratis es editar el catálogo; el contenido y el evaluador no se tocan.
- Una familia que paga un mes y se va conserva el progreso y lo gratis; lo premium se re-bloquea.
- La decisión final de precios y límites queda explícitamente en manos de Marcos.
