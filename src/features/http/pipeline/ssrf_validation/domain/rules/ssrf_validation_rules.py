"""
Blueprint:
- Business logic rules for SSRF validation, CIDR range blocking, and scheme verification.
"""
import ipaddress
import socket
from typing import List, Optional
from urllib.parse import urlparse
from src.features.http.pipeline.ssrf_validation.contracts.ssrf_validation_constants import (
    SsrfValidationConstants,
)

class SsrfValidationRules:
    @staticmethod
    def validate_url(
        url: str,
        target_class: str = "declared_upstream",
        allowed_hosts: Optional[List[str]] = None,
    ) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(SsrfValidationConstants.ERROR_INVALID_URL.format(url=url))

        # Declared upstreams bypass SSRF IP checks
        if target_class == "declared_upstream":
            return parsed.hostname or ""

        # User-supplied URLs enforce HTTPS only
        if parsed.scheme.lower() != "https":
            raise ValueError(
                SsrfValidationConstants.ERROR_SCHEME_NOT_ALLOWED.format(scheme=parsed.scheme)
            )

        hostname = parsed.hostname or ""
        if allowed_hosts and hostname not in allowed_hosts:
            raise ValueError(
                SsrfValidationConstants.ERROR_HOST_NOT_ALLOWED.format(hostname=hostname)
            )

        port = parsed.port or 443
        if port != 443:
            raise ValueError(SsrfValidationConstants.ERROR_BLOCKED_PORT.format(port=port))

        # Resolve IP and verify against blocked CIDR ranges
        SsrfValidationRules.validate_resolved_ips(hostname)
        return hostname

    @staticmethod
    def validate_resolved_ips(hostname: str) -> None:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            ip_addrs = {info[4][0] for info in addr_info}
        except socket.gaierror:
            # Cannot resolve - let network client fail naturally
            return

        blocked_networks = [
            ipaddress.ip_network(cidr) for cidr in SsrfValidationConstants.BLOCKED_CIDR_RANGES
        ]

        for ip_str in ip_addrs:
            ip_obj = ipaddress.ip_address(ip_str)
            for net in blocked_networks:
                if ip_obj in net:
                    raise ValueError(
                        SsrfValidationConstants.ERROR_BLOCKED_IP.format(ip=ip_str, cidr=str(net))
                    )
