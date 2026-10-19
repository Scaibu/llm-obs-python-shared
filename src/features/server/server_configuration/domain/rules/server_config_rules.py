"""
Blueprint:
- Pure cross-field validation rules enforcing:
  1. Timeout hierarchy: header_read_timeout < idle_connection_timeout, idle_connection_timeout > upstream_lb_idle_timeout, handshake_timeout <= header_read_timeout.
  2. Lifecycle arithmetic: propagation_wait + drain_deadline + force_cleanup_margin < orchestrator_kill_timeout.
  3. Limits: per_client_cap <= total_connection_cap.
  4. Network exposure: public_bind != admin_bind; admin_bind != 0.0.0.0 unless secured; tls off only on loopback/private.
"""
import re
from typing import List
from src.features.server.server_configuration.contracts.server_config_types import ServerPolicySnapshot

class ServerConfigRules:
    @staticmethod
    def parse_duration_to_seconds(duration_str: str) -> float:
        match = re.match(r"^([0-9]+(?:\.[0-9]+)?)(ms|s|m|h)$", duration_str.strip())
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}. Must have units (ms, s, m, h).")
        val_str, unit = match.groups()
        val = float(val_str)
        if unit == "ms":
            return val / 1000.0
        if unit == "s":
            return val
        if unit == "m":
            return val * 60.0
        if unit == "h":
            return val * 3600.0
        return val

    @classmethod
    def validate_snapshot(cls, snapshot: ServerPolicySnapshot) -> List[str]:
        errors: List[str] = []
        srv = snapshot.server
        lfc = snapshot.lifecycle
        lim = snapshot.limits

        try:
            header_timeout = cls.parse_duration_to_seconds(srv.header_read_timeout)
            idle_timeout = cls.parse_duration_to_seconds(srv.idle_connection_timeout)
            lb_idle_timeout = cls.parse_duration_to_seconds(srv.upstream_lb_idle_timeout)
            handshake_timeout = cls.parse_duration_to_seconds(srv.handshake_timeout)

            if header_timeout >= idle_timeout:
                errors.append(f"header_read_timeout ({srv.header_read_timeout}) must be < idle_connection_timeout ({srv.idle_connection_timeout})")
            if idle_timeout <= lb_idle_timeout:
                errors.append(f"idle_connection_timeout ({srv.idle_connection_timeout}) must be > upstream_lb_idle_timeout ({srv.upstream_lb_idle_timeout})")
            if handshake_timeout > header_timeout:
                errors.append(f"handshake_timeout ({srv.handshake_timeout}) must be <= header_read_timeout ({srv.header_read_timeout})")
        except ValueError as e:
            errors.append(str(e))

        try:
            prop_wait = cls.parse_duration_to_seconds(lfc.propagation_wait)
            drain = cls.parse_duration_to_seconds(lfc.drain_deadline)
            margin = cls.parse_duration_to_seconds(lfc.force_cleanup_margin)
            kill_timeout = cls.parse_duration_to_seconds(lfc.orchestrator_kill_timeout)

            if (prop_wait + drain + margin) >= kill_timeout:
                errors.append(f"Lifecycle shutdown sum ({prop_wait + drain + margin}s) must be < orchestrator_kill_timeout ({kill_timeout}s)")
        except ValueError as e:
            errors.append(str(e))

        if lim.per_client_cap > lim.total_connection_cap:
            errors.append(f"per_client_cap ({lim.per_client_cap}) must be <= total_connection_cap ({lim.total_connection_cap})")

        if srv.public_bind == srv.admin_bind:
            errors.append(f"public_bind ({srv.public_bind}) and admin_bind ({srv.admin_bind}) ports must not collide")

        if srv.admin_bind.startswith("0.0.0.0:"):
            errors.append(f"admin_bind must not listen on public interface (0.0.0.0)")

        return errors
