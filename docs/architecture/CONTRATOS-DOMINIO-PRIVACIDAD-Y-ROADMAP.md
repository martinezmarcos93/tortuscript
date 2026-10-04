# Contratos de dominio para la siguiente etapa de TortuScript

**Estado:** decisión de diseño para implementar por etapas; no implica que las capacidades estén habilitadas.  
**Fecha:** 2026-10-03  
**Alcance:** barridos 4, 7, 8, 9, 10 y 11.

## Invariantes no negociables

1. **Account** representa al adulto responsable y es la raíz de identidad, facturación y consentimiento. La cuenta no es un perfil educativo.
2. **Authentication** acredita una sesión de cuenta; no concede por sí sola acceso a un producto ni autoriza a leer/escribir el progreso de cualquier perfil.
3. **ChildProfile** es el límite de propiedad del progreso, preferencias, proyectos, diagnóstico, XP, intereses y datos educativos. Toda operación de datos de alumno debe derivar el perfil activo de una sesión validada en servidor; nunca confiar en un `profile_id` enviado libremente por el cliente.
4. **Consent** registra una decisión verificable del adulto sobre una finalidad concreta, con versión del aviso, momento, estado y mecanismo de revocación. No se debe inferir consentimiento por tener una cuenta, usar el producto o pagar.
5. **Subscription** representa el estado comercial reportado por el proveedor y la relación de facturación con la cuenta. No es la fuente de autorización curricular.
6. **Entitlement** es la proyección interna de acceso a un producto. Se modifica mediante una transición de dominio autenticada e idempotente; no por parámetros del navegador ni por un retorno de checkout.
7. **Curriculum** define lecciones, prerequisitos y reglas de evaluación; no contiene lógica de cobro. **Authorization** decide el acceso combinando sesión, perfil, consentimiento aplicable y entitlement.
8. Los identificadores del proveedor de pagos, tokens, contraseñas y secretos no se incluyen en logs de aplicación ni en exportaciones educativas.

## Matriz de propiedad y autoridad

| Dato/capacidad | Propietario | Autoridad para mutar | Lectura |
|---|---|---|---|
| Correo, credenciales y sesiones | Account / Authentication | Adulto autenticado y flujos de seguridad | Adulto; no perfil infantil |
| Alias y estado del perfil | ChildProfile | Adulto autenticado propietario | Adulto y perfil activo solo cuando se necesita |
| Progreso, XP, proyectos y preferencias educativas | ChildProfile | Sesión educativa validada con perfil activo | Solo perfil propietario y adulto responsable según política |
| Consentimiento y su historial | Consent | Adulto responsable autenticado | Adulto; servicios mínimos que necesitan comprobarlo |
| Suscripción, facturación y eventos del proveedor | Subscription | Adaptador de proveedor/webhook autenticado | Adulto y servicios de facturación |
| Acceso a producto | Entitlement | Servicio de dominio; nunca el cliente | Servicio de autorización y UI vía resumen seguro |
| Currículo y prerequisitos | Curriculum | Publicación de contenido revisada | Público/usuario según producto |
| Tutor IA y contexto temporal | TutorSession | Política de tutor y autorización del servidor | Solo contexto permitido para el perfil activo |

## Consentimiento y datos de menores

Antes de integrar analítica no esencial, tutor IA, sincronización remota o pagos, definir por separado las finalidades, los datos mínimos, los destinatarios, la retención y la forma de revocación. El consentimiento para una finalidad no debe habilitar automáticamente otra. Mantener una bitácora de cambios de estado sin almacenar más datos personales de los necesarios. La política y los umbrales legales aplicables deben revisarse con asesoramiento jurídico antes de producción; este documento no constituye una conclusión legal.

La eliminación de una cuenta debe ser un flujo explícito y auditable que contemple perfiles, progreso, proyectos, sesiones, tokens y datos derivados, y que distinga los datos que deban conservarse por obligación legal de los que deben suprimirse. No implementar borrado en cascada productivo hasta definir retención, exportación, recuperación y comportamiento de las suscripciones activas.

## Contrato de eventos de suscripción y entitlements

