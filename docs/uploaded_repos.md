# Uploaded Repositories

AgentOps Copilot can analyze repositories uploaded as `.zip` files from the Streamlit frontend.

## How Zip Upload Works

1. The user selects `Upload repo zip` in the Streamlit sidebar.
2. The frontend sends the file to `POST /upload-repo` as multipart form data.
3. The backend creates a unique `repo_id`.
4. The zip is safely extracted into `uploads/repos/<repo_id>/`.
5. If the archive contains one top-level folder, that folder is treated as the repository root.
6. The backend stores `repo_id -> repo_path` in an in-memory registry.
7. The frontend uses `repo_id` for indexing and asking questions.

Local path mode still works. Users can choose either local path analysis or zip upload mode in the UI.

## Security Protections

- Only `.zip` uploads are accepted.
- Zip entries are resolved before extraction to prevent zip-slip path traversal.
- Entries that would extract outside the upload directory are rejected.
- macOS metadata files such as `__MACOSX` and `.DS_Store` are skipped.
- Symlinks inside zip files are rejected.
- Uploading and indexing do not execute repository code.
- Tests only run when the request explicitly mentions test, pytest, failure, or bug.

## Limitations

- Uploaded repo registry is in memory, so repo IDs reset when the backend restarts.
- Uploads are stored on local disk under `uploads/repos/`.
- Very large repositories can take longer to upload, extract, and index.
- The current UI does not expose every indexing control, such as `exclude_dirs`.

## Recommended Repo Size

For smooth local demos, keep uploaded repositories reasonably small:

- Recommended max upload size: under 500 MB for smooth local testing.
- Hard configured Streamlit limit: 1000 MB.
- Uploading large repositories does not cost money or call cloud APIs, but it uses local CPU, RAM, and disk.
- Large repos may still be slow to upload, extract, and index.
- Exclude generated folders before zipping.
- Remove dependency/build directories such as `.git`, `node_modules`, `.venv`, `dist`, `build`, `.next`, `__pycache__`, `target`, `coverage`, `.pytest_cache`, and `.mypy_cache`.
- For larger repositories, use backend indexing controls such as `max_files`, `max_file_size_kb`, and `exclude_dirs`.
