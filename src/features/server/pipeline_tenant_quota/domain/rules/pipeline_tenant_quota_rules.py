"""
Blueprint:
- Tenant quota evaluation rules.
"""
class TenantQuotaRules:
    @staticmethod
    def has_budget(remaining_tokens: float, cost: float = 1.0) -> bool:
        return remaining_tokens >= cost
