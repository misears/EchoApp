---
applyTo: "**"
---

# EchoApp / Echo Pro working instructions

- Treat this repository as a local desktop audio production app, not a web service. Prioritize stable user workflows for waveform editing, recording, stem separation, voice conversion, music generation, installers, and portable/runtime setup.
- Prefer the existing Python + PySide6 architecture and reuse current modules before adding new ones. Shared UI belongs under [app/](../app/), while the main application flow still lives in [echo_pro_app.py](../echo_pro_app.py).
- Verify the active app entrypoint before editing UI flows. Echo Pro launches through the tabbed window path in [echo_pro_app.py](../echo_pro_app.py), so Home-tab and playback UI work must target the live `TabbedEchoProWindow` path or keep any parallel base-window path explicitly aligned.
- Follow the current project organization described in [README.md](../README.md): end-user launch/install files stay at repo root, while development-only helpers belong under [tools/dev/](../tools/dev/).
- For task-oriented work, backlog grooming, or issue tracking, use [TASK_HUB.md](../TASK_HUB.md) as the default repo-visible source of truth for ideas, todos, problems, and recent completions. Read it before substantial task work and update it after meaningful changes. Do not default to session SQL tables for user-facing backlog state unless the user explicitly asks for session-local tracking.
- Preserve saved-project compatibility and existing user-visible workflows unless the task explicitly asks for a breaking change. If a feature needs persistence changes, update the write and read paths together.
- For feature work, identify all affected surfaces before editing: UI, project/model persistence, playback/rendering behavior, install/runtime scripts, runtime path resolution, and developer validation helpers.
- Prefer targeted, surgical changes over broad rewrites. Reuse existing widgets, dialogs, validation helpers, and project-model patterns instead of introducing parallel implementations.
- Keep Python changes type-aware and readable. Match existing naming and file layout conventions, and avoid adding speculative abstractions.
- Keep developer-only utilities out of general end-user UI surfaces unless the task explicitly asks for exposed developer tooling. Internal checks such as P5A/P5B validation belong in clearly scoped developer areas, not duplicated across user-facing tabs.
- Treat launch/runtime work as data-root-sensitive. Source launchers and bootstrap scripts must preserve the same `ECHO_PRO_HOME` and related runtime environment variables that [app_paths.py](../app_paths.py) expects so Demucs, model assets, caches, and portable/source behaviors resolve consistently.
- Use only the repo's existing validation paths. Pytest is enabled in workspace settings, and [`.vscode/tasks.json`](../.vscode/tasks.json) defines the `Run P5A Regression Checks` task. Run the most relevant existing checks for the area you changed.
- For launcher or startup changes, do not stop at "process started". Verify the real window path or active UI path, confirm the intended controls or surfaces exist in the live app, and check that required runtime assets (for example Demucs binaries/repos or model directories) are discoverable before concluding the launch flow works.
- When a request sounds like a rough backlog item, first turn it into a scoped change with:
  - the concrete user-visible behavior,
  - the boundaries of what should not change,
  - and clear "done when" verification criteria.
- In summaries, report exactly what changed, what was verified, and any follow-up risk or manual validation still recommended.
