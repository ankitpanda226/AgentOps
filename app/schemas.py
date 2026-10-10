"""Shared API schemas."""

from pydantic import BaseModel


class IndexRequest(BaseModel):
    """Request model for repository indexing."""

    repo_path: str | None = None
    repo_id: str | None = None
    max_files: int | None = 1000
    max_file_size_kb: int = 500
    include_extensions: list[str] | None = None
    exclude_dirs: list[str] | None = None


class IndexResponse(BaseModel):
    """Response model for repository indexing."""

    indexed_chunks: int
    indexed_files: int = 0
    skipped_files: int = 0
    skipped_large_files: int = 0


class AskRequest(BaseModel):
    """Request model for agent questions."""

    question: str
    repo_path: str | None = None
    repo_id: str | None = None
    simulate_pr: bool = False


class UploadRepoResponse(BaseModel):
    """Response model for uploaded repository zips."""

    repo_id: str
    repo_path: str
    message: str


class AskResponse(BaseModel):
    """Response model for agent orchestration."""

    task_id: int | None
    plan: dict
    context: list[dict]
    issue_draft: dict
    test_result: dict | None
    critique: dict
    final_answer: str
    pr_simulation: dict | None = None


class RunTestsRequest(BaseModel):
    """Request model for test execution."""

    test_path: str = "tests"


class RunTestsResponse(BaseModel):
    """Response model for test execution."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str


class HealthResponse(BaseModel):
    """Response model for health checks."""

    status: str
