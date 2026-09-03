"""Clean synchronous TestClient wrapper over httpx.AsyncClient for FastAPI ASGI testing."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
import httpx

from app.main import app


class TestClient:
    """Synchronous test client compatible with Starlette/httpx test interfaces."""
    __test__ = False

    def __init__(self, asgi_app=app, base_url: str = "http://testserver") -> None:
        self.app = asgi_app
        self.transport = httpx.ASGITransport(app=asgi_app)
        self.base_url = base_url

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request("GET", url, **kwargs))

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request("POST", url, **kwargs))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            return await client.request(method, url, **kwargs)
