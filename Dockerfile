# ── Stage 1: build the Angular frontend ────────────────
# Production build emits hashed filenames (outputHashing: "all") for cache-busting.
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend that also serves the built SPA ──
FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    FRONTEND_DIR=/app/frontend
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
# The Angular "application" builder outputs to dist/<project>/browser
COPY --from=frontend /app/dist/c9800-monitor/browser /app/frontend

EXPOSE 5000
# Single worker: the app keeps in-process state (background collector thread +
# live RESTCONF client). Threads handle request concurrency.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", \
     "--access-logfile", "-", "--bind", "0.0.0.0:5000", "app:app"]
