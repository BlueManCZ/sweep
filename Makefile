.PHONY: test black black-fix build

test:
	uv run pytest --tb=short -q

black:
	uv run black --check src/ tests/

black-fix:
	uv run black src/ tests/

build:
	uv run pyinstaller sweep-gtk.spec --clean --noconfirm
