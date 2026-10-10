# Architecture

## 1. Overview

AgentOps Copilot is a local-first multi-agent assistant for developer workflow automation. It combines a FastAPI backend, deterministic rule-based agents, repository retrieval, safe tool wrappers, SQLite memory, optional LangGraph orchestration, and an offline evaluation suite.

The current implementation does not require paid APIs. It runs with deterministic local behavior by default, while leaving extension points for OpenAI-compatible LLMs and richer embedding providers.

```text
                         +----------------------+
                         |      FastAPI API      |
                         | /health /index /ask  |
                         |      /run-tests      |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |   SupervisorAgent    |
                         |  LangGraph workflow  |
                         +----------+-----------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
 +----------------+        +----------------+        +----------------+
 |  PlannerAgent  |        |    RAGAgent    |        |   TestAgent    |
 | structured plan|        | context search |        | pytest runner  |
 +----------------+        +-------+--------+        +----------------+
                                   |
                                   v
                         +----------------------+
                         | VectorStore / Chroma |
                         | in-memory fallback   |
                         +----------+-----------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
 +----------------+        +----------------+        +----------------+
 |   DocsAgent    |        |  CriticAgent   |        |  MemoryStore   |
 | issue draft    |        | output review  |        | SQLite history |
 +----------------+        +----------------+        +----------------+
```

## 2. Core Components

- `app/`: FastAPI entrypoint, Pydantic request/response schemas, configuration, and LLM abstraction.
- `agents/`: Planner, RAG, code inspection, test execution, documentation, critique, supervisor, and graph orchestration modules.
- `rag/`: File chunking, repository indexing, retrieval, and vector storage.
- `tools/`: Safe local wrappers for file reads/writes, repository search, pytest execution, and GitHub issue helper space.
- `memory/`: SQLite schema and `MemoryStore` for task, decision, and tool-call persistence.
- `evals/`: Deterministic benchmark tasks, metrics, runner, and generated results.
- `tests/`: Unit and integration coverage for major modules.

## 3. Agent Architecture

The agent layer is intentionally rule-based first:

- `PlannerAgent` creates a structured plan with goal, steps, needed tools, risks, and success criteria.
- `RAGAgent` retrieves relevant chunks from any object that implements `search(query, k)`.
- `CodeAgent` inspects files using the file tool layer and returns per-file success/error records.
- `TestAgent` runs pytest through a subprocess wrapper.
- `DocsAgent` creates deterministic GitHub issue drafts.
- `CriticAgent` checks for missing plan/context/tests, vague answers, and unsupported claims.
- `SupervisorAgent` preserves the public orchestration interface and delegates workflow execution to `agents.graph.run_agent_workflow`.

LLM use is optional. `app.llm.MockLLM` is deterministic and local. `OpenAICompatibleLLM` only calls the official OpenAI SDK when an API key and SDK are available; otherwise it safely falls back to mock behavior.

## 4. RAG Pipeline

The RAG pipeline has three stages:

1. `chunk_file` reads UTF-8 text files and creates chunks with `file_path`, `chunk_id`, and `text`.
2. `index_repository` walks supported file types: `.py`, `.md`, `.txt`, `.json`, `.yaml`, `.yml`.
3. `VectorStore.search` retrieves relevant chunks for a query.

Ignored directories include `.git`, `__pycache__`, `.venv`, `node_modules`, and `.pytest_cache`.

The vector store uses a deterministic hashed local embedding provider by default. ChromaDB can be used when available, but tests can run against the in-memory fallback with no external services.

## 5. Memory Layer

`MemoryStore` persists workflow history in SQLite:

- `tasks`: user request, plan, final answer, creation timestamp.
- `decisions`: task-linked decision and reason records.
- `tool_calls`: task-linked tool name, input, output, success flag, and timestamp.

Timestamps are stored in UTC ISO format. Foreign keys are enabled for every SQLite connection. Tests use `tmp_path` databases so project-root data is not polluted.

## 6. Tool-Use Layer

The tool layer wraps local developer actions behind predictable functions:

- `read_file`: reads UTF-8 text with truncation support.
- `write_file`: creates parent directories and writes UTF-8 text.
- `list_files`: recursively lists files with extension filters and ignored directories.
- `safe_path_check`: prevents path traversal by resolving paths.
- `search_text`: performs case-insensitive repository text search.
- `run_pytest`: executes pytest and returns structured stdout/stderr/exit data.

These tools are deterministic and do not require network access.

## 7. LangGraph Orchestration

`agents/graph.py` defines `AgentGraphState` and builds a workflow with these nodes:

- `plan_node`
- `retrieve_context_node`
- `generate_issue_node`
- `optional_test_node`
- `critique_node`
- `finalize_node`

When LangGraph is installed, the project uses `StateGraph`. If LangGraph is unavailable, the same node implementations run through a deterministic fallback workflow. `AGENTOPS_DISABLE_LANGGRAPH=1` can force the fallback, which is useful for offline evaluations.

## 8. Evaluation Suite

The evaluation suite uses `evals/tasks.jsonl` with 10 representative developer workflow tasks. `evals/run_eval.py` runs each task through the deterministic workflow and writes `evals/results.json`.

Metrics include:

- Keyword coverage.
- Required output field score.
- Tool coverage.
- Aggregate score.

This gives a fast regression signal without requiring LLM calls, API keys, or external services.

## 9. Safety and Reliability

Safety is handled through conservative defaults:

- Local-first behavior with no required paid APIs.
- Mock LLM by default.
- Safe path checks for file access.
- Ignored directories during repository walks.
- Structured tool results instead of free-form side effects.
- Persistent memory with foreign-key constraints.
- Deterministic tests and evals.

The critic layer also flags missing context, missing tests for bug/test requests, vague final answers, and unsupported claims.

## 10. Limitations and Future Work

Current limitations:

- Agents are rule-based, so reasoning quality is intentionally simple.
- GitHub issue creation is a draft generator, not a live GitHub API integration.
- The default embedding model is a deterministic local hash embedding, not semantic-grade retrieval.
- ChromaDB integration is intentionally defensive and falls back in-memory when unavailable.
- Safety checks are lightweight and should be hardened before untrusted multi-user deployment.

Future work:

- Add real LLM planning and response synthesis behind `BaseLLM`.
- Add richer embedding providers through the embedding abstraction.
- Add authenticated GitHub issue creation.
- Add streaming API responses.
- Add a Streamlit or web UI.
- Expand evals with retrieval accuracy, latency tracking, and hallucination checks.
