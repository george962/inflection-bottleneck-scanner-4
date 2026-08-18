from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
load_dotenv()

@dataclass(frozen=True)
class Settings:
    db_path: Path
    warehouse_path: Path
    output_dir: Path
    published_dir: Path
    config_path: Path
    benchmark: str
    price_period: str
    request_pause_seconds: float
    weights: dict[str, float]
    extension_penalty_max: float
    minimum_actionable_quality: float
    score_thresholds: dict[str, float]
    report_top_n: int
    discovery: dict[str, Any]
    cache_ttl_hours: dict[str, float]
    research: dict[str, Any]
    llm: dict[str, Any]

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _resolve_path(value: str, root: Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p

def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)

def load_settings(config_path: str | Path | None = None) -> Settings:
    root = project_root()
    raw_path = str(config_path) if config_path else os.getenv("SCANNER_CONFIG_PATH", "config/default.json")
    resolved = _resolve_path(raw_path, root)
    cfg = load_json(resolved)
    total = sum(float(v) for v in cfg["weights"].values())
    if abs(total - 100.0) > 1e-9:
        raise ValueError(f"Score weights must sum to 100, got {total}")
    return Settings(
        db_path=_resolve_path(os.getenv("SCANNER_DB_PATH", "data/scanner.db"), root),
        warehouse_path=_resolve_path(os.getenv("RESEARCH_WAREHOUSE_PATH", "data/warehouse.db"), root),
        output_dir=_resolve_path(os.getenv("SCANNER_OUTPUT_DIR", "outputs"), root),
        published_dir=_resolve_path(os.getenv("SCANNER_PUBLISHED_DIR", "published"), root),
        config_path=resolved,
        benchmark=str(cfg.get("benchmark", "SPY")).upper(),
        price_period=str(cfg.get("price_period", "2y")),
        request_pause_seconds=float(cfg.get("request_pause_seconds", 0.08)),
        weights={k: float(v) for k, v in cfg["weights"].items()},
        extension_penalty_max=float(cfg.get("extension_penalty_max", 22)),
        minimum_actionable_quality=float(cfg.get("minimum_actionable_quality", 60)),
        score_thresholds={k: float(v) for k, v in cfg.get("score_thresholds", {}).items()},
        report_top_n=int(cfg.get("report_top_n", 30)),
        discovery=dict(cfg.get("discovery", {})),
        cache_ttl_hours={k: float(v) for k, v in cfg.get("cache_ttl_hours", {}).items()},
        research=dict(cfg.get("research", {})),
        llm=dict(cfg.get("llm", {})),
    )

def load_universe(path: str | Path) -> list[dict[str, Any]]:
    root = project_root()
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    data = load_json(p)
    if not isinstance(data, list):
        raise ValueError("Universe JSON must be a list.")
    out, seen = [], set()
    for item in data:
        if isinstance(item, str):
            ticker, themes = item.upper().strip(), []
        else:
            ticker = str(item["ticker"]).upper().strip()
            themes = [str(x) for x in item.get("themes", [])]
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append({"ticker": ticker, "themes": themes})
    return out
