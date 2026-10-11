# Contratos entre TortuScript y Croco-Script (v1)

Estado: definidos, implementados y probados en los dos productos (ADR-037); verificados entre sí por HTTP el 11/10/2026. Croco-Script es otro repositorio y **no importa
código de TortuScript**: implementa estos contratos y debe pasar los mismos vectores de prueba.

| Contrato | Qué es | Dónde está |
|---|---|---|
| `Identity.v1` | Identificadores opacos de cuenta y perfil | `tortuscript/federacion.py::identidad_v1` |
| `Entitlement.v1` | Estado de acceso a un producto; Croco-Script lo consulta para cortar una sesión abierta | `acceso_v1` + `GET /federacion/v1/acceso?cuenta=&producto=` |
| `Authorization.v1` | Token firmado para pasar de un producto al otro | `emitir_autorizacion` / `validar_autorizacion` |
| `Progress.v1` | Resumen de progreso por curso que publica cada producto | `progreso_v1` |
| `ProgressQuery.v1` | Croco-Script pregunta el `Progress.v1` de un perfil (prerrequisitos entre productos) | `GET /federacion/v1/progreso` |
| `Supresion.v1` | TortuScript pide a Croco-Script borrar o exportar los datos de un perfil o cuenta | `federacion.emitir_operacion` + `federacion_operaciones.py` |
| `Curriculum.v1` | Identificadores de itinerarios y unidades que se pueden nombrar como prerrequisito | `curriculum-v1.json` (lo genera `herramientas/publicar_contratos.py`) |

## Authorization.v1 — transición autenticada

1. El chico, con su perfil activo en TortuScript, abre `GET /cuenta/ir/croco-script`.
2. TortuScript comprueba **en servidor** que la cuenta tiene el acceso (`AccesoProducto`, ADR-040). Sin acceso: 403.
3. TortuScript redirige a `<url de Croco-Script>?autorizacion=<token>` con `Referrer-Policy: no-referrer`.
4. Croco-Script valida el token y crea **su propia** sesión. El token no es una sesión.

El token tiene el formato compacto de un JWT firmado con HS256:

```
cabecera: {"alg": "HS256", "kid": "<id de la clave>", "typ": "JWT"}
cuerpo:   {"v": 1, "iss": "tortuscript", "aud": "croco-script",
           "sub": "<id opaco del perfil>", "acc": "<id opaco de la cuenta>",
           "ent": {"producto": "croco-script", "activo": true},
           "iat": <unix>, "exp": <iat + 60>, "jti": "<único>"}
```

### Lo que el receptor DEBE comprobar

- `alg` es exactamente `HS256` (nunca se usa el algoritmo que diga el token para decidir cómo validar).
- La firma, con la clave del `kid` indicado, en tiempo constante.
- `v == 1`, `iss == "tortuscript"`, `aud` es el propio producto.
- `iat` y `exp` son enteros, `exp - iat <= 60`, y ahora está entre `iat - 5 s` y `exp`.
- `sub`, `acc` y `jti` son textos no vacíos.
- `ent.producto` es el propio producto y `ent.activo` es `true`.
- El `jti` no se usó antes: hay que recordarlo hasta `exp` y rechazar el segundo uso.

Los vectores de `authorization-v1.vectores.json` cubren cada regla: uno válido y quince que deben rechazarse.

### Lo que el token NO lleva

Correo, nombre o alias del chico, edad, progreso, datos de pago, ni nada que identifique a una persona fuera del
ecosistema. Croco-Script identifica al alumno por `sub` y guarda su propio progreso bajo ese identificador.

### Clave de servicio

Un secreto de al menos 32 caracteres compartido entre los dos servidores, identificado por `kid`. Para rotarlo: el
receptor acepta la clave nueva y la vieja a la vez, TortuScript empieza a firmar con la nueva y, pasado un minuto, el
receptor descarta la vieja. La clave nunca va al navegador ni al repositorio.

## Curriculum.v1 — prerrequisitos entre productos

`curriculum-v1.json` lista los itinerarios de TortuScript y, en orden, las unidades de cada uno:

```
{"contrato": "Curriculum.v1", "producto": "tortuscript", "version_curricular": "1",
 "itinerarios": [{"id": "sql-fundamentos", "unidades": ["sql-tablas", "sql-select", …]}, …]}
```

