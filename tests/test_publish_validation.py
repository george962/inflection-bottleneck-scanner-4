import json
from pathlib import Path
import subprocess
import sys


def _script() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "validate_publish.py"


def test_publish_validator_rejects_empty_dataset(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    (published / "latest_research.json").write_text("[]", encoding="utf-8")
    (published / "metadata.json").write_text(
        json.dumps({"discovery_run": {"research_selection": {"core_candidates": 0}}}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_script()), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "research produced only 0 report" in result.stdout


def test_publish_validator_accepts_well_formed_report_without_sec(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    report = {
        "ticker": "TEST",
        "conviction": {},
        "valuation": {},
        "trust": {},
        "metrics": {},
        "sec_status": {"state": "UNAVAILABLE", "documents_cached": 0},
    }
    (published / "latest_research.json").write_text(json.dumps([report]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_script()), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "SEC is not required" in result.stdout


def test_publish_validator_rejects_malformed_report_even_when_sec_optional(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    (published / "latest_research.json").write_text(json.dumps([{"ticker": "TEST"}]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_script()), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "malformed report" in result.stdout
