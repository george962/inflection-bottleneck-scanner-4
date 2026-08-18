from __future__ import annotations

import hashlib
from pathlib import Path


def source_hash(root: str | Path | None = None) -> str:
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    files = sorted((base / "src").rglob("*.py")) + sorted((base / "config").glob("*.json"))
    h = hashlib.sha256()
    for path in files:
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(base).as_posix().encode("utf-8")
        h.update(rel); h.update(b"\0"); h.update(path.read_bytes()); h.update(b"\0")
    return h.hexdigest()[:16]