- Un curso de Croco-Script declara sus prerrequisitos con esos identificadores: un `id` de itinerario (hay que
  completarlo entero) o un `id` de unidad. Ningún identificador se repite entre itinerarios y unidades.
- Solo lleva identificadores y orden: ni títulos, ni contenido, ni reglas comerciales.
- No se edita a mano: sale del catálogo curricular (`docs/catalogo_curricular_v1.json`). Un test de TortuScript
  falla si lo publicado quedó desactualizado.
- Croco-Script lo copia a su repositorio y valida su catálogo contra él (el equivalente de
  `federacion.prerrequisitos_desconocidos_v1`): un prerrequisito desconocido es un error de publicación. Si un
  perfil cumple o no un prerrequisito lo dice `Progress.v1` de TortuScript.
- `version_curricular` cambia cuando se quita o renombra un identificador; agregar unidades no la cambia.

Los prerrequisitos de las tres fuentes del nivel avanzado (`docs/catalogo_avanzado_v1.json`) ya se validan así.

## Cómo se conectan los dos productos

| En TortuScript (`.env`) | En Croco-Script (`.env`) |
|---|---|
| `TORTU_CROCO_URL=<dirección de Croco-Script>/entrar` | — |
| `TORTU_CROCO_CLAVE=<secreto>` y `TORTU_CROCO_KID=k1` | `CROCO_CLAVES=k1:<el mismo secreto>` |
| — | `CROCO_URL_TORTUSCRIPT=<dirección de TortuScript>` |
| — | `CROCO_ACCESO_URL=<dirección de TortuScript>/federacion/v1/acceso` (corte de sesión, `Entitlement.v1`) |
| — | `CROCO_PROGRESO_URL=<dirección de TortuScript>/federacion/v1/progreso` (prerrequisitos que bloquean, `ProgressQuery.v1`) |
| `TORTU_PAGO_IMPORTE_CROCO=<pesos>` (para vender el plan) | — |

Sin esas variables no hay puente: TortuScript no muestra el botón y Croco-Script funciona en modo local.

## Consultas y pedidos entre servidores (v1)

**Croco-Script pregunta, TortuScript responde** — `Entitlement.v1` y `ProgressQuery.v1`, ambos `GET` con
`Authorization: Croco-HMAC kid=<kid>, ts=<unix>, firma=<firma>`; `firma` = HMAC-SHA256 de `<ts>.<producto>.<cuenta|perfil>`
(base64 para direcciones, sin `=`). Se rechaza lo que difiera más de 60 s del reloj. Cualquier fallo de autenticación
responde `401 {"error": "autorizacion_invalida"}` sin decir cuál; el motivo va al log, sin identificadores.
Respuestas con `Cache-Control: no-store`.

- `Entitlement.v1`: `200` siempre que la firma valga; `activo` es `false` para una cuenta desconocida, borrada o sin acceso
  (un administrador tiene acceso, igual que al entrar).
- `ProgressQuery.v1`: `200` con `Progress.v1` solo si el perfil existe, está activo y su cuenta tiene acceso al producto que
  pregunta; si no, `404 {"error": "perfil_inexistente"}` (decisión: a un perfil sin acceso se le contesta como a uno
  inexistente, para no revelar su estado). El resumen es **por itinerario** (`curso` = id de itinerario), con las unidades
  completas en `lecciones_completadas` y sin nombre, correo ni XP. Un itinerario sin actividad no figura.

**TortuScript pide, Croco-Script ejecuta** — `Supresion.v1`: `POST <origen de Croco-Script>/federacion/v1/operacion` con
`Authorization: Bearer <token>`. Se emite al eliminar un perfil archivado (`suprimir_perfil`), al purgar una cuenta vencida
(`suprimir_cuenta`) y, por perfil, al descargar los datos del adulto (`exportar_perfil`). Un borrado que no llegó se guarda
en `instance/operaciones_pendientes.json` y se reintenta (al arrancar y en cada purga) con un token nuevo.

**Retención de respaldos:** pendiente de decisión de Marcos; un borrado no reescribe los respaldos ya hechos.

## Decisiones abiertas (de Marcos)

- Dominios definitivos (`croco.tortuscript.com` u otro) y la URL de entrada de Croco-Script.
- Política si Croco-Script no puede preguntar el acceso: hoy «no se sabe» deja la sesión abierta (se prefiere no dejar a
  nadie afuera por un fallo de red); cambiarla a «se corta» es una decisión de hospedaje.
