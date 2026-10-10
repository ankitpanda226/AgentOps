# Demo Script

## 2-Minute Demo

1. Open with the problem.

   "AgentOps Copilot is a local-first multi-agent assistant for developer workflows. It can index a repo, retrieve context, plan work, draft GitHub issues, run tests, critique outputs, and store memory."

2. Show setup.

   ```bash
   make install
   make test
   ```

3. Start the API.

   ```bash
   make run
   ```

4. Index the project.

   ```bash
   curl -X POST http://127.0.0.1:8000/index \
     -H "Content-Type: application/json" \
     -d '{"repo_path": "."}'
   ```

5. Ask a repo question.

   ```bash
   curl -X POST http://127.0.0.1:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Explain how the RAG pipeline works"}'
   ```

6. Close with the key point.

   "The important part is that it is deterministic and local by default, but the LLM and vector store layers are swappable."

## 5-Minute Demo

1. Show the architecture diagram in `README.md`.

2. Run tests.

   ```bash
   make test
   ```

3. Run evals.

   ```bash
   make eval
   ```

4. Start the API.

   ```bash
   make run
   ```

5. Health check.

   ```bash
   curl http://127.0.0.1:8000/health
   ```

6. Index the repo.

   ```bash
   curl -X POST http://127.0.0.1:8000/index \
     -H "Content-Type: application/json" \
     -d '{"repo_path": "."}'
   ```

7. Ask for implementation planning.

   ```bash
   curl -X POST http://127.0.0.1:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Create an implementation plan for adding GitHub PR support"}'
   ```

8. Run a test request.

   ```bash
   curl -X POST http://127.0.0.1:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Analyze a bug and run tests", "repo_path": "tests"}'
   ```

9. Point out persistent memory.

   The supervisor saves tasks, decisions, tool calls, and final answers when a memory store is configured.

10. Close with extensibility.

   The project is ready for real LLM calls, richer embeddings, GitHub write actions, and a UI.

## Interview Talking Points

- Local-first architecture avoids API keys during demos and CI.
- `MockLLM` makes tests deterministic while preserving an LLM integration boundary.
- LangGraph is supported without making it a hard runtime dependency.
- RAG indexing and vector search are behind small abstractions.
- SQLite memory creates an audit trail for prior tasks and decisions.
- Tool calls return structured results, which makes critique and evaluation easier.
- The eval suite checks output shape, tool routing, and keyword coverage without network calls.
