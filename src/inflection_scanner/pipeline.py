from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .assessment import build_assessment
from .config import Settings
from .db import Database
from .features.estimates import compute_estimate_features
from .features.fundamentals import compute_fundamental_features
from .features.market import compute_market_features
from .providers.yahoo import YahooProvider
from .report import write_reports
from .scoring import data_quality, score_snapshot


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_json_value(v) for v in value]
    try:
        import numpy as np
        import pandas as pd
        if value is pd.NA:
            return None
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return None if not np.isfinite(value) else float(value)
    except Exception:
        pass
    if isinstance(value, float):
        import math
        return value if math.isfinite(value) else None
    return value


def scan_one(
    ticker: str,
    themes: list[str],
    provider: YahooProvider,
    benchmark_history,
    settings: Settings,
    seed_features: dict[str, Any] | None = None,
    source: str = "watchlist",
) -> dict[str, Any]:
    asof = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        history = provider.history(ticker, settings.price_period)
        if history.empty:
            raise RuntimeError("No usable price history returned by Yahoo.")

        profile = provider.profile(ticker)
        financials = provider.quarterly_financials(ticker)
        analyst = provider.analyst_data(ticker)

        market = compute_market_features(history, benchmark_history)
        fundamental = compute_fundamental_features(
            financials["income"],
            financials["cashflow"],
            financials["balance"],
        )
        estimates = compute_estimate_features(analyst)

        features = {
            **market,
            **fundamental,
            **estimates,
            **(seed_features or {}),
        }

        scores = score_snapshot(
            features,
            profile,
            settings.weights,
            extension_penalty_max=settings.extension_penalty_max,
        )

        snapshot = {
            "asof": asof,
            "ticker": ticker,
            "company": profile.get("company") or ticker,
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "themes": themes,
            "source": source,
            "profile": profile,
            "features": features,
            "scores": scores,
            "data_quality": data_quality(features),
            "assessment": {},
            "error": None,
        }
        return _clean_json_value(snapshot)
    except Exception as exc:
        return {
            "asof": asof,
            "ticker": ticker,
            "company": ticker,
            "sector": None,
            "industry": None,
            "themes": themes,
            "source": source,
            "profile": {},
            "features": seed_features or {},
            "scores": {},
            "data_quality": 0.0,
            "assessment": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def assess_snapshot(
    snap: dict[str, Any],
    previous: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    if snap.get("error"):
        return snap

    snap["assessment"] = build_assessment(
        snap,
        previous,
        minimum_actionable_quality=settings.minimum_actionable_quality,
        watch_threshold=settings.score_thresholds.get("watch", 58),
        deep_research_threshold=settings.score_thresholds.get("deep_research", 66),
        candidate_threshold=settings.score_thresholds.get("candidate", 74),
    )
    return _clean_json_value(snap)


def run_scan(
    universe: list[dict[str, Any]],
    settings: Settings,
    top_n: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provider = YahooProvider(pause_seconds=settings.request_pause_seconds)
    db = Database(settings.db_path)
    run_id = db.start_run(len(universe))

    benchmark_history = provider.history(settings.benchmark, settings.price_period)
    snapshots: list[dict[str, Any]] = []

    for item in universe:
        ticker = item["ticker"]
        previous = db.latest_snapshot_before_run(ticker, run_id)

        snap = scan_one(
            ticker=ticker,
            themes=item.get("themes", []),
            provider=provider,
            benchmark_history=benchmark_history,
            settings=settings,
            source="watchlist",
        )
        snap = assess_snapshot(snap, previous, settings)

        db.save_snapshot(run_id, snap)
        snapshots.append(snap)

    success_count = sum(not s.get("error") for s in snapshots)
    failure_count = len(snapshots) - success_count
    db.finish_run(run_id, success_count, failure_count)

    paths = write_reports(
        snapshots,
        settings.output_dir,
        top_n=top_n or settings.report_top_n,
    )
    db.close()
    return snapshots, {"run_id": run_id, "paths": paths}
