# Workflow

AgentOps Copilot processes requests through a deterministic, local-first developer
workflow. LangGraph and the plain Python fallback run the same steps.

## Request lifecycle

1. **Plan:** `PlannerAgent` identifies the goal, steps, tool needs, risks, and
   success criteria.
2. **Retrieve:** `RAGAgent` retrieves repository chunks from the indexed context.
   Requests selecting another repository must index it first.
3. **Draft an issue:** `DocsAgent` produces a GitHub-style issue title, body, and
   acceptance criteria without creating a real issue.
4. **Optionally test:** explicit test requests may invoke `TestAgent`. Test
   negation such as “skip tests” prevents execution. Uploaded-repository broad
   test runs return a safety skip (`exit_code: -2`). Simulation-only mode always
   skips test execution.
5. **Critique:** `CriticAgent` reviews the plan, context, issue draft, test evidence,
   and provisional report for missing evidence or unsupported claims.
6. **Simulate a PR:** `PRSimulatorAgent.simulate_pr()` consumes the plan, context,
   optional test result, and available critique. It creates a safe simulated
   pull-request plan with candidate files, before/after summaries, review
   questions, and an explained readiness score. It does not edit files, run
   tests, call external APIs, create commits, or create a real PR.
7. **Finalize and persist:** the final workflow report includes the simulation.
   `SupervisorAgent` saves the task, decisions, and tool history to application
   memory when configured, then returns the structured result.

The API result preserves `task_id`, `plan`, `context`, `issue_draft`, `test_result`,
`critique`, and `final_answer`, and adds optional `pr_simulation`. Current workflow
runs always populate the simulation. Older request payloads remain valid.

## Agentic PR Simulation

Example request:

```text
Add tool registration and input validation without running tests.
```

The simulator prioritizes retrieved tool interfaces and agent wiring paths,
deduplicates them, and selects at most six candidate files. The proposal suggests
tool schemas, classes, registration, regression tests, and documentation. No tests
run for this request. With missing context it returns a proposal with no invented
file paths and a lower readiness score.

The simulation fields are:

- `pr_title` and `pr_summary`
- `files_changed`: `file_path`, `change_type`, and `reason`
- `pseudo_diff`: `file_path`, `before`, `after`, and `notes`
- `test_plan`, `risk_review`, and `reviewer_questions`
- `merge_readiness_score` and `merge_readiness_reason`

Readiness starts at 70; missing context, failed or safety-skipped tests, and
critic warnings lower it. Passed tests increase it. The result is clamped to
0–100. This is planning evidence, never approval to merge; prior test results do
not validate a change that has not been implemented.

See [the simulator reference](pr_simulator.md) for the exact scoring rules,
request-specific behavior, API examples, and limitations.

## UI and exports

Upload or select a repository and index it before asking. The UI displays the
workflow report and **Agentic PR Simulation**, including expandable pseudo-diffs,
review lists, and the score's explanation. **Simulation only (skip test execution)**
can be enabled to prevent tests even when a question asks to run them.

**Download Markdown report** exports the final answer, plan, context sources,
issue draft, available test results or analysis, critique, and simulation.
**Download simulated PR (JSON)** exports the simulation's structured fields.

## Operational notes

- `AGENTOPS_DISABLE_LANGGRAPH=1` forces the plain Python fallback.
- The simulator itself has no file-writing, subprocess, network, or Git tooling.
- The default API workflow needs no API keys or paid services.
- Optional LLM behavior elsewhere in the project remains separate; the existing
  simulation-only mode disables supplied LLM clients.
- Application memory writes are separate from uploaded repository contents.
