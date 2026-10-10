"""Tests for the RAG chunking and retrieval pipeline."""

from pathlib import Path

from rag.chunker import chunk_file, chunk_text
from rag.indexer import index_repository
from rag.retriever import retrieve_context
from rag.vector_store import VectorStore


def test_chunk_text_creates_overlapping_chunks() -> None:
    """Text chunking should preserve the requested overlap."""
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_text(text, chunk_size=10, overlap=3)

    assert chunks == ["abcdefghij", "hijklmnopq", "opqrstuvwx", "vwxyz"]
    assert chunks[0][-3:] == chunks[1][:3]


def test_chunk_file_returns_metadata(tmp_path: Path) -> None:
    """File chunking should include file path, chunk id, and text."""
    source = tmp_path / "notes.md"
    source.write_text("alpha beta gamma", encoding="utf-8")

    chunks = chunk_file(str(source))

    assert chunks == [
        {
            "file_path": str(source),
            "chunk_id": 0,
            "text": "alpha beta gamma",
        }
    ]


def test_index_repository_indexes_supported_files(tmp_path: Path) -> None:
    """Repository indexing should include supported files and skip ignored paths."""
    (tmp_path / "app.py").write_text("def useful_function(): pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("project documentation", encoding="utf-8")
    (tmp_path / "image.png").write_text("not indexed", encoding="utf-8")
    ignored_dir = tmp_path / ".git"
    ignored_dir.mkdir()
    (ignored_dir / "config").write_text("not indexed", encoding="utf-8")
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "module.py").write_text("not indexed", encoding="utf-8")
    vector_store = VectorStore(use_chroma=False)

    indexed_count = index_repository(str(tmp_path), vector_store)

    assert indexed_count == 2
    assert indexed_count["indexed_chunks"] == 2
    assert indexed_count["indexed_files"] == 2
    results = vector_store.search("useful function", k=5)
    assert {result["file_path"] for result in results} == {
        str(tmp_path / "app.py"),
        str(tmp_path / "README.md"),
    }


def test_index_repository_skips_large_files(tmp_path: Path) -> None:
    """Repository indexing should skip files larger than the configured limit."""
    (tmp_path / "small.py").write_text("def small(): pass", encoding="utf-8")
    (tmp_path / "large.py").write_text("x" * 2048, encoding="utf-8")
    vector_store = VectorStore(use_chroma=False)

    result = index_repository(
        str(tmp_path),
        vector_store,
        max_file_size_kb=1,
    )

    assert result["indexed_files"] == 1
    assert result["indexed_chunks"] == 1
    assert result["skipped_large_files"] == 1
    assert result["skipped_files"] == 1
    assert vector_store.search("small", k=1)[0]["file_path"] == str(tmp_path / "small.py")


def test_index_repository_respects_max_files(tmp_path: Path) -> None:
    """Repository indexing should stop after max_files files."""
    (tmp_path / "a.py").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.py").write_text("beta", encoding="utf-8")
    (tmp_path / "c.py").write_text("gamma", encoding="utf-8")
    vector_store = VectorStore(use_chroma=False)

    result = index_repository(str(tmp_path), vector_store, max_files=2)

    assert result["indexed_files"] == 2
    assert result["indexed_chunks"] == 2
    assert len(vector_store.search("alpha beta gamma", k=10)) == 2


def test_retrieve_context_returns_relevant_chunks() -> None:
    """Retriever should return the most relevant indexed chunks."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "alpha.py",
                "chunk_id": 0,
                "text": "database migrations and sqlite memory store",
            },
            {
                "file_path": "beta.py",
                "chunk_id": 0,
                "text": "css layout and frontend button styles",
            },
        ]
    )

    results = retrieve_context("sqlite database memory", vector_store, k=1)

    assert len(results) == 1
    assert results[0]["file_path"] == "alpha.py"
    assert "sqlite memory" in results[0]["text"]


def test_vector_store_reset_clears_documents() -> None:
    """VectorStore.reset should remove previously indexed in-memory documents."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "a.py",
                "chunk_id": 0,
                "text": "alpha_unique",
            }
        ]
    )

    assert vector_store.search("alpha_unique", k=1)

    vector_store.reset()

    assert vector_store.search("alpha_unique", k=1) == []


def test_retrieval_prefers_source_files_for_api_query() -> None:
    """API queries should prefer implementation files over docs with similar text."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "docs/architecture.md",
                "chunk_id": 0,
                "text": "api endpoint implementation architecture",
            },
            {
                "file_path": "app/main.py",
                "chunk_id": 0,
                "text": "api endpoint implementation architecture",
            },
        ]
    )

    results = vector_store.search("api endpoint implementation", k=2)

    assert results[0]["file_path"] == "app/main.py"
    assert results[0]["rerank_score"] > results[1]["rerank_score"]


def test_retrieval_penalizes_docs_for_implementation_query() -> None:
    """Implementation queries should demote docs when source files are available."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "README.md",
                "chunk_id": 0,
                "text": "repo implementation code feature",
            },
            {
                "file_path": "agents/supervisor.py",
                "chunk_id": 0,
                "text": "repo implementation code feature",
            },
        ]
    )

    results = vector_store.search("repo implementation code feature", k=2)

    assert results[0]["file_path"] == "agents/supervisor.py"


