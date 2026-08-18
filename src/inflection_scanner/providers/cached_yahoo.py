from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .yahoo import YahooProvider


class CachedYahooProvider:
    def __init__(self, warehouse, provider: YahooProvider | None = None, ttl_hours: dict[str, int] | None = None):
        self.warehouse = warehouse
        self.provider = provider or YahooProvider()
        self.ttl = ttl_hours or {}

    def _cached(self, key: str, ttl_name: str, loader: Callable[[], Any], force: bool = False):
        now = datetime.now(timezone.utc)
        if not force:
            row = self.warehouse.get_cache(key)
            if row:
                expires = _dt(row.get("expires_at"))
                if expires is None or expires > now:
                    return row["payload"]
        value = loader()
        expires = now + timedelta(hours=int(self.ttl.get(ttl_name, 24)))
        self.warehouse.put_cache(key, value, expires.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"))
        return value

    def profile(self, ticker: str, force: bool = False):
        return self._cached(f"profile:{ticker.upper()}", "profile", lambda: self.provider.profile(ticker), force)

    def news(self, ticker: str, limit: int = 12, force: bool = False):
        return self._cached(f"news:{ticker.upper()}:{limit}", "news", lambda: self.provider.news(ticker, limit), force)

    def fx_rate(self, a: str, b: str, force: bool = False):
        payload = self._cached(f"fx:{a}:{b}", "fx", lambda: {"rate": self.provider.fx_rate(a, b)}, force)
        return payload.get("rate") if isinstance(payload, dict) else None


def _dt(value: str | None):
    if not value:
        return None
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except Exception:
        return None
