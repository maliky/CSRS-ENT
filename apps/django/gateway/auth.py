"""Pure login normalization and cache-backed brute-force protection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address
from typing import Protocol


class CounterCache(Protocol):
    """Small cache contract used by the rate limiter."""

    def add(self, key: str, value: int, timeout: int) -> bool: ...

    def get(self, key: str, default: int = 0) -> object: ...

    def incr(self, key: str, delta: int = 1) -> int: ...

    def delete_many(self, keys: list[str]) -> None: ...


def normalize_login(value: str) -> str:
    """Normalize email and short aliases without guessing a domain."""
    return value.strip().casefold()


def client_ip(meta: dict[str, object], trusted_proxies: frozenset[str]) -> str:
    """Use the forwarded client only when the direct peer is trusted."""
    peer = meta.get("REMOTE_ADDR", "unknown")
    peer_value = peer if isinstance(peer, str) and peer else "unknown"
    forwarded = meta.get("HTTP_X_REAL_IP")
    if peer_value not in trusted_proxies or not isinstance(forwarded, str):
        return peer_value
    try:
        return str(ip_address(forwarded.strip()))
    except ValueError:
        return peer_value


def rate_key(kind: str, value: str) -> str:
    """Avoid storing email addresses or IPs in cache key listings."""
    digest = sha256(value.encode("utf-8")).hexdigest()
    return f"pent:login:{kind}:{digest}"


@dataclass(frozen=True, slots=True)
class LoginRateLimiter:
    """Limit failures independently by network peer and login identifier."""

    cache: CounterCache
    limit: int = 5
    window_seconds: int = 900

    def is_blocked(self, ip_address: str, login: str) -> bool:
        return any(
            self._count(key) >= self.limit for key in self._keys(ip_address, login)
        )

    def record_failure(self, ip_address: str, login: str) -> None:
        for key in self._keys(ip_address, login):
            if not self.cache.add(key, 1, self.window_seconds):
                self.cache.incr(key)

    def clear(self, ip_address: str, login: str) -> None:
        self.cache.delete_many(self._keys(ip_address, login))

    def _count(self, key: str) -> int:
        value = self.cache.get(key, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    @staticmethod
    def _keys(ip_address: str, login: str) -> list[str]:
        return [rate_key("ip", ip_address), rate_key("login", login)]
