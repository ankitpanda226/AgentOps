"""Deterministic PR planning using existing evidence, without executable tools."""

from pathlib import PurePosixPath
import re

from agents.intent import has_test_negation

SAFETY_NOTICE = (
    "Safe simulated pull-request plan only: the simulator does not edit files, "
    "execute tests, create commits, or open real PRs. Pseudo-diffs describe intent, "
    "not applicable patches. Any test results are evidence from the earlier workflow."
)
MAX_FILES = 6
TOOL_PATHS = (
    "tools/base.py",
    "tools/simple.py",
    "tools/convert.py",
    "tools/render.py",
    "tool_calling_agent",
    "agents/agent.py",
)
PROFILES = {
    "tools": {
        "terms": ("tool", "tools"),
        "actions": (
            "define the tool input schema and validation",
            "implement the tool class and execution contract",
            "register the tool and wire tool calling into the agent",
            "add tool execution and failure-handling tests",
            "document tool registration and usage examples",
        ),
        "tests": (
            "Test tool schema validation, registration/wiring, successful execution, "
            "and failure handling.",
        ),
        "risk": "Preserve tool signatures, callback behavior, and error propagation.",
    },
    "auth": {
        "terms": ("auth", "authentication", "authorization", "middleware"),
        "actions": (
            "update auth middleware and authorization boundaries",
            "validate requests and authentication schemas",
            "protect routes while preserving public access where intended",
            "add authorized, unauthorized, and malformed-token tests",
            "document authentication requirements and examples",
        ),
        "tests": (
            "Test protected routes with authorized, unauthorized, expired, and "
            "malformed credentials; preserve public route behavior.",
        ),
        "risk": "Review authorization boundaries, credential handling, and secret exposure.",
    },
    "api": {
        "terms": ("api", "endpoint", "endpoints", "route", "routes"),
        "actions": (
            "update the route and request/response schema",
            "adapt service behavior while preserving existing API contracts",
            "add endpoint tests for success and validation errors",
            "document the API and request/response examples",
        ),
        "tests": (
            "Test endpoint success, invalid requests, error responses, and backward "
            "compatibility of schemas and service behavior.",
        ),
        "risk": "Check route behavior, response schemas, and existing API client compatibility.",
    },
    "bug": {
        "terms": (
            "bug",
            "bugs",
            "failure",
            "failures",
            "failing",
            "debug",
            "debugging",
        ),
        "actions": (
            "isolate the failure and propose the smallest responsible patch",
            "preserve failure handling and unrelated behavior",
            "add a regression test reproducing the original bug",
            "document a targeted validation workflow",
        ),
        "tests": (
            "Define a regression test reproducing the failure, verify the minimal "
            "patch, and check adjacent success and failure-handling paths.",
        ),
        "risk": "A minimal patch still needs a confirmed root cause and regression evidence.",
    },
    "docs": {
        "terms": ("docs", "documentation", "readme", "document"),
        "actions": (
            "update README and workflow docs to reflect actual behavior",
            "add usage examples and explicit acceptance criteria",
            "check documentation links and consistency with public interfaces",
        ),
        "tests": (
            "Review README/workflow docs, example accuracy, links, and acceptance "
            "criteria against the implementation.",
        ),
        "risk": "Documentation examples must match implemented behavior, not unverified proposals.",
    },
}


