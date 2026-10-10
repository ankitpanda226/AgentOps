"""Vector store abstraction with a local ChromaDB backend and fallback search."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol
from uuid import uuid4

IMPLEMENTATION_QUERY_TERMS = {
    "implementation",
    "repo",
    "code",
    "api",
    "authentication",
    "auth",
    "feature",
    "architecture",
    "endpoint",
}
IMPLEMENTATION_PATH_PREFIXES = ("app/", "agents/", "tools/", "rag/", "memory/")
BUG_TEST_QUERY_TERMS = {"bug", "test", "pytest", "failure", "failing", "error"}
BUG_TEST_PATH_PREFIXES = ("tests/", "tools/test_runner.py", "app/")
DOC_QUERY_TERMS = {"docs", "documentation", "readme", "workflow"}
TOOL_QUERY_TERMS = {"tool", "tools", "integration", "calling", "use"}
PROMPT_QUERY_TERMS = {"prompt", "prompts", "prompting"}
TOOL_PATH_PATTERNS = (
    "tools/",
    "/tools/",
    "/tools/base.py",
    "/tools/simple.py",
    "/tools/structured.py",
    "tools/base.py",
    "tools/simple.py",
    "tools/structured.py",
    "langchain_core/tools",
    "toolkits",
)
PROMPT_PATH_PATTERNS = (
    "/prompt.py",
    "prompt.py",
    "prompts/",
    "conversational/prompt",
    "conversational_chat/prompt",
)
BUG_TOOL_IMPLEMENTATION_PATH_PATTERNS = (
    "langchain_core/tools/base.py",
    "langchain_core/tools/simple.py",
    "langchain_core/tools/convert.py",
    "langchain_core/tools/render.py",
    "tools/base.py",
    "tools/simple.py",
    "tools/convert.py",
    "tools/render.py",
    "tool_calling_agent",
    "agents/agent.py",
    "agents/openai_assistant/base.py",
)
UNRELATED_BUG_TOOL_TEST_PATH_PATTERNS = (
    "tests/unit_tests/output_parsers",
    "tests/unit_tests/load",
    "tests/unit_tests/_api",
    "test_serializable.py",
    "test_list_parser.py",
    "test_deprecation.py",
)
TEST_FILE_QUERY_PHRASES = (
    "failing test",
    "test failure",
    "test file",
    "test files",
    "pytest failure",
)


class EmbeddingProvider(Protocol):
    """Interface for embedding providers used by vector stores."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector embedding per input text."""


