import pytest
from inflection_scanner.security_normalization import build_security_normalization


def test_same_currency_resolves_without_override():
    n=build_security_normalization("AAPL",{"currency":"USD","financial_currency":"USD"})
    assert n.resolved
    assert n.fx_financial_to_trading==1.0
    assert n.underlying_shares_per_traded_share==1.0


def test_cross_currency_requires_explicit_ratio():
    n=build_security_normalization("TSM",{"currency":"USD","financial_currency":"TWD"},overrides={},fx_loader=lambda a,b:.031)
    assert not n.resolved
    assert "ratio" in n.reason.lower()


def test_adr_override_and_fx_resolve():
    n=build_security_normalization("TSM",{"currency":"USD","financial_currency":"TWD"},overrides={"TSM":{"underlying_shares_per_traded_share":5}},fx_loader=lambda a,b:.031)
    assert n.resolved
    assert n.convert_per_underlying_share(200)==31.0
    assert n.convert_total_financial_amount(1000)==31.0


def test_explicit_fx_override_works_without_loader():
    n=build_security_normalization("XYZ",{"currency":"USD","financial_currency":"EUR"},overrides={"XYZ":{"underlying_shares_per_traded_share":2,"financial_to_trading_fx":1.1}})
    assert n.resolved
    assert n.convert_per_underlying_share(3)==pytest.approx(6.6)
