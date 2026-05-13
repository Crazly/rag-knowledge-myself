"""Simple token-based auth middleware."""

import os
import secrets

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for static files, health checks, and Dify API
        if request.url.path.startswith(("/static", "/api/dify")):
            return await call_next(request)

        # If ACCESS_TOKEN is set, require it
        if ACCESS_TOKEN:
            token = request.cookies.get("kb_token") or request.headers.get("X-Access-Token")
            if token != ACCESS_TOKEN:
                # Allow login page
                if request.url.path == "/login":
                    return await call_next(request)
                if request.method == "POST" and request.url.path == "/api/login":
                    return await call_next(request)

                # For browser requests, redirect to login; for API, return 401
                if "text/html" in request.headers.get("accept", ""):
                    from fastapi.responses import RedirectResponse
                    return RedirectResponse("/login", status_code=302)
                raise HTTPException(401, "Unauthorized")

        return await call_next(request)
