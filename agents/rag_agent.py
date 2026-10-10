"""Rule-based RAG agent."""

from typing import Protocol


class SearchableVectorStore(Protocol):
    """Protocol for vector stores used by the RAG agent."""

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Search for relevant context chunks."""


class RAGAgent:
    """Retrieve context and produce deterministic retrieval summaries."""

    def __init__(self, vector_store: SearchableVectorStore) -> None:
        """Create a RAG agent backed by a searchable vector store."""
        self.vector_store = vector_store

    def answer_with_context(self, query: str, k: int = 5) -> dict:
        """Return retrieved context, source paths, and a deterministic answer."""
        context = self.vector_store.search(query, k=k)
        sources = [
            str(item["file_path"])
            for item in context
            if item.get("file_path") is not None
        ]
        return {
            "answer": f"Retrieved {len(context)} relevant context chunks for: {query}",
            "context": context,
            "sources": list(dict.fromkeys(sources)),
        }
