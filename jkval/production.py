"""Configuración del servidor HTTPS con PostgreSQL persistente."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

DEBUG = False
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32 or SECRET_KEY.startswith('dev-only-'):
    raise ImproperlyConfigured('Configura DJANGO_SECRET_KEY con un valor aleatorio de al menos 32 caracteres.')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()]
render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
if render_host:
    ALLOWED_HOSTS.append(render_host)
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Configura los dominios exactos en DJANGO_ALLOWED_HOSTS.')
CSRF_TRUSTED_ORIGINS = ['https://' + host for host in ALLOWED_HOSTS]

# Render publica exclusivamente HTTPS (redirige HTTP en el edge).
# Selección por entorno del servidor, nunca por cabeceras de la petición.
RENDER_HTTPS_ONLY = os.environ.get('RENDER') == 'true' and bool(render_host)
if not RENDER_HTTPS_ONLY and not TRUSTED_PROXY_NETWORKS:
    raise ImproperlyConfigured(
        'Configura DJANGO_TRUSTED_PROXY_IPS con la IP o CIDR del proxy HTTPS de confianza '
        'para poder usar SECURE_PROXY_SSL_HEADER de forma segura.'
    )

# Un único Redis compartido por todos los workers; nunca degradar a locmem.
redis_url = os.environ.get('DJANGO_REDIS_URL', '').strip()
if not redis_url.startswith(('redis://', 'rediss://')):
    raise ImproperlyConfigured('Configura DJANGO_REDIS_URL con el Redis compartido de producción.')
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': redis_url,
    'KEY_PREFIX': 'jkval',
    'OPTIONS': {'socket_connect_timeout': 3, 'socket_timeout': 3},
}}
del redis_url

database_url = os.environ.get('DATABASE_URL', '')
if not database_url.startswith(('postgres://', 'postgresql://')):
    raise ImproperlyConfigured('DATABASE_URL debe apuntar a PostgreSQL persistente.')
DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)}
del database_url

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'whitenoise.middleware.WhiteNoiseMiddleware',
)
STATIC_URL = '/static/'
# Mantener nombres estables para imports relativos de módulos JS vendorizados.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
# El servidor debe quedar detrás del proxy HTTPS de confianza del proveedor.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536

if RENDER_HTTPS_ONLY:
    SECURE_PROXY_SSL_HEADER = None
    SECURE_SSL_REDIRECT = False  # Render aplica la redirección pública.
    MIDDLEWARE.insert(0, 'core.middleware.RenderHTTPSMiddleware')
