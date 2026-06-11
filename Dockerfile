# ── Stage 1: build the Angular frontend ────────────────
# Production build emits hashed filenames (outputHashing: "all") for cache-busting.
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: compile the backend to bytecode and strip the source ──
# `-b` writes module.pyc next to module.py (importable once the .py is gone), so
# the shipped image contains NO Python source — and because this happens in a
# separate stage, the .py files never land in a layer of the final image.
# NOTE: the .pyc magic number is tied to the interpreter, so this stage and the
# runtime stage MUST use the same python:3.12-slim base.
FROM python:3.12-slim AS pycompile
WORKDIR /src
COPY backend/ ./
RUN python -m compileall -b -q . \
 && find . -name '*.py' -delete \
 && find . -type d -name '__pycache__' -prune -exec rm -rf {} +

# ── Stage 3: runtime — Python backend that also serves the built SPA ──
FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    FRONTEND_DIR=/app/frontend
WORKDIR /app/backend

# requirements.txt is plain config (not proprietary) — used to install deps.
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Compiled backend (bytecode only — no .py) and the built SPA.
COPY --from=pycompile /src/ ./
COPY --from=frontend /app/dist/c9800-monitor/browser /app/frontend

# Run as a non-root user (defense in depth — a compromised worker isn't uid 0).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000
# Single worker: the app keeps in-process state (background collector thread +
# live RESTCONF client). Threads handle request concurrency.
# The license (per-customer) is NOT baked in — mount it at /app/license.key or
# pass LICENSE_KEY at runtime (see docker-compose.yml).
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", \
     "--access-logfile", "-", "--bind", "0.0.0.0:5000", "app:app"]