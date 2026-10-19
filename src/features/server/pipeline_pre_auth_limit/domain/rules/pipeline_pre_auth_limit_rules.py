"""
Blueprint:
- Pure rate limiter evaluation rule.
"""
class PreAuthLimitRules:
    @staticmethod
    def evaluate(tokens_remaining: float, cost: float = 1.0) -> bool:
        return tokens_remaining >= cost
