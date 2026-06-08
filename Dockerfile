# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM: Force linux/amd64 — required when building from Windows / Mac ARM
# (M1/M2/M3). Prevents "exec format error" on Hugging Face Spaces.
# ─────────────────────────────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.11-slim

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

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
# Hugging Face Spaces strictly requires port 7860
EXPOSE 7860

# ── Start command ─────────────────────────────────────────────────────────────
# No entrypoint.sh used — avoids CRLF/permission issues entirely.
# Runs: collectstatic → migrate → gunicorn (all in one shell command)
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:7860 --workers 2 --timeout 120 poultry_farm.wsgi:application"]
