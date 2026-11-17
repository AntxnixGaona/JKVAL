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

database_url = os.environ.get('DATABASE_URL', '')
if not database_url.startswith(('postgres://', 'postgresql://')):
    raise ImproperlyConfigured('DATABASE_URL debe apuntar a PostgreSQL persistente.')
DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)}
del database_url

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
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
