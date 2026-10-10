"""Tests for FastAPI application endpoints."""

from io import BytesIO
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest

from app.main import UPLOADED_REPOS, app
from memory.memory_store import MemoryStore
from rag.vector_store import VectorStore


def test_index_endpoint_indexes_repo(tmp_path: Path) -> None:
    """POST /index should index supported repository files."""
    _reset_app_state(tmp_path)
    (tmp_path / "module.py").write_text("def endpoint_index(): pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("Endpoint docs", encoding="utf-8")
    client = TestClient(app)

    response = client.post("/index", json={"repo_path": str(tmp_path)})

    assert response.status_code == 200
    assert response.json() == {
        "indexed_chunks": 2,
        "indexed_files": 2,
        "skipped_files": 0,
        "skipped_large_files": 0,
    }


def test_index_endpoint_returns_indexing_metadata(tmp_path: Path) -> None:
    """POST /index should return large-repo indexing metadata."""
    _reset_app_state(tmp_path)
    (tmp_path / "small.py").write_text("def endpoint_index(): pass", encoding="utf-8")
    (tmp_path / "large.py").write_text("x" * 2048, encoding="utf-8")
    client = TestClient(app)

    response = client.post(
        "/index",
        json={
            "repo_path": str(tmp_path),
            "max_file_size_kb": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "indexed_chunks": 1,
        "indexed_files": 1,
        "skipped_files": 1,
        "skipped_large_files": 1,
    }


def test_ask_endpoint_returns_agent_response(tmp_path: Path) -> None:
    """POST /ask should return the structured supervisor response."""
    _reset_app_state(tmp_path)
    app.state.vector_store.add_documents(
        [
            {
                "file_path": "app/main.py",
                "chunk_id": 0,
                "text": "FastAPI health endpoint and ask endpoint",
            }
        ]
    )
    client = TestClient(app)

    response = client.post(
        "/ask",
        json={"question": "Explain the code implementation"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == 1
    assert payload["plan"]["goal"] == "Explain the code implementation"
    assert payload["context"][0]["file_path"] == "app/main.py"
    assert payload["issue_draft"]["title"] == "Explain the code implementation"
    assert payload["test_result"] is None
    assert payload["final_answer"]


def test_run_tests_endpoint_returns_result(tmp_path: Path) -> None:
    """POST /run-tests should return structured pytest output."""
    _reset_app_state(tmp_path)
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_passes():\n    assert True\n", encoding="utf-8")
    client = TestClient(app)

    response = client.post("/run-tests", json={"test_path": str(test_file)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["exit_code"] == 0
    assert "test_sample.py" in payload["stdout"]
    assert payload["stderr"] == ""


def test_index_endpoint_rejects_missing_path(tmp_path: Path) -> None:
    """POST /index should reject missing repository paths."""
    _reset_app_state(tmp_path)
    client = TestClient(app)

    response = client.post("/index", json={"repo_path": str(tmp_path / "missing")})

    assert response.status_code == 404
    assert response.json()["detail"] == "repo_path does not exist"


def test_safe_extract_zip_blocks_path_traversal(tmp_path: Path) -> None:
    """Zip extraction should reject entries outside the destination."""
    from app.upload_utils import safe_extract_zip

    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../evil.py", "print('nope')")

    with pytest.raises(ValueError, match="Unsafe zip path"):
        safe_extract_zip(str(zip_path), str(tmp_path / "extract"))


def test_find_repo_root_single_top_level_folder(tmp_path: Path) -> None:
    """find_repo_root should return a single extracted top-level folder."""
    from app.upload_utils import find_repo_root

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('ok')", encoding="utf-8")

    assert find_repo_root(str(tmp_path)) == str(repo)


def test_upload_repo_endpoint_accepts_zip(tmp_path: Path, monkeypatch) -> None:
    """POST /upload-repo should accept and extract repository zips."""
    _reset_app_state(tmp_path)
    monkeypatch.setattr("app.upload_utils.UPLOAD_ROOT", str(tmp_path / "uploads"))
    client = TestClient(app)

    response = client.post(
        "/upload-repo",
        files={"file": ("repo.zip", _repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repo_id"] in UPLOADED_REPOS
    assert Path(payload["repo_path"]).exists()
    assert (Path(payload["repo_path"]) / "main.py").exists()
    assert payload["message"] == "Repository uploaded and extracted successfully."


def test_upload_repo_endpoint_rejects_non_zip(tmp_path: Path) -> None:
    """POST /upload-repo should reject non-zip uploads."""
    _reset_app_state(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/upload-repo",
        files={"file": ("repo.txt", b"not a zip", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .zip files are supported"


def test_index_endpoint_accepts_repo_id(tmp_path: Path, monkeypatch) -> None:
    """POST /index should index an uploaded repo by repo_id."""
    _reset_app_state(tmp_path)
    monkeypatch.setattr("app.upload_utils.UPLOAD_ROOT", str(tmp_path / "uploads"))
    client = TestClient(app)
    upload_response = client.post(
        "/upload-repo",
        files={"file": ("repo.zip", _repo_zip_bytes(), "application/zip")},
    )
    repo_id = upload_response.json()["repo_id"]

    response = client.post("/index", json={"repo_id": repo_id})

    assert response.status_code == 200
    assert response.json()["indexed_files"] == 1
    assert response.json()["indexed_chunks"] == 1


def test_ask_endpoint_accepts_repo_id(tmp_path: Path, monkeypatch) -> None:
    """POST /ask should resolve uploaded repos by repo_id."""
    _reset_app_state(tmp_path)
    monkeypatch.setattr("app.upload_utils.UPLOAD_ROOT", str(tmp_path / "uploads"))
    client = TestClient(app)
    upload_response = client.post(
        "/upload-repo",
        files={"file": ("repo.zip", _repo_zip_bytes(), "application/zip")},
    )
    repo_id = upload_response.json()["repo_id"]
    client.post("/index", json={"repo_id": repo_id})

    response = client.post(
        "/ask",
        json={"question": "Explain the API code", "repo_id": repo_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["goal"] == "Explain the API code"
    assert payload["final_answer"]


def test_index_endpoint_resets_previous_repo_context(tmp_path: Path) -> None:
    """Indexing a new local repo should replace previous RAG context."""
    _reset_app_state(tmp_path)
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    (repo_a / "a.py").write_text("alpha_unique", encoding="utf-8")
    (repo_b / "b.py").write_text("beta_unique", encoding="utf-8")
    client = TestClient(app)

    response_a = client.post("/index", json={"repo_path": str(repo_a)})
    assert response_a.status_code == 200
    assert app.state.vector_store.search("alpha_unique", k=1)[0]["file_path"] == str(
        repo_a / "a.py"
    )

    response_b = client.post("/index", json={"repo_path": str(repo_b)})

    assert response_b.status_code == 200
    alpha_results = app.state.vector_store.search("alpha_unique", k=10)
    assert str(repo_a / "a.py") not in {
        result["file_path"] for result in alpha_results
    }
    beta_results = app.state.vector_store.search("beta_unique", k=1)
    assert beta_results[0]["file_path"] == str(repo_b / "b.py")


def test_uploaded_repo_index_does_not_mix_previous_uploads(
    tmp_path: Path, monkeypatch
) -> None:
    """Indexing uploaded repo B should clear uploaded repo A context."""
    _reset_app_state(tmp_path)
    monkeypatch.setattr("app.upload_utils.UPLOAD_ROOT", str(tmp_path / "uploads"))
    client = TestClient(app)
    repo_a = client.post(
        "/upload-repo",
        files={
            "file": (
                "repo-a.zip",
                _repo_zip_bytes("repo-a", "a.py", "alpha_unique"),
                "application/zip",
            )
        },
    ).json()
    repo_b = client.post(
        "/upload-repo",
        files={
            "file": (
                "repo-b.zip",
                _repo_zip_bytes("repo-b", "b.py", "beta_unique"),
                "application/zip",
            )
        },
    ).json()

    response_a = client.post("/index", json={"repo_id": repo_a["repo_id"]})
    assert response_a.status_code == 200
    assert "alpha_unique" in app.state.vector_store.search("alpha_unique", k=1)[0]["text"]

    response_b = client.post("/index", json={"repo_id": repo_b["repo_id"]})

    assert response_b.status_code == 200
    alpha_results = app.state.vector_store.search("alpha_unique", k=10)
    assert not any(result["file_path"].endswith("a.py") for result in alpha_results)
    beta_results = app.state.vector_store.search("beta_unique", k=1)
    assert beta_results[0]["file_path"].endswith("b.py")


def _reset_app_state(tmp_path: Path) -> None:
    app.state.vector_store = VectorStore(use_chroma=False)
    app.state.memory_store = MemoryStore(str(tmp_path / "memory.db"))
    UPLOADED_REPOS.clear()


def _repo_zip_bytes(
    top_level: str = "sample-repo",
    file_name: str = "main.py",
    content: str = "def uploaded_repo():\n    return 'ok'\n",
) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{top_level}/{file_name}", content)
        archive.writestr("__MACOSX/._main.py", "metadata")
        archive.writestr(f"{top_level}/.DS_Store", "metadata")
    buffer.seek(0)
    return buffer.getvalue()
