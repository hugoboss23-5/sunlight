"""
SUNLIGHT Tenant Middleware
============================

Starlette middleware that extracts tenant_id from the request and sets
it on both the request state and the PostgreSQL session variable
(app.tenant_id) for Row-Level Security.

Tenant resolution order:
    1. X-Tenant-ID header
    2. tenant_id query parameter
    3. Falls back to "default"

Author: SUNLIGHT Team | v2.0.0
"""

import os
import sys

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

sys.path.insert(0, os.path.dirname(__file__))
from sunlight_logging import get_logger

logger = get_logger("tenant_middleware")

DEFAULT_TENANT_ID = "default"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant_id from request and injects it into:
        - request.state.tenant_id (application layer)
        - PostgreSQL session variable app.tenant_id (database layer, for RLS)

    If no tenant_id is found, falls back to DEFAULT_TENANT_ID.
    """

    def __init__(self, app, db_session_factory=None):
        """
        Args:
            app: The ASGI application.
            db_session_factory: Optional callable returning a DB connection.
                If provided, sets current_setting('app.tenant_id') on each request.
        """
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve tenant_id
        tenant_id = (
            request.headers.get("X-Tenant-ID")
            or request.query_params.get("tenant_id")
            or DEFAULT_TENANT_ID
        )

        # Sanitize: strip whitespace, limit length
        tenant_id = tenant_id.strip()[:100]

        # Store on request state
        request.state.tenant_id = tenant_id

        # Set PostgreSQL session variable for RLS if db_session_factory provided
        if self.db_session_factory is not None:
            try:
                conn = self.db_session_factory()
                conn.execute(
                    "SET LOCAL app.tenant_id = %s", (tenant_id,)
                )
            except Exception as e:
                logger.warning(
                    "Failed to set PG tenant session var",
                    extra={"tenant_id": tenant_id, "error": str(e)},
                )

        response = await call_next(request)

        # Echo tenant_id in response header for debugging
        response.headers["X-Tenant-ID"] = tenant_id

        return response
