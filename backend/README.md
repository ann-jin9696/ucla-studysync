# StudySync Backend

This backend uses `uv` for Python dependency and environment management.

## Setup

```sh
uv sync --dev
```

## Run Tests

```sh
uv run pytest
```

## Start The API

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
