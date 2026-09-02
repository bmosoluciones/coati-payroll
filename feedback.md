# Feedback de revisión — Issue #59

## Fixes aplicados

- Se agregó configuración SMTP persistida en base de datos, editable desde `Configuración > Correo y seguridad`.
- Las credenciales SMTP se cifran con una clave derivada de `SECRET_KEY`; no se muestran en la interfaz ni se escriben en logs.
- Se implementó recuperación de contraseña por enlace de correo con token hash, expiración, uso único y revocación de navegadores confiables.
- Se implementó verificación por código de un solo uso para inicios desde navegadores desconocidos, únicamente cuando el administrador la habilita y el usuario tiene correo configurado.
- Tras verificar el código se emite una cookie segura, `HttpOnly`, `SameSite=Lax`, con vencimiento y registro revocable en base de datos.
- Se agregó bloqueo persistente después de cinco intentos fallidos y reinicio del bloqueo al recuperar la contraseña.
- Se agregó control administrativo de permisos para la configuración de correo. No se implementó TOTP ni un segundo factor permanente.
- Se añadió la migración Alembic `20260902_auth_email_security` para las nuevas columnas y tablas.

## QA ejecutado

- Compilación de `coati_payroll`: correcta.
- Pruebas existentes de autenticación y configuración: `33 passed`.
- Regresiones de seguridad de correo: `7 passed`.
- Suite completa: `1688 passed, 3 skipped, 1 xfailed, 2 xpassed`.
- Pruebas de migraciones: `2 xpassed`, `1 xfailed` por la marca preexistente del conjunto.