def test_retrieval_allows_docs_for_documentation_query() -> None:
    """Documentation queries should not penalize documentation paths."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "docs/workflow.md",
                "chunk_id": 0,
                "text": "documentation workflow guide",
            },
            {
                "file_path": "app/main.py",
                "chunk_id": 0,
                "text": "api endpoint implementation",
            },
        ]
    )

    results = vector_store.search("documentation workflow guide", k=2)

    assert results[0]["file_path"] == "docs/workflow.md"


def test_search_reranks_more_than_top_k_candidates() -> None:
    """Search should rerank a larger candidate pool than the requested top k."""
    vector_store = VectorStore(use_chroma=False)
    documents = [
        {
            "file_path": f"agents/conversational/prompt_{index}.py",
            "chunk_id": 0,
            "text": "plan how to add a new tool integration",
        }
        for index in range(5)
    ]
    documents.append(
        {
            "file_path": "tools/base.py",
            "chunk_id": 0,
            "text": "plan how to add a new tool integration",
        }
    )
    vector_store.add_documents(documents)

    results = vector_store.search("Plan how to add a new tool integration", k=5)

    assert results[0]["file_path"] == "tools/base.py"
    assert "rerank_score" in results[0]


def test_tool_integration_query_prioritizes_core_tool_files_over_prompt_files() -> None:
    """Tool integration queries should rank core tool files over prompt files."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "agents/conversational/prompt.py",
                "chunk_id": 0,
                "text": "plan how to add a new tool integration",
            },
            {
                "file_path": "langchain_core/tools/base.py",
                "chunk_id": 0,
                "text": "plan how to add a new tool integration",
            },
            {
                "file_path": "tools/structured.py",
                "chunk_id": 0,
                "text": "plan how to add a new tool integration",
            },
        ]
    )

    results = vector_store.search("Plan how to add a new tool integration", k=3)

    assert results[0]["file_path"] in {
        "langchain_core/tools/base.py",
        "tools/structured.py",
    }
    assert results[-1]["file_path"] == "agents/conversational/prompt.py"


def test_prompt_query_does_not_penalize_prompt_files() -> None:
    """Prompt-specific queries should not penalize prompt files."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "prompts/planner_prompt.md",
                "chunk_id": 0,
                "text": "planner prompt for tool integration instructions",
            },
            {
                "file_path": "tools/base.py",
                "chunk_id": 0,
                "text": "tool base implementation interface",
            },
        ]
    )

    results = vector_store.search("planner prompt for tool integration", k=2)

    assert results[0]["file_path"] == "prompts/planner_prompt.md"


def test_bug_tool_investigation_prioritizes_tool_implementation_files() -> None:
    """Bug investigation queries should prefer core tool execution files."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "tests/unit_tests/output_parsers/test_list_parser.py",
                "chunk_id": 0,
                "text": "investigate bug tool execution without running tests parser",
            },
            {
                "file_path": "langchain_core/tools/base.py",
                "chunk_id": 0,
                "text": "investigate bug tool execution without running tests parser",
            },
            {
                "file_path": "agents/openai_assistant/base.py",
                "chunk_id": 0,
                "text": "investigate bug tool execution without running tests parser",
            },
        ]
    )

    results = vector_store.search(
        "Explain how you would investigate a bug in tool execution without running tests",
        k=3,
    )

    assert results[0]["file_path"] in {
        "langchain_core/tools/base.py",
        "agents/openai_assistant/base.py",
    }
    assert results[0]["rerank_score"] > results[-1]["rerank_score"]


def test_bug_tool_investigation_penalizes_unrelated_parser_tests() -> None:
    """Unrelated parser tests should rank below implementation files."""
    vector_store = VectorStore(use_chroma=False)
    vector_store.add_documents(
        [
            {
                "file_path": "tests/unit_tests/output_parsers/test_list_parser.py",
                "chunk_id": 0,
                "text": "bug investigate tool execution without running tests",
            },
            {
                "file_path": "tools/simple.py",
                "chunk_id": 0,
                "text": "bug investigate tool execution without running tests",
            },
            {
                "file_path": "tools/render.py",
                "chunk_id": 0,
                "text": "bug investigate tool execution without running tests",
            },
        ]
    )

    results = vector_store.search(
        "Explain how you would investigate a bug in tool execution without running tests",
        k=3,
    )

    assert results[-1]["file_path"] == "tests/unit_tests/output_parsers/test_list_parser.py"
