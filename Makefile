.PHONY: run test lint docs check

run:
	PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8000

test:
	pytest

lint:
	flake8 src tests

docs:
	PYTHONPATH=src pdoc configurator domain application adapters -o docs

check: lint test
