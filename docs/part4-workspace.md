# Part 4: Workspace, Documents, Uploads, and Comments

## User Story

As a logged-in study group member, I want to use a shared workspace where I can upload study materials, search the documents my group has shared, preview uploaded files, and leave comments beside a document so that my group can keep resources and discussion in one place.

## Implemented Features

- Shared workspace entry from the Dashboard through the `Shared workspace` card.
- Group discussion entry from the Dashboard through the `Group discussion` card.
- Authenticated document upload with title, document type, and file content.
- Dynamic document list loaded from the backend.
- Server-side document search by title, file name, or document type.
- Document type labels for organizing uploaded materials.
- Authenticated file preview endpoint for uploaded files.
- In-page preview modal for images and PDFs.
- Comments attached to individual documents.
- Dynamic comment list with author name and timestamp.

## Backend API

All workspace routes require the existing StudySync session cookie.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/workspace/documents` | List shared workspace documents. Supports `?search=`. |
| `POST` | `/api/workspace/documents` | Upload a document using multipart form data. |
| `GET` | `/api/workspace/documents/{document_id}/file` | Preview or open the uploaded file. |
| `GET` | `/api/workspace/documents/{document_id}/comments` | List comments for a document. |
| `POST` | `/api/workspace/documents/{document_id}/comments` | Add a comment to a document. |

## Frontend Flow

1. Log in.
2. Open the Dashboard.
3. Click `Shared workspace`.
4. Upload a document with a title, type, and file.
5. Search for the document by title, file name, or type.
6. Click the document to preview it in a modal.
7. Click `Group discussion`.
8. Select a document.
9. Use `Preview file` if needed.
10. Add a comment and confirm it appears in the comment list.

## Testing

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

## Current Integration Note

This module currently uses a default workspace with `group_id = 1` because the group membership module is not integrated yet. After the group creation and membership module is merged, this should be connected to the current user's real study group workspace.
