# Upgrade from v0.2

The simplest upgrade is to replace the project files with v0.3 but keep the
existing `data/scanner.db`.

The SQLite migration is additive.

## Important

The old Streamlit dashboard is easy to leave running in a terminal.

Stop it first with:

```bash
Ctrl+C
```

Then replace/update the project files and run:

```bash
cd /Users/georgejiang/Finance/Trend/inflection-bottleneck-scanner
source .venv/bin/activate

pip install -e ".[dashboard,dev]"

inflection-scanner doctor --network
pytest -q

# Small test first
inflection-scanner discover --max-universe 500 --deep 30 --top 15

# Full discovery
inflection-scanner discover --deep 90 --top 30

streamlit run dashboard/app.py
```

The dashboard title should now be:

```text
Broad Stock Discovery Engine
```

If it still says:

```text
Inflection & Bottleneck Scanner
```

you are still running the old dashboard file/process.
