import json
from pathlib import Path
import subprocess
import sys


def test_publish_validator_rejects_empty_dataset(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    (published / "latest_research.json").write_text("[]", encoding="utf-8")
    (published / "metadata.json").write_text(
        json.dumps({"discovery_run": {"research_selection": {"core_candidates": 0}}}),
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_publish.py"
    result = subprocess.run(
        [sys.executable, str(script), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "research produced only 0 report" in result.stdout


def test_publish_validator_accepts_well_formed_sec_ready_report(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    report = {
        "ticker": "TEST",
        "conviction": {},
        "valuation": {},
        "trust": {"evidence_ready": True},
        "metrics": {},
        "sec_status": {"state": "READY"},
    }
    (published / "latest_research.json").write_text(json.dumps([report]), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_publish.py"
    result = subprocess.run(
        [sys.executable, str(script), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "SEC evidence ready for 1/1" in result.stdout


def test_publish_validator_rejects_systemic_sec_failure(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    reports = [
        {
            "ticker": f"T{i}",
            "conviction": {},
            "valuation": {},
            "trust": {"evidence_ready": False},
            "metrics": {},
            "sec_status": {"state": "UNAVAILABLE", "errors": ["secret missing"]},
        }
        for i in range(5)
    ]
    (published / "latest_research.json").write_text(json.dumps(reports), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_publish.py"
    result = subprocess.run(
        [sys.executable, str(script), "--published", str(published), "--min-reports", "5"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "SEC evidence is ready for only" in result.stdout
