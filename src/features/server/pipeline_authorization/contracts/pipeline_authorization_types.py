"""
Blueprint:
- Authorization types and DTOs.
"""
from typing import List, Set
from pydantic import BaseModel, Field

class AuthzInputDTO(BaseModel):
    principal_scopes: Set[str] = Field(default_factory=set)
    required_scopes: Set[str] = Field(default_factory=set)

class AuthzOutputDTO(BaseModel):
    authorized: bool
    status_code: int = 200
    missing_scopes: List[str] = Field(default_factory=list)
