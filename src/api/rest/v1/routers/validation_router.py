"""
Blueprint:
- Ingress router for validation.
- Mounts REST endpoints and extracts correlation/trace context.
"""

from __future__ import annotations

from typing import Any, Mapping
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.rest.v1.handlers.validation_handler import ValidationHandler
from src.features.validation.service.validation_service import ValidationService
from src.features.validation.infrastructure.adapters.validation_repository_adapter import (
    InMemoryValidationRepositoryAdapter,
)

validation_router = APIRouter(prefix="/api/v1/validation", tags=["validation"])

_default_repo = InMemoryValidationRepositoryAdapter()
_default_service = ValidationService(repository=_default_repo)
_default_handler = ValidationHandler(service=_default_service)


@validation_router.post("/contracts")
async def validate_contract_endpoint(request: Request, payload: dict[str, Any]) -> JSONResponse:
    return await _default_handler.handle_validate_contract(request, payload)


@validation_router.post("/json")
async def validate_json_endpoint(request: Request, payload: dict[str, Any]) -> JSONResponse:
    payload_copy = dict(payload)
    payload_copy["target_type"] = "JSON"
    return await _default_handler.handle_validate_contract(request, payload_copy)
