.PHONY: setup doctor test research research-quick dashboard cache-status clean

setup:
	python3 -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip && pip install -e ".[dashboard,dev,llm]"

doctor:
	inflection-scanner doctor --network

test:
	pytest -q

research-quick:
	inflection-scanner research --max-universe 500 --deep 80 --research-count 10 --top 15

research:
	inflection-scanner research --deep 180 --research-count 24 --top 30

cache-status:
	inflection-scanner cache-status

dashboard:
	streamlit run dashboard/app.py

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
