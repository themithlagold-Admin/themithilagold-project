# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM: Force linux/amd64 — required when building from Windows / Mac ARM
# (M1/M2/M3). Prevents "exec format error" on Hugging Face Spaces.
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

# ── Non-root user (UID 1000) — required by Hugging Face Spaces ───────────────
RUN useradd -m -u 1000 hfuser && chown -R hfuser:hfuser /app
USER 1000

# ── Port ──────────────────────────────────────────────────────────────────────
# Railway injects $PORT at runtime; expose 8080 as default fallback
EXPOSE 8080

# ── Start command ─────────────────────────────────────────────────────────────
# railway.json startCommand overrides this; kept as fallback.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput; gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 --log-level info poultry_farm.wsgi:application"]
