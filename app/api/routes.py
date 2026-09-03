"""FastAPI routes for /v1/* endpoints according to the challenge contract."""

from __future__ import annotations

from typing import Union
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.schemas import (
    ContextAckResponse,
    ContextConflictResponse,
    ContextErrorResponse,
    CtxBody,
    HealthzResponse,
    MetadataResponse,
    ReplyBody,
    ReplyResponse,
    TickBody,
    TickResponse,
)
from app.api.service import EngineService

router = APIRouter(prefix="/v1")

# Global singleton service for the router
_service_instance: EngineService = EngineService()


def get_service() -> EngineService:
    return _service_instance


@router.get("/healthz", response_model=HealthzResponse)
def healthz(service: EngineService = Depends(get_service)) -> HealthzResponse:
    """Liveness probe returning server status, uptime, and context counts."""
    return service.get_health()


@router.get("/metadata", response_model=MetadataResponse)
@router.post("/metadata", response_model=MetadataResponse)
def metadata(service: EngineService = Depends(get_service)) -> MetadataResponse:
    """Metadata detailing candidate bot identity, model approach, and version."""
    return service.get_metadata()


@router.post(
    "/context",
    responses={
        200: {"model": ContextAckResponse},
        409: {"model": ContextConflictResponse},
        400: {"model": ContextErrorResponse},
    },
)
def push_context(
    body: CtxBody,
    service: EngineService = Depends(get_service),
) -> JSONResponse:
    """Ingest context envelope with atomic versioning and schema normalization."""
    accepted, ack_or_reason, conflict_ver, stored_at_or_details = service.push_context(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload,
        delivered_at=body.delivered_at,
    )

    if accepted:
        content = {
            "accepted": True,
            "ack_id": ack_or_reason,
            "stored_at": stored_at_or_details,
        }
        return JSONResponse(status_code=status.HTTP_200_OK, content=content)

    if ack_or_reason == "stale_version":
        content = {
            "accepted": False,
            "reason": "stale_version",
            "current_version": conflict_ver,
        }
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=content)

    # Malformed scope or payload
    content = {
        "accepted": False,
        "reason": ack_or_reason or "invalid_context",
        "details": stored_at_or_details,
    }
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)


@router.post("/tick", response_model=TickResponse)
def tick(
    body: TickBody,
    service: EngineService = Depends(get_service),
) -> TickResponse:
    """Periodic wake-up tick for evaluating available triggers and proactive messages."""
    return service.tick(now=body.now, available_triggers=body.available_triggers)


@router.post("/reply", response_model=ReplyResponse)
def reply(
    body: ReplyBody,
    service: EngineService = Depends(get_service),
) -> ReplyResponse:
    """Synchronous reply handling for active conversations."""
    return service.reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        received_at=body.received_at,
        turn_number=body.turn_number,
    )