- Verificar la firma del webhook sobre el cuerpo original antes de procesarlo.
- Registrar el identificador del evento del proveedor con una restricción única para idempotencia.
- Validar proveedor, cuenta relacionada, producto, moneda/importe cuando aplique y transición de estado.
- Aplicar el evento y su efecto sobre el entitlement en una transacción local; conservar un estado de procesamiento que permita reintentos seguros.
- No activar acceso por visitar una URL de éxito del checkout.
- Procesar duplicados como éxito sin volver a aplicar efectos; poner eventos inconsistentes en una cola de revisión, sin otorgar acceso.
- Definir expiración, período de gracia, cancelación, reembolso, contracargo y reconciliación antes de aceptar pagos reales.
- El entitlement pertenece a la cuenta; la regla actual de producto puede compartirlo entre los perfiles de esa cuenta, pero la política comercial debe confirmarse antes de publicar precios.

## Sandbox de ejecución remota

El intérprete no debe ejecutarse dentro del proceso web ni considerarse aislado solo por usar un subprocess. El contrato de producción es: API autenticada → cola acotada → worker efímero no privilegiado → aislamiento de sistema operativo → respuesta normalizada. Aplicar límites de CPU, memoria, tiempo, procesos, tamaño de entrada/salida, filesystem temporal y concurrencia; denegar red por defecto; no montar secretos ni el directorio de datos; terminar el grupo de procesos al cancelar o exceder cuota. Los límites actuales del modo local no certifican aislamiento para código hostil en un servidor público.

## Cloud sync

La sincronización es por perfil, con versiones monotónicas de documento y tombstones explícitos para borrados. Definir conflictos por tipo de dato (progreso acumulativo, ajustes, proyectos editables), no con una política global de “última escritura gana”. Cifrar tránsito y almacenamiento, autorizar cada objeto por cuenta y perfil, auditar revocación de dispositivos y establecer una política de retención. No subir datos de perfiles a una cuenta distinta ni mezclar progreso por coincidencia de alias.

## Tutor IA

El tutor recibe solo contexto pedagógico mínimo del perfil activo: lección, objetivo, intento actual, pistas ya usadas y nivel de ayuda permitido. Excluir correo adulto, identificadores de cuenta, información de pago, otros perfiles y proyectos no relacionados. La generación no decide entitlement, no escribe progreso directamente y no ejecuta código. Las propuestas del tutor deben pasar por el evaluador curricular existente; registrar métricas minimizadas y no guardar conversaciones indefinidamente por defecto. Incorporar filtros de contenido, límites de salida y evaluación de calidad/seguridad antes de un piloto.

## Contratos de integración con Croco-Script

Mantener TortuScript y Croco-Script como productos desplegables por separado. Compartir contratos versionados, no tablas internas ni imports de implementación:

- `Identity.v1`: identificador opaco de cuenta y perfil, sin credenciales.
- `Entitlement.v1`: producto, estado y versión/fecha efectiva; respuesta firmada o autenticada entre servicios.
- `Progress.v1`: resumen educativo versionado y opt-in, no acceso libre a la base.
- `Curriculum.v1`: identificador de curso, versión y prerequisitos.
- `Authorization.v1`: decisión explícita de permiso con razón estable y correlación de auditoría.

Cada contrato debe tener esquema, compatibilidad, pruebas de contrato y política de versionado. No compartir tokens de sesión del navegador entre productos ni aceptar un identificador de perfil sin validar su pertenencia.

## Puertas de aceptación

- No se habilitan pagos reales sin sandbox de proveedor, webhook autenticado/idempotente, reconciliación y pruebas de reversión.
- No se habilita sync remoto ni tutor IA sin consentimiento/retención definidos y controles por perfil.
- No se publica ejecución de código hasta una revisión independiente del aislamiento del worker.
- No se declara cierre de privacidad hasta que exportación, eliminación, retención y permisos estén probados en fixtures y revisados para la jurisdicción aplicable.
- Cada implementación debe aportar tests automatizados; los ensayos de datos locales reales, proveedor real y dispositivos físicos quedan separados como validación de entorno.
