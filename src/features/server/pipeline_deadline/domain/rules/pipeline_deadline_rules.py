"""
Blueprint:
- Deadline computation rules and safety margin clamping.
"""
from typing import Optional

class DeadlineRules:
    @staticmethod
    def calculate_budget(
        client_timeout_ms: Optional[float],
        route_min_ms: float,
        route_max_ms: float,
        safety_margin_ms: float,
    ) -> float:
        if client_timeout_ms is not None:
            inherited = max(0.0, client_timeout_ms - safety_margin_ms)
            return min(route_max_ms, inherited)
        return route_max_ms

    @staticmethod
    def is_viable(budget_ms: float, route_min_ms: float) -> bool:
        return budget_ms >= route_min_ms