def _compact(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _items(value: object) -> list[str]:
    """Bound optional plan/critique lists without mutating their inputs."""
    if not isinstance(value, (list, tuple)):
        return []
    return [_compact(str(item)) for item in value[:8] if item]


class PRSimulatorAgent:
    """Propose candidate changes; never read, write, or execute repository files."""

    def simulate_pr(
        self,
        user_request: str,
        context: list[dict],
        plan: dict,
        test_result: dict | None = None,
        critique: dict | None = None,
    ) -> dict:
        """Build the public PR simulation contract from completed workflow evidence."""
        tokens = set(re.findall(r"[a-z]+", user_request.lower()))
        kinds = [
            key
            for key, profile in PROFILES.items()
            if tokens.intersection(profile["terms"])
        ]
        actions = [action for kind in kinds for action in PROFILES[kind]["actions"]]
        if not actions:
            actions = [
                "make the smallest change that satisfies the request",
                "add targeted tests and update usage documentation",
            ]
        goal = _compact(user_request or str(plan.get("goal", "")), 180)
        goal = goal or "Clarify the requested change"
        sources = self._candidate_sources(context, kinds)
        changes, diffs = [], []
        for path, evidence in sources:
            change_type = self._change_type(path)
            proposal = self._proposal(path, change_type, kinds, actions)
            changes.append(
                {
                    "file_path": path,
                    "change_type": change_type,
                    "reason": f"Retrieved candidate: {proposal}. Request: {goal}",
                }
            )
            diffs.append(
                {
                    "file_path": path,
                    "before": (
                        f"Retrieved excerpt: {evidence}"
                        if evidence
                        else "Path retrieved without an excerpt; inspect current behavior."
                    ),
                    "after": f"Proposed: {proposal}. Intended outcome: {goal}",
                    "notes": "Conceptual before/after summary, not an executable patch. "
                    "Verify the source and scope before implementation.",
                }
            )

        test_plan = [self._test_evidence(user_request, test_result)]
        test_plan.extend(test for kind in kinds for test in PROFILES[kind]["tests"])
        test_plan.extend(
            [
                f"Define observable acceptance checks for: {goal}",
                "After implementation, validate a targeted test path in an isolated "
                "checkout; do not automatically run an uploaded repository's full suite.",
            ]
        )
        risks = [
            "Retrieved paths are likely candidates, not a verified change set; "
            "excerpts may be incomplete or stale.",
            "The proposed patch has not been implemented or tested. Earlier test "
            "results do not prove this simulated change works.",
            *_items(plan.get("risks")),
            *[PROFILES[kind]["risk"] for kind in kinds],
        ]
        warnings = _items((critique or {}).get("warnings"))
        risks.extend(f"Critic warning: {warning}" for warning in warnings)
        if test_result is not None:
            risks.append(self._test_evidence(user_request, test_result))
        if not sources:
            risks.insert(
                0,
                "Missing repository context: index relevant source files "
                "before choosing an implementation scope.",
            )
        score, reason = self._readiness(bool(sources), test_result, bool(warnings))
        questions = [
            "Do the retrieved files cover the requested behavior and its callers?",
            f"Which acceptance criteria prove: {goal}?",
            "Which compatibility and failure cases need regression coverage?",
            "What implementation and validation evidence is needed before merge review?",
        ]
        questions.extend(
            f"How will a reviewer verify: {criterion}?"
            for criterion in _items(plan.get("success_criteria"))[:3]
        )
        summary = (
            f"Simulated proposal for: {goal}. "
            f"{len(changes)} candidate file(s) selected from retrieved context. "
            f"Suggested scope: {'; '.join(actions)}."
        )
        steps = _items(plan.get("steps"))[:3]
        if steps:
            summary += f" Workflow plan: {'; '.join(steps)}."
        if not sources:
            summary += " Missing context: file selection is deferred until indexing."
        return {
            "pr_title": f"[Simulated PR] {_compact(goal, 80)}",
            "pr_summary": summary,
            "files_changed": changes,
            "pseudo_diff": diffs,
            "test_plan": list(dict.fromkeys(test_plan)),
            "risk_review": list(dict.fromkeys(risks)),
            "reviewer_questions": questions,
            "merge_readiness_score": score,
            "merge_readiness_reason": reason,
        }

    @staticmethod
    def _candidate_sources(
        context: list[dict], kinds: list[str]
    ) -> list[tuple[str, str]]:
        sources: dict[str, str] = {}
        for item in context:
            raw_path = str(item.get("file_path") or "").replace("\\", "/")
            if (
                not raw_path
                or any(ord(char) < 32 for char in raw_path)
                or ".." in PurePosixPath(raw_path).parts
            ):
                continue
            path = str(PurePosixPath(raw_path))
            if path == ".":
                continue
            evidence = _compact(str(item.get("text") or ""))
            if path not in sources or not sources[path]:
                sources[path] = evidence

        def priority(path: str) -> int:
            lower = path.lower()
            if "tools" in kinds and any(pattern in lower for pattern in TOOL_PATHS):
                return 0
            if "auth" in kinds and any(x in lower for x in ("auth", "middleware")):
                return 1
            if "api" in kinds and any(
                x in lower for x in ("route", "schema", "service", "api")
            ):
                return 2
            if "docs" in kinds and PRSimulatorAgent._change_type(path) == "docs":
                return 3
            return 4

        # Stable sorting retains retrieval order when request-specific ranks tie.
        paths = sorted(sources, key=priority)[:MAX_FILES]
        return [(path, sources[path]) for path in paths]

    @staticmethod
    def _change_type(path: str) -> str:
        parts = PurePosixPath(path.lower()).parts
        name = parts[-1]
        if "tests" in parts or "test" in parts or name.startswith("test_"):
            return "test"
        if "docs" in parts or name.endswith((".md", ".rst", ".txt")):
            return "docs"
        return "modify"

    @staticmethod
    def _proposal(
        path: str, change_type: str, kinds: list[str], actions: list[str]
    ) -> str:
        if change_type == "test":
            return "add regression coverage for success, invalid input, and failure handling"
        if change_type == "docs":
            return "update README/workflow documentation, examples, and acceptance criteria"
        lower = path.lower()
        if "tools" in kinds:
            if "tools/base.py" in lower:
                return "define the tool schema, validation, and base class contract"
            if "tools/simple.py" in lower:
                return "implement the tool class, execution, and failure handling"
            if "tools/render.py" in lower:
                return "update tool schema rendering and descriptions for tool calling"
            if any(
                x in lower
                for x in ("tools/convert.py", "tool_calling_agent", "agents/agent.py")
            ):
                return "register and wire the tool into agent invocation and conversion"
        if "auth" in kinds and any(x in lower for x in ("auth", "middleware")):
            return "enforce auth middleware, request validation, and protected-route authorization"
        if "api" in kinds:
            if "schema" in lower:
                return "update request/response schemas and preserve validation compatibility"
            if "service" in lower:
                return "adapt service behavior and preserve failure handling"
            if any(x in lower for x in ("route", "api", "main.py")):
                return "update route behavior and request validation without breaking clients"
        return "; ".join(actions[:2])

    @staticmethod
    def _test_evidence(user_request: str, result: dict | None) -> str:
        note = (
            "Tests explicitly deferred by request. "
            if has_test_negation(user_request)
            else ""
        )
        if result is None:
            return note + "No test result supplied; the simulator never executes tests."
        if result.get("exit_code") == -2:
            return note + "Tests skipped for uploaded-repository safety (exit code -2)."
        if result.get("success") is True:
            return (
                note
                + "Earlier workflow tests passed; rerun after any actual implementation."
            )
        return (
            note
            + "Earlier workflow tests failed; investigate before considering a merge."
        )

    @staticmethod
    def _readiness(
        has_context: bool, result: dict | None, has_warnings: bool
    ) -> tuple[int, str]:
        score = 70
        reasons = ["Start at 70"]
        if not has_context:
            score -= 25
            reasons.append("-25: missing usable repository context")
        if result is not None:
            if result.get("exit_code") == -2:
                score -= 10
                reasons.append("-10: tests skipped for uploaded-repository safety")
            elif result.get("success") is True:
                score += 10
                reasons.append("+10: earlier workflow tests passed")
            elif result.get("success") is False or result.get("exit_code", 0) != 0:
                score -= 15
                reasons.append("-15: earlier workflow tests failed")
        else:
            reasons.append("tests not run: no test adjustment")
        if has_warnings:
            score -= 10
            reasons.append("-10: critique contains warnings")
        score = max(0, min(100, score))
        reason = "; ".join(reasons) + f". Score: {score}/100. "
        reason += (
            "Planning heuristic only, not merge approval: the proposed change is "
            "not ready to merge until implemented, validated, and reviewed."
        )
        return score, reason


def render_pr_simulation(simulation: dict) -> str:
    """Render the simulation contract as readable Markdown."""
    lines = [
        "## Agentic PR Simulation",
        "",
        SAFETY_NOTICE,
        "",
        f"### {simulation.get('pr_title', 'Simulated PR')}",
        str(simulation.get("pr_summary", "")),
        "",
        f"### Merge readiness: {simulation.get('merge_readiness_score', 0)}/100",
        str(simulation.get("merge_readiness_reason", "")),
        "",
        "### Files changed (proposed candidates)",
    ]
    for change in simulation.get("files_changed", []):
        lines.append(
            f"- `{change['file_path']}` ({change['change_type']}): {change['reason']}"
        )
    if not simulation.get("files_changed"):
        lines.append("No candidate files: retrieve relevant repository evidence first.")
    lines.extend(["", "### Pseudo-diff (conceptual)"])
    for diff in simulation.get("pseudo_diff", []):
        lines.extend(["", f"#### `{diff['file_path']}`", "", str(diff["notes"]), ""])
        # Indentation prevents source text from closing a Markdown code fence.
        for label in ("before", "after"):
            lines.append(f"**{label.title()}:**\n")
            lines.extend("    " + line for line in diff[label].splitlines())
            lines.append("")
    for title, key in (
        ("Test plan", "test_plan"),
        ("Risk review", "risk_review"),
        ("Reviewer questions", "reviewer_questions"),
    ):
        lines.extend(
            ["", f"### {title}", "", *[f"- {item}" for item in simulation.get(key, [])]]
        )
    return "\n".join(lines)
