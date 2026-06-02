# Part 4: Workspace, Documents, Uploads, Comments, and AI Q&A

## User Story

As a logged-in study group member, I want to use a shared workspace where I can upload study materials, search the documents my group has shared, preview uploaded files, leave comments beside a document, and ask AI-assisted questions about indexed group documents so that my group can keep resources and discussion in one place.

## Implemented Features

- Shared workspace entry from the Dashboard through the `Shared workspace` card.
- Group discussion entry from the Dashboard through the `Group discussion` card.
- Authenticated document upload with title, document type, and file content.
- Dynamic document list loaded from the backend.
- Server-side document search by title, file name, or document type.
- Document type labels for organizing uploaded materials.
- Supported uploads for PDF, PNG, JPG, TXT, and MD files.
- Authenticated file preview endpoint for uploaded files.
- In-page preview modal for images, PDFs, text files, and Markdown files.
- Comments attached to individual documents.
- Dynamic comment list with author name and timestamp.
- Background document indexing for AI-assisted Q&A.
- AI-generated document summaries for indexed documents.
- AI-assisted question answering over ready indexed group documents.

## Backend API

All workspace routes require the existing StudySync session cookie and group membership.

| Method   | Route                                                     | Purpose                                                                   |
| -------- | --------------------------------------------------------- | ------------------------------------------------------------------------- |
| `GET`    | `/api/groups/{group_id}/documents`                        | List shared group documents. Supports `?search=`.                         |
| `POST`   | `/api/groups/{group_id}/documents`                        | Upload a document using multipart form data.                              |
| `DELETE` | `/api/groups/{group_id}/documents/{document_id}`          | Delete a document when the current user is the file owner or group owner. |
| `GET`    | `/api/groups/{group_id}/documents/{document_id}/file`     | Preview or open the uploaded file.                                        |
| `GET`    | `/api/groups/{group_id}/documents/{document_id}/comments` | List comments for a document.                                             |
| `POST`  | `/api/groups/{group_id}/documents/{document_id}/comments` | Add a comment to a document.                                              |
| `POST`   | `/api/groups/{group_id}/qa`                               | Ask an AI-assisted question about ready indexed group documents.          |

## AI Document Q&A

Uploaded documents will be saved with an `Indexing` status, then they will be indexed for AI assisted Q&A in a background task. The frontend continuously refreshes indexing documents, so a document can appear in the workspace before it is ready for Q&A.

Documents use these indexing states:

- `Indexing`: the upload succeeded and Q&A indexing is still running.
- `Ready`: the document can be used by the group Q&A feature.
- `Q&A failed`: the upload remains available, but the document could not be indexed for AI Q&A.

The Q&A endpoint only answers questions if the group has one or more ready indexed document and an OpenAI vector store is available for the group. If no indexed documents are ready yet, the API returns:

```text
No indexed documents are ready for Q&A yet.
```

If the AI response does not contain an answer, the API returns this fallback:

```text
The shared documents do not include enough information to answer that.
```

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
11. Wait for uploaded documents to show `Ready`, then ask a question about the group's shared files.

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

This module uses the user's study groups. Workspace document, comment, preview, delete, and Q&A routes all check that the signed-in user belongs to the target group.
