"""Human-friendly workflow report generation."""

from __future__ import annotations

from agents.intent import has_test_negation


class WorkflowReportAgent:
    """Generate deterministic Markdown workflow reports for developer tasks."""

    def generate_report(
        self,
        user_request: str,
        plan: dict,
        context: list[dict],
        issue_draft: dict,
        test_result: dict | None = None,
        critique: dict | None = None,
    ) -> str:
        """Generate a Markdown workflow report from agent outputs."""
        sections = [
            "# AgentOps Workflow Report",
            "",
            "## 1. Request Summary",
            self._request_summary(user_request, plan),
            "",
            "## 2. What I Found in the Repository",
            self._repository_findings(context),
            "",
            "## 3. Recommended Developer Workflow",
            self._recommended_workflow(user_request),
            "",
            "## 4. Step-by-Step Implementation Plan",
            self._implementation_plan(user_request, plan),
            "",
            "## 5. Testing and Validation Plan",
            self._testing_plan(user_request, test_result),
            "",
            "## 6. Risks and Safety Checks",
            self._risks_and_safety(plan, user_request),
            "",
            "## 7. GitHub Issue Draft",
            self._issue_section(issue_draft),
            "",
            "## 8. Final Next Steps",
            self._final_next_steps(user_request, context, test_result, critique),
        ]
        return "\n".join(sections)

    def _request_summary(self, user_request: str, plan: dict) -> str:
        goal = plan.get("goal") or user_request
        return (
            f"You asked AgentOps Copilot to handle: `{user_request}`.\n\n"
            f"In plain English, the goal is to {goal[0].lower() + goal[1:] if goal else 'complete the requested developer workflow'}."
        )

    def _repository_findings(self, context: list[dict]) -> str:
        if not context:
            return (
                "No repository context was retrieved. Index the repository first or "
                "verify that the active repo contains supported source files."
            )

        lines: list[str] = []
        seen: set[str] = set()
        for item in context[:5]:
            file_path = str(item.get("file_path", "unknown"))
            if file_path in seen:
                continue
            seen.add(file_path)
            chunk_id = item.get("chunk_id", "unknown")
            snippet = self._snippet(str(item.get("text", "")))
            reason = self._relevance_reason(file_path, snippet)
            lines.append(
                f"- `{file_path}` (chunk `{chunk_id}`): {reason} Snippet: {snippet}"
            )
        return "\n".join(lines)

    def _recommended_workflow(self, user_request: str) -> str:
        subject = self._request_subject(user_request)
        if has_test_negation(user_request):
            return "\n".join(
                [
                    f"1. Understand the current implementation for {subject}.",
                    "2. Inspect the relevant files listed above before editing anything.",
                    "3. Review the relevant code paths manually.",
                    "4. Trace tool input parsing, tool execution, callbacks, and error handling.",
                    "5. Document which targeted tests should be run later, but do not execute them now.",
                    "6. Prepare issue or PR notes that summarize the investigation, risks, and acceptance criteria.",
                ]
            )
        return "\n".join(
            [
                f"1. Understand the current implementation for {subject}.",
                "2. Inspect the relevant files listed above before editing anything.",
                f"3. Make the implementation change for {subject} in the smallest sensible scope.",
                "4. Add or update tests that prove the behavior works.",
                "5. Run validation with pytest, focusing on targeted tests first.",
                "6. Prepare issue or PR notes that summarize the change, risks, and acceptance criteria.",
            ]
        )

    def _implementation_plan(self, user_request: str, plan: dict) -> str:
        request = user_request.lower()
        steps = [
            f"- Convert plan step into action: {step}"
            for step in plan.get("steps", [])
        ]
        specialized = self._specialized_steps(
            request,
            skip_test_execution=has_test_negation(user_request),
        )
        if specialized:
            steps.extend(specialized)
        return "\n".join(steps)

    def _specialized_steps(
        self,
        request: str,
        skip_test_execution: bool = False,
    ) -> list[str]:
        steps: list[str] = []
        if "authentication" in request or "auth" in request:
            steps.extend(
                [
                    "- Review auth middleware and request validation before changing endpoint behavior.",
                    "- Trace user, session, and token handling so authorization boundaries stay explicit.",
                ]
            )
            if skip_test_execution:
                steps.append(
                    "- Note authenticated and unauthenticated validation scenarios to verify later without executing tests now."
                )
            else:
                steps.append(
                    "- Update API schemas and tests for authenticated and unauthenticated paths."
                )
        if "tool" in request or "tool calling" in request:
            steps.extend(
                [
                    "- Define or update the tool base class/interface and structured input schema.",
                    "- Register the tool and wire it into the relevant agent/tool orchestration path.",
                ]
            )
            if skip_test_execution:
                steps.append(
                    "- Document targeted tool registration, invocation, and failure-handling tests to run later without executing them now."
                )
            else:
                steps.append(
                    "- Add docs and tests covering tool registration, invocation, and failure handling."
                )
        if "api" in request or "endpoint" in request:
            if skip_test_execution:
                steps.extend(
                    [
                        "- Review route, request/response schema, and service logic manually.",
                        "- Document success and error response cases to validate later when test execution is allowed.",
                    ]
                )
            else:
                steps.extend(
                    [
                        "- Update route, request/response schema, service logic, and endpoint tests together.",
                        "- Verify error responses and success responses with deterministic API tests.",
                    ]
                )
        if any(term in request for term in ("bug", "test", "pytest", "failure", "failing")):
            if skip_test_execution:
                steps.extend(
                    [
                        "- Reproduce the suspected behavior through manual code tracing, logs, or existing context instead of executing tests.",
                        "- Isolate the source of the failure and identify the smallest responsible unit before proposing a patch.",
                    ]
                )
            else:
                steps.extend(
                    [
                        "- Reproduce the failure and read the test output before patching.",
                        "- Isolate the source of the failure, patch the smallest responsible unit, and rerun tests.",
                    ]
                )
        return steps

    def _testing_plan(self, user_request: str, test_result: dict | None) -> str:
        request = user_request.lower()
        if has_test_negation(user_request):
            return "Tests were intentionally not run because the request asked not to run them."

        if test_result is not None:
            status = "passed" if test_result.get("success") else "failed"
            stdout = self._snippet(str(test_result.get("stdout", "")), length=300)
            return (
                f"Pytest {status} with exit code `{test_result.get('exit_code')}`.\n\n"
                f"Stdout summary: {stdout or 'No stdout captured.'}"
            )

        recommendations = [
            "- Run `python -m pytest` before committing.",
            "- Add targeted tests near the module you modify.",
        ]
        if "api" in request or "endpoint" in request:
            recommendations.append("- Run API endpoint tests with FastAPI `TestClient`.")
        if "auth" in request:
            recommendations.append("- Cover authorized, unauthorized, and malformed-token cases.")
        if "tool" in request:
            recommendations.append("- Cover tool success, validation error, and failure-result paths.")
        if any(term in request for term in ("bug", "test", "pytest", "failure")):
            recommendations.append("- Re-run the failing pytest path first, then the full suite.")
        return "\n".join(recommendations)

    def _risks_and_safety(self, plan: dict, user_request: str) -> str:
        risks = [f"- {risk}" for risk in plan.get("risks", [])]
        risks.extend(
            [
                "- Avoid changing unrelated files while implementing the fix.",
                "- Verify retrieved files before trusting the generated plan.",
                "- Do not trust generated plans without human review.",
            ]
        )
        if has_test_negation(user_request):
            risks.append(
                "- Record tests to run later, but do not execute them during this no-tests investigation."
            )
        else:
            risks.append("- Run tests before committing or opening a PR.")
        return "\n".join(risks)

    def _issue_section(self, issue_draft: dict) -> str:
        title = issue_draft.get("title", "Untitled AgentOps task")
        body = self._snippet(str(issue_draft.get("body", "")), length=500)
        criteria = issue_draft.get("acceptance_criteria", [])
        criteria_lines = [f"- {criterion}" for criterion in criteria] or [
            "- Confirm the implementation is complete and tested."
        ]
        return "\n".join(
            [
                f"**Title:** {title}",
                "",
                f"**Body summary:** {body or 'No issue body generated.'}",
                "",
                "**Acceptance criteria:**",
                *criteria_lines,
            ]
        )

    def _final_next_steps(
        self,
        user_request: str,
        context: list[dict],
        test_result: dict | None,
        critique: dict | None,
    ) -> str:
        next_steps = [
            "1. Open and review the relevant files from the repository context.",
            "2. Convert the recommended workflow into a small implementation checklist.",
            "3. Make the change in a focused branch or working tree.",
        ]
        if has_test_negation(user_request):
            next_steps.append("4. Review the investigation plan manually.")
            next_steps.append(
                "5. List targeted tests to run later if test execution becomes allowed."
            )
            next_steps.append("6. Use the GitHub issue draft as PR or ticket notes.")
        elif test_result is None:
            next_steps.append("4. Add targeted tests and run `python -m pytest`.")
            next_steps.append("5. Use the GitHub issue draft as PR or ticket notes.")
        else:
            next_steps.append("4. Address any failing tests or preserve the passing result.")
            next_steps.append("5. Use the GitHub issue draft as PR or ticket notes.")

        if critique and not critique.get("passed"):
            next_steps.append(
                f"{len(next_steps) + 1}. Review critic warnings before implementation."
            )
        if not context:
            next_steps.append(
                f"{len(next_steps) + 1}. Re-index the repository if context looks incomplete."
            )
        return "\n".join(next_steps)

    def _relevance_reason(self, file_path: str, snippet: str) -> str:
        path = file_path.lower()
        if path.startswith("app/"):
            return "This appears relevant because it is part of the FastAPI app/API layer."
        if path.startswith("agents/"):
            return "This appears relevant because it controls agent behavior or orchestration."
        if path.startswith("tools/"):
            return "This appears relevant because it contains developer tool integration code."
        if path.startswith("rag/"):
            return "This appears relevant because it participates in retrieval or indexing."
        if path.startswith("tests/"):
            return "This appears relevant because it validates expected behavior."
        if "auth" in path or "token" in snippet.lower():
            return "This appears relevant because it mentions authentication or token handling."
        return "This appears relevant based on its retrieved content and file name."

    def _request_subject(self, user_request: str) -> str:
        cleaned = " ".join(user_request.split())
        return cleaned[:90].rstrip(".") if cleaned else "the requested change"

    def _snippet(self, text: str, length: int = 180) -> str:
        compact = " ".join(text.split())
        if len(compact) <= length:
            return compact
        return compact[: length - 3].rstrip() + "..."
