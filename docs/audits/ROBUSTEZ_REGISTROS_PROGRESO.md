# Robustez ante registros de repaso dañados — contrato y limitaciones

**Origen:** backlog §5-bis de `INFORME_INTEGRACION_PEDAGOGICA_2026-10-15.md` (hallazgo del PR #24, ahora contrastado por ejecución).
**Alcance:** `tortuscript/practica.py` y la lectura de `repaso[...]['proximo']` en `tortuscript/catalogo_producto.py`.
**Fuera de alcance:** esquema (sigue en v11), XP, rachas, logros, ejercicios históricos, intervalos (1, 2, 4, 8, 16 días).

## 1. Qué se reproducía

Un perfil que es JSON válido (pasa `_migrar`, que solo normaliza el primer nivel) pero con datos internos dañados hacía lanzar
excepciones no capturadas. **[EJECUTADO antes del cambio]** 23 de las 33 pruebas nuevas fallaban o daban error (el ejecutor contó
33 fallos y 50 errores porque cuenta cada subcaso; algunas fallaban solo porque `diagnosticar` aún no existía).

A nivel HTTP, **`GET /api/estado` devolvía 500** con 4 de los 6 defectos probados (clave no numérica, fecha de paso inválida,
`proximo` inválido y tarjeta que no es objeto). Con los 2 de caja dañada el servidor no fallaba, pero la tarjeta dañada se contaba
como válida. El estado general calcula `practica_pendientes` con `practica.pendientes`.

Excepciones observadas: `ValueError` (clave `abc`, fechas), `TypeError`
(`fromisoformat` con no-cadena, `<=` entre tipos), `AttributeError` (`.get` sobre cadena/lista/entero/`None`), `OverflowError`
(`9999-12-31` + 1 día). Dos defectos eran **silenciosos**: la clave `"-1"` se leía como el último paso de la lección (una
tarjeta que nadie hizo), y en el catálogo una fecha como `"0000"` daba «repasar» (comparación de cadenas).

## 2. Contrato

Principio: **un registro dañado se aísla; nunca se interpreta con una suposición.** No se inventa un vencimiento, no se
corrige un tipo, no se convierte en tarjeta nueva, no se descarta el perfil y **no se escribe nada al leer**.

| Dato | Válido | Dañado → comportamiento |
|---|---|---|
| Clave de paso en `lecciones[id].pasos` | Entero decimal ASCII canónico (`"0"`, `"12"`) | `"abc"`, `""`, `"-1"`, `"1.5"`, `"01"`, `" 2"`, `"+1"`, `"٣"`: el paso se ignora |
| `lecciones[id]` / `pasos` / registro de paso | Objeto (`pasos` ausente o `null` = vacío) | No es objeto: se ignora la lección o el paso |
| `fecha` del paso | `AAAA-MM-DD` canónica y real; ausente o `""` = progreso viejo (ya toca, como antes) | Mal formada, de otro tipo, o `9999-12-31` (el +1 día no existe): el paso se ignora |
| `repaso[clave]` (tarjeta) | Objeto. Sin tarjeta guardada = tarjeta nueva | Cualquier valor que no sea objeto (incluido `null`, `""`, `0`, `[]`): la tarjeta se ignora |
| `caja` | Entero (no `bool`) de 0 a `MAX_CAJA` (5); ausente = 0 | Cadena, decimal, `bool`, negativa, mayor que 5, `null`: se ignora |
| `proximo` | `AAAA-MM-DD` canónica; ausente, `null` o `""` = sin programar (usa la fecha del paso, como antes) | Cualquier otro valor (incluidos `0`, `{}`, `[]`, `False`): se ignora |
| Contenedores `lecciones` / `repaso` que no son objeto | — | Equivalen a vacíos |

La fecha canónica se exige porque Python acepta formas que nunca escribimos (`20260901`, `2026-W36-1`) y el catálogo compara
cadenas.

**Lo que se conserva:** el resto del progreso, las tarjetas sanas (mismo orden, mismos datos y misma elegibilidad), los
intervalos y el XP. Una prueba comprueba que `candidatos`, `pendientes`, `elegir` y `diagnosticar` **no modifican** el perfil.

**Observabilidad (sin `except Exception`):** `candidatos` avisa por `logging.warning` cuántos registros ignoró y cuáles
(primeros cinco); `practica.diagnosticar(progreso, cursos, hoy=None)` devuelve la lista `{leccion, paso, motivo}` sin tocar
nada. Un perfil sano no escribe en el log.

### `registrar` (escritura tras una respuesta real)
La web solo deja responder tarjetas que `elegir` ofreció, así que una tarjeta aislada no llega acá. En el dominio, si la
tarjeta guardada está dañada no hay información que preservar: se parte de cero con lo válido y se deja un warning.
Tarjeta que no es objeto → nueva; `caja` / `aciertos` / `fallos` inválidos → 0 (los válidos se conservan); `repaso` que
no es objeto → se reemplaza por uno vacío. El resultado es siempre una tarjeta sana con `proximo` canónico.

### Catálogo (`Progress.v1`)
`_evidencia_lecciones` usa `practica.fecha_programada`: solo una fecha válida y vencida marca «repasar».

## 3. Archivos
- `tortuscript/practica.py` — validación explícita y pequeña (`_fecha_iso`, `_caja_valida`, `_indice_de_paso`, `_analizar`), `diagnosticar`, `fecha_programada`, `registrar` robusto.
- `tortuscript/catalogo_producto.py` — usa `fecha_programada` (3 líneas).
- `tests/test_robustez_registros_progreso.py` — 33 pruebas: dominio, corrupción parcial, `registrar`, catálogo y HTTP (`/api/estado`, `/practica`, `/`).

## 4. Limitaciones y pendientes (no se tocaron)
1. **Las tarjetas aisladas quedan fuera del repaso** hasta que alguien repare el dato: no se las readmite como nuevas porque
   eso cambiaría su elegibilidad sin evidencia. Se necesita una política de reparación explícita (¿herramienta de
   mantenimiento?, ¿migración v12?) que implica decidir qué se pierde; queda como decisión separada.
2. **`ejercicios` con clave no numérica** hace fallar `_estado` (`int(k)` en `web/app.py:556`): **[EJECUTADO]** `ValueError`. Es la
   misma clase de defecto, pero toca los ejercicios históricos y no se cambió.
3. **Registro de paso sin `xp`** hace fallar `progreso.registrar_paso_leccion` (`KeyError: 'xp'`) **[EJECUTADO]**; es la ruta de XP de
   lecciones, fuera de esta unidad.
4. No se cubrió el camino de lecciones (`motor.lecciones_planas`) ante registros dañados más allá de lo que ejercita `/api/estado`
   en las pruebas HTTP.
5. El aviso en el log se emite en cada cálculo del estado mientras el dato siga dañado (puede repetirse).
