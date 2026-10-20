# Guía para escribir pistas graduadas (P4)

Las pistas ayudan a pensar; no dan la respuesta. Desde P4, un paso rápido (`elegir`, `predecir`, `completar`, `ordenar`)
puede tener, además de `pista`, una lista `pistas` de 1 a 3 textos que se muestran **de a uno**, uno por cada error:

| Error | Se muestra | Qué hace |
|---|---|---|
| 1.º | `pistas[0]` | **Orienta la atención**: dónde mirar. |
| 2.º | `pistas[1]` | **Recuerda el concepto** que hace falta. |
| 3.º en adelante | `pistas[2]` (o la última que haya) | **Casi la solución**, sin decirla. |

Después del 2.º error aparece «Ver respuesta», igual que antes: la solución completa la da ese botón, nunca una pista.

`pista` sigue siendo obligatoria: es la que se usa si un paso no tiene `pistas` y la que ven las versiones anteriores.

## Reglas

1. **Ninguna pista contiene la respuesta.** El validador marca error si una pista incluye literalmente la opción correcta de un `elegir` o `predecir`.
2. **Cada pista agrega algo.** Si la segunda dice lo mismo que la primera con otras palabras, sobra.
3. **Hablan del error probable, no del alumno.** «Fijate qué vale `n` después de la segunda vuelta», no «Te equivocaste».
4. **Cortas**: una o dos oraciones, con voseo, como el resto del contenido.
5. **Sin castigo ni presión**: nada de «¡otra vez mal!» ni cuentas regresivas.
6. Si el paso tiene una sola trampa clara, una o dos pistas alcanzan: no hace falta llegar a tres.

## Ejemplo (`predecir`)

```json
{
  "tipo": "predecir",
  "codigo": "n es 2\nrepetir 3 veces:\n    n es n * 2\nmostrar n",
  "opciones": ["8", "16", "6"],
  "correcta": 1,
  "pista": "Seguí el valor de n vuelta por vuelta.",
  "pistas": [
    "Anotá cuánto vale n antes de empezar a repetir.",
    "En cada vuelta, n pasa a valer el doble de lo que valía.",
    "Son tres vueltas: 2 → 4 → … → ?"
  ]
}
```
