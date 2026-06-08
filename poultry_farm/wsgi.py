import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poultry_farm.settings')

# ---------------------------------------------------------------------------
# Auto-migrate on Vercel cold-start
# The static-build phase (build_files.sh) runs without DATABASE_URL, so
# migrations can't execute there.  Running them here — once per Lambda
# instance — ensures the schema is always current before the first request.
# ---------------------------------------------------------------------------
_MIGRATED = False

def _run_migrations():
    global _MIGRATED
    if _MIGRATED:
        return
    try:
        from django.core.management import call_command
        call_command('migrate', '--noinput', verbosity=0)
        _MIGRATED = True
    except Exception as exc:
        # Log but don't crash — the error will surface naturally on first query
        import sys
        print(f"[wsgi] migrate failed: {exc}", file=sys.stderr)

_run_migrations()

application = get_wsgi_application()
app = application

