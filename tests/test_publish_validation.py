from pathlib import Path
import json
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
    assert "Refusing to treat this as a successful publish" in result.stdout


def test_publish_validator_accepts_well_formed_report(tmp_path: Path):
    published = tmp_path / "published"
    published.mkdir()
    report = {
        "ticker": "TEST",
        "conviction": {},
        "valuation": {},
        "trust": {},
        "metrics": {},
    }
    (published / "latest_research.json").write_text(json.dumps([report]), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_publish.py"
    result = subprocess.run(
        [sys.executable, str(script), "--published", str(published), "--min-reports", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
