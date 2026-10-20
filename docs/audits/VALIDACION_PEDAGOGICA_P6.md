# Validación pedagógica — P6 (19/10/2026)

**Fase:** P6 de `docs/ROADMAP_PEDAGOGIA_ADAPTATIVA.md` · **Herramientas:** `tortuscript/metricas_pedagogicas.py`, `herramientas/informe_pedagogico.py`
**Redactado por:** Claude Code (director).

## 1. Conclusión corta

Las mejoras P1–P5 están **implementadas y probadas técnicamente**, pero **no hay evidencia de que mejoren el aprendizaje**:
no se probaron con alumnos. Todo efecto pedagógico es, por ahora, **hipótesis**. Este informe deja definida la línea de base
y cómo medir, para que la comparación se pueda hacer cuando haya uso real.

## 2. Qué se puede medir hoy (solo con lo que ya se guarda)

El progreso guarda, por perfil y en la máquina del usuario: el **mejor resultado** de cada paso (`xp`, `perfecto`, `fecha`,
`estrellas` en `escribir`), las tarjetas de repaso (`caja`, `aciertos`, `fallos`, `proximo`), los días activos y el estado de
los proyectos integradores (etapas, ayudas vistas).

| Métrica del roadmap | Disponible | Cómo |
|---|---|---|
| Acierto al primer intento | Sí | Paso rápido con `xp >= 5` |
| Uso de ayuda | Parcial | `xp <= 0` = vio la respuesta; en `escribir`, estrellas (más pistas, menos estrellas). **No** se sabe cuántas pistas vio en un paso rápido |
| Producción autónoma | Sí | `escribir` con 3 estrellas (o `perfecto` sin estrellas) |
| Retención diferida | Sí | Tarjetas con `caja >= 3` y `aciertos >= 2`; tasa de acierto en el repaso |
| Desempeño en ejercicios nuevos | Sí, desde P5 | Resultado de los cursos de desafíos |
| Proyectos y asistencia | Parcial | Etapas completas y ayudas vistas de los proyectos integradores (no lo cubre `metricas` V1) |
| Fallos de evaluación o de contenido | Sí | `herramientas/validar_contenido.py` y la suite de tests |

## 3. Qué **no** se puede medir (y no se agrega sin revisión de privacidad)

- **Historial**: solo queda el mejor resultado de cada paso, no la secuencia de intentos. No se puede ver una curva de aprendizaje por paso.
- **Tiempo** por paso o por sesión.
- **Respuestas erróneas concretas** (qué opción eligió, qué escribió): necesarias para clasificar errores conceptuales.
- **Nivel de pista graduada** (P4) que se vio en cada intento.
- **Comparación entre alumnos**: no hay telemetría remota, por diseño. Los datos son de chicos de 9 a 15 años.

Agregar cualquiera de estos datos cambia el esquema del progreso y amplía lo que se guarda de menores:
necesita ADR y revisión de privacidad (restricción 7 del roadmap y ADR-045/046).

## 4. Línea de base

Se toma como línea de base el comportamiento de `prod` antes de P1–P5:

- Repaso: `practica.elegir` (intervalos 1, 2, 4, 8 y 16 días, lo más atrasado primero, 2 tarjetas por lección como máximo).
- Pistas: una sola pista por paso; «Ver respuesta» tras 2 errores.
- Sin desafíos de transferencia.

El planificador nuevo arranca **apagado** (`TORTU_PLANIFICADOR=adaptativo` lo enciende) para poder comparar ambos.

## 5. Cómo comparar (cuando haya uso)

1. Con permiso del adulto responsable, tomar los archivos de progreso **en la misma máquina** y correr
   `herramientas/informe_pedagogico.py RUTA` antes y después de un período (p. ej. 4 semanas). Nada se manda afuera.
2. Comparar: tasa de acierto en el repaso, tarjetas retenidas, proporción de pasos al primer intento y de `escribir` autónomos.
3. Para el planificador: un grupo con el interruptor apagado y otro encendido. Con pocos alumnos, describir casos, no porcentajes.
4. Separar siempre «la suite pasa» (técnico) de «los chicos aprenden más» (pedagógico).

## 6. Hipótesis a contrastar

| Cambio | Hipótesis | Señal esperada |
|---|---|---|
| P1 cobertura por ángulos | Practicar un concepto en varios formatos mejora la producción autónoma | Más `escribir` con 3 estrellas en unidades completadas |
| P3 planificador | Priorizar conceptos débiles e intercalar mejora la retención | Más tarjetas retenidas y mayor tasa de acierto en el repaso |
| P4 pistas graduadas | Pistas de a una reducen el «Ver respuesta» | Menos pasos con `xp <= 0` |
| P5 transferencia | Los desafíos detectan conceptos que parecían dominados | Conceptos `autonomo` con desafíos fallidos |

## 7. Decisiones recomendadas

1. **Dejar el planificador apagado** en producción hasta probarlo con un grupo chico y con el informe local.
2. **No agregar telemetría.** Si se quiere medir el nivel de pista o el historial de intentos, abrir una ADR con revisión de privacidad.
3. Volver a escribir este informe con datos reales; hasta entonces, describir las mejoras como hipótesis, también en la comunicación comercial.
