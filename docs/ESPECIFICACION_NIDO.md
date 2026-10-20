# Especificación — Nido de tortuguitas (ADR-055)

## 1. Núcleo: `tortuscript/nido.py` (puro, sin disco)

```python
TORTUGUITAS_POR_NIDO = 7
MAX_AYUDAS = 6
AYUDAS = ("lupa", "detective", "tortu")          # se guardan; el congelador se suma directo a progreso["congeladores"]
PACK = 3

def cargar_cosmeticos() -> list[dict]           # contenido/cosmeticos.json: [{"id", "nombre", "icono", "tipo"}]
def estado(progreso) -> dict                    # {"tortuguitas", "faltan", "completos", "premios_pendientes",
                                                #  "ayudas": {...}, "cosmeticos": [...], "puesto", "hoy_gano": bool}
def ganar_tortuguita(progreso, hoy) -> bool     # True si nació una hoy (False si ya había nacido hoy)
def elegir_premio(progreso, premio) -> None     # ValueError (mensaje para el chico) si no corresponde
def usar_ayuda(progreso, tipo) -> None          # ValueError si no hay
def equipar(progreso, cosmetico_id | None) -> None
```

- `ganar_tortuguita`: si `hoy` (str ISO) ya está en `nido.dias`, no hace nada. Si no: suma 1, agrega la fecha (últimas
  30), avisa `tortuguita` (`progreso.avisar`); al llegar a 7 deja `tortuguitas = 0`, `completos += 1`,
  `premios_pendientes += 1` y avisa `nido_completo`.
- `elegir_premio(progreso, {"tipo": "cosmetico", "id": X})`: requiere premio pendiente, que X exista y no esté ya en
  `cosmeticos`; lo agrega y descuenta el premio.
  `elegir_premio(progreso, {"tipo": "ayudas", "ayudas": [a, b, c]})`: exactamente 3, cada una en
  `AYUDAS + ("congelador",)`; las guardadas no pueden superar `MAX_AYUDAS` y los congeladores no pueden superar
  `progreso.MAX_CONGELADORES` (si alguna no entra, ValueError y **no** cambia nada).
- Datos dañados (tipos raros, negativos): se tratan como valores por defecto sin lanzar y sin regalar nada.
- No muta nada si lanza ValueError.

## 2. Integración

- `progreso.py`: `VERSION_ESQUEMA = 12`; los 4 campos nuevos en `PROGRESO_INICIAL` (ver ADR). En el punto donde hoy se
  avisa `meta_cumplida`, llamar a `nido.ganar_tortuguita(progreso, hoy)`.
- **Lupa** — `POST /api/lecciones/<id>/pasos/<i>/lupa` (y `/api/practica/lupa` con `leccion`/`paso` en el cuerpo):
  solo `elegir`/`predecir` con 3+ opciones, una vez por intento del paso; descuenta una lupa; devuelve
  `{"tachar": "<texto de una opción incorrecta>"}` (determinista: la primera incorrecta según el orden mezclado que vio
  el chico, o la primera incorrecta del contenido); marca el intento para que, si acierta, el XP sea `XP_REINTENTO`
  y `perfecto` sea False.
- **Detective** — `POST /api/lecciones/<id>/pasos/<i>/detective` con `{"codigo", "entradas"}`: solo `escribir`; corre como
  `evaluar`; si el programa falla al correr devuelve `{"linea": n, "tipo": "error"}`; si la salida difiere,
  `{"linea": n, "tipo": "salida"}` (n = primera línea de la salida, base 1, que no coincide); si está bien, no descuenta.
  Al usarse, suma una pista vista (`pistas_vistas`) como hoy hace `_dar_pista`.
- **Tortu extra**: `usar_ayuda(progreso, "tortu")` suma 1 a `progreso["tutor"]["extra"]` del día; `tutor.restantes` suma
  ese extra solo si es del mismo día. Ruta `POST /api/ayudas/tortu`.
- **Premios y cosméticos**: `GET /api/nido` (estado + catálogo), `POST /api/nido/premio`, `POST /api/nido/equipar`.
  Todas con el mismo control de perfil/sesión que las demás rutas `/api/`.
- Logro nuevo `primer-nido` («Tu primer nido»).

## 3. Interfaz (segunda etapa)

- Inicio/Resumen: el nido con 7 lugares (huevo / tortuguita), «te faltan N», botón «Elegir premio» si hay pendientes.
- Pantalla del premio: cosméticos no obtenidos o pack de 3 ayudas.
- Lección: botón 🔍 en elegir/predecir y 🕵️ en escribir (tras un intento fallido), con el contador; ocultos si hay 0.
- Tortuga: el cosmético puesto se dibuja sobre la tortuga en el lienzo (`dibujarTortuga`) y en el perfil.

## 4. Catálogo inicial (`contenido/cosmeticos.json`)

`sombrero-mago` 🧙, `gorra` 🧢, `corona` 👑, `anteojos` 🕶️, `mono` 🎀, `capa` 🦸, `caparazon-dorado` ✨, `caparazon-arcoiris` 🌈.
