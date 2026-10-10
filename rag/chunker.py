"""Utilities for splitting local files into retrievable text chunks."""

from pathlib import Path


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    """Split text into overlapping character chunks.

    Args:
        text: Source text to split.
        chunk_size: Maximum number of characters in each chunk.
        overlap: Number of trailing characters to repeat in the next chunk.

    Returns:
        Ordered chunks preserving the original text content.

    Raises:
        ValueError: If chunk sizing would make progress impossible.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        chunk = text[start : start + chunk_size]
        chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
        start += step

    return chunks


def chunk_file(path: str) -> list[dict]:
    """Read a file and return chunks with retrieval metadata.

    Args:
        path: Path to a UTF-8 compatible text file.

    Returns:
        A list of dictionaries containing ``file_path``, ``chunk_id``, and
        ``text`` keys.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8", errors="replace")

    return [
        {
            "file_path": str(file_path),
            "chunk_id": chunk_id,
            "text": chunk,
        }
        for chunk_id, chunk in enumerate(chunk_text(text))
    ]
