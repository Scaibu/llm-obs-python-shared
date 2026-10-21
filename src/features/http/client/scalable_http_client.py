import asyncio
import httpx
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.features.http.pipeline.types import PipelineContext, RequestConfig
from src.features.http.pipeline.pipeline_runner import (
    HttpPipelineRunner,
    get_pipeline_runner,
    pipeline_runner,
)

class PipelineHttpClient:
    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        runner: Optional[HttpPipelineRunner] = None,
        profile: str = "default",
        steps: Optional[List[Any]] = None,
        tenant_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        target_class: str = "declared_upstream",
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        if config_path is not None:
            p = Path(config_path)
            if p.is_dir():
                p = p / "http-config.yml"
            if p.exists():
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                if profile == "default" and "profile" in cfg:
                    profile = cfg["profile"]
                if "client" in cfg and "timeout_seconds" in cfg["client"]:
                    timeout = float(cfg["client"]["timeout_seconds"])
                if steps is None and "pipeline" in cfg and "steps" in cfg["pipeline"]:
                    steps = cfg["pipeline"]["steps"]
        self.base_url: str = base_url.rstrip("/")
        self.timeout: float = timeout
        self.profile: str = profile
        if runner is not None:
            self.runner: HttpPipelineRunner = runner
        elif steps is not None:
            self.runner = HttpPipelineRunner(steps=steps)
        elif profile != "default":
            self.runner = get_pipeline_runner(profile=profile)
        else:
            self.runner = pipeline_runner
        self.default_tenant_id: str = tenant_id or "default"
        self.default_principal_id: str = principal_id or "anonymous"
        self.default_target_class: str = target_class
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def from_config(cls, config_path: Union[str, Path], **kwargs: Any) -> "PipelineHttpClient":
        return cls(config_path=config_path, **kwargs)


    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        clean_path = path_or_url.lstrip("/")
        return f"{self.base_url}/{clean_path}" if self.base_url else path_or_url

    async def execute_async(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        body: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        target_class: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        full_url = self._resolve_url(url)
        payload = json if json is not None else body
        effective_timeout_ms = (timeout or self.timeout) * 1000.0

        ctx = PipelineContext(
            config=RequestConfig(
                method=method.upper(),
                url=full_url,
                headers=dict(headers or {}),
                body=payload,
                timeout_ms=effective_timeout_ms,
            ),
            tenant_id=tenant_id or self.default_tenant_id,
            principal_id=principal_id or self.default_principal_id,
            target_class=target_class or self.default_target_class,
        )
        from python_shared.telemetry.tracer import trace_pipeline_stage

        with trace_pipeline_stage(
            f"http.client.{method.upper()}",
            attributes={
                "http.method": method.upper(),
                "http.url": full_url,
                "tenant.id": ctx.tenant_id,
            },
            tracer_name="http.client",
        ):
            # 1. Run through full 7-step pipeline
            ctx = await self.runner.run(ctx)

            # 2. Check if CacheEval short-circuited with a cached response
            if ctx.cached_response is not None:
                if isinstance(ctx.cached_response, httpx.Response):
                    return ctx.cached_response
                return httpx.Response(
                    status_code=200,
                    json=ctx.cached_response,
                    headers={"X-Cache": "HIT"},
                    request=httpx.Request(method, full_url),
                )

            # 3. Live network call via httpx with deep tracing
            try:
                with trace_pipeline_stage(
                    "http.network.dispatch",
                    attributes={"http.url": full_url},
                    tracer_name="http.client",
                ):
                    async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                        response = await client.request(
                            method=ctx.config.method,
                            url=ctx.config.url,
                            params=params,
                            headers=ctx.config.headers,
                        json=payload if json is not None else None,
                        content=payload if json is None and payload is not None else None,
                        timeout=(ctx.config.timeout_ms / 1000.0),
                    )

                if ctx.circuit_key:
                    if response.is_server_error:
                        ctx.circuit_breaker.on_failure(ctx.circuit_key)
                    else:
                        ctx.circuit_breaker.on_success(ctx.circuit_key)

                # Store response in cache if storable according to RFC 9111
                if ctx.hashed_request_key:
                    from src.features.http.pipeline.cache_eval.domain.rules.cache_eval_rules import CacheEvalRules
                    if CacheEvalRules.is_storable(ctx.config.headers, dict(response.headers)):
                        try:
                            ctx.cache_store.set(ctx.tenant_id, ctx.hashed_request_key, response.json())
                        except Exception:
                            pass

                return response
            except Exception as exc:
                if ctx.circuit_key:
                    ctx.circuit_breaker.on_failure(ctx.circuit_key)
                raise exc

    def execute_sync(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        body: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        target_class: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.execute_async(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json,
            body=body,
            tenant_id=tenant_id,
            principal_id=principal_id,
            target_class=target_class,
            timeout=timeout,
        )

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    # Convenience HTTP methods
    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self.execute_sync("GET", url, params=params, headers=headers)

    def post(self, url: str, json: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self.execute_sync("POST", url, json=json, headers=headers)

    def put(self, url: str, json: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self.execute_sync("PUT", url, json=json, headers=headers)

    def patch(self, url: str, json: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self.execute_sync("PATCH", url, json=json, headers=headers)

    def delete(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self.execute_sync("DELETE", url, params=params, headers=headers)

    async def aget(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return await self.execute_async("GET", url, params=params, headers=headers)

    async def apost(self, url: str, json: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return await self.execute_async("POST", url, json=json, headers=headers)

    # Upload & Direct-to-Storage Lifecycle
    def create_upload_session(
        self,
        filename: str,
        content_type: str,
        size_bytes: int,
        declared_sha256: str,
        tenant_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        from src.features.http.pipeline.upload_pipeline import (
            UploadPipelineService,
            CreateSessionInputDTO,
            InMemoryStorageAdapter,
            InMemoryMetadataAdapter,
            InMemoryQuotaAdapter,
        )
        if not hasattr(self, "_upload_service"):
            self._upload_service = UploadPipelineService(
                InMemoryStorageAdapter(),
                InMemoryMetadataAdapter(),
                InMemoryQuotaAdapter(),
            )
        return self._upload_service.create_upload_session(
            CreateSessionInputDTO(
                tenant_id=tenant_id or self.default_tenant_id,
                principal_id=principal_id or self.default_principal_id,
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                declared_sha256=declared_sha256,
                metadata=metadata or {},
            )
        )

    def complete_upload(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
        principal_id: Optional[str] = None,
    ):
        from src.features.http.pipeline.upload_pipeline import CompleteUploadInputDTO
        return self._upload_service.complete_upload(
            CompleteUploadInputDTO(
                session_id=session_id,
                tenant_id=tenant_id or self.default_tenant_id,
                principal_id=principal_id or self.default_principal_id,
            )
        )

    def close(self) -> None:
        if self._sync_client:
            self._sync_client.close()
        if self._async_client:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_client.aclose())
            except RuntimeError:
                asyncio.run(self._async_client.aclose())

ResilientHttpClient = PipelineHttpClient
httpClient = PipelineHttpClient()

__all__ = [
    "PipelineHttpClient",
    "ResilientHttpClient",
    "httpClient",
]
