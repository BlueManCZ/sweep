.PHONY: test black black-fix

test:
	uv run pytest --tb=short -q

black:
	uv run black --check src/ tests/

black-fix:
	uv run black src/ tests/
