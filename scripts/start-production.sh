#!/usr/bin/env bash
set -euo pipefail
export DJANGO_SETTINGS_MODULE=jkval.production
python manage.py migrate --noinput
exec python -m gunicorn jkval.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile - --error-logfile -
