# Streamlit Frontend

AgentOps Copilot includes a small Streamlit frontend in `ui/streamlit_app.py`. It is a local UI for the existing FastAPI backend and does not require external APIs.

## Start the Backend

Run the API on port `8010`, which is the frontend default:

```bash
python -m uvicorn app.main:app --reload --port 8010
```

## Start the Frontend

In a second terminal:

```bash
streamlit run ui/streamlit_app.py
```

## What the UI Does

The sidebar contains:

- API base URL, defaulting to `http://127.0.0.1:8010`.
- Repo path, defaulting to `.`.
- `Index Repository` button, which calls `POST /index`.

The main page contains:

- A question text area.
- `Ask Agent` button, which calls `POST /ask`.
- Rendered sections for final answer, plan, retrieved context sources, issue draft, test result, and critique.

## Local-First Behavior

The UI talks only to your local backend by default. The backend runs with deterministic local agent behavior and `MockLLM` unless optional OpenAI-compatible environment variables are configured.

## Troubleshooting

- If indexing fails, confirm the backend is running and the repo path exists.
- If asking the agent fails, confirm the API base URL matches the backend port.
- If no context appears, index the repository first.
