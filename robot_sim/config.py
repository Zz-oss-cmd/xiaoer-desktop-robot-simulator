from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping


def _positive_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class VirtualDeviceConfig:
    """Validated deployment settings for the TCP virtual device."""

    host: str = "127.0.0.1"
    port: int = 8765
    link_timeout_ms: int = 3_000
    receive_size: int = 256
    poll_interval_s: float = 0.05
    max_connections: int = 8
    max_queue_size: int = 128

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        if isinstance(self.port, bool) or not isinstance(self.port, int):
            raise ValueError("port must be an integer")
        if not 0 <= self.port <= 65_535:
            raise ValueError("port must be in [0, 65535]")
        _positive_int("link_timeout_ms", self.link_timeout_ms)
        _positive_int("receive_size", self.receive_size)
        _positive_int("max_connections", self.max_connections)
        _positive_int("max_queue_size", self.max_queue_size)
        if (
            isinstance(self.poll_interval_s, bool)
            or not isinstance(self.poll_interval_s, (int, float))
            or not math.isfinite(self.poll_interval_s)
            or self.poll_interval_s <= 0
        ):
            raise ValueError("poll_interval_s must be a positive finite number")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "VirtualDeviceConfig":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(values) - allowed, key=str)
        if unknown:
            names = ", ".join(str(name) for name in unknown)
            raise ValueError(f"unknown configuration fields: {names}")
        return cls(**dict(values))

    @classmethod
    def load(cls, path: str | Path) -> "VirtualDeviceConfig":
        config_path = Path(path)
        try:
            values = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot load configuration {config_path}: {exc}") from exc
        if not isinstance(values, dict):
            raise ValueError("configuration root must be a JSON object")
        return cls.from_mapping(values)
