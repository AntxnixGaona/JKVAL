# Inventario y política de datos — JKVAL (Fase 0)

## Principios

- Minimización: solo datos necesarios para cuenta, perfil y consentimiento.
- Separación estricta: perfil JKVAL ≠ perfil VALORANT; datos DEMO ≠ datos reales.
- Privacidad por defecto: el perfil JKVAL nace privado.
- Riot es opcional y nunca se solicita la contraseña de Riot.
- Sin analítica de terceros ni cookies publicitarias.

## Datos y finalidad

| Dato | Finalidad | Base | Retención | Destinatarios |
|---|---|---|---|---|
| Correo | Identificar cuenta y verificar | Consentimiento del usuario | Mientras exista la cuenta | Ninguno externo en local |
| Hash de contraseña | Autenticación | Ejecución del servicio | Mientras exista la cuenta | Ninguno |
| Nombre visible / bio | Perfil JKVAL | Consentimiento | Hasta borrado o cambio | Visible según privacidad |
| Sesión (cookie) | Mantener sesión y CSRF | Necesario | Expiración de sesión | Ninguno |
| Preferencia de intro/audio | Evitar repetición | Necesario/local | `sessionStorage` de la pestaña | Ninguno |
| Estadísticas JKVAL | Mostrar resumen al usuario | Consentimiento | Hasta borrado | Solo el usuario o quien autorice |
| Consentimiento Riot | Habilitar perfil público | Consentimiento explícito | Hasta revocación | Riot solo si se habilita |
| Logs técnicos | Operación y seguridad | Interés legítimo | 30 días local | Ninguno; sin PII |
| Correo de verificación | Verificar cuenta | Necesario | 24 h / un uso | Buzón local en desarrollo |

## Derechos y controles

- Exportar datos: descarga legible (JSON/CSV) solo del propio usuario.
- Revocar consentimiento Riot: desactiva perfil público y borra tokens asociados.
- Eliminar cuenta: borrado de cuenta, perfil, sesiones y datos derivados; confirmación explícita.
- Ocultar perfil: privado por defecto; el usuario puede cambiarlo.
- No se guardan tokens de Riot en frontend ni en logs.

## Cookies y almacenamiento local

- `sessionid` y `csrftoken`: cookies de Django, HttpOnly/SameSite; Secure en producción.
- `sessionStorage`: marca de intro vista en la pestaña; no contiene datos personales.
- Sin localStorage para credenciales ni tokens.

## Pendientes que bloquean producción

- Decisión escolar sobre edad mínima, consentimiento de tutores y finalidad educativa.
- Proveedor de correo, política de retención definitiva y encargado de tratamiento.
- Aprobación de Riot y base legal para datos de jugador.
- Texto legal revisado contra la política vigente de Riot antes de publicar.
