# StudySync

StudySync is a CS 35L study group collaboration app. It includes UCLA-email
authentication, profile setup, study group matching, join request workflows, and
shared group workspaces for uploading, searching, previewing, discussing, and
asking AI-assisted questions about study materials.

## Local Prerequisites

- Python 3.11 or newer
- `uv` for backend dependency management
- Node.js and npm for the Vite/React frontend

Run the backend and frontend in two separate terminals from the repository root.

## Run Locally

### 1. Start The Backend API

```sh
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API should answer:

```sh
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

On startup, FastAPI runs `init_db()`. Local development uses SQLite by default,
creates `backend/data/studysync.sqlite3` if it does not exist, creates or
migrates the required tables, and seeds mock course/group workspace data.
Uploaded files are stored under `backend/data/uploads/`.

### 2. Start The Frontend

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies frontend `/api` requests to
`http://127.0.0.1:8000`, as configured in `frontend/vite.config.ts`, so
`VITE_API_BASE_URL` is not required for the normal local setup. The backend CORS
configuration currently allows the default Vite origins on port `5173`, so keep
that port unless you also update the backend CORS settings or continue to route
API calls through Vite's proxy.

## Local Configuration

The app runs locally without production secrets. These environment variables are
useful when you need to override defaults:

| Variable | Used by | Local behavior |
| --- | --- | --- |
| `STUDYSYNC_SECRET_KEY` | backend sessions | Defaults to a development key. Set this if you want stable local cookies across secret changes. |
| `STUDYSYNC_DB_PATH` | backend database | Defaults to `backend/data/studysync.sqlite3`. |
| `STUDYSYNC_DB_BACKEND` | backend database | Defaults to `auto`, which selects SQLite locally. Use `sqlite` to force local SQLite. |
| `STUDYSYNC_FRONTEND_URL` | backend email links | Defaults to `http://localhost:5173`. Set to `http://127.0.0.1:5173` if you use that host in links. |
| `RESEND_API_KEY` | backend email | Optional. If unset, verification, reset, and group application emails are skipped in logs. |
| `RESEND_FROM_EMAIL` | backend email | Optional sender address for Resend. |
| `OPENAI_API_KEY` | document Q&A | Optional. If unset, uploads still work, but OpenAI indexing/Q&A is unavailable. |
| `OPENAI_DOC_QA_ENABLED` | document Q&A | Optional. Set to `0` or `false` to disable document Q&A even when an API key is present. |
| `OPENAI_DOC_QA_MODEL` | document Q&A | Optional model override. Defaults in `backend/app/config.py`. |
| `VITE_API_BASE_URL` | frontend API client | Leave unset for the Vite proxy. Set only if the browser should call the API directly. |

