# Backend de JKVAL en producción

El servicio sirve frontend, API e historial desde el mismo dominio HTTPS.
Requiere PostgreSQL persistente. No utiliza db.sqlite3 del equipo local.

## Configuración del servicio Python

- Repositorio: AntxnixGaona/JKVAL, rama master.
- Versión de Python compatible con Django instalado: Python 3.14.
- Build: `bash scripts/build-production.sh`.
- Inicio: `bash scripts/start-production.sh`.
- Comprobación HTTP: `/salud/`.
- `DJANGO_SETTINGS_MODULE=jkval.production`.
- `DJANGO_SECRET_KEY`: secreto aleatorio de al menos 32 caracteres, generado en el proveedor.
- `DATABASE_URL`: conexión privada a PostgreSQL del proveedor.
- `DJANGO_ALLOWED_HOSTS`: dominio exacto sin esquema. En Render se incorpora automáticamente RENDER_EXTERNAL_HOSTNAME.
- `HENRIKDEV_API_KEY`: opcional, únicamente para el tracker externo.

La URL de uso será `https://DOMINIO/aim-trainer/`; el historial está en
`https://DOMINIO/mi-progreso/`. Los resultados de la instalación local no se
copian automáticamente a la base remota. Las migraciones crean las tablas.

## Verificación después del despliegue

1. Abrir la web y comprobar estilos, recursos 3D y ausencia de errores.
2. Entrenar con un alias de prueba y terminar la sesión.
3. Verificar el POST a /api/entrenamientos/ y el mensaje de guardado.
4. Abrir el historial y comprobar que conserva la sesión después de recargar.
5. Reiniciar el servicio y comprobar que el registro persiste en PostgreSQL.

No confundir el servicio Django con GitHub Pages, que continúa siendo estático.
Los alias actuales no son cuentas privadas y el historial es compartido.
La configuración del código no implica que exista un servicio ya desplegado.

## Seguridad y Render

Antes del siguiente despliegue, configurar en Environment del Web Service:

- `DJANGO_REDIS_URL`: URL interna de Render Key Value, en la misma región que el servicio. Todas las instancias deben usar la misma base Redis. No usar la URL pública ni publicar credenciales en Git.
- `DJANGO_TRUSTED_PROXY_IPS`: IP/CIDR del proxy inmediato verificado para este servicio. No usar `0.0.0.0/0`, `::/0` ni las IP de salida de Render: las IP de salida no identifican al proxy entrante.

El build existente instala `requirements-production.txt`. Producción rechazará arrancar si faltan Redis, proxy, PostgreSQL o secreto válido. Configurar las variables antes de publicar estos cambios.

Render termina TLS en su balanceador y reenvía HTTP al servicio. Comprobar con soporte/configuración de Render qué rango identifica al proxy inmediato y que sobrescribe X-Forwarded-Proto. No deducir confianza de una cabecera enviada por el cliente. La carpeta local no contiene esta garantía de infraestructura.

Después del despliegue, verificar HTTPS sin bucles de redirección, HTTP redirigido a HTTPS, `/salud/`, login de notas y respuesta 429 al superar límites. Verificar Redis con al menos dos workers. El limitador actual usa REMOTE_ADDR y puede agrupar visitantes detrás del proxy; extraer la IP del visitante requiere verificar primero la cadena de proxies y el saneamiento de X-Forwarded-For.

Referencia: https://render.com/docs/web-services

### Perfil automático HTTPS de Render

Actualización: con `RENDER=true` y `RENDER_EXTERNAL_HOSTNAME` (variables del proveedor), producción selecciona un origen público HTTPS fijo. No necesita `DJANGO_TRUSTED_PROXY_IPS` en ese perfil y no utiliza X-Forwarded-Proto para decidir el esquema. Render realiza la redirección HTTP pública; Django conserva cookies Secure, HSTS y comprobaciones CSRF de HTTPS. Esto sustituye el requisito de CIDR anterior exclusivamente en Render. Fuera de Render sigue siendo obligatorio configurar el proxy.

La frontera de confianza incluye la red privada de Render: no colocar un ingress HTTP alternativo ni exponer directamente el proceso. Redis sigue siendo obligatorio (`DJANGO_REDIS_URL`). El rate limit por REMOTE_ADDR sigue siendo conservador y puede agrupar visitantes del mismo proxy.

Referencia del comportamiento HTTPS del edge: https://render.com/tutorials/web-service-vs-static-site/web-services
