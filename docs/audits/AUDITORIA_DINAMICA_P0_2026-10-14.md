# Auditoría dinámica P0 — línea de base ejecutada

**Fecha:** 14/10/2026
**Base:** `prod` en `2ac6b2a` (idéntica en código a `main` en `717d621`; `prod` solo suma documentación).
**Naturaleza:** ejecución real de tests, validador y lectura del código. Complementa el baseline estático de
`BASELINE_PEDAGOGIA_ADAPTATIVA_2026-10-14.md`.

## 1. Resultados de ejecución

| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests` | 1015 tests, **1 fallo preexistente**, 2 omitidos (≈290 s) |
| `python herramientas/validar_contenido.py` | 0 errores; 2 avisos preexistentes (ver §3) |
| `python -m unittest tests.test_contenido` | 39 tests, OK |
| `docs/contratos/curriculum-v1.json` | «está al día» |
| `python herramientas/jugar_cursos.py` (interfaz real) | **No ejecutado**: Playwright no está instalado en el entorno |

### Fallo preexistente (no es regresión de este trabajo)

`test_federacion_respuestas.TestOperaciones.test_un_perfil_de_otra_cuenta_no_se_reintenta` afirmaba que un 409 se
daba por resuelto. El PR #15 (`main`) cambió el contrato —el 409 se conserva en cola como `conflicto_409` para revisión
manual, y `solicitar` devuelve `False`— y dejó este test viejo sin actualizar. `main` ya fallaba antes de esta misión.
Corrección propuesta en la rama `fix/test-409-contrato-obsoleto` (solo test; el código de producción no cambia).

## 2. Contrastes con el baseline estático

Todo lo del baseline se confirmó, con estos matices:

1. **Señales de desempeño realmente persistidas** (`tortuscript/progreso.py`):
   - Por paso de lección: `{xp, perfecto, fecha, estrellas?}`. Primer intento, reintentos y respuesta revelada solo
     se distinguen **indirectamente** por el XP (5 / 2 / 0). No se guarda cantidad de reintentos, pistas por paso
     (salvo `estrellas` en los `escribir`) ni hora del intento.
   - `repaso`: tarjeta `{caja, proximo, aciertos, fallos}`; `acierto` significa «bien al primer intento» y no
     distingue si hubo ayuda.
   - `ejercicios` (pasos `escribir` de `primeros-pasos`): `{estrellas, xp, completado}`.
   - **Consecuencia para P2:** con los datos actuales no se puede distinguir reconocimiento / predicción /
     producción ni uso de pistas por concepto. Un modelo de dominio exige señales nuevas (esquema > 11), lo que
     depende de la ADR-052 (Propuesta). No se tocó el esquema.
2. **Repaso:** intervalos 1, 2, 4, 8, 16 días confirmados en `tortuscript/practica.py`; error → caja 1.
3. **`correcta: 0` en casi todos los `elegir`** parece un sesgo de posición, pero **no lo es**: `leccion._mezclar`
   baraja las opciones con una semilla estable por lección y paso. Se verificó en el código; no requiere cambios.
4. **Contrato de IDs / `escribir` 0–29:** protegido por tests existentes, que pasan.

## 3. Hallazgos de contenido (mapa de cobertura)

Pasos por tipo y curso (conteo real de `contenido/cursos/*.json`):

| Curso | Lecciones | Tipos de actividad usados |
|---|---|---|
| `alfabetizacion-digital` | 16 | **solo `elegir`** (45) |
| `primeros-pasos` | 30 | los seis tipos |
| `python-real`, `tortuga`, `web-esencial`, `tortuaria`, `sql-fundamentos`, `juegos` | 5–15 | varios tipos |
| `proyectos` | 3 | solo `escribir` (proyectos integradores) |

### 3.1 `alfabetizacion-digital`: preguntas incoherentes (corregido en `feature/alfabetizacion-preguntas-coherentes`)

Verificado leyendo los 45 `elegir`:

- En 7 lecciones (`programa`, `navegador`, `servidor`, `base-datos`, `integracion`, y parcialmente `internet`,
  `codigo`) la pregunta del paso 3 **no correspondía a su respuesta correcta**: era la respuesta del paso anterior con
  otra pregunta (p. ej. «¿Qué ocurre cuando un navegador visita un sitio?» → «Pedir y mostrar recursos de sitios web»).
  Un chico que razona la pregunta no puede acertar con criterio.
- Pistas que pertenecían a otra pregunta (p. ej. en `programa`, «Antes de calcular, la app necesita saber qué número
  recibió.» para «¿Qué describe mejor a un programa?»).
- 4 preguntas de `json`/`git`/`github` con solo dos opciones (50 % de acierto por azar).
- Varios pasos repetían la definición del paso 1 con otras palabras (no es práctica desde otro ángulo).

La corrección mantiene IDs de lecciones, cantidad, tipo y posición de cada paso, de modo que el progreso guardado
(clave = índice de paso) sigue válido.

### 3.2 Pendiente (no seguro hacerlo todavía)

- `alfabetizacion-digital` sigue practicando solo con `elegir`. Introducir `ordenar`/`completar`/`predecir`
  requiere confirmar que el evaluador (que corre código) acepta texto no ejecutable; hasta entonces no se cambian los
  tipos. Es la oportunidad de variedad más grande detectada.
- `proyectos` solo tiene `escribir`; no hay recuperación ni predicción previa a cada etapa.
- Avisos del validador sin resolver (`primeros-pasos`): «6. Dos variables · paso 5» y «24. Tabla del 2 · paso 4»
  (`ordenar` con otro orden que muestra lo mismo; hay que aceptar ambos). No se tocó `primeros-pasos` por la
  restricción de posiciones 0–29 de `escribir`; corregirlo requiere comprobar el efecto sobre el progreso.
- P2/P3: sin cambios funcionales (ADR-052 en Propuesta).

## 4. Limitaciones

- No se ejecutó la interfaz real (sin Playwright); los cambios de contenido se validaron con el validador, los tests
  de contenido y la suite completa, no con un recorrido en navegador.
- No se midió eficacia pedagógica con alumnos; los cambios corrigen defectos objetivos de coherencia, no demuestran
  mejora de aprendizaje.
