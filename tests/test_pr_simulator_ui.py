"""Exercise the simulation control and rendering without a running backend."""

from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from agents.supervisor import SupervisorAgent


UI_PATH = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"


def test_ui_requires_index_and_sends_simulation_flag(monkeypatch):
    result = SupervisorAgent().handle_request("Add validation", simulate_pr=True)
    post = Mock()
    post.side_effect = [
        Mock(json=lambda: {"indexed_chunks": 1}),
        Mock(json=lambda: result),
    ]
    monkeypatch.setattr("requests.post", post)
    ui = AppTest.from_file(str(UI_PATH)).run()
    ask = next(button for button in ui.button if button.label == "Ask Agent")
    assert ask.disabled
    next(
        button for button in ui.button if button.label == "Index Repository"
    ).click().run()
    ui.checkbox[0].check()
    ui.text_area[0].set_value("Add validation")
    next(button for button in ui.button if button.label == "Ask Agent").click().run()
    assert not ui.exception
    assert post.call_args.kwargs["json"]["simulate_pr"] is True
    assert ui.metric[0].value == "45/100"
    assert any("Agentic PR Simulation" in heading.value for heading in ui.subheader)
    # A rerun (including a download) keeps the result without another request.
    ui.run()
    assert len(ui.metric) == 1
    assert post.call_count == 2
    # Changing repository clears visible results and requires indexing again.
    next(field for field in ui.text_input if field.label == "Repo path").set_value(
        "/another-repository"
    ).run()
    assert next(button for button in ui.button if button.label == "Ask Agent").disabled
    assert len(ui.metric) == 0


def test_ui_shows_proposal_details_and_keeps_markdown_download(monkeypatch):
    import streamlit as st

    store = Mock()
    store.search.return_value = [
        {"file_path": "app/api.py", "text": "def route(): pass", "chunk_id": 0}
    ]
    result = SupervisorAgent(vector_store=store).handle_request("Add an API endpoint")
    download = Mock(wraps=st.download_button)
    monkeypatch.setattr(st, "download_button", download)
    ui = AppTest.from_string(
        "from ui.streamlit_app import render_agent_response\n"
        f"render_agent_response({result!r})"
    ).run(timeout=15)
    assert not ui.exception
    assert ui.metric[0].value == "70/100"
    assert len(ui.dataframe) == 1
    assert any(expander.label == "Pseudo-diff: app/api.py" for expander in ui.expander)
    assert any("Retrieved excerpt" in code.value for code in ui.code)
    assert any("Proposed:" in code.value for code in ui.code)
    displayed = "\n".join(element.value for element in ui.markdown)
    for value in (
        result["pr_simulation"]["pr_title"],
        "Test plan",
        "Risk review",
        "Reviewer questions",
        result["pr_simulation"]["merge_readiness_reason"],
    ):
        assert value in displayed
    downloads = {call.args[0]: call.kwargs for call in download.call_args_list}
    assert "Download simulated PR (JSON)" in downloads
    markdown = downloads["Download Markdown report"]["data"]
    assert markdown.count("## Agentic PR Simulation") == 1
    assert "app/api.py" in markdown
    assert "## Critique" in markdown
