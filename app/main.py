"""FastAPI entrypoint for AgentOps Copilot."""

from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from app.config import get_settings
from app.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    RunTestsRequest,
    RunTestsResponse,
    UploadRepoResponse,
)
from app.upload_utils import create_repo_upload_dir, find_repo_root, safe_extract_zip
from agents.supervisor import SupervisorAgent
from memory.memory_store import MemoryStore
from rag.indexer import index_repository
from rag.vector_store import VectorStore
from tools.test_runner import run_pytest

UPLOADED_REPOS: dict[str, str] = {}
ACTIVE_REPO_PATH: str | None = None
ACTIVE_REPO_ID: str | None = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.vector_store = VectorStore(use_chroma=False)
    app.state.memory_store = MemoryStore(settings.sqlite_memory_path)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        """Return service health for probes and local smoke tests."""
        return HealthResponse(status="ok")

    @app.post("/upload-repo", response_model=UploadRepoResponse, tags=["rag"])
    def upload_repo(file: UploadFile = File(...)) -> UploadRepoResponse:
        """Upload and safely extract a repository zip file."""
        filename = file.filename or ""
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip files are supported")

        upload_info = create_repo_upload_dir(filename)
        repo_id = upload_info["repo_id"]
        repo_dir = upload_info["repo_dir"]
        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                temp_path = temp_file.name
                shutil.copyfileobj(file.file, temp_file)

            safe_extract_zip(temp_path, repo_dir)
            repo_path = find_repo_root(repo_dir)
            UPLOADED_REPOS[repo_id] = repo_path
            return UploadRepoResponse(
                repo_id=repo_id,
                repo_path=repo_path,
                message="Repository uploaded and extracted successfully.",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)
            file.file.close()

    @app.post("/index", response_model=IndexResponse, tags=["rag"])
    def index_repo(payload: IndexRequest, request: Request) -> IndexResponse:
        """Index a local repository path into the shared vector store."""
        resolved_repo_path = resolve_repo_path(payload.repo_path, payload.repo_id)
        repo_path = Path(resolved_repo_path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail="repo_path does not exist")
        if not repo_path.is_dir():
            raise HTTPException(status_code=400, detail="repo_path must be a directory")

        # Publish a fresh snapshot only after indexing succeeds. In-flight asks
        # retain their own store and cannot mix repositories during re-indexing.
        vector_store = VectorStore(use_chroma=False)
        indexing_result = index_repository(
            str(repo_path),
            vector_store,
            max_files=payload.max_files,
            max_file_size_kb=payload.max_file_size_kb,
            include_extensions=payload.include_extensions,
            exclude_dirs=payload.exclude_dirs,
        )
        vector_store.repo_path = str(repo_path.resolve())
        request.app.state.vector_store = vector_store
        set_active_repo(str(repo_path), payload.repo_id)
        return IndexResponse(**indexing_result)

    @app.post("/ask", response_model=AskResponse, tags=["agents"])
    def ask(payload: AskRequest, request: Request) -> AskResponse:
        """Handle a user question through the supervisor agent."""
        resolved_repo_path = (
            resolve_repo_path(None, payload.repo_id)
            if payload.repo_id is not None
            else payload.repo_path
        )
        vector_store = get_vector_store(request.app)
        indexed_path = getattr(vector_store, "repo_path", None)
        if resolved_repo_path is not None:
            if indexed_path != str(Path(resolved_repo_path).resolve()):
                raise HTTPException(
                    status_code=409,
                    detail="Index the selected repository before asking questions.",
                )
        else:
            resolved_repo_path = indexed_path
        supervisor = SupervisorAgent(
            vector_store=vector_store,
            memory_store=get_memory_store(request.app),
        )
        result = supervisor.handle_request(
            payload.question,
            repo_path=resolved_repo_path,
            simulate_pr=payload.simulate_pr,
        )
        return AskResponse(**result)

    @app.post("/run-tests", response_model=RunTestsResponse, tags=["tools"])
    def run_tests(payload: RunTestsRequest) -> RunTestsResponse:
        """Run pytest for the requested test path."""
        result = run_pytest(payload.test_path)
        return RunTestsResponse(**result)

    return app


def get_vector_store(app: FastAPI) -> VectorStore:
    """Return the app-scoped vector store, creating one if absent."""
    vector_store = getattr(app.state, "vector_store", None)
    if vector_store is None:
        vector_store = VectorStore(use_chroma=False)
        app.state.vector_store = vector_store
    return vector_store


def get_memory_store(app: FastAPI) -> MemoryStore:
    """Return the app-scoped memory store, creating one if absent."""
    memory_store = getattr(app.state, "memory_store", None)
    if memory_store is None:
        settings = get_settings()
        memory_store = MemoryStore(settings.sqlite_memory_path)
        app.state.memory_store = memory_store
    return memory_store


def resolve_repo_path(repo_path: str | None, repo_id: str | None) -> str:
    """Resolve a repo path from an explicit path or uploaded repository id."""
    if repo_id is not None:
        if repo_id not in UPLOADED_REPOS:
            raise HTTPException(status_code=404, detail="repo_id not found")
        return UPLOADED_REPOS[repo_id]
    if repo_path:
        return repo_path
    raise HTTPException(status_code=400, detail="repo_path or repo_id is required")


def set_active_repo(repo_path: str, repo_id: str | None) -> None:
    """Store the repo currently represented by the shared vector store."""
    global ACTIVE_REPO_PATH, ACTIVE_REPO_ID
    ACTIVE_REPO_PATH = repo_path
    ACTIVE_REPO_ID = repo_id


app = create_app()
