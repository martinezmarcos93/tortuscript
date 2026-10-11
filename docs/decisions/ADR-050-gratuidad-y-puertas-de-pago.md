# ADR-050 — Qué es gratis y cuándo se pide pagar

- **Estado:** Propuesta (no autoriza implementar; la aceptan Marcos o un cambio de estado explícito)
- **Fecha:** 2026-10-11
- **Decide:** Marcos. Este documento propone números y deja las preguntas abiertas al final.
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

### 5. Croco-Script
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

## Qué falta decidir (Marcos)
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
