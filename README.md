# AgentOps Copilot

[![Tests](https://img.shields.io/badge/tests-passing_placeholder-brightgreen)](#running-tests)

Local-first multi-agent assistant for developer workflow automation.

AgentOps Copilot combines FastAPI, rule-based agents, repository RAG, local developer tools, SQLite memory, LangGraph-compatible orchestration, deterministic evaluation, and optional OpenAI-compatible LLM integration. It runs locally with `MockLLM` behavior by default, so demos and tests do not require API keys.

## Why This Project Matters

Modern developer agents need more than chat. They need repo context, safe tool use, memory, evaluation, and clear orchestration. AgentOps Copilot demonstrates those production building blocks in a compact local project: deterministic by default, modular enough to extend, and honest about where real LLM and GitHub write integrations should plug in.

## Features

- FastAPI backend with `/health`, `/index`, `/ask`, and `/run-tests`.
- Rule-based planner, RAG, docs, test, code, critic, and supervisor agents.
- LangGraph orchestration with deterministic fallback.
- Agentic PR Simulator with evidence-linked candidate changes, conceptual diffs,
  test plans, risk review, reviewer questions, and explained merge readiness.
- Local RAG over `.py`, `.md`, `.txt`, `.json`, `.yaml`, and `.yml` files.
- ChromaDB vector store support with in-memory fallback.
- Deterministic local hash embeddings by default.
- Safe file tools, repository search, pytest execution, and GitHub issue drafts.
- SQLite memory for tasks, decisions, and tool calls.
- Mock LLM default with optional OpenAI-compatible integration.
- Offline evaluation suite with JSONL tasks and metric scoring.
- Makefile, Black/Ruff config, docs, and tests for GitHub-ready submission.

## Architecture

```text
                 +-----------------------------+
                 |          FastAPI API         |
                 | /index /ask /run-tests       |
                 +--------------+--------------+
                                |
                                v
                 +-----------------------------+
                 |       SupervisorAgent        |
                 | LangGraph or fallback graph  |
                 +--------------+--------------+
                                |
       +------------------------+------------------------+
       |                        |                        |
       v                        v                        v
+--------------+        +---------------+        +---------------+
| PlannerAgent |        |   RAGAgent    |        |   TestAgent   |
| plan + tools |        | retrieve ctx  |        | run pytest    |
+--------------+        +-------+-------+        +---------------+
                               |
                               v
                     +-------------------+
                     | VectorStore/RAG   |
                     | Chroma or memory  |
                     +---------+---------+
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
+--------------+        +--------------+        +---------------+
|  DocsAgent   |        | CriticAgent  |        |  MemoryStore  |
| issue draft  |        | review       |        | SQLite        |
+--------------+        +--------------+        +---------------+
```

## Quickstart

```bash
git clone <your-repo-url>
cd agentops-copilot
python -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
make test
```

Run the API:

```bash
make run
```

Open the interactive docs:

```text
http://127.0.0.1:8000/docs
```

Start the Streamlit frontend:

```bash
python -m uvicorn app.main:app --reload --port 8010
streamlit run ui/streamlit_app.py
```

## Configuration

The project is local-first. No API key is needed for tests, evals, indexing, or default agent workflow execution.

Optional OpenAI-compatible LLM configuration:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

If `OPENAI_API_KEY` is missing or the OpenAI SDK is unavailable, the system falls back to deterministic `MockLLM` behavior.

## Demo Commands

```bash
make install
make test
make eval
make run
```

Backend plus UI demo:

```bash
python -m uvicorn app.main:app --reload --port 8010
streamlit run ui/streamlit_app.py
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "."}'
```

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain how the RAG pipeline works"}'
```

## Analyze an Uploaded Repository Zip

Start the backend on the frontend default port:

```bash
python -m uvicorn app.main:app --reload --port 8010
```

Start the Streamlit frontend:

```bash
streamlit run ui/streamlit_app.py
```

In the sidebar:

1. Select `Upload repo zip`.
2. Choose a `.zip` file containing a repository.
3. Click `Upload Repository`.
4. Click `Index Repository`.
5. Ask questions in the main text area.

The backend extracts uploaded repositories into `uploads/repos/<repo_id>/`, returns a `repo_id`, and the frontend uses that `repo_id` for indexing and questions.

For large repositories, exclude generated folders before zipping, especially `node_modules`, `.venv`, `build`, `dist`, `.pytest_cache`, and dependency caches.

## Human-Friendly Workflow Reports

AgentOps Copilot returns a Markdown `final_answer` called the AgentOps Workflow Report. Instead of a generic summary, the report converts retrieved repository context into a structured developer workflow:

- request summary
- relevant files and why they matter
- recommended developer workflow
- step-by-step implementation plan
- testing and validation plan
- risks and safety checks
- GitHub issue draft summary
- final next actions

The report is deterministic and local-first. It is generated from the planner output, retrieved context, issue draft, optional test result, and critic output without requiring external APIs.

## Agentic PR Simulator

Every `/ask` workflow now creates a safe simulated pull-request plan after the
plan, retrieved context, issue draft, optional test result, and critique are ready.
The `pr_simulation` response contains `pr_title`, `pr_summary`, `files_changed`,
`pseudo_diff`, `test_plan`, `risk_review`, `reviewer_questions`,
`merge_readiness_score`, and `merge_readiness_reason`. Existing API fields remain
available, and older clients can omit the new optional response field.

The simulator proposes changes for tools, auth/middleware, APIs, bugs, and docs.
It prioritizes relevant retrieved paths, deduplicates candidates, and produces
conceptual before/after summaries. It does not edit files, execute tests, create
commits, open real PRs, or call external APIs.

After indexing, inspect **Agentic PR Simulation** in the UI. Download the complete
**Markdown report** or the simulation JSON. Enable **Simulation only (skip test
execution)**, or send `"simulate_pr": true`, to prevent workflow tests even when
your question asks to run them. This flag is not required to receive a simulation.

Readiness starts at 70: missing context subtracts 25, failed tests subtract 15,
safety-skipped tests subtract 10, critic warnings subtract 10, and passed tests
add 10. Scores are clamped to 0–100 and explained. They are planning heuristics,
not approval to merge or proof that the proposed change works.

See [PR simulator usage, response fields, and scoring](docs/pr_simulator.md)
and [the workflow lifecycle](docs/workflow.md).

## Large Repository Uploads

The Streamlit frontend is configured for zip uploads up to 1000 MB by default through `.streamlit/config.toml`. This is local-only: uploading and indexing repositories does not create cloud or API costs. Large repositories can still be slow because extraction and indexing use your local CPU, RAM, and disk.

For best results, remove heavy generated folders before creating the zip:

- `.git`
- `node_modules`
- `.venv`
- `dist`
- `build`
- `.next`
- `__pycache__`
- `target`
- `coverage`

Example:

```bash
zip -r my-repo.zip my-repo \
  -x "*/.git/*" "*/node_modules/*" "*/.venv/*" "*/dist/*" "*/build/*" "*/.next/*" "*/__pycache__/*" "*/target/*" "*/coverage/*"
```

## Example API Outputs

Health:

```json
{"status":"ok"}
```

Index:

```json
{"indexed_chunks":123}
```

Ask:

```json
{
  "task_id": 1,
  "plan": {
    "goal": "Explain how the RAG pipeline works",
    "steps": ["Analyze the request and identify the desired outcome."]
  },
  "context": [
    {
      "file_path": "rag/indexer.py",
      "chunk_id": 0,
      "text": "..."
    }
  ],
  "issue_draft": {
    "title": "Explain how the RAG pipeline works",
    "body": "...",
    "acceptance_criteria": ["Answer is grounded in retrieved context or inspected files."]
  },
  "test_result": null,
  "critique": {
    "passed": true,
    "warnings": [],
    "missing_items": []
  },
  "final_answer": "Planned goal: Explain how the RAG pipeline works..."
}
```

Run tests:

```json
{
  "success": true,
  "exit_code": 0,
  "stdout": "...",
  "stderr": ""
}
```

## Running Tests

```bash
make test
```

Equivalent:

```bash
python -m pytest
```

## Running the Streamlit UI

Start the backend on the UI default port:

```bash
python -m uvicorn app.main:app --reload --port 8010
```

Start the frontend in another terminal:

```bash
streamlit run ui/streamlit_app.py
```

The UI lets you index a repository, ask the agent a question, and inspect the final answer, plan, retrieved context sources, issue draft, test result, and critique.

## Running Evals

```bash
make eval
```

The runner loads `evals/tasks.jsonl`, executes deterministic workflows, computes metrics, prints a summary table, and writes `evals/results.json`.

## Makefile Commands

```text
make install  Install Python dependencies
make test     Run pytest
make run      Start FastAPI with reload
make eval     Run deterministic evals
make clean    Remove caches and generated local artifacts
```

## Project Structure

```text
app/      FastAPI app, settings, schemas, and LLM abstraction
agents/   Planner, RAG, code, test, docs, critic, supervisor, graph
tools/    File tools, repo search, pytest runner, GitHub helper space
rag/      Chunking, indexing, retrieval, and vector store abstraction
memory/   SQLite schema and persistent memory store
prompts/  Prompt templates for future LLM-backed behavior
evals/    JSONL tasks, metrics, runner, and generated results
tests/    Unit and integration tests
docs/     Architecture, workflow, demo, future work, and evaluation docs
ui/       Streamlit frontend
```

## Resume Bullets

- Built a local-first multi-agent developer assistant with FastAPI, LangGraph-compatible orchestration, RAG, tool use, SQLite memory, and deterministic evaluations.
- Implemented modular agents for planning, retrieval, testing, issue drafting, critique, and supervision with optional OpenAI-compatible LLM integration.
- Designed a ChromaDB-backed vector store abstraction with deterministic local embeddings and in-memory fallback for reliable tests.
- Added a persistent memory layer for tasks, decisions, and tool calls using SQLite with UTC timestamps and foreign-key enforcement.
- Created an offline evaluation harness with JSONL benchmarks, field/tool/keyword metrics, and repeatable local scoring.
- Packaged the project for GitHub with Makefile commands, Black/Ruff configuration, polished docs, and local-first secret-safe defaults.

## Roadmap

- Add real LLM response synthesis behind the `BaseLLM` interface.
- Add semantic embedding providers through the vector store abstraction.
- Add authenticated GitHub issue and PR creation with human approval.
- Add an MCP server for IDE and agent runtime integration.
- Add streaming responses for long-running workflows.
- Add richer safety policies around file writes and command execution.
- Add a Streamlit or React dashboard.
- Expand evals with retrieval precision, latency, and hallucination-risk scoring.

## Limitations

- Current agents are rule-based and deterministic, not deeply reasoning LLM agents.
- GitHub support currently creates safe drafts and only calls the API when a token is explicitly passed.
- Default hash embeddings are useful for tests but not as strong as semantic embeddings.
- LangGraph is optional and falls back to a plain Python workflow when unavailable.
- The API is local-development oriented and does not include auth, rate limiting, or multi-tenant controls.
