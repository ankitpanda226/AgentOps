"""Local test execution tools."""

import subprocess


def run_pytest(test_path: str = "tests", timeout_seconds: int = 60) -> dict:
    """Run pytest and return a structured execution result."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": _timeout_output_to_text(error.stdout),
            "stderr": f"pytest timed out after {timeout_seconds} seconds",
        }
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _timeout_output_to_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
