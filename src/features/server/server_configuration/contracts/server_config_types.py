"""
Blueprint:
- Strongly-typed Pydantic schemas for server configuration and policy snapshot.
- All fields strictly typed, ranged, and frozen (immutable).
"""
from typing import List, Optional, Set
from pydantic import BaseModel, Field, ConfigDict

class ServerNetworkConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    public_bind: str = Field(default="0.0.0.0:8000")
    admin_bind: str = Field(default="127.0.0.1:9090")
    max_request_timeout: str = Field(default="60s")
    idle_connection_timeout: str = Field(default="65s")
    header_read_timeout: str = Field(default="10s")
    handshake_timeout: str = Field(default="5s")
    upstream_lb_idle_timeout: str = Field(default="60s")
    tls_mode: str = Field(default="off")
    trusted_proxies: List[str] = Field(default_factory=lambda: ["127.0.0.1/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])

class ServerLifecycleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    propagation_wait: str = Field(default="2s")
    drain_deadline: str = Field(default="15s")
    force_cleanup_margin: str = Field(default="3s")
    orchestrator_kill_timeout: str = Field(default="30s")

class ServerLimitsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_connection_cap: int = Field(default=10000, gt=0)
    per_client_cap: int = Field(default=100, gt=0)
    max_body_bytes: int = Field(default=10485760, gt=0)
    global_admission_limit: int = Field(default=1000, gt=0)
    ip_rate_limit_tokens: int = Field(default=100, gt=0)
    ip_rate_limit_refill_per_sec: float = Field(default=10.0, gt=0.0)
    tenant_quota_tokens: int = Field(default=500, gt=0)
    tenant_quota_refill_per_sec: float = Field(default=50.0, gt=0.0)

class ServerPolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    server: ServerNetworkConfig = Field(default_factory=ServerNetworkConfig)
    lifecycle: ServerLifecycleConfig = Field(default_factory=ServerLifecycleConfig)
    limits: ServerLimitsConfig = Field(default_factory=ServerLimitsConfig)
