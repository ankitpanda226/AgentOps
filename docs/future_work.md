# Future Work

## MCP Server

Expose AgentOps Copilot capabilities through an MCP server so IDEs and agent runtimes can call repository search, memory, evaluation, and issue drafting tools through a standard protocol.

## Real GitHub PR Creation

Extend the GitHub tool layer from issue creation to branch, commit, pull request, and review workflows. This should include explicit user approval before any write action.

## Streamlit or React Dashboard

Add a lightweight UI for indexing repositories, asking questions, viewing retrieved context, reviewing issue drafts, inspecting memory, and running evals.

## Multi-Repo Indexing

Support multiple repository indexes with namespaced vector collections and metadata filters. This would let a user ask questions across services while preserving source attribution.

## Docker Deployment

Add a production-ready Dockerfile and deployment compose setup with mounted persistence for SQLite and ChromaDB.

## Human-In-The-Loop Approval

Add approval checkpoints before file writes, test execution in sensitive paths, GitHub issue creation, PR creation, and other side-effecting operations.

## Additional Ideas

- Streaming responses for long-running workflows.
- Richer semantic embeddings.
- Latency and cost tracking.
- Role-specific agent prompts.
- Retrieval accuracy evals over fixture repositories.
- Auth and rate limiting for hosted API use.
