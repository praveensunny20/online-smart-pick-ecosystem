"""
Shared slowapi Limiter instance.

Kept in its own module so that both `app.main` (which registers the
middleware + exception handler) and `app.api.auth` (which decorates
routes with per-endpoint limits) can import the SAME limiter without
causing a circular import.

Why this matters:
    - If we put the Limiter inside app/main.py, app/api/auth.py would have
      to `from app.main import limiter`. But app/main.py already imports
      the auth router (through app.api.__init__), which would cause Python
      to partially import app.main, fail to find `limiter`, and crash at
      startup.
    - Moving the Limiter here means nothing in app.main is required to
      import it — the dependency graph is:
          app.main ───► app.main_limiter
          app.api.auth ───► app.main_limiter
      No cycles.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Key function: rate-limit by client IP address.
# If you later put the app behind a trusted proxy, switch this to read
# X-Forwarded-For (but ONLY if you fully control the proxy — otherwise
# clients can spoof their IP).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,  # Add X-RateLimit-* response headers
)
