# Modelo de dominio pedagógico — V1 (P2)

**Fundamento:** ADR-052 (Aceptada el 18/10/2026) · **Fase:** P2 de `ROADMAP_PEDAGOGIA_ADAPTATIVA.md` · **Módulo:** `tortuscript/dominio.py`

## 1. Qué es y qué no es

Estima, para cada **concepto**, cuánta evidencia de dominio hay y de qué tipo. Es una **función pura sobre el progreso que ya existe**:

- No agrega claves al progreso ni cambia `VERSION_ESQUEMA` (sigue en 11): **se deriva, no se guarda**.
- No recopila datos nuevos de menores ni hace llamadas externas.
- No es un evaluador (no corrige respuestas) ni toca XP, logros, rachas o repaso.
- No bloquea nada: es información para el planificador (P3) y para la interfaz.
- Determinista: mismo progreso → mismo resultado. Sin azar, sin reloj (no recibe ni lee la fecha de hoy).

## 2. Concepto = unidad de `contenido/mapa_curricular.json`

Las 37 `unidades` del mapa. Solo las de `tipo = "lecciones"` se evalúan (cada una enumera `curso` y `lecciones`); las de `tipo = "proyecto"` quedan fuera del modelo V1.

## 3. Evidencia

El progreso guarda solo el **mejor resultado de cada paso** (`progreso["lecciones"][leccion_id]["pasos"][str(indice)]` = `{"xp", "perfecto", "fecha", "estrellas"?}`). El modelo lee solo eso y las tarjetas de `progreso["repaso"]`.

Cada paso registrado de una lección del concepto, según el `tipo` del paso en el curso, cuenta como evidencia de una **categoría**:

| Tipo de paso | Categoría |
|---|---|
| `elegir` | `reconocimiento` |
| `predecir` | `prediccion` |
| `completar`, `ordenar` | `construccion` |
| `escribir` | `produccion` |
| `explicacion` | (no es evidencia; se ignora) |

Y tiene una **fuerza**:

- Para `elegir`, `predecir`, `completar`, `ordenar` (campo `xp` del registro): `fuerte` si `xp >= 5` (primer intento), `debil` si `1 <= xp <= 4` (con reintentos), `ayudado` si `xp <= 0` (se vio la respuesta).
- Para `escribir`: si el registro tiene `estrellas`: `fuerte` con 3, `debil` con 1 o 2, `ayudado` con 0. Si no tiene `estrellas`: `fuerte` si `perfecto` es `True`, `debil` si no.

Un registro que no sea `dict`, o un `xp`/`estrellas` que no sea entero (los `bool` no cuentan como enteros), se trata como **dañado**: se ignora sin lanzar excepción. Un índice de paso fuera de rango o que no sea un entero decimal corto se ignora. Una lección o un curso que no existen en `cursos` aportan cero evidencia.

## 4. Nivel de dominio del concepto

Sea `disp` el conjunto de categorías con al menos un paso (de cualquier tipo evidenciable) en las lecciones del concepto, según `cursos` (existan o no registros), y `fuertes` el conjunto de categorías con al menos una evidencia `fuerte`.

| Nivel | Estado | Condición (se evalúa de arriba hacia abajo; gana la primera que se cumple) |
|---|---|---|
| 5 | `consolidado` | `disp` no vacío, `fuertes ⊇ disp` **y** hay retención (abajo) |
| 4 | `autonomo` | `disp` no vacío y `fuertes ⊇ disp` |
| 3 | `aplicado` | `len(fuertes) >= min(2, len(disp))` y `len(fuertes) >= 1` |
| 2 | `reconocido` | `len(fuertes) >= 1` |
| 1 | `visto` | hay al menos una evidencia (de cualquier fuerza) |
| 0 | `sin_evidencia` | no hay ninguna evidencia |

**Retención diferida:** existe al menos una tarjeta de `progreso["repaso"]` cuya clave `"{leccion_id}:{indice}"` pertenece a una lección del concepto, con `caja >= 3` y `aciertos >= 2` (enteros válidos; una tarjeta que no sea `dict` se ignora).

Propiedades que deben cumplirse (y probarse):

1. **Un solo acierto no basta** para pasar de `reconocido` si el concepto tiene dos o más categorías.
2. **Nunca castiga:** agregar evidencia `debil` o `ayudado` no puede bajar el nivel. Agregar evidencia nunca baja el nivel (monotonía).
3. **Conceptos sin evidenciables** (`disp` vacío) quedan en `sin_evidencia`, nunca más.
4. **Idempotente y sin efectos:** no modifica el `progreso` recibido (probar comparando una copia profunda).

## 5. API

```python
ESTADOS = ("sin_evidencia", "visto", "reconocido", "aplicado", "autonomo", "consolidado")
CATEGORIAS = ("reconocimiento", "prediccion", "construccion", "produccion")

def cargar_mapa() -> dict:
    """Devuelve `unidades` de contenido/mapa_curricular.json."""

def estado_concepto(progreso: dict, cursos: list, unidad_id: str, mapa: dict | None = None) -> dict:
    """KeyError si `unidad_id` no está en el mapa o no es de tipo 'lecciones'. Devuelve:
    {"unidad": str, "nivel": int, "estado": str,
     "disponibles": [categorías ordenadas], "fuertes": [categorías ordenadas],
     "evidencias": {categoría: {"fuerte": n, "debil": n, "ayudado": n}},   # solo categorías en `disponibles`
     "retencion": bool}"""

def dominio(progreso: dict, cursos: list, mapa: dict | None = None) -> dict:
    """{unidad_id: estado_concepto(...)} para todas las unidades 'lecciones' del mapa, en orden de inserción del mapa."""
```

`mapa=None` usa `cargar_mapa()`. `cursos` es la lista de `tortuscript.contenido.todos_los_cursos()`. Un `progreso` que no sea `dict`, o cuyas ramas `lecciones`/`repaso` no sean `dict`, se trata como vacío (no lanza).

## 6. Fuera de V1 (a propósito)

Persistir el estado, pesos estadísticos, olvido por tiempo, clasificación de tipos de error (conceptual vs sintáctico), proyectos integradores como evidencia, IA. Cualquiera de ellos requiere una decisión propia.

## 7. Limitaciones conocidas

- El progreso solo conserva el **mejor** resultado por paso: no hay historial de intentos, así que no se puede medir "cuántos intentos" ni "cuánto tiempo". `fuerte/debil/ayudado` es todo lo que la fuente permite sin ampliar datos.
- En `primeros-pasos` el XP de `escribir` se paga por `ejercicios`, no por `lecciones[...].pasos`; V1 usa el flag `perfecto` del registro del paso.
- Que el modelo diga `autonomo` no demuestra aprendizaje; es una estimación explicable de la evidencia disponible.
