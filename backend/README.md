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

## Database Mode

The backend chooses its database from environment variables at startup:

- Normal desktop/local mode defaults to SQLite at `backend/data/studysync.sqlite3`.
- OCI deployment mode uses Oracle ATP/ADB when `STUDYSYNC_RUNTIME_ENV=oci`,
  `STUDYSYNC_OCI_HOST=1`, `OCI_DEPLOYED=1`, or Oracle Cloud host metadata is detected.
- Desktop Oracle debug mode uses Oracle ATP/ADB with `STUDYSYNC_DB_DEBUG=atp` or
  `STUDYSYNC_USE_ORACLE_ADB=1`; keep the ATP network ACL limited to the desktop IP.

You can override auto-detection with `STUDYSYNC_DB_BACKEND=sqlite` or
`STUDYSYNC_DB_BACKEND=oracle`.

Oracle ATP/ADB requires:

```sh
export STUDYSYNC_ORACLE_USER=ADMIN
export STUDYSYNC_ORACLE_PASSWORD='...'
export STUDYSYNC_ORACLE_DSN='..._tp'
export STUDYSYNC_ORACLE_WALLET_DIR=/path/to/unzipped/wallet
export STUDYSYNC_ORACLE_WALLET_PASSWORD='...'
```

The OCI production service should set `STUDYSYNC_RUNTIME_ENV=oci` and the same Oracle
variables for the small ATP database. App startup runs `init_db()`, so the required
tables and indexes are created automatically before requests are served.
