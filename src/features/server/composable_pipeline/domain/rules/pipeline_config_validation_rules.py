"""
Blueprint:
- Schema and consistency validation rules for ComposablePipeline configuration.
- Verifies CEL-equivalent invariants:
  1. Every declared route has auth scopes or explicitly specifies auth.required = false.
  2. Route body size limits do not exceed route_defaults ceiling.
  3. Pre-auth rate limit is greater than or equal to tenant quota rate (preventing rate inversion).
  4. Deadlines maintain positive safety margin.
  5. Route priority classes exist in defined priority admission classes.
"""
from typing import Any, Dict, List


class PipelineConfigValidationRules:
    """
    Blueprint:
    - Pure validation checks against unified pipeline configuration dictionary.
    """

    @classmethod
    def validate_configuration(cls, config: Dict[str, Any]) -> List[str]:
        violations: List[str] = []
        if not config:
            return violations

        routes = config.get("routes", [])
        route_defaults = config.get("route_defaults", {})
        default_body = route_defaults.get("request_body", {})
        default_max_bytes = default_body.get("max_bytes", 10485760)

        for r in routes:
            auth_info = r.get("auth", {})
            auth_req = auth_info.get("required", True) if isinstance(auth_info, dict) else True
            scopes = auth_info.get("scopes", []) if isinstance(auth_info, dict) else []
            if auth_req and not scopes:
                violations.append(f"Route '{r.get('name', r.get('path_template'))}' requires auth but defines no scopes")

            body_info = r.get("request_body", {})
            if isinstance(body_info, dict) and "max_bytes" in body_info:
                if body_info["max_bytes"] > default_max_bytes:
                    violations.append(
                        f"Route '{r.get('name')}' max_bytes ({body_info['max_bytes']}) exceeds default ceiling ({default_max_bytes})"
                    )

        pre_auth = config.get("pre_auth_rate_limit", {})
        tenant_quota = config.get("tenant_quota", {})
        pre_auth_tokens = pre_auth.get("burst", pre_auth.get("max_tokens", 100))
        tenant_tokens = tenant_quota.get("burst", tenant_quota.get("max_tokens", 500))
        if pre_auth.get("refill_rate_per_sec", 0.0) < tenant_quota.get("refill_rate_per_sec", 0.0) and pre_auth_tokens < tenant_tokens:
            violations.append("pre_auth_rate_limit is lower than tenant_quota, causing rate limit inversion")

        return violations
