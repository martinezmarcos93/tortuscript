# ADR-053 — Acceso a desafíos y juegos según los conceptos que requieren

- **Estado:** Aceptada (Marcos, 19/10/2026)
- **Fecha:** 19/10/2026
- **Responsable de decisión:** Marcos
- **Relacionado:** ADR-050 (gratuidad y puertas de pago), ADR-052; `docs/ESPECIFICACION_P1_P6.md` (P5); `docs/ROADMAP_INVENTAR_CON_PYTHON.md`

## Contexto

ADR-050 fija qué unidades del mapa curricular son gratuitas y cuáles premium; lo que queda fuera del mapa (prácticas de
«primeros pasos», Tortuga, Juegos, Tortuaria, Proyectos) queda abierto. Los cursos nuevos de desafíos de transferencia (P5)
y de juegos (L1, L3) quedan fuera del mapa, pero combinan conceptos que sí están en él, algunos premium. Si se aplicara la
regla general, un desafío de Python avanzado quedaría gratis aunque su contenido solo tenga sentido después de pagar.

## Decisión

Decisión de Marcos (19/10/2026): **un ejercicio es gratuito si todo lo que hace falta para resolverlo se aprende en la
versión gratuita; si necesita alguna lección que se desbloquea con el pago, queda bloqueado.**

1. Una lección fuera del mapa puede declarar los conceptos que necesita: `transferencia.conceptos` (desafíos) o `conceptos`
   (juegos y otras lecciones). Son ids de unidades `lecciones` del mapa.
2. `catalogo_producto.unidad_de_cobro(leccion_id)` decide qué unidad cobra esa lección:
   - si la lección está en el mapa, su unidad (como hoy, `unidad_de_leccion`);
   - si no, **la primera unidad premium** entre los conceptos declarados, en el orden del mapa;
   - si ninguno es premium o no declara conceptos, `None`: queda abierta (como hoy).
3. La puerta de pago (`_unidad_del_pedido`) y la marca 💎 del camino usan `unidad_de_cobro` en lugar de `unidad_de_leccion`.
   Al cobrar por una unidad que ya existe, la pantalla de la puerta, el 402 de la API y la regla «solo donde hay pagos
   configurados» no cambian.
4. El validador exige que todo curso de desafíos o de juegos nuevo declare los conceptos de cada lección, para que ninguna
   quede abierta por olvido.

## Consecuencias

- El contenido viejo fuera del mapa no declara conceptos y sigue abierto: no cambia lo que hoy es gratis.
- Agregar o quitar un concepto de una lección puede cambiar si se cobra: el validador y los tests lo dejan a la vista.
- `Curriculum.v1` (contrato con Croco-Script) no cambia: el mapa curricular no se toca.
