"""
Blueprint:
- Authentication types and DTOs.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class AuthenticatedPrincipal(BaseModel):
    principal_id: str
    tenant_id: str
    scopes: List[str] = Field(default_factory=list)

class AuthInputDTO(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict)
    require_auth: bool = True

class AuthOutputDTO(BaseModel):
    authenticated: bool
    status_code: int = 200
    principal: Optional[AuthenticatedPrincipal] = None
    rejection_reason: Optional[str] = None
