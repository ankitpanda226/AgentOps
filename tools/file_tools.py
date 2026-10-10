"""Safe local file tools for developer workflow agents."""

from pathlib import Path

IGNORED_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache"}
TRUNCATION_NOTE = "\n\n[truncated: file exceeded max_chars]"


def read_file(path: str, max_chars: int = 12000) -> str:
    """Read a UTF-8 text file, truncating long content when requested.

    Args:
        path: File path to read.
        max_chars: Maximum number of characters to return before adding a
            truncation note.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If max_chars is negative.
    """
    if max_chars < 0:
        raise ValueError("max_chars must be greater than or equal to 0")

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(path)

    content = file_path.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + TRUNCATION_NOTE


def write_file(path: str, content: str) -> None:
    """Write UTF-8 text to a file, creating parent directories as needed."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def list_files(root: str, extensions: list[str] | None = None) -> list[str]:
    """Recursively list files under a root directory.

    Args:
        root: Directory to search.
        extensions: Optional extension allow-list such as ``[".py", ".md"]``.

    Returns:
        Sorted file paths as strings.
    """
    root_path = Path(root)
    normalized_extensions = _normalize_extensions(extensions)
    files: list[str] = []

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if _has_ignored_part(path, root_path):
            continue
        if normalized_extensions is not None and path.suffix.lower() not in normalized_extensions:
            continue
        files.append(str(path))

    return sorted(files)


def safe_path_check(path: str, root: str) -> bool:
    """Return True only when path resolves inside root."""
    resolved_path = Path(path).resolve()
    resolved_root = Path(root).resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _normalize_extensions(extensions: list[str] | None) -> set[str] | None:
    if extensions is None:
        return None
    return {
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in extensions
    }


def _has_ignored_part(path: Path, root: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
