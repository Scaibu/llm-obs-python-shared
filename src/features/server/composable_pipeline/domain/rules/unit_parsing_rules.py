"""
Blueprint:
- Duration and byte string parsing rules.
- Translates human-friendly duration strings ('10s', '50ms', '100m', '1h') to seconds (float) or milliseconds.
- Translates human-friendly byte strings ('64KiB', '1MiB', '10MiB') to integer byte counts.
"""
import re
from typing import Union


class UnitParsingRules:
    """
    Blueprint:
    - Pure unit parsing utilities for durations and byte sizes.
    """

    DURATION_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(ms|s|m|h|d)?$")
    BYTES_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(b|kib|kb|mib|mb|gib|gb)?$", re.IGNORECASE)

    @classmethod
    def parse_duration_to_seconds(cls, val: Union[str, int, float]) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip().lower()
        match = cls.DURATION_PATTERN.match(val_str)
        if not match:
            return float(val_str)
        num, unit = float(match.group(1)), match.group(2) or "s"
        if unit == "ms":
            return num / 1000.0
        elif unit == "s":
            return num
        elif unit == "m":
            return num * 60.0
        elif unit == "h":
            return num * 3600.0
        elif unit == "d":
            return num * 86400.0
        return num

    @classmethod
    def parse_duration_to_milliseconds(cls, val: Union[str, int, float]) -> float:
        return cls.parse_duration_to_seconds(val) * 1000.0

    @classmethod
    def parse_bytes(cls, val: Union[str, int]) -> int:
        if isinstance(val, int):
            return val
        val_str = str(val).strip()
        match = cls.BYTES_PATTERN.match(val_str)
        if not match:
            return int(val_str)
        num = float(match.group(1))
        unit = (match.group(2) or "b").lower()
        if unit in {"b"}:
            return int(num)
        elif unit in {"kb"}:
            return int(num * 1000)
        elif unit in {"kib"}:
            return int(num * 1024)
        elif unit in {"mb"}:
            return int(num * 1000 * 1000)
        elif unit in {"mib"}:
            return int(num * 1024 * 1024)
        elif unit in {"gb"}:
            return int(num * 1000 * 1000 * 1000)
        elif unit in {"gib"}:
            return int(num * 1024 * 1024 * 1024)
        return int(num)
