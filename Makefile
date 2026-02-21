.PHONY: lint test build clean

lint:
	uv run ruff check src/ tests/
	uv run black --check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run black src/ tests/

test:
	uv run pytest --cov=openclaw_todo --cov-report=term-missing -q

build: clean
	uv build
	@echo "Wheel built:"
	@ls -lh dist/*.whl

clean:
	rm -rf dist/ build/ src/*.egg-info
