.RECIPEPREFIX := >

.PHONY: install run lint format test build check

install:
>uv sync --locked

run:
>uv run database

lint:
>uv run ruff check .
>uv run ruff format --check .

format:
>uv run ruff check . --fix
>uv run ruff format .

test:
>uv run python tests/test_database.py

build:
>uv build
>uvx twine check dist/*

check: lint test build