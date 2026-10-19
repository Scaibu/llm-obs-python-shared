"""
Blueprint:
- Pure admission evaluation rules.
"""
class GlobalAdmissionRules:
    @staticmethod
    def should_admit(in_flight: int, max_concurrency: int) -> bool:
        return in_flight < max_concurrency
