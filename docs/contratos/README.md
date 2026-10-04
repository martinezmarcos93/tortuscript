# Contratos entre TortuScript y Croco-Script (v1)

Estado: definidos y probados del lado de TortuScript (ADR-037). Croco-Script es otro repositorio y **no importa
código de TortuScript**: implementa estos contratos y debe pasar los mismos vectores de prueba.

| Contrato | Qué es | Dónde está |
|---|---|---|
| `Identity.v1` | Identificadores opacos de cuenta y perfil | `tortuscript/federacion.py::identidad_v1` |
| `Entitlement.v1` | Estado de acceso a un producto | `acceso_v1` + `GET /cuenta/acceso?producto=` |
| `Authorization.v1` | Token firmado para pasar de un producto al otro | `emitir_autorizacion` / `validar_autorizacion` |
| `Progress.v1` | Resumen de progreso por curso que publica cada producto | `progreso_v1` |
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

## Decisiones abiertas (de Marcos)

- Dominios definitivos (`croco.tortuscript.com` u otro) y la URL de entrada de Croco-Script.
- Si Croco-Script consultará el acceso en línea (`Entitlement.v1`) además de confiar en el token al entrar: hace
  falta si una suscripción cancelada debe cortar una sesión ya abierta de Croco-Script.
