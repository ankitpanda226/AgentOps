"""Convenience functions for retrieving RAG context."""

from rag.vector_store import VectorStore


def retrieve_context(
    query: str, vector_store: VectorStore, k: int = 5
) -> list[dict]:
    """Retrieve relevant chunks for a query from a vector store."""
    return vector_store.search(query, k=k)
