# Agentic PR Simulator

Agentic PR Simulator turns the current request, retrieved repository context,
plan, test evidence, and critique into a safe simulated pull-request plan. It is
deterministic, rule-based, and local-first: the simulator does not edit files,
execute tests, create commits, open real PRs, or call external APIs.

## Workflow and UI

1. Select a local repository or upload a ZIP, then click **Index Repository**.
2. Describe the requested change and click **Ask Agent**.
3. Review **Agentic PR Simulation**: title, summary, candidate files, expandable
   before/after pseudo-diffs, test plan, risk review, reviewer questions, and score.
4. Download the complete **Markdown report** or the simulated PR as JSON.

Every workflow response includes a simulation after planning, retrieval, issue
drafting, optional test execution, and critique. The simulator only consumes
existing test evidence; it never runs tests itself. Both LangGraph and the plain
Python fallback follow this order.

Enable **Simulation only (skip test execution)** to prevent workflow tests even
when the question requests them. This existing optional mode also bypasses supplied
LLM clients. Normal requests keep their existing test safety rules: explicit test
negation prevents pytest; broad uploaded-repository test runs are skipped with
exit code `-2`. No new execution permissions are introduced by the simulator.

The UI requires indexing before asking. If an explicit API repository selector
does not match the indexed context, `/ask` returns 409 instead of using another
repository's evidence. Indexing publishes a fresh snapshot; in-flight asks retain
their own snapshot and failed indexing leaves the previous context intact.

## API contract

Existing `/ask` request payloads remain valid. The response adds
`pr_simulation: dict | None = None` for compatibility with older clients and
stored results. Current workflow runs populate it automatically.

```bash
curl -X POST http://127.0.0.1:8010/index \
  -H 'Content-Type: application/json' \
  -d '{"repo_path":"."}'

curl -X POST http://127.0.0.1:8010/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Add validation to the API endpoint","repo_path":"."}'
```

Use `repo_id` for an uploaded repository. Add `"simulate_pr": true` to force the
no-execution mode; it is not required to receive a simulation. Requests without a
repository selector use the currently indexed context.

The public method is:

```python
PRSimulatorAgent().simulate_pr(
    user_request: str,
    context: list[dict],
    plan: dict,
    test_result: dict | None = None,
    critique: dict | None = None,
) -> dict
```

The returned object has exactly these fields (illustrative values abbreviated):

```json
{
  "pr_title": "[Simulated PR] Add API validation",
  "pr_summary": "Propose route validation, schema changes, tests, and docs.",
  "files_changed": [
    {
      "file_path": "app/main.py",
      "change_type": "modify",
      "reason": "Retrieved candidate for request validation."
    }
  ],
  "pseudo_diff": [
    {
      "file_path": "app/main.py",
      "before": "Retrieved excerpt describing current route behavior.",
      "after": "Proposed route validation that preserves existing clients.",
      "notes": "Conceptual summary, not an executable patch."
    }
  ],
  "test_plan": ["Cover valid requests and validation errors."],
  "risk_review": ["Check compatibility with existing API clients."],
  "reviewer_questions": ["Which acceptance criteria prove the behavior?"],
  "merge_readiness_score": 70,
  "merge_readiness_reason": "Start at 70; no test adjustment. Planning only, not merge approval."
}
```

`change_type` describes a candidate as `modify`, `add`, `test`, or `docs`. The
current implementation labels retrieved files as `modify`, `test`, or `docs`;
it does not invent new paths or claim that an existing file must be added.

## Request-specific planning

- **Tool integration/execution/calling:** prioritize `tools/base.py`,
  `tools/simple.py`, `tools/convert.py`, `tools/render.py`, `tool_calling_agent`,
  and `agents/agent.py`; propose schemas, tool classes, registration/wiring,
  tests, and usage docs.
- **Auth/middleware:** propose middleware, request validation, auth schemas,
  protected routes, unauthorized tests, and documentation.
- **API/endpoints/routes:** propose routes, schemas, service changes, endpoint
  tests, and examples.
- **Bugs/failures/debugging:** propose a minimal patch, regression coverage,
  failure handling, and a targeted validation workflow.
- **Docs:** propose README/workflow updates, examples, links, and acceptance
  criteria.

Mixed requests combine relevant suggestions. Candidate paths are normalized,
deduplicated, and limited to six. Retrieved paths without excerpts remain
candidates but explicitly require inspection. With no usable context, file and
diff lists are empty, a proposal is still returned, and missing context reduces
the score. Source snippets are bounded and never executed.

## Merge readiness scoring

Start at **70**, then apply:

| Evidence | Adjustment |
| --- | ---: |
| No usable repository context | -25 |
| Failed tests | -15 |
| Tests skipped for uploaded-repository safety (`exit_code == -2`) | -10 |
| Critique contains warnings | -10 |
| Passed tests | +10 |

The test adjustments are mutually exclusive: a safety skip is not also counted
as a failure. With no test result there is no test adjustment. Clamp the result
to 0–100 and explain every applied adjustment in `merge_readiness_reason`.

The score is a planning heuristic, not a probability or merge approval. Passing
tests describe the earlier workflow, not an implementation of the simulated
change. An actual patch still requires implementation, validation, and review.

## Markdown export and limitations

`app.report_export.build_markdown_export(result)` includes the final answer,
plan, retrieved context sources, issue draft, available test result/analysis,
critique, and simulation. It supports legacy results without a simulation and
avoids duplicating the proposal already included in the final answer.

The simulator is not a patch generator or a verified dependency analysis.
Retrieval may be incomplete or stale. Pseudo-diffs are human-readable before/after
summaries that must not be applied as patches. Normal task history is still saved
in the application's SQLite memory outside uploaded repositories.
