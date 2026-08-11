from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_track_record(warehouse, horizons_days: list[int] | None = None) -> dict[str, Any]:
    horizons = horizons_days or [90, 180, 365]
    reports = warehouse.list_research_reports(model_version="5.2")
    now = datetime.now(timezone.utc)

    observations = []
    for report in reports:
        asof = _parse_iso(str(report.get("asof") or ""))
        start_price = report.get("metrics", {}).get("price")
        action = report.get("conviction", {}).get("action")
        if asof is None or not start_price or not action:
            continue

        for horizon in horizons:
            target = asof + timedelta(days=int(horizon))
            if now < target:
                continue
            end_price = warehouse.price_near_date(report.get("ticker"), target.date().isoformat(), max_days=10)
            if end_price is None:
                continue
            realized = float(end_price) / float(start_price) - 1.0
            observations.append(
                {
                    "ticker": report.get("ticker"),
                    "asof": report.get("asof"),
                    "action": action,
                    "horizon_days": int(horizon),
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "realized_return": round(realized, 4),
                }
            )

    summaries = []
    actions = sorted({x["action"] for x in observations})
    for action in actions:
        for horizon in horizons:
            rows = [
                x for x in observations
                if x["action"] == action and x["horizon_days"] == int(horizon)
            ]
            if not rows:
                continue
            returns = [x["realized_return"] for x in rows]
            summaries.append(
                {
                    "action": action,
                    "horizon_days": int(horizon),
                    "count": len(rows),
                    "hit_rate": round(sum(x > 0 for x in returns) / len(returns), 4),
                    "average_return": round(sum(returns) / len(returns), 4),
                    "median_return": round(median(returns), 4),
                    "enough_history": len(rows) >= 10,
                }
            )

    return {
        "model_version": "5.2",
        "generated_at": now.isoformat(timespec="seconds"),
        "observations": observations,
        "summaries": summaries,
        "note": (
            "Track record uses realized forward prices from prior v5.2 research reports. "
            "A group is not treated as statistically informative until it has at least 10 observations."
        ),
    }
