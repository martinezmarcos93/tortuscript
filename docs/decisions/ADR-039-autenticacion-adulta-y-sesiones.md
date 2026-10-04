# ADR-039 — Autenticación adulta y sesiones server-side

- Estado: Aceptada
- Fecha: 2026-09-30
- Contexto: incorporación de identidad remota a la aplicación web.

## Decisión

La autenticación remota corresponde exclusivamente al adulto titular de la cuenta.

Las credenciales se almacenan como hash de contraseña mediante el mecanismo de derivación de contraseña disponible en Werkzeug (scrypt en la implementación actual). Nunca se guarda la contraseña en claro.

Las sesiones son server-side:
- el navegador recibe un token aleatorio de sesión;
- el servidor conserva solamente su digest SHA-256;
- la sesión tiene expiración;
- puede revocarse;
- la identidad efectiva procede de la sesión, no de un parámetro enviado por el navegador.

Cada sesión posee además un secreto CSRF independiente, cuyo digest también se conserva en servidor. Las operaciones mutantes autenticadas deberán exigir ese secreto mediante mecanismo CSRF antes de exponerse públicamente.

La cookie de producción deberá configurarse con:
- Secure;
- HttpOnly;
- SameSite=Lax o Strict según el flujo;
- duración limitada.

El modo local existente no se elimina en esta etapa. La autenticación se introduce como capa separada para evitar romper el núcleo educativo.

## Verificación de correo

Una cuenta no puede autenticarse como cuenta comercial hasta haber verificado su correo. El proveedor de correo y el mecanismo de tokens de verificación se implementarán en una etapa posterior.

## No decidido

- proveedor de correo;
- dominio;
- recuperación de contraseña;
- MFA;
- proveedor de base de datos de producción;
- estrategia de rotación de sesiones;
- integración definitiva entre sesión adulta y ChildProfile activo.
