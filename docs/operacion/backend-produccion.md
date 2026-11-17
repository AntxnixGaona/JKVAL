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
- `DJANGO_SECRET_KEY`: secreto aleatorio de al menos 50 caracteres, generado en el proveedor.
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
