---
name: phase-implement
description: Implement a scoped EchoApp feature or phase with explicit boundaries and verification.
argument-hint: Provide the feature goal, boundaries, and done-when criteria.
agent: agent
---

Implement the requested EchoApp change end to end.

Repository-specific rules:

- Read [README.md](../../README.md) first for product and folder conventions.
- Read [TASK_HUB.md](../../TASK_HUB.md) before substantial task work so active ideas, problems, and follow-up items stay aligned with the repo-visible backlog.
- Reuse existing project patterns and modules before adding new structures.
- Keep end-user install and launcher behavior coherent with repo-root scripts.
- If the work touches Home-tab or playback UI, verify the live tabbed window path in [echo_pro_app.py](../../echo_pro_app.py) before editing and keep any parallel base-window path aligned only when needed.
- Keep developer-only utilities out of general end-user UI surfaces unless the request explicitly asks for exposed developer tooling.
- If persistence changes are required, update both load and save behavior together.
- If launch or runtime bootstrap behavior changes, preserve the runtime path expectations in [app_paths.py](../../app_paths.py), including `ECHO_PRO_HOME`.
- If the work touches recording, timeline, mixer, playback, or runtime bootstrap behavior, look for existing related helpers before adding new logic.

Execution checklist:

1. Restate the goal, boundaries, and done-when criteria briefly.
2. Inspect the relevant code paths before editing.
3. Make the minimum complete set of changes needed across all affected surfaces.
4. Run the most relevant existing validation:
   - targeted tests when available
   - the existing repo task(s) when relevant
   - for launcher/startup work, verify the live app surface or runtime assets, not just process start
5. Summarize:
   - files changed
   - checks run
   - remaining manual validation recommended

Do not widen scope to unrelated cleanup unless it is required to make the requested change work correctly.
