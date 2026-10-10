"""Rule-based test execution agent."""

from tools.test_runner import run_pytest

UPLOADED_REPO_WARNING = (
    "Tests were not run automatically for uploaded repositories. Provide a targeted "
    "test path to avoid large unsafe test runs."
)


class TestAgent:
    """Run local tests through the test runner tool."""

    def run_tests(self, path: str = "tests") -> dict:
        """Run pytest for a path and return the structured result."""
        if "uploads/repos" in path.replace("\\", "/"):
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": UPLOADED_REPO_WARNING,
            }
        return run_pytest(path)
