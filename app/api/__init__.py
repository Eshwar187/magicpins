"""Vera API Package (Phase 4)."""

from app.api.routes import router, get_service, _service_instance
from app.api.service import EngineService

__all__ = ["router", "get_service", "_service_instance", "EngineService"]
