.PHONY: install test run eval clean

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest

run:
	uvicorn app.main:app --reload

eval:
	python evals/run_eval.py

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -path ./.venv -prune -o -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -path ./.venv -prune -o -type f -name "*.pyc" -delete
	rm -f evals/results.json agentops_memory.db
