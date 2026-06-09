"""
Shared Flask-Limiter instance. Created here (without an app) so blueprints can
decorate routes at import time; app.py calls limiter.init_app(app).

Default storage is in-memory, which is correct for our single-gunicorn-worker
deployment. If you scale to multiple workers/processes, point RATELIMIT_STORAGE
at a shared backend (e.g. redis://...).

Client IP comes from get_remote_address, which reads request.remote_addr — the
ProxyFix middleware in app.py makes that the real client IP behind nginx.
"""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATELIMIT_STORAGE", "memory://"),
    default_limits=[],          # only explicitly-decorated routes are limited
)