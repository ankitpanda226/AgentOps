"""Repository indexing pipeline for local RAG."""

from pathlib import Path

from rag.chunker import chunk_file
from rag.vector_store import VectorStore

SUPPORTED_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}
IGNORED_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}


class IndexingResult(dict):
    """Dictionary result that remains comparable to the old chunk-count integer."""

    def __eq__(self, other: object) -> bool:
        """Compare to an integer by indexed chunk count for compatibility."""
        if isinstance(other, int):
            return self.get("indexed_chunks") == other
        return super().__eq__(other)


def index_repository(
    repo_path: str,
    vector_store: VectorStore,
    max_files: int | None = 1000,
    max_file_size_kb: int = 500,
    include_extensions: list[str] | None = None,
    exclude_dirs: list[str] | None = None,
) -> IndexingResult:
    """Index supported text files in a repository into a vector store.

    Args:
        repo_path: Root directory to walk.
        vector_store: Vector store receiving generated chunks.
        max_files: Maximum number of files to index. ``None`` means unlimited.
        max_file_size_kb: Maximum file size in KiB before a file is skipped.
        include_extensions: Optional extension allow-list.
        exclude_dirs: Optional additional directory names to ignore.

    Returns:
        Metadata describing indexed and skipped files/chunks.
    """
    root = Path(repo_path)
    documents: list[dict] = []
    indexed_files = 0
    skipped_files = 0
    skipped_large_files = 0
    extensions = _normalize_extensions(include_extensions) or SUPPORTED_SUFFIXES
    ignored_dirs = IGNORED_DIRS | set(exclude_dirs or [])

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _is_ignored(path, root, ignored_dirs):
            continue
        if path.suffix.lower() not in extensions:
            skipped_files += 1
            continue
        if max_files is not None and indexed_files >= max_files:
            break
        if _is_large_file(path, max_file_size_kb):
            skipped_files += 1
            skipped_large_files += 1
            continue

        file_chunks = chunk_file(str(path))
        documents.extend(file_chunks)
        indexed_files += 1

    vector_store.add_documents(documents)
    return IndexingResult(
        {
            "indexed_chunks": len(documents),
            "indexed_files": indexed_files,
            "skipped_files": skipped_files,
            "skipped_large_files": skipped_large_files,
        }
    )


def _is_ignored(path: Path, root: Path, ignored_dirs: set[str]) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in ignored_dirs for part in relative_parts)


def _is_large_file(path: Path, max_file_size_kb: int) -> bool:
    if max_file_size_kb < 0:
        return False
    return path.stat().st_size > max_file_size_kb * 1024


def _normalize_extensions(extensions: list[str] | None) -> set[str] | None:
    if extensions is None:
        return None
    return {
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in extensions
    }
