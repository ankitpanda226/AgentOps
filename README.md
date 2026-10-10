# AgentOps Copilot

A local-first multi-agent developer workflow platform that turns repository context
into implementation plans, workflow reports, GitHub-style issue drafts, and safe
simulated pull-request plans.

Built with FastAPI, Streamlit, repository RAG, LangGraph-style orchestration, and
SQLite memory. Default workflows are deterministic and require no API key.

## Features

- **Repository upload and indexing:** upload a ZIP or select a local path, then
  index source files into isolated repository context.
- **Repository RAG:** local chunking, deterministic hash embeddings, retrieval,
  and reranking over supported source and documentation files.
- **Multi-agent workflow:** planning, retrieval, issue drafting, optional testing,
  critique, PR simulation, and report generation.
- **Agentic PR Simulator:** candidate files, conceptual before/after summaries,
  test plans, risks, reviewer questions, and explained merge readiness.
- **Human-readable reports:** inspect evidence in Streamlit and download the
  complete Markdown report or simulation JSON.
- **Test safety:** honor requests to skip tests and block automatic broad test
  runs against uploaded repositories.
- **Local memory and evaluation:** SQLite task history, offline evals, and
  134 passing Pytest tests at the latest validation.

## Demo Preview

Screenshots will be added after the app is captured locally.

Recommended screenshots:

- Repository upload and indexing
- AgentOps Workflow Report
- Agentic PR Simulation
- Markdown report export

Expected paths:

- `docs/assets/screenshots/upload-and-index.png`
- `docs/assets/screenshots/workflow-report.png`
- `docs/assets/screenshots/pr-simulator.png`

## How to Run Locally

Use Python 3.11 or newer. Run commands from the repository root. The commands below
use macOS/Linux shell syntax; Windows Command Prompt alternatives are noted.
If your Python installation exposes `python3` instead of `python`, use it to
create the virtual environment.

### 1. Clone the repository

```bash
git clone https://github.com/ankitpanda226/AgentOps.git
cd AgentOps
```

### 2. Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

For Windows Command Prompt, activate with:

```bat
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

On Windows Command Prompt, use `copy .env.example .env`.
No API key is required for default local deterministic mode.

### 5. Run tests

```bash
python -m pytest
```

Expected at the latest validation:

```text
134 passed, 1 warning
```

The existing warning comes from LangGraph's dependency deprecation notice.

### 6. Run backend

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Keep this terminal running. The interactive API docs are at
[localhost:8010/docs](http://127.0.0.1:8010/docs).

### 7. Run frontend

In a second terminal, change into `AgentOps` and activate the same environment:

```bash
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

On Windows, use the activation command from step 2 before running Streamlit.

### 8. Use the app

