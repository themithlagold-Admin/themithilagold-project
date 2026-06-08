web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn poultry_farm.wsgi --worker-class gevent --workers 1 --timeout 120 --bind 0.0.0.0:$PORT
