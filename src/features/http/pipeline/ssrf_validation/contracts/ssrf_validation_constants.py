"""
Blueprint:
- Constants contract for ssrf_validation pipeline step.
"""
from typing import Final, List

class SsrfValidationConstants:
    STEP_NAME: Final[str] = "SsrfValidation"
    STEP_DESCRIPTION: Final[str] = "SSRF Destination & IP Allowlist Guard"
    ERROR_INVALID_URL: Final[str] = "Invalid URL for SSRF validation: {url}"
    ERROR_HOST_NOT_ALLOWED: Final[str] = "Target host '{hostname}' is not in allowed hosts list"
    ERROR_SCHEME_NOT_ALLOWED: Final[str] = "Target scheme '{scheme}' is not allowed for user-supplied URLs (https only)"
    ERROR_BLOCKED_IP: Final[str] = "Security Violation: Resolved IP address '{ip}' falls within blocked network range {cidr}"
    ERROR_BLOCKED_PORT: Final[str] = "Security Violation: Port {port} is not allowed for user-supplied target"

    BLOCKED_CIDR_RANGES: Final[List[str]] = [
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "::ffff:0:0/96",
        "64:ff9b::/96",
        "2002::/16",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    ]
