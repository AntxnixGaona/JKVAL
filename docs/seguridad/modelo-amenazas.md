# Modelo de amenazas — JKVAL (Fase 0)

Estado: borrador de Fase 0, sujeto a revisión independiente en cada gate.
Alcance: aplicación local en `127.0.0.1`, sin despliegue público. Riot/RSO desactivado.

## Activos

- Cuentas JKVAL: correo, hash de contraseña, estado de verificación, sesiones.
- Perfil JKVAL privado y sus datos derivados (partidas, agentes, mapas, armas, tendencias).
- Consentimientos, exportaciones y solicitudes de eliminación.
- Datos DEMO sintéticos y metadatos de procedencia.
- Secretos de servidor (`SECRET_KEY`, futuras claves de correo/Riot) y base de datos.
- Integridad del contenido editorial y de las fuentes citadas.
- Disponibilidad del servicio local y de los assets estáticos.

## Límites de confianza

1. Navegador (no confiable) ↔ Django (servidor).
2. Django ↔ SQLite/PostgreSQL (mismo host en local).
3. Django ↔ salida de correo local (`var/outbox/`); proveedor real solo tras autorización.
4. Django ↔ Riot (desactivado; sin llamadas en Fase 1–3).
5. Repositorio Git ↔ biblioteca cruda de assets (no versionada).

## Amenazas y controles

| ID | Amenaza | Control previsto | Verificación |
|---|---|---|---|
| T-01 | Enumeración de cuentas en registro/login/recuperación | Respuestas y tiempos homogéneos; mensajes genéricos; rate limit por IP y cuenta | Pruebas negativas con correos existentes/inexistentes |
| T-02 | Fuerza bruta o credential stuffing | Rate limiting, bloqueo temporal, contraseñas robustas, hash mantenido por Django | Prueba de límites y revisión de configuración |
| T-03 | CSRF en mutaciones | Middleware CSRF de Django, tokens en formularios, SameSite=Lax | Petición sin token debe fallar |
| T-04 | Secuestro de sesión | Cookies HttpOnly, Secure en producción, rotación al iniciar sesión, expiración | Inspección de `Set-Cookie` y pruebas |
| T-05 | IDOR en perfiles, exportaciones y ajustes | Autorización por objeto en cada vista; sin confiar en IDs; perfiles privados por defecto | Dos cuentas sintéticas, acceso cruzado debe dar 403/404 |
| T-06 | XSS en guías, consejos, nombres o mensajes | Autoescape de plantillas, sanitización de contenido editorial, CSP sin `unsafe-inline` cuando sea viable | Carga de payloads sintéticos y revisión CSP |
| T-07 | Inyección SQL | ORM de Django y consultas parametrizadas; sin SQL concatenado | Revisión de código y pruebas con entrada maliciosa |
| T-08 | Fuga de datos en logs/errores | Logs sin contraseñas/tokens/PII; errores genéricos; `DEBUG=False` fuera de local | Revisión de logs y respuestas 500 |
| T-09 | Fuga de secretos | `.env` fuera de Git, `.env.example` sin valores, secretos solo en servidor | `git grep` de patrones y revisión de repo |
| T-10 | Abuso/DoS de endpoints públicos | Rate limit, límites de payload, paginación, timeouts | Pruebas de carga moderadas en local |
| T-11 | Path traversal en assets/exportaciones | Rutas allowlist, `send_file` seguro, nombres generados | Pruebas con `../` |
| T-12 | Mezcla de datos DEMO y reales | Origen etiquetado en modelo/API/UI; feature flag; validación al publicar | Revisión de datos y pruebas de procedencia |
| T-13 | Suplantación de fuentes o consejos inventados | Registro de autor/fuente/enlace/fecha/parche; revisión editorial; enlace original | Auditoría de contenido |
| T-14 | Dependencia comprometida | Versiones fijadas, revisión de avisos, instalación desde PyPI oficial | `pip list`, revisión de requirements |
| T-15 | Clickjacking / sniffing | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP | Inspección de cabeceras |
| T-16 | Correo de verificación interceptado o reutilizado | Token de un solo uso, caducidad, hash en BD, no registrar el token | Pruebas de reutilización y caducidad |
| T-17 | SSRF si se habilita Riot | Allowlist de hosts oficiales, sin URLs de usuario, timeouts | Revisión antes de habilitar el flag |
| T-18 | Datos de menores | Decisión de la escuela sobre edad/consentimiento; no recolectar fecha de nacimiento sin necesidad | Bloqueo documentado |

## Fuera de alcance inicial

- Producción, hosting, correo real, Riot/RSO y datos reales de jugadores.
- Escaneo de servicios de terceros (Riot, Tracker.gg, GitHub).
- Afirmar invulnerabilidad: la cobertura se limita a lo probado y registrado.

## Riesgos abiertos

- Público objetivo y tratamiento de menores: pendiente de decisión escolar.
- Proveedor de correo y hosting: no definidos.
- Permisos de redistribución de assets de Riot: no confirmados; no se publican.
