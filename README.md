# StudySync

StudySync is a study group collaboration app for CS 35L. The current app includes authentication and shared group workspaces for uploading, searching, previewing, commenting on, and asking AI-assisted questions about study materials.

## Local Setup

Run the backend and frontend in two separate terminals.

### Backend

```sh
cd backend
uv sync --dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend health check:

```sh
curl http://127.0.0.1:8000/api/health
```

### Frontend

```sh
cd frontend
npm install
npm.cmd run dev -- --host 127.0.0.1 --port 3000
```

Then open:

```text
http://127.0.0.1:3000
```

Note: On some Windows machines, port `5173` may be reserved. Port `3000` works with the current local setup.

## Run Tests

Backend:

```sh
cd backend
uv run pytest
```

## Database Selection

Local desktop runs use SQLite by default. OCI deployments and desktop ATP debug runs
can use Oracle Autonomous Database by setting backend environment variables; see
[backend/README.md](backend/README.md#database-mode).

Frontend:

```sh
cd frontend
npm.cmd test
npm.cmd run build
```

## Part 4 Workspace Module

The Part 4 workspace module lets logged-in users:

- upload documents,
- search shared documents,
- preview uploaded images, PDFs, text files, and Markdown files,
- select a document for discussion,
- add and view comments attached to a document,
- ask AI-assisted questions about indexed group documents.

More details are in [docs/part4-workspace.md](docs/part4-workspace.md).
