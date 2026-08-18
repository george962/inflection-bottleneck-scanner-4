from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SecurityNormalization:
    ticker: str
    trading_currency: str | None
    financial_currency: str | None
    fx_financial_to_trading: float | None
    underlying_shares_per_traded_share: float
    resolved: bool
    reason: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def convert_total_financial_amount(self, value: float | None) -> float | None:
        if value is None or not self.resolved or self.fx_financial_to_trading is None:
            return None
        return float(value) * self.fx_financial_to_trading

    def convert_per_underlying_share(self, value: float | None) -> float | None:
        if value is None or not self.resolved or self.fx_financial_to_trading is None:
            return None
        return float(value) * self.fx_financial_to_trading * self.underlying_shares_per_traded_share


def build_security_normalization(
    ticker: str,
    profile: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    fx_loader: Callable[[str, str], float | None] | None = None,
    policy: dict[str, Any] | None = None,
) -> SecurityNormalization:
    overrides = overrides or {}
    policy = policy or {}
    t = ticker.upper()
    trading = _currency(profile.get("currency"))
    financial = _currency(profile.get("financial_currency")) or trading
    override = overrides.get(t, {}) if isinstance(overrides.get(t, {}), dict) else {}
    ratio = _positive(override.get("underlying_shares_per_traded_share")) or 1.0

    if not trading or not financial:
        return SecurityNormalization(t, trading, financial, None, ratio, False, "Trading or financial currency is unavailable.", "metadata")

    if trading == financial:
        return SecurityNormalization(t, trading, financial, 1.0, ratio, True, "Trading and financial currencies match.", "same_currency")

    require_ratio = bool(policy.get("require_explicit_adr_ratio_when_currencies_differ", True))
    if require_ratio and "underlying_shares_per_traded_share" not in override:
        return SecurityNormalization(
            t, trading, financial, None, ratio, False,
            "Financial and trading currencies differ and no explicit share/ADR ratio override exists.",
            "override_required",
        )

    explicit_fx = _positive(override.get("financial_to_trading_fx"))
    fx = explicit_fx
    source = "override" if explicit_fx else "market_fx"
    if fx is None and fx_loader is not None:
        try:
            fx = _positive(fx_loader(financial, trading))
        except Exception:
            fx = None
    if fx is None:
        return SecurityNormalization(t, trading, financial, None, ratio, False, "FX conversion is unavailable for the reporting/trading currency pair.", source)

    return SecurityNormalization(t, trading, financial, fx, ratio, True, "Currency and security units reconciled.", source)


def _currency(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def _positive(value: Any) -> float | None:
    try:
        x = float(value)
        return x if x > 0 else None
    except Exception:
        return None