Open the Streamlit URL printed in the terminal, usually
[localhost:8501](http://localhost:8501). Keep the sidebar API base URL set to
`http://127.0.0.1:8010`.

1. Select **Upload repo zip** and choose a repository ZIP.
2. Click **Upload Repository**.
3. Click **Index Repository** and wait for confirmation.
4. Enter the prompt below and click **Ask Agent**.

```text
Plan how to add a new tool integration to this repo.
```

## Demo Usage

Use a small repository with readable source files so indexing fits comfortably
into a short demo. The app also supports **Analyze local path**; choose a path
and index it before asking questions.

Inspect **Retrieved Context Sources**, the **AgentOps Workflow Report**, and the
**Issue Draft**. The report explains the request, relevant files, implementation
steps, validation plan, risks, and next actions. Review **Agentic PR Simulation**,
then use **Download Markdown report** to export the result.

Enable **Simulation only (skip test execution)** to prevent test execution even
if the question asks to run tests. This is useful for a predictable recording.
The simulator also appears in normal workflow responses.

For API-only usage after starting the backend:

```bash
curl -X POST http://127.0.0.1:8010/index \
  -H 'Content-Type: application/json' \
  -d '{"repo_path":"."}'

curl -X POST http://127.0.0.1:8010/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Plan how to add a new tool integration to this repo.","repo_path":".","simulate_pr":true}'
```

## Agentic PR Simulator

Every `/ask` workflow creates a safe simulated pull-request plan after planning,
retrieval, issue drafting, optional tests, and critique. It includes:

- PR title and summary
- Up to six deduplicated candidate files and reasons for each change
- Conceptual before/after summaries, not applicable patches
- Test plan, risk review, and reviewer questions
- Merge readiness score with an explanation

The simulator does not edit repository files, execute tests, create commits, open
real PRs, or call external APIs. Readiness starts at 70 and adjusts for missing
context, test evidence, and critic warnings. It is a planning heuristic, not
approval to merge or proof that the proposed change works.

See the [simulator reference](docs/pr_simulator.md) for the exact response fields,
scoring rules, and request-specific behavior.

## Architecture and Workflow

```text
Streamlit UI -> FastAPI -> SupervisorAgent
                              |
                              v
Plan -> Retrieve repo context -> Draft issue -> Optional tests
                                                    |
                                                    v
Report + Markdown export <- PR simulation <- Critique
           |
           v
     SQLite task memory
```

LangGraph orchestrates the agents when available; a deterministic Python fallback
runs the same workflow. The API uses local in-memory retrieval with hash embeddings
by default; the vector store abstraction also supports ChromaDB.

Agents are rule-based, and retrieved excerpts may be incomplete. Review proposed
changes before implementation. The API is intended for local development and does
not include production authentication or multi-tenant controls.

See [architecture](docs/architecture.md) and [workflow details](docs/workflow.md).

## Tests

Run the test command in [local setup, step 5](#5-run-tests) from an activated
virtual environment. The latest result is **134 passed, 1 warning**. Coverage
includes repository uploads and isolation, API behavior, agent routing, test
safety, PR simulation scoring, Markdown exports, and UI behavior.

The equivalent Makefile shortcut is `make test`.

## Evals

```bash
python evals/run_eval.py
```

The offline runner scores JSONL tasks for output fields, tool use, and keyword
coverage. It writes ignored output to `evals/results.json`. The latest run has
nine scores of 1.00 and one of 0.75: the latter expects pytest for a request that
does not explicitly ask to execute tests. Equivalent shortcut: `make eval`.

## Troubleshooting

- **Frontend cannot connect:** keep the backend running on port `8010` and check
  that the sidebar API base URL is `http://127.0.0.1:8010`.
- **No retrieved context:** upload and index the repository again. Confirm it
  contains supported files; default suffixes are `.py`, `.md`, `.txt`, `.json`,
  `.yaml`, and `.yml`.
- **Backend restarted:** uploaded repository IDs and the active index are held
  in memory. Upload the ZIP again and reindex, or select a local path and reindex.
- **Large upload:** remove `.git`, `node_modules`, `.venv`, `build`, `dist`,
  `__pycache__`, `target`, and `coverage` before making the ZIP. Large repos use
  local CPU, memory, and disk during extraction and indexing.
- **Uploaded-repository tests skipped:** this is intentional safety behavior
  (`exit_code: -2`). Use a targeted test path for deliberate validation in an
  isolated local checkout. The current `/ask` upload guard does not provide a
  targeted-path override; describing a path in the question does not bypass it.
- **Streamlit upload limit reached:** check `.streamlit/config.toml`. The current
  `server.maxUploadSize` is `1000` MB. Restart Streamlit after changing it.

## Docs

- [Agentic PR Simulator](docs/pr_simulator.md)
- [Workflow](docs/workflow.md)
- [Architecture](docs/architecture.md)
- [Uploaded repositories](docs/uploaded_repos.md)
- [Frontend guide](docs/frontend.md)
- [Evaluation report](docs/evaluation_report.md)
- [Future work](docs/future_work.md)
