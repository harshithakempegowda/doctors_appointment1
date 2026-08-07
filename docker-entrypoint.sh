#!/bin/sh
set -e

mkdir -p "$(dirname "${DJANGO_DB_PATH:-/app/db.sqlite3}")"

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "$SEED_DEMO" = "True" ]; then
  echo "Seeding demo data..."
  python manage.py seed_demo || true
fi

exec "$@"
