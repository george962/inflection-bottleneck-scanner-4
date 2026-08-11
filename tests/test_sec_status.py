from inflection_scanner.providers.sec_research import CachedSecResearchProvider
from inflection_scanner.warehouse import ResearchWarehouse


def test_sec_provider_surfaces_missing_identity_instead_of_silent_empty(tmp_path):
    warehouse = ResearchWarehouse(tmp_path / "warehouse.db")
    provider = CachedSecResearchProvider(warehouse, user_agent="", offline=False)
    filings = provider.ensure_recent_documents("AAPL", ["10-K", "10-Q"], 4, 10000)
    status = provider.status_for("AAPL")
    warehouse.close()

    assert filings == []
    assert status["state"] == "UNAVAILABLE"
    assert status["errors"]
    assert "SEC_USER_AGENT" in status["errors"][0]
