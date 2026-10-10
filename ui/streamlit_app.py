"""Streamlit frontend for AgentOps Copilot."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import requests
import streamlit as st


# Streamlit may launch this script with only ui/ on its import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.report_export import build_markdown_export
from agents.pr_simulator_agent import SAFETY_NOTICE


DEFAULT_API_BASE_URL = "http://127.0.0.1:8010"


def post_json(api_base_url: str, endpoint: str, payload: dict[str, Any]) -> dict:
    """POST JSON to the backend and return the parsed response."""
    url = f"{api_base_url.rstrip('/')}{endpoint}"
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def upload_repo_zip(api_base_url: str, uploaded_file) -> dict:
    """Upload a repository zip file to the backend."""
    url = f"{api_base_url.rstrip('/')}/upload-repo"
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/zip",
        )
    }
    response = requests.post(url, files=files, timeout=120)
    response.raise_for_status()
    return response.json()


def get_repo_payload(mode: str, repo_path: str) -> dict[str, str | None]:
    """Return the repo selector payload for index and ask calls."""
    if mode == "Upload repo zip":
        repo_id = st.session_state.get("repo_id")
        return {"repo_id": repo_id} if repo_id else {}
    return {"repo_path": repo_path}


def render_context_sources(context: list[dict]) -> None:
    """Render retrieved context source summaries."""
    if not context:
        st.info("No context chunks returned.")
        return

    for item in context:
        file_path = item.get("file_path", "unknown")
        chunk_id = item.get("chunk_id", "unknown")
        score = item.get("rerank_score", item.get("score"))
        label = f"{file_path} | chunk {chunk_id}"
        if score is not None:
            label = f"{label} | score {float(score):.3f}"
        with st.expander(label):
            st.write(item.get("text", ""))


def render_agent_response(result: dict) -> None:
    """Render the structured /ask response."""
    st.subheader("Final Answer")
    st.markdown(result.get("final_answer", ""))

    st.download_button(
        "Download Markdown report",
        data=build_markdown_export(result),
        file_name="agentops-workflow-report.md",
        mime="text/markdown",
    )

    simulation = result.get("pr_simulation")
    if simulation:
        st.subheader("Agentic PR Simulation")
        st.info(SAFETY_NOTICE)
        st.markdown(f"**{simulation['pr_title']}**")
        st.write(simulation["pr_summary"])
        st.metric(
            "Merge readiness (planning heuristic)",
            f"{simulation['merge_readiness_score']}/100",
        )
        st.write(simulation["merge_readiness_reason"])
        st.markdown("**Files changed (proposed candidates)**")
        if simulation["files_changed"]:
            st.dataframe(simulation["files_changed"], hide_index=True)
        else:
            st.info("No candidate files: index relevant repository context first.")
        for diff in simulation["pseudo_diff"]:
            with st.expander(f"Pseudo-diff: {diff['file_path']}"):
                st.caption(diff["notes"])
                st.markdown("**Before**")
                st.code(diff["before"], language="text")
                st.markdown("**After (proposed)**")
                st.code(diff["after"], language="text")
        for title, key in (
            ("Test plan", "test_plan"),
            ("Risk review", "risk_review"),
            ("Reviewer questions", "reviewer_questions"),
        ):
            st.markdown(f"**{title}**")
            for item in simulation[key]:
                st.write(f"- {item}")
        st.download_button(
            "Download simulated PR (JSON)",
            data=json.dumps(simulation, indent=2),
            file_name="simulated-pr.json",
            mime="application/json",
        )

    st.subheader("Plan")
    st.json(result.get("plan", {}))

    st.subheader("Retrieved Context Sources")
    render_context_sources(result.get("context", []))

    st.subheader("Issue Draft")
    st.json(result.get("issue_draft", {}))

    test_result = result.get("test_result")
    if test_result is not None:
        st.subheader("Test Result")
        st.json(test_result)

    st.subheader("Critique")
    st.json(result.get("critique", {}))


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="AgentOps Copilot", layout="wide")
    st.title("AgentOps Copilot")

    with st.sidebar:
        st.header("Backend")
        api_base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)
        repo_mode = st.radio(
            "Repository source",
            ["Analyze local path", "Upload repo zip"],
        )

        repo_path = "."
        if repo_mode == "Analyze local path":
            repo_path = st.text_input("Repo path", value=".")
        else:
            st.info(
                "Large zips are supported up to 1000 MB, but indexing may be slow. "
                "For best results, remove .git, node_modules, .venv, dist, build, "
                "and other generated folders before zipping."
            )
            uploaded_file = st.file_uploader("Upload repository zip", type=["zip"])
            if st.button("Upload Repository", use_container_width=True):
                if uploaded_file is None:
                    st.warning("Choose a .zip file first.")
                else:
                    with st.spinner("Uploading repository..."):
                        try:
                            result = upload_repo_zip(api_base_url, uploaded_file)
                            st.session_state.pop("indexed_selection", None)
                            st.session_state.pop("agent_result", None)
                            st.session_state["repo_id"] = result["repo_id"]
                            st.session_state["repo_path"] = result["repo_path"]
                            st.success(f"Uploaded repo_id: {result['repo_id']}")
                        except requests.RequestException as error:
                            st.error(f"Upload failed: {error}")

            if st.session_state.get("repo_id"):
                st.caption(f"repo_id: {st.session_state['repo_id']}")
                st.caption(f"repo_path: {st.session_state.get('repo_path', '')}")

        selection = (
            api_base_url,
            repo_mode,
            tuple(get_repo_payload(repo_mode, repo_path).items()),
        )
        if st.button("Index Repository", use_container_width=True):
            st.session_state.pop("indexed_selection", None)
            st.session_state.pop("agent_result", None)
            with st.spinner("Indexing repository..."):
                try:
                    repo_payload = get_repo_payload(repo_mode, repo_path)
                    if not repo_payload:
                        st.warning("Upload a repository zip before indexing.")
                        return
                    result = post_json(
                        api_base_url,
                        "/index",
                        repo_payload,
                    )
                    st.session_state["indexed_selection"] = selection
                    st.success(
                        "Repository indexed and set as active context. "
                        f"Indexed {result['indexed_chunks']} chunks."
                    )
                except requests.RequestException as error:
                    st.error(f"Indexing failed: {error}")

    question = st.text_area(
        "User question",
        height=140,
        placeholder="Ask about the repo, API, bug, tests, architecture, or docs...",
    )

    simulate_pr = st.checkbox(
        "Simulation only (skip test execution)",
        help="Every response includes a simulated PR. Enable this to prevent "
        "test execution even when the question requests it.",
    )
    indexed = st.session_state.get("indexed_selection") == selection
    if not indexed:
        st.info("Upload or select a repository, then index it before asking.")
    if st.button("Ask Agent", type="primary", disabled=not indexed):
        if not question.strip():
            st.warning("Enter a question first.")
            return

        with st.spinner("Asking AgentOps Copilot..."):
            try:
                repo_payload = get_repo_payload(repo_mode, repo_path)
                if not repo_payload:
                    st.warning("Upload a repository zip before asking.")
                    return
                result = post_json(
                    api_base_url,
                    "/ask",
                    {
                        "question": question,
                        "simulate_pr": simulate_pr,
                        **repo_payload,
                    },
                )
                st.session_state["agent_result"] = (selection, result)
            except requests.RequestException as error:
                st.error(f"Agent request failed: {error}")

    saved_result = st.session_state.get("agent_result")
    if saved_result and saved_result[0] == selection:
        render_agent_response(saved_result[1])


if __name__ == "__main__":
    main()
