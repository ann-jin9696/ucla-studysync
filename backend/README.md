# StudySync Backend

This backend uses `uv` for Python dependency and environment management.

## Setup

```sh
uv sync --dev
```

## Email Configuration

StudySync sends verification, password recovery, and group application notification
emails through Resend when `RESEND_API_KEY` is available in the environment.

Optional email settings:

```sh
export RESEND_FROM_EMAIL="StudySync <noreply@studysync.bruinapps.com>"
export STUDYSYNC_FRONTEND_URL="http://localhost:5173"
```

## Run Tests

```sh
uv run pytest
```

## Start The API

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
