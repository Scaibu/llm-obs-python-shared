"""
Blueprint:
- Right-to-left proxy traversal rules for IP extraction.
"""
import ipaddress
from typing import List

class PeerResolutionRules:
    @staticmethod
    def is_ip_trusted(ip_str: str, trusted_networks: List[str]) -> bool:
        try:
            ip = ipaddress.ip_address(ip_str.strip())
            for net_str in trusted_networks:
                net = ipaddress.ip_network(net_str.strip(), strict=False)
                if ip in net:
                    return True
        except ValueError:
            return False
        return False

    @classmethod
    def resolve_client_ip(cls, remote_addr: str, x_forwarded_for: str, trusted_proxies: List[str]) -> str:
        if not x_forwarded_for:
            return remote_addr
        hops = [h.strip() for h in x_forwarded_for.split(",") if h.strip()]
        for hop in reversed(hops):
            if not cls.is_ip_trusted(hop, trusted_proxies):
                return hop
        return remote_addr
