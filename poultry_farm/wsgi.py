import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poultry_farm.settings')

# NOTE: Migrations are handled by the start command in railway.json
# (and build_files.sh for Vercel). Do NOT run migrate here — it blocks
# gunicorn from binding to the port, causing healthcheck failures.

application = get_wsgi_application()
app = application
