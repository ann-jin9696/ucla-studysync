# Pull Request: Implement Part 4 Shared Workspace

## Suggested Title

Implement shared workspace uploads, search, previews, and comments

## Summary

This PR implements the Part 4 workspace module for StudySync. Logged-in users can upload study materials, search shared documents, preview uploaded images/PDFs, and leave comments attached to a selected document.

## What Changed

- Added authenticated workspace API routes.
- Added multipart document upload support with `python-multipart`.
- Added server-side document search by title, file name, and document type.
- Added authenticated file preview endpoint.
- Added document comment creation and retrieval.
- Added frontend `WorkspaceModule` component.
- Connected Dashboard `Shared workspace` and `Group discussion` cards to the workspace module.
- Added modal preview for images/PDFs.
- Added backend API tests for auth protection, upload, search, preview, and comments.
- Added project README and Part 4 module documentation.

## Testing

Backend:

```text
uv run pytest
10 passed
```

Frontend:

```text
npm.cmd test
2 passed

npm.cmd run build
passed
```

## Manual Test Steps

1. Start the backend on `127.0.0.1:8000`.
2. Start the frontend on `127.0.0.1:3000`.
3. Log in with a UCLA email account.
4. Click `Shared workspace`.
5. Upload a document with title, type, and file.
6. Search for the uploaded document.
7. Click the document to preview it in a modal.
8. Click `Group discussion`.
9. Select the uploaded document.
10. Click `Preview file` to view it from the discussion panel.
11. Add a comment and confirm it appears under the document.

## Integration Note

The workspace currently uses `DEFAULT_GROUP_ID = 1` because the group membership module is not integrated yet. Once the group module is merged, this should be connected to the current user's actual study group workspace.
