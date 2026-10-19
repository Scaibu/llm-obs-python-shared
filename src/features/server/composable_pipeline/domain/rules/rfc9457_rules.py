"""
Blueprint:
- RFC 9457 envelope generation rules for HTTP error statuses.
"""
from typing import Dict, Optional
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails

class ProblemDetailsRules:
    STATUS_TITLES: Dict[int, str] = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        413: "Payload Too Large",
        415: "Unsupported Media Type",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        500: "Internal Server Error",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    @classmethod
    def create_problem(cls, status: int, detail: str, instance: str, error_type: Optional[str] = None) -> ProblemDetails:
        title = cls.STATUS_TITLES.get(status, "HTTP Error")
        return ProblemDetails(
            type=error_type or f"https://httpstatuses.io/{status}",
            title=title,
            status=status,
            detail=detail,
            instance=instance,
        )
