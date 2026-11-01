"""Entry point: create the app, mount static files, register routes."""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import config, routes

app = FastAPI(title="Invoice Automation Backend", version="1.0.0")

# Template fonts are also served over HTTP so the HTML preview can use them.
app.mount(
    "/api/fonts",
    StaticFiles(directory=os.path.join(config.BACKEND_DIR, "resources", "fonts")),
    name="fonts",
)

class SecurityHeaders(BaseHTTPMiddleware):
    """Stop browsers from sniffing uploaded files as a different content type."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


app.add_middleware(SecurityHeaders)
app.include_router(routes.router)
