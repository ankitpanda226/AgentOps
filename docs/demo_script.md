# AgentOps Copilot 2-Minute Demo Script

## Before recording

Follow the [local run guide](../README.md#how-to-run-locally). Start both services,
open Streamlit, and prepare a small repository ZIP. Keep the recent Pytest result
available in a terminal. Rehearse once so indexing and navigation fit the timing;
if needed, trim waiting time and disclose the edit. Enable **Simulation only
(skip test execution)** for this walkthrough.

Use this prompt exactly:

```text
Plan how to add a new tool integration to this repo.
```

## 0:00–0:15: What the project is

**Show:** the Streamlit title and repository sidebar.

**Say:** “AgentOps Copilot is a local-first multi-agent developer workflow platform.
It turns repository context into implementation plans, workflow reports, and
reviewable change proposals. I'll show how it takes a repository upload through
to a simulated pull-request plan.”

## 0:15–0:35: Upload and index repository

**Do:** select **Upload repo zip**, choose the ZIP, click **Upload Repository**, then
**Index Repository**. Point to the indexing confirmation.

**Say:** “I upload a repository ZIP and index it locally. The system chunks supported
source files and uses RAG over uploaded repositories to retrieve relevant context.
The active index stays tied to the selected repository, so the workflow can point
back to the code it used.”

## 0:35–1:05: Ask a developer workflow question

**Do:** paste the prompt, click **Ask Agent**, and expand a retrieved context source.

**Say:** “My question is: Plan how to add a new tool integration to this repo.
LangGraph-style orchestration coordinates planning, retrieval, issue drafting,
critique, and PR simulation. A deterministic Python fallback supports the same
flow. Here are the retrieved files and excerpts. These are the evidence behind
the proposal; I can inspect them before trusting the suggested implementation.”

## 1:05–1:30: Show workflow report and issue draft

**Show:** the report's implementation and validation sections, then **Issue Draft**.
Click **Download Markdown report**.

**Say:** “The workflow report turns that context into concrete implementation steps,
a validation plan, risks, and next actions. It also includes a GitHub-style issue
draft with acceptance criteria. I can download the complete Markdown report to
review or share. This produces a planning artifact without opening a GitHub issue.”

## 1:30–1:50: Show Agentic PR Simulator

**Show:** **Agentic PR Simulation**, a candidate file, an expanded pseudo-diff,
and the readiness explanation.

**Say:** “The Agentic PR Simulator adds a simulated PR plan: candidate files,
conceptual before-and-after changes, tests, risks, and reviewer questions. It
explains its merge readiness score using context, test evidence, and critique.
This score supports review; it does not approve a merge or validate an unwritten patch.”

## 1:50–2:00: Mention safety, tests, and local-first design

**Show:** the `134 passed, 1 warning` test result, then return to the app.

**Say:** “The project has 134 passing Pytest tests. Test safety blocks broad uploaded
repo runs. The simulator edits no files, opens no PRs, and needs no paid API.”

## Recording notes

- These agents are rule-based; describe the orchestration and evidence honestly.
- Tests shown here validate this project, not the proposed change in the upload.
- Keep the pointer still while explaining a result and zoom enough to read paths.
- Use the [capture guide](screenshot_guide.md) for asset filenames and recording steps.
