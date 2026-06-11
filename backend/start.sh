#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py seed_initial_data --skip-examples

if [ -n "${ADMIN_PASSWORD:-}" ]; then
  python manage.py ensure_admin_user \
    --username "${ADMIN_USERNAME:-admin}" \
    --password "${ADMIN_PASSWORD}" \
    --email "${ADMIN_EMAIL:-admin@cajamoments.local}"
fi

exec python -m gunicorn config.wsgi:application --bind 0.0.0.0:"${PORT}"
