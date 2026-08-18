from __future__ import annotations

import re
from typing import Any

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(authorization|api[_-]?key|token|secret|password|cookie|user-agent)\s*[:=]\s*([^,;\n]+)"
)
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def sanitize_text(value: Any, max_chars: int = 500) -> str:
    text = str(value or "")
    text = text.replace("\r", " ").replace("\n", " ")
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def safe_exception(exc: BaseException, context: str = "request failed") -> str:
    # Do not serialize the raw exception because requests/urllib may include
    # HTTP header values, URLs containing secrets, or environment-derived data.
    return f"{context}: {exc.__class__.__name__}"
