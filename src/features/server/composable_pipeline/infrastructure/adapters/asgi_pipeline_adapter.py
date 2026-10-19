"""
Blueprint:
- AsgiPipelineAdapter: Exposes an ASGI-compliant callable application interface for ComposablePipelineService.
- Translates HTTP ASGI scopes, streaming receive bodies, and send events into IngressRequest and IngressResponse models.
- Serializes RFC-9457 ProblemDetails and JSON payloads into ASGI http.response.start and http.response.body events.
"""
import json
from typing import Any, Callable, Dict, List, Tuple

from src.features.server.composable_pipeline.contracts.pipeline_types import IngressRequest
from src.features.server.composable_pipeline.service.composable_pipeline_service import (
    ComposablePipelineService,
)


class AsgiPipelineAdapter:
    """
    Blueprint:
    - Provides an ASGI 3.0 compatible application interface wrapping ComposablePipelineService.
    """

    def __init__(self, pipeline_service: ComposablePipelineService) -> None:
        self._pipeline_service = pipeline_service

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[Dict[str, Any]], Any],
    ) -> None:
        if scope.get("type") != "http":
            return
        headers: Dict[str, str] = {
            k.decode("latin1").lower(): v.decode("latin1")
            for k, v in scope.get("headers", [])
        }
        client_tuple = scope.get("client") or ("127.0.0.1", 0)
        body_parts: List[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            body_parts.append(message.get("body", b""))
            more_body = message.get("more_body", False)
        raw_body = b"".join(body_parts)
        req = IngressRequest(
            method=scope.get("method", "GET"),
            path=scope.get("path", "/"),
            headers=headers,
            remote_addr=client_tuple[0],
            body=raw_body,
        )
        res = await self._pipeline_service.execute(req)
        resp_headers: List[Tuple[bytes, bytes]] = [
            (k.encode("latin1"), v.encode("latin1")) for k, v in res.headers.items()
        ]
        if res.problem_details is not None:
            body_bytes = res.problem_details.model_dump_json().encode("utf-8")
            resp_headers.append((b"content-type", b"application/problem+json"))
        elif isinstance(res.body, (dict, list)):
            body_bytes = json.dumps(res.body, default=lambda o: o.decode("utf-8", errors="replace") if isinstance(o, bytes) else str(o)).encode("utf-8")
            resp_headers.append((b"content-type", b"application/json"))
        elif isinstance(res.body, str):
            body_bytes = res.body.encode("utf-8")
        elif isinstance(res.body, bytes):
            body_bytes = res.body
        else:
            body_bytes = b""
        await send(
            {
                "type": "http.response.start",
                "status": res.status_code,
                "headers": resp_headers,
            }
        )
        await send({"type": "http.response.body", "body": body_bytes})
