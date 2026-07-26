---
applyTo: "**"
---

# EchoApp / Echo Pro working instructions

- Treat this repository as a local desktop audio production app, not a web service. Prioritize stable user workflows for waveform editing, recording, stem separation, voice conversion, music generation, installers, and portable/runtime setup.
- Prefer the existing Python + PySide6 architecture and reuse current modules before adding new ones. Shared UI belongs under [app/](../app/), while the main application flow still lives in [echo_pro_app.py](../echo_pro_app.py).
- Follow the current project organization described in [README.md](../README.md): end-user launch/install files stay at repo root, while development-only helpers belong under [tools/dev/](../tools/dev/).
- Preserve saved-project compatibility and existing user-visible workflows unless the task explicitly asks for a breaking change. If a feature needs persistence changes, update the write and read paths together.
- For feature work, identify all affected surfaces before editing: UI, project/model persistence, playback/rendering behavior, install/runtime scripts, and developer validation helpers.
- Prefer targeted, surgical changes over broad rewrites. Reuse existing widgets, dialogs, validation helpers, and project-model patterns instead of introducing parallel implementations.
- Keep Python changes type-aware and readable. Match existing naming and file layout conventions, and avoid adding speculative abstractions.
- Use only the repo's existing validation paths. Pytest is enabled in workspace settings, and [`.vscode/tasks.json`](../.vscode/tasks.json) defines the `Run P5A Regression Checks` task. Run the most relevant existing checks for the area you changed.
- When a request sounds like a rough backlog item, first turn it into a scoped change with:
  - the concrete user-visible behavior,
  - the boundaries of what should not change,
  - and clear "done when" verification criteria.
- In summaries, report exactly what changed, what was verified, and any follow-up risk or manual validation still recommended.
