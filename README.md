# StudySync

StudySync is a study group collaboration app for CS 35L. The current app includes authentication and a shared workspace module for uploading, searching, previewing, and commenting on study materials.

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
- preview uploaded images and PDFs,
- select a document for discussion,
- add and view comments attached to a document.

More details are in [docs/part4-workspace.md](docs/part4-workspace.md).
