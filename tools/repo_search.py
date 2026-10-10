"""Repository text search tools."""

from tools.file_tools import list_files


def search_text(
    root: str, query: str, extensions: list[str] | None = None
) -> list[dict]:
    """Search files recursively for a case-insensitive text query.

    Args:
        root: Directory to search.
        query: Text to find.
        extensions: Optional extension allow-list.

    Returns:
        Match dictionaries containing ``file_path``, ``line_number``, and
        ``line`` keys.
    """
    if not query:
        return []

    normalized_query = query.lower()
    matches: list[dict] = []

    for file_path in list_files(root, extensions=extensions):
        try:
            with open(file_path, encoding="utf-8", errors="replace") as file:
                for line_number, line in enumerate(file, start=1):
                    stripped_line = line.rstrip("\n")
                    if normalized_query in stripped_line.lower():
                        matches.append(
                            {
                                "file_path": file_path,
                                "line_number": line_number,
                                "line": stripped_line,
                            }
                        )
        except OSError:
            continue

    return matches
