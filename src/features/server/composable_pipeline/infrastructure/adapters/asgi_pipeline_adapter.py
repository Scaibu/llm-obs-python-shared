"""
Blueprint:
- AsgiPipelineAdapter: Exposes an ASGI-compliant callable application interface for ComposablePipelineService.
- Translates HTTP ASGI scopes, streaming receive bodies, and send events into IngressRequest and IngressResponse models.
- Serializes RFC-9457 ProblemDetails and JSON payloads into ASGI http.response.start and http.response.body events.
"""
import json
from typing import Any, Callable, Dict, List, Tuple

from src.features.server.composable_pipeline.contracts.pipeline_types import (
    IngressRequest,
    PayloadTooLargeError,
)
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
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        expects_continue = headers.get("expect", "").lower().strip() == "100-continue"

        async def read_body(max_bytes: int) -> bytes:
            if expects_continue:
                await send({"type": "http.response.informational", "status": 100, "headers": []})
            body_parts: List[bytes] = []
            total = 0
            more_body = True
            while more_body:
                message = await receive()
                chunk = message.get("body", b"")
                total += len(chunk)
                if max_bytes > 0 and total > max_bytes:
                    raise PayloadTooLargeError()
                body_parts.append(chunk)
                more_body = message.get("more_body", False)
            return b"".join(body_parts)

        req = IngressRequest(
            method=method,
            path=path,
            headers=headers,
            remote_addr=client_tuple[0],
            body=None,
        )
        res = await self._pipeline_service.execute(req, body_reader=read_body)
        await self._send_response(res, send)

    async def _send_response(
        self,
        res: Any,
        send: Callable[[Dict[str, Any]], Any],
    ) -> None:
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
