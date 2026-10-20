"""
Blueprint:
- Identity lifecycle rules and utilities:
  1. API Key prefixing and SHA-256 / HMAC hashing (stored hash only, never plaintext)
  2. Constant-time secret comparison (mitigating timing attacks)
  3. Session epoch rotation and server-side invalidation
"""
import hmac
import hashlib
import secrets
from typing import Final, Tuple

class IdentityLifecycleConstants:
    KEY_PREFIX: Final[str] = "live_sk_"
    MIN_KEY_BYTES: Final[int] = 32

class IdentityLifecycleRules:
    @staticmethod
    def generate_api_key(prefix: str = IdentityLifecycleConstants.KEY_PREFIX) -> Tuple[str, str]:
        # Generates (raw_key, hashed_key). The raw_key is displayed once; hashed_key is stored in DB.
        random_bytes = secrets.token_urlsafe(IdentityLifecycleConstants.MIN_KEY_BYTES)
        raw_key = f"{prefix}{random_bytes}"
        hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return raw_key, hashed_key

    @staticmethod
    def verify_api_key_hash(provided_raw_key: str, stored_hash: str) -> bool:
        # 3.2 Constant-time comparison everywhere a secret is compared
        computed_hash = hashlib.sha256(provided_raw_key.encode("utf-8")).hexdigest()
        return hmac.compare_digest(computed_hash, stored_hash)

    @staticmethod
    def constant_time_compare(val_a: str, val_b: str) -> bool:
        return hmac.compare_digest(val_a, val_b)
