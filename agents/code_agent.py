"""Rule-based code inspection agent."""

from tools.file_tools import read_file


class CodeAgent:
    """Inspect files using local file tools."""

    def inspect_files(self, paths: list[str]) -> dict:
        """Read requested file paths and return per-file status."""
        files: list[dict] = []
        for path in paths:
            try:
                content = read_file(path)
                files.append(
                    {
                        "path": path,
                        "content": content,
                        "success": True,
                        "error": None,
                    }
                )
            except Exception as error:
                files.append(
                    {
                        "path": path,
                        "content": "",
                        "success": False,
                        "error": str(error),
                    }
                )
        return {"files": files}
