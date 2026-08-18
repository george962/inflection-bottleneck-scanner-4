from __future__ import annotations


def historical_backtest_status() -> dict[str, str]:
    return {
        "status": "PIT_REQUIRED",
        "reason": "A valid historical backtest requires point-in-time analyst estimates, as-reported fundamentals, filing availability timestamps, and survivorship-safe universe membership. V5.4 accumulates PIT data prospectively instead of fabricating history from today's estimates."
    }