class HashEmbeddingProvider:
    """Deterministic local embedding provider based on hashed token counts."""

    def __init__(self, dimensions: int = 256) -> None:
        """Create a hashed bag-of-words embedding provider."""
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts without external services or network access."""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|\d+", text.lower())
        vector = [0.0] * self.dimensions
        counts = Counter(tokens)

        for token, count in counts.items():
            vector[hash(token) % self.dimensions] += float(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class VectorStore:
    """Store and search embedded document chunks.

    The class uses ChromaDB when available and healthy. If ChromaDB is missing
    or initialization fails, it falls back to deterministic in-memory cosine
    search, which keeps tests and local development free from paid APIs.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        persist_dir: str | None = None,
        collection_name: str = "agentops_copilot",
        use_chroma: bool = True,
    ) -> None:
        """Initialize the vector store."""
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self._documents: list[dict] = []
        self._vectors: list[list[float]] = []
        self._collection = None
        self._client = None
        self._collection_name = collection_name

        if use_chroma:
            self._collection = self._init_chroma(persist_dir, collection_name)

    def add_documents(self, documents: list[dict]) -> None:
        """Add document chunks to the vector store."""
        if not documents:
            return

        texts = [str(document["text"]) for document in documents]
        vectors = self.embedding_provider.embed(texts)

        if self._collection is not None:
            ids = [self._document_id(document) for document in documents]
            metadatas = [
                {
                    "file_path": str(document.get("file_path", "")),
                    "chunk_id": int(document.get("chunk_id", 0)),
                }
                for document in documents
            ]
            try:
                self._collection.upsert(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas,
                    embeddings=vectors,
                )
                return
            except Exception:
                self._collection = None

        self._documents.extend(dict(document) for document in documents)
        self._vectors.extend(vectors)

    def reset(self) -> None:
        """Clear all indexed documents from the vector store."""
        self._documents.clear()
        self._vectors.clear()

        if self._collection is None or self._client is None:
            return

        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass

        try:
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name
            )
        except Exception:
            self._collection = None

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return the most relevant chunks for a query."""
        if k <= 0:
            return []

        candidate_k = max(k * 8, 40)
        query_vector = self.embedding_provider.embed([query])[0]

        if self._collection is not None:
            try:
                result = self._collection.query(
                    query_embeddings=[query_vector],
                    n_results=candidate_k,
                    include=["documents", "metadatas", "distances"],
                )
                return rank_results(query, self._format_chroma_results(result))[:k]
            except Exception:
                self._collection = None

        scored = [
            (self._cosine_similarity(query_vector, vector), document)
            for document, vector in zip(self._documents, self._vectors)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [
            {
                "file_path": document.get("file_path"),
                "chunk_id": document.get("chunk_id"),
                "text": document.get("text"),
                "score": score,
            }
            for score, document in scored[:candidate_k]
        ]
        return rank_results(query, results)[:k]

    def _init_chroma(self, persist_dir: str | None, collection_name: str):
        try:
            import chromadb
        except Exception:
            return None

        try:
            if persist_dir:
                client = chromadb.PersistentClient(path=persist_dir)
            else:
                client = chromadb.Client()
            self._client = client
            return client.get_or_create_collection(name=collection_name)
        except Exception:
            return None

    def _document_id(self, document: dict) -> str:
        file_path = document.get("file_path")
        chunk_id = document.get("chunk_id")
        if file_path is None or chunk_id is None:
            return str(uuid4())
        return f"{file_path}:{chunk_id}"

    def _format_chroma_results(self, result: dict) -> list[dict]:
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        formatted: list[dict] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            formatted.append(
                {
                    "file_path": metadata.get("file_path"),
                    "chunk_id": metadata.get("chunk_id"),
                    "text": text,
                    "score": 1.0 / (1.0 + float(distance)),
                }
            )
        return formatted

    def _cosine_similarity(
        self, left: list[float], right: list[float]
    ) -> float:
        return sum(left_value * right_value for left_value, right_value in zip(left, right))


def rank_results(query: str, results: list[dict]) -> list[dict]:
    """Rerank retrieval results with deterministic path-aware boosts."""
    query_terms = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|\d+", query.lower()))
    implementation_query = bool(query_terms & IMPLEMENTATION_QUERY_TERMS)
    bug_test_query = bool(query_terms & BUG_TEST_QUERY_TERMS)
    docs_query = bool(query_terms & DOC_QUERY_TERMS)
    tool_query = _is_tool_query(query, query_terms)
    prompt_query = bool(query_terms & PROMPT_QUERY_TERMS)
    bug_tool_investigation_query = _is_bug_tool_investigation_query(
        query, query_terms
    )
    explicit_test_file_query = _is_explicit_test_file_query(query)

    reranked: list[dict] = []
    for index, result in enumerate(results):
        ranked_result = dict(result)
        path = _normalize_path(str(ranked_result.get("file_path", "")))
        rerank_score = float(ranked_result.get("score", 0.0))

        if implementation_query and path.startswith(IMPLEMENTATION_PATH_PREFIXES):
            rerank_score += 0.35
        if tool_query and not prompt_query and _contains_any(path, TOOL_PATH_PATTERNS):
            rerank_score += 0.80
        if tool_query and path.startswith("agents/"):
            rerank_score += 0.20
        if bug_tool_investigation_query and _contains_any(
            path, BUG_TOOL_IMPLEMENTATION_PATH_PATTERNS
        ):
            rerank_score += 1.20
        if (
            bug_tool_investigation_query
            and path.startswith("tests/")
            and not explicit_test_file_query
        ):
            rerank_score -= 0.35
        if bug_tool_investigation_query and _contains_any(
            path, UNRELATED_BUG_TOOL_TEST_PATH_PATTERNS
        ):
            rerank_score -= 1.00
        if prompt_query and _contains_any(path, PROMPT_PATH_PATTERNS):
            rerank_score += 0.50
        elif not prompt_query and _contains_any(path, PROMPT_PATH_PATTERNS):
            rerank_score -= 0.30
        if bug_test_query and path.startswith(BUG_TEST_PATH_PREFIXES):
            rerank_score += 0.35
        if not docs_query and (path.startswith("docs/") or path == "readme.md"):
            rerank_score -= 0.20
        if implementation_query and not bug_test_query and path.startswith("tests/"):
            rerank_score -= 0.15

        ranked_result["rerank_score"] = rerank_score
        ranked_result["_original_rank"] = index
        reranked.append(ranked_result)

    reranked.sort(
        key=lambda item: (item["rerank_score"], float(item.get("score", 0.0)), -item["_original_rank"]),
        reverse=True,
    )
    for result in reranked:
        result.pop("_original_rank", None)
    return reranked


def _is_tool_query(query: str, query_terms: set[str]) -> bool:
    normalized_query = query.lower()
    return bool(query_terms & TOOL_QUERY_TERMS) or any(
        phrase in normalized_query
        for phrase in ("tool integration", "tool calling", "tool use")
    )


def _is_bug_tool_investigation_query(query: str, query_terms: set[str]) -> bool:
    normalized_query = query.lower()
    has_bug_or_investigation = bool({"bug", "investigate"} & query_terms)
    has_tool_focus = "tool" in query_terms or "tool execution" in normalized_query
    has_without_tests = "without running tests" in normalized_query
    return (has_bug_or_investigation and has_tool_focus) or (
        has_tool_focus and has_without_tests
    )


def _is_explicit_test_file_query(query: str) -> bool:
    normalized_query = query.lower()
    return any(phrase in normalized_query for phrase in TEST_FILE_QUERY_PHRASES)


def _contains_any(path: str, patterns: tuple[str, ...]) -> bool:
    slash_path = f"/{path}"
    return any(pattern in path or pattern in slash_path for pattern in patterns)


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./").lower()
    for prefix in ("/app/", "/agents/", "/tools/", "/rag/", "/memory/", "/docs/", "/tests/"):
        if prefix in normalized:
            return normalized[normalized.index(prefix) + 1 :]
    if normalized.endswith("/readme.md"):
        return "readme.md"
    return normalized
