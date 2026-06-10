# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM: Force linux/amd64 — required when building from Windows / Mac ARM
# ─────────────────────────────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.11-slim

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project ──────────────────────────────────────────────────────────────
COPY . .

# ── Collect static files at BUILD TIME (not at runtime) ───────────────────────
# Using a dummy SECRET_KEY — collectstatic does not need the real DB or key.
# This means static files are baked into the image, and startup is instant.
RUN SECRET_KEY=dummy-build-key DATABASE_URL="" python manage.py collectstatic --noinput

# ── Non-root user (UID 1000) ──────────────────────────────────────────────────
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER 1000

# ── Port ──────────────────────────────────────────────────────────────────────
# Railway injects $PORT at runtime; 8080 is the fallback default
EXPOSE 8080

# ── Start command ─────────────────────────────────────────────────────────────
# Only migrate runs at startup (fast — no pending migrations on Neon).
# Gunicorn starts immediately after. No collectstatic delay.
CMD ["sh", "-c", "python manage.py migrate --noinput; gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 --log-level info poultry_farm.wsgi:application"]
