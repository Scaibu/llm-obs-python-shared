import os
import sys

_shared_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_features_dir = os.path.join(_shared_src, "features")

try:
    import src
    if hasattr(src, "__path__") and _shared_src not in src.__path__:
        src.__path__.append(_shared_src)
    try:
        import src.features
        if hasattr(src.features, "__path__") and _features_dir not in src.features.__path__:
            src.features.__path__.append(_features_dir)
    except Exception:
        pass
except Exception:
    pass

from python_shared.types import BaseResponse, HealthStatusResponse
from python_shared.telemetry import setup_telemetry, get_tracer, REQUEST_COUNT, REQUEST_LATENCY
from python_shared.http import (
    ResilientHttpClient,
    CircuitBreaker,
    CorrelationAndTelemetryMiddleware,
)

from python_shared.db import get_redis_client, get_redis_pool, get_postgres_connection
from python_shared.discovery import (
    resolve_service_endpoint,
    resolve_service_url,
    resolve_service_url_sync,
    ServiceResolver,
    service_resolver,
    ServiceRegistryManager,
    register_fastapi_service,
)
from python_shared.feature_flags import evaluate_flag
from python_shared.validation import (
    YamlValidationService,
    JsonValidationService,
    TomlValidationService,
    ValidationService,
    ValidationRules,
    KeyNormalizationRules,
    SchemaValidationRules,
    YamlValidationRules,
    JsonValidationRules,
    TomlValidationRules,
    ValidationStateMachine,
    ValidationReportModel,
    ValidationStatus,
    ValidationSeverity,
    ValidationTargetType,
    ContractValidationRequestDTO,
    CanonicalKeyDTO,
    ValidationErrorDetail,
    ValidationRepositoryPort,
    InMemoryValidationRepositoryAdapter,
)

__all__ = [
    "BaseResponse",
    "HealthStatusResponse",
    "setup_telemetry",
    "get_tracer",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "ResilientHttpClient",
    "CircuitBreaker",
    "CorrelationAndTelemetryMiddleware",
    "get_redis_client",
    "get_redis_pool",
    "get_postgres_connection",
    "resolve_service_endpoint",
    "resolve_service_url",
    "resolve_service_url_sync",
    "ServiceResolver",
    "service_resolver",
    "ServiceRegistryManager",
    "service_registry_manager",
    "register_fastapi_service",
    "evaluate_flag",
    "YamlValidationService",
    "JsonValidationService",
    "ValidationService",
    "ValidationRules",
    "ValidationStateMachine",
    "ValidationReportModel",
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationTargetType",
    "ContractValidationRequestDTO",
    "CanonicalKeyDTO",
    "ValidationErrorDetail",
    "ValidationRepositoryPort",
    "InMemoryValidationRepositoryAdapter",
    "validation_router",
]
