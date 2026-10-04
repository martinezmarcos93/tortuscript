# ADR-048 — Modelo de sincronización Desktop ↔ Cloud

- Estado: Aceptada
- Fecha: 2026-10-04 (propuesta y aceptada el mismo día)
- Decisor: Marcos
- Relacionadas: ADR-013, ADR-026, ADR-041, ADR-044, ADR-046

## Contexto

El barrido 9 pide definir el modelo de sincronización antes de escribir código. Hoy no hay nada que
sincronizar: en la app con cuentas el progreso de cada perfil ya vive en el servidor que la corre, y la app
local sin cuentas guarda todo en la máquina (ADR-013: Desktop no depende de Cloud). La sincronización solo
tiene sentido cuando exista un servidor desplegado y una familia use TortuScript en más de un dispositivo.

Todo cambio de progreso lo produce el servidor al evaluar una respuesta; el navegador nunca envía progreso
(un snapshot del cliente permitiría falsificar XP). La sincronización no puede abrir esa puerta.

## Decisión

1. **Unidad de sincronización: el perfil.** Se sincroniza el progreso de un `ChildProfile` entre una
   instalación local y la cuenta en la nube. Nunca entre perfiles ni entre cuentas.
2. **Qué viaja: hechos, no totales.** La instalación local no sube su snapshot: sube el registro de lo que
   el chico resolvió (lección, paso, respuesta, fecha). La nube **vuelve a evaluar** cada respuesta con su
   propio contenido y deriva XP, rachas, logros y liga. Así una instalación modificada no puede regalarse
   puntos, y los totales nunca entran en conflicto: se recalculan.
3. **Conflictos, por tipo de dato:**

   | Dato | Regla |
   |---|---|
   | Pasos y lecciones resueltos, logros | Unión: lo resuelto en cualquier lado queda resuelto. La primera fecha gana. |
   | XP, racha, liga, días activos, meta diaria | No se sincronizan: se derivan de los hechos ya unidos. |
   | Repaso espaciado (cajas y próximas fechas) | Por tarjeta, gana el estado con la revisión más reciente. |
   | Proyectos del chico (código) | Por proyecto, gana la última edición; la otra versión se conserva como copia con fecha. Nunca se pierde código. |
   | Proyectos integradores | Igual que los proyectos. |
   | Ajustes de accesibilidad, meta, recorrido | Por dispositivo: no se pisan (la letra grande del celular no cambia la de la compu). |
   | Intereses y diagnóstico | Gana el más reciente. |
   | Estado en curso (pistas, intentos) | No se sincroniza: es efímero. |

4. **Borrado.** Eliminar un perfil o la cuenta en la nube (ADR-046) deja una marca que la instalación local
   recibe en la siguiente sincronización: no vuelve a subir lo borrado. Los datos locales no se borran a
   distancia; la app avisa y el adulto decide.
5. **Consentimiento.** Sincronizar es una finalidad aparte (`sincronizacion` ya existe en la bitácora de
   consentimientos): apagada por defecto, la activa el adulto y se puede revocar.
6. **Protocolo.** Lo inicia siempre la instalación local, autenticada con la cuenta del adulto, por HTTPS.
   Cada lote lleva un identificador para poder repetirlo sin duplicar (idempotencia) y la versión del
   contenido con la que se resolvió.
7. **Contenido de otra versión.** Un hecho sobre una lección que la nube no conoce (o cambió) se guarda
   como pendiente y no suma hasta que las versiones coincidan. No se descarta.

La aceptación fija el diseño; no hay nada que implementar hasta que exista un servidor desplegado.

## Lo que queda sin decidir

- Si la versión local sin cuentas llega a ofrecer sincronización o solo importación manual (ADR-044).
- Cuánto historial de respuestas conserva la instalación local para poder subirlo.
- Cifrado en reposo del registro local.

## Alternativas descartadas

- *Subir el snapshot y quedarse con el más nuevo*: pierde lo hecho en el otro dispositivo y permite
  falsificar progreso.
- *Sincronización en tiempo real entre dispositivos*: complejidad de un sistema distribuido para un caso
  (dos dispositivos a la vez con el mismo perfil) que casi no ocurre.
