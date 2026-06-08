#!/bin/bash
set -e

echo "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
echo "   ðŸª· Mithila White Gold â€” Startup Script"
echo "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"

# â”€â”€ SQLite write-permission fix for Hugging Face Spaces â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HF Spaces runs as UID 1000 with the /app directory potentially read-only.
# We copy the DB to /tmp (always writable) so Django can write to it.
# Skip this if DATABASE_URL is set (PostgreSQL is being used instead).
if [ -z "$DATABASE_URL" ]; then
    echo "ðŸ—„ï¸  Using SQLite â€” copying DB to writable /tmp location..."
    if [ ! -f /tmp/db_makhana.sqlite3 ]; then
        if [ -f /app/db_makhana.sqlite3 ]; then
            cp /app/db_makhana.sqlite3 /tmp/db_makhana.sqlite3
            echo "   âœ… DB copied to /tmp/db_makhana.sqlite3"
        else
            echo "   âš ï¸  No source DB found â€” will create fresh DB at /tmp"
        fi
    else
        echo "   â„¹ï¸  DB already exists at /tmp/db_makhana.sqlite3 (reusing)"
    fi
    # Tell Django to use the writable path
    export SQLITE_DB_PATH=/tmp/db_makhana.sqlite3
fi

# â”€â”€ Collect static files â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo "ðŸ“¦ Collecting static files..."
python manage.py collectstatic --noinput

# â”€â”€ Apply database migrations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo "ðŸ—„ï¸  Applying database migrations..."
python manage.py migrate --noinput

# â”€â”€ Start Gunicorn on port 7860 (required by Hugging Face Spaces) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo "ðŸš€ Starting Gunicorn on port 7860..."
exec gunicorn \
    --bind 0.0.0.0:7860 \
    --workers 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    poultry_farm.wsgi:application