Oracle Autonomous Database support is present for OCI production or explicit
debugging, but it is not needed for local development. The backend switches to
Oracle only when environment variables such as `STUDYSYNC_RUNTIME_ENV=oci`,
`STUDYSYNC_DB_DEBUG=atp`, `STUDYSYNC_USE_ORACLE_ADB=1`, or
`STUDYSYNC_DB_BACKEND=oracle` are set. See
[backend/README.md](backend/README.md#database-mode) for the Oracle-specific
variables.

To reset local data, stop the backend and remove the local SQLite database file
and any uploaded files under `backend/data/`. The next backend startup will
recreate the schema and seed data.

## Run Tests And Checks

Backend:

```sh
cd backend
uv run pytest
```

Frontend:

```sh
cd frontend
npm test
npm run build
```

Playwright end-to-end:

```sh
cd backend
uv sync --dev
cd ../frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

The Playwright config starts the FastAPI backend on `127.0.0.1:8000` and the
Vite frontend on `127.0.0.1:5173` automatically. Keep those ports free before
running the suite so the configured test servers can start cleanly. The e2e
suite uses SQLite at `backend/data/studysync-e2e.sqlite3` and disables external
email and document Q&A calls.

## Architecture

### Local Runtime Topology

This diagram shows the local development processes and the boundaries between
them: the browser loads the React app from Vite, Vite proxies API calls to the
FastAPI server, and the backend owns local persistence, uploaded files, and
optional external services.

```mermaid
flowchart LR
    Browser["Browser\nhttp://127.0.0.1:5173"] --> Vite["Vite dev server\nfrontend/ React + Ant Design"]
    Vite -->|serves SPA| Browser
    Vite -->|proxy /api| FastAPI["Uvicorn + FastAPI\nbackend/app/main.py\nhttp://127.0.0.1:8000"]
    FastAPI --> SQLite["SQLite database\nbackend/data/studysync.sqlite3"]
    FastAPI --> Uploads["Uploaded files\nbackend/data/uploads/"]
    FastAPI -. optional .-> Resend["Resend email API"]
    FastAPI -. optional .-> OpenAI["OpenAI Files, Vector Stores,\nand Responses APIs"]
    FastAPI -. production/debug only .-> Oracle["Oracle ATP/ADB"]
```
### UML Sequence Diagram
This diagram traces a new user through the full flow from account creation to group collaboration. It covers five phases: signup with UCLA email validation, email verification, profile setup with course enrollment and study preferences, group discovery with preference-based filtering and join requests, and workspace collaboration including document upload, AI summary, commenting, and AI-powered Q&A over group materials. Synchronous calls use solid arrows, asynchronous background tasks use open arrows, and return
values use dashed lines.

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant BE as FastAPI Backend
    participant DB as SQLite DB
    participant Email as Email Service (SMTP)
    participant OpenAI as OpenAI API

    %% Phase 1: Sign Up
    Note over User, OpenAI: Phase 1 — Sign Up

    User->>FE: Fill signup form (name, UCLA email, password)
    FE->>BE: POST /api/auth/signup

    BE->>BE: Validate UCLA email domain
    BE->>BE: Hash password (bcrypt)

    alt Email already registered
        BE--)FE: 409 Conflict
        FE--)User: "Account already exists"
    else New user
        BE->>DB: INSERT INTO users (email_verified=0)
        BE->>DB: INSERT INTO email_verification_tokens
        BE->>Email: Send verification email with token
        BE--)FE: AuthResponse + Set-Cookie (studysync_session)
        FE--)User: Redirect to /dashboard (unverified)
    end


    %% Phase 2: Email Verification 
    Note over User, OpenAI: Phase 2 — Email Verification

    User->>FE: Click verification link from email
    FE->>BE: POST /api/auth/email-verification/confirm {token}

    BE->>DB: SELECT from email_verification_tokens

    alt Token expired or already used
        DB--)BE: No matching row
        BE--)FE: 400 Bad Request
        FE--)User: "Link is invalid or expired"
    else Token valid
        DB--)BE: token row (user_id)
        BE->>DB: UPDATE users SET email_verified=1
        BE->>DB: UPDATE token SET used_at=NOW
        BE--)FE: AuthResponse + new session cookie
        FE--)User: ProfileGate → redirect to /profile/setup
    end


    %% Phase 3: Profile Setup 
 
    Note over User, OpenAI: Phase 3 — Profile Setup

    User->>FE: Select courses, study goals, pace, group size pref
    FE->>BE: PUT /api/profile/me {courses: [...]}
    BE->>BE: Validate payload (normalize course codes, enums)

    loop For each course in payload
        BE->>DB: INSERT OR IGNORE INTO courses
        BE->>DB: SELECT course id
        BE->>DB: INSERT INTO user_course (goals, pace, size_pref)
    end

    BE--)FE: ProfileResponse {courses, has_basic_profile: true}
    FE--)User: ProfileGate passes → redirect to /dashboard

    %% Phase 4: Group Matching & Joining 
   
    Note over User, OpenAI: Phase 4 — Group Matching & Joining

    User->>FE: Open GroupMatchingModule, select a course
    FE->>BE: GET /api/matching/groups?user_course_id=X
    BE->>DB: SELECT user_course WHERE id=X
    BE->>DB: SELECT groups + member counts for this course

    loop For each group
        BE->>DB: SELECT member user_course rows (goals, pace)
        BE->>BE: Compute avg pace, top goals, group size
    end

    opt User applied filters (goals, pace, or size)
        BE->>BE: Filter out non-matching groups
    end

    BE--)FE: GroupDirectoryResponse[]
    FE--)User: Display matched groups

    User->>FE: Click "Join" on a group
    FE->>BE: POST /api/groups/{id}/join

    alt Already a member
        BE--)FE: 409 "Already in this group"
    else Already has pending request for this course
        BE--)FE: 409 "Already have a pending application"
    else Eligible
        BE->>DB: INSERT INTO join_requests (status=pending)

        opt Group owner has notifications enabled
            BE->>Email: Notify owner of new application
        end

        BE--)FE: JoinRequestResponse {status: pending}
        FE--)User: Show "Request Pending" badge
    end


    %% Phase 5: Workspace Collaboration & AI
    Note over User, OpenAI: Phase 5 — Workspace Collaboration & AI

    User->>FE: Upload document (PDF, PNG, JPG, TXT, MD)
    FE->>BE: POST /api/groups/{id}/documents (multipart form)
    BE->>BE: Validate membership, file type, storage limit
    BE->>DB: INSERT INTO documents (index_status='indexing')
    BE--)FE: DocumentResponse

    BE-)OpenAI: Background: index document into vector store
    OpenAI--)BE: IndexedDocument (file_id, status)
    opt index status = ready
        BE-)OpenAI: Background: generate AI summary
        OpenAI--)BE: Summary text
    end
    BE->>DB: UPDATE documents SET index_status='ready', ai_summary=...

    User->>FE: Add comment on document
    FE->>BE: POST /api/groups/{id}/documents/{id}/comments
    BE->>DB: INSERT INTO comments
    BE--)FE: CommentResponse

    User->>FE: Ask AI a question about group documents
    FE->>BE: POST /api/groups/{id}/qa {question}
    BE->>DB: SELECT indexed documents for group

    alt No indexed documents ready
        BE--)FE: 409 "No indexed documents ready"
    else Documents available
        BE->>OpenAI: Query vector store with question
        OpenAI--)BE: Answer + source snippets
        BE--)FE: DocumentQAResponse {answer, sources}
        FE--)User: Display AI answer with cited sources
    end
```

### Frontend And API Module Map

This diagram maps the main React modules to the FastAPI routers they call. It is
useful when tracing a user workflow from a page or dashboard module, through
`frontend/src/api.ts`, into the backend router and support modules that handle
sessions, persistence, email, and document Q&A.

```mermaid
flowchart TB
    subgraph Frontend["frontend/src"]
        Router["App.tsx\nReact Router routes"]
        Providers["AuthProvider + ProfileProvider"]
        Guards["ProtectedRoute + ProfileGate"]
        AuthPages["Login, Signup,\nVerify, Reset pages"]
        Dashboard["DashboardPage"]
        ProfileModule["ProfilePage + ProfileSetupModule"]
        MatchingModule["GroupMatchingModule"]
        WorkspaceModule["WorkspaceModule"]
        ApiClient["api.ts\nfetch with credentials"]
    end

    subgraph Backend["backend/app"]
        Main["main.py\nFastAPI app, CORS, lifespan init_db"]
        AuthRouter["auth.py\n/api/auth"]
        ProfileRouter["profile.py\n/api/profile"]
        MatchingRouter["matching.py\n/api/matching"]
        GroupsRouter["groups.py\n/api/groups"]
        Security["security.py\nsigned session cookie"]
        DB["db.py\nSQLite/Oracle connection,\nschema, seeds"]
        Email["email.py\noptional Resend delivery"]
        DocumentQA["openai_document_qa.py\noptional document indexing and Q&A"]
    end

    Router --> Providers --> Guards
    Guards --> AuthPages
    Guards --> Dashboard
    Dashboard --> ProfileModule
    Dashboard --> MatchingModule
    Dashboard --> WorkspaceModule
    AuthPages --> ApiClient
    ProfileModule --> ApiClient
    MatchingModule --> ApiClient
    WorkspaceModule --> ApiClient
    ApiClient -->|/api/auth| AuthRouter
    ApiClient -->|/api/profile| ProfileRouter
    ApiClient -->|/api/matching| MatchingRouter
    ApiClient -->|/api/groups| GroupsRouter
    Main --> AuthRouter
    Main --> ProfileRouter
    Main --> MatchingRouter
    Main --> GroupsRouter
    AuthRouter --> Security
    AuthRouter --> Email
    AuthRouter --> DB
    ProfileRouter --> DB
    MatchingRouter --> DB
    GroupsRouter --> DB
    GroupsRouter --> Email
    GroupsRouter --> DocumentQA
```

### Core Data And Workspace Flow

This diagram summarizes the core local data model and the workspace document
flow. It shows how users, course preferences, groups, membership applications,
uploaded documents, comments, local files, and optional OpenAI vector-store IDs
relate to each other.

```mermaid
flowchart TB
    Users["users\naccounts, verification state,\nemail notification preference"]
    Tokens["email_verification_tokens\npassword_reset_tokens"]
    Courses["courses\ncourse code, quarter, lecture"]
    UserCourse["user_course\nper-user course profile,\nstudy goals, pace, group size"]
    Groups["groups\ncourse group, owner,\noptional openai_vector_store_id"]
    Members["group_members\ncurrent group roster"]
    Requests["join_requests\npending, approved, rejected,\nwithdrawn applications"]
    Documents["documents\nmetadata, stored path,\nOpenAI file ids, index status,\nAI summary"]
    Comments["comments\ndocument discussion"]
    UploadFiles["backend/data/uploads/group-N\nPDF, PNG, JPG, TXT, MD files"]
    VectorStore["OpenAI vector store\nexternal index used for group Q&A"]

    Users --> Tokens
    Users --> UserCourse
    Courses --> UserCourse
    Courses --> Groups
    Users -->|owner| Groups
    Groups --> Members
    Users --> Members
    Groups --> Requests
    Users --> Requests
    Groups --> Documents
    Users -->|uploader| Documents
    Documents --> Comments
    Users -->|author| Comments
    Documents --> UploadFiles
    Groups -. stores vector store id .-> VectorStore
    Documents -. stores file/vector file ids .-> VectorStore
```

## Feature Notes

- Authentication stores an HTTP-only signed `studysync_session` cookie.
- Signup requires a UCLA email address. If `RESEND_API_KEY` is not configured,
  email delivery is skipped, but local account creation still succeeds.
- The profile flow stores one or more course preferences in `user_course`.
- Matching reads profile preferences and existing group membership/request state.
- Group workspaces allow supported files up to 50 MB each, with a 2 GB per-group
  storage cap.
- Document Q&A is optional. Without OpenAI configuration, document upload and
  comments still work, but indexing/Q&A responses report that the feature is not
  available or that no indexed documents are ready.

## Additional Documentation

- [Backend database mode](backend/README.md#database-mode)
- [Part 4 workspace module](docs/part4-workspace.md)

## AI Assistance Disclosure

Generative AI was used to help plan, debug, review, and suggest code.
Approximately 80% of the code was AI-assisted, while the remaining 20% was
written directly. All AI-assisted changes were reviewed, tested, and adapted
for the StudySync codebase, and responsibility is taken for the final code.
