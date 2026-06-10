web: python manage.py collectstatic --noinput && python manage.py migrate --noinput; gunicorn poultry_farm.wsgi --workers 2 --timeout 120 --bind 0.0.0.0:${PORT:-8080}
