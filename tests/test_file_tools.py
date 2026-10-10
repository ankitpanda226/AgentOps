"""Tests for developer workflow tools."""

from pathlib import Path

from tools.file_tools import (
    TRUNCATION_NOTE,
    list_files,
    read_file,
    safe_path_check,
    write_file,
)
from tools.repo_search import search_text
from tools.test_runner import run_pytest


def test_read_file(tmp_path: Path) -> None:
    """read_file should return text and truncate long files."""
    source = tmp_path / "sample.txt"
    source.write_text("abcdef", encoding="utf-8")

    assert read_file(str(source)) == "abcdef"
    assert read_file(str(source), max_chars=3) == "abc" + TRUNCATION_NOTE


def test_write_file(tmp_path: Path) -> None:
    """write_file should create parent directories and write UTF-8 text."""
    target = tmp_path / "nested" / "output.txt"

    write_file(str(target), "hello world")

    assert target.read_text(encoding="utf-8") == "hello world"


def test_list_files_with_extensions(tmp_path: Path) -> None:
    """list_files should filter extensions and skip ignored directories."""
    (tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "README.md").write_text("docs", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "hidden.py").write_text("hidden", encoding="utf-8")

    files = list_files(str(tmp_path), extensions=[".py", "md"])

    assert files == [str(tmp_path / "README.md"), str(tmp_path / "main.py")]


def test_safe_path_check_blocks_traversal(tmp_path: Path) -> None:
    """safe_path_check should reject paths outside the root."""
    inside = tmp_path / "nested" / "file.txt"
    outside = tmp_path.parent / "outside.txt"

    assert safe_path_check(str(inside), str(tmp_path)) is True
    assert safe_path_check(str(outside), str(tmp_path)) is False


def test_search_text_finds_matches(tmp_path: Path) -> None:
    """search_text should return matching lines with metadata."""
    source = tmp_path / "module.py"
    source.write_text("alpha\nNeedle here\nomega\nneedle again\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("needle in markdown", encoding="utf-8")

    matches = search_text(str(tmp_path), "needle", extensions=[".py"])

    assert matches == [
        {
            "file_path": str(source),
            "line_number": 2,
            "line": "Needle here",
        },
        {
            "file_path": str(source),
            "line_number": 4,
            "line": "needle again",
        },
    ]


def test_run_pytest_returns_result(tmp_path: Path) -> None:
    """run_pytest should return a structured result for a tiny passing suite."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "def test_sample_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    result = run_pytest(str(test_file))

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "test_sample.py" in result["stdout"]
    assert result["stderr"] == ""


def test_run_pytest_timeout_returns_structured_result(tmp_path: Path) -> None:
    """run_pytest should return a deterministic timeout result."""
    test_file = tmp_path / "test_slow.py"
    test_file.write_text(
        "import time\n\n"
        "def test_slow():\n"
        "    time.sleep(2)\n",
        encoding="utf-8",
    )

    result = run_pytest(str(test_file), timeout_seconds=1)

    assert result["success"] is False
    assert result["exit_code"] == -1
    assert isinstance(result["stdout"], str)
    assert result["stderr"] == "pytest timed out after 1 seconds"
