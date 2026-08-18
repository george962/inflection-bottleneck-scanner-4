.PHONY: install test validate research dashboard
install:
	python -m pip install -e ".[dashboard,dev,llm]"
test:
	python -m compileall -q src dashboard tests
	pytest -q
validate:
	python scripts/validate_publish.py --published published --min-reports 1
research:
	inflection-scanner research --deep 180 --research-count 24 --top 30
dashboard:
	streamlit run dashboard/app.py
