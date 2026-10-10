# Screenshot and Recording Guide

Capture real app output for the README preview and two-minute demo. Asset folders
are tracked with `.gitkeep`; the referenced images and GIF are intentionally
pending until you record them.

## Run the app

Complete the [local setup](../README.md#how-to-run-locally), then run these commands
from the repository root in two terminals.

Backend:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Frontend:

```bash
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

On Windows Command Prompt, replace the activation command with
`.venv\Scripts\activate`. Open the Streamlit URL printed by the frontend, usually
[localhost:8501](http://localhost:8501), and confirm the sidebar API base URL is
`http://127.0.0.1:8010`.

## Prepare the demo

Use a small repository you can show publicly. Exclude dependency folders and
private files from the ZIP. Upload it, click **Upload Repository**, and then click
**Index Repository**. Wait for the indexed-chunk confirmation before asking.
Enable **Simulation only (skip test execution)** for the recording.

Suggested demo prompt:

```text
Plan how to add a new tool integration to this repo.
```

Click **Ask Agent** and wait for the completed report. Arrange the browser so
headings, filenames, and relevant controls are legible. Avoid showing credentials,
private code, or unrelated browser tabs in public demo assets.

## Screens to capture

| Screen | What to show | Recommended file |
| --- | --- | --- |
| Upload/index sidebar | ZIP selection, upload controls, and successful indexing confirmation | `docs/assets/screenshots/upload-and-index.png` |
| Workflow report | Request summary and implementation/validation sections | `docs/assets/screenshots/workflow-report.png` |
| Retrieved context sources | Expand a source to show its path and evidence | `docs/assets/screenshots/retrieved-context.png` (optional extra) |
| Agentic PR Simulation | Title, readiness explanation, candidate files, and an expanded pseudo-diff | `docs/assets/screenshots/pr-simulator.png` |
| Markdown download button | **Download Markdown report** with the completed report visible | `docs/assets/screenshots/markdown-download.png` (optional extra) |

The README references the three main screenshots above. Include context and the
download control in those images when readable, or save the optional extra shots.
Use PNG for screenshots and keep text legible at GitHub's displayed width.

## Capture screenshots on macOS

1. Open the desired app section and move the pointer away from important text.
2. Press **Shift–Command–5** to open Screenshot controls.
3. Choose **Capture Selected Portion** and frame the relevant browser area.
4. In **Options**, choose a save location, then capture.
5. Rename the image to the expected filename and move it into
   `docs/assets/screenshots/`.

Alternatively, **Shift–Command–4** captures a selected area directly. Review each
image for readable text and accurate output before adding it to the repository.

## Record a video or GIF on macOS

1. Start backend and frontend before recording. Open the
   [two-minute speaking script](demo_script.md) for rehearsal.
2. Press **Shift–Command–5** and choose **Record Selected Portion**. In **Options**,
   select a microphone if you want narration and choose the save location.
3. Or open QuickTime Player and choose **File → New Screen Recording** to open
   the screen-recording controls.
4. Record the upload, indexing, prompt, context, report, PR simulation, and Markdown
   download. Follow the script's timing and stop using the menu-bar stop control.
5. Review and trim the recording in QuickTime. Keep a narrated video for the
   two-minute walkthrough; publish it when ready and replace **Video: Coming soon**
   in the README with its link.
6. For the README GIF, export a short, silent highlight from the recording using
   a video editor or converter with GIF export. Save it as
   `docs/assets/demo/agentops-demo.gif`.

Screenshot and QuickTime record video; they do not directly export animated GIFs.
Do not rename a `.mov` file to `.gif`. Keep the GIF focused on the core interaction,
with readable text and a modest file size. Loom or OBS Studio can also be used
for recording if already part of your workflow.

## Final asset check

Expected README paths:

```text
docs/assets/screenshots/upload-and-index.png
docs/assets/screenshots/workflow-report.png
docs/assets/screenshots/pr-simulator.png
docs/assets/demo/agentops-demo.gif
```

Preview the README after adding these assets and verify every image renders.
Only add intended public demo media; uploaded repositories, caches, local databases,
and virtual environments remain excluded. Keep large raw recordings outside Git
and link to the published video instead.
