from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


def load_config(path: str | Path = "config/default.json") -> dict[str, Any]:
    return load_json(path)


def load_security_overrides(path: str | Path = "config/security_overrides.json") -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def config_hash(cfg: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(cfg).encode("utf-8")).hexdigest()[:16]
